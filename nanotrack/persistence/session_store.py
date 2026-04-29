"""Save/load helpers for NanoTrack project sessions."""

from __future__ import annotations

import io
import json
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path, PureWindowsPath
from typing import Callable

import numpy as np

from nanotrack.core import (
    AnnotationSource,
    BBoxXYXY,
    EdgeAnnotationSource,
    EdgeFrameAnnotation,
    EdgeGeometryQuality,
    EdgeMetrics,
    EdgeTrack,
    FrameVisibility,
    ParticleMetrics,
    ParticleTrack,
    PolygonROI,
    RegistrationFrameResult,
    RegistrationResultSet,
    RegistrationSettings,
    STMSequence,
    TrackFrameAnnotation,
    TrackQuality,
    YoloDetection,
    YoloDetectionSet,
)
from nanotrack.io import FRAME_SERIES_EXTENSIONS, load_stm_sequence
from nanotrack.mask_trackers.config import MaskTrackerKind

SESSION_SCHEMA = "nanotrack.session.v1"


@dataclass
class NanoTrackSessionSnapshot:
    """Serializable state of the NanoTrack main window."""

    sequence: STMSequence
    tracks: list[ParticleTrack] = field(default_factory=list)
    edge_tracks: list[EdgeTrack] = field(default_factory=list)
    yolo_detections: YoloDetectionSet | None = None
    selected_track_id: int | None = None
    selected_edge_track_id: int | None = None
    selected_mask_tracker_kind: str = MaskTrackerKind.SAM2.value
    draft_bboxes_by_frame: dict[int, BBoxXYXY] = field(default_factory=dict)
    draft_polygons_by_frame: dict[int, PolygonROI] = field(default_factory=dict)
    draft_edge_polylines_by_frame: dict[int, np.ndarray] = field(default_factory=dict)
    repair_frames: np.ndarray | None = None
    repair_params: dict[str, float | int | str] | None = None
    denoised_frames: np.ndarray | None = None
    denoised_sigma_factor: float | None = None
    show_denoised_in_viewer: bool = False
    registration_results: RegistrationResultSet | None = None


def save_session_snapshot(path: str, snapshot: NanoTrackSessionSnapshot) -> None:
    """Write a NanoTrack session to a zip-backed `.nanotrack` file."""

    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    manifest = _build_manifest(snapshot)

    with zipfile.ZipFile(output_path, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        if snapshot.repair_frames is not None:
            _write_npz(zf, "preprocessing/repair_frames.npz", frames=np.asarray(snapshot.repair_frames, dtype=np.float32))
        if snapshot.denoised_frames is not None:
            _write_npz(
                zf,
                "preprocessing/denoised_frames.npz",
                frames=np.asarray(snapshot.denoised_frames, dtype=np.float32),
            )
        for track in snapshot.tracks:
            for annotation in track.annotations.values():
                if annotation.mask is None:
                    continue
                _write_npz(
                    zf,
                    f"tracks/{track.track_id}/mask_{annotation.frame_index}.npz",
                    mask=np.asarray(annotation.mask, dtype=np.uint8),
                )
        for edge_track in snapshot.edge_tracks:
            for annotation in edge_track.annotations.values():
                if annotation.edge_mask is None:
                    continue
                _write_npz(
                    zf,
                    f"edge_tracks/{edge_track.edge_track_id}/edge_mask_{annotation.frame_index}.npz",
                    edge_mask=np.asarray(annotation.edge_mask, dtype=np.uint8),
                )


def load_session_snapshot(
    path: str,
    *,
    sequence_loader: Callable[..., STMSequence] = load_stm_sequence,
) -> NanoTrackSessionSnapshot:
    """Load a NanoTrack session from disk and reconstruct the in-memory state."""

    with zipfile.ZipFile(path, mode="r") as zf:
        manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
        if manifest.get("schema") != SESSION_SCHEMA:
            raise ValueError(f"Unsupported NanoTrack session schema: {manifest.get('schema')!r}")

        sequence_payload = manifest["sequence"]
        sequence_source = _sequence_source_for_load(sequence_payload, session_path=path)
        reverse_frame_order = bool(manifest["sequence"].get("reverse_frame_order", False))
        sequence = sequence_loader(sequence_source, reverse_frame_order=reverse_frame_order)
        for frame_index in manifest["sequence"].get("excluded_frame_indices", []):
            sequence.set_frame_excluded(int(frame_index), True)
        sequence.set_active_frame(int(manifest["sequence"]["active_frame_index"]))

        repair_frames = _read_optional_npz(zf, "preprocessing/repair_frames.npz", "frames")
        denoised_frames = _read_optional_npz(zf, "preprocessing/denoised_frames.npz", "frames")
        tracks = _restore_tracks(zf, manifest.get("tracks", []))
        edge_tracks = _restore_edge_tracks(zf, manifest.get("edge_tracks", []))
        yolo_detections = _restore_yolo_detections(manifest.get("yolo_detections"))
        registration_results = _restore_registration_result_set(manifest.get("registration_results"))
        draft_bboxes = {
            int(item["frame_index"]): _bbox_from_payload(item["bbox"])
            for item in manifest.get("draft_bboxes", [])
        }
        draft_polygons = {
            int(item["frame_index"]): PolygonROI(np.asarray(item["vertices_xy"], dtype=np.float64))
            for item in manifest.get("draft_polygons", [])
        }
        draft_edge_polylines = {
            int(item["frame_index"]): np.asarray(item["polyline_xy"], dtype=np.float64)
            for item in manifest.get("draft_edge_polylines", [])
        }

        preprocessing = manifest.get("preprocessing", {})
        return NanoTrackSessionSnapshot(
            sequence=sequence,
            tracks=tracks,
            edge_tracks=edge_tracks,
            yolo_detections=yolo_detections,
            selected_track_id=manifest.get("selected_track_id"),
            selected_edge_track_id=manifest.get("selected_edge_track_id"),
            selected_mask_tracker_kind=_normalize_mask_tracker_kind(
                manifest.get("selected_mask_tracker_kind", MaskTrackerKind.SAM2.value)
            ),
            draft_bboxes_by_frame=draft_bboxes,
            draft_polygons_by_frame=draft_polygons,
            draft_edge_polylines_by_frame=draft_edge_polylines,
            repair_frames=repair_frames,
            repair_params=preprocessing.get("repair_params"),
            denoised_frames=denoised_frames,
            denoised_sigma_factor=preprocessing.get("denoised_sigma_factor"),
            show_denoised_in_viewer=bool(manifest.get("show_denoised_in_viewer", False)),
            registration_results=registration_results,
        )


def _build_manifest(snapshot: NanoTrackSessionSnapshot) -> dict:
    return {
        "schema": SESSION_SCHEMA,
        "sequence": {
            "source_path": snapshot.sequence.source_path,
            "source_paths": _sequence_source_paths(snapshot.sequence),
            "active_frame_index": snapshot.sequence.active_frame_index,
            "reverse_frame_order": bool(snapshot.sequence.reverse_frame_order),
            "excluded_frame_indices": snapshot.sequence.sorted_excluded_frame_indices(),
        },
        "selected_track_id": snapshot.selected_track_id,
        "selected_edge_track_id": snapshot.selected_edge_track_id,
        "selected_mask_tracker_kind": _normalize_mask_tracker_kind(snapshot.selected_mask_tracker_kind),
        "show_denoised_in_viewer": bool(snapshot.show_denoised_in_viewer),
        "yolo_detections": _serialize_yolo_detections(snapshot.yolo_detections),
        "registration_results": _serialize_registration_result_set(snapshot.registration_results),
        "draft_bboxes": [
            {
                "frame_index": int(frame_index),
                "bbox": list(bbox.as_tuple()),
            }
            for frame_index, bbox in sorted(snapshot.draft_bboxes_by_frame.items())
        ],
        "draft_polygons": [
            {
                "frame_index": int(frame_index),
                "vertices_xy": polygon.as_array().tolist(),
            }
            for frame_index, polygon in sorted(snapshot.draft_polygons_by_frame.items())
        ],
        "draft_edge_polylines": [
            {
                "frame_index": int(frame_index),
                "polyline_xy": np.asarray(polyline, dtype=np.float64).tolist(),
            }
            for frame_index, polyline in sorted(snapshot.draft_edge_polylines_by_frame.items())
        ],
        "preprocessing": {
            "repair_params": snapshot.repair_params,
            "denoised_sigma_factor": snapshot.denoised_sigma_factor,
        },
        "tracks": [_serialize_track(track) for track in snapshot.tracks],
        "edge_tracks": [_serialize_edge_track(track) for track in snapshot.edge_tracks],
    }


def _sequence_source_paths(sequence: STMSequence) -> list[str]:
    source_payload = sequence.metadata.raw_header.get("NanoTrack Source", {})
    if isinstance(source_payload, dict):
        source_files = source_payload.get("source_files")
        if isinstance(source_files, list) and source_files:
            return [str(path) for path in source_files]
    return [str(sequence.source_path)]


def _sequence_source_for_load(sequence_payload: dict, *, session_path: str | Path | None = None) -> str | list[str]:
    source_paths = sequence_payload.get("source_paths")
    if isinstance(source_paths, list) and source_paths:
        normalized_paths = [str(path) for path in source_paths]
        return normalized_paths[0] if len(normalized_paths) == 1 else normalized_paths

    source_path = str(sequence_payload["source_path"])
    if Path(source_path).suffix:
        return source_path

    session_directory = None if session_path is None else Path(session_path).resolve().parent
    inferred_paths = _infer_legacy_frame_series_source_paths(source_path, fallback_directory=session_directory)
    return inferred_paths if inferred_paths is not None else source_path


def _infer_legacy_frame_series_source_paths(
    source_path: str,
    *,
    fallback_directory: Path | None = None,
) -> list[str] | None:
    """Recover source files for old sessions saved with only a synthetic series name."""

    source = Path(source_path)
    series_name = _portable_path_name(source_path)
    match = re.fullmatch(r"(?P<first_stem>.+)_series_(?P<count>\d+)_frames", series_name)
    if match is None:
        return None

    first_stem = match.group("first_stem").casefold()
    frame_count = int(match.group("count"))

    directories = [source.parent]
    if fallback_directory is not None and fallback_directory not in directories:
        directories.append(fallback_directory)

    for directory in directories:
        if not directory.is_dir():
            continue
        candidates = sorted(
            (
                path
                for path in directory.iterdir()
                if path.is_file() and path.suffix.lower() in FRAME_SERIES_EXTENSIONS
            ),
            key=_natural_path_sort_key,
        )
        start_index = next(
            (index for index, path in enumerate(candidates) if path.stem.casefold() == first_stem),
            None,
        )
        if start_index is None:
            continue
        selected = candidates[start_index : start_index + frame_count]
        if len(selected) == frame_count:
            return [str(path) for path in selected]
    return None


def _portable_path_name(path: str) -> str:
    windows_name = PureWindowsPath(path).name
    if windows_name != path:
        return windows_name
    return Path(path).name


def _natural_path_sort_key(path: Path) -> tuple:
    parts = re.split(r"(\d+)", path.name.casefold())
    return tuple(int(part) if part.isdigit() else part for part in parts)


def _serialize_registration_result_set(result_set: RegistrationResultSet | None) -> dict | None:
    if result_set is None:
        return None
    return {
        "settings": _serialize_registration_settings(result_set.settings),
        "reference_frame_index": int(result_set.reference_frame_index),
        "template_frame_indices": (
            None if result_set.template_frame_indices is None else [int(index) for index in result_set.template_frame_indices]
        ),
        "results": [
            _serialize_registration_frame_result(result_set.get_result(frame_index))
            for frame_index in result_set.frame_indices
        ],
    }


def _serialize_registration_settings(settings: RegistrationSettings) -> dict:
    return {
        "backend": settings.backend,
        "reference_strategy": settings.reference_strategy,
        "registration_view": settings.registration_view,
        "roi_mask": None if settings.roi_mask is None else np.asarray(settings.roi_mask, dtype=bool).tolist(),
        "backend_params": _json_safe(settings.backend_params),
    }


def _serialize_registration_frame_result(result: RegistrationFrameResult | None) -> dict:
    if result is None:
        raise ValueError("registration result set contains a missing frame result.")
    return {
        "frame_index": int(result.frame_index),
        "shift_xy": [float(result.dx), float(result.dy)],
        "method": result.method,
        "quality_score": float(result.quality_score),
        "phase_peak_ratio": result.phase_peak_ratio,
        "ecc_score": result.ecc_score,
        "num_inlier_tiles": result.num_inlier_tiles,
        "num_total_tiles": result.num_total_tiles,
        "median_tile_residual": result.median_tile_residual,
        "flow_mad": result.flow_mad,
        "status": result.status,
    }


def _serialize_yolo_detections(detections: YoloDetectionSet | None) -> dict | None:
    if detections is None:
        return None
    return {
        "model_name": detections.model_name,
        "source_path": detections.source_path,
        "detections_by_frame": [
            {
                "frame_index": int(frame_index),
                "detections": [
                    {
                        "bbox": list(detection.bbox.as_tuple()),
                        "confidence": detection.confidence,
                        "selected": bool(detection.selected),
                        "model_name": detection.model_name,
                    }
                    for detection in detections.get_detections(frame_index)
                ],
            }
            for frame_index in detections.frame_indices
        ],
    }


def _serialize_track(track: ParticleTrack) -> dict:
    return {
        "track_id": track.track_id,
        "seed_frame_index": track.seed_frame_index,
        "seed_bbox": list(track.seed_bbox.as_tuple()),
        "quality": track.quality.value,
        "label": track.label,
        "annotations": [_serialize_annotation(track.track_id, annotation) for annotation in track.annotations.values()],
    }


def _serialize_annotation(track_id: int, annotation: TrackFrameAnnotation) -> dict:
    bbox_payload = None if annotation.bbox is None else list(annotation.bbox.as_tuple())
    mask_path = None
    if annotation.mask is not None:
        mask_path = f"tracks/{track_id}/mask_{annotation.frame_index}.npz"
    return {
        "frame_index": annotation.frame_index,
        "bbox": bbox_payload,
        "mask_path": mask_path,
        "visibility": annotation.visibility.value,
        "source": annotation.source.value,
        "metrics": {
            "area_px": annotation.metrics.area_px,
            "perimeter_px": annotation.metrics.perimeter_px,
            "area_nm2": annotation.metrics.area_nm2,
            "perimeter_nm": annotation.metrics.perimeter_nm,
            "intensity_sum": annotation.metrics.intensity_sum,
            "intensity_mean": annotation.metrics.intensity_mean,
            "intensity_max": annotation.metrics.intensity_max,
        },
    }


def _serialize_edge_track(track: EdgeTrack) -> dict:
    return {
        "edge_track_id": track.edge_track_id,
        "seed_frame_index": track.seed_frame_index,
        "polygon_roi": track.polygon_roi.as_array().tolist(),
        "seed_polyline": np.asarray(track.seed_polyline, dtype=np.float64).tolist(),
        "quality": track.quality.value,
        "label": track.label,
        "annotations": [_serialize_edge_annotation(track.edge_track_id, annotation) for annotation in track.annotations.values()],
    }


def _serialize_edge_annotation(edge_track_id: int, annotation: EdgeFrameAnnotation) -> dict:
    polyline_payload = None if annotation.polyline is None else np.asarray(annotation.polyline, dtype=np.float64).tolist()
    edge_mask_path = None
    if annotation.edge_mask is not None:
        edge_mask_path = f"edge_tracks/{edge_track_id}/edge_mask_{annotation.frame_index}.npz"
    return {
        "frame_index": annotation.frame_index,
        "polyline_xy": polyline_payload,
        "edge_mask_path": edge_mask_path,
        "visibility": annotation.visibility.value,
        "source": annotation.source.value,
        "geometry_quality": _serialize_edge_geometry_quality(annotation.geometry_quality),
        "metrics": {
            "length_px": annotation.metrics.length_px,
            "length_nm": annotation.metrics.length_nm,
            "roughness_rms_px": annotation.metrics.roughness_rms_px,
            "roughness_rms_nm": annotation.metrics.roughness_rms_nm,
            "mean_curvature": annotation.metrics.mean_curvature,
            "max_curvature": annotation.metrics.max_curvature,
            "waviness_amplitude_px": annotation.metrics.waviness_amplitude_px,
            "waviness_amplitude_nm": annotation.metrics.waviness_amplitude_nm,
        },
    }


def _serialize_edge_geometry_quality(geometry_quality: EdgeGeometryQuality | None) -> dict | None:
    if geometry_quality is None:
        return None
    return {
        "confidence": geometry_quality.confidence,
        "review_status": geometry_quality.review_status,
        "warnings": list(geometry_quality.warnings),
        "polyline_method": geometry_quality.polyline_method,
        "extraction_mode": geometry_quality.extraction_mode,
        "method_explicit": geometry_quality.method_explicit,
        "coarse_score": geometry_quality.coarse_score,
        "refinement_score": geometry_quality.refinement_score,
        "refinement_stability": geometry_quality.refinement_stability,
        "mean_shift_px": geometry_quality.mean_shift_px,
        "refinement_mode": geometry_quality.refinement_mode,
    }


def _restore_tracks(zf: zipfile.ZipFile, tracks_payload: list[dict]) -> list[ParticleTrack]:
    tracks: list[ParticleTrack] = []
    for track_payload in tracks_payload:
        annotations: dict[int, TrackFrameAnnotation] = {}
        for annotation_payload in track_payload.get("annotations", []):
            frame_index = int(annotation_payload["frame_index"])
            bbox = None
            if annotation_payload.get("bbox") is not None:
                bbox = _bbox_from_payload(annotation_payload["bbox"])
            mask = None
            mask_path = annotation_payload.get("mask_path")
            if mask_path:
                mask = _read_optional_npz(zf, mask_path, "mask")
                if mask is not None:
                    mask = np.asarray(mask, dtype=bool)
            metrics_payload = annotation_payload.get("metrics", {})
            annotations[frame_index] = TrackFrameAnnotation(
                frame_index=frame_index,
                bbox=bbox,
                mask=mask,
                visibility=FrameVisibility(annotation_payload["visibility"]),
                source=AnnotationSource(annotation_payload["source"]),
                metrics=ParticleMetrics(
                    area_px=metrics_payload.get("area_px"),
                    perimeter_px=metrics_payload.get("perimeter_px"),
                    area_nm2=metrics_payload.get("area_nm2"),
                    perimeter_nm=metrics_payload.get("perimeter_nm"),
                    intensity_sum=metrics_payload.get("intensity_sum"),
                    intensity_mean=metrics_payload.get("intensity_mean"),
                    intensity_max=metrics_payload.get("intensity_max"),
                ),
            )
        tracks.append(
            ParticleTrack(
                track_id=int(track_payload["track_id"]),
                seed_frame_index=int(track_payload["seed_frame_index"]),
                seed_bbox=_bbox_from_payload(track_payload["seed_bbox"]),
                annotations=annotations,
                quality=TrackQuality(track_payload.get("quality", TrackQuality.UNREVIEWED.value)),
                label=track_payload.get("label"),
            )
        )
    return tracks


def _restore_edge_tracks(zf: zipfile.ZipFile, tracks_payload: list[dict]) -> list[EdgeTrack]:
    tracks: list[EdgeTrack] = []
    for track_payload in tracks_payload:
        annotations: dict[int, EdgeFrameAnnotation] = {}
        for annotation_payload in track_payload.get("annotations", []):
            frame_index = int(annotation_payload["frame_index"])
            polyline = annotation_payload.get("polyline_xy")
            if polyline is not None:
                polyline = np.asarray(polyline, dtype=np.float64)
            edge_mask = None
            edge_mask_path = annotation_payload.get("edge_mask_path")
            if edge_mask_path:
                edge_mask = _read_optional_npz(zf, edge_mask_path, "edge_mask")
                if edge_mask is not None:
                    edge_mask = np.asarray(edge_mask, dtype=bool)
            metrics_payload = annotation_payload.get("metrics", {})
            geometry_quality_payload = annotation_payload.get("geometry_quality")
            annotations[frame_index] = EdgeFrameAnnotation(
                frame_index=frame_index,
                polyline=polyline,
                edge_mask=edge_mask,
                visibility=FrameVisibility(annotation_payload["visibility"]),
                source=EdgeAnnotationSource(annotation_payload["source"]),
                metrics=EdgeMetrics(
                    length_px=metrics_payload.get("length_px"),
                    length_nm=metrics_payload.get("length_nm"),
                    roughness_rms_px=metrics_payload.get("roughness_rms_px"),
                    roughness_rms_nm=metrics_payload.get("roughness_rms_nm"),
                    mean_curvature=metrics_payload.get("mean_curvature"),
                    max_curvature=metrics_payload.get("max_curvature"),
                    waviness_amplitude_px=metrics_payload.get("waviness_amplitude_px"),
                    waviness_amplitude_nm=metrics_payload.get("waviness_amplitude_nm"),
                ),
                geometry_quality=_restore_edge_geometry_quality(geometry_quality_payload),
            )
        tracks.append(
            EdgeTrack(
                edge_track_id=int(track_payload["edge_track_id"]),
                seed_frame_index=int(track_payload["seed_frame_index"]),
                polygon_roi=PolygonROI(np.asarray(track_payload["polygon_roi"], dtype=np.float64)),
                seed_polyline=np.asarray(track_payload["seed_polyline"], dtype=np.float64),
                annotations=annotations,
                quality=TrackQuality(track_payload.get("quality", TrackQuality.UNREVIEWED.value)),
                label=track_payload.get("label"),
            )
        )
    return tracks


def _restore_edge_geometry_quality(payload: dict | None) -> EdgeGeometryQuality | None:
    if not payload:
        return None
    return EdgeGeometryQuality(
        confidence=float(payload.get("confidence", 0.0)),
        review_status=str(payload.get("review_status", "needs_review")),
        warnings=tuple(str(warning) for warning in payload.get("warnings", [])),
        polyline_method=str(payload.get("polyline_method", "")),
        extraction_mode=str(payload.get("extraction_mode", "")),
        method_explicit=bool(payload.get("method_explicit", True)),
        coarse_score=float(payload.get("coarse_score", 0.0)),
        refinement_score=float(payload.get("refinement_score", 0.0)),
        refinement_stability=float(payload.get("refinement_stability", 0.0)),
        mean_shift_px=float(payload.get("mean_shift_px", 0.0)),
        refinement_mode=str(payload.get("refinement_mode", "")),
    )


def _restore_registration_result_set(payload: dict | None) -> RegistrationResultSet | None:
    if not payload:
        return None
    settings = _restore_registration_settings(payload.get("settings", {}))
    results_by_frame: dict[int, RegistrationFrameResult] = {}
    for result_payload in payload.get("results", []):
        result = RegistrationFrameResult(
            frame_index=int(result_payload["frame_index"]),
            shift_xy=result_payload["shift_xy"],
            method=str(result_payload["method"]),
            quality_score=float(result_payload.get("quality_score", 0.0)),
            phase_peak_ratio=result_payload.get("phase_peak_ratio"),
            ecc_score=result_payload.get("ecc_score"),
            num_inlier_tiles=result_payload.get("num_inlier_tiles"),
            num_total_tiles=result_payload.get("num_total_tiles"),
            median_tile_residual=result_payload.get("median_tile_residual"),
            flow_mad=result_payload.get("flow_mad"),
            status=str(result_payload.get("status", "ok")),
        )
        results_by_frame[result.frame_index] = result
    return RegistrationResultSet(
        settings=settings,
        results_by_frame=results_by_frame,
        reference_frame_index=int(payload.get("reference_frame_index", 0)),
        template_frame_indices=payload.get("template_frame_indices"),
    )


def _restore_registration_settings(payload: dict) -> RegistrationSettings:
    roi_mask = payload.get("roi_mask")
    return RegistrationSettings(
        backend=str(payload.get("backend", "phase_correlation")),
        reference_strategy=str(payload.get("reference_strategy", "adjacent")),
        registration_view=str(payload.get("registration_view", "raw")),
        roi_mask=None if roi_mask is None else np.asarray(roi_mask, dtype=bool),
        backend_params=dict(payload.get("backend_params", {})),
    )


def _restore_yolo_detections(payload: dict | None) -> YoloDetectionSet | None:
    if not payload:
        return None
    detections_by_frame: dict[int, list[YoloDetection]] = {}
    for frame_payload in payload.get("detections_by_frame", []):
        frame_index = int(frame_payload["frame_index"])
        detections_by_frame[frame_index] = [
            YoloDetection(
                frame_index=frame_index,
                bbox=_bbox_from_payload(detection_payload["bbox"]),
                confidence=float(detection_payload["confidence"]),
                selected=bool(detection_payload.get("selected", True)),
                model_name=str(detection_payload.get("model_name") or payload["model_name"]),
            )
            for detection_payload in frame_payload.get("detections", [])
        ]
    return YoloDetectionSet(
        model_name=str(payload["model_name"]),
        source_path=str(payload["source_path"]),
        detections_by_frame=detections_by_frame,
    )


def _bbox_from_payload(payload: list[float] | tuple[float, float, float, float]) -> BBoxXYXY:
    x0, y0, x1, y1 = [float(value) for value in payload]
    return BBoxXYXY(x0, y0, x1, y1)


def _normalize_mask_tracker_kind(value: object) -> str:
    try:
        return MaskTrackerKind.from_value(value).value
    except Exception:
        return MaskTrackerKind.SAM2.value


def _write_npz(zf: zipfile.ZipFile, path: str, **arrays: np.ndarray) -> None:
    buffer = io.BytesIO()
    np.savez_compressed(buffer, **arrays)
    zf.writestr(path, buffer.getvalue())


def _read_optional_npz(zf: zipfile.ZipFile, path: str, key: str) -> np.ndarray | None:
    try:
        raw = zf.read(path)
    except KeyError:
        return None
    with np.load(io.BytesIO(raw), allow_pickle=False) as npz:
        return np.asarray(npz[key])


def _json_safe(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value
