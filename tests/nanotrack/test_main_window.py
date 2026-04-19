import os
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np

try:
    from PyQt6.QtWidgets import QApplication
except ImportError:  # pragma: no cover - optional outside the target GUI env
    QApplication = None

from nanotrack.core import BBoxXYXY, ParticleTrack, STMSequence, STMSequenceMetadata
from nanotrack.io import load_mpp_sequence

if QApplication is not None:
    from nanotrack.ui.main_window import NanoTrackMainWindow
else:  # pragma: no cover - optional outside the target GUI env
    NanoTrackMainWindow = None


REPO_ROOT = Path(__file__).resolve().parents[2]
SAMPLE_MPP = REPO_ROOT / "data" / "MOVIE_3.MPP"


@unittest.skipUnless(QApplication is not None, "PyQt6 is required for NanoTrack GUI tests")
class NanoTrackMainWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.window = NanoTrackMainWindow()

    def tearDown(self) -> None:
        self.window.close()

    def test_set_sequence_enables_navigation_and_shows_first_frame(self) -> None:
        sequence = load_mpp_sequence(str(SAMPLE_MPP))

        self.window.set_sequence(sequence)

        self.assertIs(self.window.current_sequence(), sequence)
        self.assertTrue(self.window.slider_frame.isEnabled())
        self.assertTrue(self.window.spin_frame.isEnabled())
        self.assertEqual(self.window.slider_frame.maximum(), sequence.frame_count - 1)
        self.assertEqual(self.window.spin_frame.maximum(), sequence.frame_count)
        self.assertEqual(self.window.spin_frame.value(), 1)
        self.assertIn("Frame 1/", self.window.viewer.lbl_title.text())
        self.assertEqual(self.window.metadata_panel.lbl_file.text(), "MOVIE_3.MPP")
        self.assertEqual(self.window.track_list_panel.list_tracks.count(), 0)
        self.assertTrue(self.window.preprocessing_panel.btn_preview.isEnabled())
        self.assertTrue(self.window.preprocessing_panel.btn_apply_all.isEnabled())
        self.assertFalse(self.window.preprocessing_panel.chk_show_denoised.isEnabled())
        self.assertEqual(self.window.preprocessing_panel.lbl_status.text(), "No preview generated for current frame")

    def test_slider_navigation_updates_active_frame_index(self) -> None:
        sequence = load_mpp_sequence(str(SAMPLE_MPP))
        self.window.set_sequence(sequence)

        self.window.slider_frame.setValue(2)

        self.assertEqual(sequence.active_frame_index, 2)
        self.assertEqual(self.window.spin_frame.value(), 3)
        self.assertEqual(self.window.lbl_frame.text(), f"Frame: 3 / {sequence.frame_count}")

    def test_prev_next_buttons_follow_sequence_bounds(self) -> None:
        sequence = load_mpp_sequence(str(SAMPLE_MPP))
        self.window.set_sequence(sequence)

        self.window._on_next_frame()
        self.assertEqual(sequence.active_frame_index, 1)
        self.window._on_prev_frame()
        self.assertEqual(sequence.active_frame_index, 0)
        self.assertFalse(self.window.btn_prev.isEnabled())

    def test_set_tracks_populates_track_list(self) -> None:
        sequence = load_mpp_sequence(str(SAMPLE_MPP))
        self.window.set_sequence(sequence)

        tracks = [
            ParticleTrack(track_id=1, seed_frame_index=0, seed_bbox=BBoxXYXY(1.0, 2.0, 4.0, 5.0)),
            ParticleTrack(track_id=2, seed_frame_index=3, seed_bbox=BBoxXYXY(2.0, 3.0, 6.0, 7.0), label="NP-2"),
        ]

        self.window.set_tracks(tracks)

        self.assertEqual(len(self.window.current_tracks()), 2)
        self.assertEqual(self.window.track_list_panel.list_tracks.count(), 2)
        self.assertEqual(self.window.track_list_panel.lbl_summary.text(), "2 tracks")
        self.assertIn("Track 1", self.window.track_list_panel.list_tracks.item(0).text())
        self.assertIn("NP-2", self.window.track_list_panel.list_tracks.item(1).text())

    def test_long_filename_is_truncated_in_metadata_panel(self) -> None:
        sequence = STMSequence(
            source_path="/tmp/12345678901234567890.mpp",
            raw_frames=np.zeros((2, 2, 2), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=2, pixels_y=2),
        )

        self.window.set_sequence(sequence)

        self.assertEqual(self.window.metadata_panel.lbl_file.text(), "123456789012...")
        self.assertEqual(self.window.metadata_panel.lbl_file.toolTip(), "12345678901234567890.mpp")

    def test_preprocessing_panel_is_disabled_without_sequence(self) -> None:
        self.assertFalse(self.window.preprocessing_panel.btn_preview.isEnabled())
        self.assertFalse(self.window.preprocessing_panel.btn_apply_all.isEnabled())
        self.assertEqual(self.window.preprocessing_panel.lbl_status.text(), "No sequence loaded")

    @patch("nanotrack.ui.main_window.run_bm3d_batch")
    def test_apply_all_caches_denoised_frames_and_updates_status(self, run_bm3d_batch_mock) -> None:
        sequence = load_mpp_sequence(str(SAMPLE_MPP))
        self.window.set_sequence(sequence)
        denoised = np.full_like(sequence.raw_frames, 0.25, dtype=np.float32)

        def fake_batch(frames, sigma_factor, progress_callback):
            np.testing.assert_array_equal(frames, sequence.raw_frames)
            self.assertEqual(sigma_factor, 1.3)
            self.assertTrue(callable(progress_callback))
            self.assertFalse(self.window.preprocessing_panel.btn_preview.isEnabled())
            self.assertFalse(self.window.preprocessing_panel.btn_apply_all.isEnabled())
            progress_callback(1, sequence.frame_count)
            progress_callback(sequence.frame_count, sequence.frame_count)
            return denoised

        run_bm3d_batch_mock.side_effect = fake_batch

        self.window.preprocessing_panel.sp_bm3d_sigma.setValue(1.3)
        self.window.preprocessing_panel.btn_apply_all.click()

        run_bm3d_batch_mock.assert_called_once()
        np.testing.assert_array_equal(self.window.current_denoised_frames(), denoised)
        np.testing.assert_array_equal(self.window.current_denoised_frame(), denoised[0])
        self.assertTrue(self.window.preprocessing_panel.btn_preview.isEnabled())
        self.assertTrue(self.window.preprocessing_panel.btn_apply_all.isEnabled())
        self.assertTrue(self.window.preprocessing_panel.chk_show_denoised.isEnabled())
        self.assertFalse(self.window.preprocessing_panel.chk_show_denoised.isChecked())
        self.assertEqual(
            self.window.preprocessing_panel.lbl_status.text(),
            f"BM3D cached for all {sequence.frame_count} frames (sigma 1.30)",
        )
        self.assertEqual(
            self.window.statusBar().currentMessage(),
            f"BM3D applied to all {sequence.frame_count} frames.",
        )

    @patch("nanotrack.ui.main_window.run_bm3d_preview")
    def test_bm3d_preview_opens_comparison_dialog(self, run_bm3d_preview_mock) -> None:
        sequence = load_mpp_sequence(str(SAMPLE_MPP))
        self.window.set_sequence(sequence)
        denoised = np.full_like(sequence.active_frame, 0.5, dtype=np.float32)
        run_bm3d_preview_mock.return_value = denoised

        self.window.preprocessing_panel.sp_bm3d_sigma.setValue(1.7)
        self.window.preprocessing_panel.btn_preview.click()

        run_bm3d_preview_mock.assert_called_once()
        np.testing.assert_array_equal(run_bm3d_preview_mock.call_args.args[0], sequence.active_frame)
        self.assertEqual(run_bm3d_preview_mock.call_args.kwargs["sigma_factor"], 1.7)
        self.assertIsNotNone(self.window._bm3d_preview_dialog)
        self.assertTrue(self.window._bm3d_preview_dialog.isVisible())
        self.assertIn("Original | Frame 1/", self.window._bm3d_preview_dialog.raw_view.lbl_title.text())
        self.assertEqual(self.window._bm3d_preview_dialog.raw_view.lbl_meta.text(), "Raw frame")
        self.assertIn("BM3D | Frame 1/", self.window._bm3d_preview_dialog.denoised_view.lbl_title.text())
        self.assertEqual(self.window._bm3d_preview_dialog.denoised_view.lbl_meta.text(), "Sigma factor: 1.70")
        self.assertEqual(self.window.preprocessing_panel.lbl_status.text(), "Preview ready for frame 1")
        self.assertEqual(self.window.statusBar().currentMessage(), "BM3D preview opened for frame 1.")

    @patch("nanotrack.ui.main_window.run_bm3d_preview")
    @patch("nanotrack.ui.main_window.run_bm3d_batch")
    def test_bm3d_preview_uses_cached_frames_for_matching_sigma(
        self,
        run_bm3d_batch_mock,
        run_bm3d_preview_mock,
    ) -> None:
        sequence = load_mpp_sequence(str(SAMPLE_MPP))
        self.window.set_sequence(sequence)
        denoised = np.full_like(sequence.raw_frames, 0.75, dtype=np.float32)
        run_bm3d_batch_mock.return_value = denoised

        self.window.preprocessing_panel.sp_bm3d_sigma.setValue(1.4)
        self.window.preprocessing_panel.btn_apply_all.click()
        self.window.preprocessing_panel.btn_preview.click()

        run_bm3d_batch_mock.assert_called_once()
        run_bm3d_preview_mock.assert_not_called()
        self.assertIsNotNone(self.window._bm3d_preview_dialog)
        self.assertTrue(self.window._bm3d_preview_dialog.isVisible())
        self.assertEqual(self.window._bm3d_preview_dialog.denoised_view.lbl_meta.text(), "Sigma factor: 1.40")
        self.assertEqual(self.window.preprocessing_panel.lbl_status.text(), "Preview ready for frame 1")

    @patch("nanotrack.ui.main_window.run_bm3d_batch")
    def test_show_denoised_checkbox_switches_main_viewer_source(self, run_bm3d_batch_mock) -> None:
        sequence = load_mpp_sequence(str(SAMPLE_MPP))
        self.window.set_sequence(sequence)
        denoised = np.full_like(sequence.raw_frames, 0.9, dtype=np.float32)
        run_bm3d_batch_mock.return_value = denoised

        self.window.preprocessing_panel.sp_bm3d_sigma.setValue(1.1)
        self.window.preprocessing_panel.btn_apply_all.click()

        np.testing.assert_array_equal(self.window.viewer.viewer.image_item.image, sequence.raw_frames[0])
        self.assertIn("View: Raw", self.window.viewer.lbl_meta.text())

        self.window.preprocessing_panel.chk_show_denoised.setChecked(True)

        np.testing.assert_array_equal(self.window.viewer.viewer.image_item.image, denoised[0])
        self.assertIn("View: BM3D sigma 1.10", self.window.viewer.lbl_meta.text())

        self.window.slider_frame.setValue(1)
        np.testing.assert_array_equal(self.window.viewer.viewer.image_item.image, denoised[1])

        self.window.preprocessing_panel.chk_show_denoised.setChecked(False)
        np.testing.assert_array_equal(self.window.viewer.viewer.image_item.image, sequence.raw_frames[1])
        self.assertIn("View: Raw", self.window.viewer.lbl_meta.text())


if __name__ == "__main__":
    unittest.main()
