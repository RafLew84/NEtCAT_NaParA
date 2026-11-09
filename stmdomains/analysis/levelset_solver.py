"""Hybrid data-force level sets with periodic EDT and explicit curvature flow.

Adaptation, constants and limitations: docs/stmdomains/implementation/
interactive-v04/experiment-26.md. No intensity Chan–Vese or post-render smoothing.
"""

from collections.abc import Callable
from typing import Any

import numpy as np
from numpy.typing import NDArray
from scipy.ndimage import distance_transform_edt

from stmdomains.analysis.levelset_features import paired_costs, update_prototype
from stmdomains.analysis.levelset_settings import LevelSetSettings


def _distance(labels: NDArray, valid: NDArray, region: int, sampling: tuple[float, float]) -> NDArray:
    inside = valid & (labels == region)
    outside = valid & (labels != region)
    return (np.asarray(distance_transform_edt(~outside, sampling=sampling))
            - np.asarray(distance_transform_edt(~inside, sampling=sampling)))


def _derivative(value: NDArray, valid: NDArray, axis: int, step: float) -> NDArray:
    neighbors = []
    for shift in (-1, 1):
        allowed = np.roll(valid, shift, axis=axis)
        edge = [slice(None), slice(None)]
        edge[axis] = slice(-1, None) if shift == -1 else slice(0, 1)
        allowed[tuple(edge)] = False
        neighbors.append(np.where(allowed, np.roll(value, shift, axis=axis), value))
    return (neighbors[0]-neighbors[1]) / (2*step)


def _smooth(phi: NDArray, valid: NDArray, sampling: tuple[float, float], strength: float,
            check: Callable[[], None]) -> int:
    duration = .05 * strength
    if duration == 0:
        return 0
    hy, hx = sampling
    steps = int(np.ceil(duration / (.2/(1/hx**2 + 1/hy**2))))
    dt = duration/steps
    for _ in range(steps):
        check()
        dy = _derivative(phi, valid, 0, hy)
        dx = _derivative(phi, valid, 1, hx)
        norm = np.sqrt(dx*dx + dy*dy + 1e-8)
        curvature = _derivative(dx/norm, valid, 1, hx) + _derivative(dy/norm, valid, 0, hy)
        phi[valid] += dt * curvature[valid]
    return steps


def evolve(features: NDArray, prototypes: NDArray, scales: NDArray, valid: NDArray,
           sampling: tuple[float, float], settings: LevelSetSettings, check: Callable[[], None],
           progress: Callable[[str], None]) -> tuple[NDArray, dict[str, Any]]:
    """Return exclusive model labels; unsupported pixels always remain -1."""
    count = len(prototypes)
    if valid.size * count > 4_000_000:
        raise ValueError('Level set: limit 4 mln pikseli × regionów. Zwiększ tolerancje lub użyj mniejszego obrazu.')
    labels = np.full(valid.shape, -1, np.int32)
    metadata: dict[str, Any] = dict(initial_model_regions=count, final_model_regions=0,
        iterations=0, stopping_reason='no_support', curvature_steps=0, changed_pixels=0,
        data_step=.2, reinitialize_every=5, curvature_time_factor=.05,
        boundary_condition='masked_neumann', distance_reconstruction='scipy_edt')
    if not count or not valid.any():
        return labels, metadata
    costs = np.stack([paired_costs(features, p, scales)[0] for p in prototypes])
    labels[valid] = costs.argmin(axis=0)
    initial = labels.copy()
    phi = np.zeros((count, *valid.shape), float)
    active = np.unique(labels[valid])
    for region in active:
        check()
        phi[region] = _distance(labels, valid, int(region), sampling)
    last_block = labels.copy()
    stable_blocks = 0
    for iteration in range(1, settings.iterations+1):
        check()
        active = np.unique(labels[valid])
        if len(active) == 1:
            metadata['stopping_reason'] = 'single_region'
            break
        if iteration % 5 == 1:
            progress(f'Level set: iteracja {iteration}/{settings.iterations} · regiony modelu {len(active)}')
        for region in active:
            check()
            members = features[labels[valid] == region]
            prototypes[region] = update_prototype(members, prototypes[region], scales)
            costs[region] = paired_costs(features, prototypes[region], scales)[0]
        for region in active:
            check()
            competitor = costs[active[active != region]].min(axis=0)
            phi[region, valid] += .2 * np.clip(competitor-costs[region], -1, 1)
        labels[valid] = active[np.argmax(phi[active][:, valid], axis=0)]
        if iteration % 5 == 0:
            active = np.unique(labels[valid])
            if len(active) > 1:
                for region in active:
                    check()
                    phi[region] = _distance(labels, valid, int(region), sampling)
                    metadata['curvature_steps'] += _smooth(phi[region], valid, sampling, settings.regularization, check)
                labels[valid] = active[np.argmax(phi[active][:, valid], axis=0)]
            stable_blocks = stable_blocks+1 if np.array_equal(labels, last_block) else 0
            last_block = labels.copy()
        metadata['iterations'] = iteration
        if stable_blocks >= 2:
            metadata['stopping_reason'] = 'stable_partition'
            break
    else:
        metadata['stopping_reason'] = 'iteration_limit'
    metadata['final_model_regions'] = len(np.unique(labels[valid]))
    metadata['changed_pixels'] = int(np.count_nonzero(initial != labels))
    return labels, metadata
