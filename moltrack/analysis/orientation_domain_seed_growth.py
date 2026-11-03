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
    normalize_m6_point_state,
    validate_m6_domain_analysis_inputs,
)
from ._orientation_domain_growth import grow_m6_labels_to_fixed_point
from .orientation_domain_models import M6AssignmentStatus
from .orientation_domain_seeds import (
    M6OrientationDomainSeedDetection,
    M6OrientationSeedComponent,
    M6SeedPointComponentType,
)


@dataclass(frozen=True)
class M6OrientationGrownComponent:
    """One seed component plus points accepted by synchronous growth."""

    seed_component: M6OrientationSeedComponent
    point_indices: tuple[int, ...]
    source_ids: tuple[str, ...]
    centroid_x_nm: float
    centroid_y_nm: float
    orientation_deg: float

    def __post_init__(self) -> None:
        if not isinstance(self.seed_component, M6OrientationSeedComponent):
            raise TypeError("seed_component must be an M6OrientationSeedComponent.")
        point_indices = tuple(self.point_indices)
        if (
            not point_indices
            or any(not isinstance(value, int) or isinstance(value, bool) or value < 0 for value in point_indices)
            or tuple(sorted(point_indices)) != point_indices
            or len(set(point_indices)) != len(point_indices)
        ):
            raise ValueError("point_indices must be non-empty, sorted, unique indices.")
        if not set(self.seed_component.point_indices).issubset(point_indices):
            raise ValueError("A grown component must retain every seed point.")
        if (
            not self.seed_component.can_initiate_growth
            and point_indices != self.seed_component.point_indices
        ):
            raise ValueError("A small_ordered_island cannot grow.")
        source_ids = tuple(self.source_ids)
        if (
            len(source_ids) != len(point_indices)
            or len(set(source_ids)) != len(source_ids)
            or any(not isinstance(value, str) or not value for value in source_ids)
        ):
            raise ValueError("source_ids must contain one unique ID per component point.")
        centroid_x = _finite_float(self.centroid_x_nm, "centroid_x_nm")
        centroid_y = _finite_float(self.centroid_y_nm, "centroid_y_nm")
        orientation = _finite_float(self.orientation_deg, "orientation_deg") % 60.0
        object.__setattr__(self, "point_indices", point_indices)
        object.__setattr__(self, "source_ids", source_ids)
        object.__setattr__(self, "centroid_x_nm", centroid_x)
        object.__setattr__(self, "centroid_y_nm", centroid_y)
        object.__setattr__(self, "orientation_deg", orientation)

    @property
    def ordered_component_id(self) -> int:
        return self.seed_component.ordered_component_id

    @property
    def seed_component_type(self) -> Literal["growth_seed", "small_ordered_island"]:
        return self.seed_component.component_type

    @property
    def can_initiate_growth(self) -> bool:
        return self.seed_component.can_initiate_growth

    @property
    def seed_point_indices(self) -> tuple[int, ...]:
        return self.seed_component.point_indices

    @property
    def molecule_count(self) -> int:
        return len(self.point_indices)


@dataclass(frozen=True)
class M6OrientationDomainGrowthState:
    """Deterministic fixed point of synchronous M6 seed growth."""

    source_ids: tuple[str, ...]
    point_count: int
    seed_eligible: tuple[bool, ...]
    ordered_component_id: tuple[int, ...]
    seed_component_type: tuple[M6SeedPointComponentType, ...]
    assignment_status: tuple[M6AssignmentStatus, ...]
    edge_truncated_neighborhood: tuple[bool, ...]
    physical_duplicate_qc: tuple[bool, ...]
    geometry_duplicate_qc: tuple[bool, ...]
    components: tuple[M6OrientationGrownComponent, ...]
    growth_iteration_count: int
    settings: MolecularM6OrientationAnalysisSettings
    coordinate_frame: Literal["sample_nm"]
    orientation_reference: OrientationReference
    spatial_calibration_fingerprint: str
    registration_fingerprint: str
    point_coordinate_fingerprint: str

    def __post_init__(self) -> None:
        point_state = normalize_m6_point_state(
            point_count=self.point_count,
            source_ids=self.source_ids,
            seed_eligible=self.seed_eligible,
            ordered_component_id=self.ordered_component_id,
            component_types=self.seed_component_type,
            component_type_field_name="seed_component_type",
            assignment_status=self.assignment_status,
            edge_truncated_neighborhood=self.edge_truncated_neighborhood,
            physical_duplicate_qc=self.physical_duplicate_qc,
            geometry_duplicate_qc=self.geometry_duplicate_qc,
        )
        object.__setattr__(self, "point_count", point_state.point_count)
        object.__setattr__(self, "source_ids", point_state.source_ids)
        object.__setattr__(self, "seed_eligible", point_state.seed_eligible)
        object.__setattr__(
            self,
            "ordered_component_id",
            point_state.ordered_component_id,
        )
        object.__setattr__(
            self,
            "seed_component_type",
            point_state.component_types,
        )
        object.__setattr__(
            self,
            "assignment_status",
            point_state.assignment_status,
        )
        object.__setattr__(
            self,
            "edge_truncated_neighborhood",
            point_state.edge_truncated_neighborhood,
        )
        object.__setattr__(
            self,
            "physical_duplicate_qc",
            point_state.physical_duplicate_qc,
        )
        object.__setattr__(
            self,
            "geometry_duplicate_qc",
            point_state.geometry_duplicate_qc,
        )
        if not isinstance(self.settings, MolecularM6OrientationAnalysisSettings):
            raise TypeError("settings must be MolecularM6OrientationAnalysisSettings.")
        if (
            not isinstance(self.growth_iteration_count, int)
            or isinstance(self.growth_iteration_count, bool)
            or self.growth_iteration_count < 0
        ):
            raise ValueError("growth_iteration_count must be a non-negative integer.")
        if self.coordinate_frame != "sample_nm":
            raise ValueError("coordinate_frame must be 'sample_nm'.")
        for field_name in (
            "spatial_calibration_fingerprint",
            "registration_fingerprint",
            "point_coordinate_fingerprint",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value:
                raise TypeError(f"{field_name} must be a non-empty string.")

        components = tuple(self.components)
        if any(not isinstance(value, M6OrientationGrownComponent) for value in components):
            raise TypeError("components must contain M6OrientationGrownComponent values.")
        if tuple(component.ordered_component_id for component in components) != tuple(
            range(len(components))
        ):
            raise ValueError("components must retain compact seed ordered_component_id values.")
        covered: set[int] = set()
        for component in components:
            for point_index, source_id in zip(component.point_indices, component.source_ids):
                if point_index >= self.point_count or point_index in covered:
                    raise ValueError("Component point indices must be in range and disjoint.")
                covered.add(point_index)
                if self.source_ids[point_index] != source_id:
                    raise ValueError("Component source_ids must match point indices.")
                if self.ordered_component_id[point_index] != component.ordered_component_id:
                    raise ValueError("Point ordered_component_id must match its component.")
                if (
                    self.seed_component_type[point_index]
                    != component.seed_component_type
                ):
                    raise ValueError(
                        "Point seed_component_type must match its seed component."
                    )
                if self.assignment_status[point_index] != "assigned":
                    raise ValueError("Component points must have assignment_status='assigned'.")
            if any(not self.seed_eligible[index] for index in component.seed_point_indices):
                raise ValueError("Every retained seed point must be seed eligible.")
        assigned = {
            index
            for index, status in enumerate(self.assignment_status)
            if status == "assigned"
        }
        if assigned != covered:
            raise ValueError("Every assigned point must belong to exactly one component.")
        for index in range(self.point_count):
            if index not in covered and (
                self.ordered_component_id[index] != -1
                or self.seed_component_type[index] != "unassigned"
            ):
                raise ValueError(
                    "Unassigned points must use label=-1 and seed type='unassigned'."
                )
        object.__setattr__(self, "components", components)

    @property
    def ordered_component_count(self) -> int:
        return len(self.components)

    @property
    def growth_seed_count(self) -> int:
        return sum(component.can_initiate_growth for component in self.components)

    @property
    def small_ordered_island_count(self) -> int:
        return self.ordered_component_count - self.growth_seed_count

    def component_for_source_id(
        self,
        source_id: str,
    ) -> M6OrientationGrownComponent | None:
        try:
            point_index = self.source_ids.index(source_id)
        except ValueError as exc:
            raise KeyError(f"Unknown source_id: {source_id!r}.") from exc
        ordered_id = self.ordered_component_id[point_index]
        if ordered_id < 0:
            return None
        return self.components[ordered_id]


def grow_m6_orientation_domains(
    points_xy_nm: object,
    *,
    first_shell_graph: FirstShellGraph,
    local_order: LocalSixfoldBondOrderField,
    seeds: M6OrientationDomainSeedDetection,
    settings: MolecularM6OrientationAnalysisSettings | None = None,
) -> M6OrientationDomainGrowthState:
    """Grow eligible M6 seeds in frozen-orientation synchronous batches."""

    settings = _normalize_settings(settings)
    points = validate_m6_domain_analysis_inputs(
        points_xy_nm,
        first_shell_graph=first_shell_graph,
        local_order=local_order,
        settings=settings,
    )
    _validate_seed_detection(
        seeds,
        first_shell_graph=first_shell_graph,
        settings=settings,
    )
    labels = list(seeds.ordered_component_id)
    growth_component_ids = tuple(
        component.ordered_component_id
        for component in _growth_seed_components(seeds)
    )
    labels, iteration_count = grow_m6_labels_to_fixed_point(
        labels,
        growth_component_ids,
        first_shell_graph=first_shell_graph,
        local_order=local_order,
        settings=settings,
    )

    components = tuple(
        _grown_component(
            seed_component,
            tuple(
                point_index
                for point_index, component_id in enumerate(labels)
                if component_id == seed_component.ordered_component_id
            ),
            points=points,
            local_order=local_order,
        )
        for seed_component in seeds.components
    )
    return _build_growth_state(
        seeds=seeds,
        components=components,
        growth_iteration_count=iteration_count,
        local_order=local_order,
    )


def _normalize_settings(
    settings: MolecularM6OrientationAnalysisSettings | None,
) -> MolecularM6OrientationAnalysisSettings:
    if settings is None:
        return MolecularM6OrientationAnalysisSettings()
    if not isinstance(settings, MolecularM6OrientationAnalysisSettings):
        raise TypeError("settings must be MolecularM6OrientationAnalysisSettings.")
    return settings


def _validate_seed_detection(
    seeds: M6OrientationDomainSeedDetection,
    *,
    first_shell_graph: FirstShellGraph,
    settings: MolecularM6OrientationAnalysisSettings,
) -> None:
    if not isinstance(seeds, M6OrientationDomainSeedDetection):
        raise TypeError("seeds must be an M6OrientationDomainSeedDetection.")
    if seeds.source_ids != first_shell_graph.point_ids:
        raise ValueError("seeds must match first_shell_graph point IDs and order.")
    if seeds.settings != settings:
        raise ValueError("seeds must use the supplied settings.")
    seed_provenance = (
        seeds.coordinate_frame,
        seeds.orientation_reference,
        seeds.spatial_calibration_fingerprint,
        seeds.registration_fingerprint,
        seeds.point_coordinate_fingerprint,
    )
    graph_provenance = (
        first_shell_graph.coordinate_frame,
        first_shell_graph.orientation_reference,
        first_shell_graph.spatial_calibration_fingerprint,
        first_shell_graph.registration_fingerprint,
        first_shell_graph.point_coordinate_fingerprint,
    )
    if seed_provenance != graph_provenance:
        raise ValueError("seeds and first_shell_graph provenance must match.")


def _growth_seed_components(
    seeds: M6OrientationDomainSeedDetection,
) -> tuple[M6OrientationSeedComponent, ...]:
    return tuple(
        component for component in seeds.components if component.can_initiate_growth
    )


def _grown_component(
    seed_component: M6OrientationSeedComponent,
    members: tuple[int, ...],
    *,
    points: np.ndarray,
    local_order: LocalSixfoldBondOrderField,
) -> M6OrientationGrownComponent:
    ordered_members = sorted(members, key=lambda index: local_order.source_ids[index])
    count = len(ordered_members)
    return M6OrientationGrownComponent(
        seed_component=seed_component,
        point_indices=members,
        source_ids=tuple(local_order.source_ids[index] for index in members),
        centroid_x_nm=(
            fsum(float(points[index, 0]) for index in ordered_members) / count
        ),
        centroid_y_nm=(
            fsum(float(points[index, 1]) for index in ordered_members) / count
        ),
        orientation_deg=component_m6_orientation_deg(members, local_order),
    )


def _build_growth_state(
    *,
    seeds: M6OrientationDomainSeedDetection,
    components: tuple[M6OrientationGrownComponent, ...],
    growth_iteration_count: int,
    local_order: LocalSixfoldBondOrderField,
) -> M6OrientationDomainGrowthState:
    labels = [-1] * seeds.point_count
    component_types: list[M6SeedPointComponentType] = ["unassigned"] * seeds.point_count
    statuses = [
        initial_m6_assignment_status(value)
        for value in local_order.computation_status
    ]
    for component in components:
        for point_index in component.point_indices:
            labels[point_index] = component.ordered_component_id
            component_types[point_index] = component.seed_component_type
            statuses[point_index] = "assigned"
    return M6OrientationDomainGrowthState(
        source_ids=seeds.source_ids,
        point_count=seeds.point_count,
        seed_eligible=seeds.seed_eligible,
        ordered_component_id=tuple(labels),
        seed_component_type=tuple(component_types),
        assignment_status=tuple(statuses),
        edge_truncated_neighborhood=seeds.edge_truncated_neighborhood,
        physical_duplicate_qc=seeds.physical_duplicate_qc,
        geometry_duplicate_qc=seeds.geometry_duplicate_qc,
        components=components,
        growth_iteration_count=growth_iteration_count,
        settings=seeds.settings,
        coordinate_frame=seeds.coordinate_frame,
        orientation_reference=seeds.orientation_reference,
        spatial_calibration_fingerprint=seeds.spatial_calibration_fingerprint,
        registration_fingerprint=seeds.registration_fingerprint,
        point_coordinate_fingerprint=seeds.point_coordinate_fingerprint,
    )


def _finite_float(value: object, field_name: str) -> float:
    if isinstance(value, bool):
        raise TypeError(f"{field_name} must be numeric.")
    try:
        normalized = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise TypeError(f"{field_name} must be numeric.") from exc
    if not isfinite(normalized):
        raise ValueError(f"{field_name} must be finite.")
    return normalized
