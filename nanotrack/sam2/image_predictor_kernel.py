"""Single-image SAM2 inference kernel with an injectable predictor."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

import numpy as np

from .image_batch_contract import (
    Sam2ImageBatchInput,
    Sam2ImageBatchOutput,
    empty_sam2_image_batch_output,
    validate_sam2_image_batch_pair,
)


DEFAULT_SAM2_GPU_8_GIB_CHUNK_SIZE = 32


class Sam2ImagePredictor(Protocol):
    def set_image(self, image: np.ndarray) -> None: ...

    def predict(self, **kwargs): ...


class Sam2ChunkSizeLimiter(Protocol):
    def limit_chunk_size(
        self,
        *,
        requested_chunk_size: int,
        remaining_bbox_count: int,
        total_bbox_count: int,
        frame_shape: tuple[int, int],
        frame_channels: int,
    ) -> int: ...


class Sam2ImagePredictorKernel:
    """Run SAM2 image prediction while keeping model ownership outside the kernel."""

    def __init__(
        self,
        predictor: Sam2ImagePredictor,
        *,
        chunk_size_limiter: Sam2ChunkSizeLimiter | None = None,
    ) -> None:
        self._predictor = predictor
        self._chunk_size_limiter = chunk_size_limiter

    def run(self, run_input: Sam2ImageBatchInput) -> Sam2ImageBatchOutput:
        if not isinstance(run_input, Sam2ImageBatchInput):
            raise TypeError("run_input must be Sam2ImageBatchInput.")
        if not run_input.requires_inference:
            return empty_sam2_image_batch_output(run_input)

        bbox_count = run_input.bbox_count
        height, width = run_input.frame.shape[:2]
        frame_channels = 1 if run_input.frame.ndim == 2 else int(run_input.frame.shape[2])
        requested_chunk_size = min(
            run_input.chunk_size,
            DEFAULT_SAM2_GPU_8_GIB_CHUNK_SIZE,
        )
        chunk_size = self._resolve_chunk_size(
            requested_chunk_size=requested_chunk_size,
            remaining_bbox_count=bbox_count,
            total_bbox_count=bbox_count,
            frame_shape=(height, width),
            frame_channels=frame_channels,
        )

        self._predictor.set_image(_prepare_image_rgb(run_input.frame))
        masks = np.empty((bbox_count, height, width), dtype=bool)
        scores = np.empty((bbox_count,), dtype=np.float32)
        mask_boxes = np.empty((bbox_count, 4), dtype=np.float32)
        component_counts = np.empty((bbox_count,), dtype=np.int64)

        start = 0
        while start < bbox_count:
            remaining_bbox_count = bbox_count - start
            if start > 0:
                chunk_size = self._resolve_chunk_size(
                    requested_chunk_size=requested_chunk_size,
                    remaining_bbox_count=remaining_bbox_count,
                    total_bbox_count=bbox_count,
                    frame_shape=(height, width),
                    frame_channels=frame_channels,
                )
            stop = min(start + chunk_size, bbox_count)
            try:
                mask_logits, _, _ = self._predictor.predict(
                    box=run_input.boxes_xyxy[start:stop],
                    multimask_output=False,
                    return_logits=True,
                )
            except Exception as error:
                recover_from_cuda_oom = getattr(
                    self._chunk_size_limiter,
                    "recover_from_cuda_oom",
                    None,
                )
                if not callable(recover_from_cuda_oom) or not recover_from_cuda_oom(
                    error=error,
                    failed_chunk_size=chunk_size,
                ):
                    raise
                chunk_size = self._resolve_chunk_size(
                    requested_chunk_size=requested_chunk_size,
                    remaining_bbox_count=remaining_bbox_count,
                    total_bbox_count=bbox_count,
                    frame_shape=(height, width),
                    frame_channels=frame_channels,
                )
                continue
            chunk_logits = _normalize_mask_logits_batch(
                mask_logits,
                expected_count=stop - start,
            )
            for offset, logits in enumerate(chunk_logits, start=start):
                mask = _sigmoid(logits) >= run_input.mask_probability_threshold
                masks[offset] = mask
                scores[offset] = _mask_score(logits, mask)
                mask_boxes[offset] = _mask_bbox_xyxy(mask)
                component_counts[offset] = _mask_component_count(mask)
            start = stop

        result = Sam2ImageBatchOutput(
            frame_index=run_input.frame_index,
            source_view=run_input.source_view,
            prompt_detection_ids=run_input.prompt_detection_ids,
            masks=masks,
            mask_scores=scores,
            mask_bboxes_xyxy=mask_boxes,
            mask_component_counts=component_counts,
        )
        return validate_sam2_image_batch_pair(run_input, result)

    def _resolve_chunk_size(
        self,
        *,
        requested_chunk_size: int,
        remaining_bbox_count: int,
        total_bbox_count: int,
        frame_shape: tuple[int, int],
        frame_channels: int,
    ) -> int:
        chunk_size = requested_chunk_size
        if self._chunk_size_limiter is not None:
            chunk_size = int(
                self._chunk_size_limiter.limit_chunk_size(
                    requested_chunk_size=requested_chunk_size,
                    remaining_bbox_count=remaining_bbox_count,
                    total_bbox_count=total_bbox_count,
                    frame_shape=frame_shape,
                    frame_channels=frame_channels,
                )
            )
            if chunk_size <= 0:
                raise ValueError("SAM2 chunk size limiter must return a positive value.")
        return min(chunk_size, requested_chunk_size, remaining_bbox_count)


def build_sam2_image_predictor_kernel(
    *,
    config_identifier: str,
    checkpoint_path: str | Path,
    device: str = "cuda",
    apply_postprocessing: bool = True,
    chunk_size_limiter: Sam2ChunkSizeLimiter | None = None,
) -> Sam2ImagePredictorKernel:
    """Build a real image predictor lazily inside the configured SAM2 environment."""

    import torch
    from sam2.build_sam import build_sam2
    from sam2.sam2_image_predictor import SAM2ImagePredictor

    if chunk_size_limiter is None and str(device).startswith("cuda"):
        from .memory_budget import Sam2AdaptiveMemoryController

        cuda_oom_error_type = getattr(torch.cuda, "OutOfMemoryError", None)
        cuda_oom_error_types = (
            () if cuda_oom_error_type is None else (cuda_oom_error_type,)
        )
        chunk_size_limiter = Sam2AdaptiveMemoryController(
            cuda_memory_info=torch.cuda.mem_get_info,
            cuda_empty_cache=torch.cuda.empty_cache,
            cuda_oom_error_types=cuda_oom_error_types,
        )

    model = build_sam2(
        str(config_identifier),
        str(Path(checkpoint_path)),
        device=str(device),
        apply_postprocessing=bool(apply_postprocessing),
    )
    return Sam2ImagePredictorKernel(
        SAM2ImagePredictor(model),
        chunk_size_limiter=chunk_size_limiter,
    )


def _prepare_image_rgb(frame: np.ndarray) -> np.ndarray:
    image = np.asarray(frame)
    if image.ndim == 2:
        image = image[..., None]
    if image.ndim != 3:
        raise ValueError("frame must have shape [H, W] or [H, W, C].")
    if image.shape[-1] == 1:
        image = np.repeat(image, 3, axis=-1)
    elif image.shape[-1] >= 3:
        image = image[..., :3]
    else:
        raise ValueError("frame channel dimension must be 1 or >=3.")

    image_f32 = np.asarray(image, dtype=np.float32)
    output = np.zeros(image_f32.shape, dtype=np.uint8)
    finite_mask = np.isfinite(image_f32)
    if not np.any(finite_mask):
        return output
    finite_values = image_f32[finite_mask]
    value_min = float(np.min(finite_values))
    value_max = float(np.max(finite_values))
    if value_max <= value_min + 1e-8:
        return output
    normalized = np.clip((image_f32 - value_min) / (value_max - value_min), 0.0, 1.0)
    return np.asarray(np.round(normalized * 255.0), dtype=np.uint8)


def _normalize_mask_logits_batch(
    mask_logits: np.ndarray,
    *,
    expected_count: int,
) -> np.ndarray:
    logits = np.asarray(mask_logits, dtype=np.float32)
    if logits.ndim == 4 and logits.shape[1] == 1:
        logits = logits[:, 0]
    elif logits.ndim == 2 and expected_count == 1:
        logits = logits[None, ...]
    if logits.ndim != 3 or logits.shape[0] != expected_count:
        raise ValueError(f"Unexpected SAM2 mask logits shape: {logits.shape}")
    return logits


def _sigmoid(values: np.ndarray) -> np.ndarray:
    clipped = np.clip(np.asarray(values, dtype=np.float32), -60.0, 60.0)
    return 1.0 / (1.0 + np.exp(-clipped))


def _mask_score(mask_logits: np.ndarray, mask: np.ndarray) -> float:
    if not np.any(mask):
        return 0.0
    return float(np.mean(_sigmoid(mask_logits)[mask]))


def _mask_bbox_xyxy(mask: np.ndarray) -> np.ndarray:
    ys, xs = np.nonzero(mask)
    if ys.size == 0 or xs.size == 0:
        return np.zeros((4,), dtype=np.float32)
    return np.asarray(
        (float(xs.min()), float(ys.min()), float(xs.max() + 1), float(ys.max() + 1)),
        dtype=np.float32,
    )


def _mask_component_count(mask: np.ndarray) -> int:
    if not np.any(mask):
        return 0
    try:
        import cv2  # type: ignore

        label_count, _ = cv2.connectedComponents(np.asarray(mask, dtype=np.uint8), connectivity=8)
        return max(0, int(label_count) - 1)
    except Exception:
        return 1
