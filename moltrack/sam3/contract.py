from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite
from typing import Any, Mapping

import numpy as np


MOLTRACK_SAM3_CONTRACT_VERSION = 1
SUPPORTED_SAM3_BACKENDS = ("transformers_sam3", "official_sam31")
SUPPORTED_SAM3_SOURCE_VIEWS = ("raw", "expanded_aligned")


@dataclass(frozen=True)
class MolTrackSam3BoxPrompt:
    bbox_xyxy: tuple[float, float, float, float]
    label: int = 1
    detection_id: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "bbox_xyxy", _normalize_bbox_xyxy(self.bbox_xyxy))
        label = int(self.label)
        if label not in (0, 1):
            raise ValueError("SAM3 prompt label must be 0 or 1.")
        object.__setattr__(self, "label", label)
        object.__setattr__(self, "detection_id", str(self.detection_id))


@dataclass(frozen=True)
class MolTrackSam3RunInput:
    frame_index: int
    source_view: str
    frame: Any
    prompts: tuple[MolTrackSam3BoxPrompt, ...]
    model_id: str = "facebook/sam3"
    backend: str = "transformers_sam3"
    score_threshold: float = 0.3
    mask_threshold: float = 0.5
    max_results: int = 300
    roi_xyxy: tuple[float, float, float, float] | None = None
    upscale: int = 1

    def __post_init__(self) -> None:
        frame_index = int(self.frame_index)
        if frame_index < 0:
            raise ValueError("frame_index must be non-negative.")
        source_view = str(self.source_view).strip()
        if source_view not in SUPPORTED_SAM3_SOURCE_VIEWS:
            raise ValueError(f"Unsupported SAM3 source_view: {source_view!r}.")
        frame = np.asarray(self.frame, dtype=np.float32)
        if frame.ndim not in (2, 3):
            raise ValueError("SAM3 frame must have shape [H, W] or [H, W, C].")
        if frame.shape[0] <= 0 or frame.shape[1] <= 0:
            raise ValueError("SAM3 frame must have positive height and width.")
        prompts = tuple(self.prompts)
        if not prompts:
            raise ValueError("SAM3 run requires at least one bbox prompt.")
        for prompt in prompts:
            if not isinstance(prompt, MolTrackSam3BoxPrompt):
                raise TypeError("SAM3 prompts must be MolTrackSam3BoxPrompt instances.")
        model_id = str(self.model_id).strip()
        if not model_id:
            raise ValueError("SAM3 model_id must be a non-empty string.")
        backend = str(self.backend).strip()
        if backend not in SUPPORTED_SAM3_BACKENDS:
            raise ValueError(f"Unsupported SAM3 backend: {backend!r}.")
        score_threshold = _normalize_probability(self.score_threshold, "score_threshold")
        mask_threshold = _normalize_probability(self.mask_threshold, "mask_threshold")
        max_results = int(self.max_results)
        if max_results <= 0:
            raise ValueError("SAM3 max_results must be positive.")
        upscale = int(self.upscale)
        if upscale not in (1, 2, 4):
            raise ValueError("SAM3 upscale must be one of: 1, 2, 4.")
        roi_xyxy = None if self.roi_xyxy is None else _normalize_bbox_xyxy(self.roi_xyxy)

        object.__setattr__(self, "frame_index", frame_index)
        object.__setattr__(self, "source_view", source_view)
        object.__setattr__(self, "frame", frame)
        object.__setattr__(self, "prompts", prompts)
        object.__setattr__(self, "model_id", model_id)
        object.__setattr__(self, "backend", backend)
        object.__setattr__(self, "score_threshold", score_threshold)
        object.__setattr__(self, "mask_threshold", mask_threshold)
        object.__setattr__(self, "max_results", max_results)
        object.__setattr__(self, "roi_xyxy", roi_xyxy)
        object.__setattr__(self, "upscale", upscale)


@dataclass(frozen=True)
class MolTrackSam3OutputProposal:
    bbox_xyxy: tuple[float, float, float, float]
    score: float
    mask: Any | None = None
    polygon_xy: tuple[tuple[float, float], ...] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "bbox_xyxy", _normalize_bbox_xyxy(self.bbox_xyxy))
        score = float(self.score)
        if not isfinite(score) or not 0.0 <= score <= 1.0:
            raise ValueError("SAM3 proposal score must be between 0 and 1.")
        mask = None if self.mask is None else np.asarray(self.mask, dtype=bool)
        if mask is not None and mask.ndim != 2:
            raise ValueError("SAM3 proposal mask must be a 2D array.")
        polygon_xy = _normalize_polygon_xy(self.polygon_xy)
        object.__setattr__(self, "score", score)
        object.__setattr__(self, "mask", mask)
        object.__setattr__(self, "polygon_xy", polygon_xy)
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True)
class MolTrackSam3RunOutput:
    proposals: tuple[MolTrackSam3OutputProposal, ...] = ()

    def __post_init__(self) -> None:
        proposals = tuple(self.proposals)
        for proposal in proposals:
            if not isinstance(proposal, MolTrackSam3OutputProposal):
                raise TypeError("SAM3 output proposals must be MolTrackSam3OutputProposal instances.")
        object.__setattr__(self, "proposals", proposals)

    @property
    def proposal_count(self) -> int:
        return len(self.proposals)


def _normalize_probability(value: float, name: str) -> float:
    value = float(value)
    if not isfinite(value) or not 0.0 <= value <= 1.0:
        raise ValueError(f"SAM3 {name} must be between 0 and 1.")
    return value


def _normalize_bbox_xyxy(bbox_xyxy) -> tuple[float, float, float, float]:
    try:
        x1, y1, x2, y2 = (float(value) for value in bbox_xyxy)
    except (TypeError, ValueError) as exc:
        raise ValueError("SAM3 bbox_xyxy must contain four numeric values.") from exc
    if not all(isfinite(value) for value in (x1, y1, x2, y2)):
        raise ValueError("SAM3 bbox_xyxy values must be finite.")
    if x2 <= x1 or y2 <= y1:
        raise ValueError("SAM3 bbox_xyxy must satisfy x2 > x1 and y2 > y1.")
    return x1, y1, x2, y2


def _normalize_polygon_xy(polygon_xy) -> tuple[tuple[float, float], ...]:
    if polygon_xy is None:
        return ()
    points = tuple((float(point[0]), float(point[1])) for point in polygon_xy)
    for x, y in points:
        if not isfinite(x) or not isfinite(y):
            raise ValueError("SAM3 polygon points must be finite.")
    return points
