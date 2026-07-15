from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .range_analysis import MolecularFrameRangeAnalysis
from .range_comparison import MolecularFrameRangeComparison


@dataclass(frozen=True)
class MolecularConditionSpatialData:
    """Pooled molecular positions for one condition, without cross-frame links."""

    condition_name: str
    points_xy: tuple[tuple[float, float], ...]
    intensity_values: tuple[float | None, ...]
    density_grid: tuple[tuple[float, ...], ...]
    intensity_grid: tuple[tuple[float, ...], ...]


@dataclass(frozen=True)
class MolecularRangeSpatialComparisonData:
    """Spatial comparison data for two conditions on shared axes."""

    first: MolecularConditionSpatialData
    second: MolecularConditionSpatialData
    unit: str
    x_range: tuple[float, float]
    y_range: tuple[float, float]
    density_x_edges: tuple[float, ...]
    density_y_edges: tuple[float, ...]
    density_value_range: tuple[float, float]
    density_unit: str
    intensity_value_range: tuple[float, float] | None
    intensity_metric: str
    intensity_unit: str
    aggregation_mode: str = "pooled_positions_without_tracking"


def build_molecular_range_spatial_comparison_data(
    comparison: MolecularFrameRangeComparison,
    *,
    density_grid_shape: tuple[int, int] = (32, 32),
) -> MolecularRangeSpatialComparisonData:
    """Pool positions independently for two ranges and preserve shared geometry."""

    if not isinstance(comparison, MolecularFrameRangeComparison):
        raise TypeError("comparison must be a MolecularFrameRangeComparison instance.")
    analyses = (comparison.first_analysis, comparison.second_analysis)
    plot_data = tuple(
        frame_result.plot_data
        for analysis in analyses
        for frame_result in analysis.frame_results
    )
    units = {frame.unit for frame in plot_data}
    if len(units) != 1:
        raise ValueError("Compared ranges must use one common position unit.")
    rows, columns = _normalize_density_grid_shape(density_grid_shape)
    x_range = (
        min(frame.x_range[0] for frame in plot_data),
        max(frame.x_range[1] for frame in plot_data),
    )
    y_range = (
        min(frame.y_range[0] for frame in plot_data),
        max(frame.y_range[1] for frame in plot_data),
    )
    x_edges = np.linspace(x_range[0], x_range[1], columns + 1, dtype=np.float64)
    y_edges = np.linspace(y_range[0], y_range[1], rows + 1, dtype=np.float64)
    first = _build_condition_spatial_data(
        comparison.first_analysis,
        x_edges=x_edges,
        y_edges=y_edges,
    )
    second = _build_condition_spatial_data(
        comparison.second_analysis,
        x_edges=x_edges,
        y_edges=y_edges,
    )
    maximum_density = max(
        _maximum_density(first.density_grid),
        _maximum_density(second.density_grid),
    )
    finite_intensities = tuple(
        float(value)
        for condition in (first, second)
        for value in condition.intensity_values
        if value is not None and np.isfinite(float(value))
    )
    intensity_value_range = (
        None
        if not finite_intensities
        else (min(finite_intensities), max(finite_intensities))
    )
    return MolecularRangeSpatialComparisonData(
        first=first,
        second=second,
        unit=next(iter(units)),
        x_range=x_range,
        y_range=y_range,
        density_x_edges=tuple(float(value) for value in x_edges),
        density_y_edges=tuple(float(value) for value in y_edges),
        density_value_range=(0.0, maximum_density),
        density_unit="molecules_per_frame_per_bin",
        intensity_value_range=intensity_value_range,
        intensity_metric=comparison.first_analysis.intensity_metric,
        intensity_unit=comparison.first_analysis.intensity_unit,
    )


def _build_condition_spatial_data(
    analysis: MolecularFrameRangeAnalysis,
    *,
    x_edges: np.ndarray,
    y_edges: np.ndarray,
) -> MolecularConditionSpatialData:
    points_xy = tuple(
        point
        for frame_result in analysis.frame_results
        for point in frame_result.plot_data.points_xy
    )
    intensity_values = tuple(
        value
        for frame_result in analysis.frame_results
        for value in frame_result.plot_data.intensity_values
    )
    if points_xy:
        points = np.asarray(points_xy, dtype=np.float64)
        counts, _y_edges, _x_edges = np.histogram2d(
            points[:, 1],
            points[:, 0],
            bins=(y_edges, x_edges),
        )
    else:
        points = np.empty((0, 2), dtype=np.float64)
        counts = np.zeros((len(y_edges) - 1, len(x_edges) - 1), dtype=np.float64)
    density = counts / len(analysis.frame_results)
    intensity_array = np.asarray(
        [np.nan if value is None else float(value) for value in intensity_values],
        dtype=np.float64,
    )
    finite = np.isfinite(intensity_array)
    intensity_sums, _y_edges, _x_edges = np.histogram2d(
        points[finite, 1],
        points[finite, 0],
        bins=(y_edges, x_edges),
        weights=intensity_array[finite],
    )
    intensity_counts, _y_edges, _x_edges = np.histogram2d(
        points[finite, 1],
        points[finite, 0],
        bins=(y_edges, x_edges),
    )
    intensity_grid = np.full(intensity_sums.shape, np.nan, dtype=np.float64)
    np.divide(
        intensity_sums,
        intensity_counts,
        out=intensity_grid,
        where=intensity_counts > 0.0,
    )
    return MolecularConditionSpatialData(
        condition_name=analysis.frame_range.name,
        points_xy=points_xy,
        intensity_values=intensity_values,
        density_grid=tuple(tuple(float(value) for value in row) for row in density),
        intensity_grid=tuple(
            tuple(float(value) for value in row) for row in intensity_grid
        ),
    )


def _normalize_density_grid_shape(density_grid_shape: tuple[int, int]) -> tuple[int, int]:
    try:
        rows, columns = (int(value) for value in density_grid_shape)
    except (TypeError, ValueError) as exc:
        raise ValueError("density_grid_shape must contain rows and columns.") from exc
    if rows <= 0 or columns <= 0:
        raise ValueError("density_grid_shape values must be positive.")
    return rows, columns


def _maximum_density(density_grid: tuple[tuple[float, ...], ...]) -> float:
    return max((value for row in density_grid for value in row), default=0.0)
