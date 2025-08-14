import numpy as np
def subtract_poly_level(img, degree=1):
    im = img.astype(np.float32, copy=False)
    h, w = im.shape
    if h < 2 or w < 2:
        return im  # za małe
    yy, xx = np.mgrid[0:h, 0:w]
    if degree <= 0:
        bg = np.full_like(im, np.nanmedian(im), dtype=np.float32)
        return im - bg
    if degree == 1:
        A = np.c_[xx.ravel(), yy.ravel(), np.ones(h*w, dtype=np.float32)]
    else:
        A = np.c_[xx.ravel()**2, xx.ravel()*yy.ravel(), yy.ravel()**2, xx.ravel(), yy.ravel(), np.ones(h*w, np.float32)]
    z = im.ravel()
    # guard przed singular
    try:
        coef, *_ = np.linalg.lstsq(A, z, rcond=None)
    except Exception:
        return im
    bg = (A @ coef).reshape(h, w).astype(np.float32)
    if not np.isfinite(bg).all():
        return im
    return im - bg