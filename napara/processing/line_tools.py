import numpy as np
from sklearn.linear_model import RANSACRegressor
from statsmodels.nonparametric.smoothers_lowess import lowess

def ransac_line_baseline(img, axis='rows', mask=None, poly_deg=1,
                         residual_threshold=3.0, max_trials=200):
    im = img.astype(np.float32, copy=False)
    h, w = im.shape
    n_lines = h if axis == 'rows' else w
    length = w if axis == 'rows' else h
    poly_deg = max(0, min(3, int(poly_deg)))
    if length < max(8, 2*poly_deg+1):
        return im  # za krótkie linie
    out = im.copy()
    Xfull = np.hstack([(np.arange(length, dtype=np.float32)[:, None])**k for k in range(poly_deg+1)])
    for i in range(n_lines):
        line = im[i, :] if axis == 'rows' else im[:, i]
        sel = np.ones_like(line, dtype=bool)
        if mask is not None:
            m = mask[i, :] if axis == 'rows' else mask[:, i]
            sel = ~m.astype(bool)
        if sel.sum() < max(8, 2*poly_deg+1):
            continue
        X = Xfull[sel]
        y = line[sel]
        try:
            model = RANSACRegressor(min_samples=max(8, 2*poly_deg+1),
                                    residual_threshold=float(residual_threshold),
                                    max_trials=int(max_trials))
            model.fit(X, y)
            baseline = model.predict(Xfull).astype(np.float32)
        except Exception:
            baseline = np.poly1d(np.polyfit(np.arange(length), line, deg=min(poly_deg, 1)))(np.arange(length)).astype(np.float32)
        if axis == 'rows':
            out[i, :] = line - baseline
        else:
            out[:, i] = line - baseline
    return out

def lowess_line_baseline(img, axis='rows', frac=0.1, it=1, delta=0.0):
    from statsmodels.nonparametric.smoothers_lowess import lowess
    im = img.astype(np.float32, copy=False)
    h, w = im.shape
    n_lines = h if axis == 'rows' else w
    length = w if axis == 'rows' else h
    frac = float(min(max(frac, 0.01), 0.8))
    out = im.copy()
    x = np.arange(length, dtype=np.float32)
    for i in range(n_lines):
        y = im[i, :] if axis == 'rows' else im[:, i]
        try:
            fit = lowess(y, x, frac=frac, it=int(it), delta=float(delta), return_sorted=False)
        except Exception:
            # fallback: median blur wzdłuż linii
            k = max(3, int(round(frac*length)) | 1)
            fit = np.convolve(y, np.ones(k, dtype=np.float32)/k, mode='same')
        if axis == 'rows':
            out[i, :] = y - fit
        else:
            out[:, i] = y - fit
    return out
