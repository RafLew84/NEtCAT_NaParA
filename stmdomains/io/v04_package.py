"""Access selected v0.4 data files in a directory or ZIP without extraction."""

import csv
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
from collections.abc import Callable
from typing import Any
from zipfile import ZipFile

from stmdomains.io.moltrack_import import ImportCancelled


REQUIRED_FILES = (
    "work/expanded/metadata.json", "work/expanded/input_selected.npz", "analysis_config.json",
    "results_discovery/analysis_summary.json", "results_discovery/detections_with_domains.csv",
    "results_discovery/domains.csv", "results_discovery/frame_summary.csv",
)


class V04ImportError(ValueError):
    """The supplied result cannot be associated with the current image series."""


class ResultPackage:
    def __init__(
        self, path: Path, *, cancelled: Callable[[], bool] = lambda: False,
        image_limit: int = 512 * 1024**2,
    ) -> None:
        self.archive: ZipFile | None = None
        self.prefix = ""
        self.cancelled = cancelled
        self.image_limit = image_limit
        self._cache: dict[str, bytes] = {}
        self.root = path.parent if path.name == "MANIFEST_v04.json" else path
        if path.suffix.lower() == ".zip":
            archive = ZipFile(path)
            try:
                names = archive.namelist()
                if len(set(names)) != len(names):
                    raise V04ImportError("Powtórzone nazwy plików w archiwum wyniku.")
                manifests = [name for name in names
                             if PurePosixPath(name).name == "MANIFEST_v04.json"]
                if len(manifests) != 1:
                    raise V04ImportError("Paczka musi zawierać jeden MANIFEST_v04.json.")
                self.prefix = manifests[0][:-len("MANIFEST_v04.json")]
                self.archive = archive
            except Exception:
                archive.close()
                raise

    def __enter__(self) -> "ResultPackage":
        return self

    def __exit__(self, *args: object) -> None:
        if self.archive is not None:
            self.archive.close()

    def read(self, name: str) -> bytes:
        if self.cancelled():
            raise ImportCancelled()
        if name in self._cache:
            return self._cache[name]
        limit = self.image_limit if name.endswith(".npz") else 64 * 1024**2
        size = (self.archive.getinfo(self.prefix + name).file_size if self.archive is not None
                else (self.root / name).stat().st_size)
        if size > limit:
            raise V04ImportError(f"Plik wyniku przekracza limit odczytu: {name}.")
        stream = (self.archive.open(self.prefix + name) if self.archive is not None
                  else (self.root / name).open("rb"))
        chunks = []
        total = 0
        with stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                if self.cancelled():
                    raise ImportCancelled()
                total += len(chunk)
                if total > limit:
                    raise V04ImportError(f"Plik wyniku przekracza limit odczytu: {name}.")
                chunks.append(chunk)
        self._cache[name] = b"".join(chunks)
        return self._cache[name]

    def verify_manifest(self) -> None:
        manifest = self.json("MANIFEST_v04.json")
        if manifest.get("prototype_version") != "0.4":
            raise V04ImportError("Wymagana jest paczka wyników v0.4.")
        entries = {}
        for entry in manifest["files"]:
            name = entry["path"]
            if not isinstance(name, str) or name in entries:
                raise V04ImportError("Niepoprawne lub powtórzone wpisy manifestu.")
            entries[name] = entry
        for name in REQUIRED_FILES:
            if name not in entries:
                raise V04ImportError(f"Manifest nie zawiera wymaganego pliku: {name}.")
            data = self.read(name)
            entry = entries[name]
            if (type(entry["size_bytes"]) is not int or len(data) != entry["size_bytes"]
                    or hashlib.sha256(data).hexdigest() != entry["sha256"]):
                raise V04ImportError(f"Plik {name} nie odpowiada manifestowi wyniku.")

    def json(self, name: str) -> dict[str, Any]:
        result = json.loads(self.read(name))
        if not isinstance(result, dict):
            raise V04ImportError(f"Niepoprawny obiekt JSON: {name}.")
        return result

    def csv(self, name: str) -> list[dict[str, str]]:
        reader = csv.DictReader(io.StringIO(self.read(name).decode("utf-8-sig")))
        if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames):
            raise V04ImportError(f"Niepoprawny nagłówek CSV: {name}.")
        rows = list(reader)
        if any(None in row or any(value is None for value in row.values()) for row in rows):
            raise V04ImportError(f"Niepoprawna liczba kolumn CSV: {name}.")
        return rows
