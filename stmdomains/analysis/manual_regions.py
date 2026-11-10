"""Finite Voronoi support for manual memberships; never changes membership."""

from collections.abc import Mapping

import numpy as np
from numpy.typing import NDArray
from scipy.spatial import cKDTree

from stmdomains.core.analysis_result import MoleculeAssignment
from stmdomains.core.annotations import Detection


def manual_regions(detections: tuple[Detection, ...], assignments: Mapping[str, MoleculeAssignment],
                   shape: tuple[int, int]) -> tuple[NDArray[np.int32], tuple[int, ...]]:
    """All active centres reserve their own cells, including unassigned neighbours.

    Domains need three non-collinear members. Cells stop at 0.8 times the
    median nearest-neighbour spacing of all active centres. No bridges,
    extrapolation outside the field, inferred members or automatic splitting.
    """
    active = [d for d in detections if assignments[d.detection_id].status not in
              ('outside_field', 'suppressed_duplicate')]
    labels = np.zeros(shape, np.int32)
    domains = {a.domain_local_id for a in assignments.values() if a.domain_local_id > 0}
    if len(active) < 3:
        return labels, tuple(sorted(domains))
    points = np.asarray([d.center_xy for d in active], dtype=float)
    ids = np.asarray([assignments[d.detection_id].domain_local_id for d in active], dtype=np.int32)
    unsupported = []
    for domain in sorted(domains):
        members = points[ids == domain]
        if len(members) < 3 or np.linalg.matrix_rank(members - members.mean(axis=0)) < 2:
            unsupported.append(domain)
    values = ids.copy()
    values[np.isin(ids, unsupported)] = 0
    tree = cKDTree(points)
    spacing = float(np.median(np.asarray(tree.query(points, k=2)[0])[:, 1]))
    if not np.isfinite(spacing) or spacing <= 0:
        return labels, tuple(sorted(domains))
    height, width = shape
    for start in range(0, height, 64):
        yy, xx = np.indices((min(64, height - start), width))
        distance, nearest = tree.query(np.column_stack((xx.ravel(), yy.ravel() + start)))
        cells = values[nearest].copy()
        cells[distance > 0.8 * spacing] = 0
        labels[start:start + len(yy)] = cells.reshape(yy.shape)
    return labels, tuple(unsupported)
