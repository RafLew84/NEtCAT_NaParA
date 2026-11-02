"""Prepare an image for display without modifying the measurement samples."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True)
class RenderedImage:
    rgba: NDArray[np.uint8]
    has_data: bool


def render_image(image: NDArray[np.floating]) -> RenderedImage:
    """Apply the agreed per-frame 2–98 percentile contrast."""
    finite = np.isfinite(image)
    rgba = np.zeros((*image.shape, 4), dtype=np.uint8)
    if not finite.any():
        return RenderedImage(rgba, False)
    samples = image[finite]
    low, high = np.percentile(samples, [2, 98])
    if high == low:
        grey = np.full(samples.shape, 128, dtype=np.uint8)
    else:
        grey = np.rint(np.clip((samples - low) / (high - low), 0, 1) * 255).astype(np.uint8)
    rgba[finite, :3] = grey[:, None]
    rgba[finite, 3] = 255
    return RenderedImage(rgba, True)
