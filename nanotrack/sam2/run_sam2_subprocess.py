#!/usr/bin/env python3
"""Run real SAM2 inference for a single NanoTrack seed in a dedicated interpreter."""

from __future__ import annotations

from contextlib import contextmanager, nullcontext
import argparse
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Optional
import sys

import numpy as np

if __package__ in (None, ""):
    REPO_ROOT = Path(__file__).resolve().parents[2]
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from nanotrack.sam2.contract import Sam2RunInput, Sam2RunOutput
else:
    from .contract import Sam2RunInput, Sam2RunOutput


CHECKPOINT_TO_CONFIG = {
    "sam2.1_hiera_tiny.pt": "configs/sam2.1/sam2.1_hiera_t.yaml",
    "sam2.1_hiera_small.pt": "configs/sam2.1/sam2.1_hiera_s.yaml",
    "sam2.1_hiera_base_plus.pt": "configs/sam2.1/sam2.1_hiera_b+.yaml",
    "sam2.1_hiera_large.pt": "configs/sam2.1/sam2.1_hiera_l.yaml",
    "sam2_hiera_tiny.pt": "configs/sam2/sam2_hiera_t.yaml",
    "sam2_hiera_small.pt": "configs/sam2/sam2_hiera_s.yaml",
    "sam2_hiera_base_plus.pt": "configs/sam2/sam2_hiera_b+.yaml",
    "sam2_hiera_large.pt": "configs/sam2/sam2_hiera_l.yaml",
}
CONFIG_ROOT_CANDIDATES = (Path("."), Path("sam2"))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="NanoTrack SAM2 subprocess worker.")
    parser.add_argument("--input-npz", required=True, help="Input NPZ produced by NanoTrack.")
    parser.add_argument("--output-npz", required=True, help="Output NPZ path.")
    parser.add_argument("--checkpoint", required=True, help="Path to a SAM2 checkpoint.")
    parser.add_argument("--repo-path", default=None, help="Optional path to the local SAM2 repo.")
    parser.add_argument("--config", default=None, help="Optional SAM2 config path or identifier.")
    parser.add_argument("--device", default="auto", help="Torch device, e.g. auto, cuda, cuda:0, cpu.")
    parser.add_argument("--apply-postprocessing", dest="apply_postprocessing", action="store_true")
    parser.add_argument("--disable-postprocessing", dest="apply_postprocessing", action="store_false")
    parser.set_defaults(apply_postprocessing=True)
    parser.add_argument("--offload-video-to-cpu", action="store_true")
    parser.add_argument("--offload-state-to-cpu", action="store_true")
    parser.add_argument("--async-loading-frames", action="store_true")
    return parser.parse_args()


def _load_input(path: Path) -> Sam2RunInput:
    with np.load(path, allow_pickle=False) as payload:
        input_payload = {key: payload[key] for key in payload.files}
    return Sam2RunInput.from_npz_payload(input_payload)


def _normalize_path_key(path_value: str | os.PathLike[str] | None) -> str:
    if path_value is None:
        return ""
    return os.path.normcase(os.path.normpath(str(path_value)))


@contextmanager
def _sam2_import_context(repo_path: Optional[Path]):
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
        if module_name == "sam2" or module_name.startswith("sam2."):
            sys.modules.pop(module_name, None)
    try:
        yield
    finally:
        sys.path[:] = original_sys_path


def _resolve_config_identifier(
    config_path: str | Path | None,
    repo_path: Optional[Path],
    checkpoint_path: str | Path,
) -> str:
    if config_path is not None:
        config_candidate = Path(config_path).expanduser()
        if config_candidate.is_absolute():
            if repo_path is None:
                raise ValueError("Absolute config path requires repo_path.")
            resolved_candidate = config_candidate.resolve()
            resolved_repo = repo_path.resolve()
            for base_root in CONFIG_ROOT_CANDIDATES:
                try:
                    relative_path = resolved_candidate.relative_to((resolved_repo / base_root).resolve())
                except ValueError:
                    continue
                normalized = relative_path.as_posix()
                if normalized.startswith("configs/"):
                    return normalized
            raise ValueError(f"Could not derive config identifier from absolute config path: {config_path}")
        normalized = config_candidate.as_posix()
        if normalized.startswith("sam2/configs/"):
            return normalized[len("sam2/") :]
        return normalized

    checkpoint_name = Path(checkpoint_path).name
    config_identifier = CHECKPOINT_TO_CONFIG.get(checkpoint_name)
    if config_identifier is None:
        raise ValueError(f"Unsupported checkpoint without known config mapping: {checkpoint_name}")
    return config_identifier


def _resolve_torch_device(torch_module, requested_device: str):
    device = str(requested_device or "auto").strip().lower()
    if device in {"auto", "gpu"}:
        return torch_module.device("cuda" if torch_module.cuda.is_available() else "cpu")
    if device == "cuda" and not torch_module.cuda.is_available():
        return torch_module.device("cpu")
    return torch_module.device(device)


def _configure_cuda_runtime(torch_module, device) -> None:
    if not str(device).startswith("cuda") or not getattr(torch_module, "cuda", None):
        return
    try:
        index = getattr(device, "index", None)
        if index is not None:
            torch_module.cuda.set_device(index)
        major = torch_module.cuda.get_device_properties(device).major
        if major >= 8:
            torch_module.backends.cuda.matmul.allow_tf32 = True
            torch_module.backends.cudnn.allow_tf32 = True
    except Exception:
        return


def _make_autocast_context(torch_module, device):
    if str(device).startswith("cuda"):
        return torch_module.autocast("cuda", dtype=torch_module.bfloat16)
    return nullcontext()


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


def _write_video_sequence(video_dir: Path, frames_rgb: np.ndarray) -> None:
    from PIL import Image

    video_dir.mkdir(parents=True, exist_ok=True)
    for frame_idx, frame_rgb in enumerate(frames_rgb):
        Image.fromarray(frame_rgb, mode="RGB").save(video_dir / f"{frame_idx:05d}.jpg", format="JPEG", quality=95)


def _mask_logits_to_bool_mask(mask_logits: np.ndarray) -> np.ndarray:
    return _sigmoid(mask_logits) >= 0.5


def _sigmoid(values: np.ndarray) -> np.ndarray:
    clipped = np.clip(np.asarray(values, dtype=np.float32), -60.0, 60.0)
    return 1.0 / (1.0 + np.exp(-clipped))


def _mask_score_from_logits(mask_logits: np.ndarray, mask_bool: np.ndarray) -> float:
    if not np.any(mask_bool):
        return 0.0
    probabilities = _sigmoid(mask_logits)
    return float(np.mean(probabilities[mask_bool]))


def _mask_to_bbox_xyxy(mask_bool: np.ndarray) -> np.ndarray:
    ys, xs = np.nonzero(mask_bool)
    if ys.size == 0 or xs.size == 0:
        return np.asarray([0.0, 0.0, 0.0, 0.0], dtype=np.float32)
    return np.asarray(
        [float(np.min(xs)), float(np.min(ys)), float(np.max(xs) + 1), float(np.max(ys) + 1)],
        dtype=np.float32,
    )


def _mask_component_count(mask_bool: np.ndarray) -> int:
    if not np.any(mask_bool):
        return 0
    try:
        import cv2  # type: ignore

        num_labels, _ = cv2.connectedComponents(np.asarray(mask_bool, dtype=np.uint8), connectivity=8)
        return max(0, int(num_labels) - 1)
    except Exception:
        return 1


def _normalize_mask_logits(mask_logits) -> np.ndarray:
    logits = np.asarray(mask_logits, dtype=np.float32)
    if logits.ndim == 4 and logits.shape[1] == 1:
        logits = logits[:, 0]
    if logits.ndim == 3 and logits.shape[0] == 1:
        logits = logits[0]
    if logits.ndim != 2:
        raise ValueError(f"Unexpected SAM2 mask logits shape: {logits.shape}")
    return logits


def _build_output_from_frame_logits(
    *,
    track_id: int,
    frame_index_offset: int,
    frame_logits: dict[int, np.ndarray],
    frame_count: int,
    frame_shape: tuple[int, int],
) -> Sam2RunOutput:
    height, width = frame_shape
    masks = np.zeros((frame_count, height, width), dtype=bool)
    visible_mask = np.zeros((frame_count,), dtype=bool)
    mask_areas = np.zeros((frame_count,), dtype=np.float32)
    mask_bboxes_xyxy = np.zeros((frame_count, 4), dtype=np.float32)
    mask_scores = np.zeros((frame_count,), dtype=np.float32)
    mask_component_counts = np.zeros((frame_count,), dtype=np.int32)

    for frame_idx, logits in frame_logits.items():
        if not 0 <= frame_idx < frame_count:
            raise ValueError(f"Frame index {frame_idx} is out of range for frame_count={frame_count}.")
        mask_logits = _normalize_mask_logits(logits)
        if mask_logits.shape != (height, width):
            raise ValueError(
                f"Mask logits shape {mask_logits.shape} does not match expected frame shape {(height, width)}."
            )
        mask_bool = _mask_logits_to_bool_mask(mask_logits)
        masks[frame_idx] = mask_bool
        visible_mask[frame_idx] = bool(np.any(mask_bool))
        mask_areas[frame_idx] = float(np.count_nonzero(mask_bool))
        mask_bboxes_xyxy[frame_idx] = _mask_to_bbox_xyxy(mask_bool)
        mask_scores[frame_idx] = _mask_score_from_logits(mask_logits, mask_bool)
        mask_component_counts[frame_idx] = _mask_component_count(mask_bool)

    return Sam2RunOutput(
        track_id=track_id,
        frame_index_offset=frame_index_offset,
        masks=masks,
        visible_mask=visible_mask,
        mask_areas=mask_areas,
        mask_bboxes_xyxy=mask_bboxes_xyxy,
        mask_scores=mask_scores,
        mask_component_counts=mask_component_counts,
    )


def _run_real_sam2(
    run_input: Sam2RunInput,
    *,
    checkpoint_path: Path,
    repo_path: Path | None,
    config_path: str | Path | None,
    device_name: str,
    apply_postprocessing: bool,
    offload_video_to_cpu: bool,
    offload_state_to_cpu: bool,
    async_loading_frames: bool,
) -> Sam2RunOutput:
    with _sam2_import_context(repo_path):
        import torch
        from sam2.build_sam import build_sam2_video_predictor

        config_identifier = _resolve_config_identifier(config_path, repo_path, checkpoint_path)
        device = _resolve_torch_device(torch, device_name)
        _configure_cuda_runtime(torch, device)

        predictor = build_sam2_video_predictor(
            config_identifier,
            str(checkpoint_path),
            device=device,
            vos_optimized=False,
            apply_postprocessing=apply_postprocessing,
        )

        frames_rgb = _prepare_frames_rgb(run_input.frames)
        prompt_frame_idx = int(run_input.query_point_tyx[0]) if run_input.query_point_tyx is not None else 0
        frame_logits: dict[int, np.ndarray] = {}

        with TemporaryDirectory(prefix="nanotrack_sam2_frames_") as temp_dir:
            video_dir = Path(temp_dir)
            _write_video_sequence(video_dir, frames_rgb)
            state = predictor.init_state(
                str(video_dir),
                offload_video_to_cpu=offload_video_to_cpu,
                offload_state_to_cpu=offload_state_to_cpu,
                async_loading_frames=async_loading_frames,
            )

            if run_input.initial_mask is not None:
                predictor.add_new_mask(
                    state,
                    frame_idx=0,
                    obj_id=int(run_input.track_id),
                    mask=run_input.initial_mask,
                )
                prompt_frame_idx = 0
            else:
                points = None
                labels = None
                if run_input.query_point_tyx is not None:
                    points = np.asarray([[run_input.query_point_tyx[2], run_input.query_point_tyx[1]]], dtype=np.float32)
                    labels = np.asarray([1], dtype=np.int32)
                predictor.add_new_points_or_box(
                    state,
                    frame_idx=prompt_frame_idx,
                    obj_id=int(run_input.track_id),
                    points=points,
                    labels=labels,
                    box=(
                        None
                        if run_input.query_box_xyxy is None
                        else np.asarray(run_input.query_box_xyxy, dtype=np.float32)
                    ),
                )

            autocast_context = _make_autocast_context(torch, device)
            with torch.inference_mode():
                with autocast_context:
                    for local_frame_idx, obj_ids, video_res_masks in predictor.propagate_in_video(
                        state,
                        start_frame_idx=prompt_frame_idx,
                        max_frame_num_to_track=int(run_input.frames.shape[0] - prompt_frame_idx),
                    ):
                        obj_ids_list = [int(obj_id) for obj_id in obj_ids]
                        if int(run_input.track_id) not in obj_ids_list:
                            continue
                        obj_offset = obj_ids_list.index(int(run_input.track_id))
                        frame_logits[int(local_frame_idx)] = np.asarray(video_res_masks[obj_offset].detach().cpu().numpy())

            if hasattr(predictor, "reset_state"):
                predictor.reset_state(state)

    return _build_output_from_frame_logits(
        track_id=run_input.track_id,
        frame_index_offset=run_input.frame_index_offset,
        frame_logits=frame_logits,
        frame_count=int(run_input.frames.shape[0]),
        frame_shape=tuple(run_input.frames.shape[1:3]),
    )


def main() -> int:
    args = _parse_args()
    input_path = Path(args.input_npz).resolve()
    output_path = Path(args.output_npz).resolve()

    run_input = _load_input(input_path)
    run_output = _run_real_sam2(
        run_input,
        checkpoint_path=Path(args.checkpoint).expanduser().resolve(),
        repo_path=None if args.repo_path is None else Path(args.repo_path).expanduser().resolve(),
        config_path=args.config,
        device_name=args.device,
        apply_postprocessing=bool(args.apply_postprocessing),
        offload_video_to_cpu=bool(args.offload_video_to_cpu),
        offload_state_to_cpu=bool(args.offload_state_to_cpu),
        async_loading_frames=bool(args.async_loading_frames),
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(output_path, **run_output.to_npz_payload())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
