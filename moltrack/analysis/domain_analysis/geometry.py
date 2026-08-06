from dataclasses import dataclass, field
from math import isfinite
from typing import Literal

import numpy as np

CoordinateView = Literal["raw", "expanded_aligned"]
GeometryMode = Literal["segmentation_preferred", "bbox_centers"]
MoleculeSourceKind = Literal["segmentation", "bbox_center"]


@dataclass(frozen=True)
class M6FrameGeometry:
    """Translation-only geometry needed to canonicalize one physical frame."""

    physical_frame_id: str
    raw_shape: tuple[int, int]
    expanded_shape: tuple[int, int]
    frame_origin_xy: tuple[float, float]
    canvas_offset_xy: tuple[float, float]
    pixel_size_nm: tuple[float, float]
    scan_angle_deg: float
    registration_fingerprint: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "physical_frame_id", _text(
            self.physical_frame_id,
            "physical_frame_id",
        ))
        object.__setattr__(self, "raw_shape", _shape(self.raw_shape, "raw_shape"))
        object.__setattr__(
            self,
            "expanded_shape",
            _shape(self.expanded_shape, "expanded_shape"),
        )
        object.__setattr__(
            self,
            "frame_origin_xy",
            _pair(self.frame_origin_xy, "frame_origin_xy"),
        )
        object.__setattr__(
            self,
            "canvas_offset_xy",
            _pair(self.canvas_offset_xy, "canvas_offset_xy"),
        )
        pixel_size = _pair(self.pixel_size_nm, "pixel_size_nm")
        if pixel_size[0] <= 0.0 or pixel_size[1] <= 0.0:
            raise ValueError("pixel_size_nm values must be positive.")
        object.__setattr__(self, "pixel_size_nm", pixel_size)
        angle = float(self.scan_angle_deg)
        if not isfinite(angle):
            raise ValueError("scan_angle_deg must be finite.")
        object.__setattr__(self, "scan_angle_deg", angle)
        object.__setattr__(self, "registration_fingerprint", _text(
            self.registration_fingerprint,
            "registration_fingerprint",
        ))


@dataclass(frozen=True)
class M6SourceAnnotation:
    """One bbox and optional sparse mask authored in a supported image view."""

    source_id: str
    source_view: CoordinateView
    bbox_xyxy: tuple[float, float, float, float]
    mask_shape: tuple[int, int] | None = None
    mask_pixels_xy: tuple[tuple[int, int], ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_id", _text(self.source_id, "source_id"))
        if self.source_view not in {"raw", "expanded_aligned"}:
            raise ValueError(f"Unsupported source_view: {self.source_view!r}.")
        object.__setattr__(self, "bbox_xyxy", _bbox(self.bbox_xyxy))
        pixels = tuple(sorted({_pixel(value) for value in self.mask_pixels_xy}))
        if self.mask_shape is None:
            if pixels:
                raise ValueError("mask_pixels_xy requires mask_shape.")
        else:
            shape = _shape(self.mask_shape, "mask_shape")
            height, width = shape
            if any(x >= width or y >= height for x, y in pixels):
                raise ValueError("mask_pixels_xy must lie inside mask_shape.")
            object.__setattr__(self, "mask_shape", shape)
        object.__setattr__(self, "mask_pixels_xy", pixels)


@dataclass(frozen=True)
class M6AnalyzedMolecule:
    """Canonical raw footprint and Series Physical Coordinates used by M6."""

    source_id: str
    source_kind: MoleculeSourceKind
    raw_centroid_xy: tuple[float, float]
    centroid_xy_nm: tuple[float, float]
    footprint_pixels_xy: tuple[tuple[int, int], ...]

    def __post_init__(self) -> None:
        pixels = tuple(sorted({_pixel(value) for value in self.footprint_pixels_xy}))
        if not pixels:
            raise ValueError("footprint_pixels_xy cannot be empty.")
        object.__setattr__(self, "source_id", _text(self.source_id, "source_id"))
        if self.source_kind not in {"segmentation", "bbox_center"}:
            raise ValueError(f"Unsupported source_kind: {self.source_kind!r}.")
        object.__setattr__(
            self,
            "raw_centroid_xy",
            _pair(self.raw_centroid_xy, "raw_centroid_xy"),
        )
        object.__setattr__(
            self,
            "centroid_xy_nm",
            _pair(self.centroid_xy_nm, "centroid_xy_nm"),
        )
        object.__setattr__(self, "footprint_pixels_xy", pixels)


@dataclass(frozen=True, order=True)
class M6PublishedMolecule:
    """Atomic published membership provenance used by tables and persistence."""

    source_id: str
    source_kind: MoleculeSourceKind
    point_xy_nm: tuple[float, float]

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_id", _text(self.source_id, "source_id"))
        if self.source_kind not in {"segmentation", "bbox_center"}:
            raise ValueError(f"Unsupported source_kind: {self.source_kind!r}.")
        object.__setattr__(
            self,
            "point_xy_nm",
            _pair(self.point_xy_nm, "point_xy_nm"),
        )


@dataclass(frozen=True)
class DomainAnalysisFrame:
    """Immutable annotations and registration geometry for one working frame."""

    frame_index: int
    source_view: CoordinateView
    geometry: M6FrameGeometry
    annotations: tuple[M6SourceAnnotation, ...]
    raw_frame: np.ndarray | None = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if isinstance(self.frame_index, bool) or int(self.frame_index) < 0:
            raise ValueError("frame_index must be a non-negative integer.")
        if not isinstance(self.geometry, M6FrameGeometry):
            raise TypeError("geometry must be M6FrameGeometry.")
        if self.source_view not in {"raw", "expanded_aligned"}:
            raise ValueError(f"Unsupported source_view: {self.source_view!r}.")
        annotations = tuple(sorted(self.annotations, key=lambda value: value.source_id))
        if any(not isinstance(value, M6SourceAnnotation) for value in annotations):
            raise TypeError("annotations must contain M6SourceAnnotation values.")
        if len({value.source_id for value in annotations}) != len(annotations):
            raise ValueError("annotation source IDs must be unique within a frame.")
        if any(value.source_view != self.source_view for value in annotations):
            raise ValueError("annotation source_view must match its frame.")
        raw_frame = self.raw_frame
        if raw_frame is not None:
            values = np.asarray(raw_frame)
            if values.ndim != 2 or values.shape != self.geometry.raw_shape:
                raise ValueError("raw_frame must match geometry.raw_shape.")
            values.setflags(write=False)
            object.__setattr__(self, "raw_frame", values)
        object.__setattr__(self, "frame_index", int(self.frame_index))
        object.__setattr__(self, "annotations", annotations)


@dataclass(frozen=True)
class DomainAnalysisSeries:
    """Immutable frame inputs consumed by DomainAnalysisModule.run."""

    frames: tuple[DomainAnalysisFrame, ...]

    def __post_init__(self) -> None:
        frames = tuple(sorted(self.frames, key=lambda value: value.frame_index))
        if any(not isinstance(value, DomainAnalysisFrame) for value in frames):
            raise TypeError("frames must contain DomainAnalysisFrame values.")
        if len({value.frame_index for value in frames}) != len(frames):
            raise ValueError("Domain Analysis frame indexes must be unique.")
        object.__setattr__(self, "frames", frames)

    def frame(self, frame_index: int) -> DomainAnalysisFrame:
        for frame in self.frames:
            if frame.frame_index == frame_index:
                return frame
        raise ValueError(f"Domain Analysis series has no frame {frame_index}.")


@dataclass(frozen=True)
class M6PresentationProvenance:
    """View-only translation metadata kept outside canonical M6 geometry."""

    raw_shape: tuple[int, int]
    expanded_shape: tuple[int, int]
    source_view: CoordinateView
    frame_origin_xy: tuple[float, float]
    canvas_offset_xy: tuple[float, float]
    registration_fingerprint: str

    def __post_init__(self) -> None:
        if self.source_view not in {"raw", "expanded_aligned"}:
            raise ValueError(f"Unsupported source_view: {self.source_view!r}.")
        object.__setattr__(self, "raw_shape", _shape(self.raw_shape, "raw_shape"))
        object.__setattr__(
            self,
            "expanded_shape",
            _shape(self.expanded_shape, "expanded_shape"),
        )
        object.__setattr__(
            self,
            "frame_origin_xy",
            _pair(self.frame_origin_xy, "frame_origin_xy"),
        )
        object.__setattr__(
            self,
            "canvas_offset_xy",
            _pair(self.canvas_offset_xy, "canvas_offset_xy"),
        )
        object.__setattr__(self, "registration_fingerprint", _text(
            self.registration_fingerprint,
            "registration_fingerprint",
        ))


@dataclass(frozen=True)
class M6CanonicalFrame:
    """Canonical raw/sample geometry passed to an M6 backend."""

    frame_index: int
    physical_frame_id: str
    molecules: tuple[M6AnalyzedMolecule, ...]
    analyzed_pixels_xy: tuple[tuple[int, int], ...]
    pixel_area_nm2: float
    coordinate_frame: str
    coordinate_transform_fingerprint: str
    presentation_provenance: M6PresentationProvenance


def _shape(value: tuple[int, int], name: str) -> tuple[int, int]:
    try:
        height, width = (int(item) for item in value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must contain height and width.") from exc
    if height <= 0 or width <= 0:
        raise ValueError(f"{name} values must be positive.")
    return height, width


def _pair(value: tuple[float, float], name: str) -> tuple[float, float]:
    pair = tuple(_q(float(item)) for item in value)
    if len(pair) != 2 or not all(isfinite(item) for item in pair):
        raise ValueError(f"{name} must be a finite XY pair.")
    return pair


def _bbox(
    value: tuple[float, float, float, float],
) -> tuple[float, float, float, float]:
    bbox = tuple(_q(float(item)) for item in value)
    if len(bbox) != 4 or not all(isfinite(item) for item in bbox):
        raise ValueError("bbox_xyxy must contain four finite values.")
    if bbox[2] <= bbox[0] or bbox[3] <= bbox[1]:
        raise ValueError("bbox_xyxy must satisfy x2 > x1 and y2 > y1.")
    return bbox


def _pixel(value: tuple[int, int]) -> tuple[int, int]:
    x, y = tuple(value)
    if any(isinstance(item, bool) or int(item) != item or item < 0 for item in (x, y)):
        raise ValueError("mask_pixels_xy must contain non-negative integer pairs.")
    return int(x), int(y)


def _text(value: str, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string.")
    return value.strip()


def _q(value: float) -> float:
    normalized = round(float(value), 12)
    return 0.0 if normalized == 0.0 else normalized
