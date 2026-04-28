import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt6.QtWidgets import QApplication
except ImportError:  # pragma: no cover - optional outside the target GUI env
    QApplication = None

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
        self.assertEqual(self.panel.btn_run_selected.text(), "Run for Selected")
        self.assertEqual(self.panel.btn_run_all.text(), "Run for All Seeds")

    def test_mask_tracker_selection_can_be_changed_and_emits_kind(self) -> None:
        emitted: list[MaskTrackerKind] = []
        self.panel.mask_tracker_changed.connect(emitted.append)

        self.panel.set_mask_tracker_kind("samurai")

        self.assertEqual(self.panel.current_mask_tracker_kind(), MaskTrackerKind.SAMURAI)
        self.assertEqual(emitted[-1], MaskTrackerKind.SAMURAI)

    def test_processing_state_disables_selector_without_changing_selection(self) -> None:
        self.panel.set_mask_tracker_kind(MaskTrackerKind.DAM4SAM)

        self.panel.set_processing(True)

        self.assertFalse(self.panel.cmb_mask_tracker.isEnabled())
        self.assertEqual(self.panel.current_mask_tracker_kind(), MaskTrackerKind.DAM4SAM)

        self.panel.set_processing(False)

        self.assertTrue(self.panel.cmb_mask_tracker.isEnabled())
        self.assertEqual(self.panel.current_mask_tracker_kind(), MaskTrackerKind.DAM4SAM)


if __name__ == "__main__":
    unittest.main()
