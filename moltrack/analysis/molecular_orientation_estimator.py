"""Mask-first molecular orientation with an STM-topography fallback."""

from __future__ import annotations

from dataclasses import dataclass

from .molecular_orientation_mask import (
    MolecularMaskOrientationResult,
    MolecularMaskOrientationSettings,
    estimate_molecular_orientation_from_mask,
)
from .molecular_orientation_models import (
    MolecularOrientationMeasurement,
    MolecularOrientationProvenance,
)
from .molecular_orientation_topography import (
    MolecularTopographyOrientationResult,
    MolecularTopographyOrientationSettings,
    estimate_molecular_orientation_from_topography,
)


@dataclass(frozen=True)
class MolecularOrientationEstimationResult:
    """Auditable choice between mask geometry and STM topography."""

    measurement: MolecularOrientationMeasurement
    mask_result: MolecularMaskOrientationResult
    topography_result: MolecularTopographyOrientationResult | None

    def __post_init__(self) -> None:
        if not isinstance(self.measurement, MolecularOrientationMeasurement):
            raise TypeError("measurement must be MolecularOrientationMeasurement.")
        if not isinstance(self.mask_result, MolecularMaskOrientationResult):
            raise TypeError("mask_result must be MolecularMaskOrientationResult.")
        if self.topography_result is not None and not isinstance(
            self.topography_result,
            MolecularTopographyOrientationResult,
        ):
            raise TypeError(
                "topography_result must be MolecularTopographyOrientationResult."
            )
        if self.topography_result is not None:
            mask_measurement = self.mask_result.measurement
            topography_measurement = self.topography_result.measurement
            if (
                mask_measurement.provenance != topography_measurement.provenance
                or mask_measurement.patch_shape_px
                != topography_measurement.patch_shape_px
                or self.mask_result.coordinate_frame
                != self.topography_result.coordinate_frame
            ):
                raise ValueError(
                    "Mask and topography results must describe the same molecule, "
                    "patch, and coordinate frame."
                )
        if self.mask_result.measurement.status == "available":
            if self.topography_result is not None:
                raise ValueError(
                    "Topography fallback must not run for an available mask result."
                )
            expected = self.mask_result.measurement
        else:
            if self.topography_result is None:
                raise ValueError(
                    "An unresolved mask result requires the topography fallback."
                )
            expected = self.topography_result.measurement
        if self.measurement != expected:
            raise ValueError(
                "measurement must equal the selected orientation result."
            )

    @property
    def fallback_used(self) -> bool:
        return self.topography_result is not None


def estimate_molecular_orientation(
    topography_patch: object,
    molecule_mask: object,
    *,
    measurement_id: str,
    provenance: MolecularOrientationProvenance,
    pixel_size_nm_xy: tuple[float, float],
    scan_angle_deg: float | None,
    valid_fov_mask: object,
    mask_settings: MolecularMaskOrientationSettings | None = None,
    topography_settings: MolecularTopographyOrientationSettings | None = None,
) -> MolecularOrientationEstimationResult:
    """Use mask geometry when resolved, otherwise analyze STM topography."""

    mask_result = estimate_molecular_orientation_from_mask(
        molecule_mask,
        measurement_id=f"{measurement_id}:mask",
        provenance=provenance,
        pixel_size_nm_xy=pixel_size_nm_xy,
        scan_angle_deg=scan_angle_deg,
        valid_fov_mask=valid_fov_mask,
        settings=mask_settings,
    )
    if mask_result.measurement.status == "available":
        return MolecularOrientationEstimationResult(
            measurement=mask_result.measurement,
            mask_result=mask_result,
            topography_result=None,
        )

    topography_result = estimate_molecular_orientation_from_topography(
        topography_patch,
        molecule_mask,
        measurement_id=f"{measurement_id}:topography",
        provenance=provenance,
        pixel_size_nm_xy=pixel_size_nm_xy,
        scan_angle_deg=scan_angle_deg,
        valid_fov_mask=valid_fov_mask,
        settings=topography_settings,
    )
    return MolecularOrientationEstimationResult(
        measurement=topography_result.measurement,
        mask_result=mask_result,
        topography_result=topography_result,
    )
