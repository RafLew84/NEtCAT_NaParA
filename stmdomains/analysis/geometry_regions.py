"""Connected metric neighbourhoods and raster support, independent of classes."""

from collections.abc import Callable
from typing import Any

import numpy as np
from numpy.typing import NDArray
from scipy import ndimage as ndi
from scipy.spatial import cKDTree

from stmdomains.analysis.domain_settings import DomainSettings
from stmdomains.analysis.segmentation import _crosses_barrier


def geometry_regions(points: NDArray[np.float64], scale: tuple[float, float], spacing: float,
                     eligible: NDArray[np.bool_], compatible: Callable[[int, int], float],
                     barrier: NDArray[np.bool_], settings: DomainSettings,
                     check: Callable[[], None]) -> tuple[NDArray[np.int32], NDArray[np.int32], dict[str, Any]]:
    metric = points * scale
    pairs = sorted(cKDTree(metric).query_pairs(settings.edge_distance_factor * spacing))
    edges = []
    barrier_cuts = geometry_cuts = 0
    for a, b in pairs:
        check()
        if not (eligible[a] and eligible[b]):
            continue
        if _crosses_barrier(points[a], points[b], barrier):
            barrier_cuts += 1
            continue
        distance = compatible(a, b)
        if distance <= 1. + 1e-10:
            edges.append((distance, a, b))
        else:
            geometry_cuts += 1
    parents = np.arange(len(points))
    members = {int(i): [int(i)] for i in np.flatnonzero(eligible)}

    def find(i: int) -> int:
        while parents[i] != i:
            parents[i] = parents[parents[i]]
            i = int(parents[i])
        return i

    region_rejected = 0
    for _, first, second in sorted(edges):
        check()
        a, b = find(first), find(second)
        if a == b:
            continue
        incompatible = False
        for left in members[a]:
            check()
            if any(compatible(left, right) > 1. + 1e-10 for right in members[b]):
                incompatible = True
                break
        if incompatible:
            region_rejected += 1
            continue
        if b < a:
            a, b = b, a
        parents[b] = a
        members[a].extend(members.pop(b))
    ids = np.zeros(len(points), np.int32)
    for number, group in enumerate(members.values(), 1):
        if len(group) >= settings.minimum_domain_size:
            ids[group] = number
    final, raster = _raster(points, metric, ids, spacing, scale, barrier, settings, check)
    return final, raster, {'candidate_edges': len(pairs), 'barrier_cut_edges': barrier_cuts,
                           'geometry_cut_edges': geometry_cuts,
                           'region_rejected_merges': region_rejected}


def _raster(points, metric, ids, spacing, scale, barrier, settings, check):
    height, width = barrier.shape
    tree = cKDTree(metric)
    raster = np.zeros(barrier.shape, np.int32)
    for start in range(0, height, 64):
        check()
        yy, xx = np.indices((min(64, height-start), width))
        samples = np.column_stack((xx.ravel(), (yy+start).ravel())) * scale
        distance, nearest = tree.query(samples)
        values = ids[nearest].copy()
        values[distance > settings.raster_radius_factor * spacing] = 0
        raster[start:start+len(yy)] = values.reshape(yy.shape)
    raster[barrier] = 0
    regions = np.zeros(barrier.shape, np.int32)
    final = np.zeros(len(points), np.int32)
    groups = []
    for identifier in np.unique(ids[ids > 0]):
        check()
        components, _ = ndi.label(raster == identifier, np.ones((3, 3), bool))
        members = np.flatnonzero(ids == identifier)
        seeds = np.rint(points[members]).astype(int)
        seeds[:, 0] = np.clip(seeds[:, 0], 0, width-1)
        seeds[:, 1] = np.clip(seeds[:, 1], 0, height-1)
        labels = components[seeds[:, 1], seeds[:, 0]]
        for component in np.unique(labels):
            selected = members[labels == component]
            if component and len(selected) >= settings.minimum_domain_size:
                number = len(groups)+1
                regions[components == component] = number
                groups.append((selected, number))
    groups.sort(key=lambda item: (float(points[item[0], 1].mean()), float(points[item[0], 0].mean())))
    remap = np.zeros(len(groups)+1, np.int32)
    for number, (group, temporary) in enumerate(groups, 1):
        final[group] = number
        remap[temporary] = number
    return final, remap[regions]
