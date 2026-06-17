from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite


SUPPORTED_DETECTION_SOURCE_VIEWS = ("raw", "expanded_aligned")


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

    def __post_init__(self) -> None:
        frame_index = int(self.frame_index)
        if frame_index < 0:
            raise ValueError("frame_index must be non-negative.")

        try:
            x1, y1, x2, y2 = (float(value) for value in self.bbox_xyxy)
        except (TypeError, ValueError) as exc:
            raise ValueError("bbox_xyxy must contain four numeric values.") from exc
        if not all(isfinite(value) for value in (x1, y1, x2, y2)):
            raise ValueError("bbox_xyxy values must be finite.")
        if x2 <= x1 or y2 <= y1:
            raise ValueError("bbox_xyxy must satisfy x2 > x1 and y2 > y1.")

        confidence = float(self.confidence)
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1.")

        source_view = str(self.source_view).strip()
        if source_view not in SUPPORTED_DETECTION_SOURCE_VIEWS:
            supported = ", ".join(SUPPORTED_DETECTION_SOURCE_VIEWS)
            raise ValueError(f"Unsupported source_view: {source_view!r}. Supported: {supported}.")

        self.frame_index = frame_index
        self.bbox_xyxy = (x1, y1, x2, y2)
        self.confidence = confidence
        self.selected = bool(self.selected)
        self.model_name = str(self.model_name)
        self.checkpoint_path = str(self.checkpoint_path)
        self.source_view = source_view

    def validate_within_frame(self, frame_shape: tuple[int, int]) -> None:
        try:
            height, width = (int(value) for value in frame_shape)
        except (TypeError, ValueError) as exc:
            raise ValueError("frame_shape must contain height and width.") from exc
        if height <= 0 or width <= 0:
            raise ValueError("frame_shape must contain positive height and width.")

        x1, y1, x2, y2 = self.bbox_xyxy
        if x1 < 0.0 or y1 < 0.0 or x2 > float(width) or y2 > float(height):
            raise ValueError("bbox_xyxy must be within frame bounds.")


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

    def _validate_frame_index(self, frame_index: int) -> int:
        frame_index = int(frame_index)
        if not 0 <= frame_index < self.frame_count:
            raise IndexError("frame_index is out of range.")
        return frame_index

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
