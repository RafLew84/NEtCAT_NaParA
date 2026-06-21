from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

import numpy as np

from .contract import (
    MolTrackSam3BoxPrompt,
    MolTrackSam3OutputProposal,
    MolTrackSam3RunInput,
)
from .backend import MolTrackSam3Error, MolTrackSam3SubprocessBackend


@dataclass(frozen=True)
class MolTrackSam3Proposal:
    frame_index: int
    source_view: str
    bbox_xyxy: tuple[float, float, float, float]
    score: float
    mask: Any | None = None
    polygon_xy: tuple[tuple[float, float], ...] = ()
    prompt_detection_ids: tuple[str, ...] = ()
    model_name: str = ""
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "frame_index", int(self.frame_index))
        object.__setattr__(self, "source_view", str(self.source_view))
        object.__setattr__(self, "bbox_xyxy", tuple(float(value) for value in self.bbox_xyxy))
        object.__setattr__(self, "score", float(self.score))
        mask = None if self.mask is None else np.asarray(self.mask, dtype=bool)
        object.__setattr__(self, "mask", mask)
        object.__setattr__(
            self,
            "polygon_xy",
            tuple((float(x), float(y)) for x, y in self.polygon_xy),
        )
        object.__setattr__(self, "prompt_detection_ids", tuple(str(value) for value in self.prompt_detection_ids))
        object.__setattr__(self, "model_name", str(self.model_name))
        object.__setattr__(self, "metadata", dict(self.metadata))


class MolTrackSam3ConceptAdapter:
    """Adapter for SAM3 concept segmentation proposals in MolTrack coordinates."""

    def __init__(self, backend=None):
        self._backend = backend if backend is not None else MolTrackSam3SubprocessBackend()

    def segment_detections(
        self,
        frame,
        detections,
        *,
        frame_index: int,
        source_view: str,
        model_id: str = "facebook/sam3",
        backend: str = "transformers_sam3",
        score_threshold: float = 0.3,
        mask_threshold: float = 0.5,
        max_results: int = 300,
        roi_xyxy: tuple[float, float, float, float] | None = None,
        upscale: int = 1,
    ) -> list[MolTrackSam3Proposal]:
        detections = list(detections)
        prompts = tuple(
            MolTrackSam3BoxPrompt(
                bbox_xyxy=detection.bbox_xyxy,
                label=1,
                detection_id=detection.detection_id,
            )
            for detection in detections
        )
        prompt_detection_ids = tuple(detection.detection_id for detection in detections)
        run_input = MolTrackSam3RunInput(
            frame_index=frame_index,
            source_view=source_view,
            frame=frame,
            prompts=prompts,
            model_id=model_id,
            backend=backend,
            score_threshold=score_threshold,
            mask_threshold=mask_threshold,
            max_results=max_results,
            roi_xyxy=roi_xyxy,
            upscale=upscale,
        )
        try:
            output = self._backend.run(run_input)
        except MolTrackSam3Error:
            raise
        except Exception as exc:
            raise MolTrackSam3Error(f"SAM3 backend failed: {exc}") from exc
        frame_shape = np.asarray(frame).shape[:2]
        return [
            self._proposal_to_moltrack(
                proposal,
                run_input=run_input,
                frame_shape=frame_shape,
                prompt_detection_ids=prompt_detection_ids,
            )
            for proposal in output.proposals
        ]

    def _proposal_to_moltrack(
        self,
        proposal: MolTrackSam3OutputProposal,
        *,
        run_input: MolTrackSam3RunInput,
        frame_shape: tuple[int, int],
        prompt_detection_ids: tuple[str, ...],
    ) -> MolTrackSam3Proposal:
        return MolTrackSam3Proposal(
            frame_index=run_input.frame_index,
            source_view=run_input.source_view,
            bbox_xyxy=_map_bbox_to_frame(proposal.bbox_xyxy, run_input),
            score=proposal.score,
            mask=_map_mask_to_frame(proposal.mask, run_input, frame_shape=frame_shape),
            polygon_xy=_map_polygon_to_frame(proposal.polygon_xy, run_input),
            prompt_detection_ids=prompt_detection_ids,
            model_name=run_input.model_id,
            metadata=proposal.metadata,
        )


def _map_bbox_to_frame(
    bbox_xyxy: tuple[float, float, float, float],
    run_input: MolTrackSam3RunInput,
) -> tuple[float, float, float, float]:
    factor = float(run_input.upscale)
    offset_x, offset_y = _roi_offset_xy(run_input)
    x1, y1, x2, y2 = bbox_xyxy
    return (
        float(x1) / factor + offset_x,
        float(y1) / factor + offset_y,
        float(x2) / factor + offset_x,
        float(y2) / factor + offset_y,
    )


def _map_polygon_to_frame(
    polygon_xy: tuple[tuple[float, float], ...],
    run_input: MolTrackSam3RunInput,
) -> tuple[tuple[float, float], ...]:
    factor = float(run_input.upscale)
    offset_x, offset_y = _roi_offset_xy(run_input)
    return tuple((float(x) / factor + offset_x, float(y) / factor + offset_y) for x, y in polygon_xy)


def _map_mask_to_frame(mask, run_input: MolTrackSam3RunInput, *, frame_shape: tuple[int, int]):
    if mask is None:
        return None
    worker_mask = np.asarray(mask, dtype=bool)
    frame_height, frame_width = (int(value) for value in frame_shape)
    frame_mask = np.zeros((frame_height, frame_width), dtype=bool)
    factor = int(run_input.upscale)
    offset_x, offset_y = _roi_offset_xy(run_input)
    offset_x_i = int(round(offset_x))
    offset_y_i = int(round(offset_y))
    y_indices, x_indices = np.nonzero(worker_mask)
    for worker_y, worker_x in zip(y_indices, x_indices):
        frame_y = int(worker_y // factor) + offset_y_i
        frame_x = int(worker_x // factor) + offset_x_i
        if 0 <= frame_y < frame_height and 0 <= frame_x < frame_width:
            frame_mask[frame_y, frame_x] = True
    return frame_mask


def _roi_offset_xy(run_input: MolTrackSam3RunInput) -> tuple[float, float]:
    if run_input.roi_xyxy is None:
        return 0.0, 0.0
    x1, y1, _x2, _y2 = run_input.roi_xyxy
    return float(x1), float(y1)
