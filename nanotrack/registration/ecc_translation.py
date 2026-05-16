"""ECC translation refinement backend for registration."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from nanotrack.core import RegistrationFrameResult

from .phase_correlation import (
    PhaseCorrelationBackendError,
    PhaseCorrelationShiftBackend,
    PhaseCorrelationShiftConfig,
)
from .view import RegistrationViewResult


class ECCTranslationBackendError(RuntimeError):
    """Raised when ECC translation refinement cannot converge to a usable shift."""


@dataclass(frozen=True)
class ECCTranslationConfig:
    """Runtime configuration for ECC translation refinement."""

    max_iterations: int = 100
    epsilon: float = 1e-6
    gaussian_filter_size: int = 5
    min_texture_std: float = 1e-8
    min_mask_pixels: int = 16
    low_confidence_ecc_score: float = 0.75
    coarse_upsample_factor: int = 20
    coarse_normalization: str | None = "phase"
    coarse_peak_exclusion_radius: int = 3
    coarse_low_confidence_peak_ratio: float = 3.0

    def __post_init__(self) -> None:
        max_iterations = int(self.max_iterations)
        if max_iterations <= 0:
            raise ValueError("max_iterations must be positive.")
        object.__setattr__(self, "max_iterations", max_iterations)

        epsilon = float(self.epsilon)
        if not np.isfinite(epsilon) or epsilon <= 0.0:
            raise ValueError("epsilon must be a finite positive value.")
        object.__setattr__(self, "epsilon", epsilon)

        gaussian_filter_size = int(self.gaussian_filter_size)
        if gaussian_filter_size <= 0 or gaussian_filter_size % 2 == 0:
            raise ValueError("gaussian_filter_size must be a positive odd integer.")
        object.__setattr__(self, "gaussian_filter_size", gaussian_filter_size)

        min_texture_std = float(self.min_texture_std)
        if not np.isfinite(min_texture_std) or min_texture_std < 0.0:
            raise ValueError("min_texture_std must be a finite non-negative value.")
        object.__setattr__(self, "min_texture_std", min_texture_std)

        min_mask_pixels = int(self.min_mask_pixels)
        if min_mask_pixels <= 0:
            raise ValueError("min_mask_pixels must be positive.")
        object.__setattr__(self, "min_mask_pixels", min_mask_pixels)

        low_confidence_ecc_score = float(self.low_confidence_ecc_score)
        if not np.isfinite(low_confidence_ecc_score) or not 0.0 <= low_confidence_ecc_score <= 1.0:
            raise ValueError("low_confidence_ecc_score must be in [0, 1].")
        object.__setattr__(self, "low_confidence_ecc_score", low_confidence_ecc_score)

        coarse_upsample_factor = int(self.coarse_upsample_factor)
        if coarse_upsample_factor <= 0:
            raise ValueError("coarse_upsample_factor must be positive.")
        object.__setattr__(self, "coarse_upsample_factor", coarse_upsample_factor)

        coarse_normalization = self.coarse_normalization
        if isinstance(coarse_normalization, str):
            coarse_normalization = coarse_normalization.strip().lower()
            if coarse_normalization == "none":
                coarse_normalization = None
        if coarse_normalization not in ("phase", None):
            raise ValueError("coarse_normalization must be 'phase' or None.")
        object.__setattr__(self, "coarse_normalization", coarse_normalization)

        coarse_peak_exclusion_radius = int(self.coarse_peak_exclusion_radius)
        if coarse_peak_exclusion_radius < 0:
            raise ValueError("coarse_peak_exclusion_radius must be non-negative.")
        object.__setattr__(self, "coarse_peak_exclusion_radius", coarse_peak_exclusion_radius)

        coarse_low_confidence_peak_ratio = float(self.coarse_low_confidence_peak_ratio)
        if not np.isfinite(coarse_low_confidence_peak_ratio) or coarse_low_confidence_peak_ratio <= 0.0:
            raise ValueError("coarse_low_confidence_peak_ratio must be a finite positive value.")
        object.__setattr__(
            self,
            "coarse_low_confidence_peak_ratio",
            coarse_low_confidence_peak_ratio,
        )


class ECCTranslationBackend:
    """Refine one global translation using OpenCV ECC with MOTION_TRANSLATION."""

    method_name = "ecc_translation"

    def __init__(self, config: ECCTranslationConfig | None = None):
        self.config = config or ECCTranslationConfig()
        self._coarse_backend = PhaseCorrelationShiftBackend(
            PhaseCorrelationShiftConfig(
                upsample_factor=self.config.coarse_upsample_factor,
                normalization=self.config.coarse_normalization,
                min_texture_std=self.config.min_texture_std,
                peak_exclusion_radius=self.config.coarse_peak_exclusion_radius,
                low_confidence_peak_ratio=self.config.coarse_low_confidence_peak_ratio,
            )
        )

    def estimate(
        self,
        reference_frame: np.ndarray,
        moving_frame: np.ndarray,
        *,
        moving_frame_index: int,
        initial_shift_xy: tuple[float, float] | np.ndarray | None = None,
        reference_mask: np.ndarray | None = None,
        moving_mask: np.ndarray | None = None,
    ) -> RegistrationFrameResult:
        """Return an ECC-refined shift to apply to moving_frame."""

        frame_index = int(moving_frame_index)
        if frame_index < 0:
            raise ValueError("moving_frame_index must be non-negative.")

        reference = self._prepare_frame(reference_frame, "reference_frame")
        moving = self._prepare_frame(moving_frame, "moving_frame")
        if reference.shape != moving.shape:
            raise ValueError("reference_frame and moving_frame must have the same shape.")
        self._require_texture(reference, "reference_frame")
        self._require_texture(moving, "moving_frame")

        mask = self._combined_mask(reference_mask, moving_mask, reference.shape)
        coarse_result: RegistrationFrameResult | None = None
        if initial_shift_xy is None:
            try:
                coarse_result = self._coarse_backend.estimate(
                    reference,
                    moving,
                    moving_frame_index=frame_index,
                )
            except PhaseCorrelationBackendError as exc:
                raise ECCTranslationBackendError("ECC coarse phase estimate failed.") from exc
            initial_shift = np.asarray(coarse_result.shift_xy, dtype=np.float64)
        else:
            initial_shift = self._prepare_shift(initial_shift_xy, "initial_shift_xy")

        reference_ecc = self._normalize_for_ecc(reference, "reference_frame")
        moving_ecc = self._normalize_for_ecc(moving, "moving_frame")
        ecc_score, refined_shift = self._run_ecc(reference_ecc, moving_ecc, initial_shift, mask)

        quality_score = float(np.clip(ecc_score, 0.0, 1.0))
        status = "ok" if ecc_score >= self.config.low_confidence_ecc_score else "low_confidence"
        return RegistrationFrameResult(
            frame_index=frame_index,
            shift_xy=(float(refined_shift[0]), float(refined_shift[1])),
            method=self.method_name,
            quality_score=quality_score,
            phase_peak_ratio=coarse_result.phase_peak_ratio if coarse_result is not None else None,
            ecc_score=ecc_score,
            status=status,
        )

    def estimate_pair(
        self,
        registration_view: RegistrationViewResult | np.ndarray,
        *,
        reference_index: int,
        moving_index: int,
        initial_shift_xy: tuple[float, float] | np.ndarray | None = None,
        reference_mask: np.ndarray | None = None,
        moving_mask: np.ndarray | None = None,
    ) -> RegistrationFrameResult:
        """Estimate an ECC-refined shift between two frames from a registration-view stack."""

        frames = self._registration_frames(registration_view)
        reference_index = self._normalize_frame_index(reference_index, frames.shape[0], "reference_index")
        moving_index = self._normalize_frame_index(moving_index, frames.shape[0], "moving_index")
        return self.estimate(
            frames[reference_index],
            frames[moving_index],
            moving_frame_index=moving_index,
            initial_shift_xy=initial_shift_xy,
            reference_mask=reference_mask,
            moving_mask=moving_mask,
        )

    def _run_ecc(
        self,
        reference: np.ndarray,
        moving: np.ndarray,
        initial_shift_xy: np.ndarray,
        mask: np.ndarray | None,
    ) -> tuple[float, np.ndarray]:
        try:
            import cv2
        except ModuleNotFoundError as exc:
            raise ECCTranslationBackendError("OpenCV cv2 is required for ECCTranslationBackend.") from exc

        warp_matrix = np.asarray(
            [
                [1.0, 0.0, -float(initial_shift_xy[0])],
                [0.0, 1.0, -float(initial_shift_xy[1])],
            ],
            dtype=np.float32,
        )
        criteria = (
            cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT,
            self.config.max_iterations,
            self.config.epsilon,
        )
        input_mask = None if mask is None else np.asarray(mask, dtype=np.uint8) * 255
        try:
            ecc_score, refined_matrix = cv2.findTransformECC(
                reference,
                moving,
                warp_matrix,
                cv2.MOTION_TRANSLATION,
                criteria,
                input_mask,
                self.config.gaussian_filter_size,
            )
        except Exception as exc:
            raise ECCTranslationBackendError("OpenCV ECC translation refinement failed.") from exc

        ecc_score = float(ecc_score)
        if not np.isfinite(ecc_score):
            raise ECCTranslationBackendError("OpenCV ECC returned a non-finite score.")
        refined_matrix = np.asarray(refined_matrix, dtype=np.float64)
        if refined_matrix.shape != (2, 3) or not np.all(np.isfinite(refined_matrix[:, 2])):
            raise ECCTranslationBackendError("OpenCV ECC returned an invalid translation matrix.")
        refined_shift = np.asarray(
            [-float(refined_matrix[0, 2]), -float(refined_matrix[1, 2])],
            dtype=np.float64,
        )
        return ecc_score, refined_shift

    def _combined_mask(
        self,
        reference_mask: np.ndarray | None,
        moving_mask: np.ndarray | None,
        frame_shape: tuple[int, int],
    ) -> np.ndarray | None:
        reference_mask_bool = self._prepare_optional_mask(reference_mask, frame_shape, "reference_mask")
        moving_mask_bool = self._prepare_optional_mask(moving_mask, frame_shape, "moving_mask")
        if reference_mask_bool is None and moving_mask_bool is None:
            return None
        if reference_mask_bool is None:
            combined = moving_mask_bool
        elif moving_mask_bool is None:
            combined = reference_mask_bool
        else:
            combined = np.logical_and(reference_mask_bool, moving_mask_bool)
        assert combined is not None
        if int(np.count_nonzero(combined)) < self.config.min_mask_pixels:
            raise ValueError("combined ECC mask does not contain enough valid pixels.")
        return combined

    @staticmethod
    def _prepare_frame(frame: np.ndarray, name: str) -> np.ndarray:
        prepared = np.asarray(frame, dtype=np.float32)
        if prepared.ndim != 2:
            raise ValueError(f"{name} must be a 2D image.")
        if prepared.shape[0] < 1 or prepared.shape[1] < 1:
            raise ValueError(f"{name} must be non-empty.")
        if not np.all(np.isfinite(prepared)):
            raise ValueError(f"{name} must contain only finite values.")
        return prepared

    def _prepare_optional_mask(
        self,
        mask: np.ndarray | None,
        frame_shape: tuple[int, int],
        name: str,
    ) -> np.ndarray | None:
        if mask is None:
            return None
        prepared = np.asarray(mask, dtype=bool)
        if prepared.ndim != 2:
            raise ValueError(f"{name} must be a 2D boolean image.")
        if prepared.shape != frame_shape:
            raise ValueError(f"{name} shape must match registration frame shape.")
        if int(np.count_nonzero(prepared)) < self.config.min_mask_pixels:
            raise ValueError(f"{name} must contain at least min_mask_pixels valid pixels.")
        return prepared

    def _require_texture(self, frame: np.ndarray, name: str) -> None:
        texture_std = float(np.std(frame))
        if texture_std <= self.config.min_texture_std:
            raise ECCTranslationBackendError(f"{name} has too little texture for ECC translation.")

    @staticmethod
    def _normalize_for_ecc(frame: np.ndarray, name: str) -> np.ndarray:
        min_value = float(np.min(frame))
        max_value = float(np.max(frame))
        scale = max_value - min_value
        if not np.isfinite(scale) or scale <= np.finfo(np.float32).eps:
            raise ECCTranslationBackendError(f"{name} cannot be normalized for ECC.")
        return np.asarray((frame - min_value) / scale, dtype=np.float32)

    @staticmethod
    def _prepare_shift(shift_xy: tuple[float, float] | np.ndarray, name: str) -> np.ndarray:
        shift = np.asarray(shift_xy, dtype=np.float64)
        if shift.shape != (2,) or not np.all(np.isfinite(shift)):
            raise ValueError(f"{name} must contain exactly two finite values: dx, dy.")
        return shift

    @staticmethod
    def _registration_frames(registration_view: RegistrationViewResult | np.ndarray) -> np.ndarray:
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
