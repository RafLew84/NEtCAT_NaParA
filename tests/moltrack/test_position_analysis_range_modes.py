import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from moltrack.analysis import MolecularFrameRangeAnalysisScope

try:
    from PyQt6.QtWidgets import QApplication
except ImportError:  # pragma: no cover - optional outside target GUI env
    QApplication = None

if QApplication is not None:
    from moltrack.ui.dialogs import PositionAnalysisDialog


@unittest.skipUnless(QApplication is not None, "PyQt6 is required for MolTrack GUI tests")
class PositionAnalysisRangeModeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.dialog = PositionAnalysisDialog()
        self.dialog.configure_frame_ranges(frame_count=12, source_view="raw")

    def tearDown(self) -> None:
        self.dialog.close()
        self.dialog.deleteLater()
        self.__class__._app.processEvents()

    def test_single_range_hides_second_range_and_emits_one_inclusive_range(self) -> None:
        requested_scopes = []
        legacy_comparisons = []
        self.dialog.range_analysis_requested.connect(requested_scopes.append)
        self.dialog.compare_ranges_requested.connect(legacy_comparisons.append)
        self.dialog.edit_first_range_name.setText("stable phase")
        self.dialog.sp_first_range_start.setValue(3)
        self.dialog.sp_first_range_end.setValue(6)

        self.dialog.btn_range_mode_single.click()

        self.assertEqual(self.dialog.analysis_mode(), "single_range")
        self.assertTrue(self.dialog.edit_second_range_name.isHidden())
        self.assertTrue(self.dialog.sp_second_range_start.isHidden())
        self.assertTrue(self.dialog.sp_second_range_end.isHidden())
        self.assertFalse(self.dialog.edit_first_range_name.isHidden())
        self.assertEqual(self.dialog.btn_run_range_analysis.text(), "Analyze range")
        self.assertTrue(self.dialog.has_valid_frame_range_analysis_scope())
        self.assertTrue(self.dialog.m6_run_button.isEnabled())

        scope = self.dialog.frame_range_analysis_scope()
        self.assertIsInstance(scope, MolecularFrameRangeAnalysisScope)
        self.assertEqual(scope.analysis_mode, "single_range")
        self.assertEqual(scope.ranges, (scope.single_range,))
        self.assertEqual(scope.single_range.name, "stable phase")
        self.assertEqual(scope.single_range.frame_indices, (2, 3, 4, 5))

        self.dialog.btn_run_range_analysis.click()

        self.assertEqual(requested_scopes, [scope])
        self.assertEqual(legacy_comparisons, [])

    def test_switching_back_to_compare_preserves_and_emits_both_ranges(self) -> None:
        requested_scopes = []
        legacy_comparisons = []
        self.dialog.range_analysis_requested.connect(requested_scopes.append)
        self.dialog.compare_ranges_requested.connect(legacy_comparisons.append)
        self.dialog.edit_second_range_name.setText("readsorbed")
        self.dialog.sp_second_range_start.setValue(9)
        self.dialog.sp_second_range_end.setValue(12)

        self.dialog.btn_range_mode_single.click()
        self.dialog.btn_range_mode_compare.click()

        self.assertEqual(self.dialog.analysis_mode(), "compare_ranges")
        self.assertFalse(self.dialog.edit_second_range_name.isHidden())
        self.assertFalse(self.dialog.sp_second_range_start.isHidden())
        self.assertFalse(self.dialog.sp_second_range_end.isHidden())
        self.assertEqual(self.dialog.edit_second_range_name.text(), "readsorbed")
        self.assertEqual(self.dialog.sp_second_range_start.value(), 9)
        self.assertEqual(self.dialog.sp_second_range_end.value(), 12)
        self.assertEqual(self.dialog.btn_run_range_analysis.text(), "Compare ranges")

        expected_scope = self.dialog.frame_range_analysis_scope()
        self.dialog.btn_run_range_analysis.click()

        self.assertEqual(requested_scopes, [expected_scope])
        self.assertEqual(expected_scope.analysis_mode, "compare_ranges")
        self.assertEqual(
            expected_scope.comparison_ranges[1].frame_indices,
            (8, 9, 10, 11),
        )
        self.assertEqual(
            legacy_comparisons,
            [expected_scope.to_frame_range_selection()],
        )

    def test_validation_ignores_hidden_second_range_only_in_single_mode(self) -> None:
        self.dialog.sp_second_range_start.setValue(10)
        self.dialog.sp_second_range_end.setValue(8)

        self.assertFalse(self.dialog.has_valid_frame_range_analysis_scope())
        self.assertFalse(self.dialog.btn_run_range_analysis.isEnabled())

        self.dialog.btn_range_mode_single.click()

        self.assertTrue(self.dialog.has_valid_frame_range_analysis_scope())
        self.assertTrue(self.dialog.btn_run_range_analysis.isEnabled())
        self.assertEqual(self.dialog.range_validation_message(), "")

        self.dialog.sp_first_range_start.setValue(7)
        self.dialog.sp_first_range_end.setValue(4)
        self.assertFalse(self.dialog.has_valid_frame_range_analysis_scope())
        self.assertFalse(self.dialog.btn_run_range_analysis.isEnabled())
        self.assertIn(
            "Start frame must not exceed end frame",
            self.dialog.range_validation_message(),
        )

        self.dialog.sp_first_range_end.setValue(9)
        self.dialog.btn_range_mode_compare.click()
        self.assertFalse(self.dialog.has_valid_frame_range_analysis_scope())

    def test_mode_change_signal_is_emitted_once_per_actual_change(self) -> None:
        modes = []
        self.dialog.analysis_mode_changed.connect(modes.append)

        self.dialog.set_analysis_mode("single_range")
        self.dialog.set_analysis_mode("single_range")
        self.dialog.set_analysis_mode("compare_ranges")

        self.assertEqual(modes, ["single_range", "compare_ranges"])


if __name__ == "__main__":
    unittest.main()
