"""Contrast for estimator copies only; original pixel geometry is never changed."""
import numpy as np
from numpy.typing import NDArray

from stmviewer.correspondence_types import ImagePreparation
from stmviewer.method_parameters import ContrastParameters


def prepare_feature_image(data: NDArray[np.float64], contrast: ContrastParameters, *,
                          uint8: bool) -> tuple[NDArray[np.uint8] | NDArray[np.float32], ImagePreparation]:
    values = np.asarray(data, dtype=np.float64)
    if values.ndim != 2 or min(values.shape) < 1 or not np.isfinite(values).all():
        raise ValueError('Przygotowanie kontrastu wymaga niepustego obrazu 2D bez NaN/Inf.')
    low, high = float(values.min()), float(values.max())
    if contrast.mode == 'percentiles':
        low, high = (float(x) for x in np.percentile(values, [contrast.lower, contrast.upper]))
    if low == high:
        unit = np.zeros(values.shape, dtype=np.float64)
    else:
        scale = max(abs(low), abs(high))
        unit = np.clip((values / scale - low / scale) / (high / scale - low / scale), 0., 1.)
    if contrast.mode == 'clahe' and low != high:
        import cv2
        pixels = np.asarray(np.rint(unit * 255.), dtype=np.uint8)
        pixels = np.asarray(cv2.createCLAHE(clipLimit=contrast.clip_limit,
                                tileGridSize=(contrast.grid_x, contrast.grid_y)).apply(pixels), dtype=np.uint8)
        unit = (pixels.astype(np.float32) / 255.).astype(np.float64)
    normalized = (np.asarray(np.rint(unit * 255.), dtype=np.uint8) if uint8
                  else np.asarray(unit, dtype=np.float32))
    shape = (int(values.shape[0]), int(values.shape[1]))
    return normalized, ImagePreparation(shape, shape, (1., 1.), (0, 0, 0, 0),
                                         (low, high), contrast.normalization(uint8=uint8))
