import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt6.QtWidgets import QApplication
except ImportError:  # pragma: no cover - optional outside the target GUI env
    QApplication = None

from nanotrack.core import BBoxXYXY, ParticleTrack
from nanotrack.mask_trackers import MASK_TRACKER_KINDS, MaskTrackerKind

if QApplication is not None:
    from nanotrack.ui.widgets.track_list_panel import TrackListPanel
else:  # pragma: no cover - optional outside the target GUI env
    TrackListPanel = None


@unittest.skipUnless(QApplication is not None, "PyQt6 is required for widget tests")
class TrackListPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.panel = TrackListPanel()

    def tearDown(self) -> None:
        self.panel.close()
        self.panel.deleteLater()
        self.__class__._app.processEvents()

    def test_mask_tracker_selector_lists_supported_backends_with_sam2_default(self) -> None:
        values = [
            self.panel.cmb_mask_tracker.itemData(index)
            for index in range(self.panel.cmb_mask_tracker.count())
        ]
        labels = [
            self.panel.cmb_mask_tracker.itemText(index)
            for index in range(self.panel.cmb_mask_tracker.count())
        ]

        self.assertEqual(values, [tracker_kind.value for tracker_kind in MASK_TRACKER_KINDS])
        self.assertEqual(labels, ["SAM2", "DAM4SAM", "SAMURAI"])
        self.assertEqual(self.panel.current_mask_tracker_kind(), MaskTrackerKind.SAM2)
        self.assertIsNone(self.panel.current_run_frame_limit())
        self.assertEqual(self.panel.sp_run_frame_limit.specialValueText(), "All")
        self.assertAlmostEqual(self.panel.current_mask_probability_threshold(), 0.5)
        self.assertEqual(self.panel.sp_mask_probability_threshold.minimum(), 0.01)
        self.assertEqual(self.panel.sp_mask_probability_threshold.maximum(), 0.99)
        self.assertEqual(self.panel.btn_delete_selected.text(), "Delete Selected")
        self.assertEqual(self.panel.btn_run_selected.text(), "Run for Selected")
        self.assertEqual(self.panel.btn_run_all_at_selected_frame.text(), "Run for Seeds at Current Frame")
        self.assertEqual(self.panel.btn_run_all.text(), "Run for All Seeds")
        self.assertFalse(self.panel.btn_delete_selected.isEnabled())

    def test_run_frame_limit_defaults_to_all_and_can_be_limited(self) -> None:
        self.assertIsNone(self.panel.current_run_frame_limit())

    def test_mask_probability_threshold_can_be_changed(self) -> None:
        self.panel.set_mask_probability_threshold(0.75)

        self.assertAlmostEqual(self.panel.current_mask_probability_threshold(), 0.75)

        with self.assertRaises(ValueError):
            self.panel.set_mask_probability_threshold(1.0)

        self.panel.set_run_frame_limit(5)

        self.assertEqual(self.panel.current_run_frame_limit(), 5)

        self.panel.set_run_frame_limit(None)

        self.assertIsNone(self.panel.current_run_frame_limit())

    def test_mask_tracker_selection_can_be_changed_and_emits_kind(self) -> None:
        emitted: list[MaskTrackerKind] = []
        self.panel.mask_tracker_changed.connect(emitted.append)

        self.panel.set_mask_tracker_kind("samurai")

        self.assertEqual(self.panel.current_mask_tracker_kind(), MaskTrackerKind.SAMURAI)
        self.assertEqual(emitted[-1], MaskTrackerKind.SAMURAI)

    def test_run_all_at_selected_frame_emits_signal(self) -> None:
        emitted: list[bool] = []
        self.panel.run_all_at_selected_frame_requested.connect(lambda: emitted.append(True))
        track = ParticleTrack(track_id=1, seed_frame_index=0, seed_bbox=BBoxXYXY(1.0, 1.0, 4.0, 4.0))
        self.panel.set_tracks([track], selected_track_id=1)

        self.panel.btn_run_all_at_selected_frame.click()

        self.assertEqual(emitted, [True])

    def test_processing_state_disables_selector_without_changing_selection(self) -> None:
        self.panel.set_mask_tracker_kind(MaskTrackerKind.DAM4SAM)

        self.panel.set_processing(True)

        self.assertFalse(self.panel.cmb_mask_tracker.isEnabled())
        self.assertFalse(self.panel.sp_run_frame_limit.isEnabled())
        self.assertFalse(self.panel.sp_mask_probability_threshold.isEnabled())
        self.assertFalse(self.panel.btn_run_all_at_selected_frame.isEnabled())
        self.assertEqual(self.panel.current_mask_tracker_kind(), MaskTrackerKind.DAM4SAM)

        self.panel.set_processing(False)

        self.assertTrue(self.panel.cmb_mask_tracker.isEnabled())
        self.assertTrue(self.panel.sp_run_frame_limit.isEnabled())
        self.assertTrue(self.panel.sp_mask_probability_threshold.isEnabled())
        self.assertFalse(self.panel.btn_run_all_at_selected_frame.isEnabled())
        self.assertEqual(self.panel.current_mask_tracker_kind(), MaskTrackerKind.DAM4SAM)

    def test_delete_selected_emits_track_id_and_respects_processing_state(self) -> None:
        deleted_track_ids: list[int] = []
        self.panel.track_delete_requested.connect(deleted_track_ids.append)
        track1 = ParticleTrack(track_id=1, seed_frame_index=0, seed_bbox=BBoxXYXY(1.0, 1.0, 4.0, 4.0))
        track2 = ParticleTrack(track_id=2, seed_frame_index=1, seed_bbox=BBoxXYXY(2.0, 2.0, 5.0, 5.0))

        self.panel.set_tracks([track1, track2], selected_track_id=1)

        self.assertTrue(self.panel.btn_delete_selected.isEnabled())
        self.panel.btn_delete_selected.click()
        self.assertEqual(deleted_track_ids, [1])

        self.panel.set_selected_track_id(2)
        self.panel.set_processing(True)
        self.assertFalse(self.panel.btn_delete_selected.isEnabled())

        self.panel.set_processing(False)
        self.assertTrue(self.panel.btn_delete_selected.isEnabled())
        self.panel.btn_delete_selected.click()
        self.assertEqual(deleted_track_ids, [1, 2])


if __name__ == "__main__":
    unittest.main()
