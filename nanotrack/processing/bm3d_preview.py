from __future__ import annotations

import importlib
from collections.abc import Callable

import numpy as np


def _import_bm3d_module():
    return importlib.import_module("bm3d")


def _sanitize(img: np.ndarray) -> np.ndarray:
    out = np.asarray(img, dtype=np.float32)
    if not np.isfinite(out).all():
        med = float(np.nanmedian(out))
        out = np.where(np.isfinite(out), out, med).astype(np.float32, copy=False)
    return out


def _clamp01_if_needed(img: np.ndarray) -> np.ndarray:
    out = _sanitize(img)
    vmin = float(np.min(out))
    vmax = float(np.max(out))
    if not np.isfinite([vmin, vmax]).all() or vmax <= vmin:
        return np.zeros_like(out, dtype=np.float32)
    if vmax > 1.5 or vmin < -0.5:
        out = (out - vmin) / (vmax - vmin)
    return out.astype(np.float32, copy=False)


def run_bm3d_preview(frame: np.ndarray, sigma_factor: float = 1.0) -> np.ndarray:
    """Run BM3D preview on a single frame using the same heuristic as NaParA."""
    sigma_factor = float(sigma_factor)
    if sigma_factor <= 0:
        raise ValueError("sigma_factor must be positive.")

    image = _clamp01_if_needed(frame)
    mad = np.median(np.abs(image - np.median(image)))
    sigma_psd = mad * 1.4826 * sigma_factor

    bm3d = _import_bm3d_module()
    denoised = bm3d.bm3d(image, sigma_psd=sigma_psd)
    return np.asarray(denoised, dtype=np.float32)


def run_bm3d_batch(
    frames: np.ndarray,
    sigma_factor: float = 1.0,
    *,
    progress_callback: Callable[[int, int], None] | None = None,
) -> np.ndarray:
    """Run BM3D on a full sequence and return cached denoised frames."""
    frames_array = np.asarray(frames)
    if frames_array.ndim != 3:
        raise ValueError("frames must have shape [T, H, W].")
    if frames_array.shape[0] == 0:
        raise ValueError("frames must contain at least one frame.")

    frame_count = int(frames_array.shape[0])
    denoised_frames = []
    for frame_index, frame in enumerate(frames_array):
        denoised_frames.append(run_bm3d_preview(frame, sigma_factor=sigma_factor))
        if progress_callback is not None:
            progress_callback(frame_index + 1, frame_count)

    return np.stack(denoised_frames, axis=0).astype(np.float32, copy=False)
