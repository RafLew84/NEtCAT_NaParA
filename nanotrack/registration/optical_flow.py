"""Optical-flow backend reduced to one global translation estimate."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from skimage.registration import optical_flow_ilk, optical_flow_tvl1

from nanotrack.core import RegistrationFrameResult

from .phase_correlation import PhaseCorrelationBackendError
from .view import RegistrationViewResult


@dataclass(frozen=True)
class OpticalFlowMedianConfig:
    """Runtime configuration for optical-flow median translation estimates."""

    method: str = "tvl1"
    min_texture_std: float = 1e-8
    min_valid_fraction: float = 0.1
    low_confidence_flow_mad_px: float = 1.0
    prefilter: bool = False
    tvl1_attachment: float = 15.0
    tvl1_tightness: float = 0.3
    tvl1_num_warp: int = 5
    tvl1_num_iter: int = 10
    tvl1_tol: float = 1e-4
    ilk_radius: int = 7
    ilk_num_warp: int = 10
    ilk_gaussian: bool = False

    def __post_init__(self) -> None:
        method = str(self.method).strip().lower()
        if method not in ("tvl1", "ilk"):
            raise ValueError("method must be 'tvl1' or 'ilk'.")
        object.__setattr__(self, "method", method)

        min_texture_std = float(self.min_texture_std)
        if not np.isfinite(min_texture_std) or min_texture_std < 0.0:
            raise ValueError("min_texture_std must be a finite non-negative value.")
        object.__setattr__(self, "min_texture_std", min_texture_std)

        min_valid_fraction = float(self.min_valid_fraction)
        if not np.isfinite(min_valid_fraction) or not 0.0 < min_valid_fraction <= 1.0:
            raise ValueError("min_valid_fraction must be in (0, 1].")
        object.__setattr__(self, "min_valid_fraction", min_valid_fraction)

        low_confidence_flow_mad_px = float(self.low_confidence_flow_mad_px)
        if not np.isfinite(low_confidence_flow_mad_px) or low_confidence_flow_mad_px < 0.0:
            raise ValueError("low_confidence_flow_mad_px must be a finite non-negative value.")
        object.__setattr__(self, "low_confidence_flow_mad_px", low_confidence_flow_mad_px)

        tvl1_attachment = float(self.tvl1_attachment)
        if not np.isfinite(tvl1_attachment) or tvl1_attachment <= 0.0:
            raise ValueError("tvl1_attachment must be a finite positive value.")
        object.__setattr__(self, "tvl1_attachment", tvl1_attachment)

        tvl1_tightness = float(self.tvl1_tightness)
        if not np.isfinite(tvl1_tightness) or tvl1_tightness <= 0.0:
            raise ValueError("tvl1_tightness must be a finite positive value.")
        object.__setattr__(self, "tvl1_tightness", tvl1_tightness)

        tvl1_num_warp = int(self.tvl1_num_warp)
        if tvl1_num_warp <= 0:
            raise ValueError("tvl1_num_warp must be positive.")
        object.__setattr__(self, "tvl1_num_warp", tvl1_num_warp)

        tvl1_num_iter = int(self.tvl1_num_iter)
        if tvl1_num_iter <= 0:
            raise ValueError("tvl1_num_iter must be positive.")
        object.__setattr__(self, "tvl1_num_iter", tvl1_num_iter)

        tvl1_tol = float(self.tvl1_tol)
        if not np.isfinite(tvl1_tol) or tvl1_tol <= 0.0:
            raise ValueError("tvl1_tol must be a finite positive value.")
        object.__setattr__(self, "tvl1_tol", tvl1_tol)

        ilk_radius = int(self.ilk_radius)
        if ilk_radius <= 0:
            raise ValueError("ilk_radius must be positive.")
        object.__setattr__(self, "ilk_radius", ilk_radius)

        ilk_num_warp = int(self.ilk_num_warp)
        if ilk_num_warp <= 0:
            raise ValueError("ilk_num_warp must be positive.")
        object.__setattr__(self, "ilk_num_warp", ilk_num_warp)


class OpticalFlowMedianBackend:
    """Estimate one global dx/dy shift from the robust median of dense optical flow."""

    method_name = "optical_flow_median"

    def __init__(self, config: OpticalFlowMedianConfig | None = None):
        self.config = config or OpticalFlowMedianConfig()

    def estimate(
        self,
        reference_frame: np.ndarray,
        moving_frame: np.ndarray,
        *,
        moving_frame_index: int,
        reference_mask: np.ndarray | None = None,
        moving_mask: np.ndarray | None = None,
    ) -> RegistrationFrameResult:
        """Return a global translation by reducing dense optical flow to its median."""

        frame_index = int(moving_frame_index)
        if frame_index < 0:
            raise ValueError("moving_frame_index must be non-negative.")

        reference = self._prepare_frame(reference_frame, "reference_frame")
        moving = self._prepare_frame(moving_frame, "moving_frame")
        if reference.shape != moving.shape:
            raise ValueError("reference_frame and moving_frame must have the same shape.")
        self._require_texture(reference, "reference_frame")
        self._require_texture(moving, "moving_frame")

        valid_mask = self._combined_mask(reference_mask, moving_mask, reference.shape)
        flow_yx = self._compute_flow(reference, moving)
        if flow_yx.shape != (2, *reference.shape) or not np.all(np.isfinite(flow_yx)):
            raise PhaseCorrelationBackendError("Optical flow returned an invalid flow field.")

        flow_y = np.asarray(flow_yx[0], dtype=np.float64)[valid_mask]
        flow_x = np.asarray(flow_yx[1], dtype=np.float64)[valid_mask]
        if flow_x.size == 0:
            raise PhaseCorrelationBackendError("Optical flow produced no valid vectors.")

        median_flow_x = float(np.median(flow_x))
        median_flow_y = float(np.median(flow_y))
        residuals = np.sqrt((flow_x - median_flow_x) ** 2 + (flow_y - median_flow_y) ** 2)
        flow_mad = float(np.median(residuals))
        if not np.isfinite(flow_mad):
            raise PhaseCorrelationBackendError("Optical flow residual spread is non-finite.")

        quality_score = float(np.clip(1.0 / (1.0 + flow_mad), 0.0, 1.0))
        status = "ok" if flow_mad <= self.config.low_confidence_flow_mad_px else "low_confidence"
        return RegistrationFrameResult(
            frame_index=frame_index,
            shift_xy=(-median_flow_x, -median_flow_y),
            method=self.method_name,
            quality_score=quality_score,
            flow_mad=flow_mad,
            status=status,
        )

    def estimate_pair(
        self,
        registration_view: RegistrationViewResult | np.ndarray,
        *,
        reference_index: int,
        moving_index: int,
        reference_mask: np.ndarray | None = None,
        moving_mask: np.ndarray | None = None,
    ) -> RegistrationFrameResult:
        """Estimate a robust optical-flow shift between two frames from a registration-view stack."""

        frames = self._registration_frames(registration_view)
        reference_index = self._normalize_frame_index(reference_index, frames.shape[0], "reference_index")
        moving_index = self._normalize_frame_index(moving_index, frames.shape[0], "moving_index")
        return self.estimate(
            frames[reference_index],
            frames[moving_index],
            moving_frame_index=moving_index,
            reference_mask=reference_mask,
            moving_mask=moving_mask,
        )

    def _compute_flow(self, reference: np.ndarray, moving: np.ndarray) -> np.ndarray:
        if self.config.method == "tvl1":
            return np.asarray(
                optical_flow_tvl1(
                    reference,
                    moving,
                    attachment=self.config.tvl1_attachment,
                    tightness=self.config.tvl1_tightness,
                    num_warp=self.config.tvl1_num_warp,
                    num_iter=self.config.tvl1_num_iter,
                    tol=self.config.tvl1_tol,
                    prefilter=self.config.prefilter,
                    dtype=np.float32,
                ),
                dtype=np.float32,
            )
        return np.asarray(
            optical_flow_ilk(
                reference,
                moving,
                radius=self.config.ilk_radius,
                num_warp=self.config.ilk_num_warp,
                gaussian=self.config.ilk_gaussian,
                prefilter=self.config.prefilter,
                dtype=np.float32,
            ),
            dtype=np.float32,
        )

    def _combined_mask(
        self,
        reference_mask: np.ndarray | None,
        moving_mask: np.ndarray | None,
        frame_shape: tuple[int, int],
    ) -> np.ndarray:
        reference_mask_bool = self._prepare_optional_mask(reference_mask, frame_shape, "reference_mask")
        moving_mask_bool = self._prepare_optional_mask(moving_mask, frame_shape, "moving_mask")
        if reference_mask_bool is None:
            reference_mask_bool = np.ones(frame_shape, dtype=bool)
        if moving_mask_bool is None:
            moving_mask_bool = reference_mask_bool
        valid_mask = np.logical_and(reference_mask_bool, moving_mask_bool)
        min_valid_pixels = max(1, int(np.ceil(valid_mask.size * self.config.min_valid_fraction)))
        if int(np.count_nonzero(valid_mask)) < min_valid_pixels:
            raise ValueError("combined optical-flow mask does not contain enough valid pixels.")
        return valid_mask

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

    @staticmethod
    def _prepare_optional_mask(mask: np.ndarray | None, frame_shape: tuple[int, int], name: str) -> np.ndarray | None:
        if mask is None:
            return None
        prepared = np.asarray(mask, dtype=bool)
        if prepared.ndim != 2:
            raise ValueError(f"{name} must be a 2D boolean image.")
        if prepared.shape != frame_shape:
            raise ValueError(f"{name} shape must match registration frame shape.")
        if not np.any(prepared):
            raise ValueError(f"{name} must contain at least one valid pixel.")
        return prepared

    def _require_texture(self, frame: np.ndarray, name: str) -> None:
        texture_std = float(np.std(frame))
        if texture_std <= self.config.min_texture_std:
            raise PhaseCorrelationBackendError(f"{name} has too little texture for optical flow.")

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
