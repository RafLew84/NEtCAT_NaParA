from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Literal

from .first_shell_graph import OrientationReference
from .m6_settings import MolecularM6OrientationAnalysisSettings


M6ComponentType = Literal[
    "full_domain",
    "small_ordered_island",
    "unassigned",
]
M6AssignmentStatus = Literal[
    "assigned",
    "boundary_or_disordered",
    "insufficient_neighbors",
    "duplicate_excluded",
    "invalid_position",
]


_COMPONENT_TYPES = {
    "full_domain",
    "small_ordered_island",
    "unassigned",
}
_ASSIGNMENT_STATUSES = {
    "assigned",
    "boundary_or_disordered",
    "insufficient_neighbors",
    "duplicate_excluded",
    "invalid_position",
}
_ORIENTATION_REFERENCES = {
    "+x_sample_axis",
    "scan_x_axis_assumed_sample_x",
}


@dataclass(frozen=True)
class LatticeOrientationDomain:
    """Spatially connected psi6 orientation component.

    This is not by itself a distinct phase, translational domain, or row
    direction. Those scientific distinctions require additional analysis.
    """

    ordered_component_id: int
    m6_orientation_domain_id: int | None
    component_type: Literal["full_domain", "small_ordered_island"]
    point_indices: tuple[int, ...]
    source_ids: tuple[str, ...]
    molecule_count: int
    centroid_x_nm: float
    centroid_y_nm: float
    orientation_deg: float

    def __post_init__(self) -> None:
        ordered_id = _as_non_negative_integer(
            self.ordered_component_id,
            "ordered_component_id",
        )
        if self.component_type not in {"full_domain", "small_ordered_island"}:
            raise ValueError(f"Unsupported component_type: {self.component_type!r}.")
        if self.m6_orientation_domain_id is None:
            domain_id = None
        else:
            domain_id = _as_non_negative_integer(
                self.m6_orientation_domain_id,
                "m6_orientation_domain_id",
            )
        if self.component_type == "full_domain" and domain_id is None:
            raise ValueError("A full_domain requires m6_orientation_domain_id.")
        if self.component_type == "small_ordered_island" and domain_id is not None:
            raise ValueError(
                "A small_ordered_island cannot have m6_orientation_domain_id."
            )

        point_indices = tuple(
            _as_non_negative_integer(value, f"point_indices[{index}]")
            for index, value in enumerate(self.point_indices)
        )
        if tuple(sorted(point_indices)) != point_indices:
            raise ValueError("point_indices must be sorted in input order.")
        if len(set(point_indices)) != len(point_indices):
            raise ValueError("point_indices must be unique.")
        source_ids = tuple(self.source_ids)
        if any(not isinstance(source_id, str) or not source_id for source_id in source_ids):
            raise TypeError("source_ids must contain non-empty strings.")
        if len(set(source_ids)) != len(source_ids):
            raise ValueError("source_ids must be unique within a component.")
        molecule_count = _as_positive_integer(self.molecule_count, "molecule_count")
        if len(point_indices) != molecule_count or len(source_ids) != molecule_count:
            raise ValueError(
                "point_indices and source_ids must contain molecule_count values."
            )
        centroid_x = _as_finite_float(self.centroid_x_nm, "centroid_x_nm")
        centroid_y = _as_finite_float(self.centroid_y_nm, "centroid_y_nm")
        orientation = _as_finite_float(self.orientation_deg, "orientation_deg") % 60.0

        object.__setattr__(self, "ordered_component_id", ordered_id)
        object.__setattr__(self, "m6_orientation_domain_id", domain_id)
        object.__setattr__(self, "point_indices", point_indices)
        object.__setattr__(self, "source_ids", source_ids)
        object.__setattr__(self, "molecule_count", molecule_count)
        object.__setattr__(self, "centroid_x_nm", centroid_x)
        object.__setattr__(self, "centroid_y_nm", centroid_y)
        object.__setattr__(self, "orientation_deg", orientation)

    @property
    def smallest_source_id(self) -> str:
        return min(self.source_ids)

    @property
    def stable_sort_key(self) -> tuple[int, float, float, float, str]:
        return (
            -self.molecule_count,
            self.centroid_x_nm,
            self.centroid_y_nm,
            self.orientation_deg,
            self.smallest_source_id,
        )


@dataclass(frozen=True)
class M6OrientationDomainSegmentation:
    """Stable point assignments to spatially continuous M6 components."""

    source_ids: tuple[str, ...]
    point_count: int
    ordered_component_id: tuple[int, ...]
    m6_orientation_domain_id: tuple[int, ...]
    component_type: tuple[M6ComponentType, ...]
    assignment_status: tuple[M6AssignmentStatus, ...]
    edge_truncated_neighborhood: tuple[bool, ...]
    physical_duplicate_qc: tuple[bool, ...]
    geometry_duplicate_qc: tuple[bool, ...]
    components: tuple[LatticeOrientationDomain, ...]
    settings: MolecularM6OrientationAnalysisSettings
    coordinate_frame: Literal["sample_nm"]
    orientation_reference: OrientationReference
    spatial_calibration_fingerprint: str
    registration_fingerprint: str
    point_coordinate_fingerprint: str

    def __post_init__(self) -> None:
        point_count = _as_non_negative_integer(self.point_count, "point_count")
        source_ids = _per_point_tuple(
            self.source_ids,
            point_count=point_count,
            field_name="source_ids",
        )
        if any(not isinstance(source_id, str) or not source_id for source_id in source_ids):
            raise TypeError("source_ids must contain non-empty strings.")
        if len(set(source_ids)) != point_count:
            raise ValueError("source_ids must be unique.")
        ordered_ids = tuple(
            _as_label(value, f"ordered_component_id[{index}]")
            for index, value in enumerate(
                _per_point_tuple(
                    self.ordered_component_id,
                    point_count=point_count,
                    field_name="ordered_component_id",
                )
            )
        )
        domain_ids = tuple(
            _as_label(value, f"m6_orientation_domain_id[{index}]")
            for index, value in enumerate(
                _per_point_tuple(
                    self.m6_orientation_domain_id,
                    point_count=point_count,
                    field_name="m6_orientation_domain_id",
                )
            )
        )
        component_types = _status_tuple(
            self.component_type,
            point_count=point_count,
            field_name="component_type",
            supported=_COMPONENT_TYPES,
        )
        assignment_statuses = _status_tuple(
            self.assignment_status,
            point_count=point_count,
            field_name="assignment_status",
            supported=_ASSIGNMENT_STATUSES,
        )
        edge_qc = _boolean_tuple(
            self.edge_truncated_neighborhood,
            point_count=point_count,
            field_name="edge_truncated_neighborhood",
        )
        physical_qc = _boolean_tuple(
            self.physical_duplicate_qc,
            point_count=point_count,
            field_name="physical_duplicate_qc",
        )
        geometry_qc = _boolean_tuple(
            self.geometry_duplicate_qc,
            point_count=point_count,
            field_name="geometry_duplicate_qc",
        )

        for index in range(point_count):
            status = assignment_statuses[index]
            component = component_types[index]
            ordered_id = ordered_ids[index]
            domain_id = domain_ids[index]
            is_duplicate = physical_qc[index] or geometry_qc[index]
            if physical_qc[index] and geometry_qc[index]:
                raise ValueError("A point cannot be both a physical and geometry duplicate.")
            if is_duplicate != (status == "duplicate_excluded"):
                raise ValueError(
                    "Duplicate QC flags must correspond exactly to duplicate_excluded status."
                )
            if status == "assigned":
                if ordered_id < 0 or component == "unassigned":
                    raise ValueError("assigned points require an ordered component.")
                if component == "full_domain" and domain_id < 0:
                    raise ValueError("full_domain points require m6_orientation_domain_id.")
                if component == "small_ordered_island" and domain_id != -1:
                    raise ValueError(
                        "small_ordered_island points cannot have m6_orientation_domain_id."
                    )
            elif ordered_id != -1 or domain_id != -1 or component != "unassigned":
                raise ValueError(
                    "Unassigned statuses require both labels=-1 and component_type='unassigned'."
                )

        if not isinstance(self.settings, MolecularM6OrientationAnalysisSettings):
            raise TypeError("settings must be MolecularM6OrientationAnalysisSettings.")
        components = tuple(self.components)
        if any(not isinstance(value, LatticeOrientationDomain) for value in components):
            raise TypeError("components must contain LatticeOrientationDomain values.")
        self._validate_components(
            components,
            source_ids=source_ids,
            ordered_ids=ordered_ids,
            domain_ids=domain_ids,
            component_types=component_types,
            assignment_statuses=assignment_statuses,
        )
        components = tuple(sorted(components, key=lambda component: component.ordered_component_id))

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
        coordinate_fingerprint = _as_non_empty_string(
            self.point_coordinate_fingerprint,
            "point_coordinate_fingerprint",
        )

        object.__setattr__(self, "source_ids", source_ids)
        object.__setattr__(self, "point_count", point_count)
        object.__setattr__(self, "ordered_component_id", ordered_ids)
        object.__setattr__(self, "m6_orientation_domain_id", domain_ids)
        object.__setattr__(self, "component_type", component_types)
        object.__setattr__(self, "assignment_status", assignment_statuses)
        object.__setattr__(self, "edge_truncated_neighborhood", edge_qc)
        object.__setattr__(self, "physical_duplicate_qc", physical_qc)
        object.__setattr__(self, "geometry_duplicate_qc", geometry_qc)
        object.__setattr__(self, "components", components)
        object.__setattr__(self, "spatial_calibration_fingerprint", calibration_fingerprint)
        object.__setattr__(self, "registration_fingerprint", registration_fingerprint)
        object.__setattr__(self, "point_coordinate_fingerprint", coordinate_fingerprint)

    def _validate_components(
        self,
        components: tuple[LatticeOrientationDomain, ...],
        *,
        source_ids: tuple[object, ...],
        ordered_ids: tuple[int, ...],
        domain_ids: tuple[int, ...],
        component_types: tuple[object, ...],
        assignment_statuses: tuple[object, ...],
    ) -> None:
        sorted_components = tuple(sorted(components, key=lambda value: value.stable_sort_key))
        for expected_id, component in enumerate(sorted_components):
            if component.ordered_component_id != expected_id:
                raise ValueError(
                    "ordered_component_id values must follow the stable lexicographic order."
                )
        full_components = tuple(
            component for component in sorted_components if component.component_type == "full_domain"
        )
        for expected_id, component in enumerate(full_components):
            if component.m6_orientation_domain_id != expected_id:
                raise ValueError(
                    "m6_orientation_domain_id values must follow the stable lexicographic order."
                )

        assigned_indices: set[int] = set()
        for component in components:
            if component.component_type == "full_domain":
                if component.molecule_count < self.settings.min_domain_size:
                    raise ValueError("full_domain size must reach min_domain_size.")
            elif not (
                self.settings.min_ordered_component_size
                <= component.molecule_count
                < self.settings.min_domain_size
            ):
                raise ValueError(
                    "small_ordered_island size must lie between ordered and domain thresholds."
                )
            for point_index, component_source_id in zip(
                component.point_indices,
                component.source_ids,
            ):
                if point_index >= len(source_ids):
                    raise ValueError("Component point index is outside the point array.")
                if point_index in assigned_indices:
                    raise ValueError("A point cannot belong to more than one component.")
                assigned_indices.add(point_index)
                if source_ids[point_index] != component_source_id:
                    raise ValueError("Component source_ids must match point indices and order.")
                if ordered_ids[point_index] != component.ordered_component_id:
                    raise ValueError("Point ordered_component_id does not match its component.")
                expected_domain_id = (
                    component.m6_orientation_domain_id
                    if component.m6_orientation_domain_id is not None
                    else -1
                )
                if domain_ids[point_index] != expected_domain_id:
                    raise ValueError(
                        "Point m6_orientation_domain_id does not match its component."
                    )
                if component_types[point_index] != component.component_type:
                    raise ValueError("Point component_type does not match its component.")
                if assignment_statuses[point_index] != "assigned":
                    raise ValueError("Component points must have assignment_status='assigned'.")
        expected_assigned = {
            index for index, status in enumerate(assignment_statuses) if status == "assigned"
        }
        if assigned_indices != expected_assigned:
            raise ValueError("Every assigned point must belong to exactly one component.")

    @property
    def ordered_component_count(self) -> int:
        return len(self.components)

    @property
    def full_domain_count(self) -> int:
        return sum(component.component_type == "full_domain" for component in self.components)

    @property
    def small_ordered_island_count(self) -> int:
        return sum(
            component.component_type == "small_ordered_island"
            for component in self.components
        )

    @property
    def domains(self) -> tuple[LatticeOrientationDomain, ...]:
        return tuple(
            component for component in self.components if component.component_type == "full_domain"
        )

    @property
    def small_ordered_islands(self) -> tuple[LatticeOrientationDomain, ...]:
        return tuple(
            component
            for component in self.components
            if component.component_type == "small_ordered_island"
        )

    def component_for_source_id(self, source_id: str) -> LatticeOrientationDomain | None:
        try:
            point_index = self.source_ids.index(source_id)
        except ValueError as exc:
            raise KeyError(f"Unknown source_id: {source_id!r}.") from exc
        ordered_id = self.ordered_component_id[point_index]
        if ordered_id < 0:
            return None
        return self.components[ordered_id]


def _per_point_tuple(
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


def _status_tuple(
    values: object,
    *,
    point_count: int,
    field_name: str,
    supported: set[str],
) -> tuple:
    normalized = _per_point_tuple(
        values,
        point_count=point_count,
        field_name=field_name,
    )
    if any(value not in supported for value in normalized):
        raise ValueError(f"{field_name} contains an unsupported value.")
    return normalized


def _boolean_tuple(
    values: object,
    *,
    point_count: int,
    field_name: str,
) -> tuple[bool, ...]:
    normalized = _per_point_tuple(
        values,
        point_count=point_count,
        field_name=field_name,
    )
    if any(not isinstance(value, bool) for value in normalized):
        raise TypeError(f"{field_name} must contain only booleans.")
    return tuple(normalized)  # type: ignore[return-value]


def _as_label(value: object, field_name: str) -> int:
    normalized = _as_integer(value, field_name)
    if normalized < -1:
        raise ValueError(f"{field_name} must be -1 or a non-negative ID.")
    return normalized


def _as_non_negative_integer(value: object, field_name: str) -> int:
    normalized = _as_integer(value, field_name)
    if normalized < 0:
        raise ValueError(f"{field_name} must be non-negative.")
    return normalized


def _as_positive_integer(value: object, field_name: str) -> int:
    normalized = _as_non_negative_integer(value, field_name)
    if normalized == 0:
        raise ValueError(f"{field_name} must be positive.")
    return normalized


def _as_integer(value: object, field_name: str) -> int:
    if isinstance(value, bool):
        raise TypeError(f"{field_name} must be an integer.")
    try:
        normalized = int(value)
        numeric = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise TypeError(f"{field_name} must be an integer.") from exc
    if not isfinite(numeric) or numeric != normalized:
        raise ValueError(f"{field_name} must be an integer.")
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


def _as_non_empty_string(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise TypeError(f"{field_name} must be a non-empty string.")
    return value
