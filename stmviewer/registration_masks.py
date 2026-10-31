"""Source-pixel selections used only as evidence for masked registration."""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np
from numpy.typing import NDArray

from stmviewer.frame import ImageFrame


@dataclass(frozen=True)
class MaskRectangle:
    """Half-open pixel-edge bounds; clipping happens against the original raster."""

    x0: int
    y0: int
    x1: int
    y1: int
    kind: Literal['use', 'omit']

    def __post_init__(self) -> None:
        if (any(type(value) is not int for value in (self.x0, self.y0, self.x1, self.y1))
                or self.x0 < 0 or self.y0 < 0 or self.x1 <= self.x0 or self.y1 <= self.y0):
            raise ValueError('Maska wymaga dodatniego prostokąta w pikselach original.')
        if self.kind not in ('use', 'omit'):
            raise ValueError('Nieznany rodzaj prostokąta maski.')


@dataclass(frozen=True)
class FrameMask:
    rectangles: tuple[MaskRectangle, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.rectangles, tuple) or any(not isinstance(r, MaskRectangle) for r in self.rectangles):
            raise ValueError('Maska wymaga niezmiennej krotki prostokątów.')

    def raster(self, data: NDArray[np.float64]) -> NDArray[np.bool_]:
        """Combine use rectangles, subtract omissions, then exclude absent samples."""
        if data.ndim != 2 or min(data.shape) < 1:
            raise ValueError('Maska wymaga niepustego obrazu 2D.')
        include = tuple(rectangle for rectangle in self.rectangles if rectangle.kind == 'use')
        valid = np.zeros(data.shape, dtype=np.bool_) if include else np.ones(data.shape, dtype=np.bool_)
        for rectangle in include:
            valid[rectangle.y0:rectangle.y1, rectangle.x0:rectangle.x1] = True
        for rectangle in self.rectangles:
            if rectangle.kind == 'omit':
                valid[rectangle.y0:rectangle.y1, rectangle.x0:rectangle.x1] = False
        valid &= np.isfinite(data)
        valid.setflags(write=False)
        return valid


class FrameMasks:
    """Session selections follow source identity rather than positions in the film."""

    def __init__(self) -> None:
        self._masks: dict[tuple[Path, int | None], FrameMask] = {}

    @property
    def marked_count(self) -> int:
        return len(self._masks)

    def get(self, frame: ImageFrame) -> FrameMask:
        return self._masks.get((frame.source, frame.source_frame_index), FrameMask())

    def set(self, frame: ImageFrame, mask: FrameMask) -> None:
        if not isinstance(mask, FrameMask):
            raise ValueError('Oczekiwano maski klatki.')
        if not mask.rectangles:
            self.remove(frame)
        else:
            self._masks[(frame.source, frame.source_frame_index)] = mask

    def remove(self, frame: ImageFrame) -> None:
        self._masks.pop((frame.source, frame.source_frame_index), None)

    def clear(self) -> None:
        self._masks.clear()

    def snapshot(self, frames: tuple[ImageFrame, ...]) -> tuple[FrameMask, ...]:
        return tuple(self.get(frame) for frame in frames)
