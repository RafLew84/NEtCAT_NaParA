"""User-visible Expanded selection, editing and session persistence."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pyqtgraph as pg
from PyQt6.QtWidgets import QApplication

from nanotrack.app import configure_pyqtgraph
from nanotrack.ui.main_window import NanoTrackMainWindow
from scripts.nanotrack_acceptance.aligned import create_sample


class ExpandedAnnotationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        configure_pyqtgraph()
        cls.app = QApplication.instance() or QApplication([])

    def test_enable_registration_defaults_to_expanded_and_edits_survive_all_views_and_save_open(self):
        with TemporaryDirectory() as directory:
            path = create_sample(Path(directory))
            window = NanoTrackMainWindow()
            self.addCleanup(window.close)
            window.resize(1500, 950)
            window.show()
            window.load_session_from_path(str(path))
            self.assertTrue(window.action_show_aligned_registration.isChecked())
            window.action_apply_registration.setChecked(False)
            self.assertEqual(window.viewer.viewer.image_item.image.shape, (64, 96))
            window.action_apply_registration.setChecked(True)
            self.app.processEvents()
            self.assertTrue(window.action_show_expanded_aligned_registration.isChecked())
            frame = window.current_expanded_aligned_frame()
            self.assertEqual(frame.shape, (70, 102))
            self.assertEqual(frame.dtype, np.float64)
            self.assertAlmostEqual(frame[23, 22], 341.873456789, places=12)
            transform = window.viewer.viewer.image_item.transform()
            np.testing.assert_allclose((transform.m11(), transform.m22()), (2., 1.), atol=1e-12, rtol=0)
            rect = next(item for item in window.viewer.viewer.plot_item.items if isinstance(item, pg.RectROI))
            np.testing.assert_allclose((rect.pos().x(), rect.pos().y()), (50.5, 20.5), atol=1e-12)
            rect.setPos((54.5, 23.5))
            self.app.processEvents()
            np.testing.assert_allclose(window.current_draft_bbox().as_tuple(), (22., 23., 30., 31.), atol=1e-12)
            window.action_show_aligned_registration.setChecked(True)
            rect = next(item for item in window.viewer.viewer.plot_item.items if isinstance(item, pg.RectROI))
            np.testing.assert_allclose((rect.pos().x(), rect.pos().y()), (50.5, 20.5), atol=1e-12)
            window.action_apply_registration.setChecked(False)
            rect = next(item for item in window.viewer.viewer.plot_item.items if isinstance(item, pg.RectROI))
            np.testing.assert_allclose((rect.pos().x(), rect.pos().y()), (44., 23.), atol=1e-12)
            window.action_apply_registration.setChecked(True)
            window.save_session_to_path(str(path))
            window.load_session_from_path(str(path))
            self.assertTrue(window.action_apply_registration.isChecked())
            self.assertTrue(window.action_show_expanded_aligned_registration.isChecked())
            self.assertEqual(window.current_expanded_aligned_frame().shape, (70, 102))
            rect = next(item for item in window.viewer.viewer.plot_item.items if isinstance(item, pg.RectROI))
            np.testing.assert_allclose((rect.pos().x(), rect.pos().y()), (54.5, 23.5), atol=1e-12)
            np.testing.assert_allclose(window.current_draft_bbox().as_tuple(), (22., 23., 30., 31.), atol=1e-12)


if __name__ == "__main__":
    unittest.main()
