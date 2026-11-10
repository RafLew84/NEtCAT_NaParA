"""Prepare an image for display without modifying the measurement samples."""

from dataclasses import dataclass
from math import isfinite

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True)
class RenderedImage:
    rgba: NDArray[np.uint8]
    has_data: bool


def contrast_limits(image: NDArray[np.floating]) -> tuple[float, float] | None:
    """Return finite original-frame percentiles; no samples means no scale."""
    samples = image[np.isfinite(image)]
    if not samples.size:
        return None
    low, high = np.percentile(samples, [2, 98])
    return float(low), float(high)


def render_image(
    image: NDArray[np.floating], *, reference: NDArray[np.floating] | None = None,
    gamma: float = 1.0, limits: tuple[float, float] | None = None,
) -> RenderedImage:
    """Apply the agreed per-frame 2–98 percentile contrast."""
    if not isfinite(gamma) or gamma <= 0:
        raise ValueError("Gamma musi być skończona i dodatnia.")
    finite = np.isfinite(image)
    rgba = np.zeros((*image.shape, 4), dtype=np.uint8)
    if not finite.any():
        return RenderedImage(rgba, False)
    samples = image[finite]
    if limits is None:
        limits = contrast_limits(image if reference is None else reference)
    if limits is None:
        return RenderedImage(rgba, False)
    low, high = limits
    if high == low:
        normalized = np.full(samples.shape, 0.5)
    else:
        normalized = np.clip((samples - low) / (high - low), 0, 1)
    grey = np.rint(normalized ** (1 / gamma) * 255).astype(np.uint8)
    rgba[finite, :3] = grey[:, None]
    rgba[finite, 3] = 255
    return RenderedImage(rgba, True)
