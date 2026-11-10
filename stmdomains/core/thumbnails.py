"""Render a small raw image without annotation or main-view settings."""

import numpy as np
from numpy.typing import NDArray

from stmdomains.core.display import RenderedImage, render_image


def render_thumbnail(image: NDArray[np.float64]) -> RenderedImage:
    rendered = render_image(image)
    height, width = image.shape
    scale = min(96 / width, 64 / height)
    small_width, small_height = max(1, round(width * scale)), max(1, round(height * scale))
    rows = np.minimum((np.arange(small_height) * height / small_height).astype(int), height - 1)
    columns = np.minimum((np.arange(small_width) * width / small_width).astype(int), width - 1)
    pixels = rendered.rgba[rows[:, None], columns[None, :]].copy()
    pixels.setflags(write=False)
    return RenderedImage(pixels, rendered.has_data)
