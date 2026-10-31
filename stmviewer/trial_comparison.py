"""On-demand full-trial comparison in a shared field, without aligned stacks."""

from dataclasses import replace
import math
from typing import Literal

import numpy as np

from stmviewer.frame import ImageFrame


TrialSide = Literal['A', 'B']
XY = tuple[float, float]
# At most 128 MiB of floating-point values in one reconstructed image.
MAX_CANVAS_PIXELS = 16_777_216


class FullTrialComparison:
    """Reconstruct one image at a time from an already validated ordered series.

    Both trials use the first surviving original as their common anchor. This
    is only a coordinate translation: subtracting that frame's stored XY keeps
    every relative displacement, even when a historical reference was deleted.
    Source identity and completion are validated by the trial-document layer.
    No model, GPU, image stack or transformed-image cache is used here.
    """

    def __init__(self, frames: tuple[ImageFrame, ...], shifts_a: tuple[XY, ...],
                 shifts_b: tuple[XY, ...]) -> None:
        if not frames or not len(frames) == len(shifts_a) == len(shifts_b):
            raise ValueError('Porównanie filmu wymaga kompletnych przesunięć obu prób.')
        for frame in frames:
            if (frame.data.ndim != 2 or min(frame.data.shape) < 1
                    or frame.data.shape != frames[0].data.shape):
                raise ValueError('Porównanie: niezgodne lub puste wymiary oryginałów.')
        for series in (shifts_a, shifts_b):
            if any(len(shift) != 2 or not all(math.isfinite(value) for value in shift)
                   for shift in series):
                raise ValueError('Porównanie: nieprawidłowe przesunięcia XY.')
        self._frames = frames
        self._shifts = {side: tuple((x - series[0][0], y - series[0][1]) for x, y in series)
                        for side, series in (('A', shifts_a), ('B', shifts_b))}
        shifts = (*self._shifts['A'], *self._shifts['B'])
        if any(not math.isfinite(value) for shift in shifts for value in shift):
            raise ValueError('Porównanie: przesunięcia XY poza zakresem liczb.')
        left = math.ceil(max(0, -min(x for x, y in shifts)))
        top = math.ceil(max(0, -min(y for x, y in shifts)))
        right = math.ceil(max(0, max(x for x, y in shifts)))
        bottom = math.ceil(max(0, max(y for x, y in shifts)))
        height, width = frames[0].data.shape
        self.canvas_shape = (height + top + bottom, width + left + right)
        if self.canvas_shape[0] * self.canvas_shape[1] > MAX_CANVAS_PIXELS:
            raise ValueError('Porównanie przekracza limit pamięci: obszar większy niż '
                             '16 777 216 pikseli. Sprawdź przesunięcia prób.')
        self.origin_xy = (left, top)
        self.pixel_size_nm = _common_pixel_size(frames)

    def original_rect(self, index: int, side: TrialSide) -> tuple[float, float, int, int]:
        """Original pixel-edge footprint, independent of subpixel sample validity."""
        if not 0 <= index < len(self._frames):
            raise IndexError(index)
        if side not in ('A', 'B'):
            raise ValueError('Porównanie: nieznana próba; wybierz A albo B.')
        x, y = self._shifts[side][index]
        height, width = self._frames[index].data.shape
        return x + self.origin_xy[0], y + self.origin_xy[1], width, height

    def render(self, index: int, side: TrialSide) -> ImageFrame:
        """Return one immutable image; the caller owns its lifetime."""
        from scipy.ndimage import affine_transform

        x, y, _, _ = self.original_rect(index, side)
        frame = self._frames[index]
        values = np.asarray(affine_transform(
            frame.data, matrix=np.eye(2), offset=(-y, -x), output_shape=self.canvas_shape,
            order=1, mode='constant', cval=np.nan, prefilter=False,
        ), dtype=np.float64)
        values.setflags(write=False)
        scale = self.pixel_size_nm
        return replace(frame, data=values,
                       size_x_nm=self.canvas_shape[1] * scale[0] if scale else None,
                       size_y_nm=self.canvas_shape[0] * scale[1] if scale else None,
                       offset_x_nm=None, offset_y_nm=None, alignment=None)


def _common_pixel_size(frames: tuple[ImageFrame, ...]) -> XY | None:
    common = None
    for frame in frames:
        x, y = frame.size_x_nm, frame.size_y_nm
        if x is None or y is None or not (math.isfinite(x) and math.isfinite(y) and x > 0 and y > 0):
            return None
        scale = (x / frame.data.shape[1], y / frame.data.shape[0])
        if common is not None and not all(math.isclose(a, b, rel_tol=1e-9) for a, b in zip(scale, common)):
            return None
        common = scale
    return common
