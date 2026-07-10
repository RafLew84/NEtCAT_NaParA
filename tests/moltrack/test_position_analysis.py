import unittest

from moltrack.analysis import (
    MolecularPositionPlotData,
    build_molecular_position_plot_data,
    compute_molecular_nearest_neighbor_angle_metrics,
    compute_molecular_nearest_neighbor_metrics,
)
from moltrack.core import MolecularCentroid


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
