import math
import unittest
from dataclasses import FrozenInstanceError

import numpy as np

from moltrack.analysis import (
    FirstShellSuggestionResult,
    MolecularM6OrientationAnalysisSettings,
    PairCorrelationResult,
    suggest_first_shell_r_max,
)


def _settings(
    *,
    bin_width: float = 0.5,
    bin_count: int = 12,
    minimum_exposure: float = 50.0,
    minimum_frames: int = 1,
    smoothing_method: str = "gaussian_bins",
    smoothing_width: float = 0.2,
    prominence: float = 0.3,
) -> MolecularM6OrientationAnalysisSettings:
    return MolecularM6OrientationAnalysisSettings(
        first_shell_r_min_nm=1.0,
        first_shell_r_max_nm=2.6,
        gr_bin_width_nm=bin_width,
        gr_max_nm=bin_width * bin_count,
        gr_min_expected_pair_exposure=minimum_exposure,
        gr_min_contributing_frames=minimum_frames,
        gr_smoothing_method=smoothing_method,
        gr_smoothing_width=smoothing_width,
        gr_peak_prominence=prominence,
    )


def _pair_correlation(
    g_values: tuple[float, ...],
    *,
    bin_width: float = 0.5,
    exposure: tuple[float, ...] | None = None,
    contributions: tuple[int, ...] | None = None,
    geometry_status: str = "rectangular_translation_correction",
    point_count: int = 100,
    result_minimum_exposure: float = 1.0,
) -> PairCorrelationResult:
    bin_count = len(g_values)
    edges = tuple(index * bin_width for index in range(bin_count + 1))
    centers = tuple((left + right) / 2.0 for left, right in zip(edges, edges[1:]))
    if exposure is None:
        exposure = tuple(100.0 if math.isfinite(value) else float("nan") for value in g_values)
    if contributions is None:
        contributions = tuple(int(math.isfinite(value)) for value in exposure)
    observed = tuple(
        int(round(value * expected))
        if math.isfinite(value) and math.isfinite(expected)
        else 0
        for value, expected in zip(g_values, exposure)
    )
    statuses = tuple(
        "valid"
        if (
            math.isfinite(value)
            and math.isfinite(expected)
            and expected >= result_minimum_exposure
        )
        else "insufficient_exposure"
        for value, expected in zip(g_values, exposure)
    )
    unsupported = geometry_status == "unsupported_window_geometry"
    if unsupported:
        exposure = (float("nan"),) * bin_count
        g_values = (float("nan"),) * bin_count
        observed = (0,) * bin_count
        statuses = ("unsupported_window_geometry",) * bin_count
        contributions = (0,) * bin_count

    return PairCorrelationResult(
        bin_edges_nm=edges,
        bin_centers_nm=centers,
        g_r=g_values,
        observed_unordered_pair_count=observed,
        expected_pair_exposure=exposure,
        bin_status=statuses,
        contributing_frame_count=contributions,
        point_count=point_count,
        total_unordered_pair_count=point_count * (point_count - 1) // 2,
        min_expected_pair_exposure=result_minimum_exposure,
        window_area_nm2=None if unsupported else 100.0,
        window_geometry_status=geometry_status,
        frame_index=3,
        representative_point_ids=tuple(f"point-{index}" for index in range(point_count)),
        coordinate_frame="sample_nm",
        spatial_calibration_fingerprint="calibration-v1",
        registration_fingerprint="registration-v1",
        point_coordinate_fingerprint="coordinates-v1",
        window_origin_nm=(0.0, 0.0),
    )


class FirstShellSuggestionTests(unittest.TestCase):
    def test_proposes_first_allowed_peak_and_first_following_minimum(self) -> None:
        pair_correlation = _pair_correlation(
            (
                0.2,
                1.8,  # A short-range QC peak below first_shell_r_min_nm.
                0.4,
                0.7,
                1.7,
                0.8,
                0.0,  # A physical zero is a valid minimum, not missing data.
                0.6,
                0.9,
                0.7,
                0.8,
                0.7,
            )
        )

        result = suggest_first_shell_r_max(pair_correlation, settings=_settings())

        self.assertIsInstance(result, FirstShellSuggestionResult)
        self.assertEqual(result.quality_status, "valid_suggestion")
        self.assertEqual(result.peak_bin_index, 4)
        self.assertEqual(result.peak_radius_nm, 2.25)
        self.assertGreaterEqual(result.peak_prominence, 0.3)
        self.assertEqual(result.minimum_bin_index, 6)
        self.assertEqual(result.minimum_radius_nm, 3.25)
        self.assertEqual(result.suggested_first_shell_r_max_nm, 3.25)
        self.assertEqual(result.raw_g_r, pair_correlation.g_r)
        self.assertEqual(result.search_min_radius_nm, 1.0)
        self.assertEqual(result.distance_unit, "nm")
        self.assertEqual(
            result,
            suggest_first_shell_r_max(pair_correlation, settings=_settings()),
        )

        with self.assertRaises(FrozenInstanceError):
            result.quality_status = "no_reliable_peak"

    def test_peak_at_inclusive_search_boundary_uses_previous_valid_bin_as_context(self) -> None:
        pair_correlation = _pair_correlation((0.2, 0.5, 2.0, 1.2, 0.5, 0.8))

        result = suggest_first_shell_r_max(
            pair_correlation,
            settings=_settings(bin_count=6),
        )

        self.assertEqual(result.quality_status, "valid_suggestion")
        self.assertEqual(result.peak_bin_index, 2)
        self.assertEqual(result.peak_radius_nm, 1.25)
        self.assertEqual(result.minimum_bin_index, 4)

    def test_normalized_smoothing_does_not_turn_nan_gaps_into_zero(self) -> None:
        pair_correlation = _pair_correlation(
            (
                1.0,
                1.0,
                float("nan"),
                float("nan"),
                float("nan"),
                float("nan"),
                float("nan"),
                1.0,
                1.0,
            )
        )

        result = suggest_first_shell_r_max(
            pair_correlation,
            settings=_settings(bin_count=9, smoothing_width=0.4, prominence=0.1),
        )

        finite_values = np.asarray(result.smoothed_g_r)[np.isfinite(result.smoothed_g_r)]
        np.testing.assert_allclose(finite_values, 1.0, rtol=0.0, atol=1e-12)
        self.assertTrue(math.isnan(result.smoothed_g_r[4]))
        self.assertEqual(result.smoothing_support[4], 0.0)
        self.assertEqual(
            result.valid_bin_mask,
            (True, True, False, False, False, False, False, True, True),
        )
        self.assertTrue(math.isnan(result.raw_g_r[2]))
        self.assertEqual(result.quality_status, "insufficient_valid_range")
        self.assertIsNone(result.suggested_first_shell_r_max_nm)

    def test_peak_without_following_local_minimum_is_not_a_proposal(self) -> None:
        pair_correlation = _pair_correlation(
            (0.2, 1.8, 0.4, 0.8, 1.7, 1.2, 1.0, 0.9, 0.8, 0.7)
        )

        result = suggest_first_shell_r_max(
            pair_correlation,
            settings=_settings(bin_count=10),
        )

        self.assertEqual(result.quality_status, "no_minimum_after_peak")
        self.assertEqual(result.peak_bin_index, 4)
        self.assertIsNone(result.minimum_bin_index)
        self.assertIsNone(result.suggested_first_shell_r_max_nm)

    def test_peak_without_enough_following_range_is_an_insufficient_range(self) -> None:
        pair_correlation = _pair_correlation((0.2, 1.8, 0.4, 0.8, 1.7, 1.0))

        result = suggest_first_shell_r_max(
            pair_correlation,
            settings=_settings(bin_count=6),
        )

        self.assertEqual(result.quality_status, "insufficient_valid_range")
        self.assertEqual(result.peak_bin_index, 4)
        self.assertIsNone(result.minimum_bin_index)
        self.assertIsNone(result.suggested_first_shell_r_max_nm)

    def test_noise_below_prominence_does_not_create_a_proposal(self) -> None:
        pair_correlation = _pair_correlation(
            (0.2, 1.8, 1.00, 1.03, 1.01, 1.04, 1.02, 1.00)
        )

        result = suggest_first_shell_r_max(
            pair_correlation,
            settings=_settings(bin_count=8, prominence=0.1),
        )

        self.assertEqual(result.quality_status, "no_reliable_peak")
        self.assertIsNone(result.peak_bin_index)
        self.assertIsNone(result.suggested_first_shell_r_max_nm)

    def test_physical_zero_curve_is_data_but_has_no_reliable_peak(self) -> None:
        pair_correlation = _pair_correlation((0.0,) * 8)

        result = suggest_first_shell_r_max(
            pair_correlation,
            settings=_settings(bin_count=8),
        )

        self.assertEqual(result.quality_status, "no_reliable_peak")
        self.assertIsNone(result.suggested_first_shell_r_max_nm)

    def test_fewer_than_two_points_has_explicit_insufficient_pair_status(self) -> None:
        pair_correlation = _pair_correlation(
            (float("nan"),) * 8,
            point_count=1,
        )

        result = suggest_first_shell_r_max(
            pair_correlation,
            settings=_settings(bin_count=8),
        )

        self.assertEqual(result.quality_status, "insufficient_pair_count")
        self.assertIsNone(result.suggested_first_shell_r_max_nm)

    def test_exposure_and_contributing_frame_thresholds_limit_search_range(self) -> None:
        pair_correlation = _pair_correlation(
            (0.2, 1.8, 0.4, 1.7, 0.0, 0.6),
            exposure=(100.0, 100.0, 40.0, 100.0, 100.0, 100.0),
        )

        exposure_result = suggest_first_shell_r_max(
            pair_correlation,
            settings=_settings(bin_count=6, minimum_exposure=50.0),
        )
        frames_result = suggest_first_shell_r_max(
            pair_correlation,
            settings=_settings(bin_count=6, minimum_frames=2),
        )

        self.assertFalse(exposure_result.valid_bin_mask[2])
        self.assertEqual(frames_result.quality_status, "insufficient_valid_range")
        self.assertFalse(any(frames_result.valid_bin_mask))

    def test_disconnected_single_bins_are_an_insufficient_search_range(self) -> None:
        pair_correlation = _pair_correlation(
            (0.2, 1.8, 0.5, float("nan"), 1.2, float("nan"), 0.4)
        )

        result = suggest_first_shell_r_max(
            pair_correlation,
            settings=_settings(bin_count=7),
        )

        self.assertEqual(result.quality_status, "insufficient_valid_range")

    def test_unsupported_smoothing_method_and_geometry_return_quality_status(self) -> None:
        pair_correlation = _pair_correlation((0.2, 1.8, 0.4, 1.7, 0.0, 0.6))
        unsupported_geometry = _pair_correlation(
            (float("nan"),) * 6,
            geometry_status="unsupported_window_geometry",
        )

        method_result = suggest_first_shell_r_max(
            pair_correlation,
            settings=_settings(bin_count=6, smoothing_method="median"),
        )
        geometry_result = suggest_first_shell_r_max(
            unsupported_geometry,
            settings=_settings(bin_count=6),
        )

        self.assertEqual(method_result.quality_status, "unsupported_smoothing_method")
        self.assertTrue(all(math.isnan(value) for value in method_result.smoothed_g_r))
        self.assertEqual(
            geometry_result.quality_status,
            "unsupported_window_geometry",
        )

    def test_rejects_pair_correlation_computed_with_different_binning(self) -> None:
        pair_correlation = _pair_correlation((0.2, 1.8, 0.4, 1.7, 0.0, 0.6))

        with self.assertRaisesRegex(ValueError, "binning"):
            suggest_first_shell_r_max(
                pair_correlation,
                settings=_settings(bin_width=0.25, bin_count=12),
            )

    def test_rejects_lower_exposure_threshold_than_used_for_pair_correlation(self) -> None:
        pair_correlation = _pair_correlation(
            (0.2, 1.8, float("nan"), 1.7, 0.0, 0.6),
            exposure=(100.0, 100.0, 40.0, 100.0, 100.0, 100.0),
            result_minimum_exposure=80.0,
        )

        with self.assertRaisesRegex(ValueError, "minimum exposure"):
            suggest_first_shell_r_max(
                pair_correlation,
                settings=_settings(bin_count=6, minimum_exposure=20.0),
            )


if __name__ == "__main__":
    unittest.main()
