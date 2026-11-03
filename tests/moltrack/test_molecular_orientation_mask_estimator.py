import unittest
from dataclasses import replace
from math import cos, radians, sin

import numpy as np

from moltrack.analysis import (
    MolecularMaskOrientationSettings,
    MolecularOrientationProvenance,
    estimate_molecular_orientation_from_mask,
)


def _ellipse_mask(
    *,
    shape: tuple[int, int] = (101, 101),
    angle_deg: float,
    major_radius: float = 24.0,
    minor_radius: float = 6.0,
    center_xy: tuple[float, float] | None = None,
    pixel_size_nm_xy: tuple[float, float] = (1.0, 1.0),
) -> np.ndarray:
    height, width = shape
    center_x, center_y = center_xy or ((width - 1) / 2.0, (height - 1) / 2.0)
    yy, xx = np.indices(shape, dtype=np.float64)
    sample_x = (xx - center_x) * pixel_size_nm_xy[0]
    sample_y = -(yy - center_y) * pixel_size_nm_xy[1]
    angle = radians(angle_deg)
    along = sample_x * cos(angle) + sample_y * sin(angle)
    across = -sample_x * sin(angle) + sample_y * cos(angle)
    return (along / major_radius) ** 2 + (across / minor_radius) ** 2 <= 1.0


def _provenance(
    shape: tuple[int, int],
    *,
    source_view: str = "raw",
    orientation_reference: str = "sample_x_axis_counterclockwise",
    source_id: str = "segmentation-1",
) -> MolecularOrientationProvenance:
    height, width = shape
    return MolecularOrientationProvenance(
        source_file_name="synthetic.mpp",
        source_file_sha256="a" * 64,
        source_session_file_name=None,
        source_session_sha256=None,
        frame_index=0,
        source_view=source_view,
        source_kind="segmentation",
        source_id=source_id,
        patch_bbox_xyxy=(0.0, 0.0, float(width), float(height)),
        orientation_reference=orientation_reference,
    )


def _axis_distance_deg(first: float, second: float) -> float:
    difference = abs((first - second) % 180.0)
    return min(difference, 180.0 - difference)


class MolecularOrientationMaskEstimatorTests(unittest.TestCase):
    def test_estimates_known_ellipse_axis_in_sample_coordinates(self) -> None:
        mask = _ellipse_mask(angle_deg=34.0)

        result = estimate_molecular_orientation_from_mask(
            mask,
            measurement_id="ellipse-34",
            provenance=_provenance(mask.shape),
            pixel_size_nm_xy=(1.0, 1.0),
            scan_angle_deg=0.0,
            valid_fov_mask=np.ones(mask.shape, dtype=bool),
        )

        self.assertEqual(result.measurement.status, "available")
        self.assertEqual(result.measurement.method, "mask_principal_axis")
        self.assertEqual(result.measurement.periodicity_deg, 180.0)
        self.assertLess(
            _axis_distance_deg(result.measurement.angle_deg, 34.0),
            1.0,
        )
        self.assertGreater(result.anisotropy, 0.75)
        self.assertGreater(result.measurement.confidence, 0.5)
        self.assertEqual(result.coordinate_frame, "sample_nm")
        self.assertFalse(result.edge_truncated_qc)
        self.assertIsNone(result.rejection_reason)

    def test_uses_physical_pixel_scale_before_estimating_axis(self) -> None:
        pixel_size = (2.0, 0.5)
        mask = _ellipse_mask(
            shape=(121, 101),
            angle_deg=41.0,
            major_radius=24.0,
            minor_radius=5.0,
            pixel_size_nm_xy=pixel_size,
        )

        result = estimate_molecular_orientation_from_mask(
            mask,
            measurement_id="anisotropic-pixels",
            provenance=_provenance(mask.shape),
            pixel_size_nm_xy=pixel_size,
            scan_angle_deg=0.0,
            valid_fov_mask=np.ones(mask.shape, dtype=bool),
        )

        self.assertEqual(result.measurement.status, "available")
        self.assertLess(
            _axis_distance_deg(result.measurement.angle_deg, 41.0),
            1.0,
        )

    def test_scan_rotation_and_expanded_translation_preserve_orientation(
        self,
    ) -> None:
        raw_mask = _ellipse_mask(shape=(81, 81), angle_deg=27.0)
        expanded_mask = np.pad(raw_mask, ((11, 7), (15, 9)))
        expanded_valid_fov = np.pad(
            np.ones(raw_mask.shape, dtype=bool),
            ((11, 7), (15, 9)),
        )

        raw_result = estimate_molecular_orientation_from_mask(
            raw_mask,
            measurement_id="raw",
            provenance=_provenance(raw_mask.shape, source_view="raw"),
            pixel_size_nm_xy=(1.0, 1.0),
            scan_angle_deg=18.0,
            valid_fov_mask=np.ones(raw_mask.shape, dtype=bool),
        )
        expanded_result = estimate_molecular_orientation_from_mask(
            expanded_mask,
            measurement_id="expanded",
            provenance=_provenance(
                expanded_mask.shape,
                source_view="expanded_aligned",
                source_id="segmentation-expanded",
            ),
            pixel_size_nm_xy=(1.0, 1.0),
            scan_angle_deg=18.0,
            valid_fov_mask=expanded_valid_fov,
        )

        self.assertLess(
            _axis_distance_deg(raw_result.measurement.angle_deg, 45.0),
            1.0,
        )
        self.assertLess(
            _axis_distance_deg(
                raw_result.measurement.angle_deg,
                expanded_result.measurement.angle_deg,
            ),
            1e-9,
        )
        self.assertAlmostEqual(raw_result.anisotropy, expanded_result.anisotropy)

    def test_expanded_valid_fov_preserves_raw_edge_truncation_qc(self) -> None:
        raw_mask = _ellipse_mask(
            shape=(81, 81),
            angle_deg=0.0,
            center_xy=(4.0, 40.0),
        )
        padding = ((12, 8), (17, 6))
        expanded_mask = np.pad(raw_mask, padding)
        expanded_valid_fov = np.pad(
            np.ones(raw_mask.shape, dtype=bool),
            padding,
        )

        result = estimate_molecular_orientation_from_mask(
            expanded_mask,
            measurement_id="expanded-edge-object",
            provenance=_provenance(
                expanded_mask.shape,
                source_view="expanded_aligned",
                source_id="expanded-edge-segmentation",
            ),
            pixel_size_nm_xy=(1.0, 1.0),
            scan_angle_deg=0.0,
            valid_fov_mask=expanded_valid_fov,
        )

        self.assertEqual(result.measurement.status, "ambiguous")
        self.assertTrue(result.edge_truncated_qc)
        self.assertEqual(result.rejection_reason, "valid_fov_edge_truncation")

    def test_missing_scan_angle_uses_explicit_image_axis_reference(self) -> None:
        mask = _ellipse_mask(angle_deg=22.0)
        provenance = _provenance(
            mask.shape,
            orientation_reference="image_x_axis_counterclockwise",
        )

        result = estimate_molecular_orientation_from_mask(
            mask,
            measurement_id="image-reference",
            provenance=provenance,
            pixel_size_nm_xy=(1.0, 1.0),
            scan_angle_deg=None,
            valid_fov_mask=np.ones(mask.shape, dtype=bool),
        )

        self.assertEqual(result.coordinate_frame, "image_xy")
        self.assertLess(
            _axis_distance_deg(result.measurement.angle_deg, 22.0),
            1.0,
        )
        with self.assertRaisesRegex(ValueError, "orientation_reference"):
            estimate_molecular_orientation_from_mask(
                mask,
                measurement_id="invalid-reference",
                provenance=_provenance(mask.shape),
                pixel_size_nm_xy=(1.0, 1.0),
                scan_angle_deg=None,
                valid_fov_mask=np.ones(mask.shape, dtype=bool),
            )

    def test_nearly_circular_mask_is_unavailable_without_fake_angle(self) -> None:
        mask = _ellipse_mask(
            angle_deg=0.0,
            major_radius=16.0,
            minor_radius=15.5,
        )

        result = estimate_molecular_orientation_from_mask(
            mask,
            measurement_id="near-circle",
            provenance=_provenance(mask.shape),
            pixel_size_nm_xy=(1.0, 1.0),
            scan_angle_deg=0.0,
            settings=MolecularMaskOrientationSettings(
                min_anisotropy=0.15,
            ),
            valid_fov_mask=np.ones(mask.shape, dtype=bool),
        )

        self.assertEqual(result.measurement.status, "unavailable")
        self.assertIsNone(result.measurement.angle_deg)
        self.assertIsNone(result.measurement.confidence)
        self.assertLess(result.anisotropy, 0.15)
        self.assertEqual(result.rejection_reason, "insufficient_anisotropy")

    def test_small_mask_is_unavailable(self) -> None:
        mask = np.zeros((21, 21), dtype=bool)
        mask[10, 10:13] = True

        result = estimate_molecular_orientation_from_mask(
            mask,
            measurement_id="too-small",
            provenance=_provenance(mask.shape),
            pixel_size_nm_xy=(1.0, 1.0),
            scan_angle_deg=0.0,
            settings=MolecularMaskOrientationSettings(min_mask_area_px=9),
            valid_fov_mask=np.ones(mask.shape, dtype=bool),
        )

        self.assertEqual(result.measurement.status, "unavailable")
        self.assertEqual(result.mask_area_px, 3)
        self.assertIsNone(result.anisotropy)
        self.assertEqual(result.rejection_reason, "insufficient_mask_area")

    def test_anisotropic_object_cut_by_patch_edge_is_ambiguous(self) -> None:
        mask = _ellipse_mask(
            shape=(81, 81),
            angle_deg=0.0,
            center_xy=(4.0, 40.0),
        )

        result = estimate_molecular_orientation_from_mask(
            mask,
            measurement_id="edge-object",
            provenance=_provenance(mask.shape),
            pixel_size_nm_xy=(1.0, 1.0),
            scan_angle_deg=0.0,
            valid_fov_mask=np.ones(mask.shape, dtype=bool),
        )

        self.assertEqual(result.measurement.status, "ambiguous")
        self.assertIsNotNone(result.measurement.angle_deg)
        self.assertIsNotNone(result.measurement.confidence)
        self.assertTrue(result.edge_truncated_qc)
        self.assertEqual(result.rejection_reason, "valid_fov_edge_truncation")

    def test_valid_fov_is_required_for_every_source_view(self) -> None:
        mask = _ellipse_mask(angle_deg=0.0)

        with self.assertRaisesRegex(TypeError, "valid_fov_mask"):
            estimate_molecular_orientation_from_mask(
                mask,
                measurement_id="missing-valid-fov",
                provenance=_provenance(mask.shape),
                pixel_size_nm_xy=(1.0, 1.0),
                scan_angle_deg=0.0,
            )

    def test_rejects_non_binary_masks_and_falsey_invalid_settings(self) -> None:
        mask = _ellipse_mask(angle_deg=0.0)
        probability_mask = mask.astype(np.float64) * 0.8
        invalid_fov = np.ones(mask.shape, dtype=np.float64)
        invalid_fov[0, 0] = np.nan

        with self.assertRaisesRegex(ValueError, "binary"):
            estimate_molecular_orientation_from_mask(
                probability_mask,
                measurement_id="probability-mask",
                provenance=_provenance(mask.shape),
                pixel_size_nm_xy=(1.0, 1.0),
                scan_angle_deg=0.0,
                valid_fov_mask=np.ones(mask.shape, dtype=bool),
            )
        with self.assertRaisesRegex(ValueError, "finite"):
            estimate_molecular_orientation_from_mask(
                mask,
                measurement_id="invalid-fov",
                provenance=_provenance(mask.shape),
                pixel_size_nm_xy=(1.0, 1.0),
                scan_angle_deg=0.0,
                valid_fov_mask=invalid_fov,
            )
        with self.assertRaisesRegex(TypeError, "settings"):
            estimate_molecular_orientation_from_mask(
                mask,
                measurement_id="false-settings",
                provenance=_provenance(mask.shape),
                pixel_size_nm_xy=(1.0, 1.0),
                scan_angle_deg=0.0,
                valid_fov_mask=np.ones(mask.shape, dtype=bool),
                settings=False,
            )

    def test_uniform_scale_and_negative_angles_preserve_axis(self) -> None:
        mask = _ellipse_mask(angle_deg=-20.0)
        valid_fov = np.ones(mask.shape, dtype=bool)

        normal = estimate_molecular_orientation_from_mask(
            mask,
            measurement_id="normal-scale",
            provenance=_provenance(mask.shape),
            pixel_size_nm_xy=(1.0, 1.0),
            scan_angle_deg=-25.0,
            valid_fov_mask=valid_fov,
        )
        tiny = estimate_molecular_orientation_from_mask(
            mask,
            measurement_id="tiny-scale",
            provenance=_provenance(mask.shape, source_id="tiny-scale-segmentation"),
            pixel_size_nm_xy=(1e-9, 1e-9),
            scan_angle_deg=-25.0,
            valid_fov_mask=valid_fov,
        )

        self.assertEqual(normal.measurement.status, "available")
        self.assertEqual(tiny.measurement.status, "available")
        self.assertLess(
            _axis_distance_deg(normal.measurement.angle_deg, 135.0),
            1.0,
        )
        self.assertLess(
            _axis_distance_deg(
                normal.measurement.angle_deg,
                tiny.measurement.angle_deg,
            ),
            1e-9,
        )
        self.assertAlmostEqual(normal.anisotropy, tiny.anisotropy)

    def test_public_result_rejects_contradictory_diagnostics(self) -> None:
        mask = _ellipse_mask(angle_deg=15.0)
        result = estimate_molecular_orientation_from_mask(
            mask,
            measurement_id="valid-result",
            provenance=_provenance(mask.shape),
            pixel_size_nm_xy=(1.0, 1.0),
            scan_angle_deg=0.0,
            valid_fov_mask=np.ones(mask.shape, dtype=bool),
        )

        with self.assertRaisesRegex(ValueError, "diagnostics"):
            replace(
                result,
                anisotropy=None,
                principal_variance_nm2=None,
                minor_variance_nm2=None,
            )
        with self.assertRaisesRegex(ValueError, "edge_truncated_qc"):
            replace(result, edge_truncated_qc=True)
        with self.assertRaisesRegex(ValueError, "mask_principal_axis"):
            replace(
                result,
                measurement=replace(result.measurement, method="manual"),
            )
        with self.assertRaisesRegex(ValueError, "coordinate_frame"):
            replace(result, coordinate_frame="image_xy")
        with self.assertRaisesRegex(ValueError, "mask_area_px"):
            replace(
                result,
                mask_area_px=mask.shape[0] * mask.shape[1] + 1,
            )
        with self.assertRaisesRegex(ValueError, "anisotropy.*variances"):
            replace(result, anisotropy=0.0)

        circular_mask = _ellipse_mask(
            angle_deg=0.0,
            major_radius=16.0,
            minor_radius=15.5,
        )
        unavailable = estimate_molecular_orientation_from_mask(
            circular_mask,
            measurement_id="unavailable-result",
            provenance=_provenance(
                circular_mask.shape,
                source_id="circular-segmentation",
            ),
            pixel_size_nm_xy=(1.0, 1.0),
            scan_angle_deg=0.0,
            valid_fov_mask=np.ones(circular_mask.shape, dtype=bool),
        )
        with self.assertRaisesRegex(ValueError, "insufficient_anisotropy"):
            replace(
                unavailable,
                anisotropy=None,
                principal_variance_nm2=None,
                minor_variance_nm2=None,
            )


if __name__ == "__main__":
    unittest.main()
