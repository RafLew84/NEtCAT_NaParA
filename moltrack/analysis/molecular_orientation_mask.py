"""Principal-axis orientation estimates from molecular segmentation masks."""

from __future__ import annotations

from dataclasses import dataclass
from math import atan2, degrees, isclose, isfinite
from typing import Literal

import numpy as np

from ._molecular_orientation_contract import finite_float as _finite_float
from .molecular_orientation_models import (
    MolecularOrientationMeasurement,
    MolecularOrientationProvenance,
)


MolecularMaskOrientationRejectionReason = Literal[
    "insufficient_mask_area",
    "degenerate_covariance",
    "insufficient_anisotropy",
    "valid_fov_edge_truncation",
]


@dataclass(frozen=True)
class MolecularMaskOrientationSettings:
    """Thresholds for accepting a mask-derived principal axis."""

    min_mask_area_px: int = 9
    min_anisotropy: float = 0.15
    edge_confidence_scale: float = 0.5

    def __post_init__(self) -> None:
        if isinstance(self.min_mask_area_px, bool) or not isinstance(
            self.min_mask_area_px,
            int,
        ):
            raise TypeError("min_mask_area_px must be an integer.")
        if self.min_mask_area_px < 3:
            raise ValueError("min_mask_area_px must be at least 3.")
        min_anisotropy = _finite_float(self.min_anisotropy, "min_anisotropy")
        if not 0.0 < min_anisotropy < 1.0:
            raise ValueError("min_anisotropy must lie in (0, 1).")
        edge_scale = _finite_float(
            self.edge_confidence_scale,
            "edge_confidence_scale",
        )
        if not 0.0 <= edge_scale <= 1.0:
            raise ValueError("edge_confidence_scale must lie in [0, 1].")
        object.__setattr__(self, "min_anisotropy", min_anisotropy)
        object.__setattr__(self, "edge_confidence_scale", edge_scale)


@dataclass(frozen=True)
class MolecularMaskOrientationResult:
    """Mask estimate with the diagnostics needed to audit acceptance."""

    measurement: MolecularOrientationMeasurement
    mask_area_px: int
    anisotropy: float | None
    principal_variance_nm2: float | None
    minor_variance_nm2: float | None
    edge_truncated_qc: bool
    rejection_reason: MolecularMaskOrientationRejectionReason | None
    coordinate_frame: str

    def __post_init__(self) -> None:
        if not isinstance(self.measurement, MolecularOrientationMeasurement):
            raise TypeError("measurement must be MolecularOrientationMeasurement.")
        if isinstance(self.mask_area_px, bool) or not isinstance(
            self.mask_area_px,
            int,
        ):
            raise TypeError("mask_area_px must be an integer.")
        if self.mask_area_px < 0:
            raise ValueError("mask_area_px must be non-negative.")
        patch_height, patch_width = self.measurement.patch_shape_px
        if self.mask_area_px > patch_height * patch_width:
            raise ValueError("mask_area_px cannot exceed the measurement patch area.")
        anisotropy = _optional_unit_interval(self.anisotropy, "anisotropy")
        principal = _optional_non_negative(
            self.principal_variance_nm2,
            "principal_variance_nm2",
        )
        minor = _optional_non_negative(
            self.minor_variance_nm2,
            "minor_variance_nm2",
        )
        if (principal is None) != (minor is None):
            raise ValueError("Principal and minor variances must be present together.")
        if principal is not None and principal < minor:
            raise ValueError("principal_variance_nm2 must not be less than minor variance.")
        if anisotropy is not None:
            if principal is None or minor is None:
                raise ValueError("anisotropy requires principal and minor variances.")
            variance_sum = principal + minor
            if variance_sum <= 0.0:
                raise ValueError("PCA variances must have a positive sum.")
            expected_anisotropy = (principal - minor) / variance_sum
            if not isclose(
                anisotropy,
                expected_anisotropy,
                rel_tol=1e-12,
                abs_tol=1e-12,
            ):
                raise ValueError("anisotropy must agree with the PCA variances.")
        if not isinstance(self.edge_truncated_qc, bool):
            raise TypeError("edge_truncated_qc must be a boolean.")
        if self.coordinate_frame not in {"image_xy", "sample_nm"}:
            raise ValueError("Unsupported molecular orientation coordinate_frame.")
        if self.measurement.method != "mask_principal_axis":
            raise ValueError(
                "Mask orientation result requires method='mask_principal_axis'."
            )
        if self.measurement.periodicity_deg != 180.0:
            raise ValueError("Mask principal-axis periodicity must be 180 degrees.")
        expected_reference = (
            "sample_x_axis_counterclockwise"
            if self.coordinate_frame == "sample_nm"
            else "image_x_axis_counterclockwise"
        )
        if self.measurement.provenance.orientation_reference != expected_reference:
            raise ValueError(
                "coordinate_frame must agree with provenance orientation_reference."
            )
        allowed_reasons = {
            None,
            "insufficient_mask_area",
            "degenerate_covariance",
            "insufficient_anisotropy",
            "valid_fov_edge_truncation",
        }
        if self.rejection_reason not in allowed_reasons:
            raise ValueError("Unsupported molecular mask rejection_reason.")
        status = self.measurement.status
        if status in {"available", "ambiguous"} and self.mask_area_px == 0:
            raise ValueError("Available or ambiguous result requires a non-empty mask.")
        if status in {"available", "ambiguous"} and (
            anisotropy is None or principal is None or minor is None
        ):
            raise ValueError(
                "Available or ambiguous mask orientation requires PCA diagnostics."
            )
        if status == "ambiguous" and (
            self.measurement.angle_deg is None
            or self.measurement.confidence is None
        ):
            raise ValueError(
                "Ambiguous mask orientation requires angle and confidence."
            )
        if status == "available" and self.rejection_reason is not None:
            raise ValueError("Available mask orientation must not have a rejection reason.")
        if status == "available" and self.edge_truncated_qc:
            raise ValueError("Available mask orientation cannot have edge_truncated_qc.")
        if (
            status == "ambiguous"
            and self.rejection_reason != "valid_fov_edge_truncation"
        ):
            raise ValueError("Ambiguous mask orientation must identify edge truncation.")
        if status == "unavailable" and self.rejection_reason not in {
            "insufficient_mask_area",
            "degenerate_covariance",
            "insufficient_anisotropy",
        }:
            raise ValueError("Unavailable mask orientation requires a rejection reason.")
        if self.rejection_reason in {
            "insufficient_mask_area",
            "degenerate_covariance",
        } and any(
            value is not None for value in (anisotropy, principal, minor)
        ):
            raise ValueError(
                f"{self.rejection_reason} must not contain PCA diagnostics."
            )
        if self.rejection_reason == "insufficient_anisotropy" and (
            anisotropy is None or principal is None or minor is None
        ):
            raise ValueError(
                "insufficient_anisotropy requires complete PCA diagnostics."
            )
        if (
            self.rejection_reason == "valid_fov_edge_truncation"
            and not self.edge_truncated_qc
        ):
            raise ValueError("Edge-truncation rejection requires edge_truncated_qc.")
        object.__setattr__(self, "anisotropy", anisotropy)
        object.__setattr__(self, "principal_variance_nm2", principal)
        object.__setattr__(self, "minor_variance_nm2", minor)


def estimate_molecular_orientation_from_mask(
    mask: object,
    *,
    measurement_id: str,
    provenance: MolecularOrientationProvenance,
    pixel_size_nm_xy: tuple[float, float],
    scan_angle_deg: float | None,
    valid_fov_mask: object,
    settings: MolecularMaskOrientationSettings | None = None,
) -> MolecularMaskOrientationResult:
    """Estimate a molecular shape axis in image or canonical sample coordinates."""

    if not isinstance(provenance, MolecularOrientationProvenance):
        raise TypeError("provenance must be MolecularOrientationProvenance.")
    mask_array = _binary_mask(mask, "mask")
    if mask_array.shape[0] <= 0 or mask_array.shape[1] <= 0:
        raise ValueError("mask dimensions must be positive.")
    valid_fov = _binary_mask(valid_fov_mask, "valid_fov_mask")
    if valid_fov.shape != mask_array.shape:
        raise ValueError("valid_fov_mask must match the two-dimensional mask.")
    if np.any(mask_array & ~valid_fov):
        raise ValueError("mask contains active pixels outside valid_fov_mask.")
    pixel_size_x, pixel_size_y = _positive_pair(
        pixel_size_nm_xy,
        "pixel_size_nm_xy",
    )
    estimator_settings = (
        MolecularMaskOrientationSettings()
        if settings is None
        else settings
    )
    if not isinstance(estimator_settings, MolecularMaskOrientationSettings):
        raise TypeError("settings must be MolecularMaskOrientationSettings.")
    coordinate_frame, rotation_deg = _orientation_context(
        provenance,
        scan_angle_deg=scan_angle_deg,
    )
    area = int(np.count_nonzero(mask_array))
    edge_truncated = _touches_valid_fov_edge(mask_array, valid_fov)

    if area < estimator_settings.min_mask_area_px:
        return _unavailable_result(
            measurement_id=measurement_id,
            provenance=provenance,
            patch_shape=mask_array.shape,
            mask_area_px=area,
            edge_truncated_qc=edge_truncated,
            rejection_reason="insufficient_mask_area",
            coordinate_frame=coordinate_frame,
        )

    rows, columns = np.nonzero(mask_array)
    points = np.column_stack(
        (
            columns.astype(np.float64) * pixel_size_x,
            -rows.astype(np.float64) * pixel_size_y,
        )
    )
    centered = points - np.mean(points, axis=0, keepdims=True)
    covariance = centered.T @ centered / float(area)
    eigenvalues, eigenvectors = np.linalg.eigh(covariance)
    minor_variance = max(0.0, float(eigenvalues[0]))
    principal_variance = max(0.0, float(eigenvalues[1]))
    variance_sum = principal_variance + minor_variance
    if not isfinite(variance_sum) or variance_sum <= 0.0:
        return _unavailable_result(
            measurement_id=measurement_id,
            provenance=provenance,
            patch_shape=mask_array.shape,
            mask_area_px=area,
            edge_truncated_qc=edge_truncated,
            rejection_reason="degenerate_covariance",
            coordinate_frame=coordinate_frame,
        )
    anisotropy = float(
        np.clip(
            (principal_variance - minor_variance) / variance_sum,
            0.0,
            1.0,
        )
    )
    if anisotropy < estimator_settings.min_anisotropy:
        return _unavailable_result(
            measurement_id=measurement_id,
            provenance=provenance,
            patch_shape=mask_array.shape,
            mask_area_px=area,
            edge_truncated_qc=edge_truncated,
            rejection_reason="insufficient_anisotropy",
            coordinate_frame=coordinate_frame,
            anisotropy=anisotropy,
            principal_variance_nm2=principal_variance,
            minor_variance_nm2=minor_variance,
        )

    principal_axis = eigenvectors[:, 1]
    angle_deg = (
        degrees(atan2(float(principal_axis[1]), float(principal_axis[0])))
        + rotation_deg
    ) % 180.0
    confidence = float(
        np.clip(
            (anisotropy - estimator_settings.min_anisotropy)
            / (1.0 - estimator_settings.min_anisotropy),
            0.0,
            1.0,
        )
    )
    status = "ambiguous" if edge_truncated else "available"
    rejection_reason = "valid_fov_edge_truncation" if edge_truncated else None
    if edge_truncated:
        confidence *= estimator_settings.edge_confidence_scale
    measurement = MolecularOrientationMeasurement(
        measurement_id=measurement_id,
        status=status,
        angle_deg=angle_deg,
        periodicity_deg=180.0,
        confidence=confidence,
        method="mask_principal_axis",
        patch_shape_px=(int(mask_array.shape[0]), int(mask_array.shape[1])),
        provenance=provenance,
    )
    return MolecularMaskOrientationResult(
        measurement=measurement,
        mask_area_px=area,
        anisotropy=anisotropy,
        principal_variance_nm2=principal_variance,
        minor_variance_nm2=minor_variance,
        edge_truncated_qc=edge_truncated,
        rejection_reason=rejection_reason,
        coordinate_frame=coordinate_frame,
    )


def _unavailable_result(
    *,
    measurement_id: str,
    provenance: MolecularOrientationProvenance,
    patch_shape: tuple[int, int],
    mask_area_px: int,
    edge_truncated_qc: bool,
    rejection_reason: MolecularMaskOrientationRejectionReason,
    coordinate_frame: str,
    anisotropy: float | None = None,
    principal_variance_nm2: float | None = None,
    minor_variance_nm2: float | None = None,
) -> MolecularMaskOrientationResult:
    measurement = MolecularOrientationMeasurement(
        measurement_id=measurement_id,
        status="unavailable",
        angle_deg=None,
        periodicity_deg=180.0,
        confidence=None,
        method="mask_principal_axis",
        patch_shape_px=(int(patch_shape[0]), int(patch_shape[1])),
        provenance=provenance,
    )
    return MolecularMaskOrientationResult(
        measurement=measurement,
        mask_area_px=mask_area_px,
        anisotropy=anisotropy,
        principal_variance_nm2=principal_variance_nm2,
        minor_variance_nm2=minor_variance_nm2,
        edge_truncated_qc=edge_truncated_qc,
        rejection_reason=rejection_reason,
        coordinate_frame=coordinate_frame,
    )


def _orientation_context(
    provenance: MolecularOrientationProvenance,
    *,
    scan_angle_deg: float | None,
) -> tuple[str, float]:
    if scan_angle_deg is None:
        if provenance.orientation_reference != "image_x_axis_counterclockwise":
            raise ValueError(
                "Missing scan_angle_deg requires "
                "orientation_reference='image_x_axis_counterclockwise'."
            )
        return "image_xy", 0.0
    angle = _finite_float(scan_angle_deg, "scan_angle_deg")
    if provenance.orientation_reference != "sample_x_axis_counterclockwise":
        raise ValueError(
            "Known scan_angle_deg requires "
            "orientation_reference='sample_x_axis_counterclockwise'."
        )
    return "sample_nm", angle


def _touches_valid_fov_edge(mask: np.ndarray, valid_fov: np.ndarray) -> bool:
    if not np.any(mask):
        return False
    padded = np.pad(valid_fov, 1, mode="constant", constant_values=False)
    valid_interior = (
        valid_fov
        & padded[:-2, 1:-1]
        & padded[2:, 1:-1]
        & padded[1:-1, :-2]
        & padded[1:-1, 2:]
    )
    return bool(np.any(mask & ~valid_interior))


def _positive_pair(value: object, field_name: str) -> tuple[float, float]:
    if not isinstance(value, (tuple, list)) or len(value) != 2:
        raise TypeError(f"{field_name} must contain x and y.")
    first = _finite_float(value[0], f"{field_name}[0]")
    second = _finite_float(value[1], f"{field_name}[1]")
    if first <= 0.0 or second <= 0.0:
        raise ValueError(f"{field_name} values must be positive.")
    return first, second


def _binary_mask(value: object, field_name: str) -> np.ndarray:
    try:
        array = np.asarray(value)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"{field_name} must be a two-dimensional binary array.") from exc
    if array.ndim != 2:
        raise ValueError(f"{field_name} must be a two-dimensional array.")
    if array.dtype == np.bool_:
        return np.ascontiguousarray(array, dtype=bool)
    if not (
        np.issubdtype(array.dtype, np.integer)
        or np.issubdtype(array.dtype, np.floating)
    ):
        raise TypeError(f"{field_name} must contain binary numeric values.")
    numeric = np.asarray(array, dtype=np.float64)
    if not np.all(np.isfinite(numeric)):
        raise ValueError(f"{field_name} must contain only finite values.")
    if not np.all((numeric == 0.0) | (numeric == 1.0)):
        raise ValueError(f"{field_name} must contain only binary 0/1 values.")
    return np.ascontiguousarray(numeric, dtype=bool)


def _optional_unit_interval(value: object, field_name: str) -> float | None:
    if value is None:
        return None
    normalized = _finite_float(value, field_name)
    if not 0.0 <= normalized <= 1.0:
        raise ValueError(f"{field_name} must lie in [0, 1].")
    return normalized


def _optional_non_negative(value: object, field_name: str) -> float | None:
    if value is None:
        return None
    normalized = _finite_float(value, field_name)
    if normalized < 0.0:
        raise ValueError(f"{field_name} must be non-negative.")
    return normalized
