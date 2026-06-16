import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np

from moltrack.core import MolTrackImageSeries
from nanotrack.core import STMSequenceMetadata

try:
    from PyQt6.QtWidgets import QApplication
except ImportError:  # pragma: no cover - optional outside target GUI env
    QApplication = None

if QApplication is not None:
    from moltrack.ui.widgets import STMSeriesViewer
else:  # pragma: no cover - optional outside target GUI env
    STMSeriesViewer = None


@unittest.skipUnless(QApplication is not None, "PyQt6 is required for MolTrack viewer tests")
class STMSeriesViewerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def tearDown(self) -> None:
        if hasattr(self, "viewer"):
            self.viewer.close()
            self.viewer.deleteLater()
            self.__class__._app.processEvents()

    def test_viewer_displays_active_frame_with_series_context(self) -> None:
        frames = np.arange(24, dtype=np.float32).reshape(3, 2, 4)
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames,
            metadata=STMSequenceMetadata(
                pixels_x=4,
                pixels_y=2,
                size_nm_x=8.0,
                size_nm_y=1.0,
                image_type="Topo",
            ),
            active_frame_index=1,
        )
        self.viewer = STMSeriesViewer()

        self.viewer.set_image_series(series)

        np.testing.assert_array_equal(self.viewer.viewer.image_item.image, frames[1])
        self.assertEqual(self.viewer.lbl_title.text(), "movie.mpp | Frame 2/3")
        self.assertIn("Shape: 4x2 px", self.viewer.lbl_meta.text())
        self.assertIn("Channel: Topo", self.viewer.lbl_meta.text())

    def test_viewer_maps_pixels_to_physical_nanometers(self) -> None:
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.zeros((1, 2, 4), dtype=np.float32),
            metadata=STMSequenceMetadata(
                pixels_x=4,
                pixels_y=2,
                size_nm_x=8.0,
                size_nm_y=1.0,
            ),
        )
        self.viewer = STMSeriesViewer()

        self.viewer.set_image_series(series)

        transform = self.viewer.viewer.image_item.transform()
        self.assertAlmostEqual(transform.m11(), 2.0)
        self.assertAlmostEqual(transform.m22(), 0.5)


if __name__ == "__main__":
    unittest.main()
