from __future__ import annotations

from dataclasses import dataclass
from math import fsum, isclose, isfinite
from typing import Literal

from .first_shell_graph import OrientationReference
from .local_sixfold_bond_order import LocalSixfoldBondOrderField


@dataclass(frozen=True)
class SixfoldBondOrderAggregates:
    """Molecule-weighted local quality and global M6 coherence summaries."""

    mean_local_q6_interior: float | None
    mean_local_q6_all_valid: float | None
    global_psi6_interior: complex | None
    global_q6_interior: float | None
    global_psi6_all_valid: complex | None
    global_q6_all_valid: float | None
    edge_truncated_fraction_of_valid_representatives: float | None
    point_count: int
    valid_order_count: int
    valid_interior_count: int
    edge_truncated_valid_count: int
    insufficient_neighbors_count: int
    rejected_point_count: int
    duplicate_excluded_count: int
    invalid_position_count: int
    coordinate_frame: Literal["sample_nm"]
    orientation_reference: OrientationReference
    spatial_calibration_fingerprint: str
    registration_fingerprint: str
    first_shell_r_max_nm: float
    min_neighbors_for_local_order: int
    symmetry_m: Literal[6]
    bond_weighting: Literal["uniform"]

    def __post_init__(self) -> None:
        point_count = _as_non_negative_integer(self.point_count, "point_count")
        valid_count = _as_non_negative_integer(
            self.valid_order_count,
            "valid_order_count",
        )
        interior_count = _as_non_negative_integer(
            self.valid_interior_count,
            "valid_interior_count",
        )
        edge_count = _as_non_negative_integer(
            self.edge_truncated_valid_count,
            "edge_truncated_valid_count",
        )
        insufficient_count = _as_non_negative_integer(
            self.insufficient_neighbors_count,
            "insufficient_neighbors_count",
        )
        rejected_count = _as_non_negative_integer(
            self.rejected_point_count,
            "rejected_point_count",
        )
        duplicate_count = _as_non_negative_integer(
            self.duplicate_excluded_count,
            "duplicate_excluded_count",
        )
        invalid_count = _as_non_negative_integer(
            self.invalid_position_count,
            "invalid_position_count",
        )
        if interior_count + edge_count != valid_count:
            raise ValueError(
                "valid_interior_count + edge_truncated_valid_count must equal valid_order_count."
            )
        if duplicate_count + invalid_count != rejected_count:
            raise ValueError(
                "rejected_point_count must equal duplicate and invalid position counts."
            )
        if valid_count + insufficient_count + rejected_count != point_count:
            raise ValueError("Status counts must sum to point_count.")

        interior_metrics = _normalize_summary_metrics(
            mean_local_q6=self.mean_local_q6_interior,
            global_psi6=self.global_psi6_interior,
            global_q6=self.global_q6_interior,
            population_count=interior_count,
            metric_scope="interior",
        )
        all_valid_metrics = _normalize_summary_metrics(
            mean_local_q6=self.mean_local_q6_all_valid,
            global_psi6=self.global_psi6_all_valid,
            global_q6=self.global_q6_all_valid,
            population_count=valid_count,
            metric_scope="all_valid",
        )
        edge_fraction = _normalize_optional_fraction(
            self.edge_truncated_fraction_of_valid_representatives,
            "edge_truncated_fraction_of_valid_representatives",
        )
        if valid_count == 0:
            if edge_fraction is not None:
                raise ValueError(
                    "Edge-truncated fraction must be None without valid representatives."
                )
        else:
            expected_fraction = edge_count / valid_count
            if edge_fraction is None or not isclose(
                edge_fraction,
                expected_fraction,
                rel_tol=1e-12,
                abs_tol=1e-12,
            ):
                raise ValueError(
                    "edge_truncated_fraction_of_valid_representatives must use valid_order_count."
                )

        if self.coordinate_frame != "sample_nm":
            raise ValueError("coordinate_frame must be 'sample_nm'.")
        if self.orientation_reference not in {
            "+x_sample_axis",
            "scan_x_axis_assumed_sample_x",
        }:
            raise ValueError(f"Unsupported orientation_reference: {self.orientation_reference!r}.")
        calibration_fingerprint = _as_non_empty_string(
            self.spatial_calibration_fingerprint,
            "spatial_calibration_fingerprint",
        )
        registration_fingerprint = _as_non_empty_string(
            self.registration_fingerprint,
            "registration_fingerprint",
        )
        first_shell_r_max_nm = _as_positive_float(
            self.first_shell_r_max_nm,
            "first_shell_r_max_nm",
        )
        minimum_neighbors = _as_positive_integer(
            self.min_neighbors_for_local_order,
            "min_neighbors_for_local_order",
        )
        if self.symmetry_m != 6:
            raise ValueError("symmetry_m must be 6.")
        if self.bond_weighting != "uniform":
            raise ValueError("bond_weighting must be 'uniform'.")

        object.__setattr__(self, "mean_local_q6_interior", interior_metrics[0])
        object.__setattr__(self, "global_psi6_interior", interior_metrics[1])
        object.__setattr__(self, "global_q6_interior", interior_metrics[2])
        object.__setattr__(self, "mean_local_q6_all_valid", all_valid_metrics[0])
        object.__setattr__(self, "global_psi6_all_valid", all_valid_metrics[1])
        object.__setattr__(self, "global_q6_all_valid", all_valid_metrics[2])
        object.__setattr__(
            self,
            "edge_truncated_fraction_of_valid_representatives",
            edge_fraction,
        )
        object.__setattr__(self, "point_count", point_count)
        object.__setattr__(self, "valid_order_count", valid_count)
        object.__setattr__(self, "valid_interior_count", interior_count)
        object.__setattr__(self, "edge_truncated_valid_count", edge_count)
        object.__setattr__(self, "insufficient_neighbors_count", insufficient_count)
        object.__setattr__(self, "rejected_point_count", rejected_count)
        object.__setattr__(self, "duplicate_excluded_count", duplicate_count)
        object.__setattr__(self, "invalid_position_count", invalid_count)
        object.__setattr__(self, "spatial_calibration_fingerprint", calibration_fingerprint)
        object.__setattr__(self, "registration_fingerprint", registration_fingerprint)
        object.__setattr__(self, "first_shell_r_max_nm", first_shell_r_max_nm)
        object.__setattr__(self, "min_neighbors_for_local_order", minimum_neighbors)


def aggregate_local_sixfold_bond_order(
    local_order_field: LocalSixfoldBondOrderField,
) -> SixfoldBondOrderAggregates:
    """Aggregate local M6 values using equal weight per valid molecule."""

    if not isinstance(local_order_field, LocalSixfoldBondOrderField):
        raise TypeError("local_order_field must be a LocalSixfoldBondOrderField.")
    statuses = local_order_field.computation_status
    valid_indices = tuple(
        index for index, status in enumerate(statuses) if status == "valid_order"
    )
    interior_indices = tuple(
        index
        for index in valid_indices
        if not local_order_field.edge_truncated_neighborhood[index]
    )
    edge_count = len(valid_indices) - len(interior_indices)
    interior_metrics = _aggregate_indices(local_order_field, interior_indices)
    all_valid_metrics = _aggregate_indices(local_order_field, valid_indices)
    duplicate_count = statuses.count("duplicate_excluded")
    invalid_count = statuses.count("invalid_position")
    return SixfoldBondOrderAggregates(
        mean_local_q6_interior=interior_metrics[0],
        mean_local_q6_all_valid=all_valid_metrics[0],
        global_psi6_interior=interior_metrics[1],
        global_q6_interior=interior_metrics[2],
        global_psi6_all_valid=all_valid_metrics[1],
        global_q6_all_valid=all_valid_metrics[2],
        edge_truncated_fraction_of_valid_representatives=(
            edge_count / len(valid_indices) if valid_indices else None
        ),
        point_count=local_order_field.point_count,
        valid_order_count=len(valid_indices),
        valid_interior_count=len(interior_indices),
        edge_truncated_valid_count=edge_count,
        insufficient_neighbors_count=statuses.count("insufficient_neighbors"),
        rejected_point_count=duplicate_count + invalid_count,
        duplicate_excluded_count=duplicate_count,
        invalid_position_count=invalid_count,
        coordinate_frame=local_order_field.coordinate_frame,
        orientation_reference=local_order_field.orientation_reference,
        spatial_calibration_fingerprint=local_order_field.spatial_calibration_fingerprint,
        registration_fingerprint=local_order_field.registration_fingerprint,
        first_shell_r_max_nm=local_order_field.first_shell_r_max_nm,
        min_neighbors_for_local_order=local_order_field.min_neighbors_for_local_order,
        symmetry_m=local_order_field.symmetry_m,
        bond_weighting=local_order_field.bond_weighting,
    )


def _aggregate_indices(
    field: LocalSixfoldBondOrderField,
    indices: tuple[int, ...],
) -> tuple[float | None, complex | None, float | None]:
    if not indices:
        return None, None, None
    q_values = tuple(field.q6[index] for index in indices)
    psi_values = tuple(field.psi6[index] for index in indices)
    if any(value is None for value in q_values) or any(value is None for value in psi_values):
        raise ValueError("valid_order points must contain q6 and psi6 values.")
    normalized_q = tuple(float(value) for value in q_values if value is not None)
    normalized_psi = tuple(complex(value) for value in psi_values if value is not None)
    count = len(indices)
    mean_local_q6 = fsum(normalized_q) / count
    global_psi6 = complex(
        fsum(value.real for value in normalized_psi) / count,
        fsum(value.imag for value in normalized_psi) / count,
    )
    return mean_local_q6, global_psi6, abs(global_psi6)


def _normalize_summary_metrics(
    *,
    mean_local_q6: object,
    global_psi6: object,
    global_q6: object,
    population_count: int,
    metric_scope: str,
) -> tuple[float | None, complex | None, float | None]:
    values = (mean_local_q6, global_psi6, global_q6)
    if population_count == 0:
        if any(value is not None for value in values):
            raise ValueError(
                f"{metric_scope} metrics must be None for an empty population."
            )
        return None, None, None
    if any(value is None for value in values):
        raise ValueError(
            f"{metric_scope} metrics are required for a non-empty population."
        )
    mean_value = _as_unit_float(mean_local_q6, f"mean_local_q6_{metric_scope}")
    psi_value = _as_finite_complex(global_psi6, f"global_psi6_{metric_scope}")
    q_value = _as_unit_float(global_q6, f"global_q6_{metric_scope}")
    if not isclose(q_value, abs(psi_value), rel_tol=1e-12, abs_tol=1e-12):
        raise ValueError(
            f"global_q6_{metric_scope} must equal abs(global_psi6_{metric_scope})."
        )
    if q_value > mean_value and not isclose(
        q_value,
        mean_value,
        rel_tol=1e-12,
        abs_tol=1e-12,
    ):
        raise ValueError(
            f"global_q6_{metric_scope} cannot exceed mean_local_q6_{metric_scope}."
        )
    return mean_value, psi_value, q_value


def _normalize_optional_fraction(value: object, field_name: str) -> float | None:
    if value is None:
        return None
    return _as_unit_float(value, field_name)


def _as_unit_float(value: object, field_name: str) -> float:
    normalized = _as_finite_float(value, field_name)
    if not 0.0 <= normalized <= 1.0:
        raise ValueError(f"{field_name} must lie between 0 and 1.")
    return normalized


def _as_positive_float(value: object, field_name: str) -> float:
    normalized = _as_finite_float(value, field_name)
    if normalized <= 0.0:
        raise ValueError(f"{field_name} must be positive.")
    return normalized


def _as_finite_float(value: object, field_name: str) -> float:
    if isinstance(value, bool):
        raise TypeError(f"{field_name} must be a number.")
    try:
        normalized = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise TypeError(f"{field_name} must be a number.") from exc
    if not isfinite(normalized):
        raise ValueError(f"{field_name} must be finite.")
    return normalized


def _as_finite_complex(value: object, field_name: str) -> complex:
    if isinstance(value, bool):
        raise TypeError(f"{field_name} must be a complex number.")
    try:
        normalized = complex(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise TypeError(f"{field_name} must be a complex number.") from exc
    if not isfinite(normalized.real) or not isfinite(normalized.imag):
        raise ValueError(f"{field_name} must be finite.")
    return normalized


def _as_non_negative_integer(value: object, field_name: str) -> int:
    if isinstance(value, bool):
        raise TypeError(f"{field_name} must be an integer.")
    try:
        normalized = int(value)
        numeric = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise TypeError(f"{field_name} must be an integer.") from exc
    if not isfinite(numeric) or numeric != normalized:
        raise ValueError(f"{field_name} must be an integer.")
    if normalized < 0:
        raise ValueError(f"{field_name} must be non-negative.")
    return normalized


def _as_positive_integer(value: object, field_name: str) -> int:
    normalized = _as_non_negative_integer(value, field_name)
    if normalized == 0:
        raise ValueError(f"{field_name} must be positive.")
    return normalized


def _as_non_empty_string(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise TypeError(f"{field_name} must be a non-empty string.")
    return value
