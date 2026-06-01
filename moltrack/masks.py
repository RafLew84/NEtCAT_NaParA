from __future__ import annotations

from dataclasses import dataclass
import math
from types import MappingProxyType
from typing import Any, Mapping

import numpy as np

from moltrack.core import MolecularInstanceMask, SegmentationPrompt
from nanotrack.mask_trackers import (
    MaskTrackerKind,
    MaskTrackerRunInput,
    MaskTrackerSubprocessBackend,
    default_mask_tracker_config,
)
from nanotrack.sam2 import Sam2RunInput, Sam2SubprocessBackend


@dataclass(frozen=True)
class ClassicalLocalRefinementConfig:
    """Configuration for the first classical local mask-refinement backend."""

    polarity: str = "bright"
    crop_margin_px: int = 4
    threshold_k: float = 2.5

    def __post_init__(self) -> None:
        polarity = str(self.polarity).strip().lower()
        if polarity not in {"bright", "dark"}:
            raise ValueError("polarity must be 'bright' or 'dark'.")
        crop_margin_px = int(self.crop_margin_px)
        if crop_margin_px < 0:
            raise ValueError("crop_margin_px must be non-negative.")
        threshold_k = float(self.threshold_k)
        if not np.isfinite(threshold_k) or threshold_k < 0.0:
            raise ValueError("threshold_k must be finite and non-negative.")
        object.__setattr__(self, "polarity", polarity)
        object.__setattr__(self, "crop_margin_px", crop_margin_px)
        object.__setattr__(self, "threshold_k", threshold_k)

    def to_backend_params(self) -> Mapping[str, Any]:
        return MappingProxyType(
            {
                "polarity": self.polarity,
                "crop_margin_px": self.crop_margin_px,
                "threshold_k": self.threshold_k,
            }
        )


class ClassicalLocalRefinementBackend:
    """Local threshold/half-height/gradient refinement around one prompt bbox."""

    backend_name = "classical_local_refinement"

    def __init__(self, config: ClassicalLocalRefinementConfig | None = None) -> None:
        self.config = config or ClassicalLocalRefinementConfig()

    def segment(self, frame, prompt: SegmentationPrompt) -> MolecularInstanceMask:
        frame_array = _normalize_frame(frame)
        y0, y1, x0, x1 = _crop_bounds_yxyx(
            prompt.bbox_prompt_xyxy,
            frame_shape=frame_array.shape,
            margin_px=self.config.crop_margin_px,
        )
        crop = frame_array[y0:y1, x0:x1]
        bbox_crop_mask = _bbox_mask_for_crop(prompt.bbox_prompt_xyxy, crop_shape=crop.shape, crop_origin_xy=(x0, y0))
        center_yx = (prompt.center_point_xy[1] - y0, prompt.center_point_xy[0] - x0)

        background_values = crop[~bbox_crop_mask]
        if background_values.size == 0:
            background_values = _border_values(crop)
        background_median, background_sigma = _robust_background(background_values)
        center_value = float(crop[int(round(center_yx[0])), int(round(center_yx[1]))])

        threshold_crop = _component_near_point(
            _threshold_candidate(crop, background_median, background_sigma, self.config),
            center_yx,
        )
        half_height_crop = _component_near_point(
            _half_height_candidate(crop, background_median, center_value, self.config),
            center_yx,
        )
        gradient_crop = _component_near_point(
            _gradient_candidate(crop, background_median, center_value, self.config),
            center_yx,
        )

        measurement_mask = _place_crop_mask(frame_array.shape, (y0, y1, x0, x1), threshold_crop)
        candidate_masks = (
            measurement_mask,
            _place_crop_mask(frame_array.shape, (y0, y1, x0, x1), half_height_crop),
            _place_crop_mask(frame_array.shape, (y0, y1, x0, x1), gradient_crop),
        )
        return MolecularInstanceMask(
            detection_id=prompt.detection_id,
            working_frame_index=prompt.working_frame_index,
            source_frame_index=prompt.source_frame_index,
            measurement_mask=measurement_mask,
            candidate_masks=candidate_masks,
            backend_name=self.backend_name,
            backend_params=self.config.to_backend_params(),
            score=_mask_score(measurement_mask, candidate_masks),
            coordinate_system=prompt.coordinate_system,
        )


def run_classical_local_refinement(
    frame,
    prompt: SegmentationPrompt,
    config: ClassicalLocalRefinementConfig | None = None,
) -> MolecularInstanceMask:
    return ClassicalLocalRefinementBackend(config).segment(frame, prompt)


@dataclass(frozen=True)
class Sam2FrameSegmentationConfig:
    """MolTrack adapter configuration for single-frame SAM2 segmentation."""

    source_view: str = "raw"
    mask_probability_threshold: float = 0.5

    def __post_init__(self) -> None:
        source_view = str(self.source_view).strip() or "raw"
        threshold = float(self.mask_probability_threshold)
        if not np.isfinite(threshold) or not 0.0 < threshold < 1.0:
            raise ValueError("mask_probability_threshold must be finite and in the open range (0, 1).")
        object.__setattr__(self, "source_view", source_view)
        object.__setattr__(self, "mask_probability_threshold", threshold)

    def to_backend_params(self) -> Mapping[str, Any]:
        return MappingProxyType(
            {
                "source_view": self.source_view,
                "mask_probability_threshold": self.mask_probability_threshold,
            }
        )


class Sam2FrameSegmentationBackend:
    """Frame-level MolTrack adapter around the NanoTrack SAM2 subprocess backend."""

    backend_name = "sam2"

    def __init__(
        self,
        sam2_backend=None,
        config: Sam2FrameSegmentationConfig | None = None,
    ) -> None:
        self.sam2_backend = sam2_backend or Sam2SubprocessBackend()
        self.config = config or Sam2FrameSegmentationConfig()

    def segment_frame(
        self,
        frame,
        prompts: tuple[SegmentationPrompt, ...],
    ) -> tuple[MolecularInstanceMask, ...]:
        frame_array = _normalize_sam2_frame(frame)
        prompts = tuple(prompts)
        if not prompts:
            return ()
        _validate_prompt_frame_scope(prompts)

        masks = []
        for track_id, prompt in enumerate(prompts):
            run_input = self._run_input_for_prompt(frame_array, prompt, track_id=track_id)
            run_output = self.sam2_backend.run(run_input)
            masks.append(self._instance_mask_from_output(prompt, run_output))
        return tuple(masks)

    def cancel(self) -> None:
        cancel = getattr(self.sam2_backend, "cancel", None)
        if cancel is not None:
            cancel()

    def _run_input_for_prompt(
        self,
        frame_array: np.ndarray,
        prompt: SegmentationPrompt,
        *,
        track_id: int,
    ) -> Sam2RunInput:
        return Sam2RunInput(
            track_id=track_id,
            frame_index_offset=prompt.working_frame_index,
            frames=frame_array[np.newaxis, ...],
            query_box_xyxy=np.asarray(prompt.bbox_prompt_xyxy, dtype=np.float32),
            query_point_tyx=np.asarray(
                [0.0, prompt.center_point_xy[1], prompt.center_point_xy[0]],
                dtype=np.float32,
            ),
            source_view=self.config.source_view,
            mask_probability_threshold=self.config.mask_probability_threshold,
        )

    def _instance_mask_from_output(self, prompt: SegmentationPrompt, run_output) -> MolecularInstanceMask:
        masks = np.asarray(run_output.masks, dtype=bool)
        if masks.ndim != 3 or masks.shape[0] == 0:
            raise ValueError("SAM2 output masks must have shape [T, H, W] with at least one frame.")
        visible_mask = np.asarray(run_output.visible_mask, dtype=bool)
        if visible_mask.shape != (masks.shape[0],):
            raise ValueError("SAM2 output visible_mask must match masks length.")
        measurement_mask = np.array(masks[0], dtype=bool, copy=True)
        if not bool(visible_mask[0]):
            measurement_mask[:, :] = False
        score = _sam2_output_score(run_output)
        if not bool(visible_mask[0]):
            score = 0.0
        return MolecularInstanceMask(
            detection_id=prompt.detection_id,
            working_frame_index=prompt.working_frame_index,
            source_frame_index=prompt.source_frame_index,
            measurement_mask=measurement_mask,
            candidate_masks=(measurement_mask,),
            backend_name=self.backend_name,
            backend_params=self.config.to_backend_params(),
            score=score,
            coordinate_system=prompt.coordinate_system,
        )


def run_sam2_frame_segmentation(
    frame,
    prompts: tuple[SegmentationPrompt, ...],
    *,
    sam2_backend=None,
    config: Sam2FrameSegmentationConfig | None = None,
) -> tuple[MolecularInstanceMask, ...]:
    return Sam2FrameSegmentationBackend(sam2_backend=sam2_backend, config=config).segment_frame(frame, prompts)


@dataclass(frozen=True)
class Dam4SamFrameSegmentationConfig:
    """MolTrack adapter configuration for single-frame DAM4SAM segmentation."""

    source_view: str = "raw"
    mask_probability_threshold: float = 0.5

    def __post_init__(self) -> None:
        source_view = str(self.source_view).strip() or "raw"
        threshold = float(self.mask_probability_threshold)
        if not np.isfinite(threshold) or not 0.0 < threshold < 1.0:
            raise ValueError("mask_probability_threshold must be finite and in the open range (0, 1).")
        object.__setattr__(self, "source_view", source_view)
        object.__setattr__(self, "mask_probability_threshold", threshold)

    def to_backend_params(self, run_output=None) -> Mapping[str, Any]:
        return _mask_tracker_backend_params(
            source_view=self.source_view,
            mask_probability_threshold=self.mask_probability_threshold,
            temporal_propagation_role="proposal_only",
            run_output=run_output,
        )


class Dam4SamFrameSegmentationBackend:
    """Frame-level MolTrack adapter around NanoTrack's DAM4SAM mask-tracker subprocess backend."""

    backend_name = "dam4sam"

    def __init__(
        self,
        mask_tracker_backend=None,
        config: Dam4SamFrameSegmentationConfig | None = None,
    ) -> None:
        self.mask_tracker_backend = mask_tracker_backend or MaskTrackerSubprocessBackend(
            default_mask_tracker_config(MaskTrackerKind.DAM4SAM)
        )
        self.config = config or Dam4SamFrameSegmentationConfig()

    def segment_frame(
        self,
        frame,
        prompts: tuple[SegmentationPrompt, ...],
    ) -> tuple[MolecularInstanceMask, ...]:
        frame_array = _normalize_mask_tracker_frame(frame)
        prompts = tuple(prompts)
        if not prompts:
            return ()
        _validate_prompt_frame_scope(prompts, backend_label="DAM4SAM")

        masks = []
        for track_id, prompt in enumerate(prompts):
            run_input = self._run_input_for_prompt(frame_array, prompt, track_id=track_id)
            run_output = self.mask_tracker_backend.run(run_input)
            masks.append(self._instance_mask_from_output(prompt, run_output))
        return tuple(masks)

    def cancel(self) -> None:
        cancel = getattr(self.mask_tracker_backend, "cancel", None)
        if cancel is not None:
            cancel()

    def _run_input_for_prompt(
        self,
        frame_array: np.ndarray,
        prompt: SegmentationPrompt,
        *,
        track_id: int,
    ) -> MaskTrackerRunInput:
        return MaskTrackerRunInput(
            tracker_kind=MaskTrackerKind.DAM4SAM,
            track_id=track_id,
            frame_index_offset=prompt.working_frame_index,
            frames=frame_array[np.newaxis, ...],
            query_box_xyxy=np.asarray(prompt.bbox_prompt_xyxy, dtype=np.float32),
            query_point_tyx=np.asarray(
                [0.0, prompt.center_point_xy[1], prompt.center_point_xy[0]],
                dtype=np.float32,
            ),
            source_view=self.config.source_view,
            mask_probability_threshold=self.config.mask_probability_threshold,
        )

    def _instance_mask_from_output(self, prompt: SegmentationPrompt, run_output) -> MolecularInstanceMask:
        tracker_kind = MaskTrackerKind.from_value(getattr(run_output, "tracker_kind"))
        if tracker_kind is not MaskTrackerKind.DAM4SAM:
            raise ValueError(f"DAM4SAM adapter received output for tracker {tracker_kind.value!r}.")

        masks = np.asarray(run_output.masks, dtype=bool)
        if masks.ndim != 3 or masks.shape[0] == 0:
            raise ValueError("DAM4SAM output masks must have shape [T, H, W] with at least one frame.")
        visible_mask = np.asarray(run_output.visible_mask, dtype=bool)
        if visible_mask.shape != (masks.shape[0],):
            raise ValueError("DAM4SAM output visible_mask must match masks length.")
        measurement_mask = np.array(masks[0], dtype=bool, copy=True)
        if not bool(visible_mask[0]):
            measurement_mask[:, :] = False
        score = _mask_tracker_output_score(run_output)
        if not bool(visible_mask[0]):
            score = 0.0
        return MolecularInstanceMask(
            detection_id=prompt.detection_id,
            working_frame_index=prompt.working_frame_index,
            source_frame_index=prompt.source_frame_index,
            measurement_mask=measurement_mask,
            candidate_masks=(measurement_mask,),
            backend_name=self.backend_name,
            backend_params=self.config.to_backend_params(run_output),
            score=score,
            coordinate_system=prompt.coordinate_system,
        )


def run_dam4sam_frame_segmentation(
    frame,
    prompts: tuple[SegmentationPrompt, ...],
    *,
    mask_tracker_backend=None,
    config: Dam4SamFrameSegmentationConfig | None = None,
) -> tuple[MolecularInstanceMask, ...]:
    return Dam4SamFrameSegmentationBackend(
        mask_tracker_backend=mask_tracker_backend,
        config=config,
    ).segment_frame(frame, prompts)


@dataclass(frozen=True)
class SamuraiFrameSegmentationConfig:
    """MolTrack adapter configuration for single-frame SAMURAI segmentation."""

    source_view: str = "raw"
    mask_probability_threshold: float = 0.5

    def __post_init__(self) -> None:
        source_view = str(self.source_view).strip() or "raw"
        threshold = float(self.mask_probability_threshold)
        if not np.isfinite(threshold) or not 0.0 < threshold < 1.0:
            raise ValueError("mask_probability_threshold must be finite and in the open range (0, 1).")
        object.__setattr__(self, "source_view", source_view)
        object.__setattr__(self, "mask_probability_threshold", threshold)

    def to_backend_params(self, run_output=None) -> Mapping[str, Any]:
        return _mask_tracker_backend_params(
            source_view=self.source_view,
            mask_probability_threshold=self.mask_probability_threshold,
            temporal_propagation_role="temporal_proposal",
            run_output=run_output,
        )


class SamuraiFrameSegmentationBackend:
    """Frame-level MolTrack adapter around NanoTrack's SAMURAI mask-tracker subprocess backend."""

    backend_name = "samurai"

    def __init__(
        self,
        mask_tracker_backend=None,
        config: SamuraiFrameSegmentationConfig | None = None,
    ) -> None:
        self.mask_tracker_backend = mask_tracker_backend or MaskTrackerSubprocessBackend(
            default_mask_tracker_config(MaskTrackerKind.SAMURAI)
        )
        self.config = config or SamuraiFrameSegmentationConfig()

    def segment_frame(
        self,
        frame,
        prompts: tuple[SegmentationPrompt, ...],
    ) -> tuple[MolecularInstanceMask, ...]:
        frame_array = _normalize_mask_tracker_frame(frame)
        prompts = tuple(prompts)
        if not prompts:
            return ()
        _validate_prompt_frame_scope(prompts, backend_label="SAMURAI")

        masks = []
        for track_id, prompt in enumerate(prompts):
            run_input = self._run_input_for_prompt(frame_array, prompt, track_id=track_id)
            run_output = self.mask_tracker_backend.run(run_input)
            masks.append(self._instance_mask_from_output(prompt, run_output))
        return tuple(masks)

    def cancel(self) -> None:
        cancel = getattr(self.mask_tracker_backend, "cancel", None)
        if cancel is not None:
            cancel()

    def _run_input_for_prompt(
        self,
        frame_array: np.ndarray,
        prompt: SegmentationPrompt,
        *,
        track_id: int,
    ) -> MaskTrackerRunInput:
        return MaskTrackerRunInput(
            tracker_kind=MaskTrackerKind.SAMURAI,
            track_id=track_id,
            frame_index_offset=prompt.working_frame_index,
            frames=frame_array[np.newaxis, ...],
            query_box_xyxy=np.asarray(prompt.bbox_prompt_xyxy, dtype=np.float32),
            query_point_tyx=np.asarray(
                [0.0, prompt.center_point_xy[1], prompt.center_point_xy[0]],
                dtype=np.float32,
            ),
            source_view=self.config.source_view,
            mask_probability_threshold=self.config.mask_probability_threshold,
        )

    def _instance_mask_from_output(self, prompt: SegmentationPrompt, run_output) -> MolecularInstanceMask:
        tracker_kind = MaskTrackerKind.from_value(getattr(run_output, "tracker_kind"))
        if tracker_kind is not MaskTrackerKind.SAMURAI:
            raise ValueError(f"SAMURAI adapter received output for tracker {tracker_kind.value!r}.")

        masks = np.asarray(run_output.masks, dtype=bool)
        if masks.ndim != 3 or masks.shape[0] == 0:
            raise ValueError("SAMURAI output masks must have shape [T, H, W] with at least one frame.")
        visible_mask = np.asarray(run_output.visible_mask, dtype=bool)
        if visible_mask.shape != (masks.shape[0],):
            raise ValueError("SAMURAI output visible_mask must match masks length.")
        measurement_mask = np.array(masks[0], dtype=bool, copy=True)
        if not bool(visible_mask[0]):
            measurement_mask[:, :] = False
        score = _mask_tracker_output_score(run_output)
        if not bool(visible_mask[0]):
            score = 0.0
        return MolecularInstanceMask(
            detection_id=prompt.detection_id,
            working_frame_index=prompt.working_frame_index,
            source_frame_index=prompt.source_frame_index,
            measurement_mask=measurement_mask,
            candidate_masks=(measurement_mask,),
            backend_name=self.backend_name,
            backend_params=self.config.to_backend_params(run_output),
            score=score,
            coordinate_system=prompt.coordinate_system,
        )


def run_samurai_frame_segmentation(
    frame,
    prompts: tuple[SegmentationPrompt, ...],
    *,
    mask_tracker_backend=None,
    config: SamuraiFrameSegmentationConfig | None = None,
) -> tuple[MolecularInstanceMask, ...]:
    return SamuraiFrameSegmentationBackend(
        mask_tracker_backend=mask_tracker_backend,
        config=config,
    ).segment_frame(frame, prompts)


def _normalize_frame(frame) -> np.ndarray:
    frame_array = np.asarray(frame, dtype=np.float64)
    if frame_array.ndim != 2:
        raise ValueError("frame must be a 2D image.")
    if not np.all(np.isfinite(frame_array)):
        raise ValueError("frame values must be finite.")
    return frame_array


def _normalize_sam2_frame(frame) -> np.ndarray:
    return _normalize_mask_tracker_frame(frame)


def _normalize_mask_tracker_frame(frame) -> np.ndarray:
    frame_array = np.asarray(frame, dtype=np.float32)
    if frame_array.ndim not in (2, 3):
        raise ValueError("frame must have shape [H, W] or [H, W, C].")
    if not np.all(np.isfinite(frame_array)):
        raise ValueError("frame values must be finite.")
    return frame_array


def _validate_prompt_frame_scope(prompts: tuple[SegmentationPrompt, ...], *, backend_label: str = "SAM2") -> None:
    first = prompts[0]
    for prompt in prompts:
        if prompt.working_frame_index != first.working_frame_index:
            raise ValueError(
                f"All prompts for one {backend_label} frame segmentation call must use the same "
                "working_frame_index."
            )
        if prompt.source_frame_index != first.source_frame_index:
            raise ValueError(
                f"All prompts for one {backend_label} frame segmentation call must use the same source_frame_index."
            )


def _sam2_output_score(run_output) -> float:
    return _mask_tracker_output_score(run_output)


def _mask_tracker_output_score(run_output) -> float:
    scores = getattr(run_output, "mask_scores", None)
    if scores is None:
        return 1.0
    scores = np.asarray(scores, dtype=np.float64)
    if scores.shape[0] == 0 or not np.isfinite(scores[0]):
        return 0.0
    return float(np.clip(scores[0], 0.0, 1.0))


def _mask_tracker_backend_params(
    *,
    source_view: str,
    mask_probability_threshold: float,
    temporal_propagation_role: str,
    run_output=None,
) -> Mapping[str, Any]:
    params = {
        "source_view": source_view,
        "mask_probability_threshold": mask_probability_threshold,
        "temporal_propagation_role": temporal_propagation_role,
    }
    if run_output is not None:
        model_name = getattr(run_output, "model_name", None)
        model_variant = getattr(run_output, "model_variant", None)
        checkpoint_name = getattr(run_output, "checkpoint_name", None)
        if model_name is not None:
            params["model_name"] = model_name
        if model_variant is not None:
            params["model_variant"] = model_variant
        if checkpoint_name is not None:
            params["checkpoint_name"] = checkpoint_name
    return MappingProxyType(params)


def _crop_bounds_yxyx(
    bbox_xyxy: tuple[float, float, float, float],
    *,
    frame_shape: tuple[int, int],
    margin_px: int,
) -> tuple[int, int, int, int]:
    height, width = frame_shape
    x0, y0, x1, y1 = bbox_xyxy
    crop_x0 = max(0, int(math.floor(x0)) - margin_px)
    crop_y0 = max(0, int(math.floor(y0)) - margin_px)
    crop_x1 = min(width, int(math.ceil(x1)) + margin_px)
    crop_y1 = min(height, int(math.ceil(y1)) + margin_px)
    if crop_x1 <= crop_x0 or crop_y1 <= crop_y0:
        raise ValueError("Prompt bbox does not intersect the frame.")
    return crop_y0, crop_y1, crop_x0, crop_x1


def _bbox_mask_for_crop(
    bbox_xyxy: tuple[float, float, float, float],
    *,
    crop_shape: tuple[int, int],
    crop_origin_xy: tuple[int, int],
) -> np.ndarray:
    x0, y0, x1, y1 = bbox_xyxy
    origin_x, origin_y = crop_origin_xy
    yy, xx = np.indices(crop_shape, dtype=np.float64)
    native_x = xx + origin_x + 0.5
    native_y = yy + origin_y + 0.5
    return (x0 <= native_x) & (native_x <= x1) & (y0 <= native_y) & (native_y <= y1)


def _border_values(crop: np.ndarray) -> np.ndarray:
    if crop.size == 0:
        return np.asarray([], dtype=np.float64)
    return np.concatenate((crop[0, :], crop[-1, :], crop[:, 0], crop[:, -1]))


def _robust_background(values: np.ndarray) -> tuple[float, float]:
    if values.size == 0:
        return 0.0, 1e-9
    median = float(np.median(values))
    mad = float(np.median(np.abs(values - median)))
    return median, max(1.4826 * mad, 1e-9)


def _threshold_candidate(
    crop: np.ndarray,
    background_median: float,
    background_sigma: float,
    config: ClassicalLocalRefinementConfig,
) -> np.ndarray:
    if config.polarity == "bright":
        return crop > background_median + config.threshold_k * background_sigma
    return crop < background_median - config.threshold_k * background_sigma


def _half_height_candidate(
    crop: np.ndarray,
    background_median: float,
    center_value: float,
    config: ClassicalLocalRefinementConfig,
) -> np.ndarray:
    if config.polarity == "bright":
        threshold = background_median + max(center_value - background_median, 0.0) * 0.5
        return crop >= threshold
    threshold = background_median - max(background_median - center_value, 0.0) * 0.5
    return crop <= threshold


def _gradient_candidate(
    crop: np.ndarray,
    background_median: float,
    center_value: float,
    config: ClassicalLocalRefinementConfig,
) -> np.ndarray:
    if min(crop.shape) < 2:
        return _half_height_candidate(crop, background_median, center_value, config)
    gradient_y, gradient_x = np.gradient(crop)
    gradient = np.hypot(gradient_x, gradient_y)
    if not np.any(gradient > 0.0):
        return _half_height_candidate(crop, background_median, center_value, config)
    high_gradient = gradient >= np.percentile(gradient, 90)
    edge_values = crop[high_gradient]
    if edge_values.size == 0:
        return _half_height_candidate(crop, background_median, center_value, config)
    edge_threshold = float(np.median(edge_values))
    half_height = _half_height_candidate(crop, background_median, center_value, config)
    if config.polarity == "bright":
        if not background_median < edge_threshold < max(center_value, background_median):
            return half_height
        return crop >= edge_threshold
    if not min(center_value, background_median) < edge_threshold < background_median:
        return half_height
    return crop <= edge_threshold


def _component_near_point(mask: np.ndarray, point_yx: tuple[float, float]) -> np.ndarray:
    mask = np.asarray(mask, dtype=bool)
    if not np.any(mask):
        return np.zeros_like(mask, dtype=bool)
    point_y = int(round(point_yx[0]))
    point_x = int(round(point_yx[1]))
    if 0 <= point_y < mask.shape[0] and 0 <= point_x < mask.shape[1] and mask[point_y, point_x]:
        return _flood_component(mask, (point_y, point_x))
    return _nearest_component(mask, point_yx)


def _flood_component(mask: np.ndarray, start_yx: tuple[int, int]) -> np.ndarray:
    component = np.zeros_like(mask, dtype=bool)
    stack = [start_yx]
    while stack:
        y, x = stack.pop()
        if y < 0 or x < 0 or y >= mask.shape[0] or x >= mask.shape[1]:
            continue
        if component[y, x] or not mask[y, x]:
            continue
        component[y, x] = True
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dy == 0 and dx == 0:
                    continue
                stack.append((y + dy, x + dx))
    return component


def _nearest_component(mask: np.ndarray, point_yx: tuple[float, float]) -> np.ndarray:
    remaining = np.array(mask, dtype=bool, copy=True)
    best_component = np.zeros_like(mask, dtype=bool)
    best_distance = float("inf")
    while np.any(remaining):
        y, x = np.argwhere(remaining)[0]
        component = _flood_component(remaining, (int(y), int(x)))
        remaining[component] = False
        ys, xs = np.where(component)
        distance = (float(np.mean(ys)) - point_yx[0]) ** 2 + (float(np.mean(xs)) - point_yx[1]) ** 2
        if distance < best_distance:
            best_distance = distance
            best_component = component
    return best_component


def _place_crop_mask(
    frame_shape: tuple[int, int],
    crop_bounds_yxyx: tuple[int, int, int, int],
    crop_mask: np.ndarray,
) -> np.ndarray:
    y0, y1, x0, x1 = crop_bounds_yxyx
    full_mask = np.zeros(frame_shape, dtype=bool)
    full_mask[y0:y1, x0:x1] = crop_mask
    return full_mask


def _mask_score(measurement_mask: np.ndarray, candidate_masks: tuple[np.ndarray, ...]) -> float:
    area = int(np.count_nonzero(measurement_mask))
    if area == 0:
        return 0.0
    agreements = []
    for candidate_mask in candidate_masks[1:]:
        union = np.count_nonzero(measurement_mask | candidate_mask)
        if union == 0:
            continue
        agreements.append(np.count_nonzero(measurement_mask & candidate_mask) / union)
    if not agreements:
        return 1.0
    return float(np.clip(np.mean(agreements), 0.0, 1.0))
