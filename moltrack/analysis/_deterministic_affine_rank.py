from __future__ import annotations

import numpy as np


def deterministic_affine_rank_scale_nm(
    points_xy_nm: np.ndarray,
    *,
    minimum_scale_nm: float,
) -> float:
    """Use the same finite coordinate extent for every affine-rank consumer."""

    extents = []
    for column in range(2):
        finite = points_xy_nm[:, column][np.isfinite(points_xy_nm[:, column])]
        extents.append(float(np.ptp(finite)) if finite.size else 0.0)
    return max(float(minimum_scale_nm), *extents)


def deterministic_affine_rank_and_axis(
    representative_points: np.ndarray,
    *,
    scale_nm: float,
    relative_tolerance: float,
) -> tuple[int, np.ndarray | None]:
    """Return affine rank and a sign-canonical rank-1 projection axis."""

    centered = representative_points - np.mean(representative_points, axis=0)
    _u, singular_values, vh = np.linalg.svd(centered, full_matrices=False)
    rank = int(np.count_nonzero(singular_values > relative_tolerance * scale_nm))
    if rank != 1:
        return rank, None
    axis = np.array(vh[0], dtype=np.float64, copy=True)
    for component in axis:
        if abs(float(component)) > relative_tolerance:
            if component < 0.0:
                axis *= -1.0
            break
    return rank, axis
