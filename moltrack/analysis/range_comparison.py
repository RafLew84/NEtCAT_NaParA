from __future__ import annotations

from dataclasses import dataclass

from moltrack.core import MolTrackImageSeries

from .frame_ranges import MolecularFrameRangeSelection
from .range_analysis import MolecularFrameRangeAnalysis, analyze_molecular_frame_range


@dataclass(frozen=True)
class MolecularFrameRangeDifferences:
    """Second-minus-first differences between two range aggregates."""

    direction: str
    distance_unit: str
    mean_molecule_count_delta: float
    mean_nearest_neighbor_distance_delta: float | None
    mean_line_order_score_delta: float | None


@dataclass(frozen=True)
class MolecularFrameRangeComparison:
    """Two named molecular-position range analyses in one source view."""

    source_view: str
    first_analysis: MolecularFrameRangeAnalysis
    second_analysis: MolecularFrameRangeAnalysis
    differences: MolecularFrameRangeDifferences
    analysis_mode: str = "frame_position_distributions_without_tracking"
    uses_tracking: bool = False


def compare_molecular_frame_ranges(
    series: MolTrackImageSeries,
    selection: MolecularFrameRangeSelection,
    *,
    use_segmentation_centroids: bool = True,
) -> MolecularFrameRangeComparison:
    """Analyze two selected conditions independently for later comparison."""

    if not isinstance(series, MolTrackImageSeries):
        raise TypeError("series must be a MolTrackImageSeries instance.")
    if not isinstance(selection, MolecularFrameRangeSelection):
        raise TypeError("selection must be a MolecularFrameRangeSelection instance.")
    if selection.frame_count != series.frame_count:
        raise ValueError("selection frame_count must match the working series.")
    first_analysis = analyze_molecular_frame_range(
        series,
        selection.first_range,
        source_view=selection.source_view,
        use_segmentation_centroids=use_segmentation_centroids,
    )
    second_analysis = analyze_molecular_frame_range(
        series,
        selection.second_range,
        source_view=selection.source_view,
        use_segmentation_centroids=use_segmentation_centroids,
    )
    return MolecularFrameRangeComparison(
        source_view=selection.source_view,
        first_analysis=first_analysis,
        second_analysis=second_analysis,
        differences=MolecularFrameRangeDifferences(
            direction="second_minus_first",
            distance_unit=first_analysis.aggregates.distance_unit,
            mean_molecule_count_delta=(
                second_analysis.aggregates.mean_molecule_count
                - first_analysis.aggregates.mean_molecule_count
            ),
            mean_nearest_neighbor_distance_delta=_optional_delta(
                second_analysis.aggregates.mean_nearest_neighbor_distance,
                first_analysis.aggregates.mean_nearest_neighbor_distance,
            ),
            mean_line_order_score_delta=_optional_delta(
                second_analysis.aggregates.mean_line_order_score,
                first_analysis.aggregates.mean_line_order_score,
            ),
        ),
    )


def _optional_delta(second: float | None, first: float | None) -> float | None:
    if second is None or first is None:
        return None
    return float(second - first)
