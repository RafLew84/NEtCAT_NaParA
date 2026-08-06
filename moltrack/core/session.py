from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .data_models import MolTrackImageSeries
from .detections import MolecularDetectionSet
from .registration import MolTrackRegistrationResultSet, MolTrackRegistrationSettings
from .segmentations import MolecularSegmentationSet

if TYPE_CHECKING:
    from moltrack.analysis import (
        M6DomainTypeSessionState,
        MolecularOrientationStore,
        MolecularOrderTypeSessionState,
        MolecularStackingSessionState,
        MolecularM6SessionState,
        StructuralAnalysisCacheRecord,
        TextureDomainSessionState,
    )
    from moltrack.analysis.domain_analysis.session_state import (
        DomainAnalysisSessionState,
    )


MOLTRACK_SESSION_SCHEMA_VERSION = 2
SUPPORTED_MOLTRACK_SESSION_SCHEMA_VERSIONS = (1, 2)
SUPPORTED_SESSION_REGISTRATION_VIEW_MODES = ("Show raw", "Show expanded aligned")
SUPPORTED_POSITION_ANALYSIS_SOURCE_VIEWS = ("raw", "expanded_aligned")
SUPPORTED_POSITION_ANALYSIS_TABS = (
    "Current frame",
    "Range trends",
    "Spatial comparison",
    "Sixfold Bond Order",
    "Domain Types",
    "Texture Domains",
)
SUPPORTED_POSITION_ANALYSIS_INTENSITY_METRICS = (
    "background_corrected_median",
    "background_corrected_mean",
    "mean",
    "median",
    "max",
    "sum",
)


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
    intensity_metric: str = "background_corrected_median"
    color_points_by_intensity: bool = True
    background_inner_radius_px: int = 1
    background_outer_radius_px: int = 3
    shared_intensity_scale: bool = True

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
        intensity_metric = str(self.intensity_metric).strip()
        if intensity_metric not in SUPPORTED_POSITION_ANALYSIS_INTENSITY_METRICS:
            raise ValueError(
                f"Unsupported Position Analysis intensity_metric: {intensity_metric!r}."
            )
        background_inner_radius_px = int(self.background_inner_radius_px)
        background_outer_radius_px = int(self.background_outer_radius_px)
        if background_inner_radius_px < 0:
            raise ValueError("background_inner_radius_px must be non-negative.")
        if background_outer_radius_px <= background_inner_radius_px:
            raise ValueError(
                "background_outer_radius_px must be greater than background_inner_radius_px."
            )
        object.__setattr__(self, "source_view", source_view)
        object.__setattr__(self, "comparison_completed", bool(self.comparison_completed))
        object.__setattr__(self, "active_tab", active_tab)
        object.__setattr__(self, "density_grid_shape", (rows, columns))
        object.__setattr__(
            self,
            "use_segmentation_centroids",
            bool(self.use_segmentation_centroids),
        )
        object.__setattr__(self, "intensity_metric", intensity_metric)
        object.__setattr__(
            self,
            "color_points_by_intensity",
            bool(self.color_points_by_intensity),
        )
        object.__setattr__(self, "background_inner_radius_px", background_inner_radius_px)
        object.__setattr__(self, "background_outer_radius_px", background_outer_radius_px)
        object.__setattr__(self, "shared_intensity_scale", bool(self.shared_intensity_scale))


@dataclass(frozen=True)
class MolTrackIntensityCacheRecord:
    """Serializable numeric intensity result guarded by an annotation fingerprint."""

    frame_index: int
    source_view: str
    source_kind: str
    source_id: str
    unit: str
    background_inner_radius_px: int
    background_outer_radius_px: int
    annotation_fingerprint: str
    pixel_count: int
    sum: float | None
    mean: float | None
    median: float | None
    max: float | None
    local_background_median: float | None
    background_corrected_mean: float | None
    background_corrected_median: float | None

    def __post_init__(self) -> None:
        frame_index = int(self.frame_index)
        if frame_index < 0:
            raise ValueError("Intensity cache frame_index must be non-negative.")
        source_view = str(self.source_view).strip()
        if source_view not in SUPPORTED_POSITION_ANALYSIS_SOURCE_VIEWS:
            raise ValueError(f"Unsupported intensity cache source_view: {source_view!r}.")
        source_kind = str(self.source_kind).strip()
        if source_kind not in ("segmentation", "bbox"):
            raise ValueError(f"Unsupported intensity cache source_kind: {source_kind!r}.")
        source_id = str(self.source_id).strip()
        annotation_fingerprint = str(self.annotation_fingerprint).strip()
        if not source_id or not annotation_fingerprint:
            raise ValueError("Intensity cache source_id and annotation_fingerprint must not be empty.")
        inner_radius = int(self.background_inner_radius_px)
        outer_radius = int(self.background_outer_radius_px)
        if inner_radius < 0 or outer_radius <= inner_radius:
            raise ValueError("Intensity cache background radii are invalid.")
        pixel_count = int(self.pixel_count)
        if pixel_count < 0:
            raise ValueError("Intensity cache pixel_count must be non-negative.")
        object.__setattr__(self, "frame_index", frame_index)
        object.__setattr__(self, "source_view", source_view)
        object.__setattr__(self, "source_kind", source_kind)
        object.__setattr__(self, "source_id", source_id)
        object.__setattr__(self, "unit", str(self.unit))
        object.__setattr__(self, "background_inner_radius_px", inner_radius)
        object.__setattr__(self, "background_outer_radius_px", outer_radius)
        object.__setattr__(self, "annotation_fingerprint", annotation_fingerprint)
        object.__setattr__(self, "pixel_count", pixel_count)


@dataclass(frozen=True)
class MolTrackSession:
    """Serializable state needed to restore a MolTrack working session."""

    source_path: str
    source_frame_indices: tuple[int, ...]
    active_frame_index: int
    reverse_frame_order: bool = False
    registration_view_mode: str = "Show raw"
    bbox_overlay_visible: bool = True
    bbox_opacity_percent: int = 100
    mask_opacity_percent: int = 30
    registration_settings: MolTrackRegistrationSettings | None = None
    registration_results: MolTrackRegistrationResultSet | None = None
    molecular_detections: MolecularDetectionSet | None = None
    molecular_segmentations: MolecularSegmentationSet | None = None
    molecular_orientations: MolecularOrientationStore | None = None
    position_analysis: MolTrackPositionAnalysisState | None = None
    intensity_cache_records: tuple[MolTrackIntensityCacheRecord, ...] = ()
    domain_analysis_state: DomainAnalysisSessionState | None = None
    m6_analysis_state: MolecularM6SessionState | None = None
    m6_domain_type_analysis_state: M6DomainTypeSessionState | None = None
    molecular_stacking_state: MolecularStackingSessionState | None = None
    molecular_order_type_analysis_state: (
        MolecularOrderTypeSessionState | None
    ) = None
    texture_domain_analysis_state: TextureDomainSessionState | None = None
    structural_analysis_cache_records: tuple[
        StructuralAnalysisCacheRecord, ...
    ] = ()
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
        if schema_version not in SUPPORTED_MOLTRACK_SESSION_SCHEMA_VERSIONS:
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
        if self.molecular_orientations is not None:
            from moltrack.analysis import MolecularOrientationStore

            if not isinstance(
                self.molecular_orientations,
                MolecularOrientationStore,
            ):
                raise TypeError(
                    "molecular_orientations must be a MolecularOrientationStore."
                )
        if self.position_analysis is not None and not isinstance(
            self.position_analysis, MolTrackPositionAnalysisState
        ):
            raise TypeError("position_analysis must be a MolTrackPositionAnalysisState instance.")
        _validate_domain_analysis_state(self.domain_analysis_state, schema_version=schema_version, frame_count=len(source_frame_indices))
        if self.molecular_stacking_state is not None:
            from moltrack.analysis import MolecularStackingSessionState

            if not isinstance(
                self.molecular_stacking_state,
                MolecularStackingSessionState,
            ):
                raise TypeError(
                    "molecular_stacking_state must be a "
                    "MolecularStackingSessionState."
                )
        if self.molecular_order_type_analysis_state is not None:
            from moltrack.analysis import MolecularOrderTypeSessionState

            if not isinstance(
                self.molecular_order_type_analysis_state,
                MolecularOrderTypeSessionState,
            ):
                raise TypeError(
                    "molecular_order_type_analysis_state must be a "
                    "MolecularOrderTypeSessionState."
                )
        if self.texture_domain_analysis_state is not None:
            from moltrack.analysis import TextureDomainSessionState

            if not isinstance(
                self.texture_domain_analysis_state,
                TextureDomainSessionState,
            ):
                raise TypeError(
                    "texture_domain_analysis_state must be a "
                    "TextureDomainSessionState."
                )
        intensity_cache_records = tuple(self.intensity_cache_records)
        if not all(
            isinstance(record, MolTrackIntensityCacheRecord)
            for record in intensity_cache_records
        ):
            raise TypeError(
                "intensity_cache_records must contain MolTrackIntensityCacheRecord instances."
            )
        if any(record.frame_index >= len(source_frame_indices) for record in intensity_cache_records):
            raise ValueError("Intensity cache record exceeds source_frame_indices length.")
        structural_analysis_cache_records = tuple(
            self.structural_analysis_cache_records
        )
        if any(
            not hasattr(record, "cache_key")
            or not hasattr(record, "sample_coordinates")
            or not hasattr(record, "settings")
            for record in structural_analysis_cache_records
        ):
            raise TypeError(
                "structural_analysis_cache_records must contain M6 cache records."
            )
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
        if (
            self.molecular_orientations is not None
            and int(self.molecular_orientations.frame_count)
            != len(source_frame_indices)
        ):
            raise ValueError(
                "molecular_orientations do not match source_frame_indices length."
            )
        if self.position_analysis is not None:
            for frame_range in (
                self.position_analysis.first_range,
                self.position_analysis.second_range,
            ):
                if frame_range.end_frame >= len(source_frame_indices):
                    raise ValueError("Position Analysis range exceeds source_frame_indices length.")
        if (
            self.molecular_stacking_state is not None
            and self.molecular_stacking_state.status == "computed"
        ):
            prototype = self.molecular_stacking_state.prototype_analysis
            assert prototype is not None
            if any(
                frame_index >= len(source_frame_indices)
                for frame_index in prototype.input_frame_indices
            ):
                raise ValueError(
                    "Molecular stacking frame exceeds "
                    "source_frame_indices length."
                )
        if self.molecular_order_type_analysis_state is not None:
            scope = self.molecular_order_type_analysis_state.analysis_scope
            if scope.frame_count != len(source_frame_indices):
                raise ValueError(
                    "Molecular-order type scope does not match "
                    "source_frame_indices length."
                )
        if self.texture_domain_analysis_state is not None:
            if self.texture_domain_analysis_state.range_end_frame >= len(
                source_frame_indices
            ):
                raise ValueError(
                    "Texture-domain range exceeds source_frame_indices length."
                )

        object.__setattr__(self, "source_path", source_path)
        object.__setattr__(self, "source_frame_indices", source_frame_indices)
        object.__setattr__(self, "active_frame_index", active_frame_index)
        object.__setattr__(self, "reverse_frame_order", bool(self.reverse_frame_order))
        object.__setattr__(self, "registration_view_mode", registration_view_mode)
        object.__setattr__(self, "bbox_overlay_visible", bool(self.bbox_overlay_visible))
        object.__setattr__(self, "bbox_opacity_percent", bbox_opacity_percent)
        object.__setattr__(self, "mask_opacity_percent", mask_opacity_percent)
        object.__setattr__(self, "source_size_bytes", source_size_bytes)
        object.__setattr__(self, "source_mtime_ns", source_mtime_ns)
        object.__setattr__(self, "intensity_cache_records", intensity_cache_records)
        object.__setattr__(
            self,
            "structural_analysis_cache_records",
            structural_analysis_cache_records,
        )
        object.__setattr__(self, "schema_version", schema_version)

    @classmethod
    def from_image_series(
        cls,
        series: MolTrackImageSeries,
        *,
        registration_view_mode: str = "Show raw",
        bbox_overlay_visible: bool = True,
        bbox_opacity_percent: int = 100,
        mask_opacity_percent: int = 30,
        position_analysis: MolTrackPositionAnalysisState | None = None,
        intensity_cache_records: tuple[MolTrackIntensityCacheRecord, ...] = (),
        domain_analysis_state: DomainAnalysisSessionState | None = None,
        m6_analysis_state: MolecularM6SessionState | None = None,
        m6_domain_type_analysis_state: M6DomainTypeSessionState | None = None,
        molecular_stacking_state: MolecularStackingSessionState | None = None,
        molecular_order_type_analysis_state: (
            MolecularOrderTypeSessionState | None
        ) = None,
        texture_domain_analysis_state: TextureDomainSessionState | None = None,
        structural_analysis_cache_records: tuple[
            StructuralAnalysisCacheRecord, ...
        ] = (),
        source_size_bytes: int | None = None,
        source_mtime_ns: int | None = None,
    ) -> "MolTrackSession":
        if not isinstance(series, MolTrackImageSeries):
            raise TypeError("series must be a MolTrackImageSeries instance.")
        if m6_analysis_state is None:
            m6_analysis_state = series.m6_analysis_state
        if molecular_stacking_state is None:
            molecular_stacking_state = series.molecular_stacking_state
        if molecular_order_type_analysis_state is None:
            molecular_order_type_analysis_state = (
                series.molecular_order_type_state
            )
        if texture_domain_analysis_state is None:
            texture_domain_analysis_state = series.texture_domain_state
        source_frame_indices = series.source_frame_indices
        if source_frame_indices is None:
            raise RuntimeError(
                "MolTrackImageSeries did not normalize source_frame_indices."
            )
        registration_results = series.registration_results
        registration_settings = registration_results.settings if registration_results is not None else None
        return cls(
            source_path=series.source_path,
            source_frame_indices=source_frame_indices,
            active_frame_index=series.active_frame_index,
            reverse_frame_order=series.reverse_frame_order,
            registration_view_mode=registration_view_mode,
            bbox_overlay_visible=bbox_overlay_visible,
            bbox_opacity_percent=bbox_opacity_percent,
            mask_opacity_percent=mask_opacity_percent,
            registration_settings=registration_settings,
            registration_results=registration_results,
            molecular_detections=series.molecular_detections,
            molecular_segmentations=series.molecular_segmentations,
            molecular_orientations=series.molecular_orientations,
            position_analysis=position_analysis,
            intensity_cache_records=intensity_cache_records,
            domain_analysis_state=domain_analysis_state,
            m6_analysis_state=m6_analysis_state,
            m6_domain_type_analysis_state=m6_domain_type_analysis_state,
            molecular_stacking_state=molecular_stacking_state,
            molecular_order_type_analysis_state=(
                molecular_order_type_analysis_state
            ),
            texture_domain_analysis_state=texture_domain_analysis_state,
            structural_analysis_cache_records=structural_analysis_cache_records,
            source_size_bytes=source_size_bytes,
            source_mtime_ns=source_mtime_ns,
        )


def _validate_domain_analysis_state(
    state: DomainAnalysisSessionState | None,
    *,
    schema_version: int,
    frame_count: int,
) -> None:
    if state is None:
        return
    from moltrack.analysis.domain_analysis.session_state import (
        DomainAnalysisSessionState,
    )

    if not isinstance(state, DomainAnalysisSessionState):
        raise TypeError(
            "domain_analysis_state must be a DomainAnalysisSessionState."
        )
    if schema_version == 1:
        raise ValueError(
            "MolTrack session schema v1 cannot own Domain Analysis state."
        )
    draft = state.draft
    if draft is not None and draft.frame_range.stop > frame_count:
        raise ValueError(
            "Domain Analysis draft range exceeds source_frame_indices length."
        )
    publication = state.published_result
    if (
        publication is not None
        and publication.request.frame_range.stop > frame_count
    ):
        raise ValueError(
            "Domain Analysis range exceeds source_frame_indices length."
        )


def _normalize_optional_non_negative_int(value: int | None, name: str) -> int | None:
    if value is None:
        return None
    normalized = int(value)
    if normalized < 0:
        raise ValueError(f"{name} must be non-negative.")
    return normalized
