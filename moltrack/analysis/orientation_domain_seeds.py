from __future__ import annotations

from dataclasses import dataclass
from math import fsum, isfinite
from typing import Literal

import numpy as np

from .first_shell_graph import FirstShellGraph, OrientationReference
from .local_sixfold_bond_order import LocalSixfoldBondOrderField
from .m6_settings import MolecularM6OrientationAnalysisSettings
from ._orientation_domain_common import (
    component_m6_orientation_deg,
    initial_m6_assignment_status,
    m6_similarity_threshold,
    point_pair_m6_similarity,
    validate_m6_domain_analysis_inputs,
)
from .orientation_domain_models import M6AssignmentStatus


M6SeedComponentType = Literal["growth_seed", "small_ordered_island"]
M6SeedPointComponentType = Literal[
    "growth_seed",
    "small_ordered_island",
    "unassigned",
]


@dataclass(frozen=True)
class M6OrientationSeedComponent:
    """A strong connected M6 component before domain growth and final sizing."""

    ordered_component_id: int
    component_type: M6SeedComponentType
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
        if self.component_type not in {"growth_seed", "small_ordered_island"}:
            raise ValueError(f"Unsupported component_type: {self.component_type!r}.")
        point_indices = tuple(
            _as_non_negative_integer(value, f"point_indices[{index}]")
            for index, value in enumerate(self.point_indices)
        )
        if tuple(sorted(point_indices)) != point_indices or len(set(point_indices)) != len(
            point_indices
        ):
            raise ValueError("point_indices must be sorted and unique.")
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

        object.__setattr__(self, "ordered_component_id", ordered_id)
        object.__setattr__(self, "point_indices", point_indices)
        object.__setattr__(self, "source_ids", source_ids)
        object.__setattr__(self, "molecule_count", molecule_count)
        object.__setattr__(self, "centroid_x_nm", _as_finite_float(self.centroid_x_nm))
        object.__setattr__(self, "centroid_y_nm", _as_finite_float(self.centroid_y_nm))
        object.__setattr__(
            self,
            "orientation_deg",
            _as_finite_float(self.orientation_deg) % 60.0,
        )

    @property
    def can_initiate_growth(self) -> bool:
        return self.component_type == "growth_seed"

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
class M6OrientationDomainSeedDetection:
    """Strong M6 seed components and stable point-level pre-growth labels."""

    source_ids: tuple[str, ...]
    point_count: int
    seed_eligible: tuple[bool, ...]
    ordered_component_id: tuple[int, ...]
    component_type: tuple[M6SeedPointComponentType, ...]
    assignment_status: tuple[M6AssignmentStatus, ...]
    edge_truncated_neighborhood: tuple[bool, ...]
    physical_duplicate_qc: tuple[bool, ...]
    geometry_duplicate_qc: tuple[bool, ...]
    components: tuple[M6OrientationSeedComponent, ...]
    settings: MolecularM6OrientationAnalysisSettings
    coordinate_frame: Literal["sample_nm"]
    orientation_reference: OrientationReference
    spatial_calibration_fingerprint: str
    registration_fingerprint: str
    point_coordinate_fingerprint: str

    def __post_init__(self) -> None:
        point_count = _as_non_negative_integer(self.point_count, "point_count")
        source_ids = _per_point_tuple(self.source_ids, point_count, "source_ids")
        if any(not isinstance(source_id, str) or not source_id for source_id in source_ids):
            raise TypeError("source_ids must contain non-empty strings.")
        if len(set(source_ids)) != point_count:
            raise ValueError("source_ids must be unique.")
        eligible = _boolean_tuple(self.seed_eligible, point_count, "seed_eligible")
        ordered_ids = tuple(
            _as_label(value, f"ordered_component_id[{index}]")
            for index, value in enumerate(
                _per_point_tuple(
                    self.ordered_component_id,
                    point_count,
                    "ordered_component_id",
                )
            )
        )
        component_types = _per_point_tuple(
            self.component_type,
            point_count,
            "component_type",
        )
        supported_types = {"growth_seed", "small_ordered_island", "unassigned"}
        if any(value not in supported_types for value in component_types):
            raise ValueError("component_type contains an unsupported value.")
        statuses = _per_point_tuple(
            self.assignment_status,
            point_count,
            "assignment_status",
        )
        supported_statuses = {
            "assigned",
            "boundary_or_disordered",
            "insufficient_neighbors",
            "duplicate_excluded",
            "invalid_position",
        }
        if any(value not in supported_statuses for value in statuses):
            raise ValueError("assignment_status contains an unsupported value.")
        edge_qc = _boolean_tuple(
            self.edge_truncated_neighborhood,
            point_count,
            "edge_truncated_neighborhood",
        )
        physical_qc = _boolean_tuple(
            self.physical_duplicate_qc,
            point_count,
            "physical_duplicate_qc",
        )
        geometry_qc = _boolean_tuple(
            self.geometry_duplicate_qc,
            point_count,
            "geometry_duplicate_qc",
        )
        for index, status in enumerate(statuses):
            if physical_qc[index] and geometry_qc[index]:
                raise ValueError("A point cannot be both a physical and geometry duplicate.")
            if (physical_qc[index] or geometry_qc[index]) != (
                status == "duplicate_excluded"
            ):
                raise ValueError(
                    "Duplicate QC flags must correspond to duplicate_excluded status."
                )
        if not isinstance(self.settings, MolecularM6OrientationAnalysisSettings):
            raise TypeError("settings must be MolecularM6OrientationAnalysisSettings.")

        components = tuple(self.components)
        if any(not isinstance(value, M6OrientationSeedComponent) for value in components):
            raise TypeError("components must contain M6OrientationSeedComponent values.")
        stable_components = tuple(sorted(components, key=lambda value: value.stable_sort_key))
        covered: set[int] = set()
        for expected_id, component in enumerate(stable_components):
            if component.ordered_component_id != expected_id:
                raise ValueError(
                    "ordered_component_id values must follow the stable lexicographic order."
                )
            if component.component_type == "growth_seed":
                if component.molecule_count < self.settings.min_seed_size:
                    raise ValueError("growth_seed size must reach min_seed_size.")
            elif not (
                self.settings.min_ordered_component_size
                <= component.molecule_count
                < self.settings.min_seed_size
            ):
                raise ValueError(
                    "small_ordered_island seed size must lie below min_seed_size."
                )
            for point_index, source_id in zip(
                component.point_indices,
                component.source_ids,
            ):
                if point_index >= point_count or point_index in covered:
                    raise ValueError("Component point indices must be in range and disjoint.")
                covered.add(point_index)
                if source_ids[point_index] != source_id:
                    raise ValueError("Component source_ids must match point indices.")
                if not eligible[point_index]:
                    raise ValueError("Every component point must be seed eligible.")
                if ordered_ids[point_index] != expected_id:
                    raise ValueError("Point ordered_component_id must match its component.")
                if component_types[point_index] != component.component_type:
                    raise ValueError("Point component_type must match its component.")
                if statuses[point_index] != "assigned":
                    raise ValueError("Component points must have assignment_status='assigned'.")
        for index in range(point_count):
            if index not in covered and (
                ordered_ids[index] != -1
                or component_types[index] != "unassigned"
                or statuses[index] == "assigned"
            ):
                raise ValueError("Unassigned points must use label=-1 and type='unassigned'.")

        if self.coordinate_frame != "sample_nm":
            raise ValueError("coordinate_frame must be 'sample_nm'.")
        if self.orientation_reference not in {
            "+x_sample_axis",
            "scan_x_axis_assumed_sample_x",
        }:
            raise ValueError(f"Unsupported orientation_reference: {self.orientation_reference!r}.")

        object.__setattr__(self, "source_ids", source_ids)
        object.__setattr__(self, "point_count", point_count)
        object.__setattr__(self, "seed_eligible", eligible)
        object.__setattr__(self, "ordered_component_id", ordered_ids)
        object.__setattr__(self, "component_type", component_types)
        object.__setattr__(self, "assignment_status", statuses)
        object.__setattr__(self, "edge_truncated_neighborhood", edge_qc)
        object.__setattr__(self, "physical_duplicate_qc", physical_qc)
        object.__setattr__(self, "geometry_duplicate_qc", geometry_qc)
        object.__setattr__(
            self,
            "components",
            tuple(sorted(components, key=lambda value: value.ordered_component_id)),
        )
        for field_name in (
            "spatial_calibration_fingerprint",
            "registration_fingerprint",
            "point_coordinate_fingerprint",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value:
                raise TypeError(f"{field_name} must be a non-empty string.")

    @property
    def ordered_component_count(self) -> int:
        return len(self.components)

    @property
    def growth_seed_count(self) -> int:
        return sum(component.can_initiate_growth for component in self.components)

    @property
    def small_ordered_island_count(self) -> int:
        return sum(not component.can_initiate_growth for component in self.components)

    def component_for_source_id(
        self,
        source_id: str,
    ) -> M6OrientationSeedComponent | None:
        try:
            point_index = self.source_ids.index(source_id)
        except ValueError as exc:
            raise KeyError(f"Unknown source_id: {source_id!r}.") from exc
        ordered_id = self.ordered_component_id[point_index]
        if ordered_id < 0:
            return None
        return self.components[ordered_id]


@dataclass(frozen=True)
class _SeedCandidate:
    point_indices: tuple[int, ...]
    source_ids: tuple[str, ...]
    centroid_x_nm: float
    centroid_y_nm: float
    orientation_deg: float
    component_type: M6SeedComponentType

    @property
    def stable_sort_key(self) -> tuple[int, float, float, float, str]:
        return (
            -len(self.point_indices),
            self.centroid_x_nm,
            self.centroid_y_nm,
            self.orientation_deg,
            min(self.source_ids),
        )


def detect_m6_orientation_domain_seeds(
    points_xy_nm: object,
    *,
    first_shell_graph: FirstShellGraph,
    local_order: LocalSixfoldBondOrderField,
    settings: MolecularM6OrientationAnalysisSettings | None = None,
) -> M6OrientationDomainSeedDetection:
    """Detect strong, spatially connected M6 components eligible for growth."""

    if settings is None:
        settings = MolecularM6OrientationAnalysisSettings()
    if not isinstance(settings, MolecularM6OrientationAnalysisSettings):
        raise TypeError("settings must be MolecularM6OrientationAnalysisSettings.")
    if not isinstance(first_shell_graph, FirstShellGraph):
        raise TypeError("first_shell_graph must be a FirstShellGraph.")
    if not isinstance(local_order, LocalSixfoldBondOrderField):
        raise TypeError("local_order must be a LocalSixfoldBondOrderField.")
    points = validate_m6_domain_analysis_inputs(
        points_xy_nm,
        first_shell_graph=first_shell_graph,
        local_order=local_order,
        settings=settings,
    )

    eligible = tuple(
        local_order.computation_status[index] == "valid_order"
        and local_order.orientation_status[index] == "defined"
        and local_order.q6[index] is not None
        and local_order.q6[index] >= settings.q_seed
        and local_order.neighbor_count[index] >= settings.min_neighbors_for_seed
        and not local_order.edge_truncated_neighborhood[index]
        and not local_order.physical_duplicate_qc[index]
        and not local_order.geometry_duplicate_qc[index]
        for index in range(local_order.point_count)
    )
    adjacency: list[list[int]] = [[] for _ in range(local_order.point_count)]
    similarity_limit = m6_similarity_threshold(settings.seed_angle_tolerance_deg)
    for left, right in first_shell_graph.edges_ij:
        if not eligible[left] or not eligible[right]:
            continue
        if point_pair_m6_similarity(local_order, left, right) + 1e-15 < similarity_limit:
            continue
        adjacency[left].append(right)
        adjacency[right].append(left)

    raw_components = _connected_eligible_components(eligible, adjacency)
    candidates = tuple(
        _build_candidate(members, points, local_order, settings)
        for members in raw_components
        if len(members) >= settings.min_ordered_component_size
    )
    ordered_candidates = tuple(sorted(candidates, key=lambda value: value.stable_sort_key))

    ordered_ids = [-1] * local_order.point_count
    component_types: list[M6SeedPointComponentType] = [
        "unassigned"
    ] * local_order.point_count
    statuses: list[M6AssignmentStatus] = [
        initial_m6_assignment_status(status)
        for status in local_order.computation_status
    ]
    components: list[M6OrientationSeedComponent] = []
    for ordered_id, candidate in enumerate(ordered_candidates):
        component = M6OrientationSeedComponent(
            ordered_component_id=ordered_id,
            component_type=candidate.component_type,
            point_indices=candidate.point_indices,
            source_ids=candidate.source_ids,
            molecule_count=len(candidate.point_indices),
            centroid_x_nm=candidate.centroid_x_nm,
            centroid_y_nm=candidate.centroid_y_nm,
            orientation_deg=candidate.orientation_deg,
        )
        components.append(component)
        for point_index in component.point_indices:
            ordered_ids[point_index] = ordered_id
            component_types[point_index] = component.component_type
            statuses[point_index] = "assigned"

    return M6OrientationDomainSeedDetection(
        source_ids=local_order.source_ids,
        point_count=local_order.point_count,
        seed_eligible=eligible,
        ordered_component_id=tuple(ordered_ids),
        component_type=tuple(component_types),
        assignment_status=tuple(statuses),
        edge_truncated_neighborhood=local_order.edge_truncated_neighborhood,
        physical_duplicate_qc=local_order.physical_duplicate_qc,
        geometry_duplicate_qc=local_order.geometry_duplicate_qc,
        components=tuple(components),
        settings=settings,
        coordinate_frame="sample_nm",
        orientation_reference=first_shell_graph.orientation_reference,
        spatial_calibration_fingerprint=first_shell_graph.spatial_calibration_fingerprint,
        registration_fingerprint=first_shell_graph.registration_fingerprint,
        point_coordinate_fingerprint=first_shell_graph.point_coordinate_fingerprint,
    )


def _connected_eligible_components(
    eligible: tuple[bool, ...],
    adjacency: list[list[int]],
) -> tuple[tuple[int, ...], ...]:
    visited: set[int] = set()
    components: list[tuple[int, ...]] = []
    for start, is_eligible in enumerate(eligible):
        if not is_eligible or start in visited:
            continue
        stack = [start]
        visited.add(start)
        members: list[int] = []
        while stack:
            point = stack.pop()
            members.append(point)
            for neighbor in adjacency[point]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    stack.append(neighbor)
        components.append(tuple(sorted(members)))
    return tuple(components)


def _build_candidate(
    members: tuple[int, ...],
    points: np.ndarray,
    local_order: LocalSixfoldBondOrderField,
    settings: MolecularM6OrientationAnalysisSettings,
) -> _SeedCandidate:
    source_order = tuple(sorted(members, key=lambda index: local_order.source_ids[index]))
    return _SeedCandidate(
        point_indices=members,
        source_ids=tuple(local_order.source_ids[index] for index in members),
        centroid_x_nm=fsum(float(points[index, 0]) for index in source_order) / len(members),
        centroid_y_nm=fsum(float(points[index, 1]) for index in source_order) / len(members),
        orientation_deg=component_m6_orientation_deg(members, local_order),
        component_type=(
            "growth_seed"
            if len(members) >= settings.min_seed_size
            else "small_ordered_island"
        ),
    )


def _per_point_tuple(values: object, point_count: int, field_name: str) -> tuple:
    try:
        normalized = tuple(values)  # type: ignore[arg-type]
    except TypeError as exc:
        raise TypeError(f"{field_name} must be an iterable.") from exc
    if len(normalized) != point_count:
        raise ValueError(f"{field_name} must contain one value per point.")
    return normalized


def _boolean_tuple(values: object, point_count: int, field_name: str) -> tuple[bool, ...]:
    normalized = _per_point_tuple(values, point_count, field_name)
    if any(not isinstance(value, bool) for value in normalized):
        raise TypeError(f"{field_name} must contain only booleans.")
    return normalized


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


def _as_finite_float(value: object) -> float:
    if isinstance(value, bool):
        raise TypeError("Component coordinates and orientation must be numeric.")
    try:
        normalized = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise TypeError("Component coordinates and orientation must be numeric.") from exc
    if not isfinite(normalized):
        raise ValueError("Component coordinates and orientation must be finite.")
    return normalized
