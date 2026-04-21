#!/usr/bin/env python3
"""Run Track-On-R inference for NanoTrack in a dedicated interpreter."""

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
    parser = argparse.ArgumentParser(description="NanoTrack Track-On-R subprocess worker.")
    parser.add_argument("--input-npz", required=True, help="Input NPZ produced by NanoTrack.")
    parser.add_argument("--output-npz", required=True, help="Output NPZ path.")
    parser.add_argument("--model-name", required=True, help="Tracker name, e.g. trackonr.")
    parser.add_argument("--device", default="auto", help="Torch device, e.g. auto, cuda, cuda:0, cpu.")
    parser.add_argument("--repo-path", default=None, help="Optional path to the local Track-On repo.")
    parser.add_argument("--checkpoint", default=None, help="Optional Track-On checkpoint path.")
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


def _query_points_tyx_to_txy(query_points_tyx: np.ndarray) -> np.ndarray:
    query_points = np.asarray(query_points_tyx, dtype=np.float32)
    converted = query_points.copy()
    converted[:, 1] = query_points[:, 2]
    converted[:, 2] = query_points[:, 1]
    return converted


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

    for point_idx, query_point in enumerate(query_points):
        start_frame = int(np.floor(query_point[0]))
        y = float(query_point[1])
        x = float(query_point[2])
        tracks_xy[point_idx, :, 0] = x
        tracks_xy[point_idx, :, 1] = y
        visible_mask[point_idx, start_frame:] = True

    return PointTrackerRunOutput(
        tracks_xy=tracks_xy,
        visible_mask=visible_mask,
        model_name=model_name,
        checkpoint_name=checkpoint_name,
    )


def _resolve_repo_root(repo_path: str | Path | None) -> Path:
    if repo_path is None:
        raise ValueError("repo_path is required for real Track-On-R inference.")
    candidate = Path(repo_path).expanduser().resolve()
    model_dir = candidate / "model"
    if not model_dir.exists():
        raise FileNotFoundError(f"Track-On repo does not contain model directory: {model_dir}")
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


def _load_predictor_class(repo_root: Path):
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from model.trackon_predictor import Predictor

    return Predictor


def _load_predictor(repo_root: Path, checkpoint_path: Path, requested_device: str):
    torch_module = _load_torch()
    device = _resolve_torch_device(torch_module, requested_device)
    Predictor = _load_predictor_class(repo_root)
    predictor = Predictor(model_args=None, checkpoint_path=str(checkpoint_path), support_grid_size=0)
    predictor = predictor.to(device)
    predictor.eval()
    return predictor, torch_module, device


def _run_real_inference(
    run_input: PointTrackerRunInput,
    *,
    repo_root: Path,
    checkpoint_path: Path,
    requested_device: str,
    model_name: str,
) -> PointTrackerRunOutput:
    predictor, torch_module, device = _load_predictor(repo_root, checkpoint_path, requested_device)

    video_rgb_uint8 = _frames_to_rgb_uint8(run_input.frames)
    video_tchw = np.transpose(video_rgb_uint8, (0, 3, 1, 2)).astype(np.float32, copy=False)
    video_tensor = torch_module.from_numpy(video_tchw[None, ...].copy()).to(device)

    query_points_txy = _query_points_tyx_to_txy(run_input.query_points_tyx)
    query_tensor = torch_module.from_numpy(query_points_txy[None, ...].copy()).float().to(device)

    with torch_module.no_grad():
        tracks, visible_mask = predictor(video_tensor, query_tensor)

    tracks_xy = tracks[0].detach().cpu().numpy().transpose(1, 0, 2).astype(np.float32, copy=False)
    visible_mask_np = visible_mask[0].detach().cpu().numpy().transpose(1, 0).astype(bool, copy=False)

    return PointTrackerRunOutput(
        tracks_xy=tracks_xy,
        visible_mask=visible_mask_np,
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
            raise FileNotFoundError(f"Track-On-R checkpoint not found: {checkpoint_path}")
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
