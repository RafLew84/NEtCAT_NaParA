"""Connected domain instances with pairwise geometry and image-barrier constraints."""

from collections.abc import Callable
from typing import Any

import numpy as np
from numpy.typing import NDArray
from scipy.spatial import cKDTree
from scipy.spatial.distance import cdist

from stmdomains.analysis.domain_settings import DomainSettings
from stmdomains.analysis.domain_raster import rasterize_domains


def _crosses_barrier(a: NDArray[Any], b: NDArray[Any], barrier: NDArray[np.bool_]) -> bool:
    count = max(3, int(np.ceil(np.linalg.norm(a - b) * 3)))
    samples = a + np.linspace(0, 1, count)[:, None] * (b - a)
    xx = np.clip(np.rint(samples[:, 0]).astype(int), 0, barrier.shape[1] - 1)
    yy = np.clip(np.rint(samples[:, 1]).astype(int), 0, barrier.shape[0] - 1)
    return bool(np.any(barrier[yy, xx]))


def segment_domains(
    points: NDArray[np.float64], labels: NDArray[Any], accepted: NDArray[np.bool_],
    features: NDArray[np.float64], spacing: float, barrier: NDArray[np.bool_],
    check: Callable[[], None], *, settings: DomainSettings = DomainSettings(),
) -> tuple[NDArray[np.int32], NDArray[np.int32], dict[str, Any]]:
    pairs = np.asarray(sorted(cKDTree(points).query_pairs(settings.edge_distance_factor * spacing)), int).reshape(-1, 2)
    eligible = accepted[pairs[:, 0]] & accepted[pairs[:, 1]] & (labels[pairs[:, 0]] == labels[pairs[:, 1]])
    candidates = pairs[eligible]
    h = features / np.maximum(np.linalg.norm(features, axis=1, keepdims=True), 1e-12)
    edges = []
    cut = 0
    geometry_cut = 0
    for a, b in candidates:
        check()
        if _crosses_barrier(points[a], points[b], barrier):
            cut += 1
            continue
        distance = float(np.linalg.norm(h[a] - h[b]) / np.sqrt(2))
        if settings.geometry_mode == "off" or distance <= settings.edge_max_hellinger:
            edges.append((distance, int(a), int(b)))
        else:
            geometry_cut += 1
    parents = np.arange(len(points))
    members = {int(i): [int(i)] for i in np.flatnonzero(accepted)}

    def find(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = int(parents[index])
        return index

    rejected = 0
    for _, first, second in sorted(edges):
        check()
        a, b = find(first), find(second)
        if a == b:
            continue
        # Bound temporary distance matrices instead of allocating n×n globally.
        incompatible = False
        for start in range(0, len(members[a]) if settings.geometry_mode != "off" else 0, 32):
            check()
            distance = cdist(h[members[a][start:start + 32]], h[members[b]]) / np.sqrt(2)
            if float(distance.max()) > settings.region_max_hellinger_diameter:
                incompatible = True
                break
        if incompatible:
            rejected += 1
            continue
        if b < a:
            a, b = b, a
        parents[b] = a
        members[a].extend(members.pop(b))
    groups = [group for group in members.values() if len(group) >= settings.minimum_domain_size]
    groups.sort(key=lambda group: (float(points[group, 1].mean()), float(points[group, 0].mean())))
    ids = np.zeros(len(points), np.int32)
    for number, group in enumerate(groups, 1):
        ids[group] = number
    final, regions, reconciliation = rasterize_domains(points, ids, spacing, barrier, check, settings)
    return final, regions, {"candidate_edges": len(pairs), "eligible_edges": len(candidates),
                   "barrier_cut_edges": cut, "geometry_cut_edges": geometry_cut,
                   "region_diameter_rejected_merges": rejected, **reconciliation}
