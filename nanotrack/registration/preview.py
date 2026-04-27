"""Single-pair registration preview helpers."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.ndimage import shift as ndimage_shift

from nanotrack.core import RegistrationFrameResult, RegistrationSettings

from .phase_correlation import PhaseCorrelationShiftBackend
from .view import RegistrationViewResult, build_registration_view_from_settings


@dataclass
class RegistrationPairPreview:
    """Computed preview for one reference/moving frame pair."""

    reference_index: int
    moving_index: int
    reference_frame: np.ndarray
    moving_frame: np.ndarray
    aligned_moving_frame: np.ndarray
    registration_view: RegistrationViewResult
    result: RegistrationFrameResult

    def __post_init__(self) -> None:
        self.reference_index = int(self.reference_index)
        self.moving_index = int(self.moving_index)
        self.reference_frame = np.asarray(self.reference_frame, dtype=np.float32)
        self.moving_frame = np.asarray(self.moving_frame, dtype=np.float32)
        self.aligned_moving_frame = np.asarray(self.aligned_moving_frame, dtype=np.float32)
        if self.reference_frame.ndim != 2 or self.moving_frame.ndim != 2:
            raise ValueError("preview frames must be 2D images.")
        if self.reference_frame.shape != self.moving_frame.shape:
            raise ValueError("reference and moving preview frames must have matching shape.")
        if self.aligned_moving_frame.shape != self.reference_frame.shape:
            raise ValueError("aligned preview frame must match reference frame shape.")


def build_registration_pair_preview(
    frames: np.ndarray,
    *,
    reference_index: int,
    moving_index: int,
    settings: RegistrationSettings | None = None,
    backend: PhaseCorrelationShiftBackend | None = None,
    interpolation_order: int = 1,
) -> RegistrationPairPreview:
    """Estimate and materialize one aligned moving frame for preview only."""

    source_stack = _ensure_frame_stack(frames)
    reference_index = _normalize_frame_index(reference_index, source_stack.shape[0], "reference_index")
    moving_index = _normalize_frame_index(moving_index, source_stack.shape[0], "moving_index")
    if reference_index == moving_index:
        raise ValueError("reference_index and moving_index must be different for registration preview.")

    settings = settings or RegistrationSettings()
    backend = backend or PhaseCorrelationShiftBackend()
    registration_view = build_registration_view_from_settings(source_stack, settings)
    result = backend.estimate_pair(
        registration_view,
        reference_index=reference_index,
        moving_index=moving_index,
    )
    aligned_moving = apply_translation_to_frame(
        source_stack[moving_index],
        result.shift_xy,
        interpolation_order=interpolation_order,
    )
    return RegistrationPairPreview(
        reference_index=reference_index,
        moving_index=moving_index,
        reference_frame=source_stack[reference_index],
        moving_frame=source_stack[moving_index],
        aligned_moving_frame=aligned_moving,
        registration_view=registration_view,
        result=result,
    )


def apply_translation_to_frame(
    frame: np.ndarray,
    shift_xy: tuple[float, float],
    *,
    interpolation_order: int = 1,
) -> np.ndarray:
    """Apply a global translation to a single frame for preview rendering."""

    frame_array = np.asarray(frame, dtype=np.float32)
    if frame_array.ndim != 2:
        raise ValueError("frame must be a 2D image.")
    if not np.all(np.isfinite(frame_array)):
        raise ValueError("frame must contain only finite values.")

    dx, dy = (float(shift_xy[0]), float(shift_xy[1]))
    if not np.isfinite(dx) or not np.isfinite(dy):
        raise ValueError("shift_xy values must be finite.")

    order = int(interpolation_order)
    if order < 0 or order > 5:
        raise ValueError("interpolation_order must be between 0 and 5.")

    shifted = ndimage_shift(
        frame_array,
        shift=(dy, dx),
        order=order,
        mode="nearest",
        prefilter=order > 1,
    )
    return np.asarray(shifted, dtype=np.float32)


def _ensure_frame_stack(frames: np.ndarray) -> np.ndarray:
    stack = np.asarray(frames, dtype=np.float32)
    if stack.ndim != 3:
        raise ValueError("frames must be a 3D array with shape (frame, height, width).")
    if stack.shape[0] < 2:
        raise ValueError("registration preview requires at least two frames.")
    if not np.all(np.isfinite(stack)):
        raise ValueError("frames must contain only finite values.")
    return stack


def _normalize_frame_index(frame_index: int, frame_count: int, name: str) -> int:
    normalized = int(frame_index)
    if normalized < 0 or normalized >= frame_count:
        raise IndexError(f"{name} is out of frame range.")
    return normalized
