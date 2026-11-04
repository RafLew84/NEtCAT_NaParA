"""Finite observed environments; no periodic neighbours or padding by remote points."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray
from scipy.spatial import cKDTree

from stmdomains.analysis.freud_settings import FreudSettings


@dataclass
class Environments:
    points: NDArray[np.float64]
    query: NDArray[np.uint32]
    neighbor: NDArray[np.uint32]
    eligible: NDArray[np.int64]
    details: list[dict[str, Any]]


def prepare_environments(points, shape, scale, spacing, settings: FreudSettings,
                         check: Callable[[], None]) -> Environments:
    metric = np.asarray(points, float) * scale / spacing
    distances, neighbors = cKDTree(metric).query(metric, k=settings.neighbor_count + 2)
    height, width = shape
    edge_distance = np.minimum.reduce((points[:, 0] * scale[0], points[:, 1] * scale[1],
        (width-1-points[:, 0])*scale[0], (height-1-points[:, 1])*scale[1])) / spacing
    query, target, eligible, details = [], [], [], []
    for i, (ds, ns) in enumerate(zip(np.asarray(distances), np.asarray(neighbors))):
        check()
        within = [(float(d), int(n)) for d, n in zip(ds[1:], ns[1:])
                  if np.isfinite(d) and d <= settings.radius_factor + 1e-10]
        chosen = within[:settings.neighbor_count]
        reason = ''
        if len(chosen) < settings.neighbor_count:
            reason = 'freud_incomplete'
        elif edge_distance[i] + 1e-10 < chosen[-1][0]:
            reason = 'freud_edge'
        elif len(within) > settings.neighbor_count and abs(within[-1][0]-chosen[-1][0]) < 1e-7:
            reason = 'freud_ambiguous_shell'
        # Stable vector order, independent of detection IDs and nearest-neighbour ties.
        selected = sorted((n for _, n in chosen), key=lambda n: (np.arctan2(*(metric[n]-metric[i])[::-1]),
                                                               float(np.linalg.norm(metric[n]-metric[i]))))
        details.append({'reason': reason, 'neighbors': selected,
                        'distances_nn': [float(np.linalg.norm(metric[n]-metric[i])) for n in selected],
                        'observed_count': len(chosen), 'edge_distance_nn': float(edge_distance[i])})
        if not reason:
            eligible.append(i)
            query.extend([i] * len(selected))
            target.extend(selected)
    return Environments(metric, np.asarray(query, np.uint32), np.asarray(target, np.uint32),
                        np.asarray(eligible, np.int64), details)
