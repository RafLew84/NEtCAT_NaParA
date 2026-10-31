"""Translate measurement rasters without filling or expanding missing-sample gaps."""

import numpy as np
from numpy.typing import NDArray


def translate_samples(data: NDArray[np.float64], shift_xy: tuple[float, float],
                      output_shape: tuple[int, int]) -> NDArray[np.float64]:
    """Copy lattice samples; interpolate only where all positive weights have data.

    Coordinates outside the original sampling grid remain missing. A missing
    neighbour with zero interpolation weight must not invalidate an exact sample.
    No renormalization or gap filling is performed.
    """
    x, y = shift_xy
    values: NDArray[np.float64]
    if float(x).is_integer() and float(y).is_integer():
        # Also supports the fixed reference field in pair comparison, which clips.
        dx, dy = int(x), int(y)
        x0, y0 = max(0, dx), max(0, dy)
        x1 = min(output_shape[1], dx + data.shape[1])
        y1 = min(output_shape[0], dy + data.shape[0])
        values = np.full(output_shape, np.nan, dtype=np.float64)
        if x0 < x1 and y0 < y1:
            values[y0:y1, x0:x1] = data[y0 - dy:y1 - dy, x0 - dx:x1 - dx]
    else:
        from scipy.ndimage import affine_transform

        finite = np.isfinite(data)
        complete = bool(finite.all())
        # Replacing NaN by zero avoids NaN * 0 contamination; the independent
        # missing-weight transform rejects every positively weighted missing input.
        samples = data if complete else np.where(finite, data, 0.0)
        values = np.asarray(affine_transform(
            samples, matrix=np.eye(2), offset=(-y, -x), output_shape=output_shape,
            order=1, mode='constant', cval=np.nan, prefilter=False,
        ), dtype=np.float64)
        if not complete:
            missing_weight = affine_transform(
                (~finite).astype(np.float64), matrix=np.eye(2), offset=(-y, -x),
                output_shape=output_shape, order=1, mode='constant', cval=1.0, prefilter=False,
            )
            values[missing_weight > 0] = np.nan
    values[~np.isfinite(values)] = np.nan
    return values
