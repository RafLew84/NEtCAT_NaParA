"""Materialized aligned registration views."""

from __future__ import annotations

import numpy as np

from nanotrack.core import RegistrationResultSet

from .preview import apply_translation_to_frame


def build_aligned_frames(
    frames: np.ndarray,
    result_set: RegistrationResultSet,
    *,
    interpolation_order: int = 1,
) -> np.ndarray:
    """Apply stored global translations to a raw frame stack."""

    source_stack = _ensure_frame_stack(frames)
    if not isinstance(result_set, RegistrationResultSet):
        raise TypeError("result_set must be a RegistrationResultSet instance.")

    frame_count = int(source_stack.shape[0])
    expected_indices = set(range(frame_count))
    result_indices = set(result_set.frame_indices)
    if result_indices != expected_indices:
        missing = sorted(expected_indices - result_indices)
        extra = sorted(result_indices - expected_indices)
        details: list[str] = []
        if missing:
            details.append(f"missing frame results: {missing}")
        if extra:
            details.append(f"out-of-range frame results: {extra}")
        raise ValueError("registration results do not match frame stack: " + "; ".join(details))

    aligned = np.empty_like(source_stack, dtype=np.float32)
    for frame_index in range(frame_count):
        result = result_set.get_result(frame_index)
        if result is None:
            raise ValueError(f"missing registration result for frame {frame_index}.")
        aligned[frame_index] = apply_translation_to_frame(
            source_stack[frame_index],
            result.shift_xy,
            interpolation_order=interpolation_order,
        )
    return aligned


def _ensure_frame_stack(frames: np.ndarray) -> np.ndarray:
    stack = np.asarray(frames, dtype=np.float32)
    if stack.ndim != 3:
        raise ValueError("frames must be a 3D array with shape (frame, height, width).")
    if stack.shape[0] < 1:
        raise ValueError("aligned registration view requires at least one frame.")
    if stack.shape[1] < 1 or stack.shape[2] < 1:
        raise ValueError("registration frames must be non-empty.")
    if not np.all(np.isfinite(stack)):
        raise ValueError("frames must contain only finite values.")
    return stack
