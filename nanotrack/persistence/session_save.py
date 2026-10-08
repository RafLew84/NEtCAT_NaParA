"""Cancellable writing, verification and publication of a session archive."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile
import threading
from typing import Callable
import zipfile

import numpy as np
from .session_target import SessionSaveReceipt, inspect_target, publish_session

SaveProgress = Callable[[str, int, int], None]
ConfirmOverwrite = Callable[[Path], bool]
CHUNK_BYTES = 1024 * 1024


class SessionSaveCancelled(Exception):
    """The save was cancelled before publication."""


class SessionSaveControl:
    """Thread-safe cancellation with a single, irreversible publication point."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cancelled = threading.Event()
        self._published = False

    def cancel(self) -> bool:
        with self._lock:
            if self._published:
                return False
            self._cancelled.set()
            return True

    def check(self) -> None:
        if self._cancelled.is_set():
            raise SessionSaveCancelled("Zapis sesji anulowany.")

    @property
    def cancelled(self) -> bool:
        return self._cancelled.is_set()

    def publish(self, action: Callable[[], SessionSaveReceipt]) -> SessionSaveReceipt:
        with self._lock:
            self.check()
            receipt = action()
            self._published = True
            return receipt


class _Progress:
    def __init__(self, control: SessionSaveControl, callback: SaveProgress | None, stage: str, total: int):
        self.control, self.callback, self.stage = control, callback, stage
        self.total, self.done = max(total, 1), 0
        self.advance(0)

    def advance(self, count: int) -> None:
        self.control.check()
        self.done += count
        if self.callback is not None:
            self.callback(self.stage, min(self.done, self.total), self.total)
        self.control.check()


def save_archive(
    path: str, manifest: dict, assets: list[tuple[str, str, np.ndarray]], *,
    control: SessionSaveControl, progress: SaveProgress | None,
    confirm_overwrite: ConfirmOverwrite | None = None,
) -> SessionSaveReceipt:
    """Own only the temporary file; publish after every member has been read back."""
    target = Path(path).absolute()
    target.parent.mkdir(parents=True, exist_ok=True)
    expected = inspect_target(target, control, progress)
    if expected is not None and confirm_overwrite is not None and not confirm_overwrite(target):
        control.cancel()
    control.check()
    manifest_bytes = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
    descriptor, name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
    os.close(descriptor)
    temporary = Path(name)
    try:
        writing = _Progress(control, progress, "write", len(manifest_bytes) + sum(a.nbytes for _, _, a in assets))
        digests: dict[str, str] = {}
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("manifest.json", manifest_bytes)
            writing.advance(len(manifest_bytes))
            for name, key, array in assets:
                digest = hashlib.sha256()
                with archive.open(name, "w", force_zip64=True) as member:
                    # NPZ is stored inside the compressed session: compress only once.
                    with zipfile.ZipFile(member, "w", compression=zipfile.ZIP_STORED) as npz:
                        with npz.open(f"{key}.npy", "w", force_zip64=True) as numeric:
                            np.lib.format.write_array_header_1_0(numeric, {
                                "descr": np.lib.format.dtype_to_descr(array.dtype),
                                "fortran_order": False, "shape": array.shape,
                            })
                            for chunk in np.nditer(array, flags=["external_loop", "buffered", "zerosize_ok"],
                                                  op_flags=[["readonly"]], order="C",
                                                  buffersize=max(1, CHUNK_BYTES // array.itemsize)):
                                control.check()
                                data = np.asarray(chunk).tobytes()
                                numeric.write(data)
                                digest.update(data)
                                writing.advance(len(data))
                digests[name] = digest.hexdigest()
        _verify_archive(temporary, manifest_bytes, assets, digests, control, progress)
        with temporary.open("r+b") as stream:
            os.fsync(stream.fileno())
        _Progress(control, progress, "publish", 1)
        return publish_session(temporary, target, expected, control, progress)
    finally:
        temporary.unlink(missing_ok=True)


def _verify_archive(
    temporary: Path, manifest_bytes: bytes, assets: list[tuple[str, str, np.ndarray]],
    digests: dict[str, str], control: SessionSaveControl, progress: SaveProgress | None,
) -> None:
    with zipfile.ZipFile(temporary) as archive:
        expected = {"manifest.json", *(name for name, _, _ in assets)}
        if len(archive.namelist()) != len(expected) or set(archive.namelist()) != expected:
            raise ValueError("Archiwum sesji zawiera niekompletny zestaw danych.")
        verifying = _Progress(control, progress, "verify", sum(item.file_size for item in archive.infolist())
                              + sum(array.nbytes for _, _, array in assets))
        restored = archive.read("manifest.json")
        if restored != manifest_bytes or json.loads(restored).get("schema") != "nanotrack.session.v2":
            raise ValueError("Manifest zapisanej sesji jest niespójny.")
        verifying.advance(len(restored))
        for name, key, array in assets:
            # Bounded memory and cancellation while reading both ZIP layers.
            with tempfile.SpooledTemporaryFile(max_size=8 * CHUNK_BYTES) as buffer:
                with archive.open(name) as member:
                    while data := member.read(CHUNK_BYTES):
                        buffer.write(data)
                        verifying.advance(len(data))
                buffer.seek(0)
                with zipfile.ZipFile(buffer) as npz:
                    if npz.namelist() != [f"{key}.npy"]:
                        raise ValueError(f"Niekompletny zbiór liczbowy: {name}.")
                    with npz.open(f"{key}.npy") as numeric:
                        version = np.lib.format.read_magic(numeric)
                        if version != (1, 0):
                            raise ValueError(f"Niepoprawny format tablicy: {name}.")
                        shape, fortran, dtype = np.lib.format.read_array_header_1_0(numeric)
                        if shape != array.shape or dtype != array.dtype or fortran:
                            raise ValueError(f"Niepoprawna geometria lub dtype: {name}.")
                        digest = hashlib.sha256()
                        size = 0
                        while data := numeric.read(CHUNK_BYTES):
                            digest.update(data)
                            size += len(data)
                            verifying.advance(len(data))
                        if size != array.nbytes or digest.hexdigest() != digests[name]:
                            raise ValueError(f"Dane liczbowe sesji są uszkodzone: {name}.")
