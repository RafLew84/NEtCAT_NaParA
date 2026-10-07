from __future__ import annotations

import importlib
from collections.abc import Callable

import numpy as np

from .results import checked_preprocessing_result


def _import_bm3d_module():
    return importlib.import_module("bm3d")


def _sanitize(img: np.ndarray) -> np.ndarray:
    out = np.array(img, dtype=np.float64, copy=True)
    valid = np.isfinite(out)
    if not valid.all():
        out[~valid] = np.median(out[valid])
    return out


def _normalize(img: np.ndarray) -> tuple[np.ndarray, float, float]:
    out = _sanitize(img)
    vmin = float(np.min(out))
    vmax = float(np.max(out))
    if not np.isfinite([vmin, vmax]).all() or vmax <= vmin:
        return np.zeros_like(out, dtype=np.float32), vmin, 1.0
    if vmax > 1.5 or vmin < -0.5:
        out = (out - vmin) / (vmax - vmin)
        return out.astype(np.float32, copy=False), vmin, vmax - vmin
    return out.astype(np.float32, copy=False), 0.0, 1.0


def run_bm3d_preview(
    frame: np.ndarray, sigma_factor: float = 1.0, *,
    normalization_callback: Callable[[dict[str, float | int | str]], None] | None = None,
) -> np.ndarray:
    """Denoise a working copy and restore the input scale and invalid samples."""
    sigma_factor = float(sigma_factor)
    if not np.isfinite(sigma_factor) or sigma_factor <= 0:
        raise ValueError("sigma_factor must be positive.")

    source = np.asarray(frame, dtype=np.float64)
    if source.ndim != 2 or source.size == 0:
        raise ValueError("frame must be a non-empty 2D array.")
    valid = np.isfinite(source)
    report: dict[str, float | int | str] = {
        "offset": 0.0, "scale": 1.0, "valid_samples": int(np.count_nonzero(valid)),
        "input_dtype": str(np.asarray(frame).dtype), "restoration_dtype": "float64",
    }
    if not valid.any():
        report.update(mode="no_valid_samples", working_dtype="float64")
        if normalization_callback is not None:
            normalization_callback(report)
        return np.full(source.shape, np.nan, dtype=np.float64)
    if np.ptp(source[valid]) == 0:
        report.update(mode="constant", offset=float(source[valid][0]), working_dtype="float64")
        if normalization_callback is not None:
            normalization_callback(report)
        return np.where(valid, source, np.nan)

    image, offset, scale = _normalize(frame)
    mad = np.median(np.abs(image - np.median(image)))
    sigma_psd = mad * 1.4826 * sigma_factor

    bm3d = _import_bm3d_module()
    denoised = checked_preprocessing_result(bm3d.bm3d(image, sigma_psd=sigma_psd), source)
    restored = checked_preprocessing_result(denoised.astype(np.float64) * scale + offset, source)
    report.update(mode="affine" if offset != 0.0 or scale != 1.0 else "identity", offset=offset, scale=scale,
                  sigma_psd=float(sigma_psd), working_dtype=str(image.dtype))
    if normalization_callback is not None:
        normalization_callback(report)
    return restored


def run_bm3d_batch(
    frames: np.ndarray,
    sigma_factor: float = 1.0,
    *,
    progress_callback: Callable[[int, int], None] | None = None,
    normalization_callback: Callable[[int, dict[str, float | int | str]], None] | None = None,
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
        if normalization_callback is None:
            denoised = run_bm3d_preview(frame, sigma_factor=sigma_factor)
        else:
            denoised = run_bm3d_preview(
                frame, sigma_factor=sigma_factor,
                normalization_callback=lambda report: normalization_callback(frame_index, report),
            )
        denoised_frames.append(denoised)
        if progress_callback is not None:
            progress_callback(frame_index + 1, frame_count)

    return np.stack(denoised_frames, axis=0)
