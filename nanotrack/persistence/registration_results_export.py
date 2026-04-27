"""CSV export helpers for NanoTrack registration results."""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np

from nanotrack.core import RegistrationFrameResult, RegistrationResultSet, STMSequence


def export_registration_results_csv(
    base_path: str,
    sequence: STMSequence,
    result_set: RegistrationResultSet,
) -> dict[str, str]:
    """Export registration shifts and quality metrics to CSV files."""

    if not isinstance(result_set, RegistrationResultSet):
        raise TypeError("result_set must be a RegistrationResultSet instance.")
    if result_set.result_count == 0:
        raise RuntimeError("No registration results available for export.")

    metrics_rows = _metrics_rows(sequence, result_set)
    if not metrics_rows:
        raise RuntimeError("No registration metrics available for export.")

    base = Path(base_path)
    if base.suffix.lower() == ".csv":
        base = base.with_suffix("")
    base.parent.mkdir(parents=True, exist_ok=True)

    metrics_path = base.parent / f"{base.name}_registration_metrics.csv"
    summary_path = base.parent / f"{base.name}_registration_summary.csv"

    _write_csv(metrics_path, metrics_rows)
    _write_csv(summary_path, [_summary_row(sequence, result_set)])
    return {
        "metrics_csv": str(metrics_path),
        "summary_csv": str(summary_path),
    }


def _metrics_rows(sequence: STMSequence, result_set: RegistrationResultSet) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    settings = result_set.settings
    for frame_index in result_set.frame_indices:
        result = result_set.get_result(frame_index)
        if result is None:
            continue
        rows.append(
            {
                "frame_index": result.frame_index,
                "frame_number": result.frame_index + 1,
                "time_s": sequence.get_frame_time_s(result.frame_index),
                "frame_excluded": sequence.is_frame_excluded(result.frame_index),
                "dx_px": result.dx,
                "dy_px": result.dy,
                "shift_magnitude_px": float(np.hypot(result.dx, result.dy)),
                "quality_score": result.quality_score,
                "status": result.status,
                "method": result.method,
                "phase_peak_ratio": result.phase_peak_ratio,
                "ecc_score": result.ecc_score,
                "num_inlier_tiles": result.num_inlier_tiles,
                "num_total_tiles": result.num_total_tiles,
                "median_tile_residual": result.median_tile_residual,
                "flow_mad": result.flow_mad,
                "backend": settings.backend,
                "reference_strategy": settings.reference_strategy,
                "registration_view": settings.registration_view,
                "reference_frame_index": result_set.reference_frame_index,
                "reference_frame_number": result_set.reference_frame_index + 1,
            }
        )
    return rows


def _summary_row(sequence: STMSequence, result_set: RegistrationResultSet) -> dict[str, object]:
    results = [result_set.get_result(frame_index) for frame_index in result_set.frame_indices]
    valid_results = [result for result in results if isinstance(result, RegistrationFrameResult)]
    shifts = np.asarray([[result.dx, result.dy] for result in valid_results], dtype=np.float64)
    quality_values = [result.quality_score for result in valid_results]
    status_counts = result_set.status_counts()
    max_shift = 0.0 if shifts.size == 0 else float(np.max(np.linalg.norm(shifts, axis=1)))
    mean_shift = 0.0 if shifts.size == 0 else float(np.mean(np.linalg.norm(shifts, axis=1)))
    settings = result_set.settings
    return {
        "source_path": sequence.source_path,
        "sequence_frame_count": sequence.frame_count,
        "result_count": result_set.result_count,
        "backend": settings.backend,
        "reference_strategy": settings.reference_strategy,
        "registration_view": settings.registration_view,
        "reference_frame_index": result_set.reference_frame_index,
        "reference_frame_number": result_set.reference_frame_index + 1,
        "template_frame_indices": _format_indices(result_set.template_frame_indices, one_based=False),
        "template_frame_numbers": _format_indices(result_set.template_frame_indices, one_based=True),
        "max_shift_px": max_shift,
        "mean_shift_px": mean_shift,
        "min_quality": min(quality_values) if quality_values else None,
        "mean_quality": sum(quality_values) / len(quality_values) if quality_values else None,
        "ok_count": status_counts.get("ok", 0),
        "low_confidence_count": status_counts.get("low_confidence", 0),
        "failed_count": status_counts.get("failed", 0),
        "manual_review_count": status_counts.get("manual_review", 0),
    }


def _format_indices(indices: tuple[int, ...] | None, *, one_based: bool) -> str:
    if not indices:
        return ""
    offset = 1 if one_based else 0
    return ";".join(str(int(index) + offset) for index in indices)


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise RuntimeError(f"No rows to export for {path.name}.")
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
