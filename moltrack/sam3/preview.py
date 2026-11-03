from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from math import isfinite
from typing import Any, Mapping
from uuid import uuid4

import numpy as np

from moltrack.core import (
    MolecularDetection,
    MolecularDetectionSet,
    MolecularSegmentation,
    MolecularSegmentationSet,
)

from .adapter import MolTrackSam3Proposal
from .contract import SUPPORTED_SAM3_SOURCE_VIEWS


SUPPORTED_SAM3_COMMIT_MODES = ("bboxes", "segmentations", "both")


@dataclass(frozen=True)
class MolTrackSam3PreviewSettings:
    score_threshold: float = 0.3
    mask_threshold: float = 0.5
    max_results: int = 300
    duplicate_iou_threshold: float = 0.9

    def __post_init__(self) -> None:
        object.__setattr__(self, "score_threshold", _normalize_probability(self.score_threshold, "score_threshold"))
        object.__setattr__(self, "mask_threshold", _normalize_probability(self.mask_threshold, "mask_threshold"))
        object.__setattr__(
            self,
            "duplicate_iou_threshold",
            _normalize_probability(self.duplicate_iou_threshold, "duplicate_iou_threshold"),
        )
        max_results = int(self.max_results)
        if max_results <= 0:
            raise ValueError("SAM3 preview max_results must be positive.")
        object.__setattr__(self, "max_results", max_results)


@dataclass(frozen=True)
class MolTrackSam3PreviewProposal:
    frame_index: int
    source_view: str
    bbox_xyxy: tuple[float, float, float, float]
    score: float
    mask: Any | None = None
    polygon_xy: Any | None = None
    prompt_detection_ids: tuple[str, ...] = ()
    model_name: str = ""
    metadata: Mapping[str, object] = field(default_factory=dict)
    proposal_id: str | None = None

    def __post_init__(self) -> None:
        frame_index = int(self.frame_index)
        if frame_index < 0:
            raise ValueError("SAM3 preview frame_index must be non-negative.")
        source_view = str(self.source_view).strip()
        if source_view not in SUPPORTED_SAM3_SOURCE_VIEWS:
            raise ValueError(f"Unsupported SAM3 preview source_view: {source_view!r}.")
        score = _normalize_probability(self.score, "proposal score")
        mask = None if self.mask is None else np.asarray(self.mask, dtype=bool).copy()
        if mask is not None and mask.ndim != 2:
            raise ValueError("SAM3 preview mask must be a 2D array.")

        object.__setattr__(self, "frame_index", frame_index)
        object.__setattr__(self, "source_view", source_view)
        object.__setattr__(self, "bbox_xyxy", _normalize_bbox_xyxy(self.bbox_xyxy))
        object.__setattr__(self, "score", score)
        object.__setattr__(self, "mask", mask)
        object.__setattr__(self, "polygon_xy", _normalize_polygon_xy(self.polygon_xy))
        object.__setattr__(self, "prompt_detection_ids", _normalize_prompt_detection_ids(self.prompt_detection_ids))
        object.__setattr__(self, "model_name", str(self.model_name))
        object.__setattr__(self, "metadata", dict(self.metadata))
        object.__setattr__(self, "proposal_id", _normalize_proposal_id(self.proposal_id))


@dataclass(frozen=True)
class MolTrackSam3Preview:
    frame_index: int
    source_view: str
    proposals: tuple[MolTrackSam3PreviewProposal, ...] = ()
    settings: MolTrackSam3PreviewSettings = field(default_factory=MolTrackSam3PreviewSettings)

    def __post_init__(self) -> None:
        frame_index = int(self.frame_index)
        if frame_index < 0:
            raise ValueError("SAM3 preview frame_index must be non-negative.")
        source_view = str(self.source_view).strip()
        if source_view not in SUPPORTED_SAM3_SOURCE_VIEWS:
            raise ValueError(f"Unsupported SAM3 preview source_view: {source_view!r}.")
        proposals = tuple(self.proposals)
        for proposal in proposals:
            if not isinstance(proposal, MolTrackSam3PreviewProposal):
                raise TypeError("SAM3 preview proposals must be MolTrackSam3PreviewProposal instances.")
            if proposal.frame_index != frame_index:
                raise ValueError("SAM3 preview proposal frame_index must match preview frame_index.")
            if proposal.source_view != source_view:
                raise ValueError("SAM3 preview proposal source_view must match preview source_view.")

        object.__setattr__(self, "frame_index", frame_index)
        object.__setattr__(self, "source_view", source_view)
        object.__setattr__(self, "proposals", proposals)

    @property
    def proposal_count(self) -> int:
        return len(self.proposals)

    def matches_context(self, *, frame_index: int, source_view: str) -> bool:
        return self.frame_index == int(frame_index) and self.source_view == str(source_view).strip()


@dataclass(frozen=True)
class MolTrackSam3CommitResult:
    added_bbox_count: int = 0
    added_segmentation_count: int = 0
    skipped_duplicate_count: int = 0
    replaced_bbox_count: int = 0
    replaced_segmentation_count: int = 0

    @property
    def added_count(self) -> int:
        return self.added_bbox_count + self.added_segmentation_count


def build_moltrack_sam3_preview(
    proposals: Iterable[MolTrackSam3Proposal],
    *,
    frame_index: int,
    source_view: str,
    existing_detections: Iterable[object] = (),
    score_threshold: float = 0.3,
    mask_threshold: float = 0.5,
    max_results: int = 300,
    duplicate_iou_threshold: float = 0.9,
) -> MolTrackSam3Preview:
    settings = MolTrackSam3PreviewSettings(
        score_threshold=score_threshold,
        mask_threshold=mask_threshold,
        max_results=max_results,
        duplicate_iou_threshold=duplicate_iou_threshold,
    )
    frame_index = int(frame_index)
    source_view = str(source_view).strip()
    existing_bboxes = [detection.bbox_xyxy for detection in existing_detections]
    preview_proposals: list[MolTrackSam3PreviewProposal] = []
    for proposal in proposals:
        if proposal.frame_index != frame_index or proposal.source_view != source_view:
            continue
        if proposal.score < settings.score_threshold:
            continue
        if _is_duplicate_bbox(proposal.bbox_xyxy, existing_bboxes, threshold=settings.duplicate_iou_threshold):
            continue
        preview_proposals.append(_proposal_to_preview(proposal))
        if len(preview_proposals) >= settings.max_results:
            break
    return MolTrackSam3Preview(
        frame_index=frame_index,
        source_view=source_view,
        proposals=tuple(preview_proposals),
        settings=settings,
    )


def commit_moltrack_sam3_preview(
    preview: MolTrackSam3Preview,
    *,
    detection_set: MolecularDetectionSet | None = None,
    segmentation_set: MolecularSegmentationSet | None = None,
    mode: str = "both",
    duplicate_iou_threshold: float | None = None,
    frame_shape: tuple[int, int] | None = None,
    replace_existing: bool = False,
) -> MolTrackSam3CommitResult:
    if not isinstance(preview, MolTrackSam3Preview):
        raise TypeError("preview must be a MolTrackSam3Preview instance.")
    mode = str(mode).strip()
    if mode not in SUPPORTED_SAM3_COMMIT_MODES:
        supported = ", ".join(SUPPORTED_SAM3_COMMIT_MODES)
        raise ValueError(f"Unsupported SAM3 commit mode: {mode!r}. Supported: {supported}.")
    if mode in ("bboxes", "both") and detection_set is None:
        raise ValueError("detection_set is required when committing SAM3 preview as BBoxes.")
    if mode in ("segmentations", "both") and segmentation_set is None:
        raise ValueError("segmentation_set is required when committing SAM3 preview as Segmentations.")

    duplicate_iou_threshold = (
        preview.settings.duplicate_iou_threshold
        if duplicate_iou_threshold is None
        else _normalize_probability(duplicate_iou_threshold, "duplicate_iou_threshold")
    )
    replaced_bbox_count = 0
    replaced_segmentation_count = 0
    if replace_existing and detection_set is not None and mode in ("bboxes", "both"):
        replaced_bbox_count = _remove_committed_sam3_detections(detection_set, preview)
    if replace_existing and segmentation_set is not None and mode in ("segmentations", "both"):
        replaced_segmentation_count = _remove_committed_sam3_segmentations(segmentation_set, preview)

    added_bbox_count = 0
    added_segmentation_count = 0
    skipped_duplicate_count = 0
    for proposal in preview.proposals:
        if mode in ("bboxes", "both"):
            if _is_duplicate_proposal_for_detection_set(
                proposal,
                detection_set,
                threshold=duplicate_iou_threshold,
            ):
                skipped_duplicate_count += 1
            else:
                detection_set.add_detection(
                    preview.frame_index,
                    proposal.bbox_xyxy,
                    source_view=preview.source_view,
                    frame_shape=frame_shape,
                    confidence=proposal.score,
                    selected=True,
                    model_name=proposal.model_name,
                    checkpoint_path="",
                    detection_id=f"sam3-bbox-{proposal.proposal_id}",
                    origin="sam3_concept",
                )
                added_bbox_count += 1
        if mode in ("segmentations", "both") and _proposal_has_segmentation_payload(proposal):
            segmentation_set.add_segmentation(_proposal_to_segmentation(proposal))
            added_segmentation_count += 1

    return MolTrackSam3CommitResult(
        added_bbox_count=added_bbox_count,
        added_segmentation_count=added_segmentation_count,
        skipped_duplicate_count=skipped_duplicate_count,
        replaced_bbox_count=replaced_bbox_count,
        replaced_segmentation_count=replaced_segmentation_count,
    )


def _proposal_to_preview(proposal: MolTrackSam3Proposal) -> MolTrackSam3PreviewProposal:
    return MolTrackSam3PreviewProposal(
        frame_index=proposal.frame_index,
        source_view=proposal.source_view,
        bbox_xyxy=proposal.bbox_xyxy,
        score=proposal.score,
        mask=proposal.mask,
        polygon_xy=proposal.polygon_xy,
        prompt_detection_ids=proposal.prompt_detection_ids,
        model_name=proposal.model_name,
        metadata=proposal.metadata,
    )


def _proposal_to_segmentation(proposal: MolTrackSam3PreviewProposal) -> MolecularSegmentation:
    return MolecularSegmentation(
        frame_index=proposal.frame_index,
        source_view=proposal.source_view,
        bbox_xyxy=proposal.bbox_xyxy,
        mask=proposal.mask,
        polygon_xy=proposal.polygon_xy or None,
        score=proposal.score,
        origin="sam3",
        prompt_detection_ids=proposal.prompt_detection_ids,
        model_name=proposal.model_name,
        metadata=dict(proposal.metadata),
        segmentation_id=f"sam3-seg-{proposal.proposal_id}",
    )


def _remove_committed_sam3_detections(
    detection_set: MolecularDetectionSet,
    preview: MolTrackSam3Preview,
) -> int:
    detection_ids = [
        detection.detection_id
        for detection in detection_set.get_detections(preview.frame_index, source_view=preview.source_view)
        if detection.origin in ("sam3", "sam3_concept")
    ]
    for detection_id in detection_ids:
        detection_set.remove_detection(detection_id)
    return len(detection_ids)


def _remove_committed_sam3_segmentations(
    segmentation_set: MolecularSegmentationSet,
    preview: MolTrackSam3Preview,
) -> int:
    segmentation_ids = [
        segmentation.segmentation_id
        for segmentation in segmentation_set.get_segmentations(preview.frame_index, source_view=preview.source_view)
        if segmentation.origin == "sam3"
    ]
    for segmentation_id in segmentation_ids:
        segmentation_set.remove_segmentation(segmentation_id)
    return len(segmentation_ids)


def _proposal_has_segmentation_payload(proposal: MolTrackSam3PreviewProposal) -> bool:
    return proposal.mask is not None or bool(proposal.polygon_xy)


def _is_duplicate_proposal_for_detection_set(
    proposal: MolTrackSam3PreviewProposal,
    detection_set: MolecularDetectionSet,
    *,
    threshold: float,
) -> bool:
    if threshold >= 1.0:
        return False
    current_detections = detection_set.get_detections(proposal.frame_index, source_view=proposal.source_view)
    return any(_bbox_iou(proposal.bbox_xyxy, detection.bbox_xyxy) >= threshold for detection in current_detections)


def _is_duplicate_bbox(
    bbox_xyxy: tuple[float, float, float, float],
    existing_bboxes: Iterable[tuple[float, float, float, float]],
    *,
    threshold: float,
) -> bool:
    if threshold >= 1.0:
        return False
    return any(_bbox_iou(bbox_xyxy, existing_bbox) >= threshold for existing_bbox in existing_bboxes)


def _bbox_iou(
    a: tuple[float, float, float, float],
    b: tuple[float, float, float, float],
) -> float:
    ax0, ay0, ax1, ay1 = _normalize_bbox_xyxy(a)
    bx0, by0, bx1, by1 = _normalize_bbox_xyxy(b)
    inter_x0 = max(ax0, bx0)
    inter_y0 = max(ay0, by0)
    inter_x1 = min(ax1, bx1)
    inter_y1 = min(ay1, by1)
    if inter_x1 <= inter_x0 or inter_y1 <= inter_y0:
        return 0.0
    intersection = (inter_x1 - inter_x0) * (inter_y1 - inter_y0)
    area_a = (ax1 - ax0) * (ay1 - ay0)
    area_b = (bx1 - bx0) * (by1 - by0)
    union = area_a + area_b - intersection
    return float(intersection / union) if union > 0.0 else 0.0


def _normalize_probability(value: float, name: str) -> float:
    value = float(value)
    if not isfinite(value) or not 0.0 <= value <= 1.0:
        raise ValueError(f"SAM3 preview {name} must be between 0 and 1.")
    return value


def _normalize_bbox_xyxy(bbox_xyxy: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    try:
        x0, y0, x1, y1 = (float(value) for value in bbox_xyxy)
    except (TypeError, ValueError) as exc:
        raise ValueError("SAM3 preview bbox_xyxy must contain four numeric values.") from exc
    if not all(isfinite(value) for value in (x0, y0, x1, y1)):
        raise ValueError("SAM3 preview bbox_xyxy values must be finite.")
    if x1 <= x0 or y1 <= y0:
        raise ValueError("SAM3 preview bbox_xyxy must satisfy x2 > x1 and y2 > y1.")
    return x0, y0, x1, y1


def _normalize_polygon_xy(polygon_xy: Any | None) -> tuple[tuple[float, float], ...]:
    if polygon_xy is None:
        return ()
    points = tuple((float(point[0]), float(point[1])) for point in polygon_xy)
    for x, y in points:
        if not isfinite(x) or not isfinite(y):
            raise ValueError("SAM3 preview polygon points must be finite.")
    return points


def _normalize_prompt_detection_ids(prompt_detection_ids: Any) -> tuple[str, ...]:
    if prompt_detection_ids is None:
        return ()
    if isinstance(prompt_detection_ids, str):
        values = (prompt_detection_ids,)
    else:
        values = tuple(prompt_detection_ids)
    normalized = []
    for value in values:
        value = str(value).strip()
        if not value:
            raise ValueError("SAM3 preview prompt_detection_ids must contain non-empty strings.")
        normalized.append(value)
    return tuple(normalized)


def _normalize_proposal_id(proposal_id: str | None) -> str:
    if proposal_id is None:
        return uuid4().hex
    proposal_id = str(proposal_id).strip()
    if not proposal_id:
        raise ValueError("SAM3 preview proposal_id must be a non-empty string.")
    return proposal_id
