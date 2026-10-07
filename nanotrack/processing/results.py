"""Validation before a same-grid preprocessing result becomes active."""

import numpy as np


def checked_preprocessing_result(result: np.ndarray, source: np.ndarray) -> np.ndarray:
    """Own the returned buffer and preserve the input's invalid-sample mask."""
    frames = np.asarray(result)
    if frames.shape != source.shape:
        raise ValueError("Wynik preprocessingu ma nieprawidłowy kształt lub liczbę klatek.")
    if not np.issubdtype(frames.dtype, np.floating):
        raise ValueError("Wynik preprocessingu musi zawierać rzeczywiste wartości zmiennoprzecinkowe.")
    valid = np.isfinite(source)
    if not np.isfinite(frames[valid]).all():
        raise ValueError("Wynik preprocessingu zawiera braki w miejscach ważnych pomiarów.")
    return np.where(valid, frames, np.nan)
