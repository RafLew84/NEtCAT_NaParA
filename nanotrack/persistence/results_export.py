"""CSV export helpers for NanoTrack measurement results."""

from __future__ import annotations

import csv
from pathlib import Path

from nanotrack.core import ParticleTrack, STMSequence


def export_results_csv(base_path: str, sequence: STMSequence, tracks: list[ParticleTrack]) -> dict[str, str]:
    """Export per-frame metrics and per-track summaries to CSV files."""

    exportable_tracks = list(tracks)
    if not exportable_tracks:
        raise RuntimeError("No tracks available for export.")

    metrics_rows = list(_metrics_rows(sequence, exportable_tracks))
    if not metrics_rows:
        raise RuntimeError("No measured results available for export.")

    base = Path(base_path)
    if base.suffix.lower() == ".csv":
        base = base.with_suffix("")
    base.parent.mkdir(parents=True, exist_ok=True)

    metrics_path = base.parent / f"{base.name}_metrics.csv"
    summary_path = base.parent / f"{base.name}_summary.csv"

    _write_csv(metrics_path, metrics_rows)
    _write_csv(summary_path, list(_summary_rows(exportable_tracks)))
    return {
        "metrics_csv": str(metrics_path),
        "summary_csv": str(summary_path),
    }


def _metrics_rows(sequence: STMSequence, tracks: list[ParticleTrack]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for track in tracks:
        label = track.label or f"Track {track.track_id}"
        for frame_index in track.frame_indices:
            annotation = track.get_annotation(frame_index)
            if annotation is None:
                continue
            metrics = annotation.metrics
            if (
                metrics.area_px is None
                or metrics.perimeter_px is None
                or metrics.intensity_sum is None
                or metrics.intensity_mean is None
                or metrics.intensity_max is None
            ):
                continue
            bbox = annotation.bbox
            rows.append(
                {
                    "track_id": track.track_id,
                    "label": label,
                    "quality": track.quality.value,
                    "frame_index": frame_index,
                    "frame_number": frame_index + 1,
                    "time_s": sequence.get_frame_time_s(frame_index),
                    "visibility": annotation.visibility.value,
                    "source": annotation.source.value,
                    "bbox_x0": None if bbox is None else bbox.x0,
                    "bbox_y0": None if bbox is None else bbox.y0,
                    "bbox_x1": None if bbox is None else bbox.x1,
                    "bbox_y1": None if bbox is None else bbox.y1,
                    "area_px": metrics.area_px,
                    "perimeter_px": metrics.perimeter_px,
                    "intensity_sum": metrics.intensity_sum,
                    "intensity_mean": metrics.intensity_mean,
                    "intensity_max": metrics.intensity_max,
                }
            )
    return rows


def _summary_rows(tracks: list[ParticleTrack]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for track in tracks:
        label = track.label or f"Track {track.track_id}"
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
                metrics.area_px is not None
                and metrics.perimeter_px is not None
                and metrics.intensity_sum is not None
                and metrics.intensity_mean is not None
                and metrics.intensity_max is not None
            ):
                measured_annotations.append(annotation)

        if measured_annotations:
            area_values = [annotation.metrics.area_px for annotation in measured_annotations]
            perimeter_values = [annotation.metrics.perimeter_px for annotation in measured_annotations]
            intensity_sum_values = [annotation.metrics.intensity_sum for annotation in measured_annotations]
            intensity_mean_values = [annotation.metrics.intensity_mean for annotation in measured_annotations]
            intensity_max_values = [annotation.metrics.intensity_max for annotation in measured_annotations]
            summary = {
                "mean_area_px": sum(area_values) / len(area_values),
                "max_area_px": max(area_values),
                "mean_perimeter_px": sum(perimeter_values) / len(perimeter_values),
                "max_perimeter_px": max(perimeter_values),
                "mean_intensity_sum": sum(intensity_sum_values) / len(intensity_sum_values),
                "max_intensity_sum": max(intensity_sum_values),
                "mean_intensity_mean": sum(intensity_mean_values) / len(intensity_mean_values),
                "max_intensity_max": max(intensity_max_values),
                "measured_frames": len(measured_annotations),
            }
        else:
            summary = {
                "mean_area_px": None,
                "max_area_px": None,
                "mean_perimeter_px": None,
                "max_perimeter_px": None,
                "mean_intensity_sum": None,
                "max_intensity_sum": None,
                "mean_intensity_mean": None,
                "max_intensity_max": None,
                "measured_frames": 0,
            }

        rows.append(
            {
                "track_id": track.track_id,
                "label": label,
                "quality": track.quality.value,
                "seed_frame_index": track.seed_frame_index,
                "seed_frame_number": track.seed_frame_index + 1,
                "end_frame_index": track.end_frame_index,
                "end_frame_number": track.end_frame_index + 1,
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
