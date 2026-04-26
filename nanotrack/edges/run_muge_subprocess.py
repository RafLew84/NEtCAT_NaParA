#!/usr/bin/env python3
"""Run real MuGE inference for NanoTrack in a dedicated interpreter."""

from __future__ import annotations

import argparse
import importlib
from pathlib import Path
from types import SimpleNamespace
import sys
from typing import Iterable

import numpy as np

if __package__ in (None, ""):
    REPO_ROOT = Path(__file__).resolve().parents[2]
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from nanotrack.edges.contract import DexiNedRunInput, DexiNedRunOutput
else:
    from .contract import DexiNedRunInput, DexiNedRunOutput


DEFAULT_GRANULARITY = 0.5


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="NanoTrack MuGE subprocess worker.")
    parser.add_argument("--input-npz", required=True, help="Input NPZ produced by NanoTrack.")
    parser.add_argument("--output-npz", required=True, help="Output NPZ path.")
    parser.add_argument("--checkpoint", required=True, help="Path to a MuGE checkpoint.")
    parser.add_argument("--repo-path", default=None, help="Optional path to the local UAED_MuGE repo.")
    parser.add_argument("--device", default="auto", help="Torch device, e.g. auto, cuda, cuda:0, cpu.")
    parser.add_argument("--distribution", default="gs", help="MuGE output distribution mode.")
    parser.add_argument(
        "--granularity",
        default=str(DEFAULT_GRANULARITY),
        help="MuGE alpha/label_style in [0, 1]. Lower is more conservative, higher is denser.",
    )
    return parser.parse_args()


def _load_input(path: Path) -> DexiNedRunInput:
    with np.load(path, allow_pickle=False) as payload:
        input_payload = {key: payload[key] for key in payload.files}
    return DexiNedRunInput.from_npz_payload(input_payload)


def _resolve_repo_root(repo_path: str | Path | None) -> Path:
    if repo_path is None:
        candidate = Path.cwd()
    else:
        candidate = Path(repo_path).expanduser()
    candidate = candidate.resolve()
    model_path = candidate / "model" / "sigma_logit_unetpp_alpha_ffthalf_feat.py"
    if not model_path.exists():
        raise FileNotFoundError(
            f"MuGE repo does not contain model/sigma_logit_unetpp_alpha_ffthalf_feat.py: {model_path}"
        )
    return candidate


def _resolve_granularity(value: str | float | int | None) -> float:
    if value is None:
        return DEFAULT_GRANULARITY
    value_text = str(value).strip().lower()
    if value_text in {"", "default", "medium", "mid"}:
        return DEFAULT_GRANULARITY
    if value_text in {"coarse", "low"}:
        return 0.0
    if value_text in {"fine", "high"}:
        return 1.0
    granularity = float(value_text)
    if not np.isfinite(granularity) or not 0.0 <= granularity <= 1.0:
        raise ValueError("MuGE granularity must be within [0, 1].")
    return granularity


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


def _torch_load_state(torch_module, checkpoint_path: Path, *, map_location):
    try:
        return torch_module.load(checkpoint_path, map_location=map_location, weights_only=True)
    except Exception:
        return torch_module.load(checkpoint_path, map_location=map_location)


def _strip_module_prefix(state_dict: dict) -> dict:
    stripped = {}
    for key, value in state_dict.items():
        normalized_key = key[7:] if str(key).startswith("module.") else key
        stripped[normalized_key] = value
    return stripped


def _extract_state_dict(torch_module, checkpoint_path: Path) -> dict:
    checkpoint = _torch_load_state(torch_module, checkpoint_path, map_location="cpu")
    if isinstance(checkpoint, dict) and "state_dict" in checkpoint:
        checkpoint = checkpoint["state_dict"]
    if not isinstance(checkpoint, dict):
        raise TypeError("MuGE checkpoint must contain a state_dict mapping.")
    return _strip_module_prefix(dict(checkpoint))


def _load_muge_model_class(repo_root: Path):
    sys.path.insert(0, str(repo_root))
    try:
        module = importlib.import_module("model.sigma_logit_unetpp_alpha_ffthalf_feat")
    finally:
        if sys.path and sys.path[0] == str(repo_root):
            sys.path.pop(0)
    if not hasattr(module, "Mymodel"):
        raise ImportError(
            f"Mymodel class not found in {repo_root / 'model' / 'sigma_logit_unetpp_alpha_ffthalf_feat.py'}"
        )
    return module.Mymodel


def _load_model(
    repo_root: Path,
    checkpoint_path: Path,
    requested_device: str,
    *,
    distribution: str,
):
    torch_module = _load_torch()
    device = _resolve_torch_device(torch_module, requested_device)
    _configure_cuda_runtime(torch_module, device)

    Mymodel = _load_muge_model_class(repo_root)
    model_args = SimpleNamespace(distribution=str(distribution))
    model = Mymodel(model_args, encoder_weights=None).to(device)
    model.load_state_dict(_extract_state_dict(torch_module, checkpoint_path))
    model.eval()
    return model, torch_module, device


def _resolve_polygon_bbox(polygon_mask: np.ndarray) -> tuple[int, int, int, int]:
    ys, xs = np.nonzero(np.asarray(polygon_mask, dtype=bool))
    if ys.size == 0 or xs.size == 0:
        raise ValueError("polygon_mask must contain at least one True pixel.")
    y0 = int(np.min(ys))
    y1 = int(np.max(ys)) + 1
    x0 = int(np.min(xs))
    x1 = int(np.max(xs)) + 1
    return y0, y1, x0, x1


def _round_up_to_multiple(value: int, divisor: int) -> int:
    return max(divisor, ((int(value) + divisor - 1) // divisor) * divisor)


def _resolve_inference_shape(
    source_hw: tuple[int, int],
    inference_resolution_hw: np.ndarray | None,
) -> tuple[int, int]:
    if inference_resolution_hw is not None:
        resolution = np.asarray(inference_resolution_hw, dtype=np.int32)
        if resolution.shape != (2,):
            raise ValueError("inference_resolution_hw must have shape [2].")
        return int(resolution[0]), int(resolution[1])
    height, width = source_hw
    return _round_up_to_multiple(height, 32), _round_up_to_multiple(width, 32)


def _normalize_to_uint8(frame: np.ndarray) -> np.ndarray:
    frame_f32 = np.asarray(frame, dtype=np.float32)
    finite_mask = np.isfinite(frame_f32)
    if not np.any(finite_mask):
        return np.zeros(frame_f32.shape, dtype=np.uint8)
    finite_values = frame_f32[finite_mask]
    value_min = float(np.min(finite_values))
    value_max = float(np.max(finite_values))
    if value_max <= value_min + 1e-8:
        return np.zeros(frame_f32.shape, dtype=np.uint8)
    normalized = np.clip((frame_f32 - value_min) / (value_max - value_min), 0.0, 1.0)
    return np.asarray(np.round(normalized * 255.0), dtype=np.uint8)


def _frame_to_rgb_uint8(frame: np.ndarray) -> np.ndarray:
    frame_np = np.asarray(frame)
    if frame_np.ndim == 2:
        gray = _normalize_to_uint8(frame_np)
        return np.repeat(gray[:, :, None], 3, axis=2)
    if frame_np.ndim != 3:
        raise ValueError("frame must have shape [H, W] or [H, W, C].")

    if frame_np.shape[-1] == 1:
        gray = _normalize_to_uint8(frame_np[..., 0])
        return np.repeat(gray[:, :, None], 3, axis=2)

    channels: list[np.ndarray] = []
    for channel_idx in range(3):
        channels.append(_normalize_to_uint8(frame_np[..., channel_idx]))
    return np.stack(channels, axis=2)


def _resize_image(image: np.ndarray, target_hw: tuple[int, int]) -> np.ndarray:
    target_height, target_width = target_hw
    try:
        import cv2

        return cv2.resize(image, (target_width, target_height), interpolation=cv2.INTER_LINEAR)
    except ModuleNotFoundError:
        from PIL import Image

        pil_image = Image.fromarray(np.asarray(image, dtype=np.uint8))
        resized = pil_image.resize((target_width, target_height), resample=Image.BILINEAR)
        return np.asarray(resized)


def _prepare_frame_tensor(
    frame: np.ndarray,
    *,
    polygon_bbox: tuple[int, int, int, int],
    inference_resolution_hw: np.ndarray | None,
) -> tuple[np.ndarray, tuple[int, int], tuple[int, int]]:
    y0, y1, x0, x1 = polygon_bbox
    rgb_frame = _frame_to_rgb_uint8(frame)
    crop_rgb = rgb_frame[y0:y1, x0:x1]
    source_hw = crop_rgb.shape[:2]
    target_hw = _resolve_inference_shape(source_hw, inference_resolution_hw)
    if target_hw != source_hw:
        crop_rgb = _resize_image(crop_rgb, target_hw)
    chw = np.transpose(np.asarray(crop_rgb, dtype=np.float32), (2, 0, 1)) / 255.0
    return chw.astype(np.float32, copy=False), source_hw, target_hw


def _resize_prob_map(edge_prob: np.ndarray, target_hw: tuple[int, int]) -> np.ndarray:
    target_height, target_width = target_hw
    try:
        import cv2

        resized = cv2.resize(edge_prob, (target_width, target_height), interpolation=cv2.INTER_LINEAR)
        return np.asarray(resized, dtype=np.float32)
    except ModuleNotFoundError:
        from PIL import Image

        normalized = np.clip(np.asarray(edge_prob, dtype=np.float32), 0.0, 1.0)
        pil_image = Image.fromarray(np.asarray(np.round(normalized * 255.0), dtype=np.uint8))
        resized = pil_image.resize((target_width, target_height), resample=Image.BILINEAR)
        return np.asarray(resized, dtype=np.float32) / 255.0


def _clip_prob_map(edge_prob: np.ndarray) -> np.ndarray:
    edge_f32 = np.asarray(edge_prob, dtype=np.float32)
    return np.clip(edge_f32, 0.0, 1.0).astype(np.float32, copy=False)


def _run_model_on_tensor(
    model,
    torch_module,
    device,
    chw_frame: np.ndarray,
    *,
    granularity: float,
) -> np.ndarray:
    input_tensor = torch_module.from_numpy(chw_frame[None, ...].copy()).float().to(device)
    label_bias = torch_module.full((1,), float(granularity), device=device)
    with torch_module.no_grad():
        mean, _std = model(input_tensor, label_bias)
        edge_tensor = torch_module.sigmoid(mean[0, 0])
    edge_prob = edge_tensor.detach().cpu().numpy().astype(np.float32, copy=False)
    return _clip_prob_map(edge_prob)


def _iter_frames(frames: np.ndarray) -> Iterable[np.ndarray]:
    frames_np = np.asarray(frames)
    if frames_np.ndim == 3:
        for frame in frames_np:
            yield frame
        return
    if frames_np.ndim == 4:
        for frame in frames_np:
            yield frame
        return
    raise ValueError("frames must have shape [T, H, W] or [T, H, W, C].")


def _run_real_inference(
    run_input: DexiNedRunInput,
    *,
    checkpoint_path: Path,
    repo_root: Path,
    requested_device: str,
    distribution: str,
    granularity: float,
) -> DexiNedRunOutput:
    model, torch_module, device = _load_model(
        repo_root,
        checkpoint_path,
        requested_device,
        distribution=distribution,
    )
    polygon_mask = np.asarray(run_input.polygon_mask, dtype=bool)
    polygon_bbox = _resolve_polygon_bbox(polygon_mask)
    y0, y1, x0, x1 = polygon_bbox

    frame_probs: list[np.ndarray] = []
    for frame in _iter_frames(run_input.frames):
        chw_frame, source_hw, _ = _prepare_frame_tensor(
            frame,
            polygon_bbox=polygon_bbox,
            inference_resolution_hw=run_input.inference_resolution_hw,
        )
        edge_prob_crop = _run_model_on_tensor(
            model,
            torch_module,
            device,
            chw_frame,
            granularity=granularity,
        )
        if edge_prob_crop.shape != source_hw:
            edge_prob_crop = _resize_prob_map(edge_prob_crop, source_hw)

        edge_prob_frame = np.zeros(polygon_mask.shape, dtype=np.float32)
        edge_prob_frame[y0:y1, x0:x1] = edge_prob_crop
        edge_prob_frame *= polygon_mask.astype(np.float32, copy=False)
        frame_probs.append(_clip_prob_map(edge_prob_frame))

    edge_prob = np.stack(frame_probs, axis=0)
    effective_threshold = 0.5 if run_input.threshold is None else float(run_input.threshold)
    edge_binary = edge_prob >= effective_threshold

    if str(device).startswith("cuda") and getattr(torch_module, "cuda", None):
        try:
            torch_module.cuda.empty_cache()
        except Exception:
            pass

    return DexiNedRunOutput(
        edge_prob=edge_prob.astype(np.float32, copy=False),
        edge_binary=edge_binary,
        model_name="muge",
        checkpoint_name=checkpoint_path.name,
    )


def main() -> int:
    args = _parse_args()
    run_input = _load_input(Path(args.input_npz))
    checkpoint_path = Path(args.checkpoint).expanduser().resolve()
    repo_root = _resolve_repo_root(args.repo_path)
    granularity = _resolve_granularity(args.granularity)
    run_output = _run_real_inference(
        run_input,
        checkpoint_path=checkpoint_path,
        repo_root=repo_root,
        requested_device=args.device,
        distribution=args.distribution,
        granularity=granularity,
    )
    Path(args.output_npz).parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(args.output_npz, **run_output.to_npz_payload())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
