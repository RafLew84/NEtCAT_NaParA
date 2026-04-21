#!/usr/bin/env python3
"""Run TAPIR inference for NanoTrack in a dedicated interpreter."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import numpy as np

if __package__ in (None, ""):
    REPO_ROOT = Path(__file__).resolve().parents[2]
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from nanotrack.trackers.contract import PointTrackerRunInput, PointTrackerRunOutput
else:
    from .contract import PointTrackerRunInput, PointTrackerRunOutput


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="NanoTrack TAPIR subprocess worker.")
    parser.add_argument("--input-npz", required=True, help="Input NPZ produced by NanoTrack.")
    parser.add_argument("--output-npz", required=True, help="Output NPZ path.")
    parser.add_argument("--model-name", required=True, help="Tracker name, e.g. tapir.")
    parser.add_argument("--device", default="auto", help="Torch device, e.g. auto, cuda, cuda:0, cpu.")
    parser.add_argument("--repo-path", default=None, help="Optional path to the local tapnet repo.")
    parser.add_argument("--checkpoint", default=None, help="Optional TAPIR PyTorch checkpoint path.")
    return parser.parse_args()


def _load_input(path: Path) -> PointTrackerRunInput:
    with np.load(path, allow_pickle=False) as payload:
        input_payload = {key: payload[key] for key in payload.files}
    return PointTrackerRunInput.from_npz_payload(input_payload)


def _normalize_to_uint8(values: np.ndarray) -> np.ndarray:
    values_f32 = np.asarray(values, dtype=np.float32)
    finite_mask = np.isfinite(values_f32)
    if not np.any(finite_mask):
        return np.zeros(values_f32.shape, dtype=np.uint8)
    finite_values = values_f32[finite_mask]
    value_min = float(np.min(finite_values))
    value_max = float(np.max(finite_values))
    if value_max <= value_min + 1e-8:
        return np.zeros(values_f32.shape, dtype=np.uint8)
    normalized = np.clip((values_f32 - value_min) / (value_max - value_min), 0.0, 1.0)
    return np.asarray(np.round(normalized * 255.0), dtype=np.uint8)


def _frames_to_rgb_uint8(frames: np.ndarray) -> np.ndarray:
    frames_np = np.asarray(frames)
    if frames_np.ndim == 3:
        gray = _normalize_to_uint8(frames_np)
        return np.repeat(gray[..., None], 3, axis=-1)

    if frames_np.ndim != 4:
        raise ValueError("frames must have shape [T, H, W] or [T, H, W, C].")

    channel_count = int(frames_np.shape[-1])
    if channel_count == 1:
        gray = _normalize_to_uint8(frames_np[..., 0])
        return np.repeat(gray[..., None], 3, axis=-1)

    channels: list[np.ndarray] = []
    for channel_idx in range(min(3, channel_count)):
        channels.append(_normalize_to_uint8(frames_np[..., channel_idx]))
    while len(channels) < 3:
        channels.append(channels[-1].copy())
    return np.stack(channels[:3], axis=-1)


def _resolve_inference_shape(
    source_hw: tuple[int, int],
    inference_resolution_hw: np.ndarray | None,
) -> tuple[int, int]:
    if inference_resolution_hw is None:
        return (256, 256)

    resolution = np.asarray(inference_resolution_hw, dtype=np.int32)
    if resolution.shape != (2,):
        raise ValueError("inference_resolution_hw must have shape [2].")
    if int(resolution[0]) <= 0 or int(resolution[1]) <= 0:
        raise ValueError("inference_resolution_hw must contain positive integers.")
    return int(resolution[0]), int(resolution[1])


def _resize_video(video_rgb: np.ndarray, target_hw: tuple[int, int]) -> np.ndarray:
    target_height, target_width = target_hw
    try:
        import cv2

        resized_frames = [
            cv2.resize(frame, (target_width, target_height), interpolation=cv2.INTER_LINEAR)
            for frame in video_rgb
        ]
        return np.asarray(resized_frames, dtype=np.uint8)
    except ModuleNotFoundError:
        from PIL import Image

        resized_frames = []
        for frame in video_rgb:
            image = Image.fromarray(np.asarray(frame, dtype=np.uint8))
            resized = image.resize((target_width, target_height), resample=Image.BILINEAR)
            resized_frames.append(np.asarray(resized, dtype=np.uint8))
        return np.asarray(resized_frames, dtype=np.uint8)


def _preprocess_frames(video_rgb_uint8: np.ndarray) -> np.ndarray:
    frames_f32 = np.asarray(video_rgb_uint8, dtype=np.float32)
    return frames_f32 / 255.0 * 2.0 - 1.0


def _scale_query_points_tyx(
    query_points_tyx: np.ndarray,
    source_hw: tuple[int, int],
    target_hw: tuple[int, int],
) -> np.ndarray:
    scaled = np.asarray(query_points_tyx, dtype=np.float32).copy()
    source_height, source_width = source_hw
    target_height, target_width = target_hw
    scaled[:, 1] *= float(target_height) / float(source_height)
    scaled[:, 2] *= float(target_width) / float(source_width)
    return scaled


def _scale_tracks_xy(
    tracks_xy: np.ndarray,
    source_hw: tuple[int, int],
    target_hw: tuple[int, int],
) -> np.ndarray:
    scaled = np.asarray(tracks_xy, dtype=np.float32).copy()
    source_height, source_width = source_hw
    target_height, target_width = target_hw
    scaled[..., 0] *= float(target_width) / float(source_width)
    scaled[..., 1] *= float(target_height) / float(source_height)
    return scaled


def _sigmoid(values: np.ndarray) -> np.ndarray:
    values_f32 = np.asarray(values, dtype=np.float32)
    return 1.0 / (1.0 + np.exp(-values_f32))


def _postprocess_scores(
    occlusion_logits: np.ndarray,
    expected_dist_logits: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    occlusion_scores = _sigmoid(occlusion_logits)
    expected_dist_scores = _sigmoid(expected_dist_logits)
    confidence_scores = (1.0 - occlusion_scores) * (1.0 - expected_dist_scores)
    visible_mask = confidence_scores > 0.5
    return visible_mask, occlusion_scores, confidence_scores, expected_dist_scores


def _build_stub_output(
    run_input: PointTrackerRunInput,
    *,
    model_name: str,
    checkpoint_name: str | None,
) -> PointTrackerRunOutput:
    frame_count = int(np.asarray(run_input.frames).shape[0])
    query_points = np.asarray(run_input.query_points_tyx, dtype=np.float32)
    point_count = int(query_points.shape[0])

    tracks_xy = np.zeros((point_count, frame_count, 2), dtype=np.float32)
    visible_mask = np.zeros((point_count, frame_count), dtype=bool)
    occlusion_scores = np.ones((point_count, frame_count), dtype=np.float32)
    confidence_scores = np.zeros((point_count, frame_count), dtype=np.float32)
    expected_dist_scores = np.zeros((point_count, frame_count), dtype=np.float32)

    for point_idx, query_point in enumerate(query_points):
        start_frame = int(np.floor(query_point[0]))
        y = float(query_point[1])
        x = float(query_point[2])
        tracks_xy[point_idx, :, 0] = x
        tracks_xy[point_idx, :, 1] = y
        visible_mask[point_idx, start_frame:] = True
        occlusion_scores[point_idx, start_frame:] = 0.0
        confidence_scores[point_idx, start_frame:] = 1.0

    return PointTrackerRunOutput(
        tracks_xy=tracks_xy,
        visible_mask=visible_mask,
        occlusion_scores=occlusion_scores,
        confidence_scores=confidence_scores,
        expected_dist=expected_dist_scores,
        model_name=model_name,
        checkpoint_name=checkpoint_name,
    )


def _resolve_repo_root(repo_path: str | Path | None) -> Path:
    if repo_path is None:
        raise ValueError("repo_path is required for real TAPIR inference.")
    candidate = Path(repo_path).expanduser().resolve()
    package_root = candidate / "tapnet"
    if not package_root.exists():
        raise FileNotFoundError(f"TAPIR repo does not contain tapnet package: {package_root}")
    return candidate


def _load_torch():
    import torch

    return torch


def _resolve_torch_device(torch_module, requested_device: str):
    device = str(requested_device or "auto").strip().lower()
    if device in {"auto", "gpu"}:
        return torch_module.device("cuda" if torch_module.cuda.is_available() else "cpu")
    if device == "cuda" and not torch_module.cuda.is_available():
        return torch_module.device("cpu")
    return torch_module.device(device)


def _load_tapir_model_class(repo_root: Path):
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from tapnet.torch import tapir_model

    return tapir_model.TAPIR


def _uses_bootstrap_architecture(checkpoint_path: Path) -> bool:
    checkpoint_name = checkpoint_path.name.lower()
    return "bootstap" in checkpoint_name


def _load_model(
    *,
    repo_root: Path,
    checkpoint_path: Path,
    requested_device: str,
):
    torch_module = _load_torch()
    device = _resolve_torch_device(torch_module, requested_device)

    TAPIR = _load_tapir_model_class(repo_root)
    model = TAPIR(
        pyramid_level=1,
        extra_convs=_uses_bootstrap_architecture(checkpoint_path),
    )
    state_dict = torch_module.load(checkpoint_path, map_location=device)
    model.load_state_dict(state_dict)
    model = model.to(device)
    model.eval()
    return model, torch_module, device


def _run_real_inference(
    run_input: PointTrackerRunInput,
    *,
    repo_root: Path,
    checkpoint_path: Path,
    requested_device: str,
    model_name: str,
) -> PointTrackerRunOutput:
    model, torch_module, device = _load_model(
        repo_root=repo_root,
        checkpoint_path=checkpoint_path,
        requested_device=requested_device,
    )

    video_rgb_uint8 = _frames_to_rgb_uint8(run_input.frames)
    source_hw = tuple(int(v) for v in video_rgb_uint8.shape[1:3])
    target_hw = _resolve_inference_shape(source_hw, run_input.inference_resolution_hw)
    if target_hw != source_hw:
        resized_video = _resize_video(video_rgb_uint8, target_hw)
    else:
        resized_video = video_rgb_uint8

    preprocessed_video = _preprocess_frames(resized_video)
    scaled_query_points = _scale_query_points_tyx(run_input.query_points_tyx, source_hw, target_hw)

    video_tensor = torch_module.from_numpy(preprocessed_video[None, ...].copy()).float().to(device)
    query_tensor = torch_module.from_numpy(scaled_query_points[None, ...].copy()).float().to(device)

    query_chunk_size = run_input.query_chunk_size
    with torch_module.no_grad():
        outputs = model(
            video_tensor,
            query_tensor,
            query_chunk_size=query_chunk_size,
        )

    tracks_xy = outputs["tracks"][0].detach().cpu().numpy().astype(np.float32, copy=False)
    occlusion_logits = outputs["occlusion"][0].detach().cpu().numpy().astype(np.float32, copy=False)
    expected_dist_logits = outputs["expected_dist"][0].detach().cpu().numpy().astype(np.float32, copy=False)
    tracks_xy = _scale_tracks_xy(tracks_xy, target_hw, source_hw)
    visible_mask, occlusion_scores, confidence_scores, expected_dist_scores = _postprocess_scores(
        occlusion_logits,
        expected_dist_logits,
    )

    return PointTrackerRunOutput(
        tracks_xy=tracks_xy,
        visible_mask=visible_mask,
        occlusion_scores=occlusion_scores,
        confidence_scores=confidence_scores,
        expected_dist=expected_dist_scores,
        model_name=model_name,
        checkpoint_name=checkpoint_path.name,
    )


def main() -> int:
    args = _parse_args()
    run_input = _load_input(Path(args.input_npz))
    output_path = Path(args.output_npz)

    if args.checkpoint is None:
        result = _build_stub_output(
            run_input,
            model_name=f"{args.model_name}_stub",
            checkpoint_name=None,
        )
    else:
        checkpoint_path = Path(args.checkpoint).expanduser().resolve()
        if not checkpoint_path.exists():
            raise FileNotFoundError(f"TAPIR checkpoint not found: {checkpoint_path}")
        repo_root = _resolve_repo_root(args.repo_path)
        result = _run_real_inference(
            run_input,
            repo_root=repo_root,
            checkpoint_path=checkpoint_path,
            requested_device=args.device,
            model_name=args.model_name,
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(output_path, **result.to_npz_payload())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
