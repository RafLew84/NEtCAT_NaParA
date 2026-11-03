"""Read the image subset of MolTrack without its analysis or mask loaders."""

from __future__ import annotations

import json
import hashlib
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path, PureWindowsPath
from typing import Any

import numpy as np

from nanotrack.io.mpp_loader import load_mpp_sequence
from nanotrack.core import STMSequence

from stmdomains.core.series import Series
from stmdomains.io.source_identity import source_digest


class MolTrackImportError(ValueError):
    """The session cannot describe a valid working series."""


class ImportCancelled(Exception):
    """The caller abandoned this candidate; the active series is unaffected."""


@dataclass(frozen=True)
class ImportCandidate:
    series: Series
    confirmation_reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class SourceRequest:
    message: str
    suggested_path: Path | None = None


def _read_session(path: Path) -> tuple[dict[str, Any], str]:
    try:
        contents = path.read_bytes()
        payload = json.loads(contents)
    except (OSError, UnicodeError, ValueError) as exc:
        raise MolTrackImportError(f"Nie można odczytać zapisu MolTrack: {exc}") from exc
    if not isinstance(payload, dict):
        raise MolTrackImportError("Zapis MolTrack musi być obiektem JSON.")
    version = payload.get("schema_version")
    if type(version) is not int or version not in (1, 2, 3):
        raise MolTrackImportError(f"Nieobsługiwana wersja zapisu MolTrack: {version!r}.")
    if not isinstance(payload.get("source"), dict):
        raise MolTrackImportError("Brak poprawnego opisu źródła MPP (source).")
    working = payload.get("working_series")
    if not isinstance(working, dict):
        raise MolTrackImportError("Brak poprawnego opisu serii (working_series).")
    indices = working.get("source_frame_indices")
    if not isinstance(indices, list) or not indices:
        raise MolTrackImportError("Mapa klatek źródłowych musi być niepustą listą.")
    if any(type(i) is not int or i < 0 for i in indices):
        raise MolTrackImportError("Mapa klatek wymaga nieujemnych indeksów całkowitych.")
    if len(set(indices)) != len(indices):
        raise MolTrackImportError("Mapa klatek zawiera powtórzone indeksy.")
    return payload, hashlib.sha256(contents).hexdigest()


def _source_paths(source: dict[str, Any], session_path: Path) -> list[Path]:
    paths = []
    saved = source.get("path")
    relative = source.get("path_relative_to_session")
    for value in (saved, relative):
        if value is not None and not isinstance(value, str):
            raise MolTrackImportError("Ścieżka źródła musi być tekstem lub wartością null.")
    if saved and not PureWindowsPath(saved).drive:
        path = Path(saved).expanduser()
        paths.append(path if path.is_absolute() else session_path.parent / path)
    if relative:
        paths.append(session_path.parent / relative.replace("\\", "/"))
    if saved:
        paths.append(session_path.parent / PureWindowsPath(saved).name)
    return list(dict.fromkeys(path.resolve() for path in paths))


def _source_metadata(source: dict[str, Any]) -> tuple[int | None, int | None]:
    values = []
    for field in ("size_bytes", "mtime_ns"):
        value = source.get(field)
        if value is not None and (type(value) is not int or value < 0):
            raise MolTrackImportError(f"Niepoprawna metadana źródła: {field}.")
        values.append(value)
    return values[0], values[1]


def _load_source(
    path: Path, source: dict[str, Any], indices: tuple[int, ...],
) -> tuple[STMSequence, tuple[str, ...]]:
    size, mtime = _source_metadata(source)
    if path.suffix.lower() != ".mpp":
        raise ValueError("Wymagany jest pojedynczy plik MPP.")
    before = path.stat()
    if not path.is_file():
        raise ValueError("Wskazana ścieżka nie jest plikiem.")
    if size is not None and before.st_size != size:
        raise ValueError("Rozmiar pliku w bajtach nie zgadza się z zapisem MolTrack.")
    sequence = load_mpp_sequence(str(path), reverse_frame_order=False)
    if max(indices) >= sequence.frame_count:
        raise ValueError("MPP nie zawiera wszystkich wymaganych klatek źródłowych.")
    expected_shape = source.get("frame_shape_hw")
    if expected_shape is not None:
        if (not isinstance(expected_shape, list) or len(expected_shape) != 2
                or any(type(n) is not int or n <= 0 for n in expected_shape)):
            raise MolTrackImportError("Niepoprawna zadeklarowana geometria źródła frame_shape_hw.")
        if tuple(expected_shape) != sequence.frame_shape:
            raise ValueError("Wymiary obrazów MPP nie zgadzają się z zapisaną geometrią źródła.")
    after = path.stat()
    if (after.st_size, after.st_mtime_ns) != (before.st_size, before.st_mtime_ns):
        raise ValueError("Plik MPP zmienił się w trakcie odczytu; otwórz go ponownie.")
    reasons = () if mtime is None or mtime == before.st_mtime_ns else (
        "Zmieniona data modyfikacji MPP względem zapisu MolTrack. "
        "Pozostałe dostępne kontrole źródła są zgodne. Potwierdź użycie tego pliku.",
    )
    return sequence, reasons


def _series_from_source(
    session_path: Path, source_path: Path, payload: dict[str, Any], sequence: STMSequence,
) -> Series:
    indices = tuple(payload["working_series"]["source_frame_indices"])
    active = payload["working_series"].get("active_frame_index")
    diagnostics = []
    if type(active) is not int or not 0 <= active < len(indices):
        active = 0
        diagnostics.append("Brak poprawnego numeru aktywnej klatki; pokazano pierwszą klatkę serii.")
    source = payload["source"]
    metadata_names = {
        "size_bytes": "rozmiaru pliku", "mtime_ns": "daty modyfikacji",
        "frame_shape_hw": "wymiarów obrazów",
    }
    missing = [label for name, label in metadata_names.items() if source.get(name) is None]
    if missing:
        diagnostics.append("Niepełna weryfikacja źródła — w zapisie brak: " + ", ".join(missing) + ".")
    diagnostics.append("Kalibracja fizyczna niepotwierdzona; współrzędne obrazu są w px.")
    times = sequence.metadata.frame_times_s
    source_times = None
    if (times is not None and np.isfinite(times).all() and not np.all(times == 0)
            and (len(times) == 1 or np.all(np.diff(times) > 0))):
        source_times = tuple(float(t) for t in times)
    else:
        diagnostics.append("Czas klatek nieznany lub zastępczy; używaj numerów klatek.")
    sequence.raw_frames.setflags(write=False)
    return Series(
        session_path=session_path,
        source_path=source_path,
        source_frame_indices=indices,
        active_frame_index=active,
        raw_frames=sequence.raw_frames,
        diagnostics=tuple(diagnostics),
        raw_payload=payload,
        raw_header=sequence.metadata.raw_header,
        source_times_s=source_times,
    )


def _checkpoint(
    cancelled: Callable[[], bool] | None,
    progress: Callable[[str], None] | None = None,
    message: str = "",
) -> None:
    if cancelled is not None and cancelled():
        raise ImportCancelled()
    if message and progress is not None:
        progress(message)
    if cancelled is not None and cancelled():
        raise ImportCancelled()


def prepare_import(
    session_path: str | Path,
    source_override: str | Path | None = None,
    *,
    cancelled: Callable[[], bool] | None = None,
    progress: Callable[[str], None] | None = None,
) -> ImportCandidate | SourceRequest:
    _checkpoint(cancelled, progress, "Odczyt zapisu MolTrack…")
    session_path = Path(session_path).resolve()
    payload, session_sha256 = _read_session(session_path)
    _checkpoint(cancelled)
    indices = tuple(payload["working_series"]["source_frame_indices"])
    source = payload["source"]
    _source_metadata(source)
    paths = _source_paths(source, session_path)
    if source_override is not None:
        paths = [Path(source_override).expanduser().resolve()]
    failures = []
    for source_path in paths:
        _checkpoint(cancelled, progress, f"Odczyt MPP: {source_path.name}…")
        try:
            digest = source_digest(source_path, lambda: _checkpoint(cancelled))
            sequence, reasons = _load_source(source_path, source, indices)
            if source_digest(source_path, lambda: _checkpoint(cancelled)) != digest:
                raise MolTrackImportError("MPP zmienił się podczas odczytu. Otwórz źródło ponownie.")
        except MolTrackImportError:
            raise
        except (OSError, ValueError, OverflowError) as exc:
            failures.append(f"{source_path}: {exc}")
            continue
        _checkpoint(cancelled, progress, "Przygotowanie serii…")
        series = _series_from_source(session_path, source_path, payload, sequence)
        series = replace(series, source_sha256=digest, provenance={
            "input_session_path": str(session_path), "input_session_sha256": session_sha256,
            "source_original_path": str(source_path), "source_sha256_at_import": digest,
            "adapter": "moltrack-1", "source_confirmation_reasons": list(reasons),
            "historical_source_hash_available": False,
        })
        _checkpoint(cancelled)
        return ImportCandidate(series, reasons)
    _checkpoint(cancelled)
    message = "Nie znaleziono zgodnego źródła. Wskaż plik MPP powiązany z tym zapisem."
    if failures:
        message += "\n" + "\n".join(failures)
    return SourceRequest(message, paths[-1] if paths else None)
