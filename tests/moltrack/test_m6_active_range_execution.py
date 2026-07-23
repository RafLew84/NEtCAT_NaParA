import os
import threading
import time
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np

from moltrack.analysis import (
    MolecularFrameRangeAnalysis,
    MolecularFrameRangeComparison,
    MolecularM6SessionState,
    analyze_molecular_frame_range,
    compare_molecular_frame_ranges,
)
from moltrack.core import MolTrackImageSeries
from nanotrack.core import STMSequenceMetadata

try:
    from PyQt6.QtWidgets import QApplication, QMessageBox
except ImportError:  # pragma: no cover - optional outside target GUI env
    QApplication = None

if QApplication is not None:
    from moltrack.ui import MolTrackMainWindow


def _series(frame_count: int = 4) -> MolTrackImageSeries:
    return MolTrackImageSeries(
        source_path="movie.mpp",
        raw_frames=np.zeros((frame_count, 8, 8), dtype=np.float32),
        metadata=STMSequenceMetadata(
            pixels_x=8,
            pixels_y=8,
            size_nm_x=8.0,
            size_nm_y=8.0,
        ),
    )


@unittest.skipUnless(QApplication is not None, "PyQt6 is required for MolTrack GUI tests")
class M6ActiveRangeExecutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def tearDown(self) -> None:
        if hasattr(self, "window"):
            self.window.close()
            self.window.deleteLater()
            self.__class__._app.processEvents()

    def process_events_until(self, condition, *, timeout_s: float = 3.0) -> None:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            self.__class__._app.processEvents()
            if condition():
                return
            time.sleep(0.005)
        self.fail("Timed out waiting for Qt event-loop condition.")

    def test_analyze_range_button_uses_single_backend_without_comparator(self) -> None:
        analyzer_calls = []
        comparator = Mock(side_effect=AssertionError("comparison backend called"))

        def analyzer(series, frame_range, **kwargs):
            analyzer_calls.append((frame_range, dict(kwargs)))
            return analyze_molecular_frame_range(series, frame_range, **kwargs)

        self.window = MolTrackMainWindow(
            yolo_model_discovery=lambda: [],
            position_range_analyzer=analyzer,
            position_range_comparator=comparator,
        )
        self.window.set_image_series(_series())
        self.window.btn_position_analysis.click()
        dialog = self.window.position_analysis_dialog()
        dialog.btn_range_mode_single.click()
        dialog.edit_first_range_name.setText("selected condition")
        dialog.sp_first_range_start.setValue(2)
        dialog.sp_first_range_end.setValue(4)

        dialog.btn_run_range_analysis.click()

        self.assertEqual(len(analyzer_calls), 1)
        frame_range, kwargs = analyzer_calls[0]
        self.assertEqual(frame_range.name, "selected condition")
        self.assertEqual(frame_range.frame_indices, (1, 2, 3))
        self.assertEqual(kwargs["source_view"], "raw")
        comparator.assert_not_called()
        self.assertIsInstance(
            dialog.range_analysis_result(),
            MolecularFrameRangeAnalysis,
        )

    def test_m6_worker_runs_single_range_responsively_with_actual_progress(self) -> None:
        worker_started = threading.Event()
        release_worker = threading.Event()
        analyzer_calls = []
        comparator = Mock(side_effect=AssertionError("comparison backend called"))

        def blocking_analyzer(series, frame_range, **kwargs):
            analyzer_calls.append((frame_range, dict(kwargs)))
            progress_callback = kwargs.get("progress_callback")
            if progress_callback is not None:
                progress_callback(1, len(frame_range.frame_indices), frame_range.start_frame)
            worker_started.set()
            if not release_worker.wait(timeout=2.0):
                raise RuntimeError("Test did not release the single-range backend.")
            return analyze_molecular_frame_range(series, frame_range, **kwargs)

        self.window = MolTrackMainWindow(
            yolo_model_discovery=lambda: [],
            position_range_analyzer=blocking_analyzer,
            position_range_comparator=comparator,
        )
        series = _series()
        self.window.set_image_series(series)
        self.window.btn_position_analysis.click()
        dialog = self.window.position_analysis_dialog()
        dialog.btn_range_mode_single.click()
        dialog.sp_first_range_start.setValue(2)
        dialog.sp_first_range_end.setValue(4)

        started_at = time.monotonic()
        dialog.m6_run_button.click()
        elapsed = time.monotonic() - started_at

        try:
            self.assertLess(elapsed, 0.2)
            self.process_events_until(worker_started.is_set)
            self.assertTrue(self.window._m6_analysis_running)
            self.process_events_until(
                lambda: "1/3" in dialog.m6_settings_panel.progress_label.text()
            )
            self.assertIsNone(series.m6_analysis_state)
        finally:
            release_worker.set()

        self.process_events_until(lambda: not self.window._m6_analysis_running)
        self.assertEqual(len(analyzer_calls), 1)
        self.assertEqual(analyzer_calls[0][0].frame_indices, (1, 2, 3))
        self.assertIsNotNone(analyzer_calls[0][1]["m6_orientation_settings"])
        comparator.assert_not_called()
        self.assertIsInstance(dialog.range_analysis_result(), MolecularFrameRangeAnalysis)
        self.assertTrue(
            all(
                frame.m6_orientation_analysis is not None
                and frame.m6_orientation_analysis.lattice_domain_analysis is not None
                for frame in dialog.range_analysis_result().frame_results
            )
        )
        self.assertEqual(self.window._m6_completed_context.analysis_mode, "single_range")
        self.assertEqual(
            self.window._m6_completed_context.source.analysis_mode,
            "single_range",
        )
        self.assertEqual(
            self.window._m6_completed_context.source.range_analyses,
            (dialog.range_analysis_result(),),
        )
        self.assertEqual(self.window._m6_completed_context.scope.ranges, (analyzer_calls[0][0],))
        self.assertIsInstance(series.m6_analysis_state, MolecularM6SessionState)
        self.assertTrue(series.m6_analysis_state.enabled)
        self.assertIn("complete", self.window.statusBar().currentMessage().lower())

    def test_m6_worker_keeps_comparison_backend_for_compare_mode(self) -> None:
        analyzer = Mock(side_effect=AssertionError("single backend called"))
        comparator_calls = []

        def comparator(series, selection, **kwargs):
            comparator_calls.append((selection, dict(kwargs)))
            return compare_molecular_frame_ranges(series, selection, **kwargs)

        self.window = MolTrackMainWindow(
            yolo_model_discovery=lambda: [],
            position_range_analyzer=analyzer,
            position_range_comparator=comparator,
        )
        self.window.set_image_series(_series())
        self.window.btn_position_analysis.click()
        dialog = self.window.position_analysis_dialog()

        dialog.m6_run_button.click()
        self.process_events_until(lambda: not self.window._m6_analysis_running)

        analyzer.assert_not_called()
        self.assertEqual(len(comparator_calls), 1)
        selection, _kwargs = comparator_calls[0]
        self.assertEqual(
            len(selection.first_range.frame_indices)
            + len(selection.second_range.frame_indices),
            4,
        )
        self.assertIsInstance(dialog.range_analysis_result(), MolecularFrameRangeComparison)
        comparison_result = dialog.range_analysis_result()
        self.assertTrue(
            all(
                frame.m6_orientation_analysis is not None
                and frame.m6_orientation_analysis.lattice_domain_analysis is not None
                for analysis in (
                    comparison_result.first_analysis,
                    comparison_result.second_analysis,
                )
                for frame in analysis.frame_results
            )
        )
        self.assertEqual(self.window._m6_completed_context.analysis_mode, "compare_ranges")
        self.assertEqual(
            self.window._m6_completed_context.source.analysis_mode,
            "compare_ranges",
        )

    def test_m6_worker_cancels_between_frames_without_publishing_partial_result(self) -> None:
        first_frame_complete = threading.Event()
        release_next_progress = threading.Event()

        def cancellable_analyzer(_series, frame_range, **kwargs):
            callback = kwargs["progress_callback"]
            callback(1, len(frame_range.frame_indices), frame_range.start_frame)
            first_frame_complete.set()
            if not release_next_progress.wait(timeout=2.0):
                raise RuntimeError("Test did not release the next progress callback.")
            callback(2, len(frame_range.frame_indices), frame_range.start_frame + 1)
            raise AssertionError("Canceled analysis continued after a frame boundary.")

        self.window = MolTrackMainWindow(
            yolo_model_discovery=lambda: [],
            position_range_analyzer=cancellable_analyzer,
        )
        series = _series()
        self.window.set_image_series(series)
        self.window.btn_position_analysis.click()
        dialog = self.window.position_analysis_dialog()
        dialog.btn_range_mode_single.click()

        dialog.m6_run_button.click()
        self.process_events_until(first_frame_complete.is_set)
        self.process_events_until(
            lambda: dialog.m6_run_button.text() == "Cancel analysis"
        )
        dialog.m6_run_button.click()
        release_next_progress.set()
        self.process_events_until(lambda: not self.window._m6_analysis_running)

        self.assertIsNone(series.m6_analysis_state)
        self.assertIsNone(dialog.range_analysis_result())
        self.assertIsNone(self.window._m6_completed_context)
        self.assertIn("canceled", self.window.statusBar().currentMessage().lower())

    def test_m6_worker_honors_cancellation_racing_with_backend_return(self) -> None:
        worker_started = threading.Event()
        release_worker = threading.Event()

        def late_returning_analyzer(series, frame_range, **kwargs):
            worker_started.set()
            if not release_worker.wait(timeout=2.0):
                raise RuntimeError("Test did not release the backend.")
            return analyze_molecular_frame_range(
                series,
                frame_range,
                source_view=kwargs["source_view"],
                use_segmentation_centroids=kwargs["use_segmentation_centroids"],
                intensity_metric=kwargs["intensity_metric"],
                background_inner_radius_px=kwargs["background_inner_radius_px"],
                background_outer_radius_px=kwargs["background_outer_radius_px"],
                m6_orientation_settings=kwargs["m6_orientation_settings"],
            )

        self.window = MolTrackMainWindow(
            yolo_model_discovery=lambda: [],
            position_range_analyzer=late_returning_analyzer,
        )
        series = _series()
        self.window.set_image_series(series)
        self.window.btn_position_analysis.click()
        dialog = self.window.position_analysis_dialog()
        dialog.btn_range_mode_single.click()

        dialog.m6_run_button.click()
        self.process_events_until(worker_started.is_set)
        dialog.m6_run_button.click()
        release_worker.set()
        self.process_events_until(lambda: not self.window._m6_analysis_running)

        self.assertIsNone(series.m6_analysis_state)
        self.assertIsNone(dialog.range_analysis_result())
        self.assertIsNone(self.window._m6_completed_context)
        self.assertIn("canceled", self.window.statusBar().currentMessage().lower())

    def test_single_range_worker_failure_preserves_state_and_reenables_controls(self) -> None:
        previous_state = MolecularM6SessionState(enabled=True)

        def failing_analyzer(_series, _frame_range, **_kwargs):
            raise RuntimeError("synthetic single-range failure")

        self.window = MolTrackMainWindow(
            yolo_model_discovery=lambda: [],
            position_range_analyzer=failing_analyzer,
        )
        series = _series()
        series.m6_analysis_state = previous_state
        self.window.set_image_series(series)
        self.window.btn_position_analysis.click()
        dialog = self.window.position_analysis_dialog()
        dialog.btn_range_mode_single.click()

        with patch.object(QMessageBox, "critical") as critical:
            dialog.m6_run_button.click()
            self.process_events_until(lambda: not self.window._m6_analysis_running)

        self.assertIs(series.m6_analysis_state, previous_state)
        self.assertTrue(dialog.m6_run_button.isEnabled())
        self.assertIsNone(dialog.range_analysis_result())
        critical.assert_called_once()

    def test_worker_rejects_result_with_another_centroid_context(self) -> None:
        def wrong_context_analyzer(series, frame_range, **kwargs):
            return analyze_molecular_frame_range(
                series,
                frame_range,
                source_view=kwargs["source_view"],
                use_segmentation_centroids=False,
                intensity_metric=kwargs["intensity_metric"],
                background_inner_radius_px=kwargs["background_inner_radius_px"],
                background_outer_radius_px=kwargs["background_outer_radius_px"],
                m6_orientation_settings=kwargs["m6_orientation_settings"],
            )

        self.window = MolTrackMainWindow(
            yolo_model_discovery=lambda: [],
            position_range_analyzer=wrong_context_analyzer,
        )
        series = _series()
        self.window.set_image_series(series)
        self.window.btn_position_analysis.click()
        dialog = self.window.position_analysis_dialog()
        dialog.btn_range_mode_single.click()

        with patch.object(QMessageBox, "critical") as critical:
            dialog.m6_run_button.click()
            self.process_events_until(lambda: not self.window._m6_analysis_running)

        self.assertIsNone(self.window._m6_completed_context)
        self.assertIsNone(series.m6_analysis_state)
        self.assertIsNone(dialog.range_analysis_result())
        self.assertIn("centroid mode", critical.call_args.args[2])

    def test_worker_discards_result_after_series_and_dialog_replacement(self) -> None:
        worker_started = threading.Event()
        release_worker = threading.Event()

        def blocking_analyzer(series, frame_range, **kwargs):
            worker_started.set()
            if not release_worker.wait(timeout=2.0):
                raise RuntimeError("Test did not release the stale worker.")
            return analyze_molecular_frame_range(series, frame_range, **kwargs)

        self.window = MolTrackMainWindow(
            yolo_model_discovery=lambda: [],
            position_range_analyzer=blocking_analyzer,
        )
        original_series = _series()
        replacement_series = _series(3)
        self.window.set_image_series(original_series)
        self.window.btn_position_analysis.click()
        original_dialog = self.window.position_analysis_dialog()
        original_dialog.btn_range_mode_single.click()
        original_dialog.m6_run_button.click()
        self.process_events_until(worker_started.is_set)

        self.window.set_image_series(replacement_series)
        release_worker.set()
        self.process_events_until(lambda: not self.window._m6_analysis_running)
        self.window.btn_position_analysis.click()
        replacement_dialog = self.window.position_analysis_dialog()

        self.assertIsNone(self.window._m6_completed_context)
        self.assertIsNone(original_series.m6_analysis_state)
        self.assertIsNone(replacement_series.m6_analysis_state)
        self.assertIsNone(replacement_dialog.range_analysis_result())
        self.assertIn("discarded", self.window.statusBar().currentMessage().lower())

    def test_worker_discards_result_after_active_mode_changes(self) -> None:
        worker_started = threading.Event()
        release_worker = threading.Event()

        def blocking_analyzer(series, frame_range, **kwargs):
            worker_started.set()
            if not release_worker.wait(timeout=2.0):
                raise RuntimeError("Test did not release the changed-mode worker.")
            return analyze_molecular_frame_range(series, frame_range, **kwargs)

        self.window = MolTrackMainWindow(
            yolo_model_discovery=lambda: [],
            position_range_analyzer=blocking_analyzer,
        )
        series = _series()
        self.window.set_image_series(series)
        self.window.btn_position_analysis.click()
        dialog = self.window.position_analysis_dialog()
        dialog.btn_range_mode_single.click()
        dialog.m6_run_button.click()
        self.process_events_until(worker_started.is_set)

        dialog.set_analysis_mode("compare_ranges")
        release_worker.set()
        self.process_events_until(lambda: not self.window._m6_analysis_running)

        self.assertIsNone(self.window._m6_completed_context)
        self.assertIsNone(series.m6_analysis_state)
        self.assertIsNone(dialog.range_analysis_result())
        self.assertIn("discarded", self.window.statusBar().currentMessage().lower())

    def test_worker_discards_progress_and_failure_after_active_mode_changes(self) -> None:
        worker_started = threading.Event()
        release_progress = threading.Event()
        progress_sent = threading.Event()
        release_failure = threading.Event()

        def blocking_analyzer(_series, frame_range, **kwargs):
            worker_started.set()
            if not release_progress.wait(timeout=2.0):
                raise RuntimeError("Test did not release stale progress.")
            kwargs["progress_callback"](
                1,
                len(frame_range.frame_indices),
                frame_range.start_frame,
            )
            progress_sent.set()
            if not release_failure.wait(timeout=2.0):
                raise RuntimeError("Test did not release stale failure.")
            raise RuntimeError("stale worker failure")

        self.window = MolTrackMainWindow(
            yolo_model_discovery=lambda: [],
            position_range_analyzer=blocking_analyzer,
        )
        series = _series()
        self.window.set_image_series(series)
        self.window.btn_position_analysis.click()
        dialog = self.window.position_analysis_dialog()
        dialog.btn_range_mode_single.click()

        with patch.object(QMessageBox, "critical") as critical:
            dialog.m6_run_button.click()
            self.process_events_until(worker_started.is_set)
            dialog.set_analysis_mode("compare_ranges")
            release_progress.set()
            self.process_events_until(progress_sent.is_set)
            for _ in range(10):
                self.__class__._app.processEvents()
                time.sleep(0.005)
            self.assertEqual(dialog.m6_settings_panel.progress_label.text(), "")
            release_failure.set()
            self.process_events_until(lambda: not self.window._m6_analysis_running)

        critical.assert_not_called()
        self.assertIsNone(self.window._m6_completed_context)
        self.assertIsNone(series.m6_analysis_state)
        self.assertIn("discarded", self.window.statusBar().currentMessage().lower())


if __name__ == "__main__":
    unittest.main()
