"""Ground-truth validation and conservative merge policy for orientation methods."""

from __future__ import annotations

from dataclasses import dataclass
from math import isclose
from statistics import median
from typing import Literal, Sequence

from ._molecular_orientation_contract import (
    finite_float as _finite_float,
    non_empty_string as _non_empty_string,
    non_negative_integer as _non_negative_integer,
    strict_integer as _strict_integer,
)
from ._molecular_orientation_geometry import periodic_axis_distance
from .molecular_orientation_models import MolecularOrientationMeasurement
from .molecular_orientation_reference import (
    MolecularOrientationReferenceDataset,
    MolecularOrientationReferenceSplit,
)


MolecularOrientationMethodAgreementStatus = Literal[
    "agrees",
    "systematic_disagreement",
    "insufficient_data",
]
MolecularOrientationMethodMergeStatus = Literal[
    "agrees",
    "systematic_method_disagreement",
    "reference_disagreement",
    "insufficient_data",
]
_AUTOMATIC_METHODS = {"mask_principal_axis", "stm_topography"}


@dataclass(frozen=True)
class MolecularOrientationMethodValidation:
    """One automatic method evaluated against manual orientation labels."""

    reference_dataset_id: str
    reference_fingerprint: str
    method: str
    split: MolecularOrientationReferenceSplit
    tolerance_deg: float
    min_comparable_count: int
    reference_available_count: int
    reference_unresolved_count: int
    estimate_available_count: int
    estimate_available_on_unresolved_count: int
    source_keys: tuple[str, ...]
    source_ids: tuple[str, ...]
    errors_deg: tuple[float, ...]
    reference_coverage_fraction: float | None
    median_error_deg: float | None
    max_error_deg: float | None
    within_tolerance_fraction: float | None
    agreement_status: MolecularOrientationMethodAgreementStatus

    def __post_init__(self) -> None:
        dataset_id = _non_empty_string(
            self.reference_dataset_id,
            "reference_dataset_id",
        )
        fingerprint = _fingerprint(self.reference_fingerprint)
        method = _automatic_method(self.method)
        if self.split not in {"development", "holdout"}:
            raise ValueError("Unsupported molecular orientation reference split.")
        tolerance = _positive_tolerance(self.tolerance_deg)
        minimum = _positive_integer(
            self.min_comparable_count,
            "min_comparable_count",
        )
        reference_count = _non_negative_integer(
            self.reference_available_count,
            "reference_available_count",
        )
        unresolved_count = _non_negative_integer(
            self.reference_unresolved_count,
            "reference_unresolved_count",
        )
        estimate_count = _non_negative_integer(
            self.estimate_available_count,
            "estimate_available_count",
        )
        estimate_on_unresolved_count = _non_negative_integer(
            self.estimate_available_on_unresolved_count,
            "estimate_available_on_unresolved_count",
        )
        if estimate_on_unresolved_count > unresolved_count:
            raise ValueError(
                "Available estimates on unresolved references cannot exceed "
                "the unresolved reference count."
            )
        source_ids = tuple(
            _non_empty_string(value, "source_ids")
            for value in self.source_ids
        )
        source_keys = tuple(
            _non_empty_string(value, "source_keys")
            for value in self.source_keys
        )
        if len(set(source_keys)) != len(source_keys):
            raise ValueError("source_keys must be unique.")
        errors = tuple(_axis_error(value) for value in self.errors_deg)
        if len(source_keys) != len(source_ids) or len(source_ids) != len(errors):
            raise ValueError(
                "source_keys, source_ids, and errors_deg must align."
            )
        if len(errors) > min(reference_count, estimate_count):
            raise ValueError("Comparable errors cannot exceed available counts.")
        expected_coverage = (
            None
            if reference_count == 0
            else len(errors) / reference_count
        )
        expected_median = None if not errors else float(median(errors))
        expected_max = None if not errors else max(errors)
        expected_fraction = (
            None
            if not errors
            else sum(error <= tolerance for error in errors) / len(errors)
        )
        _require_optional_close(
            self.reference_coverage_fraction,
            expected_coverage,
            "reference_coverage_fraction",
        )
        _require_optional_close(
            self.median_error_deg,
            expected_median,
            "median_error_deg",
        )
        _require_optional_close(
            self.max_error_deg,
            expected_max,
            "max_error_deg",
        )
        _require_optional_close(
            self.within_tolerance_fraction,
            expected_fraction,
            "within_tolerance_fraction",
        )
        expected_status = _agreement_status(
            comparable_count=len(errors),
            minimum=minimum,
            max_error=expected_max,
            tolerance=tolerance,
            unresolved_conflict_count=estimate_on_unresolved_count,
            reference_available_count=reference_count,
        )
        if self.agreement_status != expected_status:
            raise ValueError("agreement_status does not match validation errors.")
        object.__setattr__(self, "reference_dataset_id", dataset_id)
        object.__setattr__(self, "reference_fingerprint", fingerprint)
        object.__setattr__(self, "method", method)
        object.__setattr__(self, "tolerance_deg", tolerance)
        object.__setattr__(self, "min_comparable_count", minimum)
        object.__setattr__(self, "reference_available_count", reference_count)
        object.__setattr__(
            self,
            "reference_unresolved_count",
            unresolved_count,
        )
        object.__setattr__(self, "estimate_available_count", estimate_count)
        object.__setattr__(
            self,
            "estimate_available_on_unresolved_count",
            estimate_on_unresolved_count,
        )
        object.__setattr__(self, "source_keys", source_keys)
        object.__setattr__(self, "source_ids", source_ids)
        object.__setattr__(self, "errors_deg", errors)
        object.__setattr__(
            self,
            "reference_coverage_fraction",
            expected_coverage,
        )
        object.__setattr__(self, "median_error_deg", expected_median)
        object.__setattr__(self, "max_error_deg", expected_max)
        object.__setattr__(
            self,
            "within_tolerance_fraction",
            expected_fraction,
        )

    @property
    def comparable_count(self) -> int:
        return len(self.errors_deg)

    @property
    def automatic_merge_eligible(self) -> bool:
        return self.agreement_status == "agrees"


@dataclass(frozen=True)
class MolecularOrientationMethodMergeAssessment:
    """Pairwise merge decision guarded by manual-reference validation."""

    first: MolecularOrientationMethodValidation
    second: MolecularOrientationMethodValidation
    paired_source_keys: tuple[str, ...]
    paired_source_ids: tuple[str, ...]
    pairwise_errors_deg: tuple[float, ...]
    pairwise_median_error_deg: float | None
    pairwise_max_error_deg: float | None
    pairwise_within_tolerance_fraction: float | None
    merge_status: MolecularOrientationMethodMergeStatus

    def __post_init__(self) -> None:
        if not isinstance(self.first, MolecularOrientationMethodValidation):
            raise TypeError("first must be a method validation.")
        if not isinstance(self.second, MolecularOrientationMethodValidation):
            raise TypeError("second must be a method validation.")
        if self.first.method == self.second.method:
            raise ValueError("Method merge assessment requires distinct methods.")
        if (
            self.first.reference_dataset_id != self.second.reference_dataset_id
            or self.first.reference_fingerprint != self.second.reference_fingerprint
            or self.first.split != self.second.split
            or self.first.tolerance_deg != self.second.tolerance_deg
            or self.first.min_comparable_count != self.second.min_comparable_count
        ):
            raise ValueError("Method validations must share one reference contract.")
        source_ids = tuple(
            _non_empty_string(value, "paired_source_ids")
            for value in self.paired_source_ids
        )
        source_keys = tuple(
            _non_empty_string(value, "paired_source_keys")
            for value in self.paired_source_keys
        )
        if len(set(source_keys)) != len(source_keys):
            raise ValueError("paired_source_keys must be unique.")
        errors = tuple(_axis_error(value) for value in self.pairwise_errors_deg)
        if len(source_keys) != len(source_ids) or len(source_ids) != len(errors):
            raise ValueError(
                "Paired source keys, source IDs, and errors must align."
            )
        expected_median = None if not errors else float(median(errors))
        expected_max = None if not errors else max(errors)
        expected_fraction = (
            None
            if not errors
            else sum(
                error <= self.first.tolerance_deg for error in errors
            )
            / len(errors)
        )
        _require_optional_close(
            self.pairwise_median_error_deg,
            expected_median,
            "pairwise_median_error_deg",
        )
        _require_optional_close(
            self.pairwise_max_error_deg,
            expected_max,
            "pairwise_max_error_deg",
        )
        _require_optional_close(
            self.pairwise_within_tolerance_fraction,
            expected_fraction,
            "pairwise_within_tolerance_fraction",
        )
        expected_status = _merge_status(
            first=self.first,
            second=self.second,
            paired_count=len(errors),
            pairwise_max_error=expected_max,
        )
        if self.merge_status != expected_status:
            raise ValueError("merge_status does not match method comparisons.")
        object.__setattr__(self, "paired_source_keys", source_keys)
        object.__setattr__(self, "paired_source_ids", source_ids)
        object.__setattr__(self, "pairwise_errors_deg", errors)
        object.__setattr__(
            self,
            "pairwise_median_error_deg",
            expected_median,
        )
        object.__setattr__(
            self,
            "pairwise_max_error_deg",
            expected_max,
        )
        object.__setattr__(
            self,
            "pairwise_within_tolerance_fraction",
            expected_fraction,
        )

    @property
    def paired_count(self) -> int:
        return len(self.pairwise_errors_deg)

    @property
    def automatic_merge_allowed(self) -> bool:
        return self.merge_status == "agrees"


def evaluate_molecular_orientation_method_against_reference(
    reference: MolecularOrientationReferenceDataset,
    measurements: Sequence[MolecularOrientationMeasurement],
    *,
    method: str,
    split: MolecularOrientationReferenceSplit = "holdout",
    tolerance_deg: float = 10.0,
    min_comparable_count: int = 2,
) -> MolecularOrientationMethodValidation:
    """Evaluate one method without using unavailable labels as zero angles."""

    if not isinstance(reference, MolecularOrientationReferenceDataset):
        raise TypeError("reference must be MolecularOrientationReferenceDataset.")
    if not reference.reviewed:
        raise ValueError(
            "Method validation requires a reviewed manual reference dataset."
        )
    method = _automatic_method(method)
    if split not in {"development", "holdout"}:
        raise ValueError("Unsupported molecular orientation reference split.")
    tolerance = _positive_tolerance(tolerance_deg)
    minimum = _positive_integer(min_comparable_count, "min_comparable_count")
    estimates = _measurement_map(
        reference,
        measurements,
        expected_method=method,
    )
    reference_samples = tuple(
        sample for sample in reference.samples if sample.split == split
    )
    available_reference = tuple(
        sample
        for sample in reference_samples
        if sample.measurement.status == "available"
    )
    unresolved_reference = tuple(
        sample
        for sample in reference_samples
        if sample.measurement.status != "available"
    )
    available_estimate_count = sum(
        estimate.status == "available"
        for sample in reference_samples
        if (estimate := estimates.get(_source_key(sample.measurement))) is not None
    )
    available_on_unresolved_count = sum(
        estimate.status == "available"
        for sample in unresolved_reference
        if (estimate := estimates.get(_source_key(sample.measurement))) is not None
    )
    source_keys = []
    source_ids = []
    errors = []
    for sample in available_reference:
        manual = sample.measurement
        estimate = estimates.get(_source_key(manual))
        if estimate is None or estimate.status != "available":
            continue
        if not isclose(
            estimate.periodicity_deg,
            manual.periodicity_deg,
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            raise ValueError("Estimate periodicity must match manual ground truth.")
        source_keys.append(_source_key_label(manual))
        source_ids.append(manual.provenance.source_id)
        errors.append(
            periodic_axis_distance(
                estimate.angle_deg,
                manual.angle_deg,
                period_deg=manual.periodicity_deg,
            )
        )
    median_error = None if not errors else float(median(errors))
    max_error = None if not errors else max(errors)
    within_fraction = (
        None
        if not errors
        else sum(error <= tolerance for error in errors) / len(errors)
    )
    status = _agreement_status(
        comparable_count=len(errors),
        minimum=minimum,
        max_error=max_error,
        tolerance=tolerance,
        unresolved_conflict_count=available_on_unresolved_count,
        reference_available_count=len(available_reference),
    )
    return MolecularOrientationMethodValidation(
        reference_dataset_id=reference.dataset_id,
        reference_fingerprint=reference.fingerprint,
        method=method,
        split=split,
        tolerance_deg=tolerance,
        min_comparable_count=minimum,
        reference_available_count=len(available_reference),
        reference_unresolved_count=len(unresolved_reference),
        estimate_available_count=available_estimate_count,
        estimate_available_on_unresolved_count=available_on_unresolved_count,
        source_keys=tuple(source_keys),
        source_ids=tuple(source_ids),
        errors_deg=tuple(errors),
        reference_coverage_fraction=(
            None
            if not available_reference
            else len(errors) / len(available_reference)
        ),
        median_error_deg=median_error,
        max_error_deg=max_error,
        within_tolerance_fraction=within_fraction,
        agreement_status=status,
    )


def assess_molecular_orientation_method_merge(
    reference: MolecularOrientationReferenceDataset,
    first_measurements: Sequence[MolecularOrientationMeasurement],
    second_measurements: Sequence[MolecularOrientationMeasurement],
    *,
    split: MolecularOrientationReferenceSplit = "holdout",
    tolerance_deg: float = 10.0,
    min_comparable_count: int = 2,
) -> MolecularOrientationMethodMergeAssessment:
    """Allow merging only after reference and pairwise agreement."""

    first_measurements = tuple(first_measurements)
    second_measurements = tuple(second_measurements)
    first_method = _single_method(first_measurements, "first_measurements")
    second_method = _single_method(second_measurements, "second_measurements")
    if first_method == second_method:
        raise ValueError("Cannot assess merge of the same orientation method.")
    first = evaluate_molecular_orientation_method_against_reference(
        reference,
        first_measurements,
        method=first_method,
        split=split,
        tolerance_deg=tolerance_deg,
        min_comparable_count=min_comparable_count,
    )
    second = evaluate_molecular_orientation_method_against_reference(
        reference,
        second_measurements,
        method=second_method,
        split=split,
        tolerance_deg=tolerance_deg,
        min_comparable_count=min_comparable_count,
    )
    first_map = _measurement_map(
        reference,
        first_measurements,
        expected_method=first_method,
    )
    second_map = _measurement_map(
        reference,
        second_measurements,
        expected_method=second_method,
    )
    source_keys = []
    source_ids = []
    errors = []
    for sample in reference.samples:
        if sample.split != split or sample.measurement.status != "available":
            continue
        key = _source_key(sample.measurement)
        first_estimate = first_map.get(key)
        second_estimate = second_map.get(key)
        if (
            first_estimate is None
            or second_estimate is None
            or first_estimate.status != "available"
            or second_estimate.status != "available"
        ):
            continue
        if not isclose(
            first_estimate.periodicity_deg,
            second_estimate.periodicity_deg,
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            raise ValueError("Method periodicities must agree before merging.")
        source_keys.append(_source_key_label(sample.measurement))
        source_ids.append(sample.measurement.provenance.source_id)
        errors.append(
            periodic_axis_distance(
                first_estimate.angle_deg,
                second_estimate.angle_deg,
                period_deg=first_estimate.periodicity_deg,
            )
        )
    pairwise_median = None if not errors else float(median(errors))
    pairwise_max = None if not errors else max(errors)
    pairwise_fraction = (
        None
        if not errors
        else sum(error <= first.tolerance_deg for error in errors)
        / len(errors)
    )
    status = _merge_status(
        first=first,
        second=second,
        paired_count=len(errors),
        pairwise_max_error=pairwise_max,
    )
    return MolecularOrientationMethodMergeAssessment(
        first=first,
        second=second,
        paired_source_keys=tuple(source_keys),
        paired_source_ids=tuple(source_ids),
        pairwise_errors_deg=tuple(errors),
        pairwise_median_error_deg=pairwise_median,
        pairwise_max_error_deg=pairwise_max,
        pairwise_within_tolerance_fraction=pairwise_fraction,
        merge_status=status,
    )


def _measurement_map(
    reference: MolecularOrientationReferenceDataset,
    measurements: Sequence[MolecularOrientationMeasurement],
    *,
    expected_method: str,
) -> dict[tuple[object, ...], MolecularOrientationMeasurement]:
    expected_method = _automatic_method(expected_method)
    references_by_key = {
        _source_key(sample.measurement): sample.measurement
        for sample in reference.samples
    }
    result = {}
    for measurement in measurements:
        if not isinstance(measurement, MolecularOrientationMeasurement):
            raise TypeError("measurements must contain orientation measurements.")
        if measurement.method != expected_method:
            raise ValueError("Every estimate must use the requested method.")
        provenance = measurement.provenance
        if (
            provenance.source_file_name != reference.source_file_name
            or provenance.source_file_sha256 != reference.source_file_sha256
            or provenance.source_session_file_name
            != reference.source_session_file_name
            or provenance.source_session_sha256
            != reference.source_session_sha256
        ):
            raise ValueError("Estimate provenance must match the reference dataset.")
        key = _source_key(measurement)
        manual = references_by_key.get(key)
        if manual is None:
            raise ValueError(
                "Every estimate must identify a molecule in the reference dataset."
            )
        if (
            provenance.orientation_reference
            != manual.provenance.orientation_reference
        ):
            raise ValueError(
                "Estimate orientation_reference must match manual ground truth."
            )
        if not _bbox_matches(
            provenance.patch_bbox_xyxy,
            manual.provenance.patch_bbox_xyxy,
        ):
            raise ValueError(
                "Estimate patch_bbox_xyxy must match manual ground truth."
            )
        if measurement.patch_shape_px != manual.patch_shape_px:
            raise ValueError(
                "Estimate patch_shape_px must match manual ground truth."
            )
        if key in result:
            raise ValueError("Orientation estimates must identify unique molecules.")
        result[key] = measurement
    return result


def _source_key(
    measurement: MolecularOrientationMeasurement,
) -> tuple[object, ...]:
    provenance = measurement.provenance
    return (
        provenance.frame_index,
        provenance.source_view,
        provenance.source_kind,
        provenance.source_id,
    )


def _source_key_label(
    measurement: MolecularOrientationMeasurement,
) -> str:
    provenance = measurement.provenance
    return (
        f"{provenance.frame_index}|{provenance.source_view}|"
        f"{provenance.source_kind}|{provenance.source_id}"
    )


def _single_method(
    measurements: tuple[MolecularOrientationMeasurement, ...],
    field_name: str,
) -> str:
    if not measurements:
        raise ValueError(f"{field_name} must not be empty.")
    if any(
        not isinstance(value, MolecularOrientationMeasurement)
        for value in measurements
    ):
        raise TypeError(f"{field_name} must contain orientation measurements.")
    methods = {measurement.method for measurement in measurements}
    if len(methods) != 1:
        raise ValueError(f"{field_name} must contain exactly one method.")
    return next(iter(methods))


def _agreement_status(
    *,
    comparable_count: int,
    minimum: int,
    max_error: float | None,
    tolerance: float,
    unresolved_conflict_count: int,
    reference_available_count: int,
) -> MolecularOrientationMethodAgreementStatus:
    if unresolved_conflict_count:
        return "systematic_disagreement"
    if comparable_count < minimum:
        return "insufficient_data"
    if comparable_count < reference_available_count:
        return "insufficient_data"
    if max_error is not None and max_error <= tolerance:
        return "agrees"
    return "systematic_disagreement"


def _merge_status(
    *,
    first: MolecularOrientationMethodValidation,
    second: MolecularOrientationMethodValidation,
    paired_count: int,
    pairwise_max_error: float | None,
) -> MolecularOrientationMethodMergeStatus:
    minimum = first.min_comparable_count
    if paired_count < minimum:
        if (
            first.agreement_status == "systematic_disagreement"
            or second.agreement_status == "systematic_disagreement"
        ):
            return "reference_disagreement"
        return "insufficient_data"
    if (
        pairwise_max_error is not None
        and pairwise_max_error > first.tolerance_deg
    ):
        return "systematic_method_disagreement"
    if (
        first.agreement_status != "agrees"
        or second.agreement_status != "agrees"
    ):
        return "reference_disagreement"
    return "agrees"


def _automatic_method(value: object) -> str:
    method = _non_empty_string(value, "method")
    if method not in _AUTOMATIC_METHODS:
        raise ValueError(
            "Method validation accepts automatic orientation methods only."
        )
    return method


def _bbox_matches(
    first: tuple[float, float, float, float],
    second: tuple[float, float, float, float],
) -> bool:
    return all(
        isclose(left, right, rel_tol=0.0, abs_tol=1e-9)
        for left, right in zip(first, second)
    )


def _positive_tolerance(value: object) -> float:
    tolerance = _finite_float(value, "tolerance_deg")
    if not 0.0 < tolerance <= 90.0:
        raise ValueError("tolerance_deg must lie in (0, 90].")
    return tolerance


def _positive_integer(value: object, field_name: str) -> int:
    normalized = _strict_integer(value, field_name)
    if normalized <= 0:
        raise ValueError(f"{field_name} must be positive.")
    return normalized


def _axis_error(value: object) -> float:
    error = _finite_float(value, "errors_deg")
    if not 0.0 <= error <= 90.0:
        raise ValueError("Orientation errors must lie in [0, 90].")
    return error


def _fingerprint(value: object) -> str:
    normalized = _non_empty_string(value, "reference_fingerprint")
    if len(normalized) != 64 or any(
        character not in "0123456789abcdef" for character in normalized
    ):
        raise ValueError("reference_fingerprint must be a SHA-256 digest.")
    return normalized


def _require_optional_close(
    value: object,
    expected: float | None,
    field_name: str,
) -> None:
    if expected is None:
        if value is not None:
            raise ValueError(f"{field_name} must be None.")
        return
    normalized = _finite_float(value, field_name)
    if not isclose(normalized, expected, rel_tol=1e-12, abs_tol=1e-12):
        raise ValueError(f"{field_name} does not match errors.")
