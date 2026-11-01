"""A shared movie canvas, rendering only the requested frame from its original."""
from collections.abc import Mapping
from dataclasses import dataclass, replace
import math

import numpy as np
from numpy.typing import NDArray

from stmviewer.avi_raster import MovieGeometry, MoviePresentation, movie_contrast_levels, render_movie_frame
from stmviewer.frame import ImageFrame

XY = tuple[float, float]


@dataclass(frozen=True)
class GraphRaster:
    rgba: NDArray[np.uint8]
    aspect: float


class GraphMoviePreview:
    """Keep original references and XY; never construct a movie of warped arrays.

    All variants use one canvas and the same original-frame contrast. Callers
    provide coordinates anchored to the same first image, including a fallback
    aligned result whose historical anchor may no longer belong to the series.
    """
    def __init__(self, frames: tuple[ImageFrame, ...], variants: Mapping[str, tuple[XY, ...]]) -> None:
        if not frames or not variants:
            raise ValueError('Podgląd wymaga klatek i co najmniej jednego wariantu.')
        shape = frames[0].data.shape
        if len(shape) != 2 or min(shape) < 1 or any(frame.data.shape != shape for frame in frames):
            raise ValueError('Podgląd wymaga zgodnych wymiarów obrazów.')
        for positions in variants.values():
            if len(positions) != len(frames) or any(len(p) != 2 or not np.isfinite(p).all() for p in positions):
                raise ValueError('Podgląd wymaga kompletnych, skończonych przesunięć.')
        positions = tuple(p for variant in variants.values() for p in variant)
        self._left = math.ceil(max(0, -min(x for x, _ in positions)))
        self._top = math.ceil(max(0, -min(y for _, y in positions)))
        right = math.ceil(max(0, max(x for x, _ in positions)))
        bottom = math.ceil(max(0, max(y for _, y in positions)))
        height, width = shape[0] + self._top + bottom, shape[1] + self._left + right
        if max(height, width) > 32766 or height * width > 100_000_000:
            raise ValueError('Obszar podglądu jest zbyt duży; sprawdź przesunięcia par.')
        self.canvas_shape = (height, width)
        self._frames = frames
        self._variants = dict(variants)
        self._pixel_ratio = self._physical_ratio(frames)
        self._contrast: dict[int, tuple[float, float] | None] = {}

    def render(self, index: int, variant: str, *, gamma: float = 1,
               pixel_proportions: bool = False) -> GraphRaster:
        from scipy.ndimage import affine_transform

        frame = self._frames[index]
        x, y = self._variants[variant][index]
        values = np.asarray(affine_transform(
            frame.data, matrix=np.eye(2), offset=(-y - self._top, -x - self._left),
            output_shape=self.canvas_shape, order=1, mode='constant', cval=np.nan, prefilter=False,
        ), dtype=np.float64)
        if index not in self._contrast:
            self._contrast[index] = movie_contrast_levels((frame,))
        height, width = self.canvas_shape
        limits = self._contrast[index]
        options = MoviePresentation(gamma=gamma, background=255,
                                    contrast='movie' if limits is not None else 'per_frame')
        rgb = render_movie_frame(replace(frame, data=values), options,
                                 MovieGeometry(self.canvas_shape, (width, height)), contrast_limits=limits)
        rgba = np.empty((height, width, 4), dtype=np.uint8)
        rgba[:, :, :3] = rgb[:height, :width]
        rgba[:, :, 3] = np.isfinite(values) * 255
        rgba.setflags(write=False)
        ratio = 1.0 if pixel_proportions else self._pixel_ratio
        return GraphRaster(rgba, width / height * ratio)

    @staticmethod
    def _physical_ratio(frames: tuple[ImageFrame, ...]) -> float:
        common: tuple[float, float] | None = None
        for frame in frames:
            x, y = frame.size_x_nm, frame.size_y_nm
            if x is None or y is None or not all(math.isfinite(v) and v > 0 for v in (x, y)):
                return 1.0
            size = (x / frame.data.shape[1], y / frame.data.shape[0])
            if common is not None and not all(math.isclose(a, b, rel_tol=1e-9) for a, b in zip(size, common)):
                return 1.0
            common = size
        assert common is not None
        return common[0] / common[1]
