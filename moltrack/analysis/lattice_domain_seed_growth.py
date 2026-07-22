"""Bridge-resistant seed construction and synchronous multisymmetry growth."""

from __future__ import annotations

from dataclasses import dataclass
from math import atan2, cos, degrees, pi, sin
from typing import Literal

from ._first_shell_graph_fingerprint import first_shell_graph_fingerprint
from .first_shell_graph import FirstShellGraph
from .lattice_domain_edge_models import LatticeDomainEdgeCompatibilityField
from .lattice_domain_seed_growth_models import (
    LatticeDomainBoundaryReason,
    LatticeDomainPointRole,
    LatticeDomainSeedComponent,
    LatticeDomainSeedGrowthResult,
    LatticeDomainSeedGrowthSettings,
    LatticeDomainSeedState,
    LatticeDomainSeedSupportStability,
    LatticeDomainSymmetry,
    lattice_domain_seed_growth_settings_fingerprint,
)
from .local_multisymmetry_bond_order import LocalMultiSymmetryBondOrderField
from .local_symmetry_evidence_models import (
    LocalSymmetryEvidenceField,
)


_PERIOD_DEG = 60.0
_Channel = Literal["m3", "m6"]


@dataclass(frozen=True)
class _SymmetryPolicy:
    model_score_field: Literal[
        "trifold_model_score",
        "sixfold_model_score",
        "mixed_model_score",
    ]
    channels: tuple[_Channel, ...]
    core_edge_decision: Literal[
        "compatible_trifold",
        "compatible_sixfold",
        "compatible_mixed",
    ]


_SYMMETRY_POLICIES: dict[LatticeDomainSymmetry, _SymmetryPolicy] = {
    "trifold": _SymmetryPolicy(
        model_score_field="trifold_model_score",
        channels=("m3",),
        core_edge_decision="compatible_trifold",
    ),
    "sixfold": _SymmetryPolicy(
        model_score_field="sixfold_model_score",
        channels=("m6",),
        core_edge_decision="compatible_sixfold",
    ),
    "mixed": _SymmetryPolicy(
        model_score_field="mixed_model_score",
        channels=("m3", "m6"),
        core_edge_decision="compatible_mixed",
    ),
}


@dataclass(frozen=True)
class _Cluster:
    symmetry_model: LatticeDomainSymmetry
    core_indices: frozenset[int]


@dataclass(frozen=True)
class _Claim:
    point_index: int
    component_id: int
    score: float


@dataclass(frozen=True)
class _GrowthPartition:
    point_role: tuple[LatticeDomainPointRole, ...]
    component_id: tuple[int, ...]
    boundary_reason: tuple[LatticeDomainBoundaryReason | None, ...]
    halo_by_component: tuple[frozenset[int], ...]
    growth_iteration_count: int


def build_lattice_domain_seed_growth(
    graph: FirstShellGraph,
    local_order: LocalMultiSymmetryBondOrderField,
    local_evidence: LocalSymmetryEvidenceField,
    edge_compatibility: LatticeDomainEdgeCompatibilityField,
    *,
    settings: LatticeDomainSeedGrowthSettings | None = None,
) -> LatticeDomainSeedGrowthResult:
    """Build strict cores, merge them by complete linkage, then grow halo batches."""

    if settings is None:
        settings = LatticeDomainSeedGrowthSettings()
    if not isinstance(settings, LatticeDomainSeedGrowthSettings):
        raise TypeError("settings must be LatticeDomainSeedGrowthSettings.")
    graph_fingerprint = _validate_inputs(
        graph,
        local_order,
        local_evidence,
        edge_compatibility,
    )
    edge_lookup = {
        edge: edge_index for edge_index, edge in enumerate(edge_compatibility.edges_ij)
    }
    adjacency = _edge_adjacency(graph)
    clusters = _build_core_clusters(
        graph,
        local_order,
        local_evidence,
        edge_compatibility,
        settings=settings,
    )
    clusters = tuple(sorted(clusters, key=lambda value: _cluster_sort_key(value, graph)))
    partitions = {
        offset: _build_growth_partition(
            graph,
            local_order,
            local_evidence,
            edge_compatibility,
            clusters=clusters,
            min_seed_size=max(1, settings.min_seed_size + offset),
            adjacency=adjacency,
            edge_lookup=edge_lookup,
            settings=settings,
        )
        for offset in (-1, 0, 1)
    }
    baseline = partitions[0]
    seed_states = tuple(
        _seed_state(
            len(cluster.core_indices),
            min_seed_size=settings.min_seed_size,
            min_ordered_component_size=settings.min_ordered_component_size,
        )
        for cluster in clusters
    )
    components = tuple(
        _materialize_component(
            component_id,
            cluster,
            seed_states[component_id],
            set(baseline.halo_by_component[component_id]),
            graph=graph,
            local_order=local_order,
        )
        for component_id, cluster in enumerate(clusters)
    )
    stability = _seed_support_stability(
        components,
        partitions=partitions,
        graph=graph,
        settings=settings,
    )
    return LatticeDomainSeedGrowthResult(
        source_ids=graph.point_ids,
        point_count=graph.point_count,
        point_role=baseline.point_role,
        component_id=baseline.component_id,
        boundary_reason=baseline.boundary_reason,
        components=components,
        seed_support_stability=stability,
        growth_iteration_count=baseline.growth_iteration_count,
        settings=settings,
        first_shell_graph_fingerprint=graph_fingerprint,
        local_order_analysis_fingerprint=(
            local_order.provenance.analysis_settings_fingerprint
        ),
        local_symmetry_evidence_settings_fingerprint=(
            local_evidence.settings_fingerprint
        ),
        local_symmetry_bond_evidence_fingerprint=(
            local_evidence.bond_evidence_fingerprint
        ),
        edge_compatibility_settings_fingerprint=(
            edge_compatibility.settings_fingerprint
        ),
        settings_fingerprint=lattice_domain_seed_growth_settings_fingerprint(settings),
    )


def _build_core_clusters(
    graph: FirstShellGraph,
    local_order: LocalMultiSymmetryBondOrderField,
    local_evidence: LocalSymmetryEvidenceField,
    edge_compatibility: LatticeDomainEdgeCompatibilityField,
    *,
    settings: LatticeDomainSeedGrowthSettings,
) -> tuple[_Cluster, ...]:
    eligible = {
        index
        for index in range(graph.point_count)
        if _core_point_symmetry(
            index,
            local_order=local_order,
            local_evidence=local_evidence,
            settings=settings,
        )
        is not None
    }
    core_merge_edges = tuple(
        edge
        for edge_index, edge in enumerate(edge_compatibility.edges_ij)
        if _is_core_merge_edge(
            edge_index,
            edge,
            local_evidence=local_evidence,
            edge_compatibility=edge_compatibility,
        )
    )
    graph_edge_set = frozenset(edge_compatibility.edges_ij)
    core_merge_edge_set = frozenset(core_merge_edges)
    core_adjacency: dict[int, set[int]] = {index: set() for index in eligible}
    for left, right in core_merge_edges:
        if left in eligible and right in eligible:
            core_adjacency[left].add(right)
            core_adjacency[right].add(left)

    clusters: list[_Cluster] = []
    remaining = set(eligible)
    while remaining:
        anchor = min(
            remaining,
            key=lambda index: _core_point_sort_key(
                index,
                graph=graph,
                local_order=local_order,
                local_evidence=local_evidence,
            ),
        )
        symmetry_model = _required_core_symmetry(
            anchor,
            local_order=local_order,
            local_evidence=local_evidence,
            settings=settings,
        )
        core_points = {anchor}
        remaining.remove(anchor)
        while True:
            candidates = {
                neighbor
                for point_index in core_points
                for neighbor in core_adjacency[point_index]
                if neighbor in remaining
            }
            selected: set[int] = set()
            for candidate in sorted(
                candidates,
                key=lambda index: _core_point_sort_key(
                    index,
                    graph=graph,
                    local_order=local_order,
                    local_evidence=local_evidence,
                ),
            ):
                if _core_candidate_can_join(
                    candidate,
                    core_points | selected,
                    symmetry_model,
                    local_order=local_order,
                    graph_edge_set=graph_edge_set,
                    core_merge_edge_set=core_merge_edge_set,
                    settings=settings,
                ):
                    selected.add(candidate)
            if not selected:
                break
            core_points.update(selected)
            remaining.difference_update(selected)
        clusters.append(
            _Cluster(
                symmetry_model=symmetry_model,
                core_indices=frozenset(core_points),
            )
        )
    return tuple(clusters)


def _core_candidate_can_join(
    candidate: int,
    core_points: set[int],
    symmetry_model: LatticeDomainSymmetry,
    *,
    local_order: LocalMultiSymmetryBondOrderField,
    graph_edge_set: frozenset[tuple[int, int]],
    core_merge_edge_set: frozenset[tuple[int, int]],
    settings: LatticeDomainSeedGrowthSettings,
) -> bool:
    cross_edges = {
        _canonical_edge(candidate, point_index)
        for point_index in core_points
        if _canonical_edge(candidate, point_index) in graph_edge_set
    }
    if not cross_edges or not cross_edges.issubset(core_merge_edge_set):
        return False
    return _within_orientation_spread(
        frozenset(core_points | {candidate}),
        symmetry_model,
        local_order=local_order,
        maximum=settings.seed_max_orientation_spread_deg,
    )


def _core_point_sort_key(
    point_index: int,
    *,
    graph: FirstShellGraph,
    local_order: LocalMultiSymmetryBondOrderField,
    local_evidence: LocalSymmetryEvidenceField,
) -> tuple[float, float, float, str]:
    symmetry_model = local_evidence.best_model[point_index]
    if symmetry_model not in _SYMMETRY_POLICIES:
        raise ValueError("Only ordered core points have a core sort key.")
    classification_confidence = local_evidence.classification_confidence[point_index]
    return (
        -_model_score(point_index, symmetry_model, local_evidence),
        -_order_amplitude(point_index, symmetry_model, local_order),
        -(0.0 if classification_confidence is None else classification_confidence),
        graph.point_ids[point_index],
    )


def _is_core_merge_edge(
    edge_index: int,
    edge: tuple[int, int],
    *,
    local_evidence: LocalSymmetryEvidenceField,
    edge_compatibility: LatticeDomainEdgeCompatibilityField,
) -> bool:
    left, right = edge
    model = local_evidence.best_model[left]
    policy = _SYMMETRY_POLICIES.get(model)
    return (
        policy is not None
        and model == local_evidence.best_model[right]
        and edge_compatibility.core_connectivity_eligible[edge_index]
        and edge_compatibility.decision[edge_index] == policy.core_edge_decision
    )


def _build_growth_partition(
    graph: FirstShellGraph,
    local_order: LocalMultiSymmetryBondOrderField,
    local_evidence: LocalSymmetryEvidenceField,
    edge_compatibility: LatticeDomainEdgeCompatibilityField,
    *,
    clusters: tuple[_Cluster, ...],
    min_seed_size: int,
    adjacency: tuple[tuple[int, ...], ...],
    edge_lookup: dict[tuple[int, int], int],
    settings: LatticeDomainSeedGrowthSettings,
) -> _GrowthPartition:
    roles: list[LatticeDomainPointRole] = ["unassigned"] * graph.point_count
    component_ids = [-1] * graph.point_count
    boundary_reasons: list[LatticeDomainBoundaryReason | None] = [None] * graph.point_count
    halo_by_component: list[set[int]] = [set() for _ in clusters]
    seed_states = tuple(
        _seed_state(
            len(cluster.core_indices),
            min_seed_size=min_seed_size,
            min_ordered_component_size=settings.min_ordered_component_size,
        )
        for cluster in clusters
    )
    for component_id, cluster in enumerate(clusters):
        for point_index in cluster.core_indices:
            roles[point_index] = "core"
            component_ids[point_index] = component_id
    growth_iterations = _grow_halo_to_fixed_point(
        graph,
        local_order,
        local_evidence,
        edge_compatibility,
        clusters=clusters,
        seed_states=seed_states,
        halo_by_component=halo_by_component,
        roles=roles,
        component_ids=component_ids,
        boundary_reasons=boundary_reasons,
        adjacency=adjacency,
        edge_lookup=edge_lookup,
        settings=settings,
    )
    _mark_explicit_boundary_points(
        edge_compatibility,
        roles=roles,
        component_ids=component_ids,
        boundary_reasons=boundary_reasons,
    )
    return _GrowthPartition(
        point_role=tuple(roles),
        component_id=tuple(component_ids),
        boundary_reason=tuple(boundary_reasons),
        halo_by_component=tuple(frozenset(values) for values in halo_by_component),
        growth_iteration_count=growth_iterations,
    )


def _grow_halo_to_fixed_point(
    graph: FirstShellGraph,
    local_order: LocalMultiSymmetryBondOrderField,
    local_evidence: LocalSymmetryEvidenceField,
    edge_compatibility: LatticeDomainEdgeCompatibilityField,
    *,
    clusters: tuple[_Cluster, ...],
    seed_states: tuple[LatticeDomainSeedState, ...],
    halo_by_component: list[set[int]],
    roles: list[LatticeDomainPointRole],
    component_ids: list[int],
    boundary_reasons: list[LatticeDomainBoundaryReason | None],
    adjacency: tuple[tuple[int, ...], ...],
    edge_lookup: dict[tuple[int, int], int],
    settings: LatticeDomainSeedGrowthSettings,
) -> int:
    growth_iterations = 0
    while True:
        claims_by_point: dict[int, list[_Claim]] = {}
        for point_index in range(graph.point_count):
            if roles[point_index] != "unassigned":
                continue
            for component_id, cluster in enumerate(clusters):
                if seed_states[component_id] != "validated_seed":
                    continue
                assigned_points = cluster.core_indices | frozenset(
                    halo_by_component[component_id]
                )
                claim = _candidate_claim(
                    point_index,
                    component_id,
                    cluster.symmetry_model,
                    assigned_points=assigned_points,
                    core_points=cluster.core_indices,
                    local_order=local_order,
                    local_evidence=local_evidence,
                    edge_compatibility=edge_compatibility,
                    adjacency=adjacency,
                    edge_lookup=edge_lookup,
                    settings=settings,
                )
                if claim is not None:
                    claims_by_point.setdefault(point_index, []).append(claim)

        accepted_by_component: dict[int, list[int]] = {}
        for point_index in sorted(claims_by_point, key=lambda index: graph.point_ids[index]):
            claims = sorted(
                claims_by_point[point_index],
                key=lambda claim: (
                    -claim.score,
                    _component_claim_key(claim.component_id, clusters, graph),
                ),
            )
            if len(claims) > 1 and claims[0].score - claims[1].score < settings.conflict_margin:
                roles[point_index] = "boundary"
                boundary_reasons[point_index] = "competing_domain_claim"
                continue
            accepted_by_component.setdefault(claims[0].component_id, []).append(point_index)

        accepted_any = False
        for component_id in sorted(accepted_by_component):
            raw_candidates = tuple(
                sorted(
                    accepted_by_component[component_id],
                    key=lambda index: graph.point_ids[index],
                )
            )
            conflict_points = _batch_conflict_points(
                raw_candidates,
                edge_compatibility=edge_compatibility,
                edge_lookup=edge_lookup,
            )
            for point_index in conflict_points:
                roles[point_index] = "boundary"
                boundary_reasons[point_index] = "incompatible_domain_edge"
            candidates = tuple(
                point_index
                for point_index in raw_candidates
                if point_index not in conflict_points
            )
            if not candidates:
                continue
            cluster = clusters[component_id]
            combined = (
                cluster.core_indices
                | frozenset(halo_by_component[component_id])
                | frozenset(candidates)
            )
            if not _within_orientation_spread(
                combined,
                cluster.symmetry_model,
                local_order=local_order,
                maximum=settings.grow_max_orientation_spread_deg,
            ):
                for point_index in candidates:
                    roles[point_index] = "boundary"
                    boundary_reasons[point_index] = "batch_orientation_spread"
                continue
            for point_index in candidates:
                roles[point_index] = "halo"
                component_ids[point_index] = component_id
                halo_by_component[component_id].add(point_index)
            accepted_any = accepted_any or bool(candidates)
        if not accepted_any:
            return growth_iterations
        growth_iterations += 1


def _batch_conflict_points(
    candidates: tuple[int, ...],
    *,
    edge_compatibility: LatticeDomainEdgeCompatibilityField,
    edge_lookup: dict[tuple[int, int], int],
) -> frozenset[int]:
    conflict_points: set[int] = set()
    for position, left in enumerate(candidates):
        for right in candidates[position + 1 :]:
            edge_index = edge_lookup.get(_canonical_edge(left, right))
            if edge_index is not None and edge_compatibility.decision[edge_index] in {
                "conflict_boundary",
                "boundary_unassigned",
            }:
                conflict_points.update((left, right))
    return frozenset(conflict_points)


def _candidate_claim(
    point_index: int,
    component_id: int,
    symmetry_model: LatticeDomainSymmetry,
    *,
    assigned_points: frozenset[int],
    core_points: frozenset[int],
    local_order: LocalMultiSymmetryBondOrderField,
    local_evidence: LocalSymmetryEvidenceField,
    edge_compatibility: LatticeDomainEdgeCompatibilityField,
    adjacency: tuple[tuple[int, ...], ...],
    edge_lookup: dict[tuple[int, int], int],
    settings: LatticeDomainSeedGrowthSettings,
) -> _Claim | None:
    if not _halo_point_is_eligible(
        point_index,
        symmetry_model,
        local_order=local_order,
        local_evidence=local_evidence,
        settings=settings,
    ):
        return None
    domain_neighbor_edges = tuple(
        edge_lookup[_canonical_edge(point_index, neighbor)]
        for neighbor in adjacency[point_index]
        if neighbor in assigned_points
    )
    if not any(
        _edge_index_supports_domain(
            edge_index,
            symmetry_model,
            edge_compatibility=edge_compatibility,
        )
        for edge_index in domain_neighbor_edges
    ):
        return None
    if any(
        edge_compatibility.decision[edge_index]
        in {"conflict_boundary", "boundary_unassigned"}
        for edge_index in domain_neighbor_edges
    ):
        return None
    if not _within_orientation_spread(
        assigned_points | frozenset((point_index,)),
        symmetry_model,
        local_order=local_order,
        maximum=settings.grow_max_orientation_spread_deg,
    ):
        return None
    orientation_fit = _orientation_fit_to_core(
        point_index,
        core_points,
        symmetry_model,
        local_order=local_order,
        tolerance=settings.grow_max_orientation_spread_deg,
    )
    evidence_strength = min(
        _model_score(point_index, symmetry_model, local_evidence),
        _order_amplitude(point_index, symmetry_model, local_order),
    )
    return _Claim(
        point_index=point_index,
        component_id=component_id,
        score=0.5 * orientation_fit + 0.5 * evidence_strength,
    )


def _core_point_symmetry(
    point_index: int,
    *,
    local_order: LocalMultiSymmetryBondOrderField,
    local_evidence: LocalSymmetryEvidenceField,
    settings: LatticeDomainSeedGrowthSettings,
) -> LatticeDomainSymmetry | None:
    model = local_evidence.best_model[point_index]
    if model not in _SYMMETRY_POLICIES:
        return None
    symmetry_model = model
    if (
        local_order.computation_status[point_index] != "valid_order"
        or local_order.neighbor_count[point_index] < settings.min_neighbors_for_seed
        or local_order.edge_truncated_neighborhood[point_index]
        or local_evidence.edge_truncated_neighborhood[point_index]
        or local_order.physical_duplicate_qc[point_index]
        or local_order.geometry_duplicate_qc[point_index]
    ):
        return None
    if _model_score(point_index, symmetry_model, local_evidence) < settings.seed_min_model_score:
        return None
    if (
        _order_amplitude(point_index, symmetry_model, local_order)
        < settings.core_min_order_amplitude
    ):
        return None
    if not _orientation_channels_defined(point_index, symmetry_model, local_order):
        return None
    confidence = local_evidence.classification_confidence[point_index]
    if (
        confidence is None
        or confidence < settings.minimum_classification_confidence
        or _orientation_confidence(point_index, symmetry_model, local_order)
        < settings.minimum_orientation_confidence
    ):
        return None
    return symmetry_model


def _required_core_symmetry(
    point_index: int,
    *,
    local_order: LocalMultiSymmetryBondOrderField,
    local_evidence: LocalSymmetryEvidenceField,
    settings: LatticeDomainSeedGrowthSettings,
) -> LatticeDomainSymmetry:
    result = _core_point_symmetry(
        point_index,
        local_order=local_order,
        local_evidence=local_evidence,
        settings=settings,
    )
    assert result is not None
    return result


def _halo_point_is_eligible(
    point_index: int,
    symmetry_model: LatticeDomainSymmetry,
    *,
    local_order: LocalMultiSymmetryBondOrderField,
    local_evidence: LocalSymmetryEvidenceField,
    settings: LatticeDomainSeedGrowthSettings,
) -> bool:
    if (
        local_order.computation_status[point_index] != "valid_order"
        or local_order.physical_duplicate_qc[point_index]
        or local_order.geometry_duplicate_qc[point_index]
        or not _orientation_channels_defined(point_index, symmetry_model, local_order)
    ):
        return False
    return (
        _model_score(point_index, symmetry_model, local_evidence)
        >= settings.halo_min_model_score
        and _order_amplitude(point_index, symmetry_model, local_order)
        >= settings.halo_min_order_amplitude
    )


def _edge_index_supports_domain(
    edge_index: int,
    symmetry_model: LatticeDomainSymmetry,
    *,
    edge_compatibility: LatticeDomainEdgeCompatibilityField,
) -> bool:
    if not edge_compatibility.retained_for_domain_growth[edge_index]:
        return False
    decision = edge_compatibility.decision[edge_index]
    policy = _SYMMETRY_POLICIES[symmetry_model]
    if decision == policy.core_edge_decision:
        return True
    if decision != "conditional_halo_edge":
        return False
    compatible_channels = edge_compatibility.compatible_channels[edge_index]
    return all(channel in compatible_channels for channel in policy.channels)


def _mark_explicit_boundary_points(
    edge_compatibility: LatticeDomainEdgeCompatibilityField,
    *,
    roles: list[LatticeDomainPointRole],
    component_ids: list[int],
    boundary_reasons: list[LatticeDomainBoundaryReason | None],
) -> None:
    for edge, decision in zip(edge_compatibility.edges_ij, edge_compatibility.decision):
        if decision not in {"conflict_boundary", "boundary_unassigned"}:
            continue
        left, right = edge
        for point_index, other_index in ((left, right), (right, left)):
            if roles[point_index] == "unassigned" and component_ids[other_index] >= 0:
                roles[point_index] = "boundary"
                boundary_reasons[point_index] = "incompatible_domain_edge"


def _materialize_component(
    component_id: int,
    cluster: _Cluster,
    seed_state: LatticeDomainSeedState,
    halo_indices: set[int],
    *,
    graph: FirstShellGraph,
    local_order: LocalMultiSymmetryBondOrderField,
) -> LatticeDomainSeedComponent:
    core = tuple(sorted(cluster.core_indices))
    halo = tuple(sorted(halo_indices))
    assigned = frozenset(core + halo)
    channels = _SYMMETRY_POLICIES[cluster.symmetry_model].channels
    theta3 = (
        _channel_prototype(core, local_order.theta3_lattice_deg)
        if "m3" in channels
        else None
    )
    theta6 = (
        _channel_prototype(core, local_order.theta6_deg)
        if "m6" in channels
        else None
    )
    return LatticeDomainSeedComponent(
        component_id=component_id,
        symmetry_model=cluster.symmetry_model,
        seed_state=seed_state,
        core_point_indices=core,
        core_source_ids=tuple(graph.point_ids[index] for index in core),
        halo_point_indices=halo,
        halo_source_ids=tuple(graph.point_ids[index] for index in halo),
        core_theta3_deg=theta3,
        core_theta6_deg=theta6,
        core_theta3_spread_deg=(
            _channel_spread(cluster.core_indices, local_order.theta3_lattice_deg)
            if "m3" in channels
            else None
        ),
        core_theta6_spread_deg=(
            _channel_spread(cluster.core_indices, local_order.theta6_deg)
            if "m6" in channels
            else None
        ),
        assigned_theta3_spread_deg=(
            _channel_spread(assigned, local_order.theta3_lattice_deg)
            if "m3" in channels
            else None
        ),
        assigned_theta6_spread_deg=(
            _channel_spread(assigned, local_order.theta6_deg)
            if "m6" in channels
            else None
        ),
    )


def _seed_support_stability(
    components: tuple[LatticeDomainSeedComponent, ...],
    *,
    partitions: dict[int, _GrowthPartition],
    graph: FirstShellGraph,
    settings: LatticeDomainSeedGrowthSettings,
) -> tuple[LatticeDomainSeedSupportStability, ...]:
    entries: list[LatticeDomainSeedSupportStability] = []
    for offset in (-1, 0, 1):
        threshold = max(1, settings.min_seed_size + offset)
        partition = partitions[offset]
        component_ids = tuple(
            component.component_id
            for component in components
            if component.seed_support_count >= threshold
        )
        entries.append(
            LatticeDomainSeedSupportStability(
                threshold_offset=offset,
                min_seed_size=threshold,
                validated_component_ids=component_ids,
                validated_core_point_count=sum(
                    components[component_id].core_size for component_id in component_ids
                ),
                halo_source_ids=tuple(
                    sorted(
                        graph.point_ids[index]
                        for index, role in enumerate(partition.point_role)
                        if role == "halo"
                    )
                ),
                boundary_source_ids=tuple(
                    sorted(
                        graph.point_ids[index]
                        for index, role in enumerate(partition.point_role)
                        if role == "boundary"
                    )
                ),
                growth_iteration_count=partition.growth_iteration_count,
            )
        )
    return tuple(entries)


def _seed_state(
    core_size: int,
    *,
    min_seed_size: int,
    min_ordered_component_size: int,
) -> LatticeDomainSeedState:
    if core_size >= min_seed_size:
        return "validated_seed"
    if core_size >= min_ordered_component_size:
        return "small_ordered_island"
    return "proto_seed"


def _model_score(
    point_index: int,
    symmetry_model: LatticeDomainSymmetry,
    local_evidence: LocalSymmetryEvidenceField,
) -> float:
    values = getattr(
        local_evidence,
        _SYMMETRY_POLICIES[symmetry_model].model_score_field,
    )
    value = values[point_index]
    return 0.0 if value is None else value


def _order_amplitude(
    point_index: int,
    symmetry_model: LatticeDomainSymmetry,
    local_order: LocalMultiSymmetryBondOrderField,
) -> float:
    amplitudes = tuple(
        _channel_order_amplitude(point_index, channel, local_order)
        for channel in _SYMMETRY_POLICIES[symmetry_model].channels
    )
    return min(amplitudes, default=0.0)


def _orientation_channels_defined(
    point_index: int,
    symmetry_model: LatticeDomainSymmetry,
    local_order: LocalMultiSymmetryBondOrderField,
) -> bool:
    return all(
        _channel_angles(channel, local_order)[point_index] is not None
        for channel in _SYMMETRY_POLICIES[symmetry_model].channels
    )


def _orientation_confidence(
    point_index: int,
    symmetry_model: LatticeDomainSymmetry,
    local_order: LocalMultiSymmetryBondOrderField,
) -> float:
    confidences = [
        _channel_orientation_confidence(point_index, channel, local_order)
        for channel in _SYMMETRY_POLICIES[symmetry_model].channels
    ]
    return min(confidences, default=0.0)


def _channel_order_amplitude(
    point_index: int,
    channel: _Channel,
    local_order: LocalMultiSymmetryBondOrderField,
) -> float:
    values = local_order.q3 if channel == "m3" else local_order.q6
    value = values[point_index]
    return 0.0 if value is None else value


def _channel_angles(
    channel: _Channel,
    local_order: LocalMultiSymmetryBondOrderField,
) -> tuple[float | None, ...]:
    return (
        local_order.theta3_lattice_deg
        if channel == "m3"
        else local_order.theta6_deg
    )


def _channel_orientation_confidence(
    point_index: int,
    channel: _Channel,
    local_order: LocalMultiSymmetryBondOrderField,
) -> float:
    values = (
        local_order.m3_orientation_confidence
        if channel == "m3"
        else local_order.m6_orientation_confidence
    )
    value = values[point_index]
    return 0.0 if value is None else value


def _within_orientation_spread(
    point_indices: frozenset[int],
    symmetry_model: LatticeDomainSymmetry,
    *,
    local_order: LocalMultiSymmetryBondOrderField,
    maximum: float,
) -> bool:
    return all(
        _channel_spread(point_indices, _channel_angles(channel, local_order))
        <= maximum
        for channel in _SYMMETRY_POLICIES[symmetry_model].channels
    )


def _channel_spread(
    point_indices: frozenset[int] | tuple[int, ...],
    values: tuple[float | None, ...],
) -> float:
    angles = tuple(values[index] for index in point_indices)
    if any(value is None for value in angles):
        return float("inf")
    normalized = tuple(
        sorted(float(value) % _PERIOD_DEG for value in angles if value is not None)
    )
    if len(normalized) < 2:
        return 0.0
    circular_gaps = tuple(
        right - left for left, right in zip(normalized, normalized[1:])
    ) + (_PERIOD_DEG - normalized[-1] + normalized[0],)
    return _PERIOD_DEG - max(circular_gaps)


def _channel_prototype(
    point_indices: tuple[int, ...],
    values: tuple[float | None, ...],
) -> float:
    angles = tuple(values[index] for index in point_indices)
    if any(value is None for value in angles):
        raise ValueError("A core orientation channel cannot contain missing angles.")
    phases = tuple(float(value) * 2.0 * pi / _PERIOD_DEG for value in angles if value is not None)
    x = sum(cos(value) for value in phases)
    y = sum(sin(value) for value in phases)
    if abs(x) < 1e-12 and abs(y) < 1e-12:
        return min(float(value) % _PERIOD_DEG for value in angles if value is not None)
    return degrees(atan2(y, x)) * _PERIOD_DEG / 360.0 % _PERIOD_DEG


def _orientation_fit_to_core(
    point_index: int,
    core_points: frozenset[int],
    symmetry_model: LatticeDomainSymmetry,
    *,
    local_order: LocalMultiSymmetryBondOrderField,
    tolerance: float,
) -> float:
    distances = [
        _distance_to_prototype(
            point_index,
            core_points,
            _channel_angles(channel, local_order),
        )
        for channel in _SYMMETRY_POLICIES[symmetry_model].channels
    ]
    maximum_distance = max(distances, default=0.0)
    if tolerance == 0.0:
        return 1.0 if maximum_distance == 0.0 else 0.0
    return max(0.0, 1.0 - maximum_distance / tolerance)


def _distance_to_prototype(
    point_index: int,
    core_points: frozenset[int],
    values: tuple[float | None, ...],
) -> float:
    value = values[point_index]
    if value is None:
        return float("inf")
    prototype = _channel_prototype(tuple(sorted(core_points)), values)
    return _periodic_distance(value, prototype)


def _periodic_distance(first: float, second: float) -> float:
    difference = abs((first % _PERIOD_DEG) - (second % _PERIOD_DEG))
    return min(difference, _PERIOD_DEG - difference)


def _edge_adjacency(graph: FirstShellGraph) -> tuple[tuple[int, ...], ...]:
    adjacency = [set() for _ in range(graph.point_count)]
    for left, right in graph.edges_ij:
        adjacency[left].add(right)
        adjacency[right].add(left)
    return tuple(tuple(sorted(values)) for values in adjacency)


def _cluster_sort_key(cluster: _Cluster, graph: FirstShellGraph) -> tuple[object, ...]:
    return (
        cluster.symmetry_model,
        -len(cluster.core_indices),
        tuple(sorted(graph.point_ids[index] for index in cluster.core_indices)),
    )


def _component_claim_key(
    component_id: int,
    clusters: tuple[_Cluster, ...],
    graph: FirstShellGraph,
) -> tuple[object, ...]:
    return _cluster_sort_key(clusters[component_id], graph)


def _canonical_edge(first: int, second: int) -> tuple[int, int]:
    return (first, second) if first < second else (second, first)


def _validate_inputs(
    graph: FirstShellGraph,
    local_order: LocalMultiSymmetryBondOrderField,
    local_evidence: LocalSymmetryEvidenceField,
    edge_compatibility: LatticeDomainEdgeCompatibilityField,
) -> str:
    if not isinstance(graph, FirstShellGraph):
        raise TypeError("graph must be a FirstShellGraph.")
    if not isinstance(local_order, LocalMultiSymmetryBondOrderField):
        raise TypeError("local_order must be a LocalMultiSymmetryBondOrderField.")
    if not isinstance(local_evidence, LocalSymmetryEvidenceField):
        raise TypeError("local_evidence must be a LocalSymmetryEvidenceField.")
    if not isinstance(edge_compatibility, LatticeDomainEdgeCompatibilityField):
        raise TypeError("edge_compatibility must be a LatticeDomainEdgeCompatibilityField.")
    graph_fingerprint = first_shell_graph_fingerprint(graph)
    if (
        local_order.source_ids != graph.point_ids
        or local_evidence.source_ids != graph.point_ids
        or edge_compatibility.source_ids != graph.point_ids
        or edge_compatibility.edges_ij != graph.edges_ij
    ):
        raise ValueError("Lattice-domain seed/growth inputs must preserve graph order.")
    if (
        local_order.provenance.first_shell_graph_fingerprint != graph_fingerprint
        or local_evidence.first_shell_graph_fingerprint != graph_fingerprint
        or edge_compatibility.first_shell_graph_fingerprint != graph_fingerprint
        or local_evidence.local_order_analysis_fingerprint
        != local_order.provenance.analysis_settings_fingerprint
        or edge_compatibility.local_order_analysis_fingerprint
        != local_order.provenance.analysis_settings_fingerprint
        or edge_compatibility.local_symmetry_evidence_settings_fingerprint
        != local_evidence.settings_fingerprint
        or edge_compatibility.local_symmetry_bond_evidence_fingerprint
        != local_evidence.bond_evidence_fingerprint
    ):
        raise ValueError("Lattice-domain seed/growth inputs have incompatible provenance.")
    return graph_fingerprint
