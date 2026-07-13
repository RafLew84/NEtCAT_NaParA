from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Any, Callable, Mapping
import zlib

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
    MolTrackPositionAnalysisRange,
    MolTrackPositionAnalysisState,
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
    bbox_opacity_percent = _bbox_opacity_percent_from_ui_state(ui_state)
    mask_opacity_percent = _mask_opacity_percent_from_ui_state(ui_state)
    position_analysis = _position_analysis_from_ui_state(ui_state)
    session = MolTrackSession.from_image_series(
        series,
        registration_view_mode=registration_view_mode,
        bbox_opacity_percent=bbox_opacity_percent,
        mask_opacity_percent=mask_opacity_percent,
        position_analysis=position_analysis,
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
    position_analysis_payload = payload.get("position_analysis")

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
        bbox_opacity_percent=int(ui_payload.get("bbox_opacity_percent", 100)),
        mask_opacity_percent=int(ui_payload.get("mask_opacity_percent", 30)),
        registration_settings=registration_settings,
        registration_results=registration_results,
        molecular_detections=molecular_detections,
        molecular_segmentations=molecular_segmentations,
        position_analysis=_position_analysis_from_payload(position_analysis_payload),
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
            "bbox_opacity_percent": session.bbox_opacity_percent,
            "mask_opacity_percent": session.mask_opacity_percent,
        },
        "registration": _registration_to_payload(session.registration_results),
        "molecular_detections": _molecular_detections_to_payload(session.molecular_detections),
        "molecular_segmentations": _molecular_segmentations_to_payload(session.molecular_segmentations),
        "position_analysis": _position_analysis_to_payload(session.position_analysis),
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
            mask_payload = _mask_to_payload(segmentation.mask)
            original_mask_payload = _original_mask_to_payload(
                segmentation.original_mask,
                segmentation.mask,
            )
            items.append(
                {
                    "frame_index": segmentation.frame_index,
                    "source_view": segmentation.source_view,
                    "bbox_xyxy": None if segmentation.bbox_xyxy is None else list(segmentation.bbox_xyxy),
                    "mask": mask_payload,
                    "original_mask": original_mask_payload,
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
        mask = _mask_from_payload(item_payload.get("mask"))
        segmentation = MolecularSegmentation(
            frame_index=int(item_payload["frame_index"]),
            source_view=str(item_payload.get("source_view", "raw")),
            bbox_xyxy=(
                None
                if item_payload.get("bbox_xyxy") is None
                else tuple(item_payload.get("bbox_xyxy"))
            ),
            mask=mask,
            original_mask=_mask_from_payload(
                item_payload.get("original_mask"),
                reference_mask=mask,
            ),
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
    packed = np.packbits(mask_array.ravel(order="C"), bitorder="little")
    compressed = zlib.compress(packed.tobytes(), level=1)
    return {
        "encoding": "packbits-zlib-base64",
        "shape": [int(mask_array.shape[0]), int(mask_array.shape[1])],
        "data": base64.b64encode(compressed).decode("ascii"),
    }


def _original_mask_to_payload(original_mask, mask) -> dict[str, Any] | None:
    if original_mask is None:
        return None
    if mask is not None and np.array_equal(
        np.asarray(original_mask, dtype=bool),
        np.asarray(mask, dtype=bool),
    ):
        return {"encoding": "same-as-mask"}
    return _mask_to_payload(original_mask)


def _mask_from_payload(
    payload: Any,
    *,
    reference_mask: np.ndarray | None = None,
) -> np.ndarray | None:
    if payload is None:
        return None
    mask_payload = _require_mapping(payload, "molecular segmentation mask")
    encoding = str(mask_payload.get("encoding", ""))
    if encoding == "same-as-mask":
        if reference_mask is None:
            raise ValueError("same-as-mask encoding requires a decoded mask.")
        return np.asarray(reference_mask, dtype=bool).copy()
    shape = tuple(int(value) for value in mask_payload.get("shape", ()))
    if len(shape) != 2 or shape[0] <= 0 or shape[1] <= 0:
        raise ValueError("molecular segmentation mask shape must contain positive height and width.")
    total = shape[0] * shape[1]
    if encoding == "packbits-zlib-base64":
        try:
            compressed = base64.b64decode(
                str(mask_payload.get("data", "")),
                validate=True,
            )
            packed_bytes = zlib.decompress(compressed)
        except (ValueError, zlib.error) as exc:
            raise ValueError("Invalid compressed molecular segmentation mask.") from exc
        expected_byte_count = (total + 7) // 8
        if len(packed_bytes) != expected_byte_count:
            raise ValueError(
                "Compressed molecular segmentation mask does not match mask shape."
            )
        unpacked = np.unpackbits(
            np.frombuffer(packed_bytes, dtype=np.uint8),
            count=total,
            bitorder="little",
        )
        return np.asarray(unpacked, dtype=bool).reshape(shape)
    if encoding != "rle":
        raise ValueError(f"Unsupported molecular segmentation mask encoding: {encoding!r}.")
    counts = [int(value) for value in mask_payload.get("counts", [])]
    if any(count < 0 for count in counts):
        raise ValueError("molecular segmentation mask RLE counts must be non-negative.")

    if sum(counts) != total:
        raise ValueError("molecular segmentation mask RLE counts do not match mask shape.")
    values = np.arange(len(counts), dtype=np.uint8) % 2
    return np.repeat(values, np.asarray(counts, dtype=np.int64)).astype(
        bool,
        copy=False,
    ).reshape(shape)


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


def _position_analysis_to_payload(
    state: MolTrackPositionAnalysisState | None,
) -> dict[str, Any] | None:
    if state is None:
        return None
    return {
        "source_view": state.source_view,
        "first_range": _position_analysis_range_to_payload(state.first_range),
        "second_range": _position_analysis_range_to_payload(state.second_range),
        "comparison_completed": state.comparison_completed,
        "active_tab": state.active_tab,
        "density_grid_shape": list(state.density_grid_shape),
        "use_segmentation_centroids": state.use_segmentation_centroids,
    }


def _position_analysis_range_to_payload(
    frame_range: MolTrackPositionAnalysisRange,
) -> dict[str, Any]:
    return {
        "name": frame_range.name,
        "start_frame": frame_range.start_frame,
        "end_frame": frame_range.end_frame,
    }


def _position_analysis_from_payload(payload: Any) -> MolTrackPositionAnalysisState | None:
    if payload is None:
        return None
    state_payload = _require_mapping(payload, "position_analysis")
    first_payload = _require_mapping(state_payload.get("first_range"), "position_analysis.first_range")
    second_payload = _require_mapping(state_payload.get("second_range"), "position_analysis.second_range")
    return MolTrackPositionAnalysisState(
        source_view=str(state_payload.get("source_view", "raw")),
        first_range=MolTrackPositionAnalysisRange(
            name=str(first_payload.get("name", "")),
            start_frame=int(first_payload.get("start_frame", 0)),
            end_frame=int(first_payload.get("end_frame", 0)),
        ),
        second_range=MolTrackPositionAnalysisRange(
            name=str(second_payload.get("name", "")),
            start_frame=int(second_payload.get("start_frame", 0)),
            end_frame=int(second_payload.get("end_frame", 0)),
        ),
        comparison_completed=bool(state_payload.get("comparison_completed", False)),
        active_tab=str(state_payload.get("active_tab", "Current frame")),
        density_grid_shape=tuple(state_payload.get("density_grid_shape", (32, 32))),
        use_segmentation_centroids=bool(state_payload.get("use_segmentation_centroids", True)),
    )


def _position_analysis_from_ui_state(ui_state: Any | None) -> MolTrackPositionAnalysisState | None:
    if ui_state is None or isinstance(ui_state, str):
        return None
    if isinstance(ui_state, Mapping):
        payload = ui_state.get("position_analysis")
    else:
        payload = getattr(ui_state, "position_analysis", None)
    if isinstance(payload, MolTrackPositionAnalysisState):
        return payload
    return _position_analysis_from_payload(payload)


def _registration_view_mode_from_ui_state(ui_state: Any | None) -> str:
    if ui_state is None:
        return "Show raw"
    if isinstance(ui_state, str):
        return ui_state
    if isinstance(ui_state, Mapping):
        return str(ui_state.get("registration_view_mode", "Show raw"))
    return str(getattr(ui_state, "registration_view_mode", "Show raw"))


def _bbox_opacity_percent_from_ui_state(ui_state: Any | None) -> int:
    if ui_state is None or isinstance(ui_state, str):
        return 100
    if isinstance(ui_state, Mapping):
        return int(ui_state.get("bbox_opacity_percent", 100))
    return int(getattr(ui_state, "bbox_opacity_percent", 100))


def _mask_opacity_percent_from_ui_state(ui_state: Any | None) -> int:
    if ui_state is None or isinstance(ui_state, str):
        return 30
    if isinstance(ui_state, Mapping):
        return int(ui_state.get("mask_opacity_percent", 30))
    return int(getattr(ui_state, "mask_opacity_percent", 30))


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
