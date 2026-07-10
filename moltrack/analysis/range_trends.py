from __future__ import annotations

from dataclasses import dataclass

from .range_analysis import MolecularFrameRangeAnalysis
from .range_comparison import MolecularFrameRangeComparison


@dataclass(frozen=True)
class MolecularRangeTrendSeries:
    """Per-frame trend values for one named experimental condition."""

    condition_name: str
    frame_indices: tuple[int, ...]
    molecule_counts: tuple[int, ...]
    nearest_neighbor_distances: tuple[float | None, ...]
    line_order_scores: tuple[float | None, ...]
    distance_unit: str


@dataclass(frozen=True)
class MolecularRangeComparisonTrendData:
    """Two separate condition trends ready for comparison plots."""

    first: MolecularRangeTrendSeries
    second: MolecularRangeTrendSeries


def build_molecular_range_comparison_trend_data(
    comparison: MolecularFrameRangeComparison,
) -> MolecularRangeComparisonTrendData:
    """Build plotting data without joining observations across frames."""

    if not isinstance(comparison, MolecularFrameRangeComparison):
        raise TypeError("comparison must be a MolecularFrameRangeComparison instance.")
    return MolecularRangeComparisonTrendData(
        first=_build_range_trend_series(comparison.first_analysis),
        second=_build_range_trend_series(comparison.second_analysis),
    )


def _build_range_trend_series(analysis: MolecularFrameRangeAnalysis) -> MolecularRangeTrendSeries:
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
    )
