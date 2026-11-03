from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from math import fsum, isfinite
from typing import Literal

import numpy as np

from ._orientation_domain_common import (
    component_m6_orientation_deg,
    initial_m6_assignment_status,
    m6_orientation_distance_deg,
    normalize_m6_point_state,
    validate_m6_domain_analysis_inputs,
)
from ._orientation_domain_growth import (
    graph_adjacency,
    grow_m6_labels_to_fixed_point,
    is_m6_growth_candidate,
)
from .first_shell_graph import FirstShellGraph, OrientationReference
from .local_sixfold_bond_order import LocalSixfoldBondOrderField
from .m6_settings import MolecularM6OrientationAnalysisSettings
from .orientation_domain_models import M6AssignmentStatus
from .orientation_domain_seed_growth import M6OrientationDomainGrowthState
from .orientation_domain_seeds import (
    M6OrientationSeedComponent,
    M6SeedPointComponentType,
)


@dataclass(frozen=True)
class M6OrientationMergeConstituent:
    """One original seed component and its frozen pre-merge orientation."""

    seed_component: M6OrientationSeedComponent
    orientation_deg: float

    def __post_init__(self) -> None:
        if not isinstance(self.seed_component, M6OrientationSeedComponent):
            raise TypeError("seed_component must be an M6OrientationSeedComponent.")
        object.__setattr__(
            self,
            "orientation_deg",
            _finite_float(self.orientation_deg, "orientation_deg") % 60.0,
        )

    @property
    def stable_sort_key(self) -> tuple[int, float, float, float, str, float]:
        return (*self.seed_component.stable_sort_key, self.orientation_deg)


@dataclass(frozen=True)
class M6OrientationMergedComponent:
    """One temporary component after deterministic complete-linkage merging."""

    ordered_component_id: int
    constituents: tuple[M6OrientationMergeConstituent, ...]
    point_indices: tuple[int, ...]
    source_ids: tuple[str, ...]
    centroid_x_nm: float
    centroid_y_nm: float
    orientation_deg: float

    def __post_init__(self) -> None:
        component_id = _non_negative_integer(
            self.ordered_component_id,
            "ordered_component_id",
        )
        constituents = tuple(self.constituents)
        if not constituents or any(
            not isinstance(value, M6OrientationMergeConstituent)
            for value in constituents
        ):
            raise TypeError(
                "constituents must contain at least one M6OrientationMergeConstituent."
            )
        constituents = tuple(sorted(constituents, key=lambda value: value.stable_sort_key))
        seeds = tuple(value.seed_component for value in constituents)
        if len({seed.ordered_component_id for seed in seeds}) != len(seeds):
            raise ValueError("constituents must refer to unique seed components.")
        if len(seeds) > 1 and any(not seed.can_initiate_growth for seed in seeds):
            raise ValueError("Only growth-seed components may be merged.")

        point_indices = tuple(self.point_indices)
        if (
            not point_indices
            or any(
                not isinstance(value, int)
                or isinstance(value, bool)
                or value < 0
                for value in point_indices
            )
            or tuple(sorted(point_indices)) != point_indices
            or len(set(point_indices)) != len(point_indices)
        ):
            raise ValueError("point_indices must be non-empty, sorted, unique indices.")
        seed_points = {
            point_index
            for seed in seeds
            for point_index in seed.point_indices
        }
        if not seed_points.issubset(point_indices):
            raise ValueError("A merged component must retain every seed point.")
        if not any(seed.can_initiate_growth for seed in seeds) and (
            len(seeds) != 1 or point_indices != seeds[0].point_indices
        ):
            raise ValueError("A small_ordered_island cannot merge or grow.")

        source_ids = tuple(self.source_ids)
        if (
            len(source_ids) != len(point_indices)
            or len(set(source_ids)) != len(source_ids)
            or any(not isinstance(value, str) or not value for value in source_ids)
        ):
            raise ValueError("source_ids must contain one unique ID per component point.")

        object.__setattr__(self, "ordered_component_id", component_id)
        object.__setattr__(self, "constituents", constituents)
        object.__setattr__(self, "point_indices", point_indices)
        object.__setattr__(self, "source_ids", source_ids)
        object.__setattr__(
            self,
            "centroid_x_nm",
            _finite_float(self.centroid_x_nm, "centroid_x_nm"),
        )
        object.__setattr__(
            self,
            "centroid_y_nm",
            _finite_float(self.centroid_y_nm, "centroid_y_nm"),
        )
        object.__setattr__(
            self,
            "orientation_deg",
            _finite_float(self.orientation_deg, "orientation_deg") % 60.0,
        )

    @property
    def component_type(self) -> Literal["growth_seed", "small_ordered_island"]:
        return "growth_seed" if self.can_initiate_growth else "small_ordered_island"

    @property
    def can_initiate_growth(self) -> bool:
        return any(seed.can_initiate_growth for seed in self.seed_components)

    @property
    def seed_components(self) -> tuple[M6OrientationSeedComponent, ...]:
        return tuple(value.seed_component for value in self.constituents)

    @property
    def constituent_orientation_deg(self) -> tuple[float, ...]:
        return tuple(value.orientation_deg for value in self.constituents)

    @property
    def seed_component_count(self) -> int:
        return len(self.seed_components)

    @property
    def seed_point_indices(self) -> tuple[int, ...]:
        return tuple(
            sorted(
                point_index
                for seed in self.seed_components
                for point_index in seed.point_indices
            )
        )

    @property
    def molecule_count(self) -> int:
        return len(self.point_indices)

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
class M6OrientationDomainMergeState:
    """Fixed point of synchronous M6 component merging and boundary regrowth."""

    source_ids: tuple[str, ...]
    point_count: int
    seed_eligible: tuple[bool, ...]
    ordered_component_id: tuple[int, ...]
    component_type: tuple[M6SeedPointComponentType, ...]
    assignment_status: tuple[M6AssignmentStatus, ...]
    edge_truncated_neighborhood: tuple[bool, ...]
    physical_duplicate_qc: tuple[bool, ...]
    geometry_duplicate_qc: tuple[bool, ...]
    components: tuple[M6OrientationMergedComponent, ...]
    growth_iteration_count: int
    merge_iteration_count: int
    post_merge_growth_iteration_count: int
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
            component_types=self.component_type,
            component_type_field_name="component_type",
            assignment_status=self.assignment_status,
            edge_truncated_neighborhood=self.edge_truncated_neighborhood,
            physical_duplicate_qc=self.physical_duplicate_qc,
            geometry_duplicate_qc=self.geometry_duplicate_qc,
        )
        if not isinstance(self.settings, MolecularM6OrientationAnalysisSettings):
            raise TypeError("settings must be MolecularM6OrientationAnalysisSettings.")
        growth_iterations = _non_negative_integer(
            self.growth_iteration_count,
            "growth_iteration_count",
        )
        merge_iterations = _non_negative_integer(
            self.merge_iteration_count,
            "merge_iteration_count",
        )
        post_merge_iterations = _non_negative_integer(
            self.post_merge_growth_iteration_count,
            "post_merge_growth_iteration_count",
        )
        if post_merge_iterations > growth_iterations:
            raise ValueError(
                "post_merge_growth_iteration_count cannot exceed growth_iteration_count."
            )
        if merge_iterations == 0 and post_merge_iterations != 0:
            raise ValueError("Post-merge growth requires at least one merge iteration.")
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
        if any(not isinstance(value, M6OrientationMergedComponent) for value in components):
            raise TypeError("components must contain M6OrientationMergedComponent values.")
        if tuple(component.ordered_component_id for component in components) != tuple(
            range(len(components))
        ):
            raise ValueError("components must have compact ordered_component_id values.")
        covered: set[int] = set()
        for component in components:
            for point_index, source_id in zip(component.point_indices, component.source_ids):
                if point_index >= point_state.point_count or point_index in covered:
                    raise ValueError("Component point indices must be in range and disjoint.")
                covered.add(point_index)
                if point_state.source_ids[point_index] != source_id:
                    raise ValueError("Component source_ids must match point indices.")
                if (
                    point_state.ordered_component_id[point_index]
                    != component.ordered_component_id
                ):
                    raise ValueError("Point ordered_component_id must match its component.")
                if point_state.component_types[point_index] != component.component_type:
                    raise ValueError("Point component_type must match its component.")
                if point_state.assignment_status[point_index] != "assigned":
                    raise ValueError("Component points must have assignment_status='assigned'.")
            if any(
                not point_state.seed_eligible[index]
                for index in component.seed_point_indices
            ):
                raise ValueError("Every retained seed point must be seed eligible.")
        assigned = {
            index
            for index, status in enumerate(point_state.assignment_status)
            if status == "assigned"
        }
        if assigned != covered:
            raise ValueError("Every assigned point must belong to exactly one component.")
        for index in range(point_state.point_count):
            if index not in covered and (
                point_state.ordered_component_id[index] != -1
                or point_state.component_types[index] != "unassigned"
            ):
                raise ValueError(
                    "Unassigned points must use label=-1 and component_type='unassigned'."
                )

        object.__setattr__(self, "source_ids", point_state.source_ids)
        object.__setattr__(self, "point_count", point_state.point_count)
        object.__setattr__(self, "seed_eligible", point_state.seed_eligible)
        object.__setattr__(
            self,
            "ordered_component_id",
            point_state.ordered_component_id,
        )
        object.__setattr__(self, "component_type", point_state.component_types)
        object.__setattr__(self, "assignment_status", point_state.assignment_status)
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
        object.__setattr__(self, "components", components)
        object.__setattr__(self, "growth_iteration_count", growth_iterations)
        object.__setattr__(self, "merge_iteration_count", merge_iterations)
        object.__setattr__(
            self,
            "post_merge_growth_iteration_count",
            post_merge_iterations,
        )

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
    ) -> M6OrientationMergedComponent | None:
        try:
            point_index = self.source_ids.index(source_id)
        except ValueError as exc:
            raise KeyError(f"Unknown source_id: {source_id!r}.") from exc
        component_id = self.ordered_component_id[point_index]
        if component_id < 0:
            return None
        return self.components[component_id]


@dataclass(frozen=True)
class _ComponentDraft:
    constituents: tuple[M6OrientationMergeConstituent, ...]
    point_indices: tuple[int, ...]


def merge_and_grow_m6_orientation_domains(
    points_xy_nm: object,
    *,
    first_shell_graph: FirstShellGraph,
    local_order: LocalSixfoldBondOrderField,
    growth: M6OrientationDomainGrowthState,
    settings: MolecularM6OrientationAnalysisSettings | None = None,
) -> M6OrientationDomainMergeState:
    """Merge adjacent compatible components and regrow until a fixed point."""

    settings = _normalize_settings(settings)
    points = validate_m6_domain_analysis_inputs(
        points_xy_nm,
        first_shell_graph=first_shell_graph,
        local_order=local_order,
        settings=settings,
    )
    _validate_growth_state(growth, first_shell_graph=first_shell_graph, settings=settings)

    drafts = tuple(
        _ComponentDraft(
            constituents=(
                M6OrientationMergeConstituent(
                    seed_component=component.seed_component,
                    orientation_deg=component.orientation_deg,
                ),
            ),
            point_indices=component.point_indices,
        )
        for component in growth.components
    )
    components, labels = _materialize_components(
        drafts,
        points=points,
        local_order=local_order,
    )
    merge_iterations = 0
    post_merge_growth_iterations = 0

    while True:
        spatial_pairs = _spatially_adjacent_component_pairs(
            labels,
            components=components,
            first_shell_graph=first_shell_graph,
            local_order=local_order,
            settings=settings,
        )
        merge_groups = _complete_linkage_merge_groups(
            components,
            spatial_pairs=spatial_pairs,
            tolerance_deg=settings.domain_merge_angle_tolerance_deg,
        )
        if all(len(group) == 1 for group in merge_groups):
            break

        drafts = tuple(
            _merge_group_draft(group, components)
            for group in merge_groups
        )
        components, labels = _materialize_components(
            drafts,
            points=points,
            local_order=local_order,
        )
        growth_ids = tuple(
            component.ordered_component_id
            for component in components
            if component.can_initiate_growth
        )
        labels, iteration_count = grow_m6_labels_to_fixed_point(
            labels,
            growth_ids,
            first_shell_graph=first_shell_graph,
            local_order=local_order,
            settings=settings,
        )
        drafts = tuple(
            _ComponentDraft(
                constituents=component.constituents,
                point_indices=tuple(
                    point_index
                    for point_index, label in enumerate(labels)
                    if label == component.ordered_component_id
                ),
            )
            for component in components
        )
        components, labels = _materialize_components(
            drafts,
            points=points,
            local_order=local_order,
        )
        merge_iterations += 1
        post_merge_growth_iterations += iteration_count

    return _build_merge_state(
        growth=growth,
        components=components,
        labels=labels,
        merge_iteration_count=merge_iterations,
        post_merge_growth_iteration_count=post_merge_growth_iterations,
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


def _validate_growth_state(
    growth: M6OrientationDomainGrowthState,
    *,
    first_shell_graph: FirstShellGraph,
    settings: MolecularM6OrientationAnalysisSettings,
) -> None:
    if not isinstance(growth, M6OrientationDomainGrowthState):
        raise TypeError("growth must be an M6OrientationDomainGrowthState.")
    if growth.source_ids != first_shell_graph.point_ids:
        raise ValueError("growth must match first_shell_graph point IDs and order.")
    if growth.settings != settings:
        raise ValueError("growth must use the supplied settings.")
    growth_provenance = (
        growth.coordinate_frame,
        growth.orientation_reference,
        growth.spatial_calibration_fingerprint,
        growth.registration_fingerprint,
        growth.point_coordinate_fingerprint,
    )
    graph_provenance = (
        first_shell_graph.coordinate_frame,
        first_shell_graph.orientation_reference,
        first_shell_graph.spatial_calibration_fingerprint,
        first_shell_graph.registration_fingerprint,
        first_shell_graph.point_coordinate_fingerprint,
    )
    if growth_provenance != graph_provenance:
        raise ValueError("growth and first_shell_graph provenance must match.")


def _materialize_components(
    drafts: tuple[_ComponentDraft, ...],
    *,
    points: np.ndarray,
    local_order: LocalSixfoldBondOrderField,
) -> tuple[tuple[M6OrientationMergedComponent, ...], tuple[int, ...]]:
    candidates: list[M6OrientationMergedComponent] = []
    for draft in drafts:
        members = tuple(sorted(draft.point_indices))
        source_order = tuple(
            sorted(members, key=lambda index: local_order.source_ids[index])
        )
        count = len(members)
        candidates.append(
            M6OrientationMergedComponent(
                ordered_component_id=0,
                constituents=draft.constituents,
                point_indices=members,
                source_ids=tuple(local_order.source_ids[index] for index in members),
                centroid_x_nm=(
                    fsum(float(points[index, 0]) for index in source_order) / count
                ),
                centroid_y_nm=(
                    fsum(float(points[index, 1]) for index in source_order) / count
                ),
                orientation_deg=component_m6_orientation_deg(members, local_order),
            )
        )
    ordered_candidates = tuple(sorted(candidates, key=lambda value: value.stable_sort_key))
    components = tuple(
        M6OrientationMergedComponent(
            ordered_component_id=component_id,
            constituents=candidate.constituents,
            point_indices=candidate.point_indices,
            source_ids=candidate.source_ids,
            centroid_x_nm=candidate.centroid_x_nm,
            centroid_y_nm=candidate.centroid_y_nm,
            orientation_deg=candidate.orientation_deg,
        )
        for component_id, candidate in enumerate(ordered_candidates)
    )
    labels = [-1] * local_order.point_count
    for component in components:
        for point_index in component.point_indices:
            labels[point_index] = component.ordered_component_id
    return components, tuple(labels)


def _spatially_adjacent_component_pairs(
    labels: tuple[int, ...],
    *,
    components: tuple[M6OrientationMergedComponent, ...],
    first_shell_graph: FirstShellGraph,
    local_order: LocalSixfoldBondOrderField,
    settings: MolecularM6OrientationAnalysisSettings,
) -> frozenset[tuple[int, int]]:
    growth_ids = {
        component.ordered_component_id
        for component in components
        if component.can_initiate_growth
    }
    pairs: set[tuple[int, int]] = set()
    for left, right in first_shell_graph.edges_ij:
        left_id = labels[left]
        right_id = labels[right]
        if left_id != right_id and left_id in growth_ids and right_id in growth_ids:
            pairs.add(tuple(sorted((left_id, right_id))))

    adjacency = graph_adjacency(first_shell_graph)
    for point_index, label in enumerate(labels):
        if label >= 0 or not is_m6_growth_candidate(
            point_index,
            local_order=local_order,
            settings=settings,
        ):
            continue
        neighboring_ids = sorted(
            {
                labels[neighbor]
                for neighbor in adjacency[point_index]
                if labels[neighbor] in growth_ids
                and m6_orientation_distance_deg(
                    local_order.lattice_orientation_deg[point_index],
                    components[labels[neighbor]].orientation_deg,
                )
                <= settings.grow_angle_tolerance_deg + 1e-12
            }
        )
        pairs.update(combinations(neighboring_ids, 2))
    return frozenset(pairs)


def _complete_linkage_merge_groups(
    components: tuple[M6OrientationMergedComponent, ...],
    *,
    spatial_pairs: frozenset[tuple[int, int]],
    tolerance_deg: float,
) -> tuple[frozenset[int], ...]:
    clusters = [frozenset((component.ordered_component_id,)) for component in components]
    orientation_sets = {
        component.ordered_component_id: (
            *component.constituent_orientation_deg,
            component.orientation_deg,
        )
        for component in components
    }
    pair_maximum_delta = {
        (left, right): max(
            m6_orientation_distance_deg(left_orientation, right_orientation)
            for left_orientation in orientation_sets[left]
            for right_orientation in orientation_sets[right]
        )
        for left, right in combinations(range(len(components)), 2)
    }
    internal_maximum_delta: dict[frozenset[int], float] = {
        frozenset((component_id,)): max(
            (
                m6_orientation_distance_deg(left, right)
                for left, right in combinations(orientation_sets[component_id], 2)
            ),
            default=0.0,
        )
        for component_id in range(len(components))
    }
    cluster_physical_key = {
        frozenset((component.ordered_component_id,)): (
            _component_physical_key(component),
        )
        for component in components
    }
    cluster_source_key = {
        frozenset((component.ordered_component_id,)): tuple(sorted(component.source_ids))
        for component in components
    }
    contact_cache: dict[frozenset[frozenset[int]], int] = {}
    cross_delta_cache: dict[frozenset[frozenset[int]], float] = {}

    def contact_count(left: frozenset[int], right: frozenset[int]) -> int:
        cache_key = frozenset((left, right))
        if cache_key not in contact_cache:
            contact_cache[cache_key] = sum(
                tuple(sorted((left_id, right_id))) in spatial_pairs
                for left_id in left
                for right_id in right
            )
        return contact_cache[cache_key]

    def cross_maximum_delta(left: frozenset[int], right: frozenset[int]) -> float:
        cache_key = frozenset((left, right))
        if cache_key not in cross_delta_cache:
            cross_delta_cache[cache_key] = max(
                pair_maximum_delta[tuple(sorted((left_id, right_id)))]
                for left_id in left
                for right_id in right
            )
        return cross_delta_cache[cache_key]

    while True:
        candidates: list[
            tuple[
                tuple[
                    float,
                    int,
                    tuple[tuple[int, float, float, float], ...],
                    tuple[str, ...],
                ],
                int,
                int,
            ]
        ] = []
        for left_index, right_index in combinations(range(len(clusters)), 2):
            left = clusters[left_index]
            right = clusters[right_index]
            pair_contact_count = contact_count(left, right)
            if pair_contact_count == 0:
                continue
            combined = left | right
            maximum_delta = max(
                internal_maximum_delta[left],
                internal_maximum_delta[right],
                cross_maximum_delta(left, right),
            )
            if maximum_delta > tolerance_deg + 1e-12:
                continue
            physical_key = tuple(sorted(cluster_physical_key[left] + cluster_physical_key[right]))
            source_key = tuple(
                sorted(cluster_source_key[left] + cluster_source_key[right])
            )
            candidates.append(
                (
                    (maximum_delta, -pair_contact_count, physical_key, source_key),
                    left_index,
                    right_index,
                )
            )
        if not candidates:
            break
        _, left_index, right_index = min(candidates, key=lambda value: value[0])
        left = clusters[left_index]
        right = clusters[right_index]
        combined = left | right
        internal_maximum_delta[combined] = max(
            internal_maximum_delta[left],
            internal_maximum_delta[right],
            cross_maximum_delta(left, right),
        )
        cluster_physical_key[combined] = tuple(
            sorted(cluster_physical_key[left] + cluster_physical_key[right])
        )
        cluster_source_key[combined] = tuple(
            sorted(cluster_source_key[left] + cluster_source_key[right])
        )
        clusters = [
            cluster
            for index, cluster in enumerate(clusters)
            if index not in {left_index, right_index}
        ]
        clusters.append(combined)

    return tuple(sorted(clusters, key=lambda cluster: _cluster_sort_key(cluster, components)))


def _merge_group_draft(
    group: frozenset[int],
    components: tuple[M6OrientationMergedComponent, ...],
) -> _ComponentDraft:
    group_components = tuple(components[index] for index in sorted(group))
    return _ComponentDraft(
        constituents=tuple(
            constituent
            for component in group_components
            for constituent in component.constituents
        ),
        point_indices=tuple(
            sorted(
                point_index
                for component in group_components
                for point_index in component.point_indices
            )
        ),
    )


def _build_merge_state(
    *,
    growth: M6OrientationDomainGrowthState,
    components: tuple[M6OrientationMergedComponent, ...],
    labels: tuple[int, ...],
    merge_iteration_count: int,
    post_merge_growth_iteration_count: int,
    local_order: LocalSixfoldBondOrderField,
) -> M6OrientationDomainMergeState:
    component_types: list[M6SeedPointComponentType] = ["unassigned"] * growth.point_count
    statuses = [
        initial_m6_assignment_status(value)
        for value in local_order.computation_status
    ]
    for component in components:
        for point_index in component.point_indices:
            component_types[point_index] = component.component_type
            statuses[point_index] = "assigned"
    return M6OrientationDomainMergeState(
        source_ids=growth.source_ids,
        point_count=growth.point_count,
        seed_eligible=growth.seed_eligible,
        ordered_component_id=labels,
        component_type=tuple(component_types),
        assignment_status=tuple(statuses),
        edge_truncated_neighborhood=growth.edge_truncated_neighborhood,
        physical_duplicate_qc=growth.physical_duplicate_qc,
        geometry_duplicate_qc=growth.geometry_duplicate_qc,
        components=components,
        growth_iteration_count=(
            growth.growth_iteration_count + post_merge_growth_iteration_count
        ),
        merge_iteration_count=merge_iteration_count,
        post_merge_growth_iteration_count=post_merge_growth_iteration_count,
        settings=growth.settings,
        coordinate_frame=growth.coordinate_frame,
        orientation_reference=growth.orientation_reference,
        spatial_calibration_fingerprint=growth.spatial_calibration_fingerprint,
        registration_fingerprint=growth.registration_fingerprint,
        point_coordinate_fingerprint=growth.point_coordinate_fingerprint,
    )


def _component_physical_key(
    component: M6OrientationMergedComponent,
) -> tuple[int, float, float, float]:
    return (
        -component.molecule_count,
        component.centroid_x_nm,
        component.centroid_y_nm,
        component.orientation_deg,
    )


def _cluster_sort_key(
    cluster: frozenset[int],
    components: tuple[M6OrientationMergedComponent, ...],
) -> tuple[tuple[tuple[int, float, float, float], ...], tuple[str, ...]]:
    return (
        tuple(sorted(_component_physical_key(components[index]) for index in cluster)),
        tuple(
            sorted(
                source_id
                for index in cluster
                for source_id in components[index].source_ids
            )
        ),
    )


def _non_negative_integer(value: object, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{field_name} must be an integer.")
    if value < 0:
        raise ValueError(f"{field_name} must be non-negative.")
    return value


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
