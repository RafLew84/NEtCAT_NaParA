import unittest

from moltrack.analysis import build_molecular_position_plot_data
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


if __name__ == "__main__":
    unittest.main()
