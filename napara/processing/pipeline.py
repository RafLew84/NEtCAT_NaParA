from __future__ import annotations
import numpy as np
from scipy.ndimage import gaussian_filter, median_filter
from skimage.restoration import richardson_lucy, unsupervised_wiener
from typing import Dict, Any, Tuple, Optional
from dataclasses import asdict
from .pipeline_spec import PipelineSpec

import bm3d

# Reuse helpers if masz je w pliku; jeśli nie, wklej te dwa:
def _apply_rect_roi(img: np.ndarray, rect_nm: Tuple[float, float, float, float],
                    nm_per_px: Tuple[Optional[float], Optional[float]]):
    """Extract rectangular ROI in pixel coords from nm-space rect (x,y,w,h in nm)."""
    sx, sy = nm_per_px
    if not (sx and sy and sx > 0 and sy > 0):
        x, y, w, h = rect_nm
        xs, ys, ws, hs = int(round(x)), int(round(y)), int(round(w)), int(round(h))
    else:
        x, y, w, h = rect_nm
        xs = max(0, int(np.floor(x / sx)))
        ys = max(0, int(np.floor(y / sy)))
        ws = max(1, int(np.round(w / sx)))
        hs = max(1, int(np.round(h / sy)))
    xs2 = min(img.shape[1], xs + ws)
    ys2 = min(img.shape[0], ys + hs)
    return (ys, ys2, xs, xs2), img[ys:ys2, xs:xs2]

def _rect_mask_to_full(mask_roi: np.ndarray, roi_slice, full_shape):
    """Place ROI mask back into full image canvas."""
    out = np.zeros(full_shape, dtype=bool)
    y0, y1, x0, x1 = roi_slice
    out[y0:y1, x0:x1] = mask_roi
    return out

def run_pipeline(
    img: np.ndarray,
    *,
    roi_rect_nm: Optional[Tuple[float, float, float, float]],   # (x,y,w,h) in nm; None -> whole image
    nm_per_px: Tuple[Optional[float], Optional[float]],         # (sx, sy) in nm/px
    spec: PipelineSpec,
) -> Dict[str, Any]:
    """
    NO-OP pipeline: returns an all-false mask and no contours.
    This keeps the interface stable while we iterate on visual testing of steps.
    """
    assert img.ndim == 2, "Expect 2D grayscale image"

    # Determine ROI slice (only for debug preview); whole image if ROI is None
    if roi_rect_nm is not None:
        roi_slice, roi_img = _apply_rect_roi(img, roi_rect_nm, nm_per_px)
    else:
        roi_slice = (0, img.shape[0], 0, img.shape[1])
        roi_img = img

    # processed_img = roi_img.copy() # Start with a copy of the ROI data

    # 1. Gaussian Blur
    if spec.gaussian_blur:
        # sigma is in pixels. For now, assume spec.gaussian_sigma is in px.
        roi_img = gaussian_filter(roi_img, sigma=spec.gaussian_sigma)


    final_mask_roi = np.zeros(roi_img.shape, dtype=bool)
    contours: list[np.ndarray] = []
    
    # --- End of Detection Steps ---

    full_mask = _rect_mask_to_full(final_mask_roi, roi_slice, img.shape)

    # Minimal debug payload to help w/ visual checks
    debug = {
        "roi_slice": np.array(roi_slice, dtype=np.int32),
        "roi_preview": roi_img.copy(),
    }

    return {
        "mask": full_mask,
        "contours": contours,
        "debug": debug,
        "spec": asdict(spec),
    }

def run_heavy_preprocessing(image: np.ndarray, spec: Dict[str, Any]) -> np.ndarray:
    processed_image = image.copy().astype(np.float32)

    # Krok 1: Opcjonalny Filtr Medianowy
    if spec.get('median_filter', False):
        size = spec.get('median_size', 3)
        processed_image = median_filter(processed_image, size=size)

    # Krok 2: Destriping
    if spec.get('destripe', False):
        row_medians = np.median(processed_image, axis=1, keepdims=True)
        processed_image -= row_medians

    # Krok 3: Opcjonalna Dekonwolucja
    deconv_mode = spec.get('deconv_mode', 'none')
    y, x = np.mgrid[-5:6, -5:6]
    sx = spec.get('psf_sigma_x', 2.0)
    sy = spec.get('psf_sigma_y', 0.5)
    psf = np.exp(-(x**2 / (2.0 * sx**2) + y**2 / (2.0 * sy**2)))
    psf /= psf.sum()
    if deconv_mode == 'richardson_lucy':
        processed_image = richardson_lucy(processed_image, psf, num_iter=spec.get('rl_iter', 15))
    elif deconv_mode == 'wiener':
        processed_image, _ = unsupervised_wiener(processed_image, psf=psf)

    # Krok 4: Opcjonalne Odszumianie BM3D
    if spec.get('denoise_bm3d', False):
        mad = np.median(np.abs(processed_image - np.median(processed_image)))
        sigma_psd = mad * 1.4826 * spec.get('bm3d_sigma_factor', 1.0)
        processed_image = bm3d.bm3d(processed_image, sigma_psd=sigma_psd)

    return processed_image
