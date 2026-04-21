import os
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np

try:
    from PyQt6.QtWidgets import QApplication
except ImportError:  # pragma: no cover - optional outside the target GUI env
    QApplication = None

from nanotrack.core import EdgeFrameAnnotation, EdgeMetrics, EdgeTrack, PolygonROI, STMSequence, STMSequenceMetadata

if QApplication is not None:
    from nanotrack.ui.dialogs import EdgeTrackResultsDialog
else:  # pragma: no cover - optional outside the target GUI env
    EdgeTrackResultsDialog = None


@unittest.skipUnless(QApplication is not None, "PyQt6 is required for NanoTrack dialog tests")
class EdgeTrackResultsDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.dialog = EdgeTrackResultsDialog()

    def tearDown(self) -> None:
        self.dialog.close()
        self.dialog.deleteLater()
        self.__class__._app.processEvents()

    def test_set_context_populates_selector_and_plots_metric_series(self) -> None:
        sequence = STMSequence(
            source_path="/tmp/edge_results.mpp",
            raw_frames=np.zeros((4, 8, 8), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=8, pixels_y=8),
        )
        polygon = PolygonROI(np.asarray([[1.0, 1.0], [6.0, 1.0], [6.0, 6.0], [1.0, 6.0]], dtype=np.float64))
        track1 = EdgeTrack(
            edge_track_id=1,
            seed_frame_index=0,
            polygon_roi=polygon,
            seed_polyline=np.asarray([[1.0, 2.0], [6.0, 2.0]], dtype=np.float64),
        )
        track1.add_annotation(
            EdgeFrameAnnotation(
                frame_index=1,
                polyline=np.asarray([[1.0, 2.0], [6.0, 2.0]], dtype=np.float64),
                metrics=EdgeMetrics(
                    length_px=5.0,
                    roughness_rms_px=0.2,
                    mean_curvature=0.05,
                    max_curvature=0.09,
                    waviness_amplitude_px=0.4,
                ),
            )
        )
        track1.add_annotation(
            EdgeFrameAnnotation(
                frame_index=2,
                polyline=np.asarray([[1.0, 2.0], [6.0, 3.0]], dtype=np.float64),
                metrics=EdgeMetrics(
                    length_px=5.2,
                    roughness_rms_px=0.3,
                    mean_curvature=0.06,
                    max_curvature=0.11,
                    waviness_amplitude_px=0.6,
                ),
            )
        )

        self.dialog.set_context(sequence, [track1], selected_track_id=1)

        self.assertEqual(self.dialog.cmb_tracks.count(), 2)
        self.assertEqual(self.dialog.current_track_id(), 1)
        length_items = self.dialog.plot_length.plotItem.listDataItems()
        self.assertEqual(len(length_items), 1)
        x_data, y_data = length_items[0].getData()
        np.testing.assert_array_equal(x_data, np.asarray([2.0, 3.0], dtype=np.float32))
        np.testing.assert_array_equal(y_data, np.asarray([5.0, 5.2], dtype=np.float32))
        curvature_items = self.dialog.plot_curvature.plotItem.listDataItems()
        self.assertEqual(len(curvature_items), 2)
        self.assertIn("measured frames: 2 / 4", self.dialog.lbl_summary.text())

    def test_all_edge_tracks_and_nanometer_units_aggregate_plots(self) -> None:
        sequence = STMSequence(
            source_path="/tmp/edge_results_nm.mpp",
            raw_frames=np.zeros((4, 8, 8), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=8, pixels_y=8, size_nm_x=80.0, size_nm_y=40.0),
        )
        polygon = PolygonROI(np.asarray([[1.0, 1.0], [6.0, 1.0], [6.0, 6.0], [1.0, 6.0]], dtype=np.float64))
        track1 = EdgeTrack(
            edge_track_id=1,
            seed_frame_index=0,
            polygon_roi=polygon,
            seed_polyline=np.asarray([[1.0, 2.0], [6.0, 2.0]], dtype=np.float64),
        )
        track1.add_annotation(
            EdgeFrameAnnotation(
                frame_index=1,
                polyline=np.asarray([[1.0, 2.0], [6.0, 2.0]], dtype=np.float64),
                metrics=EdgeMetrics(
                    length_px=5.0,
                    length_nm=50.0,
                    roughness_rms_px=0.2,
                    roughness_rms_nm=2.0,
                    mean_curvature=0.05,
                    max_curvature=0.09,
                    waviness_amplitude_px=0.4,
                    waviness_amplitude_nm=4.0,
                ),
            )
        )
        track2 = EdgeTrack(
            edge_track_id=2,
            seed_frame_index=0,
            polygon_roi=polygon,
            seed_polyline=np.asarray([[1.0, 3.0], [6.0, 3.0]], dtype=np.float64),
        )
        track2.add_annotation(
            EdgeFrameAnnotation(
                frame_index=1,
                polyline=np.asarray([[1.0, 3.0], [6.0, 3.0]], dtype=np.float64),
                metrics=EdgeMetrics(
                    length_px=6.0,
                    length_nm=60.0,
                    roughness_rms_px=0.4,
                    roughness_rms_nm=4.0,
                    mean_curvature=0.07,
                    max_curvature=0.12,
                    waviness_amplitude_px=0.8,
                    waviness_amplitude_nm=8.0,
                ),
            )
        )

        self.dialog.set_context(sequence, [track1, track2], selected_track_id=None)
        self.dialog.cmb_units.setCurrentIndex(1)
        self.__class__._app.processEvents()

        self.assertIsNone(self.dialog.current_track_id())
        length_items = self.dialog.plot_length.plotItem.listDataItems()
        x_data, y_data = length_items[0].getData()
        np.testing.assert_array_equal(x_data, np.asarray([2.0], dtype=np.float32))
        np.testing.assert_array_equal(y_data, np.asarray([110.0], dtype=np.float32))
        roughness_items = self.dialog.plot_roughness.plotItem.listDataItems()
        _, roughness_data = roughness_items[0].getData()
        np.testing.assert_allclose(roughness_data, np.asarray([3.0], dtype=np.float32))
        curvature_items = self.dialog.plot_curvature.plotItem.listDataItems()
        _, max_curvature_data = curvature_items[1].getData()
        np.testing.assert_allclose(max_curvature_data, np.asarray([0.12], dtype=np.float32))
        self.assertIn("All edge tracks", self.dialog.lbl_summary.text())

    def test_export_results_to_path_writes_csv_pair(self) -> None:
        sequence = STMSequence(
            source_path="/tmp/edge_results_export.mpp",
            raw_frames=np.zeros((4, 8, 8), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=8, pixels_y=8, size_nm_x=80.0, size_nm_y=40.0, frame_interval_s=0.5),
        )
        polygon = PolygonROI(np.asarray([[1.0, 1.0], [6.0, 1.0], [6.0, 6.0], [1.0, 6.0]], dtype=np.float64))
        track = EdgeTrack(
            edge_track_id=1,
            seed_frame_index=0,
            polygon_roi=polygon,
            seed_polyline=np.asarray([[1.0, 2.0], [6.0, 2.0]], dtype=np.float64),
        )
        track.add_annotation(
            EdgeFrameAnnotation(
                frame_index=1,
                polyline=np.asarray([[1.0, 2.0], [6.0, 2.0]], dtype=np.float64),
                metrics=EdgeMetrics(
                    length_px=5.0,
                    length_nm=50.0,
                    roughness_rms_px=0.2,
                    roughness_rms_nm=2.0,
                    mean_curvature=0.05,
                    max_curvature=0.08,
                    waviness_amplitude_px=0.4,
                    waviness_amplitude_nm=4.0,
                ),
            )
        )
        self.dialog.set_context(sequence, [track], selected_track_id=1)

        with tempfile.TemporaryDirectory() as tmpdir:
            exported = self.dialog.export_results_to_path(f"{tmpdir}/edge_results.csv")

            self.assertTrue(os.path.exists(exported["metrics_csv"]))
            self.assertTrue(os.path.exists(exported["summary_csv"]))


if __name__ == "__main__":
    unittest.main()
