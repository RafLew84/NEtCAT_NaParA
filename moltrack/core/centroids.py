from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

import numpy as np

from .detections import MolecularDetection
from .data_models import MolTrackImageSeries
from .segmentations import MolecularSegmentation, SUPPORTED_SEGMENTATION_SOURCE_VIEWS


SUPPORTED_CENTROID_SOURCE_KINDS = ("segmentation", "bbox_center")


def build_molecular_centroids(
    series: MolTrackImageSeries,
    *,
    frame_index: int | None = None,
    source_view: str = "raw",
    use_segmentation_centroids: bool = True,
) -> list["MolecularCentroid"]:
    """Build molecule positions from linked masks or exclusively from bbox centers."""

    if not isinstance(series, MolTrackImageSeries):
        raise TypeError("series must be a MolTrackImageSeries instance.")
    frame_index = series.active_frame_index if frame_index is None else int(frame_index)
    series.get_frame(frame_index)
    source_view = str(source_view).strip()
    if source_view not in SUPPORTED_SEGMENTATION_SOURCE_VIEWS:
        supported = ", ".join(SUPPORTED_SEGMENTATION_SOURCE_VIEWS)
        raise ValueError(f"Unsupported source_view: {source_view!r}. Supported: {supported}.")
    frame_shape, scale_nm_per_px = _series_context_geometry(series, source_view=source_view)

    centroids: list[MolecularCentroid] = []
    linked_detection_ids: set[str] = set()
    segmentation_set = series.molecular_segmentations
    if bool(use_segmentation_centroids) and segmentation_set is not None:
        for segmentation in segmentation_set.get_segmentations(frame_index, source_view=source_view):
            if segmentation.mask is None:
                continue
            centroids.append(
                MolecularCentroid.from_segmentation(
                    segmentation,
                    frame_shape=frame_shape,
                    scale_nm_per_px=scale_nm_per_px,
                )
            )
            linked_detection_ids.update(segmentation.prompt_detection_ids)

    detection_set = series.molecular_detections
    if detection_set is not None:
        for detection in detection_set.get_detections(frame_index, source_view=source_view):
            if detection.detection_id in linked_detection_ids:
                continue
            centroids.append(
                MolecularCentroid.from_detection(
                    detection,
                    frame_shape=frame_shape,
                    scale_nm_per_px=scale_nm_per_px,
                )
            )
    return centroids


def _series_context_geometry(
    series: MolTrackImageSeries,
    *,
    source_view: str,
) -> tuple[tuple[int, int], tuple[float, float] | None]:
    if source_view == "raw":
        return series.frame_shape, _metadata_pixel_size_nm(series.metadata)

    expanded_stack = series.expanded_aligned_stack
    if expanded_stack is None:
        raise ValueError("expanded_aligned source_view requires an expanded_aligned_stack.")
    frames = np.asarray(getattr(expanded_stack, "frames", None))
    if frames.ndim != 3 or frames.shape[0] != series.frame_count:
        raise ValueError("expanded_aligned_stack frames must match the working series.")
    frame_shape = int(frames.shape[1]), int(frames.shape[2])
    metadata = getattr(expanded_stack, "metadata", series.metadata)
    return frame_shape, _metadata_pixel_size_nm(metadata)


def _metadata_pixel_size_nm(metadata) -> tuple[float, float] | None:
    get_pixel_size = getattr(metadata, "get_pixel_size_nm", None)
    if not callable(get_pixel_size):
        return None
    try:
        scale_x, scale_y = get_pixel_size()
        scale_x = float(scale_x)
        scale_y = float(scale_y)
    except (TypeError, ValueError):
        return None
    if not isfinite(scale_x) or not isfinite(scale_y) or scale_x <= 0.0 or scale_y <= 0.0:
        return None
    return scale_x, scale_y


@dataclass(frozen=True)
class MolecularCentroid:
    """Position of one molecule inferred from a segmentation or bbox."""

    frame_index: int
    source_view: str
    x_px: float
    y_px: float
    source_kind: str
    source_id: str
    x_nm: float | None = None
    y_nm: float | None = None
    area_px: float | None = None
    origin: str | None = None

    def __post_init__(self) -> None:
        frame_index = int(self.frame_index)
        if frame_index < 0:
            raise ValueError("frame_index must be non-negative.")

        source_view = str(self.source_view).strip()
        if source_view not in SUPPORTED_SEGMENTATION_SOURCE_VIEWS:
            supported = ", ".join(SUPPORTED_SEGMENTATION_SOURCE_VIEWS)
            raise ValueError(f"Unsupported source_view: {source_view!r}. Supported: {supported}.")

        x_px = _normalize_non_negative_finite(self.x_px, "x_px")
        y_px = _normalize_non_negative_finite(self.y_px, "y_px")
        source_kind = str(self.source_kind).strip()
        if source_kind not in SUPPORTED_CENTROID_SOURCE_KINDS:
            supported = ", ".join(SUPPORTED_CENTROID_SOURCE_KINDS)
            raise ValueError(f"Unsupported source_kind: {source_kind!r}. Supported: {supported}.")
        source_id = str(self.source_id).strip()
        if not source_id:
            raise ValueError("source_id must be a non-empty string.")

        x_nm, y_nm = _normalize_optional_nm_pair(self.x_nm, self.y_nm)
        area_px = None if self.area_px is None else _normalize_positive_finite(self.area_px, "area_px")
        origin = None if self.origin is None else str(self.origin).strip()
        if origin == "":
            raise ValueError("origin must be a non-empty string when provided.")

        object.__setattr__(self, "frame_index", frame_index)
        object.__setattr__(self, "source_view", source_view)
        object.__setattr__(self, "x_px", x_px)
        object.__setattr__(self, "y_px", y_px)
        object.__setattr__(self, "source_kind", source_kind)
        object.__setattr__(self, "source_id", source_id)
        object.__setattr__(self, "x_nm", x_nm)
        object.__setattr__(self, "y_nm", y_nm)
        object.__setattr__(self, "area_px", area_px)
        object.__setattr__(self, "origin", origin)

    @classmethod
    def from_segmentation(
        cls,
        segmentation: MolecularSegmentation,
        *,
        frame_shape: tuple[int, int],
        scale_nm_per_px: tuple[float, float] | None = None,
    ) -> "MolecularCentroid":
        if not isinstance(segmentation, MolecularSegmentation):
            raise TypeError("segmentation must be a MolecularSegmentation instance.")
        height, width = _normalize_frame_shape(frame_shape)
        if segmentation.mask is None:
            raise ValueError("A segmentation mask is required to compute its centroid.")
        mask = np.asarray(segmentation.mask, dtype=bool)
        if mask.shape != (height, width):
            raise ValueError("Segmentation mask shape must match frame_shape.")

        y_indices, x_indices = np.nonzero(mask)
        if x_indices.size == 0:
            raise ValueError("Cannot compute a centroid from an empty segmentation mask.")
        x_px = float(np.mean(x_indices, dtype=np.float64) + 0.5)
        y_px = float(np.mean(y_indices, dtype=np.float64) + 0.5)
        x_nm, y_nm = _scaled_position_nm(x_px, y_px, scale_nm_per_px)
        centroid = cls(
            frame_index=segmentation.frame_index,
            source_view=segmentation.source_view,
            x_px=x_px,
            y_px=y_px,
            x_nm=x_nm,
            y_nm=y_nm,
            source_kind="segmentation",
            source_id=segmentation.segmentation_id,
            area_px=int(x_indices.size),
            origin=segmentation.origin,
        )
        centroid.validate_within_frame((height, width))
        return centroid

    @classmethod
    def from_detection(
        cls,
        detection: MolecularDetection,
        *,
        frame_shape: tuple[int, int],
        scale_nm_per_px: tuple[float, float] | None = None,
    ) -> "MolecularCentroid":
        if not isinstance(detection, MolecularDetection):
            raise TypeError("detection must be a MolecularDetection instance.")
        height, width = _normalize_frame_shape(frame_shape)
        detection.validate_within_frame((height, width))
        x1, y1, x2, y2 = detection.bbox_xyxy
        x_px = (x1 + x2) / 2.0
        y_px = (y1 + y2) / 2.0
        x_nm, y_nm = _scaled_position_nm(x_px, y_px, scale_nm_per_px)
        centroid = cls(
            frame_index=detection.frame_index,
            source_view=detection.source_view,
            x_px=x_px,
            y_px=y_px,
            x_nm=x_nm,
            y_nm=y_nm,
            source_kind="bbox_center",
            source_id=detection.detection_id,
            area_px=None,
            origin=detection.origin,
        )
        centroid.validate_within_frame((height, width))
        return centroid

    def validate_within_frame(self, frame_shape: tuple[int, int]) -> None:
        height, width = _normalize_frame_shape(frame_shape)
        if not 0.0 <= self.x_px < width or not 0.0 <= self.y_px < height:
            raise ValueError("Molecular centroid must be within frame bounds.")


def _normalize_frame_shape(frame_shape: tuple[int, int]) -> tuple[int, int]:
    try:
        height, width = (int(value) for value in frame_shape)
    except (TypeError, ValueError) as exc:
        raise ValueError("frame_shape must contain height and width.") from exc
    if height <= 0 or width <= 0:
        raise ValueError("frame_shape height and width must be positive.")
    return height, width


def _normalize_non_negative_finite(value: float, name: str) -> float:
    value = float(value)
    if not isfinite(value) or value < 0.0:
        raise ValueError(f"{name} must be a non-negative finite value.")
    return value


def _normalize_positive_finite(value: float, name: str) -> float:
    value = float(value)
    if not isfinite(value) or value <= 0.0:
        raise ValueError(f"{name} must be a positive finite value.")
    return value


def _normalize_optional_nm_pair(x_nm: float | None, y_nm: float | None) -> tuple[float | None, float | None]:
    if x_nm is None and y_nm is None:
        return None, None
    if x_nm is None or y_nm is None:
        raise ValueError("x_nm and y_nm must either both be provided or both be omitted.")
    return _normalize_non_negative_finite(x_nm, "x_nm"), _normalize_non_negative_finite(y_nm, "y_nm")


def _scaled_position_nm(
    x_px: float,
    y_px: float,
    scale_nm_per_px: tuple[float, float] | None,
) -> tuple[float | None, float | None]:
    if scale_nm_per_px is None:
        return None, None
    try:
        scale_x, scale_y = (float(value) for value in scale_nm_per_px)
    except (TypeError, ValueError) as exc:
        raise ValueError("scale_nm_per_px must contain x and y scales.") from exc
    scale_x = _normalize_positive_finite(scale_x, "scale_nm_per_px x")
    scale_y = _normalize_positive_finite(scale_y, "scale_nm_per_px y")
    return x_px * scale_x, y_px * scale_y
