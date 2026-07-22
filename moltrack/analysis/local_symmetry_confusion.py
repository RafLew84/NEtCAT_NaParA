"""Synthetic validation summaries for local symmetry classification."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .local_symmetry_evidence_models import LocalSymmetryModel


LOCAL_SYMMETRY_CONFUSION_LABELS: tuple[LocalSymmetryModel, ...] = (
    "trifold",
    "sixfold",
    "mixed",
    "disordered",
    "ambiguous",
    "unavailable",
)
_LABEL_INDEX = {
    label: index for index, label in enumerate(LOCAL_SYMMETRY_CONFUSION_LABELS)
}


@dataclass(frozen=True)
class LocalSymmetryValidationError:
    case_id: str
    expected: LocalSymmetryModel
    predicted: LocalSymmetryModel


@dataclass(frozen=True)
class LocalSymmetryConfusionReport:
    labels: tuple[LocalSymmetryModel, ...]
    confusion_matrix: tuple[tuple[int, ...], ...]
    case_count: int
    correct_count: int
    accuracy: float
    errors: tuple[LocalSymmetryValidationError, ...]


def build_local_symmetry_confusion_report(
    *,
    case_ids: Sequence[str],
    expected: Sequence[LocalSymmetryModel],
    predicted: Sequence[LocalSymmetryModel],
) -> LocalSymmetryConfusionReport:
    """Build an expected-row/predicted-column confusion matrix and error list."""

    normalized_case_ids = tuple(case_ids)
    normalized_expected = tuple(expected)
    normalized_predicted = tuple(predicted)
    if not (
        len(normalized_case_ids)
        == len(normalized_expected)
        == len(normalized_predicted)
    ):
        raise ValueError("case_ids, expected, and predicted must have equal lengths.")
    if any(not isinstance(case_id, str) or not case_id for case_id in normalized_case_ids):
        raise TypeError("case_ids must contain non-empty strings.")
    if len(set(normalized_case_ids)) != len(normalized_case_ids):
        raise ValueError("case_ids must be unique.")
    unsupported = (
        set(normalized_expected).union(normalized_predicted).difference(_LABEL_INDEX)
    )
    if unsupported:
        raise ValueError(f"Unsupported local symmetry model: {sorted(unsupported)!r}.")

    matrix = [
        [0 for _ in LOCAL_SYMMETRY_CONFUSION_LABELS]
        for _ in LOCAL_SYMMETRY_CONFUSION_LABELS
    ]
    errors: list[LocalSymmetryValidationError] = []
    correct_count = 0
    for case_id, expected_model, predicted_model in zip(
        normalized_case_ids,
        normalized_expected,
        normalized_predicted,
    ):
        matrix[_LABEL_INDEX[expected_model]][_LABEL_INDEX[predicted_model]] += 1
        if expected_model == predicted_model:
            correct_count += 1
        else:
            errors.append(
                LocalSymmetryValidationError(
                    case_id=case_id,
                    expected=expected_model,
                    predicted=predicted_model,
                )
            )
    case_count = len(normalized_case_ids)
    return LocalSymmetryConfusionReport(
        labels=LOCAL_SYMMETRY_CONFUSION_LABELS,
        confusion_matrix=tuple(tuple(row) for row in matrix),
        case_count=case_count,
        correct_count=correct_count,
        accuracy=correct_count / case_count if case_count else 0.0,
        errors=tuple(errors),
    )
