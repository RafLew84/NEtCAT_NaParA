import os
import time
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np

try:
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QApplication
except ImportError:  # pragma: no cover - optional outside the target GUI env
    Qt = None
    QApplication = None

from nanotrack.core import BBoxXYXY, ParticleTrack, STMSequence, STMSequenceMetadata
from nanotrack.io import load_mpp_sequence
from nanotrack.sam2 import Sam2RunOutput

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
        if getattr(self.window, "_bm3d_preview_dialog", None) is not None:
            self.window._bm3d_preview_dialog.close()
        if getattr(self.window, "_sam2_progress_dialog", None) is not None:
            self.window._sam2_progress_dialog.close()
        self.window.close()
        self.window.deleteLater()
        self.__class__._app.processEvents()

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
        self.assertFalse(self.window.track_list_panel.btn_run_selected.isEnabled())
        self.assertFalse(self.window.track_list_panel.btn_run_all.isEnabled())
        self.assertTrue(self.window.bbox_tools_panel.btn_place.isEnabled())
        self.assertFalse(self.window.bbox_tools_panel.btn_add_seed.isEnabled())
        self.assertFalse(self.window.bbox_tools_panel.btn_clear.isEnabled())
        self.assertEqual(self.window.bbox_tools_panel.lbl_bbox.text(), "No bbox on current frame")
        self.assertTrue(self.window.preprocessing_panel.btn_preview.isEnabled())
        self.assertTrue(self.window.preprocessing_panel.btn_apply_all.isEnabled())
        self.assertTrue(self.window.preprocessing_panel.btn_repair_preview.isEnabled())
        self.assertTrue(self.window.preprocessing_panel.btn_repair_apply_all.isEnabled())
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
        self.assertFalse(self.window.bbox_tools_panel.btn_place.isEnabled())
        self.assertFalse(self.window.bbox_tools_panel.btn_add_seed.isEnabled())
        self.assertFalse(self.window.bbox_tools_panel.btn_clear.isEnabled())
        self.assertEqual(self.window.bbox_tools_panel.lbl_bbox.text(), "No sequence loaded")
        self.assertFalse(self.window.preprocessing_panel.btn_preview.isEnabled())
        self.assertFalse(self.window.preprocessing_panel.btn_apply_all.isEnabled())
        self.assertFalse(self.window.preprocessing_panel.btn_repair_preview.isEnabled())
        self.assertFalse(self.window.preprocessing_panel.btn_repair_apply_all.isEnabled())
        self.assertEqual(self.window.preprocessing_panel.lbl_status.text(), "No sequence loaded")

    def test_bbox_placement_uses_default_size_and_updates_panel(self) -> None:
        sequence = load_mpp_sequence(str(SAMPLE_MPP))
        self.window.set_sequence(sequence)
        self.window.bbox_tools_panel.sp_width.setValue(20)
        self.window.bbox_tools_panel.sp_height.setValue(10)
        self.window.bbox_tools_panel.btn_place.setChecked(True)

        bbox = self.window.viewer.place_bbox_at_pixel(30.0, 40.0)

        self.assertEqual(bbox, BBoxXYXY(20.0, 35.0, 40.0, 45.0))
        self.assertEqual(self.window.current_draft_bbox(), bbox)
        self.assertIsNotNone(self.window.viewer._bbox_roi)
        self.assertEqual(self.window.bbox_tools_panel.lbl_frame.text(), "Frame: 1")
        self.assertIn("20.0x10.0 px", self.window.bbox_tools_panel.lbl_bbox.text())
        self.assertTrue(self.window.bbox_tools_panel.btn_add_seed.isEnabled())

    def test_bbox_state_is_per_frame_and_manual_correction_updates_current_frame(self) -> None:
        sequence = load_mpp_sequence(str(SAMPLE_MPP))
        self.window.set_sequence(sequence)
        self.window.bbox_tools_panel.sp_width.setValue(16)
        self.window.bbox_tools_panel.sp_height.setValue(12)

        frame0_bbox = self.window.viewer.place_bbox_at_pixel(20.0, 22.0)
        self.assertEqual(self.window.current_draft_bbox(), frame0_bbox)

        self.window.slider_frame.setValue(1)
        self.assertIsNone(self.window.current_draft_bbox())
        self.assertIsNone(self.window.viewer.current_bbox())
        self.assertEqual(self.window.bbox_tools_panel.lbl_bbox.text(), "No bbox on current frame")

        frame1_bbox = self.window.viewer.place_bbox_at_pixel(32.0, 28.0)
        self.assertEqual(self.window.current_draft_bbox(), frame1_bbox)

        self.window.slider_frame.setValue(0)
        self.assertEqual(self.window.current_draft_bbox(), frame0_bbox)
        self.assertEqual(self.window.viewer.current_bbox(), frame0_bbox)

        corrected_bbox = BBoxXYXY(15.0, 18.0, 33.0, 34.0)
        self.window.viewer._commit_bbox(corrected_bbox)

        self.assertEqual(self.window.current_draft_bbox(), corrected_bbox)
        self.assertEqual(self.window.viewer.current_bbox(), corrected_bbox)
        self.assertIn("18.0x16.0 px", self.window.bbox_tools_panel.lbl_bbox.text())

    def test_clear_current_bbox_removes_overlay_and_state(self) -> None:
        sequence = load_mpp_sequence(str(SAMPLE_MPP))
        self.window.set_sequence(sequence)
        self.window.viewer.place_bbox_at_pixel(24.0, 24.0)

        self.window.bbox_tools_panel.btn_clear.click()

        self.assertIsNone(self.window.current_draft_bbox())
        self.assertIsNone(self.window.viewer.current_bbox())
        self.assertIsNone(self.window.viewer._bbox_roi)
        self.assertEqual(self.window.bbox_tools_panel.lbl_bbox.text(), "No bbox on current frame")
        self.assertFalse(self.window.bbox_tools_panel.btn_add_seed.isEnabled())

    def test_add_seed_creates_track_and_clears_current_draft_bbox(self) -> None:
        sequence = load_mpp_sequence(str(SAMPLE_MPP))
        self.window.set_sequence(sequence)
        bbox = self.window.viewer.place_bbox_at_pixel(24.0, 24.0)

        self.window.bbox_tools_panel.btn_add_seed.click()

        tracks = self.window.current_tracks()
        self.assertEqual(len(tracks), 1)
        self.assertEqual(tracks[0].track_id, 1)
        self.assertEqual(tracks[0].seed_frame_index, 0)
        self.assertEqual(tracks[0].seed_bbox, bbox)
        self.assertEqual(self.window.current_selected_track_id(), 1)
        self.assertEqual(self.window.track_list_panel.list_tracks.count(), 1)
        self.assertEqual(self.window.track_list_panel.current_track_id(), 1)
        self.assertTrue(self.window.track_list_panel.btn_run_selected.isEnabled())
        self.assertTrue(self.window.track_list_panel.btn_run_all.isEnabled())
        self.assertIsNone(self.window.current_draft_bbox())
        self.assertIsNone(self.window.viewer.current_bbox())
        self.assertFalse(self.window.bbox_tools_panel.btn_add_seed.isEnabled())

    def test_can_add_multiple_seed_tracks_from_different_frames_and_select_them(self) -> None:
        sequence = load_mpp_sequence(str(SAMPLE_MPP))
        self.window.set_sequence(sequence)

        self.window.viewer.place_bbox_at_pixel(20.0, 20.0)
        self.window.bbox_tools_panel.btn_add_seed.click()

        self.window.slider_frame.setValue(2)
        self.window.viewer.place_bbox_at_pixel(30.0, 35.0)
        self.window.bbox_tools_panel.btn_add_seed.click()

        tracks = self.window.current_tracks()
        self.assertEqual(len(tracks), 2)
        self.assertEqual([track.track_id for track in tracks], [1, 2])
        self.assertEqual([track.seed_frame_index for track in tracks], [0, 2])
        self.assertEqual(self.window.track_list_panel.list_tracks.count(), 2)
        self.assertEqual(self.window.current_selected_track_id(), 2)

        first_item = self.window.track_list_panel.list_tracks.item(0)
        self.window.track_list_panel.list_tracks.setCurrentItem(first_item)

        self.assertEqual(self.window.current_selected_track_id(), 1)
        self.assertEqual(sequence.active_frame_index, 0)
        self.assertEqual(self.window.viewer.current_bbox(), None)
        self.assertGreater(len(self.window.viewer.viewer._overlay_items), 0)

    def test_preprocessing_panel_uses_scroll_area_for_small_screens(self) -> None:
        panel = self.window.preprocessing_panel

        self.assertGreaterEqual(panel.content_widget.minimumWidth(), 360)
        self.assertEqual(
            panel.scroll_area.horizontalScrollBarPolicy(),
            Qt.ScrollBarPolicy.ScrollBarAsNeeded,
        )
        self.assertEqual(
            panel.scroll_area.verticalScrollBarPolicy(),
            Qt.ScrollBarPolicy.ScrollBarAsNeeded,
        )

    def test_right_sidebar_uses_scroll_area(self) -> None:
        self.assertTrue(self.window.sidebar_scroll_area.widgetResizable())
        self.assertIs(self.window.sidebar_scroll_area.widget(), self.window.sidebar_content)
        self.assertEqual(
            self.window.sidebar_scroll_area.horizontalScrollBarPolicy(),
            Qt.ScrollBarPolicy.ScrollBarAsNeeded,
        )
        self.assertEqual(
            self.window.sidebar_scroll_area.verticalScrollBarPolicy(),
            Qt.ScrollBarPolicy.ScrollBarAsNeeded,
        )

    @patch("nanotrack.ui.main_window.run_horizontal_dropout_batch")
    def test_repair_apply_all_caches_frames_and_updates_status(self, run_repair_batch_mock) -> None:
        sequence = load_mpp_sequence(str(SAMPLE_MPP))
        self.window.set_sequence(sequence)
        repaired = np.full_like(sequence.raw_frames, 0.15, dtype=np.float32)

        def fake_batch(frames, progress_callback, **params):
            np.testing.assert_array_equal(frames, sequence.raw_frames)
            self.assertTrue(callable(progress_callback))
            self.assertFalse(self.window.preprocessing_panel.btn_preview.isEnabled())
            self.assertFalse(self.window.preprocessing_panel.btn_apply_all.isEnabled())
            self.assertFalse(self.window.preprocessing_panel.btn_repair_preview.isEnabled())
            self.assertFalse(self.window.preprocessing_panel.btn_repair_apply_all.isEnabled())
            self.assertEqual(params["repair_mode"], "vertical_interp")
            progress_callback(1, sequence.frame_count)
            progress_callback(sequence.frame_count, sequence.frame_count)
            return repaired

        run_repair_batch_mock.side_effect = fake_batch

        self.window.preprocessing_panel.btn_repair_apply_all.click()

        run_repair_batch_mock.assert_called_once()
        np.testing.assert_array_equal(self.window.current_repair_frames(), repaired)
        np.testing.assert_array_equal(self.window.current_repaired_frame(), repaired[0])
        self.assertTrue(self.window.preprocessing_panel.btn_preview.isEnabled())
        self.assertTrue(self.window.preprocessing_panel.btn_apply_all.isEnabled())
        self.assertTrue(self.window.preprocessing_panel.btn_repair_preview.isEnabled())
        self.assertTrue(self.window.preprocessing_panel.btn_repair_apply_all.isEnabled())
        self.assertTrue(self.window.preprocessing_panel.chk_show_denoised.isEnabled())
        self.assertFalse(self.window.preprocessing_panel.chk_show_denoised.isChecked())
        self.assertEqual(
            self.window.preprocessing_panel.lbl_status.text(),
            f"Horizontal repair cached for all {sequence.frame_count} frames",
        )
        self.assertEqual(
            self.window.statusBar().currentMessage(),
            f"Horizontal repair applied to all {sequence.frame_count} frames.",
        )

    @patch("nanotrack.ui.main_window.run_horizontal_dropout_preview")
    def test_repair_preview_opens_comparison_dialog(self, run_repair_preview_mock) -> None:
        sequence = load_mpp_sequence(str(SAMPLE_MPP))
        self.window.set_sequence(sequence)
        repaired = np.full_like(sequence.active_frame, 0.35, dtype=np.float32)
        mask = np.zeros_like(sequence.active_frame, dtype=bool)
        mask[4:6, 8:14] = True
        run_repair_preview_mock.return_value = (repaired, mask)

        self.window.preprocessing_panel.btn_repair_preview.click()

        run_repair_preview_mock.assert_called_once()
        np.testing.assert_array_equal(run_repair_preview_mock.call_args.args[0], sequence.active_frame)
        self.assertIsNotNone(self.window._bm3d_preview_dialog)
        self.assertTrue(self.window._bm3d_preview_dialog.isVisible())
        self.assertIn("Original | Frame 1/", self.window._bm3d_preview_dialog.raw_view.lbl_title.text())
        self.assertEqual(self.window._bm3d_preview_dialog.raw_view.lbl_meta.text(), "Raw frame")
        self.assertIn("Repair | Frame 1/", self.window._bm3d_preview_dialog.denoised_view.lbl_title.text())
        self.assertIn("thr", self.window._bm3d_preview_dialog.denoised_view.lbl_meta.text())
        self.assertIn("mask 12px", self.window._bm3d_preview_dialog.denoised_view.lbl_meta.text())
        self.assertIn("Repair preview ready for frame 1", self.window.preprocessing_panel.lbl_status.text())
        self.assertEqual(self.window.statusBar().currentMessage(), "Repair preview opened for frame 1.")

    @patch("nanotrack.ui.main_window.run_bm3d_preview")
    @patch("nanotrack.ui.main_window.run_bm3d_batch")
    @patch("nanotrack.ui.main_window.run_horizontal_dropout_batch")
    def test_bm3d_preview_uses_repair_cache_and_cached_frames_for_matching_sigma(
        self,
        run_repair_batch_mock,
        run_bm3d_batch_mock,
        run_bm3d_preview_mock,
    ) -> None:
        sequence = load_mpp_sequence(str(SAMPLE_MPP))
        self.window.set_sequence(sequence)
        repaired = np.full_like(sequence.raw_frames, 0.2, dtype=np.float32)
        denoised = np.full_like(sequence.raw_frames, 0.75, dtype=np.float32)
        run_repair_batch_mock.return_value = repaired
        run_bm3d_batch_mock.return_value = denoised

        self.window.preprocessing_panel.btn_repair_apply_all.click()
        self.window.preprocessing_panel.sp_bm3d_sigma.setValue(1.4)
        self.window.preprocessing_panel.btn_apply_all.click()
        self.window.preprocessing_panel.btn_preview.click()

        run_repair_batch_mock.assert_called_once()
        run_bm3d_batch_mock.assert_called_once()
        np.testing.assert_array_equal(run_bm3d_batch_mock.call_args.args[0], repaired)
        run_bm3d_preview_mock.assert_not_called()
        self.assertIsNotNone(self.window._bm3d_preview_dialog)
        self.assertTrue(self.window._bm3d_preview_dialog.isVisible())
        self.assertEqual(self.window._bm3d_preview_dialog.raw_view.lbl_meta.text(), "Horizontal repair cache")
        self.assertEqual(self.window._bm3d_preview_dialog.denoised_view.lbl_meta.text(), "Sigma factor: 1.40")
        self.assertEqual(self.window.preprocessing_panel.lbl_status.text(), "BM3D preview ready for frame 1")

    @patch("nanotrack.ui.main_window.run_horizontal_dropout_batch")
    @patch("nanotrack.ui.main_window.run_bm3d_batch")
    def test_show_denoised_checkbox_switches_main_viewer_source(
        self,
        run_bm3d_batch_mock,
        run_repair_batch_mock,
    ) -> None:
        sequence = load_mpp_sequence(str(SAMPLE_MPP))
        self.window.set_sequence(sequence)
        repaired = np.full_like(sequence.raw_frames, 0.4, dtype=np.float32)
        denoised = np.full_like(sequence.raw_frames, 0.9, dtype=np.float32)
        run_repair_batch_mock.return_value = repaired
        run_bm3d_batch_mock.return_value = denoised

        self.window.preprocessing_panel.btn_repair_apply_all.click()

        np.testing.assert_array_equal(self.window.viewer.viewer.image_item.image, sequence.raw_frames[0])
        self.assertIn("View: Raw", self.window.viewer.lbl_meta.text())

        self.window.preprocessing_panel.chk_show_denoised.setChecked(True)

        np.testing.assert_array_equal(self.window.viewer.viewer.image_item.image, repaired[0])
        self.assertIn("View: Horizontal repair", self.window.viewer.lbl_meta.text())

        self.window.preprocessing_panel.sp_bm3d_sigma.setValue(1.1)
        self.window.preprocessing_panel.btn_apply_all.click()

        np.testing.assert_array_equal(self.window.viewer.viewer.image_item.image, denoised[0])
        self.assertIn("View: BM3D sigma 1.10", self.window.viewer.lbl_meta.text())

        self.window.slider_frame.setValue(1)
        np.testing.assert_array_equal(self.window.viewer.viewer.image_item.image, denoised[1])

        self.window.preprocessing_panel.chk_show_denoised.setChecked(False)
        np.testing.assert_array_equal(self.window.viewer.viewer.image_item.image, sequence.raw_frames[1])
        self.assertIn("View: Raw", self.window.viewer.lbl_meta.text())

    def test_run_selected_sam2_updates_track_annotations_and_overlays(self) -> None:
        sequence = load_mpp_sequence(str(SAMPLE_MPP))
        self.assertGreaterEqual(sequence.frame_count, 3)
        self.window.set_sequence(sequence)
        self.window.slider_frame.setValue(1)
        bbox = self.window.viewer.place_bbox_at_pixel(24.0, 24.0)
        self.window.bbox_tools_panel.btn_add_seed.click()

        denoised = np.full_like(sequence.raw_frames, 0.8, dtype=np.float32)
        self.window._denoised_frames = denoised
        self.window._denoised_sigma_factor = 1.2

        tracked_frame_count = sequence.frame_count - 1
        masks = np.zeros((tracked_frame_count, *sequence.frame_shape), dtype=bool)
        masks[0, 12:20, 14:23] = True
        masks[1, 13:21, 15:24] = True
        visible_mask = np.zeros((tracked_frame_count,), dtype=bool)
        visible_mask[:2] = True
        mask_bboxes = np.zeros((tracked_frame_count, 4), dtype=np.float32)
        mask_bboxes[0] = np.asarray([14.0, 12.0, 23.0, 20.0], dtype=np.float32)
        mask_bboxes[1] = np.asarray([15.0, 13.0, 24.0, 21.0], dtype=np.float32)
        mask_areas = np.zeros((tracked_frame_count,), dtype=np.float32)
        mask_areas[:2] = 72.0
        mask_scores = np.zeros((tracked_frame_count,), dtype=np.float32)
        mask_scores[:2] = np.asarray([0.95, 0.91], dtype=np.float32)
        mask_component_counts = np.zeros((tracked_frame_count,), dtype=np.int32)
        mask_component_counts[:2] = 1
        run_output = Sam2RunOutput(
            track_id=1,
            frame_index_offset=1,
            masks=masks,
            visible_mask=visible_mask,
            mask_areas=mask_areas,
            mask_bboxes_xyxy=mask_bboxes,
            mask_scores=mask_scores,
            mask_component_counts=mask_component_counts,
        )

        def fake_run(run_input):
            time.sleep(0.05)
            np.testing.assert_array_equal(run_input.frames, denoised[1:])
            np.testing.assert_array_equal(
                run_input.query_box_xyxy,
                np.asarray(bbox.as_tuple(), dtype=np.float32),
            )
            np.testing.assert_allclose(
                run_input.query_point_tyx,
                np.asarray([0.0, bbox.center_xy[1], bbox.center_xy[0]], dtype=np.float32),
            )
            self.assertEqual(run_input.track_id, 1)
            self.assertEqual(run_input.frame_index_offset, 1)
            self.assertEqual(run_input.source_view, "bm3d")
            return run_output

        with patch.object(self.window._sam2_backend, "run", side_effect=fake_run) as run_mock:
            self.window.track_list_panel.btn_run_selected.click()
            self.assertFalse(self.window.track_list_panel.btn_run_selected.isEnabled())
            self.assertIsNotNone(self.window._sam2_progress_dialog)
            self.assertTrue(self.window._sam2_progress_dialog.isVisible())
            for _ in range(200):
                self.__class__._app.processEvents()
                track = self.window.current_tracks()[0]
                if run_mock.called and track.get_annotation(2) is not None:
                    break
                time.sleep(0.01)

        run_mock.assert_called_once()
        track = self.window.current_tracks()[0]
        frame1_annotation = track.get_annotation(1)
        frame2_annotation = track.get_annotation(2)
        frame_last_annotation = track.get_annotation(sequence.frame_count - 1)
        self.assertIsNotNone(frame1_annotation)
        self.assertIsNotNone(frame2_annotation)
        self.assertIsNotNone(frame_last_annotation)
        self.assertEqual(frame1_annotation.source.value, "sam2")
        self.assertEqual(frame1_annotation.bbox, BBoxXYXY(14.0, 12.0, 23.0, 20.0))
        self.assertTrue(frame1_annotation.mask.any())
        self.assertEqual(frame2_annotation.bbox, BBoxXYXY(15.0, 13.0, 24.0, 21.0))
        self.assertTrue(frame2_annotation.mask.any())
        self.assertEqual(frame_last_annotation.visibility.value, "lost")
        self.assertFalse(frame_last_annotation.mask.any())
        self.assertGreater(len(self.window.viewer.viewer._overlay_items), 0)
        self.assertTrue(self.window.track_list_panel.btn_run_selected.isEnabled())
        self.assertIn("SAM2 finished for Track 1.", self.window.statusBar().currentMessage())

        self.window.slider_frame.setValue(2)
        self.assertGreater(len(self.window.viewer.viewer._overlay_items), 0)

    def test_run_all_sam2_updates_multiple_tracks_from_different_seed_frames(self) -> None:
        sequence = load_mpp_sequence(str(SAMPLE_MPP))
        self.assertGreaterEqual(sequence.frame_count, 4)
        self.window.set_sequence(sequence)

        self.window.slider_frame.setValue(0)
        bbox1 = self.window.viewer.place_bbox_at_pixel(20.0, 20.0)
        self.window.bbox_tools_panel.btn_add_seed.click()

        self.window.slider_frame.setValue(2)
        bbox2 = self.window.viewer.place_bbox_at_pixel(32.0, 28.0)
        self.window.bbox_tools_panel.btn_add_seed.click()

        repaired = np.full_like(sequence.raw_frames, 0.6, dtype=np.float32)
        self.window._repair_frames = repaired

        def build_output(track_id: int, frame_index_offset: int, frame_count: int, frame_shape: tuple[int, int]):
            masks = np.zeros((frame_count, *frame_shape), dtype=bool)
            visible_mask = np.zeros((frame_count,), dtype=bool)
            mask_bboxes = np.zeros((frame_count, 4), dtype=np.float32)
            if track_id == 1:
                masks[0, 8:14, 10:18] = True
                masks[1, 9:15, 11:19] = True
                visible_mask[:2] = True
                mask_bboxes[0] = np.asarray([10.0, 8.0, 18.0, 14.0], dtype=np.float32)
                mask_bboxes[1] = np.asarray([11.0, 9.0, 19.0, 15.0], dtype=np.float32)
            else:
                masks[0, 18:24, 22:29] = True
                masks[1, 19:25, 23:30] = True
                visible_mask[:2] = True
                mask_bboxes[0] = np.asarray([22.0, 18.0, 29.0, 24.0], dtype=np.float32)
                mask_bboxes[1] = np.asarray([23.0, 19.0, 30.0, 25.0], dtype=np.float32)

            mask_areas = visible_mask.astype(np.float32) * np.asarray(
                [float(np.count_nonzero(mask)) for mask in masks],
                dtype=np.float32,
            )
            mask_scores = visible_mask.astype(np.float32) * 0.9
            mask_component_counts = visible_mask.astype(np.int32)
            return Sam2RunOutput(
                track_id=track_id,
                frame_index_offset=frame_index_offset,
                masks=masks,
                visible_mask=visible_mask,
                mask_areas=mask_areas,
                mask_bboxes_xyxy=mask_bboxes,
                mask_scores=mask_scores,
                mask_component_counts=mask_component_counts,
            )

        observed_inputs = []

        def fake_run(run_input):
            time.sleep(0.05)
            observed_inputs.append((run_input.track_id, run_input.frame_index_offset, run_input.source_view))
            if run_input.track_id == 1:
                np.testing.assert_array_equal(run_input.frames, repaired[0:])
                np.testing.assert_array_equal(run_input.query_box_xyxy, np.asarray(bbox1.as_tuple(), dtype=np.float32))
            else:
                np.testing.assert_array_equal(run_input.frames, repaired[2:])
                np.testing.assert_array_equal(run_input.query_box_xyxy, np.asarray(bbox2.as_tuple(), dtype=np.float32))
            return build_output(
                run_input.track_id,
                run_input.frame_index_offset,
                int(run_input.frames.shape[0]),
                tuple(run_input.frames.shape[1:3]),
            )

        with patch.object(self.window._sam2_backend, "run", side_effect=fake_run) as run_mock:
            self.window.track_list_panel.btn_run_all.click()
            self.assertFalse(self.window.track_list_panel.btn_run_selected.isEnabled())
            self.assertFalse(self.window.track_list_panel.btn_run_all.isEnabled())
            self.assertIsNotNone(self.window._sam2_progress_dialog)
            self.assertTrue(self.window._sam2_progress_dialog.isVisible())
            for _ in range(300):
                self.__class__._app.processEvents()
                tracks = self.window.current_tracks()
                if run_mock.call_count == 2 and tracks[0].get_annotation(1) is not None and tracks[1].get_annotation(3) is not None:
                    break
                time.sleep(0.01)
            for _ in range(20):
                self.__class__._app.processEvents()
                if self.window.statusBar().currentMessage() == "SAM2 finished for all 2 seeds.":
                    break
                time.sleep(0.01)

        self.assertEqual(run_mock.call_count, 2)
        self.assertEqual(observed_inputs, [(1, 0, "repair"), (2, 2, "repair")])

        tracks = self.window.current_tracks()
        track1 = tracks[0]
        track2 = tracks[1]
        self.assertEqual(track1.get_annotation(0).bbox, BBoxXYXY(10.0, 8.0, 18.0, 14.0))
        self.assertEqual(track1.get_annotation(1).bbox, BBoxXYXY(11.0, 9.0, 19.0, 15.0))
        self.assertEqual(track2.get_annotation(2).bbox, BBoxXYXY(22.0, 18.0, 29.0, 24.0))
        self.assertEqual(track2.get_annotation(3).bbox, BBoxXYXY(23.0, 19.0, 30.0, 25.0))
        self.assertTrue(track1.get_annotation(1).mask.any())
        self.assertTrue(track2.get_annotation(3).mask.any())
        self.assertTrue(self.window.track_list_panel.btn_run_all.isEnabled())
        self.assertTrue(
            self.window.statusBar().currentMessage() in {"SAM2 finished for all 2 seeds.", "SAM2 batch 2/2 finished: Track 2"}
        )


if __name__ == "__main__":
    unittest.main()
