from __future__ import annotations

import base64
from dataclasses import dataclass
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Callable, Mapping
import zlib

import numpy as np

from moltrack.analysis import (
    M6DomainTypeSessionState,
    MolecularM6OrientationAnalysisSettings,
    MolecularM6SessionState,
    MolecularM6ViewSettings,
    MolecularOrientationMeasurement,
    MolecularOrientationStore,
    MolecularOrderTypeSessionState,
    MolecularStackingSessionState,
    StructuralAnalysisCacheKey,
    StructuralAnalysisCacheRecord,
    export_molecular_intensity_cache_records,
    export_structural_analysis_cache_records,
    restore_molecular_intensity_cache_records,
    restore_structural_analysis_cache_records,
)
from moltrack.analysis.sample_coordinates import MolecularSampleCoordinates
from moltrack.core import (
    MOLTRACK_SESSION_SCHEMA_VERSION,
    MolecularDetection,
    MolecularDetectionSet,
    MolecularSegmentation,
    MolecularSegmentationSet,
    MolTrackImageSeries,
    MolTrackIntensityCacheRecord,
    MolTrackRegistrationFrameResult,
    MolTrackRegistrationResultSet,
    MolTrackRegistrationSettings,
    MolTrackPositionAnalysisRange,
    MolTrackPositionAnalysisState,
    MolTrackSession,
)
from moltrack.io import load_moltrack_image_series


SeriesLoader = Callable[..., MolTrackImageSeries]
StateSaveProgressCallback = Callable[["MolTrackStateSaveProgress"], None]
_JSON_WRITE_BUFFER_CHARS = 1024 * 1024
_MAX_SEGMENTATION_PROGRESS_EVENTS = 200


@dataclass(frozen=True)
class MolTrackStateSaveProgress:
    phase: str
    completed_count: int
    total_count: int


def save_moltrack_session(
    path: str | Path,
    series: MolTrackImageSeries,
    ui_state: Any | None = None,
    *,
    progress_callback: StateSaveProgressCallback | None = None,
) -> MolTrackSession:
    """Save a MolTrack working-session descriptor as human-readable JSON."""

    if not isinstance(series, MolTrackImageSeries):
        raise TypeError("series must be a MolTrackImageSeries instance.")

    session_path = Path(path)
    source_path = Path(series.source_path).expanduser().resolve()
    source_stat = _stat_existing_source_file(source_path)
    registration_view_mode = _registration_view_mode_from_ui_state(ui_state)
    bbox_overlay_visible = _bbox_overlay_visible_from_ui_state(ui_state)
    bbox_opacity_percent = _bbox_opacity_percent_from_ui_state(ui_state)
    mask_opacity_percent = _mask_opacity_percent_from_ui_state(ui_state)
    position_analysis = _position_analysis_from_ui_state(ui_state)
    intensity_cache_records = export_molecular_intensity_cache_records(series)
    structural_cache_records = export_structural_analysis_cache_records(series)
    m6_analysis_state = _m6_analysis_state_from_ui_or_series(
        ui_state,
        series=series,
        cache_records=structural_cache_records,
    )
    m6_domain_type_analysis_state = _m6_domain_type_state_from_ui_state(ui_state)
    molecular_order_type_analysis_state = (
        _molecular_order_type_state_from_ui_state(ui_state)
    )
    session = MolTrackSession.from_image_series(
        series,
        registration_view_mode=registration_view_mode,
        bbox_overlay_visible=bbox_overlay_visible,
        bbox_opacity_percent=bbox_opacity_percent,
        mask_opacity_percent=mask_opacity_percent,
        position_analysis=position_analysis,
        intensity_cache_records=intensity_cache_records,
        m6_analysis_state=m6_analysis_state,
        m6_domain_type_analysis_state=m6_domain_type_analysis_state,
        molecular_order_type_analysis_state=(
            molecular_order_type_analysis_state
        ),
        structural_analysis_cache_records=structural_cache_records,
        source_size_bytes=source_stat.st_size,
        source_mtime_ns=source_stat.st_mtime_ns,
    )
    segmentation_count = (
        0
        if session.molecular_segmentations is None
        else session.molecular_segmentations.segmentation_count
    )
    _report_save_progress(
        progress_callback,
        phase="preparing",
        completed_count=0,
        total_count=segmentation_count,
    )
    payload = _session_to_payload(
        session,
        source_path=source_path,
        session_path=session_path,
        progress_callback=progress_callback,
    )
    session_path.parent.mkdir(parents=True, exist_ok=True)
    _report_save_progress(
        progress_callback,
        phase="writing",
        completed_count=segmentation_count,
        total_count=segmentation_count,
    )
    _write_json_atomically(session_path, payload)
    _report_save_progress(
        progress_callback,
        phase="complete",
        completed_count=segmentation_count,
        total_count=segmentation_count,
    )
    return session


def _write_json_atomically(path: Path, payload: Mapping[str, Any]) -> None:
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            encoder = json.JSONEncoder(indent=2, ensure_ascii=False)
            buffered_chunks: list[str] = []
            buffered_character_count = 0
            for chunk in encoder.iterencode(payload):
                buffered_chunks.append(chunk)
                buffered_character_count += len(chunk)
                if buffered_character_count < _JSON_WRITE_BUFFER_CHARS:
                    continue
                handle.write("".join(buffered_chunks))
                buffered_chunks.clear()
                buffered_character_count = 0
            if buffered_chunks:
                handle.write("".join(buffered_chunks))
            handle.write("\n")
        os.replace(temporary_path, path)
    except Exception:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise


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
    molecular_orientations_payload = payload.get("molecular_orientations")
    position_analysis_payload = payload.get("position_analysis")
    intensity_cache_payload = payload.get("molecular_intensity_cache", [])
    m6_analysis_payload = payload.get("molecular_m6_analysis")
    m6_analysis_state, structural_cache_records = _m6_analysis_from_payload(
        m6_analysis_payload
    )
    m6_domain_type_analysis_state = _m6_domain_type_state_from_payload(
        payload.get("m6_domain_type_analysis")
    )
    molecular_stacking_state = _molecular_stacking_state_from_payload(
        payload.get("molecular_stacking_analysis")
    )
    molecular_order_type_analysis_state = (
        _molecular_order_type_state_from_payload(
            payload.get("molecular_order_type_analysis")
        )
    )

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
    molecular_orientations = _molecular_orientations_from_payload(
        molecular_orientations_payload,
        expected_frame_count=len(working_series_payload["source_frame_indices"]),
    )

    return MolTrackSession(
        source_path=str(source_path),
        source_frame_indices=tuple(working_series_payload["source_frame_indices"]),
        active_frame_index=int(working_series_payload["active_frame_index"]),
        reverse_frame_order=bool(working_series_payload.get("reverse_frame_order", False)),
        registration_view_mode=str(ui_payload.get("registration_view_mode", "Show raw")),
        bbox_overlay_visible=bool(ui_payload.get("bbox_overlay_visible", True)),
        bbox_opacity_percent=int(ui_payload.get("bbox_opacity_percent", 100)),
        mask_opacity_percent=int(ui_payload.get("mask_opacity_percent", 30)),
        registration_settings=registration_settings,
        registration_results=registration_results,
        molecular_detections=molecular_detections,
        molecular_segmentations=molecular_segmentations,
        molecular_orientations=molecular_orientations,
        position_analysis=_position_analysis_from_payload(position_analysis_payload),
        intensity_cache_records=_intensity_cache_records_from_payload(
            intensity_cache_payload
        ),
        m6_analysis_state=m6_analysis_state,
        m6_domain_type_analysis_state=m6_domain_type_analysis_state,
        molecular_stacking_state=molecular_stacking_state,
        molecular_order_type_analysis_state=(
            molecular_order_type_analysis_state
        ),
        structural_analysis_cache_records=structural_cache_records,
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
        molecular_orientations=session.molecular_orientations,
        m6_analysis_state=session.m6_analysis_state,
        molecular_stacking_state=session.molecular_stacking_state,
        molecular_order_type_state=(
            session.molecular_order_type_analysis_state
        ),
    )
    restore_molecular_intensity_cache_records(
        restored,
        session.intensity_cache_records,
    )
    restore_structural_analysis_cache_records(
        restored,
        session.structural_analysis_cache_records,
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
    progress_callback: StateSaveProgressCallback | None = None,
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
            "bbox_overlay_visible": session.bbox_overlay_visible,
            "bbox_opacity_percent": session.bbox_opacity_percent,
            "mask_opacity_percent": session.mask_opacity_percent,
        },
        "registration": _registration_to_payload(session.registration_results),
        "molecular_detections": _molecular_detections_to_payload(session.molecular_detections),
        "molecular_segmentations": _molecular_segmentations_to_payload(
            session.molecular_segmentations,
            progress_callback=progress_callback,
        ),
        "molecular_orientations": _molecular_orientations_to_payload(
            session.molecular_orientations
        ),
        "position_analysis": _position_analysis_to_payload(session.position_analysis),
        "molecular_intensity_cache": _intensity_cache_records_to_payload(
            session.intensity_cache_records
        ),
        "molecular_m6_analysis": _m6_analysis_to_payload(
            session.m6_analysis_state,
            session.structural_analysis_cache_records,
        ),
        "m6_domain_type_analysis": (
            None
            if session.m6_domain_type_analysis_state is None
            else session.m6_domain_type_analysis_state.to_dict()
        ),
        "molecular_stacking_analysis": (
            MolecularStackingSessionState().to_dict()
            if session.molecular_stacking_state is None
            else session.molecular_stacking_state.to_dict()
        ),
        "molecular_order_type_analysis": (
            None
            if session.molecular_order_type_analysis_state is None
            else session.molecular_order_type_analysis_state.to_dict()
        ),
    }


def _molecular_stacking_state_from_payload(
    payload: Any,
) -> MolecularStackingSessionState:
    if payload is None:
        return MolecularStackingSessionState()
    try:
        return MolecularStackingSessionState.from_dict(
            _require_mapping(payload, "molecular_stacking_analysis")
        )
    except (TypeError, ValueError):
        # This reproducible cache is optional and must not block core state.
        return MolecularStackingSessionState()


def _molecular_order_type_state_from_ui_state(
    ui_state: Any | None,
) -> MolecularOrderTypeSessionState | None:
    candidate = None
    if isinstance(ui_state, Mapping):
        candidate = ui_state.get("molecular_order_type_analysis")
    elif ui_state is not None and not isinstance(ui_state, str):
        candidate = getattr(
            ui_state,
            "molecular_order_type_analysis",
            None,
        )
    if candidate is None:
        return None
    if isinstance(candidate, MolecularOrderTypeSessionState):
        return candidate
    if isinstance(candidate, Mapping):
        return MolecularOrderTypeSessionState.from_dict(candidate)
    raise TypeError(
        "molecular_order_type_analysis must be a "
        "MolecularOrderTypeSessionState or mapping."
    )


def _molecular_order_type_state_from_payload(
    payload: Any,
) -> MolecularOrderTypeSessionState | None:
    if payload is None:
        return None
    try:
        return MolecularOrderTypeSessionState.from_dict(
            _require_mapping(payload, "molecular_order_type_analysis")
        )
    except (TypeError, ValueError):
        # The derived cache is optional and must not block core session data.
        return None


def _m6_domain_type_state_from_ui_state(
    ui_state: Any | None,
) -> M6DomainTypeSessionState | None:
    candidate = None
    if isinstance(ui_state, Mapping):
        candidate = ui_state.get("m6_domain_type_analysis")
    elif ui_state is not None and not isinstance(ui_state, str):
        candidate = getattr(ui_state, "m6_domain_type_analysis", None)
    if candidate is None:
        return None
    if isinstance(candidate, M6DomainTypeSessionState):
        return candidate
    if isinstance(candidate, Mapping):
        return M6DomainTypeSessionState.from_dict(candidate)
    raise TypeError(
        "m6_domain_type_analysis must be an M6DomainTypeSessionState or mapping."
    )


def _m6_domain_type_state_from_payload(
    payload: Any,
) -> M6DomainTypeSessionState | None:
    if payload is None:
        return None
    try:
        return M6DomainTypeSessionState.from_dict(
            _require_mapping(payload, "m6_domain_type_analysis")
        )
    except (TypeError, ValueError):
        # Domain-type analysis is optional and must not block core session data.
        return None


def _m6_analysis_state_from_ui_or_series(
    ui_state: Any | None,
    *,
    series: MolTrackImageSeries,
    cache_records: tuple[StructuralAnalysisCacheRecord, ...],
) -> MolecularM6SessionState:
    candidate = None
    if isinstance(ui_state, Mapping):
        candidate = ui_state.get("molecular_m6_analysis", ui_state.get("m6_analysis"))
    elif ui_state is not None and not isinstance(ui_state, str):
        candidate = getattr(
            ui_state,
            "molecular_m6_analysis",
            getattr(ui_state, "m6_analysis", None),
        )
    if isinstance(candidate, MolecularM6SessionState):
        return candidate
    if isinstance(candidate, Mapping):
        return _m6_session_state_from_mapping(candidate)
    series_state = getattr(series, "m6_analysis_state", None)
    if isinstance(series_state, MolecularM6SessionState):
        return series_state
    if cache_records:
        latest = cache_records[-1]
        return MolecularM6SessionState(
            enabled=False,
            source_view=latest.cache_key.source_view,
            use_segmentation_centroids=(
                latest.cache_key.centroid_mode == "segmentation_preferred"
            ),
            settings=latest.settings,
        )
    return MolecularM6SessionState()


def _m6_analysis_to_payload(
    state: Any | None,
    records: tuple[Any, ...],
) -> dict[str, Any]:
    if not isinstance(state, MolecularM6SessionState):
        state = MolecularM6SessionState()
    cache_records = tuple(records)
    if not all(isinstance(record, StructuralAnalysisCacheRecord) for record in cache_records):
        raise TypeError("M6 cache records must be StructuralAnalysisCacheRecord instances.")
    view = state.view_settings
    return {
        "enabled": state.enabled,
        "source_view": state.source_view,
        "use_segmentation_centroids": state.use_segmentation_centroids,
        "settings": state.settings.to_dict(),
        "view_settings": {
            "show_domain_overlay": view.show_domain_overlay,
            "overlay_mode": view.overlay_mode,
            "show_first_shell_graph": view.show_first_shell_graph,
            "show_unassigned_points": view.show_unassigned_points,
            "overlay_opacity_percent": view.overlay_opacity_percent,
        },
        "reproducible_cache": [
            _structural_cache_record_to_payload(record) for record in cache_records
        ],
    }


def _m6_analysis_from_payload(
    payload: Any,
) -> tuple[MolecularM6SessionState, tuple[StructuralAnalysisCacheRecord, ...]]:
    if payload is None:
        return MolecularM6SessionState(), ()
    analysis_payload = _require_mapping(payload, "molecular_m6_analysis")
    state = _m6_session_state_from_mapping(analysis_payload)
    records_payload = analysis_payload.get("reproducible_cache", [])
    if not isinstance(records_payload, list):
        raise ValueError("molecular_m6_analysis.reproducible_cache must be a list.")
    records = []
    for index, item in enumerate(records_payload):
        try:
            record = _structural_cache_record_from_payload(item, index=index)
        except (KeyError, TypeError, ValueError):
            continue
        records.append(record)
    return state, tuple(records)


def _m6_session_state_from_mapping(payload: Mapping[str, Any]) -> MolecularM6SessionState:
    default_settings = MolecularM6OrientationAnalysisSettings().to_dict()
    settings_payload = _require_mapping(
        payload.get("settings", default_settings),
        "molecular_m6_analysis.settings",
    )
    settings_values = {**default_settings, **dict(settings_payload)}
    default_view = MolecularM6ViewSettings()
    view_payload = _require_mapping(
        payload.get("view_settings", {}),
        "molecular_m6_analysis.view_settings",
    )
    return MolecularM6SessionState(
        enabled=_m6_bool(payload.get("enabled", False), "enabled"),
        source_view=str(payload.get("source_view", "raw")),
        use_segmentation_centroids=_m6_bool(
            payload.get("use_segmentation_centroids", True),
            "use_segmentation_centroids",
        ),
        settings=MolecularM6OrientationAnalysisSettings.from_dict(settings_values),
        view_settings=MolecularM6ViewSettings(
            show_domain_overlay=_m6_bool(
                view_payload.get(
                    "show_domain_overlay", default_view.show_domain_overlay
                ),
                "view_settings.show_domain_overlay",
            ),
            overlay_mode=str(
                view_payload.get("overlay_mode", default_view.overlay_mode)
            ),
            show_first_shell_graph=_m6_bool(
                view_payload.get(
                    "show_first_shell_graph", default_view.show_first_shell_graph
                ),
                "view_settings.show_first_shell_graph",
            ),
            show_unassigned_points=_m6_bool(
                view_payload.get(
                    "show_unassigned_points", default_view.show_unassigned_points
                ),
                "view_settings.show_unassigned_points",
            ),
            overlay_opacity_percent=int(
                view_payload.get(
                    "overlay_opacity_percent", default_view.overlay_opacity_percent
                )
            ),
        ),
    )


def _structural_cache_record_to_payload(
    record: StructuralAnalysisCacheRecord,
) -> dict[str, Any]:
    key = record.cache_key
    sample = record.sample_coordinates
    return {
        "cache_record_schema_version": record.record_schema_version,
        "cache_key": {
            "frame_id": key.frame_id,
            "source_view": key.source_view,
            "centroid_mode": key.centroid_mode,
            "annotation_fingerprint": key.annotation_fingerprint,
            "registration_fingerprint": key.registration_fingerprint,
            "spatial_calibration_fingerprint": key.spatial_calibration_fingerprint,
            "coordinate_transform_fingerprint": key.coordinate_transform_fingerprint,
            "sample_geometry_fingerprint": key.sample_geometry_fingerprint,
            "valid_fov_fingerprint": key.valid_fov_fingerprint,
            "settings_hash": key.settings_hash,
            "algorithm_version": key.algorithm_version,
        },
        "settings": record.settings.to_dict(),
        "lattice_domain_result": (
            None
            if record.lattice_domain_result_fingerprint is None
            else {
                "schema_version": record.lattice_domain_analysis_schema_version,
                "algorithm_version": (
                    record.lattice_domain_analysis_algorithm_version
                ),
                "fingerprint": record.lattice_domain_result_fingerprint,
            }
        ),
        "sample_coordinates": {
            "frame_index": sample.frame_index,
            "source_view": sample.source_view,
            "point_source_ids": list(sample.point_source_ids),
            "point_source_kinds": list(sample.point_source_kinds),
            "point_annotation_fingerprints": list(
                sample.point_annotation_fingerprints
            ),
            "source_points_xy_px": [list(point) for point in sample.source_points_xy_px],
            "points_xy_nm": [list(point) for point in sample.points_xy_nm],
            "distance_to_valid_fov_boundary_nm": list(
                sample.distance_to_valid_fov_boundary_nm
            ),
            "valid_fov_polygon_xy_nm": [
                list(point) for point in sample.valid_fov_polygon_xy_nm
            ],
            "plot_canvas_polygon_xy_nm": [
                list(point) for point in sample.plot_canvas_polygon_xy_nm
            ],
            "window_side_lengths_nm": list(sample.window_side_lengths_nm),
            "coordinate_transform_fingerprint": (
                sample.coordinate_transform_fingerprint
            ),
            "spatial_calibration_fingerprint": (
                sample.spatial_calibration_fingerprint
            ),
            "registration_fingerprint": sample.registration_fingerprint,
            "scan_angle_deg": sample.scan_angle_deg,
            "scan_angle_missing_qc": sample.scan_angle_missing_qc,
            "coordinate_frame": sample.coordinate_frame,
            "orientation_reference": sample.orientation_reference,
        },
    }


def _structural_cache_record_from_payload(
    payload: Any,
    *,
    index: int,
) -> StructuralAnalysisCacheRecord:
    prefix = f"molecular_m6_analysis.reproducible_cache[{index}]"
    record = _require_mapping(payload, prefix)
    record_schema_version = int(record.get("cache_record_schema_version", -1))
    if record_schema_version not in {1, 2}:
        raise ValueError(f"Unsupported {prefix} schema version.")
    key_payload = _require_mapping(record.get("cache_key"), f"{prefix}.cache_key")
    settings_payload = _require_mapping(record.get("settings"), f"{prefix}.settings")
    sample_payload = _require_mapping(
        record.get("sample_coordinates"),
        f"{prefix}.sample_coordinates",
    )
    lattice_payload = record.get("lattice_domain_result")
    if record_schema_version == 1:
        lattice_payload = None
    elif lattice_payload is not None:
        lattice_payload = _require_mapping(
            lattice_payload,
            f"{prefix}.lattice_domain_result",
        )
    return StructuralAnalysisCacheRecord(
        cache_key=StructuralAnalysisCacheKey(
            frame_id=str(key_payload.get("frame_id", "")),
            source_view=str(key_payload.get("source_view", "")),
            centroid_mode=str(key_payload.get("centroid_mode", "")),
            annotation_fingerprint=str(
                key_payload.get("annotation_fingerprint", "")
            ),
            registration_fingerprint=str(
                key_payload.get("registration_fingerprint", "")
            ),
            spatial_calibration_fingerprint=str(
                key_payload.get("spatial_calibration_fingerprint", "")
            ),
            coordinate_transform_fingerprint=str(
                key_payload.get("coordinate_transform_fingerprint", "")
            ),
            sample_geometry_fingerprint=str(
                key_payload.get("sample_geometry_fingerprint", "")
            ),
            valid_fov_fingerprint=str(
                key_payload.get("valid_fov_fingerprint", "")
            ),
            settings_hash=str(key_payload.get("settings_hash", "")),
            algorithm_version=str(key_payload.get("algorithm_version", "")),
        ),
        settings=MolecularM6OrientationAnalysisSettings.from_dict(settings_payload),
        record_schema_version=record_schema_version,
        lattice_domain_analysis_schema_version=(
            None
            if lattice_payload is None
            else int(lattice_payload.get("schema_version", -1))
        ),
        lattice_domain_analysis_algorithm_version=(
            None
            if lattice_payload is None
            else str(lattice_payload.get("algorithm_version", ""))
        ),
        lattice_domain_result_fingerprint=(
            None
            if lattice_payload is None
            else str(lattice_payload.get("fingerprint", ""))
        ),
        sample_coordinates=MolecularSampleCoordinates(
            frame_index=int(sample_payload.get("frame_index", -1)),
            source_view=str(sample_payload.get("source_view", "")),
            point_source_ids=tuple(sample_payload.get("point_source_ids", ())),
            point_source_kinds=tuple(sample_payload.get("point_source_kinds", ())),
            point_annotation_fingerprints=tuple(
                sample_payload.get("point_annotation_fingerprints", ())
            ),
            source_points_xy_px=tuple(
                tuple(point)
                for point in sample_payload.get("source_points_xy_px", ())
            ),
            points_xy_nm=tuple(
                tuple(point) for point in sample_payload.get("points_xy_nm", ())
            ),
            distance_to_valid_fov_boundary_nm=tuple(
                sample_payload.get("distance_to_valid_fov_boundary_nm", ())
            ),
            valid_fov_polygon_xy_nm=tuple(
                tuple(point)
                for point in sample_payload.get("valid_fov_polygon_xy_nm", ())
            ),
            plot_canvas_polygon_xy_nm=tuple(
                tuple(point)
                for point in sample_payload.get("plot_canvas_polygon_xy_nm", ())
            ),
            window_side_lengths_nm=tuple(
                sample_payload.get("window_side_lengths_nm", ())
            ),
            coordinate_transform_fingerprint=str(
                sample_payload.get("coordinate_transform_fingerprint", "")
            ),
            spatial_calibration_fingerprint=str(
                sample_payload.get("spatial_calibration_fingerprint", "")
            ),
            registration_fingerprint=str(
                sample_payload.get("registration_fingerprint", "")
            ),
            scan_angle_deg=float(sample_payload.get("scan_angle_deg", 0.0)),
            scan_angle_missing_qc=_m6_bool(
                sample_payload.get("scan_angle_missing_qc", False),
                "reproducible_cache.sample_coordinates.scan_angle_missing_qc",
            ),
            coordinate_frame=str(
                sample_payload.get("coordinate_frame", "sample_nm")
            ),
            orientation_reference=str(
                sample_payload.get("orientation_reference", "+x_sample_axis")
            ),
        ),
    )


def _m6_bool(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"molecular_m6_analysis.{field_name} must be boolean.")
    return value


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
    *,
    progress_callback: StateSaveProgressCallback | None = None,
) -> dict[str, Any] | None:
    if segmentation_set is None:
        _report_save_progress(
            progress_callback,
            phase="segmentations",
            completed_count=0,
            total_count=0,
        )
        return None
    items: list[dict[str, Any]] = []
    total_count = segmentation_set.segmentation_count
    completed_count = 0
    progress_interval = max(
        1,
        (total_count + _MAX_SEGMENTATION_PROGRESS_EVENTS - 1)
        // _MAX_SEGMENTATION_PROGRESS_EVENTS,
    )
    _report_save_progress(
        progress_callback,
        phase="segmentations",
        completed_count=0,
        total_count=total_count,
    )
    for frame_index in range(segmentation_set.frame_count):
        for segmentation in segmentation_set.get_segmentations(frame_index):
            metadata = dict(segmentation.metadata)
            mask_payload = _mask_to_payload(
                segmentation.mask,
                bbox_xyxy=segmentation.bbox_xyxy,
            )
            original_mask_payload = _original_mask_to_payload(
                segmentation.original_mask,
                segmentation.mask,
                assume_identical=(
                    segmentation.origin == "sam2"
                    and not bool(metadata.get("edited", False))
                ),
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
                    "metadata": metadata,
                    "segmentation_id": segmentation.segmentation_id,
                }
            )
            completed_count += 1
            if completed_count == total_count or completed_count % progress_interval == 0:
                _report_save_progress(
                    progress_callback,
                    phase="segmentations",
                    completed_count=completed_count,
                    total_count=total_count,
                )
    return {
        "frame_count": segmentation_set.frame_count,
        "segmentations": items,
    }


def _report_save_progress(
    callback: StateSaveProgressCallback | None,
    *,
    phase: str,
    completed_count: int,
    total_count: int,
) -> None:
    if callback is None:
        return
    callback(
        MolTrackStateSaveProgress(
            phase=str(phase),
            completed_count=int(completed_count),
            total_count=int(total_count),
        )
    )


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


def _molecular_orientations_to_payload(
    store: object | None,
) -> dict[str, Any] | None:
    if store is None:
        return None
    if not isinstance(store, MolecularOrientationStore):
        raise TypeError(
            "molecular_orientations must be a MolecularOrientationStore."
        )
    return {
        "frame_count": store.frame_count,
        "measurements": [
            measurement.to_dict() for measurement in store.measurements
        ],
    }


def _molecular_orientations_from_payload(
    payload: Any,
    *,
    expected_frame_count: int,
) -> MolecularOrientationStore | None:
    if payload is None:
        return None
    orientation_payload = _require_mapping(
        payload,
        "molecular_orientations",
    )
    frame_count = int(orientation_payload.get("frame_count", -1))
    if frame_count != int(expected_frame_count):
        raise ValueError(
            "molecular_orientations frame_count does not match working "
            "series frame count."
        )
    raw_measurements = orientation_payload.get("measurements", [])
    if not isinstance(raw_measurements, list):
        raise ValueError(
            "molecular_orientations.measurements must be a list."
        )
    measurements = []
    for index, raw_measurement in enumerate(raw_measurements):
        measurement_payload = _require_mapping(
            raw_measurement,
            f"molecular_orientations.measurements[{index}]",
        )
        measurements.append(
            MolecularOrientationMeasurement.from_dict(measurement_payload)
        )
    return MolecularOrientationStore(
        frame_count=frame_count,
        measurements=measurements,
    )


def _mask_to_payload(mask, *, bbox_xyxy=None) -> dict[str, Any] | None:
    if mask is None:
        return None
    mask_array = np.asarray(mask, dtype=bool)
    if mask_array.ndim != 2:
        raise ValueError("molecular segmentation mask must be a 2D array.")
    crop_bounds = _mask_crop_bounds(bbox_xyxy, mask_array.shape)
    if crop_bounds is not None:
        x0, y0, x1, y1 = crop_bounds
        cropped_mask = mask_array[y0:y1, x0:x1]
        if bool(np.any(cropped_mask)):
            packed = np.packbits(cropped_mask.ravel(order="C"), bitorder="little")
            compressed = zlib.compress(packed.tobytes(), level=1)
            return {
                "encoding": "bbox-packbits-zlib-base64",
                "shape": [int(mask_array.shape[0]), int(mask_array.shape[1])],
                "bbox_xyxy": [x0, y0, x1, y1],
                "data": base64.b64encode(compressed).decode("ascii"),
            }
    packed = np.packbits(mask_array.ravel(order="C"), bitorder="little")
    compressed = zlib.compress(packed.tobytes(), level=1)
    return {
        "encoding": "packbits-zlib-base64",
        "shape": [int(mask_array.shape[0]), int(mask_array.shape[1])],
        "data": base64.b64encode(compressed).decode("ascii"),
    }


def _original_mask_to_payload(
    original_mask,
    mask,
    *,
    assume_identical: bool = False,
) -> dict[str, Any] | None:
    if original_mask is None:
        return None
    original_mask_array = np.asarray(original_mask, dtype=bool)
    if mask is not None and (
        bool(assume_identical)
        or original_mask is mask
        or np.array_equal(original_mask_array, np.asarray(mask, dtype=bool))
    ):
        return {"encoding": "same-as-mask"}
    return _mask_to_payload(
        original_mask_array,
        bbox_xyxy=_active_mask_bbox(original_mask_array),
    )


def _mask_crop_bounds(bbox_xyxy, shape: tuple[int, int]) -> tuple[int, int, int, int] | None:
    if bbox_xyxy is None:
        return None
    try:
        values = np.asarray(tuple(bbox_xyxy), dtype=np.float64)
    except (TypeError, ValueError):
        return None
    if values.shape != (4,) or not bool(np.all(np.isfinite(values))):
        return None
    height, width = (int(value) for value in shape)
    x0 = max(0, min(width, int(np.floor(values[0]))))
    y0 = max(0, min(height, int(np.floor(values[1]))))
    x1 = max(0, min(width, int(np.ceil(values[2]))))
    y1 = max(0, min(height, int(np.ceil(values[3]))))
    if x1 <= x0 or y1 <= y0:
        return None
    return x0, y0, x1, y1


def _active_mask_bbox(mask: np.ndarray) -> tuple[int, int, int, int] | None:
    active_rows = np.flatnonzero(np.any(mask, axis=1))
    active_columns = np.flatnonzero(np.any(mask, axis=0))
    if active_rows.size == 0 or active_columns.size == 0:
        return None
    return (
        int(active_columns[0]),
        int(active_rows[0]),
        int(active_columns[-1] + 1),
        int(active_rows[-1] + 1),
    )


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
    if encoding in ("packbits-zlib-base64", "bbox-packbits-zlib-base64"):
        try:
            compressed = base64.b64decode(
                str(mask_payload.get("data", "")),
                validate=True,
            )
            packed_bytes = zlib.decompress(compressed)
        except (ValueError, zlib.error) as exc:
            raise ValueError("Invalid compressed molecular segmentation mask.") from exc
        crop_bounds = None
        encoded_pixel_count = total
        if encoding == "bbox-packbits-zlib-base64":
            crop_bounds = _mask_crop_bounds(mask_payload.get("bbox_xyxy"), shape)
            if crop_bounds is None:
                raise ValueError("Compressed molecular segmentation mask has an invalid bbox_xyxy.")
            x0, y0, x1, y1 = crop_bounds
            encoded_pixel_count = (y1 - y0) * (x1 - x0)
        expected_byte_count = (encoded_pixel_count + 7) // 8
        if len(packed_bytes) != expected_byte_count:
            raise ValueError(
                "Compressed molecular segmentation mask does not match mask shape."
            )
        unpacked = np.unpackbits(
            np.frombuffer(packed_bytes, dtype=np.uint8),
            count=encoded_pixel_count,
            bitorder="little",
        )
        decoded = np.asarray(unpacked, dtype=bool)
        if crop_bounds is None:
            return decoded.reshape(shape)
        x0, y0, x1, y1 = crop_bounds
        restored = np.zeros(shape, dtype=bool)
        restored[y0:y1, x0:x1] = decoded.reshape((y1 - y0, x1 - x0))
        return restored
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


def _intensity_cache_records_to_payload(
    records: tuple[MolTrackIntensityCacheRecord, ...],
) -> list[dict[str, Any]]:
    return [
        {
            "frame_index": record.frame_index,
            "source_view": record.source_view,
            "source_kind": record.source_kind,
            "source_id": record.source_id,
            "unit": record.unit,
            "background_inner_radius_px": record.background_inner_radius_px,
            "background_outer_radius_px": record.background_outer_radius_px,
            "annotation_fingerprint": record.annotation_fingerprint,
            "pixel_count": record.pixel_count,
            "sum": record.sum,
            "mean": record.mean,
            "median": record.median,
            "max": record.max,
            "local_background_median": record.local_background_median,
            "background_corrected_mean": record.background_corrected_mean,
            "background_corrected_median": record.background_corrected_median,
        }
        for record in records
    ]


def _intensity_cache_records_from_payload(
    payload: Any,
) -> tuple[MolTrackIntensityCacheRecord, ...]:
    if payload is None:
        return ()
    if not isinstance(payload, list):
        raise ValueError("molecular_intensity_cache must be a list.")
    records = []
    for index, item in enumerate(payload):
        record = _require_mapping(item, f"molecular_intensity_cache[{index}]")
        records.append(
            MolTrackIntensityCacheRecord(
                frame_index=int(record.get("frame_index", -1)),
                source_view=str(record.get("source_view", "raw")),
                source_kind=str(record.get("source_kind", "")),
                source_id=str(record.get("source_id", "")),
                unit=str(record.get("unit", "a.u.")),
                background_inner_radius_px=int(
                    record.get("background_inner_radius_px", 1)
                ),
                background_outer_radius_px=int(
                    record.get("background_outer_radius_px", 3)
                ),
                annotation_fingerprint=str(record.get("annotation_fingerprint", "")),
                pixel_count=int(record.get("pixel_count", 0)),
                sum=_optional_float_from_payload(record.get("sum")),
                mean=_optional_float_from_payload(record.get("mean")),
                median=_optional_float_from_payload(record.get("median")),
                max=_optional_float_from_payload(record.get("max")),
                local_background_median=_optional_float_from_payload(
                    record.get("local_background_median")
                ),
                background_corrected_mean=_optional_float_from_payload(
                    record.get("background_corrected_mean")
                ),
                background_corrected_median=_optional_float_from_payload(
                    record.get("background_corrected_median")
                ),
            )
        )
    return tuple(records)


def _optional_float_from_payload(value: Any) -> float | None:
    return None if value is None else float(value)


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
        "intensity_metric": state.intensity_metric,
        "color_points_by_intensity": state.color_points_by_intensity,
        "background_inner_radius_px": state.background_inner_radius_px,
        "background_outer_radius_px": state.background_outer_radius_px,
        "shared_intensity_scale": state.shared_intensity_scale,
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
        intensity_metric=str(
            state_payload.get("intensity_metric", "background_corrected_median")
        ),
        color_points_by_intensity=bool(
            state_payload.get("color_points_by_intensity", True)
        ),
        background_inner_radius_px=int(
            state_payload.get("background_inner_radius_px", 1)
        ),
        background_outer_radius_px=int(
            state_payload.get("background_outer_radius_px", 3)
        ),
        shared_intensity_scale=bool(state_payload.get("shared_intensity_scale", True)),
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


def _bbox_overlay_visible_from_ui_state(ui_state: Any | None) -> bool:
    if ui_state is None or isinstance(ui_state, str):
        return True
    if isinstance(ui_state, Mapping):
        return bool(ui_state.get("bbox_overlay_visible", True))
    return bool(getattr(ui_state, "bbox_overlay_visible", True))


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
