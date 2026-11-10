"""Paired axial features and bounded nearest-centre spatial support."""

from collections.abc import Callable, Sequence

import numpy as np
from numpy.typing import NDArray
from scipy.spatial import cKDTree

from stmdomains.analysis.geometry_domain_settings import GeometryDomainSettings
from stmdomains.analysis.geometry_domains import geometry_distance
from stmdomains.core.geometry import MoleculeGeometry


def paired_features(records: Sequence[MoleculeGeometry]) -> NDArray[np.float64]:
    values = np.empty((len(records), 2, 3), float)
    for i, record in enumerate(records):
        for j, axis in enumerate(record.axes):
            angle = np.deg2rad(2 * axis.row_angle_deg)
            values[i, j] = np.cos(angle), np.sin(angle), np.log(axis.period)
    return values


def feature_scales(settings: GeometryDomainSettings) -> NDArray[np.float64]:
    chord = 2 * np.sin(np.deg2rad(settings.angle_degrees))
    return np.array([chord, chord, np.log1p(settings.spacing_percent / 100)])


def paired_costs(values: NDArray, prototype: NDArray, scales: NDArray) -> tuple[NDArray, NDArray]:
    direct = np.sum(((values - prototype) / scales) ** 2, axis=(1, 2)) / 2
    swapped = np.sum(((values[:, ::-1] - prototype) / scales) ** 2, axis=(1, 2)) / 2
    return np.minimum(direct, swapped), swapped < direct


def update_prototype(values: NDArray, old: NDArray, scales: NDArray) -> NDArray:
    _, swap = paired_costs(values, old, scales)
    aligned = values.copy()
    aligned[swap] = values[swap, ::-1]
    mean = aligned.mean(axis=0)
    norms = np.linalg.norm(mean[:, :2], axis=1)
    for axis in range(2):
        mean[axis, :2] = mean[axis, :2] / norms[axis] if norms[axis] > 1e-10 else old[axis, :2]
    return mean


def initial_prototypes(records: Sequence[MoleculeGeometry], settings: GeometryDomainSettings,
                       check: Callable[[], None]) -> NDArray[np.float64]:
    selected: list[MoleculeGeometry] = []
    for record in records:
        check()
        if all(geometry_distance(record, other, settings) > 1 for other in selected):
            selected.append(record)
            if len(selected) > 32:
                raise ValueError('Level set: ponad 32 regiony początkowe. Zwiększ tolerancje geometrii.')
    return paired_features(selected)


def spatial_support(points: NDArray, eligible: NDArray, scale: tuple[float, float], spacing: float,
                    radius: float, forbidden: NDArray, check: Callable[[], None]) -> tuple[NDArray, NDArray]:
    """Invalid nearest centres retain holes; no interpolation from a farther valid centre."""
    height, width = forbidden.shape
    nearest_map = np.zeros(forbidden.shape, np.int32)
    valid = np.zeros(forbidden.shape, bool)
    tree = cKDTree(points * scale)
    for start in range(0, height, 64):
        check()
        yy, xx = np.indices((min(64, height-start), width))
        distance, nearest = tree.query(np.column_stack((xx.ravel(), (yy+start).ravel())) * scale)
        nearest_map[start:start+len(yy)] = nearest.reshape(yy.shape)
        valid[start:start+len(yy)] = (eligible[nearest] & (distance <= radius*spacing)).reshape(yy.shape)
    valid &= ~forbidden
    return nearest_map, valid
