"""Mask-based particle measurements computed in the main NanoTrack process."""

from __future__ import annotations

import numpy as np

from nanotrack.core import ParticleMetrics


def compute_particle_metrics(mask: np.ndarray, raw_frame: np.ndarray) -> ParticleMetrics:
    """Compute per-frame particle metrics from a binary mask and the raw STM frame."""

    mask_array = np.asarray(mask, dtype=bool)
    raw_array = np.asarray(raw_frame, dtype=np.float32)

    if mask_array.ndim != 2:
        raise ValueError("mask must have shape [H, W].")
    if raw_array.ndim != 2:
        raise ValueError("raw_frame must have shape [H, W].")
    if mask_array.shape != raw_array.shape:
        raise ValueError("mask and raw_frame must have the same shape.")
    if not np.any(mask_array):
        return ParticleMetrics()

    values = raw_array[mask_array]
    area_px = float(np.count_nonzero(mask_array))
    perimeter_px = float(_binary_mask_perimeter_px(mask_array))

    return ParticleMetrics(
        area_px=area_px,
        perimeter_px=perimeter_px,
        intensity_sum=float(values.sum()),
        intensity_mean=float(values.mean()),
        intensity_max=float(values.max()),
    )


def _binary_mask_perimeter_px(mask: np.ndarray) -> int:
    """Return the exposed-edge perimeter on the pixel grid."""

    padded = np.pad(np.asarray(mask, dtype=bool), 1, mode="constant", constant_values=False)
    vertical_edges = np.count_nonzero(padded[1:, :] != padded[:-1, :])
    horizontal_edges = np.count_nonzero(padded[:, 1:] != padded[:, :-1])
    return int(vertical_edges + horizontal_edges)
