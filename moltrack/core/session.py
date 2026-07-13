from __future__ import annotations

from dataclasses import dataclass

from .data_models import MolTrackImageSeries
from .detections import MolecularDetectionSet
from .registration import MolTrackRegistrationResultSet, MolTrackRegistrationSettings
from .segmentations import MolecularSegmentationSet


MOLTRACK_SESSION_SCHEMA_VERSION = 1
SUPPORTED_SESSION_REGISTRATION_VIEW_MODES = ("Show raw", "Show expanded aligned")
SUPPORTED_POSITION_ANALYSIS_SOURCE_VIEWS = ("raw", "expanded_aligned")
SUPPORTED_POSITION_ANALYSIS_TABS = ("Current frame", "Range trends", "Spatial comparison")


@dataclass(frozen=True)
class MolTrackPositionAnalysisRange:
    """Serializable inclusive frame range used by Position Analysis."""

    name: str
    start_frame: int
    end_frame: int

    def __post_init__(self) -> None:
        name = str(self.name).strip()
        start_frame = int(self.start_frame)
        end_frame = int(self.end_frame)
        if not name:
            raise ValueError("Position Analysis range name must not be empty.")
        if start_frame < 0 or start_frame > end_frame:
            raise ValueError("Position Analysis range start_frame must not exceed end_frame.")
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "start_frame", start_frame)
        object.__setattr__(self, "end_frame", end_frame)

    @property
    def frame_indices(self) -> tuple[int, ...]:
        return tuple(range(self.start_frame, self.end_frame + 1))


@dataclass(frozen=True)
class MolTrackPositionAnalysisState:
    """Serializable Position Analysis configuration; derived metrics are recomputed."""

    source_view: str
    first_range: MolTrackPositionAnalysisRange
    second_range: MolTrackPositionAnalysisRange
    comparison_completed: bool = False
    active_tab: str = "Current frame"
    density_grid_shape: tuple[int, int] = (32, 32)
    use_segmentation_centroids: bool = True

    def __post_init__(self) -> None:
        source_view = str(self.source_view).strip()
        if source_view not in SUPPORTED_POSITION_ANALYSIS_SOURCE_VIEWS:
            raise ValueError(f"Unsupported Position Analysis source_view: {source_view!r}.")
        if not isinstance(self.first_range, MolTrackPositionAnalysisRange) or not isinstance(
            self.second_range, MolTrackPositionAnalysisRange
        ):
            raise TypeError("Position Analysis ranges must be MolTrackPositionAnalysisRange instances.")
        active_tab = str(self.active_tab).strip()
        if active_tab not in SUPPORTED_POSITION_ANALYSIS_TABS:
            raise ValueError(f"Unsupported Position Analysis active_tab: {active_tab!r}.")
        try:
            rows, columns = (int(value) for value in self.density_grid_shape)
        except (TypeError, ValueError) as exc:
            raise ValueError("density_grid_shape must contain rows and columns.") from exc
        if rows <= 0 or columns <= 0:
            raise ValueError("density_grid_shape values must be positive.")
        object.__setattr__(self, "source_view", source_view)
        object.__setattr__(self, "comparison_completed", bool(self.comparison_completed))
        object.__setattr__(self, "active_tab", active_tab)
        object.__setattr__(self, "density_grid_shape", (rows, columns))
        object.__setattr__(
            self,
            "use_segmentation_centroids",
            bool(self.use_segmentation_centroids),
        )


@dataclass(frozen=True)
class MolTrackSession:
    """Serializable state needed to restore a MolTrack working session."""

    source_path: str
    source_frame_indices: tuple[int, ...]
    active_frame_index: int
    reverse_frame_order: bool = False
    registration_view_mode: str = "Show raw"
    bbox_opacity_percent: int = 100
    mask_opacity_percent: int = 30
    registration_settings: MolTrackRegistrationSettings | None = None
    registration_results: MolTrackRegistrationResultSet | None = None
    molecular_detections: MolecularDetectionSet | None = None
    molecular_segmentations: MolecularSegmentationSet | None = None
    position_analysis: MolTrackPositionAnalysisState | None = None
    source_size_bytes: int | None = None
    source_mtime_ns: int | None = None
    schema_version: int = MOLTRACK_SESSION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        source_path = str(self.source_path)
        if not source_path:
            raise ValueError("source_path must be a non-empty string.")
        source_frame_indices = tuple(int(index) for index in self.source_frame_indices)
        if not source_frame_indices:
            raise ValueError("source_frame_indices must contain at least one frame index.")
        if any(index < 0 for index in source_frame_indices):
            raise ValueError("source_frame_indices must be non-negative.")
        if len(set(source_frame_indices)) != len(source_frame_indices):
            raise ValueError("source_frame_indices must not contain duplicates.")

        active_frame_index = int(self.active_frame_index)
        if not 0 <= active_frame_index < len(source_frame_indices):
            raise IndexError("active_frame_index is out of source_frame_indices range.")

        registration_view_mode = str(self.registration_view_mode).strip()
        if registration_view_mode not in SUPPORTED_SESSION_REGISTRATION_VIEW_MODES:
            supported = ", ".join(SUPPORTED_SESSION_REGISTRATION_VIEW_MODES)
            raise ValueError(f"Unsupported registration_view_mode: {registration_view_mode!r}. Supported: {supported}.")

        bbox_opacity_percent = int(self.bbox_opacity_percent)
        if not 0 <= bbox_opacity_percent <= 100:
            raise ValueError("bbox_opacity_percent must be between 0 and 100.")
        mask_opacity_percent = int(self.mask_opacity_percent)
        if not 0 <= mask_opacity_percent <= 100:
            raise ValueError("mask_opacity_percent must be between 0 and 100.")

        schema_version = int(self.schema_version)
        if schema_version != MOLTRACK_SESSION_SCHEMA_VERSION:
            raise ValueError(f"Unsupported MolTrack session schema_version: {schema_version}.")

        source_size_bytes = _normalize_optional_non_negative_int(self.source_size_bytes, "source_size_bytes")
        source_mtime_ns = _normalize_optional_non_negative_int(self.source_mtime_ns, "source_mtime_ns")

        if self.registration_settings is not None and not isinstance(
            self.registration_settings, MolTrackRegistrationSettings
        ):
            raise TypeError("registration_settings must be a MolTrackRegistrationSettings instance.")
        if self.registration_results is not None and not isinstance(
            self.registration_results, MolTrackRegistrationResultSet
        ):
            raise TypeError("registration_results must be a MolTrackRegistrationResultSet instance.")
        if self.molecular_detections is not None and not isinstance(
            self.molecular_detections, MolecularDetectionSet
        ):
            raise TypeError("molecular_detections must be a MolecularDetectionSet instance.")
        if self.molecular_segmentations is not None and not isinstance(
            self.molecular_segmentations, MolecularSegmentationSet
        ):
            raise TypeError("molecular_segmentations must be a MolecularSegmentationSet instance.")
        if self.position_analysis is not None and not isinstance(
            self.position_analysis, MolTrackPositionAnalysisState
        ):
            raise TypeError("position_analysis must be a MolTrackPositionAnalysisState instance.")
        if self.registration_results is not None:
            expected = tuple(range(len(source_frame_indices)))
            if self.registration_results.frame_indices != expected:
                raise ValueError("registration_results do not match source_frame_indices length.")
            if self.registration_settings is not None and self.registration_results.settings != self.registration_settings:
                raise ValueError("registration_settings must match registration_results.settings.")
        if self.molecular_detections is not None and self.molecular_detections.frame_count != len(source_frame_indices):
            raise ValueError("molecular_detections do not match source_frame_indices length.")
        if (
            self.molecular_segmentations is not None
            and self.molecular_segmentations.frame_count != len(source_frame_indices)
        ):
            raise ValueError("molecular_segmentations do not match source_frame_indices length.")
        if self.position_analysis is not None:
            for frame_range in (
                self.position_analysis.first_range,
                self.position_analysis.second_range,
            ):
                if frame_range.end_frame >= len(source_frame_indices):
                    raise ValueError("Position Analysis range exceeds source_frame_indices length.")

        object.__setattr__(self, "source_path", source_path)
        object.__setattr__(self, "source_frame_indices", source_frame_indices)
        object.__setattr__(self, "active_frame_index", active_frame_index)
        object.__setattr__(self, "reverse_frame_order", bool(self.reverse_frame_order))
        object.__setattr__(self, "registration_view_mode", registration_view_mode)
        object.__setattr__(self, "bbox_opacity_percent", bbox_opacity_percent)
        object.__setattr__(self, "mask_opacity_percent", mask_opacity_percent)
        object.__setattr__(self, "source_size_bytes", source_size_bytes)
        object.__setattr__(self, "source_mtime_ns", source_mtime_ns)
        object.__setattr__(self, "schema_version", schema_version)

    @classmethod
    def from_image_series(
        cls,
        series: MolTrackImageSeries,
        *,
        registration_view_mode: str = "Show raw",
        bbox_opacity_percent: int = 100,
        mask_opacity_percent: int = 30,
        position_analysis: MolTrackPositionAnalysisState | None = None,
        source_size_bytes: int | None = None,
        source_mtime_ns: int | None = None,
    ) -> "MolTrackSession":
        if not isinstance(series, MolTrackImageSeries):
            raise TypeError("series must be a MolTrackImageSeries instance.")
        registration_results = series.registration_results
        registration_settings = registration_results.settings if registration_results is not None else None
        return cls(
            source_path=series.source_path,
            source_frame_indices=series.source_frame_indices,
            active_frame_index=series.active_frame_index,
            reverse_frame_order=series.reverse_frame_order,
            registration_view_mode=registration_view_mode,
            bbox_opacity_percent=bbox_opacity_percent,
            mask_opacity_percent=mask_opacity_percent,
            registration_settings=registration_settings,
            registration_results=registration_results,
            molecular_detections=series.molecular_detections,
            molecular_segmentations=series.molecular_segmentations,
            position_analysis=position_analysis,
            source_size_bytes=source_size_bytes,
            source_mtime_ns=source_mtime_ns,
        )


def _normalize_optional_non_negative_int(value: int | None, name: str) -> int | None:
    if value is None:
        return None
    normalized = int(value)
    if normalized < 0:
        raise ValueError(f"{name} must be non-negative.")
    return normalized
