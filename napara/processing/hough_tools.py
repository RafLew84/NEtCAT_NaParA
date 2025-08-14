import numpy as np
from skimage.feature import canny
from skimage.transform import hough_line, hough_line_peaks
from skimage.restoration import inpaint

def remove_streaks_hough(img, canny_sigma=1.0, angle_center_deg=0.0,
                         angle_tol_deg=5.0, hough_threshold=10,
                         line_length=30, line_gap=5, mask_width_px=3):
    im = img.astype(np.float32, copy=False)
    try:
        edges = canny(im, sigma=canny_sigma)
    except Exception:
        return im, np.zeros_like(im, bool)
    tested_angles = np.deg2rad(np.linspace(angle_center_deg - angle_tol_deg,
                                           angle_center_deg + angle_tol_deg, max(3, int(2*angle_tol_deg)+1)))
    try:
        hspace, angles, dists = hough_line(edges, theta=tested_angles)
        accums, angles_peaks, dists_peaks = hough_line_peaks(hspace, angles, dists,
                                                             threshold=hough_threshold)
    except Exception:
        return im, np.zeros_like(im, bool)
    if accums is None or len(accums) == 0:
        return im, np.zeros_like(im, bool)
    mask = np.zeros_like(im, dtype=bool)
    for angle, dist in zip(angles_peaks, dists_peaks):
        yy, xx = np.indices(im.shape)
        band = np.abs(xx*np.cos(angle) + yy*np.sin(angle) - dist) < max(1, int(mask_width_px))
        mask |= band
    if not mask.any():
        return im, mask
    try:
        out = inpaint.inpaint_biharmonic(im, mask, channel_axis=None)
    except Exception:
        # fallback: średnia z sąsiadów wzdłuż normalnej
        out = im.copy()
        out[mask] = np.nan
        # prosta interpolacja najbliższymi
        from scipy.ndimage import distance_transform_edt
        dist, idx = distance_transform_edt(np.isnan(out), return_indices=True)
        out = out[tuple(idx)]
    return out.astype(np.float32, copy=False), mask
