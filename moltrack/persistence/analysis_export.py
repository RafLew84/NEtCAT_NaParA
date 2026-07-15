from __future__ import annotations

import csv
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from moltrack import __version__ as moltrack_version
from moltrack.analysis import (
    MolecularFrameAnalysisResult,
    MolecularFrameRange,
    MolecularFrameRangeAnalysis,
    MolecularFrameRangeComparison,
    MolecularFrameRangeSelection,
    MolecularIntensityMeasurement,
    MolecularPositionPlotData,
    MolecularRangeSpatialComparisonData,
    analyze_molecular_frame_range,
    build_molecular_range_spatial_comparison_data,
    compare_molecular_frame_ranges,
)
from moltrack.core import MolTrackImageSeries, MolecularCentroid, build_molecular_centroids

if TYPE_CHECKING:
    from .analysis_plots import AnalysisPlotExportResult


ANALYSIS_EXPORT_SCHEMA_VERSION = 1


_MOLECULES_CSV_FIELDS = (
    "working_frame_index",
    "working_frame_number",
    "source_frame_index",
    "source_frame_number",
    "time_s",
    "source_view",
    "source_kind",
    "source_id",
    "origin",
    "position_x",
    "position_y",
    "position_unit",
    "x_px",
    "y_px",
    "x_nm",
    "y_nm",
)

_FULL_MOLECULES_CSV_FIELDS = _MOLECULES_CSV_FIELDS + (
    "detection_id",
    "segmentation_id",
    "area_px",
    "bbox_x1",
    "bbox_y1",
    "bbox_x2",
    "bbox_y2",
    "confidence",
    "nearest_neighbor_distance",
    "nearest_neighbor_distance_unit",
    "nearest_neighbor_angle_deg",
    "intensity_pixel_count",
    "intensity_unit",
    "intensity_sum",
    "intensity_mean",
    "intensity_median",
    "intensity_max",
    "local_background_median",
    "background_corrected_mean",
    "background_corrected_median",
)

_FRAMES_CSV_FIELDS = (
    "working_frame_index",
    "working_frame_number",
    "source_frame_index",
    "source_frame_number",
    "time_s",
    "source_view",
    "molecule_count",
    "nearest_neighbor_distance_unit",
    "mean_nearest_neighbor_distance",
    "median_nearest_neighbor_distance",
    "min_nearest_neighbor_distance",
    "max_nearest_neighbor_distance",
    "line_order_score",
    "intensity_metric",
    "intensity_unit",
    "mean_intensity",
    "median_intensity",
)

_RANGES_CSV_FIELDS = (
    "condition_order",
    "condition_name",
    "start_frame_index",
    "start_frame_number",
    "end_frame_index",
    "end_frame_number",
    "source_view",
    "analyzed_frame_count",
    "total_molecule_count",
    "mean_molecule_count",
    "nearest_neighbor_distance_unit",
    "mean_nearest_neighbor_distance",
    "mean_line_order_score",
    "intensity_metric",
    "intensity_unit",
    "mean_intensity",
    "median_intensity",
)

_COMPARISON_CSV_FIELDS = (
    "direction",
    "first_condition_name",
    "second_condition_name",
    "source_view",
    "analysis_mode",
    "uses_tracking",
    "nearest_neighbor_distance_unit",
    "intensity_metric",
    "intensity_unit",
    "mean_molecule_count_delta",
    "mean_nearest_neighbor_distance_delta",
    "mean_line_order_score_delta",
    "mean_intensity_delta",
    "median_intensity_delta",
)

_SPATIAL_BINS_CSV_FIELDS = (
    "condition_order",
    "condition_name",
    "row",
    "column",
    "x_min",
    "x_max",
    "y_min",
    "y_max",
    "position_unit",
    "molecules_per_frame",
    "density_unit",
    "intensity_metric",
    "intensity_unit",
    "mean_intensity",
)


def export_selected_ranges_analysis_csv(
    series: MolTrackImageSeries,
    selection: MolecularFrameRangeSelection,
    destination_dir: str | Path,
    *,
    use_segmentation_centroids: bool = True,
    intensity_metric: str = "background_corrected_median",
    intensity_unit: str = "a.u.",
    background_inner_radius_px: int = 1,
    background_outer_radius_px: int = 3,
    density_grid_shape: tuple[int, int] = (32, 32),
    include_plots: bool = False,
    plot_dpi: int = 150,
    plot_size_inches: tuple[float, float] = (8.0, 6.0),
    progress_callback=None,
    phase_callback=None,
) -> dict[str, Path]:
    """Analyze and export two named frame ranges without creating tracks."""

    comparison = compare_molecular_frame_ranges(
        series,
        selection,
        use_segmentation_centroids=use_segmentation_centroids,
        intensity_metric=intensity_metric,
        intensity_unit=intensity_unit,
        background_inner_radius_px=background_inner_radius_px,
        background_outer_radius_px=background_outer_radius_px,
        progress_callback=progress_callback,
    )
    spatial_data = build_molecular_range_spatial_comparison_data(
        comparison,
        density_grid_shape=density_grid_shape,
    )
    if phase_callback is not None:
        phase_callback("writing_tables")
    molecule_rows = []
    frame_rows = []
    range_rows = []
    for condition_order, analysis in (
        ("first", comparison.first_analysis),
        ("second", comparison.second_analysis),
    ):
        condition_name = analysis.frame_range.name
        for frame_analysis in analysis.frame_results:
            analyzed_rows = _analyzed_molecule_rows(series, frame_analysis)
            for row in analyzed_rows:
                row["condition_name"] = condition_name
            molecule_rows.extend(analyzed_rows)
            frame_row = _frame_row(series, frame_analysis)
            frame_row["condition_name"] = condition_name
            frame_rows.append(frame_row)
        range_rows.append(_range_row(condition_order, analysis))

    destination = Path(destination_dir)
    destination.mkdir(parents=True, exist_ok=True)
    molecules_path = destination / "molecules.csv"
    _write_csv(
        molecules_path,
        molecule_rows,
        fieldnames=("condition_name",) + _FULL_MOLECULES_CSV_FIELDS,
    )
    frames_path = destination / "frames.csv"
    _write_csv(
        frames_path,
        frame_rows,
        fieldnames=("condition_name",) + _FRAMES_CSV_FIELDS,
    )
    ranges_path = destination / "ranges.csv"
    _write_csv(ranges_path, range_rows, fieldnames=_RANGES_CSV_FIELDS)
    comparison_path = destination / "comparison.csv"
    _write_csv(
        comparison_path,
        [_comparison_row(comparison)],
        fieldnames=_COMPARISON_CSV_FIELDS,
    )
    spatial_bins_path = destination / "spatial_bins.csv"
    spatial_bin_rows = _spatial_bin_rows(spatial_data)
    _write_csv(
        spatial_bins_path,
        spatial_bin_rows,
        fieldnames=_SPATIAL_BINS_CSV_FIELDS,
    )
    plots_dir = None
    plot_export = None
    if include_plots:
        if phase_callback is not None:
            phase_callback("rendering_plots")
        from .analysis_plots import export_selected_range_analysis_plots

        plots_dir = destination / "plots"
        current_analysis = _current_frame_analysis(
            series,
            comparison,
            use_segmentation_centroids=use_segmentation_centroids,
            intensity_metric=intensity_metric,
            intensity_unit=intensity_unit,
            background_inner_radius_px=background_inner_radius_px,
            background_outer_radius_px=background_outer_radius_px,
        )
        plot_export = export_selected_range_analysis_plots(
            current_analysis,
            comparison,
            spatial_data,
            plots_dir,
            dpi=plot_dpi,
            size_inches=plot_size_inches,
        )
    file_entries = [
        {"path": molecules_path.name, "record_count": len(molecule_rows)},
        {"path": frames_path.name, "record_count": len(frame_rows)},
        {"path": ranges_path.name, "record_count": len(range_rows)},
        {"path": comparison_path.name, "record_count": 1},
        {
            "path": spatial_bins_path.name,
            "record_count": len(spatial_bin_rows),
        },
    ]
    if plot_export is not None:
        file_entries.extend(_plot_file_entries(plot_export, destination))
    manifest_path = destination / "manifest.json"
    _write_json(
        manifest_path,
        {
            "export_schema_version": ANALYSIS_EXPORT_SCHEMA_VERSION,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "application": {"name": "MolTrack", "version": moltrack_version},
            "source": _source_manifest(series, destination),
            "stm_metadata": _stm_metadata_manifest(series),
            "working_series": {
                "frame_count": series.frame_count,
                "source_frame_indices": list(series.source_frame_indices),
                "reverse_frame_order": series.reverse_frame_order,
            },
            "ranges": _ranges_manifest(selection),
            "analysis": _analysis_manifest(
                series,
                comparison,
                spatial_data,
                use_segmentation_centroids=use_segmentation_centroids,
                background_inner_radius_px=background_inner_radius_px,
                background_outer_radius_px=background_outer_radius_px,
            ),
            "registration": _registration_manifest(series),
            "plots": _plots_manifest(plot_export, destination),
            "files": file_entries,
        },
    )
    paths = {
        "molecules_csv": molecules_path,
        "frames_csv": frames_path,
        "ranges_csv": ranges_path,
        "comparison_csv": comparison_path,
        "spatial_bins_csv": spatial_bins_path,
        "manifest_json": manifest_path,
    }
    if plots_dir is not None:
        paths["plots_dir"] = plots_dir
    return paths


def _current_frame_analysis(
    series: MolTrackImageSeries,
    comparison: MolecularFrameRangeComparison,
    *,
    use_segmentation_centroids: bool,
    intensity_metric: str,
    intensity_unit: str,
    background_inner_radius_px: int,
    background_outer_radius_px: int,
) -> MolecularFrameAnalysisResult:
    for analysis in (comparison.first_analysis, comparison.second_analysis):
        for frame_analysis in analysis.frame_results:
            if frame_analysis.frame_index == series.active_frame_index:
                return frame_analysis
    return analyze_molecular_frame_range(
        series,
        MolecularFrameRange(
            "Current frame",
            series.active_frame_index,
            series.active_frame_index,
        ),
        source_view=comparison.source_view,
        use_segmentation_centroids=use_segmentation_centroids,
        intensity_metric=intensity_metric,
        intensity_unit=intensity_unit,
        background_inner_radius_px=background_inner_radius_px,
        background_outer_radius_px=background_outer_radius_px,
    ).frame_results[0]


def _plots_manifest(
    plot_export: AnalysisPlotExportResult | None,
    destination: Path,
) -> dict[str, object]:
    if plot_export is None:
        return {
            "included": False,
            "formats": [],
            "png_dpi": None,
            "size_inches": None,
            "generated": [],
            "skipped": [],
        }
    width, height = plot_export.size_inches
    return {
        "included": True,
        "formats": ["svg", "png"],
        "png_dpi": plot_export.dpi,
        "size_inches": {"width": width, "height": height},
        "generated": [
            {
                "kind": kind,
                "files": [
                    path.relative_to(destination).as_posix() for path in paths
                ],
            }
            for kind, paths in plot_export.generated
        ],
        "skipped": [
            {"kind": kind, "reason": reason}
            for kind, reason in plot_export.skipped
        ],
    }


def _plot_file_entries(
    plot_export: AnalysisPlotExportResult,
    destination: Path,
) -> list[dict[str, object]]:
    return [
        {
            "path": path.relative_to(destination).as_posix(),
            "record_count": None,
        }
        for _kind, paths in plot_export.generated
        for path in paths
    ]


def _range_row(
    condition_order: str,
    analysis: MolecularFrameRangeAnalysis,
) -> dict[str, object]:
    frame_range = analysis.frame_range
    aggregates = analysis.aggregates
    return {
        "condition_order": condition_order,
        "condition_name": frame_range.name,
        "start_frame_index": frame_range.start_frame,
        "start_frame_number": frame_range.start_frame + 1,
        "end_frame_index": frame_range.end_frame,
        "end_frame_number": frame_range.end_frame + 1,
        "source_view": analysis.source_view,
        "analyzed_frame_count": aggregates.analyzed_frame_count,
        "total_molecule_count": aggregates.total_molecule_count,
        "mean_molecule_count": aggregates.mean_molecule_count,
        "nearest_neighbor_distance_unit": aggregates.distance_unit,
        "mean_nearest_neighbor_distance": aggregates.mean_nearest_neighbor_distance,
        "mean_line_order_score": aggregates.mean_line_order_score,
        "intensity_metric": analysis.intensity_metric,
        "intensity_unit": analysis.intensity_unit,
        "mean_intensity": aggregates.mean_intensity,
        "median_intensity": aggregates.median_intensity,
    }


def _comparison_row(
    comparison: MolecularFrameRangeComparison,
) -> dict[str, object]:
    first_analysis = comparison.first_analysis
    second_analysis = comparison.second_analysis
    differences = comparison.differences
    return {
        "direction": differences.direction,
        "first_condition_name": first_analysis.frame_range.name,
        "second_condition_name": second_analysis.frame_range.name,
        "source_view": comparison.source_view,
        "analysis_mode": comparison.analysis_mode,
        "uses_tracking": str(comparison.uses_tracking).lower(),
        "nearest_neighbor_distance_unit": differences.distance_unit,
        "intensity_metric": first_analysis.intensity_metric,
        "intensity_unit": first_analysis.intensity_unit,
        "mean_molecule_count_delta": differences.mean_molecule_count_delta,
        "mean_nearest_neighbor_distance_delta": (
            differences.mean_nearest_neighbor_distance_delta
        ),
        "mean_line_order_score_delta": differences.mean_line_order_score_delta,
        "mean_intensity_delta": differences.mean_intensity_delta,
        "median_intensity_delta": differences.median_intensity_delta,
    }


def _spatial_bin_rows(
    spatial_data: MolecularRangeSpatialComparisonData,
) -> list[dict[str, object]]:
    rows = []
    for condition_order, condition in (
        ("first", spatial_data.first),
        ("second", spatial_data.second),
    ):
        for row_index, (density_row, intensity_row) in enumerate(
            zip(condition.density_grid, condition.intensity_grid)
        ):
            for column_index, (density, intensity) in enumerate(
                zip(density_row, intensity_row)
            ):
                rows.append(
                    {
                        "condition_order": condition_order,
                        "condition_name": condition.condition_name,
                        "row": row_index,
                        "column": column_index,
                        "x_min": spatial_data.density_x_edges[column_index],
                        "x_max": spatial_data.density_x_edges[column_index + 1],
                        "y_min": spatial_data.density_y_edges[row_index],
                        "y_max": spatial_data.density_y_edges[row_index + 1],
                        "position_unit": spatial_data.unit,
                        "molecules_per_frame": density,
                        "density_unit": spatial_data.density_unit,
                        "intensity_metric": spatial_data.intensity_metric,
                        "intensity_unit": spatial_data.intensity_unit,
                        "mean_intensity": (
                            float(intensity) if np.isfinite(intensity) else None
                        ),
                    }
                )
    return rows


def _source_manifest(
    series: MolTrackImageSeries,
    destination: Path,
) -> dict[str, object]:
    source_path = Path(series.source_path)
    resolved_source = source_path.resolve(strict=False)
    try:
        relative_path = Path(
            os.path.relpath(resolved_source, destination.resolve(strict=False))
        ).as_posix()
    except ValueError:
        relative_path = source_path.name

    size_bytes = None
    modified_time_ns = None
    integrity = None
    try:
        source_stat = resolved_source.stat()
        if resolved_source.is_file():
            size_bytes = int(source_stat.st_size)
            modified_time_ns = int(source_stat.st_mtime_ns)
            integrity = {
                "algorithm": "sha256",
                "value": _sha256_file(resolved_source),
            }
    except OSError:
        pass
    return {
        "format": "MPP",
        "path": relative_path,
        "file_name": source_path.name,
        "size_bytes": size_bytes,
        "modified_time_ns": modified_time_ns,
        "integrity": integrity,
    }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stm_metadata_manifest(series: MolTrackImageSeries) -> dict[str, object]:
    metadata = series.metadata
    pixel_size_x, pixel_size_y = series.pixel_size_nm
    frame_times = getattr(metadata, "frame_times_s", None)
    return {
        "pixels": {
            "x": int(getattr(metadata, "pixels_x", series.frame_shape[1])),
            "y": int(getattr(metadata, "pixels_y", series.frame_shape[0])),
        },
        "size_nm": {
            "x": _optional_finite_float(getattr(metadata, "size_nm_x", None)),
            "y": _optional_finite_float(getattr(metadata, "size_nm_y", None)),
        },
        "pixel_size_nm": {
            "x": _optional_finite_float(pixel_size_x),
            "y": _optional_finite_float(pixel_size_y),
        },
        "offset_nm": {
            "x": _optional_finite_float(getattr(metadata, "offset_nm_x", None)),
            "y": _optional_finite_float(getattr(metadata, "offset_nm_y", None)),
        },
        "scan_angle_deg": _optional_finite_float(
            getattr(metadata, "scan_angle_deg", None)
        ),
        "bias_v": _optional_finite_float(getattr(metadata, "bias_v", None)),
        "setpoint_a": _optional_finite_float(getattr(metadata, "setpoint_a", None)),
        "image_type": str(getattr(metadata, "image_type", "Unknown")),
        "frame_interval_s": _optional_finite_float(
            getattr(metadata, "frame_interval_s", None)
        ),
        "frame_times_s": (
            None
            if frame_times is None
            else [
                _optional_finite_float(value)
                for value in np.asarray(frame_times).reshape(-1)
            ]
        ),
    }


def _optional_finite_float(value: object | None) -> float | None:
    if value is None:
        return None
    numeric = float(value)
    return numeric if np.isfinite(numeric) else None


def _ranges_manifest(
    selection: MolecularFrameRangeSelection,
) -> list[dict[str, object]]:
    rows = []
    for condition_order, frame_range in (
        ("first", selection.first_range),
        ("second", selection.second_range),
    ):
        rows.append(
            {
                "condition_order": condition_order,
                "condition_name": frame_range.name,
                "start_frame_index": frame_range.start_frame,
                "start_frame_number": frame_range.start_frame + 1,
                "end_frame_index": frame_range.end_frame,
                "end_frame_number": frame_range.end_frame + 1,
            }
        )
    return rows


def _analysis_manifest(
    series: MolTrackImageSeries,
    comparison: MolecularFrameRangeComparison,
    spatial_data: MolecularRangeSpatialComparisonData,
    *,
    use_segmentation_centroids: bool,
    background_inner_radius_px: int,
    background_outer_radius_px: int,
) -> dict[str, object]:
    return {
        "analysis_mode": comparison.analysis_mode,
        "uses_tracking": comparison.uses_tracking,
        "source_view": comparison.source_view,
        "centroid_mode": (
            "segmentation_centroids_with_bbox_center_fallback"
            if use_segmentation_centroids
            else "bbox_centers"
        ),
        "density_grid_shape": {
            "rows": len(spatial_data.density_y_edges) - 1,
            "columns": len(spatial_data.density_x_edges) - 1,
        },
        "intensity": {
            "metric": spatial_data.intensity_metric,
            "unit": spatial_data.intensity_unit,
            "background_inner_radius_px": int(background_inner_radius_px),
            "background_outer_radius_px": int(background_outer_radius_px),
        },
        "coordinate_system": _coordinate_system_manifest(
            series,
            spatial_data,
            source_view=comparison.source_view,
        ),
    }


def _coordinate_system_manifest(
    series: MolTrackImageSeries,
    spatial_data: MolecularRangeSpatialComparisonData,
    *,
    source_view: str,
) -> dict[str, object]:
    stack = series.expanded_aligned_stack if source_view == "expanded_aligned" else None
    if stack is None:
        return {
            "convention": "image_xy_x_right_y_down",
            "origin": "raw_frame_top_left",
            "position_unit": spatial_data.unit,
            "expanded_canvas_offset_px": None,
            "padding_ltrb": None,
            "frame_origins_xy": None,
        }
    padding = tuple(int(value) for value in getattr(stack, "padding_ltrb", (0, 0, 0, 0)))
    canvas_offset = getattr(stack, "canvas_offset_xy", (padding[0], padding[1]))
    frame_origins = np.asarray(getattr(stack, "frame_origins_xy", ()), dtype=np.float64)
    return {
        "convention": "image_xy_x_right_y_down",
        "origin": "reference_raw_frame_top_left",
        "position_unit": spatial_data.unit,
        "expanded_canvas_offset_px": {
            "x": float(canvas_offset[0]),
            "y": float(canvas_offset[1]),
        },
        "padding_ltrb": list(padding),
        "frame_origins_xy": [
            [float(origin[0]), float(origin[1])] for origin in frame_origins
        ],
    }


def _registration_manifest(series: MolTrackImageSeries) -> dict[str, object]:
    results = series.registration_results
    if results is None:
        return {
            "available": False,
            "backend": None,
            "reference_strategy": None,
            "registration_view": None,
            "backend_params": None,
            "reference_frame_index": None,
        }
    settings = results.settings
    return {
        "available": True,
        "backend": settings.backend,
        "reference_strategy": settings.reference_strategy,
        "registration_view": settings.registration_view,
        "backend_params": _json_compatible(settings.backend_params),
        "reference_frame_index": results.reference_frame_index,
    }


def _json_compatible(value: object) -> object:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if np.isfinite(value) else None
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, np.ndarray):
        return _json_compatible(value.tolist())
    if isinstance(value, np.generic):
        return _json_compatible(value.item())
    if isinstance(value, dict):
        return {str(key): _json_compatible(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_compatible(item) for item in value]
    return str(value)


def export_full_working_series_analysis_csv(
    series: MolTrackImageSeries,
    destination_dir: str | Path,
    *,
    source_view: str = "raw",
    use_segmentation_centroids: bool = True,
    intensity_metric: str = "background_corrected_median",
    intensity_unit: str = "a.u.",
    background_inner_radius_px: int = 1,
    background_outer_radius_px: int = 3,
    progress_callback=None,
    phase_callback=None,
) -> dict[str, Path]:
    """Analyze and export every frame remaining in the working series."""

    if not isinstance(series, MolTrackImageSeries):
        raise TypeError("series must be a MolTrackImageSeries instance.")
    analysis = analyze_molecular_frame_range(
        series,
        MolecularFrameRange("Full working series", 0, series.frame_count - 1),
        source_view=source_view,
        use_segmentation_centroids=use_segmentation_centroids,
        intensity_metric=intensity_metric,
        intensity_unit=intensity_unit,
        background_inner_radius_px=background_inner_radius_px,
        background_outer_radius_px=background_outer_radius_px,
        progress_callback=progress_callback,
    )
    molecule_rows = []
    frame_rows = []
    for frame_analysis in analysis.frame_results:
        molecule_rows.extend(_analyzed_molecule_rows(series, frame_analysis))
        frame_rows.append(_frame_row(series, frame_analysis))
    molecule_rows.sort(
        key=lambda row: (
            int(row["working_frame_index"]),
            str(row["source_kind"]),
            str(row["source_id"]),
        )
    )
    frame_rows.sort(key=lambda row: int(row["working_frame_index"]))
    if phase_callback is not None:
        phase_callback("writing_tables")
    return _write_analysis_tables(destination_dir, molecule_rows, frame_rows)


def export_current_frame_analysis_csv(
    series: MolTrackImageSeries,
    frame_analysis: MolecularFrameAnalysisResult,
    destination_dir: str | Path,
) -> dict[str, Path]:
    """Export full per-molecule analysis for one working-series frame."""

    if not isinstance(frame_analysis, MolecularFrameAnalysisResult):
        raise TypeError("frame_analysis must be a MolecularFrameAnalysisResult instance.")
    rows = _analyzed_molecule_rows(series, frame_analysis)
    return _write_analysis_tables(
        destination_dir,
        rows,
        [_frame_row(series, frame_analysis)],
    )


def _analyzed_molecule_rows(
    series: MolTrackImageSeries,
    frame_analysis: MolecularFrameAnalysisResult,
) -> list[dict[str, object]]:
    rows = _molecule_rows(series, frame_analysis.plot_data)
    distances = frame_analysis.distance_metrics.nearest_neighbor_distances
    angles = frame_analysis.angle_metrics.nearest_neighbor_angles_degrees
    intensity_by_source = {
        (measurement.source_kind, measurement.source_id): measurement
        for measurement in frame_analysis.intensity_measurements
    }
    for point_index, row in enumerate(rows):
        row.update(_annotation_fields(series, frame_analysis.plot_data, point_index))
        row["nearest_neighbor_distance"] = (
            None if not distances else distances[point_index]
        )
        row["nearest_neighbor_distance_unit"] = frame_analysis.distance_metrics.unit
        row["nearest_neighbor_angle_deg"] = None if not angles else angles[point_index]
        measurement = intensity_by_source.get(
            (str(row["source_kind"]), str(row["source_id"]))
        )
        row.update(_intensity_fields(measurement))
    return rows


def _write_analysis_tables(
    destination_dir: str | Path,
    molecule_rows: list[dict[str, object]],
    frame_rows: list[dict[str, object]],
) -> dict[str, Path]:
    destination = Path(destination_dir)
    destination.mkdir(parents=True, exist_ok=True)
    molecules_path = destination / "molecules.csv"
    _write_csv(molecules_path, molecule_rows, fieldnames=_FULL_MOLECULES_CSV_FIELDS)
    frames_path = destination / "frames.csv"
    _write_csv(frames_path, frame_rows, fieldnames=_FRAMES_CSV_FIELDS)
    return {"molecules_csv": molecules_path, "frames_csv": frames_path}


def export_current_frame_molecules_csv(
    series: MolTrackImageSeries,
    plot_data: MolecularPositionPlotData,
    destination_dir: str | Path,
) -> Path:
    """Export the plotted molecules from one working-series frame to CSV."""

    if not isinstance(series, MolTrackImageSeries):
        raise TypeError("series must be a MolTrackImageSeries instance.")
    if not isinstance(plot_data, MolecularPositionPlotData):
        raise TypeError("plot_data must be a MolecularPositionPlotData instance.")
    series.get_frame(plot_data.frame_index)
    if not plot_data.points_xy:
        raise RuntimeError("No molecular positions are available for the current frame.")

    rows = _molecule_rows(series, plot_data)
    destination = Path(destination_dir)
    destination.mkdir(parents=True, exist_ok=True)
    output_path = destination / "molecules.csv"
    _write_csv(output_path, rows, fieldnames=_MOLECULES_CSV_FIELDS)
    return output_path


def _molecule_rows(
    series: MolTrackImageSeries,
    plot_data: MolecularPositionPlotData,
) -> list[dict[str, object]]:
    if not isinstance(series, MolTrackImageSeries):
        raise TypeError("series must be a MolTrackImageSeries instance.")
    series.get_frame(plot_data.frame_index)
    frame_index = plot_data.frame_index
    source_frame_index = series.source_frame_indices[frame_index]
    centroids_by_source = _centroids_by_source(series, plot_data)
    rows = []
    for (position_x, position_y), source_id, source_kind in zip(
        plot_data.points_xy,
        plot_data.point_source_ids,
        plot_data.point_source_kinds,
    ):
        try:
            centroid = centroids_by_source[(source_kind, source_id)]
        except KeyError as exc:
            raise ValueError(
                f"Plot point source is not available in the series: {source_kind}:{source_id}."
            ) from exc
        rows.append(
            {
                "working_frame_index": frame_index,
                "working_frame_number": frame_index + 1,
                "source_frame_index": source_frame_index,
                "source_frame_number": source_frame_index + 1,
                "time_s": _source_frame_time_s(series, frame_index),
                "source_view": plot_data.source_view,
                "source_kind": source_kind,
                "source_id": source_id,
                "origin": centroid.origin,
                "position_x": position_x,
                "position_y": position_y,
                "position_unit": plot_data.unit,
                "x_px": centroid.x_px,
                "y_px": centroid.y_px,
                "x_nm": centroid.x_nm,
                "y_nm": centroid.y_nm,
            }
        )
    return rows


def _annotation_fields(
    series: MolTrackImageSeries,
    plot_data: MolecularPositionPlotData,
    point_index: int,
) -> dict[str, object]:
    source_kind = plot_data.point_source_kinds[point_index]
    source_id = plot_data.point_source_ids[point_index]
    if source_kind == "bbox" and series.molecular_detections is not None:
        matching_detections = [
            detection
            for detection in series.molecular_detections.get_detections(
                plot_data.frame_index,
                source_view=plot_data.source_view,
            )
            if detection.detection_id == source_id
        ]
        if not matching_detections:
            raise ValueError(f"Unknown molecular detection: {source_id}.")
        detection = matching_detections[0]
        x1, y1, x2, y2 = detection.bbox_xyxy
        return {
            "detection_id": detection.detection_id,
            "segmentation_id": None,
            "area_px": (x2 - x1) * (y2 - y1),
            "bbox_x1": x1,
            "bbox_y1": y1,
            "bbox_x2": x2,
            "bbox_y2": y2,
            "confidence": detection.confidence,
        }
    if source_kind == "segmentation" and series.molecular_segmentations is not None:
        matching_segmentations = [
            segmentation
            for segmentation in series.molecular_segmentations.get_segmentations(
                plot_data.frame_index,
                source_view=plot_data.source_view,
            )
            if segmentation.segmentation_id == source_id
        ]
        if not matching_segmentations:
            raise ValueError(f"Unknown molecular segmentation: {source_id}.")
        segmentation = matching_segmentations[0]
        mask = np.asarray(segmentation.mask, dtype=bool)
        active_y, active_x = np.nonzero(mask)
        if active_y.size == 0:
            raise ValueError(f"Molecular segmentation has an empty mask: {source_id}.")
        bbox_xyxy = segmentation.bbox_xyxy
        if bbox_xyxy is None:
            bbox_xyxy = (
                float(np.min(active_x)),
                float(np.min(active_y)),
                float(np.max(active_x) + 1),
                float(np.max(active_y) + 1),
            )
        x1, y1, x2, y2 = bbox_xyxy
        return {
            "detection_id": None,
            "segmentation_id": segmentation.segmentation_id,
            "area_px": float(active_y.size),
            "bbox_x1": x1,
            "bbox_y1": y1,
            "bbox_x2": x2,
            "bbox_y2": y2,
            "confidence": segmentation.score,
        }
    raise ValueError(f"Unsupported molecule annotation source: {source_kind}:{source_id}.")


def _intensity_fields(
    measurement: MolecularIntensityMeasurement | None,
) -> dict[str, object]:
    if measurement is None:
        return {
            "intensity_pixel_count": None,
            "intensity_unit": None,
            "intensity_sum": None,
            "intensity_mean": None,
            "intensity_median": None,
            "intensity_max": None,
            "local_background_median": None,
            "background_corrected_mean": None,
            "background_corrected_median": None,
        }
    return {
        "intensity_pixel_count": measurement.pixel_count,
        "intensity_unit": measurement.unit,
        "intensity_sum": measurement.sum,
        "intensity_mean": measurement.mean,
        "intensity_median": measurement.median,
        "intensity_max": measurement.max,
        "local_background_median": measurement.local_background_median,
        "background_corrected_mean": measurement.background_corrected_mean,
        "background_corrected_median": measurement.background_corrected_median,
    }


def _frame_row(
    series: MolTrackImageSeries,
    frame_analysis: MolecularFrameAnalysisResult,
) -> dict[str, object]:
    frame_index = frame_analysis.frame_index
    source_frame_index = series.source_frame_indices[frame_index]
    distance_metrics = frame_analysis.distance_metrics
    return {
        "working_frame_index": frame_index,
        "working_frame_number": frame_index + 1,
        "source_frame_index": source_frame_index,
        "source_frame_number": source_frame_index + 1,
        "time_s": _source_frame_time_s(series, frame_index),
        "source_view": frame_analysis.source_view,
        "molecule_count": frame_analysis.point_count,
        "nearest_neighbor_distance_unit": distance_metrics.unit,
        "mean_nearest_neighbor_distance": distance_metrics.mean_distance,
        "median_nearest_neighbor_distance": distance_metrics.median_distance,
        "min_nearest_neighbor_distance": distance_metrics.min_distance,
        "max_nearest_neighbor_distance": distance_metrics.max_distance,
        "line_order_score": frame_analysis.angle_metrics.line_order_score,
        "intensity_metric": frame_analysis.intensity_metric,
        "intensity_unit": frame_analysis.intensity_unit,
        "mean_intensity": frame_analysis.mean_intensity,
        "median_intensity": frame_analysis.median_intensity,
    }


def _write_csv(
    path: Path,
    rows: list[dict[str, object]],
    *,
    fieldnames: tuple[str, ...],
) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, payload: dict[str, object]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def _centroids_by_source(
    series: MolTrackImageSeries,
    plot_data: MolecularPositionPlotData,
) -> dict[tuple[str, str], MolecularCentroid]:
    centroids_by_source: dict[tuple[str, str], MolecularCentroid] = {}
    for use_segmentation_centroids in (True, False):
        centroids = build_molecular_centroids(
            series,
            frame_index=plot_data.frame_index,
            source_view=plot_data.source_view,
            use_segmentation_centroids=use_segmentation_centroids,
        )
        for centroid in centroids:
            source_kind = (
                "segmentation" if centroid.source_kind == "segmentation" else "bbox"
            )
            centroids_by_source[(source_kind, centroid.source_id)] = centroid
    return centroids_by_source


def _source_frame_time_s(series: MolTrackImageSeries, frame_index: int) -> float | None:
    source_frame_index = series.source_frame_indices[frame_index]
    frame_times = getattr(series.metadata, "frame_times_s", None)
    if frame_times is not None:
        metadata_index = source_frame_index
        if series.reverse_frame_order:
            metadata_index = len(frame_times) - source_frame_index - 1
        if 0 <= metadata_index < len(frame_times):
            return float(frame_times[metadata_index])
    frame_interval_s = getattr(series.metadata, "frame_interval_s", None)
    if frame_interval_s is None:
        return None
    return float(source_frame_index * frame_interval_s)
