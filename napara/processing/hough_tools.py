import numpy as np
from skimage.feature import canny
from skimage.transform import hough_line, hough_line_peaks
from skimage.restoration import inpaint

def remove_streaks_hough(img, canny_sigma=1.0, angle_center_deg=0.0,
                         angle_tol_deg=5.0, hough_threshold=10,
                         line_length=30, line_gap=5, mask_width_px=3):
    edges = canny(img, sigma=canny_sigma)
    tested_angles = np.deg2rad(np.linspace(angle_center_deg - angle_tol_deg,
                                           angle_center_deg + angle_tol_deg, 360))
    hspace, angles, dists = hough_line(edges, theta=tested_angles)
    accums, angles_peaks, dists_peaks = hough_line_peaks(hspace, angles, dists,
                                                         threshold=hough_threshold)
    mask = np.zeros_like(img, dtype=bool)
    for _, angle, dist in zip(accums, angles_peaks, dists_peaks):
        yy, xx = np.indices(img.shape)
        line_mask = np.abs(xx*np.cos(angle) + yy*np.sin(angle) - dist) < mask_width_px
        mask |= line_mask
    img_filled = inpaint.inpaint_biharmonic(img, mask, channel_axis=None)
    return img_filled, mask
