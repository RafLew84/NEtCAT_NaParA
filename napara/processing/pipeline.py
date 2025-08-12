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

def anisotropic_diffusion_pm(img: np.ndarray, *, n_iter: int = 10, kappa: float = 20.0,
                             gamma: float = 0.15, option: int = 1) -> np.ndarray:
    """
    Perona–Malik anisotropic diffusion (4-neighbour). 
    Stabilność: 0 < gamma <= 0.25.
    option=1: c(s)=exp(-(s/kappa)^2); option=2: c(s)=1/(1+(s/kappa)^2).
    """
    u = img.astype(np.float32).copy()
    for _ in range(int(n_iter)):
        # różnice kierunkowe
        dn = np.zeros_like(u); ds = np.zeros_like(u); de = np.zeros_like(u); dw = np.zeros_like(u)
        dn[1:, :]  = u[1:, :]  - u[:-1, :]
        ds[:-1, :] = u[:-1, :] - u[1:, :]
        dw[:, 1:]  = u[:, 1:]  - u[:, :-1]
        de[:, :-1] = u[:, :-1] - u[:, 1:]

        if option == 1:
            cn = np.exp(-(dn / kappa) ** 2); cs = np.exp(-(ds / kappa) ** 2)
            cw = np.exp(-(dw / kappa) ** 2); ce = np.exp(-(de / kappa) ** 2)
        else:
            cn = 1.0 / (1.0 + (dn / kappa) ** 2); cs = 1.0 / (1.0 + (ds / kappa) ** 2)
            cw = 1.0 / (1.0 + (dw / kappa) ** 2); ce = 1.0 / (1.0 + (de / kappa) ** 2)

        div = cn * dn + cs * ds + cw * dw + ce * de
        u += gamma * div
    return u.astype(img.dtype)

def lowess_line_baseline(img: np.ndarray, *, axis: str = 'rows',
                         frac: float = 0.1, it: int = 1, delta: float = 0.0) -> np.ndarray:
    """LOWESS per-line baseline subtraction. axis ∈ {'rows','cols'}."""
    h, w = img.shape
    out = img.astype(np.float32).copy()
    n_lines = h if axis == 'rows' else w
    for i in range(n_lines):
        y = img[i, :] if axis == 'rows' else img[:, i]
        x = np.arange(y.size, dtype=np.float32)
        # statsmodels.lowess zwraca Nx2: [x, y_fit]
        fit = lowess(y, x, frac=float(frac), it=int(it), delta=float(delta), return_sorted=True)
        baseline = fit[:, 1].astype(np.float32)
        if axis == 'rows':
            out[i, :] = y - baseline
        else:
            out[:, i] = y - baseline
    return out

def remove_streaks_hough(img: np.ndarray, *,
    canny_sigma: float = 1.0,
    angle_center_deg: float = 0.0,
    angle_tol_deg: float = 5.0,
    hough_threshold: int = 10,
    line_length: int = 30,
    line_gap: int = 5,
    mask_width_px: int = 3
) -> tuple[np.ndarray, np.ndarray]:
    """
    1) krawędzie (Canny) -> 2) Hough probabilistyczny -> 3) maska smug -> 4) inpaint.
    Zwraca (obraz_po, maska).
    """
    # 1) krawędzie
    edges = canny(img.astype(np.float32), sigma=canny_sigma)

    # 2) segmenty linii
    segments = probabilistic_hough_line(edges,
                                        threshold=hough_threshold,
                                        line_length=line_length,
                                        line_gap=line_gap)

    # 3) filtr kątowy i maska
    mask = np.zeros(img.shape, dtype=bool)
    a0 = angle_center_deg
    tol = abs(angle_tol_deg)
    for (x0, y0), (x1, y1) in segments:
        dy = y1 - y0; dx = x1 - x0
        ang = np.degrees(np.arctan2(dy, dx))  # [-180,180], 0° = poziomo
        # najkrótsza odległość kątowa do a0
        d = (ang - a0 + 180.0) % 360.0 - 180.0
        if abs(d) <= tol:
            rr, cc = draw_line(y0, x0, y1, x1)
            rr = np.clip(rr, 0, img.shape[0]-1); cc = np.clip(cc, 0, img.shape[1]-1)
            mask[rr, cc] = True

    if mask.any() and mask_width_px > 1:
        mask = dilation(mask, disk(max(1, mask_width_px // 2)))

    # 4) inpainting (biharmonic)
    if mask.any():
        out = inpaint.inpaint_biharmonic(img.astype(np.float32), mask, channel_axis=None)
        out = out.astype(img.dtype)
    else:
        out = img
    return out, mask

def _tv_chambolle_aniso(u0: np.ndarray, lam_x: float, lam_y: float, n_iter: int = 50) -> np.ndarray:
    """Anizotropowe ROF (Chambolle) z różnymi wagami dla ∂x i ∂y."""
    u0 = u0.astype(np.float32)
    p1 = np.zeros_like(u0); p2 = np.zeros_like(u0)
    tau = 0.25  # stabilne
    lam_x = float(lam_x); lam_y = float(lam_y)
    for _ in range(int(n_iter)):
        # u = f - div(p)
        divp = np.zeros_like(u0)
        divp[:, :-1] += p1[:, :-1]; divp[:, 1:] -= p1[:, :-1]
        divp[:-1, :] += p2[:-1, :]; divp[1:, :] -= p2[:-1, :]
        u = u0 - (divp)

        # grad(u)
        gx = np.zeros_like(u); gy = np.zeros_like(u)
        gx[:, :-1] = u[:, 1:] - u[:, :-1]
        gy[:-1, :] = u[1:, :] - u[:-1, :]

        # aktualizacja dualna z wagami lam_x, lam_y
        px_new = p1 + tau * lam_x * gx
        py_new = p2 + tau * lam_y * gy
        norm = np.maximum(1.0, np.sqrt(px_new**2 + py_new**2))
        p1, p2 = px_new / norm, py_new / norm
    # final u
    divp = np.zeros_like(u0)
    divp[:, :-1] += p1[:, :-1]; divp[:, 1:] -= p1[:, :-1]
    divp[:-1, :] += p2[:-1, :]; divp[1:, :] -= p2[:-1, :]
    u = u0 - (divp)
    return u.astype(u0.dtype)

def subtract_poly_level(img: np.ndarray, degree: int = 1) -> np.ndarray:
    """
    Odejmuje tło dopasowane wielomianem 2D stopnia 0/1/2.
    degree=0: stała, 1: płaszczyzna ax+by+c, 2: + x^2, xy, y^2.
    """
    h, w = img.shape
    y, x = np.mgrid[0:h, 0:w]
    x = x.astype(np.float32).ravel()
    y = y.astype(np.float32).ravel()
    z = img.astype(np.float32).ravel()

    if degree == 0:
        A = np.c_[np.ones_like(x)]
    elif degree == 1:
        A = np.c_[x, y, np.ones_like(x)]
    else:  # degree == 2
        A = np.c_[x*x, x*y, y*y, x, y, np.ones_like(x)]

    coef, *_ = np.linalg.lstsq(A, z, rcond=None)
    if degree == 0:
        bg = (coef[0]).reshape(1, 1) * np.ones((h, w), dtype=np.float32)
    elif degree == 1:
        a, b, c = coef
        bg = (a * np.arange(w)[None, :] + b * np.arange(h)[:, None] + c).astype(np.float32)
    else:
        a, b, c, d, e, f = coef
        X = np.arange(w, dtype=np.float32)[None, :].repeat(h, 0)
        Y = np.arange(h, dtype=np.float32)[:, None].repeat(w, 1)
        bg = (a*X*X + b*X*Y + c*Y*Y + d*X + e*Y + f).astype(np.float32)

    out = img.astype(np.float32) - bg
    return out

def directional_tv(img: np.ndarray, *, angle_deg: float = 0.0,
                   lam_along: float = 0.2, lam_across: float = 0.05,
                   n_iter: int = 50) -> np.ndarray:
    """
    Kierunkowe TV: silniejsze wygładzanie wzdłuż zadanego kierunku (angle_deg).
    Realizacja: obrót -> TV anizotropowe (lam_x=along, lam_y=across) -> odwrót.
    """
    r = rotate(img, -angle_deg, resize=False, preserve_range=True, order=1, mode="edge")
    out_r = _tv_chambolle_aniso(r, lam_x=lam_along, lam_y=lam_across, n_iter=n_iter)
    out = rotate(out_r, angle_deg, resize=False, preserve_range=True, order=1, mode="edge")
    return out.astype(img.dtype)

def run_heavy_preprocessing(image: np.ndarray, spec: Dict[str, Any]) -> np.ndarray:
    processed_image = image.copy().astype(np.float32)

    # Krok 1: Opcjonalny Filtr Medianowy
    if spec.get('median_filter', False):
        size = spec.get('median_size', 3)
        processed_image = median_filter(processed_image, size=size)

    # 1b: Plane/Polynomial leveling
    if spec.get('level_enable', False):
        deg = int(spec.get('level_degree', 1))
        deg = 0 if deg <= 0 else 2 if deg >= 2 else 1
        processed_image = subtract_poly_level(processed_image, degree=deg)

    # Krok 2: Destriping
    if spec.get('destripe', False):
        row_medians = np.median(processed_image, axis=1, keepdims=True)
        processed_image -= row_medians

    # 2a: LOWESS/LOESS line-by-line
    if spec.get('destripe_lowess', False):
        processed_image = lowess_line_baseline(
            processed_image,
            axis=spec.get('lowess_axis', 'rows'),
            frac=float(spec.get('lowess_frac', 0.1)),
            it=int(spec.get('lowess_it', 1)),
            delta=float(spec.get('lowess_delta', 0.0)),
        )
    
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

    # 2e: Hough-guided streak removal (detekcja smug + inpainting)
    if spec.get('hough_streak_enable', False):
        processed_image, _ = remove_streaks_hough(
            processed_image,
            canny_sigma=float(spec.get('hough_canny_sigma', 1.0)),
            angle_center_deg=float(spec.get('hough_angle_center', 0.0)),
            angle_tol_deg=float(spec.get('hough_angle_tol', 5.0)),
            hough_threshold=int(spec.get('hough_threshold', 10)),
            line_length=int(spec.get('hough_line_length', 30)),
            line_gap=int(spec.get('hough_line_gap', 5)),
            mask_width_px=int(spec.get('hough_mask_width', 3)),
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

    # Krok 3.5: Wavelet Shrinkage
    if spec.get('wavelet_enable', False):
        method = spec.get('wavelet_method', 'BayesShrink')
        mode = spec.get('wavelet_mode', 'soft')  # 'soft' | 'hard'
        wavelet = spec.get('wavelet_name', 'db2')
        level = int(spec.get('wavelet_level', 0)) or None  # 0 => auto
        rescale_sigma = bool(spec.get('wavelet_rescale_sigma', True))
        processed_image = denoise_wavelet(
            processed_image.astype(np.float32),
            method=method,
            mode=mode,
            wavelet=wavelet,
            wavelet_levels=level,
            rescale_sigma=rescale_sigma,
            channel_axis=None
        ).astype(processed_image.dtype)

    # Krok 3.6: Non-Local Means (NLM)
    if spec.get('nlm_enable', False):
        # auto-sigma -> h = h_factor * sigma
        if spec.get('nlm_auto_sigma', True):
            sigma = float(estimate_sigma(processed_image, channel_axis=None, average_sigmas=True))
            h = float(spec.get('nlm_h_factor', 1.0)) * sigma
        else:
            h = float(spec.get('nlm_h', 0.1))

        processed_image = denoise_nl_means(
            processed_image.astype(np.float32),
            patch_size=int(spec.get('nlm_patch_size', 7)),
            patch_distance=int(spec.get('nlm_patch_distance', 15)),
            h=h,
            fast_mode=bool(spec.get('nlm_fast', True)),
            channel_axis=None,
            preserve_range=True
        ).astype(processed_image.dtype)

    # Krok 3.7: Anisotropic diffusion (Perona–Malik)
    if spec.get('pm_enable', False):
        processed_image = anisotropic_diffusion_pm(
            processed_image,
            n_iter=int(spec.get('pm_n_iter', 10)),
            kappa=float(spec.get('pm_kappa', 20.0)),
            gamma=float(spec.get('pm_gamma', 0.15)),
            option=int(spec.get('pm_option', 1)),
        )

    # Krok 3.8: Directional / Anisotropic TV
    if spec.get('dtv_enable', False):
        processed_image = directional_tv(
            processed_image,
            angle_deg=float(spec.get('dtv_angle', 0.0)),
            lam_along=float(spec.get('dtv_lam_along', 0.2)),
            lam_across=float(spec.get('dtv_lam_across', 0.05)),
            n_iter=int(spec.get('dtv_n_iter', 50)),
        )

    # Krok 4: Opcjonalne Odszumianie BM3D
    if spec.get('denoise_bm3d', False):
        mad = np.median(np.abs(processed_image - np.median(processed_image)))
        sigma_psd = mad * 1.4826 * spec.get('bm3d_sigma_factor', 1.0)
        processed_image = bm3d.bm3d(processed_image, sigma_psd=sigma_psd)

    return processed_image
