"""Conditional publication without discarding an unconfirmed destination."""
from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import stat
import tempfile
from typing import BinaryIO, TYPE_CHECKING

if TYPE_CHECKING:
    from .session_save import SaveProgress, SessionSaveControl

GENERIC_READ = 0x80000000
DELETE_ACCESS = 0x00010000
FILE_SHARE_READ = 1
OPEN_EXISTING = 3
FILE_ATTRIBUTE_NORMAL = 0x80
FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
FILE_RENAME_INFO = 3
FILE_DISPOSITION_INFO = 4


@dataclass(frozen=True)
class TargetStamp:
    device: int
    inode: int
    size: int
    modified_ns: int

    @classmethod
    def from_stat(cls, info: os.stat_result) -> TargetStamp:
        if not stat.S_ISREG(info.st_mode):
            raise FileExistsError("Cel zapisu nie jest zwykłym plikiem; wybierz inną nazwę.")
        return cls(info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)


@dataclass(frozen=True)
class TargetFingerprint:
    stamp: TargetStamp
    sha256: str


@dataclass(frozen=True)
class SessionSaveReceipt:
    path: Path
    recovery_path: Path | None = None


class SessionSaveConflict(FileExistsError):
    def __init__(self, message: str, recovery_path: Path | None = None):
        self.recovery_path = recovery_path
        if recovery_path is not None:
            message += f"\nPoprzednia sesja jest zachowana i można ją otworzyć:\n{recovery_path}"
        super().__init__(message)


def _stamp(path: Path) -> TargetStamp | None:
    try:
        return TargetStamp.from_stat(path.lstat())
    except FileNotFoundError:
        return None


def _fingerprint(stream: BinaryIO, control: SessionSaveControl, progress: SaveProgress | None) -> TargetFingerprint:
    before = TargetStamp.from_stat(os.fstat(stream.fileno()))
    digest, done = hashlib.sha256(), 0
    control.check()
    if progress is not None:
        progress("target", 0, max(1, before.size))
    while data := stream.read(1024 * 1024):
        digest.update(data)
        done += len(data)
        control.check()
        if progress is not None:
            progress("target", done, max(1, before.size))
    control.check()
    if TargetStamp.from_stat(os.fstat(stream.fileno())) != before:
        raise SessionSaveConflict("Cel zapisu zmienił się podczas sprawdzania.")
    return TargetFingerprint(before, digest.hexdigest())


def inspect_target(path: Path, control: SessionSaveControl, progress: SaveProgress | None) -> TargetFingerprint | None:
    before = _stamp(path)
    if before is None:
        return None
    with path.open("rb") as stream:
        fingerprint = _fingerprint(stream, control, progress)
    if fingerprint.stamp != before or _stamp(path) != before:
        raise SessionSaveConflict("Cel zapisu zmienił się podczas sprawdzania.")
    return fingerprint


def _publish_new(temporary: Path, target: Path) -> SessionSaveReceipt:
    try:
        if os.name == "nt":
            os.rename(temporary, target)  # Windows refuses an existing destination.
        else:
            os.link(temporary, target)  # Same no-overwrite guarantee on POSIX.
    except FileExistsError as exc:
        raise SessionSaveConflict("Cel zapisu zmienił się; nie został zastąpiony.") from exc
    return SessionSaveReceipt(target)


def publish_session(
    temporary: Path, target: Path, expected: TargetFingerprint | None,
    control: SessionSaveControl, progress: SaveProgress | None,
) -> SessionSaveReceipt:
    if expected is None:
        return control.publish(lambda: _publish_new(temporary, target))
    if os.name != "nt":
        raise OSError("Bezpieczne nadpisanie wymaga blokady pliku Windows; zapisz pod nową nazwą.")
    with _WindowsTarget(target) as locked:
        if _fingerprint(locked.stream, control, progress) != expected or _stamp(target) != expected.stamp:
            raise SessionSaveConflict("Cel zapisu zmienił się; nie został zastąpiony.")
        return control.publish(lambda: locked.publish(temporary))


class _WindowsTarget:
    """Hold READ|DELETE on the exact file, denying other writes and renames."""

    def __init__(self, target: Path):
        import msvcrt

        self.target = target
        self.directory: Path | None = None
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                           ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        self.kernel.CreateFileW.restype = wintypes.HANDLE
        self.kernel.SetFileInformationByHandle.argtypes = [wintypes.HANDLE, ctypes.c_int,
                                                          ctypes.c_void_p, wintypes.DWORD]
        self.kernel.SetFileInformationByHandle.restype = wintypes.BOOL
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.kernel.CloseHandle.restype = wintypes.BOOL
        handle = self.kernel.CreateFileW(str(target), GENERIC_READ | DELETE_ACCESS, FILE_SHARE_READ, None,
                                         OPEN_EXISTING, FILE_FLAG_OPEN_REPARSE_POINT | FILE_ATTRIBUTE_NORMAL, None)
        if handle == ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        self.handle = handle
        try:
            self.stream = os.fdopen(msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY), "rb")
        except Exception:
            self.kernel.CloseHandle(handle)
            raise

    def __enter__(self) -> _WindowsTarget:
        return self

    def __exit__(self, *args: object) -> None:
        self.stream.close()
        if self.directory is not None:
            try:
                self.directory.rmdir()  # Only our empty recovery directory.
            except OSError:
                pass  # A retained session must never be deleted as cleanup.

    def _rename(self, path: Path) -> None:
        encoded = str(path).encode("utf-16-le")

        class RenameInfo(ctypes.Structure):
            _fields_ = [("ReplaceIfExists", wintypes.DWORD), ("RootDirectory", wintypes.HANDLE),
                        ("FileNameLength", wintypes.DWORD), ("FileName", ctypes.c_wchar * (len(encoded) // 2 + 1))]

        info = RenameInfo()
        info.ReplaceIfExists = 0
        info.FileNameLength = len(encoded)
        ctypes.memmove(ctypes.addressof(info) + RenameInfo.FileName.offset, encoded, len(encoded))
        if not self.kernel.SetFileInformationByHandle(self.handle, FILE_RENAME_INFO, ctypes.byref(info), ctypes.sizeof(info)):
            raise ctypes.WinError(ctypes.get_last_error())

    def publish(self, temporary: Path) -> SessionSaveReceipt:
        self.directory = Path(tempfile.mkdtemp(prefix=f".{self.target.name}.recovery-", dir=self.target.parent))
        backup = self.directory / "previous.nanotrack"
        self._rename(backup)
        try:
            receipt = _publish_new(temporary, self.target)
        except OSError as exc:
            try:
                self._rename(self.target)
            except OSError:
                raise SessionSaveConflict("Nie opublikowano sesji. Przywrócenie nazwy celu było niemożliwe.", backup) from exc
            raise
        # Delete our predecessor through the owned handle, with no close/unlink race.
        disposition = ctypes.c_ubyte(1)
        if not self.kernel.SetFileInformationByHandle(self.handle, FILE_DISPOSITION_INFO, ctypes.byref(disposition), ctypes.sizeof(disposition)):
            return SessionSaveReceipt(self.target, backup)
        return receipt
