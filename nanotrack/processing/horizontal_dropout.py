from __future__ import annotations

from collections.abc import Callable

import numpy as np
from scipy import ndimage as ndi
from skimage.restoration import inpaint


def _sanitize(img: np.ndarray) -> np.ndarray:
    out = np.asarray(img, dtype=np.float32)
    if not np.isfinite(out).all():
        med = float(np.nanmedian(out))
        out = np.where(np.isfinite(out), out, med).astype(np.float32, copy=False)
    return out


def _validate_params(
    *,
    threshold_sigma: float,
    min_width_frac: float,
    max_width_frac: float,
    max_thickness_px: int,
    gap_closing_px: int,
    repair_mode: str,
) -> None:
    if threshold_sigma <= 0:
        raise ValueError("threshold_sigma must be positive.")
    if not 0 < min_width_frac < 1:
        raise ValueError("min_width_frac must be between 0 and 1.")
    if not 0 < max_width_frac <= 1:
        raise ValueError("max_width_frac must be between 0 and 1.")
    if min_width_frac >= max_width_frac:
        raise ValueError("min_width_frac must be smaller than max_width_frac.")
    if max_thickness_px <= 0:
        raise ValueError("max_thickness_px must be positive.")
    if gap_closing_px < 0:
        raise ValueError("gap_closing_px must be non-negative.")
    if repair_mode not in {"vertical_interp", "inpaint"}:
        raise ValueError("repair_mode must be 'vertical_interp' or 'inpaint'.")


def _vertical_prediction(image: np.ndarray) -> np.ndarray:
    neighbors = []
    for shift in (-2, -1, 1, 2):
        if shift < 0:
            pad = np.repeat(image[:1], abs(shift), axis=0)
            shifted = np.vstack([pad, image[:shift]])
        else:
            pad = np.repeat(image[-1:], shift, axis=0)
            shifted = np.vstack([image[shift:], pad])
        neighbors.append(shifted)
    return np.median(np.stack(neighbors, axis=0), axis=0).astype(np.float32, copy=False)


def _detect_horizontal_dropout_mask(
    image: np.ndarray,
    *,
    threshold_sigma: float,
    min_width_frac: float,
    max_width_frac: float,
    max_thickness_px: int,
    gap_closing_px: int,
) -> np.ndarray:
    prediction = _vertical_prediction(image)
    residual = np.abs(image - prediction)
    median = float(np.median(residual))
    mad = float(np.median(np.abs(residual - median)))
    dynamic_floor = max(float(np.ptp(image)) * 1e-4, 1e-6)
    sigma = max(mad * 1.4826, dynamic_floor)
    threshold = median + threshold_sigma * sigma
    mask = residual > threshold

    if gap_closing_px > 0:
        structure = np.ones((1, max(1, int(gap_closing_px))), dtype=bool)
        mask = ndi.binary_closing(mask, structure=structure)

    labels, count = ndi.label(mask)
    if count == 0:
        return np.zeros_like(mask, dtype=bool)

    h, w = image.shape
    min_width_px = max(1, int(np.ceil(min_width_frac * w)))
    max_width_px = max(min_width_px, int(np.ceil(max_width_frac * w)))

    keep = np.zeros_like(mask, dtype=bool)
    for label in range(1, count + 1):
        ys, xs = np.nonzero(labels == label)
        if ys.size == 0:
            continue
        height = int(ys.max() - ys.min() + 1)
        width = int(xs.max() - xs.min() + 1)
        if height > max_thickness_px + 2:
            continue
        if width < min_width_px or width > max_width_px:
            continue
        if width < height * 1.5:
            continue
        keep[labels == label] = True
    return keep


def _repair_vertical_interp(image: np.ndarray, mask: np.ndarray) -> np.ndarray:
    repaired = np.array(image, copy=True, dtype=np.float32)
    h, w = repaired.shape
    for x in range(w):
        bad_rows = np.flatnonzero(mask[:, x])
        if bad_rows.size == 0:
            continue
        good_rows = np.flatnonzero(~mask[:, x])
        if good_rows.size == 0:
            continue
        repaired[bad_rows, x] = np.interp(bad_rows, good_rows, repaired[good_rows, x]).astype(np.float32)
    return repaired


def run_horizontal_dropout_preview(
    frame: np.ndarray,
    *,
    threshold_sigma: float = 3.0,
    min_width_frac: float = 0.02,
    max_width_frac: float = 0.2,
    max_thickness_px: int = 3,
    gap_closing_px: int = 3,
    repair_mode: str = "vertical_interp",
) -> tuple[np.ndarray, np.ndarray]:
    """Repair local horizontal dropout segments in a single frame."""
    _validate_params(
        threshold_sigma=threshold_sigma,
        min_width_frac=min_width_frac,
        max_width_frac=max_width_frac,
        max_thickness_px=max_thickness_px,
        gap_closing_px=gap_closing_px,
        repair_mode=repair_mode,
    )

    image = _sanitize(frame)
    mask = _detect_horizontal_dropout_mask(
        image,
        threshold_sigma=threshold_sigma,
        min_width_frac=min_width_frac,
        max_width_frac=max_width_frac,
        max_thickness_px=max_thickness_px,
        gap_closing_px=gap_closing_px,
    )

    if not mask.any():
        return image.astype(np.float32, copy=True), mask

    if repair_mode == "vertical_interp":
        repaired = _repair_vertical_interp(image, mask)
    else:
        repaired = inpaint.inpaint_biharmonic(image, mask, channel_axis=None)
    return np.asarray(repaired, dtype=np.float32), mask


def run_horizontal_dropout_batch(
    frames: np.ndarray,
    *,
    threshold_sigma: float = 3.0,
    min_width_frac: float = 0.02,
    max_width_frac: float = 0.2,
    max_thickness_px: int = 3,
    gap_closing_px: int = 3,
    repair_mode: str = "vertical_interp",
    progress_callback: Callable[[int, int], None] | None = None,
) -> np.ndarray:
    """Run horizontal dropout repair on a full sequence."""
    frames_array = np.asarray(frames)
    if frames_array.ndim != 3:
        raise ValueError("frames must have shape [T, H, W].")
    if frames_array.shape[0] == 0:
        raise ValueError("frames must contain at least one frame.")

    frame_count = int(frames_array.shape[0])
    repaired_frames = []
    for frame_index, frame in enumerate(frames_array):
        repaired, _ = run_horizontal_dropout_preview(
            frame,
            threshold_sigma=threshold_sigma,
            min_width_frac=min_width_frac,
            max_width_frac=max_width_frac,
            max_thickness_px=max_thickness_px,
            gap_closing_px=gap_closing_px,
            repair_mode=repair_mode,
        )
        repaired_frames.append(repaired)
        if progress_callback is not None:
            progress_callback(frame_index + 1, frame_count)

    return np.stack(repaired_frames, axis=0).astype(np.float32, copy=False)
