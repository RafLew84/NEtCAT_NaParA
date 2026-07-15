import math
import unittest
from dataclasses import FrozenInstanceError, replace

import numpy as np

from moltrack.analysis import (
    FirstShellGraph,
    MolecularM6OrientationAnalysisSettings,
    PairCorrelationResult,
    build_first_shell_graph,
    compute_pair_correlation,
)


def _settings(*, minimum_exposure: float = 1e-12) -> MolecularM6OrientationAnalysisSettings:
    return MolecularM6OrientationAnalysisSettings(
        gr_bin_width_nm=1.0,
        gr_max_nm=3.0,
        gr_min_expected_pair_exposure=minimum_exposure,
    )


def _rectangular_annulus_overlap(
    inner_radius: float,
    outer_radius: float,
    *,
    width: float,
    height: float,
) -> float:
    def cumulative(radius: float) -> float:
        return (
            math.pi * width * height * radius**2
            - (4.0 / 3.0) * (width + height) * radius**3
            + 0.5 * radius**4
        )

    return cumulative(outer_radius) - cumulative(inner_radius)


def _compute_pair_correlation(
    points_xy_nm: object,
    *,
    settings: MolecularM6OrientationAnalysisSettings,
    frame_index: int = 0,
    point_ids: tuple[str, ...] | None = None,
    spatial_calibration_fingerprint: str = "calibration-v1",
    registration_fingerprint: str = "registration-v1",
    **window: object,
) -> PairCorrelationResult:
    points = np.asarray(points_xy_nm, dtype=np.float64)
    if point_ids is None and points.ndim == 2:
        point_ids = tuple(f"point-{index}" for index in range(len(points)))
    graph = build_first_shell_graph(
        points,
        point_ids=point_ids,
        settings=settings,
        spatial_calibration_fingerprint=spatial_calibration_fingerprint,
        registration_fingerprint=registration_fingerprint,
    )
    return compute_pair_correlation(
        points,
        point_ids=graph.point_ids,
        point_frame_indices=(frame_index,) * len(points),
        first_shell_graph=graph,
        frame_index=frame_index,
        settings=settings,
        **window,
    )


class PairCorrelationTests(unittest.TestCase):
    def test_rectangular_result_keeps_unordered_counts_and_translation_exposure(self) -> None:
        result = _compute_pair_correlation(
            np.asarray(((0.0, 0.0), (1.5, 0.0), (0.0, 2.5))),
            settings=_settings(),
            window_geometry="rectangular",
            window_size_nm=(10.0, 10.0),
        )

        self.assertIsInstance(result, PairCorrelationResult)
        self.assertEqual(result.bin_edges_nm, (0.0, 1.0, 2.0, 3.0))
        self.assertEqual(result.bin_centers_nm, (0.5, 1.5, 2.5))
        self.assertEqual(result.observed_unordered_pair_count, (0, 1, 2))
        self.assertEqual(result.total_unordered_pair_count, 3)
        self.assertEqual(result.point_count, 3)
        self.assertEqual(result.frame_index, 0)
        self.assertEqual(result.representative_point_ids, ("point-0", "point-1", "point-2"))
        self.assertEqual(result.coordinate_frame, "sample_nm")
        self.assertEqual(result.spatial_calibration_fingerprint, "calibration-v1")
        self.assertEqual(result.registration_fingerprint, "registration-v1")
        self.assertEqual(len(result.point_coordinate_fingerprint), 64)
        self.assertEqual(result.distance_unit, "nm")
        self.assertEqual(result.window_geometry_status, "rectangular_translation_correction")
        self.assertEqual(result.bin_status, ("valid", "valid", "valid"))
        self.assertEqual(result.contributing_frame_count, (1, 1, 1))

        area = 100.0
        unordered_density_factor = 3.0 * 2.0 / (2.0 * area**2)
        expected_exposure = tuple(
            unordered_density_factor
            * _rectangular_annulus_overlap(
                float(index),
                float(index + 1),
                width=10.0,
                height=10.0,
            )
            for index in range(3)
        )
        np.testing.assert_allclose(result.expected_pair_exposure, expected_exposure)
        self.assertEqual(result.g_r[0], 0.0)
        np.testing.assert_allclose(
            result.g_r[1:],
            np.asarray((1.0, 2.0)) / np.asarray(expected_exposure[1:]),
        )

        with self.assertRaises(FrozenInstanceError):
            result.point_count = 4
        with self.assertRaises(ValueError):
            replace(result, observed_unordered_pair_count=(0, 1))

    def test_positive_observation_with_low_exposure_is_not_reported_as_zero(self) -> None:
        result = _compute_pair_correlation(
            np.asarray(((0.0, 0.0), (1.5, 0.0))),
            settings=_settings(minimum_exposure=10.0),
            window_geometry="rectangular",
            window_size_nm=(10.0, 10.0),
        )

        self.assertEqual(result.observed_unordered_pair_count, (0, 1, 0))
        self.assertTrue(all(math.isnan(value) for value in result.g_r))
        self.assertEqual(result.bin_status, ("insufficient_exposure",) * 3)
        self.assertEqual(result.contributing_frame_count, (1, 1, 1))

    def test_nonfinite_exposure_is_insufficient_in_supported_geometry(self) -> None:
        result = _compute_pair_correlation(
            np.asarray(((0.0, 0.0), (1.5, 0.0))),
            settings=_settings(),
            window_geometry="rectangular",
            window_size_nm=(10.0, 10.0),
        )
        exposure = list(result.expected_pair_exposure)
        g_values = list(result.g_r)
        statuses = list(result.bin_status)
        contributions = list(result.contributing_frame_count)
        exposure[0] = float("nan")
        g_values[0] = float("nan")
        statuses[0] = "insufficient_exposure"
        contributions[0] = 0

        restored = replace(
            result,
            expected_pair_exposure=tuple(exposure),
            g_r=tuple(g_values),
            bin_status=tuple(statuses),
            contributing_frame_count=tuple(contributions),
        )
        self.assertEqual(restored.bin_status[0], "insufficient_exposure")
        self.assertTrue(math.isnan(restored.g_r[0]))

        exposure[0] = -1.0
        with self.assertRaises(ValueError):
            replace(result, expected_pair_exposure=tuple(exposure))
        exposure[0] = float("-inf")
        restored_negative_infinity = replace(
            result,
            expected_pair_exposure=tuple(exposure),
            g_r=tuple(g_values),
            bin_status=tuple(statuses),
            contributing_frame_count=tuple(contributions),
        )
        self.assertEqual(
            restored_negative_infinity.bin_status[0],
            "insufficient_exposure",
        )

    def test_uses_every_unordered_pair_not_only_neighbor_graph_edges(self) -> None:
        result = _compute_pair_correlation(
            np.asarray(((0.0, 0.0), (1.0, 0.0), (2.0, 0.0), (3.0, 0.0))),
            settings=MolecularM6OrientationAnalysisSettings(
                gr_bin_width_nm=1.0,
                gr_max_nm=4.0,
                gr_min_expected_pair_exposure=1e-12,
            ),
            window_geometry="rectangular",
            window_size_nm=(10.0, 10.0),
        )

        self.assertEqual(result.total_unordered_pair_count, 6)
        self.assertEqual(sum(result.observed_unordered_pair_count), 6)
        self.assertEqual(result.observed_unordered_pair_count, (0, 3, 2, 1))

    def test_excludes_rejected_duplicates_using_first_shell_graph(self) -> None:
        result = _compute_pair_correlation(
            np.asarray(((0.0, 0.0), (0.1, 0.0), (1.5, 0.0))),
            point_ids=("point-a", "point-b", "point-c"),
            settings=_settings(),
            window_geometry="rectangular",
            window_size_nm=(10.0, 10.0),
        )

        self.assertEqual(result.representative_point_ids, ("point-a", "point-c"))
        self.assertEqual(result.point_count, 2)
        self.assertEqual(result.total_unordered_pair_count, 1)
        self.assertEqual(sum(result.observed_unordered_pair_count), 1)

    def test_irregular_mask_uses_binary_autocorrelation_exposure(self) -> None:
        result = _compute_pair_correlation(
            np.asarray(((0.0, 0.0), (1.0, 0.0))),
            settings=_settings(minimum_exposure=1e-12),
            window_geometry="irregular",
            valid_fov_mask=np.asarray(((1, 1), (1, 0)), dtype=np.uint8),
            valid_fov_pixel_size_nm=(1.0, 1.0),
        )

        self.assertEqual(result.window_geometry_status, "irregular_mask_autocorrelation")
        self.assertEqual(result.window_area_nm2, 3.0)
        self.assertEqual(result.observed_unordered_pair_count, (0, 1, 0))
        self.assertAlmostEqual(sum(result.expected_pair_exposure), 1.0, places=4)
        self.assertEqual(result.bin_status, ("valid", "valid", "valid"))
        self.assertEqual(result.contributing_frame_count, (1, 1, 1))
        self.assertEqual(result.g_r[0], 0.0)
        self.assertGreater(result.g_r[1], 0.0)
        self.assertEqual(result.g_r[2], 0.0)

    def test_missing_irregular_mask_has_explicit_unsupported_status(self) -> None:
        result = _compute_pair_correlation(
            np.asarray(((0.0, 0.0), (1.5, 0.0))),
            settings=_settings(),
            window_geometry="irregular",
        )

        self.assertEqual(result.observed_unordered_pair_count, (0, 1, 0))
        self.assertEqual(result.window_geometry_status, "unsupported_window_geometry")
        self.assertIsNone(result.window_area_nm2)
        self.assertEqual(result.bin_status, ("unsupported_window_geometry",) * 3)
        self.assertEqual(result.contributing_frame_count, (0, 0, 0))
        self.assertTrue(all(math.isnan(value) for value in result.expected_pair_exposure))
        self.assertTrue(all(math.isnan(value) for value in result.g_r))

    def test_rectangular_exposure_integrates_to_all_pairs_past_window_diagonal(self) -> None:
        result = _compute_pair_correlation(
            np.asarray(((0.0, 0.0), (1.0, 1.0), (1.5, 2.0))),
            settings=MolecularM6OrientationAnalysisSettings(
                gr_bin_width_nm=0.5,
                gr_max_nm=4.0,
                gr_min_expected_pair_exposure=1e-12,
            ),
            window_geometry="rectangular",
            window_size_nm=(2.0, 3.0),
        )

        self.assertAlmostEqual(sum(result.expected_pair_exposure), 3.0, places=10)

    def test_regular_lattice_has_first_spacing_peak_and_empty_gap(self) -> None:
        coordinates = np.arange(1.0, 20.0, 2.0)
        grid_x, grid_y = np.meshgrid(coordinates, coordinates)
        points = np.column_stack((grid_x.ravel(), grid_y.ravel()))
        result = _compute_pair_correlation(
            points,
            settings=MolecularM6OrientationAnalysisSettings(
                gr_bin_width_nm=0.25,
                gr_max_nm=5.0,
                gr_min_expected_pair_exposure=1e-12,
            ),
            window_geometry="rectangular",
            window_size_nm=(20.0, 20.0),
        )

        spacing_bin = result.bin_centers_nm.index(2.125)
        empty_gap_bin = result.bin_centers_nm.index(1.375)
        self.assertGreater(result.g_r[spacing_bin], 3.0)
        self.assertEqual(result.g_r[empty_gap_bin], 0.0)

    def test_uniform_random_frames_average_to_one_after_edge_correction(self) -> None:
        settings = MolecularM6OrientationAnalysisSettings(
            gr_bin_width_nm=1.0,
            gr_max_nm=15.0,
            gr_min_expected_pair_exposure=1e-12,
        )
        random = np.random.default_rng(20260716)
        observed_sum = np.zeros(15, dtype=np.float64)
        exposure_sum = np.zeros(15, dtype=np.float64)
        for _frame_index in range(80):
            point_count = int(random.poisson(120.0))
            result = _compute_pair_correlation(
                random.uniform(0.0, 50.0, size=(point_count, 2)),
                settings=settings,
                window_geometry="rectangular",
                window_size_nm=(50.0, 50.0),
            )
            observed_sum += np.asarray(result.observed_unordered_pair_count)
            exposure_sum += np.asarray(result.expected_pair_exposure)

        aggregated_g = observed_sum / exposure_sum
        np.testing.assert_allclose(aggregated_g[2:12], 1.0, rtol=0.0, atol=0.08)

    def test_pixelized_rectangle_mask_matches_analytic_exposure(self) -> None:
        settings = _settings()
        points = np.asarray(((1.0, 1.0), (8.0, 8.0), (5.0, 5.0)))
        analytic = _compute_pair_correlation(
            points,
            settings=settings,
            window_geometry="rectangular",
            window_size_nm=(10.0, 10.0),
        )
        pixelized = _compute_pair_correlation(
            points,
            settings=settings,
            window_geometry="irregular",
            valid_fov_mask=np.ones((100, 100), dtype=bool),
            valid_fov_pixel_size_nm=(0.1, 0.1),
        )

        np.testing.assert_allclose(
            pixelized.expected_pair_exposure,
            analytic.expected_pair_exposure,
            rtol=0.03,
            atol=0.0,
        )

    def test_single_coarse_mask_pixel_integrates_across_radial_bins(self) -> None:
        settings = MolecularM6OrientationAnalysisSettings(
            gr_bin_width_nm=0.25,
            gr_max_nm=0.5,
            gr_min_expected_pair_exposure=1e-12,
        )
        points = np.asarray(((0.1, 0.1), (0.9, 0.9)))
        analytic = _compute_pair_correlation(
            points,
            settings=settings,
            window_geometry="rectangular",
            window_size_nm=(1.0, 1.0),
        )
        pixelized = _compute_pair_correlation(
            points,
            settings=settings,
            window_geometry="irregular",
            valid_fov_mask=np.ones((1, 1), dtype=bool),
            valid_fov_pixel_size_nm=(1.0, 1.0),
        )

        np.testing.assert_allclose(
            pixelized.expected_pair_exposure,
            analytic.expected_pair_exposure,
            rtol=2e-4,
            atol=1e-8,
        )

    def test_rejects_invalid_points_windows_and_masks(self) -> None:
        cases = (
            {
                "points_xy_nm": np.asarray((1.0, 2.0)),
                "window_geometry": "rectangular",
                "window_size_nm": (2.0, 2.0),
            },
            {
                "points_xy_nm": np.asarray(((math.nan, 0.0),)),
                "window_geometry": "rectangular",
                "window_size_nm": (2.0, 2.0),
            },
            {"points_xy_nm": np.empty((0, 2)), "window_geometry": "rectangular"},
            {"points_xy_nm": np.empty((0, 2)), "window_geometry": "ellipse"},
            {
                "points_xy_nm": np.empty((0, 2)),
                "window_geometry": "irregular",
                "valid_fov_mask": np.asarray(((1, 2),)),
                "valid_fov_pixel_size_nm": (1.0, 1.0),
            },
            {
                "points_xy_nm": np.empty((0, 2)),
                "window_geometry": "irregular",
                "valid_fov_mask": np.zeros((2, 2)),
                "valid_fov_pixel_size_nm": (1.0, 1.0),
            },
        )
        for payload in cases:
            with self.subTest(payload=payload):
                with self.assertRaises((TypeError, ValueError)):
                    _compute_pair_correlation(settings=_settings(), **payload)

    def test_rejects_points_outside_window_and_graph_mismatch(self) -> None:
        with self.assertRaisesRegex(ValueError, "outside the rectangular window"):
            _compute_pair_correlation(
                np.asarray(((0.0, 0.0), (3.0, 0.0))),
                settings=_settings(),
                window_geometry="rectangular",
                window_size_nm=(2.0, 2.0),
            )
        with self.assertRaisesRegex(ValueError, "outside valid_fov_mask"):
            _compute_pair_correlation(
                np.asarray(((0.25, 0.25), (1.25, 1.25))),
                settings=_settings(),
                window_geometry="irregular",
                valid_fov_mask=np.asarray(((1, 1), (1, 0))),
                valid_fov_pixel_size_nm=(1.0, 1.0),
            )

        graph: FirstShellGraph = build_first_shell_graph(
            np.asarray(((0.0, 0.0), (1.0, 0.0))),
            point_ids=("point-a", "point-b"),
            settings=_settings(),
        )
        with self.assertRaisesRegex(ValueError, "first_shell_graph"):
            compute_pair_correlation(
                np.asarray(((0.0, 0.0), (1.0, 0.0), (2.0, 0.0))),
                point_ids=("point-a", "point-b", "point-c"),
                point_frame_indices=(0, 0, 0),
                first_shell_graph=graph,
                frame_index=0,
                settings=_settings(),
                window_geometry="rectangular",
                window_size_nm=(3.0, 2.0),
            )

        matching_graph = build_first_shell_graph(
            np.asarray(((0.0, 0.0), (1.0, 0.0))),
            point_ids=("point-a", "point-b"),
            settings=_settings(),
        )
        with self.assertRaisesRegex(ValueError, "exactly one frame"):
            compute_pair_correlation(
                np.asarray(((0.0, 0.0), (1.0, 0.0))),
                point_ids=("point-a", "point-b"),
                point_frame_indices=(0, 1),
                first_shell_graph=matching_graph,
                frame_index=0,
                settings=_settings(),
                window_geometry="rectangular",
                window_size_nm=(2.0, 2.0),
            )

        original_points = np.asarray(((0.0, 0.0), (1.5, 0.0), (3.0, 0.0)))
        folded_points = np.asarray(((0.0, 0.0), (1.5, 0.0), (0.0, 0.0)))
        original_graph = build_first_shell_graph(
            original_points,
            point_ids=("point-a", "point-b", "point-c"),
            settings=_settings(),
        )
        with self.assertRaisesRegex(ValueError, "coordinate fingerprint"):
            compute_pair_correlation(
                folded_points,
                point_ids=("point-a", "point-b", "point-c"),
                point_frame_indices=(0, 0, 0),
                first_shell_graph=original_graph,
                frame_index=0,
                settings=_settings(),
                window_geometry="rectangular",
                window_size_nm=(3.0, 2.0),
            )


if __name__ == "__main__":
    unittest.main()
