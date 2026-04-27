"""Tile-wise robust translation estimates for registration."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from skimage.registration import phase_cross_correlation

from nanotrack.core import RegistrationFrameResult

from .phase_correlation import PhaseCorrelationBackendError
from .view import RegistrationViewResult


@dataclass(frozen=True)
class TileCorrelationRansacConfig:
    """Runtime configuration for tile correlation with robust consensus."""

    tile_size: int = 32
    stride: int = 16
    upsample_factor: int = 1
    normalization: str | None = "phase"
    min_texture_std: float = 1e-8
    min_tile_valid_fraction: float = 0.8
    residual_threshold_px: float = 1.5
    min_inlier_tiles: int = 3
    low_confidence_inlier_ratio: float = 0.5

    def __post_init__(self) -> None:
        tile_size = int(self.tile_size)
        if tile_size <= 1:
            raise ValueError("tile_size must be greater than 1.")
        object.__setattr__(self, "tile_size", tile_size)

        stride = int(self.stride)
        if stride <= 0:
            raise ValueError("stride must be positive.")
        object.__setattr__(self, "stride", stride)

        upsample_factor = int(self.upsample_factor)
        if upsample_factor <= 0:
            raise ValueError("upsample_factor must be positive.")
        object.__setattr__(self, "upsample_factor", upsample_factor)

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

        min_tile_valid_fraction = float(self.min_tile_valid_fraction)
        if not np.isfinite(min_tile_valid_fraction) or not 0.0 < min_tile_valid_fraction <= 1.0:
            raise ValueError("min_tile_valid_fraction must be in (0, 1].")
        object.__setattr__(self, "min_tile_valid_fraction", min_tile_valid_fraction)

        residual_threshold_px = float(self.residual_threshold_px)
        if not np.isfinite(residual_threshold_px) or residual_threshold_px <= 0.0:
            raise ValueError("residual_threshold_px must be a finite positive value.")
        object.__setattr__(self, "residual_threshold_px", residual_threshold_px)

        min_inlier_tiles = int(self.min_inlier_tiles)
        if min_inlier_tiles <= 0:
            raise ValueError("min_inlier_tiles must be positive.")
        object.__setattr__(self, "min_inlier_tiles", min_inlier_tiles)

        low_confidence_inlier_ratio = float(self.low_confidence_inlier_ratio)
        if not np.isfinite(low_confidence_inlier_ratio) or not 0.0 < low_confidence_inlier_ratio <= 1.0:
            raise ValueError("low_confidence_inlier_ratio must be in (0, 1].")
        object.__setattr__(self, "low_confidence_inlier_ratio", low_confidence_inlier_ratio)


class TileCorrelationRansacBackend:
    """Estimate a global translation from tile-wise local phase correlations."""

    method_name = "tile_correlation_ransac"

    def __init__(self, config: TileCorrelationRansacConfig | None = None):
        self.config = config or TileCorrelationRansacConfig()

    def estimate(
        self,
        reference_frame: np.ndarray,
        moving_frame: np.ndarray,
        *,
        moving_frame_index: int,
        reference_mask: np.ndarray | None = None,
        moving_mask: np.ndarray | None = None,
    ) -> RegistrationFrameResult:
        """Return the shift to apply to moving_frame based on robust tile consensus."""

        frame_index = int(moving_frame_index)
        if frame_index < 0:
            raise ValueError("moving_frame_index must be non-negative.")

        reference = self._prepare_frame(reference_frame, "reference_frame")
        moving = self._prepare_frame(moving_frame, "moving_frame")
        if reference.shape != moving.shape:
            raise ValueError("reference_frame and moving_frame must have the same shape.")
        if min(reference.shape) < self.config.tile_size:
            raise ValueError("registration frames must be at least tile_size in both dimensions.")

        reference_mask_bool = self._prepare_optional_mask(reference_mask, reference.shape, "reference_mask")
        moving_mask_bool = self._prepare_optional_mask(moving_mask, moving.shape, "moving_mask")
        if reference_mask_bool is None:
            reference_mask_bool = np.ones(reference.shape, dtype=bool)
        if moving_mask_bool is None:
            moving_mask_bool = reference_mask_bool

        local_shifts = self._estimate_local_shifts(reference, moving, reference_mask_bool, moving_mask_bool)
        if local_shifts.shape[0] < self.config.min_inlier_tiles:
            raise PhaseCorrelationBackendError(
                f"Only {local_shifts.shape[0]} usable registration tiles; "
                f"need at least {self.config.min_inlier_tiles}."
            )

        consensus = self._robust_consensus(local_shifts)
        if consensus["num_inliers"] < self.config.min_inlier_tiles:
            raise PhaseCorrelationBackendError(
                f"Only {consensus['num_inliers']} inlier registration tiles; "
                f"need at least {self.config.min_inlier_tiles}."
            )

        inlier_ratio = float(consensus["num_inliers"] / local_shifts.shape[0])
        median_residual = float(consensus["median_residual"])
        residual_quality = 1.0 - min(median_residual / self.config.residual_threshold_px, 1.0)
        quality_score = float(np.clip(0.7 * inlier_ratio + 0.3 * residual_quality, 0.0, 1.0))
        status = "ok" if inlier_ratio >= self.config.low_confidence_inlier_ratio else "low_confidence"
        shift_xy = np.asarray(consensus["shift_xy"], dtype=np.float64)

        return RegistrationFrameResult(
            frame_index=frame_index,
            shift_xy=(float(shift_xy[0]), float(shift_xy[1])),
            method=self.method_name,
            quality_score=quality_score,
            phase_peak_ratio=None,
            num_inlier_tiles=int(consensus["num_inliers"]),
            num_total_tiles=int(local_shifts.shape[0]),
            median_tile_residual=median_residual,
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
        """Estimate a robust tile shift between two frames from a registration-view stack."""

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

    def _estimate_local_shifts(
        self,
        reference: np.ndarray,
        moving: np.ndarray,
        reference_mask: np.ndarray,
        moving_mask: np.ndarray,
    ) -> np.ndarray:
        shifts: list[tuple[float, float]] = []
        tile_size = self.config.tile_size
        for y0 in self._tile_positions(reference.shape[0]):
            for x0 in self._tile_positions(reference.shape[1]):
                tile_slice = np.s_[y0 : y0 + tile_size, x0 : x0 + tile_size]
                ref_mask_tile = reference_mask[tile_slice]
                mov_mask_tile = moving_mask[tile_slice]
                if self._valid_fraction(ref_mask_tile) < self.config.min_tile_valid_fraction:
                    continue
                if self._valid_fraction(mov_mask_tile) < self.config.min_tile_valid_fraction:
                    continue
                ref_tile = self._fill_invalid_with_tile_median(reference[tile_slice], ref_mask_tile)
                mov_tile = self._fill_invalid_with_tile_median(moving[tile_slice], mov_mask_tile)
                if float(np.std(ref_tile)) <= self.config.min_texture_std:
                    continue
                if float(np.std(mov_tile)) <= self.config.min_texture_std:
                    continue
                try:
                    shift_yx, _error, _phase_diff = phase_cross_correlation(
                        ref_tile - float(np.mean(ref_tile)),
                        mov_tile - float(np.mean(mov_tile)),
                        upsample_factor=self.config.upsample_factor,
                        normalization=self.config.normalization,
                    )
                except Exception:
                    continue
                shift_yx = np.asarray(shift_yx, dtype=np.float64)
                if shift_yx.shape != (2,) or not np.all(np.isfinite(shift_yx)):
                    continue
                shifts.append((float(shift_yx[1]), float(shift_yx[0])))
        return np.asarray(shifts, dtype=np.float64).reshape((-1, 2))

    def _tile_positions(self, length: int) -> list[int]:
        tile_size = self.config.tile_size
        stride = self.config.stride
        last = int(length) - tile_size
        if last < 0:
            return []
        positions = list(range(0, last + 1, stride))
        if not positions or positions[-1] != last:
            positions.append(last)
        return sorted(set(int(position) for position in positions))

    def _robust_consensus(self, shifts_xy: np.ndarray) -> dict[str, object]:
        best_inliers: np.ndarray | None = None
        best_median_residual = float("inf")
        for candidate in shifts_xy:
            residuals = np.linalg.norm(shifts_xy - candidate, axis=1)
            inliers = residuals <= self.config.residual_threshold_px
            num_inliers = int(np.count_nonzero(inliers))
            if num_inliers == 0:
                continue
            median_residual = float(np.median(residuals[inliers]))
            if best_inliers is None or num_inliers > int(np.count_nonzero(best_inliers)):
                best_inliers = inliers
                best_median_residual = median_residual
            elif num_inliers == int(np.count_nonzero(best_inliers)) and median_residual < best_median_residual:
                best_inliers = inliers
                best_median_residual = median_residual

        if best_inliers is None:
            return {"shift_xy": np.asarray([0.0, 0.0]), "num_inliers": 0, "median_residual": float("inf")}

        refined_shift = np.median(shifts_xy[best_inliers], axis=0)
        refined_residuals = np.linalg.norm(shifts_xy - refined_shift, axis=1)
        refined_inliers = refined_residuals <= self.config.residual_threshold_px
        if int(np.count_nonzero(refined_inliers)) >= int(np.count_nonzero(best_inliers)):
            best_inliers = refined_inliers
            best_median_residual = float(np.median(refined_residuals[best_inliers]))
            refined_shift = np.median(shifts_xy[best_inliers], axis=0)

        return {
            "shift_xy": np.asarray(refined_shift, dtype=np.float64),
            "num_inliers": int(np.count_nonzero(best_inliers)),
            "median_residual": best_median_residual,
        }

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

    @staticmethod
    def _valid_fraction(mask: np.ndarray) -> float:
        if mask.size == 0:
            return 0.0
        return float(np.count_nonzero(mask) / mask.size)

    @staticmethod
    def _fill_invalid_with_tile_median(tile: np.ndarray, mask: np.ndarray) -> np.ndarray:
        if bool(np.all(mask)):
            return np.asarray(tile, dtype=np.float32)
        valid_values = np.asarray(tile, dtype=np.float32)[mask]
        if valid_values.size == 0:
            return np.asarray(tile, dtype=np.float32)
        filled = np.asarray(tile, dtype=np.float32).copy()
        filled[~mask] = float(np.median(valid_values))
        return filled
