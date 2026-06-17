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
    source_frame_indices: tuple[int, ...] | None = None
    registration_results: Any | None = None
    expanded_aligned_stack: Any | None = None
    molecular_detections: Any | None = None

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
        self.source_frame_indices = self._normalize_source_frame_indices()

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

    def remove_frame(self, frame_index: int | None = None) -> None:
        frame_index = self.active_frame_index if frame_index is None else int(frame_index)
        self.get_frame(frame_index)
        if self.frame_count <= 1:
            raise ValueError("at least one frame must remain active.")

        old_active_index = self.active_frame_index
        self.raw_frames = np.delete(self.raw_frames, frame_index, axis=0)
        source_indices = list(self.source_frame_indices)
        del source_indices[frame_index]
        self.source_frame_indices = tuple(source_indices)
        if old_active_index > frame_index:
            self.active_frame_index = old_active_index - 1
        elif old_active_index == frame_index:
            self.active_frame_index = min(frame_index, self.frame_count - 1)
        self.registration_results = None
        self.expanded_aligned_stack = None
        self.molecular_detections = None

    def _normalize_source_frame_indices(self) -> tuple[int, ...]:
        if self.source_frame_indices is None:
            if self.reverse_frame_order:
                return tuple(reversed(range(self.frame_count)))
            return tuple(range(self.frame_count))

        indices = tuple(int(index) for index in self.source_frame_indices)
        if len(indices) != self.frame_count:
            raise ValueError("source_frame_indices length must match frame_count.")
        if any(index < 0 for index in indices):
            raise ValueError("source_frame_indices must be non-negative.")
        if len(set(indices)) != len(indices):
            raise ValueError("source_frame_indices must not contain duplicates.")
        return indices

    def _validate_metadata_dimensions(self) -> None:
        pixels_y, pixels_x = self.frame_shape
        metadata_pixels_x = int(getattr(self.metadata, "pixels_x", 0) or 0)
        metadata_pixels_y = int(getattr(self.metadata, "pixels_y", 0) or 0)
        if metadata_pixels_x > 0 and metadata_pixels_x != pixels_x:
            raise ValueError("metadata pixels_x must match raw_frames width.")
        if metadata_pixels_y > 0 and metadata_pixels_y != pixels_y:
            raise ValueError("metadata pixels_y must match raw_frames height.")
