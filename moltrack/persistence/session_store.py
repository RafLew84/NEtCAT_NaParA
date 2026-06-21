from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable, Mapping

import numpy as np

from moltrack.core import (
    MOLTRACK_SESSION_SCHEMA_VERSION,
    MolecularDetection,
    MolecularDetectionSet,
    MolecularSegmentation,
    MolecularSegmentationSet,
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
    molecular_detections_payload = payload.get("molecular_detections")
    molecular_segmentations_payload = payload.get("molecular_segmentations")

    registration_settings: MolTrackRegistrationSettings | None = None
    registration_results: MolTrackRegistrationResultSet | None = None
    if registration_payload is not None:
        registration_settings, registration_results = _registration_from_payload(registration_payload)
    molecular_detections = _molecular_detections_from_payload(
        molecular_detections_payload,
        expected_frame_count=len(working_series_payload["source_frame_indices"]),
    )
    molecular_segmentations = _molecular_segmentations_from_payload(
        molecular_segmentations_payload,
        expected_frame_count=len(working_series_payload["source_frame_indices"]),
    )

    return MolTrackSession(
        source_path=str(source_path),
        source_frame_indices=tuple(working_series_payload["source_frame_indices"]),
        active_frame_index=int(working_series_payload["active_frame_index"]),
        reverse_frame_order=bool(working_series_payload.get("reverse_frame_order", False)),
        registration_view_mode=str(ui_payload.get("registration_view_mode", "Show raw")),
        registration_settings=registration_settings,
        registration_results=registration_results,
        molecular_detections=molecular_detections,
        molecular_segmentations=molecular_segmentations,
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
        molecular_detections=session.molecular_detections,
        molecular_segmentations=session.molecular_segmentations,
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
        "molecular_detections": _molecular_detections_to_payload(session.molecular_detections),
        "molecular_segmentations": _molecular_segmentations_to_payload(session.molecular_segmentations),
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


def _molecular_detections_to_payload(detection_set: MolecularDetectionSet | None) -> dict[str, Any] | None:
    if detection_set is None:
        return None
    items: list[dict[str, Any]] = []
    for frame_index in range(detection_set.frame_count):
        for detection in detection_set.get_detections(frame_index):
            items.append(
                {
                    "frame_index": detection.frame_index,
                    "bbox_xyxy": list(detection.bbox_xyxy),
                    "original_bbox_xyxy": list(detection.original_bbox_xyxy),
                    "confidence": detection.confidence,
                    "selected": detection.selected,
                    "model_name": detection.model_name,
                    "checkpoint_path": detection.checkpoint_path,
                    "source_view": detection.source_view,
                    "detection_id": detection.detection_id,
                    "origin": detection.origin,
                }
            )
    return {
        "frame_count": detection_set.frame_count,
        "detections": items,
    }


def _molecular_detections_from_payload(
    payload: Any,
    *,
    expected_frame_count: int,
) -> MolecularDetectionSet | None:
    if payload is None:
        return None
    detections_payload = _require_mapping(payload, "molecular_detections")
    frame_count = int(detections_payload["frame_count"])
    if frame_count != int(expected_frame_count):
        raise ValueError("molecular_detections frame_count does not match working series frame count.")
    items = detections_payload.get("detections", [])
    if not isinstance(items, list):
        raise ValueError("molecular_detections.detections must be a list.")

    detection_set = MolecularDetectionSet(frame_count=frame_count)
    detections_by_frame_and_view: dict[tuple[int, str], list[MolecularDetection]] = {}
    for item in items:
        item_payload = _require_mapping(item, "molecular detection")
        bbox_xyxy = tuple(item_payload["bbox_xyxy"])
        detection = MolecularDetection(
            frame_index=int(item_payload["frame_index"]),
            bbox_xyxy=bbox_xyxy,
            original_bbox_xyxy=tuple(item_payload.get("original_bbox_xyxy", bbox_xyxy)),
            confidence=float(item_payload["confidence"]),
            selected=bool(item_payload.get("selected", True)),
            model_name=str(item_payload.get("model_name", "")),
            checkpoint_path=str(item_payload.get("checkpoint_path", "")),
            source_view=str(item_payload.get("source_view", "raw")),
            detection_id=item_payload.get("detection_id"),
            origin=item_payload.get("origin"),
        )
        detections_by_frame_and_view.setdefault((detection.frame_index, detection.source_view), []).append(detection)

    for (frame_index, source_view), detections in detections_by_frame_and_view.items():
        detection_set.set_detections(frame_index, detections, source_view=source_view)
    return detection_set


def _molecular_segmentations_to_payload(
    segmentation_set: MolecularSegmentationSet | None,
) -> dict[str, Any] | None:
    if segmentation_set is None:
        return None
    items: list[dict[str, Any]] = []
    for frame_index in range(segmentation_set.frame_count):
        for segmentation in segmentation_set.get_segmentations(frame_index):
            items.append(
                {
                    "frame_index": segmentation.frame_index,
                    "source_view": segmentation.source_view,
                    "bbox_xyxy": None if segmentation.bbox_xyxy is None else list(segmentation.bbox_xyxy),
                    "mask": _mask_to_payload(segmentation.mask),
                    "polygon_xy": _polygon_to_payload(segmentation.polygon_xy),
                    "score": segmentation.score,
                    "origin": segmentation.origin,
                    "prompt_detection_ids": list(segmentation.prompt_detection_ids),
                    "model_name": segmentation.model_name,
                    "metadata": dict(segmentation.metadata),
                    "segmentation_id": segmentation.segmentation_id,
                }
            )
    return {
        "frame_count": segmentation_set.frame_count,
        "segmentations": items,
    }


def _molecular_segmentations_from_payload(
    payload: Any,
    *,
    expected_frame_count: int,
) -> MolecularSegmentationSet | None:
    if payload is None:
        return None
    segmentations_payload = _require_mapping(payload, "molecular_segmentations")
    frame_count = int(segmentations_payload["frame_count"])
    if frame_count != int(expected_frame_count):
        raise ValueError("molecular_segmentations frame_count does not match working series frame count.")
    items = segmentations_payload.get("segmentations", [])
    if not isinstance(items, list):
        raise ValueError("molecular_segmentations.segmentations must be a list.")

    segmentation_set = MolecularSegmentationSet(frame_count=frame_count)
    for item in items:
        item_payload = _require_mapping(item, "molecular segmentation")
        segmentation = MolecularSegmentation(
            frame_index=int(item_payload["frame_index"]),
            source_view=str(item_payload.get("source_view", "raw")),
            bbox_xyxy=(
                None
                if item_payload.get("bbox_xyxy") is None
                else tuple(item_payload.get("bbox_xyxy"))
            ),
            mask=_mask_from_payload(item_payload.get("mask")),
            polygon_xy=_polygon_from_payload(item_payload.get("polygon_xy")),
            score=item_payload.get("score"),
            origin=str(item_payload.get("origin", "manual")),
            prompt_detection_ids=tuple(item_payload.get("prompt_detection_ids", ())),
            model_name=str(item_payload.get("model_name", "")),
            metadata=dict(item_payload.get("metadata", {})),
            segmentation_id=item_payload.get("segmentation_id"),
        )
        segmentation_set.add_segmentation(segmentation)
    return segmentation_set


def _mask_to_payload(mask) -> dict[str, Any] | None:
    if mask is None:
        return None
    mask_array = np.asarray(mask, dtype=bool)
    if mask_array.ndim != 2:
        raise ValueError("molecular segmentation mask must be a 2D array.")
    flat = mask_array.ravel(order="C")
    counts: list[int] = []
    expected_value = False
    run_length = 0
    for value in flat:
        value = bool(value)
        if value == expected_value:
            run_length += 1
            continue
        counts.append(run_length)
        expected_value = value
        run_length = 1
    counts.append(run_length)
    return {
        "encoding": "rle",
        "shape": [int(mask_array.shape[0]), int(mask_array.shape[1])],
        "counts": counts,
    }


def _mask_from_payload(payload: Any) -> np.ndarray | None:
    if payload is None:
        return None
    mask_payload = _require_mapping(payload, "molecular segmentation mask")
    encoding = str(mask_payload.get("encoding", ""))
    if encoding != "rle":
        raise ValueError(f"Unsupported molecular segmentation mask encoding: {encoding!r}.")
    shape = tuple(int(value) for value in mask_payload.get("shape", ()))
    if len(shape) != 2 or shape[0] <= 0 or shape[1] <= 0:
        raise ValueError("molecular segmentation mask shape must contain positive height and width.")
    counts = [int(value) for value in mask_payload.get("counts", [])]
    if any(count < 0 for count in counts):
        raise ValueError("molecular segmentation mask RLE counts must be non-negative.")

    total = shape[0] * shape[1]
    values: list[bool] = []
    current_value = False
    for count in counts:
        values.extend([current_value] * count)
        current_value = not current_value
    if len(values) != total:
        raise ValueError("molecular segmentation mask RLE counts do not match mask shape.")
    return np.asarray(values, dtype=bool).reshape(shape)


def _polygon_to_payload(polygon_xy) -> list[list[float]] | None:
    if polygon_xy is None:
        return None
    return [[float(x), float(y)] for x, y in polygon_xy]


def _polygon_from_payload(payload: Any) -> tuple[tuple[float, float], ...] | None:
    if payload is None:
        return None
    if not isinstance(payload, list):
        raise ValueError("molecular segmentation polygon_xy must be a list.")
    return tuple((float(point[0]), float(point[1])) for point in payload)


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
