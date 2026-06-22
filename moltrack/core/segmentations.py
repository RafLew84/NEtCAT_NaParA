from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite
from typing import Any
from uuid import uuid4

import numpy as np


SUPPORTED_SEGMENTATION_SOURCE_VIEWS = ("raw", "expanded_aligned")


@dataclass
class MolecularSegmentation:
    """One MolTrack molecular mask or polygon on one working-series frame."""

    frame_index: int
    source_view: str = "raw"
    bbox_xyxy: tuple[float, float, float, float] | None = None
    mask: Any | None = None
    original_mask: Any | None = None
    polygon_xy: Any | None = None
    score: float | None = None
    origin: str = "manual"
    prompt_detection_ids: tuple[str, ...] = ()
    model_name: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    segmentation_id: str | None = None

    def __post_init__(self) -> None:
        frame_index = int(self.frame_index)
        if frame_index < 0:
            raise ValueError("frame_index must be non-negative.")

        source_view = _normalize_source_view(self.source_view)
        bbox_xyxy = None if self.bbox_xyxy is None else _normalize_bbox_xyxy(self.bbox_xyxy)
        mask = _normalize_mask(self.mask)
        original_mask = _normalize_mask(self.original_mask)
        polygon_xy = _normalize_polygon_xy(self.polygon_xy)
        if mask is None and polygon_xy is None:
            raise ValueError("MolecularSegmentation requires a mask or polygon_xy.")
        if mask is not None and original_mask is not None and original_mask.shape != mask.shape:
            raise ValueError("original_mask shape must match mask shape.")

        score = _normalize_score(self.score)
        origin = str(self.origin).strip().lower()
        if not origin:
            raise ValueError("origin must be a non-empty string.")

        self.frame_index = frame_index
        self.source_view = source_view
        self.bbox_xyxy = bbox_xyxy
        self.mask = mask
        self.original_mask = original_mask
        self.polygon_xy = polygon_xy
        self.score = score
        self.origin = origin
        self.prompt_detection_ids = _normalize_prompt_detection_ids(self.prompt_detection_ids)
        self.model_name = str(self.model_name)
        self.metadata = dict(self.metadata)
        self.segmentation_id = _normalize_segmentation_id(self.segmentation_id)


@dataclass
class MolecularSegmentationSet:
    """Frame-indexed MolTrack molecular segmentations."""

    frame_count: int
    segmentations_by_frame: dict[int, list[MolecularSegmentation]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        frame_count = int(self.frame_count)
        if frame_count <= 0:
            raise ValueError("frame_count must be positive.")
        self.frame_count = frame_count

        normalized: dict[int, list[MolecularSegmentation]] = {}
        seen_ids: set[str] = set()
        for frame_index, segmentations in self.segmentations_by_frame.items():
            frame_index = self._validate_frame_index(frame_index)
            normalized_segmentations = self._normalize_segmentations(frame_index, segmentations)
            for segmentation in normalized_segmentations:
                if segmentation.segmentation_id in seen_ids:
                    raise ValueError(f"Duplicate segmentation_id: {segmentation.segmentation_id}")
                seen_ids.add(segmentation.segmentation_id)
            normalized[frame_index] = normalized_segmentations
        self.segmentations_by_frame = normalized

    @property
    def segmentation_count(self) -> int:
        return sum(len(segmentations) for segmentations in self.segmentations_by_frame.values())

    def add_segmentation(self, segmentation: MolecularSegmentation) -> MolecularSegmentation:
        if not isinstance(segmentation, MolecularSegmentation):
            raise TypeError("segmentation must be a MolecularSegmentation instance.")
        frame_index = self._validate_frame_index(segmentation.frame_index)
        if self.get_segmentation(segmentation.segmentation_id) is not None:
            raise ValueError(f"Duplicate segmentation_id: {segmentation.segmentation_id}")
        self.segmentations_by_frame.setdefault(frame_index, []).append(segmentation)
        return segmentation

    def get_segmentations(
        self,
        frame_index: int,
        *,
        source_view: str | None = None,
    ) -> list[MolecularSegmentation]:
        frame_index = self._validate_frame_index(frame_index)
        segmentations = list(self.segmentations_by_frame.get(frame_index, []))
        if source_view is None:
            return segmentations
        source_view = _normalize_source_view(source_view)
        return [segmentation for segmentation in segmentations if segmentation.source_view == source_view]

    def get_segmentation(self, segmentation_id: str) -> MolecularSegmentation | None:
        segmentation_id = _normalize_segmentation_id(segmentation_id)
        for segmentations in self.segmentations_by_frame.values():
            for segmentation in segmentations:
                if segmentation.segmentation_id == segmentation_id:
                    return segmentation
        return None

    def remove_segmentation(self, segmentation_id: str) -> MolecularSegmentation:
        segmentation_id = _normalize_segmentation_id(segmentation_id)
        for frame_index, segmentations in list(self.segmentations_by_frame.items()):
            for position, segmentation in enumerate(segmentations):
                if segmentation.segmentation_id != segmentation_id:
                    continue
                removed = segmentations.pop(position)
                if segmentations:
                    self.segmentations_by_frame[frame_index] = segmentations
                else:
                    self.segmentations_by_frame.pop(frame_index, None)
                return removed
        raise KeyError(f"Unknown molecular segmentation_id: {segmentation_id}")

    def clear_frame(self, frame_index: int, *, source_view: str | None = None) -> int:
        frame_index = self._validate_frame_index(frame_index)
        existing = self.segmentations_by_frame.get(frame_index, [])
        if source_view is None:
            removed = len(existing)
            self.segmentations_by_frame.pop(frame_index, None)
            return removed

        source_view = _normalize_source_view(source_view)
        kept = [segmentation for segmentation in existing if segmentation.source_view != source_view]
        removed = len(existing) - len(kept)
        if kept:
            self.segmentations_by_frame[frame_index] = kept
        else:
            self.segmentations_by_frame.pop(frame_index, None)
        return removed

    def _validate_frame_index(self, frame_index: int) -> int:
        frame_index = int(frame_index)
        if not 0 <= frame_index < self.frame_count:
            raise IndexError("frame_index is out of range.")
        return frame_index

    @staticmethod
    def _normalize_segmentations(
        frame_index: int,
        segmentations: list[MolecularSegmentation],
    ) -> list[MolecularSegmentation]:
        normalized = list(segmentations)
        for segmentation in normalized:
            if not isinstance(segmentation, MolecularSegmentation):
                raise TypeError("segmentations must contain MolecularSegmentation instances.")
            if segmentation.frame_index != frame_index:
                raise ValueError("Segmentation frame_index must match the frame key.")
        return normalized


def _normalize_source_view(source_view: str) -> str:
    source_view = str(source_view).strip()
    if source_view not in SUPPORTED_SEGMENTATION_SOURCE_VIEWS:
        supported = ", ".join(SUPPORTED_SEGMENTATION_SOURCE_VIEWS)
        raise ValueError(f"Unsupported source_view: {source_view!r}. Supported: {supported}.")
    return source_view


def _normalize_segmentation_id(segmentation_id: str | None) -> str:
    if segmentation_id is None:
        return uuid4().hex
    segmentation_id = str(segmentation_id).strip()
    if not segmentation_id:
        raise ValueError("segmentation_id must be a non-empty string.")
    return segmentation_id


def _normalize_bbox_xyxy(bbox_xyxy: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    try:
        x1, y1, x2, y2 = (float(value) for value in bbox_xyxy)
    except (TypeError, ValueError) as exc:
        raise ValueError("bbox_xyxy must contain four numeric values.") from exc
    if not all(isfinite(value) for value in (x1, y1, x2, y2)):
        raise ValueError("bbox_xyxy values must be finite.")
    if x2 <= x1 or y2 <= y1:
        raise ValueError("bbox_xyxy must satisfy x2 > x1 and y2 > y1.")
    return x1, y1, x2, y2


def _normalize_mask(mask: Any | None) -> np.ndarray | None:
    if mask is None:
        return None
    mask_array = np.asarray(mask, dtype=bool)
    if mask_array.ndim != 2:
        raise ValueError("mask must be a 2D array.")
    if mask_array.shape[0] == 0 or mask_array.shape[1] == 0:
        raise ValueError("mask must have positive height and width.")
    return mask_array.copy()


def _normalize_polygon_xy(polygon_xy: Any | None) -> tuple[tuple[float, float], ...] | None:
    if polygon_xy is None:
        return None
    try:
        normalized = tuple((float(point[0]), float(point[1])) for point in polygon_xy)
    except (TypeError, ValueError, IndexError) as exc:
        raise ValueError("polygon_xy must contain xy point pairs.") from exc
    if len(normalized) < 3:
        raise ValueError("polygon_xy must contain at least three points.")
    for x, y in normalized:
        if not isfinite(x) or not isfinite(y):
            raise ValueError("polygon_xy values must be finite.")
    return normalized


def _normalize_score(score: float | None) -> float | None:
    if score is None:
        return None
    score = float(score)
    if not isfinite(score) or not 0.0 <= score <= 1.0:
        raise ValueError("score must be between 0 and 1.")
    return score


def _normalize_prompt_detection_ids(prompt_detection_ids: Any) -> tuple[str, ...]:
    if prompt_detection_ids is None:
        return ()
    if isinstance(prompt_detection_ids, str):
        values = (prompt_detection_ids,)
    else:
        values = tuple(prompt_detection_ids)
    normalized: list[str] = []
    for detection_id in values:
        detection_id = str(detection_id).strip()
        if not detection_id:
            raise ValueError("prompt_detection_ids must contain non-empty strings.")
        normalized.append(detection_id)
    return tuple(normalized)
