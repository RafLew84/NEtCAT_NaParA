from __future__ import annotations
import numpy as np
from scipy.ndimage import gaussian_filter, median_filter
from statsmodels.nonparametric.smoothers_lowess import lowess
from skimage.restoration import richardson_lucy, unsupervised_wiener, inpaint, denoise_wavelet, denoise_nl_means, estimate_sigma
from skimage.morphology import rectangle, erosion, dilation, reconstruction, opening, disk
from skimage.feature import canny
from skimage.transform import rotate, probabilistic_hough_line
from skimage.filters import threshold_otsu
from skimage.measure import label, regionprops
from skimage.draw import line as draw_line
from sklearn.linear_model import RANSACRegressor
from typing import Dict, Any, Tuple, Optional
from dataclasses import asdict
from .pipeline_spec import PipelineSpec, HeavyPreprocSpec


import bm3d

# import funkcji z Twoich wcześniejszych modułów:
from .line_tools import ransac_line_baseline, lowess_line_baseline
from .hough_tools import remove_streaks_hough
from .morphrec_tools import _directional_morph_reconstruction
from .leveling_tools import subtract_poly_level
from .pm_tools import anisotropic_diffusion_pm
from .dtv_tools import directional_tv

# --- utils ---
def _as_float32(img: np.ndarray) -> np.ndarray:
    return img.astype(np.float32, copy=False)


# --- kroki pipeline ---
def step_median(img, s):
    return median_filter(img, size=int(s['median_size'])) if s.get('median_filter') else img

def step_level(img, s):
    if not s.get('level_enable'):
        return img
    return subtract_poly_level(img, degree=int(s['level_degree']))

def step_destripe_simple(img, s):
    if not s.get('destripe'):
        return img
    row_medians = np.median(img, axis=1, keepdims=True)
    return img - row_medians

def step_destripe_ransac(img, s):
    if not s.get('destripe_ransac'):
        return img
    return ransac_line_baseline(
        img,
        axis=s.get('ransac_axis','rows'),
        mask=None,
        poly_deg=int(s.get('ransac_poly_deg',1)),
        residual_threshold=float(s.get('ransac_residual',3.0)),
        max_trials=int(s.get('ransac_trials',200)),
    )

def step_lowess(img, s):
    if not s.get('destripe_lowess'):
        return img
    return lowess_line_baseline(
        img,
        axis=s.get('lowess_axis','rows'),
        frac=float(s.get('lowess_frac',0.1)),
        it=int(s.get('lowess_it',1)),
        delta=float(s.get('lowess_delta',0.0)),
    )

def step_hough_streak(img, s):
    if not s.get('hough_streak_enable'):
        return img
    out, _ = remove_streaks_hough(
        img,
        canny_sigma=float(s.get('hough_canny_sigma',1.0)),
        angle_center_deg=float(s.get('hough_angle_center',0.0)),
        angle_tol_deg=float(s.get('hough_angle_tol',5.0)),
        hough_threshold=int(s.get('hough_threshold',10)),
        line_length=int(s.get('hough_line_length',30)),
        line_gap=int(s.get('hough_line_gap',5)),
        mask_width_px=int(s.get('hough_mask_width',3)),
    )
    return out

def step_morphrec_bright(img, s):
    if not s.get('morphrec_bright_enable'):
        return img
    return _directional_morph_reconstruction(
        img,
        length_px=s.get('morphrec_bright_len_px',31),
        width_px=s.get('morphrec_bright_w_px',1),
        angle_deg=s.get('morphrec_bright_angle',0.0),
        mode="open",
        protect_min_area_px=int(s.get('morphrec_protect_min_area_px',0)),
        protect_min_minor_px=int(s.get('morphrec_protect_min_minor_px',0)),
    )

def step_morphrec_dark(img, s):
    if not s.get('morphrec_dark_enable'):
        return img
    return _directional_morph_reconstruction(
        img,
        length_px=s.get('morphrec_dark_len_px',31),
        width_px=s.get('morphrec_dark_w_px',1),
        angle_deg=s.get('morphrec_dark_angle',0.0),
        mode="close",
        protect_min_area_px=int(s.get('morphrec_protect_min_area_px',0)),
        protect_min_minor_px=int(s.get('morphrec_protect_min_minor_px',0)),
    )

def step_deconv(img, s):
    mode = s.get('deconv_mode','none')
    if mode == 'none':
        return img
    y, x = np.mgrid[-5:6, -5:6]
    sx, sy = float(s.get('psf_sigma_x',2.0)), float(s.get('psf_sigma_y',0.5))
    psf = np.exp(-(x**2/(2*sx**2) + y**2/(2*sy**2)))
    psf /= psf.sum()
    if mode == 'richardson_lucy':
        return richardson_lucy(img, psf, num_iter=int(s.get('rl_iter',15)))
    if mode == 'wiener':
        out, _ = unsupervised_wiener(img, psf=psf)
        return out
    return img

def step_wavelet(img, s):
    if not s.get('wavelet_enable'):
        return img
    level = int(s.get('wavelet_level',0)) or None
    return denoise_wavelet(
        img,
        method=s.get('wavelet_method','BayesShrink'),
        mode=s.get('wavelet_mode','soft'),
        wavelet=s.get('wavelet_name','db2'),
        wavelet_levels=level,
        rescale_sigma=bool(s.get('wavelet_rescale_sigma',True)),
        channel_axis=None,
    )

def step_nlm(img, s):
    if not s.get('nlm_enable'):
        return img
    if s.get('nlm_auto_sigma', True):
        sigma = float(estimate_sigma(img, channel_axis=None, average_sigmas=True))
        h = float(s.get('nlm_h_factor',1.0)) * sigma
    else:
        h = float(s.get('nlm_h',0.1))
    return denoise_nl_means(
        img,
        patch_size=int(s.get('nlm_patch_size',7)),
        patch_distance=int(s.get('nlm_patch_distance',15)),
        h=h,
        fast_mode=bool(s.get('nlm_fast',True)),
        channel_axis=None,
        preserve_range=True
    )

def step_pm(img, s):
    if not s.get('pm_enable'):
        return img
    return anisotropic_diffusion_pm(
        img,
        n_iter=int(s.get('pm_n_iter',10)),
        kappa=float(s.get('pm_kappa',20.0)),
        gamma=float(min(float(s.get('pm_gamma',0.15)), 0.25)),
        option=int(s.get('pm_option',1)),
    )

def step_dtv(img, s):
    if not s.get('dtv_enable'):
        return img
    return directional_tv(
        img,
        angle_deg=float(s.get('dtv_angle',0.0)),
        lam_along=float(s.get('dtv_lam_along',0.2)),
        lam_across=float(s.get('dtv_lam_across',0.05)),
        n_iter=int(s.get('dtv_n_iter',50)),
    )

def step_bm3d(img, s):
    if not s.get('denoise_bm3d'):
        return img
    mad = np.median(np.abs(img - np.median(img)))
    sigma_psd = mad * 1.4826 * float(s.get('bm3d_sigma_factor',1.0))
    return bm3d.bm3d(img, sigma_psd=sigma_psd)


# --- rejestr kroków ---
_STEPS = (
    step_median,
    step_level,
    step_destripe_simple,
    step_lowess,
    step_destripe_ransac,
    step_hough_streak,
    step_morphrec_bright,
    step_morphrec_dark,
    step_deconv,
    step_wavelet,
    step_nlm,
    step_pm,
    step_dtv,
    step_bm3d,
)


# --- główna funkcja ---
def run_heavy_preprocessing(image: np.ndarray, spec: Dict[str, Any] | HeavyPreprocSpec) -> np.ndarray:
    if isinstance(spec, HeavyPreprocSpec):
        spec = spec.validate().to_dict()
    im = _as_float32(image.copy())
    for fn in _STEPS:
        im = fn(im, spec)
    return im.astype(image.dtype, copy=False)

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
