"""Batch registration workflows for NanoTrack sequences."""

from __future__ import annotations

from typing import Callable, Iterable

import numpy as np

from nanotrack.core import (
    RegistrationFrameResult,
    RegistrationResultSet,
    RegistrationSettings,
)

from .ecc_translation import (
    ECCTranslationBackend,
    ECCTranslationConfig,
)
from .deep_matcher import (
    DeepMatcherTranslationBackend,
    DeepMatcherTranslationConfig,
)
from .phase_correlation import (
    MaskedPhaseCorrelationBackend,
    MaskedPhaseCorrelationConfig,
    PhaseCorrelationShiftBackend,
)
from .optical_flow import (
    OpticalFlowMedianBackend,
    OpticalFlowMedianConfig,
)
from .tile_correlation import (
    TileCorrelationRansacBackend,
    TileCorrelationRansacConfig,
)
from .view import build_registration_view_from_settings


RegistrationProgressCallback = Callable[[int, int, RegistrationFrameResult], None]
AdjacentRegistrationBackend = (
    PhaseCorrelationShiftBackend
    | MaskedPhaseCorrelationBackend
    | TileCorrelationRansacBackend
    | ECCTranslationBackend
    | OpticalFlowMedianBackend
    | DeepMatcherTranslationBackend
)


def run_adjacent_phase_registration(
    frames: np.ndarray,
    *,
    settings: RegistrationSettings | None = None,
    backend: AdjacentRegistrationBackend | None = None,
    progress_callback: RegistrationProgressCallback | None = None,
    excluded_frame_indices: Iterable[int] | None = None,
) -> RegistrationResultSet:
    """Register included frames by accumulating adjacent translations."""

    source_stack = _ensure_frame_stack(frames)
    total = int(source_stack.shape[0])
    excluded = _normalize_excluded_frame_indices(excluded_frame_indices, frame_count=total)
    included = [frame_index for frame_index in range(total) if frame_index not in excluded]
    if not included:
        raise ValueError("registration requires at least one frame that is not excluded.")

    settings = settings or RegistrationSettings(
        backend="phase_correlation",
        reference_strategy="adjacent",
        registration_view="raw",
    )
    if settings.reference_strategy != "adjacent":
        raise ValueError("run_adjacent_phase_registration requires reference_strategy='adjacent'.")

    backend = backend or _backend_from_settings(settings)
    if isinstance(backend, MaskedPhaseCorrelationBackend) and settings.roi_mask is None:
        raise ValueError("MaskedPhaseCorrelationBackend requires RegistrationSettings.roi_mask.")
    registration_view = build_registration_view_from_settings(source_stack, settings)

    results: dict[int, RegistrationFrameResult] = {}
    cumulative_shift = np.asarray((0.0, 0.0), dtype=np.float64)
    cumulative_quality = 1.0
    cumulative_status = "ok"
    previous_included_index: int | None = None

    for frame_index in range(total):
        if frame_index in excluded:
            result = _excluded_registration_result(frame_index, cumulative_shift)
            results[frame_index] = result
            if progress_callback is not None:
                progress_callback(frame_index + 1, total, result)
            continue

        if previous_included_index is None:
            result = RegistrationFrameResult(
                frame_index=frame_index,
                shift_xy=(0.0, 0.0),
                method="identity",
                quality_score=1.0,
                status="ok",
            )
            previous_included_index = frame_index
        else:
            pair_result = _estimate_adjacent_pair(
                backend,
                registration_view,
                settings,
                reference_index=previous_included_index,
                moving_index=frame_index,
            )
            pair_shift = np.asarray(pair_result.shift_xy, dtype=np.float64)
            cumulative_shift = cumulative_shift + pair_shift
            cumulative_quality = min(cumulative_quality, pair_result.quality_score)
            cumulative_status = _combine_registration_status(cumulative_status, pair_result.status)

            result = RegistrationFrameResult(
                frame_index=frame_index,
                shift_xy=(float(cumulative_shift[0]), float(cumulative_shift[1])),
                method=_adjacent_method_name(pair_result.method),
                quality_score=cumulative_quality,
                phase_peak_ratio=pair_result.phase_peak_ratio,
                ecc_score=pair_result.ecc_score,
                num_inlier_tiles=pair_result.num_inlier_tiles,
                num_total_tiles=pair_result.num_total_tiles,
                median_tile_residual=pair_result.median_tile_residual,
                flow_mad=pair_result.flow_mad,
                status=cumulative_status,
            )
            previous_included_index = frame_index

        results[frame_index] = result
        if progress_callback is not None:
            progress_callback(frame_index + 1, total, result)

    return RegistrationResultSet(
        settings=settings,
        results_by_frame=results,
        reference_frame_index=included[0],
        template_frame_indices=(included[0],),
    )


def build_registration_backend_from_settings(settings: RegistrationSettings) -> AdjacentRegistrationBackend:
    """Create a registration backend from shared registration settings."""

    backend_name = settings.backend.strip().lower()
    if backend_name == "phase_correlation":
        return PhaseCorrelationShiftBackend()
    if backend_name == "masked_phase_correlation":
        params = dict(settings.backend_params)
        return MaskedPhaseCorrelationBackend(
            MaskedPhaseCorrelationConfig(
                overlap_ratio=float(params.get("overlap_ratio", 0.3)),
                min_mask_pixels=int(params.get("min_mask_pixels", 16)),
                min_texture_std=float(params.get("min_texture_std", 1e-8)),
                low_confidence_overlap_ratio=float(params.get("low_confidence_overlap_ratio", 0.5)),
            )
        )
    if backend_name == "tile_correlation_ransac":
        params = dict(settings.backend_params)
        return TileCorrelationRansacBackend(
            TileCorrelationRansacConfig(
                tile_size=int(params.get("tile_size", 32)),
                stride=int(params.get("stride", 16)),
                upsample_factor=int(params.get("upsample_factor", 1)),
                normalization=params.get("normalization", "phase"),
                min_texture_std=float(params.get("min_texture_std", 1e-8)),
                min_tile_valid_fraction=float(params.get("min_tile_valid_fraction", 0.8)),
                residual_threshold_px=float(params.get("residual_threshold_px", 1.5)),
                min_inlier_tiles=int(params.get("min_inlier_tiles", 3)),
                low_confidence_inlier_ratio=float(params.get("low_confidence_inlier_ratio", 0.5)),
            )
        )
    if backend_name == "ecc_translation":
        params = dict(settings.backend_params)
        return ECCTranslationBackend(
            ECCTranslationConfig(
                max_iterations=int(params.get("max_iterations", 100)),
                epsilon=float(params.get("epsilon", 1e-6)),
                gaussian_filter_size=int(params.get("gaussian_filter_size", 5)),
                min_texture_std=float(params.get("min_texture_std", 1e-8)),
                min_mask_pixels=int(params.get("min_mask_pixels", 16)),
                low_confidence_ecc_score=float(params.get("low_confidence_ecc_score", 0.75)),
                coarse_upsample_factor=int(params.get("coarse_upsample_factor", 20)),
                coarse_normalization=params.get("coarse_normalization", "phase"),
                coarse_peak_exclusion_radius=int(params.get("coarse_peak_exclusion_radius", 3)),
                coarse_low_confidence_peak_ratio=float(
                    params.get("coarse_low_confidence_peak_ratio", 3.0)
                ),
            )
        )
    if backend_name == "optical_flow_median":
        params = dict(settings.backend_params)
        return OpticalFlowMedianBackend(
            OpticalFlowMedianConfig(
                method=str(params.get("method", "tvl1")),
                min_texture_std=float(params.get("min_texture_std", 1e-8)),
                min_valid_fraction=float(params.get("min_valid_fraction", 0.1)),
                low_confidence_flow_mad_px=float(params.get("low_confidence_flow_mad_px", 1.0)),
                prefilter=bool(params.get("prefilter", False)),
                tvl1_attachment=float(params.get("tvl1_attachment", 15.0)),
                tvl1_tightness=float(params.get("tvl1_tightness", 0.3)),
                tvl1_num_warp=int(params.get("tvl1_num_warp", 5)),
                tvl1_num_iter=int(params.get("tvl1_num_iter", 10)),
                tvl1_tol=float(params.get("tvl1_tol", 1e-4)),
                ilk_radius=int(params.get("ilk_radius", 7)),
                ilk_num_warp=int(params.get("ilk_num_warp", 10)),
                ilk_gaussian=bool(params.get("ilk_gaussian", False)),
            )
        )
    if backend_name == "deep_matcher_translation":
        params = dict(settings.backend_params)
        return DeepMatcherTranslationBackend(
            DeepMatcherTranslationConfig(
                matcher=str(params.get("matcher", "loftr")),
                device=str(params.get("device", "auto")),
                pretrained=str(params.get("pretrained", "outdoor")),
                min_matches=int(params.get("min_matches", 8)),
                min_inliers=int(params.get("min_inliers", 4)),
                residual_threshold_px=float(params.get("residual_threshold_px", 2.0)),
                low_confidence_inlier_ratio=float(params.get("low_confidence_inlier_ratio", 0.5)),
            )
        )
    raise ValueError(f"Unsupported registration backend: {settings.backend!r}.")


def _backend_from_settings(settings: RegistrationSettings) -> AdjacentRegistrationBackend:
    return build_registration_backend_from_settings(settings)


def _estimate_adjacent_pair(
    backend: AdjacentRegistrationBackend,
    registration_view: np.ndarray,
    settings: RegistrationSettings,
    *,
    reference_index: int,
    moving_index: int,
) -> RegistrationFrameResult:
    if isinstance(backend, MaskedPhaseCorrelationBackend):
        return backend.estimate_pair(
            registration_view,
            reference_index=reference_index,
            moving_index=moving_index,
            reference_mask=settings.roi_mask,
        )
    if isinstance(backend, TileCorrelationRansacBackend):
        return backend.estimate_pair(
            registration_view,
            reference_index=reference_index,
            moving_index=moving_index,
            reference_mask=settings.roi_mask,
        )
    if isinstance(backend, ECCTranslationBackend):
        return backend.estimate_pair(
            registration_view,
            reference_index=reference_index,
            moving_index=moving_index,
            reference_mask=settings.roi_mask,
        )
    if isinstance(backend, OpticalFlowMedianBackend):
        return backend.estimate_pair(
            registration_view,
            reference_index=reference_index,
            moving_index=moving_index,
            reference_mask=settings.roi_mask,
        )
    if isinstance(backend, DeepMatcherTranslationBackend):
        return backend.estimate_pair(
            registration_view,
            reference_index=reference_index,
            moving_index=moving_index,
            reference_mask=settings.roi_mask,
        )
    return backend.estimate_pair(
        registration_view,
        reference_index=reference_index,
        moving_index=moving_index,
    )


def _adjacent_method_name(pair_method: str) -> str:
    method = str(pair_method).strip()
    if method.endswith("_adjacent"):
        return method
    return f"{method}_adjacent"


def _normalize_excluded_frame_indices(
    excluded_frame_indices: Iterable[int] | None,
    *,
    frame_count: int,
) -> set[int]:
    if excluded_frame_indices is None:
        return set()
    excluded = {int(frame_index) for frame_index in excluded_frame_indices}
    for frame_index in excluded:
        if not 0 <= frame_index < frame_count:
            raise IndexError("excluded_frame_indices contains an out-of-range frame index.")
    return excluded


def _excluded_registration_result(frame_index: int, cumulative_shift: np.ndarray) -> RegistrationFrameResult:
    return RegistrationFrameResult(
        frame_index=frame_index,
        shift_xy=(float(cumulative_shift[0]), float(cumulative_shift[1])),
        method="excluded_frame",
        quality_score=0.0,
        status="manual_review",
    )


def _combine_registration_status(current_status: str, pair_status: str) -> str:
    if current_status == "failed" or pair_status == "failed":
        return "failed"
    if current_status == "manual_review" or pair_status == "manual_review":
        return "manual_review"
    if current_status == "low_confidence" or pair_status == "low_confidence":
        return "low_confidence"
    return "ok"


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
