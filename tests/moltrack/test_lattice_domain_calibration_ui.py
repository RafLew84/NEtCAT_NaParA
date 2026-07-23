import os
import tempfile
import threading
import time
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from moltrack.analysis import (
    LatticeDomainCalibrationCanceled,
    MolecularFrameRange,
    adapt_m6_domain_type_analysis_source,
    analyze_molecular_frame_range,
)
from test_m6_range_analysis import _m6_settings
from test_m6_range_trends_panel import _series

try:
    from PyQt6.QtCore import QThread, QTimer
    from PyQt6.QtWidgets import QApplication
except ImportError:  # pragma: no cover - optional outside target GUI env
    QApplication = None

if QApplication is not None:
    from moltrack.ui.dialogs import (
        LatticeDomainCalibrationDialog,
        M6DomainTypesPanel,
        PositionAnalysisDialog,
    )
    from moltrack.ui.lattice_domain_calibration_worker import (
        LatticeDomainCalibrationController,
    )


@unittest.skipUnless(QApplication is not None, "PyQt6 is required for GUI tests")
class LatticeDomainCalibrationUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])
        cls.series = _series()
        cls.analysis = analyze_molecular_frame_range(
            cls.series,
            MolecularFrameRange("calibration", 0, 1),
            source_view="raw",
            m6_orientation_settings=_m6_settings(),
        )
        cls.source = adapt_m6_domain_type_analysis_source(
            cls.analysis,
            frame_count=cls.series.frame_count,
        )

    def tearDown(self) -> None:
        self.__class__._app.processEvents()

    def test_domain_types_panel_and_position_dialog_forward_calibration_request(self) -> None:
        panel = M6DomainTypesPanel()
        dialog = PositionAnalysisDialog()
        panel_requests = []
        dialog_requests = []
        try:
            panel.calibration_requested.connect(lambda: panel_requests.append(True))
            panel.set_analysis_source(self.source)
            self.assertTrue(panel.calibration_button.isEnabled())
            panel.calibration_button.click()
            self.assertEqual(panel_requests, [True])

            dialog.m6_lattice_domain_calibration_requested.connect(
                lambda: dialog_requests.append(True)
            )
            dialog.set_m6_domain_type_analysis_source(self.source)
            dialog.domain_types_panel.calibration_button.click()
            self.assertEqual(dialog_requests, [True])
        finally:
            panel.close()
            panel.deleteLater()
            dialog.close()
            dialog.deleteLater()

    def test_dialog_exposes_bounded_parameters_and_locks_first_shell(self) -> None:
        calibration_dialog = LatticeDomainCalibrationDialog(
            self.source,
            source_file_name="movie.mpp",
            baseline_settings=_m6_settings(),
        )
        try:
            selected = calibration_dialog.selected_parameter_names()
            self.assertIn(
                "local_symmetry_trifold_minimum_model_score",
                selected,
            )
            self.assertIn("min_seed_size", selected)
            self.assertIn("q_seed", selected)
            self.assertIn("q_grow", selected)
            self.assertNotIn("first_shell_r_max_nm", selected)
            baseline = _m6_settings()
            self.assertIn(
                (
                    f"{baseline.first_shell_r_min_nm:g}-"
                    f"{baseline.first_shell_r_max_nm:g} nm"
                ),
                calibration_dialog.first_shell_label.text(),
            )
            self.assertFalse(calibration_dialog.run_button.isEnabled())
            calibration_dialog.reference_path.setText("reference.json")
            calibration_dialog.report_directory.setText("report")
            self.assertTrue(calibration_dialog.run_button.isEnabled())
            self.assertFalse(calibration_dialog.sweep_settings().parameter_names == ())
            self.assertEqual(
                calibration_dialog.sweep_settings().max_stability_candidates,
                5,
            )
        finally:
            calibration_dialog.close()
            calibration_dialog.deleteLater()

    def test_controller_runs_off_main_thread_and_writes_report(self) -> None:
        started = threading.Event()
        release = threading.Event()
        worker_thread_ids = []
        writer_calls = []

        def runner(
            _reference,
            _sweep,
            _source,
            *,
            source_file_name,
            progress_callback,
            cancel_callback,
        ):
            del source_file_name, cancel_callback
            worker_thread_ids.append(int(QThread.currentThreadId()))
            started.set()
            progress_callback("progress")
            if not release.wait(timeout=2.0):
                raise RuntimeError("test runner timeout")
            return "report"

        def writer(report, destination):
            writer_calls.append((report, Path(destination)))
            return {"markdown": Path(destination) / "report.md"}

        controller = LatticeDomainCalibrationController(
            runner=runner,
            report_writer=writer,
        )
        progress = []
        finished = []
        ticks = []
        controller.progress.connect(progress.append)
        controller.finished.connect(finished.append)
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                main_thread_id = int(QThread.currentThreadId())
                self.assertTrue(
                    controller.start(
                        object(),
                        object(),
                        object(),
                        source_file_name="movie.mpp",
                        report_directory=tmpdir,
                    )
                )
                self._wait_until(started.is_set)
                QTimer.singleShot(
                    10,
                    lambda: (ticks.append(True), release.set()),
                )
                self._wait_until(lambda: bool(finished))
                self._wait_until(lambda: not controller.is_running)

            self.assertEqual(progress, ["progress"])
            self.assertEqual(ticks, [True])
            self.assertNotEqual(worker_thread_ids, [main_thread_id])
            self.assertEqual(writer_calls[0][0], "report")
            self.assertEqual(finished[0].report, "report")
        finally:
            release.set()
            self._wait_until(lambda: not controller.is_running)
            controller.deleteLater()

    def test_controller_cancels_cooperatively(self) -> None:
        started = threading.Event()

        def runner(
            _reference,
            _sweep,
            _source,
            *,
            source_file_name,
            progress_callback,
            cancel_callback,
        ):
            del source_file_name, progress_callback
            started.set()
            deadline = time.monotonic() + 2.0
            while time.monotonic() < deadline:
                if cancel_callback():
                    raise LatticeDomainCalibrationCanceled()
                time.sleep(0.005)
            raise RuntimeError("cancel was not forwarded")

        controller = LatticeDomainCalibrationController(runner=runner)
        canceled = []
        controller.canceled.connect(lambda: canceled.append(True))
        try:
            self.assertTrue(
                controller.start(
                    object(),
                    object(),
                    object(),
                    source_file_name="movie.mpp",
                    report_directory=".",
                )
            )
            self._wait_until(started.is_set)
            self.assertTrue(controller.cancel())
            self._wait_until(lambda: bool(canceled))
            self._wait_until(lambda: not controller.is_running)
            self.assertEqual(canceled, [True])
        finally:
            controller.cancel()
            self._wait_until(lambda: not controller.is_running)
            controller.deleteLater()

    def _wait_until(self, condition, *, timeout_s: float = 3.0) -> None:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            self.__class__._app.processEvents()
            if condition():
                return
            time.sleep(0.005)
        self.fail("Timed out waiting for Qt event-loop condition.")


if __name__ == "__main__":
    unittest.main()
