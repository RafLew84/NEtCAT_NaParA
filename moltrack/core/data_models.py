from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass
class MolTrackImageSeries:
    """One STM image series loaded into the MolTrack workspace."""

    source_path: str
    raw_frames: np.ndarray
    metadata: Any
    active_frame_index: int = 0
    reverse_frame_order: bool = False

    @classmethod
    def from_stm_sequence(cls, sequence: Any) -> "MolTrackImageSeries":
        return cls(
            source_path=sequence.source_path,
            raw_frames=sequence.raw_frames,
            metadata=sequence.metadata,
            active_frame_index=sequence.active_frame_index,
            reverse_frame_order=sequence.reverse_frame_order,
        )

    def __post_init__(self) -> None:
        frames = np.asarray(self.raw_frames)
        if frames.ndim != 3:
            raise ValueError("raw_frames must have shape [T, H, W].")
        if frames.shape[0] == 0:
            raise ValueError("raw_frames must contain at least one frame.")
        self.raw_frames = frames
        self._validate_metadata_dimensions()

        if not 0 <= int(self.active_frame_index) < self.frame_count:
            raise IndexError("active_frame_index is out of range.")
        self.active_frame_index = int(self.active_frame_index)
        self.source_path = str(self.source_path)
        self.reverse_frame_order = bool(self.reverse_frame_order)

    @property
    def frame_count(self) -> int:
        return int(self.raw_frames.shape[0])

    @property
    def frame_shape(self) -> tuple[int, int]:
        return int(self.raw_frames.shape[1]), int(self.raw_frames.shape[2])

    @property
    def active_frame(self) -> np.ndarray:
        return self.get_frame(self.active_frame_index)

    @property
    def pixel_size_nm(self) -> tuple[float | None, float | None]:
        get_pixel_size = getattr(self.metadata, "get_pixel_size_nm", None)
        if not callable(get_pixel_size):
            return None, None
        return get_pixel_size()

    def get_frame(self, frame_index: int) -> np.ndarray:
        frame_index = int(frame_index)
        if not 0 <= frame_index < self.frame_count:
            raise IndexError("frame_index is out of range.")
        return self.raw_frames[frame_index]

    def set_active_frame(self, frame_index: int) -> None:
        self.get_frame(frame_index)
        self.active_frame_index = int(frame_index)

    def _validate_metadata_dimensions(self) -> None:
        pixels_y, pixels_x = self.frame_shape
        metadata_pixels_x = int(getattr(self.metadata, "pixels_x", 0) or 0)
        metadata_pixels_y = int(getattr(self.metadata, "pixels_y", 0) or 0)
        if metadata_pixels_x > 0 and metadata_pixels_x != pixels_x:
            raise ValueError("metadata pixels_x must match raw_frames width.")
        if metadata_pixels_y > 0 and metadata_pixels_y != pixels_y:
            raise ValueError("metadata pixels_y must match raw_frames height.")
