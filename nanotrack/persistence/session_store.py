"""Save/load helpers for NanoTrack project sessions."""

from __future__ import annotations

import io
import json
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import numpy as np

from nanotrack.core import (
    AnnotationSource,
    BBoxXYXY,
    EdgeAnnotationSource,
    EdgeFrameAnnotation,
    EdgeMetrics,
    EdgeTrack,
    FrameVisibility,
    ParticleMetrics,
    ParticleTrack,
    PolygonROI,
    STMSequence,
    TrackFrameAnnotation,
    TrackQuality,
)
from nanotrack.io import load_mpp_sequence

SESSION_SCHEMA = "nanotrack.session.v1"


@dataclass
class NanoTrackSessionSnapshot:
    """Serializable state of the NanoTrack main window."""

    sequence: STMSequence
    tracks: list[ParticleTrack] = field(default_factory=list)
    edge_tracks: list[EdgeTrack] = field(default_factory=list)
    selected_track_id: int | None = None
    selected_edge_track_id: int | None = None
    draft_bboxes_by_frame: dict[int, BBoxXYXY] = field(default_factory=dict)
    draft_polygons_by_frame: dict[int, PolygonROI] = field(default_factory=dict)
    draft_edge_polylines_by_frame: dict[int, np.ndarray] = field(default_factory=dict)
    repair_frames: np.ndarray | None = None
    repair_params: dict[str, float | int | str] | None = None
    denoised_frames: np.ndarray | None = None
    denoised_sigma_factor: float | None = None
    show_denoised_in_viewer: bool = False


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
    sequence_loader: Callable[..., STMSequence] = load_mpp_sequence,
) -> NanoTrackSessionSnapshot:
    """Load a NanoTrack session from disk and reconstruct the in-memory state."""

    with zipfile.ZipFile(path, mode="r") as zf:
        manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
        if manifest.get("schema") != SESSION_SCHEMA:
            raise ValueError(f"Unsupported NanoTrack session schema: {manifest.get('schema')!r}")

        sequence_path = str(manifest["sequence"]["source_path"])
        reverse_frame_order = bool(manifest["sequence"].get("reverse_frame_order", False))
        sequence = sequence_loader(sequence_path, reverse_frame_order=reverse_frame_order)
        sequence.set_active_frame(int(manifest["sequence"]["active_frame_index"]))

        repair_frames = _read_optional_npz(zf, "preprocessing/repair_frames.npz", "frames")
        denoised_frames = _read_optional_npz(zf, "preprocessing/denoised_frames.npz", "frames")
        tracks = _restore_tracks(zf, manifest.get("tracks", []))
        edge_tracks = _restore_edge_tracks(zf, manifest.get("edge_tracks", []))
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
            selected_track_id=manifest.get("selected_track_id"),
            selected_edge_track_id=manifest.get("selected_edge_track_id"),
            draft_bboxes_by_frame=draft_bboxes,
            draft_polygons_by_frame=draft_polygons,
            draft_edge_polylines_by_frame=draft_edge_polylines,
            repair_frames=repair_frames,
            repair_params=preprocessing.get("repair_params"),
            denoised_frames=denoised_frames,
            denoised_sigma_factor=preprocessing.get("denoised_sigma_factor"),
            show_denoised_in_viewer=bool(manifest.get("show_denoised_in_viewer", False)),
        )


def _build_manifest(snapshot: NanoTrackSessionSnapshot) -> dict:
    return {
        "schema": SESSION_SCHEMA,
        "sequence": {
            "source_path": snapshot.sequence.source_path,
            "active_frame_index": snapshot.sequence.active_frame_index,
            "reverse_frame_order": bool(snapshot.sequence.reverse_frame_order),
        },
        "selected_track_id": snapshot.selected_track_id,
        "selected_edge_track_id": snapshot.selected_edge_track_id,
        "show_denoised_in_viewer": bool(snapshot.show_denoised_in_viewer),
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


def _bbox_from_payload(payload: list[float] | tuple[float, float, float, float]) -> BBoxXYXY:
    x0, y0, x1, y1 = [float(value) for value in payload]
    return BBoxXYXY(x0, y0, x1, y1)


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
