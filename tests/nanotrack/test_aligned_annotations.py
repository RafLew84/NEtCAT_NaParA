"""Original/Aligned interaction and persistence through the running Qt interface."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pyqtgraph as pg
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QPointF

from nanotrack.app import configure_pyqtgraph
from nanotrack.core import BBoxXYXY, PolygonROI, RegistrationFrameResult, RegistrationResultSet, RegistrationSettings
from nanotrack.io import load_mpp_sequence
from nanotrack.persistence.session_store import NanoTrackSessionSnapshot, save_session_snapshot
from nanotrack.ui.main_window import NanoTrackMainWindow
from nanotrack.ui.widgets.sequence_viewer_widget import SequenceViewerWidget
from nanotrack.core import STMSequence, STMSequenceMetadata
from nanotrack.registration.scalar_frames import FrameGeometry


class AlignedAnnotationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        configure_pyqtgraph()
        cls.app = QApplication.instance() or QApplication([])

    def test_missing_measurements_render_as_black_independent_of_contrast(self):
        widget = SequenceViewerWidget()
        self.addCleanup(widget.close)
        widget.resize(900, 700)
        widget.show()
        values = np.arange(32*32, dtype=np.float64).reshape(32, 32)
        values[8:16, 8:16] = np.nan
        sequence = STMSequence("S1.MPP", values[None], STMSequenceMetadata(pixels_x=32, pixels_y=32))
        widget.set_sequence(sequence)
        widget.show_frame(0, geometry=FrameGeometry())
        self.app.processEvents()
        widget.viewer.hist.setLevels(0., 1023.)
        point = widget.viewer.plot_item.getViewBox().mapViewToScene(QPointF(12., 12.))
        pixel = widget.viewer.glw.mapFromScene(point)
        color = widget.viewer.glw.viewport().grab().toImage().pixelColor(pixel)
        self.assertEqual((color.red(), color.green(), color.blue()), (0, 0, 0))
        widget.viewer.hist.setLevels(-1000., 1500.)
        widget.viewer.set_gamma(2.)
        self.app.processEvents()
        color = widget.viewer.glw.viewport().grab().toImage().pixelColor(pixel)
        self.assertEqual((color.red(), color.green(), color.blue()), (0, 0, 0))

    def test_missing_pixels_do_not_quantize_valid_float64_display_samples(self):
        widget = SequenceViewerWidget()
        self.addCleanup(widget.close)
        values = 1e8 + np.arange(32*32, dtype=np.float64).reshape(32, 32) / 1024
        values[0, 0] = np.nan
        sequence = STMSequence("S1.MPP", values[None], STMSequenceMetadata(pixels_x=32, pixels_y=32))
        widget.set_sequence(sequence)
        widget.show_frame(0, geometry=FrameGeometry())
        self.assertEqual(float(widget.viewer.image_item.image[2, 3]), 100000000.0654296875)

    def test_aligned_edit_and_save_open_keep_source_coordinates(self):
        with TemporaryDirectory() as directory:
            source = Path(directory) / "S1.MPP"
            y, x = np.mgrid[:64, :96]
            frames = np.stack([100.123456789 + 10*y + x]*2)
            header = "[General Info]\nNumber of columns: 96\nNumber of rows: 64\nNumber of Frames: 2\n[Control]\nX Amplitude: 192 nm\nY Amplitude: 64 nm\n[Header end]\n"
            source.write_bytes(header.encode("ascii") + frames[:, ::-1, ::-1].astype("<f8").tobytes())
            sequence = load_mpp_sequence(str(source))
            sequence.set_active_frame(1)
            registration = RegistrationResultSet(RegistrationSettings(), {
                0: RegistrationFrameResult(0, (0., 0.), "identity"),
                1: RegistrationFrameResult(1, (3.25, -2.5), "manual"),
            })
            path = Path(directory) / "S1.nanotrack"
            save_session_snapshot(str(path), NanoTrackSessionSnapshot(
                sequence, registration_results=registration,
                draft_bboxes_by_frame={1: BBoxXYXY(20., 20., 28., 28.)},
                draft_polygons_by_frame={1: PolygonROI(np.array([[40., 20.], [48., 20.], [44., 28.]]))},
                draft_edge_polylines_by_frame={1: np.array([[60., 20.], [68., 24.]])},
            ))
            window = NanoTrackMainWindow()
            self.addCleanup(window.close)
            window.resize(1500, 950)
            window.show()
            window.load_session_from_path(str(path))
            window.action_show_aligned_registration.setChecked(True)
            self.app.processEvents()
            rect = next(item for item in window.viewer.viewer.plot_item.items if isinstance(item, pg.RectROI))
            self.assertAlmostEqual(rect.pos().x(), 46.5)
            self.assertAlmostEqual(rect.pos().y(), 17.5)
            self.assertEqual(window.current_aligned_frame().dtype, np.float64)
            self.assertAlmostEqual(window.current_aligned_frame()[20, 20], 341.873456789)
            # Move the visible rectangle using its public Qt graphics interface.
            rect.setPos((50.5, 20.5))
            self.app.processEvents()
            np.testing.assert_allclose(window.current_draft_bbox().as_tuple(), (22., 23., 30., 31.), atol=1e-12)
            window.save_session_to_path(str(path))
            window.load_session_from_path(str(path))
            self.assertTrue(window.action_show_aligned_registration.isChecked())
            window.action_show_aligned_registration.setChecked(False)
            rect = next(item for item in window.viewer.viewer.plot_item.items if isinstance(item, pg.RectROI))
            np.testing.assert_allclose((rect.pos().x(), rect.pos().y()), (44., 23.), atol=1e-12)
            np.testing.assert_allclose(window.current_draft_bbox().as_tuple(), (22., 23., 30., 31.), atol=1e-12)


if __name__ == "__main__":
    unittest.main()
