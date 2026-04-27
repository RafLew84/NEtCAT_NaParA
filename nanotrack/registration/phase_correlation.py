"""Phase-correlation backend for global translation estimates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
from skimage.registration import phase_cross_correlation

from nanotrack.core.data_models import RegistrationFrameResult

from .view import RegistrationViewResult


NormalizationMode = Literal["phase"] | None


class PhaseCorrelationBackendError(RuntimeError):
    """Raised when phase correlation cannot produce a usable translation."""


@dataclass(frozen=True)
class PhaseCorrelationShiftConfig:
    """Runtime configuration for phase-correlation translation estimates."""

    upsample_factor: int = 20
    normalization: NormalizationMode | str = "phase"
    min_texture_std: float = 1e-8
    peak_exclusion_radius: int = 3
    low_confidence_peak_ratio: float = 3.0

    def __post_init__(self) -> None:
        if int(self.upsample_factor) <= 0:
            raise ValueError("upsample_factor must be positive.")
        object.__setattr__(self, "upsample_factor", int(self.upsample_factor))

        normalization = self.normalization
        if isinstance(normalization, str):
            normalization = normalization.strip().lower()
            if normalization == "none":
                normalization = None
        if normalization not in ("phase", None):
            raise ValueError("normalization must be 'phase' or None.")
        object.__setattr__(self, "normalization", normalization)

        min_texture_std = float(self.min_texture_std)
        if not np.isfinite(min_texture_std) or min_texture_std < 0.0:
            raise ValueError("min_texture_std must be a finite non-negative value.")
        object.__setattr__(self, "min_texture_std", min_texture_std)

        peak_exclusion_radius = int(self.peak_exclusion_radius)
        if peak_exclusion_radius < 0:
            raise ValueError("peak_exclusion_radius must be non-negative.")
        object.__setattr__(self, "peak_exclusion_radius", peak_exclusion_radius)

        low_confidence_peak_ratio = float(self.low_confidence_peak_ratio)
        if not np.isfinite(low_confidence_peak_ratio) or low_confidence_peak_ratio <= 0.0:
            raise ValueError("low_confidence_peak_ratio must be a finite positive value.")
        object.__setattr__(self, "low_confidence_peak_ratio", low_confidence_peak_ratio)


class PhaseCorrelationShiftBackend:
    """Estimate one global dx/dy shift between two registration frames."""

    method_name = "phase_correlation"

    def __init__(self, config: PhaseCorrelationShiftConfig | None = None):
        self.config = config or PhaseCorrelationShiftConfig()

    def estimate(
        self,
        reference_frame: np.ndarray,
        moving_frame: np.ndarray,
        *,
        moving_frame_index: int,
    ) -> RegistrationFrameResult:
        """Return the shift to apply to moving_frame so it aligns to reference_frame."""

        frame_index = int(moving_frame_index)
        if frame_index < 0:
            raise ValueError("moving_frame_index must be non-negative.")

        reference = self._prepare_frame(reference_frame, "reference_frame")
        moving = self._prepare_frame(moving_frame, "moving_frame")
        if reference.shape != moving.shape:
            raise ValueError("reference_frame and moving_frame must have the same shape.")
        self._require_texture(reference, "reference_frame")
        self._require_texture(moving, "moving_frame")

        reference_zero = reference - float(np.mean(reference))
        moving_zero = moving - float(np.mean(moving))
        shift_yx, _error, _phase_diff = phase_cross_correlation(
            reference_zero,
            moving_zero,
            upsample_factor=self.config.upsample_factor,
            normalization=self.config.normalization,
        )
        shift_yx = np.asarray(shift_yx, dtype=np.float64)
        if shift_yx.shape != (2,) or not np.all(np.isfinite(shift_yx)):
            raise PhaseCorrelationBackendError("Phase correlation returned an invalid shift.")

        peak_ratio = self._phase_peak_ratio(reference_zero, moving_zero)
        quality_score = self._quality_from_peak_ratio(peak_ratio)
        status = "ok" if peak_ratio >= self.config.low_confidence_peak_ratio else "low_confidence"

        return RegistrationFrameResult(
            frame_index=frame_index,
            shift_xy=(float(shift_yx[1]), float(shift_yx[0])),
            method=self.method_name,
            quality_score=quality_score,
            phase_peak_ratio=peak_ratio,
            status=status,
        )

    def estimate_pair(
        self,
        registration_view: RegistrationViewResult | np.ndarray,
        *,
        reference_index: int,
        moving_index: int,
    ) -> RegistrationFrameResult:
        """Estimate a shift between two frames from a registration-view stack."""

        frames = self._registration_frames(registration_view)
        reference_index = self._normalize_frame_index(reference_index, frames.shape[0], "reference_index")
        moving_index = self._normalize_frame_index(moving_index, frames.shape[0], "moving_index")
        return self.estimate(
            frames[reference_index],
            frames[moving_index],
            moving_frame_index=moving_index,
        )

    def _prepare_frame(self, frame: np.ndarray, name: str) -> np.ndarray:
        prepared = np.asarray(frame, dtype=np.float32)
        if prepared.ndim != 2:
            raise ValueError(f"{name} must be a 2D image.")
        if prepared.shape[0] < 1 or prepared.shape[1] < 1:
            raise ValueError(f"{name} must be non-empty.")
        if not np.all(np.isfinite(prepared)):
            raise ValueError(f"{name} must contain only finite values.")
        return prepared

    def _require_texture(self, frame: np.ndarray, name: str) -> None:
        texture_std = float(np.std(frame))
        if texture_std <= self.config.min_texture_std:
            raise PhaseCorrelationBackendError(f"{name} has too little texture for phase correlation.")

    def _registration_frames(self, registration_view: RegistrationViewResult | np.ndarray) -> np.ndarray:
        frames = registration_view.frames if isinstance(registration_view, RegistrationViewResult) else registration_view
        stack = np.asarray(frames, dtype=np.float32)
        if stack.ndim != 3:
            raise ValueError("registration_view must be a 3D frame stack.")
        if stack.shape[0] < 1:
            raise ValueError("registration_view must contain at least one frame.")
        if not np.all(np.isfinite(stack)):
            raise ValueError("registration_view must contain only finite values.")
        return stack

    @staticmethod
    def _normalize_frame_index(frame_index: int, frame_count: int, name: str) -> int:
        normalized = int(frame_index)
        if normalized < 0 or normalized >= frame_count:
            raise IndexError(f"{name} is out of registration_view frame range.")
        return normalized

    def _phase_peak_ratio(self, reference_zero: np.ndarray, moving_zero: np.ndarray) -> float:
        reference_fft = np.fft.fft2(reference_zero)
        moving_fft = np.fft.fft2(moving_zero)
        cross_power = reference_fft * np.conj(moving_fft)
        magnitude = np.abs(cross_power)
        valid = magnitude > np.finfo(np.float32).eps
        if not np.any(valid):
            return 0.0
        cross_power = np.divide(
            cross_power,
            magnitude,
            out=np.zeros_like(cross_power),
            where=valid,
        )
        correlation = np.abs(np.fft.ifft2(cross_power))
        peak_index = np.unravel_index(int(np.argmax(correlation)), correlation.shape)
        peak_value = float(correlation[peak_index])
        if peak_value <= 0.0 or not np.isfinite(peak_value):
            return 0.0

        centered = np.roll(
            correlation,
            shift=(
                correlation.shape[0] // 2 - peak_index[0],
                correlation.shape[1] // 2 - peak_index[1],
            ),
            axis=(0, 1),
        )
        sidelobe_mask = np.ones(centered.shape, dtype=bool)
        center_y = centered.shape[0] // 2
        center_x = centered.shape[1] // 2
        radius = self.config.peak_exclusion_radius
        y0 = max(0, center_y - radius)
        y1 = min(centered.shape[0], center_y + radius + 1)
        x0 = max(0, center_x - radius)
        x1 = min(centered.shape[1], center_x + radius + 1)
        sidelobe_mask[y0:y1, x0:x1] = False
        sidelobes = centered[sidelobe_mask]
        if sidelobes.size == 0:
            return 0.0
        second_peak = float(np.max(sidelobes))
        if second_peak <= np.finfo(np.float32).eps:
            return peak_value / float(np.finfo(np.float32).eps)
        return float(peak_value / second_peak)

    def _quality_from_peak_ratio(self, peak_ratio: float) -> float:
        if not np.isfinite(peak_ratio) or peak_ratio <= 0.0:
            return 0.0
        quality = peak_ratio / (peak_ratio + self.config.low_confidence_peak_ratio)
        return float(np.clip(quality, 0.0, 1.0))
