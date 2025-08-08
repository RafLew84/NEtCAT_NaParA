from __future__ import annotations
import numpy as np
from typing import Dict, Any, Tuple, Optional
from dataclasses import asdict

from .pipeline_spec import PipelineSpec
from skimage import filters, morphology, exposure, feature, measure, restoration, util
from scipy import ndimage as ndi

# Optional BM3D support
try:
    from bm3d import bm3d as bm3d_denoise
    _HAS_BM3D = True
except Exception:
    _HAS_BM3D = False


# --------- helpers ---------
def _mad_sigma(img: np.ndarray) -> float:
    """Estimate noise sigma using MAD on high-frequency residual."""
    # high-pass via small median filter
    resid = img - ndi.median_filter(img, size=3)
    mad = np.median(np.abs(resid - np.median(resid)))
    return 1.4826 * mad if mad > 0 else float(np.std(resid))


def _nm_to_px(length_nm: float, nm_per_px: float) -> int:
    """Convert physical length (nm) to nearest odd pixel size for structuring elements."""
    if nm_per_px is None or nm_per_px <= 0:
        return 1
    px = max(1, int(round(length_nm / nm_per_px)))
    # force odd for symmetric SE
    return px if px % 2 == 1 else px + 1


def _disk_or_square(radius_px: int):
    """Choose disk if radius≥2, otherwise tiny square to avoid zero-size structuring element."""
    if radius_px <= 1:
        return morphology.square(3)
    return morphology.disk(radius_px)


def _apply_rect_roi(img: np.ndarray, rect_nm: Tuple[float, float, float, float], nm_per_px: Tuple[Optional[float], Optional[float]]):
    """Extract rectangular ROI in pixel coords from nm-space rect (x,y,w,h in nm)."""
    sx, sy = nm_per_px
    if not (sx and sy and sx > 0 and sy > 0):
        # Fall back: treat rect as pixel units
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


def _destripe_rows_median(img: np.ndarray) -> np.ndarray:
    """Row-wise median subtraction."""
    row_med = np.median(img, axis=1, keepdims=True)
    return img - row_med


def _destripe_rows_poly(img: np.ndarray, deg: int = 1) -> np.ndarray:
    """Row-wise polynomial fit subtraction."""
    x = np.arange(img.shape[1], dtype=np.float64)
    out = np.empty_like(img, dtype=np.float64)
    for r in range(img.shape[0]):
        coeff = np.polyfit(x, img[r, :], deg=max(1, int(deg)))
        trend = np.polyval(coeff, x)
        out[r, :] = img[r, :] - trend
    return out


# --------- main pipeline ---------
def run_pipeline(
    img: np.ndarray,
    *,
    roi_rect_nm: Optional[Tuple[float, float, float, float]],   # (x,y,w,h) in nm; None -> whole image
    nm_per_px: Tuple[Optional[float], Optional[float]],         # (sx, sy) in nm/px
    spec: PipelineSpec,
) -> Dict[str, Any]:
    """
    Execute deterministic ROI processing pipeline and return mask/contours + debug steps.

    Returns:
        dict with keys:
          - "mask": bool ndarray in full image space
          - "contours": list of Nx2 float arrays in full image pixel coords
          - "debug": dict of intermediate arrays (ROI-space small copies)
    """
    assert img.ndim == 2, "Expect 2D grayscale image"
    sx, sy = nm_per_px

    # 0) ROI crop
    if roi_rect_nm is not None:
        roi_slice, work = _apply_rect_roi(img, roi_rect_nm, nm_per_px)
    else:
        roi_slice = (0, img.shape[0], 0, img.shape[1])
        work = img

    debug: Dict[str, np.ndarray] = {}

    # 1) Destriping
    if spec.destripe_median_rows:
        work = _destripe_rows_median(work)
        debug["destripe_median"] = work.copy()
    if spec.destripe_poly_rows:
        work = _destripe_rows_poly(work, spec.destripe_poly_deg)
        debug["destripe_poly"] = work.copy()

    # 2) Background / leveling
    if spec.plane_leveling:
        # simple plane via least squares on grid
        yy, xx = np.mgrid[0:work.shape[0], 0:work.shape[1]]
        A = np.c_[xx.ravel(), yy.ravel(), np.ones(work.size)]
        c, *_ = np.linalg.lstsq(A, work.ravel(), rcond=None)
        plane = (c[0] * xx + c[1] * yy + c[2])
        work = work - plane
        debug["plane_level"] = work.copy()

    if spec.white_tophat:
        # radius in px from nm; use sx~sy (prefer x if both available)
        nmpp = sx if sx else (sy if sy else None)
        radius_px = _nm_to_px(spec.wth_radius_nm, nmpp) if nmpp else max(3, spec.sauvola_window_px // 2)
        selem = _disk_or_square(radius_px)
        work = morphology.white_tophat(work, footprint=selem)
        debug["white_tophat"] = work.copy()

    # 3) Denoising (choose one)
    if spec.denoise != "off":
        sigma = _mad_sigma(work)
        if spec.denoise == "nlm":
            # skimage denoise_nl_means expects image in [0,1] for fast mode
            w = work.astype(np.float32)
            w = (w - np.percentile(w, 1)) / (np.percentile(w, 99) - np.percentile(w, 1) + 1e-12)
            w = np.clip(w, 0, 1)
            patch_kw = dict(patch_size=spec.nlm_patch_size,
                            patch_distance=spec.nlm_patch_distance,
                            fast_mode=True)
            h = spec.nlm_h_factor * sigma
            w = restoration.denoise_nl_means(w, h=h, channel_axis=None, **patch_kw)
            # re-contrast back to original scale
            work = w.astype(np.float32)
            debug["nlm"] = work.copy()

        elif spec.denoise == "bm3d" and _HAS_BM3D:
            w = work.astype(np.float32)
            w = (w - np.percentile(w, 1)) / (np.percentile(w, 99) - np.percentile(w, 1) + 1e-12)
            w = np.clip(w, 0, 1)
            work = bm3d_denoise(w, sigma_psd=spec.bm3d_sigma_factor * sigma).astype(np.float32)
            debug["bm3d"] = work.copy()

        elif spec.denoise == "wavelet":
            work = restoration.denoise_wavelet(work, rescale_sigma=True, channel_axis=None)
            debug["wavelet"] = work.copy()

    # 4) Contrast normalization
    if spec.clahe:
        # CLAHE expects uint/img in [0..1]; use skimage exposure.equalize_adapthist
        w = work.astype(np.float32)
        w = (w - np.percentile(w, 2)) / (np.percentile(w, 98) - np.percentile(w, 2) + 1e-12)
        w = np.clip(w, 0, 1)
        work = exposure.equalize_adapthist(w, kernel_size=spec.clahe_tile_px, clip_limit=spec.clahe_clip_limit)
        debug["clahe"] = work.copy()

    # 5) Segmentation (choose path)
    if spec.thresh_mode == "sauvola":
        win = max(5, int(spec.sauvola_window_px))
        thr = filters.threshold_sauvola(work, window_size=win, k=spec.sauvola_k)
        mask = work > thr

    elif spec.thresh_mode == "otsu":
        thr = filters.threshold_otsu(work)
        mask = work > thr

    elif spec.thresh_mode == "yen":
        thr = filters.threshold_yen(work)
        mask = work > thr

    elif spec.thresh_mode == "isodata":
        thr = filters.threshold_isodata(work)
        mask = work > thr

    elif spec.thresh_mode == "canny":
        # edge → contours → fill
        # thresholds from percentiles of gradient magnitude
        edges = feature.canny(work, sigma=spec.canny_sigma)
        debug["canny"] = edges.astype(np.uint8)
        # fill edges using binary_fill_holes on labeled contours
        mask = ndi.binary_fill_holes(edges)

    else:
        raise ValueError(f"Unsupported thresh_mode: {spec.thresh_mode}")

    debug["mask_raw"] = mask.astype(np.uint8)

    # 6) Morphological cleanup
    if spec.morph_open_px and spec.morph_open_px > 0:
        mask = morphology.opening(mask, morphology.disk(int(spec.morph_open_px)))
    if spec.morph_close_px and spec.morph_close_px > 0:
        mask = morphology.closing(mask, morphology.disk(int(spec.morph_close_px)))
    if spec.remove_small_holes_px and spec.remove_small_holes_px > 0:
        mask = morphology.remove_small_holes(mask, area_threshold=int(spec.remove_small_holes_px))
    # Remove very small objects by area in nm^2 if we know scaling
    if spec.remove_small_area_nm2 and sx and sy and sx > 0 and sy > 0:
        pix_nm2 = sx * sy
        thr_px = max(1, int(round(spec.remove_small_area_nm2 / pix_nm2)))
        mask = morphology.remove_small_objects(mask, min_size=thr_px)

    debug["mask_clean"] = mask.astype(np.uint8)

    # 7) (Optional) watershed to split touching blobs
    if spec.watershed:
        dist = ndi.distance_transform_edt(mask)
        local_max = feature.peak_local_max(dist, indices=False, footprint=np.ones((3, 3)))
        markers = ndi.label(local_max)[0]
        labels = morphology.watershed(-dist, markers, mask=mask)
        mask = labels > 0
        debug["watershed"] = labels.astype(np.int32)

    # 8) Final size filter (nm^2)
    if (spec.min_area_nm2 or spec.max_area_nm2) and sx and sy and sx > 0 and sy > 0:
        pix_nm2 = sx * sy
        min_px = int(np.floor((spec.min_area_nm2 or 0) / pix_nm2))
        max_px = int(np.ceil((spec.max_area_nm2 or np.inf) / pix_nm2))
        labeled = measure.label(mask)
        props = measure.regionprops(labeled)
        keep = np.zeros_like(mask, dtype=bool)
        for p in props:
            if (min_px <= p.area <= max_px):
                keep[labeled == p.label] = True
        mask = keep
        debug["mask_sized"] = mask.astype(np.uint8)

    # Bring mask back to full image coords
    full_mask = _rect_mask_to_full(mask, roi_slice, img.shape)

    # Extract contours (full-image pixel coords)
    contours = []
    for c in measure.find_contours(full_mask.astype(np.uint8), 0.5):
        # c is in (row, col) -> (y, x)
        contours.append(np.fliplr(c))  # to (x, y)

    return {
        "mask": full_mask,
        "contours": contours,
        "debug": debug,
        "spec": asdict(spec),
    }
