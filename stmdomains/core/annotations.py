"""Immutable annotations prepared for one frame and one image coordinate system."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from numpy.typing import NDArray

BBox = tuple[float, float, float, float]
Polygon = tuple[tuple[float, float], ...]


@dataclass(frozen=True)
class Detection:
    detection_id: str
    frame_index: int
    bbox_xyxy: BBox
    source_bbox_xyxy: BBox
    original_bbox_xyxy: BBox | None
    source_view: str
    outside_field: bool
    metadata: Mapping[str, Any] = field(repr=False)

    @property
    def center_xy(self) -> tuple[float, float]:
        x1, y1, x2, y2 = self.bbox_xyxy
        return (x1 + x2) / 2, (y1 + y2) / 2


@dataclass(frozen=True)
class Segmentation:
    segmentation_id: str
    frame_index: int
    bbox_xyxy: BBox | None
    polygon_xy: Polygon | None
    mask: NDArray[np.bool_] | None = field(repr=False)
    prompt_detection_ids: tuple[str, ...]
    source_view: str
    metadata: Mapping[str, Any] = field(repr=False)
    diagnostics: tuple[str, ...] = ()


@dataclass(frozen=True)
class FrameAnnotations:
    detections: tuple[Detection, ...]
    segmentations: tuple[Segmentation, ...]
    diagnostics: tuple[str, ...]
    detection_state: str
    segmentation_state: str
    detection_message: str
    segmentation_message: str
