from __future__ import annotations

from hashlib import sha256

import numpy as np


def point_coordinate_fingerprint(
    points_xy_nm: np.ndarray,
    point_ids: tuple[str, ...],
) -> str:
    """Return an order-sensitive fingerprint of point IDs and float64 coordinates."""

    points = np.ascontiguousarray(points_xy_nm, dtype="<f8")
    digest = sha256(b"moltrack.sample_nm.points.v1\0")
    digest.update(np.asarray(points.shape, dtype="<i8").tobytes())
    for point_id in point_ids:
        encoded = point_id.encode("utf-8")
        digest.update(len(encoded).to_bytes(8, byteorder="little", signed=False))
        digest.update(encoded)
    digest.update(points.tobytes())
    return digest.hexdigest()
