from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable, Mapping

import numpy as np

from moltrack.core import (
    MOLTRACK_SESSION_SCHEMA_VERSION,
    MolTrackImageSeries,
    MolTrackRegistrationFrameResult,
    MolTrackRegistrationResultSet,
    MolTrackRegistrationSettings,
    MolTrackSession,
)
from moltrack.io import load_moltrack_image_series


SeriesLoader = Callable[..., MolTrackImageSeries]


def save_moltrack_session(path: str | Path, series: MolTrackImageSeries, ui_state: Any | None = None) -> MolTrackSession:
    """Save a MolTrack working-session descriptor as human-readable JSON."""

    if not isinstance(series, MolTrackImageSeries):
        raise TypeError("series must be a MolTrackImageSeries instance.")

    session_path = Path(path)
    source_path = Path(series.source_path).expanduser().resolve()
    source_stat = _stat_existing_source_file(source_path)
    registration_view_mode = _registration_view_mode_from_ui_state(ui_state)
    session = MolTrackSession.from_image_series(
        series,
        registration_view_mode=registration_view_mode,
        source_size_bytes=source_stat.st_size,
        source_mtime_ns=source_stat.st_mtime_ns,
    )
    payload = _session_to_payload(
        session,
        source_path=source_path,
        session_path=session_path,
    )
    session_path.parent.mkdir(parents=True, exist_ok=True)
    session_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return session


def load_moltrack_session(path: str | Path) -> MolTrackSession:
    """Load and validate a MolTrack working-session descriptor."""

    session_path = Path(path)
    payload = json.loads(session_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("MolTrack session file must contain a JSON object.")

    schema_version = int(payload.get("schema_version", -1))
    if schema_version != MOLTRACK_SESSION_SCHEMA_VERSION:
        raise ValueError(f"Unsupported MolTrack session schema_version: {schema_version}.")

    source_payload = _require_mapping(payload.get("source"), "source")
    source_path = _resolve_source_path(source_payload, session_path=session_path)
    source_stat = _stat_existing_source_file(source_path)
    _validate_source_file_matches_payload(source_payload, source_stat)

    working_series_payload = _require_mapping(payload.get("working_series"), "working_series")
    ui_payload = _require_mapping(payload.get("ui", {}), "ui")
    registration_payload = payload.get("registration")

    registration_settings: MolTrackRegistrationSettings | None = None
    registration_results: MolTrackRegistrationResultSet | None = None
    if registration_payload is not None:
        registration_settings, registration_results = _registration_from_payload(registration_payload)

    return MolTrackSession(
        source_path=str(source_path),
        source_frame_indices=tuple(working_series_payload["source_frame_indices"]),
        active_frame_index=int(working_series_payload["active_frame_index"]),
        reverse_frame_order=bool(working_series_payload.get("reverse_frame_order", False)),
        registration_view_mode=str(ui_payload.get("registration_view_mode", "Show raw")),
        registration_settings=registration_settings,
        registration_results=registration_results,
        source_size_bytes=int(source_payload["size_bytes"]),
        source_mtime_ns=int(source_payload["mtime_ns"]),
        schema_version=schema_version,
    )


def restore_moltrack_image_series_from_session(
    session_or_path: str | Path | MolTrackSession,
    *,
    series_loader: SeriesLoader = load_moltrack_image_series,
) -> MolTrackImageSeries:
    """Reload the source MPP and restore the saved MolTrack working series."""

    session = (
        session_or_path
        if isinstance(session_or_path, MolTrackSession)
        else load_moltrack_session(session_or_path)
    )
    loaded_series = series_loader(
        session.source_path,
        reverse_frame_order=session.reverse_frame_order,
    )
    if not isinstance(loaded_series, MolTrackImageSeries):
        raise TypeError("series_loader must return a MolTrackImageSeries instance.")

    source_index_to_loaded_position = {
        source_index: position for position, source_index in enumerate(loaded_series.source_frame_indices)
    }
    try:
        loaded_positions = [source_index_to_loaded_position[index] for index in session.source_frame_indices]
    except KeyError as exc:
        raise ValueError("session source_frame_indices are not available in the loaded source series.") from exc

    raw_frames = np.asarray(loaded_series.raw_frames)[loaded_positions].copy()
    restored = MolTrackImageSeries(
        source_path=session.source_path,
        raw_frames=raw_frames,
        metadata=loaded_series.metadata,
        active_frame_index=session.active_frame_index,
        reverse_frame_order=session.reverse_frame_order,
        source_frame_indices=session.source_frame_indices,
        registration_results=session.registration_results,
        expanded_aligned_stack=None,
    )
    if restored.registration_results is not None:
        expected = tuple(range(restored.frame_count))
        if restored.registration_results.frame_indices != expected:
            raise ValueError("registration_results do not match restored working frame count.")
    return restored


def _session_to_payload(
    session: MolTrackSession,
    *,
    source_path: Path,
    session_path: Path,
) -> dict[str, Any]:
    return {
        "schema_version": session.schema_version,
        "source": {
            "path": str(source_path),
            "path_relative_to_session": _relative_path_or_none(source_path, session_path.parent),
            "size_bytes": session.source_size_bytes,
            "mtime_ns": session.source_mtime_ns,
        },
        "working_series": {
            "source_frame_indices": list(session.source_frame_indices),
            "active_frame_index": session.active_frame_index,
            "reverse_frame_order": session.reverse_frame_order,
        },
        "ui": {
            "registration_view_mode": session.registration_view_mode,
        },
        "registration": _registration_to_payload(session.registration_results),
    }


def _registration_to_payload(result_set: MolTrackRegistrationResultSet | None) -> dict[str, Any] | None:
    if result_set is None:
        return None
    settings = result_set.settings
    return {
        "settings": {
            "backend": settings.backend,
            "reference_strategy": settings.reference_strategy,
            "registration_view": settings.registration_view,
            "backend_params": dict(settings.backend_params),
        },
        "reference_frame_index": result_set.reference_frame_index,
        "results_by_frame": [
            {
                "frame_index": result.frame_index,
                "shift_xy": [result.dx, result.dy],
                "method": result.method,
                "quality_score": result.quality_score,
                "status": result.status,
            }
            for result in result_set.results_by_frame.values()
        ],
    }


def _registration_from_payload(payload: Any) -> tuple[MolTrackRegistrationSettings, MolTrackRegistrationResultSet]:
    registration_payload = _require_mapping(payload, "registration")
    settings_payload = _require_mapping(registration_payload.get("settings"), "registration.settings")
    settings = MolTrackRegistrationSettings(
        backend=str(settings_payload.get("backend", "phase_correlation")),
        reference_strategy=str(settings_payload.get("reference_strategy", "adjacent")),
        registration_view=str(settings_payload.get("registration_view", "raw")),
        backend_params=dict(settings_payload.get("backend_params", {})),
    )
    result_items = registration_payload.get("results_by_frame", [])
    if not isinstance(result_items, list):
        raise ValueError("registration.results_by_frame must be a list.")
    results_by_frame: dict[int, MolTrackRegistrationFrameResult] = {}
    for item in result_items:
        item_payload = _require_mapping(item, "registration result")
        result = MolTrackRegistrationFrameResult(
            frame_index=int(item_payload["frame_index"]),
            shift_xy=tuple(item_payload["shift_xy"]),
            method=str(item_payload["method"]),
            quality_score=float(item_payload.get("quality_score", 0.0)),
            status=str(item_payload.get("status", "ok")),
        )
        results_by_frame[result.frame_index] = result
    result_set = MolTrackRegistrationResultSet(
        settings=settings,
        results_by_frame=results_by_frame,
        reference_frame_index=int(registration_payload.get("reference_frame_index", 0)),
    )
    return settings, result_set


def _registration_view_mode_from_ui_state(ui_state: Any | None) -> str:
    if ui_state is None:
        return "Show raw"
    if isinstance(ui_state, str):
        return ui_state
    if isinstance(ui_state, Mapping):
        return str(ui_state.get("registration_view_mode", "Show raw"))
    return str(getattr(ui_state, "registration_view_mode", "Show raw"))


def _resolve_source_path(source_payload: Mapping[str, Any], *, session_path: Path) -> Path:
    source_path = Path(str(source_payload.get("path", ""))).expanduser()
    if source_path.exists():
        return source_path.resolve()

    relative_path = source_payload.get("path_relative_to_session")
    if relative_path:
        candidate = (session_path.parent / str(relative_path)).expanduser()
        if candidate.exists():
            return candidate.resolve()

    raise FileNotFoundError(f"MolTrack source file does not exist: {source_path}")


def _validate_source_file_matches_payload(source_payload: Mapping[str, Any], source_stat: os.stat_result) -> None:
    expected_size = int(source_payload["size_bytes"])
    expected_mtime_ns = int(source_payload["mtime_ns"])
    if source_stat.st_size != expected_size or source_stat.st_mtime_ns != expected_mtime_ns:
        raise ValueError("MolTrack source file metadata does not match the saved session.")


def _stat_existing_source_file(source_path: Path) -> os.stat_result:
    if not source_path.exists():
        raise FileNotFoundError(f"MolTrack source file does not exist: {source_path}")
    if not source_path.is_file():
        raise ValueError(f"MolTrack source path is not a file: {source_path}")
    return source_path.stat()


def _relative_path_or_none(path: Path, base: Path) -> str | None:
    try:
        return os.path.relpath(path, base)
    except ValueError:
        return None


def _require_mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be a JSON object.")
    return value
