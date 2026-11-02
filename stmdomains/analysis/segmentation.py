"""Connected domain instances with pairwise geometry and image-barrier constraints."""

from collections.abc import Callable
from typing import Any

import numpy as np
from numpy.typing import NDArray
from scipy import ndimage as ndi
from scipy.spatial import cKDTree
from scipy.spatial.distance import cdist


def _crosses_barrier(a: NDArray[Any], b: NDArray[Any], barrier: NDArray[np.bool_]) -> bool:
    count = max(3, int(np.ceil(np.linalg.norm(a - b) * 3)))
    samples = a + np.linspace(0, 1, count)[:, None] * (b - a)
    xx = np.clip(np.rint(samples[:, 0]).astype(int), 0, barrier.shape[1] - 1)
    yy = np.clip(np.rint(samples[:, 1]).astype(int), 0, barrier.shape[0] - 1)
    return bool(np.any(barrier[yy, xx]))


def segment_domains(
    points: NDArray[np.float64], labels: NDArray[Any], accepted: NDArray[np.bool_],
    features: NDArray[np.float64], spacing: float, barrier: NDArray[np.bool_],
    check: Callable[[], None],
) -> tuple[NDArray[np.int32], NDArray[np.int32], dict[str, Any]]:
    pairs = np.asarray(sorted(cKDTree(points).query_pairs(1.5 * spacing)), int).reshape(-1, 2)
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
        if distance <= .20:
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
        for start in range(0, len(members[a]), 32):
            check()
            distance = cdist(h[members[a][start:start + 32]], h[members[b]]) / np.sqrt(2)
            if float(distance.max()) > .50:
                incompatible = True
                break
        if incompatible:
            rejected += 1
            continue
        if b < a:
            a, b = b, a
        parents[b] = a
        members[a].extend(members.pop(b))
    groups = [group for group in members.values() if len(group) >= 8]
    groups.sort(key=lambda group: (float(points[group, 1].mean()), float(points[group, 0].mean())))
    ids = np.zeros(len(points), np.int32)
    for number, group in enumerate(groups, 1):
        ids[group] = number
    final, regions, reconciliation = _reconcile(points, ids, spacing, barrier, check)
    return final, regions, {"candidate_edges": len(pairs), "eligible_edges": len(candidates),
                   "barrier_cut_edges": cut, "geometry_cut_edges": geometry_cut,
                   "region_diameter_rejected_merges": rejected, **reconciliation}


def _reconcile(
    points: NDArray[np.float64], ids: NDArray[np.int32], spacing: float,
    barrier: NDArray[np.bool_], check: Callable[[], None],
) -> tuple[NDArray[np.int32], NDArray[np.int32], dict[str, Any]]:
    """Require one seeded 8-connected Voronoi support per final domain, as in v0.4."""
    height, width = barrier.shape
    mask = np.zeros(barrier.shape, np.int32)
    tree = cKDTree(points)
    for start in range(0, height, 64):
        check()
        yy, xx = np.indices((min(64, height - start), width))
        samples = np.column_stack((xx.ravel(), (yy + start).ravel()))
        distance, nearest = tree.query(samples)
        values = ids[nearest].copy()
        values[distance > .85 * spacing] = 0
        mask[start:start + len(yy)] = values.reshape(yy.shape)
    mask[barrier] = 0
    groups: list[tuple[NDArray[np.intp], int]] = []
    regions = np.zeros(mask.shape, np.int32)
    for domain in np.unique(ids[ids > 0]):
        check()
        components = np.zeros(mask.shape, np.int32)
        ndi.label(mask == domain, structure=np.ones((3, 3), bool), output=components)
        members = np.flatnonzero(ids == domain)
        seeds = np.rint(points[members]).astype(int)
        seeds[:, 0] = np.clip(seeds[:, 0], 0, width - 1)
        seeds[:, 1] = np.clip(seeds[:, 1], 0, height - 1)
        point_components = components[seeds[:, 1], seeds[:, 0]]
        for component in np.unique(point_components):
            check()
            selected = members[point_components == component]
            if component > 0 and len(selected) >= 8:
                temporary_id = len(groups) + 1
                regions[components == component] = temporary_id
                groups.append((selected, temporary_id))
    groups.sort(key=lambda item: (float(points[item[0], 1].mean()), float(points[item[0], 0].mean())))
    final = np.zeros(len(points), np.int32)
    remap = np.zeros(len(groups) + 1, np.int32)
    for number, (group, temporary_id) in enumerate(groups, 1):
        final[group] = number
        remap[temporary_id] = number
    return final, remap[regions], {"graph_domains": int(len(np.unique(ids[ids > 0]))),
                   "final_domains": len(groups),
                   "removed_by_raster_support": int(np.sum((ids > 0) & (final == 0)))}
