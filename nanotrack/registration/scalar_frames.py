"""On-demand scientific frames in the oriented source pixel coordinate system."""
from __future__ import annotations

from dataclasses import dataclass, replace
from collections import OrderedDict
from math import ceil, floor
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
class FrameCanvas:
    """One pixel-aligned field for a whole sequence, in registered source coordinates."""

    bounds_xyxy: tuple[int, int, int, int]
    metadata: STMSequenceMetadata

    @property
    def shape_hw(self) -> tuple[int, int]:
        x0, y0, x1, y1 = self.bounds_xyxy
        return y1 - y0, x1 - x0

    @property
    def offset_xy(self) -> tuple[float, float]:
        x0, y0, _, _ = self.bounds_xyxy
        return -float(x0), -float(y0)


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
        self._cache: OrderedDict[tuple[int, bool, float, float, str, tuple[int, int, int, int]], ScalarFrame] = OrderedDict()
        self._cache_bytes = 0

    def get_canvas(
        self, *, expanded: bool = False, registration: RegistrationResultSet | None = None,
    ) -> FrameCanvas:
        """Cover every frame, including identity for missing or legacy inherited shifts."""
        count, height, width = self._frames.shape
        if not expanded or registration is None:
            return FrameCanvas((0, 0, width, height), self._metadata)
        min_x = min_y = float("inf")
        max_x = max_y = float("-inf")
        for index in range(count):
            result = registration.get_result(index)
            dx, dy = result.shift_xy if result is not None and result.method != "excluded_frame" else (0., 0.)
            min_x, min_y = min(min_x, dx), min(min_y, dy)
            max_x, max_y = max(max_x, dx), max(max_y, dy)
        x0, y0, x1, y1 = floor(min_x), floor(min_y), width + ceil(max_x), height + ceil(max_y)
        if (x1-x0) * (y1-y0) * 48 > 512 * 1024 * 1024:
            raise MemoryError("Płótno Expanded wymaga ponad 512 MiB pamięci roboczej; nie zmniejszono obrazu.")
        sx, sy = self._metadata.get_pixel_size_nm()
        metadata = replace(
            self._metadata, pixels_x=x1-x0, pixels_y=y1-y0,
            size_nm_x=(x1-x0)*sx if sx is not None else 0.,
            size_nm_y=(y1-y0)*sy if sy is not None else 0.,
            offset_nm_x=self._metadata.offset_nm_x + x0*sx if sx is not None else self._metadata.offset_nm_x,
            offset_nm_y=self._metadata.offset_nm_y + y0*sy if sy is not None else self._metadata.offset_nm_y,
        )
        return FrameCanvas((x0, y0, x1, y1), metadata)

    def get_frame(
        self, frame_index: int, *, aligned: bool = False, expanded: bool = False,
        registration: RegistrationResultSet | None = None,
    ) -> ScalarFrame:
        if not 0 <= frame_index < self._frames.shape[0]:
            raise IndexError("Frame index is out of range.")
        result = registration.get_result(frame_index) if aligned and registration is not None else None
        if result is not None and result.method == "excluded_frame":
            result = None  # Legacy batch values were inherited, not measured for this frame.
        dx, dy = result.shift_xy if result is not None else (0., 0.)
        status = result.status if result is not None else ("missing" if aligned else "not_applied")
        canvas = self.get_canvas(expanded=aligned and expanded, registration=registration)
        offset_x, offset_y = canvas.offset_xy
        geometry = FrameGeometry((float(dx) + offset_x, float(dy) + offset_y))
        key = (frame_index, aligned, float(dx), float(dy), status, canvas.bounds_xyxy)
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        # Account for the output, validity, source conversion and bilinear work
        # buffers before materializing anything, without silently downsampling.
        height, width = canvas.shape_hw
        if int(height) * int(width) * 48 > 512 * 1024 * 1024:
            raise MemoryError("Klatka wymaga ponad 512 MiB pamięci roboczej; zachowano jej rozdzielczość.")
        source = np.asarray(self._frames[frame_index], dtype=np.float64)
        values, valid = _translate(source, *geometry.offset_xy, output_shape=canvas.shape_hw)
        values.setflags(write=False)
        valid.setflags(write=False)
        frame = ScalarFrame(values, valid, canvas.metadata, geometry,
                            status, self._source_revision, self._provenance)
        size = values.nbytes + valid.nbytes
        while self._cache and self._cache_bytes + size > self._max_cache_bytes:
            _, old = self._cache.popitem(last=False)
            self._cache_bytes -= old.values.nbytes + old.valid_mask.nbytes
        if size <= self._max_cache_bytes:
            self._cache[key] = frame
            self._cache_bytes += size
        return frame


def _translate(
    source: np.ndarray, dx: float, dy: float, *, output_shape: tuple[int, int],
) -> tuple[np.ndarray, np.ndarray]:
    """Only nonzero bilinear contributors participate in the validity intersection."""
    height, width = source.shape
    left, top = floor(-dx), floor(-dy)
    fx, fy = -dx - left, -dy - top
    output_height, output_width = output_shape
    values = np.zeros(output_shape, dtype=np.float64)
    valid = np.ones(output_shape, dtype=bool)
    for sx, wx in ((left, 1. - fx), (left + 1, fx)):
        for sy, wy in ((top, 1. - fy), (top + 1, fy)):
            weight = wx * wy
            if weight == 0.:
                continue
            x0, x1 = max(0, -sx), min(output_width, width - sx)
            y0, y1 = max(0, -sy), min(output_height, height - sy)
            contributor_valid = np.zeros(output_shape, dtype=bool)
            if x0 < x1 and y0 < y1:
                samples = source[y0+sy:y1+sy, x0+sx:x1+sx]
                finite = np.isfinite(samples)
                contributor_valid[y0:y1, x0:x1] = finite
                values[y0:y1, x0:x1] += np.where(finite, samples, 0.) * weight
            valid &= contributor_valid
    values[~valid] = np.nan
    return values, valid
