import os
import unittest
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np

from moltrack.core import MolTrackImageSeries
from nanotrack.core import STMSequenceMetadata

try:
    from PyQt6.QtWidgets import QApplication
except ImportError:  # pragma: no cover - optional outside target GUI env
    QApplication = None

if QApplication is not None:
    from moltrack.ui.widgets import SeriesMetadataPanel
else:  # pragma: no cover - optional outside target GUI env
    SeriesMetadataPanel = None


@unittest.skipUnless(QApplication is not None, "PyQt6 is required for MolTrack metadata panel tests")
class SeriesMetadataPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def tearDown(self) -> None:
        if hasattr(self, "panel"):
            self.panel.close()
            self.panel.deleteLater()
            self.__class__._app.processEvents()

    def test_panel_can_be_initialized_without_series(self) -> None:
        self.panel = SeriesMetadataPanel()

        self.assertEqual(self.panel.title(), "Metadata")
        self.assertEqual(self.panel.metadata_text(), "No series loaded")

        self.panel.clear()

        self.assertEqual(self.panel.metadata_text(), "No series loaded")

    def test_panel_displays_series_metadata_and_active_frame(self) -> None:
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.zeros((3, 2, 4), dtype=np.float32),
            metadata=STMSequenceMetadata(
                pixels_x=4,
                pixels_y=2,
                size_nm_x=8.0,
                size_nm_y=1.0,
                image_type="Topo",
                bias_v=-0.25,
                setpoint_a=1.2e-10,
                scan_angle_deg=12.5,
                frame_interval_s=0.5,
            ),
            active_frame_index=1,
        )
        self.panel = SeriesMetadataPanel()

        self.panel.set_image_series(series)

        text = self.panel.metadata_text()
        self.assertIn("Source: movie.mpp", text)
        self.assertIn("Frames: 3", text)
        self.assertNotIn("Removed frames", text)
        self.assertIn("Active frame: 2 / 3", text)
        self.assertIn("Shape: 4x2 px", text)
        self.assertIn("Physical size: 8 nm x 1 nm", text)
        self.assertIn("Pixel size: 2 nm/px x 0.5 nm/px", text)
        self.assertIn("Channel: Topo", text)
        self.assertIn("Bias: -0.25 V", text)
        self.assertIn("Setpoint: 1.2e-10 A", text)
        self.assertIn("Scan angle: 12.5 deg", text)
        self.assertIn("Frame interval: 0.5 s", text)

    def test_panel_uses_na_for_missing_metadata(self) -> None:
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.zeros((1, 2, 4), dtype=np.float32),
            metadata=STMSequenceMetadata(
                pixels_x=4,
                pixels_y=2,
                image_type="",
            ),
        )
        self.panel = SeriesMetadataPanel()

        self.panel.set_image_series(series)

        text = self.panel.metadata_text()
        self.assertIn("Physical size: n/a nm x n/a nm", text)
        self.assertIn("Pixel size: n/a nm/px x n/a nm/px", text)
        self.assertIn("Channel: n/a", text)
        self.assertIn("Setpoint: n/a A", text)
        self.assertIn("Frame interval: n/a s", text)

    def test_panel_displays_expanded_aligned_shape_and_padding(self) -> None:
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.zeros((3, 2, 4), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=2),
        )
        series.expanded_aligned_stack = SimpleNamespace(
            frames=np.zeros((3, 5, 9), dtype=np.float32),
            padding_ltrb=(2, 1, 3, 1),
        )
        self.panel = SeriesMetadataPanel()

        self.panel.set_image_series(series)

        text = self.panel.metadata_text()
        self.assertIn("Expanded shape: 9x5 px", text)
        self.assertIn("Expanded padding: 2,1,3,1 px", text)


if __name__ == "__main__":
    unittest.main()
