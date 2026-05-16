#!/usr/bin/env python3
"""Run DAM4SAM inference for one NanoTrack mask-tracker seed."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import importlib
import os
from pathlib import Path
import sys
from typing import Optional

import numpy as np

if __package__ in (None, ""):
    REPO_ROOT = Path(__file__).resolve().parents[2]
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from nanotrack.mask_trackers.config import MaskTrackerKind
    from nanotrack.mask_trackers.contract import MaskTrackerRunInput, MaskTrackerRunOutput
else:
    from .config import MaskTrackerKind
    from .contract import MaskTrackerRunInput, MaskTrackerRunOutput


DEFAULT_DAM4SAM_VARIANT = "sam21pp-B"
VARIANT_TO_CONFIG = {
    "sam21pp-L": "sam21pp_hiera_l.yaml",
    "sam21pp-B": "sam21pp_hiera_b+.yaml",
    "sam21pp-S": "sam21pp_hiera_s.yaml",
    "sam21pp-T": "sam21pp_hiera_t.yaml",
}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="NanoTrack DAM4SAM subprocess worker.")
    parser.add_argument("--input-npz", required=True, help="Input NPZ produced by NanoTrack.")
    parser.add_argument("--output-npz", required=True, help="Output NPZ path.")
    parser.add_argument("--checkpoint", required=True, help="Path to a DAM4SAM/SAM2 checkpoint.")
    parser.add_argument("--repo-path", default=None, help="Optional path to the local DAM4SAM repo.")
    parser.add_argument("--variant", default=None, help="DAM4SAM tracker variant.")
    parser.add_argument("--config", default=None, help="DAM4SAM config identifier.")
    parser.add_argument("--device", default="auto", help="Torch device request; DAM4SAM currently expects CUDA.")
    parser.add_argument("--stub", action="store_true", help="Use deterministic synthetic masks instead of DAM4SAM.")
    return parser.parse_args()


def _load_input(path: Path) -> MaskTrackerRunInput:
    with np.load(path, allow_pickle=False) as payload:
        input_payload = {key: payload[key] for key in payload.files}
    return MaskTrackerRunInput.from_npz_payload(input_payload)


def _normalize_path_key(path_value: str | os.PathLike[str] | None) -> str:
    if path_value is None:
        return ""
    return os.path.normcase(os.path.normpath(str(path_value)))


@contextmanager
def _dam4sam_import_context(repo_path: Optional[Path]):
    if repo_path is None:
        yield
        return

    resolved_repo_path = repo_path.resolve()
    repo_root_str = str(resolved_repo_path)
    repo_root_key = _normalize_path_key(resolved_repo_path)
    repo_parent_key = _normalize_path_key(resolved_repo_path.parent)
    original_sys_path = list(sys.path)

    filtered_sys_path: list[str] = []
    for entry in original_sys_path:
        entry_key = _normalize_path_key(entry)
        if not entry_key:
            filtered_sys_path.append(entry)
            continue
        if entry_key in {repo_root_key, repo_parent_key}:
            continue
        filtered_sys_path.append(entry)

    sys.path[:] = [repo_root_str, *filtered_sys_path]
    for module_name in list(sys.modules):
        if (
            module_name == "dam4sam_tracker"
            or module_name.startswith("sam2.")
            or module_name == "sam2"
            or module_name.startswith("utils.")
            or module_name == "utils"
        ):
            sys.modules.pop(module_name, None)
    try:
        yield
    finally:
        sys.path[:] = original_sys_path


def _prepare_frames_rgb(frames: np.ndarray) -> np.ndarray:
    frames_np = np.asarray(frames)
    if frames_np.ndim == 3:
        frames_np = frames_np[..., None]
    if frames_np.ndim != 4:
        raise ValueError("frames must have shape [T, H, W] or [T, H, W, C].")
    if frames_np.shape[-1] == 1:
        frames_np = np.repeat(frames_np, 3, axis=-1)
    elif frames_np.shape[-1] >= 3:
        frames_np = frames_np[..., :3]
    else:
        raise ValueError("frames channel dimension must be 1 or >=3.")

    output = np.zeros(frames_np.shape, dtype=np.uint8)
    for frame_idx, frame in enumerate(frames_np):
        frame_f32 = np.asarray(frame, dtype=np.float32)
        finite_mask = np.isfinite(frame_f32)
        if not np.any(finite_mask):
            continue
        finite_values = frame_f32[finite_mask]
        value_min = float(np.min(finite_values))
        value_max = float(np.max(finite_values))
        if value_max <= value_min + 1e-8:
            continue
        normalized = np.clip((frame_f32 - value_min) / (value_max - value_min), 0.0, 1.0)
        output[frame_idx] = np.asarray(np.round(normalized * 255.0), dtype=np.uint8)
    return output


def _frames_to_pil_images(frames: np.ndarray):
    from PIL import Image

    frames_rgb = _prepare_frames_rgb(frames)
    return [Image.fromarray(frame_rgb, mode="RGB") for frame_rgb in frames_rgb]


def _query_bbox_xywh(run_input: MaskTrackerRunInput) -> np.ndarray | None:
    if run_input.query_box_xyxy is not None:
        x0, y0, x1, y1 = [float(value) for value in run_input.query_box_xyxy]
        return np.asarray([x0, y0, max(0.0, x1 - x0), max(0.0, y1 - y0)], dtype=np.float32)
    if run_input.query_point_tyx is not None:
        _local_t, y, x = [float(value) for value in run_input.query_point_tyx]
        return np.asarray([x - 1.0, y - 1.0, 3.0, 3.0], dtype=np.float32)
    return None


def _resolve_config_identifier(config_identifier: str | None, variant: str | None) -> str:
    if config_identifier:
        return str(config_identifier)
    tracker_variant = variant or DEFAULT_DAM4SAM_VARIANT
    if tracker_variant not in VARIANT_TO_CONFIG:
        raise ValueError(f"Unsupported DAM4SAM variant without explicit config: {tracker_variant!r}.")
    return VARIANT_TO_CONFIG[tracker_variant]


def _run_real_dam4sam(
    run_input: MaskTrackerRunInput,
    *,
    checkpoint_path: Path,
    repo_path: Path | None,
    variant: str | None,
    config_identifier: str | None,
    device_name: str,
) -> MaskTrackerRunOutput:
    if run_input.tracker_kind is not MaskTrackerKind.DAM4SAM:
        raise ValueError(
            f"DAM4SAM worker expected tracker_kind='dam4sam', got {run_input.tracker_kind.value!r}."
        )
    with _dam4sam_import_context(repo_path):
        tracker_module = importlib.import_module("dam4sam_tracker")
        tracker_class = getattr(tracker_module, "DAM4SAMTracker")
        tracker_variant = variant or DEFAULT_DAM4SAM_VARIANT
        resolved_config = _resolve_config_identifier(config_identifier, tracker_variant)

        original_determine_tracker = getattr(tracker_module, "determine_tracker", None)
        if original_determine_tracker is not None:
            tracker_module.determine_tracker = lambda _tracker_name: (str(checkpoint_path), resolved_config)
        try:
            tracker = tracker_class(tracker_name=tracker_variant)
        finally:
            if original_determine_tracker is not None:
                tracker_module.determine_tracker = original_determine_tracker

        frames_pil = _frames_to_pil_images(run_input.frames)
        init_mask = None if run_input.initial_mask is None else np.asarray(run_input.initial_mask, dtype=np.uint8)
        init_bbox_xywh = _query_bbox_xywh(run_input)
        if init_mask is None and init_bbox_xywh is None:
            raise ValueError("DAM4SAM real inference requires initial_mask, query_box_xyxy, or query_point_tyx.")

        masks: list[np.ndarray] = []
        first_output = tracker.initialize(frames_pil[0], init_mask, bbox=init_bbox_xywh)
        masks.append(_coerce_pred_mask(first_output["pred_mask"], frame_shape=run_input.frames.shape[1:3]))
        for frame_pil in frames_pil[1:]:
            output = tracker.track(frame_pil)
            masks.append(_coerce_pred_mask(output["pred_mask"], frame_shape=run_input.frames.shape[1:3]))

    return _output_from_masks(
        run_input,
        masks=np.asarray(masks, dtype=bool),
        model_name="dam4sam",
        checkpoint_name=checkpoint_path.name,
        variant=variant,
    )


def _coerce_pred_mask(mask: np.ndarray, *, frame_shape: tuple[int, int]) -> np.ndarray:
    height, width = frame_shape
    mask_np = np.asarray(mask, dtype=bool)
    if mask_np.ndim != 2:
        raise ValueError(f"DAM4SAM pred_mask must be 2D, got shape {mask_np.shape}.")
    if mask_np.shape == (height, width):
        return mask_np
    output = np.zeros((height, width), dtype=bool)
    copy_height = min(height, mask_np.shape[0])
    copy_width = min(width, mask_np.shape[1])
    output[:copy_height, :copy_width] = mask_np[:copy_height, :copy_width]
    return output


def _synthetic_output(
    run_input: MaskTrackerRunInput,
    *,
    checkpoint_name: str,
    variant: str | None,
) -> MaskTrackerRunOutput:
    if run_input.tracker_kind is not MaskTrackerKind.DAM4SAM:
        raise ValueError(
            f"DAM4SAM worker expected tracker_kind='dam4sam', got {run_input.tracker_kind.value!r}."
        )

    frame_count, height, width = run_input.frames.shape[:3]
    masks = np.zeros((frame_count, height, width), dtype=bool)

    if run_input.initial_mask is not None:
        masks[:] = run_input.initial_mask
    elif run_input.query_box_xyxy is not None:
        masks[:] = _mask_from_bbox(run_input.query_box_xyxy, height=height, width=width)
    elif run_input.query_point_tyx is not None:
        masks[:] = _mask_from_point(run_input.query_point_tyx, height=height, width=width)
    else:  # Defensive only; MaskTrackerRunInput already validates this.
        raise ValueError("DAM4SAM stub requires a bbox, point, or initial mask prompt.")

    return _output_from_masks(
        run_input,
        masks=masks,
        model_name="dam4sam_stub",
        checkpoint_name=checkpoint_name,
        variant=variant,
    )


def _output_from_masks(
    run_input: MaskTrackerRunInput,
    *,
    masks: np.ndarray,
    model_name: str,
    checkpoint_name: str,
    variant: str | None,
) -> MaskTrackerRunOutput:
    masks_bool = np.asarray(masks, dtype=bool)
    visible_mask = np.any(masks_bool, axis=(1, 2))
    mask_areas = np.asarray([float(np.count_nonzero(mask)) for mask in masks_bool], dtype=np.float32)
    mask_bboxes = np.asarray([_bbox_from_mask(mask) for mask in masks_bool], dtype=np.float32)
    mask_scores = visible_mask.astype(np.float32)
    mask_component_counts = np.asarray([_mask_component_count(mask) for mask in masks_bool], dtype=np.int32)

    return MaskTrackerRunOutput(
        tracker_kind=MaskTrackerKind.DAM4SAM,
        track_id=run_input.track_id,
        frame_index_offset=run_input.frame_index_offset,
        masks=masks_bool,
        visible_mask=visible_mask,
        mask_areas=mask_areas,
        mask_bboxes_xyxy=mask_bboxes,
        mask_scores=mask_scores,
        mask_component_counts=mask_component_counts,
        model_name=model_name,
        model_variant=variant,
        checkpoint_name=checkpoint_name,
    )


def _mask_from_bbox(bbox_xyxy: np.ndarray, *, height: int, width: int) -> np.ndarray:
    x0, y0, x1, y1 = [float(value) for value in np.asarray(bbox_xyxy, dtype=np.float32)]
    col0 = max(0, min(width, int(np.floor(x0))))
    row0 = max(0, min(height, int(np.floor(y0))))
    col1 = max(0, min(width, int(np.ceil(x1))))
    row1 = max(0, min(height, int(np.ceil(y1))))

    mask = np.zeros((height, width), dtype=bool)
    if col1 > col0 and row1 > row0:
        mask[row0:row1, col0:col1] = True
    return mask


def _mask_from_point(point_tyx: np.ndarray, *, height: int, width: int) -> np.ndarray:
    _local_t, y, x = [float(value) for value in np.asarray(point_tyx, dtype=np.float32)]
    center_col = int(round(x))
    center_row = int(round(y))
    col0 = max(0, center_col - 1)
    row0 = max(0, center_row - 1)
    col1 = min(width, center_col + 2)
    row1 = min(height, center_row + 2)

    mask = np.zeros((height, width), dtype=bool)
    if col1 > col0 and row1 > row0:
        mask[row0:row1, col0:col1] = True
    return mask


def _bbox_from_mask(mask: np.ndarray) -> tuple[float, float, float, float]:
    rows, cols = np.nonzero(mask)
    if rows.size == 0 or cols.size == 0:
        return (0.0, 0.0, 0.0, 0.0)
    return (
        float(cols.min()),
        float(rows.min()),
        float(cols.max() + 1),
        float(rows.max() + 1),
    )


def _mask_component_count(mask: np.ndarray) -> int:
    if not np.any(mask):
        return 0
    try:
        import cv2  # type: ignore

        num_labels, _ = cv2.connectedComponents(np.asarray(mask, dtype=np.uint8), connectivity=8)
        return max(0, int(num_labels) - 1)
    except Exception:
        return 1


def main() -> int:
    args = _parse_args()
    checkpoint_path = Path(args.checkpoint).expanduser().resolve()
    run_input = _load_input(Path(args.input_npz).resolve())
    if args.stub or args.variant == "stub":
        run_output = _synthetic_output(
            run_input,
            checkpoint_name=checkpoint_path.name,
            variant=args.variant,
        )
    else:
        run_output = _run_real_dam4sam(
            run_input,
            checkpoint_path=checkpoint_path,
            repo_path=None if args.repo_path is None else Path(args.repo_path).expanduser().resolve(),
            variant=args.variant,
            config_identifier=args.config,
            device_name=str(args.device),
        )
    output_path = Path(args.output_npz)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(output_path, **run_output.to_npz_payload())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
