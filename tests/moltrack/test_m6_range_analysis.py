import math
import unittest
from dataclasses import fields, replace
from unittest.mock import patch

import numpy as np

from moltrack.analysis import (
    MolecularFrameRange,
    MolecularFrameRangeSelection,
    MolecularM6OrientationAnalysisSettings,
    build_molecular_range_comparison_trend_data,
    compare_molecular_frame_ranges,
)
from moltrack.analysis.m6_errors import M6BlockingGraphQCError
from moltrack.core import MolecularDetection, MolecularDetectionSet, MolTrackImageSeries
from nanotrack.core import STMSequenceMetadata


def _triangular_patch(
    angle_deg: float,
    shift_xy_nm: tuple[float, float],
    *,
    width: int = 8,
    height: int = 8,
) -> np.ndarray:
    points = np.asarray(
        [
            (2.0 * (column + 0.5 * (row % 2)), math.sqrt(3.0) * row)
            for row in range(height)
            for column in range(width)
        ],
        dtype=np.float64,
    )
    angle = math.radians(angle_deg)
    rotation = np.asarray(
        ((math.cos(angle), -math.sin(angle)), (math.sin(angle), math.cos(angle)))
    )
    return points @ rotation.T + np.asarray(shift_xy_nm)


def _m6_settings() -> MolecularM6OrientationAnalysisSettings:
    return MolecularM6OrientationAnalysisSettings(
        first_shell_r_min_nm=1.5,
        first_shell_r_max_nm=2.3,
        min_ordered_component_size=3,
        min_seed_size=8,
        min_domain_size=15,
        q_seed=0.65,
        q_grow=0.25,
        seed_angle_tolerance_deg=6.0,
        grow_angle_tolerance_deg=12.0,
        domain_merge_angle_tolerance_deg=6.0,
        footprint_support_radius_nm=1.2,
        gr_bin_width_nm=0.25,
        gr_max_nm=10.0,
        gr_min_expected_pair_exposure=0.1,
    )


def _build_series(frame_points: tuple[np.ndarray, ...]) -> MolTrackImageSeries:
    frame_size = 72
    detections = MolecularDetectionSet(frame_count=len(frame_points))
    for frame_index, points in enumerate(frame_points):
        detections.set_detections(
            frame_index,
            [
                MolecularDetection(
                    frame_index=frame_index,
                    bbox_xyxy=(
                        x - 0.2,
                        frame_size - y - 0.2,
                        x + 0.2,
                        frame_size - y + 0.2,
                    ),
                    confidence=0.9,
                    detection_id=f"frame-{frame_index}-molecule-{point_index}",
                )
                for point_index, (x, y) in enumerate(points)
            ],
            source_view="raw",
            frame_shape=(frame_size, frame_size),
        )
    return MolTrackImageSeries(
        source_path="movie.mpp",
        raw_frames=np.zeros(
            (len(frame_points), frame_size, frame_size), dtype=np.float32
        ),
        metadata=STMSequenceMetadata(
            raw_header={"General Info": {"Angle": "0.0"}},
            pixels_x=frame_size,
            pixels_y=frame_size,
            size_nm_x=float(frame_size),
            size_nm_y=float(frame_size),
            scan_angle_deg=0.0,
        ),
        molecular_detections=detections,
    )


def _selection() -> MolecularFrameRangeSelection:
    return MolecularFrameRangeSelection(
        frame_count=4,
        source_view="raw",
        first_range=MolecularFrameRange("one domain", 0, 1),
        second_range=MolecularFrameRange("two domains", 2, 3),
    )


class MolecularM6RangeAnalysisTests(unittest.TestCase):
    def setUp(self) -> None:
        one_domain = _triangular_patch(0.0, (6.0, 6.0))
        one_domain_small = _triangular_patch(
            0.0,
            (6.0, 6.0),
            width=6,
            height=6,
        )
        two_domains = np.vstack(
            (
                _triangular_patch(0.0, (6.0, 6.0)),
                _triangular_patch(22.0, (38.0, 6.0)),
            )
        )
        self.series = _build_series(
            (one_domain, one_domain_small, two_domains, two_domains.copy())
        )

    def test_disabled_m6_preserves_legacy_range_contract(self) -> None:
        comparison = compare_molecular_frame_ranges(self.series, _selection())
        trends = build_molecular_range_comparison_trend_data(comparison)

        self.assertIsNone(comparison.first_analysis.aggregates.m6_orientation)
        self.assertIsNone(comparison.second_analysis.aggregates.m6_orientation)
        self.assertIsNone(comparison.differences.m6_orientation)
        self.assertIsNone(trends.first.m6_orientation)
        self.assertIsNone(trends.second.m6_orientation)

    def test_exposes_frame_trends_range_means_and_second_minus_first_deltas(self) -> None:
        self.series.source_frame_indices = (10, 20, 30, 40)
        comparison = compare_molecular_frame_ranges(
            self.series,
            _selection(),
            m6_orientation_settings=_m6_settings(),
        )
        trends = build_molecular_range_comparison_trend_data(comparison)

        first_trends = trends.first.m6_orientation
        second_trends = trends.second.m6_orientation
        self.assertIsNotNone(first_trends)
        self.assertIsNotNone(second_trends)
        assert first_trends is not None and second_trends is not None
        self.assertEqual(first_trends.availability_statuses, ("available", "available"))
        self.assertEqual(first_trends.frame_indices, (0, 1))
        self.assertEqual(first_trends.source_frame_indices, (10, 20))
        self.assertEqual(second_trends.source_frame_indices, (30, 40))
        self.assertEqual(first_trends.full_domain_counts, (1, 1))
        self.assertEqual(second_trends.full_domain_counts, (2, 2))
        self.assertEqual(second_trends.ordered_component_counts, (2, 2))

        required_metric_fields = {
            "mean_local_q6_interior",
            "mean_local_q6_all_valid",
            "global_q6_interior",
            "edge_truncated_fraction_of_valid_representatives",
            "full_domain_counts",
            "small_ordered_island_counts",
            "ordered_component_counts",
            "full_domain_molecule_fraction",
            "small_island_molecule_fraction",
            "unassigned_molecule_fraction",
            "full_domain_footprint_fraction",
            "small_island_footprint_fraction",
            "unassigned_supported_footprint_fraction",
            "unsupported_background_fraction",
            "largest_domain_molecule_fraction",
            "largest_domain_footprint_fraction",
            "full_domain_molecule_weighted_coherent_q6",
            "full_domain_footprint_weighted_coherent_q6",
            "domain_molecule_entropy",
            "domain_footprint_entropy",
        }
        self.assertTrue(required_metric_fields.issubset(first_trends.__dataclass_fields__))

        trend_to_frame_field = {
            "mean_local_q6_interior": "mean_local_q6_interior",
            "mean_local_q6_all_valid": "mean_local_q6_all_valid",
            "global_q6_interior": "global_q6_interior",
            "edge_truncated_fraction_of_valid_representatives": (
                "edge_truncated_fraction_of_valid_representatives"
            ),
            "full_domain_counts": "full_domain_count",
            "small_ordered_island_counts": "small_ordered_island_count",
            "ordered_component_counts": "ordered_component_count",
            "full_domain_molecule_fraction": "full_domain_molecule_fraction",
            "small_island_molecule_fraction": "small_island_molecule_fraction",
            "unassigned_molecule_fraction": "unassigned_molecule_fraction",
            "full_domain_footprint_fraction": "full_domain_footprint_fraction",
            "small_island_footprint_fraction": "small_island_footprint_fraction",
            "unassigned_supported_footprint_fraction": (
                "unassigned_supported_footprint_fraction"
            ),
            "unsupported_background_fraction": "unsupported_background_fraction",
            "largest_domain_molecule_fraction": "largest_domain_molecule_fraction",
            "largest_domain_footprint_fraction": "largest_domain_footprint_fraction",
            "full_domain_molecule_weighted_coherent_q6": (
                "full_domain_molecule_weighted_coherent_q6"
            ),
            "full_domain_footprint_weighted_coherent_q6": (
                "full_domain_footprint_weighted_coherent_q6"
            ),
            "domain_molecule_entropy": "domain_molecule_entropy",
            "domain_footprint_entropy": "domain_footprint_entropy",
        }
        for trend_field, frame_field in trend_to_frame_field.items():
            expected = tuple(
                getattr(result.m6_orientation_analysis.frame_aggregates, frame_field)
                for result in comparison.first_analysis.frame_results
            )
            self.assertEqual(getattr(first_trends, trend_field), expected)

        first_aggregates = comparison.first_analysis.aggregates.m6_orientation
        second_aggregates = comparison.second_analysis.aggregates.m6_orientation
        differences = comparison.differences.m6_orientation
        self.assertIsNotNone(first_aggregates)
        self.assertIsNotNone(second_aggregates)
        self.assertIsNotNone(differences)
        assert first_aggregates is not None
        assert second_aggregates is not None
        assert differences is not None
        self.assertEqual(first_aggregates.available_frame_count, 2)
        self.assertEqual(first_aggregates.mean_full_domain_count, 1.0)
        self.assertEqual(second_aggregates.mean_full_domain_count, 2.0)
        aggregate_to_trend_field = {
            "mean_local_q6_interior": "mean_local_q6_interior",
            "mean_local_q6_all_valid": "mean_local_q6_all_valid",
            "global_q6_interior": "global_q6_interior",
            "edge_truncated_fraction_of_valid_representatives": (
                "edge_truncated_fraction_of_valid_representatives"
            ),
            "mean_full_domain_count": "full_domain_counts",
            "mean_small_ordered_island_count": "small_ordered_island_counts",
            "mean_ordered_component_count": "ordered_component_counts",
            "full_domain_molecule_fraction": "full_domain_molecule_fraction",
            "small_island_molecule_fraction": "small_island_molecule_fraction",
            "unassigned_molecule_fraction": "unassigned_molecule_fraction",
            "full_domain_footprint_fraction": "full_domain_footprint_fraction",
            "small_island_footprint_fraction": "small_island_footprint_fraction",
            "unassigned_supported_footprint_fraction": (
                "unassigned_supported_footprint_fraction"
            ),
            "unsupported_background_fraction": "unsupported_background_fraction",
            "largest_domain_molecule_fraction": "largest_domain_molecule_fraction",
            "largest_domain_footprint_fraction": "largest_domain_footprint_fraction",
            "full_domain_molecule_weighted_coherent_q6": (
                "full_domain_molecule_weighted_coherent_q6"
            ),
            "full_domain_footprint_weighted_coherent_q6": (
                "full_domain_footprint_weighted_coherent_q6"
            ),
            "domain_molecule_entropy": "domain_molecule_entropy",
            "domain_footprint_entropy": "domain_footprint_entropy",
        }
        for aggregate_field, trend_field in aggregate_to_trend_field.items():
            values = tuple(
                value
                for value in getattr(first_trends, trend_field)
                if value is not None
            )
            expected = None if not values else sum(values) / len(values)
            actual = getattr(first_aggregates, aggregate_field)
            if expected is None:
                self.assertIsNone(actual)
            else:
                self.assertAlmostEqual(actual, expected)

            first_value = getattr(first_aggregates, aggregate_field)
            second_value = getattr(second_aggregates, aggregate_field)
            delta = getattr(differences, f"{aggregate_field}_delta")
            if first_value is None or second_value is None:
                self.assertIsNone(delta)
            else:
                self.assertAlmostEqual(delta, second_value - first_value)

        first_fractions = first_trends.full_domain_molecule_fraction
        self.assertNotEqual(first_fractions[0], first_fractions[1])
        pooled_fraction = (
            first_fractions[0] * 64 + first_fractions[1] * 36
        ) / 100
        self.assertNotAlmostEqual(
            first_aggregates.full_domain_molecule_fraction,
            pooled_fraction,
        )
        self.assertEqual(differences.direction, "second_minus_first")
        self.assertEqual(differences.mean_full_domain_count_delta, 1.0)
        self.assertAlmostEqual(
            differences.full_domain_molecule_fraction_delta,
            second_aggregates.full_domain_molecule_fraction
            - first_aggregates.full_domain_molecule_fraction,
        )

        public_field_names = {
            field.name
            for model in (first_trends, first_aggregates, differences)
            for field in fields(model)
        }
        self.assertFalse(any("domain_id" in name for name in public_field_names))
        self.assertFalse(comparison.uses_tracking)
        self.assertEqual(
            comparison.analysis_mode,
            "frame_position_distributions_without_tracking",
        )

        frame_result = comparison.first_analysis.frame_results[0]
        with self.assertRaisesRegex(ValueError, "requires available status"):
            replace(
                frame_result,
                m6_orientation_availability_status="disabled",
            )
        with self.assertRaisesRegex(ValueError, "requires an analysis result"):
            replace(
                frame_result,
                m6_orientation_analysis=None,
            )

    def test_marks_one_blocking_frame_unavailable_and_excludes_it_from_means(self) -> None:
        from moltrack.analysis.range_analysis import analyze_molecular_m6_orientation

        def fail_one_frame(sample_coordinates, *, settings):
            if sample_coordinates.frame_index == 1:
                raise M6BlockingGraphQCError("blocking_rank2_radius_fallback")
            return analyze_molecular_m6_orientation(
                sample_coordinates,
                settings=settings,
            )

        with patch(
            "moltrack.analysis.range_analysis.analyze_molecular_m6_orientation",
            side_effect=fail_one_frame,
        ):
            comparison = compare_molecular_frame_ranges(
                self.series,
                _selection(),
                m6_orientation_settings=_m6_settings(),
            )

        trends = build_molecular_range_comparison_trend_data(comparison)
        first_trends = trends.first.m6_orientation
        first_aggregates = comparison.first_analysis.aggregates.m6_orientation
        self.assertIsNotNone(first_trends)
        self.assertIsNotNone(first_aggregates)
        assert first_trends is not None and first_aggregates is not None
        self.assertEqual(
            first_trends.availability_statuses,
            ("available", "unavailable_blocking_graph_qc"),
        )
        self.assertEqual(
            first_trends.unavailability_reasons,
            (None, "blocking_rank2_radius_fallback"),
        )
        self.assertEqual(first_trends.full_domain_counts, (1, None))
        self.assertEqual(first_aggregates.analyzed_frame_count, 2)
        self.assertEqual(first_aggregates.available_frame_count, 1)
        self.assertEqual(first_aggregates.unavailable_frame_count, 1)
        self.assertEqual(first_aggregates.mean_full_domain_count, 1.0)


if __name__ == "__main__":
    unittest.main()
