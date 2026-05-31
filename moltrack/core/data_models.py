"""Core MolTrack domain models."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

import numpy as np


class AnalysisRegionKind(str, Enum):
    """Semantic type of a MolTrack analysis region."""

    TERRACE = "terrace"
    STEP_EDGE = "step_edge"
    IGNORE = "ignore"
    CUSTOM = "custom"


@dataclass(frozen=True)
class AnalysisRegion:
    """A named image area in native frame coordinates."""

    kind: AnalysisRegionKind | str
    name: str
    color_rgb: tuple[int, int, int]
    rect_xyxy: tuple[float, float, float, float] | None = None
    polygon_xy: np.ndarray | None = None
    coordinate_system: str = "native"

    @classmethod
    def rectangle(
        cls,
        *,
        kind: AnalysisRegionKind | str,
        name: str,
        color_rgb: tuple[int, int, int],
        rect_xyxy: tuple[float, float, float, float],
    ) -> AnalysisRegion:
        return cls(kind=kind, name=name, color_rgb=color_rgb, rect_xyxy=rect_xyxy)

    @classmethod
    def polygon(
        cls,
        *,
        kind: AnalysisRegionKind | str,
        name: str,
        color_rgb: tuple[int, int, int],
        vertices_xy,
    ) -> AnalysisRegion:
        return cls(kind=kind, name=name, color_rgb=color_rgb, polygon_xy=vertices_xy)

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", AnalysisRegionKind(self.kind))
        object.__setattr__(self, "name", str(self.name).strip())
        if not self.name:
            raise ValueError("Analysis region name must be a non-empty string.")
        object.__setattr__(self, "color_rgb", _normalize_color_rgb(self.color_rgb))
        if self.coordinate_system != "native":
            raise ValueError("AnalysisRegion geometry must be stored in native coordinates.")

        has_rect = self.rect_xyxy is not None
        has_polygon = self.polygon_xy is not None
        if has_rect == has_polygon:
            raise ValueError("AnalysisRegion requires exactly one geometry: rect_xyxy or polygon_xy.")
        if has_rect:
            object.__setattr__(self, "rect_xyxy", _normalize_rect_xyxy(self.rect_xyxy))
        if has_polygon:
            object.__setattr__(self, "polygon_xy", _normalize_polygon_xy(self.polygon_xy))

    @property
    def geometry_type(self) -> str:
        return "rect" if self.rect_xyxy is not None else "polygon"

    @property
    def bounds_xyxy(self) -> tuple[float, float, float, float]:
        if self.rect_xyxy is not None:
            return self.rect_xyxy
        polygon = np.asarray(self.polygon_xy, dtype=np.float64)
        return (
            float(np.min(polygon[:, 0])),
            float(np.min(polygon[:, 1])),
            float(np.max(polygon[:, 0])),
            float(np.max(polygon[:, 1])),
        )


@dataclass(frozen=True)
class CopiedAnalysisRegion:
    """An analysis region reused on working frames without geometry changes."""

    region: AnalysisRegion
    working_frame_indices: tuple[int, ...]

    @classmethod
    def from_working_series(
        cls,
        region: AnalysisRegion,
        working_series: WorkingImageSeries,
    ) -> CopiedAnalysisRegion:
        return cls(
            region=region,
            working_frame_indices=tuple(frame.working_frame_index for frame in working_series.frames),
        )

    def __post_init__(self) -> None:
        if not isinstance(self.region, AnalysisRegion):
            raise TypeError("region must be an AnalysisRegion.")
        working_frame_indices = tuple(int(index) for index in self.working_frame_indices)
        if not working_frame_indices:
            raise ValueError("working_frame_indices must contain at least one frame.")
        if any(index < 0 for index in working_frame_indices):
            raise ValueError("working_frame_indices must be non-negative.")
        if len(set(working_frame_indices)) != len(working_frame_indices):
            raise ValueError("working_frame_indices must be unique.")
        object.__setattr__(self, "working_frame_indices", working_frame_indices)

    def applies_to_working_frame(self, working_frame_index: int) -> bool:
        return int(working_frame_index) in self.working_frame_indices

    def region_for_working_frame(self, working_frame_index: int) -> AnalysisRegion:
        if not self.applies_to_working_frame(working_frame_index):
            raise IndexError("working_frame_index is not covered by the copied analysis region.")
        return self.region


@dataclass(frozen=True)
class FrameScopedAnalysisRegion:
    """An analysis region geometry active only on selected working frames."""

    region: AnalysisRegion
    working_frame_indices: tuple[int, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.region, AnalysisRegion):
            raise TypeError("region must be an AnalysisRegion.")
        working_frame_indices = tuple(sorted({int(index) for index in self.working_frame_indices}))
        if not working_frame_indices:
            raise ValueError("working_frame_indices must contain at least one frame.")
        if any(index < 0 for index in working_frame_indices):
            raise ValueError("working_frame_indices must be non-negative.")
        object.__setattr__(self, "working_frame_indices", working_frame_indices)

    @classmethod
    def from_working_series(
        cls,
        region: AnalysisRegion,
        working_series: WorkingImageSeries,
    ) -> FrameScopedAnalysisRegion:
        return cls(
            region=region,
            working_frame_indices=tuple(frame.working_frame_index for frame in working_series.frames),
        )

    def applies_to_working_frame(self, working_frame_index: int) -> bool:
        return int(working_frame_index) in self.working_frame_indices


@dataclass(frozen=True)
class RegistrationShift:
    """A global XY translation estimated for one working frame."""

    working_frame_index: int
    dx: float
    dy: float
    method: str = "unknown"

    def __post_init__(self) -> None:
        working_frame_index = int(self.working_frame_index)
        if working_frame_index < 0:
            raise ValueError("working_frame_index must be non-negative.")
        dx = float(self.dx)
        dy = float(self.dy)
        if not np.isfinite(dx) or not np.isfinite(dy):
            raise ValueError("RegistrationShift dx and dy must be finite.")
        method = str(self.method).strip() or "unknown"
        object.__setattr__(self, "working_frame_index", working_frame_index)
        object.__setattr__(self, "dx", dx)
        object.__setattr__(self, "dy", dy)
        object.__setattr__(self, "method", method)

    @property
    def shift_xy(self) -> tuple[float, float]:
        return self.dx, self.dy


def _normalize_color_rgb(color_rgb: tuple[int, int, int]) -> tuple[int, int, int]:
    if len(color_rgb) != 3:
        raise ValueError("color_rgb must contain exactly three channels.")
    color = tuple(int(channel) for channel in color_rgb)
    if any(channel < 0 or channel > 255 for channel in color):
        raise ValueError("color_rgb channels must be in the range 0..255.")
    return color


def _normalize_rect_xyxy(rect_xyxy: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    rect = tuple(float(value) for value in rect_xyxy)
    if len(rect) != 4:
        raise ValueError("rect_xyxy must contain exactly four values.")
    if not np.all(np.isfinite(rect)):
        raise ValueError("rect_xyxy values must be finite.")
    x0, y0, x1, y1 = rect
    if x1 <= x0 or y1 <= y0:
        raise ValueError("rect_xyxy must have positive width and height.")
    return rect


def _normalize_polygon_xy(vertices_xy) -> np.ndarray:
    vertices = np.asarray(vertices_xy, dtype=np.float64)
    if vertices.ndim != 2 or vertices.shape[1] != 2:
        raise ValueError("vertices_xy must have shape [N, 2].")
    if len(vertices) < 3:
        raise ValueError("AnalysisRegion polygon requires at least three vertices.")
    if not np.all(np.isfinite(vertices)):
        raise ValueError("AnalysisRegion polygon vertices must be finite.")
    return vertices


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
    analysis_regions: tuple[AnalysisRegion, ...] = ()
    copied_analysis_regions: tuple[CopiedAnalysisRegion, ...] = ()
    frame_scoped_analysis_regions: tuple[FrameScopedAnalysisRegion, ...] = ()
    registration_shifts: tuple[RegistrationShift, ...] = ()

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
        analysis_regions = tuple(self.analysis_regions)
        if any(not isinstance(region, AnalysisRegion) for region in analysis_regions):
            raise TypeError("analysis_regions must contain AnalysisRegion instances.")
        region_names = [region.name for region in analysis_regions]
        if len(set(region_names)) != len(region_names):
            raise ValueError("analysis_regions must have unique names.")

        copied_analysis_regions = tuple(self.copied_analysis_regions)
        if any(not isinstance(region, CopiedAnalysisRegion) for region in copied_analysis_regions):
            raise TypeError("copied_analysis_regions must contain CopiedAnalysisRegion instances.")
        region_by_name = {region.name: region for region in analysis_regions}
        normalized_copied_regions = []
        for copied_region in copied_analysis_regions:
            if copied_region.region.name not in region_by_name:
                raise ValueError("copied_analysis_regions must reference project analysis_regions.")
            normalized_copied_regions.append(
                CopiedAnalysisRegion(
                    region=region_by_name[copied_region.region.name],
                    working_frame_indices=copied_region.working_frame_indices,
                )
            )
        frame_scoped_analysis_regions = tuple(self.frame_scoped_analysis_regions)
        if any(not isinstance(region, FrameScopedAnalysisRegion) for region in frame_scoped_analysis_regions):
            raise TypeError("frame_scoped_analysis_regions must contain FrameScopedAnalysisRegion instances.")
        _validate_frame_scoped_regions(frame_scoped_analysis_regions, self.working_series)

        registration_shifts = tuple(self.registration_shifts)
        if any(not isinstance(shift, RegistrationShift) for shift in registration_shifts):
            raise TypeError("registration_shifts must contain RegistrationShift instances.")
        normalized_registration_shifts = _validate_registration_shifts(registration_shifts, self.working_series)
        object.__setattr__(
            self,
            "project_name",
            str(self.project_name).strip() or "Untitled MolTrack Project",
        )
        object.__setattr__(self, "analysis_regions", analysis_regions)
        object.__setattr__(self, "copied_analysis_regions", tuple(normalized_copied_regions))
        object.__setattr__(self, "frame_scoped_analysis_regions", frame_scoped_analysis_regions)
        object.__setattr__(self, "registration_shifts", normalized_registration_shifts)

    def remove_working_frame(self, working_frame_index: int) -> MolTrackProject:
        working_series = self.working_series.remove_working_frame(working_frame_index)
        remaining_old_indices = [
            frame.working_frame_index
            for frame in self.working_series.frames
            if frame.working_frame_index != int(working_frame_index)
        ]
        old_to_new_index = {
            old_index: new_index
            for new_index, old_index in enumerate(remaining_old_indices)
        }
        remapped_scoped_regions = []
        for scoped_region in self.frame_scoped_analysis_regions:
            remapped_indices = tuple(
                old_to_new_index[index]
                for index in scoped_region.working_frame_indices
                if index in old_to_new_index
            )
            if remapped_indices:
                remapped_scoped_regions.append(
                    FrameScopedAnalysisRegion(
                        region=scoped_region.region,
                        working_frame_indices=remapped_indices,
                    )
                )
        remapped_registration_shifts = tuple(
            RegistrationShift(
                working_frame_index=old_to_new_index[shift.working_frame_index],
                dx=shift.dx,
                dy=shift.dy,
                method=shift.method,
            )
            for shift in self.registration_shifts
            if shift.working_frame_index in old_to_new_index
        )
        return MolTrackProject(
            source_series=self.source_series,
            working_series=working_series,
            project_name=self.project_name,
            analysis_regions=self.analysis_regions,
            copied_analysis_regions=tuple(
                CopiedAnalysisRegion.from_working_series(copied_region.region, working_series)
                for copied_region in self.copied_analysis_regions
            ),
            frame_scoped_analysis_regions=tuple(remapped_scoped_regions),
            registration_shifts=remapped_registration_shifts,
        )

    def with_analysis_regions(
        self,
        analysis_regions: tuple[AnalysisRegion, ...],
        *,
        copied_analysis_regions: tuple[CopiedAnalysisRegion, ...] = (),
        frame_scoped_analysis_regions: tuple[FrameScopedAnalysisRegion, ...] | None = None,
        registration_shifts: tuple[RegistrationShift, ...] | None = None,
    ) -> MolTrackProject:
        return MolTrackProject(
            source_series=self.source_series,
            working_series=self.working_series,
            project_name=self.project_name,
            analysis_regions=tuple(analysis_regions),
            copied_analysis_regions=tuple(copied_analysis_regions),
            frame_scoped_analysis_regions=(
                self.frame_scoped_analysis_regions
                if frame_scoped_analysis_regions is None
                else tuple(frame_scoped_analysis_regions)
            ),
            registration_shifts=(
                self.registration_shifts
                if registration_shifts is None
                else tuple(registration_shifts)
            ),
        )

    def with_frame_scoped_analysis_regions(
        self,
        frame_scoped_analysis_regions: tuple[FrameScopedAnalysisRegion, ...],
    ) -> MolTrackProject:
        return MolTrackProject(
            source_series=self.source_series,
            working_series=self.working_series,
            project_name=self.project_name,
            analysis_regions=self.analysis_regions,
            copied_analysis_regions=self.copied_analysis_regions,
            frame_scoped_analysis_regions=tuple(frame_scoped_analysis_regions),
            registration_shifts=self.registration_shifts,
        )

    def with_registration_shifts(
        self,
        registration_shifts: tuple[RegistrationShift, ...],
    ) -> MolTrackProject:
        return MolTrackProject(
            source_series=self.source_series,
            working_series=self.working_series,
            project_name=self.project_name,
            analysis_regions=self.analysis_regions,
            copied_analysis_regions=self.copied_analysis_regions,
            frame_scoped_analysis_regions=self.frame_scoped_analysis_regions,
            registration_shifts=tuple(registration_shifts),
        )

    def analysis_regions_for_working_frame(self, working_frame_index: int) -> tuple[AnalysisRegion, ...]:
        working_frame_index = int(working_frame_index)
        self.working_series.get_working_frame(working_frame_index)
        scoped_regions = [
            scoped_region.region
            for scoped_region in self.frame_scoped_analysis_regions
            if scoped_region.applies_to_working_frame(working_frame_index)
        ]
        scoped_names = {region.name for region in scoped_regions}
        inherited_global_regions = [
            region
            for region in self.analysis_regions
            if region.name not in scoped_names
        ]
        return tuple(_sort_regions_by_priority(scoped_regions + inherited_global_regions))

    def region_for_working_frame(self, region_name: str, working_frame_index: int) -> AnalysisRegion:
        region_name = str(region_name)
        for region in self.analysis_regions_for_working_frame(working_frame_index):
            if region.name == region_name:
                return region
        raise KeyError(f"Unknown analysis region for frame {working_frame_index}: {region_name}")

    def registration_shift_for_working_frame(self, working_frame_index: int) -> RegistrationShift | None:
        working_frame_index = int(working_frame_index)
        self.working_series.get_working_frame(working_frame_index)
        for shift in self.registration_shifts:
            if shift.working_frame_index == working_frame_index:
                return shift
        return None


def _sort_regions_by_priority(regions: list[AnalysisRegion]) -> list[AnalysisRegion]:
    priority = {
        AnalysisRegionKind.IGNORE: 0,
        AnalysisRegionKind.STEP_EDGE: 1,
        AnalysisRegionKind.TERRACE: 2,
        AnalysisRegionKind.CUSTOM: 3,
    }
    return sorted(regions, key=lambda region: (priority[region.kind], region.name))


def _validate_frame_scoped_regions(
    frame_scoped_analysis_regions: tuple[FrameScopedAnalysisRegion, ...],
    working_series: WorkingImageSeries,
) -> None:
    frames_by_region_name: dict[str, set[int]] = {}
    for scoped_region in frame_scoped_analysis_regions:
        frames = frames_by_region_name.setdefault(scoped_region.region.name, set())
        for working_frame_index in scoped_region.working_frame_indices:
            working_series.get_working_frame(working_frame_index)
            if working_frame_index in frames:
                raise ValueError(
                    f"Region {scoped_region.region.name!r} has overlapping frame scopes."
                )
            frames.add(working_frame_index)


def _validate_registration_shifts(
    registration_shifts: tuple[RegistrationShift, ...],
    working_series: WorkingImageSeries,
) -> tuple[RegistrationShift, ...]:
    shifts_by_working_frame_index: dict[int, RegistrationShift] = {}
    for shift in registration_shifts:
        working_series.get_working_frame(shift.working_frame_index)
        if shift.working_frame_index in shifts_by_working_frame_index:
            raise ValueError(
                f"Duplicate RegistrationShift for working frame {shift.working_frame_index}."
            )
        shifts_by_working_frame_index[shift.working_frame_index] = shift
    return tuple(
        shifts_by_working_frame_index[index]
        for index in sorted(shifts_by_working_frame_index)
    )
