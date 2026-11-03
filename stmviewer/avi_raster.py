"""Full-image movie rasters, independent of Qt and the preview viewport."""
from dataclasses import dataclass
import math
from collections.abc import Callable
from typing import Literal

import numpy as np
from numpy.typing import NDArray

from stmviewer.frame import ImageFrame
from stmviewer.calibration import common_pixel_size


@dataclass(frozen=True)
class MoviePresentation:
    gamma: float = 1.0
    pixel_proportions: bool = False
    background: int = 0
    contrast: Literal['per_frame', 'movie'] = 'per_frame'

    def __post_init__(self) -> None:
        if self.contrast not in ('per_frame', 'movie'):
            raise ValueError('Wybierz kontrast osobno dla klatki albo wspólny dla filmu.')
        if not math.isfinite(self.gamma) or not 0.1 <= self.gamma <= 4:
            raise ValueError('Gamma musi należeć do zakresu 0,1–4.')
        if self.background not in (0, 128, 255):
            raise ValueError('Tło musi być czarne, szare lub białe (0, 128 lub 255).')


@dataclass(frozen=True)
class MovieGeometry:
    source_shape: tuple[int, int]
    image_size: tuple[int, int]  # width, height before right/bottom padding
    physical: bool = False

    @property
    def output_size(self) -> tuple[int, int]:
        width, height = self.image_size
        return width + width % 2, height + height % 2


def movie_geometry(frames: tuple[ImageFrame, ...], options: MoviePresentation) -> MovieGeometry:
    if not frames:
        raise ValueError('Nie można zapisać pustej serii.')
    shape = frames[0].data.shape
    if len(shape) != 2 or min(shape) < 1 or any(f.data.shape != shape for f in frames):
        raise ValueError('Klatki muszą mieć jednakowe, dodatnie wymiary.')
    height, width = shape
    common = common_pixel_size(frames)
    physical = not options.pixel_proportions and common is not None
    if physical and common is not None:
        ratio = common[0] / common[1]
        if not math.isfinite(ratio) or ratio <= 0:
            raise ValueError('Skala nie pozwala wyznaczyć rozmiaru AVI.')
        width = max(width, round(width * ratio))
        height = max(height, round(height / ratio))
    # Reject impossible codec dimensions before allocating an output raster.
    if max(width, height) > 32766 or width * height > 100_000_000:
        raise ValueError('Rozmiar AVI jest zbyt duży; sprawdź skalę lub wybierz proporcje pikselowe.')
    return MovieGeometry(shape, (width, height), physical)


def movie_contrast_levels(frames: tuple[ImageFrame, ...], *,
                          progress: Callable[[int, int], None] | None = None) -> tuple[float, float] | None:
    """Finite limits of already selected frames; no frames are stacked or copied.

    Call in the export worker. Progress is also a cancellation checkpoint within
    large frames; it reports completed frames, not the number of image blocks.
    """
    low, high = math.inf, -math.inf
    for index, frame in enumerate(frames):
        rows = max(1, (4 * 1024 * 1024) // (frame.data.shape[1] * 8))
        for row in range(0, frame.data.shape[0], rows):
            if progress is not None:
                progress(index, len(frames))
            block = frame.data[row:row + rows]
            finite = np.isfinite(block)
            low = min(low, float(np.min(block, where=finite, initial=np.inf)))
            high = max(high, float(np.max(block, where=finite, initial=-np.inf)))
    if progress is not None:
        progress(len(frames), len(frames))
    return (low, high) if low <= high else None


def render_movie_frame(frame: ImageFrame, options: MoviePresentation,
                       geometry: MovieGeometry, *,
                       contrast_limits: tuple[float, float] | None = None) -> NDArray[np.uint8]:
    """Map finite samples to grayscale; missing samples and padding use the selected background."""
    if frame.data.shape != geometry.source_shape:
        raise ValueError('Klatka ma wymiary inne niż film.')
    finite = np.isfinite(frame.data)
    gray = np.full(frame.data.shape, options.background, dtype=np.uint8)
    if finite.any():
        values = frame.data[finite]
        if options.contrast == 'movie':
            if contrast_limits is None:
                raise ValueError('Wspólny kontrast wymaga poziomów całego wybranego zakresu.')
            low, high = contrast_limits
        else:
            low, high = float(values.min()), float(values.max())
        if low == high:
            gray[finite] = int(255 * 0.5 ** (1 / options.gamma))
        else:
            scale = max(abs(low), abs(high))
            values = (values / scale - low / scale) / (high / scale - low / scale)
            gray[finite] = (np.clip(values, 0, 1) ** (1 / options.gamma) * 255).astype(np.uint8)
    width, height = geometry.output_size
    raster = np.full((height, width, 3), options.background, dtype=np.uint8)
    w, h = geometry.image_size
    # Nearest sampling expands samples and their mask together, without halos
    # from interpolating a presentation background into valid measurements.
    rows = np.minimum(np.arange(h) * gray.shape[0] // h, gray.shape[0] - 1)
    columns = np.minimum(np.arange(w) * gray.shape[1] // w, gray.shape[1] - 1)
    raster[:h, :w] = gray[rows[:, None], columns][:, :, None]
    return raster
