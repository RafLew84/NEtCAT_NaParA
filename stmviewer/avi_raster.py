"""Full-image movie rasters, independent of Qt and the preview viewport."""
from dataclasses import dataclass
import math

import numpy as np
from numpy.typing import NDArray

from stmviewer.frame import ImageFrame


@dataclass(frozen=True)
class MoviePresentation:
    gamma: float = 1.0
    pixel_proportions: bool = False

    def __post_init__(self) -> None:
        if not math.isfinite(self.gamma) or not 0.1 <= self.gamma <= 4:
            raise ValueError('Gamma musi należeć do zakresu 0,1–4.')


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
    common: tuple[float, float] | None = None
    physical = not options.pixel_proportions
    for frame in frames:
        x, y = frame.size_x_nm, frame.size_y_nm
        if x is None or y is None or not all(math.isfinite(v) and v > 0 for v in (x, y)):
            physical = False
            break
        size = (x / width, y / height)
        if common is not None and not all(math.isclose(a, b, rel_tol=1e-9) for a, b in zip(size, common)):
            physical = False
            break
        common = size
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


def render_movie_frame(frame: ImageFrame, options: MoviePresentation,
                       geometry: MovieGeometry) -> NDArray[np.uint8]:
    """Map finite samples to grayscale; missing samples and padding stay black."""
    if frame.data.shape != geometry.source_shape:
        raise ValueError('Klatka ma wymiary inne niż film.')
    finite = np.isfinite(frame.data)
    gray = np.zeros(frame.data.shape, dtype=np.uint8)
    if finite.any():
        values = frame.data[finite]
        low, high = float(values.min()), float(values.max())
        if low == high:
            gray[finite] = int(255 * 0.5 ** (1 / options.gamma))
        else:
            scale = max(abs(low), abs(high))
            values = (values / scale - low / scale) / (high / scale - low / scale)
            gray[finite] = (np.clip(values, 0, 1) ** (1 / options.gamma) * 255).astype(np.uint8)
    width, height = geometry.output_size
    raster = np.zeros((height, width, 3), dtype=np.uint8)
    w, h = geometry.image_size
    # Nearest sampling expands samples and their mask together, without halos
    # from interpolating a presentation background into valid measurements.
    rows = np.minimum(np.arange(h) * gray.shape[0] // h, gray.shape[0] - 1)
    columns = np.minimum(np.arange(w) * gray.shape[1] // w, gray.shape[1] - 1)
    raster[:h, :w] = gray[rows[:, None], columns][:, :, None]
    return raster
