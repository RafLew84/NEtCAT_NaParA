from __future__ import annotations
import numpy as np
from scipy.ndimage import gaussian_filter, median_filter
from skimage.restoration import richardson_lucy, unsupervised_wiener, inpaint
from skimage.morphology import rectangle, erosion, dilation, reconstruction, opening
from skimage.transform import rotate
from skimage.filters import threshold_otsu
from skimage.measure import label, regionprops
from sklearn.linear_model import RANSACRegressor
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

def remove_horizontal_lines(img, *,
    Lmin=20, Lse=61, Wse=1, angles=(-2,0,2), Wmax_keep=3):
    acc = np.zeros_like(img, dtype=np.float32)
    for a in angles:
        r = rotate(img, -a, resize=False, preserve_range=True, order=1, mode="edge")
        bh = r - reconstruction(erosion(r, rectangle(Wse, Lse)), r, method='dilation')  # bottom-hat
        acc += rotate(bh, a, resize=False, preserve_range=True, order=1, mode="edge")
    thr = threshold_otsu(acc.astype(np.float32))
    cand = acc > thr

    lab = label(cand, connectivity=2)
    keep = np.zeros_like(cand, dtype=bool)
    for reg in regionprops(lab):
        if reg.major_axis_length >= Lmin and reg.minor_axis_length <= Wmax_keep and reg.eccentricity >= 0.98:
            keep[lab == reg.label] = True

    # inpainting
    mask = keep
    out = inpaint.inpaint_biharmonic(img.astype(np.float32), mask, channel_axis=None)
    return out.astype(img.dtype), mask

def _directional_morph_reconstruction(
    img: np.ndarray,
    length_px: int,
    width_px: int,
    angle_deg: float,
    mode: str = "open",
    *,
    protect_min_area_px: int = 0,
    protect_min_minor_px: int = 0
) -> np.ndarray:
    """Directional opening/closing by reconstruction with rectangular SE,
    with optional restoration of removed large/thick objects."""
    rot = rotate(img, -angle_deg, resize=False, preserve_range=True, order=1, mode="edge")

    L = max(3, int(length_px) | 1)
    W = max(1, int(width_px))
    se = rectangle(W, L)

    if mode == "open":   # remove bright lines
        seed = erosion(rot, se)
        rec  = reconstruction(seed, rot, method='dilation')
        removed = (rot - rec)  # positive where bright content got removed
    else:                # "close" -> remove dark lines
        seed = dilation(rot, se)
        rec  = reconstruction(seed, rot, method='erosion')
        removed = (rec - rot)  # positive where dark deficits got filled

    out_rot = rec

    # Ochrona obiektów większych/grubszych
    if (protect_min_area_px > 0) or (protect_min_minor_px > 0):
        # Bierzemy tylko wartości dodatnie (rzeczywiście „usunięte”)
        pos = removed > 0
        if np.any(pos):
            rem_vals = removed[pos].astype(np.float32)
            # bezpieczne Otsu: jeśli jednolite, ustaw próg minimalny
            thr = threshold_otsu(rem_vals) if rem_vals.size >= 64 else float(rem_vals.mean() if rem_vals.size else 0.0)
            cand = np.zeros_like(pos, dtype=bool)
            cand[pos] = removed[pos] > max(thr, 0.0)

            lab = label(cand, connectivity=2)
            if lab.max() > 0:
                restore = np.zeros_like(cand, dtype=bool)
                for r in regionprops(lab):
                    too_big = (r.area >= protect_min_area_px) if protect_min_area_px > 0 else False
                    too_thick = (getattr(r, "minor_axis_length", 0.0) >= protect_min_minor_px) if protect_min_minor_px > 0 else False
                    if too_big or too_thick:
                        restore[lab == r.label] = True

                # Przywracamy piksele z oryginału w zaznaczonych komponentach
                out_rot[restore] = rot[restore]

    out = rotate(out_rot, angle_deg, resize=False, preserve_range=True, order=1, mode="edge")
    return out.astype(img.dtype)

def ransac_line_baseline(img: np.ndarray, axis: str = 'rows', mask: np.ndarray | None = None,
                         poly_deg: int = 1, residual_threshold: float = 3.0, max_trials: int = 200) -> np.ndarray:
    """Robust per-line baseline subtraction using RANSAC. axis: 'rows' or 'cols'."""
    h, w = img.shape
    out = img.astype(np.float32).copy()
    n_lines = h if axis == 'rows' else w

    for i in range(n_lines):
        line = img[i, :] if axis == 'rows' else img[:, i]
        x = np.arange(line.size).astype(np.float32).reshape(-1, 1)

        if mask is not None:
            m = mask[i, :] if axis == 'rows' else mask[:, i]
            sel = ~m.astype(bool)
        else:
            sel = np.ones_like(line, dtype=bool)

        if sel.sum() < max(8, 2 * poly_deg + 1):
            continue

        # Polynomial design matrix
        X = np.hstack([x ** k for k in range(poly_deg + 1)])[sel]
        y = line[sel]

        try:
            model = RANSACRegressor(
                min_samples=max(8, 2 * poly_deg + 1),
                residual_threshold=residual_threshold,
                max_trials=max_trials
            )
            model.fit(X, y)
            Xfull = np.hstack([x ** k for k in range(poly_deg + 1)])
            baseline = model.predict(Xfull).astype(np.float32)
            if axis == 'rows':
                out[i, :] = line - baseline
            else:
                out[:, i] = line - baseline
        except Exception:
            # fall back: skip this line on failure
            pass

    return out

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
    
    if spec.get('destripe_ransac', False):
        processed_image = ransac_line_baseline(
            processed_image,
            axis=spec.get('ransac_axis', 'rows'),
            mask=None,  # opcjonalnie: tu można wpiąć maskę tła
            poly_deg=int(spec.get('ransac_poly_deg', 1)),
            residual_threshold=float(spec.get('ransac_residual', 3.0)),
            max_trials=int(spec.get('ransac_trials', 200))
        )

    if spec.get('remove_hlines', False):
        processed_image, hmask = remove_horizontal_lines(
            processed_image,
            Lmin=spec.get('hl_Lmin', 20),
            Lse=spec.get('hl_Lse', 61),
            Wse=spec.get('hl_Wse', 1),
            angles=spec.get('hl_angles', (-2,0,2)),
            Wmax_keep=spec.get('hl_Wmax_keep', 3),
        )
    
    # 2.5A: Morph. Recon – bright lines (opening)
    if spec.get('morphrec_bright_enable', False):
        processed_image = _directional_morph_reconstruction(
            processed_image,
            length_px=spec.get('morphrec_bright_len_px', 31),
            width_px=spec.get('morphrec_bright_w_px', 1),
            angle_deg=spec.get('morphrec_bright_angle', 0.0),
            mode="open",
            protect_min_area_px=int(spec.get('morphrec_protect_min_area_px', 0)),
            protect_min_minor_px=int(spec.get('morphrec_protect_min_minor_px', 0)),
        )

    # 2.5B: Morph. Recon – dark lines (closing)
    if spec.get('morphrec_dark_enable', False):
        processed_image = _directional_morph_reconstruction(
            processed_image,
            length_px=spec.get('morphrec_dark_len_px', 31),
            width_px=spec.get('morphrec_dark_w_px', 1),
            angle_deg=spec.get('morphrec_dark_angle', 0.0),
            mode="close",
            protect_min_area_px=int(spec.get('morphrec_protect_min_area_px', 0)),
            protect_min_minor_px=int(spec.get('morphrec_protect_min_minor_px', 0)),
        )

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
