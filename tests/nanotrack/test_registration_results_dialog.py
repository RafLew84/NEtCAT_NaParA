import csv
import os
import tempfile
import unittest

import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt6.QtWidgets import QApplication
except ImportError:  # pragma: no cover - optional outside target GUI env
    QApplication = None

from nanotrack.core import (
    RegistrationFrameResult,
    RegistrationResultSet,
    RegistrationSettings,
    STMSequence,
    STMSequenceMetadata,
)

if QApplication is not None:
    from nanotrack.ui.dialogs import RegistrationResultsDialog
else:  # pragma: no cover - optional outside target GUI env
    RegistrationResultsDialog = None


@unittest.skipUnless(QApplication is not None, "PyQt6 is required for registration results dialog tests")
class RegistrationResultsDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def tearDown(self) -> None:
        if hasattr(self, "dialog"):
            self.dialog.close()
            self.dialog.deleteLater()
            self.__class__._app.processEvents()

    def _result_set(self) -> RegistrationResultSet:
        return RegistrationResultSet(
            settings=RegistrationSettings(
                backend="phase_correlation",
                reference_strategy="adjacent",
                registration_view="normalized",
            ),
            results_by_frame={
                0: RegistrationFrameResult(
                    frame_index=0,
                    shift_xy=(0.0, 0.0),
                    method="identity",
                    quality_score=1.0,
                    status="ok",
                ),
                1: RegistrationFrameResult(
                    frame_index=1,
                    shift_xy=(3.0, -2.0),
                    method="phase_correlation_adjacent",
                    quality_score=0.72,
                    phase_peak_ratio=2.4,
                    status="low_confidence",
                ),
                2: RegistrationFrameResult(
                    frame_index=2,
                    shift_xy=(-2.0, -1.0),
                    method="phase_correlation_adjacent",
                    quality_score=0.88,
                    phase_peak_ratio=4.1,
                    ecc_score=0.91,
                    num_inlier_tiles=7,
                    num_total_tiles=9,
                    median_tile_residual=0.2,
                    flow_mad=0.15,
                    status="ok",
                ),
            },
            reference_frame_index=0,
            template_frame_indices=(0,),
        )

    def test_populates_registration_plots_and_quality_table(self) -> None:
        sequence = STMSequence(
            source_path="/tmp/registration_results.mpp",
            raw_frames=np.zeros((3, 8, 8), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=8, pixels_y=8),
        )
        self.dialog = RegistrationResultsDialog()

        self.dialog.set_context(sequence, self._result_set())

        self.assertEqual(self.dialog.table_results.rowCount(), 3)
        self.assertEqual(self.dialog.table_results.item(1, 0).text(), "2")
        self.assertEqual(self.dialog.table_results.item(1, 1).text(), "3.000")
        self.assertEqual(self.dialog.table_results.item(1, 2).text(), "-2.000")
        self.assertEqual(self.dialog.table_results.item(1, 4).text(), "low_confidence")
        self.assertEqual(self.dialog.table_results.item(2, 8).text(), "7/9")
        self.assertIn("frames: 3 / 3", self.dialog.lbl_summary.text())
        self.assertIn("low_confidence: 1", self.dialog.lbl_summary.text())
        self.assertIn("view: normalized", self.dialog.lbl_settings.text())
        self.assertTrue(self.dialog.btn_export.isEnabled())
        self.assertEqual(len(self.dialog.plot_dx.plotItem.listDataItems()), 1)
        self.assertEqual(len(self.dialog.plot_dy.plotItem.listDataItems()), 1)
        self.assertEqual(len(self.dialog.plot_quality.plotItem.listDataItems()), 1)

    def test_empty_state_clears_rows_and_plots(self) -> None:
        self.dialog = RegistrationResultsDialog()
        self.dialog.set_context(None, self._result_set())

        self.dialog.set_context(None, None)

        self.assertEqual(self.dialog.table_results.rowCount(), 0)
        self.assertEqual(self.dialog.lbl_summary.text(), "No registration results available")
        self.assertEqual(len(self.dialog.plot_dx.plotItem.listDataItems()), 0)
        self.assertEqual(len(self.dialog.plot_dy.plotItem.listDataItems()), 0)
        self.assertEqual(len(self.dialog.plot_quality.plotItem.listDataItems()), 0)
        self.assertFalse(self.dialog.btn_export.isEnabled())

    def test_export_results_to_path_writes_csv_pair(self) -> None:
        sequence = STMSequence(
            source_path="/tmp/registration_results_export.mpp",
            raw_frames=np.zeros((3, 8, 8), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=8, pixels_y=8, frame_interval_s=0.5),
        )
        self.dialog = RegistrationResultsDialog()
        self.dialog.set_context(sequence, self._result_set())

        with tempfile.TemporaryDirectory() as tmpdir:
            exported = self.dialog.export_results_to_path(f"{tmpdir}/registration_results.csv")
            with open(exported["metrics_csv"], newline="", encoding="utf-8") as handle:
                metrics_rows = list(csv.DictReader(handle))
            with open(exported["summary_csv"], newline="", encoding="utf-8") as handle:
                summary_rows = list(csv.DictReader(handle))

        self.assertEqual(len(metrics_rows), 3)
        self.assertEqual(metrics_rows[1]["dx_px"], "3.0")
        self.assertEqual(metrics_rows[2]["ecc_score"], "0.91")
        self.assertEqual(summary_rows[0]["result_count"], "3")


if __name__ == "__main__":
    unittest.main()
