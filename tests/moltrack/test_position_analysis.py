import unittest
from types import SimpleNamespace

import numpy as np

from moltrack.analysis import (
    MolecularFrameRange,
    MolecularFrameRangeSelection,
    MolecularPositionPlotData,
    analyze_molecular_frame_range,
    build_molecular_position_plot_data,
    build_molecular_range_comparison_trend_data,
    build_molecular_range_spatial_comparison_data,
    compare_molecular_frame_ranges,
    compute_molecular_nearest_neighbor_angle_metrics,
    compute_molecular_nearest_neighbor_metrics,
)
from moltrack.core import (
    MolecularCentroid,
    MolecularDetection,
    MolecularDetectionSet,
    MolTrackImageSeries,
)
from nanotrack.core import STMSequenceMetadata


class MolecularFrameRangeSelectionTests(unittest.TestCase):
    def test_selection_preserves_two_named_ranges_and_one_source_view(self) -> None:
        selection = MolecularFrameRangeSelection(
            frame_count=12,
            source_view="expanded_aligned",
            first_range=MolecularFrameRange("before desorption", 0, 3),
            second_range=MolecularFrameRange("after adsorption", 8, 11),
        )

        self.assertEqual(selection.source_view, "expanded_aligned")
        self.assertEqual(selection.frame_count, 12)
        self.assertEqual(selection.first_range.name, "before desorption")
        self.assertEqual(selection.first_range.frame_indices, (0, 1, 2, 3))
        self.assertEqual(selection.second_range.name, "after adsorption")
        self.assertEqual(selection.second_range.frame_indices, (8, 9, 10, 11))

    def test_selection_rejects_reversed_or_out_of_series_ranges(self) -> None:
        with self.assertRaisesRegex(ValueError, "start_frame"):
            MolecularFrameRange("before desorption", 4, 3)

        with self.assertRaisesRegex(ValueError, "frame_count"):
            MolecularFrameRangeSelection(
                frame_count=10,
                source_view="raw",
                first_range=MolecularFrameRange("before desorption", 0, 2),
                second_range=MolecularFrameRange("after adsorption", 8, 10),
            )


class MolecularFrameRangeAnalysisTests(unittest.TestCase):
    def test_expanded_analysis_uses_reference_coordinates_after_registration_shift(self) -> None:
        detections = MolecularDetectionSet(frame_count=2)
        detections.set_detections(
            0,
            [
                MolecularDetection(
                    frame_index=0,
                    bbox_xyxy=(0, 3, 2, 5),
                    confidence=0.9,
                    source_view="expanded_aligned",
                )
            ],
            source_view="expanded_aligned",
            frame_shape=(6, 4),
        )
        detections.set_detections(
            1,
            [
                MolecularDetection(
                    frame_index=1,
                    bbox_xyxy=(0, 1, 2, 3),
                    confidence=0.9,
                    source_view="expanded_aligned",
                )
            ],
            source_view="expanded_aligned",
            frame_shape=(6, 4),
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.zeros((2, 4, 4), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=4),
            molecular_detections=detections,
            expanded_aligned_stack=SimpleNamespace(
                frames=np.zeros((2, 6, 4), dtype=np.float32),
                metadata=STMSequenceMetadata(pixels_x=4, pixels_y=6),
                canvas_offset_xy=(0.0, 2.0),
                padding_ltrb=(0, 2, 0, 0),
                frame_origins_xy=np.asarray(((0.0, 2.0), (0.0, 0.0))),
            ),
        )

        analysis = analyze_molecular_frame_range(
            series,
            MolecularFrameRange("registered", 0, 1),
            source_view="expanded_aligned",
        )

        self.assertEqual(analysis.frame_results[0].plot_data.points_xy, ((1.0, 2.0),))
        self.assertEqual(analysis.frame_results[1].plot_data.points_xy, ((1.0, 0.0),))
        self.assertEqual(analysis.frame_results[0].plot_data.x_range, (0.0, 4.0))
        self.assertEqual(analysis.frame_results[0].plot_data.y_range, (-2.0, 4.0))

    def test_analysis_keeps_centroids_and_metrics_separate_for_each_frame(self) -> None:
        detections = MolecularDetectionSet(frame_count=2)
        detections.set_detections(
            0,
            [
                MolecularDetection(frame_index=0, bbox_xyxy=(0, 0, 2, 2), confidence=0.9),
                MolecularDetection(frame_index=0, bbox_xyxy=(3, 0, 5, 2), confidence=0.8),
            ],
            source_view="raw",
            frame_shape=(8, 8),
        )
        detections.set_detections(
            1,
            [
                MolecularDetection(frame_index=1, bbox_xyxy=(0, 0, 2, 2), confidence=0.9),
                MolecularDetection(frame_index=1, bbox_xyxy=(0, 4, 2, 6), confidence=0.8),
            ],
            source_view="raw",
            frame_shape=(8, 8),
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.zeros((2, 8, 8), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=8, pixels_y=8),
            molecular_detections=detections,
        )

        analysis = analyze_molecular_frame_range(
            series,
            MolecularFrameRange("before desorption", 0, 1),
            source_view="raw",
        )

        self.assertEqual(analysis.frame_range.name, "before desorption")
        self.assertEqual(analysis.source_view, "raw")
        self.assertEqual(tuple(result.frame_index for result in analysis.frame_results), (0, 1))
        self.assertEqual(analysis.frame_results[0].point_count, 2)
        self.assertEqual(analysis.frame_results[0].distance_metrics.mean_distance, 3.0)
        self.assertEqual(analysis.frame_results[0].angle_metrics.line_order_score, 1.0)
        self.assertEqual(analysis.frame_results[1].point_count, 2)
        self.assertEqual(analysis.frame_results[1].distance_metrics.mean_distance, 4.0)
        self.assertEqual(analysis.frame_results[1].angle_metrics.line_order_score, 1.0)

    def test_analysis_aggregates_counts_distances_and_line_order_across_frames(self) -> None:
        detections = MolecularDetectionSet(frame_count=3)
        detections.set_detections(
            0,
            [
                MolecularDetection(frame_index=0, bbox_xyxy=(0, 0, 2, 2), confidence=0.9),
                MolecularDetection(frame_index=0, bbox_xyxy=(3, 0, 5, 2), confidence=0.8),
            ],
            source_view="raw",
            frame_shape=(8, 8),
        )
        detections.set_detections(
            1,
            [
                MolecularDetection(frame_index=1, bbox_xyxy=(0, 0, 2, 2), confidence=0.9),
                MolecularDetection(frame_index=1, bbox_xyxy=(2, 0, 4, 2), confidence=0.8),
                MolecularDetection(frame_index=1, bbox_xyxy=(0, 2, 2, 4), confidence=0.7),
                MolecularDetection(frame_index=1, bbox_xyxy=(2, 2, 4, 4), confidence=0.6),
            ],
            source_view="raw",
            frame_shape=(8, 8),
        )
        detections.set_detections(
            2,
            [MolecularDetection(frame_index=2, bbox_xyxy=(5, 5, 7, 7), confidence=0.9)],
            source_view="raw",
            frame_shape=(8, 8),
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.zeros((3, 8, 8), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=8, pixels_y=8),
            molecular_detections=detections,
        )

        analysis = analyze_molecular_frame_range(
            series,
            MolecularFrameRange("condition", 0, 2),
            source_view="raw",
        )

        self.assertEqual(analysis.aggregates.analyzed_frame_count, 3)
        self.assertEqual(analysis.aggregates.total_molecule_count, 7)
        self.assertAlmostEqual(analysis.aggregates.mean_molecule_count, 7.0 / 3.0)
        self.assertEqual(analysis.aggregates.mean_nearest_neighbor_distance, 2.5)
        self.assertAlmostEqual(analysis.aggregates.mean_line_order_score, 0.5)

    def test_analysis_keeps_empty_frames_without_inventing_metrics(self) -> None:
        detections = MolecularDetectionSet(frame_count=3)
        detections.set_detections(
            0,
            [
                MolecularDetection(frame_index=0, bbox_xyxy=(0, 0, 2, 2), confidence=0.9),
                MolecularDetection(frame_index=0, bbox_xyxy=(2, 0, 4, 2), confidence=0.8),
            ],
            source_view="raw",
            frame_shape=(6, 6),
        )
        detections.set_detections(
            2,
            [MolecularDetection(frame_index=2, bbox_xyxy=(4, 4, 6, 6), confidence=0.9)],
            source_view="raw",
            frame_shape=(6, 6),
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.zeros((3, 6, 6), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=6, pixels_y=6),
            molecular_detections=detections,
        )

        analysis = analyze_molecular_frame_range(
            series,
            MolecularFrameRange("condition", 0, 2),
            source_view="raw",
        )

        self.assertEqual(tuple(result.point_count for result in analysis.frame_results), (2, 0, 1))
        self.assertIsNone(analysis.frame_results[1].distance_metrics.mean_distance)
        self.assertIsNone(analysis.frame_results[1].angle_metrics.line_order_score)
        self.assertIsNone(analysis.frame_results[2].distance_metrics.mean_distance)
        self.assertEqual(analysis.aggregates.total_molecule_count, 3)
        self.assertEqual(analysis.aggregates.mean_molecule_count, 1.0)
        self.assertEqual(analysis.aggregates.mean_nearest_neighbor_distance, 2.0)
        self.assertEqual(analysis.aggregates.mean_line_order_score, 1.0)

    def test_analysis_isolates_expanded_view_and_uses_its_physical_geometry(self) -> None:
        detections = MolecularDetectionSet(frame_count=1)
        detections.set_detections(
            0,
            [
                MolecularDetection(
                    frame_index=0,
                    bbox_xyxy=(0, 0, 2, 2),
                    confidence=0.9,
                    detection_id="raw-only",
                )
            ],
            source_view="raw",
            frame_shape=(4, 4),
        )
        detections.set_detections(
            0,
            [
                MolecularDetection(
                    frame_index=0,
                    bbox_xyxy=(2, 1, 4, 3),
                    confidence=0.9,
                    source_view="expanded_aligned",
                    detection_id="expanded-a",
                ),
                MolecularDetection(
                    frame_index=0,
                    bbox_xyxy=(6, 1, 8, 3),
                    confidence=0.8,
                    source_view="expanded_aligned",
                    detection_id="expanded-b",
                ),
            ],
            source_view="expanded_aligned",
            frame_shape=(8, 10),
        )
        expanded_metadata = STMSequenceMetadata(
            pixels_x=10,
            pixels_y=8,
            size_nm_x=20.0,
            size_nm_y=8.0,
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.zeros((1, 4, 4), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=4),
            molecular_detections=detections,
            expanded_aligned_stack=SimpleNamespace(
                frames=np.zeros((1, 8, 10), dtype=np.float32),
                metadata=expanded_metadata,
                canvas_offset_xy=(2.0, 1.0),
                padding_ltrb=(2, 1, 0, 0),
            ),
        )

        analysis = analyze_molecular_frame_range(
            series,
            MolecularFrameRange("registered condition", 0, 0),
            source_view="expanded_aligned",
        )

        result = analysis.frame_results[0]
        self.assertEqual(tuple(centroid.source_id for centroid in result.centroids), ("expanded-a", "expanded-b"))
        self.assertEqual(result.plot_data.unit, "nm")
        self.assertEqual(result.plot_data.points_xy, ((2.0, 1.0), (10.0, 1.0)))
        self.assertEqual(result.plot_data.x_range, (-4.0, 16.0))
        self.assertEqual(result.plot_data.y_range, (-1.0, 7.0))
        self.assertEqual(result.distance_metrics.mean_distance, 8.0)
        self.assertEqual(analysis.aggregates.distance_unit, "nm")


class MolecularFrameRangeComparisonTests(unittest.TestCase):
    @staticmethod
    def _build_two_condition_series_and_selection():
        detections = MolecularDetectionSet(frame_count=2)
        detections.set_detections(
            0,
            [
                MolecularDetection(frame_index=0, bbox_xyxy=(0, 0, 2, 2), confidence=0.9),
                MolecularDetection(frame_index=0, bbox_xyxy=(2, 0, 4, 2), confidence=0.8),
            ],
            source_view="raw",
            frame_shape=(8, 8),
        )
        detections.set_detections(
            1,
            [
                MolecularDetection(frame_index=1, bbox_xyxy=(0, 0, 2, 2), confidence=0.9),
                MolecularDetection(frame_index=1, bbox_xyxy=(3, 0, 5, 2), confidence=0.8),
                MolecularDetection(frame_index=1, bbox_xyxy=(0, 3, 2, 5), confidence=0.7),
                MolecularDetection(frame_index=1, bbox_xyxy=(3, 3, 5, 5), confidence=0.6),
            ],
            source_view="raw",
            frame_shape=(8, 8),
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.zeros((2, 8, 8), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=8, pixels_y=8),
            molecular_detections=detections,
        )
        selection = MolecularFrameRangeSelection(
            frame_count=2,
            source_view="raw",
            first_range=MolecularFrameRange("before desorption", 0, 0),
            second_range=MolecularFrameRange("after adsorption", 1, 1),
        )
        return series, selection

    def test_comparison_preserves_two_separate_named_range_analyses(self) -> None:
        series, selection = self._build_two_condition_series_and_selection()

        comparison = compare_molecular_frame_ranges(series, selection)

        self.assertEqual(comparison.source_view, "raw")
        self.assertEqual(comparison.first_analysis.frame_range.name, "before desorption")
        self.assertEqual(comparison.first_analysis.frame_results[0].point_count, 2)
        self.assertEqual(comparison.second_analysis.frame_range.name, "after adsorption")
        self.assertEqual(comparison.second_analysis.frame_results[0].point_count, 4)

    def test_comparison_reports_second_minus_first_aggregate_differences(self) -> None:
        series, selection = self._build_two_condition_series_and_selection()

        comparison = compare_molecular_frame_ranges(series, selection)

        self.assertEqual(comparison.differences.direction, "second_minus_first")
        self.assertEqual(comparison.differences.mean_molecule_count_delta, 2.0)
        self.assertEqual(comparison.differences.mean_nearest_neighbor_distance_delta, 1.0)
        self.assertAlmostEqual(comparison.differences.mean_line_order_score_delta, -1.0)
        self.assertEqual(comparison.differences.distance_unit, "px")

    def test_comparison_explicitly_uses_distributions_without_tracking_or_invented_deltas(self) -> None:
        detections = MolecularDetectionSet(frame_count=2)
        detections.set_detections(
            0,
            [MolecularDetection(frame_index=0, bbox_xyxy=(0, 0, 2, 2), confidence=0.9)],
            source_view="raw",
            frame_shape=(4, 4),
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.zeros((2, 4, 4), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=4),
            molecular_detections=detections,
        )
        selection = MolecularFrameRangeSelection(
            frame_count=2,
            source_view="raw",
            first_range=MolecularFrameRange("before desorption", 0, 0),
            second_range=MolecularFrameRange("after adsorption", 1, 1),
        )

        comparison = compare_molecular_frame_ranges(series, selection)

        self.assertEqual(comparison.analysis_mode, "frame_position_distributions_without_tracking")
        self.assertFalse(comparison.uses_tracking)
        self.assertEqual(comparison.differences.mean_molecule_count_delta, -1.0)
        self.assertIsNone(comparison.differences.mean_nearest_neighbor_distance_delta)
        self.assertIsNone(comparison.differences.mean_line_order_score_delta)

    def test_trend_data_keeps_molecule_counts_assigned_to_each_named_range(self) -> None:
        series, selection = self._build_two_condition_series_and_selection()
        comparison = compare_molecular_frame_ranges(series, selection)

        trend_data = build_molecular_range_comparison_trend_data(comparison)

        self.assertEqual(trend_data.first.condition_name, "before desorption")
        self.assertEqual(trend_data.first.frame_indices, (0,))
        self.assertEqual(trend_data.first.molecule_counts, (2,))
        self.assertEqual(trend_data.second.condition_name, "after adsorption")
        self.assertEqual(trend_data.second.frame_indices, (1,))
        self.assertEqual(trend_data.second.molecule_counts, (4,))

    def test_trend_data_preserves_distance_and_line_order_gaps_per_frame(self) -> None:
        detections = MolecularDetectionSet(frame_count=4)
        detections.set_detections(
            0,
            [
                MolecularDetection(frame_index=0, bbox_xyxy=(0, 0, 2, 2), confidence=0.9),
                MolecularDetection(frame_index=0, bbox_xyxy=(2, 0, 4, 2), confidence=0.8),
            ],
            source_view="raw",
            frame_shape=(8, 8),
        )
        detections.set_detections(
            2,
            [
                MolecularDetection(frame_index=2, bbox_xyxy=(0, 0, 2, 2), confidence=0.9),
                MolecularDetection(frame_index=2, bbox_xyxy=(3, 0, 5, 2), confidence=0.8),
                MolecularDetection(frame_index=2, bbox_xyxy=(0, 3, 2, 5), confidence=0.7),
                MolecularDetection(frame_index=2, bbox_xyxy=(3, 3, 5, 5), confidence=0.6),
            ],
            source_view="raw",
            frame_shape=(8, 8),
        )
        detections.set_detections(
            3,
            [MolecularDetection(frame_index=3, bbox_xyxy=(6, 6, 8, 8), confidence=0.9)],
            source_view="raw",
            frame_shape=(8, 8),
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.zeros((4, 8, 8), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=8, pixels_y=8),
            molecular_detections=detections,
        )
        comparison = compare_molecular_frame_ranges(
            series,
            MolecularFrameRangeSelection(
                frame_count=4,
                source_view="raw",
                first_range=MolecularFrameRange("before", 0, 1),
                second_range=MolecularFrameRange("after", 2, 3),
            ),
        )

        trend_data = build_molecular_range_comparison_trend_data(comparison)

        self.assertEqual(trend_data.first.nearest_neighbor_distances, (2.0, None))
        self.assertEqual(trend_data.first.line_order_scores, (1.0, None))
        self.assertEqual(trend_data.second.nearest_neighbor_distances, (3.0, None))
        self.assertAlmostEqual(trend_data.second.line_order_scores[0], 0.0)
        self.assertIsNone(trend_data.second.line_order_scores[1])
        self.assertEqual(trend_data.first.distance_unit, "px")
        self.assertEqual(trend_data.second.distance_unit, "px")

    def test_spatial_data_keeps_pooled_scatter_points_separate_without_tracking(self) -> None:
        series, selection = self._build_two_condition_series_and_selection()
        comparison = compare_molecular_frame_ranges(series, selection)

        spatial_data = build_molecular_range_spatial_comparison_data(comparison)

        self.assertEqual(spatial_data.first.condition_name, "before desorption")
        self.assertEqual(spatial_data.first.points_xy, ((1.0, 1.0), (3.0, 1.0)))
        self.assertEqual(spatial_data.second.condition_name, "after adsorption")
        self.assertEqual(
            spatial_data.second.points_xy,
            ((1.0, 1.0), (4.0, 1.0), (1.0, 4.0), (4.0, 4.0)),
        )
        self.assertEqual(spatial_data.unit, "px")
        self.assertEqual(spatial_data.x_range, (0.0, 8.0))
        self.assertEqual(spatial_data.y_range, (0.0, 8.0))
        self.assertEqual(spatial_data.aggregation_mode, "pooled_positions_without_tracking")

    def test_spatial_data_uses_shared_density_grid_and_color_scale(self) -> None:
        series, selection = self._build_two_condition_series_and_selection()
        comparison = compare_molecular_frame_ranges(series, selection)

        spatial_data = build_molecular_range_spatial_comparison_data(
            comparison,
            density_grid_shape=(2, 2),
        )

        self.assertEqual(spatial_data.density_x_edges, (0.0, 4.0, 8.0))
        self.assertEqual(spatial_data.density_y_edges, (0.0, 4.0, 8.0))
        self.assertEqual(spatial_data.first.density_grid, ((2.0, 0.0), (0.0, 0.0)))
        self.assertEqual(spatial_data.second.density_grid, ((1.0, 1.0), (1.0, 1.0)))
        self.assertEqual(spatial_data.density_value_range, (0.0, 2.0))
        self.assertEqual(spatial_data.density_unit, "molecules_per_frame_per_bin")


class MolecularPositionPlotDataTests(unittest.TestCase):
    def test_build_position_plot_data_exposes_pixel_points_count_and_image_axes(self) -> None:
        centroids = [
            MolecularCentroid(
                frame_index=2,
                source_view="expanded_aligned",
                x_px=2.5,
                y_px=3.5,
                source_kind="segmentation",
                source_id="seg-1",
            ),
            MolecularCentroid(
                frame_index=2,
                source_view="expanded_aligned",
                x_px=12.0,
                y_px=7.0,
                source_kind="bbox_center",
                source_id="bbox-2",
            ),
        ]

        plot_data = build_molecular_position_plot_data(
            centroids,
            frame_index=2,
            source_view="expanded_aligned",
            frame_shape=(10, 20),
        )

        self.assertEqual(plot_data.frame_index, 2)
        self.assertEqual(plot_data.source_view, "expanded_aligned")
        self.assertEqual(plot_data.points_xy, ((2.5, 3.5), (12.0, 7.0)))
        self.assertEqual(plot_data.point_count, 2)
        self.assertEqual(plot_data.unit, "px")
        self.assertEqual(plot_data.x_range, (0.0, 20.0))
        self.assertEqual(plot_data.y_range, (0.0, 10.0))

    def test_build_position_plot_data_uses_nanometers_when_physical_positions_are_available(self) -> None:
        centroids = [
            MolecularCentroid(
                frame_index=0,
                source_view="raw",
                x_px=2.0,
                y_px=3.0,
                x_nm=1.0,
                y_nm=6.0,
                source_kind="segmentation",
                source_id="seg-1",
            ),
            MolecularCentroid(
                frame_index=0,
                source_view="raw",
                x_px=10.0,
                y_px=4.0,
                x_nm=5.0,
                y_nm=8.0,
                source_kind="bbox_center",
                source_id="bbox-2",
            ),
        ]

        plot_data = build_molecular_position_plot_data(
            centroids,
            frame_index=0,
            source_view="raw",
            frame_shape=(10, 20),
            scale_nm_per_px=(0.5, 2.0),
        )

        self.assertEqual(plot_data.points_xy, ((1.0, 6.0), (5.0, 8.0)))
        self.assertEqual(plot_data.unit, "nm")
        self.assertEqual(plot_data.x_range, (0.0, 10.0))
        self.assertEqual(plot_data.y_range, (0.0, 20.0))

    def test_build_position_plot_data_rejects_centroids_from_another_frame(self) -> None:
        centroid = MolecularCentroid(
            frame_index=1,
            source_view="raw",
            x_px=2.0,
            y_px=3.0,
            source_kind="bbox_center",
            source_id="bbox-other-frame",
        )

        with self.assertRaisesRegex(ValueError, "frame_index"):
            build_molecular_position_plot_data(
                [centroid],
                frame_index=0,
                source_view="raw",
                frame_shape=(10, 20),
            )

    def test_build_position_plot_data_rejects_centroids_from_another_source_view(self) -> None:
        centroid = MolecularCentroid(
            frame_index=0,
            source_view="expanded_aligned",
            x_px=2.0,
            y_px=3.0,
            source_kind="segmentation",
            source_id="seg-other-view",
        )

        with self.assertRaisesRegex(ValueError, "source_view"):
            build_molecular_position_plot_data(
                [centroid],
                frame_index=0,
                source_view="raw",
                frame_shape=(10, 20),
            )

    def test_build_position_plot_data_returns_stable_empty_physical_plot(self) -> None:
        plot_data = build_molecular_position_plot_data(
            [],
            frame_index=4,
            source_view="expanded_aligned",
            frame_shape=(6, 8),
            scale_nm_per_px=(0.25, 0.5),
        )

        self.assertEqual(plot_data.frame_index, 4)
        self.assertEqual(plot_data.source_view, "expanded_aligned")
        self.assertEqual(plot_data.points_xy, ())
        self.assertEqual(plot_data.point_count, 0)
        self.assertEqual(plot_data.unit, "nm")
        self.assertEqual(plot_data.x_range, (0.0, 2.0))
        self.assertEqual(plot_data.y_range, (0.0, 3.0))


class MolecularNearestNeighborMetricsTests(unittest.TestCase):
    def test_nearest_neighbor_metrics_returns_per_point_distances_and_aggregates(self) -> None:
        plot_data = MolecularPositionPlotData(
            frame_index=3,
            source_view="raw",
            points_xy=((0.0, 0.0), (3.0, 0.0), (3.0, 4.0)),
            unit="px",
            x_range=(0.0, 10.0),
            y_range=(0.0, 10.0),
        )

        metrics = compute_molecular_nearest_neighbor_metrics(plot_data)

        self.assertEqual(metrics.frame_index, 3)
        self.assertEqual(metrics.source_view, "raw")
        self.assertEqual(metrics.unit, "px")
        self.assertEqual(metrics.point_count, 3)
        self.assertEqual(metrics.nearest_neighbor_distances, (3.0, 3.0, 4.0))
        self.assertAlmostEqual(metrics.mean_distance, 10.0 / 3.0)
        self.assertEqual(metrics.median_distance, 3.0)
        self.assertEqual(metrics.min_distance, 3.0)
        self.assertEqual(metrics.max_distance, 4.0)

    def test_nearest_neighbor_metrics_handles_zero_or_one_point_without_error(self) -> None:
        for points_xy in ((), ((2.0, 3.0),)):
            with self.subTest(point_count=len(points_xy)):
                plot_data = MolecularPositionPlotData(
                    frame_index=1,
                    source_view="expanded_aligned",
                    points_xy=points_xy,
                    unit="nm",
                    x_range=(0.0, 10.0),
                    y_range=(0.0, 10.0),
                )

                metrics = compute_molecular_nearest_neighbor_metrics(plot_data)

                self.assertEqual(metrics.point_count, len(points_xy))
                self.assertEqual(metrics.unit, "nm")
                self.assertEqual(metrics.nearest_neighbor_distances, ())
                self.assertIsNone(metrics.mean_distance)
                self.assertIsNone(metrics.median_distance)
                self.assertIsNone(metrics.min_distance)
                self.assertIsNone(metrics.max_distance)

    def test_nearest_neighbor_metrics_uses_physical_plot_coordinates_in_nanometers(self) -> None:
        centroids = [
            MolecularCentroid(
                frame_index=0,
                source_view="raw",
                x_px=1.0,
                y_px=1.0,
                x_nm=2.0,
                y_nm=0.5,
                source_kind="bbox_center",
                source_id="bbox-1",
            ),
            MolecularCentroid(
                frame_index=0,
                source_view="raw",
                x_px=4.0,
                y_px=5.0,
                x_nm=8.0,
                y_nm=2.5,
                source_kind="bbox_center",
                source_id="bbox-2",
            ),
        ]
        plot_data = build_molecular_position_plot_data(
            centroids,
            frame_index=0,
            source_view="raw",
            frame_shape=(8, 8),
            scale_nm_per_px=(2.0, 0.5),
        )

        metrics = compute_molecular_nearest_neighbor_metrics(plot_data)

        expected_distance_nm = (40.0) ** 0.5
        self.assertEqual(metrics.unit, "nm")
        self.assertAlmostEqual(metrics.nearest_neighbor_distances[0], expected_distance_nm)
        self.assertAlmostEqual(metrics.nearest_neighbor_distances[1], expected_distance_nm)
        self.assertAlmostEqual(metrics.mean_distance, expected_distance_nm)


class MolecularNearestNeighborAngleMetricsTests(unittest.TestCase):
    def test_horizontal_nearest_neighbor_angles_are_axial_and_fill_first_histogram_bin(self) -> None:
        plot_data = MolecularPositionPlotData(
            frame_index=0,
            source_view="raw",
            points_xy=((0.0, 0.0), (1.0, 0.0), (2.0, 0.0)),
            unit="px",
            x_range=(0.0, 3.0),
            y_range=(0.0, 1.0),
        )

        metrics = compute_molecular_nearest_neighbor_angle_metrics(plot_data)

        self.assertEqual(metrics.frame_index, 0)
        self.assertEqual(metrics.source_view, "raw")
        self.assertEqual(metrics.unit, "px")
        self.assertEqual(metrics.point_count, 3)
        self.assertEqual(metrics.nearest_neighbor_angles_degrees, (0.0, 0.0, 0.0))
        self.assertEqual(metrics.histogram_bin_edges_degrees, tuple(float(value) for value in range(0, 181, 10)))
        self.assertEqual(metrics.histogram_counts, (3,) + (0,) * 17)
        self.assertEqual(metrics.line_order_score, 1.0)

    def test_vertical_nearest_neighbor_angles_fill_ninety_degree_histogram_bin(self) -> None:
        plot_data = MolecularPositionPlotData(
            frame_index=0,
            source_view="raw",
            points_xy=((0.0, 0.0), (0.0, 1.0), (0.0, 2.0)),
            unit="px",
            x_range=(0.0, 1.0),
            y_range=(0.0, 3.0),
        )

        metrics = compute_molecular_nearest_neighbor_angle_metrics(plot_data)

        self.assertEqual(metrics.nearest_neighbor_angles_degrees, (90.0, 90.0, 90.0))
        self.assertEqual(metrics.histogram_counts, (0,) * 9 + (3,) + (0,) * 8)

    def test_nearest_neighbor_angle_ties_are_resolved_deterministically_by_point_index(self) -> None:
        plot_data = MolecularPositionPlotData(
            frame_index=0,
            source_view="raw",
            points_xy=((0.0, 1.0), (2.0, 1.0), (1.0, 0.0)),
            unit="px",
            x_range=(0.0, 3.0),
            y_range=(0.0, 2.0),
        )

        repeated_angles = tuple(
            compute_molecular_nearest_neighbor_angle_metrics(plot_data).nearest_neighbor_angles_degrees
            for _ in range(5)
        )

        self.assertEqual(repeated_angles, ((135.0, 45.0, 135.0),) * 5)
        metrics = compute_molecular_nearest_neighbor_angle_metrics(plot_data)
        expected_counts = [0] * 18
        expected_counts[4] = 1
        expected_counts[13] = 2
        self.assertEqual(metrics.histogram_counts, tuple(expected_counts))

    def test_line_order_score_is_low_for_balanced_horizontal_and_vertical_directions(self) -> None:
        plot_data = MolecularPositionPlotData(
            frame_index=0,
            source_view="raw",
            points_xy=((0.0, 0.0), (1.0, 0.0), (0.0, 1.0), (1.0, 1.0)),
            unit="px",
            x_range=(0.0, 2.0),
            y_range=(0.0, 2.0),
        )

        metrics = compute_molecular_nearest_neighbor_angle_metrics(plot_data)

        self.assertEqual(metrics.nearest_neighbor_angles_degrees, (0.0, 0.0, 90.0, 90.0))
        self.assertAlmostEqual(metrics.line_order_score, 0.0, places=12)
        self.assertLess(metrics.line_order_score, 1.0)

    def test_line_order_score_is_unavailable_for_zero_or_one_point(self) -> None:
        for points_xy in ((), ((1.0, 1.0),)):
            with self.subTest(point_count=len(points_xy)):
                plot_data = MolecularPositionPlotData(
                    frame_index=0,
                    source_view="raw",
                    points_xy=points_xy,
                    unit="px",
                    x_range=(0.0, 2.0),
                    y_range=(0.0, 2.0),
                )

                metrics = compute_molecular_nearest_neighbor_angle_metrics(plot_data)

                self.assertEqual(metrics.point_count, len(points_xy))
                self.assertEqual(metrics.nearest_neighbor_angles_degrees, ())
                self.assertIsNone(metrics.line_order_score)


if __name__ == "__main__":
    unittest.main()
