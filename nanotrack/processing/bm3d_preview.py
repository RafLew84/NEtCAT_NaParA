from __future__ import annotations

import importlib

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
