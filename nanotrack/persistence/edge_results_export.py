"""CSV export helpers for NanoTrack edge-tracking results."""

from __future__ import annotations

import csv
from pathlib import Path

from nanotrack.core import EdgeTrack, STMSequence


def export_edge_results_csv(base_path: str, sequence: STMSequence, edge_tracks: list[EdgeTrack]) -> dict[str, str]:
    """Export per-frame edge metrics and per-track summaries to CSV files."""

    exportable_tracks = list(edge_tracks)
    if not exportable_tracks:
        raise RuntimeError("No edge tracks available for export.")

    metrics_rows = list(_metrics_rows(sequence, exportable_tracks))
    if not metrics_rows:
        raise RuntimeError("No measured edge results available for export.")

    base = Path(base_path)
    if base.suffix.lower() == ".csv":
        base = base.with_suffix("")
    base.parent.mkdir(parents=True, exist_ok=True)

    metrics_path = base.parent / f"{base.name}_edge_metrics.csv"
    summary_path = base.parent / f"{base.name}_edge_summary.csv"

    _write_csv(metrics_path, metrics_rows)
    _write_csv(summary_path, list(_summary_rows(sequence, exportable_tracks)))
    return {
        "metrics_csv": str(metrics_path),
        "summary_csv": str(summary_path),
    }


def _metrics_rows(sequence: STMSequence, edge_tracks: list[EdgeTrack]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    pixel_size_x_nm, pixel_size_y_nm = sequence.metadata.get_pixel_size_nm()
    for track in edge_tracks:
        label = track.label or f"Edge {track.edge_track_id}"
        for frame_index in track.frame_indices:
            annotation = track.get_annotation(frame_index)
            if annotation is None:
                continue
            metrics = annotation.metrics
            if (
                metrics.length_px is None
                or metrics.roughness_rms_px is None
                or metrics.mean_curvature is None
                or metrics.max_curvature is None
                or metrics.waviness_amplitude_px is None
            ):
                continue
            rows.append(
                {
                    "edge_track_id": track.edge_track_id,
                    "label": label,
                    "quality": track.quality.value,
                    "frame_index": frame_index,
                    "frame_number": frame_index + 1,
                    "time_s": sequence.get_frame_time_s(frame_index),
                    "visibility": annotation.visibility.value,
                    "source": annotation.source.value,
                    "image_size_nm_x": sequence.metadata.size_nm_x or None,
                    "image_size_nm_y": sequence.metadata.size_nm_y or None,
                    "pixel_size_nm_x": pixel_size_x_nm,
                    "pixel_size_nm_y": pixel_size_y_nm,
                    "polyline_point_count": annotation.polyline_point_count,
                    "length_px": metrics.length_px,
                    "length_nm": metrics.length_nm,
                    "roughness_rms_px": metrics.roughness_rms_px,
                    "roughness_rms_nm": metrics.roughness_rms_nm,
                    "mean_curvature": metrics.mean_curvature,
                    "max_curvature": metrics.max_curvature,
                    "waviness_amplitude_px": metrics.waviness_amplitude_px,
                    "waviness_amplitude_nm": metrics.waviness_amplitude_nm,
                }
            )
    return rows


def _summary_rows(sequence: STMSequence, edge_tracks: list[EdgeTrack]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    pixel_size_x_nm, pixel_size_y_nm = sequence.metadata.get_pixel_size_nm()
    for track in edge_tracks:
        label = track.label or f"Edge {track.edge_track_id}"
        measured_annotations = []
        visible_frames = 0
        for frame_index in track.frame_indices:
            annotation = track.get_annotation(frame_index)
            if annotation is None:
                continue
            if annotation.visibility.value == "visible":
                visible_frames += 1
            metrics = annotation.metrics
            if (
                metrics.length_px is not None
                and metrics.roughness_rms_px is not None
                and metrics.mean_curvature is not None
                and metrics.max_curvature is not None
                and metrics.waviness_amplitude_px is not None
            ):
                measured_annotations.append(annotation)

        if measured_annotations:
            length_px_values = [annotation.metrics.length_px for annotation in measured_annotations]
            length_nm_values = [annotation.metrics.length_nm for annotation in measured_annotations if annotation.metrics.length_nm is not None]
            roughness_px_values = [annotation.metrics.roughness_rms_px for annotation in measured_annotations]
            roughness_nm_values = [annotation.metrics.roughness_rms_nm for annotation in measured_annotations if annotation.metrics.roughness_rms_nm is not None]
            mean_curvature_values = [annotation.metrics.mean_curvature for annotation in measured_annotations]
            max_curvature_values = [annotation.metrics.max_curvature for annotation in measured_annotations]
            waviness_px_values = [annotation.metrics.waviness_amplitude_px for annotation in measured_annotations]
            waviness_nm_values = [annotation.metrics.waviness_amplitude_nm for annotation in measured_annotations if annotation.metrics.waviness_amplitude_nm is not None]
            summary = {
                "mean_length_px": sum(length_px_values) / len(length_px_values),
                "max_length_px": max(length_px_values),
                "mean_length_nm": sum(length_nm_values) / len(length_nm_values) if length_nm_values else None,
                "max_length_nm": max(length_nm_values) if length_nm_values else None,
                "mean_roughness_rms_px": sum(roughness_px_values) / len(roughness_px_values),
                "max_roughness_rms_px": max(roughness_px_values),
                "mean_roughness_rms_nm": sum(roughness_nm_values) / len(roughness_nm_values) if roughness_nm_values else None,
                "max_roughness_rms_nm": max(roughness_nm_values) if roughness_nm_values else None,
                "mean_mean_curvature": sum(mean_curvature_values) / len(mean_curvature_values),
                "max_mean_curvature": max(mean_curvature_values),
                "mean_max_curvature": sum(max_curvature_values) / len(max_curvature_values),
                "max_max_curvature": max(max_curvature_values),
                "mean_waviness_amplitude_px": sum(waviness_px_values) / len(waviness_px_values),
                "max_waviness_amplitude_px": max(waviness_px_values),
                "mean_waviness_amplitude_nm": sum(waviness_nm_values) / len(waviness_nm_values) if waviness_nm_values else None,
                "max_waviness_amplitude_nm": max(waviness_nm_values) if waviness_nm_values else None,
                "measured_frames": len(measured_annotations),
            }
        else:
            summary = {
                "mean_length_px": None,
                "max_length_px": None,
                "mean_length_nm": None,
                "max_length_nm": None,
                "mean_roughness_rms_px": None,
                "max_roughness_rms_px": None,
                "mean_roughness_rms_nm": None,
                "max_roughness_rms_nm": None,
                "mean_mean_curvature": None,
                "max_mean_curvature": None,
                "mean_max_curvature": None,
                "max_max_curvature": None,
                "mean_waviness_amplitude_px": None,
                "max_waviness_amplitude_px": None,
                "mean_waviness_amplitude_nm": None,
                "max_waviness_amplitude_nm": None,
                "measured_frames": 0,
            }

        rows.append(
            {
                "edge_track_id": track.edge_track_id,
                "label": label,
                "quality": track.quality.value,
                "seed_frame_index": track.seed_frame_index,
                "seed_frame_number": track.seed_frame_index + 1,
                "end_frame_index": track.end_frame_index,
                "end_frame_number": track.end_frame_index + 1,
                "image_size_nm_x": sequence.metadata.size_nm_x or None,
                "image_size_nm_y": sequence.metadata.size_nm_y or None,
                "pixel_size_nm_x": pixel_size_x_nm,
                "pixel_size_nm_y": pixel_size_y_nm,
                "visible_frames": visible_frames,
                **summary,
            }
        )
    return rows


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise RuntimeError(f"No rows to export for {path.name}.")
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
