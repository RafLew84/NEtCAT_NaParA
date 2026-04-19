import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np

try:
    from PyQt6.QtWidgets import QApplication
except ImportError:  # pragma: no cover - optional outside the target GUI env
    QApplication = None

from nanotrack.core import BBoxXYXY, ParticleMetrics, ParticleTrack, STMSequence, STMSequenceMetadata, TrackFrameAnnotation

if QApplication is not None:
    from nanotrack.ui.dialogs import TrackResultsDialog
else:  # pragma: no cover - optional outside the target GUI env
    TrackResultsDialog = None


@unittest.skipUnless(QApplication is not None, "PyQt6 is required for NanoTrack dialog tests")
class TrackResultsDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.dialog = TrackResultsDialog()

    def tearDown(self) -> None:
        self.dialog.close()
        self.dialog.deleteLater()
        self.__class__._app.processEvents()

    def test_set_context_populates_selector_and_plots_metric_series(self) -> None:
        sequence = STMSequence(
            source_path="/tmp/results.mpp",
            raw_frames=np.zeros((4, 8, 8), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=8, pixels_y=8),
        )
        track1 = ParticleTrack(track_id=1, seed_frame_index=0, seed_bbox=BBoxXYXY(1.0, 1.0, 4.0, 4.0))
        track1.add_annotation(
            TrackFrameAnnotation(
                frame_index=1,
                bbox=BBoxXYXY(2.0, 2.0, 5.0, 5.0),
                metrics=ParticleMetrics(area_px=12.0, perimeter_px=16.0, intensity_sum=24.0, intensity_mean=2.0, intensity_max=3.0),
            )
        )
        track1.add_annotation(
            TrackFrameAnnotation(
                frame_index=2,
                bbox=BBoxXYXY(3.0, 3.0, 6.0, 6.0),
                metrics=ParticleMetrics(area_px=14.0, perimeter_px=18.0, intensity_sum=30.0, intensity_mean=2.14, intensity_max=4.0),
            )
        )
        track2 = ParticleTrack(track_id=2, seed_frame_index=2, seed_bbox=BBoxXYXY(2.0, 2.0, 6.0, 6.0))
        track2.add_annotation(
            TrackFrameAnnotation(
                frame_index=3,
                bbox=BBoxXYXY(3.0, 3.0, 7.0, 7.0),
                metrics=ParticleMetrics(area_px=21.0, perimeter_px=24.0, intensity_sum=55.0, intensity_mean=2.62, intensity_max=5.0),
            )
        )

        self.dialog.set_context(sequence, [track1, track2], selected_track_id=1)

        self.assertEqual(self.dialog.cmb_tracks.count(), 2)
        self.assertEqual(self.dialog.current_track_id(), 1)
        area_items = self.dialog.plot_area.plotItem.listDataItems()
        self.assertEqual(len(area_items), 1)
        x_data, y_data = area_items[0].getData()
        np.testing.assert_array_equal(x_data, np.asarray([2.0, 3.0], dtype=np.float32))
        np.testing.assert_array_equal(y_data, np.asarray([12.0, 14.0], dtype=np.float32))
        intensity_items = self.dialog.plot_intensity.plotItem.listDataItems()
        self.assertEqual(len(intensity_items), 3)
        self.assertIn("measured frames: 2 / 4", self.dialog.lbl_summary.text())

    def test_changing_track_updates_plots_and_emits_selection(self) -> None:
        sequence = STMSequence(
            source_path="/tmp/results.mpp",
            raw_frames=np.zeros((4, 8, 8), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=8, pixels_y=8),
        )
        track1 = ParticleTrack(track_id=1, seed_frame_index=0, seed_bbox=BBoxXYXY(1.0, 1.0, 4.0, 4.0))
        track1.add_annotation(
            TrackFrameAnnotation(
                frame_index=1,
                bbox=BBoxXYXY(2.0, 2.0, 5.0, 5.0),
                metrics=ParticleMetrics(area_px=12.0, perimeter_px=16.0, intensity_sum=24.0, intensity_mean=2.0, intensity_max=3.0),
            )
        )
        track2 = ParticleTrack(track_id=2, seed_frame_index=2, seed_bbox=BBoxXYXY(2.0, 2.0, 6.0, 6.0))
        track2.add_annotation(
            TrackFrameAnnotation(
                frame_index=3,
                bbox=BBoxXYXY(3.0, 3.0, 7.0, 7.0),
                metrics=ParticleMetrics(area_px=21.0, perimeter_px=24.0, intensity_sum=55.0, intensity_mean=2.62, intensity_max=5.0),
            )
        )
        selected = []
        self.dialog.track_selected.connect(selected.append)
        self.dialog.set_context(sequence, [track1, track2], selected_track_id=1)

        self.dialog.cmb_tracks.setCurrentIndex(1)
        self.__class__._app.processEvents()

        self.assertEqual(selected[-1], 2)
        area_items = self.dialog.plot_area.plotItem.listDataItems()
        x_data, y_data = area_items[0].getData()
        np.testing.assert_array_equal(x_data, np.asarray([4.0], dtype=np.float32))
        np.testing.assert_array_equal(y_data, np.asarray([21.0], dtype=np.float32))


if __name__ == "__main__":
    unittest.main()
