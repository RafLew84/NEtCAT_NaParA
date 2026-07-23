"""Directional molecular-orientation estimates from STM topography patches."""

from __future__ import annotations

from dataclasses import dataclass
from math import isclose, isfinite
from typing import Literal

import numpy as np
from scipy.ndimage import binary_dilation, binary_erosion

from ._molecular_orientation_contract import finite_float as _finite_float
from ._molecular_orientation_geometry import (
    binary_mask as _binary_mask,
    orientation_context as _orientation_context,
    periodic_axis_distance as _axis_distance,
    positive_pair as _positive_pair,
)
from .molecular_orientation_models import (
    MolecularOrientationMeasurement,
    MolecularOrientationProvenance,
)


MolecularTopographyOrientationRejectionReason = Literal[
    "insufficient_mask_area",
    "insufficient_context",
    "insufficient_mask_interior",
    "insufficient_intensity_variation",
    "insufficient_gradient_energy",
    "insufficient_directional_margin",
]
_REJECTION_REASONS = {
    "insufficient_mask_area",
    "insufficient_context",
    "insufficient_mask_interior",
    "insufficient_intensity_variation",
    "insufficient_gradient_energy",
    "insufficient_directional_margin",
}


@dataclass(frozen=True)
class MolecularTopographyOrientationSettings:
    """Sampling and acceptance settings for the STM directional descriptor."""

    min_mask_area_px: int = 9
    context_radius_px: int = 3
    gradient_erosion_px: int = 1
    min_gradient_support_px: int = 9
    angle_step_deg: float = 2.0
    competitor_separation_deg: float = 25.0
    min_directional_confidence: float = 0.05
    normalization_lower_percentile: float = 5.0
    normalization_upper_percentile: float = 95.0
    normalization_clip: float = 5.0

    def __post_init__(self) -> None:
        min_mask_area = _strict_integer(
            self.min_mask_area_px,
            "min_mask_area_px",
        )
        context_radius = _strict_integer(
            self.context_radius_px,
            "context_radius_px",
        )
        erosion = _strict_integer(
            self.gradient_erosion_px,
            "gradient_erosion_px",
        )
        min_gradient_support = _strict_integer(
            self.min_gradient_support_px,
            "min_gradient_support_px",
        )
        if min_mask_area < 3:
            raise ValueError("min_mask_area_px must be at least 3.")
        if context_radius < 1:
            raise ValueError("context_radius_px must be positive.")
        if erosion < 0:
            raise ValueError("gradient_erosion_px must be non-negative.")
        if min_gradient_support < 3:
            raise ValueError("min_gradient_support_px must be at least 3.")
        angle_step = _finite_float(self.angle_step_deg, "angle_step_deg")
        bin_count = 180.0 / angle_step if angle_step > 0.0 else 0.0
        rounded_bin_count = int(round(bin_count))
        if (
            angle_step <= 0.0
            or bin_count < 12.0
            or not isclose(
                bin_count,
                rounded_bin_count,
                rel_tol=0.0,
                abs_tol=1e-12,
            )
        ):
            raise ValueError(
                "angle_step_deg must divide 180 degrees into at least 12 bins."
            )
        competitor_separation = _finite_float(
            self.competitor_separation_deg,
            "competitor_separation_deg",
        )
        maximum_sampled_distance = (
            rounded_bin_count // 2
        ) * angle_step
        if not (
            angle_step
            <= competitor_separation
            <= maximum_sampled_distance
        ):
            raise ValueError(
                "competitor_separation_deg must select at least one sampled "
                "competitor outside the best-angle neighborhood."
            )
        min_confidence = _finite_float(
            self.min_directional_confidence,
            "min_directional_confidence",
        )
        if not 0.0 < min_confidence < 1.0:
            raise ValueError("min_directional_confidence must lie in (0, 1).")
        lower = _finite_float(
            self.normalization_lower_percentile,
            "normalization_lower_percentile",
        )
        upper = _finite_float(
            self.normalization_upper_percentile,
            "normalization_upper_percentile",
        )
        if not 0.0 <= lower < upper <= 100.0:
            raise ValueError("Normalization percentiles must be ordered in [0, 100].")
        clip = _finite_float(self.normalization_clip, "normalization_clip")
        if clip <= 0.0:
            raise ValueError("normalization_clip must be positive.")
        object.__setattr__(self, "min_mask_area_px", min_mask_area)
        object.__setattr__(self, "context_radius_px", context_radius)
        object.__setattr__(self, "gradient_erosion_px", erosion)
        object.__setattr__(
            self,
            "min_gradient_support_px",
            min_gradient_support,
        )
        object.__setattr__(self, "angle_step_deg", angle_step)
        object.__setattr__(
            self,
            "competitor_separation_deg",
            competitor_separation,
        )
        object.__setattr__(
            self,
            "min_directional_confidence",
            min_confidence,
        )
        object.__setattr__(self, "normalization_lower_percentile", lower)
        object.__setattr__(self, "normalization_upper_percentile", upper)
        object.__setattr__(self, "normalization_clip", clip)


@dataclass(frozen=True)
class MolecularTopographyOrientationScoreCurve:
    """Directional score sampled over one 180-degree axis period."""

    angles_deg: tuple[float, ...]
    scores: tuple[float, ...]
    periodicity_deg: float = 180.0

    def __post_init__(self) -> None:
        angles = tuple(
            _finite_float(value, "angles_deg")
            for value in self.angles_deg
        )
        scores = tuple(_unit_interval(value, "scores") for value in self.scores)
        if len(angles) != len(scores):
            raise ValueError("Score-curve angles and scores must align.")
        if self.periodicity_deg != 180.0:
            raise ValueError("Topography score curve must have 180-degree periodicity.")
        if angles:
            if angles[0] != 0.0:
                raise ValueError("Topography score curve must start at 0 degrees.")
            if len(angles) < 12:
                raise ValueError(
                    "Topography score curve must cover a complete axis period."
                )
            if any(
                not 0.0 <= angle < self.periodicity_deg
                for angle in angles
            ):
                raise ValueError("Score-curve angles must lie in [0, 180).")
            if any(right <= left for left, right in zip(angles, angles[1:])):
                raise ValueError("Score-curve angles must be strictly increasing.")
            step = angles[1] - angles[0]
            if any(
                not isclose(
                    right - left,
                    step,
                    rel_tol=1e-12,
                    abs_tol=1e-12,
                )
                for left, right in zip(angles, angles[1:])
            ):
                raise ValueError("Score-curve angles must use uniform sampling.")
            if not isclose(
                angles[-1] + step,
                self.periodicity_deg,
                rel_tol=1e-12,
                abs_tol=1e-12,
            ):
                raise ValueError(
                    "Topography score curve must cover a complete axis period."
                )
        object.__setattr__(self, "angles_deg", angles)
        object.__setattr__(self, "scores", scores)

    @property
    def best_angle_deg(self) -> float | None:
        if not self.scores:
            return None
        return self.angles_deg[int(np.argmax(self.scores))]


@dataclass(frozen=True)
class MolecularTopographyOrientationResult:
    """Topography estimate and all diagnostics used for acceptance."""

    measurement: MolecularOrientationMeasurement
    score_curve: MolecularTopographyOrientationScoreCurve
    settings: MolecularTopographyOrientationSettings
    mask_area_px: int
    context_area_px: int
    gradient_support_area_px: int
    pixel_size_nm_xy: tuple[float, float]
    scan_angle_deg: float | None
    background_plane_coefficients: tuple[float, float, float] | None
    normalization_center: float | None
    normalization_scale: float | None
    best_score: float | None
    competitor_score: float | None
    score_margin: float | None
    directional_confidence: float | None
    rejection_reason: MolecularTopographyOrientationRejectionReason | None
    coordinate_frame: str

    def __post_init__(self) -> None:
        if not isinstance(self.measurement, MolecularOrientationMeasurement):
            raise TypeError("measurement must be MolecularOrientationMeasurement.")
        if not isinstance(
            self.score_curve,
            MolecularTopographyOrientationScoreCurve,
        ):
            raise TypeError(
                "score_curve must be MolecularTopographyOrientationScoreCurve."
            )
        if not isinstance(self.settings, MolecularTopographyOrientationSettings):
            raise TypeError("settings must be MolecularTopographyOrientationSettings.")
        if self.measurement.method != "stm_topography":
            raise ValueError("Topography result requires method='stm_topography'.")
        if self.measurement.periodicity_deg != 180.0:
            raise ValueError("Topography orientation periodicity must be 180 degrees.")
        areas = (
            _non_negative_integer(self.mask_area_px, "mask_area_px"),
            _non_negative_integer(self.context_area_px, "context_area_px"),
            _non_negative_integer(
                self.gradient_support_area_px,
                "gradient_support_area_px",
            ),
        )
        patch_height, patch_width = self.measurement.patch_shape_px
        patch_area = patch_height * patch_width
        if any(area > patch_area for area in areas):
            raise ValueError("Topography result areas cannot exceed patch area.")
        if not areas[2] <= areas[0] <= areas[1]:
            raise ValueError(
                "Gradient support, molecule mask, and context areas must be nested."
            )
        pixel_size = _positive_pair(
            self.pixel_size_nm_xy,
            "pixel_size_nm_xy",
        )
        scan_angle = (
            None
            if self.scan_angle_deg is None
            else _finite_float(self.scan_angle_deg, "scan_angle_deg")
        )
        plane = _optional_finite_triplet(
            self.background_plane_coefficients,
            "background_plane_coefficients",
        )
        center = _optional_finite(
            self.normalization_center,
            "normalization_center",
        )
        scale = _optional_positive(
            self.normalization_scale,
            "normalization_scale",
        )
        best = _optional_unit_interval(self.best_score, "best_score")
        competitor = _optional_unit_interval(
            self.competitor_score,
            "competitor_score",
        )
        margin = _optional_unit_interval(self.score_margin, "score_margin")
        confidence = _optional_unit_interval(
            self.directional_confidence,
            "directional_confidence",
        )
        if self.coordinate_frame not in {"image_xy", "sample_nm"}:
            raise ValueError("Unsupported topography coordinate_frame.")
        if (self.coordinate_frame == "image_xy") != (scan_angle is None):
            raise ValueError(
                "scan_angle_deg must be absent only for image coordinates."
            )
        expected_reference = (
            "sample_x_axis_counterclockwise"
            if self.coordinate_frame == "sample_nm"
            else "image_x_axis_counterclockwise"
        )
        if self.measurement.provenance.orientation_reference != expected_reference:
            raise ValueError(
                "coordinate_frame must agree with provenance orientation_reference."
            )
        score_metrics = (best, competitor, margin, confidence)
        if self.score_curve.scores:
            if center is None or scale is None or plane is None:
                raise ValueError(
                    "Scored topography results require detrending and "
                    "normalization diagnostics."
                )
            score_step = (
                self.score_curve.angles_deg[1]
                - self.score_curve.angles_deg[0]
            )
            if not isclose(
                score_step,
                self.settings.angle_step_deg,
                rel_tol=1e-12,
                abs_tol=1e-12,
            ):
                raise ValueError("Score curve must use the configured angle step.")
            if any(value is None for value in score_metrics):
                raise ValueError("Non-empty score curve requires complete score metrics.")
            expected_best = max(self.score_curve.scores)
            if not isclose(best, expected_best, abs_tol=1e-12):
                raise ValueError("best_score must match the score curve.")
            if competitor > best:
                raise ValueError("competitor_score must not exceed best_score.")
            best_angle = self.score_curve.best_angle_deg
            distances = tuple(
                _axis_distance(angle, best_angle)
                for angle in self.score_curve.angles_deg
            )
            eligible_scores = tuple(
                score
                for score, distance in zip(
                    self.score_curve.scores,
                    distances,
                )
                if distance >= self.settings.competitor_separation_deg
            )
            expected_competitor = max(eligible_scores)
            if not isclose(
                competitor,
                expected_competitor,
                rel_tol=1e-12,
                abs_tol=1e-12,
            ):
                raise ValueError(
                    "competitor_score must match the configured score competitor."
                )
            if not isclose(margin, best - competitor, abs_tol=1e-12):
                raise ValueError("score_margin must equal best minus competitor.")
            expected_confidence = 0.0 if best <= 0.0 else margin / best
            if not isclose(confidence, expected_confidence, abs_tol=1e-12):
                raise ValueError("directional_confidence must match score margin.")
        elif any(value is not None for value in score_metrics):
            raise ValueError("Empty score curve must not contain score metrics.")
        status = self.measurement.status
        if (
            self.rejection_reason is not None
            and self.rejection_reason not in _REJECTION_REASONS
        ):
            raise ValueError("Unsupported topography rejection_reason.")
        if status == "available":
            if self.rejection_reason is not None:
                raise ValueError("Available topography result cannot be rejected.")
            if not self.score_curve.scores:
                raise ValueError("Available topography result requires a score curve.")
            if self.measurement.angle_deg is None or self.measurement.confidence is None:
                raise ValueError("Available topography result requires angle and confidence.")
            if not isclose(
                self.measurement.angle_deg,
                self.score_curve.best_angle_deg,
                abs_tol=1e-12,
            ):
                raise ValueError("Measurement angle must match the best score angle.")
            if not isclose(
                self.measurement.confidence,
                confidence,
                abs_tol=1e-12,
            ):
                raise ValueError("Measurement confidence must match score confidence.")
            if confidence < self.settings.min_directional_confidence:
                raise ValueError(
                    "Available result must meet min_directional_confidence."
                )
        elif status == "unavailable":
            if self.rejection_reason is None:
                raise ValueError("Unavailable topography result requires a reason.")
        else:
            raise ValueError("Topography estimator does not emit ambiguous results.")
        if self.rejection_reason == "insufficient_directional_margin":
            if not self.score_curve.scores:
                raise ValueError(
                    "Directional-margin rejection requires a score curve."
                )
            if confidence >= self.settings.min_directional_confidence:
                raise ValueError(
                    "Directional-margin rejection must remain below confidence threshold."
                )
        elif self.rejection_reason is not None and self.score_curve.scores:
            raise ValueError(
                "Pre-score topography rejection must have an empty score curve."
            )
        object.__setattr__(self, "mask_area_px", areas[0])
        object.__setattr__(self, "context_area_px", areas[1])
        object.__setattr__(self, "gradient_support_area_px", areas[2])
        object.__setattr__(self, "pixel_size_nm_xy", pixel_size)
        object.__setattr__(self, "scan_angle_deg", scan_angle)
        object.__setattr__(
            self,
            "background_plane_coefficients",
            plane,
        )
        object.__setattr__(self, "normalization_center", center)
        object.__setattr__(self, "normalization_scale", scale)
        object.__setattr__(self, "best_score", best)
        object.__setattr__(self, "competitor_score", competitor)
        object.__setattr__(self, "score_margin", margin)
        object.__setattr__(self, "directional_confidence", confidence)


def estimate_molecular_orientation_from_topography(
    topography_patch: object,
    molecule_mask: object,
    *,
    measurement_id: str,
    provenance: MolecularOrientationProvenance,
    pixel_size_nm_xy: tuple[float, float],
    scan_angle_deg: float | None,
    valid_fov_mask: object,
    settings: MolecularTopographyOrientationSettings | None = None,
) -> MolecularTopographyOrientationResult:
    """Estimate an internal molecular axis from normalized STM gradients."""

    if not isinstance(provenance, MolecularOrientationProvenance):
        raise TypeError("provenance must be MolecularOrientationProvenance.")
    mask = _binary_mask(molecule_mask, "molecule_mask")
    valid_fov = _binary_mask(valid_fov_mask, "valid_fov_mask")
    if mask.shape != valid_fov.shape:
        raise ValueError("molecule_mask and valid_fov_mask must have matching shapes.")
    topography = _topography_array(topography_patch)
    if topography.shape != mask.shape:
        raise ValueError("topography_patch must match molecule_mask shape.")
    if np.any(mask & ~valid_fov):
        raise ValueError("molecule_mask contains pixels outside valid_fov_mask.")
    pixel_size_x, pixel_size_y = _positive_pair(
        pixel_size_nm_xy,
        "pixel_size_nm_xy",
    )
    estimator_settings = (
        MolecularTopographyOrientationSettings()
        if settings is None
        else settings
    )
    if not isinstance(
        estimator_settings,
        MolecularTopographyOrientationSettings,
    ):
        raise TypeError("settings must be MolecularTopographyOrientationSettings.")
    coordinate_frame, rotation_deg = _orientation_context(
        provenance,
        scan_angle_deg=scan_angle_deg,
    )
    mask_area = int(np.count_nonzero(mask))
    empty_curve = MolecularTopographyOrientationScoreCurve((), ())
    if mask_area < estimator_settings.min_mask_area_px:
        return _unavailable_result(
            measurement_id=measurement_id,
            provenance=provenance,
            patch_shape=mask.shape,
            score_curve=empty_curve,
            settings=estimator_settings,
            mask_area_px=mask_area,
            context_area_px=0,
            gradient_support_area_px=0,
            rejection_reason="insufficient_mask_area",
            coordinate_frame=coordinate_frame,
            pixel_size_nm_xy=(pixel_size_x, pixel_size_y),
            scan_angle_deg=scan_angle_deg,
        )

    context, complete_context = _context_region(
        mask,
        radius=estimator_settings.context_radius_px,
    )
    context_area = int(np.count_nonzero(context))
    if (
        not complete_context
        or np.any(context & ~valid_fov)
        or not np.all(np.isfinite(topography[context]))
    ):
        return _unavailable_result(
            measurement_id=measurement_id,
            provenance=provenance,
            patch_shape=mask.shape,
            score_curve=empty_curve,
            settings=estimator_settings,
            mask_area_px=mask_area,
            context_area_px=context_area,
            gradient_support_area_px=0,
            rejection_reason="insufficient_context",
            coordinate_frame=coordinate_frame,
            pixel_size_nm_xy=(pixel_size_x, pixel_size_y),
            scan_angle_deg=scan_angle_deg,
        )

    if estimator_settings.gradient_erosion_px == 0:
        gradient_support = mask.copy()
    else:
        gradient_support = binary_erosion(
            mask,
            iterations=estimator_settings.gradient_erosion_px,
            border_value=0,
        )
    gradient_support_area = int(np.count_nonzero(gradient_support))
    if gradient_support_area < estimator_settings.min_gradient_support_px:
        return _unavailable_result(
            measurement_id=measurement_id,
            provenance=provenance,
            patch_shape=mask.shape,
            score_curve=empty_curve,
            settings=estimator_settings,
            mask_area_px=mask_area,
            context_area_px=context_area,
            gradient_support_area_px=gradient_support_area,
            rejection_reason="insufficient_mask_interior",
            coordinate_frame=coordinate_frame,
            pixel_size_nm_xy=(pixel_size_x, pixel_size_y),
            scan_angle_deg=scan_angle_deg,
        )

    background_ring = context & ~mask
    plane = _fit_background_plane(
        topography,
        background_ring,
        pixel_size_nm_xy=(pixel_size_x, pixel_size_y),
    )
    if plane is None:
        return _unavailable_result(
            measurement_id=measurement_id,
            provenance=provenance,
            patch_shape=mask.shape,
            score_curve=empty_curve,
            settings=estimator_settings,
            mask_area_px=mask_area,
            context_area_px=context_area,
            gradient_support_area_px=gradient_support_area,
            rejection_reason="insufficient_context",
            coordinate_frame=coordinate_frame,
            pixel_size_nm_xy=(pixel_size_x, pixel_size_y),
            scan_angle_deg=scan_angle_deg,
        )
    detrended = _subtract_background_plane(
        topography,
        plane,
        pixel_size_nm_xy=(pixel_size_x, pixel_size_y),
    )
    context_values = np.asarray(detrended[context], dtype=np.float64)
    center = float(np.median(context_values))
    lower, upper = np.percentile(
        context_values,
        (
            estimator_settings.normalization_lower_percentile,
            estimator_settings.normalization_upper_percentile,
        ),
    )
    scale = float(upper - lower)
    raw_context_values = np.asarray(topography[context], dtype=np.float64)
    numerical_floor = (
        np.finfo(np.float64).eps
        * max(float(np.max(np.abs(raw_context_values))), np.finfo(np.float64).tiny)
        * 128.0
    )
    if not isfinite(scale) or scale <= numerical_floor:
        return _unavailable_result(
            measurement_id=measurement_id,
            provenance=provenance,
            patch_shape=mask.shape,
            score_curve=empty_curve,
            settings=estimator_settings,
            mask_area_px=mask_area,
            context_area_px=context_area,
            gradient_support_area_px=gradient_support_area,
            rejection_reason="insufficient_intensity_variation",
            coordinate_frame=coordinate_frame,
            pixel_size_nm_xy=(pixel_size_x, pixel_size_y),
            scan_angle_deg=scan_angle_deg,
            background_plane_coefficients=plane,
            normalization_center=center,
        )
    normalized = np.zeros(mask.shape, dtype=np.float64)
    normalized[context] = np.clip(
        (detrended[context] - center) / scale,
        -estimator_settings.normalization_clip,
        estimator_settings.normalization_clip,
    )
    gradient_rows, gradient_columns = np.gradient(normalized)
    local_gradient_x = gradient_columns / pixel_size_x
    local_gradient_y = -gradient_rows / pixel_size_y
    rotation_rad = np.deg2rad(rotation_deg)
    cosine = float(np.cos(rotation_rad))
    sine = float(np.sin(rotation_rad))
    gradient_x = cosine * local_gradient_x - sine * local_gradient_y
    gradient_y = sine * local_gradient_x + cosine * local_gradient_y
    gx = gradient_x[gradient_support]
    gy = gradient_y[gradient_support]
    total_energy = float(np.sum(gx * gx + gy * gy))
    if not isfinite(total_energy) or total_energy <= 0.0:
        return _unavailable_result(
            measurement_id=measurement_id,
            provenance=provenance,
            patch_shape=mask.shape,
            score_curve=empty_curve,
            settings=estimator_settings,
            mask_area_px=mask_area,
            context_area_px=context_area,
            gradient_support_area_px=gradient_support_area,
            rejection_reason="insufficient_gradient_energy",
            coordinate_frame=coordinate_frame,
            pixel_size_nm_xy=(pixel_size_x, pixel_size_y),
            scan_angle_deg=scan_angle_deg,
            background_plane_coefficients=plane,
            normalization_center=center,
            normalization_scale=scale,
        )

    angle_bin_count = int(
        round(180.0 / estimator_settings.angle_step_deg)
    )
    angles = (
        np.arange(angle_bin_count, dtype=np.float64)
        * estimator_settings.angle_step_deg
    )
    angles_rad = np.deg2rad(angles)
    normal_x = -np.sin(angles_rad)
    normal_y = np.cos(angles_rad)
    projections = (
        gx[:, np.newaxis] * normal_x[np.newaxis, :]
        + gy[:, np.newaxis] * normal_y[np.newaxis, :]
    )
    scores_array = np.sum(projections * projections, axis=0) / total_energy
    scores_array = np.clip(scores_array, 0.0, 1.0)
    score_curve = MolecularTopographyOrientationScoreCurve(
        angles_deg=tuple(float(value) for value in angles),
        scores=tuple(float(value) for value in scores_array),
    )
    best_index = int(np.argmax(scores_array))
    best_angle = float(angles[best_index])
    best_score = float(scores_array[best_index])
    distances = np.minimum(
        np.abs(angles - best_angle),
        180.0 - np.abs(angles - best_angle),
    )
    competitor_mask = (
        distances >= estimator_settings.competitor_separation_deg
    )
    if not np.any(competitor_mask):
        raise RuntimeError(
            "Validated topography settings produced no score competitor."
        )
    competitor_score = float(np.max(scores_array[competitor_mask]))
    score_margin = max(0.0, best_score - competitor_score)
    confidence = 0.0 if best_score <= 0.0 else score_margin / best_score
    accepted = confidence >= estimator_settings.min_directional_confidence
    measurement = MolecularOrientationMeasurement(
        measurement_id=measurement_id,
        status="available" if accepted else "unavailable",
        angle_deg=best_angle if accepted else None,
        periodicity_deg=180.0,
        confidence=confidence if accepted else None,
        method="stm_topography",
        patch_shape_px=(int(mask.shape[0]), int(mask.shape[1])),
        provenance=provenance,
    )
    return MolecularTopographyOrientationResult(
        measurement=measurement,
        score_curve=score_curve,
        settings=estimator_settings,
        mask_area_px=mask_area,
        context_area_px=context_area,
        gradient_support_area_px=gradient_support_area,
        pixel_size_nm_xy=(pixel_size_x, pixel_size_y),
        scan_angle_deg=scan_angle_deg,
        background_plane_coefficients=plane,
        normalization_center=center,
        normalization_scale=scale,
        best_score=best_score,
        competitor_score=competitor_score,
        score_margin=score_margin,
        directional_confidence=confidence,
        rejection_reason=(
            None if accepted else "insufficient_directional_margin"
        ),
        coordinate_frame=coordinate_frame,
    )


def _unavailable_result(
    *,
    measurement_id: str,
    provenance: MolecularOrientationProvenance,
    patch_shape: tuple[int, int],
    score_curve: MolecularTopographyOrientationScoreCurve,
    settings: MolecularTopographyOrientationSettings,
    mask_area_px: int,
    context_area_px: int,
    gradient_support_area_px: int,
    rejection_reason: MolecularTopographyOrientationRejectionReason,
    coordinate_frame: str,
    pixel_size_nm_xy: tuple[float, float],
    scan_angle_deg: float | None,
    background_plane_coefficients: tuple[float, float, float] | None = None,
    normalization_center: float | None = None,
    normalization_scale: float | None = None,
) -> MolecularTopographyOrientationResult:
    measurement = MolecularOrientationMeasurement(
        measurement_id=measurement_id,
        status="unavailable",
        angle_deg=None,
        periodicity_deg=180.0,
        confidence=None,
        method="stm_topography",
        patch_shape_px=(int(patch_shape[0]), int(patch_shape[1])),
        provenance=provenance,
    )
    return MolecularTopographyOrientationResult(
        measurement=measurement,
        score_curve=score_curve,
        settings=settings,
        mask_area_px=mask_area_px,
        context_area_px=context_area_px,
        gradient_support_area_px=gradient_support_area_px,
        pixel_size_nm_xy=pixel_size_nm_xy,
        scan_angle_deg=scan_angle_deg,
        background_plane_coefficients=background_plane_coefficients,
        normalization_center=normalization_center,
        normalization_scale=normalization_scale,
        best_score=None,
        competitor_score=None,
        score_margin=None,
        directional_confidence=None,
        rejection_reason=rejection_reason,
        coordinate_frame=coordinate_frame,
    )


def _context_region(mask: np.ndarray, *, radius: int) -> tuple[np.ndarray, bool]:
    padded = np.pad(mask, radius, mode="constant", constant_values=False)
    dilated = binary_dilation(padded, iterations=radius)
    height, width = mask.shape
    context = np.asarray(
        dilated[radius : radius + height, radius : radius + width],
        dtype=bool,
    )
    complete = int(np.count_nonzero(context)) == int(np.count_nonzero(dilated))
    return context, complete


def _fit_background_plane(
    topography: np.ndarray,
    background_ring: np.ndarray,
    *,
    pixel_size_nm_xy: tuple[float, float],
) -> tuple[float, float, float] | None:
    rows, columns = np.nonzero(background_ring)
    if rows.size < 3:
        return None
    pixel_size_x, pixel_size_y = pixel_size_nm_xy
    coordinates = np.column_stack(
        (
            np.ones(rows.size, dtype=np.float64),
            columns.astype(np.float64) * pixel_size_x,
            -rows.astype(np.float64) * pixel_size_y,
        )
    )
    coefficients, _, rank, _ = np.linalg.lstsq(
        coordinates,
        np.asarray(topography[background_ring], dtype=np.float64),
        rcond=None,
    )
    if rank != 3 or not np.all(np.isfinite(coefficients)):
        return None
    return tuple(float(value) for value in coefficients)


def _subtract_background_plane(
    topography: np.ndarray,
    coefficients: tuple[float, float, float],
    *,
    pixel_size_nm_xy: tuple[float, float],
) -> np.ndarray:
    rows, columns = np.indices(topography.shape, dtype=np.float64)
    pixel_size_x, pixel_size_y = pixel_size_nm_xy
    intercept, slope_x, slope_y = coefficients
    plane = (
        intercept
        + slope_x * columns * pixel_size_x
        + slope_y * (-rows * pixel_size_y)
    )
    return np.asarray(topography, dtype=np.float64) - plane


def _topography_array(value: object) -> np.ndarray:
    try:
        array = np.asarray(value)
    except (TypeError, ValueError) as exc:
        raise TypeError("topography_patch must be a numeric 2D array.") from exc
    if array.ndim != 2:
        raise ValueError("topography_patch must be a two-dimensional array.")
    if not (
        np.issubdtype(array.dtype, np.integer)
        or np.issubdtype(array.dtype, np.floating)
    ):
        raise TypeError("topography_patch must contain real numeric values.")
    return np.asarray(array, dtype=np.float64)


def _strict_integer(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer.")
    return value


def _non_negative_integer(value: object, field_name: str) -> int:
    normalized = _strict_integer(value, field_name)
    if normalized < 0:
        raise ValueError(f"{field_name} must be non-negative.")
    return normalized


def _unit_interval(value: object, field_name: str) -> float:
    normalized = _finite_float(value, field_name)
    if not 0.0 <= normalized <= 1.0:
        raise ValueError(f"{field_name} must lie in [0, 1].")
    return normalized


def _optional_unit_interval(value: object, field_name: str) -> float | None:
    if value is None:
        return None
    return _unit_interval(value, field_name)


def _optional_finite(value: object, field_name: str) -> float | None:
    if value is None:
        return None
    return _finite_float(value, field_name)


def _optional_positive(value: object, field_name: str) -> float | None:
    if value is None:
        return None
    normalized = _finite_float(value, field_name)
    if normalized <= 0.0:
        raise ValueError(f"{field_name} must be positive.")
    return normalized


def _optional_finite_triplet(
    value: object,
    field_name: str,
) -> tuple[float, float, float] | None:
    if value is None:
        return None
    if not isinstance(value, (tuple, list)) or len(value) != 3:
        raise TypeError(f"{field_name} must contain three values.")
    return tuple(
        _finite_float(item, f"{field_name}[{index}]")
        for index, item in enumerate(value)
    )
