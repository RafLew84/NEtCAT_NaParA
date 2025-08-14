import numpy as np
from sklearn.linear_model import RANSACRegressor
from statsmodels.nonparametric.smoothers_lowess import lowess

def ransac_line_baseline(img, axis='rows', mask=None, poly_deg=1,
                         residual_threshold=3.0, max_trials=200):
    img = img.astype(np.float32, copy=False)
    out = img.copy()
    n_lines = img.shape[0] if axis == 'rows' else img.shape[1]
    length = img.shape[1] if axis == 'rows' else img.shape[0]

    for i in range(n_lines):
        line = img[i, :] if axis == 'rows' else img[:, i]
        x = np.arange(length)[:, None]
        y = line
        if mask is not None:
            m = mask[i, :] if axis == 'rows' else mask[:, i]
            idx = np.where(m == 0)[0]
            x, y = x[idx], y[idx]
        model = RANSACRegressor(
            min_samples=2, residual_threshold=residual_threshold,
            max_trials=max_trials
        )
        try:
            model.fit(np.hstack([x**p for p in range(1, poly_deg+1)]), y)
            baseline = model.predict(np.hstack([np.arange(length)[:, None]**p for p in range(1, poly_deg+1)]))
        except Exception:
            baseline = np.zeros_like(line)
        if axis == 'rows':
            out[i, :] -= baseline
        else:
            out[:, i] -= baseline
    return out

def lowess_line_baseline(img, axis='rows', frac=0.1, it=1, delta=0.0):
    img = img.astype(np.float32, copy=False)
    out = img.copy()
    n_lines = img.shape[0] if axis == 'rows' else img.shape[1]
    length = img.shape[1] if axis == 'rows' else img.shape[0]

    for i in range(n_lines):
        line = img[i, :] if axis == 'rows' else img[:, i]
        fitted = lowess(line, np.arange(length), frac=frac, it=it, delta=delta, return_sorted=False)
        if axis == 'rows':
            out[i, :] -= fitted
        else:
            out[:, i] -= fitted
    return out
