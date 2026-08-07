from __future__ import annotations

from dataclasses import dataclass

from .m6_range_analysis import (
    MolecularM6FrameTrendSeries,
    build_molecular_m6_frame_trend_series,
)
from .range_analysis import MolecularFrameRangeAnalysis


@dataclass(frozen=True)
class MolecularRangeTrendSeries:
    """Per-frame trend values for one named experimental condition."""

    condition_name: str
    frame_indices: tuple[int, ...]
    molecule_counts: tuple[int, ...]
    nearest_neighbor_distances: tuple[float | None, ...]
    line_order_scores: tuple[float | None, ...]
    distance_unit: str
    mean_intensities: tuple[float | None, ...]
    median_intensities: tuple[float | None, ...]
    intensity_metric: str
    intensity_unit: str
    m6_orientation: MolecularM6FrameTrendSeries | None = None


MolecularRangeTrendData = MolecularRangeTrendSeries


def unpack_molecular_range_trend_data(
    trend_data: MolecularRangeTrendData | None,
) -> tuple[MolecularRangeTrendSeries, ...]:
    """Return the real one- or two-series content of range trend data."""

    if isinstance(trend_data, MolecularRangeTrendSeries):
        return (trend_data,)
    if trend_data is None:
        return ()
    raise TypeError("trend_data must be a range trend series or None.")


def build_molecular_range_trend_series(
    analysis: MolecularFrameRangeAnalysis,
) -> MolecularRangeTrendSeries:
    """Build plotting data for one analyzed frame range."""

    if not isinstance(analysis, MolecularFrameRangeAnalysis):
        raise TypeError("analysis must be a MolecularFrameRangeAnalysis instance.")
    return MolecularRangeTrendSeries(
        condition_name=analysis.frame_range.name,
        frame_indices=tuple(result.frame_index for result in analysis.frame_results),
        molecule_counts=tuple(result.point_count for result in analysis.frame_results),
        nearest_neighbor_distances=tuple(
            result.distance_metrics.mean_distance for result in analysis.frame_results
        ),
        line_order_scores=tuple(
            result.angle_metrics.line_order_score for result in analysis.frame_results
        ),
        distance_unit=analysis.aggregates.distance_unit,
        mean_intensities=tuple(
            result.mean_intensity for result in analysis.frame_results
        ),
        median_intensities=tuple(
            result.median_intensity for result in analysis.frame_results
        ),
        intensity_metric=analysis.intensity_metric,
        intensity_unit=analysis.intensity_unit,
        m6_orientation=(
            None
            if analysis.aggregates.m6_orientation is None
            else build_molecular_m6_frame_trend_series(analysis.frame_results)
        ),
    )
