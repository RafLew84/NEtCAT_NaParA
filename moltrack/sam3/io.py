from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from .contract import (
    MOLTRACK_SAM3_CONTRACT_VERSION,
    MolTrackSam3OutputProposal,
    MolTrackSam3RunInput,
    MolTrackSam3RunOutput,
)


def write_moltrack_sam3_input_npz(run_input: MolTrackSam3RunInput, path: str | Path) -> None:
    image_uint8 = _normalize_display_uint8(run_input.frame)
    if run_input.roi_xyxy is not None:
        image_uint8 = _crop_to_roi(image_uint8, run_input.roi_xyxy)
    if run_input.upscale > 1:
        image_uint8 = np.repeat(image_uint8, run_input.upscale, axis=0)
        image_uint8 = np.repeat(image_uint8, run_input.upscale, axis=1)
    image_rgb = _to_rgb_uint8(image_uint8)
    prompt_bboxes, prompt_labels, prompt_detection_ids = _local_prompt_payload(run_input)
    roi_xyxy = (
        np.asarray(run_input.roi_xyxy, dtype=np.float32)
        if run_input.roi_xyxy is not None
        else np.asarray([np.nan, np.nan, np.nan, np.nan], dtype=np.float32)
    )

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        path,
        contract_version=np.asarray(MOLTRACK_SAM3_CONTRACT_VERSION, dtype=np.int64),
        frame_index=np.asarray(run_input.frame_index, dtype=np.int64),
        source_view=np.asarray(run_input.source_view),
        image_rgb=image_rgb,
        prompt_bboxes_xyxy=prompt_bboxes,
        prompt_labels=prompt_labels,
        prompt_detection_ids=prompt_detection_ids,
        model_id=np.asarray(run_input.model_id),
        backend=np.asarray(run_input.backend),
        score_threshold=np.asarray(run_input.score_threshold, dtype=np.float32),
        mask_threshold=np.asarray(run_input.mask_threshold, dtype=np.float32),
        max_results=np.asarray(run_input.max_results, dtype=np.int32),
        roi_xyxy=roi_xyxy,
        upscale=np.asarray(run_input.upscale, dtype=np.int32),
    )


def _local_prompt_payload(run_input: MolTrackSam3RunInput) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    boxes: list[tuple[float, float, float, float]] = []
    labels: list[int] = []
    detection_ids: list[str] = []
    for prompt in run_input.prompts:
        local_box = _local_prompt_box(prompt.bbox_xyxy, run_input)
        if local_box is None:
            continue
        boxes.append(local_box)
        labels.append(prompt.label)
        detection_ids.append(prompt.detection_id)
    return (
        np.asarray(boxes, dtype=np.float32).reshape((-1, 4)),
        np.asarray(labels, dtype=np.int64).reshape((-1,)),
        np.asarray(detection_ids),
    )


def _local_prompt_box(
    bbox_xyxy: tuple[float, float, float, float],
    run_input: MolTrackSam3RunInput,
) -> tuple[float, float, float, float] | None:
    x1, y1, x2, y2 = bbox_xyxy
    if run_input.roi_xyxy is None:
        origin_x = 0.0
        origin_y = 0.0
        max_x = float(np.asarray(run_input.frame).shape[1])
        max_y = float(np.asarray(run_input.frame).shape[0])
    else:
        roi_x1, roi_y1, roi_x2, roi_y2 = run_input.roi_xyxy
        origin_x = float(roi_x1)
        origin_y = float(roi_y1)
        max_x = float(roi_x2) - float(roi_x1)
        max_y = float(roi_y2) - float(roi_y1)

    local_x1 = max(0.0, min(max_x, float(x1) - origin_x))
    local_y1 = max(0.0, min(max_y, float(y1) - origin_y))
    local_x2 = max(0.0, min(max_x, float(x2) - origin_x))
    local_y2 = max(0.0, min(max_y, float(y2) - origin_y))
    if local_x2 <= local_x1 or local_y2 <= local_y1:
        return None
    factor = float(run_input.upscale)
    return local_x1 * factor, local_y1 * factor, local_x2 * factor, local_y2 * factor


def _crop_to_roi(image_uint8: np.ndarray, roi_xyxy: tuple[float, float, float, float]) -> np.ndarray:
    height, width = image_uint8.shape[:2]
    x1, y1, x2, y2 = roi_xyxy
    left = int(max(0, min(width, round(float(x1)))))
    top = int(max(0, min(height, round(float(y1)))))
    right = int(max(0, min(width, round(float(x2)))))
    bottom = int(max(0, min(height, round(float(y2)))))
    return image_uint8[top:bottom, left:right]


def parse_moltrack_sam3_output_npz(
    path: str | Path,
    *,
    score_threshold: float,
) -> MolTrackSam3RunOutput:
    with np.load(Path(path), allow_pickle=False) as data:
        boxes = np.asarray(
            data["bboxes_xyxy"] if "bboxes_xyxy" in data.files else data["boxes"],
            dtype=np.float32,
        ).reshape((-1, 4))
        scores = np.asarray(data["scores"], dtype=np.float32).reshape((-1,))
        masks = _normalize_masks(np.asarray(data["masks"])) if "masks" in data.files else None
        metadata = _metadata_from_npz(data)

    proposals: list[MolTrackSam3OutputProposal] = []
    for index, (bbox, score) in enumerate(zip(boxes, scores, strict=False)):
        score = float(score)
        if score < float(score_threshold):
            continue
        mask = masks[index] if masks is not None and index < len(masks) else None
        proposals.append(
            MolTrackSam3OutputProposal(
                bbox_xyxy=tuple(float(value) for value in bbox),
                score=score,
                mask=mask,
                polygon_xy=_mask_bbox_polygon_xy(mask) if mask is not None else (),
                metadata=metadata,
            )
        )
    return MolTrackSam3RunOutput(proposals=tuple(proposals))


def _normalize_display_uint8(frame: Any) -> np.ndarray:
    frame_array = np.asarray(frame, dtype=np.float32)
    if frame_array.ndim == 3 and frame_array.shape[2] in (3, 4):
        frame_array = frame_array[:, :, :3]
    finite = frame_array[np.isfinite(frame_array)]
    if finite.size == 0:
        return np.zeros(frame_array.shape[:2], dtype=np.uint8)
    min_value = float(finite.min())
    max_value = float(finite.max())
    if max_value <= min_value:
        return np.zeros(frame_array.shape[:2], dtype=np.uint8)
    normalized = (frame_array - min_value) / (max_value - min_value)
    normalized = np.clip(normalized, 0.0, 1.0)
    return np.asarray(np.rint(normalized * 255.0), dtype=np.uint8)


def _to_rgb_uint8(image_uint8: np.ndarray) -> np.ndarray:
    if image_uint8.ndim == 2:
        return np.repeat(image_uint8[:, :, None], 3, axis=2).astype(np.uint8, copy=False)
    if image_uint8.ndim == 3 and image_uint8.shape[2] == 3:
        return image_uint8.astype(np.uint8, copy=False)
    raise ValueError("SAM3 input image must be grayscale or RGB.")


def _normalize_masks(values: np.ndarray) -> np.ndarray:
    if values.ndim == 4 and values.shape[0] == 1:
        return np.asarray(values[0], dtype=bool)
    if values.ndim == 4 and values.shape[1] == 1:
        return np.asarray(values[:, 0, :, :], dtype=bool)
    if values.ndim == 3:
        return np.asarray(values, dtype=bool)
    if values.ndim == 2:
        return np.asarray(values[None, :, :], dtype=bool)
    return np.asarray([], dtype=bool).reshape((0, 0, 0))


def _metadata_from_npz(data: np.lib.npyio.NpzFile) -> dict[str, object]:
    metadata: dict[str, object] = {}
    for key in ("backend", "model_id", "device"):
        if key in data.files:
            metadata[key] = str(np.asarray(data[key]).item())
    return metadata


def _mask_bbox_polygon_xy(mask: np.ndarray) -> tuple[tuple[float, float], ...]:
    mask_bool = np.asarray(mask, dtype=bool)
    if mask_bool.size == 0 or not bool(mask_bool.any()):
        return ()
    y_indices, x_indices = np.nonzero(mask_bool)
    x1 = float(x_indices.min())
    y1 = float(y_indices.min())
    x2 = float(x_indices.max() + 1)
    y2 = float(y_indices.max() + 1)
    return ((x1, y1), (x2, y1), (x2, y2), (x1, y2))
