"""Batch registration workflows for NanoTrack sequences."""

from __future__ import annotations

from typing import Callable

import numpy as np

from nanotrack.core import (
    RegistrationFrameResult,
    RegistrationResultSet,
    RegistrationSettings,
)

from .phase_correlation import PhaseCorrelationShiftBackend
from .view import build_registration_view_from_settings


RegistrationProgressCallback = Callable[[int, int, RegistrationFrameResult], None]


def run_adjacent_phase_registration(
    frames: np.ndarray,
    *,
    settings: RegistrationSettings | None = None,
    backend: PhaseCorrelationShiftBackend | None = None,
    progress_callback: RegistrationProgressCallback | None = None,
) -> RegistrationResultSet:
    """Register all frames to frame 0 by accumulating adjacent translations."""

    source_stack = _ensure_frame_stack(frames)
    settings = settings or RegistrationSettings(
        backend="phase_correlation",
        reference_strategy="adjacent",
        registration_view="raw",
    )
    if settings.reference_strategy != "adjacent":
        raise ValueError("run_adjacent_phase_registration requires reference_strategy='adjacent'.")

    backend = backend or PhaseCorrelationShiftBackend()
    registration_view = build_registration_view_from_settings(source_stack, settings)
    total = int(source_stack.shape[0])

    results: dict[int, RegistrationFrameResult] = {}
    identity = RegistrationFrameResult(
        frame_index=0,
        shift_xy=(0.0, 0.0),
        method="identity",
        quality_score=1.0,
        status="ok",
    )
    results[0] = identity
    if progress_callback is not None:
        progress_callback(1, total, identity)

    cumulative_shift = np.asarray(identity.shift_xy, dtype=np.float64)
    cumulative_quality = float(identity.quality_score)
    cumulative_status = identity.status

    for moving_index in range(1, total):
        pair_result = backend.estimate_pair(
            registration_view,
            reference_index=moving_index - 1,
            moving_index=moving_index,
        )
        pair_shift = np.asarray(pair_result.shift_xy, dtype=np.float64)
        cumulative_shift = cumulative_shift + pair_shift
        cumulative_quality = min(cumulative_quality, pair_result.quality_score)
        if cumulative_status == "failed" or pair_result.status == "failed":
            cumulative_status = "failed"
        elif cumulative_status == "manual_review" or pair_result.status == "manual_review":
            cumulative_status = "manual_review"
        elif cumulative_status == "low_confidence" or pair_result.status == "low_confidence":
            cumulative_status = "low_confidence"
        else:
            cumulative_status = "ok"

        cumulative_result = RegistrationFrameResult(
            frame_index=moving_index,
            shift_xy=(float(cumulative_shift[0]), float(cumulative_shift[1])),
            method="phase_correlation_adjacent",
            quality_score=cumulative_quality,
            phase_peak_ratio=pair_result.phase_peak_ratio,
            status=cumulative_status,
        )
        results[moving_index] = cumulative_result
        if progress_callback is not None:
            progress_callback(moving_index + 1, total, cumulative_result)

    return RegistrationResultSet(
        settings=settings,
        results_by_frame=results,
        reference_frame_index=0,
        template_frame_indices=(0,),
    )


def _ensure_frame_stack(frames: np.ndarray) -> np.ndarray:
    stack = np.asarray(frames, dtype=np.float32)
    if stack.ndim != 3:
        raise ValueError("frames must be a 3D array with shape (frame, height, width).")
    if stack.shape[0] < 1:
        raise ValueError("registration batch requires at least one frame.")
    if stack.shape[1] < 1 or stack.shape[2] < 1:
        raise ValueError("registration frames must be non-empty.")
    if not np.all(np.isfinite(stack)):
        raise ValueError("frames must contain only finite values.")
    return stack
