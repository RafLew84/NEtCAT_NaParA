"""Core MolTrack domain models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True)
class SourceImageSeries:
    """The original STM image series referenced by one MolTrack project."""

    source_uri: str
    frame_count: int
    display_name: str = ""
    source_uris: tuple[str, ...] = ()
    raw_frames: np.ndarray | None = None
    metadata: Any = None

    def __post_init__(self) -> None:
        source_uri = str(self.source_uri).strip()
        if not source_uri:
            raise ValueError("source_uri must be a non-empty string.")
        if int(self.frame_count) <= 0:
            raise ValueError("frame_count must be positive.")
        object.__setattr__(self, "source_uri", source_uri)
        object.__setattr__(self, "frame_count", int(self.frame_count))
        object.__setattr__(self, "display_name", str(self.display_name).strip() or source_uri)
        source_uris = tuple(str(uri) for uri in (self.source_uris or (source_uri,)))
        if not source_uris:
            raise ValueError("source_uris must contain at least one path.")
        object.__setattr__(self, "source_uris", source_uris)

        if self.raw_frames is not None:
            raw_frames = np.asarray(self.raw_frames)
            if raw_frames.ndim != 3:
                raise ValueError("raw_frames must have shape [T, H, W].")
            if raw_frames.shape[0] != self.frame_count:
                raise ValueError("raw_frames frame count must match frame_count.")
            object.__setattr__(self, "raw_frames", raw_frames)

    @property
    def frame_shape(self) -> tuple[int, int] | None:
        if self.raw_frames is None:
            return None
        return int(self.raw_frames.shape[1]), int(self.raw_frames.shape[2])

    def get_frame(self, source_frame_index: int) -> np.ndarray:
        if self.raw_frames is None:
            raise ValueError("Source image frames are not loaded.")
        source_frame_index = int(source_frame_index)
        if not 0 <= source_frame_index < self.frame_count:
            raise IndexError("source_frame_index is out of range.")
        return self.raw_frames[source_frame_index]

    def create_working_series(self, *, reverse_frame_order: bool = False) -> WorkingImageSeries:
        source_frame_indices = range(self.frame_count - 1, -1, -1) if reverse_frame_order else range(self.frame_count)
        frames = tuple(
            WorkingFrame(working_frame_index=working_index, source_frame_index=source_index)
            for working_index, source_index in enumerate(source_frame_indices)
        )
        return WorkingImageSeries(source_series=self, frames=frames)


@dataclass(frozen=True)
class WorkingFrame:
    """One frame in the working image series with source-frame provenance."""

    working_frame_index: int
    source_frame_index: int

    def __post_init__(self) -> None:
        working_frame_index = int(self.working_frame_index)
        source_frame_index = int(self.source_frame_index)
        if working_frame_index < 0:
            raise ValueError("working_frame_index must be non-negative.")
        if source_frame_index < 0:
            raise ValueError("source_frame_index must be non-negative.")
        object.__setattr__(self, "working_frame_index", working_frame_index)
        object.__setattr__(self, "source_frame_index", source_frame_index)


@dataclass(frozen=True)
class WorkingImageSeries:
    """The frame series after import-time ordering and frame removals."""

    source_series: SourceImageSeries
    frames: tuple[WorkingFrame, ...]

    def __post_init__(self) -> None:
        frames = tuple(self.frames)
        if not frames:
            raise ValueError("frames must contain at least one working frame.")
        for expected_index, frame in enumerate(frames):
            if frame.working_frame_index != expected_index:
                raise ValueError("working_frame_index values must be contiguous from zero.")
            if frame.source_frame_index >= self.source_series.frame_count:
                raise IndexError("source_frame_index is out of range for the source series.")
        object.__setattr__(self, "frames", frames)

    @property
    def frame_count(self) -> int:
        return len(self.frames)

    def get_working_frame(self, working_frame_index: int) -> WorkingFrame:
        working_frame_index = int(working_frame_index)
        if not 0 <= working_frame_index < self.frame_count:
            raise IndexError("working_frame_index is out of range.")
        return self.frames[working_frame_index]

    def get_source_frame_index(self, working_frame_index: int) -> int:
        return self.get_working_frame(working_frame_index).source_frame_index

    def source_frame_indices(self) -> list[int]:
        return [frame.source_frame_index for frame in self.frames]

    def removed_source_frame_indices(self) -> list[int]:
        active = set(self.source_frame_indices())
        return [source_index for source_index in range(self.source_series.frame_count) if source_index not in active]

    def remove_working_frame(self, working_frame_index: int) -> WorkingImageSeries:
        working_frame_index = int(working_frame_index)
        if not 0 <= working_frame_index < self.frame_count:
            raise IndexError("working_frame_index is out of range.")
        remaining_source_indices = [
            frame.source_frame_index
            for frame in self.frames
            if frame.working_frame_index != working_frame_index
        ]
        if not remaining_source_indices:
            raise ValueError("Cannot remove the last working frame.")
        frames = tuple(
            WorkingFrame(working_frame_index=index, source_frame_index=source_frame_index)
            for index, source_frame_index in enumerate(remaining_source_indices)
        )
        return WorkingImageSeries(source_series=self.source_series, frames=frames)


@dataclass(frozen=True)
class MolTrackProject:
    """A molecular-field analysis state for one source image series."""

    source_series: SourceImageSeries
    working_series: WorkingImageSeries
    project_name: str = "Untitled MolTrack Project"

    @classmethod
    def from_source_series(
        cls,
        source_series: SourceImageSeries,
        *,
        project_name: str = "Untitled MolTrack Project",
        reverse_frame_order: bool = False,
    ) -> MolTrackProject:
        return cls(
            source_series=source_series,
            working_series=source_series.create_working_series(reverse_frame_order=reverse_frame_order),
            project_name=project_name,
        )

    def __post_init__(self) -> None:
        if self.working_series.source_series != self.source_series:
            raise ValueError("working_series must be derived from source_series.")
        object.__setattr__(
            self,
            "project_name",
            str(self.project_name).strip() or "Untitled MolTrack Project",
        )

    def remove_working_frame(self, working_frame_index: int) -> MolTrackProject:
        return MolTrackProject(
            source_series=self.source_series,
            working_series=self.working_series.remove_working_frame(working_frame_index),
            project_name=self.project_name,
        )
