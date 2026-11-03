import math
import unittest
from dataclasses import FrozenInstanceError, replace

import numpy as np
from scipy.spatial.distance import pdist

from moltrack.analysis import (
    AggregatedPairCorrelationResult,
    MolecularFrameRange,
    MolecularM6OrientationAnalysisSettings,
    PairCorrelationResult,
    aggregate_pair_correlation_results,
    build_first_shell_graph,
    compute_pair_correlation,
    suggest_first_shell_r_max,
    suggest_shared_first_shell_r_max,
)


def _settings(
    *,
    bin_width: float = 1.0,
    bin_count: int = 3,
    minimum_exposure: float = 1.0,
    minimum_frames: int = 1,
) -> MolecularM6OrientationAnalysisSettings:
    return MolecularM6OrientationAnalysisSettings(
        gr_bin_width_nm=bin_width,
        gr_max_nm=bin_width * bin_count,
        gr_min_expected_pair_exposure=minimum_exposure,
        gr_min_contributing_frames=minimum_frames,
        gr_smoothing_width=0.2,
        gr_peak_prominence=0.3,
    )


def _frame_result(
    frame_index: int,
    *,
    observed: tuple[int, ...],
    exposure: tuple[float, ...],
    minimum_exposure: float = 1.0,
    point_count: int = 10,
    bin_width: float = 1.0,
    geometry_status: str = "rectangular_translation_correction",
    calibration_fingerprint: str = "calibration-v1",
    registration_fingerprint: str = "registration-v1",
) -> PairCorrelationResult:
    bin_count = len(observed)
    edges = tuple(index * bin_width for index in range(bin_count + 1))
    centers = tuple((left + right) / 2.0 for left, right in zip(edges, edges[1:]))
    unsupported = geometry_status == "unsupported_window_geometry"
    if unsupported:
        normalized_exposure = (float("nan"),) * bin_count
        g_values = (float("nan"),) * bin_count
        statuses = ("unsupported_window_geometry",) * bin_count
        contributions = (0,) * bin_count
    else:
        normalized_exposure = exposure
        g_values = tuple(
            count / expected
            if math.isfinite(expected) and expected >= minimum_exposure
            else float("nan")
            for count, expected in zip(observed, normalized_exposure)
        )
        statuses = tuple(
            "valid"
            if math.isfinite(expected) and expected >= minimum_exposure
            else "insufficient_exposure"
            for expected in normalized_exposure
        )
        contributions = tuple(
            int(math.isfinite(expected) and expected > 0.0)
            for expected in normalized_exposure
        )
    return PairCorrelationResult(
        bin_edges_nm=edges,
        bin_centers_nm=centers,
        g_r=g_values,
        observed_unordered_pair_count=observed,
        expected_pair_exposure=normalized_exposure,
        bin_status=statuses,
        contributing_frame_count=contributions,
        point_count=point_count,
        total_unordered_pair_count=point_count * (point_count - 1) // 2,
        min_expected_pair_exposure=minimum_exposure,
        window_area_nm2=None if unsupported else 100.0,
        window_geometry_status=geometry_status,
        frame_index=frame_index,
        representative_point_ids=tuple(
            f"frame-{frame_index}-point-{index}" for index in range(point_count)
        ),
        coordinate_frame="sample_nm",
        spatial_calibration_fingerprint=calibration_fingerprint,
        registration_fingerprint=registration_fingerprint,
        point_coordinate_fingerprint=f"coordinates-frame-{frame_index}",
        window_origin_nm=(0.0, 0.0),
    )


def _computed_frame_result(
    points: np.ndarray,
    *,
    frame_index: int,
    settings: MolecularM6OrientationAnalysisSettings,
) -> PairCorrelationResult:
    point_ids = tuple(f"frame-{frame_index}-point-{index}" for index in range(len(points)))
    graph = build_first_shell_graph(points, point_ids=point_ids, settings=settings)
    return compute_pair_correlation(
        points,
        point_ids=point_ids,
        point_frame_indices=(frame_index,) * len(points),
        first_shell_graph=graph,
        frame_index=frame_index,
        settings=settings,
        window_geometry="rectangular",
        window_size_nm=(10.0, 10.0),
    )


class PairCorrelationAggregationTests(unittest.TestCase):
    def test_uses_ratio_of_summed_counts_and_exposures_deterministically(self) -> None:
        first = _frame_result(
            3,
            observed=(0, 2, 1),
            exposure=(1.0, 2.0, 1.0),
        )
        second = _frame_result(
            4,
            observed=(0, 9, 0),
            exposure=(1.0, 3.0, 1.0),
        )
        settings = _settings(minimum_exposure=0.5)
        frame_range = MolecularFrameRange("condition A", 3, 4)

        result = aggregate_pair_correlation_results(
            (second, first),
            frame_range=frame_range,
            settings=settings,
        )

        self.assertIsInstance(result, AggregatedPairCorrelationResult)
        self.assertEqual(result.frame_range, frame_range)
        self.assertEqual(result.frame_indices, (3, 4))
        self.assertEqual(result.frame_count, 2)
        self.assertEqual(result.frame_point_counts, (10, 10))
        self.assertEqual(result.total_point_count, 20)
        self.assertEqual(result.frame_unordered_pair_counts, (45, 45))
        self.assertEqual(result.total_unordered_pair_count, 90)
        self.assertEqual(result.observed_unordered_pair_count, (0, 11, 1))
        self.assertEqual(result.expected_pair_exposure, (2.0, 5.0, 2.0))
        self.assertEqual(result.g_r, (0.0, 2.2, 0.5))
        self.assertNotEqual(result.g_r[1], (first.g_r[1] + second.g_r[1]) / 2.0)
        self.assertEqual(result.contributing_frame_count, (2, 2, 2))
        self.assertEqual(result.bin_status, ("valid", "valid", "valid"))
        self.assertEqual(
            result,
            aggregate_pair_correlation_results(
                (first, second),
                frame_range=frame_range,
                settings=settings,
            ),
        )
        with self.assertRaises(FrozenInstanceError):
            result.frame_count = 3
        with self.assertRaises(ValueError):
            replace(result, total_point_count=19)

    def test_does_not_create_cross_frame_pairs_by_concatenating_points(self) -> None:
        settings = _settings(minimum_exposure=1e-12)
        first_points = np.asarray(((2.0, 2.0), (3.0, 2.0)))
        second_points = np.asarray(((2.0, 3.0), (3.0, 3.0)))
        first = _computed_frame_result(first_points, frame_index=0, settings=settings)
        second = _computed_frame_result(second_points, frame_index=1, settings=settings)

        result = aggregate_pair_correlation_results(
            (first, second),
            frame_range=MolecularFrameRange("two frames", 0, 1),
            settings=settings,
        )
        naive_histogram, _edges = np.histogram(
            pdist(np.vstack((first_points, second_points))),
            bins=np.asarray(result.bin_edges_nm),
        )

        self.assertEqual(result.observed_unordered_pair_count, (0, 2, 0))
        self.assertEqual(result.total_unordered_pair_count, 2)
        self.assertEqual(tuple(int(value) for value in naive_histogram), (0, 6, 0))
        self.assertEqual(4 * 3 // 2, 6)

    def test_combines_low_exposure_frames_before_applying_thresholds(self) -> None:
        first = _frame_result(
            0,
            observed=(0, 3, 0),
            exposure=(3.0, 3.0, 3.0),
            minimum_exposure=10.0,
        )
        second = _frame_result(
            1,
            observed=(0, 4, 0),
            exposure=(4.0, 4.0, 4.0),
            minimum_exposure=10.0,
        )
        self.assertTrue(math.isnan(first.g_r[1]))
        self.assertTrue(math.isnan(second.g_r[1]))

        result = aggregate_pair_correlation_results(
            (first, second),
            frame_range=MolecularFrameRange("low exposure", 0, 1),
            settings=_settings(minimum_exposure=5.0, minimum_frames=2),
        )

        self.assertEqual(result.expected_pair_exposure, (7.0, 7.0, 7.0))
        self.assertEqual(result.contributing_frame_count, (2, 2, 2))
        self.assertEqual(result.bin_status, ("valid", "valid", "valid"))
        self.assertEqual(result.g_r, (0.0, 1.0, 0.0))

    def test_requires_minimum_contributing_frames_after_exposure_sum(self) -> None:
        first = _frame_result(
            0,
            observed=(0, 2, 0),
            exposure=(10.0, 10.0, 10.0),
        )
        second = _frame_result(
            1,
            observed=(0, 0, 0),
            exposure=(0.0, 0.0, 0.0),
        )

        result = aggregate_pair_correlation_results(
            (first, second),
            frame_range=MolecularFrameRange("one contributor", 0, 1),
            settings=_settings(minimum_exposure=5.0, minimum_frames=2),
        )

        self.assertEqual(result.expected_pair_exposure, (10.0, 10.0, 10.0))
        self.assertEqual(result.contributing_frame_count, (1, 1, 1))
        self.assertEqual(result.bin_status, ("insufficient_exposure",) * 3)
        self.assertTrue(all(math.isnan(value) for value in result.g_r))
        with self.assertRaisesRegex(ValueError, "contributing-frame minimum"):
            suggest_first_shell_r_max(
                result,
                settings=_settings(minimum_exposure=5.0, minimum_frames=1),
            )

    def test_aggregated_zero_observations_remain_valid_physical_zero(self) -> None:
        frames = tuple(
            _frame_result(
                frame_index,
                observed=(0, 0, 0),
                exposure=(3.0, 3.0, 3.0),
                minimum_exposure=10.0,
            )
            for frame_index in (0, 1)
        )

        result = aggregate_pair_correlation_results(
            frames,
            frame_range=MolecularFrameRange("empty shell", 0, 1),
            settings=_settings(minimum_exposure=5.0, minimum_frames=2),
        )

        self.assertEqual(result.observed_unordered_pair_count, (0, 0, 0))
        self.assertEqual(result.g_r, (0.0, 0.0, 0.0))
        self.assertEqual(result.bin_status, ("valid", "valid", "valid"))

    def test_excludes_unsupported_frame_bins_but_records_provenance(self) -> None:
        supported = _frame_result(
            0,
            observed=(0, 2, 0),
            exposure=(2.0, 2.0, 2.0),
        )
        unsupported = _frame_result(
            1,
            observed=(0, 8, 0),
            exposure=(1.0, 1.0, 1.0),
            geometry_status="unsupported_window_geometry",
        )

        result = aggregate_pair_correlation_results(
            (supported, unsupported),
            frame_range=MolecularFrameRange("partial geometry", 0, 1),
            settings=_settings(minimum_exposure=1.0),
        )

        self.assertEqual(result.observed_unordered_pair_count, (0, 2, 0))
        self.assertEqual(result.expected_pair_exposure, (2.0, 2.0, 2.0))
        self.assertEqual(result.contributing_frame_count, (1, 1, 1))
        self.assertEqual(result.window_geometry_status, "partially_unsupported_frame_windows")
        self.assertEqual(result.unsupported_frame_indices, (1,))

    def test_all_unsupported_frames_return_explicit_unsupported_aggregate(self) -> None:
        frames = tuple(
            _frame_result(
                frame_index,
                observed=(0, 4, 0),
                exposure=(1.0, 1.0, 1.0),
                geometry_status="unsupported_window_geometry",
            )
            for frame_index in (0, 1)
        )

        result = aggregate_pair_correlation_results(
            frames,
            frame_range=MolecularFrameRange("unsupported", 0, 1),
            settings=_settings(),
        )

        self.assertEqual(result.window_geometry_status, "unsupported_window_geometry")
        self.assertEqual(result.unsupported_frame_indices, (0, 1))
        self.assertEqual(result.observed_unordered_pair_count, (0, 0, 0))
        self.assertEqual(result.expected_pair_exposure, (0.0, 0.0, 0.0))
        self.assertEqual(result.contributing_frame_count, (0, 0, 0))
        self.assertEqual(result.bin_status, ("unsupported_window_geometry",) * 3)
        self.assertTrue(all(math.isnan(value) for value in result.g_r))
        self.assertEqual(
            suggest_first_shell_r_max(result, settings=_settings()).quality_status,
            "unsupported_window_geometry",
        )

    def test_rejects_positive_observation_without_positive_finite_exposure(self) -> None:
        inconsistent = _frame_result(
            0,
            observed=(0, 1, 0),
            exposure=(1.0, 0.0, 1.0),
        )

        with self.assertRaisesRegex(ValueError, "positive observed count"):
            aggregate_pair_correlation_results(
                (inconsistent,),
                frame_range=MolecularFrameRange("inconsistent", 0, 0),
                settings=_settings(),
            )

    def test_rejects_nonfinite_aggregate_exposure_sum(self) -> None:
        maximum = float(np.finfo(np.float64).max)
        frames = tuple(
            _frame_result(
                frame_index,
                observed=(0, 0, 0),
                exposure=(maximum, maximum, maximum),
            )
            for frame_index in (0, 1)
        )

        with self.assertRaisesRegex(ValueError, "aggregate exposure"):
            aggregate_pair_correlation_results(
                frames,
                frame_range=MolecularFrameRange("overflow", 0, 1),
                settings=_settings(),
            )

    def test_requires_exact_range_compatible_binning_and_coordinate_provenance(self) -> None:
        first = _frame_result(
            0,
            observed=(0, 1, 0),
            exposure=(1.0, 1.0, 1.0),
        )
        second = _frame_result(
            1,
            observed=(0, 1, 0),
            exposure=(1.0, 1.0, 1.0),
        )
        frame_range = MolecularFrameRange("condition", 0, 1)

        invalid_cases = (
            ((first,), frame_range, _settings(), "exactly one result"),
            ((first, first), frame_range, _settings(), "frame indices"),
            (
                (first, replace(second, registration_fingerprint="registration-v2")),
                frame_range,
                _settings(),
                "registration fingerprint",
            ),
            (
                (first, second),
                frame_range,
                _settings(bin_width=0.5, bin_count=6),
                "binning",
            ),
        )
        for results, selected_range, settings, message in invalid_cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(ValueError, message):
                    aggregate_pair_correlation_results(
                        results,
                        frame_range=selected_range,
                        settings=settings,
                    )

    def test_first_shell_suggestion_accepts_aggregated_pair_correlation(self) -> None:
        g_values = (0.2, 1.8, 0.4, 0.7, 1.7, 0.8, 0.0, 0.6, 0.9, 0.7, 0.8, 0.7)
        observed = tuple(int(round(value * 100.0)) for value in g_values)
        frames = tuple(
            _frame_result(
                frame_index,
                observed=observed,
                exposure=(100.0,) * len(g_values),
                bin_width=0.5,
                point_count=100,
            )
            for frame_index in (5, 6)
        )
        settings = _settings(
            bin_width=0.5,
            bin_count=len(g_values),
            minimum_exposure=100.0,
            minimum_frames=2,
        )
        aggregated = aggregate_pair_correlation_results(
            frames,
            frame_range=MolecularFrameRange("shared shell", 5, 6),
            settings=settings,
        )

        suggestion = suggest_first_shell_r_max(aggregated, settings=settings)

        self.assertEqual(suggestion.quality_status, "valid_suggestion")
        self.assertEqual(suggestion.peak_radius_nm, 2.25)
        self.assertEqual(suggestion.suggested_first_shell_r_max_nm, 3.25)

    def test_shared_suggestion_pools_two_range_histograms_without_centroids(self) -> None:
        g_values = (0.2, 1.8, 0.4, 0.7, 1.7, 0.8, 0.0, 0.6, 0.9, 0.7, 0.8, 0.7)
        observed = tuple(int(round(value * 100.0)) for value in g_values)
        frames = tuple(
            _frame_result(
                frame_index,
                observed=observed,
                exposure=(100.0,) * len(g_values),
                bin_width=0.5,
                point_count=100,
            )
            for frame_index in (0, 1, 4, 5)
        )
        settings = _settings(
            bin_width=0.5,
            bin_count=len(g_values),
            minimum_exposure=100.0,
            minimum_frames=2,
        )
        first_range = aggregate_pair_correlation_results(
            frames[:2],
            frame_range=MolecularFrameRange("before", 0, 1),
            settings=settings,
        )
        second_range = aggregate_pair_correlation_results(
            frames[2:],
            frame_range=MolecularFrameRange("after", 4, 5),
            settings=settings,
        )

        suggestion = suggest_shared_first_shell_r_max(
            first_range,
            second_range,
            settings=settings,
        )

        self.assertEqual(suggestion.quality_status, "valid_suggestion")
        self.assertEqual(suggestion.peak_radius_nm, 2.25)
        self.assertEqual(suggestion.suggested_first_shell_r_max_nm, 3.25)
        self.assertEqual(
            suggestion,
            suggest_shared_first_shell_r_max(
                second_range,
                first_range,
                settings=settings,
            ),
        )

    def test_shared_suggestion_is_not_inferred_from_only_one_supported_range(self) -> None:
        settings = _settings(minimum_exposure=1.0)
        supported = aggregate_pair_correlation_results(
            tuple(
                _frame_result(
                    frame_index,
                    observed=(0, 2, 0),
                    exposure=(2.0, 2.0, 2.0),
                )
                for frame_index in (0, 1)
            ),
            frame_range=MolecularFrameRange("supported", 0, 1),
            settings=settings,
        )
        unsupported = aggregate_pair_correlation_results(
            tuple(
                _frame_result(
                    frame_index,
                    observed=(0, 2, 0),
                    exposure=(1.0, 1.0, 1.0),
                    geometry_status="unsupported_window_geometry",
                )
                for frame_index in (4, 5)
            ),
            frame_range=MolecularFrameRange("unsupported", 4, 5),
            settings=settings,
        )

        suggestion = suggest_shared_first_shell_r_max(
            supported,
            unsupported,
            settings=settings,
        )

        self.assertEqual(suggestion.quality_status, "unsupported_window_geometry")
        self.assertIsNone(suggestion.suggested_first_shell_r_max_nm)


if __name__ == "__main__":
    unittest.main()
