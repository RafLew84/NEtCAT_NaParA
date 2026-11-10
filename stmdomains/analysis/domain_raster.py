"""Seeded, connected Voronoi support shared by baseline and geometric domains."""

from collections.abc import Callable
from typing import Any

import numpy as np
from numpy.typing import NDArray
from scipy import ndimage as ndi
from scipy.spatial import cKDTree

from stmdomains.analysis.domain_settings import DomainSettings


def rasterize_domains(
    points: NDArray[np.float64], ids: NDArray[np.int32], spacing: float,
    barrier: NDArray[np.bool_], check: Callable[[], None], settings: DomainSettings,
    *, scale: tuple[float, float] = (1., 1.),
) -> tuple[NDArray[np.int32], NDArray[np.int32], dict[str, Any]]:
    """Require one seeded 8-connected Voronoi support per final domain, as in v0.4."""
    height, width = barrier.shape
    mask = np.zeros(barrier.shape, np.int32)
    tree = cKDTree(points * scale)
    for start in range(0, height, 64):
        check()
        yy, xx = np.indices((min(64, height - start), width))
        samples = np.column_stack((xx.ravel(), (yy + start).ravel())) * scale
        distance, nearest = tree.query(samples)
        values = ids[nearest].copy()
        values[distance > settings.raster_radius_factor * spacing] = 0
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
            if component > 0 and len(selected) >= settings.minimum_domain_size:
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
