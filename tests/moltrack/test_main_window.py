import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np

from moltrack.core import MolTrackImageSeries
from nanotrack.core import STMSequenceMetadata

try:
    from PyQt6.QtWidgets import QApplication
except ImportError:  # pragma: no cover - optional outside target GUI env
    QApplication = None

if QApplication is not None:
    from PyQt6.QtWidgets import QFileDialog, QMessageBox

    from moltrack.ui import MolTrackMainWindow
else:  # pragma: no cover - optional outside target GUI env
    QFileDialog = None
    QMessageBox = None
    MolTrackMainWindow = None


@unittest.skipUnless(QApplication is not None, "PyQt6 is required for MolTrack GUI tests")
class MolTrackMainWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def tearDown(self) -> None:
        if hasattr(self, "window"):
            self.window.close()
            self.window.deleteLater()
            self.__class__._app.processEvents()

    def test_empty_workspace_exposes_file_actions_and_disables_frame_navigation(self) -> None:
        self.window = MolTrackMainWindow()

        self.assertEqual(self.window.action_open_stm.text(), "Open STM...")
        self.assertEqual(self.window.action_open_stm_reverse.text(), "Open STM Reverse...")
        self.assertEqual(self.window.lbl_frame.text(), "Frame: - / -")
        self.assertFalse(self.window.slider_frame.isEnabled())
        self.assertEqual(self.window.metadata_panel.title(), "Metadata")

    def test_canceling_open_dialog_keeps_loaded_series_unchanged(self) -> None:
        calls = []

        def fake_loader(source_path, *, reverse_frame_order=False):
            calls.append((source_path, reverse_frame_order))
            raise AssertionError("loader must not run when the dialog is canceled")

        self.window = MolTrackMainWindow(series_loader=fake_loader)
        frames = np.arange(24, dtype=np.float32).reshape(3, 2, 4)
        series = MolTrackImageSeries(
            source_path="loaded.mpp",
            raw_frames=frames,
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=2, image_type="Topo"),
        )
        self.window.set_image_series(series)

        with (
            patch.object(QFileDialog, "getOpenFileName", return_value=("", "")),
            patch.object(QMessageBox, "critical", return_value=QMessageBox.StandardButton.Ok) as critical,
        ):
            self.window.action_open_stm.trigger()
            self.__class__._app.processEvents()

        self.assertEqual(calls, [])
        self.assertEqual(self.window.lbl_frame.text(), "Frame: 1 / 3")
        np.testing.assert_array_equal(self.window.viewer.viewer.image_item.image, frames[0])
        self.assertIn("Active frame: 1 / 3", self.window.metadata_panel.metadata_text())
        critical.assert_not_called()

    def test_open_dialog_loader_error_reports_problem_and_preserves_loaded_series(self) -> None:
        calls = []

        def fake_loader(source_path, *, reverse_frame_order=False):
            calls.append((source_path, reverse_frame_order))
            raise ValueError(f"Only .mpp STM movies are supported: {source_path}")

        self.window = MolTrackMainWindow(series_loader=fake_loader)
        frames = np.arange(24, dtype=np.float32).reshape(3, 2, 4)
        series = MolTrackImageSeries(
            source_path="current.mpp",
            raw_frames=frames,
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=2, image_type="Topo"),
        )
        self.window.set_image_series(series)
        self.window.slider_frame.setValue(2)
        self.__class__._app.processEvents()

        with (
            patch.object(QFileDialog, "getOpenFileName", return_value=("bad.txt", "")),
            patch.object(QMessageBox, "critical", return_value=QMessageBox.StandardButton.Ok) as critical,
        ):
            self.window.action_open_stm.trigger()
            self.__class__._app.processEvents()

        self.assertEqual(calls, [("bad.txt", False)])
        self.assertEqual(series.active_frame_index, 2)
        self.assertEqual(self.window.lbl_frame.text(), "Frame: 3 / 3")
        np.testing.assert_array_equal(self.window.viewer.viewer.image_item.image, frames[2])
        metadata_text = self.window.metadata_panel.metadata_text()
        self.assertIn("Source: current.mpp", metadata_text)
        self.assertIn("Active frame: 3 / 3", metadata_text)
        critical.assert_called_once()
        _parent, title, message = critical.call_args.args
        self.assertEqual(title, "Open STM failed")
        self.assertIn("bad.txt", message)
        self.assertIn("Open STM failed", self.window.statusBar().currentMessage())

    def test_setting_series_enables_frame_navigation_and_slider_selects_frame(self) -> None:
        self.window = MolTrackMainWindow()
        frames = np.arange(24, dtype=np.float32).reshape(3, 2, 4)
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames,
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=2),
        )

        self.window.set_image_series(series)

        self.assertTrue(self.window.slider_frame.isEnabled())
        self.assertEqual(self.window.slider_frame.minimum(), 0)
        self.assertEqual(self.window.slider_frame.maximum(), 2)
        self.assertEqual(self.window.lbl_frame.text(), "Frame: 1 / 3")

        self.window.slider_frame.setValue(2)
        self.__class__._app.processEvents()

        self.assertEqual(series.active_frame_index, 2)
        self.assertEqual(self.window.lbl_frame.text(), "Frame: 3 / 3")
        np.testing.assert_array_equal(self.window.viewer.viewer.image_item.image, frames[2])

    def test_open_stm_source_uses_loader_and_displays_loaded_series(self) -> None:
        frames = np.zeros((2, 3, 4), dtype=np.float32)
        metadata = STMSequenceMetadata(pixels_x=4, pixels_y=3)
        calls = []

        def fake_loader(source_path, *, reverse_frame_order=False):
            calls.append((source_path, reverse_frame_order))
            return MolTrackImageSeries(
                source_path=str(source_path),
                raw_frames=frames,
                metadata=metadata,
                reverse_frame_order=reverse_frame_order,
            )

        self.window = MolTrackMainWindow(series_loader=fake_loader)

        self.window.open_stm_source("movie.mpp", reverse_frame_order=True)

        self.assertEqual(calls, [("movie.mpp", True)])
        self.assertTrue(self.window.slider_frame.isEnabled())
        self.assertEqual(self.window.slider_frame.maximum(), 1)
        self.assertEqual(self.window.lbl_frame.text(), "Frame: 1 / 2")

    def test_setting_series_updates_metadata_summary(self) -> None:
        self.window = MolTrackMainWindow()
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.zeros((3, 2, 4), dtype=np.float32),
            metadata=STMSequenceMetadata(
                pixels_x=4,
                pixels_y=2,
                size_nm_x=8.0,
                size_nm_y=1.0,
                image_type="Topo",
            ),
        )

        self.window.set_image_series(series)

        metadata_text = self.window.metadata_panel.metadata_text()
        self.assertIn("Source: movie.mpp", metadata_text)
        self.assertIn("Frames: 3", metadata_text)
        self.assertIn("Active frame: 1 / 3", metadata_text)
        self.assertIn("Shape: 4x2 px", metadata_text)
        self.assertIn("Physical size: 8 nm x 1 nm", metadata_text)
        self.assertIn("Pixel size: 2 nm/px x 0.5 nm/px", metadata_text)
        self.assertIn("Channel: Topo", metadata_text)

        self.window.slider_frame.setValue(2)
        self.__class__._app.processEvents()

        self.assertIn("Active frame: 3 / 3", self.window.metadata_panel.metadata_text())


if __name__ == "__main__":
    unittest.main()
