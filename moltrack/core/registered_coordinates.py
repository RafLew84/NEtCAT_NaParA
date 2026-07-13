from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

import numpy as np
from scipy.ndimage import affine_transform

from .detections import MolecularDetection
from .segmentations import MolecularSegmentation


@dataclass(frozen=True)
class RegisteredFrameTransform:
    """Translation between one raw frame and its observed expanded-canvas footprint."""

    raw_shape: tuple[int, int]
    expanded_shape: tuple[int, int]
    frame_origin_xy: tuple[float, float]

    def __post_init__(self) -> None:
        object.__setattr__(self, "raw_shape", _normalize_shape(self.raw_shape, "raw_shape"))
        object.__setattr__(self, "expanded_shape", _normalize_shape(self.expanded_shape, "expanded_shape"))
        try:
            origin_x, origin_y = (float(value) for value in self.frame_origin_xy)
        except (TypeError, ValueError) as exc:
            raise ValueError("frame_origin_xy must contain x and y.") from exc
        if not isfinite(origin_x) or not isfinite(origin_y):
            raise ValueError("frame_origin_xy values must be finite.")
        object.__setattr__(self, "frame_origin_xy", (origin_x, origin_y))

    def raw_bbox_to_expanded(
        self,
        bbox_xyxy: tuple[float, float, float, float],
    ) -> tuple[float, float, float, float]:
        x1, y1, x2, y2 = _normalize_bbox(bbox_xyxy)
        origin_x, origin_y = self.frame_origin_xy
        return x1 + origin_x, y1 + origin_y, x2 + origin_x, y2 + origin_y

    def expanded_bbox_to_raw(
        self,
        bbox_xyxy: tuple[float, float, float, float],
    ) -> tuple[float, float, float, float]:
        x1, y1, x2, y2 = _normalize_bbox(bbox_xyxy)
        origin_x, origin_y = self.frame_origin_xy
        return x1 - origin_x, y1 - origin_y, x2 - origin_x, y2 - origin_y

    def expanded_prompt_bbox_to_raw(
        self,
        bbox_xyxy: tuple[float, float, float, float],
    ) -> tuple[float, float, float, float]:
        x1, y1, x2, y2 = self.expanded_bbox_to_raw(bbox_xyxy)
        raw_height, raw_width = self.raw_shape
        clipped = (
            min(max(x1, 0.0), float(raw_width)),
            min(max(y1, 0.0), float(raw_height)),
            min(max(x2, 0.0), float(raw_width)),
            min(max(y2, 0.0), float(raw_height)),
        )
        if clipped[2] <= clipped[0] or clipped[3] <= clipped[1]:
            raise ValueError("Expanded prompt bbox does not overlap the observed raw frame footprint.")
        return clipped

    def raw_polygon_to_expanded(
        self,
        polygon_xy: tuple[tuple[float, float], ...],
    ) -> tuple[tuple[float, float], ...]:
        origin_x, origin_y = self.frame_origin_xy
        return tuple((float(x) + origin_x, float(y) + origin_y) for x, y in polygon_xy)

    def raw_mask_to_expanded(self, mask: np.ndarray) -> np.ndarray:
        raw_mask = np.asarray(mask, dtype=bool)
        if raw_mask.shape != self.raw_shape:
            raise ValueError("Raw mask shape must match raw_shape.")
        origin_x, origin_y = self.frame_origin_xy
        expanded = affine_transform(
            raw_mask.astype(np.uint8),
            matrix=np.eye(2, dtype=np.float64),
            offset=(-origin_y, -origin_x),
            output_shape=self.expanded_shape,
            order=0,
            mode="constant",
            cval=0,
            prefilter=False,
        )
        return np.asarray(expanded, dtype=bool)

    def raw_detection_to_expanded(self, detection: MolecularDetection) -> MolecularDetection:
        if not isinstance(detection, MolecularDetection):
            raise TypeError("detection must be a MolecularDetection instance.")
        if detection.source_view != "raw":
            raise ValueError("Only a raw MolecularDetection can be transformed to expanded coordinates.")
        return MolecularDetection(
            frame_index=detection.frame_index,
            bbox_xyxy=self.raw_bbox_to_expanded(detection.bbox_xyxy),
            original_bbox_xyxy=self.raw_bbox_to_expanded(detection.original_bbox_xyxy),
            confidence=detection.confidence,
            selected=detection.selected,
            model_name=detection.model_name,
            checkpoint_path=detection.checkpoint_path,
            source_view="expanded_aligned",
            detection_id=detection.detection_id,
            origin=detection.origin,
        )

    def expanded_detection_to_raw_prompt(self, detection: MolecularDetection) -> MolecularDetection:
        if not isinstance(detection, MolecularDetection):
            raise TypeError("detection must be a MolecularDetection instance.")
        if detection.source_view != "expanded_aligned":
            raise ValueError("Only an expanded MolecularDetection can be mapped to a raw prompt.")
        raw_bbox = self.expanded_prompt_bbox_to_raw(detection.bbox_xyxy)
        return MolecularDetection(
            frame_index=detection.frame_index,
            bbox_xyxy=raw_bbox,
            original_bbox_xyxy=raw_bbox,
            confidence=detection.confidence,
            selected=detection.selected,
            model_name=detection.model_name,
            checkpoint_path=detection.checkpoint_path,
            source_view="raw",
            detection_id=detection.detection_id,
            origin=detection.origin,
        )

    def raw_segmentation_to_expanded(
        self,
        segmentation: MolecularSegmentation,
    ) -> MolecularSegmentation:
        if not isinstance(segmentation, MolecularSegmentation):
            raise TypeError("segmentation must be a MolecularSegmentation instance.")
        if segmentation.source_view != "raw":
            raise ValueError("Only a raw MolecularSegmentation can be transformed to expanded coordinates.")
        metadata = dict(segmentation.metadata)
        metadata["inference_source_view"] = "raw"
        metadata["registered_frame_origin_xy"] = list(self.frame_origin_xy)
        return MolecularSegmentation(
            frame_index=segmentation.frame_index,
            source_view="expanded_aligned",
            bbox_xyxy=(
                None
                if segmentation.bbox_xyxy is None
                else self.raw_bbox_to_expanded(segmentation.bbox_xyxy)
            ),
            mask=(None if segmentation.mask is None else self.raw_mask_to_expanded(segmentation.mask)),
            original_mask=(
                None
                if segmentation.original_mask is None
                else self.raw_mask_to_expanded(segmentation.original_mask)
            ),
            polygon_xy=(
                None
                if segmentation.polygon_xy is None
                else self.raw_polygon_to_expanded(segmentation.polygon_xy)
            ),
            score=segmentation.score,
            origin=segmentation.origin,
            prompt_detection_ids=segmentation.prompt_detection_ids,
            model_name=segmentation.model_name,
            metadata=metadata,
            segmentation_id=segmentation.segmentation_id,
        )


def _normalize_shape(shape: tuple[int, int], name: str) -> tuple[int, int]:
    try:
        height, width = (int(value) for value in shape)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must contain height and width.") from exc
    if height <= 0 or width <= 0:
        raise ValueError(f"{name} values must be positive.")
    return height, width


def _normalize_bbox(
    bbox_xyxy: tuple[float, float, float, float],
) -> tuple[float, float, float, float]:
    try:
        x1, y1, x2, y2 = (float(value) for value in bbox_xyxy)
    except (TypeError, ValueError) as exc:
        raise ValueError("bbox_xyxy must contain four numeric values.") from exc
    if not all(isfinite(value) for value in (x1, y1, x2, y2)):
        raise ValueError("bbox_xyxy values must be finite.")
    if x2 <= x1 or y2 <= y1:
        raise ValueError("bbox_xyxy must satisfy x2 > x1 and y2 > y1.")
    return x1, y1, x2, y2
