"""Source-aligned group and campaign metrics for M6 Calibration."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable

from .lattice_domain_validation import (
    LatticeDomainPartitionLabels,
    evaluate_lattice_domain_partition,
)
from .m6_calibration_campaign_models import (
    M6CalibrationAggregateMetrics,
    M6CalibrationGroupMetrics,
    M6CalibrationGroupPrediction,
    M6CalibrationMetric,
    M6CalibrationObjective,
    M6CalibrationReferenceGroup,
)


M6_FUNNEL_STAGE_ORDER = (
    "source_input",
    "centroid",
    "sample_coordinates",
    "first_shell",
    "local_order",
    "local_symmetry",
    "domain_edges",
    "seed_growth",
    "domain_size",
    "automatic_result",
)
_FUNNEL_STAGE_RANK = {
    value: index for index, value in enumerate(M6_FUNNEL_STAGE_ORDER)
}


def evaluate_m6_calibration_prediction(
    group: M6CalibrationReferenceGroup,
    prediction: M6CalibrationGroupPrediction,
    *,
    explicit_boundary: bool,
) -> M6CalibrationGroupMetrics:
    reference = _frame_local_partition(group.reference_labels)
    predicted = _frame_local_partition(_without_sources(
        prediction.labels,
        set(group.excluded_source_ids),
    ))
    report = evaluate_lattice_domain_partition(predicted, reference)
    predicted_by_id = dict(zip(
        predicted.source_ids,
        predicted.domain_labels,
    ))
    reference_by_id = dict(zip(reference.source_ids, reference.domain_labels))
    predicted_positive = {
        source_id for source_id, label in predicted_by_id.items() if label is not None
    }
    reference_positive = {
        source_id for source_id, label in reference_by_id.items() if label is not None
    }
    true_positive = len(predicted_positive & reference_positive)
    false_positive = len(predicted_positive - reference_positive)
    false_negative_ids = tuple(sorted(reference_positive - predicted_positive))
    reference_domain_count = len({
        value for value in reference.domain_labels if value is not None
    })
    boundary_counts, boundary_precision, boundary_recall = _group_boundary_metrics(
        explicit_boundary,
        group.reference_boundary_available,
        (
            report.boundary_true_positive_count,
            report.boundary_false_positive_count,
            report.boundary_false_negative_count,
        ),
    )
    return M6CalibrationGroupMetrics(
        measurement_group_id=group.measurement_group_id,
        evaluated_molecule_count=report.evaluated_molecule_count,
        abstention_count=group.abstention_count,
        membership_true_positive_count=true_positive,
        membership_false_positive_count=false_positive,
        membership_false_negative_count=len(false_negative_ids),
        membership_precision=_safe_ratio(
            true_positive,
            true_positive + false_positive,
        ),
        membership_recall=_safe_ratio(
            true_positive,
            true_positive + len(false_negative_ids),
        ),
        adjusted_rand_index=report.adjusted_rand_index,
        variation_of_information_nats=report.variation_of_information_nats,
        correctly_assigned_molecule_fraction=(
            report.correctly_assigned_molecule_fraction or 0.0
        ),
        absolute_domain_count_error=abs(report.domain_count_error),
        reference_domain_count=reference_domain_count,
        split_count=report.over_segmentation_count,
        merge_count=report.under_segmentation_count,
        split_rate=_safe_rate(
            report.over_segmentation_count,
            reference_domain_count,
        ),
        merge_rate=_safe_rate(
            report.under_segmentation_count,
            reference_domain_count,
        ),
        boundary_true_positive_count=boundary_counts[0],
        boundary_false_positive_count=boundary_counts[1],
        boundary_false_negative_count=boundary_counts[2],
        boundary_precision=boundary_precision,
        boundary_recall=boundary_recall,
        funnel_misses=_funnel_misses(
            false_negative_ids,
            prediction.failed_stage_ids,
        ),
    )


def aggregate_m6_calibration_metrics(
    groups: tuple[M6CalibrationGroupMetrics, ...],
) -> M6CalibrationAggregateMetrics:
    true_positive = sum(value.membership_true_positive_count for value in groups)
    false_positive = sum(value.membership_false_positive_count for value in groups)
    false_negative = sum(value.membership_false_negative_count for value in groups)
    boundary_precision, boundary_recall = _aggregate_boundary_metrics(groups)
    misses = Counter[str]()
    for value in groups:
        misses.update(dict(value.funnel_misses))
    return M6CalibrationAggregateMetrics(
        measurement_group_count=len(groups),
        evaluated_molecule_count=sum(value.evaluated_molecule_count for value in groups),
        abstention_count=sum(value.abstention_count for value in groups),
        membership_true_positive_count=true_positive,
        membership_false_positive_count=false_positive,
        membership_false_negative_count=false_negative,
        macro_membership_precision=_complete_mean(
            value.membership_precision for value in groups
        ),
        macro_membership_recall=_complete_mean(
            value.membership_recall for value in groups
        ),
        micro_membership_precision=_safe_ratio(
            true_positive,
            true_positive + false_positive,
        ),
        micro_membership_recall=_safe_ratio(
            true_positive,
            true_positive + false_negative,
        ),
        macro_adjusted_rand_index=_mean(
            value.adjusted_rand_index for value in groups
        ),
        macro_variation_of_information_nats=_mean(
            value.variation_of_information_nats for value in groups
        ),
        macro_correctly_assigned_molecule_fraction=_mean(
            value.correctly_assigned_molecule_fraction for value in groups
        ),
        macro_absolute_domain_count_error=_mean(
            float(value.absolute_domain_count_error) for value in groups
        ),
        split_count=sum(value.split_count for value in groups),
        merge_count=sum(value.merge_count for value in groups),
        macro_split_rate=_mean(value.split_rate for value in groups),
        macro_merge_rate=_mean(value.merge_rate for value in groups),
        boundary_precision=boundary_precision,
        boundary_recall=boundary_recall,
        funnel_misses=tuple(
            (stage_id, misses[stage_id])
            for stage_id in M6_FUNNEL_STAGE_ORDER
            if misses[stage_id]
        ),
    )


def m6_calibration_objective_loss(
    metrics: M6CalibrationAggregateMetrics,
    objective: M6CalibrationObjective,
) -> float | None:
    recall = metrics.macro_membership_recall
    if recall is None:
        return None
    return (
        1.0
        - recall
        + objective.split_weight * metrics.macro_split_rate
        + objective.merge_weight * metrics.macro_merge_rate
    )


def m6_local_partition_stability(
    baseline: M6CalibrationGroupPrediction,
    changed: M6CalibrationGroupPrediction,
    excluded_source_ids: tuple[str, ...],
) -> float:
    excluded = set(excluded_source_ids)
    baseline_labels = _frame_local_partition(
        _without_sources(baseline.labels, excluded)
    )
    changed_labels = _frame_local_partition(
        _without_sources(changed.labels, excluded)
    )
    return evaluate_lattice_domain_partition(
        changed_labels,
        baseline_labels,
    ).adjusted_rand_index


def _boundary_metrics(
    explicit_boundary: bool,
    reference_available: bool,
    true_positive: int,
    false_positive: int,
    false_negative: int,
) -> tuple[M6CalibrationMetric, M6CalibrationMetric]:
    if not explicit_boundary:
        unavailable = M6CalibrationMetric.unavailable(
            "boundary_or_disordered_is_ambiguous"
        )
        return unavailable, unavailable
    if not reference_available:
        unavailable = M6CalibrationMetric.unavailable(
            "reference_boundary_unavailable"
        )
        return unavailable, unavailable
    return (
        M6CalibrationMetric.available(_safe_ratio(
            true_positive,
            true_positive + false_positive,
        )),
        M6CalibrationMetric.available(_safe_ratio(
            true_positive,
            true_positive + false_negative,
        )),
    )


def _group_boundary_metrics(
    explicit_boundary: bool,
    reference_available: bool,
    counts: tuple[int, int, int],
) -> tuple[
    tuple[int | None, int | None, int | None],
    M6CalibrationMetric,
    M6CalibrationMetric,
]:
    precision, recall = _boundary_metrics(
        explicit_boundary,
        reference_available,
        *counts,
    )
    reported_counts: tuple[int | None, int | None, int | None] = (
        counts if precision.status == "available" else (None, None, None)
    )
    return reported_counts, precision, recall


def _aggregate_boundary_metrics(
    groups: tuple[M6CalibrationGroupMetrics, ...],
) -> tuple[M6CalibrationMetric, M6CalibrationMetric]:
    unavailable = next(
        (
            value.boundary_precision
            for value in groups
            if value.boundary_precision.status == "unavailable"
        ),
        None,
    )
    if unavailable is not None:
        return unavailable, M6CalibrationMetric.unavailable(str(unavailable.reason))
    counts = tuple(
        sum(int(getattr(value, field_name) or 0) for value in groups)
        for field_name in (
            "boundary_true_positive_count",
            "boundary_false_positive_count",
            "boundary_false_negative_count",
        )
    )
    return _boundary_metrics(True, True, *counts)


def _funnel_misses(
    false_negative_ids: tuple[str, ...],
    failures: tuple[tuple[str, tuple[str, ...]], ...],
) -> tuple[tuple[str, int], ...]:
    failures_by_id = dict(failures)
    misses = Counter[str]()
    for source_id in false_negative_ids:
        stage_ids = failures_by_id.get(source_id, ())
        if set(stage_ids).difference(_FUNNEL_STAGE_RANK):
            raise ValueError(
                "M6 campaign prediction contains an unsupported funnel stage."
            )
        earliest = min(
            stage_ids,
            key=_FUNNEL_STAGE_RANK.__getitem__,
            default="automatic_result",
        )
        misses[earliest] += 1
    if sum(misses.values()) != len(false_negative_ids):
        raise AssertionError("Funnel miss attribution must sum to membership FN.")
    return tuple(
        (stage_id, misses[stage_id])
        for stage_id in M6_FUNNEL_STAGE_ORDER
        if misses[stage_id]
    )


def _without_sources(
    labels: LatticeDomainPartitionLabels,
    excluded: set[str],
) -> LatticeDomainPartitionLabels:
    kept = tuple(
        index
        for index, source_id in enumerate(labels.source_ids)
        if source_id not in excluded
    )
    return LatticeDomainPartitionLabels(
        source_ids=tuple(labels.source_ids[index] for index in kept),
        domain_labels=tuple(labels.domain_labels[index] for index in kept),
        boundary=tuple(labels.boundary[index] for index in kept),
        confidence=tuple(labels.confidence[index] for index in kept),
    )


def _frame_local_partition(
    labels: LatticeDomainPartitionLabels,
) -> LatticeDomainPartitionLabels:
    domain_labels = tuple(
        None
        if label is None
        else f"{source_id.rpartition('::')[0]}::{label}"
        for source_id, label in zip(labels.source_ids, labels.domain_labels)
    )
    return LatticeDomainPartitionLabels(
        source_ids=labels.source_ids,
        domain_labels=domain_labels,
        boundary=labels.boundary,
        confidence=labels.confidence,
    )


def _mean(values: Iterable[float]) -> float:
    items = tuple(values)
    if not items:
        raise ValueError("At least one metric value is required.")
    return sum(items) / len(items)


def _complete_mean(values: Iterable[float | None]) -> float | None:
    items = tuple(values)
    if not items or any(value is None for value in items):
        return None
    return _mean(float(value) for value in items if value is not None)


def _safe_ratio(numerator: int, denominator: int) -> float | None:
    return None if denominator == 0 else numerator / denominator


def _safe_rate(numerator: int, denominator: int) -> float:
    return 0.0 if denominator == 0 else numerator / denominator


__all__ = [
    "aggregate_m6_calibration_metrics",
    "evaluate_m6_calibration_prediction",
    "m6_calibration_objective_loss",
    "m6_local_partition_stability",
]
