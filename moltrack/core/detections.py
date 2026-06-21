from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite
from uuid import uuid4


SUPPORTED_DETECTION_SOURCE_VIEWS = ("raw", "expanded_aligned")
SUPPORTED_DETECTION_ORIGINS = ("yolo", "manual")


@dataclass
class MolecularDetection:
    """One MolTrack molecular bbox detection on one working-series frame."""

    frame_index: int
    bbox_xyxy: tuple[float, float, float, float]
    confidence: float
    selected: bool = True
    model_name: str = ""
    checkpoint_path: str = ""
    source_view: str = "raw"
    original_bbox_xyxy: tuple[float, float, float, float] | None = None
    detection_id: str | None = None
    origin: str | None = None

    def __post_init__(self) -> None:
        frame_index = int(self.frame_index)
        if frame_index < 0:
            raise ValueError("frame_index must be non-negative.")

        bbox_xyxy = _normalize_bbox_xyxy(self.bbox_xyxy, field_name="bbox_xyxy")
        if self.original_bbox_xyxy is None:
            original_bbox_xyxy = bbox_xyxy
        else:
            original_bbox_xyxy = _normalize_bbox_xyxy(
                self.original_bbox_xyxy,
                field_name="original_bbox_xyxy",
            )

        confidence = float(self.confidence)
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1.")

        source_view = str(self.source_view).strip()
        if source_view not in SUPPORTED_DETECTION_SOURCE_VIEWS:
            supported = ", ".join(SUPPORTED_DETECTION_SOURCE_VIEWS)
            raise ValueError(f"Unsupported source_view: {source_view!r}. Supported: {supported}.")

        self.frame_index = frame_index
        self.bbox_xyxy = bbox_xyxy
        self.original_bbox_xyxy = original_bbox_xyxy
        self.confidence = confidence
        self.selected = bool(self.selected)
        self.model_name = str(self.model_name)
        self.checkpoint_path = str(self.checkpoint_path)
        self.source_view = source_view
        self.detection_id = _normalize_detection_id(self.detection_id)
        self.origin = _normalize_detection_origin(self.origin, model_name=self.model_name)

    def validate_within_frame(self, frame_shape: tuple[int, int]) -> None:
        _validate_bbox_within_frame(self.bbox_xyxy, frame_shape, field_name="bbox_xyxy")
        _validate_bbox_within_frame(
            self.original_bbox_xyxy,
            frame_shape,
            field_name="original_bbox_xyxy",
        )


@dataclass
class MolecularDetectionSet:
    """Frame-indexed MolTrack molecular bbox detections."""

    frame_count: int
    detections_by_frame: dict[int, list[MolecularDetection]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        frame_count = int(self.frame_count)
        if frame_count <= 0:
            raise ValueError("frame_count must be positive.")
        self.frame_count = frame_count

        normalized: dict[int, list[MolecularDetection]] = {}
        for frame_index, detections in self.detections_by_frame.items():
            frame_index = self._validate_frame_index(frame_index)
            normalized[frame_index] = self._normalize_detections(frame_index, detections)
        self.detections_by_frame = normalized

    @property
    def detection_count(self) -> int:
        return sum(len(detections) for detections in self.detections_by_frame.values())

    def get_detections(self, frame_index: int, *, source_view: str | None = None) -> list[MolecularDetection]:
        frame_index = self._validate_frame_index(frame_index)
        detections = list(self.detections_by_frame.get(frame_index, []))
        if source_view is None:
            return detections
        source_view = _normalize_source_view(source_view)
        return [detection for detection in detections if detection.source_view == source_view]

    def get_detection(self, detection_id: str) -> MolecularDetection | None:
        detection_id = _normalize_detection_id(detection_id)
        for detections in self.detections_by_frame.values():
            for detection in detections:
                if detection.detection_id == detection_id:
                    return detection
        return None

    def set_detections(
        self,
        frame_index: int,
        detections: list[MolecularDetection],
        *,
        source_view: str,
        frame_shape: tuple[int, int] | None = None,
    ) -> None:
        frame_index = self._validate_frame_index(frame_index)
        source_view = _normalize_source_view(source_view)
        normalized = self._normalize_detections(frame_index, detections)
        for detection in normalized:
            if detection.source_view != source_view:
                raise ValueError("Detection source_view must match the requested source_view.")
            if frame_shape is not None:
                detection.validate_within_frame(frame_shape)

        existing = [
            detection
            for detection in self.detections_by_frame.get(frame_index, [])
            if detection.source_view != source_view
        ]
        self.detections_by_frame[frame_index] = existing + normalized
        if not self.detections_by_frame[frame_index]:
            del self.detections_by_frame[frame_index]

    def clear_frame(self, frame_index: int, *, source_view: str | None = None) -> int:
        frame_index = self._validate_frame_index(frame_index)
        existing = self.detections_by_frame.get(frame_index, [])
        if source_view is None:
            removed = len(existing)
            self.detections_by_frame.pop(frame_index, None)
            return removed

        source_view = _normalize_source_view(source_view)
        kept = [detection for detection in existing if detection.source_view != source_view]
        removed = len(existing) - len(kept)
        if kept:
            self.detections_by_frame[frame_index] = kept
        else:
            self.detections_by_frame.pop(frame_index, None)
        return removed

    def remove_detection(self, detection_id: str) -> MolecularDetection:
        detection_id = _normalize_detection_id(detection_id)
        for frame_index, detections in list(self.detections_by_frame.items()):
            for position, detection in enumerate(detections):
                if detection.detection_id != detection_id:
                    continue
                removed = detections.pop(position)
                if detections:
                    self.detections_by_frame[frame_index] = detections
                else:
                    self.detections_by_frame.pop(frame_index, None)
                return removed
        raise KeyError(f"Unknown molecular detection_id: {detection_id}")

    def update_detection_bbox(
        self,
        detection_id: str,
        bbox_xyxy: tuple[float, float, float, float],
        *,
        frame_shape: tuple[int, int] | None = None,
        update_original: bool = False,
    ) -> MolecularDetection:
        detection = self.get_detection(detection_id)
        if detection is None:
            raise KeyError(f"Unknown molecular detection_id: {_normalize_detection_id(detection_id)}")

        bbox_xyxy = _normalize_bbox_xyxy(bbox_xyxy, field_name="bbox_xyxy")
        previous_bbox = detection.bbox_xyxy
        previous_original = detection.original_bbox_xyxy
        detection.bbox_xyxy = bbox_xyxy
        if update_original:
            detection.original_bbox_xyxy = bbox_xyxy
        try:
            if frame_shape is not None:
                detection.validate_within_frame(frame_shape)
        except Exception:
            detection.bbox_xyxy = previous_bbox
            detection.original_bbox_xyxy = previous_original
            raise
        return detection

    def clear_all(self, *, source_view: str | None = None) -> int:
        if source_view is None:
            removed = self.detection_count
            self.detections_by_frame.clear()
            return removed

        removed = 0
        for frame_index in list(self.detections_by_frame):
            removed += self.clear_frame(frame_index, source_view=source_view)
        return removed

    def set_frame_selected(self, frame_index: int, selected: bool, *, source_view: str | None = None) -> int:
        frame_index = self._validate_frame_index(frame_index)
        selected = bool(selected)
        changed = 0
        for detection in self.get_detections(frame_index, source_view=source_view):
            if detection.selected != selected:
                detection.selected = selected
                changed += 1
        return changed

    def set_all_selected(self, selected: bool, *, source_view: str | None = None) -> int:
        changed = 0
        for frame_index in range(self.frame_count):
            changed += self.set_frame_selected(frame_index, selected, source_view=source_view)
        return changed

    def add_detection(
        self,
        frame_index: int,
        bbox_xyxy: tuple[float, float, float, float],
        *,
        source_view: str,
        frame_shape: tuple[int, int] | None = None,
        confidence: float = 1.0,
        selected: bool = True,
        model_name: str = "manual",
        checkpoint_path: str = "",
        detection_id: str | None = None,
        origin: str = "manual",
    ) -> MolecularDetection:
        frame_index = self._validate_frame_index(frame_index)
        source_view = _normalize_source_view(source_view)
        detection = MolecularDetection(
            frame_index=frame_index,
            bbox_xyxy=bbox_xyxy,
            confidence=confidence,
            selected=selected,
            model_name=model_name,
            checkpoint_path=checkpoint_path,
            source_view=source_view,
            detection_id=detection_id,
            origin=origin,
        )
        if self.get_detection(detection.detection_id) is not None:
            raise ValueError(f"Duplicate detection_id: {detection.detection_id}")
        if frame_shape is not None:
            detection.validate_within_frame(frame_shape)
        self.detections_by_frame.setdefault(frame_index, []).append(detection)
        return detection

    def resize_all(
        self,
        *,
        frame_shape: tuple[int, int],
        source_view: str | None = None,
        scale_factor: float | None = None,
        margin_px: float | None = None,
        min_size_px: float = 1.0,
    ) -> int:
        """Resize matching detections around their current bbox centers."""

        _normalize_frame_shape(frame_shape)
        if source_view is not None:
            source_view = _normalize_source_view(source_view)

        if (scale_factor is None) == (margin_px is None):
            raise ValueError("Provide exactly one of scale_factor or margin_px.")

        if scale_factor is not None:
            scale_factor = float(scale_factor)
            if not isfinite(scale_factor) or scale_factor <= 0.0:
                raise ValueError("scale_factor must be a positive finite value.")
        if margin_px is not None:
            margin_px = float(margin_px)
            if not isfinite(margin_px):
                raise ValueError("margin_px must be finite.")

        min_size_px = float(min_size_px)
        if not isfinite(min_size_px) or min_size_px <= 0.0:
            raise ValueError("min_size_px must be a positive finite value.")

        changed = 0
        for detection in self._iter_matching_detections(source_view=source_view):
            detection.bbox_xyxy = _resize_bbox_about_center(
                detection.bbox_xyxy,
                frame_shape=frame_shape,
                scale_factor=scale_factor,
                margin_px=margin_px,
                min_size_px=min_size_px,
            )
            changed += 1
        return changed

    def reset_all_to_original(
        self,
        *,
        source_view: str | None = None,
        frame_shape: tuple[int, int] | None = None,
    ) -> int:
        if source_view is not None:
            source_view = _normalize_source_view(source_view)
        if frame_shape is not None:
            _normalize_frame_shape(frame_shape)

        changed = 0
        for detection in self._iter_matching_detections(source_view=source_view):
            detection.bbox_xyxy = detection.original_bbox_xyxy
            if frame_shape is not None:
                detection.validate_within_frame(frame_shape)
            changed += 1
        return changed

    def _validate_frame_index(self, frame_index: int) -> int:
        frame_index = int(frame_index)
        if not 0 <= frame_index < self.frame_count:
            raise IndexError("frame_index is out of range.")
        return frame_index

    def _iter_matching_detections(self, *, source_view: str | None) -> list[MolecularDetection]:
        detections: list[MolecularDetection] = []
        for frame_index in range(self.frame_count):
            for detection in self.detections_by_frame.get(frame_index, []):
                if source_view is None or detection.source_view == source_view:
                    detections.append(detection)
        return detections

    @staticmethod
    def _normalize_detections(frame_index: int, detections: list[MolecularDetection]) -> list[MolecularDetection]:
        normalized = list(detections)
        for detection in normalized:
            if not isinstance(detection, MolecularDetection):
                raise TypeError("detections must contain MolecularDetection instances.")
            if detection.frame_index != frame_index:
                raise ValueError("Detection frame_index must match the frame key.")
        return normalized


def _normalize_source_view(source_view: str) -> str:
    source_view = str(source_view).strip()
    if source_view not in SUPPORTED_DETECTION_SOURCE_VIEWS:
        supported = ", ".join(SUPPORTED_DETECTION_SOURCE_VIEWS)
        raise ValueError(f"Unsupported source_view: {source_view!r}. Supported: {supported}.")
    return source_view


def _normalize_detection_id(detection_id: str | None) -> str:
    if detection_id is None:
        return uuid4().hex
    detection_id = str(detection_id).strip()
    if not detection_id:
        raise ValueError("detection_id must be a non-empty string.")
    return detection_id


def _normalize_detection_origin(origin: str | None, *, model_name: str) -> str:
    if origin is None:
        origin = "manual" if str(model_name).strip().lower() == "manual" else "yolo"
    origin = str(origin).strip().lower()
    if origin not in SUPPORTED_DETECTION_ORIGINS:
        supported = ", ".join(SUPPORTED_DETECTION_ORIGINS)
        raise ValueError(f"Unsupported origin: {origin!r}. Supported: {supported}.")
    return origin


def _normalize_bbox_xyxy(
    bbox_xyxy: tuple[float, float, float, float],
    *,
    field_name: str,
) -> tuple[float, float, float, float]:
    try:
        x1, y1, x2, y2 = (float(value) for value in bbox_xyxy)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must contain four numeric values.") from exc
    if not all(isfinite(value) for value in (x1, y1, x2, y2)):
        raise ValueError(f"{field_name} values must be finite.")
    if x2 <= x1 or y2 <= y1:
        raise ValueError(f"{field_name} must satisfy x2 > x1 and y2 > y1.")
    return (x1, y1, x2, y2)


def _normalize_frame_shape(frame_shape: tuple[int, int]) -> tuple[int, int]:
    try:
        height, width = (int(value) for value in frame_shape)
    except (TypeError, ValueError) as exc:
        raise ValueError("frame_shape must contain height and width.") from exc
    if height <= 0 or width <= 0:
        raise ValueError("frame_shape must contain positive height and width.")
    return height, width


def _validate_bbox_within_frame(
    bbox_xyxy: tuple[float, float, float, float],
    frame_shape: tuple[int, int],
    *,
    field_name: str,
) -> None:
    height, width = _normalize_frame_shape(frame_shape)
    x1, y1, x2, y2 = bbox_xyxy
    if x1 < 0.0 or y1 < 0.0 or x2 > float(width) or y2 > float(height):
        raise ValueError(f"{field_name} must be within frame bounds.")


def _resize_bbox_about_center(
    bbox_xyxy: tuple[float, float, float, float],
    *,
    frame_shape: tuple[int, int],
    scale_factor: float | None,
    margin_px: float | None,
    min_size_px: float,
) -> tuple[float, float, float, float]:
    height, width = _normalize_frame_shape(frame_shape)
    x1, y1, x2, y2 = bbox_xyxy
    current_width = x2 - x1
    current_height = y2 - y1
    if scale_factor is not None:
        requested_width = current_width * scale_factor
        requested_height = current_height * scale_factor
    elif margin_px is not None:
        requested_width = current_width + (2.0 * margin_px)
        requested_height = current_height + (2.0 * margin_px)
    else:
        raise ValueError("Provide exactly one of scale_factor or margin_px.")

    new_width = min(max(requested_width, min_size_px), float(width))
    new_height = min(max(requested_height, min_size_px), float(height))
    center_x = (x1 + x2) / 2.0
    center_y = (y1 + y2) / 2.0

    resized_x1 = center_x - (new_width / 2.0)
    resized_y1 = center_y - (new_height / 2.0)
    resized_x2 = center_x + (new_width / 2.0)
    resized_y2 = center_y + (new_height / 2.0)

    resized_x1, resized_x2 = _shift_interval_into_bounds(resized_x1, resized_x2, float(width))
    resized_y1, resized_y2 = _shift_interval_into_bounds(resized_y1, resized_y2, float(height))
    return _normalize_bbox_xyxy(
        (resized_x1, resized_y1, resized_x2, resized_y2),
        field_name="bbox_xyxy",
    )


def _shift_interval_into_bounds(start: float, end: float, upper_bound: float) -> tuple[float, float]:
    if start < 0.0:
        end -= start
        start = 0.0
    if end > upper_bound:
        start -= end - upper_bound
        end = upper_bound
    if start < 0.0:
        start = 0.0
    return start, end
