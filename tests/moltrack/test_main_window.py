import os
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np

from moltrack.core import (
    MolTrackImageSeries,
    MolTrackRegistrationFrameResult,
    MolTrackRegistrationResultSet,
)
from nanotrack.core import STMSequenceMetadata

try:
    from PyQt6.QtWidgets import QApplication
except ImportError:  # pragma: no cover - optional outside target GUI env
    QApplication = None

if QApplication is not None:
    from PyQt6.QtCore import QThread
    from PyQt6.QtWidgets import QFileDialog, QMessageBox

    from moltrack.ui import MolTrackMainWindow
else:  # pragma: no cover - optional outside target GUI env
    QFileDialog = None
    QMessageBox = None
    MolTrackMainWindow = None


@unittest.skipUnless(QApplication is not None, "PyQt6 is required for MolTrack GUI tests")
class MolTrackMainWindowTests(unittest.TestCase):
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
            time.sleep(0.01)
        self.fail("Timed out waiting for Qt event-loop condition.")

    def test_empty_workspace_exposes_file_actions_and_disables_frame_navigation(self) -> None:
        self.window = MolTrackMainWindow()

        self.assertEqual(self.window.action_open_stm.text(), "Open STM...")
        self.assertEqual(self.window.action_open_stm_reverse.text(), "Open STM Reverse...")
        self.assertEqual(self.window.lbl_frame.text(), "Frame: - / -")
        self.assertFalse(self.window.slider_frame.isEnabled())
        self.assertFalse(self.window.btn_remove_current_frame.isEnabled())
        self.assertEqual(self.window.metadata_panel.title(), "Metadata")

    def test_canceling_open_dialog_keeps_loaded_series_unchanged(self) -> None:
        calls = []

        def fake_loader(source_path, *, reverse_frame_order=False):
            calls.append((source_path, reverse_frame_order))
            raise AssertionError("loader must not run when the dialog is canceled")

        self.window = MolTrackMainWindow(series_loader=fake_loader)
        frames = np.arange(24, dtype=np.float32).reshape(3, 2, 4)
        series = MolTrackImageSeries(
            source_path="loaded.mpp",
            raw_frames=frames,
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=2, image_type="Topo"),
        )
        self.window.set_image_series(series)

        with (
            patch.object(QFileDialog, "getOpenFileName", return_value=("", "")),
            patch.object(QMessageBox, "critical", return_value=QMessageBox.StandardButton.Ok) as critical,
        ):
            self.window.action_open_stm.trigger()
            self.__class__._app.processEvents()

        self.assertEqual(calls, [])
        self.assertEqual(self.window.lbl_frame.text(), "Frame: 1 / 3")
        np.testing.assert_array_equal(self.window.viewer.viewer.image_item.image, frames[0])
        self.assertIn("Active frame: 1 / 3", self.window.metadata_panel.metadata_text())
        critical.assert_not_called()

    def test_open_dialog_loader_error_reports_problem_and_preserves_loaded_series(self) -> None:
        calls = []

        def fake_loader(source_path, *, reverse_frame_order=False):
            calls.append((source_path, reverse_frame_order))
            raise ValueError(f"Only .mpp STM movies are supported: {source_path}")

        self.window = MolTrackMainWindow(series_loader=fake_loader)
        frames = np.arange(24, dtype=np.float32).reshape(3, 2, 4)
        series = MolTrackImageSeries(
            source_path="current.mpp",
            raw_frames=frames,
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=2, image_type="Topo"),
        )
        self.window.set_image_series(series)
        self.window.slider_frame.setValue(2)
        self.__class__._app.processEvents()

        with (
            patch.object(QFileDialog, "getOpenFileName", return_value=("bad.txt", "")),
            patch.object(QMessageBox, "critical", return_value=QMessageBox.StandardButton.Ok) as critical,
        ):
            self.window.action_open_stm.trigger()
            self.__class__._app.processEvents()

        self.assertEqual(calls, [("bad.txt", False)])
        self.assertEqual(series.active_frame_index, 2)
        self.assertEqual(self.window.lbl_frame.text(), "Frame: 3 / 3")
        np.testing.assert_array_equal(self.window.viewer.viewer.image_item.image, frames[2])
        metadata_text = self.window.metadata_panel.metadata_text()
        self.assertIn("Source: current.mpp", metadata_text)
        self.assertIn("Active frame: 3 / 3", metadata_text)
        critical.assert_called_once()
        _parent, title, message = critical.call_args.args
        self.assertEqual(title, "Open STM failed")
        self.assertIn("bad.txt", message)
        self.assertIn("Open STM failed", self.window.statusBar().currentMessage())

    def test_setting_series_enables_frame_navigation_and_slider_selects_frame(self) -> None:
        self.window = MolTrackMainWindow()
        frames = np.arange(24, dtype=np.float32).reshape(3, 2, 4)
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames,
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=2),
        )

        self.window.set_image_series(series)

        self.assertTrue(self.window.slider_frame.isEnabled())
        self.assertEqual(self.window.slider_frame.minimum(), 0)
        self.assertEqual(self.window.slider_frame.maximum(), 2)
        self.assertEqual(self.window.lbl_frame.text(), "Frame: 1 / 3")

        self.window.slider_frame.setValue(2)
        self.__class__._app.processEvents()

        self.assertEqual(series.active_frame_index, 2)
        self.assertEqual(self.window.lbl_frame.text(), "Frame: 3 / 3")
        np.testing.assert_array_equal(self.window.viewer.viewer.image_item.image, frames[2])

    def test_remove_current_frame_button_deletes_active_frame_from_working_series(self) -> None:
        self.window = MolTrackMainWindow()
        frames = np.arange(24, dtype=np.float32).reshape(3, 2, 4)
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames.copy(),
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=2),
        )
        self.window.set_image_series(series)
        self.window.slider_frame.setValue(1)
        self.__class__._app.processEvents()

        self.window.btn_remove_current_frame.click()
        self.__class__._app.processEvents()

        self.assertEqual(series.frame_count, 2)
        self.assertEqual(series.active_frame_index, 1)
        np.testing.assert_array_equal(series.raw_frames, frames[[0, 2]])
        self.assertEqual(self.window.slider_frame.maximum(), 1)
        self.assertEqual(self.window.lbl_frame.text(), "Frame: 2 / 2")
        np.testing.assert_array_equal(self.window.viewer.viewer.image_item.image, frames[2])
        self.assertIn("Frames: 2", self.window.metadata_panel.metadata_text())

    def test_remove_current_frame_button_disables_when_one_frame_remains(self) -> None:
        self.window = MolTrackMainWindow()
        frames = np.arange(16, dtype=np.float32).reshape(2, 2, 4)
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames.copy(),
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=2),
        )
        self.window.set_image_series(series)

        self.window.btn_remove_current_frame.click()
        self.__class__._app.processEvents()

        self.assertEqual(series.frame_count, 1)
        self.assertFalse(self.window.btn_remove_current_frame.isEnabled())
        self.assertEqual(self.window.slider_frame.maximum(), 0)
        self.assertEqual(self.window.lbl_frame.text(), "Frame: 1 / 1")

    def test_run_registration_button_registers_current_working_series(self) -> None:
        calls = []

        def fake_registration_runner(series, *, settings):
            calls.append((series.raw_frames.copy(), settings.backend))
            result_set = MolTrackRegistrationResultSet(
                settings=settings,
                results_by_frame={
                    0: MolTrackRegistrationFrameResult(
                        frame_index=0,
                        shift_xy=(0.0, 0.0),
                        method="identity",
                        quality_score=1.0,
                    ),
                    1: MolTrackRegistrationFrameResult(
                        frame_index=1,
                        shift_xy=(1.25, -0.5),
                        method="phase_correlation",
                        quality_score=0.8,
                    ),
                },
            )
            series.registration_results = result_set
            return result_set

        self.window = MolTrackMainWindow(registration_runner=fake_registration_runner)
        frames = np.arange(16, dtype=np.float32).reshape(2, 2, 4)
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames.copy(),
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=2),
        )
        self.window.set_image_series(series)

        self.window.btn_run_registration.click()
        self.process_events_until(lambda: series.registration_results is not None and self.window.btn_run_registration.isEnabled())

        self.assertEqual(len(calls), 1)
        passed_frames, backend = calls[0]
        np.testing.assert_array_equal(passed_frames, frames)
        self.assertEqual(backend, "phase_correlation")
        self.assertIsNotNone(series.registration_results)
        self.assertEqual(series.registration_results.result_count, 2)
        self.assertIn("Registered 2 frames", self.window.lbl_registration_status.text())
        self.assertIn("Registration finished", self.window.statusBar().currentMessage())

    def test_can_select_and_run_optical_flow_median_registration(self) -> None:
        calls = []

        def fake_registration_runner(series, *, settings):
            calls.append(settings.backend)
            result_set = MolTrackRegistrationResultSet(
                settings=settings,
                results_by_frame={
                    0: MolTrackRegistrationFrameResult(
                        frame_index=0,
                        shift_xy=(0.0, 0.0),
                        method="identity",
                        quality_score=1.0,
                    ),
                    1: MolTrackRegistrationFrameResult(
                        frame_index=1,
                        shift_xy=(0.5, -1.5),
                        method="optical_flow_median",
                        quality_score=0.8,
                    ),
                },
            )
            series.registration_results = result_set
            return result_set

        self.window = MolTrackMainWindow(registration_runner=fake_registration_runner)
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.arange(16, dtype=np.float32).reshape(2, 2, 4),
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=2),
        )
        self.window.set_image_series(series)

        self.assertGreaterEqual(self.window.cmb_registration_backend.findText("optical_flow_median"), 0)
        self.window.cmb_registration_backend.setCurrentText("optical_flow_median")
        self.window.btn_run_registration.click()
        self.process_events_until(lambda: series.registration_results is not None and self.window.btn_run_registration.isEnabled())

        self.assertEqual(calls, ["optical_flow_median"])
        self.assertEqual(series.registration_results.settings.backend, "optical_flow_median")
        self.assertIn("Registered 2 frames with optical_flow_median", self.window.lbl_registration_status.text())

    def test_run_registration_uses_worker_thread_and_shows_busy_dialog_while_running(self) -> None:
        events = []
        main_thread_id = int(QThread.currentThreadId())

        class FakeProgressDialog:
            def __init__(self, label_text, cancel_button_text, minimum, maximum, parent):
                events.append(("dialog_init", label_text, cancel_button_text, minimum, maximum, parent))

            def setWindowTitle(self, title):
                events.append(("title", title))

            def setWindowModality(self, modality):
                events.append(("modality", modality))

            def setCancelButton(self, button):
                events.append(("cancel_button", button))

            def setMinimumDuration(self, duration_ms):
                events.append(("minimum_duration", duration_ms))

            def setAutoClose(self, enabled):
                events.append(("auto_close", enabled))

            def setAutoReset(self, enabled):
                events.append(("auto_reset", enabled))

            def show(self):
                events.append("show")

            def close(self):
                events.append("close")

        def fake_registration_runner(series, *, settings):
            events.append(("runner_thread", int(QThread.currentThreadId())))
            result_set = MolTrackRegistrationResultSet(
                settings=settings,
                results_by_frame={
                    frame_index: MolTrackRegistrationFrameResult(
                        frame_index=frame_index,
                        shift_xy=(0.0, 0.0),
                        method="phase_correlation",
                        quality_score=1.0,
                    )
                    for frame_index in range(series.frame_count)
                },
            )
            series.registration_results = result_set
            return result_set

        self.window = MolTrackMainWindow(registration_runner=fake_registration_runner)
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.arange(16, dtype=np.float32).reshape(2, 2, 4),
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=2),
        )
        self.window.set_image_series(series)

        with patch("moltrack.ui.main_window.QProgressDialog", FakeProgressDialog, create=True):
            self.window.btn_run_registration.click()
            self.assertIn("show", events)
            self.assertFalse(self.window.btn_run_registration.isEnabled())
            self.process_events_until(lambda: series.registration_results is not None and self.window.btn_run_registration.isEnabled())

        self.assertIn("show", events)
        self.assertIn("close", events)
        runner_events = [event for event in events if isinstance(event, tuple) and event[0] == "runner_thread"]
        self.assertEqual(len(runner_events), 1)
        self.assertNotEqual(runner_events[0][1], main_thread_id)
        self.assertLess(events.index("show"), events.index(runner_events[0]))
        self.assertLess(events.index(runner_events[0]), events.index("close"))
        self.assertTrue(self.window.btn_run_registration.isEnabled())
        self.assertIn("Registered 2 frames", self.window.lbl_registration_status.text())

    def test_run_registration_after_frame_removal_uses_shortened_working_series(self) -> None:
        calls = []

        def fake_registration_runner(series, *, settings):
            calls.append(series.raw_frames.copy())
            result_set = MolTrackRegistrationResultSet(
                settings=settings,
                results_by_frame={
                    frame_index: MolTrackRegistrationFrameResult(
                        frame_index=frame_index,
                        shift_xy=(float(frame_index), -float(frame_index)),
                        method="phase_correlation",
                        quality_score=0.8,
                    )
                    for frame_index in range(series.frame_count)
                },
            )
            series.registration_results = result_set
            return result_set

        self.window = MolTrackMainWindow(registration_runner=fake_registration_runner)
        frames = np.arange(24, dtype=np.float32).reshape(3, 2, 4)
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames.copy(),
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=2),
        )
        self.window.set_image_series(series)
        self.window.slider_frame.setValue(1)
        self.__class__._app.processEvents()

        self.window.btn_remove_current_frame.click()
        self.window.btn_run_registration.click()
        self.process_events_until(lambda: series.registration_results is not None and self.window.btn_run_registration.isEnabled())

        self.assertEqual(len(calls), 1)
        np.testing.assert_array_equal(calls[0], frames[[0, 2]])
        self.assertEqual(series.registration_results.result_count, 2)
        self.assertIn("Registered 2 frames", self.window.lbl_registration_status.text())

    def test_registration_view_mode_switches_between_raw_and_expanded_aligned_frames(self) -> None:
        expanded_frames = (np.arange(2 * 3 * 5, dtype=np.float32).reshape(2, 3, 5) + 1000.0)

        def fake_registration_runner(series, *, settings):
            result_set = MolTrackRegistrationResultSet(
                settings=settings,
                results_by_frame={
                    0: MolTrackRegistrationFrameResult(
                        frame_index=0,
                        shift_xy=(0.0, 0.0),
                        method="identity",
                        quality_score=1.0,
                    ),
                    1: MolTrackRegistrationFrameResult(
                        frame_index=1,
                        shift_xy=(2.0, -1.0),
                        method="phase_correlation",
                        quality_score=0.8,
                    ),
                },
            )
            series.registration_results = result_set
            return result_set

        def fake_expanded_builder(series):
            expanded_stack = SimpleNamespace(
                frames=expanded_frames,
                metadata=STMSequenceMetadata(pixels_x=5, pixels_y=3),
                padding_ltrb=(0, 1, 1, 0),
                frame_origins_xy=np.asarray([[0.0, 1.0], [2.0, 0.0]], dtype=np.float64),
            )
            series.expanded_aligned_stack = expanded_stack
            return expanded_stack

        self.window = MolTrackMainWindow(
            registration_runner=fake_registration_runner,
            expanded_aligned_builder=fake_expanded_builder,
        )
        frames = np.arange(16, dtype=np.float32).reshape(2, 2, 4)
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames.copy(),
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=2),
        )
        self.window.set_image_series(series)

        self.window.btn_run_registration.click()
        self.process_events_until(lambda: series.registration_results is not None and self.window.btn_run_registration.isEnabled())
        self.window.cmb_registration_view_mode.setCurrentText("Show expanded aligned")
        self.__class__._app.processEvents()

        np.testing.assert_array_equal(self.window.viewer.viewer.image_item.image, expanded_frames[0])
        self.assertIn("Expanded aligned", self.window.viewer.lbl_title.text())

        self.window.slider_frame.setValue(1)
        self.__class__._app.processEvents()

        np.testing.assert_array_equal(self.window.viewer.viewer.image_item.image, expanded_frames[1])

        self.window.cmb_registration_view_mode.setCurrentText("Show raw")
        self.__class__._app.processEvents()

        np.testing.assert_array_equal(self.window.viewer.viewer.image_item.image, frames[1])
        self.assertNotIn("Expanded aligned", self.window.viewer.lbl_title.text())

    def test_remove_current_frame_disables_expanded_aligned_view_until_registration_reruns(self) -> None:
        def fake_registration_runner(series, *, settings):
            result_set = MolTrackRegistrationResultSet(
                settings=settings,
                results_by_frame={
                    frame_index: MolTrackRegistrationFrameResult(
                        frame_index=frame_index,
                        shift_xy=(float(frame_index), 0.0),
                        method="phase_correlation",
                        quality_score=0.8,
                    )
                    for frame_index in range(series.frame_count)
                },
            )
            series.registration_results = result_set
            return result_set

        def fake_expanded_builder(series):
            expanded_stack = SimpleNamespace(
                frames=np.full((series.frame_count, 3, 5), 42.0, dtype=np.float32),
                metadata=STMSequenceMetadata(pixels_x=5, pixels_y=3),
                padding_ltrb=(0, 0, 1, 1),
                frame_origins_xy=np.zeros((series.frame_count, 2), dtype=np.float64),
            )
            series.expanded_aligned_stack = expanded_stack
            return expanded_stack

        self.window = MolTrackMainWindow(
            registration_runner=fake_registration_runner,
            expanded_aligned_builder=fake_expanded_builder,
        )
        frames = np.arange(24, dtype=np.float32).reshape(3, 2, 4)
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames.copy(),
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=2),
        )
        self.window.set_image_series(series)
        self.window.btn_run_registration.click()
        self.process_events_until(lambda: series.registration_results is not None and self.window.btn_run_registration.isEnabled())
        self.window.cmb_registration_view_mode.setCurrentText("Show expanded aligned")
        self.__class__._app.processEvents()

        self.window.btn_remove_current_frame.click()
        self.__class__._app.processEvents()

        self.assertIsNone(series.registration_results)
        self.assertIsNone(series.expanded_aligned_stack)
        self.assertEqual(self.window.cmb_registration_view_mode.currentText(), "Show raw")
        self.assertFalse(self.window.cmb_registration_view_mode.isEnabled())
        np.testing.assert_array_equal(self.window.viewer.viewer.image_item.image, frames[1])

    def test_run_registration_reports_error_when_series_has_too_few_frames(self) -> None:
        self.window = MolTrackMainWindow()
        series = MolTrackImageSeries(
            source_path="single.mpp",
            raw_frames=np.zeros((1, 2, 4), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=2),
        )
        self.window.set_image_series(series)

        with patch.object(QMessageBox, "critical", return_value=QMessageBox.StandardButton.Ok) as critical:
            self.window.btn_run_registration.click()
            self.process_events_until(lambda: critical.called)

        critical.assert_called_once()
        _parent, title, message = critical.call_args.args
        self.assertEqual(title, "Registration failed")
        self.assertIn("at least two frames", message)
        self.assertTrue(self.window.btn_run_registration.isEnabled())
        self.assertIn("Registration failed", self.window.lbl_registration_status.text())
        self.assertIn("Registration failed", self.window.statusBar().currentMessage())

    def test_open_stm_source_uses_loader_and_displays_loaded_series(self) -> None:
        frames = np.zeros((2, 3, 4), dtype=np.float32)
        metadata = STMSequenceMetadata(pixels_x=4, pixels_y=3)
        calls = []

        def fake_loader(source_path, *, reverse_frame_order=False):
            calls.append((source_path, reverse_frame_order))
            return MolTrackImageSeries(
                source_path=str(source_path),
                raw_frames=frames,
                metadata=metadata,
                reverse_frame_order=reverse_frame_order,
            )

        self.window = MolTrackMainWindow(series_loader=fake_loader)

        self.window.open_stm_source("movie.mpp", reverse_frame_order=True)

        self.assertEqual(calls, [("movie.mpp", True)])
        self.assertTrue(self.window.slider_frame.isEnabled())
        self.assertEqual(self.window.slider_frame.maximum(), 1)
        self.assertEqual(self.window.lbl_frame.text(), "Frame: 1 / 2")

    def test_setting_series_updates_metadata_summary(self) -> None:
        self.window = MolTrackMainWindow()
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.zeros((3, 2, 4), dtype=np.float32),
            metadata=STMSequenceMetadata(
                pixels_x=4,
                pixels_y=2,
                size_nm_x=8.0,
                size_nm_y=1.0,
                image_type="Topo",
            ),
        )

        self.window.set_image_series(series)

        metadata_text = self.window.metadata_panel.metadata_text()
        self.assertIn("Source: movie.mpp", metadata_text)
        self.assertIn("Frames: 3", metadata_text)
        self.assertIn("Active frame: 1 / 3", metadata_text)
        self.assertIn("Shape: 4x2 px", metadata_text)
        self.assertIn("Physical size: 8 nm x 1 nm", metadata_text)
        self.assertIn("Pixel size: 2 nm/px x 0.5 nm/px", metadata_text)
        self.assertIn("Channel: Topo", metadata_text)

        self.window.slider_frame.setValue(2)
        self.__class__._app.processEvents()

        self.assertIn("Active frame: 3 / 3", self.window.metadata_panel.metadata_text())


if __name__ == "__main__":
    unittest.main()
