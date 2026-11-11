"""Independent E3 perturbations of already normalized patches, without reclipping.

The caller supplies only historical training windows to fit_gradient(). This
module accepts no labels, paths, model identity or regime. Noise is shared by
all readouts/regimes for the same window ID and resolution; the48/64 noise
fields are intentionally independent diagnostic input perturbations.
"""
from __future__ import annotations

import hashlib
import json

import numpy as np

CONDITIONS = ("identity", "offset_minus", "offset_plus", "gain_minus", "gain_plus",
              "noise", "gradient_x_minus", "gradient_x_plus", "gradient_y_minus",
              "gradient_y_plus")
NOISE_SEED = 20261111
NOISE_SIGMA = .03


def _patches(values) -> np.ndarray:
    values = np.asarray(values)
    if values.ndim != 3 or values.shape[1] != values.shape[2] or values.shape[1] not in (48, 64):
        raise ValueError("Expected N-by-S-by-S patches with S48 or64")
    if values.dtype.kind not in "fiu" or not np.isfinite(values).all():
        raise ValueError("Patches must be finite numeric measurements")
    return values


def transform(patches, condition: str, gradient: float, window_ids) -> np.ndarray:
    """Apply one condition directly to baseline inputs; never mutate or clip.

    Gain means multiplication around zero, matching historical augmentation.
    A gradient has zero mean and a full span2*gradient on pixel endpoints.
    Each noise realization is keyed by (fixed seed, window_id, resolution),
    independent of ordering, chunking, model and regime.
    """
    source = _patches(patches)
    ids = tuple(window_ids)
    if len(ids) != len(source) or any(not isinstance(key, str) or not key for key in ids):
        raise ValueError("One nonempty window ID is required per patch")
    if condition not in CONDITIONS:
        raise ValueError(f"Unknown E3 condition: {condition}")
    if not np.isfinite(gradient) or gradient < 0:
        raise ValueError("Gradient amplitude must be finite and nonnegative")
    result = source.astype(np.float32, copy=True)
    if condition.startswith("offset_"):
        result += np.float32(-.1 if condition.endswith("minus") else .1)
    elif condition.startswith("gain_"):
        result *= np.float32(.9 if condition.endswith("minus") else 1.1)
    elif condition == "noise":
        size = source.shape[1]
        for index, ident in enumerate(ids):
            key = json.dumps([NOISE_SEED, ident, size], ensure_ascii=False, separators=(",", ":"))
            entropy = int.from_bytes(hashlib.sha256(key.encode()).digest()[:16], "little")
            noise = np.random.default_rng(entropy).normal(0., NOISE_SIGMA, (size, size))
            result[index] = (result[index] + noise).astype(np.float32)
    elif condition.startswith("gradient_"):
        axis = np.linspace(-1., 1., source.shape[1], dtype=np.float32)
        pattern = axis[None, :] if condition.startswith("gradient_x_") else axis[:, None]
        sign = -1 if condition.endswith("minus") else 1
        result += np.float32(sign * gradient) * pattern
    if not np.isfinite(result).all():
        raise ValueError("Perturbation overflowed float32 inputs")
    return result


def pixel_stats(base, changed) -> dict[str, np.ndarray]:
    """Per-window statistics, distinguishing old saturation from new excursions."""
    base, changed = _patches(base), _patches(changed)
    if base.shape != changed.shape:
        raise ValueError("Baseline and changed patches must share shape")
    a, b = base.astype(np.float64), changed.astype(np.float64)
    return dict(mean=b.mean((1, 2)), std=b.std((1, 2)),
                baseline_mean=a.mean((1, 2)), baseline_std=a.std((1, 2)),
                input_rmse=np.sqrt(np.mean((b-a)**2, axis=(1, 2))),
                baseline_saturation_fraction=((a <= 0) | (a >= 1)).mean((1, 2)),
                post_outside_fraction=((b < 0) | (b > 1)).mean((1, 2)))


def fit_gradient(patches) -> dict:
    """Calibrate one amplitude from supplied TRAIN patches, not test references.

    Fit p=c+ax*x+ay*y by least squares with x,y in[-1,1]. The plane's
    half-range over that square is |ax|+|ay|. Use its median, clipped to
    [.02,.1]. No baseline/perturbed test image can enter through this API
    unless the caller incorrectly supplies it as training data.
    """
    images = _patches(patches).astype(np.float64)
    if not len(images):
        raise ValueError("Gradient calibration requires training patches")
    axis = np.linspace(-1., 1., images.shape[1])
    axis -= axis.mean()
    variance = np.mean(axis**2)
    centered = images - images.mean((1, 2), keepdims=True)
    ax = np.mean(centered * axis[None, None, :], axis=(1, 2)) / variance
    ay = np.mean(centered * axis[None, :, None], axis=(1, 2)) / variance
    half_range = np.abs(ax) + np.abs(ay)
    levels = (0., .05, .25, .5, .75, .95, 1.)
    values = np.quantile(half_range, levels, method="linear")
    quantiles = dict(zip(("min", "q05", "q25", "q50", "q75", "q95", "max"), values.tolist()))
    return dict(value=float(np.clip(quantiles["q50"], .02, .1)), count=len(images),
                quantiles=quantiles, bounds=[.02, .1], resolution=images.shape[1],
                formula="g=clip(q50(abs(ax)+abs(ay)),0.02,0.1); least-squares plane c+ax*x+ay*y, x/y=linspace(-1,1,S); training windows only")
