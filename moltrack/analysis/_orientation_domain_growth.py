from __future__ import annotations

from collections.abc import Iterable

from ._orientation_domain_common import (
    component_m6_unit_orientation,
    m6_similarity_threshold,
    point_domain_m6_similarity,
)
from .first_shell_graph import FirstShellGraph
from .local_sixfold_bond_order import LocalSixfoldBondOrderField
from .m6_settings import MolecularM6OrientationAnalysisSettings


def grow_m6_labels_to_fixed_point(
    initial_labels: Iterable[int],
    growth_component_ids: Iterable[int],
    *,
    first_shell_graph: FirstShellGraph,
    local_order: LocalSixfoldBondOrderField,
    settings: MolecularM6OrientationAnalysisSettings,
) -> tuple[tuple[int, ...], int]:
    """Grow an existing component partition using frozen synchronous batches."""

    labels = list(initial_labels)
    if len(labels) != first_shell_graph.point_count:
        raise ValueError("initial_labels must contain one label per graph point.")
    if any(
        not isinstance(label, int) or isinstance(label, bool) or label < -1
        for label in labels
    ):
        raise ValueError("initial_labels must contain integer labels greater than or equal to -1.")
    component_ids = tuple(growth_component_ids)
    if len(set(component_ids)) != len(component_ids):
        raise ValueError("growth_component_ids must be unique.")
    if any(
        not isinstance(component_id, int)
        or isinstance(component_id, bool)
        or component_id < 0
        for component_id in component_ids
    ):
        raise ValueError("growth_component_ids must be non-negative integers.")
    if any(component_id not in labels for component_id in component_ids):
        raise ValueError("Every growth component must have at least one labeled point.")

    component_id_set = frozenset(component_ids)
    adjacency = graph_adjacency(first_shell_graph)
    similarity_threshold = m6_similarity_threshold(
        settings.grow_angle_tolerance_deg
    )
    iteration_count = 0
    while True:
        domain_vectors = {
            component_id: component_m6_unit_orientation(
                tuple(
                    point_index
                    for point_index, label in enumerate(labels)
                    if label == component_id
                ),
                local_order,
            )
            for component_id in component_ids
        }
        proposals: list[tuple[int, int]] = []
        for point_index in range(first_shell_graph.point_count):
            if labels[point_index] >= 0 or not is_m6_growth_candidate(
                point_index,
                local_order=local_order,
                settings=settings,
            ):
                continue
            neighboring_domains = {
                labels[neighbor]
                for neighbor in adjacency[point_index]
                if labels[neighbor] in component_id_set
            }
            scored_domains = sorted(
                (
                    (
                        point_domain_m6_similarity(
                            point_index,
                            domain_vectors[component_id],
                            local_order,
                        ),
                        component_id,
                    )
                    for component_id in neighboring_domains
                ),
                key=lambda value: (-value[0], value[1]),
            )
            if not scored_domains or scored_domains[0][0] + 1e-12 < similarity_threshold:
                continue
            if len(scored_domains) > 1 and (
                scored_domains[0][0] - scored_domains[1][0] + 1e-12
                < settings.domain_conflict_margin
            ):
                continue
            proposals.append((point_index, scored_domains[0][1]))
        if not proposals:
            return tuple(labels), iteration_count
        for point_index, component_id in proposals:
            labels[point_index] = component_id
        iteration_count += 1


def is_m6_growth_candidate(
    point_index: int,
    *,
    local_order: LocalSixfoldBondOrderField,
    settings: MolecularM6OrientationAnalysisSettings,
) -> bool:
    point_q6 = local_order.q6[point_index]
    return (
        local_order.computation_status[point_index] == "valid_order"
        and local_order.orientation_status[point_index] == "defined"
        and point_q6 is not None
        and point_q6 >= settings.q_grow
        and not local_order.physical_duplicate_qc[point_index]
        and not local_order.geometry_duplicate_qc[point_index]
    )


def graph_adjacency(graph: FirstShellGraph) -> tuple[tuple[int, ...], ...]:
    adjacency: list[list[int]] = [[] for _ in range(graph.point_count)]
    for left, right in graph.edges_ij:
        adjacency[left].append(right)
        adjacency[right].append(left)
    return tuple(tuple(neighbors) for neighbors in adjacency)
