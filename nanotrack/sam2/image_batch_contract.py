"""Versioned NPZ contract for batching SAM2 BBox prompts on one image."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import numpy as np


SAM2_IMAGE_BATCH_CONTRACT_VERSION = 1


def _require_key(payload: Mapping[str, Any], key: str) -> Any:
    if key not in payload:
        raise KeyError(f"Missing required SAM2 image batch field: {key}")
    return payload[key]


@dataclass(frozen=True)
class Sam2ImageBatchInput:
    """One image and an ordered collection of SAM2 BBox prompts."""

    frame: np.ndarray
    frame_index: int
    source_view: str
    boxes_xyxy: np.ndarray
    prompt_detection_ids: tuple[str, ...]
    mask_probability_threshold: float = 0.5
    chunk_size: int = 32

    def __post_init__(self) -> None:
        frame = np.asarray(self.frame, dtype=np.float32)
        if frame.ndim not in (2, 3):
            raise ValueError("frame must have shape [H, W] or [H, W, C].")
        if frame.shape[0] <= 0 or frame.shape[1] <= 0:
            raise ValueError("frame spatial dimensions must be positive.")

        frame_index = int(self.frame_index)
        if frame_index < 0:
            raise ValueError("frame_index must be non-negative.")
        source_view = str(self.source_view).strip()
        if not source_view:
            raise ValueError("source_view must be a non-empty string.")

        boxes = np.asarray(self.boxes_xyxy, dtype=np.float32)
        if boxes.ndim != 2 or boxes.shape[1:] != (4,):
            raise ValueError("boxes_xyxy must have shape [N, 4].")
        _validate_boxes_within_frame(boxes, frame_shape=frame.shape[:2])

        prompt_detection_ids = tuple(str(value).strip() for value in self.prompt_detection_ids)
        if len(prompt_detection_ids) != boxes.shape[0]:
            raise ValueError("prompt_detection_ids length must match boxes_xyxy.")
        if any(not value for value in prompt_detection_ids):
            raise ValueError("prompt_detection_ids must contain non-empty strings.")
        if len(set(prompt_detection_ids)) != len(prompt_detection_ids):
            raise ValueError("prompt_detection_ids must be unique within one image batch.")

        threshold = float(self.mask_probability_threshold)
        if not np.isfinite(threshold) or not 0.0 < threshold < 1.0:
            raise ValueError("mask_probability_threshold must be finite and in (0, 1).")
        chunk_size = int(self.chunk_size)
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive.")

        object.__setattr__(self, "frame", frame)
        object.__setattr__(self, "frame_index", frame_index)
        object.__setattr__(self, "source_view", source_view)
        object.__setattr__(self, "boxes_xyxy", boxes)
        object.__setattr__(self, "prompt_detection_ids", prompt_detection_ids)
        object.__setattr__(self, "mask_probability_threshold", threshold)
        object.__setattr__(self, "chunk_size", chunk_size)

    @property
    def bbox_count(self) -> int:
        return len(self.prompt_detection_ids)

    @property
    def requires_inference(self) -> bool:
        return self.bbox_count > 0

    def to_npz_payload(self) -> dict[str, np.ndarray]:
        return {
            "contract_version": np.asarray(SAM2_IMAGE_BATCH_CONTRACT_VERSION, dtype=np.int64),
            "frame": self.frame.astype(np.float32, copy=False),
            "frame_index": np.asarray(self.frame_index, dtype=np.int64),
            "source_view": np.asarray(self.source_view),
            "boxes_xyxy": self.boxes_xyxy.astype(np.float32, copy=False),
            "prompt_detection_ids": np.asarray(self.prompt_detection_ids, dtype=np.str_),
            "mask_probability_threshold": np.asarray(
                self.mask_probability_threshold,
                dtype=np.float32,
            ),
            "chunk_size": np.asarray(self.chunk_size, dtype=np.int64),
        }

    @classmethod
    def from_npz_payload(cls, payload: Mapping[str, Any]) -> "Sam2ImageBatchInput":
        version = int(np.asarray(_require_key(payload, "contract_version")).item())
        if version != SAM2_IMAGE_BATCH_CONTRACT_VERSION:
            raise ValueError(
                f"Unsupported SAM2 image batch contract_version {version}; "
                f"expected {SAM2_IMAGE_BATCH_CONTRACT_VERSION}."
            )
        return cls(
            frame=np.asarray(_require_key(payload, "frame"), dtype=np.float32),
            frame_index=int(np.asarray(_require_key(payload, "frame_index")).item()),
            source_view=str(np.asarray(_require_key(payload, "source_view")).item()),
            boxes_xyxy=np.asarray(_require_key(payload, "boxes_xyxy"), dtype=np.float32),
            prompt_detection_ids=tuple(
                str(value)
                for value in np.asarray(_require_key(payload, "prompt_detection_ids")).tolist()
            ),
            mask_probability_threshold=float(
                np.asarray(_require_key(payload, "mask_probability_threshold")).item()
            ),
            chunk_size=int(np.asarray(_require_key(payload, "chunk_size")).item()),
        )


@dataclass(frozen=True)
class Sam2ImageBatchOutput:
    """Ordered SAM2 mask results for one image batch."""

    frame_index: int
    source_view: str
    prompt_detection_ids: tuple[str, ...]
    masks: np.ndarray
    mask_scores: np.ndarray
    mask_bboxes_xyxy: np.ndarray
    mask_component_counts: np.ndarray

    def __post_init__(self) -> None:
        frame_index = int(self.frame_index)
        if frame_index < 0:
            raise ValueError("frame_index must be non-negative.")
        source_view = str(self.source_view).strip()
        if not source_view:
            raise ValueError("source_view must be a non-empty string.")

        masks = np.asarray(self.masks, dtype=bool)
        if masks.ndim != 3:
            raise ValueError("masks must have shape [N, H, W].")
        if masks.shape[1] <= 0 or masks.shape[2] <= 0:
            raise ValueError("mask spatial dimensions must be positive.")
        result_count = int(masks.shape[0])

        prompt_detection_ids = tuple(str(value).strip() for value in self.prompt_detection_ids)
        if len(prompt_detection_ids) != result_count:
            raise ValueError("prompt_detection_ids length must match masks.")
        if any(not value for value in prompt_detection_ids):
            raise ValueError("prompt_detection_ids must contain non-empty strings.")
        if len(set(prompt_detection_ids)) != len(prompt_detection_ids):
            raise ValueError("prompt_detection_ids must be unique within one image batch.")

        mask_scores = np.asarray(self.mask_scores, dtype=np.float32)
        if mask_scores.shape != (result_count,):
            raise ValueError("mask_scores must have shape [N] matching masks.")
        if not bool(np.all(np.isfinite(mask_scores))):
            raise ValueError("mask_scores must contain only finite values.")

        mask_bboxes = np.asarray(self.mask_bboxes_xyxy, dtype=np.float32)
        if mask_bboxes.shape != (result_count, 4):
            raise ValueError("mask_bboxes_xyxy must have shape [N, 4] matching masks.")
        _validate_mask_boxes(mask_bboxes, frame_shape=masks.shape[1:])

        component_counts = np.asarray(self.mask_component_counts, dtype=np.int64)
        if component_counts.shape != (result_count,):
            raise ValueError("mask_component_counts must have shape [N] matching masks.")
        if bool(np.any(component_counts < 0)):
            raise ValueError("mask_component_counts must be non-negative.")

        object.__setattr__(self, "frame_index", frame_index)
        object.__setattr__(self, "source_view", source_view)
        object.__setattr__(self, "prompt_detection_ids", prompt_detection_ids)
        object.__setattr__(self, "masks", masks)
        object.__setattr__(self, "mask_scores", mask_scores)
        object.__setattr__(self, "mask_bboxes_xyxy", mask_bboxes)
        object.__setattr__(self, "mask_component_counts", component_counts)

    @property
    def result_count(self) -> int:
        return len(self.prompt_detection_ids)

    def to_npz_payload(self) -> dict[str, np.ndarray]:
        return {
            "contract_version": np.asarray(SAM2_IMAGE_BATCH_CONTRACT_VERSION, dtype=np.int64),
            "frame_index": np.asarray(self.frame_index, dtype=np.int64),
            "source_view": np.asarray(self.source_view),
            "prompt_detection_ids": np.asarray(self.prompt_detection_ids, dtype=np.str_),
            "masks": self.masks.astype(np.uint8, copy=False),
            "mask_scores": self.mask_scores.astype(np.float32, copy=False),
            "mask_bboxes_xyxy": self.mask_bboxes_xyxy.astype(np.float32, copy=False),
            "mask_component_counts": self.mask_component_counts.astype(np.int64, copy=False),
        }

    @classmethod
    def from_npz_payload(cls, payload: Mapping[str, Any]) -> "Sam2ImageBatchOutput":
        version = int(np.asarray(_require_key(payload, "contract_version")).item())
        if version != SAM2_IMAGE_BATCH_CONTRACT_VERSION:
            raise ValueError(
                f"Unsupported SAM2 image batch contract_version {version}; "
                f"expected {SAM2_IMAGE_BATCH_CONTRACT_VERSION}."
            )
        return cls(
            frame_index=int(np.asarray(_require_key(payload, "frame_index")).item()),
            source_view=str(np.asarray(_require_key(payload, "source_view")).item()),
            prompt_detection_ids=tuple(
                str(value)
                for value in np.asarray(_require_key(payload, "prompt_detection_ids")).tolist()
            ),
            masks=np.asarray(_require_key(payload, "masks"), dtype=bool),
            mask_scores=np.asarray(_require_key(payload, "mask_scores"), dtype=np.float32),
            mask_bboxes_xyxy=np.asarray(
                _require_key(payload, "mask_bboxes_xyxy"),
                dtype=np.float32,
            ),
            mask_component_counts=np.asarray(
                _require_key(payload, "mask_component_counts"),
                dtype=np.int64,
            ),
        )


def empty_sam2_image_batch_output(run_input: Sam2ImageBatchInput) -> Sam2ImageBatchOutput:
    """Return a valid no-inference result for an empty image batch."""

    if not isinstance(run_input, Sam2ImageBatchInput):
        raise TypeError("run_input must be Sam2ImageBatchInput.")
    if run_input.requires_inference:
        raise ValueError("empty output can only be created for a batch without BBoxes.")
    height, width = run_input.frame.shape[:2]
    return Sam2ImageBatchOutput(
        frame_index=run_input.frame_index,
        source_view=run_input.source_view,
        prompt_detection_ids=(),
        masks=np.empty((0, height, width), dtype=bool),
        mask_scores=np.empty((0,), dtype=np.float32),
        mask_bboxes_xyxy=np.empty((0, 4), dtype=np.float32),
        mask_component_counts=np.empty((0,), dtype=np.int64),
    )


def validate_sam2_image_batch_pair(
    run_input: Sam2ImageBatchInput,
    run_output: Sam2ImageBatchOutput,
) -> Sam2ImageBatchOutput:
    """Validate that one output corresponds exactly to one ordered input batch."""

    if not isinstance(run_input, Sam2ImageBatchInput):
        raise TypeError("run_input must be Sam2ImageBatchInput.")
    if not isinstance(run_output, Sam2ImageBatchOutput):
        raise TypeError("run_output must be Sam2ImageBatchOutput.")
    if run_output.frame_index != run_input.frame_index:
        raise ValueError("SAM2 image batch output frame_index does not match input.")
    if run_output.source_view != run_input.source_view:
        raise ValueError("SAM2 image batch output source_view does not match input.")
    if run_output.prompt_detection_ids != run_input.prompt_detection_ids:
        raise ValueError("SAM2 image batch output prompt ID order does not match input.")
    if run_output.masks.shape[1:] != run_input.frame.shape[:2]:
        raise ValueError("SAM2 image batch output mask shape does not match input frame.")
    return run_output


def write_sam2_image_batch_input_npz(
    path: str | Path,
    run_input: Sam2ImageBatchInput,
) -> Path:
    if not isinstance(run_input, Sam2ImageBatchInput):
        raise TypeError("run_input must be Sam2ImageBatchInput.")
    return _write_npz(path, run_input.to_npz_payload())


def read_sam2_image_batch_input_npz(path: str | Path) -> Sam2ImageBatchInput:
    return Sam2ImageBatchInput.from_npz_payload(_read_npz(path))


def write_sam2_image_batch_output_npz(
    path: str | Path,
    run_output: Sam2ImageBatchOutput,
) -> Path:
    if not isinstance(run_output, Sam2ImageBatchOutput):
        raise TypeError("run_output must be Sam2ImageBatchOutput.")
    return _write_npz(path, run_output.to_npz_payload())


def read_sam2_image_batch_output_npz(path: str | Path) -> Sam2ImageBatchOutput:
    return Sam2ImageBatchOutput.from_npz_payload(_read_npz(path))


def _write_npz(path: str | Path, payload: Mapping[str, np.ndarray]) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(output_path, **payload)
    return output_path


def _read_npz(path: str | Path) -> dict[str, np.ndarray]:
    with np.load(Path(path), allow_pickle=False) as payload:
        return {key: payload[key] for key in payload.files}


def _validate_boxes_within_frame(boxes: np.ndarray, *, frame_shape: tuple[int, int]) -> None:
    if boxes.size == 0:
        return
    if not bool(np.all(np.isfinite(boxes))):
        raise ValueError("boxes_xyxy must contain only finite coordinates.")
    height, width = (int(value) for value in frame_shape)
    x1, y1, x2, y2 = boxes.T
    if bool(np.any(x2 <= x1)) or bool(np.any(y2 <= y1)):
        raise ValueError("Every SAM2 image batch BBox must have positive width and height.")
    if (
        bool(np.any(x1 < 0.0))
        or bool(np.any(y1 < 0.0))
        or bool(np.any(x2 > width))
        or bool(np.any(y2 > height))
    ):
        raise ValueError("Every SAM2 image batch BBox must fit within the frame.")


def _validate_mask_boxes(boxes: np.ndarray, *, frame_shape: tuple[int, int]) -> None:
    if boxes.size == 0:
        return
    if not bool(np.all(np.isfinite(boxes))):
        raise ValueError("mask_bboxes_xyxy must contain only finite coordinates.")
    empty_boxes = np.all(boxes == 0.0, axis=1)
    non_empty_boxes = boxes[~empty_boxes]
    if non_empty_boxes.size:
        _validate_boxes_within_frame(non_empty_boxes, frame_shape=frame_shape)
