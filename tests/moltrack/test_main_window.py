import os
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np

from moltrack.core import (
    MolecularDetection,
    MolecularDetectionSet,
    MolTrackImageSeries,
    MolTrackRegistrationFrameResult,
    MolTrackRegistrationResultSet,
    MolTrackRegistrationSettings,
)
from moltrack.persistence import save_moltrack_session
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
        self.window = MolTrackMainWindow(yolo_model_discovery=lambda: [])

        self.assertEqual(self.window.action_open_stm.text(), "Open STM...")
        self.assertEqual(self.window.action_open_stm_reverse.text(), "Open STM Reverse...")
        self.assertEqual(self.window.action_open_state.text(), "Open State...")
        self.assertEqual(self.window.action_save_state.text(), "Save State...")
        self.assertEqual(self.window.action_save_state_as.text(), "Save State As...")
        self.assertEqual(self.window.lbl_frame.text(), "Frame: - / -")
        self.assertFalse(self.window.slider_frame.isEnabled())
        self.assertFalse(self.window.btn_remove_current_frame.isEnabled())
        self.assertTrue(self.window.action_open_state.isEnabled())
        self.assertFalse(self.window.action_save_state.isEnabled())
        self.assertFalse(self.window.action_save_state_as.isEnabled())
        self.assertEqual(self.window.metadata_panel.title(), "Metadata")
        self.assertEqual(self.window.yolo_group.title(), "YOLO Detection")
        self.assertEqual(self.window.cmb_yolo_model.count(), 0)
        self.assertIn("No YOLO models found in nanotrack/yolo_models", self.window.lbl_yolo_models.text())
        self.assertFalse(self.window.btn_yolo_detect_current.isEnabled())
        self.assertEqual(self.window.btn_yolo_detect_all_frames.text(), "Detect All Frames")
        self.assertFalse(self.window.btn_yolo_detect_all_frames.isEnabled())
        self.assertFalse(self.window.btn_yolo_clear_current.isEnabled())
        self.assertIn("current 0", self.window.lbl_yolo_status.text())
        self.assertIn("series 0", self.window.lbl_yolo_status.text())

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

    def test_save_state_as_uses_dialog_and_remembers_session_path(self) -> None:
        saved = []

        def fake_saver(path, series, ui_state):
            saved.append((path, series, dict(ui_state)))
            return SimpleNamespace(source_path=series.source_path)

        self.window = MolTrackMainWindow(session_saver=fake_saver)
        frames = np.arange(24, dtype=np.float32).reshape(3, 2, 4)
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames,
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=2),
        )
        self.window.set_image_series(series)

        self.assertTrue(self.window.action_save_state.isEnabled())
        self.assertTrue(self.window.action_save_state_as.isEnabled())

        with patch.object(QFileDialog, "getSaveFileName", return_value=("state.moltrack.json", "")) as dialog:
            self.window.action_save_state_as.trigger()
            self.__class__._app.processEvents()

        dialog.assert_called_once()
        self.assertEqual(saved, [("state.moltrack.json", series, {"registration_view_mode": "Show raw"})])
        self.assertIn("Saved state state.moltrack.json", self.window.statusBar().currentMessage())

        saved.clear()
        with patch.object(QFileDialog, "getSaveFileName", return_value=("other.moltrack.json", "")) as dialog:
            self.window.action_save_state.trigger()
            self.__class__._app.processEvents()

        dialog.assert_not_called()
        self.assertEqual(saved, [("state.moltrack.json", series, {"registration_view_mode": "Show raw"})])

    def test_open_state_uses_dialog_and_restores_working_series(self) -> None:
        loaded_session = SimpleNamespace(registration_view_mode="Show raw")
        load_calls = []
        restore_calls = []
        frames = np.arange(24, dtype=np.float32).reshape(3, 2, 4)

        def fake_session_loader(path):
            load_calls.append(path)
            return loaded_session

        def fake_session_restorer(session):
            restore_calls.append(session)
            return MolTrackImageSeries(
                source_path="movie.mpp",
                raw_frames=frames,
                metadata=STMSequenceMetadata(pixels_x=4, pixels_y=2),
                active_frame_index=1,
            )

        self.window = MolTrackMainWindow(
            session_loader=fake_session_loader,
            session_restorer=fake_session_restorer,
        )

        with patch.object(QFileDialog, "getOpenFileName", return_value=("state.moltrack.json", "")) as dialog:
            self.window.action_open_state.trigger()
            self.__class__._app.processEvents()

        dialog.assert_called_once()
        self.assertEqual(load_calls, ["state.moltrack.json"])
        self.assertEqual(restore_calls, [loaded_session])
        self.assertEqual(self.window.lbl_frame.text(), "Frame: 2 / 3")
        np.testing.assert_array_equal(self.window.viewer.viewer.image_item.image, frames[1])
        self.assertIn("Source: movie.mpp", self.window.metadata_panel.metadata_text())
        self.assertIn("Loaded state state.moltrack.json", self.window.statusBar().currentMessage())
        self.assertTrue(self.window.action_save_state.isEnabled())

    def test_save_then_open_state_round_trip_restores_working_series_and_expanded_view(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            source_path = tmp_path / "movie.mpp"
            source_path.write_bytes(b"fake mpp bytes")
            session_path = tmp_path / "state.moltrack.json"
            full_frames = np.arange(40, dtype=np.float32).reshape(5, 2, 4)
            working_series = MolTrackImageSeries(
                source_path=str(source_path),
                raw_frames=full_frames.copy(),
                metadata=STMSequenceMetadata(pixels_x=4, pixels_y=2),
                active_frame_index=2,
            )
            working_series.remove_frame(1)
            working_series.remove_frame(2)
            working_series.set_active_frame(1)
            settings = MolTrackRegistrationSettings(backend="phase_correlation")
            working_series.registration_results = MolTrackRegistrationResultSet(
                settings=settings,
                results_by_frame={
                    frame_index: MolTrackRegistrationFrameResult(
                        frame_index=frame_index,
                        shift_xy=(float(frame_index), -float(frame_index)),
                        method="phase_correlation",
                        quality_score=0.8,
                    )
                    for frame_index in range(working_series.frame_count)
                },
            )
            detections = MolecularDetectionSet(frame_count=working_series.frame_count)
            detections.set_detections(
                1,
                [
                    MolecularDetection(
                        frame_index=1,
                        bbox_xyxy=(1, 0, 4, 2),
                        confidence=0.86,
                        model_name="missing-model.pt",
                        checkpoint_path="nanotrack/yolo_models/missing-model.pt",
                        source_view="expanded_aligned",
                    )
                ],
                source_view="expanded_aligned",
                frame_shape=(3, 5),
            )
            working_series.molecular_detections = detections
            expanded_frames = np.arange(working_series.frame_count * 3 * 5, dtype=np.float32).reshape(
                working_series.frame_count,
                3,
                5,
            )
            loader_calls = []
            expanded_builder_calls = []

            def fake_series_loader(source_path_arg, *, reverse_frame_order=False):
                loader_calls.append((str(source_path_arg), reverse_frame_order))
                return MolTrackImageSeries(
                    source_path=str(source_path_arg),
                    raw_frames=full_frames.copy(),
                    metadata=STMSequenceMetadata(pixels_x=4, pixels_y=2),
                    reverse_frame_order=reverse_frame_order,
                )

            def fake_expanded_builder(series):
                expanded_builder_calls.append(series.frame_count)
                expanded_stack = SimpleNamespace(
                    frames=expanded_frames,
                    metadata=STMSequenceMetadata(pixels_x=5, pixels_y=3),
                    padding_ltrb=(0, 1, 1, 0),
                    frame_origins_xy=np.zeros((series.frame_count, 2), dtype=np.float64),
                )
                series.expanded_aligned_stack = expanded_stack
                return expanded_stack

            self.window = MolTrackMainWindow(
                series_loader=fake_series_loader,
                expanded_aligned_builder=fake_expanded_builder,
                yolo_model_discovery=lambda: [],
            )
            self.window.set_image_series(working_series)
            self.window.cmb_registration_view_mode.setCurrentText("Show expanded aligned")
            self.__class__._app.processEvents()
            expanded_builder_calls.clear()

            with patch.object(QFileDialog, "getSaveFileName", return_value=(str(session_path), "")):
                self.window.action_save_state_as.trigger()
                self.__class__._app.processEvents()

            self.window.close()
            self.window.deleteLater()
            self.__class__._app.processEvents()
            self.window = MolTrackMainWindow(
                series_loader=fake_series_loader,
                expanded_aligned_builder=fake_expanded_builder,
                yolo_model_discovery=lambda: [],
            )

            with patch.object(QFileDialog, "getOpenFileName", return_value=(str(session_path), "")):
                self.window.action_open_state.trigger()
                self.__class__._app.processEvents()

            self.assertEqual(loader_calls, [(str(source_path.resolve()), False)])
            self.assertEqual(expanded_builder_calls, [3])
            self.assertEqual(self.window.lbl_frame.text(), "Frame: 2 / 3")
            self.assertEqual(self.window.slider_frame.maximum(), 2)
            self.assertEqual(self.window.cmb_registration_view_mode.currentText(), "Show expanded aligned")
            np.testing.assert_array_equal(self.window.viewer.viewer.image_item.image, expanded_frames[1])
            self.assertIn("Expanded aligned", self.window.viewer.lbl_title.text())
            self.assertEqual(self.window.viewer.visible_molecular_detection_count(), 1)
            self.assertIn("No YOLO models found", self.window.lbl_yolo_models.text())
            self.assertIn("current 1", self.window.lbl_yolo_status.text())
            self.assertIn("series 1", self.window.lbl_yolo_status.text())
            metadata_text = self.window.metadata_panel.metadata_text()
            self.assertIn("Frames: 3", metadata_text)
            self.assertIn("Active frame: 2 / 3", metadata_text)
            self.assertIn("Expanded shape: 5x3 px", metadata_text)
            self.assertIn(f"Loaded state {session_path}", self.window.statusBar().currentMessage())

    def test_open_state_reports_missing_source_and_preserves_loaded_series(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            source_path = tmp_path / "movie.mpp"
            source_path.write_bytes(b"fake mpp bytes")
            session_path = tmp_path / "state.moltrack.json"
            saved_series = MolTrackImageSeries(
                source_path=str(source_path),
                raw_frames=np.arange(16, dtype=np.float32).reshape(2, 2, 4),
                metadata=STMSequenceMetadata(pixels_x=4, pixels_y=2),
            )
            save_moltrack_session(session_path, saved_series, None)
            source_path.unlink()

            self.window = MolTrackMainWindow()
            current_frames = np.full((2, 2, 4), 7.0, dtype=np.float32)
            current_series = MolTrackImageSeries(
                source_path="current.mpp",
                raw_frames=current_frames,
                metadata=STMSequenceMetadata(pixels_x=4, pixels_y=2),
                active_frame_index=1,
            )
            self.window.set_image_series(current_series)

            with (
                patch.object(QFileDialog, "getOpenFileName", return_value=(str(session_path), "")),
                patch.object(QMessageBox, "critical", return_value=QMessageBox.StandardButton.Ok) as critical,
            ):
                self.window.action_open_state.trigger()
                self.__class__._app.processEvents()

            self.assertEqual(self.window.lbl_frame.text(), "Frame: 2 / 2")
            np.testing.assert_array_equal(self.window.viewer.viewer.image_item.image, current_frames[1])
            self.assertIn("Source: current.mpp", self.window.metadata_panel.metadata_text())
            critical.assert_called_once()
            _parent, title, message = critical.call_args.args
            self.assertEqual(title, "Open State failed")
            self.assertIn("does not exist", message)
            self.assertIn("Open State failed", self.window.statusBar().currentMessage())

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

    def test_viewer_shows_molecular_detections_for_active_raw_frame(self) -> None:
        self.window = MolTrackMainWindow()
        frames = np.arange(48, dtype=np.float32).reshape(3, 4, 4)
        detections = MolecularDetectionSet(frame_count=3)
        detections.set_detections(
            0,
            [
                MolecularDetection(frame_index=0, bbox_xyxy=(0, 0, 2, 2), confidence=0.9, selected=True),
                MolecularDetection(frame_index=0, bbox_xyxy=(2, 1, 4, 3), confidence=0.6, selected=False),
            ],
            source_view="raw",
            frame_shape=(4, 4),
        )
        detections.set_detections(
            2,
            [MolecularDetection(frame_index=2, bbox_xyxy=(1, 1, 3, 3), confidence=0.7)],
            source_view="raw",
            frame_shape=(4, 4),
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames,
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=4),
            molecular_detections=detections,
        )

        self.window.set_image_series(series)

        self.assertEqual(self.window.viewer.visible_molecular_detection_count(), 2)
        self.assertEqual(
            self.window.viewer.visible_molecular_detection_colors(),
            [(255, 0, 255), (255, 140, 0)],
        )

        self.window.slider_frame.setValue(1)
        self.__class__._app.processEvents()

        self.assertEqual(self.window.viewer.visible_molecular_detection_count(), 0)

        self.window.slider_frame.setValue(2)
        self.__class__._app.processEvents()

        self.assertEqual(self.window.viewer.visible_molecular_detection_count(), 1)

    def test_viewer_uses_detection_source_view_for_expanded_aligned_overlay(self) -> None:
        expanded_frames = np.arange(2 * 5 * 6, dtype=np.float32).reshape(2, 5, 6)

        def fake_expanded_builder(series):
            expanded_stack = SimpleNamespace(
                frames=expanded_frames,
                metadata=STMSequenceMetadata(pixels_x=6, pixels_y=5),
                padding_ltrb=(1, 1, 1, 2),
                frame_origins_xy=np.zeros((series.frame_count, 2), dtype=np.float64),
            )
            series.expanded_aligned_stack = expanded_stack
            return expanded_stack

        self.window = MolTrackMainWindow(expanded_aligned_builder=fake_expanded_builder)
        frames = np.arange(2 * 4 * 4, dtype=np.float32).reshape(2, 4, 4)
        detections = MolecularDetectionSet(frame_count=2)
        detections.set_detections(
            0,
            [
                MolecularDetection(frame_index=0, bbox_xyxy=(0, 0, 2, 2), confidence=0.9, source_view="raw"),
                MolecularDetection(frame_index=0, bbox_xyxy=(2, 2, 4, 4), confidence=0.7, source_view="raw"),
            ],
            source_view="raw",
            frame_shape=(4, 4),
        )
        detections.set_detections(
            0,
            [
                MolecularDetection(
                    frame_index=0,
                    bbox_xyxy=(1, 1, 5, 4),
                    confidence=0.8,
                    source_view="expanded_aligned",
                )
            ],
            source_view="expanded_aligned",
            frame_shape=(5, 6),
        )
        settings = MolTrackRegistrationSettings()
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames,
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=4),
            registration_results=MolTrackRegistrationResultSet(
                settings=settings,
                results_by_frame={
                    frame_index: MolTrackRegistrationFrameResult(
                        frame_index=frame_index,
                        shift_xy=(0.0, 0.0),
                        method="identity",
                    )
                    for frame_index in range(2)
                },
            ),
            molecular_detections=detections,
        )

        self.window.set_image_series(series)

        self.assertEqual(self.window.viewer.visible_molecular_detection_count(), 2)

        self.window.cmb_registration_view_mode.setCurrentText("Show expanded aligned")
        self.__class__._app.processEvents()

        self.assertEqual(self.window.viewer.visible_molecular_detection_count(), 1)
        np.testing.assert_array_equal(self.window.viewer.viewer.image_item.image, expanded_frames[0])
        self.assertIn("Expanded aligned", self.window.viewer.lbl_title.text())

    def test_yolo_detect_current_frame_stores_raw_detections_and_updates_viewer(self) -> None:
        calls = []
        checkpoint = Path("model-a.pt")

        class FakeYoloDetector:
            def detect_frame(
                self,
                frame,
                *,
                frame_index,
                checkpoint_path,
                confidence_threshold,
                iou_threshold,
                source_view,
            ):
                calls.append(
                    {
                        "frame": np.asarray(frame).copy(),
                        "frame_index": frame_index,
                        "checkpoint_path": checkpoint_path,
                        "confidence_threshold": confidence_threshold,
                        "iou_threshold": iou_threshold,
                        "source_view": source_view,
                    }
                )
                return [
                    MolecularDetection(
                        frame_index=frame_index,
                        bbox_xyxy=(1, 1, 3, 3),
                        confidence=0.82,
                        model_name="model-a.pt",
                        checkpoint_path=str(checkpoint_path),
                        source_view=source_view,
                    )
                ]

        self.window = MolTrackMainWindow(
            yolo_model_discovery=lambda: [SimpleNamespace(name="model-a.pt", path=checkpoint)],
            yolo_detector=FakeYoloDetector(),
        )
        frames = np.arange(3 * 4 * 4, dtype=np.float32).reshape(3, 4, 4)
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames.copy(),
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=4),
        )
        self.window.set_image_series(series)
        self.window.slider_frame.setValue(1)
        self.window.sp_yolo_confidence.setValue(0.35)
        self.window.sp_yolo_iou.setValue(0.55)
        self.__class__._app.processEvents()

        self.window.btn_yolo_detect_current.click()
        self.__class__._app.processEvents()

        self.assertEqual(len(calls), 1)
        np.testing.assert_array_equal(calls[0]["frame"], frames[1])
        self.assertEqual(calls[0]["frame_index"], 1)
        self.assertEqual(calls[0]["checkpoint_path"], checkpoint)
        self.assertAlmostEqual(calls[0]["confidence_threshold"], 0.35)
        self.assertAlmostEqual(calls[0]["iou_threshold"], 0.55)
        self.assertEqual(calls[0]["source_view"], "raw")
        self.assertIsNotNone(series.molecular_detections)
        current = series.molecular_detections.get_detections(1, source_view="raw")
        self.assertEqual(len(current), 1)
        self.assertEqual(current[0].model_name, "model-a.pt")
        self.assertEqual(self.window.viewer.visible_molecular_detection_count(), 1)
        self.assertIn("current 1", self.window.lbl_yolo_status.text())
        self.assertIn("series 1", self.window.lbl_yolo_status.text())
        self.assertIn("model-a.pt", self.window.statusBar().currentMessage())
        self.assertIn("1 detection", self.window.statusBar().currentMessage())
        self.assertIn("frame 2", self.window.statusBar().currentMessage())

    def test_yolo_detect_all_frames_stores_raw_detections_from_worker_thread(self) -> None:
        calls = []
        thread_ids = []
        main_thread_id = int(QThread.currentThreadId())
        checkpoint = Path("model-a.pt")

        class FakeYoloDetector:
            def detect_frame(
                self,
                frame,
                *,
                frame_index,
                checkpoint_path,
                confidence_threshold,
                iou_threshold,
                source_view,
            ):
                thread_ids.append(int(QThread.currentThreadId()))
                calls.append(
                    {
                        "frame": np.asarray(frame).copy(),
                        "frame_index": frame_index,
                        "checkpoint_path": checkpoint_path,
                        "confidence_threshold": confidence_threshold,
                        "iou_threshold": iou_threshold,
                        "source_view": source_view,
                    }
                )
                return [
                    MolecularDetection(
                        frame_index=frame_index,
                        bbox_xyxy=(0, 0, 2, 2),
                        confidence=0.8,
                        model_name="model-a.pt",
                        checkpoint_path=str(checkpoint_path),
                        source_view=source_view,
                    )
                ]

        self.window = MolTrackMainWindow(
            yolo_model_discovery=lambda: [SimpleNamespace(name="model-a.pt", path=checkpoint)],
            yolo_detector=FakeYoloDetector(),
        )
        frames = np.arange(3 * 4 * 4, dtype=np.float32).reshape(3, 4, 4)
        detections = MolecularDetectionSet(frame_count=3)
        detections.set_detections(
            0,
            [MolecularDetection(frame_index=0, bbox_xyxy=(1, 1, 3, 3), confidence=0.5, source_view="raw")],
            source_view="raw",
            frame_shape=(4, 4),
        )
        detections.set_detections(
            0,
            [
                MolecularDetection(
                    frame_index=0,
                    bbox_xyxy=(2, 2, 4, 4),
                    confidence=0.6,
                    source_view="expanded_aligned",
                )
            ],
            source_view="expanded_aligned",
            frame_shape=(4, 4),
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames.copy(),
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=4),
            active_frame_index=1,
            molecular_detections=detections,
        )
        self.window.set_image_series(series)
        self.window.sp_yolo_confidence.setValue(0.4)
        self.window.sp_yolo_iou.setValue(0.6)

        self.window.btn_yolo_detect_all_frames.click()
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            self.__class__._app.processEvents()
            if (
                series.molecular_detections is not None
                and series.molecular_detections.detection_count == 4
                and "detections" in self.window.statusBar().currentMessage()
            ):
                break
            time.sleep(0.01)
        else:
            self.fail(
                "Timed out waiting for YOLO all-frames completion. "
                f"count={series.molecular_detections.detection_count}, "
                f"status={self.window.statusBar().currentMessage()!r}, "
                f"calls={calls!r}"
            )

        self.assertEqual([call["frame_index"] for call in calls], [0, 1, 2])
        self.assertTrue(thread_ids)
        self.assertTrue(all(thread_id != main_thread_id for thread_id in thread_ids))
        for frame_index, call in enumerate(calls):
            np.testing.assert_array_equal(call["frame"], frames[frame_index])
            self.assertEqual(call["checkpoint_path"], checkpoint)
            self.assertAlmostEqual(call["confidence_threshold"], 0.4)
            self.assertAlmostEqual(call["iou_threshold"], 0.6)
            self.assertEqual(call["source_view"], "raw")
            current = series.molecular_detections.get_detections(frame_index, source_view="raw")
            self.assertEqual(len(current), 1)
            self.assertEqual(current[0].model_name, "model-a.pt")
        self.assertEqual(len(series.molecular_detections.get_detections(0, source_view="expanded_aligned")), 1)
        self.assertEqual(series.active_frame_index, 1)
        self.assertEqual(self.window.viewer.visible_molecular_detection_count(), 1)
        self.assertIn("current 1", self.window.lbl_yolo_status.text())
        self.assertIn("series 4", self.window.lbl_yolo_status.text())
        self.assertIn("model-a.pt", self.window.statusBar().currentMessage())
        self.assertIn("3 detections", self.window.statusBar().currentMessage())
        self.assertIn("3 frames", self.window.statusBar().currentMessage())

    def test_yolo_detect_all_frames_shows_progress_dialog_while_worker_runs(self) -> None:
        events = []

        class FakeProgressDialog:
            def __init__(self, label_text, cancel_button_text, minimum, maximum, parent):
                events.append(("init", label_text, cancel_button_text, minimum, maximum, parent))

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

            def setValue(self, value):
                events.append(("value", value))

            def setLabelText(self, label_text):
                events.append(("label", label_text))

            def show(self):
                events.append("show")

            def close(self):
                events.append("close")

        class SlowYoloDetector:
            def detect_frame(
                self,
                frame,
                *,
                frame_index,
                checkpoint_path,
                confidence_threshold,
                iou_threshold,
                source_view,
            ):
                time.sleep(0.05)
                return []

        self.window = MolTrackMainWindow(
            yolo_model_discovery=lambda: [SimpleNamespace(name="model-a.pt", path=Path("model-a.pt"))],
            yolo_detector=SlowYoloDetector(),
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.arange(2 * 4 * 4, dtype=np.float32).reshape(2, 4, 4),
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=4),
        )
        self.window.set_image_series(series)

        with patch("moltrack.ui.main_window.QProgressDialog", FakeProgressDialog, create=True):
            self.window.btn_yolo_detect_all_frames.click()
            self.__class__._app.processEvents()

            self.assertIn("show", events)
            self.assertFalse(self.window.btn_yolo_detect_all_frames.isEnabled())
            self.assertFalse(self.window.action_open_stm.isEnabled())

            self.process_events_until(
                lambda: any(
                    isinstance(event, tuple) and event[0] == "label" and "frame 1 / 2" in event[1]
                    for event in events
                ),
                timeout_s=1.0,
            )
            self.process_events_until(
                lambda: "0 detections" in self.window.statusBar().currentMessage()
                and self.window.btn_yolo_detect_all_frames.isEnabled(),
                timeout_s=2.0,
            )

        self.assertIn(("title", "YOLO Detection"), events)
        self.assertIn(("value", 0), events)
        self.assertTrue(any(isinstance(event, tuple) and event == ("value", 1) for event in events))
        self.assertIn("close", events)
        self.assertTrue(self.window.action_open_stm.isEnabled())

    def test_yolo_detect_all_frames_uses_expanded_aligned_active_view(self) -> None:
        calls = []
        checkpoint = Path("expanded-model.pt")
        expanded_frames = (np.arange(2 * 5 * 6, dtype=np.float32).reshape(2, 5, 6) + 100.0)

        class FakeYoloDetector:
            def detect_frame(
                self,
                frame,
                *,
                frame_index,
                checkpoint_path,
                confidence_threshold,
                iou_threshold,
                source_view,
            ):
                calls.append((np.asarray(frame).copy(), frame_index, checkpoint_path, source_view))
                return [
                    MolecularDetection(
                        frame_index=frame_index,
                        bbox_xyxy=(1, 1, 5, 4),
                        confidence=0.7,
                        model_name="expanded-model.pt",
                        checkpoint_path=str(checkpoint_path),
                        source_view=source_view,
                    )
                ]

        def fake_expanded_builder(series):
            expanded_stack = SimpleNamespace(
                frames=expanded_frames,
                metadata=STMSequenceMetadata(pixels_x=6, pixels_y=5),
                padding_ltrb=(1, 1, 1, 2),
                frame_origins_xy=np.zeros((series.frame_count, 2), dtype=np.float64),
            )
            series.expanded_aligned_stack = expanded_stack
            return expanded_stack

        self.window = MolTrackMainWindow(
            expanded_aligned_builder=fake_expanded_builder,
            yolo_model_discovery=lambda: [SimpleNamespace(name="expanded-model.pt", path=checkpoint)],
            yolo_detector=FakeYoloDetector(),
        )
        raw_detections = MolecularDetectionSet(frame_count=2)
        raw_detections.set_detections(
            0,
            [MolecularDetection(frame_index=0, bbox_xyxy=(0, 0, 2, 2), confidence=0.9, source_view="raw")],
            source_view="raw",
            frame_shape=(4, 4),
        )
        settings = MolTrackRegistrationSettings()
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.arange(2 * 4 * 4, dtype=np.float32).reshape(2, 4, 4),
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=4),
            registration_results=MolTrackRegistrationResultSet(
                settings=settings,
                results_by_frame={
                    frame_index: MolTrackRegistrationFrameResult(
                        frame_index=frame_index,
                        shift_xy=(0.0, 0.0),
                        method="identity",
                    )
                    for frame_index in range(2)
                },
            ),
            molecular_detections=raw_detections,
        )
        self.window.set_image_series(series)
        self.window.cmb_registration_view_mode.setCurrentText("Show expanded aligned")
        self.__class__._app.processEvents()

        self.window.btn_yolo_detect_all_frames.click()
        self.process_events_until(
            lambda: series.molecular_detections.detection_count == 3
            and "2 detections" in self.window.statusBar().currentMessage(),
            timeout_s=2.0,
        )

        self.assertEqual(len(calls), 2)
        for frame_index, call in enumerate(calls):
            np.testing.assert_array_equal(call[0], expanded_frames[frame_index])
            self.assertEqual(call[1], frame_index)
            self.assertEqual(call[2], checkpoint)
            self.assertEqual(call[3], "expanded_aligned")
            self.assertEqual(
                len(series.molecular_detections.get_detections(frame_index, source_view="expanded_aligned")),
                1,
            )
        self.assertEqual(len(series.molecular_detections.get_detections(0, source_view="raw")), 1)
        np.testing.assert_array_equal(self.window.viewer.viewer.image_item.image, expanded_frames[0])
        self.assertEqual(self.window.viewer.visible_molecular_detection_count(), 1)
        self.assertIn("current 1", self.window.lbl_yolo_status.text())
        self.assertIn("series 3", self.window.lbl_yolo_status.text())

    def test_yolo_clear_current_removes_only_active_frame_and_view_detections(self) -> None:
        self.window = MolTrackMainWindow(yolo_model_discovery=lambda: [])
        frames = np.arange(2 * 4 * 4, dtype=np.float32).reshape(2, 4, 4)
        detections = MolecularDetectionSet(frame_count=2)
        detections.set_detections(
            0,
            [MolecularDetection(frame_index=0, bbox_xyxy=(0, 0, 2, 2), confidence=0.9, source_view="raw")],
            source_view="raw",
            frame_shape=(4, 4),
        )
        detections.set_detections(
            0,
            [
                MolecularDetection(
                    frame_index=0,
                    bbox_xyxy=(1, 1, 3, 3),
                    confidence=0.8,
                    source_view="expanded_aligned",
                )
            ],
            source_view="expanded_aligned",
            frame_shape=(4, 4),
        )
        detections.set_detections(
            1,
            [MolecularDetection(frame_index=1, bbox_xyxy=(2, 2, 4, 4), confidence=0.7, source_view="raw")],
            source_view="raw",
            frame_shape=(4, 4),
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames.copy(),
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=4),
            molecular_detections=detections,
        )
        self.window.set_image_series(series)

        self.assertEqual(self.window.viewer.visible_molecular_detection_count(), 1)
        self.assertTrue(self.window.btn_yolo_clear_current.isEnabled())

        self.window.btn_yolo_clear_current.click()
        self.__class__._app.processEvents()

        self.assertEqual(series.molecular_detections.get_detections(0, source_view="raw"), [])
        self.assertEqual(len(series.molecular_detections.get_detections(0, source_view="expanded_aligned")), 1)
        self.assertEqual(len(series.molecular_detections.get_detections(1, source_view="raw")), 1)
        self.assertEqual(self.window.viewer.visible_molecular_detection_count(), 0)
        self.assertFalse(self.window.btn_yolo_clear_current.isEnabled())
        self.assertIn("current 0", self.window.lbl_yolo_status.text())
        self.assertIn("series 2", self.window.lbl_yolo_status.text())

    def test_remove_current_frame_after_yolo_clears_detections_and_requires_rerun(self) -> None:
        checkpoint = Path("model-a.pt")

        class FakeYoloDetector:
            def detect_frame(
                self,
                frame,
                *,
                frame_index,
                checkpoint_path,
                confidence_threshold,
                iou_threshold,
                source_view,
            ):
                return [
                    MolecularDetection(
                        frame_index=frame_index,
                        bbox_xyxy=(0, 0, 2, 2),
                        confidence=0.8,
                        model_name="model-a.pt",
                        checkpoint_path=str(checkpoint_path),
                        source_view=source_view,
                    )
                ]

        self.window = MolTrackMainWindow(
            yolo_model_discovery=lambda: [SimpleNamespace(name="model-a.pt", path=checkpoint)],
            yolo_detector=FakeYoloDetector(),
        )
        frames = np.arange(3 * 4 * 4, dtype=np.float32).reshape(3, 4, 4)
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames.copy(),
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=4),
        )
        self.window.set_image_series(series)
        self.window.slider_frame.setValue(1)
        self.__class__._app.processEvents()

        self.window.btn_yolo_detect_current.click()
        self.__class__._app.processEvents()

        self.assertIsNotNone(series.molecular_detections)
        self.assertEqual(self.window.viewer.visible_molecular_detection_count(), 1)
        self.assertIn("series 1", self.window.lbl_yolo_status.text())

        self.window.btn_remove_current_frame.click()
        self.__class__._app.processEvents()

        self.assertIsNone(series.molecular_detections)
        self.assertEqual(series.frame_count, 2)
        self.assertEqual(series.active_frame_index, 1)
        self.assertEqual(self.window.viewer.visible_molecular_detection_count(), 0)
        self.assertIn("current 0", self.window.lbl_yolo_status.text())
        self.assertIn("series 0", self.window.lbl_yolo_status.text())
        self.assertTrue(self.window.btn_yolo_detect_current.isEnabled())

    def test_yolo_status_tracks_active_registration_view(self) -> None:
        expanded_frames = np.arange(2 * 5 * 6, dtype=np.float32).reshape(2, 5, 6)

        def fake_expanded_builder(series):
            expanded_stack = SimpleNamespace(
                frames=expanded_frames,
                metadata=STMSequenceMetadata(pixels_x=6, pixels_y=5),
                padding_ltrb=(1, 1, 1, 2),
                frame_origins_xy=np.zeros((series.frame_count, 2), dtype=np.float64),
            )
            series.expanded_aligned_stack = expanded_stack
            return expanded_stack

        self.window = MolTrackMainWindow(
            expanded_aligned_builder=fake_expanded_builder,
            yolo_model_discovery=lambda: [],
        )
        detections = MolecularDetectionSet(frame_count=2)
        detections.set_detections(
            0,
            [MolecularDetection(frame_index=0, bbox_xyxy=(0, 0, 2, 2), confidence=0.9, source_view="raw")],
            source_view="raw",
            frame_shape=(4, 4),
        )
        settings = MolTrackRegistrationSettings()
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.arange(2 * 4 * 4, dtype=np.float32).reshape(2, 4, 4),
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=4),
            registration_results=MolTrackRegistrationResultSet(
                settings=settings,
                results_by_frame={
                    frame_index: MolTrackRegistrationFrameResult(
                        frame_index=frame_index,
                        shift_xy=(0.0, 0.0),
                        method="identity",
                    )
                    for frame_index in range(2)
                },
            ),
            molecular_detections=detections,
        )
        self.window.set_image_series(series)

        self.assertIn("current 1", self.window.lbl_yolo_status.text())
        self.assertTrue(self.window.btn_yolo_clear_current.isEnabled())

        self.window.cmb_registration_view_mode.setCurrentText("Show expanded aligned")
        self.__class__._app.processEvents()

        self.assertIn("current 0", self.window.lbl_yolo_status.text())
        self.assertFalse(self.window.btn_yolo_clear_current.isEnabled())

        self.window.cmb_registration_view_mode.setCurrentText("Show raw")
        self.__class__._app.processEvents()

        self.assertIn("current 1", self.window.lbl_yolo_status.text())
        self.assertTrue(self.window.btn_yolo_clear_current.isEnabled())

    def test_yolo_detect_current_frame_uses_expanded_aligned_active_view(self) -> None:
        calls = []
        checkpoint = Path("expanded-model.pt")
        expanded_frames = (np.arange(2 * 5 * 6, dtype=np.float32).reshape(2, 5, 6) + 100.0)

        class FakeYoloDetector:
            def detect_frame(
                self,
                frame,
                *,
                frame_index,
                checkpoint_path,
                confidence_threshold,
                iou_threshold,
                source_view,
            ):
                calls.append((np.asarray(frame).copy(), frame_index, checkpoint_path, source_view))
                return [
                    MolecularDetection(
                        frame_index=frame_index,
                        bbox_xyxy=(1, 1, 5, 4),
                        confidence=0.75,
                        model_name="expanded-model.pt",
                        checkpoint_path=str(checkpoint_path),
                        source_view=source_view,
                    )
                ]

        def fake_expanded_builder(series):
            expanded_stack = SimpleNamespace(
                frames=expanded_frames,
                metadata=STMSequenceMetadata(pixels_x=6, pixels_y=5),
                padding_ltrb=(1, 1, 1, 2),
                frame_origins_xy=np.zeros((series.frame_count, 2), dtype=np.float64),
            )
            series.expanded_aligned_stack = expanded_stack
            return expanded_stack

        self.window = MolTrackMainWindow(
            expanded_aligned_builder=fake_expanded_builder,
            yolo_model_discovery=lambda: [SimpleNamespace(name="expanded-model.pt", path=checkpoint)],
            yolo_detector=FakeYoloDetector(),
        )
        raw_frames = np.arange(2 * 4 * 4, dtype=np.float32).reshape(2, 4, 4)
        raw_detections = MolecularDetectionSet(frame_count=2)
        raw_detections.set_detections(
            1,
            [MolecularDetection(frame_index=1, bbox_xyxy=(0, 0, 2, 2), confidence=0.9, source_view="raw")],
            source_view="raw",
            frame_shape=(4, 4),
        )
        settings = MolTrackRegistrationSettings()
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=raw_frames.copy(),
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=4),
            registration_results=MolTrackRegistrationResultSet(
                settings=settings,
                results_by_frame={
                    frame_index: MolTrackRegistrationFrameResult(
                        frame_index=frame_index,
                        shift_xy=(0.0, 0.0),
                        method="identity",
                    )
                    for frame_index in range(2)
                },
            ),
            molecular_detections=raw_detections,
        )
        self.window.set_image_series(series)
        self.window.slider_frame.setValue(1)
        self.window.cmb_registration_view_mode.setCurrentText("Show expanded aligned")
        self.__class__._app.processEvents()

        self.window.btn_yolo_detect_current.click()
        self.__class__._app.processEvents()

        self.assertEqual(len(calls), 1)
        np.testing.assert_array_equal(calls[0][0], expanded_frames[1])
        self.assertEqual(calls[0][1], 1)
        self.assertEqual(calls[0][2], checkpoint)
        self.assertEqual(calls[0][3], "expanded_aligned")
        self.assertEqual(len(series.molecular_detections.get_detections(1, source_view="raw")), 1)
        self.assertEqual(len(series.molecular_detections.get_detections(1, source_view="expanded_aligned")), 1)
        np.testing.assert_array_equal(self.window.viewer.viewer.image_item.image, expanded_frames[1])
        self.assertEqual(self.window.viewer.visible_molecular_detection_count(), 1)
        self.assertIn("current 1", self.window.lbl_yolo_status.text())
        self.assertIn("series 2", self.window.lbl_yolo_status.text())

    def test_yolo_detect_current_frame_reports_inference_errors(self) -> None:
        class FailingYoloDetector:
            def detect_frame(self, *args, **kwargs):
                raise RuntimeError("GPU inference failed")

        self.window = MolTrackMainWindow(
            yolo_model_discovery=lambda: [SimpleNamespace(name="model-a.pt", path=Path("model-a.pt"))],
            yolo_detector=FailingYoloDetector(),
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.arange(2 * 4 * 4, dtype=np.float32).reshape(2, 4, 4),
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=4),
        )
        self.window.set_image_series(series)

        with patch.object(QMessageBox, "critical", return_value=QMessageBox.StandardButton.Ok) as critical:
            self.window.btn_yolo_detect_current.click()
            self.__class__._app.processEvents()

        critical.assert_called_once()
        _parent, title, message = critical.call_args.args
        self.assertEqual(title, "YOLO detection error")
        self.assertIn("GPU inference failed", message)
        self.assertIsNone(series.molecular_detections)
        self.assertIn("YOLO detection failed", self.window.statusBar().currentMessage())

    def test_yolo_detect_all_frames_reports_inference_errors_without_partial_results(self) -> None:
        class FailingYoloDetector:
            def detect_frame(
                self,
                frame,
                *,
                frame_index,
                checkpoint_path,
                confidence_threshold,
                iou_threshold,
                source_view,
            ):
                if frame_index == 1:
                    raise RuntimeError("GPU inference failed on frame 2")
                return [
                    MolecularDetection(
                        frame_index=frame_index,
                        bbox_xyxy=(0, 0, 2, 2),
                        confidence=0.8,
                        model_name="model-a.pt",
                        checkpoint_path=str(checkpoint_path),
                        source_view=source_view,
                    )
                ]

        self.window = MolTrackMainWindow(
            yolo_model_discovery=lambda: [SimpleNamespace(name="model-a.pt", path=Path("model-a.pt"))],
            yolo_detector=FailingYoloDetector(),
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.arange(3 * 4 * 4, dtype=np.float32).reshape(3, 4, 4),
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=4),
        )
        self.window.set_image_series(series)

        with patch.object(QMessageBox, "critical", return_value=QMessageBox.StandardButton.Ok) as critical:
            self.window.btn_yolo_detect_all_frames.click()
            self.process_events_until(
                lambda: critical.called and "YOLO detection failed" in self.window.statusBar().currentMessage(),
                timeout_s=2.0,
            )

        critical.assert_called_once()
        _parent, title, message = critical.call_args.args
        self.assertEqual(title, "YOLO detection error")
        self.assertIn("GPU inference failed on frame 2", message)
        self.assertIsNone(series.molecular_detections)
        self.assertTrue(self.window.btn_yolo_detect_all_frames.isEnabled())
        self.assertIn("YOLO detection failed", self.window.statusBar().currentMessage())

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
            self.assertFalse(self.window.action_open_stm.isEnabled())
            self.assertFalse(self.window.action_open_stm_reverse.isEnabled())
            self.assertFalse(self.window.action_open_state.isEnabled())
            self.assertFalse(self.window.action_save_state.isEnabled())
            self.assertFalse(self.window.action_save_state_as.isEnabled())
            self.process_events_until(lambda: series.registration_results is not None and self.window.btn_run_registration.isEnabled())

        self.assertIn("show", events)
        self.assertIn("close", events)
        runner_events = [event for event in events if isinstance(event, tuple) and event[0] == "runner_thread"]
        self.assertEqual(len(runner_events), 1)
        self.assertNotEqual(runner_events[0][1], main_thread_id)
        self.assertLess(events.index("show"), events.index(runner_events[0]))
        self.assertLess(events.index(runner_events[0]), events.index("close"))
        self.assertTrue(self.window.btn_run_registration.isEnabled())
        self.assertTrue(self.window.action_open_stm.isEnabled())
        self.assertTrue(self.window.action_open_stm_reverse.isEnabled())
        self.assertTrue(self.window.action_open_state.isEnabled())
        self.assertTrue(self.window.action_save_state.isEnabled())
        self.assertTrue(self.window.action_save_state_as.isEnabled())
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
