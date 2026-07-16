from __future__ import annotations

from dataclasses import dataclass
from math import isclose, isfinite
from typing import Literal

from .first_shell_graph import OrientationReference


LocalOrderComputationStatus = Literal[
    "valid_order",
    "insufficient_neighbors",
    "duplicate_excluded",
    "invalid_position",
]
LocalOrientationStatus = Literal[
    "defined",
    "undefined_zero_magnitude",
    "not_available",
]


_COMPUTATION_STATUSES = {
    "valid_order",
    "insufficient_neighbors",
    "duplicate_excluded",
    "invalid_position",
}
_ORIENTATION_STATUSES = {
    "defined",
    "undefined_zero_magnitude",
    "not_available",
}
_ORIENTATION_REFERENCES = {
    "+x_sample_axis",
    "scan_x_axis_assumed_sample_x",
}


@dataclass(frozen=True)
class LocalSixfoldBondOrderField:
    """Immutable per-molecule local sixfold-order values and quality context."""

    source_ids: tuple[str, ...]
    point_count: int
    psi6: tuple[complex | None, ...]
    q6: tuple[float | None, ...]
    lattice_orientation_deg: tuple[float | None, ...]
    orientation_status: tuple[LocalOrientationStatus, ...]
    neighbor_count: tuple[int, ...]
    computation_status: tuple[LocalOrderComputationStatus, ...]
    local_median_bond_length_nm: tuple[float | None, ...]
    local_bond_length_mad_nm: tuple[float | None, ...]
    local_bond_length_iqr_nm: tuple[float | None, ...]
    local_bond_length_robust_cv: tuple[float | None, ...]
    physical_duplicate_qc: tuple[bool, ...]
    geometry_duplicate_qc: tuple[bool, ...]
    edge_truncated_neighborhood: tuple[bool, ...]
    distance_to_valid_fov_boundary_nm: tuple[float | None, ...]
    first_shell_r_max_nm: float
    coordinate_frame: Literal["sample_nm"]
    orientation_reference: OrientationReference
    spatial_calibration_fingerprint: str
    registration_fingerprint: str
    min_neighbors_for_local_order: int = 3
    symmetry_m: Literal[6] = 6
    bond_weighting: Literal["uniform"] = "uniform"

    def __post_init__(self) -> None:
        point_count = _as_non_negative_integer(self.point_count, "point_count")
        source_ids = tuple(self.source_ids)
        if len(source_ids) != point_count:
            raise ValueError("point_count must equal the number of source_ids.")
        if any(not isinstance(source_id, str) or not source_id for source_id in source_ids):
            raise TypeError("source_ids must contain non-empty strings.")
        if len(set(source_ids)) != point_count:
            raise ValueError("source_ids must be unique.")

        minimum_neighbors = _as_positive_integer(
            self.min_neighbors_for_local_order,
            "min_neighbors_for_local_order",
        )
        first_shell_r_max_nm = _as_positive_float(
            self.first_shell_r_max_nm,
            "first_shell_r_max_nm",
        )
        if self.symmetry_m != 6:
            raise ValueError("symmetry_m must be 6.")
        if self.bond_weighting != "uniform":
            raise ValueError("bond_weighting must be 'uniform'.")
        if self.coordinate_frame != "sample_nm":
            raise ValueError("coordinate_frame must be 'sample_nm'.")
        if self.orientation_reference not in _ORIENTATION_REFERENCES:
            raise ValueError(f"Unsupported orientation_reference: {self.orientation_reference!r}.")
        calibration_fingerprint = _as_non_empty_string(
            self.spatial_calibration_fingerprint,
            "spatial_calibration_fingerprint",
        )
        registration_fingerprint = _as_non_empty_string(
            self.registration_fingerprint,
            "registration_fingerprint",
        )

        psi6 = _optional_complex_tuple(self.psi6, point_count=point_count, field_name="psi6")
        q6 = _optional_float_tuple(self.q6, point_count=point_count, field_name="q6")
        orientations = _optional_float_tuple(
            self.lattice_orientation_deg,
            point_count=point_count,
            field_name="lattice_orientation_deg",
        )
        orientation_statuses = _status_tuple(
            self.orientation_status,
            point_count=point_count,
            field_name="orientation_status",
            supported=_ORIENTATION_STATUSES,
        )
        neighbor_counts = tuple(
            _as_non_negative_integer(value, f"neighbor_count[{index}]")
            for index, value in enumerate(
                _per_point_values(
                    self.neighbor_count,
                    point_count=point_count,
                    field_name="neighbor_count",
                )
            )
        )
        computation_statuses = _status_tuple(
            self.computation_status,
            point_count=point_count,
            field_name="computation_status",
            supported=_COMPUTATION_STATUSES,
        )
        medians = _optional_float_tuple(
            self.local_median_bond_length_nm,
            point_count=point_count,
            field_name="local_median_bond_length_nm",
        )
        mads = _optional_float_tuple(
            self.local_bond_length_mad_nm,
            point_count=point_count,
            field_name="local_bond_length_mad_nm",
        )
        iqrs = _optional_float_tuple(
            self.local_bond_length_iqr_nm,
            point_count=point_count,
            field_name="local_bond_length_iqr_nm",
        )
        robust_cvs = _optional_float_tuple(
            self.local_bond_length_robust_cv,
            point_count=point_count,
            field_name="local_bond_length_robust_cv",
        )
        physical_duplicate_qc = _boolean_tuple(
            self.physical_duplicate_qc,
            point_count=point_count,
            field_name="physical_duplicate_qc",
        )
        geometry_duplicate_qc = _boolean_tuple(
            self.geometry_duplicate_qc,
            point_count=point_count,
            field_name="geometry_duplicate_qc",
        )
        edge_truncated = _boolean_tuple(
            self.edge_truncated_neighborhood,
            point_count=point_count,
            field_name="edge_truncated_neighborhood",
        )
        boundary_distances = _optional_float_tuple(
            self.distance_to_valid_fov_boundary_nm,
            point_count=point_count,
            field_name="distance_to_valid_fov_boundary_nm",
        )

        normalized_orientations: list[float | None] = []
        for index in range(point_count):
            status = computation_statuses[index]
            orientation_state = orientation_statuses[index]
            neighbors = neighbor_counts[index]
            point_psi6 = psi6[index]
            point_q6 = q6[index]
            orientation = orientations[index]
            physical_duplicate = physical_duplicate_qc[index]
            geometry_duplicate = geometry_duplicate_qc[index]
            boundary_distance = boundary_distances[index]

            if physical_duplicate and geometry_duplicate:
                raise ValueError("A point cannot be both a physical and geometry duplicate.")
            is_duplicate = physical_duplicate or geometry_duplicate
            if is_duplicate != (status == "duplicate_excluded"):
                raise ValueError(
                    "Duplicate QC flags must correspond exactly to duplicate_excluded status."
                )
            if status == "invalid_position":
                if boundary_distance is not None:
                    raise ValueError(
                        "invalid_position cannot have distance_to_valid_fov_boundary_nm."
                    )
            else:
                if boundary_distance is None:
                    raise ValueError(
                        "A valid position requires distance_to_valid_fov_boundary_nm."
                    )
                if boundary_distance < 0.0:
                    raise ValueError(
                        "distance_to_valid_fov_boundary_nm values must be non-negative."
                    )
            expected_edge_truncated = (
                boundary_distance is not None
                and boundary_distance < first_shell_r_max_nm
            )
            if edge_truncated[index] != expected_edge_truncated:
                raise ValueError(
                    "edge_truncated_neighborhood must equal "
                    "distance_to_valid_fov_boundary_nm < first_shell_r_max_nm."
                )

            if status == "valid_order":
                if neighbors < minimum_neighbors:
                    raise ValueError(
                        "valid_order requires at least min_neighbors_for_local_order neighbors."
                    )
                if point_psi6 is None or point_q6 is None:
                    raise ValueError("valid_order requires psi6 and q6 values.")
                if not 0.0 <= point_q6 <= 1.0:
                    raise ValueError("q6 values must lie between 0 and 1.")
                if not isclose(point_q6, abs(point_psi6), rel_tol=1e-12, abs_tol=1e-12):
                    raise ValueError("q6 must equal abs(psi6).")
                if orientation_state == "defined":
                    if orientation is None:
                        raise ValueError("Defined orientation requires lattice_orientation_deg.")
                    normalized_orientations.append(orientation % 60.0)
                elif orientation_state == "undefined_zero_magnitude":
                    if orientation is not None:
                        raise ValueError(
                            "undefined_zero_magnitude orientation cannot have an angle."
                        )
                    normalized_orientations.append(None)
                else:
                    raise ValueError("valid_order requires a computed orientation status.")
            else:
                if point_psi6 is not None or point_q6 is not None or orientation is not None:
                    raise ValueError("Non-valid order statuses cannot contain order values.")
                if orientation_state != "not_available":
                    raise ValueError(
                        "Non-valid order statuses require orientation_status='not_available'."
                    )
                if status == "insufficient_neighbors" and neighbors >= minimum_neighbors:
                    raise ValueError(
                        "insufficient_neighbors requires fewer than min_neighbors_for_local_order neighbors."
                    )
                if status in {"duplicate_excluded", "invalid_position"} and neighbors != 0:
                    raise ValueError(f"{status} requires neighbor_count=0.")
                normalized_orientations.append(None)

            statistics = (medians[index], mads[index], iqrs[index], robust_cvs[index])
            if neighbors == 0:
                if any(value is not None for value in statistics):
                    raise ValueError("Points without neighbors cannot have bond-length statistics.")
            else:
                if any(value is None for value in statistics):
                    raise ValueError(
                        "Points with neighbors require complete bond-length statistics."
                    )
                if medians[index] is not None and medians[index] <= 0.0:
                    raise ValueError("local_median_bond_length_nm values must be positive.")
                if any(
                    value is not None and value < 0.0
                    for value in (mads[index], iqrs[index], robust_cvs[index])
                ):
                    raise ValueError("Bond-length dispersion values must be non-negative.")

        object.__setattr__(self, "source_ids", source_ids)
        object.__setattr__(self, "point_count", point_count)
        object.__setattr__(self, "psi6", psi6)
        object.__setattr__(self, "q6", q6)
        object.__setattr__(self, "lattice_orientation_deg", tuple(normalized_orientations))
        object.__setattr__(self, "orientation_status", orientation_statuses)
        object.__setattr__(self, "neighbor_count", neighbor_counts)
        object.__setattr__(self, "computation_status", computation_statuses)
        object.__setattr__(self, "local_median_bond_length_nm", medians)
        object.__setattr__(self, "local_bond_length_mad_nm", mads)
        object.__setattr__(self, "local_bond_length_iqr_nm", iqrs)
        object.__setattr__(self, "local_bond_length_robust_cv", robust_cvs)
        object.__setattr__(self, "physical_duplicate_qc", physical_duplicate_qc)
        object.__setattr__(self, "geometry_duplicate_qc", geometry_duplicate_qc)
        object.__setattr__(self, "edge_truncated_neighborhood", edge_truncated)
        object.__setattr__(self, "distance_to_valid_fov_boundary_nm", boundary_distances)
        object.__setattr__(self, "first_shell_r_max_nm", first_shell_r_max_nm)
        object.__setattr__(self, "spatial_calibration_fingerprint", calibration_fingerprint)
        object.__setattr__(self, "registration_fingerprint", registration_fingerprint)
        object.__setattr__(self, "min_neighbors_for_local_order", minimum_neighbors)

    def index_for_source_id(self, source_id: str) -> int:
        """Return the input-order index linked to a molecular source ID."""

        try:
            return self.source_ids.index(source_id)
        except ValueError as exc:
            raise KeyError(f"Unknown source_id: {source_id!r}.") from exc


def _per_point_values(
    values: object,
    *,
    point_count: int,
    field_name: str,
) -> tuple[object, ...]:
    try:
        normalized = tuple(values)  # type: ignore[arg-type]
    except TypeError as exc:
        raise TypeError(f"{field_name} must be an iterable.") from exc
    if len(normalized) != point_count:
        raise ValueError(f"{field_name} must contain one value per point.")
    return normalized


def _optional_complex_tuple(
    values: object,
    *,
    point_count: int,
    field_name: str,
) -> tuple[complex | None, ...]:
    normalized: list[complex | None] = []
    for index, value in enumerate(
        _per_point_values(values, point_count=point_count, field_name=field_name)
    ):
        if value is None:
            normalized.append(None)
            continue
        if isinstance(value, bool):
            raise TypeError(f"{field_name}[{index}] must be a complex number or None.")
        try:
            number = complex(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise TypeError(f"{field_name}[{index}] must be a complex number or None.") from exc
        if not isfinite(number.real) or not isfinite(number.imag):
            raise ValueError(f"{field_name}[{index}] must be finite.")
        normalized.append(number)
    return tuple(normalized)


def _optional_float_tuple(
    values: object,
    *,
    point_count: int,
    field_name: str,
) -> tuple[float | None, ...]:
    normalized: list[float | None] = []
    for index, value in enumerate(
        _per_point_values(values, point_count=point_count, field_name=field_name)
    ):
        if value is None:
            normalized.append(None)
            continue
        if isinstance(value, bool):
            raise TypeError(f"{field_name}[{index}] must be a number or None.")
        try:
            number = float(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise TypeError(f"{field_name}[{index}] must be a number or None.") from exc
        if not isfinite(number):
            raise ValueError(f"{field_name}[{index}] must be finite.")
        normalized.append(number)
    return tuple(normalized)


def _boolean_tuple(
    values: object,
    *,
    point_count: int,
    field_name: str,
) -> tuple[bool, ...]:
    normalized = _per_point_values(values, point_count=point_count, field_name=field_name)
    if any(not isinstance(value, bool) for value in normalized):
        raise TypeError(f"{field_name} must contain only booleans.")
    return tuple(normalized)  # type: ignore[return-value]


def _status_tuple(
    values: object,
    *,
    point_count: int,
    field_name: str,
    supported: set[str],
) -> tuple:
    normalized = _per_point_values(values, point_count=point_count, field_name=field_name)
    if any(value not in supported for value in normalized):
        raise ValueError(f"{field_name} contains an unsupported status.")
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


def _as_positive_float(value: object, field_name: str) -> float:
    if isinstance(value, bool):
        raise TypeError(f"{field_name} must be a number.")
    try:
        normalized = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise TypeError(f"{field_name} must be a number.") from exc
    if not isfinite(normalized):
        raise ValueError(f"{field_name} must be finite.")
    if normalized <= 0.0:
        raise ValueError(f"{field_name} must be positive.")
    return normalized


def _as_non_empty_string(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise TypeError(f"{field_name} must be a non-empty string.")
    return value
