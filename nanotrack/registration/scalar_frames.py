"""On-demand scientific frames in the oriented source pixel coordinate system."""
from __future__ import annotations

from dataclasses import dataclass
from collections import OrderedDict
from math import floor
from numpy.typing import ArrayLike

import numpy as np

from nanotrack.core import RegistrationResultSet, STMSequenceMetadata
from nanotrack.core.preview_sources import PreprocessingProvenance


@dataclass(frozen=True)
class FrameGeometry:
    """Translation from canonical source pixels to display pixels, before XY scaling."""

    offset_xy: tuple[float, float] = (0., 0.)

    def __post_init__(self) -> None:
        offset = np.asarray(self.offset_xy, dtype=np.float64)
        if offset.shape != (2,) or not np.isfinite(offset).all():
            raise ValueError("The frame translation must contain two finite values.")
        object.__setattr__(self, "offset_xy", (float(offset[0]), float(offset[1])))

    def source_to_display(self, points: ArrayLike) -> np.ndarray:
        return np.asarray(points, dtype=np.float64) + self.offset_xy

    def display_to_source(self, points: ArrayLike) -> np.ndarray:
        return np.asarray(points, dtype=np.float64) - self.offset_xy


@dataclass(frozen=True)
class ScalarFrame:
    values: np.ndarray
    valid_mask: np.ndarray
    metadata: STMSequenceMetadata
    geometry: FrameGeometry
    registration_status: str
    source_revision: str
    provenance: PreprocessingProvenance | None = None


class ScalarFrameProvider:
    """Read-only frames with a byte-bounded cache.

    The caller owns the unaligned source and must replace this provider when its
    source revision changes. No stack copy is made. Registration values are read
    on each request, so even edits within the current result set invalidate a frame.
    """

    def __init__(
        self, frames: np.ndarray, metadata: STMSequenceMetadata, *,
        source_revision: str = "original", provenance: PreprocessingProvenance | None = None,
        max_cache_bytes: int = 32 * 1024 * 1024,
    ):
        if frames.ndim != 3 or any(size < 1 for size in frames.shape):
            raise ValueError("Source frames must have shape (frame, height, width).")
        if not np.issubdtype(frames.dtype, np.floating):
            raise ValueError("Source frames must contain real floating-point measurements.")
        if frames.shape[1:] != (metadata.pixels_y, metadata.pixels_x):
            raise ValueError("Source frame dimensions do not match their calibration.")
        if max_cache_bytes < 0:
            raise ValueError("The cache memory budget cannot be negative.")
        self._frames = frames
        self._metadata = metadata
        self._source_revision = source_revision
        self._provenance = provenance
        self._max_cache_bytes = max_cache_bytes
        self._cache: OrderedDict[tuple[int, bool, float, float, str], ScalarFrame] = OrderedDict()
        self._cache_bytes = 0

    def get_frame(
        self, frame_index: int, *, aligned: bool = False,
        registration: RegistrationResultSet | None = None,
    ) -> ScalarFrame:
        if not 0 <= frame_index < self._frames.shape[0]:
            raise IndexError("Frame index is out of range.")
        result = registration.get_result(frame_index) if aligned and registration is not None else None
        if result is not None and result.method == "excluded_frame":
            result = None  # Legacy batch values were inherited, not measured for this frame.
        dx, dy = result.shift_xy if result is not None else (0., 0.)
        status = result.status if result is not None else ("missing" if aligned else "not_applied")
        key = (frame_index, aligned, float(dx), float(dy), status)
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        # Account for the output, validity, source conversion and bilinear work
        # buffers before materializing anything, without silently downsampling.
        height, width = self._frames.shape[1:]
        if int(height) * int(width) * 48 > 512 * 1024 * 1024:
            raise MemoryError("Klatka wymaga ponad 512 MiB pamięci roboczej; zachowano jej rozdzielczość.")
        source = np.asarray(self._frames[frame_index], dtype=np.float64)
        values, valid = _translate(source, float(dx), float(dy))
        values.setflags(write=False)
        valid.setflags(write=False)
        frame = ScalarFrame(values, valid, self._metadata, FrameGeometry((float(dx), float(dy))),
                            status, self._source_revision, self._provenance)
        size = values.nbytes + valid.nbytes
        while self._cache and self._cache_bytes + size > self._max_cache_bytes:
            _, old = self._cache.popitem(last=False)
            self._cache_bytes -= old.values.nbytes + old.valid_mask.nbytes
        if size <= self._max_cache_bytes:
            self._cache[key] = frame
            self._cache_bytes += size
        return frame


def _translate(source: np.ndarray, dx: float, dy: float) -> tuple[np.ndarray, np.ndarray]:
    """Only nonzero bilinear contributors participate in the validity intersection."""
    height, width = source.shape
    left, top = floor(-dx), floor(-dy)
    fx, fy = -dx - left, -dy - top
    values = np.zeros(source.shape, dtype=np.float64)
    valid = np.ones(source.shape, dtype=bool)
    for sx, wx in ((left, 1. - fx), (left + 1, fx)):
        for sy, wy in ((top, 1. - fy), (top + 1, fy)):
            weight = wx * wy
            if weight == 0.:
                continue
            x0, x1 = max(0, -sx), min(width, width - sx)
            y0, y1 = max(0, -sy), min(height, height - sy)
            contributor_valid = np.zeros(source.shape, dtype=bool)
            if x0 < x1 and y0 < y1:
                samples = source[y0+sy:y1+sy, x0+sx:x1+sx]
                finite = np.isfinite(samples)
                contributor_valid[y0:y1, x0:x1] = finite
                values[y0:y1, x0:x1] += np.where(finite, samples, 0.) * weight
            valid &= contributor_valid
    values[~valid] = np.nan
    return values, valid
