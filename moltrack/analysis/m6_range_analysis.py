from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import TYPE_CHECKING, Literal, Sequence

if TYPE_CHECKING:
    from .range_analysis import MolecularFrameAnalysisResult


MolecularM6ComparisonDirection = Literal["second_minus_first"]


@dataclass(frozen=True)
class MolecularM6FrameTrendSeries:
    """Reliable per-frame M6 values without cross-frame domain matching."""

    frame_indices: tuple[int, ...]
    source_frame_indices: tuple[int, ...]
    availability_statuses: tuple[str, ...]
    unavailability_reasons: tuple[str | None, ...]
    mean_local_q6_interior: tuple[float | None, ...]
    mean_local_q6_all_valid: tuple[float | None, ...]
    global_q6_interior: tuple[float | None, ...]
    edge_truncated_fraction_of_valid_representatives: tuple[float | None, ...]
    full_domain_counts: tuple[int | None, ...]
    small_ordered_island_counts: tuple[int | None, ...]
    ordered_component_counts: tuple[int | None, ...]
    full_domain_molecule_fraction: tuple[float | None, ...]
    small_island_molecule_fraction: tuple[float | None, ...]
    unassigned_molecule_fraction: tuple[float | None, ...]
    full_domain_footprint_fraction: tuple[float | None, ...]
    small_island_footprint_fraction: tuple[float | None, ...]
    unassigned_supported_footprint_fraction: tuple[float | None, ...]
    unsupported_background_fraction: tuple[float | None, ...]
    largest_domain_molecule_fraction: tuple[float | None, ...]
    largest_domain_footprint_fraction: tuple[float | None, ...]
    full_domain_molecule_weighted_coherent_q6: tuple[float | None, ...]
    full_domain_footprint_weighted_coherent_q6: tuple[float | None, ...]
    domain_molecule_entropy: tuple[float | None, ...]
    domain_footprint_entropy: tuple[float | None, ...]


@dataclass(frozen=True)
class MolecularM6RangeAggregates:
    """Frame-weighted M6 means for one range of independent frames."""

    analyzed_frame_count: int
    available_frame_count: int
    unavailable_frame_count: int
    mean_local_q6_interior: float | None
    mean_local_q6_all_valid: float | None
    global_q6_interior: float | None
    edge_truncated_fraction_of_valid_representatives: float | None
    mean_full_domain_count: float | None
    mean_small_ordered_island_count: float | None
    mean_ordered_component_count: float | None
    full_domain_molecule_fraction: float | None
    small_island_molecule_fraction: float | None
    unassigned_molecule_fraction: float | None
    full_domain_footprint_fraction: float | None
    small_island_footprint_fraction: float | None
    unassigned_supported_footprint_fraction: float | None
    unsupported_background_fraction: float | None
    largest_domain_molecule_fraction: float | None
    largest_domain_footprint_fraction: float | None
    full_domain_molecule_weighted_coherent_q6: float | None
    full_domain_footprint_weighted_coherent_q6: float | None
    domain_molecule_entropy: float | None
    domain_footprint_entropy: float | None


@dataclass(frozen=True)
class MolecularM6RangeDifferences:
    """Second-minus-first differences between frame-weighted M6 means."""

    direction: MolecularM6ComparisonDirection
    mean_local_q6_interior_delta: float | None
    mean_local_q6_all_valid_delta: float | None
    global_q6_interior_delta: float | None
    edge_truncated_fraction_of_valid_representatives_delta: float | None
    mean_full_domain_count_delta: float | None
    mean_small_ordered_island_count_delta: float | None
    mean_ordered_component_count_delta: float | None
    full_domain_molecule_fraction_delta: float | None
    small_island_molecule_fraction_delta: float | None
    unassigned_molecule_fraction_delta: float | None
    full_domain_footprint_fraction_delta: float | None
    small_island_footprint_fraction_delta: float | None
    unassigned_supported_footprint_fraction_delta: float | None
    unsupported_background_fraction_delta: float | None
    largest_domain_molecule_fraction_delta: float | None
    largest_domain_footprint_fraction_delta: float | None
    full_domain_molecule_weighted_coherent_q6_delta: float | None
    full_domain_footprint_weighted_coherent_q6_delta: float | None
    domain_molecule_entropy_delta: float | None
    domain_footprint_entropy_delta: float | None


_METRIC_FIELDS = (
    ("mean_local_q6_interior", "mean_local_q6_interior", "mean_local_q6_interior"),
    ("mean_local_q6_all_valid", "mean_local_q6_all_valid", "mean_local_q6_all_valid"),
    ("global_q6_interior", "global_q6_interior", "global_q6_interior"),
    (
        "edge_truncated_fraction_of_valid_representatives",
        "edge_truncated_fraction_of_valid_representatives",
        "edge_truncated_fraction_of_valid_representatives",
    ),
    ("full_domain_counts", "mean_full_domain_count", "full_domain_count"),
    (
        "small_ordered_island_counts",
        "mean_small_ordered_island_count",
        "small_ordered_island_count",
    ),
    (
        "ordered_component_counts",
        "mean_ordered_component_count",
        "ordered_component_count",
    ),
    (
        "full_domain_molecule_fraction",
        "full_domain_molecule_fraction",
        "full_domain_molecule_fraction",
    ),
    (
        "small_island_molecule_fraction",
        "small_island_molecule_fraction",
        "small_island_molecule_fraction",
    ),
    (
        "unassigned_molecule_fraction",
        "unassigned_molecule_fraction",
        "unassigned_molecule_fraction",
    ),
    (
        "full_domain_footprint_fraction",
        "full_domain_footprint_fraction",
        "full_domain_footprint_fraction",
    ),
    (
        "small_island_footprint_fraction",
        "small_island_footprint_fraction",
        "small_island_footprint_fraction",
    ),
    (
        "unassigned_supported_footprint_fraction",
        "unassigned_supported_footprint_fraction",
        "unassigned_supported_footprint_fraction",
    ),
    (
        "unsupported_background_fraction",
        "unsupported_background_fraction",
        "unsupported_background_fraction",
    ),
    (
        "largest_domain_molecule_fraction",
        "largest_domain_molecule_fraction",
        "largest_domain_molecule_fraction",
    ),
    (
        "largest_domain_footprint_fraction",
        "largest_domain_footprint_fraction",
        "largest_domain_footprint_fraction",
    ),
    (
        "full_domain_molecule_weighted_coherent_q6",
        "full_domain_molecule_weighted_coherent_q6",
        "full_domain_molecule_weighted_coherent_q6",
    ),
    (
        "full_domain_footprint_weighted_coherent_q6",
        "full_domain_footprint_weighted_coherent_q6",
        "full_domain_footprint_weighted_coherent_q6",
    ),
    (
        "domain_molecule_entropy",
        "domain_molecule_entropy",
        "domain_molecule_entropy",
    ),
    (
        "domain_footprint_entropy",
        "domain_footprint_entropy",
        "domain_footprint_entropy",
    ),
)

M6_DOMAIN_TREND_FIELD_NAMES = (
    "mean_local_q6_interior",
    "mean_local_q6_all_valid",
    "global_q6_interior",
    "edge_truncated_fraction_of_valid_representatives",
    "full_domain_counts",
    "small_ordered_island_counts",
    "largest_domain_molecule_fraction",
    "largest_domain_footprint_fraction",
    "full_domain_molecule_fraction",
    "small_island_molecule_fraction",
    "unassigned_molecule_fraction",
    "full_domain_footprint_fraction",
    "small_island_footprint_fraction",
    "unassigned_supported_footprint_fraction",
    "unsupported_background_fraction",
    "full_domain_molecule_weighted_coherent_q6",
    "full_domain_footprint_weighted_coherent_q6",
    "domain_molecule_entropy",
    "domain_footprint_entropy",
)

if not set(M6_DOMAIN_TREND_FIELD_NAMES).issubset(
    {trend_name for trend_name, _aggregate_name, _source_name in _METRIC_FIELDS}
):
    raise RuntimeError("Public M6 domain trends must come from the metric registry.")


def build_molecular_m6_frame_trend_series(
    frame_results: Sequence[MolecularFrameAnalysisResult],
) -> MolecularM6FrameTrendSeries:
    """Extract M6 frame trends while retaining unavailable frame positions."""

    extracted = tuple(_extract_frame_metrics(result) for result in frame_results)
    values = {
        trend_name: tuple(
            None if aggregates is None else getattr(aggregates, source_name)
            for _, _, aggregates in extracted
        )
        for trend_name, _aggregate_name, source_name in _METRIC_FIELDS
    }
    return MolecularM6FrameTrendSeries(
        frame_indices=tuple(result.frame_index for result in frame_results),
        source_frame_indices=tuple(
            int(result.source_frame_index) for result in frame_results
        ),
        availability_statuses=tuple(status for status, _, _ in extracted),
        unavailability_reasons=tuple(reason for _, reason, _ in extracted),
        **values,
    )


def aggregate_molecular_m6_frame_range(
    frame_results: Sequence[MolecularFrameAnalysisResult],
    *,
    enabled: bool,
) -> MolecularM6RangeAggregates | None:
    """Average each available M6 metric per frame, never by pooled molecule count."""

    if not enabled:
        return None
    extracted = tuple(_extract_frame_metrics(result) for result in frame_results)
    available = tuple(
        aggregates
        for status, _reason, aggregates in extracted
        if status == "available" and aggregates is not None
    )
    means = {
        aggregate_name: _optional_finite_mean(
            tuple(getattr(aggregates, source_name) for aggregates in available)
        )
        for _trend_name, aggregate_name, source_name in _METRIC_FIELDS
    }
    return MolecularM6RangeAggregates(
        analyzed_frame_count=len(frame_results),
        available_frame_count=len(available),
        unavailable_frame_count=len(frame_results) - len(available),
        **means,
    )


def compare_molecular_m6_range_aggregates(
    second: MolecularM6RangeAggregates | None,
    first: MolecularM6RangeAggregates | None,
) -> MolecularM6RangeDifferences | None:
    """Subtract range-level frame means without matching domain identities."""

    if second is None or first is None:
        return None
    differences = {
        f"{aggregate_name}_delta": _optional_delta(
            getattr(second, aggregate_name),
            getattr(first, aggregate_name),
        )
        for _trend_name, aggregate_name, _source_name in _METRIC_FIELDS
    }
    return MolecularM6RangeDifferences(
        direction="second_minus_first",
        **differences,
    )


def _extract_frame_metrics(result: MolecularFrameAnalysisResult):
    analysis = result.m6_orientation_analysis
    if analysis is None:
        status = result.m6_orientation_availability_status
        if status == "disabled":
            status = "unavailable_missing_analysis"
        reason = (
            result.m6_orientation_unavailability_reason
            or "m6_orientation_analysis_missing"
        )
        return status, reason, None
    graph_qc = analysis.first_shell_graph.qc_status
    if graph_qc.startswith("blocking_"):
        return "unavailable_blocking_graph_qc", graph_qc, None
    return "available", None, analysis.frame_aggregates


def _optional_finite_mean(values: Sequence[float | int | None]) -> float | None:
    finite_values = tuple(
        float(value)
        for value in values
        if value is not None and isfinite(float(value))
    )
    if not finite_values:
        return None
    return float(sum(finite_values) / len(finite_values))


def _optional_delta(second: float | None, first: float | None) -> float | None:
    if second is None or first is None:
        return None
    return float(second - first)
