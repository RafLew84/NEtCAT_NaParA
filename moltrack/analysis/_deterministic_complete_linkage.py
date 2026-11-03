"""Reusable deterministic complete-linkage clustering for analysis records."""

from __future__ import annotations

import heapq
from collections.abc import Callable, Iterable
from itertools import combinations
from typing import TypeVar


_T = TypeVar("_T")
_StructuralKey = tuple[object, ...]
_ClusterKey = tuple[_StructuralKey, ...]


def deterministic_complete_linkage_clusters(
    values: Iterable[_T],
    *,
    distance: Callable[[_T, _T], float],
    structural_key: Callable[[_T], _StructuralKey],
) -> tuple[tuple[_T, ...], ...]:
    """Cluster values with complete linkage and deterministic tie-breaking."""

    ordered = tuple(sorted(values, key=structural_key))
    active = {
        cluster_id: (value,)
        for cluster_id, value in enumerate(ordered)
    }
    active_keys = {
        cluster_id: (structural_key(value),)
        for cluster_id, value in enumerate(ordered)
    }
    compatible: dict[int, dict[int, float]] = {
        cluster_id: {} for cluster_id in active
    }
    candidates: list[tuple[float, _ClusterKey, int, int]] = []
    for left_id, right_id in combinations(active, 2):
        value = float(distance(active[left_id][0], active[right_id][0]))
        if value > 1.0:
            continue
        compatible[left_id][right_id] = value
        compatible[right_id][left_id] = value
        candidates.append(
            (
                value,
                _merge_keys(
                    active_keys[left_id],
                    active_keys[right_id],
                ),
                left_id,
                right_id,
            )
        )
    heapq.heapify(candidates)

    next_cluster_id = len(active)
    while candidates:
        value, merged_key, left_id, right_id = heapq.heappop(candidates)
        if left_id not in active or right_id not in active:
            continue
        if compatible[left_id].get(right_id) != value:
            continue
        merged = tuple(
            sorted(
                (*active[left_id], *active[right_id]),
                key=structural_key,
            )
        )
        left_neighbors = compatible.pop(left_id)
        right_neighbors = compatible.pop(right_id)
        common_neighbors = (
            set(left_neighbors).intersection(right_neighbors).intersection(
                active
            )
            - {left_id, right_id}
        )
        for neighbor_id in set(left_neighbors).union(right_neighbors):
            if neighbor_id in compatible:
                compatible[neighbor_id].pop(left_id, None)
                compatible[neighbor_id].pop(right_id, None)
        del active[left_id]
        del active[right_id]
        del active_keys[left_id]
        del active_keys[right_id]

        merged_id = next_cluster_id
        next_cluster_id += 1
        active[merged_id] = merged
        active_keys[merged_id] = merged_key
        compatible[merged_id] = {}
        for neighbor_id in common_neighbors:
            neighbor_distance = max(
                left_neighbors[neighbor_id],
                right_neighbors[neighbor_id],
            )
            compatible[merged_id][neighbor_id] = neighbor_distance
            compatible[neighbor_id][merged_id] = neighbor_distance
            heapq.heappush(
                candidates,
                (
                    neighbor_distance,
                    _merge_keys(
                        merged_key,
                        active_keys[neighbor_id],
                    ),
                    merged_id,
                    neighbor_id,
                ),
            )
    return tuple(
        active[key] for key in sorted(active, key=active_keys.__getitem__)
    )


def _merge_keys(
    left: _ClusterKey,
    right: _ClusterKey,
) -> _ClusterKey:
    return tuple(sorted((*left, *right)))
