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
    from scipy.ndimage import affine_transform

    x, y = shift_xy
    values: NDArray[np.float64]
    if float(x).is_integer() and float(y).is_integer():
        # At lattice coordinates order=0 transports the exact sample and its gap.
        values = np.asarray(affine_transform(
            data, matrix=np.eye(2), offset=(-y, -x), output_shape=output_shape,
            order=0, mode='constant', cval=np.nan, prefilter=False,
        ), dtype=np.float64)
    else:
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
