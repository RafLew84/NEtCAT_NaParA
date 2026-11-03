import unittest
from dataclasses import replace
from math import cos, radians, sin

import numpy as np

from moltrack.analysis import (
    MolecularOrientationEstimationResult,
    MolecularTopographyOrientationSettings,
    MolecularTopographyOrientationScoreCurve,
    MolecularOrientationProvenance,
    estimate_molecular_orientation,
    estimate_molecular_orientation_from_mask,
    estimate_molecular_orientation_from_topography,
)


def _circle_mask(
    shape: tuple[int, int] = (101, 101),
    *,
    radius: float = 27.0,
    center_xy: tuple[float, float] | None = None,
) -> np.ndarray:
    height, width = shape
    center_x, center_y = center_xy or ((width - 1) / 2.0, (height - 1) / 2.0)
    yy, xx = np.indices(shape, dtype=np.float64)
    return (xx - center_x) ** 2 + (yy - center_y) ** 2 <= radius**2


def _directional_topography(
    mask: np.ndarray,
    *,
    angle_deg: float,
    pixel_size_nm_xy: tuple[float, float] = (1.0, 1.0),
    center_xy: tuple[float, float] | None = None,
) -> np.ndarray:
    height, width = mask.shape
    center_x, center_y = center_xy or ((width - 1) / 2.0, (height - 1) / 2.0)
    yy, xx = np.indices(mask.shape, dtype=np.float64)
    sample_x = (xx - center_x) * pixel_size_nm_xy[0]
    sample_y = -(yy - center_y) * pixel_size_nm_xy[1]
    angle = radians(angle_deg)
    along = sample_x * cos(angle) + sample_y * sin(angle)
    across = -sample_x * sin(angle) + sample_y * cos(angle)
    ridge = np.exp(-0.5 * (across / 2.5) ** 2) * np.exp(
        -0.5 * (along / 18.0) ** 2
    )
    shoulder = 0.2 * np.exp(-0.5 * (across / 7.0) ** 2) * np.exp(
        -0.5 * (along / 22.0) ** 2
    )
    return np.where(mask, ridge + shoulder, 0.0)


def _radial_topography(mask: np.ndarray) -> np.ndarray:
    height, width = mask.shape
    yy, xx = np.indices(mask.shape, dtype=np.float64)
    radius_squared = (
        (xx - (width - 1) / 2.0) ** 2
        + (yy - (height - 1) / 2.0) ** 2
    )
    return np.where(mask, np.exp(-radius_squared / (2.0 * 10.0**2)), 0.0)


def _provenance(
    shape: tuple[int, int],
    *,
    source_view: str = "raw",
    source_id: str = "segmentation-1",
    orientation_reference: str = "sample_x_axis_counterclockwise",
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


class MolecularOrientationTopographyEstimatorTests(unittest.TestCase):
    def test_mask_first_estimator_uses_topography_only_as_fallback(self) -> None:
        circular_mask = _circle_mask()
        circular = estimate_molecular_orientation(
            _directional_topography(circular_mask, angle_deg=37.0),
            circular_mask,
            measurement_id="circular",
            provenance=_provenance(circular_mask.shape),
            pixel_size_nm_xy=(1.0, 1.0),
            scan_angle_deg=0.0,
            valid_fov_mask=np.ones(circular_mask.shape, dtype=bool),
        )

        elongated_mask = _directional_topography(
            _circle_mask(),
            angle_deg=20.0,
        ) > 0.2
        elongated = estimate_molecular_orientation(
            _directional_topography(elongated_mask, angle_deg=80.0),
            elongated_mask,
            measurement_id="elongated",
            provenance=_provenance(
                elongated_mask.shape,
                source_id="elongated-segmentation",
            ),
            pixel_size_nm_xy=(1.0, 1.0),
            scan_angle_deg=0.0,
            valid_fov_mask=np.ones(elongated_mask.shape, dtype=bool),
        )

        self.assertTrue(circular.fallback_used)
        self.assertEqual(circular.mask_result.measurement.status, "unavailable")
        self.assertEqual(circular.measurement.method, "stm_topography")
        self.assertLess(
            _axis_distance_deg(circular.measurement.angle_deg, 37.0),
            2.0,
        )
        self.assertFalse(elongated.fallback_used)
        self.assertEqual(elongated.measurement.method, "mask_principal_axis")
        self.assertIsNone(elongated.topography_result)

        foreign = estimate_molecular_orientation(
            _directional_topography(circular_mask, angle_deg=55.0),
            circular_mask,
            measurement_id="foreign",
            provenance=_provenance(
                circular_mask.shape,
                source_id="foreign-segmentation",
            ),
            pixel_size_nm_xy=(1.0, 1.0),
            scan_angle_deg=0.0,
            valid_fov_mask=np.ones(circular_mask.shape, dtype=bool),
        )
        with self.assertRaisesRegex(ValueError, "same molecule"):
            MolecularOrientationEstimationResult(
                measurement=foreign.measurement,
                mask_result=circular.mask_result,
                topography_result=foreign.topography_result,
            )

    def test_topography_resolves_direction_inside_circular_mask(self) -> None:
        mask = _circle_mask()
        valid_fov = np.ones(mask.shape, dtype=bool)
        topography = _directional_topography(mask, angle_deg=37.0)
        provenance = _provenance(mask.shape)

        mask_result = estimate_molecular_orientation_from_mask(
            mask,
            measurement_id="circular-mask",
            provenance=provenance,
            pixel_size_nm_xy=(1.0, 1.0),
            scan_angle_deg=0.0,
            valid_fov_mask=valid_fov,
        )
        result = estimate_molecular_orientation_from_topography(
            topography,
            mask,
            measurement_id="directional-topography",
            provenance=provenance,
            pixel_size_nm_xy=(1.0, 1.0),
            scan_angle_deg=0.0,
            valid_fov_mask=valid_fov,
        )

        self.assertEqual(mask_result.measurement.status, "unavailable")
        self.assertEqual(result.measurement.status, "available")
        self.assertEqual(result.measurement.method, "stm_topography")
        self.assertLess(
            _axis_distance_deg(result.measurement.angle_deg, 37.0),
            2.0,
        )
        self.assertGreater(result.directional_confidence, 0.05)
        self.assertIsNone(result.rejection_reason)

    def test_stores_complete_score_curve_and_competitor_margin(self) -> None:
        mask = _circle_mask()
        topography = _directional_topography(mask, angle_deg=64.0)
        settings = MolecularTopographyOrientationSettings(
            angle_step_deg=2.0,
            competitor_separation_deg=25.0,
        )

        result = estimate_molecular_orientation_from_topography(
            topography,
            mask,
            measurement_id="score-curve",
            provenance=_provenance(mask.shape),
            pixel_size_nm_xy=(1.0, 1.0),
            scan_angle_deg=0.0,
            valid_fov_mask=np.ones(mask.shape, dtype=bool),
            settings=settings,
        )

        self.assertEqual(len(result.score_curve.angles_deg), 90)
        self.assertEqual(result.settings, settings)
        self.assertEqual(result.score_curve.angles_deg[0], 0.0)
        self.assertEqual(result.score_curve.angles_deg[-1], 178.0)
        self.assertTrue(
            all(0.0 <= score <= 1.0 for score in result.score_curve.scores)
        )
        self.assertLess(
            _axis_distance_deg(result.score_curve.best_angle_deg, 64.0),
            2.1,
        )
        self.assertAlmostEqual(
            result.score_margin,
            result.best_score - result.competitor_score,
        )
        self.assertAlmostEqual(
            result.directional_confidence,
            result.score_margin / result.best_score,
        )
        with self.assertRaisesRegex(ValueError, "competitor_score"):
            replace(
                result,
                competitor_score=result.competitor_score - 0.01,
                score_margin=result.score_margin + 0.01,
                directional_confidence=(
                    result.score_margin + 0.01
                )
                / result.best_score,
            )

    def test_score_curve_requires_complete_uniform_axis_period(self) -> None:
        with self.assertRaisesRegex(ValueError, "complete"):
            MolecularTopographyOrientationScoreCurve(
                angles_deg=(0.0, 2.0, 4.0),
                scores=(0.1, 0.2, 0.3),
            )
        with self.assertRaisesRegex(ValueError, "uniform"):
            MolecularTopographyOrientationScoreCurve(
                angles_deg=tuple(
                    float(value)
                    for value in (*range(0, 165, 15), 166)
                ),
                scores=(0.1,) * 12,
            )

    def test_settings_require_an_exact_grid_with_a_sampled_competitor(self) -> None:
        with self.assertRaisesRegex(ValueError, "divide 180"):
            MolecularTopographyOrientationSettings(
                angle_step_deg=180.0 / (12.0 + 1e-9),
            )
        with self.assertRaisesRegex(ValueError, "sampled competitor"):
            MolecularTopographyOrientationSettings(
                angle_step_deg=12.0,
                competitor_separation_deg=90.0,
            )

    def test_scan_rotation_and_expanded_translation_preserve_result(self) -> None:
        raw_mask = _circle_mask(shape=(81, 81), radius=23.0)
        raw_topography = _directional_topography(raw_mask, angle_deg=27.0)
        padding = ((10, 8), (14, 7))
        expanded_mask = np.pad(raw_mask, padding)
        expanded_topography = np.pad(
            raw_topography,
            padding,
            constant_values=np.nan,
        )
        expanded_valid_fov = np.pad(
            np.ones(raw_mask.shape, dtype=bool),
            padding,
        )

        raw_result = estimate_molecular_orientation_from_topography(
            raw_topography,
            raw_mask,
            measurement_id="raw-topography",
            provenance=_provenance(raw_mask.shape),
            pixel_size_nm_xy=(1.0, 1.0),
            scan_angle_deg=18.0,
            valid_fov_mask=np.ones(raw_mask.shape, dtype=bool),
        )
        expanded_result = estimate_molecular_orientation_from_topography(
            expanded_topography,
            expanded_mask,
            measurement_id="expanded-topography",
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
            2.0,
        )
        self.assertLess(
            _axis_distance_deg(
                raw_result.measurement.angle_deg,
                expanded_result.measurement.angle_deg,
            ),
            1e-9,
        )
        self.assertEqual(
            raw_result.score_curve.scores,
            expanded_result.score_curve.scores,
        )

    def test_physical_pixel_scale_is_applied_before_directional_scoring(
        self,
    ) -> None:
        pixel_size = (2.0, 0.5)
        mask = _circle_mask(shape=(151, 101), radius=35.0)
        topography = _directional_topography(
            mask,
            angle_deg=41.0,
            pixel_size_nm_xy=pixel_size,
        )

        result = estimate_molecular_orientation_from_topography(
            topography,
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
            2.0,
        )

    def test_uniform_intensity_scale_preserves_directional_result(self) -> None:
        mask = _circle_mask()
        topography = _directional_topography(mask, angle_deg=52.0)
        valid_fov = np.ones(mask.shape, dtype=bool)

        normal = estimate_molecular_orientation_from_topography(
            topography,
            mask,
            measurement_id="normal-amplitude",
            provenance=_provenance(mask.shape),
            pixel_size_nm_xy=(1.0, 1.0),
            scan_angle_deg=0.0,
            valid_fov_mask=valid_fov,
        )
        tiny = estimate_molecular_orientation_from_topography(
            topography * 1e-12,
            mask,
            measurement_id="tiny-amplitude",
            provenance=_provenance(
                mask.shape,
                source_id="tiny-amplitude-segmentation",
            ),
            pixel_size_nm_xy=(1.0, 1.0),
            scan_angle_deg=0.0,
            valid_fov_mask=valid_fov,
        )

        self.assertEqual(tiny.measurement.status, "available")
        self.assertEqual(
            normal.measurement.angle_deg,
            tiny.measurement.angle_deg,
        )
        np.testing.assert_allclose(
            normal.score_curve.scores,
            tiny.score_curve.scores,
            rtol=1e-12,
            atol=1e-12,
        )

    def test_linear_background_plane_is_not_molecular_orientation(self) -> None:
        mask = _circle_mask()
        yy, xx = np.indices(mask.shape, dtype=np.float64)
        topography = 3.0 * xx - 2.0 * yy + 17.0

        result = estimate_molecular_orientation_from_topography(
            topography,
            mask,
            measurement_id="linear-background",
            provenance=_provenance(mask.shape),
            pixel_size_nm_xy=(2.0, 0.5),
            scan_angle_deg=23.0,
            valid_fov_mask=np.ones(mask.shape, dtype=bool),
        )

        self.assertEqual(result.measurement.status, "unavailable")
        self.assertIsNone(result.measurement.angle_deg)
        self.assertIn(
            result.rejection_reason,
            {
                "insufficient_intensity_variation",
                "insufficient_gradient_energy",
            },
        )
        self.assertEqual(result.pixel_size_nm_xy, (2.0, 0.5))
        self.assertEqual(result.scan_angle_deg, 23.0)
        self.assertEqual(len(result.background_plane_coefficients), 3)

    def test_radially_symmetric_topography_has_no_orientation(self) -> None:
        mask = _circle_mask()

        result = estimate_molecular_orientation_from_topography(
            _radial_topography(mask),
            mask,
            measurement_id="radial-topography",
            provenance=_provenance(mask.shape),
            pixel_size_nm_xy=(1.0, 1.0),
            scan_angle_deg=0.0,
            valid_fov_mask=np.ones(mask.shape, dtype=bool),
        )

        self.assertEqual(result.measurement.status, "unavailable")
        self.assertIsNone(result.measurement.angle_deg)
        self.assertIsNone(result.measurement.confidence)
        self.assertEqual(
            result.rejection_reason,
            "insufficient_directional_margin",
        )
        self.assertGreater(len(result.score_curve.scores), 0)
        with self.assertRaisesRegex(ValueError, "rejection_reason"):
            replace(result, rejection_reason="not-a-supported-reason")
        with self.assertRaisesRegex(ValueError, "normalization"):
            replace(result, normalization_center=None)

    def test_flat_topography_is_unavailable_without_score_curve(self) -> None:
        mask = _circle_mask()

        result = estimate_molecular_orientation_from_topography(
            np.ones(mask.shape, dtype=np.float64),
            mask,
            measurement_id="flat-topography",
            provenance=_provenance(mask.shape),
            pixel_size_nm_xy=(1.0, 1.0),
            scan_angle_deg=0.0,
            valid_fov_mask=np.ones(mask.shape, dtype=bool),
        )

        self.assertEqual(result.measurement.status, "unavailable")
        self.assertEqual(
            result.rejection_reason,
            "insufficient_intensity_variation",
        )
        self.assertEqual(result.score_curve.angles_deg, ())
        self.assertIsNone(result.directional_confidence)

    def test_missing_context_around_mask_is_unavailable(self) -> None:
        mask = _circle_mask(
            shape=(61, 61),
            radius=20.0,
            center_xy=(12.0, 30.0),
        )

        result = estimate_molecular_orientation_from_topography(
            _directional_topography(
                mask,
                angle_deg=0.0,
                center_xy=(12.0, 30.0),
            ),
            mask,
            measurement_id="missing-context",
            provenance=_provenance(mask.shape),
            pixel_size_nm_xy=(1.0, 1.0),
            scan_angle_deg=0.0,
            valid_fov_mask=np.ones(mask.shape, dtype=bool),
            settings=MolecularTopographyOrientationSettings(
                context_radius_px=4,
            ),
        )

        self.assertEqual(result.measurement.status, "unavailable")
        self.assertEqual(result.rejection_reason, "insufficient_context")
        self.assertEqual(result.score_curve.scores, ())


if __name__ == "__main__":
    unittest.main()
