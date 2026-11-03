from __future__ import annotations

from dataclasses import dataclass

from moltrack.core import MolTrackImageSeries

from .frame_ranges import MolecularFrameRangeSelection
from .m6_range_analysis import (
    MolecularM6RangeDifferences,
    compare_molecular_m6_range_aggregates,
)
from .m6_settings import MolecularM6OrientationAnalysisSettings
from .range_analysis import MolecularFrameRangeAnalysis, analyze_molecular_frame_range


@dataclass(frozen=True)
class MolecularFrameRangeDifferences:
    """Second-minus-first differences between two range aggregates."""

    direction: str
    distance_unit: str
    mean_molecule_count_delta: float
    mean_nearest_neighbor_distance_delta: float | None
    mean_line_order_score_delta: float | None
    mean_intensity_delta: float | None
    median_intensity_delta: float | None
    m6_orientation: MolecularM6RangeDifferences | None = None


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
    intensity_metric: str = "background_corrected_median",
    intensity_unit: str = "a.u.",
    background_inner_radius_px: int = 1,
    background_outer_radius_px: int = 3,
    progress_callback=None,
    m6_orientation_settings: MolecularM6OrientationAnalysisSettings | None = None,
) -> MolecularFrameRangeComparison:
    """Analyze two selected conditions independently for later comparison."""

    if not isinstance(series, MolTrackImageSeries):
        raise TypeError("series must be a MolTrackImageSeries instance.")
    if not isinstance(selection, MolecularFrameRangeSelection):
        raise TypeError("selection must be a MolecularFrameRangeSelection instance.")
    if selection.frame_count != series.frame_count:
        raise ValueError("selection frame_count must match the working series.")
    first_count = len(selection.first_range.frame_indices)
    second_count = len(selection.second_range.frame_indices)
    total_count = first_count + second_count

    def first_progress(completed_count, _range_total, frame_index) -> None:
        if progress_callback is not None:
            progress_callback(completed_count, total_count, frame_index)

    def second_progress(completed_count, _range_total, frame_index) -> None:
        if progress_callback is not None:
            progress_callback(first_count + completed_count, total_count, frame_index)

    first_analysis = analyze_molecular_frame_range(
        series,
        selection.first_range,
        source_view=selection.source_view,
        use_segmentation_centroids=use_segmentation_centroids,
        intensity_metric=intensity_metric,
        intensity_unit=intensity_unit,
        background_inner_radius_px=background_inner_radius_px,
        background_outer_radius_px=background_outer_radius_px,
        progress_callback=first_progress,
        m6_orientation_settings=m6_orientation_settings,
    )
    second_analysis = analyze_molecular_frame_range(
        series,
        selection.second_range,
        source_view=selection.source_view,
        use_segmentation_centroids=use_segmentation_centroids,
        intensity_metric=intensity_metric,
        intensity_unit=intensity_unit,
        background_inner_radius_px=background_inner_radius_px,
        background_outer_radius_px=background_outer_radius_px,
        progress_callback=second_progress,
        m6_orientation_settings=m6_orientation_settings,
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
            mean_intensity_delta=_optional_delta(
                second_analysis.aggregates.mean_intensity,
                first_analysis.aggregates.mean_intensity,
            ),
            median_intensity_delta=_optional_delta(
                second_analysis.aggregates.median_intensity,
                first_analysis.aggregates.median_intensity,
            ),
            m6_orientation=compare_molecular_m6_range_aggregates(
                second_analysis.aggregates.m6_orientation,
                first_analysis.aggregates.m6_orientation,
            ),
        ),
    )


def _optional_delta(second: float | None, first: float | None) -> float | None:
    if second is None or first is None:
        return None
    return float(second - first)
