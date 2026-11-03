"""Permutation-invariant validation metrics for final lattice-domain partitions."""

from __future__ import annotations

from dataclasses import dataclass
from math import comb, isfinite, log

import numpy as np
from scipy.optimize import linear_sum_assignment

from .lattice_domain_models import LatticeDomainAnalysis


_MISSING_SOURCE = object()


@dataclass(frozen=True)
class LatticeDomainPartitionLabels:
    """One domain partition aligned by stable molecule source IDs."""

    source_ids: tuple[str, ...]
    domain_labels: tuple[str | None, ...]
    boundary: tuple[bool, ...]
    confidence: tuple[float | None, ...]

    def __post_init__(self) -> None:
        source_ids = tuple(self.source_ids)
        labels = tuple(self.domain_labels)
        boundary = tuple(self.boundary)
        confidence = tuple(self.confidence)
        count = len(source_ids)
        if not (len(labels) == len(boundary) == len(confidence) == count):
            raise ValueError("Partition label arrays must have equal lengths.")
        if len(set(source_ids)) != count or any(
            not isinstance(value, str) or not value for value in source_ids
        ):
            raise ValueError("source_ids must be unique non-empty strings.")
        if any(
            value is not None and (not isinstance(value, str) or not value)
            for value in labels
        ):
            raise ValueError("domain_labels must contain non-empty strings or None.")
        if any(not isinstance(value, bool) for value in boundary):
            raise TypeError("boundary must contain booleans.")
        for value in confidence:
            if value is None:
                continue
            normalized = float(value)
            if not isfinite(normalized) or not 0.0 <= normalized <= 1.0:
                raise ValueError("confidence values must lie between 0 and 1.")
        object.__setattr__(self, "source_ids", source_ids)
        object.__setattr__(self, "domain_labels", labels)
        object.__setattr__(self, "boundary", boundary)
        object.__setattr__(self, "confidence", confidence)


@dataclass(frozen=True)
class LatticeDomainValidationReport:
    evaluated_molecule_count: int
    missing_prediction_molecule_count: int
    unexpected_prediction_molecule_count: int
    adjusted_rand_index: float
    variation_of_information_nats: float
    predicted_domain_count: int
    reference_domain_count: int
    domain_count_error: int
    over_segmentation_count: int
    under_segmentation_count: int
    boundary_true_positive_count: int
    boundary_false_positive_count: int
    boundary_false_negative_count: int
    boundary_precision: float | None
    boundary_recall: float | None
    correctly_assigned_molecule_fraction: float | None
    confidence_brier_score: float | None
    confidence_expected_calibration_error: float | None
    partition_stability_ari: float | None


def lattice_domain_partition_labels_from_analysis(
    analysis: LatticeDomainAnalysis,
) -> LatticeDomainPartitionLabels:
    if not isinstance(analysis, LatticeDomainAnalysis):
        raise TypeError("analysis must be LatticeDomainAnalysis.")
    confidence_by_id = {
        component.lattice_domain_id: component.confidence
        for component in analysis.components
    }
    return LatticeDomainPartitionLabels(
        source_ids=analysis.source_ids,
        domain_labels=analysis.point_lattice_domain_id,
        boundary=tuple(role == "boundary" for role in analysis.point_role),
        confidence=tuple(
            None if domain_id is None else confidence_by_id[domain_id]
            for domain_id in analysis.point_lattice_domain_id
        ),
    )


def evaluate_lattice_domain_analysis(
    analysis: LatticeDomainAnalysis,
    reference: LatticeDomainPartitionLabels,
    *,
    stability_reference: LatticeDomainAnalysis | None = None,
) -> LatticeDomainValidationReport:
    return evaluate_lattice_domain_partition(
        lattice_domain_partition_labels_from_analysis(analysis),
        reference,
        stability_reference=(
            None
            if stability_reference is None
            else lattice_domain_partition_labels_from_analysis(stability_reference)
        ),
    )


def evaluate_lattice_domain_partition(
    predicted: LatticeDomainPartitionLabels,
    reference: LatticeDomainPartitionLabels,
    *,
    stability_reference: LatticeDomainPartitionLabels | None = None,
) -> LatticeDomainValidationReport:
    """Compare clustering, boundaries, confidence, and optional stability."""

    if not isinstance(predicted, LatticeDomainPartitionLabels):
        raise TypeError("predicted must be LatticeDomainPartitionLabels.")
    if not isinstance(reference, LatticeDomainPartitionLabels):
        raise TypeError("reference must be LatticeDomainPartitionLabels.")
    source_ids, predicted_rows, reference_rows = _aligned_rows(predicted, reference)
    if not source_ids:
        raise ValueError("Predicted and reference partitions have no common source IDs.")
    predicted_labels = tuple(
        row[0] if row[3] else _MISSING_SOURCE for row in predicted_rows
    )
    reference_labels = tuple(
        row[0] if row[3] else _MISSING_SOURCE for row in reference_rows
    )
    predicted_boundary = tuple(row[1] if row[3] else False for row in predicted_rows)
    reference_boundary = tuple(row[1] if row[3] else False for row in reference_rows)

    adjusted_rand = _adjusted_rand_index(predicted_labels, reference_labels)
    variation = _variation_of_information(predicted_labels, reference_labels)
    label_mapping = _optimal_label_mapping(
        tuple(row[0] if row[3] else None for row in predicted_rows),
        tuple(row[0] if row[3] else None for row in reference_rows),
    )
    correct_by_index = {
        index: (
            predicted_rows[index][3]
            and reference_rows[index][3]
            and (
                (
                    reference_rows[index][0] is None
                    and predicted_rows[index][0] is None
                )
                or (
                    reference_rows[index][0] is not None
                    and predicted_rows[index][0] is not None
                    and label_mapping.get(predicted_rows[index][0])
                    == reference_rows[index][0]
                )
            )
        )
        for index in range(len(source_ids))
    }
    correct_fraction = sum(correct_by_index.values()) / len(source_ids)

    true_positive = sum(
        predicted_value and reference_value
        for predicted_value, reference_value in zip(
            predicted_boundary,
            reference_boundary,
        )
    )
    false_positive = sum(
        predicted_value and not reference_value
        for predicted_value, reference_value in zip(
            predicted_boundary,
            reference_boundary,
        )
    )
    false_negative = sum(
        not predicted_value and reference_value
        for predicted_value, reference_value in zip(
            predicted_boundary,
            reference_boundary,
        )
    )
    predicted_domain_count = len(
        {row[0] for row in predicted_rows if row[3] and row[0] is not None}
    )
    reference_domain_count = len(
        {row[0] for row in reference_rows if row[3] and row[0] is not None}
    )
    count_error = predicted_domain_count - reference_domain_count
    over_segmentation_count, under_segmentation_count = _split_merge_counts(
        predicted_rows,
        reference_rows,
    )

    confidence_values: list[float] = []
    confidence_correctness: list[float] = []
    for index in range(len(source_ids)):
        confidence = predicted_rows[index][2]
        if confidence is None or not predicted_rows[index][3]:
            continue
        confidence_values.append(float(confidence))
        confidence_correctness.append(float(correct_by_index[index]))
    brier, calibration_error = _confidence_calibration(
        confidence_values,
        confidence_correctness,
    )

    stability = None
    if stability_reference is not None:
        if not isinstance(stability_reference, LatticeDomainPartitionLabels):
            raise TypeError(
                "stability_reference must be LatticeDomainPartitionLabels or None."
            )
        _stable_ids, stable_predicted, stable_reference = _aligned_rows(
            predicted,
            stability_reference,
        )
        if not _stable_ids:
            raise ValueError(
                "Predicted and stability partitions have no common source IDs."
            )
        stability = _adjusted_rand_index(
            tuple(row[0] if row[3] else _MISSING_SOURCE for row in stable_predicted),
            tuple(row[0] if row[3] else _MISSING_SOURCE for row in stable_reference),
        )

    return LatticeDomainValidationReport(
        evaluated_molecule_count=len(source_ids),
        missing_prediction_molecule_count=len(
            set(reference.source_ids).difference(predicted.source_ids)
        ),
        unexpected_prediction_molecule_count=len(
            set(predicted.source_ids).difference(reference.source_ids)
        ),
        adjusted_rand_index=adjusted_rand,
        variation_of_information_nats=variation,
        predicted_domain_count=predicted_domain_count,
        reference_domain_count=reference_domain_count,
        domain_count_error=count_error,
        over_segmentation_count=over_segmentation_count,
        under_segmentation_count=under_segmentation_count,
        boundary_true_positive_count=true_positive,
        boundary_false_positive_count=false_positive,
        boundary_false_negative_count=false_negative,
        boundary_precision=_safe_ratio(true_positive, true_positive + false_positive),
        boundary_recall=_safe_ratio(true_positive, true_positive + false_negative),
        correctly_assigned_molecule_fraction=correct_fraction,
        confidence_brier_score=brier,
        confidence_expected_calibration_error=calibration_error,
        partition_stability_ari=stability,
    )


def _aligned_rows(
    left: LatticeDomainPartitionLabels,
    right: LatticeDomainPartitionLabels,
) -> tuple[
    tuple[str, ...],
    tuple[tuple[str | None, bool, float | None, bool], ...],
    tuple[tuple[str | None, bool, float | None, bool], ...],
]:
    left_by_id = dict(
        zip(left.source_ids, zip(left.domain_labels, left.boundary, left.confidence))
    )
    right_by_id = dict(
        zip(right.source_ids, zip(right.domain_labels, right.boundary, right.confidence))
    )
    source_ids = tuple(sorted(set(left_by_id).union(right_by_id)))
    return (
        source_ids,
        tuple(
            (*left_by_id[source_id], True)
            if source_id in left_by_id
            else (None, False, None, False)
            for source_id in source_ids
        ),
        tuple(
            (*right_by_id[source_id], True)
            if source_id in right_by_id
            else (None, False, None, False)
            for source_id in source_ids
        ),
    )


def _split_merge_counts(
    predicted_rows: tuple[tuple[str | None, bool, float | None, bool], ...],
    reference_rows: tuple[tuple[str | None, bool, float | None, bool], ...],
) -> tuple[int, int]:
    predicted_labels = {
        row[0] for row in predicted_rows if row[3] and row[0] is not None
    }
    reference_labels = {
        row[0] for row in reference_rows if row[3] and row[0] is not None
    }
    predicted_by_reference = {label: set() for label in reference_labels}
    reference_by_predicted = {label: set() for label in predicted_labels}
    for predicted_row, reference_row in zip(predicted_rows, reference_rows):
        predicted_label = predicted_row[0] if predicted_row[3] else None
        reference_label = reference_row[0] if reference_row[3] else None
        if predicted_label is None or reference_label is None:
            continue
        predicted_by_reference[reference_label].add(predicted_label)
        reference_by_predicted[predicted_label].add(reference_label)
    over_segmentation = sum(
        max(0, len(overlaps) - 1)
        for overlaps in predicted_by_reference.values()
    ) + sum(not reference_by_predicted[label] for label in predicted_labels)
    under_segmentation = sum(
        max(0, len(overlaps) - 1)
        for overlaps in reference_by_predicted.values()
    ) + sum(not predicted_by_reference[label] for label in reference_labels)
    return int(over_segmentation), int(under_segmentation)


def _adjusted_rand_index(
    left: tuple[object, ...],
    right: tuple[object, ...],
) -> float:
    if len(left) != len(right):
        raise ValueError("ARI partitions must have equal lengths.")
    count = len(left)
    if count < 2:
        return 1.0
    contingency, _left_labels, _right_labels = _contingency(left, right)
    sum_cells = sum(comb(int(value), 2) for value in contingency.flat)
    sum_left = sum(comb(int(value), 2) for value in contingency.sum(axis=1))
    sum_right = sum(comb(int(value), 2) for value in contingency.sum(axis=0))
    pair_count = comb(count, 2)
    expected = sum_left * sum_right / pair_count
    maximum = 0.5 * (sum_left + sum_right)
    denominator = maximum - expected
    if abs(denominator) <= 1e-15:
        return 1.0
    return float((sum_cells - expected) / denominator)


def _variation_of_information(
    left: tuple[object, ...],
    right: tuple[object, ...],
) -> float:
    contingency, _left_labels, _right_labels = _contingency(left, right)
    total = float(contingency.sum())
    if total == 0.0:
        return 0.0
    left_probabilities = contingency.sum(axis=1) / total
    right_probabilities = contingency.sum(axis=0) / total
    entropy_left = -sum(value * log(value) for value in left_probabilities if value > 0)
    entropy_right = -sum(value * log(value) for value in right_probabilities if value > 0)
    mutual_information = 0.0
    for left_index, right_index in zip(*np.nonzero(contingency)):
        joint = contingency[left_index, right_index] / total
        mutual_information += joint * log(
            joint / (left_probabilities[left_index] * right_probabilities[right_index])
        )
    return float(max(0.0, entropy_left + entropy_right - 2.0 * mutual_information))


def _contingency(
    left: tuple[object, ...],
    right: tuple[object, ...],
) -> tuple[np.ndarray, tuple[object, ...], tuple[object, ...]]:
    missing = ("__unassigned__",)
    normalized_left = tuple(missing if value is None else value for value in left)
    normalized_right = tuple(missing if value is None else value for value in right)
    left_labels = tuple(sorted(set(normalized_left), key=repr))
    right_labels = tuple(sorted(set(normalized_right), key=repr))
    left_index = {value: index for index, value in enumerate(left_labels)}
    right_index = {value: index for index, value in enumerate(right_labels)}
    matrix = np.zeros((len(left_labels), len(right_labels)), dtype=np.int64)
    for left_value, right_value in zip(normalized_left, normalized_right):
        matrix[left_index[left_value], right_index[right_value]] += 1
    return matrix, left_labels, right_labels


def _optimal_label_mapping(
    predicted: tuple[str | None, ...],
    reference: tuple[str | None, ...],
) -> dict[str, str]:
    predicted_labels = tuple(sorted({value for value in predicted if value is not None}))
    reference_labels = tuple(sorted({value for value in reference if value is not None}))
    if not predicted_labels or not reference_labels:
        return {}
    matrix = np.zeros((len(predicted_labels), len(reference_labels)), dtype=np.int64)
    predicted_index = {value: index for index, value in enumerate(predicted_labels)}
    reference_index = {value: index for index, value in enumerate(reference_labels)}
    for predicted_value, reference_value in zip(predicted, reference):
        if predicted_value is None or reference_value is None:
            continue
        matrix[predicted_index[predicted_value], reference_index[reference_value]] += 1
    rows, columns = linear_sum_assignment(-matrix)
    return {
        predicted_labels[row]: reference_labels[column]
        for row, column in zip(rows, columns)
        if matrix[row, column] > 0
    }


def _confidence_calibration(
    confidence: list[float],
    correctness: list[float],
) -> tuple[float | None, float | None]:
    if not confidence:
        return None, None
    confidence_array = np.asarray(confidence, dtype=np.float64)
    correctness_array = np.asarray(correctness, dtype=np.float64)
    brier = float(np.mean((confidence_array - correctness_array) ** 2))
    expected_calibration_error = 0.0
    for lower in np.linspace(0.0, 0.9, 10):
        upper = lower + 0.1
        selected = (confidence_array >= lower) & (
            confidence_array <= upper if upper >= 1.0 else confidence_array < upper
        )
        if not np.any(selected):
            continue
        expected_calibration_error += float(np.mean(selected)) * abs(
            float(np.mean(confidence_array[selected]))
            - float(np.mean(correctness_array[selected]))
        )
    return brier, expected_calibration_error


def _safe_ratio(numerator: int, denominator: int) -> float | None:
    return None if denominator == 0 else numerator / denominator


__all__ = [
    "LatticeDomainPartitionLabels",
    "LatticeDomainValidationReport",
    "evaluate_lattice_domain_analysis",
    "evaluate_lattice_domain_partition",
    "lattice_domain_partition_labels_from_analysis",
]
