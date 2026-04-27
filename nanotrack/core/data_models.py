"""Core data models for NanoTrack sequence and annotation handling."""

from __future__ import annotations

import os
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any, Dict, Optional, Tuple

import numpy as np


@dataclass(frozen=True)
class STMSequenceMetadata:
    """Physical and timing metadata shared by all frames in an MPP sequence."""

    raw_header: Dict[str, Any] = field(default_factory=dict, repr=False)
    pixels_x: int = 0
    pixels_y: int = 0
    size_nm_x: float = 0.0
    size_nm_y: float = 0.0
    offset_nm_x: float = 0.0
    offset_nm_y: float = 0.0
    scan_angle_deg: float = 0.0
    bias_v: float = 0.0
    setpoint_a: Optional[float] = None
    image_type: str = "Unknown"
    frame_interval_s: Optional[float] = None
    frame_times_s: Optional[np.ndarray] = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self.pixels_x < 0 or self.pixels_y < 0:
            raise ValueError("Pixel dimensions must be non-negative.")
        if self.frame_interval_s is not None and self.frame_interval_s < 0:
            raise ValueError("Frame interval must be non-negative.")
        if self.frame_times_s is not None:
            frame_times = np.asarray(self.frame_times_s, dtype=np.float64)
            if frame_times.ndim != 1:
                raise ValueError("frame_times_s must be a 1D array.")
            object.__setattr__(self, "frame_times_s", frame_times)

    def get_pixel_size_nm(self) -> Tuple[Optional[float], Optional[float]]:
        """Return pixel size in nanometers for x and y directions."""
        px_x = self.size_nm_x / self.pixels_x if self.pixels_x > 0 and self.size_nm_x > 0 else None
        px_y = self.size_nm_y / self.pixels_y if self.pixels_y > 0 and self.size_nm_y > 0 else None
        return px_x, px_y


@dataclass
class STMSequence:
    """Sequence container for MPP-derived STM frames."""

    source_path: str
    raw_frames: np.ndarray = field(repr=False)
    metadata: STMSequenceMetadata
    active_frame_index: int = 0
    reverse_frame_order: bool = False
    excluded_frame_indices: set[int] = field(default_factory=set, repr=False)

    def __post_init__(self) -> None:
        frames = np.asarray(self.raw_frames)
        if frames.ndim != 3:
            raise ValueError("raw_frames must have shape [T, H, W].")
        if frames.shape[0] == 0:
            raise ValueError("raw_frames must contain at least one frame.")
        self.raw_frames = frames

        frame_count, pixels_y, pixels_x = frames.shape
        if self.metadata.frame_times_s is not None and len(self.metadata.frame_times_s) != frame_count:
            raise ValueError("frame_times_s length must match the number of frames.")

        needs_shape_inference = self.metadata.pixels_x == 0 or self.metadata.pixels_y == 0
        if needs_shape_inference:
            self.metadata = replace(
                self.metadata,
                pixels_x=self.metadata.pixels_x or pixels_x,
                pixels_y=self.metadata.pixels_y or pixels_y,
            )

        if self.metadata.pixels_x != pixels_x or self.metadata.pixels_y != pixels_y:
            raise ValueError("Metadata pixel dimensions must match raw_frames shape.")
        if not 0 <= self.active_frame_index < frame_count:
            raise IndexError("active_frame_index is out of range.")
        self.reverse_frame_order = bool(self.reverse_frame_order)
        excluded = {int(frame_index) for frame_index in self.excluded_frame_indices}
        for frame_index in excluded:
            if not 0 <= frame_index < frame_count:
                raise IndexError("excluded_frame_indices contains an out-of-range frame index.")
        self.excluded_frame_indices = excluded

    @property
    def file_name(self) -> str:
        """Return the basename of the source file."""
        return os.path.basename(self.source_path)

    @property
    def frame_count(self) -> int:
        """Number of frames in the sequence."""
        return int(self.raw_frames.shape[0])

    @property
    def frame_shape(self) -> tuple[int, int]:
        """Height and width of a single frame."""
        return int(self.raw_frames.shape[1]), int(self.raw_frames.shape[2])

    @property
    def active_frame(self) -> np.ndarray:
        """Currently selected raw frame."""
        return self.raw_frames[self.active_frame_index]

    @property
    def active_frame_time_s(self) -> Optional[float]:
        """Timestamp of the active frame if timing metadata is available."""
        return self.get_frame_time_s(self.active_frame_index)

    def set_active_frame(self, frame_index: int) -> None:
        """Update the currently active frame index."""
        if not 0 <= frame_index < self.frame_count:
            raise IndexError("frame_index is out of range.")
        self.active_frame_index = frame_index

    def get_frame(self, frame_index: int) -> np.ndarray:
        """Return raw frame by index."""
        if not 0 <= frame_index < self.frame_count:
            raise IndexError("frame_index is out of range.")
        return self.raw_frames[frame_index]

    def get_frame_time_s(self, frame_index: int) -> Optional[float]:
        """Return timestamp for a frame index if available."""
        if not 0 <= frame_index < self.frame_count:
            raise IndexError("frame_index is out of range.")
        if self.metadata.frame_times_s is not None:
            return float(self.metadata.frame_times_s[frame_index])
        if self.metadata.frame_interval_s is not None:
            return float(frame_index * self.metadata.frame_interval_s)
        return None

    def is_frame_excluded(self, frame_index: int) -> bool:
        if not 0 <= frame_index < self.frame_count:
            raise IndexError("frame_index is out of range.")
        return int(frame_index) in self.excluded_frame_indices

    def set_frame_excluded(self, frame_index: int, excluded: bool = True) -> None:
        if not 0 <= frame_index < self.frame_count:
            raise IndexError("frame_index is out of range.")
        frame_index = int(frame_index)
        if excluded:
            self.excluded_frame_indices.add(frame_index)
        else:
            self.excluded_frame_indices.discard(frame_index)

    def included_frame_indices(self) -> list[int]:
        return [frame_index for frame_index in range(self.frame_count) if frame_index not in self.excluded_frame_indices]

    def sorted_excluded_frame_indices(self) -> list[int]:
        return sorted(self.excluded_frame_indices)


@dataclass
class RegistrationSettings:
    """Configuration used to estimate global frame-to-frame registration shifts."""

    backend: str = "phase_correlation"
    reference_strategy: str = "adjacent"
    registration_view: str = "raw"
    roi_mask: Optional[np.ndarray] = field(default=None, repr=False)
    backend_params: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.backend = str(self.backend).strip()
        self.reference_strategy = str(self.reference_strategy).strip()
        self.registration_view = str(self.registration_view).strip()
        if not self.backend:
            raise ValueError("backend must be a non-empty string.")
        if not self.reference_strategy:
            raise ValueError("reference_strategy must be a non-empty string.")
        if not self.registration_view:
            raise ValueError("registration_view must be a non-empty string.")
        if self.roi_mask is not None:
            roi_mask = np.asarray(self.roi_mask, dtype=bool)
            if roi_mask.ndim != 2:
                raise ValueError("roi_mask must be a 2D boolean image.")
            self.roi_mask = roi_mask
        self.backend_params = dict(self.backend_params)


@dataclass
class RegistrationFrameResult:
    """One translation-only registration estimate for a single frame."""

    frame_index: int
    shift_xy: tuple[float, float] | np.ndarray
    method: str
    quality_score: float = 0.0
    phase_peak_ratio: Optional[float] = None
    ecc_score: Optional[float] = None
    num_inlier_tiles: Optional[int] = None
    num_total_tiles: Optional[int] = None
    median_tile_residual: Optional[float] = None
    flow_mad: Optional[float] = None
    status: str = "ok"

    VALID_STATUSES = {"ok", "low_confidence", "failed", "manual_review"}

    def __post_init__(self) -> None:
        self.frame_index = int(self.frame_index)
        if self.frame_index < 0:
            raise ValueError("frame_index must be non-negative.")

        shift = np.asarray(self.shift_xy, dtype=np.float64)
        if shift.shape != (2,):
            raise ValueError("shift_xy must contain exactly two values: dx, dy.")
        if not np.all(np.isfinite(shift)):
            raise ValueError("shift_xy values must be finite.")
        self.shift_xy = (float(shift[0]), float(shift[1]))

        self.method = str(self.method).strip()
        if not self.method:
            raise ValueError("method must be a non-empty string.")

        if not np.isfinite(self.quality_score):
            raise ValueError("quality_score must be finite.")
        if not 0.0 <= float(self.quality_score) <= 1.0:
            raise ValueError("quality_score must be in [0, 1].")
        self.quality_score = float(self.quality_score)

        self.phase_peak_ratio = self._normalize_optional_nonnegative_float(
            self.phase_peak_ratio,
            "phase_peak_ratio",
        )
        self.ecc_score = self._normalize_optional_finite_float(self.ecc_score, "ecc_score")
        self.median_tile_residual = self._normalize_optional_nonnegative_float(
            self.median_tile_residual,
            "median_tile_residual",
        )
        self.flow_mad = self._normalize_optional_nonnegative_float(self.flow_mad, "flow_mad")
        self.num_inlier_tiles = self._normalize_optional_nonnegative_int(
            self.num_inlier_tiles,
            "num_inlier_tiles",
        )
        self.num_total_tiles = self._normalize_optional_nonnegative_int(
            self.num_total_tiles,
            "num_total_tiles",
        )
        if (
            self.num_inlier_tiles is not None
            and self.num_total_tiles is not None
            and self.num_inlier_tiles > self.num_total_tiles
        ):
            raise ValueError("num_inlier_tiles cannot exceed num_total_tiles.")

        self.status = str(self.status).strip()
        if self.status not in self.VALID_STATUSES:
            allowed = ", ".join(sorted(self.VALID_STATUSES))
            raise ValueError(f"status must be one of: {allowed}.")

    @property
    def dx(self) -> float:
        return float(self.shift_xy[0])

    @property
    def dy(self) -> float:
        return float(self.shift_xy[1])

    @staticmethod
    def _normalize_optional_finite_float(value: Optional[float], field_name: str) -> Optional[float]:
        if value is None:
            return None
        value = float(value)
        if not np.isfinite(value):
            raise ValueError(f"{field_name} must be finite.")
        return value

    @classmethod
    def _normalize_optional_nonnegative_float(cls, value: Optional[float], field_name: str) -> Optional[float]:
        value = cls._normalize_optional_finite_float(value, field_name)
        if value is not None and value < 0.0:
            raise ValueError(f"{field_name} must be non-negative.")
        return value

    @staticmethod
    def _normalize_optional_nonnegative_int(value: Optional[int], field_name: str) -> Optional[int]:
        if value is None:
            return None
        value = int(value)
        if value < 0:
            raise ValueError(f"{field_name} must be non-negative.")
        return value


@dataclass
class RegistrationResultSet:
    """Collection of registration estimates for one sequence."""

    settings: RegistrationSettings
    results_by_frame: Dict[int, RegistrationFrameResult] = field(default_factory=dict, repr=False)
    reference_frame_index: int = 0
    template_frame_indices: Optional[tuple[int, ...] | list[int] | np.ndarray] = None

    def __post_init__(self) -> None:
        if not isinstance(self.settings, RegistrationSettings):
            raise TypeError("settings must be a RegistrationSettings instance.")
        self.reference_frame_index = int(self.reference_frame_index)
        if self.reference_frame_index < 0:
            raise ValueError("reference_frame_index must be non-negative.")

        normalized_results: Dict[int, RegistrationFrameResult] = {}
        for frame_index, result in self.results_by_frame.items():
            frame_key = int(frame_index)
            if frame_key < 0:
                raise ValueError("results_by_frame keys must be non-negative.")
            if not isinstance(result, RegistrationFrameResult):
                raise TypeError("results_by_frame values must be RegistrationFrameResult instances.")
            if result.frame_index != frame_key:
                raise ValueError("results_by_frame keys must match result.frame_index.")
            normalized_results[frame_key] = result
        self.results_by_frame = dict(sorted(normalized_results.items()))

        if self.template_frame_indices is not None:
            template_indices = tuple(int(index) for index in self.template_frame_indices)
            if any(index < 0 for index in template_indices):
                raise ValueError("template_frame_indices must be non-negative.")
            self.template_frame_indices = template_indices

    @property
    def frame_indices(self) -> list[int]:
        return list(self.results_by_frame.keys())

    @property
    def result_count(self) -> int:
        return len(self.results_by_frame)

    def get_result(self, frame_index: int) -> Optional[RegistrationFrameResult]:
        return self.results_by_frame.get(int(frame_index))

    def shifts_xy_array(self) -> np.ndarray:
        """Return shifts ordered by frame index with shape [N, 2]."""
        return np.asarray([self.results_by_frame[index].shift_xy for index in self.frame_indices], dtype=np.float64)

    def status_counts(self) -> dict[str, int]:
        counts = {status: 0 for status in sorted(RegistrationFrameResult.VALID_STATUSES)}
        for result in self.results_by_frame.values():
            counts[result.status] = counts.get(result.status, 0) + 1
        return counts


class AnnotationSource(str, Enum):
    """How an annotation was created or last updated."""

    MANUAL = "manual"
    SAM2 = "sam2"
    RESUME = "resume"


class EdgeAnnotationSource(str, Enum):
    """How an edge annotation was created or last updated."""

    MANUAL = "manual"
    DEXINED = "dexined"
    TRACKER_REFINE = "tracker_refine"


class FrameVisibility(str, Enum):
    """Visibility state of an object in a single frame."""

    VISIBLE = "visible"
    HIDDEN = "hidden"
    LOST = "lost"


class TrackQuality(str, Enum):
    """Review status for a tracked object."""

    UNREVIEWED = "unreviewed"
    ACCEPTED = "accepted"
    NEEDS_REVIEW = "needs_review"
    REJECTED = "rejected"


@dataclass(frozen=True)
class PolygonROI:
    """Polygonal region of interest stored as [x, y] vertices."""

    vertices_xy: np.ndarray = field(repr=False)

    def __post_init__(self) -> None:
        vertices = np.asarray(self.vertices_xy, dtype=np.float64)
        if vertices.ndim != 2 or vertices.shape[1] != 2:
            raise ValueError("vertices_xy must have shape [N, 2].")
        if len(vertices) < 3:
            raise ValueError("PolygonROI requires at least three vertices.")
        if not np.all(np.isfinite(vertices)):
            raise ValueError("PolygonROI vertices must be finite.")
        object.__setattr__(self, "vertices_xy", vertices)

    @property
    def vertex_count(self) -> int:
        return int(len(self.vertices_xy))

    @property
    def bounds_xyxy(self) -> tuple[float, float, float, float]:
        x_coords = self.vertices_xy[:, 0]
        y_coords = self.vertices_xy[:, 1]
        return (
            float(np.min(x_coords)),
            float(np.min(y_coords)),
            float(np.max(x_coords)),
            float(np.max(y_coords)),
        )

    def as_array(self) -> np.ndarray:
        return np.asarray(self.vertices_xy, dtype=np.float64)


@dataclass(frozen=True)
class BBoxXYXY:
    """Axis-aligned bounding box in pixel coordinates."""

    x0: float
    y0: float
    x1: float
    y1: float

    def __post_init__(self) -> None:
        coords = np.asarray([self.x0, self.y0, self.x1, self.y1], dtype=np.float64)
        if not np.all(np.isfinite(coords)):
            raise ValueError("Bounding box coordinates must be finite.")
        if self.x1 <= self.x0 or self.y1 <= self.y0:
            raise ValueError("Bounding box must have positive width and height.")

    @property
    def width(self) -> float:
        return float(self.x1 - self.x0)

    @property
    def height(self) -> float:
        return float(self.y1 - self.y0)

    @property
    def center_xy(self) -> tuple[float, float]:
        return float((self.x0 + self.x1) / 2.0), float((self.y0 + self.y1) / 2.0)

    def as_tuple(self) -> tuple[float, float, float, float]:
        return self.x0, self.y0, self.x1, self.y1


@dataclass
class ParticleMetrics:
    """Per-frame measurements derived from a segmentation mask."""

    area_px: Optional[float] = None
    perimeter_px: Optional[float] = None
    area_nm2: Optional[float] = None
    perimeter_nm: Optional[float] = None
    intensity_sum: Optional[float] = None
    intensity_mean: Optional[float] = None
    intensity_max: Optional[float] = None

    def __post_init__(self) -> None:
        if self.area_px is not None and self.area_px < 0:
            raise ValueError("area_px must be non-negative.")
        if self.perimeter_px is not None and self.perimeter_px < 0:
            raise ValueError("perimeter_px must be non-negative.")
        if self.area_nm2 is not None and self.area_nm2 < 0:
            raise ValueError("area_nm2 must be non-negative.")
        if self.perimeter_nm is not None and self.perimeter_nm < 0:
            raise ValueError("perimeter_nm must be non-negative.")


@dataclass
class EdgeMetrics:
    """Per-frame measurements describing step-edge geometry and roughness."""

    length_px: Optional[float] = None
    length_nm: Optional[float] = None
    roughness_rms_px: Optional[float] = None
    roughness_rms_nm: Optional[float] = None
    mean_curvature: Optional[float] = None
    max_curvature: Optional[float] = None
    waviness_amplitude_px: Optional[float] = None
    waviness_amplitude_nm: Optional[float] = None

    def __post_init__(self) -> None:
        for field_name in (
            "length_px",
            "length_nm",
            "roughness_rms_px",
            "roughness_rms_nm",
            "mean_curvature",
            "max_curvature",
            "waviness_amplitude_px",
            "waviness_amplitude_nm",
        ):
            value = getattr(self, field_name)
            if value is not None and value < 0:
                raise ValueError(f"{field_name} must be non-negative.")


@dataclass
class EdgeGeometryQuality:
    """Confidence and review metadata for one refined edge geometry."""

    confidence: float = 0.0
    review_status: str = "needs_review"
    warnings: tuple[str, ...] = field(default_factory=tuple)
    polyline_method: str = ""
    extraction_mode: str = ""
    method_explicit: bool = True
    coarse_score: float = 0.0
    refinement_score: float = 0.0
    refinement_stability: float = 0.0
    mean_shift_px: float = 0.0
    refinement_mode: str = ""

    def __post_init__(self) -> None:
        if not np.isfinite(self.confidence):
            raise ValueError("confidence must be finite.")
        if not 0.0 <= float(self.confidence) <= 1.0:
            raise ValueError("confidence must be in [0, 1].")
        if not np.isfinite(self.refinement_stability):
            raise ValueError("refinement_stability must be finite.")
        if not 0.0 <= float(self.refinement_stability) <= 1.0:
            raise ValueError("refinement_stability must be in [0, 1].")
        if not np.isfinite(self.coarse_score):
            raise ValueError("coarse_score must be finite.")
        if not np.isfinite(self.refinement_score):
            raise ValueError("refinement_score must be finite.")
        if not np.isfinite(self.mean_shift_px):
            raise ValueError("mean_shift_px must be finite.")
        if float(self.mean_shift_px) < 0.0:
            raise ValueError("mean_shift_px must be non-negative.")
        review_status = str(self.review_status)
        if review_status not in {"ok", "needs_review"}:
            raise ValueError("review_status must be 'ok' or 'needs_review'.")
        self.confidence = float(self.confidence)
        self.review_status = review_status
        self.warnings = tuple(str(warning) for warning in self.warnings)
        self.polyline_method = str(self.polyline_method)
        self.extraction_mode = str(self.extraction_mode)
        self.method_explicit = bool(self.method_explicit)
        self.coarse_score = float(self.coarse_score)
        self.refinement_score = float(self.refinement_score)
        self.refinement_stability = float(self.refinement_stability)
        self.mean_shift_px = float(self.mean_shift_px)
        self.refinement_mode = str(self.refinement_mode)


@dataclass
class YoloDetection:
    """One YOLO bbox proposal for a single frame."""

    frame_index: int
    bbox: BBoxXYXY
    confidence: float
    selected: bool = True
    model_name: str = ""

    def __post_init__(self) -> None:
        if self.frame_index < 0:
            raise ValueError("frame_index must be non-negative.")
        if not np.isfinite(self.confidence):
            raise ValueError("confidence must be finite.")
        if not 0.0 <= float(self.confidence) <= 1.0:
            raise ValueError("confidence must be in [0, 1].")
        self.confidence = float(self.confidence)
        self.selected = bool(self.selected)
        self.model_name = str(self.model_name).strip()
        if not self.model_name:
            raise ValueError("model_name must be a non-empty string.")


@dataclass
class YoloDetectionSet:
    """Frame-indexed YOLO bbox proposals for one sequence and one model."""

    model_name: str
    source_path: str
    detections_by_frame: Dict[int, list[YoloDetection]] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        self.model_name = str(self.model_name).strip()
        self.source_path = str(self.source_path).strip()
        if not self.model_name:
            raise ValueError("model_name must be a non-empty string.")
        if not self.source_path:
            raise ValueError("source_path must be a non-empty string.")

        normalized: Dict[int, list[YoloDetection]] = {}
        for frame_index, detections in self.detections_by_frame.items():
            frame_key = int(frame_index)
            if frame_key < 0:
                raise ValueError("detections_by_frame keys must be non-negative.")
            normalized[frame_key] = self._normalize_frame_detections(frame_key, detections)
        self.detections_by_frame = dict(sorted(normalized.items()))

    @property
    def frame_indices(self) -> list[int]:
        return list(self.detections_by_frame.keys())

    @property
    def detection_count(self) -> int:
        return sum(len(detections) for detections in self.detections_by_frame.values())

    def get_detections(self, frame_index: int) -> list[YoloDetection]:
        return list(self.detections_by_frame.get(int(frame_index), []))

    def selected_detections(self, frame_index: int | None = None) -> list[YoloDetection]:
        if frame_index is not None:
            return [detection for detection in self.get_detections(frame_index) if detection.selected]
        selected: list[YoloDetection] = []
        for current_frame_index in self.frame_indices:
            selected.extend(self.selected_detections(current_frame_index))
        return selected

    def selected_detection_count(self, frame_index: int | None = None) -> int:
        return len(self.selected_detections(frame_index))

    def set_detections(self, frame_index: int, detections: list[YoloDetection]) -> None:
        frame_index = int(frame_index)
        if frame_index < 0:
            raise ValueError("frame_index must be non-negative.")
        normalized = self._normalize_frame_detections(frame_index, detections)
        if normalized:
            self.detections_by_frame[frame_index] = normalized
        else:
            self.detections_by_frame.pop(frame_index, None)
        self.detections_by_frame = dict(sorted(self.detections_by_frame.items()))

    def add_detection(self, detection: YoloDetection) -> None:
        frame_index = int(detection.frame_index)
        current = self.get_detections(frame_index)
        current.append(detection)
        self.set_detections(frame_index, current)

    def clear_frame(self, frame_index: int) -> None:
        self.detections_by_frame.pop(int(frame_index), None)

    def clear_all(self) -> None:
        self.detections_by_frame.clear()

    def set_selected(self, frame_index: int | None, selected: bool) -> None:
        if frame_index is None:
            target_frame_indices = self.frame_indices
        else:
            target_frame_indices = [int(frame_index)]
        for current_frame_index in target_frame_indices:
            for detection in self.detections_by_frame.get(current_frame_index, []):
                detection.selected = bool(selected)

    def _normalize_frame_detections(
        self,
        frame_index: int,
        detections: list[YoloDetection],
    ) -> list[YoloDetection]:
        normalized: list[YoloDetection] = []
        for detection in detections:
            if detection.frame_index != frame_index:
                raise ValueError("Detection frame_index must match the frame key in detections_by_frame.")
            if detection.model_name != self.model_name:
                raise ValueError("All detections inside YoloDetectionSet must match model_name.")
            normalized.append(detection)
        return list(normalized)


@dataclass
class TrackFrameAnnotation:
    """Single-frame annotation for one tracked object."""

    frame_index: int
    bbox: Optional[BBoxXYXY] = None
    mask: Optional[np.ndarray] = field(default=None, repr=False)
    visibility: FrameVisibility = FrameVisibility.VISIBLE
    source: AnnotationSource = AnnotationSource.SAM2
    metrics: ParticleMetrics = field(default_factory=ParticleMetrics)

    def __post_init__(self) -> None:
        if self.frame_index < 0:
            raise ValueError("frame_index must be non-negative.")
        if self.mask is not None:
            mask = np.asarray(self.mask, dtype=bool)
            if mask.ndim != 2:
                raise ValueError("mask must have shape [H, W].")
            self.mask = mask
        has_geometry = self.bbox is not None or self.mask is not None
        if self.visibility == FrameVisibility.VISIBLE and not has_geometry:
            raise ValueError("Visible annotations require at least a bbox or a mask.")

    @property
    def has_mask(self) -> bool:
        return self.mask is not None

    @property
    def has_geometry(self) -> bool:
        return self.bbox is not None or self.mask is not None


@dataclass
class EdgeFrameAnnotation:
    """Single-frame annotation for one tracked step edge."""

    frame_index: int
    polyline: Optional[np.ndarray] = field(default=None, repr=False)
    edge_mask: Optional[np.ndarray] = field(default=None, repr=False)
    visibility: FrameVisibility = FrameVisibility.VISIBLE
    source: EdgeAnnotationSource = EdgeAnnotationSource.DEXINED
    metrics: EdgeMetrics = field(default_factory=EdgeMetrics)
    geometry_quality: Optional[EdgeGeometryQuality] = None

    def __post_init__(self) -> None:
        if self.frame_index < 0:
            raise ValueError("frame_index must be non-negative.")
        if self.polyline is not None:
            polyline = np.asarray(self.polyline, dtype=np.float64)
            if polyline.ndim != 2 or polyline.shape[1] != 2:
                raise ValueError("polyline must have shape [N, 2].")
            if len(polyline) < 2:
                raise ValueError("polyline must contain at least two points.")
            if not np.all(np.isfinite(polyline)):
                raise ValueError("polyline points must be finite.")
            self.polyline = polyline
        if self.edge_mask is not None:
            edge_mask = np.asarray(self.edge_mask, dtype=bool)
            if edge_mask.ndim != 2:
                raise ValueError("edge_mask must have shape [H, W].")
            self.edge_mask = edge_mask
        if self.geometry_quality is not None and not isinstance(self.geometry_quality, EdgeGeometryQuality):
            raise ValueError("geometry_quality must be an EdgeGeometryQuality instance.")
        if self.visibility == FrameVisibility.VISIBLE and not self.has_geometry:
            raise ValueError("Visible edge annotations require at least a polyline or an edge_mask.")

    @property
    def has_geometry(self) -> bool:
        return self.polyline is not None or self.edge_mask is not None

    @property
    def has_edge_mask(self) -> bool:
        return self.edge_mask is not None

    @property
    def polyline_point_count(self) -> int:
        if self.polyline is None:
            return 0
        return int(len(self.polyline))


@dataclass
class ParticleTrack:
    """Frame-indexed annotations for a single tracked nanoparticle."""

    track_id: int
    seed_frame_index: int
    seed_bbox: BBoxXYXY
    annotations: Dict[int, TrackFrameAnnotation] = field(default_factory=dict, repr=False)
    quality: TrackQuality = TrackQuality.UNREVIEWED
    label: Optional[str] = None

    def __post_init__(self) -> None:
        if self.track_id < 0:
            raise ValueError("track_id must be non-negative.")
        if self.seed_frame_index < 0:
            raise ValueError("seed_frame_index must be non-negative.")

        normalized: Dict[int, TrackFrameAnnotation] = {}
        for frame_index, annotation in self.annotations.items():
            if frame_index != annotation.frame_index:
                raise ValueError("Annotation dictionary keys must match annotation.frame_index.")
            normalized[frame_index] = annotation

        if self.seed_frame_index not in normalized:
            normalized[self.seed_frame_index] = TrackFrameAnnotation(
                frame_index=self.seed_frame_index,
                bbox=self.seed_bbox,
                source=AnnotationSource.MANUAL,
            )

        self.annotations = dict(sorted(normalized.items()))

    @property
    def frame_indices(self) -> list[int]:
        return list(self.annotations.keys())

    @property
    def visible_frame_indices(self) -> list[int]:
        return [
            frame_index
            for frame_index, annotation in self.annotations.items()
            if annotation.visibility == FrameVisibility.VISIBLE
        ]

    @property
    def end_frame_index(self) -> int:
        return max(self.annotations)

    def get_annotation(self, frame_index: int) -> Optional[TrackFrameAnnotation]:
        return self.annotations.get(frame_index)

    def add_annotation(self, annotation: TrackFrameAnnotation) -> None:
        self.annotations[annotation.frame_index] = annotation
        self.annotations = dict(sorted(self.annotations.items()))

    def drop_annotations_after(self, frame_index: int) -> None:
        self.annotations = dict(
            sorted(
                (
                    annotation_frame,
                    annotation,
                )
                for annotation_frame, annotation in self.annotations.items()
                if annotation_frame <= frame_index
            )
        )


@dataclass
class EdgeTrack:
    """Frame-indexed annotations for a single tracked STM step edge."""

    edge_track_id: int
    seed_frame_index: int
    polygon_roi: PolygonROI
    seed_polyline: np.ndarray = field(repr=False)
    annotations: Dict[int, EdgeFrameAnnotation] = field(default_factory=dict, repr=False)
    quality: TrackQuality = TrackQuality.UNREVIEWED
    label: Optional[str] = None

    def __post_init__(self) -> None:
        if self.edge_track_id < 0:
            raise ValueError("edge_track_id must be non-negative.")
        if self.seed_frame_index < 0:
            raise ValueError("seed_frame_index must be non-negative.")

        seed_polyline = np.asarray(self.seed_polyline, dtype=np.float64)
        if seed_polyline.ndim != 2 or seed_polyline.shape[1] != 2:
            raise ValueError("seed_polyline must have shape [N, 2].")
        if len(seed_polyline) < 2:
            raise ValueError("seed_polyline must contain at least two points.")
        if not np.all(np.isfinite(seed_polyline)):
            raise ValueError("seed_polyline points must be finite.")
        self.seed_polyline = seed_polyline

        normalized: Dict[int, EdgeFrameAnnotation] = {}
        for frame_index, annotation in self.annotations.items():
            if frame_index != annotation.frame_index:
                raise ValueError("Annotation dictionary keys must match annotation.frame_index.")
            normalized[frame_index] = annotation

        if self.seed_frame_index not in normalized:
            normalized[self.seed_frame_index] = EdgeFrameAnnotation(
                frame_index=self.seed_frame_index,
                polyline=self.seed_polyline,
                source=EdgeAnnotationSource.MANUAL,
            )

        self.annotations = dict(sorted(normalized.items()))

    @property
    def frame_indices(self) -> list[int]:
        return list(self.annotations.keys())

    @property
    def visible_frame_indices(self) -> list[int]:
        return [
            frame_index
            for frame_index, annotation in self.annotations.items()
            if annotation.visibility == FrameVisibility.VISIBLE
        ]

    @property
    def end_frame_index(self) -> int:
        return max(self.annotations)

    def get_annotation(self, frame_index: int) -> Optional[EdgeFrameAnnotation]:
        return self.annotations.get(frame_index)

    def add_annotation(self, annotation: EdgeFrameAnnotation) -> None:
        self.annotations[annotation.frame_index] = annotation
        self.annotations = dict(sorted(self.annotations.items()))

    def drop_annotations_after(self, frame_index: int) -> None:
        self.annotations = dict(
            sorted(
                (
                    annotation_frame,
                    annotation,
                )
                for annotation_frame, annotation in self.annotations.items()
                if annotation_frame <= frame_index
            )
        )
