import csv
from contextlib import ExitStack
import os
import time
import tempfile
import threading
from types import SimpleNamespace
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np

from nanotrack.analysis import compute_particle_metrics

try:
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QApplication, QMessageBox
except ImportError:  # pragma: no cover - optional outside the target GUI env
    Qt = None
    QApplication = None
    QMessageBox = None

from nanotrack.core import (
    AnnotationSource,
    BBoxXYXY,
    EdgeAnnotationSource,
    EdgeFrameAnnotation,
    EdgeMetrics,
    EdgeTrack,
    FrameVisibility,
    ParticleMetrics,
    ParticleTrack,
    PolygonROI,
    RegistrationFrameResult,
    RegistrationResultSet,
    RegistrationSettings,
    STMSequence,
    STMSequenceMetadata,
    TrackFrameAnnotation,
    YoloDetection,
)
from nanotrack.io import load_mpp_sequence
from nanotrack.edges import DexiNedRunOutput
from nanotrack.mask_trackers import MaskTrackerKind, MaskTrackerRunOutput
from nanotrack.sam2 import Sam2RunOutput
from nanotrack.trackers import PointTrackerRunOutput

if QApplication is not None:
    from nanotrack.ui.main_window import NanoTrackMainWindow
else:  # pragma: no cover - optional outside the target GUI env
    NanoTrackMainWindow = None


REPO_ROOT = Path(__file__).resolve().parents[2]
SAMPLE_MPP = REPO_ROOT / "data" / "MOVIE_3.MPP"


class _FakeCancelableEdgeBackend:
    def __init__(self) -> None:
        self.started = threading.Event()
        self.canceled = threading.Event()
        self.cancel_called = False
        self.run_input = None

    def run(self, run_input):
        self.run_input = run_input
        self.started.set()
        self.canceled.wait(timeout=5.0)
        raise RuntimeError("fake backend stopped")

    def cancel(self) -> None:
        self.cancel_called = True
        self.canceled.set()


class _FakeCancelableMaskTrackerBackend:
    def __init__(self) -> None:
        self.started = threading.Event()
        self.canceled = threading.Event()
        self.cancel_called = False
        self.run_inputs = []

    def run(self, run_input):
        self.run_inputs.append(run_input)
        self.started.set()
        self.canceled.wait(timeout=5.0)
        raise RuntimeError("fake mask tracker stopped")

    def cancel(self) -> None:
        self.cancel_called = True
        self.canceled.set()


@unittest.skipUnless(QApplication is not None, "PyQt6 is required for NanoTrack GUI tests")
class NanoTrackMainWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self._messagebox_patcher = None
        if QMessageBox is not None:
            self._messagebox_patcher = patch.multiple(
                QMessageBox,
                critical=lambda *args, **kwargs: QMessageBox.StandardButton.Ok,
                warning=lambda *args, **kwargs: QMessageBox.StandardButton.Ok,
                information=lambda *args, **kwargs: QMessageBox.StandardButton.Ok,
            )
            self._messagebox_patcher.start()
        self.window = NanoTrackMainWindow()

    def tearDown(self) -> None:
        if getattr(self.window, "_bm3d_preview_dialog", None) is not None:
            self.window._bm3d_preview_dialog.close()
        if getattr(self.window, "_edge_preview_dialog", None) is not None:
            self.window._edge_preview_dialog.close()
        if getattr(self.window, "_registration_preview_dialog", None) is not None:
            self.window._registration_preview_dialog.close()
        if getattr(self.window, "_registration_results_dialog", None) is not None:
            self.window._registration_results_dialog.close()
        if getattr(self.window, "_edge_results_dialog", None) is not None:
            self.window._edge_results_dialog.close()
        if getattr(self.window, "_dexined_progress_dialog", None) is not None:
            self.window._dexined_progress_dialog.close()
        if getattr(self.window, "_point_tracker_progress_dialog", None) is not None:
            self.window._point_tracker_progress_dialog.close()
        if getattr(self.window, "_results_dialog", None) is not None:
            self.window._results_dialog.close()
        if getattr(self.window, "_sam2_progress_dialog", None) is not None:
            self.window._sam2_progress_dialog.close()
        self.window.close()
        self.window.deleteLater()
        self.__class__._app.processEvents()
        if self._messagebox_patcher is not None:
            self._messagebox_patcher.stop()

    def _wait_until(self, predicate, *, attempts: int = 250) -> None:
        for _ in range(attempts):
            self.__class__._app.processEvents()
            if predicate():
                return
            time.sleep(0.01)

    def _edge_probability_output(
        self,
        frame_count: int,
        frame_shape: tuple[int, int],
        *,
        model_name: str = "ddn",
        checkpoint_name: str = "DDN_M36_BSDS.pth",
        start_row: int = 10,
        start_col: int = 8,
    ) -> DexiNedRunOutput:
        edge_prob = np.zeros((frame_count, *frame_shape), dtype=np.float32)
        for frame_offset in range(frame_count):
            row = start_row + frame_offset
            col = start_col + frame_offset
            edge_prob[frame_offset, row : row + 3, col : col + 13] = 0.78 + 0.01 * frame_offset
        return DexiNedRunOutput(
            edge_prob=edge_prob,
            edge_binary=edge_prob >= 0.5,
            model_name=model_name,
            checkpoint_name=checkpoint_name,
        )

    def _mask_tracker_output(
        self,
        tracker_kind: MaskTrackerKind,
        *,
        track_id: int,
        frame_index_offset: int,
        frame_count: int,
        frame_shape: tuple[int, int],
        row: int,
        col: int,
        visible_count: int = 2,
    ) -> MaskTrackerRunOutput:
        masks = np.zeros((frame_count, *frame_shape), dtype=bool)
        visible_mask = np.zeros((frame_count,), dtype=bool)
        mask_bboxes = np.zeros((frame_count, 4), dtype=np.float32)
        for local_index in range(min(visible_count, frame_count)):
            local_row = row + local_index
            local_col = col + local_index
            masks[local_index, local_row : local_row + 6, local_col : local_col + 7] = True
            visible_mask[local_index] = True
            mask_bboxes[local_index] = np.asarray(
                [float(local_col), float(local_row), float(local_col + 7), float(local_row + 6)],
                dtype=np.float32,
            )
        mask_areas = np.asarray([float(np.count_nonzero(mask)) for mask in masks], dtype=np.float32)
        mask_scores = visible_mask.astype(np.float32) * 0.91
        mask_component_counts = visible_mask.astype(np.int32)
        return MaskTrackerRunOutput(
            tracker_kind=tracker_kind,
            track_id=track_id,
            frame_index_offset=frame_index_offset,
            masks=masks,
            visible_mask=visible_mask,
            mask_areas=mask_areas,
            mask_bboxes_xyxy=mask_bboxes,
            mask_scores=mask_scores,
            mask_component_counts=mask_component_counts,
            model_name=tracker_kind.value,
            model_variant="test-variant",
            checkpoint_name=f"{tracker_kind.value}.pt",
        )

    def _set_existing_edge_track(
        self,
        sequence: STMSequence,
        *,
        frame_indices: list[int],
        polygon: PolygonROI | None = None,
    ) -> EdgeTrack:
        if polygon is None:
            polygon = PolygonROI(
                np.asarray([[6.0, 8.0], [24.0, 8.0], [24.0, 24.0], [8.0, 26.0]], dtype=np.float64)
            )
        annotations: dict[int, EdgeFrameAnnotation] = {}
        seed_polyline = np.asarray([[8.0, 12.0], [14.0, 12.5], [20.0, 13.0]], dtype=np.float64)
        edge_mask = np.zeros(sequence.frame_shape, dtype=bool)
        edge_mask[10:13, 8:21] = True
        for frame_index in frame_indices:
            polyline = seed_polyline + np.asarray([float(frame_index), 0.5 * float(frame_index)], dtype=np.float64)
            annotations[int(frame_index)] = EdgeFrameAnnotation(
                frame_index=int(frame_index),
                polyline=polyline,
                edge_mask=edge_mask,
                source=EdgeAnnotationSource.DEXINED,
                metrics=self.window._compute_edge_metrics(polyline),
            )
        track = EdgeTrack(
            edge_track_id=1,
            seed_frame_index=int(frame_indices[0]),
            polygon_roi=polygon,
            seed_polyline=annotations[int(frame_indices[0])].polyline,
            annotations=annotations,
            label="Edge 1",
        )
        self.window.set_edge_tracks([track], selected_track_id=track.edge_track_id)
        return track

    def _snapshot_edge_track(self, track: EdgeTrack) -> dict[str, object]:
        annotations: dict[int, dict[str, object]] = {}
        for frame_index, annotation in track.annotations.items():
            annotations[int(frame_index)] = {
                "polyline": None
                if annotation.polyline is None
                else np.asarray(annotation.polyline, dtype=np.float64).copy(),
                "edge_mask": None if annotation.edge_mask is None else np.asarray(annotation.edge_mask, dtype=bool).copy(),
                "source": annotation.source,
                "visibility": annotation.visibility,
            }
        return {
            "edge_track_id": track.edge_track_id,
            "seed_frame_index": track.seed_frame_index,
            "polygon_roi": track.polygon_roi.as_array().copy(),
            "seed_polyline": np.asarray(track.seed_polyline, dtype=np.float64).copy(),
            "frame_indices": list(track.frame_indices),
            "annotations": annotations,
        }

    def _assert_edge_track_matches_snapshot(self, track: EdgeTrack, snapshot: dict[str, object]) -> None:
        self.assertEqual(track.edge_track_id, snapshot["edge_track_id"])
        self.assertEqual(track.seed_frame_index, snapshot["seed_frame_index"])
        self.assertEqual(track.frame_indices, snapshot["frame_indices"])
        np.testing.assert_array_equal(track.polygon_roi.as_array(), snapshot["polygon_roi"])
        np.testing.assert_array_equal(track.seed_polyline, snapshot["seed_polyline"])
        expected_annotations = snapshot["annotations"]
        assert isinstance(expected_annotations, dict)
        self.assertEqual(set(track.annotations), set(expected_annotations))
        for frame_index, expected in expected_annotations.items():
            annotation = track.get_annotation(frame_index)
            self.assertIsNotNone(annotation)
            assert annotation is not None
            self.assertEqual(annotation.source, expected["source"])
            self.assertEqual(annotation.visibility, expected["visibility"])
            expected_polyline = expected["polyline"]
            if expected_polyline is None:
                self.assertIsNone(annotation.polyline)
            else:
                np.testing.assert_array_equal(annotation.polyline, expected_polyline)
            expected_edge_mask = expected["edge_mask"]
            if expected_edge_mask is None:
                self.assertIsNone(annotation.edge_mask)
            else:
                np.testing.assert_array_equal(annotation.edge_mask, expected_edge_mask)

    def _cancel_active_edge_operation(self, fake_backend: _FakeCancelableEdgeBackend) -> None:
        self._wait_until(lambda: fake_backend.started.is_set())
        self.assertIsNotNone(self.window._dexined_progress_dialog)
        self.assertTrue(self.window._dexined_progress_dialog.isVisible())

        self.window._on_edge_detector_cancel_requested()
        self._wait_until(lambda: self.window._dexined_thread is None and self.window._dexined_progress_dialog is None)

        self.assertTrue(fake_backend.cancel_called)
        self.assertFalse(self.window._is_preprocessing)
        self.assertIn("operation canceled", self.window.statusBar().currentMessage().lower())

    def _cancel_active_mask_tracker_operation(self, fake_backend: _FakeCancelableMaskTrackerBackend) -> None:
        self._wait_until(lambda: fake_backend.started.is_set())
        self.assertIsNotNone(self.window._sam2_progress_dialog)
        self.assertTrue(self.window._sam2_progress_dialog.isVisible())

        self.window._on_mask_tracker_cancel_requested()
        self._wait_until(lambda: self.window._sam2_thread is None and self.window._sam2_progress_dialog is None)

        self.assertTrue(fake_backend.cancel_called)
        self.assertFalse(self.window._is_tracking)
        self.assertIn("operation canceled", self.window.statusBar().currentMessage().lower())

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
        self.assertEqual(self.window.track_list_panel.btn_run_selected.text(), "Run for Selected")
        self.assertEqual(self.window.track_list_panel.btn_run_all.text(), "Run for All Seeds")
        self.assertEqual(self.window.track_list_panel.current_mask_tracker_kind(), MaskTrackerKind.SAM2)
        self.assertEqual(self.window.edge_track_list_panel.list_tracks.count(), 0)
        self.assertEqual(self.window.edge_track_list_panel.lbl_summary.text(), "0 edge tracks")
        self.assertTrue(self.window.bbox_tools_panel.btn_place.isEnabled())
        self.assertTrue(self.window.chk_exclude_frame.isEnabled())
        self.assertFalse(self.window.chk_exclude_frame.isChecked())
        self.assertFalse(self.window.bbox_tools_panel.btn_add_seed.isEnabled())
        self.assertFalse(self.window.bbox_tools_panel.btn_clear.isEnabled())
        self.assertFalse(self.window.bbox_tools_panel.btn_load_track_bbox.isEnabled())
        self.assertFalse(self.window.bbox_tools_panel.btn_save_correction.isEnabled())
        self.assertFalse(self.window.bbox_tools_panel.btn_resume_track.isEnabled())
        self.assertEqual(self.window.bbox_tools_panel.btn_resume_track.text(), "Resume")
        self.assertEqual(self.window.bbox_tools_panel.lbl_bbox.text(), "No bbox on current frame")
        self.assertEqual(self.window.yolo_panel.lbl_frame.text(), f"Frame: 1 / {sequence.frame_count}")
        self.assertGreaterEqual(self.window.yolo_panel.cmb_model.count(), 0)
        self.assertEqual(
            self.window.yolo_panel.btn_detect_current.isEnabled(),
            self.window.yolo_panel.cmb_model.count() > 0,
        )
        self.assertEqual(
            self.window.yolo_panel.btn_detect_all.isEnabled(),
            self.window.yolo_panel.cmb_model.count() > 0,
        )
        self.assertFalse(self.window.yolo_panel.btn_select_all_current.isEnabled())
        self.assertFalse(self.window.yolo_panel.btn_deselect_all_current.isEnabled())
        self.assertFalse(self.window.yolo_panel.btn_select_all_global.isEnabled())
        self.assertFalse(self.window.yolo_panel.btn_deselect_all_global.isEnabled())
        self.assertFalse(self.window.yolo_panel.btn_scale_current.isEnabled())
        self.assertFalse(self.window.yolo_panel.btn_scale_all.isEnabled())
        self.assertFalse(self.window.yolo_panel.btn_load_selected_bbox.isEnabled())
        self.assertFalse(self.window.yolo_panel.btn_save_edited_bbox.isEnabled())
        self.assertFalse(self.window.yolo_panel.btn_convert_current.isEnabled())
        self.assertFalse(self.window.yolo_panel.btn_convert_all.isEnabled())
        self.assertFalse(self.window.yolo_panel.btn_clear.isEnabled())
        self.assertTrue(self.window.action_preview_registration.isEnabled())
        self.assertTrue(self.window.action_run_registration.isEnabled())
        self.assertFalse(self.window.action_open_registration_results.isEnabled())
        self.assertFalse(self.window.action_show_aligned_registration.isEnabled())
        self.assertFalse(self.window.action_show_aligned_registration.isChecked())
        self.assertFalse(self.window.action_show_expanded_aligned_registration.isEnabled())
        self.assertFalse(self.window.action_show_expanded_aligned_registration.isChecked())
        self.assertTrue(self.window.polygon_tools_panel.btn_draw.isEnabled())
        self.assertFalse(self.window.polygon_tools_panel.btn_finish.isEnabled())
        self.assertFalse(self.window.polygon_tools_panel.btn_clear.isEnabled())
        self.assertFalse(self.window.polygon_tools_panel.btn_preview.isEnabled())
        self.assertFalse(self.window.polygon_tools_panel.btn_run_sequence.isEnabled())
        self.assertFalse(self.window.polygon_tools_panel.btn_load_edge.isEnabled())
        self.assertFalse(self.window.polygon_tools_panel.btn_save_edge.isEnabled())
        self.assertFalse(self.window.polygon_tools_panel.btn_resume_edge.isEnabled())
        self.assertFalse(self.window.polygon_tools_panel.btn_redetect_edge.isEnabled())
        self.assertFalse(self.window.polygon_tools_panel.btn_redetect_edge_range.isEnabled())
        self.assertFalse(self.window.polygon_tools_panel.btn_hybrid.isEnabled())
        self.assertTrue(self.window.polygon_tools_panel.cmb_polyline_method.isEnabled())
        self.assertEqual(self.window.polygon_tools_panel.edge_polyline_method(), "graph")
        self.assertEqual(self.window.polygon_tools_panel.lbl_polygon.text(), "No polygon ROI on current frame")
        self.assertTrue(self.window.preprocessing_panel.btn_preview.isEnabled())
        self.assertTrue(self.window.preprocessing_panel.btn_apply_all.isEnabled())
        self.assertTrue(self.window.preprocessing_panel.btn_repair_preview.isEnabled())
        self.assertTrue(self.window.preprocessing_panel.btn_repair_apply_all.isEnabled())
        self.assertFalse(self.window.preprocessing_panel.chk_show_denoised.isEnabled())
        self.assertEqual(self.window.preprocessing_panel.lbl_status.text(), "No preview generated for current frame")

    @patch("nanotrack.ui.main_window.QFileDialog.getOpenFileNames", return_value=(["/tmp/reversed.mpp"], "STM files"))
    def test_open_reverse_uses_reversed_frame_order_loader(self, _get_open_file_names) -> None:
        with patch.object(self.window, "load_sequence_from_path") as load_sequence_mock:
            self.window.action_open_mpp_reverse.trigger()

        load_sequence_mock.assert_called_once_with("/tmp/reversed.mpp", reverse_frame_order=True)
        self.assertEqual(self.window.action_open_mpp_reverse.text(), "Open STM Reverse...")
        self.assertIn("STP/S94", self.window.action_open_mpp_reverse.toolTip())

    @patch("nanotrack.ui.main_window.QFileDialog.getOpenFileNames", return_value=(["/tmp/movie.mpp"], "STM files"))
    def test_open_stm_accepts_single_mpp_file(self, get_open_file_names_mock) -> None:
        with patch.object(self.window, "load_sequence_from_path") as load_sequence_mock:
            self.window.action_open_mpp.trigger()

        load_sequence_mock.assert_called_once_with("/tmp/movie.mpp", reverse_frame_order=False)
        filter_text = get_open_file_names_mock.call_args.args[3]
        self.assertIn("*.stp", filter_text)
        self.assertIn("*.s94", filter_text)
        self.assertEqual(self.window.action_open_mpp.text(), "Open STM...")

    @patch(
        "nanotrack.ui.main_window.QFileDialog.getOpenFileNames",
        return_value=(["/tmp/frame_001.stp", "/tmp/frame_002.s94", "/tmp/frame_003.stp"], "STM files"),
    )
    def test_open_reverse_accepts_stp_s94_frame_series(self, get_open_file_names_mock) -> None:
        with patch.object(self.window, "load_sequence_from_path") as load_sequence_mock:
            self.window.action_open_mpp_reverse.trigger()

        load_sequence_mock.assert_called_once_with(
            ["/tmp/frame_001.stp", "/tmp/frame_002.s94", "/tmp/frame_003.stp"],
            reverse_frame_order=True,
        )
        dialog_args = get_open_file_names_mock.call_args.args
        self.assertIn("reverse", dialog_args[1].lower())
        self.assertIn("*.stp", dialog_args[3])
        self.assertIn("*.s94", dialog_args[3])

    @patch(
        "nanotrack.ui.main_window.QFileDialog.getOpenFileNames",
        return_value=(["/tmp/frame_001.stp", "/tmp/frame_002.s94"], "STM files"),
    )
    def test_open_stm_accepts_stp_s94_frame_series(self, _get_open_file_names) -> None:
        with patch.object(self.window, "load_sequence_from_path") as load_sequence_mock:
            self.window.action_open_mpp.trigger()

        load_sequence_mock.assert_called_once_with(
            ["/tmp/frame_001.stp", "/tmp/frame_002.s94"],
            reverse_frame_order=False,
        )

    def test_load_sequence_from_path_uses_common_stm_loader(self) -> None:
        sequence = STMSequence(
            source_path="/tmp/frame_001_series_2_frames",
            raw_frames=np.zeros((2, 8, 8), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=8, pixels_y=8),
        )

        with (
            patch("nanotrack.ui.main_window.load_stm_sequence", return_value=sequence) as load_sequence_mock,
            patch.object(self.window, "set_sequence") as set_sequence_mock,
        ):
            self.window.load_sequence_from_path(["/tmp/frame_001.stp", "/tmp/frame_002.s94"], reverse_frame_order=True)

        load_sequence_mock.assert_called_once_with(
            ["/tmp/frame_001.stp", "/tmp/frame_002.s94"],
            reverse_frame_order=True,
        )
        set_sequence_mock.assert_called_once_with(sequence)

    def test_slider_navigation_updates_active_frame_index(self) -> None:
        sequence = load_mpp_sequence(str(SAMPLE_MPP))
        self.window.set_sequence(sequence)

        self.window.slider_frame.setValue(2)

        self.assertEqual(sequence.active_frame_index, 2)
        self.assertEqual(self.window.spin_frame.value(), 3)
        self.assertEqual(self.window.lbl_frame.text(), f"Frame: 3 / {sequence.frame_count}")

    def test_yolo_detect_current_creates_detection_proposals_for_active_frame(self) -> None:
        sequence = load_mpp_sequence(str(SAMPLE_MPP))
        self.window.set_sequence(sequence)
        if self.window.yolo_panel.cmb_model.count() == 0:
            self.skipTest("No local YOLO models available for the GUI test.")

        model_name = self.window.yolo_panel.current_model_name()
        self.assertIsNotNone(model_name)

        with patch.object(
            self.window._yolo_runtime,
            "predict_frame",
            return_value=[SimpleNamespace(bbox=BBoxXYXY(5.0, 6.0, 15.0, 18.0), confidence=0.82)],
        ) as predict_mock:
            self.window._on_yolo_detect_current_requested()

        predict_mock.assert_called_once()
        detection_set = self.window.current_yolo_detection_set()
        self.assertIsNotNone(detection_set)
        assert detection_set is not None
        self.assertEqual(detection_set.model_name, model_name)
        self.assertEqual(detection_set.source_path, sequence.source_path)
        detections = detection_set.get_detections(sequence.active_frame_index)
        self.assertEqual(len(detections), 1)
        detection = detections[0]
        self.assertEqual(detection.bbox, BBoxXYXY(5.0, 6.0, 15.0, 18.0))
        self.assertAlmostEqual(detection.confidence, 0.82, places=6)
        self.assertTrue(detection.selected)
        self.assertEqual(detection.model_name, model_name)
        self.assertEqual(
            self.window.yolo_panel.lbl_detections.text(),
            "Detections: current 1 (selected 1) | all 1 (selected 1)",
        )
        self.assertEqual(len(self.window.viewer.viewer._overlay_items), 2)
        self.assertTrue(self.window.yolo_panel.btn_detect_current.isEnabled())
        self.assertTrue(self.window.yolo_panel.btn_detect_all.isEnabled())
        self.assertTrue(self.window.yolo_panel.btn_select_all_current.isEnabled())
        self.assertTrue(self.window.yolo_panel.btn_deselect_all_current.isEnabled())
        self.assertTrue(self.window.yolo_panel.btn_select_all_global.isEnabled())
        self.assertTrue(self.window.yolo_panel.btn_deselect_all_global.isEnabled())
        self.assertTrue(self.window.yolo_panel.btn_scale_current.isEnabled())
        self.assertTrue(self.window.yolo_panel.btn_scale_all.isEnabled())
        self.assertTrue(self.window.yolo_panel.btn_load_selected_bbox.isEnabled())
        self.assertFalse(self.window.yolo_panel.btn_save_edited_bbox.isEnabled())
        self.assertTrue(self.window.yolo_panel.btn_convert_current.isEnabled())
        self.assertTrue(self.window.yolo_panel.btn_convert_all.isEnabled())
        self.assertTrue(self.window.yolo_panel.btn_clear.isEnabled())

    def test_yolo_single_detection_selection_toggles_selected_flag(self) -> None:
        sequence = load_mpp_sequence(str(SAMPLE_MPP))
        self.window.set_sequence(sequence)
        if self.window.yolo_panel.cmb_model.count() == 0:
            self.skipTest("No local YOLO models available for the GUI test.")

        model_name = self.window.yolo_panel.current_model_name()
        self.assertIsNotNone(model_name)

        with patch.object(
            self.window._yolo_runtime,
            "predict_frame",
            return_value=[SimpleNamespace(bbox=BBoxXYXY(5.0, 6.0, 15.0, 18.0), confidence=0.82)],
        ):
            self.window._on_yolo_detect_current_requested()

        detection_set = self.window.current_yolo_detection_set()
        self.assertIsNotNone(detection_set)
        assert detection_set is not None
        self.assertEqual(detection_set.selected_detection_count(), 1)

        self.window._on_yolo_detection_clicked(0)

        detections = detection_set.get_detections(sequence.active_frame_index)
        self.assertEqual(len(detections), 1)
        self.assertFalse(detections[0].selected)
        self.assertEqual(detection_set.selected_detection_count(), 0)
        self.assertEqual(
            self.window.yolo_panel.lbl_detections.text(),
            "Detections: current 1 (selected 0) | all 1 (selected 0)",
        )
        self.assertEqual(len(self.window.viewer.viewer._overlay_items), 2)

        self.window._on_yolo_detection_clicked(0)

        self.assertTrue(detections[0].selected)
        self.assertEqual(detection_set.selected_detection_count(), 1)
        self.assertEqual(
            self.window.yolo_panel.lbl_detections.text(),
            "Detections: current 1 (selected 1) | all 1 (selected 1)",
        )

    def test_yolo_select_all_and_deselect_all_current_affect_active_frame_only(self) -> None:
        sequence = STMSequence(
            source_path="/tmp/yolo_select_current.mpp",
            raw_frames=np.zeros((2, 8, 8), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=8, pixels_y=8),
        )
        self.window.set_sequence(sequence)
        if self.window.yolo_panel.cmb_model.count() == 0:
            self.skipTest("No local YOLO models available for the GUI test.")

        model_name = self.window.yolo_panel.current_model_name()
        self.assertIsNotNone(model_name)
        self.window._replace_yolo_detections(
            model_name=str(model_name),
            detections_by_frame={
                0: [
                    YoloDetection(
                        frame_index=0,
                        bbox=BBoxXYXY(1.0, 1.0, 3.0, 3.0),
                        confidence=0.9,
                        selected=True,
                        model_name=str(model_name),
                    ),
                    YoloDetection(
                        frame_index=0,
                        bbox=BBoxXYXY(4.0, 4.0, 6.0, 6.0),
                        confidence=0.8,
                        selected=True,
                        model_name=str(model_name),
                    ),
                ],
                1: [
                    YoloDetection(
                        frame_index=1,
                        bbox=BBoxXYXY(2.0, 2.0, 5.0, 5.0),
                        confidence=0.7,
                        selected=True,
                        model_name=str(model_name),
                    )
                ],
            },
        )
        detection_set = self.window.current_yolo_detection_set()
        self.assertIsNotNone(detection_set)
        assert detection_set is not None
        self.assertTrue(self.window.yolo_panel.btn_select_all_current.isEnabled())
        self.assertTrue(self.window.yolo_panel.btn_deselect_all_current.isEnabled())
        self.assertTrue(self.window.yolo_panel.btn_select_all_global.isEnabled())
        self.assertTrue(self.window.yolo_panel.btn_deselect_all_global.isEnabled())
        self.assertTrue(self.window.yolo_panel.btn_scale_current.isEnabled())
        self.assertTrue(self.window.yolo_panel.btn_scale_all.isEnabled())
        self.assertFalse(self.window.yolo_panel.btn_load_selected_bbox.isEnabled())
        self.assertFalse(self.window.yolo_panel.btn_save_edited_bbox.isEnabled())
        self.assertEqual(
            self.window.yolo_panel.lbl_detections.text(),
            "Detections: current 2 (selected 2) | all 3 (selected 3)",
        )

        self.window._on_yolo_deselect_all_current_requested()

        self.assertEqual(detection_set.selected_detection_count(0), 0)
        self.assertEqual(detection_set.selected_detection_count(1), 1)
        self.assertEqual(detection_set.selected_detection_count(), 1)
        self.assertEqual(
            self.window.yolo_panel.lbl_detections.text(),
            "Detections: current 2 (selected 0) | all 3 (selected 1)",
        )

        self.window._on_yolo_select_all_current_requested()

        self.assertEqual(detection_set.selected_detection_count(0), 2)
        self.assertEqual(detection_set.selected_detection_count(), 3)
        self.assertEqual(
            self.window.yolo_panel.lbl_detections.text(),
            "Detections: current 2 (selected 2) | all 3 (selected 3)",
        )

        self.window.slider_frame.setValue(1)
        self.__class__._app.processEvents()
        self.assertTrue(self.window.yolo_panel.btn_select_all_current.isEnabled())
        self.assertTrue(self.window.yolo_panel.btn_deselect_all_current.isEnabled())
        self.assertEqual(
            self.window.yolo_panel.lbl_detections.text(),
            "Detections: current 1 (selected 1) | all 3 (selected 3)",
        )

    def test_yolo_select_all_and_deselect_all_global_affect_all_frames(self) -> None:
        sequence = STMSequence(
            source_path="/tmp/yolo_select_global.mpp",
            raw_frames=np.zeros((2, 8, 8), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=8, pixels_y=8),
        )
        self.window.set_sequence(sequence)
        if self.window.yolo_panel.cmb_model.count() == 0:
            self.skipTest("No local YOLO models available for the GUI test.")

        model_name = self.window.yolo_panel.current_model_name()
        self.assertIsNotNone(model_name)
        self.window._replace_yolo_detections(
            model_name=str(model_name),
            detections_by_frame={
                0: [
                    YoloDetection(
                        frame_index=0,
                        bbox=BBoxXYXY(1.0, 1.0, 3.0, 3.0),
                        confidence=0.9,
                        selected=True,
                        model_name=str(model_name),
                    ),
                    YoloDetection(
                        frame_index=0,
                        bbox=BBoxXYXY(4.0, 4.0, 6.0, 6.0),
                        confidence=0.8,
                        selected=False,
                        model_name=str(model_name),
                    ),
                ],
                1: [
                    YoloDetection(
                        frame_index=1,
                        bbox=BBoxXYXY(2.0, 2.0, 5.0, 5.0),
                        confidence=0.7,
                        selected=True,
                        model_name=str(model_name),
                    )
                ],
            },
        )
        detection_set = self.window.current_yolo_detection_set()
        self.assertIsNotNone(detection_set)
        assert detection_set is not None
        self.assertTrue(self.window.yolo_panel.btn_select_all_global.isEnabled())
        self.assertTrue(self.window.yolo_panel.btn_deselect_all_global.isEnabled())
        self.assertEqual(
            self.window.yolo_panel.lbl_detections.text(),
            "Detections: current 2 (selected 1) | all 3 (selected 2)",
        )

        self.window._on_yolo_deselect_all_global_requested()

        self.assertEqual(detection_set.selected_detection_count(0), 0)
        self.assertEqual(detection_set.selected_detection_count(1), 0)
        self.assertEqual(detection_set.selected_detection_count(), 0)
        self.assertEqual(
            self.window.yolo_panel.lbl_detections.text(),
            "Detections: current 2 (selected 0) | all 3 (selected 0)",
        )

        self.window._on_yolo_select_all_global_requested()

        self.assertEqual(detection_set.selected_detection_count(0), 2)
        self.assertEqual(detection_set.selected_detection_count(1), 1)
        self.assertEqual(detection_set.selected_detection_count(), 3)
        self.assertEqual(
            self.window.yolo_panel.lbl_detections.text(),
            "Detections: current 2 (selected 2) | all 3 (selected 3)",
        )

        self.window.slider_frame.setValue(1)
        self.__class__._app.processEvents()
        self.assertTrue(self.window.yolo_panel.btn_select_all_global.isEnabled())
        self.assertTrue(self.window.yolo_panel.btn_deselect_all_global.isEnabled())
        self.assertEqual(
            self.window.yolo_panel.lbl_detections.text(),
            "Detections: current 1 (selected 1) | all 3 (selected 3)",
        )
        self.assertTrue(self.window.yolo_panel.btn_load_selected_bbox.isEnabled())
        self.assertFalse(self.window.yolo_panel.btn_save_edited_bbox.isEnabled())
        self.assertTrue(self.window.yolo_panel.btn_convert_current.isEnabled())

    def test_yolo_can_load_selected_bbox_and_save_manual_edit(self) -> None:
        sequence = STMSequence(
            source_path="/tmp/yolo_edit_bbox.mpp",
            raw_frames=np.zeros((2, 8, 10), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=10, pixels_y=8),
        )
        self.window.set_sequence(sequence)
        if self.window.yolo_panel.cmb_model.count() == 0:
            self.skipTest("No local YOLO models available for the GUI test.")

        model_name = self.window.yolo_panel.current_model_name()
        self.assertIsNotNone(model_name)
        original_bbox = BBoxXYXY(2.0, 1.0, 6.0, 5.0)
        self.window._replace_yolo_detections(
            model_name=str(model_name),
            detections_by_frame={
                0: [
                    YoloDetection(
                        frame_index=0,
                        bbox=original_bbox,
                        confidence=0.9,
                        selected=True,
                        model_name=str(model_name),
                    )
                ],
                1: [
                    YoloDetection(
                        frame_index=1,
                        bbox=BBoxXYXY(1.0, 1.0, 4.0, 4.0),
                        confidence=0.8,
                        selected=True,
                        model_name=str(model_name),
                    )
                ],
            },
        )

        self.assertTrue(self.window.yolo_panel.btn_load_selected_bbox.isEnabled())
        self.assertFalse(self.window.yolo_panel.btn_save_edited_bbox.isEnabled())

        self.window.yolo_panel.btn_load_selected_bbox.click()

        self.assertEqual(self.window.current_draft_bbox(), original_bbox)
        self.assertEqual(self.window.viewer.current_bbox(), original_bbox)
        self.assertTrue(self.window.yolo_panel.btn_save_edited_bbox.isEnabled())
        self.assertFalse(self.window.yolo_panel.btn_convert_current.isEnabled())

        corrected_bbox = BBoxXYXY(3.0, 2.0, 7.0, 6.0)
        self.window.viewer._commit_bbox(corrected_bbox)
        self.window.yolo_panel.btn_save_edited_bbox.click()

        detection_set = self.window.current_yolo_detection_set()
        self.assertIsNotNone(detection_set)
        assert detection_set is not None
        self.assertEqual(detection_set.get_detections(0)[0].bbox, corrected_bbox)
        self.assertIsNone(self.window.current_draft_bbox())
        self.assertIsNone(self.window.viewer.current_bbox())
        self.assertFalse(self.window.yolo_panel.btn_save_edited_bbox.isEnabled())
        self.assertTrue(self.window.yolo_panel.btn_load_selected_bbox.isEnabled())
        self.assertTrue(self.window.yolo_panel.btn_convert_current.isEnabled())

    def test_yolo_convert_selected_current_creates_seed_tracks_and_removes_converted_detections(self) -> None:
        sequence = STMSequence(
            source_path="/tmp/yolo_convert_current.mpp",
            raw_frames=np.zeros((2, 8, 10), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=10, pixels_y=8),
        )
        self.window.set_sequence(sequence)
        if self.window.yolo_panel.cmb_model.count() == 0:
            self.skipTest("No local YOLO models available for the GUI test.")

        model_name = self.window.yolo_panel.current_model_name()
        self.assertIsNotNone(model_name)
        self.window._replace_yolo_detections(
            model_name=str(model_name),
            detections_by_frame={
                0: [
                    YoloDetection(
                        frame_index=0,
                        bbox=BBoxXYXY(1.0, 1.0, 3.0, 3.0),
                        confidence=0.9,
                        selected=True,
                        model_name=str(model_name),
                    ),
                    YoloDetection(
                        frame_index=0,
                        bbox=BBoxXYXY(4.0, 4.0, 6.0, 6.0),
                        confidence=0.8,
                        selected=False,
                        model_name=str(model_name),
                    ),
                ],
                1: [
                    YoloDetection(
                        frame_index=1,
                        bbox=BBoxXYXY(2.0, 2.0, 5.0, 5.0),
                        confidence=0.7,
                        selected=True,
                        model_name=str(model_name),
                    )
                ],
            },
        )

        self.assertTrue(self.window.yolo_panel.btn_convert_current.isEnabled())
        self.assertTrue(self.window.yolo_panel.btn_convert_all.isEnabled())

        self.window.yolo_panel.btn_convert_current.click()

        tracks = self.window.current_tracks()
        self.assertEqual(len(tracks), 1)
        self.assertEqual(tracks[0].track_id, 1)
        self.assertEqual(tracks[0].seed_frame_index, 0)
        self.assertEqual(tracks[0].seed_bbox, BBoxXYXY(1.0, 1.0, 3.0, 3.0))
        self.assertEqual(self.window.current_selected_track_id(), 1)

        detection_set = self.window.current_yolo_detection_set()
        self.assertIsNotNone(detection_set)
        assert detection_set is not None
        self.assertEqual(len(detection_set.get_detections(0)), 1)
        self.assertEqual(detection_set.get_detections(0)[0].bbox, BBoxXYXY(4.0, 4.0, 6.0, 6.0))
        self.assertEqual(len(detection_set.get_detections(1)), 1)
        self.assertEqual(
            self.window.yolo_panel.lbl_detections.text(),
            "Detections: current 1 (selected 0) | all 2 (selected 1)",
        )
        self.assertFalse(self.window.yolo_panel.btn_convert_current.isEnabled())
        self.assertTrue(self.window.yolo_panel.btn_convert_all.isEnabled())
        self.assertTrue(self.window.yolo_panel.btn_clear.isEnabled())

    def test_yolo_convert_selected_all_creates_seed_tracks_and_removes_selected_detections_across_frames(self) -> None:
        sequence = STMSequence(
            source_path="/tmp/yolo_convert_all.mpp",
            raw_frames=np.zeros((3, 8, 10), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=10, pixels_y=8),
        )
        self.window.set_sequence(sequence)
        if self.window.yolo_panel.cmb_model.count() == 0:
            self.skipTest("No local YOLO models available for the GUI test.")

        model_name = self.window.yolo_panel.current_model_name()
        self.assertIsNotNone(model_name)
        self.window._replace_yolo_detections(
            model_name=str(model_name),
            detections_by_frame={
                0: [
                    YoloDetection(
                        frame_index=0,
                        bbox=BBoxXYXY(1.0, 1.0, 3.0, 3.0),
                        confidence=0.9,
                        selected=True,
                        model_name=str(model_name),
                    ),
                    YoloDetection(
                        frame_index=0,
                        bbox=BBoxXYXY(4.0, 4.0, 6.0, 6.0),
                        confidence=0.8,
                        selected=False,
                        model_name=str(model_name),
                    ),
                ],
                1: [
                    YoloDetection(
                        frame_index=1,
                        bbox=BBoxXYXY(2.0, 2.0, 5.0, 5.0),
                        confidence=0.7,
                        selected=True,
                        model_name=str(model_name),
                    )
                ],
                2: [
                    YoloDetection(
                        frame_index=2,
                        bbox=BBoxXYXY(3.0, 1.0, 7.0, 4.0),
                        confidence=0.6,
                        selected=True,
                        model_name=str(model_name),
                    )
                ],
            },
        )

        self.assertTrue(self.window.yolo_panel.btn_convert_current.isEnabled())
        self.assertTrue(self.window.yolo_panel.btn_convert_all.isEnabled())

        self.window.yolo_panel.btn_convert_all.click()

        tracks = self.window.current_tracks()
        self.assertEqual(len(tracks), 3)
        self.assertEqual([track.track_id for track in tracks], [1, 2, 3])
        self.assertEqual([track.seed_frame_index for track in tracks], [0, 1, 2])
        self.assertEqual(tracks[0].seed_bbox, BBoxXYXY(1.0, 1.0, 3.0, 3.0))
        self.assertEqual(tracks[1].seed_bbox, BBoxXYXY(2.0, 2.0, 5.0, 5.0))
        self.assertEqual(tracks[2].seed_bbox, BBoxXYXY(3.0, 1.0, 7.0, 4.0))
        self.assertEqual(self.window.current_selected_track_id(), 3)

        detection_set = self.window.current_yolo_detection_set()
        self.assertIsNotNone(detection_set)
        assert detection_set is not None
        self.assertEqual(len(detection_set.get_detections(0)), 1)
        self.assertEqual(detection_set.get_detections(0)[0].bbox, BBoxXYXY(4.0, 4.0, 6.0, 6.0))
        self.assertEqual(len(detection_set.get_detections(1)), 0)
        self.assertEqual(len(detection_set.get_detections(2)), 0)
        self.assertEqual(
            self.window.yolo_panel.lbl_detections.text(),
            "Detections: current 1 (selected 0) | all 1 (selected 0)",
        )
        self.assertFalse(self.window.yolo_panel.btn_convert_current.isEnabled())
        self.assertFalse(self.window.yolo_panel.btn_convert_all.isEnabled())
        self.assertTrue(self.window.yolo_panel.btn_clear.isEnabled())

    def test_yolo_clear_detections_removes_proposals_without_touching_created_tracks(self) -> None:
        sequence = STMSequence(
            source_path="/tmp/yolo_clear_detections.mpp",
            raw_frames=np.zeros((2, 8, 10), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=10, pixels_y=8),
        )
        self.window.set_sequence(sequence)
        if self.window.yolo_panel.cmb_model.count() == 0:
            self.skipTest("No local YOLO models available for the GUI test.")

        model_name = self.window.yolo_panel.current_model_name()
        self.assertIsNotNone(model_name)
        self.window._replace_yolo_detections(
            model_name=str(model_name),
            detections_by_frame={
                0: [
                    YoloDetection(
                        frame_index=0,
                        bbox=BBoxXYXY(1.0, 1.0, 3.0, 3.0),
                        confidence=0.9,
                        selected=True,
                        model_name=str(model_name),
                    ),
                ],
                1: [
                    YoloDetection(
                        frame_index=1,
                        bbox=BBoxXYXY(2.0, 2.0, 5.0, 5.0),
                        confidence=0.7,
                        selected=False,
                        model_name=str(model_name),
                    )
                ],
            },
        )
        self.window.yolo_panel.btn_convert_current.click()

        tracks = self.window.current_tracks()
        self.assertEqual(len(tracks), 1)
        self.assertEqual(tracks[0].seed_bbox, BBoxXYXY(1.0, 1.0, 3.0, 3.0))
        self.assertIsNotNone(self.window.current_yolo_detection_set())
        self.assertTrue(self.window.yolo_panel.btn_clear.isEnabled())

        self.window.yolo_panel.btn_clear.click()

        self.assertIsNone(self.window.current_yolo_detection_set())
        tracks_after_clear = self.window.current_tracks()
        self.assertEqual(len(tracks_after_clear), 1)
        self.assertEqual(tracks_after_clear[0].seed_bbox, BBoxXYXY(1.0, 1.0, 3.0, 3.0))
        self.assertEqual(self.window.yolo_panel.lbl_detections.text(), "Detections: current 0 (selected 0) | all 0 (selected 0)")
        self.assertFalse(self.window.yolo_panel.btn_clear.isEnabled())

    def test_yolo_scale_bboxes_current_affects_only_active_frame(self) -> None:
        sequence = STMSequence(
            source_path="/tmp/yolo_scale_current.mpp",
            raw_frames=np.zeros((2, 8, 10), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=10, pixels_y=8),
        )
        self.window.set_sequence(sequence)
        if self.window.yolo_panel.cmb_model.count() == 0:
            self.skipTest("No local YOLO models available for the GUI test.")

        model_name = self.window.yolo_panel.current_model_name()
        self.assertIsNotNone(model_name)
        self.window._replace_yolo_detections(
            model_name=str(model_name),
            detections_by_frame={
                0: [
                    YoloDetection(
                        frame_index=0,
                        bbox=BBoxXYXY(2.0, 2.0, 6.0, 6.0),
                        confidence=0.9,
                        selected=True,
                        model_name=str(model_name),
                    )
                ],
                1: [
                    YoloDetection(
                        frame_index=1,
                        bbox=BBoxXYXY(1.0, 1.0, 5.0, 5.0),
                        confidence=0.8,
                        selected=True,
                        model_name=str(model_name),
                    )
                ],
            },
        )
        detection_set = self.window.current_yolo_detection_set()
        self.assertIsNotNone(detection_set)
        assert detection_set is not None

        self.window.yolo_panel.sp_scale_multiplier.setValue(0.50)
        self.window._on_yolo_scale_current_requested()

        self.assertEqual(detection_set.get_detections(0)[0].bbox, BBoxXYXY(3.0, 3.0, 5.0, 5.0))
        self.assertEqual(detection_set.get_detections(1)[0].bbox, BBoxXYXY(1.0, 1.0, 5.0, 5.0))
        self.assertEqual(
            self.window.yolo_panel.lbl_detections.text(),
            "Detections: current 1 (selected 1) | all 2 (selected 2)",
        )

    def test_yolo_scale_bboxes_all_affects_all_frames_and_clips_to_bounds(self) -> None:
        sequence = STMSequence(
            source_path="/tmp/yolo_scale_all.mpp",
            raw_frames=np.zeros((2, 8, 8), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=8, pixels_y=8),
        )
        self.window.set_sequence(sequence)
        if self.window.yolo_panel.cmb_model.count() == 0:
            self.skipTest("No local YOLO models available for the GUI test.")

        model_name = self.window.yolo_panel.current_model_name()
        self.assertIsNotNone(model_name)
        self.window._replace_yolo_detections(
            model_name=str(model_name),
            detections_by_frame={
                0: [
                    YoloDetection(
                        frame_index=0,
                        bbox=BBoxXYXY(2.0, 2.0, 4.0, 4.0),
                        confidence=0.9,
                        selected=True,
                        model_name=str(model_name),
                    )
                ],
                1: [
                    YoloDetection(
                        frame_index=1,
                        bbox=BBoxXYXY(1.0, 1.0, 3.0, 3.0),
                        confidence=0.8,
                        selected=False,
                        model_name=str(model_name),
                    )
                ],
            },
        )
        detection_set = self.window.current_yolo_detection_set()
        self.assertIsNotNone(detection_set)
        assert detection_set is not None

        self.window.yolo_panel.sp_scale_multiplier.setValue(3.00)
        self.window._on_yolo_scale_all_requested()

        self.assertEqual(detection_set.get_detections(0)[0].bbox, BBoxXYXY(0.0, 0.0, 6.0, 6.0))
        self.assertEqual(detection_set.get_detections(1)[0].bbox, BBoxXYXY(0.0, 0.0, 5.0, 5.0))
        self.assertFalse(detection_set.get_detections(1)[0].selected)
        self.window.slider_frame.setValue(1)
        self.__class__._app.processEvents()
        self.assertEqual(
            self.window.yolo_panel.lbl_detections.text(),
            "Detections: current 1 (selected 0) | all 2 (selected 1)",
        )

    def test_yolo_detect_all_creates_detection_proposals_for_included_frames(self) -> None:
        sequence = STMSequence(
            source_path="/tmp/yolo_detect_all.mpp",
            raw_frames=np.zeros((4, 8, 8), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=8, pixels_y=8),
        )
        self.window.set_sequence(sequence)
        if self.window.yolo_panel.cmb_model.count() == 0:
            self.skipTest("No local YOLO models available for the GUI test.")

        sequence.set_frame_excluded(2, True)
        self.window._show_current_frame(preserve_zoom=True)
        model_name = self.window.yolo_panel.current_model_name()
        self.assertIsNotNone(model_name)

        detections_per_call = {
            0: [SimpleNamespace(bbox=BBoxXYXY(1.0, 1.0, 3.0, 3.0), confidence=0.9)],
            1: [SimpleNamespace(bbox=BBoxXYXY(2.0, 2.0, 4.0, 4.0), confidence=0.8)],
            3: [SimpleNamespace(bbox=BBoxXYXY(4.0, 4.0, 6.0, 6.0), confidence=0.7)],
        }

        def _predict_frame(frame, **_kwargs):
            frame = np.asarray(frame)
            frame_index = int(frame[0, 0])
            return detections_per_call[frame_index]

        sequence.raw_frames[0, ...] = 0.0
        sequence.raw_frames[1, ...] = 1.0
        sequence.raw_frames[2, ...] = 2.0
        sequence.raw_frames[3, ...] = 3.0

        with patch.object(self.window._yolo_runtime, "predict_frame", side_effect=_predict_frame) as predict_mock:
            self.window._on_yolo_detect_all_requested()

        self.assertEqual(predict_mock.call_count, 3)
        detection_set = self.window.current_yolo_detection_set()
        self.assertIsNotNone(detection_set)
        assert detection_set is not None
        self.assertEqual(detection_set.model_name, model_name)
        self.assertEqual(detection_set.frame_indices, [0, 1, 3])
        self.assertEqual(detection_set.detection_count, 3)
        self.assertEqual(len(detection_set.get_detections(2)), 0)
        self.assertEqual(self.window.yolo_panel.lbl_detections.text(), "Detections: current 1 (selected 1) | all 3 (selected 3)")
        self.assertEqual(len(self.window.viewer.viewer._overlay_items), 2)
        self.assertTrue(self.window.yolo_panel.btn_detect_current.isEnabled())
        self.assertTrue(self.window.yolo_panel.btn_detect_all.isEnabled())
        self.assertTrue(self.window.yolo_panel.btn_scale_current.isEnabled())
        self.assertTrue(self.window.yolo_panel.btn_scale_all.isEnabled())
        self.assertTrue(self.window.yolo_panel.btn_convert_current.isEnabled())
        self.assertTrue(self.window.yolo_panel.btn_convert_all.isEnabled())

        self.window.slider_frame.setValue(1)
        self.__class__._app.processEvents()
        self.assertEqual(len(self.window.viewer.viewer._overlay_items), 2)

        self.window.slider_frame.setValue(2)
        self.__class__._app.processEvents()
        self.assertEqual(len(self.window.viewer.viewer._overlay_items), 0)

    def test_excluding_current_frame_removes_it_from_analysis_state(self) -> None:
        sequence = STMSequence(
            source_path="/tmp/excluded_frame.mpp",
            raw_frames=np.zeros((3, 8, 8), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=8, pixels_y=8),
        )
        self.window.set_sequence(sequence)

        particle_track_keep = ParticleTrack(
            track_id=1,
            seed_frame_index=0,
            seed_bbox=BBoxXYXY(1.0, 1.0, 4.0, 4.0),
        )
        particle_track_keep.add_annotation(
            TrackFrameAnnotation(
                frame_index=1,
                bbox=BBoxXYXY(2.0, 2.0, 5.0, 5.0),
                source=AnnotationSource.MANUAL,
            )
        )
        particle_track_drop = ParticleTrack(
            track_id=2,
            seed_frame_index=1,
            seed_bbox=BBoxXYXY(1.0, 1.0, 3.0, 3.0),
        )

        polygon = PolygonROI(np.asarray([[1.0, 1.0], [6.0, 1.0], [6.0, 6.0], [1.0, 6.0]], dtype=np.float64))
        edge_track_keep = EdgeTrack(
            edge_track_id=1,
            seed_frame_index=0,
            polygon_roi=polygon,
            seed_polyline=np.asarray([[1.0, 2.0], [6.0, 2.0]], dtype=np.float64),
        )
        edge_track_keep.add_annotation(
            EdgeFrameAnnotation(
                frame_index=1,
                polyline=np.asarray([[1.5, 2.5], [6.5, 2.5]], dtype=np.float64),
                source=EdgeAnnotationSource.MANUAL,
            )
        )
        edge_track_drop = EdgeTrack(
            edge_track_id=2,
            seed_frame_index=1,
            polygon_roi=polygon,
            seed_polyline=np.asarray([[1.0, 3.0], [6.0, 3.0]], dtype=np.float64),
        )

        self.window.set_tracks([particle_track_keep, particle_track_drop], selected_track_id=1)
        self.window.set_edge_tracks([edge_track_keep, edge_track_drop], selected_track_id=1)

        self.window.slider_frame.setValue(1)
        self.__class__._app.processEvents()
        self.window.viewer.set_bbox(BBoxXYXY(0.5, 0.5, 3.5, 3.5))
        self.window.viewer._commit_polygon(polygon)
        self.window.viewer.set_edge_polyline(np.asarray([[1.0, 4.0], [6.0, 4.0]], dtype=np.float64))

        self.window.chk_exclude_frame.setChecked(True)
        self.__class__._app.processEvents()

        self.assertTrue(sequence.is_frame_excluded(1))
        self.assertTrue(self.window.chk_exclude_frame.isChecked())
        self.assertIn("excluded", self.window.lbl_frame.text().lower())
        self.assertIsNone(self.window.current_draft_bbox())
        self.assertIsNone(self.window.current_draft_polygon_roi())
        self.assertIsNone(self.window.current_draft_edge_polyline())

        remaining_track_ids = [track.track_id for track in self.window.current_tracks()]
        self.assertEqual(remaining_track_ids, [1])
        self.assertEqual(self.window.current_tracks()[0].frame_indices, [0])

        remaining_edge_track_ids = [track.edge_track_id for track in self.window.current_edge_tracks()]
        self.assertEqual(remaining_edge_track_ids, [1])
        self.assertEqual(self.window.current_edge_tracks()[0].frame_indices, [0])

        self.window.chk_exclude_frame.setChecked(False)
        self.__class__._app.processEvents()
        self.assertFalse(sequence.is_frame_excluded(1))

    def test_hide_excluded_frames_skips_hidden_frames_in_navigation(self) -> None:
        sequence = STMSequence(
            source_path="/tmp/hide_excluded_navigation.mpp",
            raw_frames=np.zeros((5, 8, 8), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=8, pixels_y=8),
        )
        sequence.set_frame_excluded(1, True)
        sequence.set_frame_excluded(3, True)
        self.window.set_sequence(sequence)

        self.window.chk_hide_excluded_frames.setChecked(True)
        self.__class__._app.processEvents()

        self.window._on_next_frame()
        self.assertEqual(sequence.active_frame_index, 2)

        self.window.slider_frame.setValue(3)
        self.__class__._app.processEvents()
        self.assertEqual(sequence.active_frame_index, 4)

        self.window._on_prev_frame()
        self.assertEqual(sequence.active_frame_index, 2)

        self.window.spin_frame.setValue(2)
        self.__class__._app.processEvents()
        self.assertEqual(sequence.active_frame_index, 0)
        self.assertFalse(self.window.btn_prev.isEnabled())

    def test_excluding_current_frame_moves_to_visible_frame_when_hidden(self) -> None:
        sequence = STMSequence(
            source_path="/tmp/exclude_hidden_current.mpp",
            raw_frames=np.zeros((3, 8, 8), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=8, pixels_y=8),
        )
        self.window.set_sequence(sequence)
        self.window.chk_hide_excluded_frames.setChecked(True)
        self.window._set_active_frame(1)

        self.window.chk_exclude_frame.setChecked(True)
        self.__class__._app.processEvents()

        self.assertTrue(sequence.is_frame_excluded(1))
        self.assertTrue(self.window.chk_hide_excluded_frames.isChecked())
        self.assertEqual(sequence.active_frame_index, 2)
        self.assertFalse(self.window.chk_exclude_frame.isChecked())

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

    def test_set_edge_tracks_populates_edge_track_list(self) -> None:
        sequence = load_mpp_sequence(str(SAMPLE_MPP))
        self.window.set_sequence(sequence)

        polygon = PolygonROI(np.asarray([[1.0, 1.0], [6.0, 1.0], [6.0, 6.0], [1.0, 6.0]], dtype=np.float64))
        track1 = EdgeTrack(
            edge_track_id=1,
            seed_frame_index=0,
            polygon_roi=polygon,
            seed_polyline=np.asarray([[1.0, 2.0], [6.0, 2.0]], dtype=np.float64),
        )
        track2 = EdgeTrack(
            edge_track_id=2,
            seed_frame_index=3,
            polygon_roi=polygon,
            seed_polyline=np.asarray([[1.0, 3.0], [6.0, 3.0]], dtype=np.float64),
            label="Step-B",
        )

        self.window.set_edge_tracks([track1, track2], selected_track_id=2)

        self.assertEqual(len(self.window.current_edge_tracks()), 2)
        self.assertEqual(self.window.edge_track_list_panel.list_tracks.count(), 2)
        self.assertEqual(self.window.edge_track_list_panel.lbl_summary.text(), "2 edge tracks")
        self.assertIn("Edge 1", self.window.edge_track_list_panel.list_tracks.item(0).text())
        self.assertIn("Step-B", self.window.edge_track_list_panel.list_tracks.item(1).text())
        self.assertEqual(self.window.edge_track_list_panel.current_track_id(), 2)

    def test_long_filename_is_truncated_in_metadata_panel(self) -> None:
        sequence = STMSequence(
            source_path="/tmp/12345678901234567890.mpp",
            raw_frames=np.zeros((2, 2, 2), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=2, pixels_y=2),
        )

        self.window.set_sequence(sequence)

        self.assertEqual(self.window.metadata_panel.lbl_file.text(), "123456789012...")
        self.assertEqual(self.window.metadata_panel.lbl_file.toolTip(), "12345678901234567890.mpp")

    def test_results_action_opens_dialog_and_syncs_track_selection(self) -> None:
        sequence = STMSequence(
            source_path="/tmp/results_main.mpp",
            raw_frames=np.zeros((5, 8, 8), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=8, pixels_y=8),
        )
        self.window.set_sequence(sequence)

        track1 = ParticleTrack(track_id=1, seed_frame_index=0, seed_bbox=BBoxXYXY(1.0, 1.0, 4.0, 4.0))
        track1.add_annotation(
            TrackFrameAnnotation(
                frame_index=1,
                bbox=BBoxXYXY(2.0, 2.0, 5.0, 5.0),
                metrics=ParticleMetrics(area_px=12.0, perimeter_px=16.0, intensity_sum=24.0, intensity_mean=2.0, intensity_max=3.0),
            )
        )
        track2 = ParticleTrack(track_id=2, seed_frame_index=3, seed_bbox=BBoxXYXY(2.0, 2.0, 6.0, 6.0))
        track2.add_annotation(
            TrackFrameAnnotation(
                frame_index=4,
                bbox=BBoxXYXY(3.0, 3.0, 7.0, 7.0),
                metrics=ParticleMetrics(area_px=21.0, perimeter_px=24.0, intensity_sum=55.0, intensity_mean=2.62, intensity_max=5.0),
            )
        )
        self.window.set_tracks([track1, track2], selected_track_id=1)

        self.assertTrue(self.window.action_open_results.isEnabled())

        self.window.action_open_results.trigger()
        self.__class__._app.processEvents()

        dialog = self.window.current_results_dialog()
        self.assertIsNotNone(dialog)
        self.assertTrue(dialog.isVisible())
        self.assertEqual(dialog.current_track_id(), 1)

        dialog.cmb_tracks.setCurrentIndex(2)
        self.__class__._app.processEvents()

        self.assertEqual(self.window.current_selected_track_id(), 2)
        self.assertEqual(sequence.active_frame_index, 3)

    def test_edge_results_action_opens_dialog_and_syncs_edge_track_selection(self) -> None:
        sequence = STMSequence(
            source_path="/tmp/edge_results_main.mpp",
            raw_frames=np.zeros((5, 8, 8), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=8, pixels_y=8, size_nm_x=80.0, size_nm_y=40.0),
        )
        self.window.set_sequence(sequence)

        polygon = PolygonROI(np.asarray([[1.0, 1.0], [6.0, 1.0], [6.0, 6.0], [1.0, 6.0]], dtype=np.float64))
        track1 = EdgeTrack(
            edge_track_id=1,
            seed_frame_index=0,
            polygon_roi=polygon,
            seed_polyline=np.asarray([[1.0, 2.0], [6.0, 2.0]], dtype=np.float64),
        )
        track1.add_annotation(
            EdgeFrameAnnotation(
                frame_index=1,
                polyline=np.asarray([[1.0, 2.0], [6.0, 2.0]], dtype=np.float64),
                metrics=EdgeMetrics(
                    length_px=5.0,
                    length_nm=50.0,
                    roughness_rms_px=0.2,
                    roughness_rms_nm=2.0,
                    mean_curvature=0.05,
                    max_curvature=0.08,
                    waviness_amplitude_px=0.4,
                    waviness_amplitude_nm=4.0,
                ),
            )
        )
        track2 = EdgeTrack(
            edge_track_id=2,
            seed_frame_index=3,
            polygon_roi=polygon,
            seed_polyline=np.asarray([[1.0, 3.0], [6.0, 3.0]], dtype=np.float64),
        )
        track2.add_annotation(
            EdgeFrameAnnotation(
                frame_index=4,
                polyline=np.asarray([[1.0, 3.0], [6.0, 3.0]], dtype=np.float64),
                metrics=EdgeMetrics(
                    length_px=6.0,
                    length_nm=60.0,
                    roughness_rms_px=0.3,
                    roughness_rms_nm=3.0,
                    mean_curvature=0.06,
                    max_curvature=0.10,
                    waviness_amplitude_px=0.5,
                    waviness_amplitude_nm=5.0,
                ),
            )
        )

        self.window.set_edge_tracks([track1, track2], selected_track_id=1)

        self.assertTrue(self.window.action_open_edge_results.isEnabled())

        self.window.action_open_edge_results.trigger()
        self.__class__._app.processEvents()

        dialog = self.window.current_edge_results_dialog()
        self.assertIsNotNone(dialog)
        self.assertTrue(dialog.isVisible())
        self.assertEqual(dialog.current_track_id(), 1)

        dialog.cmb_tracks.setCurrentIndex(2)
        self.__class__._app.processEvents()

        self.assertEqual(self.window.current_selected_edge_track_id(), 2)
        self.assertEqual(self.window.edge_track_list_panel.current_track_id(), 2)
        self.assertEqual(sequence.active_frame_index, 3)

    def test_edge_track_list_selection_syncs_results_dialog_and_frame(self) -> None:
        sequence = STMSequence(
            source_path="/tmp/edge_sidebar_sync.mpp",
            raw_frames=np.zeros((5, 8, 8), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=8, pixels_y=8, size_nm_x=80.0, size_nm_y=40.0),
        )
        self.window.set_sequence(sequence)

        polygon = PolygonROI(np.asarray([[1.0, 1.0], [6.0, 1.0], [6.0, 6.0], [1.0, 6.0]], dtype=np.float64))
        track1 = EdgeTrack(
            edge_track_id=1,
            seed_frame_index=0,
            polygon_roi=polygon,
            seed_polyline=np.asarray([[1.0, 2.0], [6.0, 2.0]], dtype=np.float64),
        )
        track1.add_annotation(
            EdgeFrameAnnotation(
                frame_index=1,
                polyline=np.asarray([[1.0, 2.0], [6.0, 2.0]], dtype=np.float64),
                metrics=EdgeMetrics(
                    length_px=5.0,
                    roughness_rms_px=0.2,
                    mean_curvature=0.05,
                    max_curvature=0.08,
                    waviness_amplitude_px=0.4,
                ),
            )
        )
        track2 = EdgeTrack(
            edge_track_id=2,
            seed_frame_index=3,
            polygon_roi=polygon,
            seed_polyline=np.asarray([[1.0, 3.0], [6.0, 3.0]], dtype=np.float64),
        )
        track2.add_annotation(
            EdgeFrameAnnotation(
                frame_index=4,
                polyline=np.asarray([[1.0, 3.0], [6.0, 3.0]], dtype=np.float64),
                metrics=EdgeMetrics(
                    length_px=6.0,
                    roughness_rms_px=0.3,
                    mean_curvature=0.06,
                    max_curvature=0.10,
                    waviness_amplitude_px=0.5,
                ),
            )
        )

        self.window.set_edge_tracks([track1, track2], selected_track_id=1)
        self.window.action_open_edge_results.trigger()
        self.__class__._app.processEvents()

        second_item = self.window.edge_track_list_panel.list_tracks.item(1)
        self.window.edge_track_list_panel.list_tracks.setCurrentItem(second_item)
        self.__class__._app.processEvents()

        self.assertEqual(self.window.current_selected_edge_track_id(), 2)
        self.assertEqual(sequence.active_frame_index, 3)
        self.assertEqual(self.window.current_edge_results_dialog().current_track_id(), 2)

    def test_delete_selected_edge_track_from_main_window_updates_results_and_session(self) -> None:
        sequence = STMSequence(
            source_path="/tmp/edge_delete_main.mpp",
            raw_frames=np.zeros((5, 8, 8), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=8, pixels_y=8, size_nm_x=80.0, size_nm_y=40.0),
        )
        self.window.set_sequence(sequence)

        polygon = PolygonROI(np.asarray([[1.0, 1.0], [6.0, 1.0], [6.0, 6.0], [1.0, 6.0]], dtype=np.float64))
        track1 = EdgeTrack(
            edge_track_id=1,
            seed_frame_index=0,
            polygon_roi=polygon,
            seed_polyline=np.asarray([[1.0, 2.0], [6.0, 2.0]], dtype=np.float64),
        )
        track1.add_annotation(
            EdgeFrameAnnotation(
                frame_index=1,
                polyline=np.asarray([[1.0, 2.1], [6.0, 2.2]], dtype=np.float64),
                metrics=EdgeMetrics(
                    length_px=5.0,
                    length_nm=50.0,
                    roughness_rms_px=0.2,
                    roughness_rms_nm=2.0,
                    mean_curvature=0.05,
                    max_curvature=0.08,
                    waviness_amplitude_px=0.4,
                    waviness_amplitude_nm=4.0,
                ),
            )
        )
        track2 = EdgeTrack(
            edge_track_id=2,
            seed_frame_index=3,
            polygon_roi=polygon,
            seed_polyline=np.asarray([[1.0, 3.0], [6.0, 3.0]], dtype=np.float64),
            label="Step-B",
        )
        track2.add_annotation(
            EdgeFrameAnnotation(
                frame_index=4,
                polyline=np.asarray([[1.0, 3.2], [6.0, 3.1]], dtype=np.float64),
                metrics=EdgeMetrics(
                    length_px=6.0,
                    length_nm=60.0,
                    roughness_rms_px=0.3,
                    roughness_rms_nm=3.0,
                    mean_curvature=0.06,
                    max_curvature=0.10,
                    waviness_amplitude_px=0.5,
                    waviness_amplitude_nm=5.0,
                ),
            )
        )

        self.window.set_edge_tracks([track1, track2], selected_track_id=1)
        self.window.action_open_edge_results.trigger()
        self.__class__._app.processEvents()

        self.assertTrue(self.window.edge_track_list_panel.btn_delete_selected.isEnabled())

        self.window.edge_track_list_panel.btn_delete_selected.click()
        self.__class__._app.processEvents()

        remaining_tracks = self.window.current_edge_tracks()
        self.assertEqual(len(remaining_tracks), 1)
        self.assertEqual(remaining_tracks[0].edge_track_id, 2)
        self.assertEqual(self.window.current_selected_edge_track_id(), 2)
        self.assertEqual(self.window.edge_track_list_panel.list_tracks.count(), 1)
        self.assertEqual(self.window.edge_track_list_panel.lbl_summary.text(), "1 edge track")
        self.assertEqual(self.window.edge_track_list_panel.current_track_id(), 2)

        dialog = self.window.current_edge_results_dialog()
        self.assertIsNotNone(dialog)
        self.assertEqual(dialog.current_track_id(), 2)
        self.assertEqual(dialog.cmb_tracks.count(), 2)
        self.assertEqual(dialog.cmb_tracks.itemData(1, Qt.ItemDataRole.UserRole), 2)

        snapshot = self.window.current_session_snapshot()
        self.assertIsNotNone(snapshot)
        assert snapshot is not None
        self.assertEqual(len(snapshot.edge_tracks), 1)
        self.assertEqual(snapshot.edge_tracks[0].edge_track_id, 2)

    def test_delete_track_from_results_dialog_updates_all_tracks_export_and_session(self) -> None:
        sequence = load_mpp_sequence(str(SAMPLE_MPP))
        self.window.set_sequence(sequence)
        pixel_size_nm = sequence.metadata.get_pixel_size_nm()

        mask1 = np.zeros(sequence.frame_shape, dtype=bool)
        mask1[6:10, 10:15] = True
        mask2 = np.zeros(sequence.frame_shape, dtype=bool)
        mask2[18:23, 20:26] = True

        track1 = ParticleTrack(track_id=1, seed_frame_index=0, seed_bbox=BBoxXYXY(9.0, 5.0, 16.0, 11.0))
        track1.add_annotation(
            TrackFrameAnnotation(
                frame_index=1,
                bbox=BBoxXYXY(10.0, 6.0, 15.0, 10.0),
                mask=mask1,
                metrics=compute_particle_metrics(
                    mask1,
                    sequence.raw_frames[1],
                    pixel_size_nm=pixel_size_nm,
                ),
            )
        )

        track2 = ParticleTrack(track_id=2, seed_frame_index=0, seed_bbox=BBoxXYXY(19.0, 17.0, 27.0, 24.0))
        track2.add_annotation(
            TrackFrameAnnotation(
                frame_index=1,
                bbox=BBoxXYXY(20.0, 18.0, 26.0, 23.0),
                mask=mask2,
                metrics=compute_particle_metrics(
                    mask2,
                    sequence.raw_frames[1],
                    pixel_size_nm=pixel_size_nm,
                ),
            )
        )
        self.window.set_tracks([track1, track2], selected_track_id=1)
        self.window.action_open_results.trigger()
        self.__class__._app.processEvents()

        dialog = self.window.current_results_dialog()
        self.assertIsNotNone(dialog)
        self.assertEqual(dialog.current_track_id(), 1)

        dialog.btn_delete.click()
        self.__class__._app.processEvents()

        self.assertEqual([track.track_id for track in self.window.current_tracks()], [2])
        self.assertIsNone(self.window.current_selected_track_id())
        self.assertEqual(self.window.track_list_panel.list_tracks.count(), 1)
        self.assertEqual(dialog.cmb_tracks.count(), 2)
        self.assertIsNone(dialog.current_track_id())

        dialog.cmb_tracks.setCurrentIndex(0)
        self.__class__._app.processEvents()

        area_items = dialog.plot_area.plotItem.listDataItems()
        self.assertEqual(len(area_items), 1)
        x_data, y_data = area_items[0].getData()
        np.testing.assert_array_equal(x_data, np.asarray([2.0], dtype=np.float32))
        np.testing.assert_array_equal(
            y_data,
            np.asarray([track2.get_annotation(1).metrics.area_px], dtype=np.float32),
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            exported = dialog.export_results_to_path(f"{tmpdir}/deleted_track_results.csv")
            with open(exported["metrics_csv"], newline="", encoding="utf-8") as handle:
                metrics_rows = list(csv.DictReader(handle))
            self.assertEqual({row["track_id"] for row in metrics_rows}, {"2"})

            session_path = f"{tmpdir}/deleted_track_session.nanotrack"
            self.window.save_session_to_path(session_path)
            self.window.set_tracks([])
            self.window.load_session_from_path(session_path)

        self.assertEqual([track.track_id for track in self.window.current_tracks()], [2])

    def test_save_and_load_session_roundtrip_restores_window_state(self) -> None:
        sequence = load_mpp_sequence(str(SAMPLE_MPP))
        self.window.set_sequence(sequence)
        self.window.slider_frame.setValue(2)
        self.window.viewer.place_bbox_at_pixel(24.0, 24.0)

        track = ParticleTrack(track_id=1, seed_frame_index=1, seed_bbox=BBoxXYXY(10.0, 10.0, 18.0, 18.0), label="NP-1")
        mask = np.zeros(sequence.frame_shape, dtype=bool)
        mask[8:12, 11:16] = True
        track.add_annotation(
            TrackFrameAnnotation(
                frame_index=2,
                bbox=BBoxXYXY(11.0, 8.0, 16.0, 12.0),
                mask=mask,
                source=AnnotationSource.SAM2,
                metrics=ParticleMetrics(
                    area_px=float(np.count_nonzero(mask)),
                    perimeter_px=18.0,
                    intensity_sum=33.0,
                    intensity_mean=2.2,
                    intensity_max=4.5,
                ),
            )
        )
        self.window.set_tracks([track], selected_track_id=1)
        polygon = PolygonROI(np.asarray([[10.0, 10.0], [36.0, 12.0], [34.0, 36.0], [12.0, 34.0]], dtype=np.float64))
        edge_track = EdgeTrack(
            edge_track_id=2,
            seed_frame_index=1,
            polygon_roi=polygon,
            seed_polyline=np.asarray([[12.0, 18.0], [34.0, 18.0]], dtype=np.float64),
            label="Edge-2",
        )
        edge_mask = np.zeros(sequence.frame_shape, dtype=bool)
        edge_mask[18, 12:35] = True
        edge_track.add_annotation(
            EdgeFrameAnnotation(
                frame_index=2,
                polyline=np.asarray([[12.0, 18.5], [23.0, 19.0], [34.0, 19.5]], dtype=np.float64),
                edge_mask=edge_mask,
                source=EdgeAnnotationSource.TRACKER_REFINE,
                metrics=EdgeMetrics(
                    length_px=22.0,
                    length_nm=22.0,
                    roughness_rms_px=0.4,
                    roughness_rms_nm=0.4,
                    mean_curvature=0.1,
                    max_curvature=0.15,
                    waviness_amplitude_px=1.0,
                    waviness_amplitude_nm=1.0,
                ),
            )
        )
        self.window._edge_tracks = [edge_track]
        self.window._selected_edge_track_id = 2
        self.window._draft_polygons_by_frame = {2: polygon}
        self.window._draft_edge_polylines_by_frame = {2: np.asarray([[12.0, 20.0], [34.0, 20.0]], dtype=np.float64)}
        self.window._repair_frames = np.full_like(sequence.raw_frames, 0.15, dtype=np.float32)
        self.window._repair_params = {"threshold_sigma": 3.0, "repair_mode": "vertical_interp"}
        self.window._denoised_frames = np.full_like(sequence.raw_frames, 0.85, dtype=np.float32)
        self.window._denoised_sigma_factor = 1.2
        self.window._replace_yolo_detections(
            model_name="yolo11s_v2.0",
            detections_by_frame={
                1: [
                    YoloDetection(
                        frame_index=1,
                        bbox=BBoxXYXY(9.0, 9.0, 18.0, 18.0),
                        confidence=0.87,
                        selected=True,
                        model_name="yolo11s_v2.0",
                    )
                ],
                2: [
                    YoloDetection(
                        frame_index=2,
                        bbox=BBoxXYXY(20.0, 12.0, 30.0, 22.0),
                        confidence=0.52,
                        selected=False,
                        model_name="yolo11s_v2.0",
                    )
                ],
            },
        )
        self.window._update_cached_preprocessing_availability()
        self.window.preprocessing_panel.chk_show_denoised.setChecked(True)
        self.window.track_list_panel.set_mask_tracker_kind(MaskTrackerKind.DAM4SAM)
        registration_results = RegistrationResultSet(
            settings=RegistrationSettings(
                backend="phase_correlation",
                reference_strategy="adjacent",
                registration_view="raw",
            ),
            results_by_frame={
                frame_index: RegistrationFrameResult(
                    frame_index=frame_index,
                    shift_xy=(float(frame_index), -0.5 * float(frame_index)),
                    method="identity" if frame_index == 0 else "phase_correlation_adjacent",
                    quality_score=1.0 if frame_index == 0 else 0.8,
                    phase_peak_ratio=None if frame_index == 0 else 3.0,
                    status="ok",
                )
                for frame_index in range(sequence.frame_count)
            },
            reference_frame_index=0,
            template_frame_indices=(0,),
        )
        self.window._registration_results = registration_results

        with tempfile.TemporaryDirectory() as tmpdir:
            session_path = f"{tmpdir}/sample.nanotrack"
            self.window.save_session_to_path(session_path)

            self.window._repair_frames = None
            self.window._repair_params = None
            self.window._denoised_frames = None
            self.window._denoised_sigma_factor = None
            self.window._draft_bboxes_by_frame = {}
            self.window._draft_polygons_by_frame = {}
            self.window._draft_edge_polylines_by_frame = {}
            self.window._edge_tracks = []
            self.window._selected_edge_track_id = None
            self.window._yolo_detections = None
            self.window._registration_results = None
            self.window.set_tracks([])
            self.window.preprocessing_panel.chk_show_denoised.setChecked(False)
            self.window.track_list_panel.set_mask_tracker_kind(MaskTrackerKind.SAM2)

            self.window.load_session_from_path(session_path)

        self.assertEqual(self.window.current_sequence().active_frame_index, 2)
        self.assertEqual(self.window.current_selected_track_id(), 1)
        self.assertEqual(self.window.track_list_panel.current_mask_tracker_kind(), MaskTrackerKind.DAM4SAM)
        self.assertTrue(self.window.action_save_session.isEnabled())
        self.assertEqual(self.window.current_draft_bbox(), BBoxXYXY(0.0, 0.0, 48.0, 48.0))
        self.assertTrue(self.window.preprocessing_panel.chk_show_denoised.isChecked())
        restored_registration = self.window.current_registration_results()
        self.assertIsNotNone(restored_registration)
        assert restored_registration is not None
        np.testing.assert_allclose(restored_registration.shifts_xy_array(), registration_results.shifts_xy_array())
        self.assertEqual(restored_registration.settings.registration_view, "raw")
        self.assertTrue(self.window.action_open_registration_results.isEnabled())
        self.assertTrue(self.window.action_show_aligned_registration.isEnabled())
        self.assertFalse(self.window.action_show_aligned_registration.isChecked())
        self.assertTrue(self.window.action_show_expanded_aligned_registration.isEnabled())
        self.assertFalse(self.window.action_show_expanded_aligned_registration.isChecked())
        self.window.action_show_aligned_registration.trigger()
        self.assertTrue(self.window.action_show_aligned_registration.isChecked())
        self.assertFalse(self.window.action_show_expanded_aligned_registration.isChecked())
        self.assertIsNotNone(self.window.current_aligned_frames())
        self.assertFalse(self.window.preprocessing_panel.chk_show_denoised.isChecked())
        self.assertIn("View: Aligned registration", self.window.viewer.lbl_meta.text())
        np.testing.assert_array_equal(self.window.current_repair_frames(), np.full_like(sequence.raw_frames, 0.15, dtype=np.float32))
        np.testing.assert_array_equal(self.window.current_denoised_frames(), np.full_like(sequence.raw_frames, 0.85, dtype=np.float32))
        restored_track = self.window.current_tracks()[0]
        restored_annotation = restored_track.get_annotation(2)
        self.assertEqual(restored_track.label, "NP-1")
        np.testing.assert_array_equal(restored_annotation.mask, mask)
        self.assertEqual(restored_annotation.metrics.area_px, float(np.count_nonzero(mask)))
        self.assertEqual(restored_annotation.metrics.intensity_sum, 33.0)
        self.assertEqual(self.window.current_selected_edge_track_id(), 2)
        np.testing.assert_array_equal(self.window.current_draft_polygon_roi().as_array(), polygon.as_array())
        np.testing.assert_array_equal(
            self.window.current_draft_edge_polyline(),
            np.asarray([[12.0, 20.0], [34.0, 20.0]], dtype=np.float64),
        )
        restored_edge_track = self.window.current_edge_tracks()[0]
        self.assertEqual(restored_edge_track.label, "Edge-2")
        restored_edge_annotation = restored_edge_track.get_annotation(2)
        self.assertEqual(restored_edge_annotation.source, EdgeAnnotationSource.TRACKER_REFINE)
        np.testing.assert_array_equal(restored_edge_annotation.edge_mask, edge_mask)
        self.assertEqual(restored_edge_annotation.metrics.length_px, 22.0)
        restored_yolo_detections = self.window.current_yolo_detection_set()
        self.assertIsNotNone(restored_yolo_detections)
        self.assertEqual(restored_yolo_detections.model_name, "yolo11s_v2.0")
        self.assertEqual(restored_yolo_detections.detection_count, 2)
        self.assertEqual(restored_yolo_detections.selected_detection_count(), 1)
        self.assertEqual(
            self.window.yolo_panel.lbl_detections.text(),
            "Detections: current 1 (selected 0) | all 2 (selected 1)",
        )
        self.assertTrue(self.window.yolo_panel.btn_clear.isEnabled())
        restored_unselected_detection = restored_yolo_detections.get_detections(2)[0]
        self.assertFalse(restored_unselected_detection.selected)
        self.assertEqual(restored_unselected_detection.bbox, BBoxXYXY(20.0, 12.0, 30.0, 22.0))

    def test_preprocessing_panel_is_disabled_without_sequence(self) -> None:
        self.assertFalse(self.window.bbox_tools_panel.btn_place.isEnabled())
        self.assertFalse(self.window.bbox_tools_panel.btn_add_seed.isEnabled())
        self.assertFalse(self.window.bbox_tools_panel.btn_clear.isEnabled())
        self.assertEqual(self.window.bbox_tools_panel.lbl_bbox.text(), "No sequence loaded")
        self.assertFalse(self.window.polygon_tools_panel.btn_draw.isEnabled())
        self.assertFalse(self.window.polygon_tools_panel.btn_finish.isEnabled())
        self.assertFalse(self.window.polygon_tools_panel.btn_clear.isEnabled())
        self.assertFalse(self.window.polygon_tools_panel.btn_preview.isEnabled())
        self.assertEqual(self.window.polygon_tools_panel.lbl_polygon.text(), "No sequence loaded")
        self.assertFalse(self.window.preprocessing_panel.btn_preview.isEnabled())
        self.assertFalse(self.window.preprocessing_panel.btn_apply_all.isEnabled())
        self.assertFalse(self.window.preprocessing_panel.btn_repair_preview.isEnabled())
        self.assertFalse(self.window.preprocessing_panel.btn_repair_apply_all.isEnabled())
        self.assertFalse(self.window.action_preview_registration.isEnabled())
        self.assertFalse(self.window.action_run_registration.isEnabled())
        self.assertFalse(self.window.action_open_registration_results.isEnabled())
        self.assertFalse(self.window.action_show_aligned_registration.isEnabled())
        self.assertFalse(self.window.action_show_expanded_aligned_registration.isEnabled())
        self.assertEqual(self.window.cmb_registration_backend.currentData(), "phase_correlation")
        self.assertEqual(self.window.preprocessing_panel.lbl_status.text(), "No sequence loaded")

    def test_registration_backend_combo_lists_supported_algorithms(self) -> None:
        backend_keys = [
            self.window.cmb_registration_backend.itemData(index)
            for index in range(self.window.cmb_registration_backend.count())
        ]

        self.assertEqual(backend_keys[0], "phase_correlation")
        self.assertIn("tile_correlation_ransac", backend_keys)
        self.assertIn("ecc_translation", backend_keys)
        self.assertIn("optical_flow_median", backend_keys)
        self.assertIn("deep_matcher_translation", backend_keys)

    def test_registration_preview_action_opens_adjacent_pair_dialog(self) -> None:
        rng = np.random.default_rng(123)
        reference = rng.normal(0.0, 0.1, (48, 48)).astype(np.float32)
        reference[10:22, 14:27] += 2.0
        reference[28:40, 32:39] -= 1.5
        moving = np.roll(reference, shift=(3, -4), axis=(0, 1))
        sequence = STMSequence(
            source_path="/tmp/registration_preview.mpp",
            raw_frames=np.stack([reference, moving]).astype(np.float32),
            metadata=STMSequenceMetadata(pixels_x=48, pixels_y=48, size_nm_x=24.0, size_nm_y=24.0),
        )
        self.window.set_sequence(sequence)
        self.window._set_active_frame(1)

        self.window.action_preview_registration.trigger()

        dialog = self.window._registration_preview_dialog
        self.assertIsNotNone(dialog)
        assert dialog is not None
        self.assertTrue(dialog.isVisible())
        self.assertIn("Reference | Frame 1/2", dialog.reference_view.lbl_title.text())
        self.assertIn("Registration view: raw", dialog.reference_view.lbl_meta.text())
        self.assertIn("Moving | Frame 2/2", dialog.moving_view.lbl_title.text())
        self.assertEqual(dialog.moving_view.lbl_meta.text(), "Before alignment")
        self.assertIn("Aligned Moving | Frame 2/2", dialog.aligned_view.lbl_title.text())
        aligned_meta = dialog.aligned_view.lbl_meta.text()
        self.assertIn("dx 4.000px", aligned_meta)
        self.assertIn("dy -3.000px", aligned_meta)
        self.assertIn("status ok", aligned_meta)
        self.assertIn("quality", aligned_meta)
        self.assertEqual(
            self.window.statusBar().currentMessage(),
            "Phase registration preview opened for frames 1 -> 2.",
        )

    def test_registration_batch_action_stores_adjacent_shift_results(self) -> None:
        rng = np.random.default_rng(321)
        frame0 = rng.normal(0.0, 0.1, (48, 48)).astype(np.float32)
        frame0[8:20, 10:23] += 2.0
        frame0[29:41, 30:38] -= 1.4
        frame1 = np.roll(frame0, shift=(2, -3), axis=(0, 1))
        frame2 = np.roll(frame1, shift=(-1, 5), axis=(0, 1))
        sequence = STMSequence(
            source_path="/tmp/registration_batch.mpp",
            raw_frames=np.stack([frame0, frame1, frame2]).astype(np.float32),
            metadata=STMSequenceMetadata(pixels_x=48, pixels_y=48),
        )
        self.window.set_sequence(sequence)

        self.window.action_run_registration.trigger()

        result_set = self.window.current_registration_results()
        self.assertIsNotNone(result_set)
        assert result_set is not None
        self.assertEqual(result_set.reference_frame_index, 0)
        self.assertEqual(result_set.frame_indices, [0, 1, 2])
        np.testing.assert_allclose(
            result_set.shifts_xy_array(),
            np.asarray([[0.0, 0.0], [3.0, -2.0], [-2.0, -1.0]], dtype=np.float64),
            atol=1e-6,
        )
        self.assertEqual(result_set.get_result(2).method, "phase_correlation_adjacent")
        self.assertEqual(result_set.status_counts()["ok"], 3)
        self.assertTrue(self.window.action_open_registration_results.isEnabled())
        self.assertTrue(self.window.action_show_aligned_registration.isEnabled())
        self.assertFalse(self.window.action_show_aligned_registration.isChecked())
        self.assertTrue(self.window.action_show_expanded_aligned_registration.isEnabled())
        self.assertFalse(self.window.action_show_expanded_aligned_registration.isChecked())
        self.assertIsNone(self.window.current_aligned_frames())
        self.assertIsNone(self.window.current_expanded_aligned_stack())
        self.assertIn("Registration finished for 3 frames", self.window.statusBar().currentMessage())

    def test_registration_batch_action_uses_selected_ui_backend(self) -> None:
        sequence = STMSequence(
            source_path="/tmp/registration_backend_choice.mpp",
            raw_frames=np.zeros((2, 16, 16), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=16, pixels_y=16),
        )
        self.window.set_sequence(sequence)
        backend_index = self.window.cmb_registration_backend.findData("tile_correlation_ransac")
        self.assertNotEqual(backend_index, -1)
        self.window.cmb_registration_backend.setCurrentIndex(backend_index)
        expected_result_set = RegistrationResultSet(
            settings=RegistrationSettings(
                backend="tile_correlation_ransac",
                reference_strategy="adjacent",
                registration_view="raw",
            ),
            results_by_frame={
                0: RegistrationFrameResult(0, (0.0, 0.0), "identity", quality_score=1.0),
                1: RegistrationFrameResult(1, (1.0, -1.0), "tile_correlation_ransac_adjacent", quality_score=0.9),
            },
            reference_frame_index=0,
            template_frame_indices=(0,),
        )

        with patch("nanotrack.ui.main_window.run_adjacent_phase_registration", return_value=expected_result_set) as run_mock:
            self.window.action_run_registration.trigger()

        run_mock.assert_called_once()
        _, kwargs = run_mock.call_args
        self.assertEqual(kwargs["settings"].backend, "tile_correlation_ransac")
        self.assertEqual(kwargs["settings"].reference_strategy, "adjacent")
        self.assertEqual(kwargs["settings"].registration_view, "raw")
        self.assertEqual(kwargs["excluded_frame_indices"], [])
        self.assertNotIn("backend", kwargs)
        self.assertIs(self.window.current_registration_results(), expected_result_set)

    def test_registration_batch_action_passes_excluded_frames_to_runner(self) -> None:
        sequence = STMSequence(
            source_path="/tmp/registration_excluded_frames.mpp",
            raw_frames=np.zeros((4, 16, 16), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=16, pixels_y=16),
        )
        sequence.set_frame_excluded(1, True)
        sequence.set_frame_excluded(3, True)
        self.window.set_sequence(sequence)
        expected_result_set = RegistrationResultSet(
            settings=RegistrationSettings(
                backend="phase_correlation",
                reference_strategy="adjacent",
                registration_view="raw",
            ),
            results_by_frame={
                0: RegistrationFrameResult(0, (0.0, 0.0), "identity", quality_score=1.0),
                1: RegistrationFrameResult(1, (0.0, 0.0), "excluded_frame", quality_score=0.0, status="manual_review"),
                2: RegistrationFrameResult(2, (1.0, 0.0), "phase_correlation_adjacent", quality_score=0.9),
                3: RegistrationFrameResult(3, (1.0, 0.0), "excluded_frame", quality_score=0.0, status="manual_review"),
            },
            reference_frame_index=0,
            template_frame_indices=(0,),
        )

        with patch("nanotrack.ui.main_window.run_adjacent_phase_registration", return_value=expected_result_set) as run_mock:
            self.window.action_run_registration.trigger()

        run_mock.assert_called_once()
        _, kwargs = run_mock.call_args
        self.assertEqual(kwargs["excluded_frame_indices"], [1, 3])
        self.assertIs(self.window.current_registration_results(), expected_result_set)

    def test_registration_results_action_opens_quality_dialog(self) -> None:
        rng = np.random.default_rng(987)
        frame0 = rng.normal(0.0, 0.1, (48, 48)).astype(np.float32)
        frame0[8:20, 10:23] += 2.0
        frame0[29:41, 30:38] -= 1.4
        frame1 = np.roll(frame0, shift=(2, -3), axis=(0, 1))
        frame2 = np.roll(frame1, shift=(-1, 5), axis=(0, 1))
        sequence = STMSequence(
            source_path="/tmp/registration_results.mpp",
            raw_frames=np.stack([frame0, frame1, frame2]).astype(np.float32),
            metadata=STMSequenceMetadata(pixels_x=48, pixels_y=48),
        )
        self.window.set_sequence(sequence)
        self.window.action_run_registration.trigger()

        self.window.action_open_registration_results.trigger()

        dialog = self.window.current_registration_results_dialog()
        self.assertIsNotNone(dialog)
        assert dialog is not None
        self.assertTrue(dialog.isVisible())
        self.assertEqual(dialog.table_results.rowCount(), 3)
        self.assertEqual(dialog.table_results.item(1, 0).text(), "2")
        self.assertEqual(dialog.table_results.item(1, 1).text(), "3.000")
        self.assertEqual(dialog.table_results.item(1, 2).text(), "-2.000")
        self.assertIn("frames: 3 / 3", dialog.lbl_summary.text())
        self.assertIn("ok: 3", dialog.lbl_summary.text())
        self.assertEqual(len(dialog.plot_dx.plotItem.listDataItems()), 1)
        self.assertEqual(len(dialog.plot_dy.plotItem.listDataItems()), 1)
        self.assertEqual(len(dialog.plot_quality.plotItem.listDataItems()), 1)
        self.assertEqual(self.window.statusBar().currentMessage(), "Registration results window opened.")

    def test_registration_aligned_view_uses_stored_shifts_without_mutating_raw_frames(self) -> None:
        rng = np.random.default_rng(654)
        frame0 = rng.normal(0.0, 0.1, (48, 48)).astype(np.float32)
        frame0[8:20, 10:23] += 2.0
        frame0[29:41, 30:38] -= 1.4
        frame1 = np.roll(frame0, shift=(2, -3), axis=(0, 1))
        frame2 = np.roll(frame1, shift=(-1, 5), axis=(0, 1))
        raw_frames = np.stack([frame0, frame1, frame2]).astype(np.float32)
        sequence = STMSequence(
            source_path="/tmp/registration_aligned.mpp",
            raw_frames=raw_frames.copy(),
            metadata=STMSequenceMetadata(pixels_x=48, pixels_y=48),
        )
        self.window.set_sequence(sequence)

        self.window.action_run_registration.trigger()
        self.window.action_show_aligned_registration.trigger()

        aligned = self.window.current_aligned_frames()
        self.assertIsNotNone(aligned)
        assert aligned is not None
        self.assertTrue(self.window.action_show_aligned_registration.isChecked())
        self.assertFalse(self.window.action_show_expanded_aligned_registration.isChecked())
        self.assertIn("View: Aligned registration", self.window.viewer.lbl_meta.text())
        np.testing.assert_array_equal(sequence.raw_frames, raw_frames)
        np.testing.assert_array_equal(self.window.viewer.viewer.image_item.image, aligned[0])

        self.window.slider_frame.setValue(1)
        np.testing.assert_array_equal(self.window.viewer.viewer.image_item.image, aligned[1])
        self.assertLess(float(np.mean((aligned[1] - frame0) ** 2)), float(np.mean((frame1 - frame0) ** 2)))

        self.window.action_show_aligned_registration.trigger()
        self.assertFalse(self.window.action_show_aligned_registration.isChecked())
        np.testing.assert_array_equal(self.window.viewer.viewer.image_item.image, sequence.raw_frames[1])
        self.assertIn("View: Raw", self.window.viewer.lbl_meta.text())

    def test_registration_expanded_aligned_view_uses_expanded_cache_and_renders_frame(self) -> None:
        raw_frames = np.arange(2 * 3 * 4, dtype=np.float32).reshape(2, 3, 4)
        sequence = STMSequence(
            source_path="/tmp/registration_expanded_aligned.mpp",
            raw_frames=raw_frames.copy(),
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=3, size_nm_x=8.0, size_nm_y=6.0),
        )
        result_set = RegistrationResultSet(
            settings=RegistrationSettings(registration_view="raw"),
            results_by_frame={
                0: RegistrationFrameResult(0, (0.0, 0.0), "identity", quality_score=1.0),
                1: RegistrationFrameResult(1, (2.0, -1.0), "manual", quality_score=0.9),
            },
        )
        self.window.set_sequence(sequence)
        self.window._registration_results = result_set
        self.window._update_menu_action_state()

        self.assertTrue(self.window.action_show_expanded_aligned_registration.isEnabled())
        self.assertIsNone(self.window.current_expanded_aligned_stack())
        self.window.action_show_expanded_aligned_registration.trigger()

        expanded = self.window.current_expanded_aligned_stack()
        self.assertIsNotNone(expanded)
        assert expanded is not None
        self.assertTrue(self.window.action_show_expanded_aligned_registration.isChecked())
        self.assertFalse(self.window.action_show_aligned_registration.isChecked())
        self.assertEqual(expanded.frames.shape, (2, 4, 6))
        self.assertEqual(expanded.padding_ltrb, (0, 1, 2, 0))
        self.assertIn("View: Expanded aligned registration 6x4 px pad 0,1,2,0", self.window.viewer.lbl_meta.text())
        np.testing.assert_array_equal(sequence.raw_frames, raw_frames)
        np.testing.assert_array_equal(self.window.viewer.viewer.image_item.image, expanded.frames[0])

        self.window.slider_frame.setValue(1)
        np.testing.assert_array_equal(self.window.viewer.viewer.image_item.image, expanded.frames[1])

        self.window.action_show_expanded_aligned_registration.trigger()
        self.assertFalse(self.window.action_show_expanded_aligned_registration.isChecked())
        np.testing.assert_array_equal(self.window.viewer.viewer.image_item.image, sequence.raw_frames[1])
        self.assertIn("View: Raw", self.window.viewer.lbl_meta.text())

    def test_registration_view_actions_switch_between_raw_aligned_and_expanded_aligned(self) -> None:
        raw_frames = np.arange(2 * 4 * 5, dtype=np.float32).reshape(2, 4, 5)
        sequence = STMSequence(
            source_path="/tmp/registration_view_switching.mpp",
            raw_frames=raw_frames.copy(),
            metadata=STMSequenceMetadata(pixels_x=5, pixels_y=4, size_nm_x=10.0, size_nm_y=8.0),
        )
        result_set = RegistrationResultSet(
            settings=RegistrationSettings(registration_view="raw"),
            results_by_frame={
                0: RegistrationFrameResult(0, (0.0, 0.0), "identity", quality_score=1.0),
                1: RegistrationFrameResult(1, (2.0, -1.0), "manual", quality_score=0.9),
            },
        )
        self.window.set_sequence(sequence)
        self.window._registration_results = result_set
        self.window._set_active_frame(1)
        self.window._update_menu_action_state()

        self.assertFalse(self.window.action_show_aligned_registration.isChecked())
        self.assertFalse(self.window.action_show_expanded_aligned_registration.isChecked())
        np.testing.assert_array_equal(self.window.viewer.viewer.image_item.image, sequence.raw_frames[1])
        self.assertIn("View: Raw", self.window.viewer.lbl_meta.text())

        self.window.action_show_aligned_registration.trigger()
        aligned = self.window.current_aligned_frames()
        self.assertIsNotNone(aligned)
        assert aligned is not None
        self.assertTrue(self.window.action_show_aligned_registration.isChecked())
        self.assertFalse(self.window.action_show_expanded_aligned_registration.isChecked())
        np.testing.assert_array_equal(self.window.viewer.viewer.image_item.image, aligned[1])
        self.assertIn("View: Aligned registration", self.window.viewer.lbl_meta.text())

        self.window.action_show_expanded_aligned_registration.trigger()
        expanded = self.window.current_expanded_aligned_stack()
        self.assertIsNotNone(expanded)
        assert expanded is not None
        self.assertFalse(self.window.action_show_aligned_registration.isChecked())
        self.assertTrue(self.window.action_show_expanded_aligned_registration.isChecked())
        np.testing.assert_array_equal(self.window.viewer.viewer.image_item.image, expanded.frames[1])
        self.assertIn("View: Expanded aligned registration", self.window.viewer.lbl_meta.text())

        self.window.action_show_aligned_registration.trigger()
        self.assertTrue(self.window.action_show_aligned_registration.isChecked())
        self.assertFalse(self.window.action_show_expanded_aligned_registration.isChecked())
        np.testing.assert_array_equal(self.window.viewer.viewer.image_item.image, aligned[1])
        self.assertIn("View: Aligned registration", self.window.viewer.lbl_meta.text())

        self.window.action_show_aligned_registration.trigger()
        self.assertFalse(self.window.action_show_aligned_registration.isChecked())
        self.assertFalse(self.window.action_show_expanded_aligned_registration.isChecked())
        np.testing.assert_array_equal(self.window.viewer.viewer.image_item.image, sequence.raw_frames[1])
        self.assertIn("View: Raw", self.window.viewer.lbl_meta.text())

    def test_expanded_aligned_view_offsets_overlays_without_mutating_raw_annotations(self) -> None:
        raw_frames = np.arange(2 * 3 * 4, dtype=np.float32).reshape(2, 3, 4)
        sequence = STMSequence(
            source_path="/tmp/registration_expanded_overlay_offset.mpp",
            raw_frames=raw_frames.copy(),
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=3, size_nm_x=8.0, size_nm_y=6.0),
        )
        result_set = RegistrationResultSet(
            settings=RegistrationSettings(registration_view="raw"),
            results_by_frame={
                0: RegistrationFrameResult(0, (0.0, 0.0), "identity", quality_score=1.0),
                1: RegistrationFrameResult(1, (2.0, -1.0), "manual", quality_score=0.9),
            },
        )
        bbox = BBoxXYXY(1.0, 1.0, 3.0, 2.0)
        polygon = PolygonROI(np.asarray([[1.0, 1.0], [3.0, 1.0], [1.0, 2.0]], dtype=np.float64))
        edge_polyline = np.asarray([[1.5, 1.0], [2.5, 1.5]], dtype=np.float64)
        self.window.set_sequence(sequence)
        self.window._draft_bboxes_by_frame[1] = bbox
        self.window._draft_polygons_by_frame[1] = polygon
        self.window._draft_edge_polylines_by_frame[1] = edge_polyline.copy()
        self.window._registration_results = result_set
        self.window._set_active_frame(1)
        self.window._update_menu_action_state()

        self.window.action_show_expanded_aligned_registration.trigger()

        expanded = self.window.current_expanded_aligned_stack()
        self.assertIsNotNone(expanded)
        assert expanded is not None
        np.testing.assert_allclose(expanded.frame_origins_xy[1], np.asarray([2.0, 0.0]))
        self.assertEqual(self.window.current_draft_bbox(), bbox)
        np.testing.assert_array_equal(self.window.current_draft_polygon_roi().as_array(), polygon.as_array())
        np.testing.assert_array_equal(self.window.current_draft_edge_polyline(), edge_polyline)
        self.assertEqual(self.window.viewer.current_bbox(), bbox)
        np.testing.assert_array_equal(self.window.viewer.current_polygon_roi().as_array(), polygon.as_array())
        np.testing.assert_array_equal(self.window.viewer.current_edge_polyline(), edge_polyline)

        bbox_pos = self.window.viewer._bbox_roi.pos()
        bbox_size = self.window.viewer._bbox_roi.size()
        self.assertAlmostEqual(bbox_pos.x(), 6.0)
        self.assertAlmostEqual(bbox_pos.y(), 2.0)
        self.assertAlmostEqual(bbox_size.x(), 4.0)
        self.assertAlmostEqual(bbox_size.y(), 2.0)
        np.testing.assert_allclose(
            self.window.viewer._polygon_vertices_px_to_nm(polygon.vertices_xy),
            np.asarray([[6.0, 2.0], [10.0, 2.0], [6.0, 4.0]], dtype=np.float64),
        )
        np.testing.assert_allclose(
            self.window.viewer._polyline_nm(edge_polyline),
            np.asarray([[7.0, 2.0], [9.0, 3.0]], dtype=np.float64),
        )
        np.testing.assert_allclose(self.window.viewer._view_to_pixel_coords(8.0, 3.0), (2.0, 1.5))

        self.window.action_show_expanded_aligned_registration.trigger()
        bbox_pos = self.window.viewer._bbox_roi.pos()
        self.assertAlmostEqual(bbox_pos.x(), 2.0)
        self.assertAlmostEqual(bbox_pos.y(), 2.0)
        np.testing.assert_allclose(
            self.window.viewer._polygon_vertices_px_to_nm(polygon.vertices_xy),
            np.asarray([[2.0, 2.0], [6.0, 2.0], [2.0, 4.0]], dtype=np.float64),
        )

    def test_expanded_aligned_registration_cache_is_lazy_and_reused(self) -> None:
        sequence = STMSequence(
            source_path="/tmp/expanded_aligned_cache.mpp",
            raw_frames=np.arange(2 * 3 * 4, dtype=np.float32).reshape(2, 3, 4),
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=3, size_nm_x=8.0, size_nm_y=6.0),
        )
        result_set = RegistrationResultSet(
            settings=RegistrationSettings(registration_view="raw"),
            results_by_frame={
                0: RegistrationFrameResult(0, (0.0, 0.0), "identity", quality_score=1.0),
                1: RegistrationFrameResult(1, (2.0, -1.0), "manual", quality_score=0.9),
            },
        )
        self.window.set_sequence(sequence)
        self.window._registration_results = result_set

        self.assertIsNone(self.window.current_expanded_aligned_stack())
        expanded = self.window._ensure_expanded_aligned_registration_cache()

        self.assertIs(self.window.current_expanded_aligned_stack(), expanded)
        self.assertIs(self.window.current_expanded_aligned_frames(), expanded.frames)
        self.assertIs(self.window._ensure_expanded_aligned_registration_cache(), expanded)
        self.assertEqual(expanded.frames.shape, (2, 4, 6))
        self.assertEqual(expanded.metadata.pixels_x, 6)
        self.assertEqual(expanded.metadata.pixels_y, 4)
        self.window._set_active_frame(1)
        np.testing.assert_array_equal(self.window.current_expanded_aligned_frame(), expanded.frames[1])

    def test_expanded_aligned_registration_cache_is_cleared_on_sequence_change_and_registration_rerun(self) -> None:
        sequence = STMSequence(
            source_path="/tmp/expanded_aligned_cache_clear.mpp",
            raw_frames=np.zeros((2, 8, 8), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=8, pixels_y=8),
        )
        old_result_set = RegistrationResultSet(
            settings=RegistrationSettings(registration_view="raw"),
            results_by_frame={
                0: RegistrationFrameResult(0, (0.0, 0.0), "identity", quality_score=1.0),
                1: RegistrationFrameResult(1, (1.0, 0.0), "manual", quality_score=0.9),
            },
        )
        self.window.set_sequence(sequence)
        self.window._registration_results = old_result_set
        self.window._ensure_expanded_aligned_registration_cache()
        self.assertIsNotNone(self.window.current_expanded_aligned_stack())

        replacement = STMSequence(
            source_path="/tmp/replacement.mpp",
            raw_frames=np.zeros((1, 8, 8), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=8, pixels_y=8),
        )
        self.window.set_sequence(replacement)
        self.assertIsNone(self.window.current_expanded_aligned_stack())

        new_result_set = RegistrationResultSet(
            settings=RegistrationSettings(registration_view="raw"),
            results_by_frame={
                0: RegistrationFrameResult(0, (0.0, 0.0), "identity", quality_score=1.0),
                1: RegistrationFrameResult(1, (-1.0, 1.0), "manual", quality_score=0.8),
            },
        )
        self.window.set_sequence(sequence)
        self.window._registration_results = old_result_set
        self.window._ensure_expanded_aligned_registration_cache()

        with patch("nanotrack.ui.main_window.run_adjacent_phase_registration", return_value=new_result_set):
            self.window._on_registration_batch_requested()

        self.assertIs(self.window.current_registration_results(), new_result_set)
        self.assertIsNone(self.window.current_expanded_aligned_stack())

    def test_polygon_roi_can_be_finished_and_updates_panel(self) -> None:
        sequence = load_mpp_sequence(str(SAMPLE_MPP))
        self.window.set_sequence(sequence)

        self.window.polygon_tools_panel.btn_draw.setChecked(True)
        self.window.viewer.place_polygon_vertex_at_pixel(10.0, 12.0)
        self.window.viewer.place_polygon_vertex_at_pixel(22.0, 14.0)
        self.window.viewer.place_polygon_vertex_at_pixel(18.0, 28.0)
        self.window.polygon_tools_panel.btn_finish.click()

        polygon = self.window.current_draft_polygon_roi()
        self.assertIsNotNone(polygon)
        np.testing.assert_array_equal(
            polygon.as_array(),
            np.asarray([[10.0, 12.0], [22.0, 14.0], [18.0, 28.0]], dtype=np.float64),
        )
        self.assertIsNotNone(self.window.viewer.current_polygon_roi())
        self.assertIsNotNone(self.window.viewer._polygon_roi)
        self.assertEqual(self.window.polygon_tools_panel.lbl_frame.text(), "Frame: 1")
        self.assertIn("Vertices: 3", self.window.polygon_tools_panel.lbl_polygon.text())
        self.assertTrue(self.window.polygon_tools_panel.btn_clear.isEnabled())
        self.assertTrue(self.window.polygon_tools_panel.btn_preview.isEnabled())

    def test_edge_preview_uses_preprocessed_input_and_opens_dialog(self) -> None:
        sequence = load_mpp_sequence(str(SAMPLE_MPP))
        self.window.set_sequence(sequence)

        polygon = PolygonROI(np.asarray([[10.0, 12.0], [22.0, 14.0], [18.0, 28.0]], dtype=np.float64))
        self.window.viewer._commit_polygon(polygon)
        self.window.polygon_tools_panel.sp_dexined_threshold.setValue(0.35)
        self.window.polygon_tools_panel.sp_edge_components.setValue(2)
        self.window.polygon_tools_panel.cmb_inference_resolution.setCurrentIndex(1)

        repaired = np.full_like(sequence.raw_frames, 0.2, dtype=np.float32)
        denoised = np.full_like(sequence.raw_frames, 0.4, dtype=np.float32)
        self.window._repair_frames = repaired
        self.window._denoised_frames = denoised
        self.window._denoised_sigma_factor = 0.8

        edge_prob = np.zeros((1, *sequence.frame_shape), dtype=np.float32)
        edge_prob[0, 12:28, 10:22] = 0.75
        edge_prob[0, 4:7, 4:10] = 0.6
        edge_binary = edge_prob >= 0.5
        run_output = DexiNedRunOutput(
            edge_prob=edge_prob,
            edge_binary=edge_binary,
            model_name="dexined",
            checkpoint_name="DexiNed_BIPED_10.pth",
        )

        def fake_run(run_input):
            time.sleep(0.05)
            np.testing.assert_array_equal(run_input.frames, denoised[[0]])
            self.assertEqual(run_input.source_view, "repair+bm3d")
            self.assertEqual(run_input.polygon_mask.shape, sequence.frame_shape)
            self.assertTrue(np.any(run_input.polygon_mask))
            self.assertAlmostEqual(run_input.threshold, 0.35, places=6)
            np.testing.assert_array_equal(run_input.inference_resolution_hw, np.asarray([512, 512], dtype=np.int32))
            return run_output

        with patch.object(self.window._dexined_backend, "run", side_effect=fake_run) as run_mock:
            self.window.polygon_tools_panel.btn_preview.click()
            self.assertIsNotNone(self.window._dexined_progress_dialog)
            self.assertTrue(self.window._dexined_progress_dialog.isVisible())
            for _ in range(250):
                self.__class__._app.processEvents()
                if run_mock.called and self.window._edge_preview_dialog is not None and self.window._edge_preview_dialog.isVisible():
                    break
                time.sleep(0.01)

        run_mock.assert_called_once()
        self.assertIsNotNone(self.window._edge_preview_dialog)
        self.assertTrue(self.window._edge_preview_dialog.isVisible())
        self.assertIn("BM3D input | Frame 1/", self.window._edge_preview_dialog.input_view.lbl_title.text())
        self.assertEqual(self.window._edge_preview_dialog.input_view.lbl_meta.text(), "BM3D cache")
        self.assertGreater(len(self.window._edge_preview_dialog.input_view.viewer._overlay_items), 0)
        self.assertIn("Dominant Edge | Frame 1/", self.window._edge_preview_dialog.edge_view.lbl_title.text())
        self.assertIn("repair+bm3d", self.window._edge_preview_dialog.edge_view.lbl_meta.text())
        self.assertIn("thr 0.35", self.window._edge_preview_dialog.edge_view.lbl_meta.text())
        self.assertIn("k 2", self.window._edge_preview_dialog.edge_view.lbl_meta.text())
        self.assertIn("512", self.window._edge_preview_dialog.edge_view.lbl_meta.text())
        self.assertIn("selected px", self.window._edge_preview_dialog.edge_view.lbl_meta.text())
        self.assertIn("mode component", self.window._edge_preview_dialog.edge_view.lbl_meta.text())
        self.assertIn("coarse graph_path", self.window._edge_preview_dialog.edge_view.lbl_meta.text())
        self.assertIn("refine combined", self.window._edge_preview_dialog.edge_view.lbl_meta.text())
        self.assertIn("subpx step_tanh", self.window._edge_preview_dialog.edge_view.lbl_meta.text())
        self.assertIn("fit", self.window._edge_preview_dialog.edge_view.lbl_meta.text())
        self.assertIn("sigma", self.window._edge_preview_dialog.edge_view.lbl_meta.text())
        self.assertIn("geom graph->graph_path", self.window._edge_preview_dialog.edge_view.lbl_meta.text())
        self.assertIn("conf", self.window._edge_preview_dialog.edge_view.lbl_meta.text())
        self.assertIn("review", self.window._edge_preview_dialog.edge_view.lbl_meta.text())
        self.assertIn("shift", self.window._edge_preview_dialog.edge_view.lbl_meta.text())
        self.assertIn("pts", self.window._edge_preview_dialog.edge_view.lbl_meta.text())
        self.assertGreater(len(self.window._edge_preview_dialog.edge_view.viewer._overlay_items), 0)
        self.assertEqual(self.window.statusBar().currentMessage(), "DexiNed preview opened for frame 1.")

    def test_edge_polyline_method_can_use_pca_binning(self) -> None:
        sequence = load_mpp_sequence(str(SAMPLE_MPP))
        self.window.set_sequence(sequence)

        polygon = PolygonROI(np.asarray([[8.0, 10.0], [24.0, 10.0], [24.0, 28.0], [8.0, 28.0]], dtype=np.float64))
        self.window.viewer._commit_polygon(polygon)
        method_index = self.window.polygon_tools_panel.cmb_polyline_method.findData("pca_bins")
        self.assertNotEqual(method_index, -1)
        self.window.polygon_tools_panel.cmb_polyline_method.setCurrentIndex(method_index)

        run_input, input_frame, preview_meta = self.window._build_dexined_preview_input(polygon)
        self.assertEqual(self.window.polygon_tools_panel.edge_polyline_method(), "pca_bins")
        self.assertEqual(preview_meta["polyline_method"], "pca_bins")
        self.assertEqual(run_input.frames.shape[0], 1)

        edge_frame = np.zeros(sequence.frame_shape, dtype=np.float32)
        edge_frame[14:17, 10:24] = 0.8
        selection, _selected_edge_frame, coarse_polyline, refined_polyline, geometry_quality, _max_prob = (
            self.window._extract_dominant_edge_geometry(
                edge_frame,
                np.asarray(preview_meta["polygon_mask"], dtype=bool),
                input_frame=input_frame,
                edge_binary_frame=edge_frame >= 0.5,
                requested_threshold=float(preview_meta["threshold"]),
                top_k_components=int(preview_meta["top_k_components"]),
                polyline_method=str(preview_meta["polyline_method"]),
                refine_score_mode="edge_prob",
                refine_search_radius_px=1,
            )
        )

        self.assertEqual(coarse_polyline.extraction_mode, "binned_pca")
        self.assertEqual(geometry_quality.polyline_method, "pca_bins")
        self.assertEqual(geometry_quality.extraction_mode, "binned_pca")
        self.assertEqual(refined_polyline.subpixel_mode, "step_tanh")
        self.assertGreater(selection.pixel_count, 0)
        self.assertGreater(refined_polyline.point_count, 1)

    def test_edge_polyline_method_is_preserved_across_edge_workflow_metadata(self) -> None:
        sequence = STMSequence(
            source_path="/tmp/edge_polyline_method_meta.mpp",
            raw_frames=np.zeros((5, 32, 32), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=32, pixels_y=32, size_nm_x=32.0, size_nm_y=32.0),
        )
        self.window.set_sequence(sequence)
        track = self._set_existing_edge_track(sequence, frame_indices=[0, 1, 2, 3, 4])

        method_index = self.window.polygon_tools_panel.cmb_polyline_method.findData("pca_bins")
        self.assertNotEqual(method_index, -1)
        self.window.polygon_tools_panel.cmb_polyline_method.setCurrentIndex(method_index)
        self.window.slider_frame.setValue(1)
        self.__class__._app.processEvents()
        polygon = PolygonROI(np.asarray([[6.0, 8.0], [25.0, 8.0], [25.0, 25.0], [8.0, 27.0]], dtype=np.float64))
        self.window.viewer._commit_polygon(polygon)
        self.window.polygon_tools_panel.sp_run_end_frame.setValue(4)

        _preview_input, _preview_frame, preview_meta = self.window._build_dexined_preview_input(polygon)
        sequence_input, sequence_meta = self.window._build_dexined_sequence_input(polygon)
        stitch_input, stitch_meta = self.window._build_dexined_stitch_input(track, polygon)
        redetect_input, redetect_meta = self.window._build_dexined_redetect_input(track)
        partial_input, partial_meta = self.window._build_dexined_partial_redetect_input(track)
        resume_input, resume_meta = self.window._build_dexined_resume_input(track, polygon, track.get_annotation(1))

        for meta in (preview_meta, sequence_meta, stitch_meta, redetect_meta, partial_meta, resume_meta):
            self.assertEqual(meta["polyline_method"], "pca_bins")

        np.testing.assert_array_equal(sequence_input.frame_indices, np.asarray([1, 2, 3], dtype=np.int32))
        self.assertIsNotNone(stitch_input)
        assert stitch_input is not None
        np.testing.assert_array_equal(stitch_input.frame_indices, np.asarray([2, 3], dtype=np.int32))
        np.testing.assert_array_equal(redetect_input.frame_indices, np.asarray([0, 1, 2, 3, 4], dtype=np.int32))
        np.testing.assert_array_equal(partial_input.frame_indices, np.asarray([1, 2, 3], dtype=np.int32))
        self.assertEqual(resume_input.frames.shape[0], 3)

    def test_edge_geometry_pipeline_end_to_end_for_graph_and_pca_methods(self) -> None:
        y_coords = np.arange(32, dtype=np.float64)[:, None]
        x_coords = np.arange(32, dtype=np.float64)[None, :]
        true_y = 13.35
        step_sigma = 0.7
        input_frame = (
            0.10
            + 0.01 * x_coords
            + 2.0 * 0.5 * (1.0 + np.tanh((y_coords - true_y) / step_sigma))
        ).astype(np.float32)
        sequence = STMSequence(
            source_path="/tmp/advanced_edge_geometry.mpp",
            raw_frames=input_frame[None, ...],
            metadata=STMSequenceMetadata(pixels_x=32, pixels_y=32, size_nm_x=32.0, size_nm_y=32.0),
        )
        self.window.set_sequence(sequence)

        edge_profile = 1.0 / np.cosh((np.arange(32, dtype=np.float64) - true_y) / step_sigma) ** 2
        edge_frame = np.zeros(sequence.frame_shape, dtype=np.float32)
        edge_frame[:, 5:27] = edge_profile[:, None].astype(np.float32)
        polygon = PolygonROI(np.asarray([[4.0, 5.0], [28.0, 5.0], [28.0, 26.0], [4.0, 26.0]], dtype=np.float64))
        polygon_mask = self.window._polygon_roi_to_mask(polygon)

        for polyline_method, extraction_mode in (("graph", "graph_path"), ("pca_bins", "binned_pca")):
            output = DexiNedRunOutput(
                edge_prob=edge_frame[None, ...],
                edge_binary=edge_frame[None, ...] >= 0.25,
                model_name="dexined",
                checkpoint_name="DexiNed_BIPED_10.pth",
            )
            annotations = self.window._build_edge_annotations_from_dexined_output(
                output,
                frame_indices=np.asarray([0], dtype=np.int32),
                input_frames=input_frame[None, ...],
                polygon_mask=polygon_mask,
                threshold=0.25,
                top_k_components=1,
                polyline_method=polyline_method,
                refine_score_mode="edge_prob",
                refine_search_radius_px=5,
            )

            annotation = annotations[0]
            self.assertIsNotNone(annotation.geometry_quality)
            assert annotation.geometry_quality is not None
            self.assertEqual(annotation.geometry_quality.polyline_method, polyline_method)
            self.assertEqual(annotation.geometry_quality.extraction_mode, extraction_mode)
            self.assertEqual(annotation.geometry_quality.refinement_mode, "normal_dp_edge_prob")
            self.assertIsNotNone(annotation.polyline)
            self.assertIsNotNone(annotation.metrics)
            self.assertGreater(annotation.metrics.length_px, 0.0)
            self.assertLess(abs(float(np.mean(annotation.polyline[:, 1])) - true_y), 0.30)

    def test_edge_preview_can_use_teed_backend(self) -> None:
        sequence = load_mpp_sequence(str(SAMPLE_MPP))
        self.window.set_sequence(sequence)

        polygon = PolygonROI(np.asarray([[10.0, 12.0], [22.0, 14.0], [18.0, 28.0]], dtype=np.float64))
        self.window.viewer._commit_polygon(polygon)
        self.window.polygon_tools_panel.cmb_edge_backend.setCurrentIndex(1)

        edge_prob = np.zeros((1, *sequence.frame_shape), dtype=np.float32)
        edge_prob[0, 12:28, 10:22] = 0.78
        run_output = DexiNedRunOutput(
            edge_prob=edge_prob,
            edge_binary=edge_prob >= 0.5,
            model_name="teed",
            checkpoint_name="5_model.pth",
        )

        def fake_teed_run(run_input):
            time.sleep(0.05)
            self.assertEqual(run_input.source_view, "raw")
            return run_output

        with (
            patch.object(self.window._teed_backend, "run", side_effect=fake_teed_run) as teed_run_mock,
            patch.object(
                self.window._dexined_backend,
                "run",
                side_effect=AssertionError("DexiNed backend should not run when TEED is selected."),
            ) as dexined_run_mock,
        ):
            self.window.polygon_tools_panel.btn_preview.click()
            for _ in range(250):
                self.__class__._app.processEvents()
                if teed_run_mock.called and self.window._edge_preview_dialog is not None and self.window._edge_preview_dialog.isVisible():
                    break
                time.sleep(0.01)

        teed_run_mock.assert_called_once()
        dexined_run_mock.assert_not_called()
        self.assertIsNotNone(self.window._edge_preview_dialog)
        self.assertTrue(self.window._edge_preview_dialog.isVisible())
        self.assertEqual(self.window._edge_preview_dialog.windowTitle(), "TEED Preview")
        self.assertEqual(self.window.statusBar().currentMessage(), "TEED preview opened for frame 1.")

    def test_edge_preview_can_use_nbed_backend(self) -> None:
        sequence = load_mpp_sequence(str(SAMPLE_MPP))
        self.window.set_sequence(sequence)

        polygon = PolygonROI(np.asarray([[10.0, 12.0], [22.0, 14.0], [18.0, 28.0]], dtype=np.float64))
        self.window.viewer._commit_polygon(polygon)
        self.window.polygon_tools_panel.cmb_edge_backend.setCurrentIndex(2)

        edge_prob = np.zeros((1, *sequence.frame_shape), dtype=np.float32)
        edge_prob[0, 12:28, 10:22] = 0.78
        run_output = DexiNedRunOutput(
            edge_prob=edge_prob,
            edge_binary=edge_prob >= 0.5,
            model_name="nbed",
            checkpoint_name="NBED_BIPED.pth",
        )

        def fake_nbed_run(run_input):
            time.sleep(0.05)
            self.assertEqual(run_input.source_view, "raw")
            return run_output

        with (
            patch.object(self.window._nbed_backend, "run", side_effect=fake_nbed_run) as nbed_run_mock,
            patch.object(
                self.window._dexined_backend,
                "run",
                side_effect=AssertionError("DexiNed backend should not run when NBED is selected."),
            ) as dexined_run_mock,
            patch.object(
                self.window._teed_backend,
                "run",
                side_effect=AssertionError("TEED backend should not run when NBED is selected."),
            ) as teed_run_mock,
        ):
            self.window.polygon_tools_panel.btn_preview.click()
            for _ in range(250):
                self.__class__._app.processEvents()
                if nbed_run_mock.called and self.window._edge_preview_dialog is not None and self.window._edge_preview_dialog.isVisible():
                    break
                time.sleep(0.01)

        nbed_run_mock.assert_called_once()
        dexined_run_mock.assert_not_called()
        teed_run_mock.assert_not_called()
        self.assertIsNotNone(self.window._edge_preview_dialog)
        self.assertTrue(self.window._edge_preview_dialog.isVisible())
        self.assertEqual(self.window._edge_preview_dialog.windowTitle(), "NBED Preview")
        self.assertEqual(self.window.statusBar().currentMessage(), "NBED preview opened for frame 1.")

    def test_edge_preview_can_use_ddn_backend(self) -> None:
        sequence = load_mpp_sequence(str(SAMPLE_MPP))
        self.window.set_sequence(sequence)

        polygon = PolygonROI(np.asarray([[10.0, 12.0], [22.0, 14.0], [18.0, 28.0]], dtype=np.float64))
        self.window.viewer._commit_polygon(polygon)
        self.window.polygon_tools_panel.cmb_edge_backend.setCurrentIndex(3)

        edge_prob = np.zeros((1, *sequence.frame_shape), dtype=np.float32)
        edge_prob[0, 12:28, 10:22] = 0.78
        run_output = DexiNedRunOutput(
            edge_prob=edge_prob,
            edge_binary=edge_prob >= 0.5,
            model_name="ddn",
            checkpoint_name="DDN_M36_BSDS.pth",
        )

        def fake_ddn_run(run_input):
            time.sleep(0.05)
            self.assertEqual(run_input.source_view, "raw")
            return run_output

        with (
            patch.object(self.window._ddn_backend, "run", side_effect=fake_ddn_run) as ddn_run_mock,
            patch.object(
                self.window._dexined_backend,
                "run",
                side_effect=AssertionError("DexiNed backend should not run when DDN is selected."),
            ) as dexined_run_mock,
            patch.object(
                self.window._teed_backend,
                "run",
                side_effect=AssertionError("TEED backend should not run when DDN is selected."),
            ) as teed_run_mock,
            patch.object(
                self.window._nbed_backend,
                "run",
                side_effect=AssertionError("NBED backend should not run when DDN is selected."),
            ) as nbed_run_mock,
        ):
            self.window.polygon_tools_panel.btn_preview.click()
            for _ in range(250):
                self.__class__._app.processEvents()
                if ddn_run_mock.called and self.window._edge_preview_dialog is not None and self.window._edge_preview_dialog.isVisible():
                    break
                time.sleep(0.01)

        ddn_run_mock.assert_called_once()
        dexined_run_mock.assert_not_called()
        teed_run_mock.assert_not_called()
        nbed_run_mock.assert_not_called()
        self.assertIsNotNone(self.window._edge_preview_dialog)
        self.assertTrue(self.window._edge_preview_dialog.isVisible())
        self.assertEqual(self.window._edge_preview_dialog.windowTitle(), "DDN Preview")
        self.assertEqual(self.window.statusBar().currentMessage(), "DDN preview opened for frame 1.")

    def test_edge_preview_can_use_pidinet_backend(self) -> None:
        sequence = load_mpp_sequence(str(SAMPLE_MPP))
        self.window.set_sequence(sequence)

        polygon = PolygonROI(np.asarray([[10.0, 12.0], [22.0, 14.0], [18.0, 28.0]], dtype=np.float64))
        self.window.viewer._commit_polygon(polygon)
        backend_index = self.window.polygon_tools_panel.cmb_edge_backend.findData("pidinet")
        self.assertNotEqual(backend_index, -1)
        self.window.polygon_tools_panel.cmb_edge_backend.setCurrentIndex(backend_index)

        edge_prob = np.zeros((1, *sequence.frame_shape), dtype=np.float32)
        edge_prob[0, 12:28, 10:22] = 0.78
        run_output = DexiNedRunOutput(
            edge_prob=edge_prob,
            edge_binary=edge_prob >= 0.5,
            model_name="pidinet",
            checkpoint_name="table5_pidinet.pth",
        )

        def fake_pidinet_run(run_input):
            time.sleep(0.05)
            self.assertEqual(run_input.source_view, "raw")
            return run_output

        with (
            patch.object(self.window._pidinet_backend, "run", side_effect=fake_pidinet_run) as pidinet_run_mock,
            patch.object(
                self.window._dexined_backend,
                "run",
                side_effect=AssertionError("DexiNed backend should not run when PiDiNet is selected."),
            ) as dexined_run_mock,
            patch.object(
                self.window._teed_backend,
                "run",
                side_effect=AssertionError("TEED backend should not run when PiDiNet is selected."),
            ) as teed_run_mock,
            patch.object(
                self.window._nbed_backend,
                "run",
                side_effect=AssertionError("NBED backend should not run when PiDiNet is selected."),
            ) as nbed_run_mock,
            patch.object(
                self.window._ddn_backend,
                "run",
                side_effect=AssertionError("DDN backend should not run when PiDiNet is selected."),
            ) as ddn_run_mock,
        ):
            self.window.polygon_tools_panel.btn_preview.click()
            self._wait_until(
                lambda: pidinet_run_mock.called
                and self.window._edge_preview_dialog is not None
                and self.window._edge_preview_dialog.isVisible()
            )

        pidinet_run_mock.assert_called_once()
        dexined_run_mock.assert_not_called()
        teed_run_mock.assert_not_called()
        nbed_run_mock.assert_not_called()
        ddn_run_mock.assert_not_called()
        self.assertIsNotNone(self.window._edge_preview_dialog)
        self.assertTrue(self.window._edge_preview_dialog.isVisible())
        self.assertEqual(self.window._edge_preview_dialog.windowTitle(), "PiDiNet Preview")
        self.assertEqual(self.window.statusBar().currentMessage(), "PiDiNet preview opened for frame 1.")

    def test_edge_preview_can_use_uaed_backend(self) -> None:
        sequence = load_mpp_sequence(str(SAMPLE_MPP))
        self.window.set_sequence(sequence)

        polygon = PolygonROI(np.asarray([[10.0, 12.0], [22.0, 14.0], [18.0, 28.0]], dtype=np.float64))
        self.window.viewer._commit_polygon(polygon)
        backend_index = self.window.polygon_tools_panel.cmb_edge_backend.findData("uaed")
        self.assertNotEqual(backend_index, -1)
        self.window.polygon_tools_panel.cmb_edge_backend.setCurrentIndex(backend_index)

        edge_prob = np.zeros((1, *sequence.frame_shape), dtype=np.float32)
        edge_prob[0, 12:28, 10:22] = 0.78
        run_output = DexiNedRunOutput(
            edge_prob=edge_prob,
            edge_binary=edge_prob >= 0.5,
            model_name="uaed",
            checkpoint_name="epoch-19-checkpoint.pth",
        )

        def fake_uaed_run(run_input):
            time.sleep(0.05)
            self.assertEqual(run_input.source_view, "raw")
            return run_output

        with (
            patch.object(self.window._uaed_backend, "run", side_effect=fake_uaed_run) as uaed_run_mock,
            patch.object(
                self.window._dexined_backend,
                "run",
                side_effect=AssertionError("DexiNed backend should not run when UAED is selected."),
            ) as dexined_run_mock,
            patch.object(
                self.window._teed_backend,
                "run",
                side_effect=AssertionError("TEED backend should not run when UAED is selected."),
            ) as teed_run_mock,
            patch.object(
                self.window._nbed_backend,
                "run",
                side_effect=AssertionError("NBED backend should not run when UAED is selected."),
            ) as nbed_run_mock,
            patch.object(
                self.window._ddn_backend,
                "run",
                side_effect=AssertionError("DDN backend should not run when UAED is selected."),
            ) as ddn_run_mock,
            patch.object(
                self.window._pidinet_backend,
                "run",
                side_effect=AssertionError("PiDiNet backend should not run when UAED is selected."),
            ) as pidinet_run_mock,
        ):
            self.window.polygon_tools_panel.btn_preview.click()
            self._wait_until(
                lambda: uaed_run_mock.called
                and self.window._edge_preview_dialog is not None
                and self.window._edge_preview_dialog.isVisible()
            )

        uaed_run_mock.assert_called_once()
        dexined_run_mock.assert_not_called()
        teed_run_mock.assert_not_called()
        nbed_run_mock.assert_not_called()
        ddn_run_mock.assert_not_called()
        pidinet_run_mock.assert_not_called()
        self.assertIsNotNone(self.window._edge_preview_dialog)
        self.assertTrue(self.window._edge_preview_dialog.isVisible())
        self.assertEqual(self.window._edge_preview_dialog.windowTitle(), "UAED Preview")
        self.assertEqual(self.window.statusBar().currentMessage(), "UAED preview opened for frame 1.")

    def test_edge_preview_can_use_muge_backend_with_granularity(self) -> None:
        sequence = load_mpp_sequence(str(SAMPLE_MPP))
        self.window.set_sequence(sequence)

        polygon = PolygonROI(np.asarray([[10.0, 12.0], [22.0, 14.0], [18.0, 28.0]], dtype=np.float64))
        self.window.viewer._commit_polygon(polygon)
        backend_index = self.window.polygon_tools_panel.cmb_edge_backend.findData("muge")
        self.assertNotEqual(backend_index, -1)
        self.assertFalse(self.window.polygon_tools_panel.sp_muge_granularity.isEnabled())
        self.window.polygon_tools_panel.cmb_edge_backend.setCurrentIndex(backend_index)
        self.assertTrue(self.window.polygon_tools_panel.sp_muge_granularity.isEnabled())
        self.window.polygon_tools_panel.sp_muge_granularity.setValue(0.75)

        edge_prob = np.zeros((1, *sequence.frame_shape), dtype=np.float32)
        edge_prob[0, 12:28, 10:22] = 0.78
        run_output = DexiNedRunOutput(
            edge_prob=edge_prob,
            edge_binary=edge_prob >= 0.5,
            model_name="muge",
            checkpoint_name="muge-epoch-19-checkpoint.pth",
        )

        def fake_muge_run(run_input):
            time.sleep(0.05)
            self.assertEqual(run_input.source_view, "raw")
            self.assertAlmostEqual(self.window._muge_backend.config.granularity, 0.75, places=6)
            return run_output

        with (
            patch.object(self.window._muge_backend, "run", side_effect=fake_muge_run) as muge_run_mock,
            patch.object(
                self.window._dexined_backend,
                "run",
                side_effect=AssertionError("DexiNed backend should not run when MuGE is selected."),
            ) as dexined_run_mock,
            patch.object(
                self.window._teed_backend,
                "run",
                side_effect=AssertionError("TEED backend should not run when MuGE is selected."),
            ) as teed_run_mock,
            patch.object(
                self.window._nbed_backend,
                "run",
                side_effect=AssertionError("NBED backend should not run when MuGE is selected."),
            ) as nbed_run_mock,
            patch.object(
                self.window._ddn_backend,
                "run",
                side_effect=AssertionError("DDN backend should not run when MuGE is selected."),
            ) as ddn_run_mock,
            patch.object(
                self.window._pidinet_backend,
                "run",
                side_effect=AssertionError("PiDiNet backend should not run when MuGE is selected."),
            ) as pidinet_run_mock,
            patch.object(
                self.window._uaed_backend,
                "run",
                side_effect=AssertionError("UAED backend should not run when MuGE is selected."),
            ) as uaed_run_mock,
        ):
            self.window.polygon_tools_panel.btn_preview.click()
            self._wait_until(
                lambda: muge_run_mock.called
                and self.window._edge_preview_dialog is not None
                and self.window._edge_preview_dialog.isVisible()
            )

        muge_run_mock.assert_called_once()
        dexined_run_mock.assert_not_called()
        teed_run_mock.assert_not_called()
        nbed_run_mock.assert_not_called()
        ddn_run_mock.assert_not_called()
        pidinet_run_mock.assert_not_called()
        uaed_run_mock.assert_not_called()
        self.assertIsNotNone(self.window._edge_preview_dialog)
        self.assertTrue(self.window._edge_preview_dialog.isVisible())
        self.assertEqual(self.window._edge_preview_dialog.windowTitle(), "MuGE Preview")
        self.assertEqual(self.window.statusBar().currentMessage(), "MuGE preview opened for frame 1.")

    def test_edge_preview_failure_uses_uaed_backend_label(self) -> None:
        sequence = load_mpp_sequence(str(SAMPLE_MPP))
        self.window.set_sequence(sequence)

        polygon = PolygonROI(np.asarray([[10.0, 12.0], [22.0, 14.0], [18.0, 28.0]], dtype=np.float64))
        self.window.viewer._commit_polygon(polygon)
        backend_index = self.window.polygon_tools_panel.cmb_edge_backend.findData("uaed")
        self.assertNotEqual(backend_index, -1)
        self.window.polygon_tools_panel.cmb_edge_backend.setCurrentIndex(backend_index)

        with (
            patch.object(self.window._uaed_backend, "run", side_effect=RuntimeError("UAED worker failed.")) as uaed_run_mock,
            patch.object(
                self.window._dexined_backend,
                "run",
                side_effect=AssertionError("DexiNed backend should not run when UAED is selected."),
            ) as dexined_run_mock,
            patch.object(
                self.window._teed_backend,
                "run",
                side_effect=AssertionError("TEED backend should not run when UAED is selected."),
            ) as teed_run_mock,
            patch.object(
                self.window._nbed_backend,
                "run",
                side_effect=AssertionError("NBED backend should not run when UAED is selected."),
            ) as nbed_run_mock,
            patch.object(
                self.window._ddn_backend,
                "run",
                side_effect=AssertionError("DDN backend should not run when UAED is selected."),
            ) as ddn_run_mock,
            patch.object(
                self.window._pidinet_backend,
                "run",
                side_effect=AssertionError("PiDiNet backend should not run when UAED is selected."),
            ) as pidinet_run_mock,
            patch("nanotrack.ui.main_window.QMessageBox.critical", return_value=QMessageBox.StandardButton.Ok) as critical_mock,
        ):
            self.window.polygon_tools_panel.btn_preview.click()
            self._wait_until(lambda: critical_mock.called)

        uaed_run_mock.assert_called_once()
        dexined_run_mock.assert_not_called()
        teed_run_mock.assert_not_called()
        nbed_run_mock.assert_not_called()
        ddn_run_mock.assert_not_called()
        pidinet_run_mock.assert_not_called()
        critical_mock.assert_called_once()
        self.assertEqual(critical_mock.call_args.args[1], "UAED preview error")
        self.assertIn("UAED worker failed.", critical_mock.call_args.args[2])
        self.assertEqual(self.window.statusBar().currentMessage(), "UAED preview failed.")
        self.assertFalse(self.window.current_edge_tracks())

    def test_edge_sequence_run_creates_edge_track_for_all_frames(self) -> None:
        sequence = STMSequence(
            source_path="/tmp/edge_sequence.mpp",
            raw_frames=np.zeros((3, 32, 32), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=32, pixels_y=32, size_nm_x=32.0, size_nm_y=32.0),
        )
        sequence.raw_frames[0, 10:22, 8:20] = 0.3
        sequence.raw_frames[1, 11:23, 9:21] = 0.5
        sequence.raw_frames[2, 12:24, 10:22] = 0.7
        self.window.set_sequence(sequence)
        self.window.polygon_tools_panel.sp_dexined_threshold.setValue(0.4)
        self.window.polygon_tools_panel.sp_edge_components.setValue(2)
        self.window.polygon_tools_panel.cmb_inference_resolution.setCurrentIndex(2)

        polygon = PolygonROI(np.asarray([[8.0, 10.0], [22.0, 10.0], [24.0, 24.0], [10.0, 26.0]], dtype=np.float64))
        self.window.viewer._commit_polygon(polygon)
        self.assertTrue(self.window.polygon_tools_panel.btn_run_sequence.isEnabled())

        edge_prob = np.zeros((sequence.frame_count, *sequence.frame_shape), dtype=np.float32)
        edge_prob[0, 12:15, 8:21] = 0.72
        edge_prob[0, 9:11, 19:22] = 0.71
        edge_prob[1, 13:16, 9:22] = 0.74
        edge_prob[1, 10:12, 20:23] = 0.73
        edge_prob[2, 14:17, 10:23] = 0.76
        edge_prob[2, 11:13, 21:24] = 0.75
        edge_binary = edge_prob >= 0.5
        run_output = DexiNedRunOutput(
            edge_prob=edge_prob,
            edge_binary=edge_binary,
            model_name="dexined",
            checkpoint_name="DexiNed_BIPED_10.pth",
        )

        def fake_run(run_input):
            time.sleep(0.05)
            self.assertEqual(run_input.frames.shape, sequence.raw_frames.shape)
            np.testing.assert_array_equal(run_input.frames, sequence.raw_frames)
            self.assertEqual(run_input.source_view, "raw")
            self.assertTrue(np.any(run_input.polygon_mask))
            self.assertAlmostEqual(run_input.threshold, 0.4, places=6)
            np.testing.assert_array_equal(run_input.inference_resolution_hw, np.asarray([768, 768], dtype=np.int32))
            return run_output

        with patch.object(self.window._dexined_backend, "run", side_effect=fake_run) as run_mock:
            self.window.polygon_tools_panel.btn_run_sequence.click()
            self.assertIsNotNone(self.window._dexined_progress_dialog)
            self.assertTrue(self.window._dexined_progress_dialog.isVisible())
            for _ in range(250):
                self.__class__._app.processEvents()
                if run_mock.called and self.window.current_edge_tracks():
                    break
                time.sleep(0.01)

        run_mock.assert_called_once()
        edge_tracks = self.window.current_edge_tracks()
        self.assertEqual(len(edge_tracks), 1)
        track = edge_tracks[0]
        self.assertEqual(track.edge_track_id, 1)
        self.assertEqual(track.seed_frame_index, 0)
        self.assertEqual(track.label, "Edge 1")
        self.assertEqual(track.frame_indices, [0, 1, 2])
        self.assertEqual(self.window.current_selected_edge_track_id(), 1)
        for frame_index in range(sequence.frame_count):
            annotation = track.get_annotation(frame_index)
            self.assertIsNotNone(annotation)
            self.assertIsNotNone(annotation.edge_mask)
            self.assertIsNotNone(annotation.polyline)
            self.assertGreaterEqual(annotation.polyline_point_count, 2)
            self.assertIsNotNone(annotation.metrics.length_px)
            self.assertGreater(annotation.metrics.length_px, 0.0)
            self.assertIsNotNone(annotation.metrics.length_nm)
            self.assertGreaterEqual(annotation.metrics.roughness_rms_px, 0.0)
            self.assertGreaterEqual(annotation.metrics.mean_curvature, 0.0)
            self.assertGreaterEqual(annotation.metrics.max_curvature, 0.0)
            self.assertGreaterEqual(annotation.metrics.waviness_amplitude_px, 0.0)
        self.assertGreater(len(self.window.viewer.viewer._overlay_items), 0)
        self.assertIn("Edge Track 1", self.window.statusBar().currentMessage())

        self.window.slider_frame.setValue(2)
        self.__class__._app.processEvents()
        self.assertEqual(sequence.active_frame_index, 2)
        self.assertGreater(len(self.window.viewer.viewer._overlay_items), 0)

    def test_edge_sequence_run_can_use_teed_backend(self) -> None:
        sequence = STMSequence(
            source_path="/tmp/edge_sequence_teed.mpp",
            raw_frames=np.zeros((3, 32, 32), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=32, pixels_y=32, size_nm_x=32.0, size_nm_y=32.0),
        )
        self.window.set_sequence(sequence)
        self.window.polygon_tools_panel.cmb_edge_backend.setCurrentIndex(1)

        polygon = PolygonROI(np.asarray([[8.0, 10.0], [22.0, 10.0], [24.0, 24.0], [10.0, 26.0]], dtype=np.float64))
        self.window.viewer._commit_polygon(polygon)

        edge_prob = np.zeros((sequence.frame_count, *sequence.frame_shape), dtype=np.float32)
        edge_prob[0, 12:15, 8:21] = 0.72
        edge_prob[1, 13:16, 9:22] = 0.74
        edge_prob[2, 14:17, 10:23] = 0.76
        run_output = DexiNedRunOutput(
            edge_prob=edge_prob,
            edge_binary=edge_prob >= 0.5,
            model_name="teed",
            checkpoint_name="5_model.pth",
        )

        def fake_teed_run(run_input):
            time.sleep(0.05)
            self.assertEqual(run_input.frames.shape[0], 3)
            return run_output

        with (
            patch.object(self.window._teed_backend, "run", side_effect=fake_teed_run) as teed_run_mock,
            patch.object(
                self.window._dexined_backend,
                "run",
                side_effect=AssertionError("DexiNed backend should not run when TEED is selected."),
            ) as dexined_run_mock,
        ):
            self.window.polygon_tools_panel.btn_run_sequence.click()
            for _ in range(250):
                self.__class__._app.processEvents()
                if teed_run_mock.called and self.window.current_edge_tracks():
                    break
                time.sleep(0.01)

        teed_run_mock.assert_called_once()
        dexined_run_mock.assert_not_called()
        self.assertEqual(len(self.window.current_edge_tracks()), 1)
        self.assertIn("TEED sequence finished: Edge Track 1", self.window.statusBar().currentMessage())

    def test_edge_sequence_run_can_use_ddn_backend(self) -> None:
        sequence = STMSequence(
            source_path="/tmp/edge_sequence_ddn.mpp",
            raw_frames=np.zeros((3, 32, 32), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=32, pixels_y=32, size_nm_x=32.0, size_nm_y=32.0),
        )
        self.window.set_sequence(sequence)
        self.window.polygon_tools_panel.cmb_edge_backend.setCurrentIndex(3)

        polygon = PolygonROI(np.asarray([[8.0, 10.0], [22.0, 10.0], [24.0, 24.0], [10.0, 26.0]], dtype=np.float64))
        self.window.viewer._commit_polygon(polygon)

        edge_prob = np.zeros((sequence.frame_count, *sequence.frame_shape), dtype=np.float32)
        edge_prob[0, 12:15, 8:21] = 0.72
        edge_prob[1, 13:16, 9:22] = 0.74
        edge_prob[2, 14:17, 10:23] = 0.76
        run_output = DexiNedRunOutput(
            edge_prob=edge_prob,
            edge_binary=edge_prob >= 0.5,
            model_name="ddn",
            checkpoint_name="DDN_M36_BSDS.pth",
        )

        def fake_ddn_run(run_input):
            time.sleep(0.05)
            self.assertEqual(run_input.frames.shape[0], 3)
            return run_output

        with (
            patch.object(self.window._ddn_backend, "run", side_effect=fake_ddn_run) as ddn_run_mock,
            patch.object(
                self.window._dexined_backend,
                "run",
                side_effect=AssertionError("DexiNed backend should not run when DDN is selected."),
            ) as dexined_run_mock,
            patch.object(
                self.window._teed_backend,
                "run",
                side_effect=AssertionError("TEED backend should not run when DDN is selected."),
            ) as teed_run_mock,
            patch.object(
                self.window._nbed_backend,
                "run",
                side_effect=AssertionError("NBED backend should not run when DDN is selected."),
            ) as nbed_run_mock,
        ):
            self.window.polygon_tools_panel.btn_run_sequence.click()
            for _ in range(250):
                self.__class__._app.processEvents()
                if ddn_run_mock.called and self.window.current_edge_tracks():
                    break
                time.sleep(0.01)

        ddn_run_mock.assert_called_once()
        dexined_run_mock.assert_not_called()
        teed_run_mock.assert_not_called()
        nbed_run_mock.assert_not_called()
        self.assertEqual(len(self.window.current_edge_tracks()), 1)
        self.assertIn("DDN sequence finished: Edge Track 1", self.window.statusBar().currentMessage())

    def test_edge_sequence_run_can_use_pidinet_backend(self) -> None:
        sequence = STMSequence(
            source_path="/tmp/edge_sequence_pidinet.mpp",
            raw_frames=np.zeros((3, 32, 32), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=32, pixels_y=32, size_nm_x=32.0, size_nm_y=32.0),
        )
        self.window.set_sequence(sequence)
        backend_index = self.window.polygon_tools_panel.cmb_edge_backend.findData("pidinet")
        self.assertNotEqual(backend_index, -1)
        self.window.polygon_tools_panel.cmb_edge_backend.setCurrentIndex(backend_index)

        polygon = PolygonROI(np.asarray([[8.0, 10.0], [22.0, 10.0], [24.0, 24.0], [10.0, 26.0]], dtype=np.float64))
        self.window.viewer._commit_polygon(polygon)

        edge_prob = np.zeros((sequence.frame_count, *sequence.frame_shape), dtype=np.float32)
        edge_prob[0, 12:15, 8:21] = 0.72
        edge_prob[1, 13:16, 9:22] = 0.74
        edge_prob[2, 14:17, 10:23] = 0.76
        run_output = DexiNedRunOutput(
            edge_prob=edge_prob,
            edge_binary=edge_prob >= 0.5,
            model_name="pidinet",
            checkpoint_name="table5_pidinet.pth",
        )

        def fake_pidinet_run(run_input):
            time.sleep(0.05)
            self.assertEqual(run_input.frames.shape[0], 3)
            return run_output

        with (
            patch.object(self.window._pidinet_backend, "run", side_effect=fake_pidinet_run) as pidinet_run_mock,
            patch.object(
                self.window._dexined_backend,
                "run",
                side_effect=AssertionError("DexiNed backend should not run when PiDiNet is selected."),
            ) as dexined_run_mock,
            patch.object(
                self.window._teed_backend,
                "run",
                side_effect=AssertionError("TEED backend should not run when PiDiNet is selected."),
            ) as teed_run_mock,
            patch.object(
                self.window._nbed_backend,
                "run",
                side_effect=AssertionError("NBED backend should not run when PiDiNet is selected."),
            ) as nbed_run_mock,
            patch.object(
                self.window._ddn_backend,
                "run",
                side_effect=AssertionError("DDN backend should not run when PiDiNet is selected."),
            ) as ddn_run_mock,
        ):
            self.window.polygon_tools_panel.btn_run_sequence.click()
            self._wait_until(lambda: pidinet_run_mock.called and self.window.current_edge_tracks())

        pidinet_run_mock.assert_called_once()
        dexined_run_mock.assert_not_called()
        teed_run_mock.assert_not_called()
        nbed_run_mock.assert_not_called()
        ddn_run_mock.assert_not_called()
        self.assertEqual(len(self.window.current_edge_tracks()), 1)
        self.assertIn("PiDiNet sequence finished: Edge Track 1", self.window.statusBar().currentMessage())

    def test_edge_sequence_run_can_use_uaed_backend(self) -> None:
        sequence = STMSequence(
            source_path="/tmp/edge_sequence_uaed.mpp",
            raw_frames=np.zeros((3, 32, 32), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=32, pixels_y=32, size_nm_x=32.0, size_nm_y=32.0),
        )
        self.window.set_sequence(sequence)
        backend_index = self.window.polygon_tools_panel.cmb_edge_backend.findData("uaed")
        self.assertNotEqual(backend_index, -1)
        self.window.polygon_tools_panel.cmb_edge_backend.setCurrentIndex(backend_index)

        polygon = PolygonROI(np.asarray([[8.0, 10.0], [22.0, 10.0], [24.0, 24.0], [10.0, 26.0]], dtype=np.float64))
        self.window.viewer._commit_polygon(polygon)

        edge_prob = np.zeros((sequence.frame_count, *sequence.frame_shape), dtype=np.float32)
        edge_prob[0, 12:15, 8:21] = 0.72
        edge_prob[1, 13:16, 9:22] = 0.74
        edge_prob[2, 14:17, 10:23] = 0.76
        run_output = DexiNedRunOutput(
            edge_prob=edge_prob,
            edge_binary=edge_prob >= 0.5,
            model_name="uaed",
            checkpoint_name="epoch-19-checkpoint.pth",
        )

        def fake_uaed_run(run_input):
            time.sleep(0.05)
            self.assertEqual(run_input.frames.shape[0], 3)
            return run_output

        with (
            patch.object(self.window._uaed_backend, "run", side_effect=fake_uaed_run) as uaed_run_mock,
            patch.object(
                self.window._dexined_backend,
                "run",
                side_effect=AssertionError("DexiNed backend should not run when UAED is selected."),
            ) as dexined_run_mock,
            patch.object(
                self.window._teed_backend,
                "run",
                side_effect=AssertionError("TEED backend should not run when UAED is selected."),
            ) as teed_run_mock,
            patch.object(
                self.window._nbed_backend,
                "run",
                side_effect=AssertionError("NBED backend should not run when UAED is selected."),
            ) as nbed_run_mock,
            patch.object(
                self.window._ddn_backend,
                "run",
                side_effect=AssertionError("DDN backend should not run when UAED is selected."),
            ) as ddn_run_mock,
            patch.object(
                self.window._pidinet_backend,
                "run",
                side_effect=AssertionError("PiDiNet backend should not run when UAED is selected."),
            ) as pidinet_run_mock,
        ):
            self.window.polygon_tools_panel.btn_run_sequence.click()
            self._wait_until(lambda: uaed_run_mock.called and self.window.current_edge_tracks())

        uaed_run_mock.assert_called_once()
        dexined_run_mock.assert_not_called()
        teed_run_mock.assert_not_called()
        nbed_run_mock.assert_not_called()
        ddn_run_mock.assert_not_called()
        pidinet_run_mock.assert_not_called()
        self.assertEqual(len(self.window.current_edge_tracks()), 1)
        self.assertIn("UAED sequence finished: Edge Track 1", self.window.statusBar().currentMessage())

    def test_edge_sequence_run_can_use_muge_backend_with_granularity(self) -> None:
        sequence = STMSequence(
            source_path="/tmp/edge_sequence_muge.mpp",
            raw_frames=np.zeros((3, 32, 32), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=32, pixels_y=32, size_nm_x=32.0, size_nm_y=32.0),
        )
        self.window.set_sequence(sequence)
        backend_index = self.window.polygon_tools_panel.cmb_edge_backend.findData("muge")
        self.assertNotEqual(backend_index, -1)
        self.window.polygon_tools_panel.cmb_edge_backend.setCurrentIndex(backend_index)
        self.window.polygon_tools_panel.sp_muge_granularity.setValue(0.25)

        polygon = PolygonROI(np.asarray([[8.0, 10.0], [22.0, 10.0], [24.0, 24.0], [10.0, 26.0]], dtype=np.float64))
        self.window.viewer._commit_polygon(polygon)

        edge_prob = np.zeros((sequence.frame_count, *sequence.frame_shape), dtype=np.float32)
        edge_prob[0, 12:15, 8:21] = 0.72
        edge_prob[1, 13:16, 9:22] = 0.74
        edge_prob[2, 14:17, 10:23] = 0.76
        run_output = DexiNedRunOutput(
            edge_prob=edge_prob,
            edge_binary=edge_prob >= 0.5,
            model_name="muge",
            checkpoint_name="muge-epoch-19-checkpoint.pth",
        )

        def fake_muge_run(run_input):
            time.sleep(0.05)
            self.assertEqual(run_input.frames.shape[0], 3)
            self.assertAlmostEqual(self.window._muge_backend.config.granularity, 0.25, places=6)
            return run_output

        with (
            patch.object(self.window._muge_backend, "run", side_effect=fake_muge_run) as muge_run_mock,
            patch.object(
                self.window._dexined_backend,
                "run",
                side_effect=AssertionError("DexiNed backend should not run when MuGE is selected."),
            ) as dexined_run_mock,
            patch.object(
                self.window._teed_backend,
                "run",
                side_effect=AssertionError("TEED backend should not run when MuGE is selected."),
            ) as teed_run_mock,
            patch.object(
                self.window._nbed_backend,
                "run",
                side_effect=AssertionError("NBED backend should not run when MuGE is selected."),
            ) as nbed_run_mock,
            patch.object(
                self.window._ddn_backend,
                "run",
                side_effect=AssertionError("DDN backend should not run when MuGE is selected."),
            ) as ddn_run_mock,
            patch.object(
                self.window._pidinet_backend,
                "run",
                side_effect=AssertionError("PiDiNet backend should not run when MuGE is selected."),
            ) as pidinet_run_mock,
            patch.object(
                self.window._uaed_backend,
                "run",
                side_effect=AssertionError("UAED backend should not run when MuGE is selected."),
            ) as uaed_run_mock,
        ):
            self.window.polygon_tools_panel.btn_run_sequence.click()
            self._wait_until(lambda: muge_run_mock.called and self.window.current_edge_tracks())

        muge_run_mock.assert_called_once()
        dexined_run_mock.assert_not_called()
        teed_run_mock.assert_not_called()
        nbed_run_mock.assert_not_called()
        ddn_run_mock.assert_not_called()
        pidinet_run_mock.assert_not_called()
        uaed_run_mock.assert_not_called()
        self.assertEqual(len(self.window.current_edge_tracks()), 1)
        self.assertIn("MuGE sequence finished: Edge Track 1", self.window.statusBar().currentMessage())

    def test_edge_sequence_failure_uses_muge_backend_label_and_granularity(self) -> None:
        sequence = STMSequence(
            source_path="/tmp/edge_sequence_muge_failure.mpp",
            raw_frames=np.zeros((3, 32, 32), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=32, pixels_y=32, size_nm_x=32.0, size_nm_y=32.0),
        )
        self.window.set_sequence(sequence)
        backend_index = self.window.polygon_tools_panel.cmb_edge_backend.findData("muge")
        self.assertNotEqual(backend_index, -1)
        self.window.polygon_tools_panel.cmb_edge_backend.setCurrentIndex(backend_index)
        self.window.polygon_tools_panel.sp_muge_granularity.setValue(0.9)

        polygon = PolygonROI(np.asarray([[8.0, 10.0], [22.0, 10.0], [24.0, 24.0], [10.0, 26.0]], dtype=np.float64))
        self.window.viewer._commit_polygon(polygon)

        observed_granularity: list[float] = []

        def fail_muge_run(run_input):
            observed_granularity.append(float(self.window._muge_backend.config.granularity))
            raise RuntimeError("MuGE worker failed.")

        with (
            patch.object(self.window._muge_backend, "run", side_effect=fail_muge_run) as muge_run_mock,
            patch.object(
                self.window._dexined_backend,
                "run",
                side_effect=AssertionError("DexiNed backend should not run when MuGE is selected."),
            ) as dexined_run_mock,
            patch.object(
                self.window._teed_backend,
                "run",
                side_effect=AssertionError("TEED backend should not run when MuGE is selected."),
            ) as teed_run_mock,
            patch.object(
                self.window._nbed_backend,
                "run",
                side_effect=AssertionError("NBED backend should not run when MuGE is selected."),
            ) as nbed_run_mock,
            patch.object(
                self.window._ddn_backend,
                "run",
                side_effect=AssertionError("DDN backend should not run when MuGE is selected."),
            ) as ddn_run_mock,
            patch.object(
                self.window._pidinet_backend,
                "run",
                side_effect=AssertionError("PiDiNet backend should not run when MuGE is selected."),
            ) as pidinet_run_mock,
            patch.object(
                self.window._uaed_backend,
                "run",
                side_effect=AssertionError("UAED backend should not run when MuGE is selected."),
            ) as uaed_run_mock,
            patch("nanotrack.ui.main_window.QMessageBox.critical", return_value=QMessageBox.StandardButton.Ok) as critical_mock,
        ):
            self.window.polygon_tools_panel.btn_run_sequence.click()
            self._wait_until(lambda: critical_mock.called)

        muge_run_mock.assert_called_once()
        dexined_run_mock.assert_not_called()
        teed_run_mock.assert_not_called()
        nbed_run_mock.assert_not_called()
        ddn_run_mock.assert_not_called()
        pidinet_run_mock.assert_not_called()
        uaed_run_mock.assert_not_called()
        self.assertEqual(observed_granularity, [0.9])
        critical_mock.assert_called_once()
        self.assertEqual(critical_mock.call_args.args[1], "MuGE sequence error")
        self.assertIn("MuGE worker failed.", critical_mock.call_args.args[2])
        self.assertEqual(self.window.statusBar().currentMessage(), "MuGE sequence failed.")
        self.assertFalse(self.window.current_edge_tracks())

    def test_all_edge_backends_feed_common_edge_prob_workflow(self) -> None:
        backend_specs = [
            ("dexined", "_dexined_backend", "DexiNed", "DexiNed_BIPED_10.pth"),
            ("teed", "_teed_backend", "TEED", "5_model.pth"),
            ("nbed", "_nbed_backend", "NBED", "NBED_BSDS.pth"),
            ("ddn", "_ddn_backend", "DDN", "DDN_M36_BSDS.pth"),
            ("pidinet", "_pidinet_backend", "PiDiNet", "table5_pidinet.pth"),
            ("uaed", "_uaed_backend", "UAED", "epoch-19-checkpoint.pth"),
            ("muge", "_muge_backend", "MuGE", "muge-epoch-19-checkpoint.pth"),
        ]
        baseline_polylines: dict[int, np.ndarray] | None = None
        baseline_mask_counts: dict[int, int] | None = None

        for backend_key, backend_attr, backend_label, checkpoint_name in backend_specs:
            with self.subTest(backend=backend_key):
                sequence = STMSequence(
                    source_path=f"/tmp/edge_sequence_{backend_key}_common.mpp",
                    raw_frames=np.zeros((3, 32, 32), dtype=np.float32),
                    metadata=STMSequenceMetadata(pixels_x=32, pixels_y=32, size_nm_x=32.0, size_nm_y=32.0),
                )
                sequence.raw_frames[0, 10:22, 8:20] = 0.25
                sequence.raw_frames[1, 11:23, 9:21] = 0.5
                sequence.raw_frames[2, 12:24, 10:22] = 0.75
                self.window.set_sequence(sequence)
                self.window.polygon_tools_panel.sp_dexined_threshold.setValue(0.5)
                self.window.polygon_tools_panel.sp_edge_components.setValue(1)

                backend_index = self.window.polygon_tools_panel.cmb_edge_backend.findData(backend_key)
                self.assertNotEqual(backend_index, -1)
                self.window.polygon_tools_panel.cmb_edge_backend.setCurrentIndex(backend_index)
                if backend_key == "muge":
                    self.window.polygon_tools_panel.sp_muge_granularity.setValue(0.65)

                polygon = PolygonROI(
                    np.asarray([[8.0, 10.0], [22.0, 10.0], [24.0, 24.0], [10.0, 26.0]], dtype=np.float64)
                )
                self.window.viewer._commit_polygon(polygon)

                run_output = self._edge_probability_output(
                    sequence.frame_count,
                    sequence.frame_shape,
                    model_name=backend_key,
                    checkpoint_name=checkpoint_name,
                    start_row=12,
                    start_col=8,
                )
                captured_inputs = []

                def selected_run(run_input):
                    time.sleep(0.01)
                    captured_inputs.append(run_input)
                    return run_output

                with ExitStack() as stack:
                    backend_mocks = {}
                    for spec_key, spec_attr, _spec_label, _spec_checkpoint_name in backend_specs:
                        backend = getattr(self.window, spec_attr)
                        if spec_key == backend_key:
                            side_effect = selected_run
                        else:
                            side_effect = AssertionError(
                                f"{spec_key} backend should not run when {backend_key} is selected."
                            )
                        backend_mocks[spec_key] = stack.enter_context(
                            patch.object(backend, "run", side_effect=side_effect)
                        )

                    self.window.polygon_tools_panel.btn_run_sequence.click()
                    self._wait_until(
                        lambda: len(self.window.current_edge_tracks()) == 1 and self.window._dexined_thread is None,
                        attempts=500,
                    )

                backend_mocks[backend_key].assert_called_once()
                for spec_key, mock in backend_mocks.items():
                    if spec_key != backend_key:
                        mock.assert_not_called()
                self.assertEqual(len(captured_inputs), 1)
                run_input = captured_inputs[0]
                self.assertEqual(run_input.frames.shape, sequence.raw_frames.shape)
                np.testing.assert_array_equal(run_input.frames, sequence.raw_frames)
                self.assertEqual(run_input.source_view, "raw")
                self.assertEqual(run_input.threshold, 0.5)
                self.assertTrue(np.any(run_input.polygon_mask))
                if backend_key == "muge":
                    self.assertAlmostEqual(self.window._muge_backend.config.granularity, 0.65, places=6)

                tracks = self.window.current_edge_tracks()
                self.assertEqual(len(tracks), 1)
                track = tracks[0]
                self.assertEqual(track.edge_track_id, 1)
                self.assertEqual(track.frame_indices, [0, 1, 2])
                self.assertIn(f"{backend_label} sequence finished: Edge Track 1", self.window.statusBar().currentMessage())

                current_polylines = {}
                current_mask_counts = {}
                for frame_index in range(sequence.frame_count):
                    annotation = track.get_annotation(frame_index)
                    self.assertIsNotNone(annotation)
                    assert annotation is not None
                    self.assertEqual(annotation.source, EdgeAnnotationSource.DEXINED)
                    self.assertIsNotNone(annotation.edge_mask)
                    self.assertIsNotNone(annotation.polyline)
                    self.assertIsNotNone(annotation.metrics)
                    self.assertGreater(annotation.polyline_point_count, 1)
                    self.assertGreater(annotation.metrics.length_px, 0.0)
                    current_polylines[frame_index] = np.asarray(annotation.polyline, dtype=np.float64)
                    current_mask_counts[frame_index] = int(np.count_nonzero(annotation.edge_mask))

                if baseline_polylines is None:
                    baseline_polylines = current_polylines
                    baseline_mask_counts = current_mask_counts
                else:
                    assert baseline_mask_counts is not None
                    self.assertEqual(current_mask_counts, baseline_mask_counts)
                    for frame_index, baseline_polyline in baseline_polylines.items():
                        np.testing.assert_allclose(current_polylines[frame_index], baseline_polyline, atol=1e-9)

    def test_edge_stitch_can_use_selected_alternative_backend(self) -> None:
        sequence = STMSequence(
            source_path="/tmp/edge_stitch_backend_ddn.mpp",
            raw_frames=np.zeros((5, 32, 32), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=32, pixels_y=32, size_nm_x=32.0, size_nm_y=32.0),
        )
        self.window.set_sequence(sequence)
        track = self._set_existing_edge_track(sequence, frame_indices=[0, 1])

        self.window.slider_frame.setValue(1)
        self.__class__._app.processEvents()
        stitched_polygon = PolygonROI(
            np.asarray([[7.0, 9.0], [25.0, 9.0], [25.0, 25.0], [9.0, 27.0]], dtype=np.float64)
        )
        self.window.viewer._commit_polygon(stitched_polygon)
        self.window.polygon_tools_panel.cmb_edge_backend.setCurrentIndex(3)
        self.window.polygon_tools_panel.chk_stitch_active.setChecked(True)
        self.window.polygon_tools_panel.sp_run_end_frame.setValue(4)

        stitch_output = self._edge_probability_output(2, sequence.frame_shape, start_row=13, start_col=10)

        def fake_ddn_run(run_input):
            self.assertEqual(run_input.frames.shape[0], 2)
            np.testing.assert_array_equal(run_input.frame_indices, np.asarray([2, 3], dtype=np.int32))
            return stitch_output

        with (
            patch.object(self.window._ddn_backend, "run", side_effect=fake_ddn_run) as ddn_run_mock,
            patch.object(
                self.window._dexined_backend,
                "run",
                side_effect=AssertionError("DexiNed backend should not run when DDN is selected."),
            ) as dexined_run_mock,
            patch.object(
                self.window._teed_backend,
                "run",
                side_effect=AssertionError("TEED backend should not run when DDN is selected."),
            ) as teed_run_mock,
            patch.object(
                self.window._nbed_backend,
                "run",
                side_effect=AssertionError("NBED backend should not run when DDN is selected."),
            ) as nbed_run_mock,
        ):
            self.window.polygon_tools_panel.btn_run_sequence.click()
            self._wait_until(lambda: ddn_run_mock.called and track.get_annotation(3) is not None)

        ddn_run_mock.assert_called_once()
        dexined_run_mock.assert_not_called()
        teed_run_mock.assert_not_called()
        nbed_run_mock.assert_not_called()
        self.assertEqual(track.frame_indices, [0, 1, 2, 3])
        self.assertEqual(self.window.current_selected_edge_track_id(), track.edge_track_id)
        self.assertIn("stitched edge track 1", self.window.statusBar().currentMessage().lower())

    def test_edge_resume_can_use_selected_alternative_backend(self) -> None:
        sequence = STMSequence(
            source_path="/tmp/edge_resume_backend_ddn.mpp",
            raw_frames=np.zeros((4, 32, 32), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=32, pixels_y=32, size_nm_x=32.0, size_nm_y=32.0),
        )
        self.window.set_sequence(sequence)
        track = self._set_existing_edge_track(sequence, frame_indices=[0, 1, 2, 3])
        original_frame3_polyline = np.asarray(track.get_annotation(3).polyline, dtype=np.float64)

        self.window.slider_frame.setValue(1)
        self.__class__._app.processEvents()
        self.window.viewer._commit_polygon(track.polygon_roi)
        self.window.polygon_tools_panel.cmb_edge_backend.setCurrentIndex(3)
        self.assertTrue(self.window.polygon_tools_panel.btn_resume_edge.isEnabled())

        resume_output = self._edge_probability_output(2, sequence.frame_shape, start_row=14, start_col=11)

        def fake_ddn_run(run_input):
            self.assertEqual(run_input.frames.shape[0], 2)
            self.assertIsNone(run_input.frame_indices)
            return resume_output

        with (
            patch.object(self.window._ddn_backend, "run", side_effect=fake_ddn_run) as ddn_run_mock,
            patch.object(
                self.window._dexined_backend,
                "run",
                side_effect=AssertionError("DexiNed backend should not run when DDN is selected."),
            ) as dexined_run_mock,
            patch.object(
                self.window._teed_backend,
                "run",
                side_effect=AssertionError("TEED backend should not run when DDN is selected."),
            ) as teed_run_mock,
            patch.object(
                self.window._nbed_backend,
                "run",
                side_effect=AssertionError("NBED backend should not run when DDN is selected."),
            ) as nbed_run_mock,
        ):
            self.window.polygon_tools_panel.btn_resume_edge.click()
            self._wait_until(
                lambda: ddn_run_mock.called
                and not np.array_equal(track.get_annotation(3).polyline, original_frame3_polyline)
            )

        ddn_run_mock.assert_called_once()
        dexined_run_mock.assert_not_called()
        teed_run_mock.assert_not_called()
        nbed_run_mock.assert_not_called()
        self.assertEqual(track.frame_indices, [0, 1, 2, 3])
        self.assertFalse(np.array_equal(track.get_annotation(3).polyline, original_frame3_polyline))
        self.assertIn("resumed edge tracking with ddn", self.window.statusBar().currentMessage().lower())

    def test_edge_redetect_can_use_selected_alternative_backend(self) -> None:
        sequence = STMSequence(
            source_path="/tmp/edge_redetect_backend_ddn.mpp",
            raw_frames=np.zeros((4, 32, 32), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=32, pixels_y=32, size_nm_x=32.0, size_nm_y=32.0),
        )
        self.window.set_sequence(sequence)
        track = self._set_existing_edge_track(sequence, frame_indices=[0, 1, 2])
        original_frame2_polyline = np.asarray(track.get_annotation(2).polyline, dtype=np.float64)
        self.window.polygon_tools_panel.cmb_edge_backend.setCurrentIndex(3)
        self.assertTrue(self.window.polygon_tools_panel.btn_redetect_edge.isEnabled())

        redetect_output = self._edge_probability_output(3, sequence.frame_shape, start_row=13, start_col=7)

        def fake_ddn_run(run_input):
            self.assertEqual(run_input.frames.shape[0], 3)
            np.testing.assert_array_equal(run_input.frame_indices, np.asarray([0, 1, 2], dtype=np.int32))
            return redetect_output

        with (
            patch.object(self.window._ddn_backend, "run", side_effect=fake_ddn_run) as ddn_run_mock,
            patch.object(
                self.window._dexined_backend,
                "run",
                side_effect=AssertionError("DexiNed backend should not run when DDN is selected."),
            ) as dexined_run_mock,
            patch.object(
                self.window._teed_backend,
                "run",
                side_effect=AssertionError("TEED backend should not run when DDN is selected."),
            ) as teed_run_mock,
            patch.object(
                self.window._nbed_backend,
                "run",
                side_effect=AssertionError("NBED backend should not run when DDN is selected."),
            ) as nbed_run_mock,
        ):
            self.window.polygon_tools_panel.btn_redetect_edge.click()
            self._wait_until(
                lambda: ddn_run_mock.called
                and not np.array_equal(track.get_annotation(2).polyline, original_frame2_polyline)
            )

        ddn_run_mock.assert_called_once()
        dexined_run_mock.assert_not_called()
        teed_run_mock.assert_not_called()
        nbed_run_mock.assert_not_called()
        self.assertEqual(len(self.window.current_edge_tracks()), 1)
        self.assertEqual(track.frame_indices, [0, 1, 2])
        self.assertFalse(np.array_equal(track.get_annotation(2).polyline, original_frame2_polyline))
        self.assertEqual(self.window.current_selected_edge_track_id(), track.edge_track_id)
        self.assertIn("re-detected edge track 1", self.window.statusBar().currentMessage().lower())

    def test_edge_partial_redetect_can_use_selected_alternative_backend(self) -> None:
        sequence = STMSequence(
            source_path="/tmp/edge_partial_redetect_backend_ddn.mpp",
            raw_frames=np.zeros((5, 32, 32), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=32, pixels_y=32, size_nm_x=32.0, size_nm_y=32.0),
        )
        self.window.set_sequence(sequence)
        track = self._set_existing_edge_track(sequence, frame_indices=[0, 1, 2, 3, 4])
        original_frame0_polyline = np.asarray(track.get_annotation(0).polyline, dtype=np.float64)
        original_frame3_polyline = np.asarray(track.get_annotation(3).polyline, dtype=np.float64)
        original_frame4_polyline = np.asarray(track.get_annotation(4).polyline, dtype=np.float64)

        self.window.slider_frame.setValue(2)
        self.__class__._app.processEvents()
        self.window.polygon_tools_panel.cmb_edge_backend.setCurrentIndex(3)
        self.window.polygon_tools_panel.sp_run_end_frame.setValue(4)
        self.assertTrue(self.window.polygon_tools_panel.btn_redetect_edge_range.isEnabled())

        redetect_output = self._edge_probability_output(2, sequence.frame_shape, start_row=12, start_col=9)

        def fake_ddn_run(run_input):
            self.assertEqual(run_input.frames.shape[0], 2)
            np.testing.assert_array_equal(run_input.frame_indices, np.asarray([2, 3], dtype=np.int32))
            return redetect_output

        with (
            patch.object(self.window._ddn_backend, "run", side_effect=fake_ddn_run) as ddn_run_mock,
            patch.object(
                self.window._dexined_backend,
                "run",
                side_effect=AssertionError("DexiNed backend should not run when DDN is selected."),
            ) as dexined_run_mock,
            patch.object(
                self.window._teed_backend,
                "run",
                side_effect=AssertionError("TEED backend should not run when DDN is selected."),
            ) as teed_run_mock,
            patch.object(
                self.window._nbed_backend,
                "run",
                side_effect=AssertionError("NBED backend should not run when DDN is selected."),
            ) as nbed_run_mock,
        ):
            self.window.polygon_tools_panel.btn_redetect_edge_range.click()
            self._wait_until(
                lambda: ddn_run_mock.called
                and not np.array_equal(track.get_annotation(3).polyline, original_frame3_polyline)
            )

        ddn_run_mock.assert_called_once()
        dexined_run_mock.assert_not_called()
        teed_run_mock.assert_not_called()
        nbed_run_mock.assert_not_called()
        self.assertEqual(track.frame_indices, [0, 1, 2, 3, 4])
        np.testing.assert_array_equal(track.get_annotation(0).polyline, original_frame0_polyline)
        self.assertFalse(np.array_equal(track.get_annotation(3).polyline, original_frame3_polyline))
        np.testing.assert_array_equal(track.get_annotation(4).polyline, original_frame4_polyline)
        self.assertEqual(self.window.current_selected_edge_track_id(), track.edge_track_id)
        self.assertIn("partially re-detected edge track 1", self.window.statusBar().currentMessage().lower())

    def test_edge_sequence_run_can_be_limited_to_selected_frame_range(self) -> None:
        sequence = STMSequence(
            source_path="/tmp/edge_sequence_range.mpp",
            raw_frames=np.zeros((5, 32, 32), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=32, pixels_y=32, size_nm_x=32.0, size_nm_y=32.0),
        )
        self.window.set_sequence(sequence)

        polygon = PolygonROI(np.asarray([[8.0, 10.0], [22.0, 10.0], [24.0, 24.0], [10.0, 26.0]], dtype=np.float64))
        self.window.viewer._commit_polygon(polygon)
        self.window.polygon_tools_panel.sp_run_end_frame.setValue(3)

        edge_prob = np.zeros((3, *sequence.frame_shape), dtype=np.float32)
        edge_prob[0, 12:15, 8:21] = 0.72
        edge_prob[1, 13:16, 9:22] = 0.74
        edge_prob[2, 14:17, 10:23] = 0.76
        run_output = DexiNedRunOutput(
            edge_prob=edge_prob,
            edge_binary=edge_prob >= 0.5,
            model_name="dexined",
            checkpoint_name="DexiNed_BIPED_10.pth",
        )

        def fake_run(run_input):
            self.assertEqual(run_input.frames.shape[0], 3)
            np.testing.assert_array_equal(run_input.frame_indices, np.asarray([0, 1, 2], dtype=np.int32))
            return run_output

        with patch.object(self.window._dexined_backend, "run", side_effect=fake_run) as run_mock:
            self.window.polygon_tools_panel.btn_run_sequence.click()
            for _ in range(250):
                self.__class__._app.processEvents()
                if run_mock.called and self.window.current_edge_tracks():
                    break
                time.sleep(0.01)

        run_mock.assert_called_once()
        edge_tracks = self.window.current_edge_tracks()
        self.assertEqual(len(edge_tracks), 1)
        track = edge_tracks[0]
        self.assertEqual(track.frame_indices, [0, 1, 2])
        self.assertEqual(track.seed_frame_index, 0)
        self.assertIsNone(track.get_annotation(3))
        self.assertIsNone(track.get_annotation(4))

    def test_edge_sequence_cancel_stops_worker_without_creating_track(self) -> None:
        sequence = STMSequence(
            source_path="/tmp/edge_sequence_cancel.mpp",
            raw_frames=np.zeros((4, 32, 32), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=32, pixels_y=32, size_nm_x=32.0, size_nm_y=32.0),
        )
        self.window.set_sequence(sequence)

        polygon = PolygonROI(np.asarray([[8.0, 10.0], [22.0, 10.0], [24.0, 24.0], [10.0, 26.0]], dtype=np.float64))
        self.window.viewer._commit_polygon(polygon)
        self.window.polygon_tools_panel.sp_run_end_frame.setValue(4)

        fake_backend = _FakeCancelableEdgeBackend()
        self.window._dexined_backend = fake_backend

        self.window.polygon_tools_panel.btn_run_sequence.click()
        self._cancel_active_edge_operation(fake_backend)

        self.assertEqual(fake_backend.run_input.frames.shape[0], 4)
        np.testing.assert_array_equal(fake_backend.run_input.frame_indices, np.asarray([0, 1, 2, 3], dtype=np.int32))
        self.assertEqual(self.window.current_edge_tracks(), [])

    def test_edge_resume_cancel_keeps_existing_track_annotations(self) -> None:
        sequence = STMSequence(
            source_path="/tmp/edge_resume_cancel.mpp",
            raw_frames=np.zeros((4, 32, 32), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=32, pixels_y=32, size_nm_x=32.0, size_nm_y=32.0),
        )
        self.window.set_sequence(sequence)
        track = self._set_existing_edge_track(sequence, frame_indices=[0, 1, 2, 3])
        snapshot = self._snapshot_edge_track(track)

        self.window.slider_frame.setValue(1)
        self.__class__._app.processEvents()
        self.window.viewer._commit_polygon(track.polygon_roi)
        self.assertTrue(self.window.polygon_tools_panel.btn_resume_edge.isEnabled())

        fake_backend = _FakeCancelableEdgeBackend()
        self.window._dexined_backend = fake_backend

        self.window.polygon_tools_panel.btn_resume_edge.click()
        self._cancel_active_edge_operation(fake_backend)

        self.assertEqual(fake_backend.run_input.frames.shape[0], 2)
        self.assertIsNone(fake_backend.run_input.frame_indices)
        self.assertEqual(len(self.window.current_edge_tracks()), 1)
        self._assert_edge_track_matches_snapshot(track, snapshot)
        self.assertEqual(self.window.current_selected_edge_track_id(), track.edge_track_id)

    def test_edge_redetect_cancel_keeps_existing_track_annotations(self) -> None:
        sequence = STMSequence(
            source_path="/tmp/edge_redetect_cancel.mpp",
            raw_frames=np.zeros((4, 32, 32), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=32, pixels_y=32, size_nm_x=32.0, size_nm_y=32.0),
        )
        self.window.set_sequence(sequence)
        track = self._set_existing_edge_track(sequence, frame_indices=[0, 1, 2])
        snapshot = self._snapshot_edge_track(track)
        self.assertTrue(self.window.polygon_tools_panel.btn_redetect_edge.isEnabled())

        fake_backend = _FakeCancelableEdgeBackend()
        self.window._dexined_backend = fake_backend

        self.window.polygon_tools_panel.btn_redetect_edge.click()
        self._cancel_active_edge_operation(fake_backend)

        self.assertEqual(fake_backend.run_input.frames.shape[0], 3)
        np.testing.assert_array_equal(fake_backend.run_input.frame_indices, np.asarray([0, 1, 2], dtype=np.int32))
        self.assertEqual(len(self.window.current_edge_tracks()), 1)
        self._assert_edge_track_matches_snapshot(track, snapshot)
        self.assertEqual(self.window.current_selected_edge_track_id(), track.edge_track_id)

    def test_edge_partial_redetect_cancel_keeps_existing_track_annotations(self) -> None:
        sequence = STMSequence(
            source_path="/tmp/edge_partial_redetect_cancel.mpp",
            raw_frames=np.zeros((5, 32, 32), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=32, pixels_y=32, size_nm_x=32.0, size_nm_y=32.0),
        )
        self.window.set_sequence(sequence)
        track = self._set_existing_edge_track(sequence, frame_indices=[0, 1, 2, 3, 4])
        snapshot = self._snapshot_edge_track(track)

        self.window.slider_frame.setValue(1)
        self.__class__._app.processEvents()
        self.window.polygon_tools_panel.sp_run_end_frame.setValue(4)
        self.assertTrue(self.window.polygon_tools_panel.btn_redetect_edge_range.isEnabled())

        fake_backend = _FakeCancelableEdgeBackend()
        self.window._dexined_backend = fake_backend

        self.window.polygon_tools_panel.btn_redetect_edge_range.click()
        self._cancel_active_edge_operation(fake_backend)

        self.assertEqual(fake_backend.run_input.frames.shape[0], 3)
        np.testing.assert_array_equal(fake_backend.run_input.frame_indices, np.asarray([1, 2, 3], dtype=np.int32))
        self.assertEqual(len(self.window.current_edge_tracks()), 1)
        self._assert_edge_track_matches_snapshot(track, snapshot)
        self.assertEqual(self.window.current_selected_edge_track_id(), track.edge_track_id)

    def test_edge_sequence_run_can_stitch_new_range_into_existing_edge_track(self) -> None:
        sequence = STMSequence(
            source_path="/tmp/edge_sequence_stitch.mpp",
            raw_frames=np.zeros((6, 32, 32), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=32, pixels_y=32, size_nm_x=32.0, size_nm_y=32.0),
        )
        self.window.set_sequence(sequence)

        initial_polygon = PolygonROI(
            np.asarray([[8.0, 10.0], [22.0, 10.0], [24.0, 24.0], [10.0, 26.0]], dtype=np.float64)
        )
        self.window.viewer._commit_polygon(initial_polygon)
        self.window.polygon_tools_panel.sp_run_end_frame.setValue(2)

        initial_edge_prob = np.zeros((2, *sequence.frame_shape), dtype=np.float32)
        initial_edge_prob[0, 12:15, 8:21] = 0.72
        initial_edge_prob[1, 13:16, 9:22] = 0.74
        initial_output = DexiNedRunOutput(
            edge_prob=initial_edge_prob,
            edge_binary=initial_edge_prob >= 0.5,
            model_name="dexined",
            checkpoint_name="DexiNed_BIPED_10.pth",
        )

        with patch.object(self.window._dexined_backend, "run", return_value=initial_output):
            self.window.polygon_tools_panel.btn_run_sequence.click()
            for _ in range(250):
                self.__class__._app.processEvents()
                if self.window.current_edge_tracks():
                    break
                time.sleep(0.01)

        self.assertEqual(len(self.window.current_edge_tracks()), 1)
        track = self.window.current_edge_tracks()[0]
        self.assertEqual(track.frame_indices, [0, 1])

        self.window.slider_frame.setValue(2)
        self.__class__._app.processEvents()
        stitched_polygon = PolygonROI(
            np.asarray([[9.0, 11.0], [23.0, 11.0], [25.0, 25.0], [11.0, 27.0]], dtype=np.float64)
        )
        self.window.viewer._commit_polygon(stitched_polygon)
        self.window.polygon_tools_panel.chk_stitch_active.setChecked(True)
        self.window.polygon_tools_panel.sp_run_end_frame.setValue(5)

        stitched_edge_prob = np.zeros((3, *sequence.frame_shape), dtype=np.float32)
        stitched_edge_prob[0, 15:18, 11:24] = 0.78
        stitched_edge_prob[1, 16:19, 12:25] = 0.80
        stitched_edge_prob[2, 17:20, 13:26] = 0.82
        stitched_output = DexiNedRunOutput(
            edge_prob=stitched_edge_prob,
            edge_binary=stitched_edge_prob >= 0.5,
            model_name="dexined",
            checkpoint_name="DexiNed_BIPED_10.pth",
        )

        def fake_stitch_run(run_input):
            self.assertEqual(run_input.frames.shape[0], 3)
            np.testing.assert_array_equal(run_input.frame_indices, np.asarray([2, 3, 4], dtype=np.int32))
            self.assertEqual(run_input.source_view, "raw")
            return stitched_output

        with patch.object(self.window._dexined_backend, "run", side_effect=fake_stitch_run) as run_mock:
            self.window.polygon_tools_panel.btn_run_sequence.click()
            for _ in range(250):
                self.__class__._app.processEvents()
                updated_track = self.window.current_edge_tracks()[0]
                if run_mock.called and updated_track.get_annotation(4) is not None:
                    break
                time.sleep(0.01)

        run_mock.assert_called_once()
        edge_tracks = self.window.current_edge_tracks()
        self.assertEqual(len(edge_tracks), 1)
        track = edge_tracks[0]
        self.assertEqual(track.edge_track_id, 1)
        self.assertEqual(track.frame_indices, [0, 1, 2, 3, 4])
        np.testing.assert_array_equal(track.polygon_roi.as_array(), stitched_polygon.as_array())
        self.assertEqual(self.window.current_selected_edge_track_id(), 1)
        self.assertIn("stitched edge track 1", self.window.statusBar().currentMessage().lower())

    def test_edge_correction_and_resume_replace_suffix(self) -> None:
        sequence = STMSequence(
            source_path="/tmp/edge_resume.mpp",
            raw_frames=np.zeros((4, 32, 32), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=32, pixels_y=32, size_nm_x=32.0, size_nm_y=32.0),
        )
        self.window.set_sequence(sequence)

        polygon = PolygonROI(np.asarray([[6.0, 8.0], [24.0, 8.0], [24.0, 24.0], [8.0, 26.0]], dtype=np.float64))
        self.window.viewer._commit_polygon(polygon)

        initial_edge_prob = np.zeros((sequence.frame_count, *sequence.frame_shape), dtype=np.float32)
        initial_edge_prob[0, 10:13, 8:20] = 0.70
        initial_edge_prob[1, 11:14, 9:21] = 0.72
        initial_edge_prob[2, 12:15, 10:22] = 0.74
        initial_edge_prob[3, 13:16, 11:23] = 0.76
        initial_output = DexiNedRunOutput(
            edge_prob=initial_edge_prob,
            edge_binary=initial_edge_prob >= 0.5,
            model_name="dexined",
            checkpoint_name="DexiNed_BIPED_10.pth",
        )

        with patch.object(self.window._dexined_backend, "run", return_value=initial_output):
            self.window.polygon_tools_panel.btn_run_sequence.click()
            for _ in range(250):
                self.__class__._app.processEvents()
                if self.window.current_edge_tracks():
                    break
                time.sleep(0.01)

        track = self.window.current_edge_tracks()[0]
        original_frame3_polyline = np.asarray(track.get_annotation(3).polyline, dtype=np.float64)

        self.window.slider_frame.setValue(1)
        self.__class__._app.processEvents()
        self.window.polygon_tools_panel.btn_load_edge.click()
        self.__class__._app.processEvents()

        corrected_polygon = PolygonROI(np.asarray([[7.0, 9.0], [25.0, 9.0], [25.0, 25.0], [9.0, 27.0]], dtype=np.float64))
        corrected_polyline = np.asarray([[9.0, 12.0], [14.0, 12.5], [19.0, 13.0], [24.0, 13.5]], dtype=np.float64)
        self.window._draft_polygons_by_frame[1] = corrected_polygon
        self.window._draft_edge_polylines_by_frame[1] = corrected_polyline
        self.window.viewer.set_polygon_roi(corrected_polygon)
        self.window.viewer.set_edge_polyline(corrected_polyline)
        self.window._sync_current_polygon_ui()

        self.assertTrue(self.window.polygon_tools_panel.btn_save_edge.isEnabled())
        self.assertTrue(self.window.polygon_tools_panel.btn_resume_edge.isEnabled())

        self.window.polygon_tools_panel.btn_save_edge.click()
        self.__class__._app.processEvents()
        self.assertEqual(track.get_annotation(1).source, EdgeAnnotationSource.MANUAL)
        np.testing.assert_array_equal(track.get_annotation(1).polyline, corrected_polyline)
        np.testing.assert_array_equal(track.polygon_roi.as_array(), corrected_polygon.as_array())
        self.assertIsNotNone(track.get_annotation(1).metrics.length_px)
        self.assertGreater(track.get_annotation(1).metrics.length_px, 0.0)
        self.assertTrue(self.window.polygon_tools_panel.btn_resume_edge.isEnabled())

        resume_edge_prob = np.zeros((2, *sequence.frame_shape), dtype=np.float32)
        resume_edge_prob[0, 16:19, 12:24] = 0.81
        resume_edge_prob[1, 17:20, 13:25] = 0.83
        resume_output = DexiNedRunOutput(
            edge_prob=resume_edge_prob,
            edge_binary=resume_edge_prob >= 0.5,
            model_name="dexined",
            checkpoint_name="DexiNed_BIPED_10.pth",
        )

        def fake_resume(run_input):
            self.assertEqual(run_input.frames.shape[0], 2)
            self.assertEqual(run_input.source_view, "raw")
            self.assertTrue(np.any(run_input.polygon_mask))
            return resume_output

        with patch.object(self.window._dexined_backend, "run", side_effect=fake_resume) as run_mock:
            self.window.polygon_tools_panel.btn_resume_edge.click()
            for _ in range(250):
                self.__class__._app.processEvents()
                if run_mock.called and np.any(track.get_annotation(2).edge_mask):
                    break
                time.sleep(0.01)

        run_mock.assert_called_once()
        self.assertEqual(track.get_annotation(1).source, EdgeAnnotationSource.MANUAL)
        np.testing.assert_array_equal(track.get_annotation(1).polyline, corrected_polyline)
        self.assertEqual(track.get_annotation(2).source, EdgeAnnotationSource.DEXINED)
        self.assertEqual(track.get_annotation(3).source, EdgeAnnotationSource.DEXINED)
        self.assertIsNotNone(track.get_annotation(2).metrics.length_px)
        self.assertGreater(track.get_annotation(2).metrics.length_px, 0.0)
        self.assertIsNotNone(track.get_annotation(3).metrics.length_px)
        self.assertFalse(np.array_equal(track.get_annotation(3).polyline, original_frame3_polyline))
        self.assertGreater(len(self.window.viewer.viewer._overlay_items), 0)

    def test_edge_redetect_replaces_existing_track_annotations_without_creating_new_track(self) -> None:
        sequence = STMSequence(
            source_path="/tmp/edge_redetect.mpp",
            raw_frames=np.zeros((4, 32, 32), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=32, pixels_y=32, size_nm_x=32.0, size_nm_y=32.0),
        )
        self.window.set_sequence(sequence)

        polygon = PolygonROI(np.asarray([[6.0, 8.0], [24.0, 8.0], [24.0, 24.0], [8.0, 26.0]], dtype=np.float64))
        self.window.viewer._commit_polygon(polygon)

        initial_edge_prob = np.zeros((3, *sequence.frame_shape), dtype=np.float32)
        initial_edge_prob[0, 10:13, 8:20] = 0.70
        initial_edge_prob[1, 11:14, 9:21] = 0.72
        initial_edge_prob[2, 12:15, 10:22] = 0.74
        initial_output = DexiNedRunOutput(
            edge_prob=initial_edge_prob,
            edge_binary=initial_edge_prob >= 0.5,
            model_name="dexined",
            checkpoint_name="DexiNed_BIPED_10.pth",
        )

        self.window.polygon_tools_panel.sp_run_end_frame.setValue(3)
        with patch.object(self.window._dexined_backend, "run", return_value=initial_output):
            self.window.polygon_tools_panel.btn_run_sequence.click()
            for _ in range(250):
                self.__class__._app.processEvents()
                if self.window.current_edge_tracks():
                    break
                time.sleep(0.01)

        self.assertEqual(len(self.window.current_edge_tracks()), 1)
        track = self.window.current_edge_tracks()[0]
        manual_polyline = np.asarray([[8.0, 24.0], [20.0, 24.0]], dtype=np.float64)
        track.add_annotation(
            EdgeFrameAnnotation(
                frame_index=2,
                polyline=manual_polyline,
                visibility=FrameVisibility.VISIBLE,
                source=EdgeAnnotationSource.MANUAL,
            )
        )
        self.window.set_edge_tracks(self.window.current_edge_tracks(), selected_track_id=track.edge_track_id)
        self.assertEqual(track.get_annotation(2).source, EdgeAnnotationSource.MANUAL)
        self.assertTrue(self.window.polygon_tools_panel.btn_redetect_edge.isEnabled())

        self.window.polygon_tools_panel.sp_dexined_threshold.setValue(0.30)
        self.window.polygon_tools_panel.sp_edge_components.setValue(2)
        self.window.polygon_tools_panel.cmb_refine_score_mode.setCurrentIndex(2)
        self.window.polygon_tools_panel.sp_refine_radius.setValue(6)

        redetect_edge_prob = np.zeros((3, *sequence.frame_shape), dtype=np.float32)
        for offset in range(8):
            redetect_edge_prob[0, 10 + offset, 8 + offset] = 0.82
            redetect_edge_prob[1, 11 + offset, 8 + offset] = 0.84
            redetect_edge_prob[2, 12 + offset, 8 + offset] = 0.86
        redetect_output = DexiNedRunOutput(
            edge_prob=redetect_edge_prob,
            edge_binary=redetect_edge_prob >= 0.5,
            model_name="dexined",
            checkpoint_name="DexiNed_BIPED_10.pth",
        )

        run_input, redetect_meta = self.window._build_dexined_redetect_input(track)
        np.testing.assert_array_equal(run_input.frame_indices, np.asarray([0, 1, 2], dtype=np.int32))
        self.assertEqual(run_input.frames.shape[0], 3)
        self.assertEqual(run_input.source_view, "raw")
        self.assertAlmostEqual(run_input.threshold, 0.30, places=6)
        self.window._apply_edge_redetect_output(redetect_output, redetect_meta)

        self.assertEqual(len(self.window.current_edge_tracks()), 1)
        updated_track = self.window.current_edge_tracks()[0]
        self.assertEqual(updated_track.edge_track_id, 1)
        self.assertEqual(updated_track.frame_indices, [0, 1, 2])
        self.assertEqual(self.window.current_selected_edge_track_id(), 1)
        self.assertEqual(updated_track.get_annotation(2).source, EdgeAnnotationSource.DEXINED)

    def test_edge_partial_redetect_replaces_only_selected_range(self) -> None:
        sequence = STMSequence(
            source_path="/tmp/edge_partial_redetect.mpp",
            raw_frames=np.zeros((5, 32, 32), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=32, pixels_y=32, size_nm_x=32.0, size_nm_y=32.0),
        )
        self.window.set_sequence(sequence)

        polygon = PolygonROI(np.asarray([[6.0, 8.0], [24.0, 8.0], [24.0, 24.0], [8.0, 26.0]], dtype=np.float64))
        self.window.viewer._commit_polygon(polygon)

        initial_edge_prob = np.zeros((5, *sequence.frame_shape), dtype=np.float32)
        initial_edge_prob[0, 10:13, 8:20] = 0.70
        initial_edge_prob[1, 11:14, 9:21] = 0.72
        initial_edge_prob[2, 12:15, 10:22] = 0.74
        initial_edge_prob[3, 13:16, 11:23] = 0.76
        initial_edge_prob[4, 14:17, 12:24] = 0.78
        initial_output = DexiNedRunOutput(
            edge_prob=initial_edge_prob,
            edge_binary=initial_edge_prob >= 0.5,
            model_name="dexined",
            checkpoint_name="DexiNed_BIPED_10.pth",
        )

        self.window.polygon_tools_panel.sp_run_end_frame.setValue(5)
        with patch.object(self.window._dexined_backend, "run", return_value=initial_output):
            self.window.polygon_tools_panel.btn_run_sequence.click()
            for _ in range(250):
                self.__class__._app.processEvents()
                if self.window.current_edge_tracks():
                    break
                time.sleep(0.01)

        self.assertEqual(len(self.window.current_edge_tracks()), 1)
        track = self.window.current_edge_tracks()[0]
        original_frame0_polyline = np.asarray(track.get_annotation(0).polyline, dtype=np.float64)
        original_frame4_polyline = np.asarray(track.get_annotation(4).polyline, dtype=np.float64)
        manual_polyline = np.asarray([[8.0, 22.0], [20.0, 22.0]], dtype=np.float64)
        track.add_annotation(
            EdgeFrameAnnotation(
                frame_index=1,
                polyline=manual_polyline,
                visibility=FrameVisibility.VISIBLE,
                source=EdgeAnnotationSource.MANUAL,
            )
        )
        self.window.set_edge_tracks(self.window.current_edge_tracks(), selected_track_id=track.edge_track_id)

        self.window.slider_frame.setValue(2)
        self.__class__._app.processEvents()
        self.window.polygon_tools_panel.sp_run_end_frame.setValue(4)
        self.assertTrue(self.window.polygon_tools_panel.btn_redetect_edge_range.isEnabled())

        self.window.polygon_tools_panel.sp_dexined_threshold.setValue(0.28)
        self.window.polygon_tools_panel.sp_edge_components.setValue(2)
        self.window.polygon_tools_panel.cmb_refine_score_mode.setCurrentIndex(1)
        self.window.polygon_tools_panel.sp_refine_radius.setValue(5)

        redetect_edge_prob = np.zeros((2, *sequence.frame_shape), dtype=np.float32)
        for offset in range(8):
            redetect_edge_prob[0, 10 + offset, 7 + offset] = 0.82
            redetect_edge_prob[1, 11 + offset, 7 + offset] = 0.84
        redetect_output = DexiNedRunOutput(
            edge_prob=redetect_edge_prob,
            edge_binary=redetect_edge_prob >= 0.5,
            model_name="dexined",
            checkpoint_name="DexiNed_BIPED_10.pth",
        )

        run_input, redetect_meta = self.window._build_dexined_partial_redetect_input(track)
        np.testing.assert_array_equal(run_input.frame_indices, np.asarray([2, 3], dtype=np.int32))
        self.assertEqual(run_input.frames.shape[0], 2)
        self.assertAlmostEqual(run_input.threshold, 0.28, places=6)
        self.assertEqual(redetect_meta["start_frame_index"], 2)
        self.assertEqual(redetect_meta["end_frame_index"], 3)
        self.window._apply_edge_partial_redetect_output(redetect_output, redetect_meta)

        self.assertEqual(len(self.window.current_edge_tracks()), 1)
        updated_track = self.window.current_edge_tracks()[0]
        self.assertEqual(updated_track.edge_track_id, 1)
        self.assertEqual(updated_track.frame_indices, [0, 1, 2, 3, 4])
        np.testing.assert_array_equal(updated_track.get_annotation(0).polyline, original_frame0_polyline)
        np.testing.assert_array_equal(updated_track.get_annotation(1).polyline, manual_polyline)
        self.assertEqual(updated_track.get_annotation(1).source, EdgeAnnotationSource.MANUAL)
        np.testing.assert_array_equal(updated_track.get_annotation(4).polyline, original_frame4_polyline)
        self.assertEqual(updated_track.get_annotation(2).source, EdgeAnnotationSource.DEXINED)
        self.assertEqual(updated_track.get_annotation(3).source, EdgeAnnotationSource.DEXINED)
        self.assertEqual(self.window.current_selected_edge_track_id(), 1)

    def test_edge_hybrid_stabilization_replaces_suffix_with_tracker_refine(self) -> None:
        sequence = STMSequence(
            source_path="/tmp/edge_hybrid.mpp",
            raw_frames=np.zeros((4, 32, 32), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=32, pixels_y=32, size_nm_x=32.0, size_nm_y=32.0),
        )
        self.window.set_sequence(sequence)

        polygon = PolygonROI(np.asarray([[6.0, 8.0], [24.0, 8.0], [24.0, 24.0], [8.0, 26.0]], dtype=np.float64))
        self.window.viewer._commit_polygon(polygon)

        initial_edge_prob = np.zeros((sequence.frame_count, *sequence.frame_shape), dtype=np.float32)
        initial_edge_prob[0, 10:13, 8:20] = 0.70
        initial_edge_prob[1, 11:14, 9:21] = 0.72
        initial_edge_prob[2, 12:15, 10:22] = 0.74
        initial_edge_prob[3, 13:16, 11:23] = 0.76
        initial_output = DexiNedRunOutput(
            edge_prob=initial_edge_prob,
            edge_binary=initial_edge_prob >= 0.5,
            model_name="dexined",
            checkpoint_name="DexiNed_BIPED_10.pth",
        )

        with patch.object(self.window._dexined_backend, "run", return_value=initial_output):
            self.window.polygon_tools_panel.btn_run_sequence.click()
            for _ in range(250):
                self.__class__._app.processEvents()
                if self.window.current_edge_tracks():
                    break
                time.sleep(0.01)

        track = self.window.current_edge_tracks()[0]
        original_frame2_polyline = np.asarray(track.get_annotation(2).polyline, dtype=np.float64)
        original_frame3_polyline = np.asarray(track.get_annotation(3).polyline, dtype=np.float64)

        self.window.slider_frame.setValue(1)
        self.__class__._app.processEvents()
        self.assertTrue(self.window.polygon_tools_panel.btn_hybrid.isEnabled())

        def fake_tracker_run(run_input):
            self.assertEqual(run_input.frames.shape[0], 3)
            self.assertEqual(run_input.source_view, "raw")
            self.assertEqual(run_input.query_points_tyx.shape[0], self.window.polygon_tools_panel.hybrid_control_point_count())
            query_points_xy = np.column_stack([run_input.query_points_tyx[:, 2], run_input.query_points_tyx[:, 1]]).astype(
                np.float32,
                copy=False,
            )
            tracks_xy = np.stack(
                [
                    query_points_xy,
                    query_points_xy + np.asarray([1.5, 0.4], dtype=np.float32),
                    query_points_xy + np.asarray([3.0, 0.8], dtype=np.float32),
                ],
                axis=1,
            )
            visible_mask = np.ones(tracks_xy.shape[:2], dtype=bool)
            return PointTrackerRunOutput(
                tracks_xy=tracks_xy,
                visible_mask=visible_mask,
                model_name="tapir_stub",
                checkpoint_name=None,
            )

        with patch.object(self.window._point_tracker_backends["tapir"], "run", side_effect=fake_tracker_run) as run_mock:
            self.window.polygon_tools_panel.btn_hybrid.click()
            self.assertIsNotNone(self.window._point_tracker_progress_dialog)
            self.assertTrue(self.window._point_tracker_progress_dialog.isVisible())
            for _ in range(250):
                self.__class__._app.processEvents()
                if run_mock.called and track.get_annotation(2).source == EdgeAnnotationSource.TRACKER_REFINE:
                    break
                time.sleep(0.01)

        run_mock.assert_called_once()
        self.assertEqual(track.get_annotation(1).source, EdgeAnnotationSource.DEXINED)
        self.assertEqual(track.get_annotation(2).source, EdgeAnnotationSource.TRACKER_REFINE)
        self.assertEqual(track.get_annotation(3).source, EdgeAnnotationSource.TRACKER_REFINE)
        self.assertFalse(np.array_equal(track.get_annotation(2).polyline, original_frame2_polyline))
        self.assertFalse(np.array_equal(track.get_annotation(3).polyline, original_frame3_polyline))
        self.assertIsNotNone(track.get_annotation(2).metrics.length_px)
        self.assertIsNotNone(track.get_annotation(3).metrics.length_px)
        self.assertGreater(len(self.window.viewer.viewer._overlay_items), 0)
        self.assertIn("hybrid stabilization finished", self.window.statusBar().currentMessage().lower())

    def test_polygon_roi_state_is_per_frame_and_can_be_replaced_on_current_frame(self) -> None:
        sequence = load_mpp_sequence(str(SAMPLE_MPP))
        self.window.set_sequence(sequence)

        frame0_polygon = PolygonROI(np.asarray([[8.0, 8.0], [24.0, 10.0], [18.0, 26.0]], dtype=np.float64))
        self.window.viewer._commit_polygon(frame0_polygon)
        self.assertIsNotNone(self.window.current_draft_polygon_roi())

        self.window.slider_frame.setValue(1)
        self.assertIsNone(self.window.current_draft_polygon_roi())
        self.assertIsNone(self.window.viewer.current_polygon_roi())
        self.assertEqual(self.window.polygon_tools_panel.lbl_polygon.text(), "No polygon ROI on current frame")

        frame1_polygon = PolygonROI(np.asarray([[12.0, 14.0], [28.0, 16.0], [26.0, 30.0]], dtype=np.float64))
        self.window.viewer._commit_polygon(frame1_polygon)
        np.testing.assert_array_equal(self.window.current_draft_polygon_roi().as_array(), frame1_polygon.as_array())

        self.window.slider_frame.setValue(0)
        np.testing.assert_array_equal(self.window.current_draft_polygon_roi().as_array(), frame0_polygon.as_array())
        np.testing.assert_array_equal(self.window.viewer.current_polygon_roi().as_array(), frame0_polygon.as_array())

        replacement_polygon = PolygonROI(np.asarray([[9.0, 9.0], [26.0, 11.0], [20.0, 29.0]], dtype=np.float64))
        self.window.viewer._commit_polygon(replacement_polygon)

        np.testing.assert_array_equal(self.window.current_draft_polygon_roi().as_array(), replacement_polygon.as_array())
        np.testing.assert_array_equal(self.window.viewer.current_polygon_roi().as_array(), replacement_polygon.as_array())
        self.assertIn("Vertices: 3", self.window.polygon_tools_panel.lbl_polygon.text())

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

    def test_can_load_track_bbox_and_save_manual_correction(self) -> None:
        sequence = load_mpp_sequence(str(SAMPLE_MPP))
        self.window.set_sequence(sequence)

        seed_bbox = BBoxXYXY(10.0, 10.0, 18.0, 18.0)
        track = ParticleTrack(track_id=1, seed_frame_index=0, seed_bbox=seed_bbox)
        original_bbox = BBoxXYXY(14.0, 12.0, 23.0, 20.0)
        track.add_annotation(
            TrackFrameAnnotation(
                frame_index=2,
                bbox=original_bbox,
                source=AnnotationSource.SAM2,
            )
        )
        self.window.set_tracks([track], selected_track_id=1)
        self.window.slider_frame.setValue(2)

        self.assertTrue(self.window.bbox_tools_panel.btn_load_track_bbox.isEnabled())
        self.assertFalse(self.window.bbox_tools_panel.btn_save_correction.isEnabled())

        self.window.bbox_tools_panel.btn_load_track_bbox.click()

        self.assertEqual(self.window.current_draft_bbox(), original_bbox)
        self.assertEqual(self.window.viewer.current_bbox(), original_bbox)
        self.assertTrue(self.window.bbox_tools_panel.btn_save_correction.isEnabled())

        corrected_bbox = BBoxXYXY(16.0, 13.0, 26.0, 21.0)
        self.window.viewer._commit_bbox(corrected_bbox)
        self.window.bbox_tools_panel.btn_save_correction.click()

        corrected_annotation = self.window.current_tracks()[0].get_annotation(2)
        self.assertIsNotNone(corrected_annotation)
        self.assertEqual(corrected_annotation.bbox, corrected_bbox)
        self.assertEqual(corrected_annotation.source, AnnotationSource.MANUAL)
        self.assertIsNone(corrected_annotation.mask)
        self.assertIsNone(self.window.current_draft_bbox())
        self.assertIsNone(self.window.viewer.current_bbox())
        self.assertIn("Saved manual correction for Track 1 on frame 3.", self.window.statusBar().currentMessage())

    def test_resume_sam2_replaces_only_tail_after_current_frame(self) -> None:
        sequence = load_mpp_sequence(str(SAMPLE_MPP))
        self.assertGreaterEqual(sequence.frame_count, 5)
        self.window.set_sequence(sequence)

        track = ParticleTrack(track_id=1, seed_frame_index=0, seed_bbox=BBoxXYXY(10.0, 10.0, 18.0, 18.0))
        track.add_annotation(
            TrackFrameAnnotation(
                frame_index=1,
                bbox=BBoxXYXY(11.0, 11.0, 19.0, 19.0),
                source=AnnotationSource.SAM2,
            )
        )
        track.add_annotation(
            TrackFrameAnnotation(
                frame_index=2,
                bbox=BBoxXYXY(12.0, 12.0, 20.0, 20.0),
                source=AnnotationSource.SAM2,
            )
        )
        track.add_annotation(
            TrackFrameAnnotation(
                frame_index=3,
                bbox=BBoxXYXY(13.0, 13.0, 21.0, 21.0),
                source=AnnotationSource.SAM2,
            )
        )
        track.add_annotation(
            TrackFrameAnnotation(
                frame_index=4,
                bbox=BBoxXYXY(14.0, 14.0, 22.0, 22.0),
                source=AnnotationSource.SAM2,
            )
        )
        self.window.set_tracks([track], selected_track_id=1)
        self.window.slider_frame.setValue(2)

        self.window.bbox_tools_panel.btn_load_track_bbox.click()
        corrected_bbox = BBoxXYXY(16.0, 15.0, 25.0, 23.0)
        self.window.viewer._commit_bbox(corrected_bbox)
        self.window.bbox_tools_panel.btn_save_correction.click()
        self.assertTrue(self.window.bbox_tools_panel.btn_resume_track.isEnabled())

        repaired = np.full_like(sequence.raw_frames, 0.55, dtype=np.float32)
        self.window._repair_frames = repaired

        resumed_frame_count = sequence.frame_count - 2
        masks = np.zeros((resumed_frame_count, *sequence.frame_shape), dtype=bool)
        masks[0, 15:23, 16:25] = True
        masks[1, 17:24, 18:26] = True
        masks[2, 18:25, 19:27] = True
        visible_mask = np.zeros((resumed_frame_count,), dtype=bool)
        visible_mask[:3] = True
        mask_bboxes = np.zeros((resumed_frame_count, 4), dtype=np.float32)
        mask_bboxes[0] = np.asarray([16.0, 15.0, 25.0, 23.0], dtype=np.float32)
        mask_bboxes[1] = np.asarray([18.0, 17.0, 26.0, 24.0], dtype=np.float32)
        mask_bboxes[2] = np.asarray([19.0, 18.0, 27.0, 25.0], dtype=np.float32)
        mask_areas = np.zeros((resumed_frame_count,), dtype=np.float32)
        mask_areas[:3] = np.asarray([72.0, 56.0, 56.0], dtype=np.float32)
        mask_scores = np.zeros((resumed_frame_count,), dtype=np.float32)
        mask_scores[:3] = np.asarray([0.93, 0.89, 0.87], dtype=np.float32)
        mask_component_counts = np.zeros((resumed_frame_count,), dtype=np.int32)
        mask_component_counts[:3] = 1
        run_output = Sam2RunOutput(
            track_id=1,
            frame_index_offset=2,
            masks=masks,
            visible_mask=visible_mask,
            mask_areas=mask_areas,
            mask_bboxes_xyxy=mask_bboxes,
            mask_scores=mask_scores,
            mask_component_counts=mask_component_counts,
        )

        def fake_run(run_input):
            time.sleep(0.05)
            np.testing.assert_array_equal(run_input.frames, repaired[2:])
            np.testing.assert_array_equal(run_input.query_box_xyxy, np.asarray(corrected_bbox.as_tuple(), dtype=np.float32))
            self.assertEqual(run_input.frame_index_offset, 2)
            self.assertEqual(run_input.source_view, "repair")
            return run_output

        with patch.object(self.window._sam2_backend, "run", side_effect=fake_run) as run_mock:
            self.window.bbox_tools_panel.btn_resume_track.click()
            self.assertFalse(self.window.bbox_tools_panel.btn_resume_track.isEnabled())
            self.assertIsNotNone(self.window._sam2_progress_dialog)
            self.assertTrue(self.window._sam2_progress_dialog.isVisible())
            for _ in range(250):
                self.__class__._app.processEvents()
                resumed_track = self.window.current_tracks()[0]
                annotation3 = resumed_track.get_annotation(3)
                annotation4 = resumed_track.get_annotation(4)
                if run_mock.called and annotation3 is not None and annotation4 is not None:
                    if annotation3.bbox == BBoxXYXY(18.0, 17.0, 26.0, 24.0) and annotation4.bbox == BBoxXYXY(19.0, 18.0, 27.0, 25.0):
                        break
                time.sleep(0.01)

        run_mock.assert_called_once()
        resumed_track = self.window.current_tracks()[0]
        self.assertEqual(resumed_track.get_annotation(0).bbox, BBoxXYXY(10.0, 10.0, 18.0, 18.0))
        self.assertEqual(resumed_track.get_annotation(1).bbox, BBoxXYXY(11.0, 11.0, 19.0, 19.0))
        self.assertEqual(resumed_track.get_annotation(2).bbox, corrected_bbox)
        self.assertEqual(resumed_track.get_annotation(2).source, AnnotationSource.MANUAL)
        self.assertIsNone(resumed_track.get_annotation(2).metrics.area_px)
        self.assertEqual(resumed_track.get_annotation(3).bbox, BBoxXYXY(18.0, 17.0, 26.0, 24.0))
        self.assertEqual(resumed_track.get_annotation(4).bbox, BBoxXYXY(19.0, 18.0, 27.0, 25.0))
        self.assertEqual(resumed_track.get_annotation(3).source, AnnotationSource.SAM2)
        self.assertEqual(resumed_track.get_annotation(4).source, AnnotationSource.SAM2)
        expected_resume_metrics = compute_particle_metrics(
            resumed_track.get_annotation(3).mask,
            sequence.raw_frames[3],
        )
        self.assertEqual(resumed_track.get_annotation(3).metrics.area_px, expected_resume_metrics.area_px)
        self.assertEqual(resumed_track.get_annotation(3).metrics.perimeter_px, expected_resume_metrics.perimeter_px)
        self.assertEqual(resumed_track.get_annotation(3).metrics.intensity_sum, expected_resume_metrics.intensity_sum)
        self.assertEqual(resumed_track.get_annotation(3).metrics.intensity_mean, expected_resume_metrics.intensity_mean)
        self.assertEqual(resumed_track.get_annotation(3).metrics.intensity_max, expected_resume_metrics.intensity_max)
        self.assertTrue(self.window.bbox_tools_panel.btn_resume_track.isEnabled())
        self.assertIn("SAM2 resume finished for Track 1 from frame 3.", self.window.statusBar().currentMessage())

    def _assert_resume_with_mask_tracker(
        self,
        tracker_kind: MaskTrackerKind,
        expected_source: AnnotationSource,
    ) -> None:
        sequence = load_mpp_sequence(str(SAMPLE_MPP))
        self.assertGreaterEqual(sequence.frame_count, 5)
        self.window.set_sequence(sequence)

        corrected_bbox = BBoxXYXY(16.0, 15.0, 25.0, 23.0)
        track = ParticleTrack(track_id=1, seed_frame_index=0, seed_bbox=BBoxXYXY(10.0, 10.0, 18.0, 18.0))
        track.add_annotation(
            TrackFrameAnnotation(
                frame_index=1,
                bbox=BBoxXYXY(11.0, 11.0, 19.0, 19.0),
                source=AnnotationSource.SAM2,
            )
        )
        track.add_annotation(
            TrackFrameAnnotation(
                frame_index=2,
                bbox=corrected_bbox,
                source=AnnotationSource.MANUAL,
            )
        )
        track.add_annotation(
            TrackFrameAnnotation(
                frame_index=3,
                bbox=BBoxXYXY(13.0, 13.0, 21.0, 21.0),
                source=AnnotationSource.SAM2,
            )
        )
        track.add_annotation(
            TrackFrameAnnotation(
                frame_index=4,
                bbox=BBoxXYXY(14.0, 14.0, 22.0, 22.0),
                source=AnnotationSource.SAM2,
            )
        )
        self.window.set_tracks([track], selected_track_id=1)
        self.window.slider_frame.setValue(2)
        self.window.track_list_panel.set_mask_tracker_kind(tracker_kind)
        self.assertTrue(self.window.bbox_tools_panel.btn_resume_track.isEnabled())

        repaired = np.full_like(sequence.raw_frames, 0.55, dtype=np.float32)
        self.window._repair_frames = repaired

        def fake_run(run_input):
            time.sleep(0.05)
            self.assertEqual(run_input.tracker_kind, tracker_kind)
            self.assertEqual(run_input.track_id, 1)
            self.assertEqual(run_input.frame_index_offset, 2)
            self.assertEqual(run_input.source_view, "repair")
            np.testing.assert_array_equal(run_input.frames, repaired[2:])
            np.testing.assert_array_equal(run_input.query_box_xyxy, np.asarray(corrected_bbox.as_tuple(), dtype=np.float32))
            return self._mask_tracker_output(
                tracker_kind,
                track_id=1,
                frame_index_offset=2,
                frame_count=int(run_input.frames.shape[0]),
                frame_shape=tuple(run_input.frames.shape[1:3]),
                row=30,
                col=40,
                visible_count=3,
            )

        backend = self.window._mask_tracker_backends[tracker_kind]
        with patch.object(backend, "run", side_effect=fake_run) as run_mock:
            self.window.bbox_tools_panel.btn_resume_track.click()
            self.assertFalse(self.window.bbox_tools_panel.btn_resume_track.isEnabled())
            self.assertIsNotNone(self.window._sam2_progress_dialog)
            self.assertTrue(self.window._sam2_progress_dialog.isVisible())
            self._wait_until(
                lambda: (
                    run_mock.called
                    and self.window.current_tracks()[0].get_annotation(3) is not None
                    and self.window.current_tracks()[0].get_annotation(4) is not None
                    and not self.window._is_tracking
                ),
                attempts=350,
            )

        run_mock.assert_called_once()
        resumed_track = self.window.current_tracks()[0]
        self.assertEqual(resumed_track.get_annotation(0).bbox, BBoxXYXY(10.0, 10.0, 18.0, 18.0))
        self.assertEqual(resumed_track.get_annotation(1).bbox, BBoxXYXY(11.0, 11.0, 19.0, 19.0))
        self.assertEqual(resumed_track.get_annotation(2).bbox, corrected_bbox)
        self.assertEqual(resumed_track.get_annotation(2).source, AnnotationSource.MANUAL)
        self.assertEqual(resumed_track.get_annotation(3).bbox, BBoxXYXY(41.0, 31.0, 48.0, 37.0))
        self.assertEqual(resumed_track.get_annotation(4).bbox, BBoxXYXY(42.0, 32.0, 49.0, 38.0))
        self.assertEqual(resumed_track.get_annotation(3).source, expected_source)
        self.assertEqual(resumed_track.get_annotation(4).source, expected_source)
        self.assertTrue(resumed_track.get_annotation(3).mask.any())
        self.assertTrue(resumed_track.get_annotation(4).mask.any())
        backend_label = self.window._format_mask_tracker_backend_label(tracker_kind)
        self.assertTrue(self.window.bbox_tools_panel.btn_resume_track.isEnabled())
        self.assertIn(
            f"{backend_label} resume finished for Track 1 from frame 3.",
            self.window.statusBar().currentMessage(),
        )

    def test_resume_dam4sam_replaces_tail_with_dam4sam_source(self) -> None:
        self._assert_resume_with_mask_tracker(MaskTrackerKind.DAM4SAM, AnnotationSource.DAM4SAM)

    def test_resume_samurai_replaces_tail_with_samurai_source(self) -> None:
        self._assert_resume_with_mask_tracker(MaskTrackerKind.SAMURAI, AnnotationSource.SAMURAI)

    @patch("nanotrack.ui.main_window.QMessageBox.critical")
    def test_resume_samurai_failure_keeps_existing_tail_and_uses_backend_label(self, critical_mock) -> None:
        sequence = load_mpp_sequence(str(SAMPLE_MPP))
        self.assertGreaterEqual(sequence.frame_count, 5)
        self.window.set_sequence(sequence)

        track = ParticleTrack(track_id=1, seed_frame_index=0, seed_bbox=BBoxXYXY(10.0, 10.0, 18.0, 18.0))
        for frame_index in range(5):
            track.add_annotation(
                TrackFrameAnnotation(
                    frame_index=frame_index,
                    bbox=BBoxXYXY(10.0 + frame_index, 9.0, 18.0 + frame_index, 17.0),
                    source=AnnotationSource.MANUAL if frame_index == 2 else AnnotationSource.SAM2,
                )
            )
        expected = {
            frame_index: (annotation.bbox, annotation.source)
            for frame_index, annotation in track.annotations.items()
        }
        self.window.set_tracks([track], selected_track_id=1)
        self.window.slider_frame.setValue(2)
        self.window.track_list_panel.set_mask_tracker_kind(MaskTrackerKind.SAMURAI)

        samurai_backend = self.window._mask_tracker_backends[MaskTrackerKind.SAMURAI]
        with patch.object(samurai_backend, "run", side_effect=RuntimeError("SAMURAI worker failed.")) as run_mock:
            self.window.bbox_tools_panel.btn_resume_track.click()
            self._wait_until(lambda: critical_mock.called and not self.window._is_tracking, attempts=350)

        run_mock.assert_called_once()
        critical_mock.assert_called_once()
        self.assertEqual(critical_mock.call_args.args[1], "SAMURAI error")
        self.assertIn("SAMURAI worker failed.", critical_mock.call_args.args[2])
        self.assertEqual(self.window.statusBar().currentMessage(), "SAMURAI run failed.")
        resumed_track = self.window.current_tracks()[0]
        self.assertEqual(set(resumed_track.annotations), set(expected))
        for frame_index, (expected_bbox, expected_source) in expected.items():
            annotation = resumed_track.get_annotation(frame_index)
            self.assertIsNotNone(annotation)
            self.assertEqual(annotation.bbox, expected_bbox)
            self.assertEqual(annotation.source, expected_source)
        self.assertTrue(self.window.bbox_tools_panel.btn_resume_track.isEnabled())

    def test_mask_tracker_selected_cancel_stops_worker_without_new_annotations(self) -> None:
        sequence = STMSequence(
            source_path="/tmp/mask_tracker_selected_cancel.mpp",
            raw_frames=np.zeros((4, 32, 32), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=32, pixels_y=32, size_nm_x=32.0, size_nm_y=32.0),
        )
        self.window.set_sequence(sequence)
        self.window.slider_frame.setValue(0)
        self.window.viewer.place_bbox_at_pixel(16.0, 16.0)
        self.window.bbox_tools_panel.btn_add_seed.click()
        self.window.track_list_panel.set_mask_tracker_kind(MaskTrackerKind.DAM4SAM)

        fake_backend = _FakeCancelableMaskTrackerBackend()
        self.window._mask_tracker_backends[MaskTrackerKind.DAM4SAM] = fake_backend

        self.window.track_list_panel.btn_run_selected.click()
        self._cancel_active_mask_tracker_operation(fake_backend)

        self.assertEqual(len(fake_backend.run_inputs), 1)
        self.assertEqual(fake_backend.run_inputs[0].tracker_kind, MaskTrackerKind.DAM4SAM)
        self.assertEqual(fake_backend.run_inputs[0].frame_index_offset, 0)
        track = self.window.current_tracks()[0]
        self.assertIsNotNone(track.get_annotation(0))
        self.assertIsNone(track.get_annotation(1))
        self.assertIsNone(track.get_annotation(2))

    def test_mask_tracker_resume_cancel_keeps_existing_track_annotations(self) -> None:
        sequence = STMSequence(
            source_path="/tmp/mask_tracker_resume_cancel.mpp",
            raw_frames=np.zeros((4, 32, 32), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=32, pixels_y=32, size_nm_x=32.0, size_nm_y=32.0),
        )
        self.window.set_sequence(sequence)
        track = ParticleTrack(track_id=1, seed_frame_index=0, seed_bbox=BBoxXYXY(10.0, 10.0, 18.0, 18.0))
        for frame_index in range(4):
            track.add_annotation(
                TrackFrameAnnotation(
                    frame_index=frame_index,
                    bbox=BBoxXYXY(10.0 + frame_index, 10.0, 18.0 + frame_index, 18.0),
                    source=AnnotationSource.MANUAL if frame_index == 1 else AnnotationSource.SAM2,
                )
            )
        expected = {
            frame_index: (annotation.bbox, annotation.source)
            for frame_index, annotation in track.annotations.items()
        }
        self.window.set_tracks([track], selected_track_id=1)
        self.window.slider_frame.setValue(1)
        self.window.track_list_panel.set_mask_tracker_kind(MaskTrackerKind.DAM4SAM)

        fake_backend = _FakeCancelableMaskTrackerBackend()
        self.window._mask_tracker_backends[MaskTrackerKind.DAM4SAM] = fake_backend

        self.window.bbox_tools_panel.btn_resume_track.click()
        self._cancel_active_mask_tracker_operation(fake_backend)

        self.assertEqual(len(fake_backend.run_inputs), 1)
        self.assertEqual(fake_backend.run_inputs[0].frame_index_offset, 1)
        resumed_track = self.window.current_tracks()[0]
        self.assertEqual(set(resumed_track.annotations), set(expected))
        for frame_index, (expected_bbox, expected_source) in expected.items():
            annotation = resumed_track.get_annotation(frame_index)
            self.assertIsNotNone(annotation)
            self.assertEqual(annotation.bbox, expected_bbox)
            self.assertEqual(annotation.source, expected_source)

    def test_mask_tracker_batch_cancel_stops_current_worker_without_processing_remaining_seeds(self) -> None:
        sequence = STMSequence(
            source_path="/tmp/mask_tracker_batch_cancel.mpp",
            raw_frames=np.zeros((5, 32, 32), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=32, pixels_y=32, size_nm_x=32.0, size_nm_y=32.0),
        )
        self.window.set_sequence(sequence)
        self.window.slider_frame.setValue(0)
        self.window.viewer.place_bbox_at_pixel(12.0, 12.0)
        self.window.bbox_tools_panel.btn_add_seed.click()
        self.window.slider_frame.setValue(2)
        self.window.viewer.place_bbox_at_pixel(20.0, 20.0)
        self.window.bbox_tools_panel.btn_add_seed.click()
        self.window.track_list_panel.set_mask_tracker_kind(MaskTrackerKind.SAMURAI)

        fake_backend = _FakeCancelableMaskTrackerBackend()
        self.window._mask_tracker_backends[MaskTrackerKind.SAMURAI] = fake_backend

        self.window.track_list_panel.btn_run_all.click()
        self._cancel_active_mask_tracker_operation(fake_backend)

        self.assertEqual(len(fake_backend.run_inputs), 1)
        self.assertEqual(fake_backend.run_inputs[0].tracker_kind, MaskTrackerKind.SAMURAI)
        self.assertEqual(fake_backend.run_inputs[0].track_id, 1)
        tracks = self.window.current_tracks()
        self.assertIsNotNone(tracks[0].get_annotation(0))
        self.assertIsNone(tracks[0].get_annotation(1))
        self.assertIsNotNone(tracks[1].get_annotation(2))
        self.assertIsNone(tracks[1].get_annotation(3))

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
        expected_frame1_metrics = compute_particle_metrics(frame1_annotation.mask, sequence.raw_frames[1])
        self.assertEqual(frame1_annotation.metrics.area_px, expected_frame1_metrics.area_px)
        self.assertEqual(frame1_annotation.metrics.perimeter_px, expected_frame1_metrics.perimeter_px)
        self.assertEqual(frame1_annotation.metrics.intensity_sum, expected_frame1_metrics.intensity_sum)
        self.assertEqual(frame1_annotation.metrics.intensity_mean, expected_frame1_metrics.intensity_mean)
        self.assertEqual(frame1_annotation.metrics.intensity_max, expected_frame1_metrics.intensity_max)
        self.assertEqual(frame2_annotation.bbox, BBoxXYXY(15.0, 13.0, 24.0, 21.0))
        self.assertTrue(frame2_annotation.mask.any())
        expected_frame2_metrics = compute_particle_metrics(frame2_annotation.mask, sequence.raw_frames[2])
        self.assertEqual(frame2_annotation.metrics.area_px, expected_frame2_metrics.area_px)
        self.assertEqual(frame2_annotation.metrics.perimeter_px, expected_frame2_metrics.perimeter_px)
        self.assertEqual(frame2_annotation.metrics.intensity_sum, expected_frame2_metrics.intensity_sum)
        self.assertEqual(frame2_annotation.metrics.intensity_mean, expected_frame2_metrics.intensity_mean)
        self.assertEqual(frame2_annotation.metrics.intensity_max, expected_frame2_metrics.intensity_max)
        self.assertEqual(frame_last_annotation.visibility.value, "lost")
        self.assertFalse(frame_last_annotation.mask.any())
        self.assertIsNone(frame_last_annotation.metrics.area_px)
        self.assertIsNone(frame_last_annotation.metrics.perimeter_px)
        self.assertIsNone(frame_last_annotation.metrics.intensity_sum)
        self.assertGreater(len(self.window.viewer.viewer._overlay_items), 0)
        self.assertTrue(self.window.track_list_panel.btn_run_selected.isEnabled())
        self.assertIn("SAM2 finished for Track 1.", self.window.statusBar().currentMessage())

        self.window.slider_frame.setValue(2)
        self.assertGreater(len(self.window.viewer.viewer._overlay_items), 0)

    def test_run_selected_samurai_updates_track_annotations_with_samurai_source(self) -> None:
        sequence = load_mpp_sequence(str(SAMPLE_MPP))
        self.assertGreaterEqual(sequence.frame_count, 3)
        self.window.set_sequence(sequence)
        self.window.slider_frame.setValue(1)
        bbox = self.window.viewer.place_bbox_at_pixel(24.0, 24.0)
        self.window.bbox_tools_panel.btn_add_seed.click()
        self.window.track_list_panel.set_mask_tracker_kind(MaskTrackerKind.SAMURAI)

        frame_count = sequence.frame_count - 1
        run_output = self._mask_tracker_output(
            MaskTrackerKind.SAMURAI,
            track_id=1,
            frame_index_offset=1,
            frame_count=frame_count,
            frame_shape=sequence.frame_shape,
            row=10,
            col=11,
        )
        observed_inputs = []

        def fake_run(run_input):
            time.sleep(0.05)
            observed_inputs.append(run_input)
            return run_output

        samurai_backend = self.window._mask_tracker_backends[MaskTrackerKind.SAMURAI]
        with patch.object(samurai_backend, "run", side_effect=fake_run) as run_mock:
            self.window.track_list_panel.btn_run_selected.click()
            self._wait_until(
                lambda: (
                    run_mock.called
                    and self.window.current_tracks()[0].get_annotation(2) is not None
                    and not self.window._is_tracking
                )
            )

        run_mock.assert_called_once()
        self.assertEqual(len(observed_inputs), 1)
        run_input = observed_inputs[0]
        self.assertEqual(run_input.tracker_kind, MaskTrackerKind.SAMURAI)
        self.assertEqual(run_input.track_id, 1)
        self.assertEqual(run_input.frame_index_offset, 1)
        self.assertEqual(run_input.source_view, "raw")
        np.testing.assert_allclose(run_input.frames, np.asarray(sequence.raw_frames[1:], dtype=np.float32))
        np.testing.assert_array_equal(run_input.query_box_xyxy, np.asarray(bbox.as_tuple(), dtype=np.float32))
        track = self.window.current_tracks()[0]
        frame1_annotation = track.get_annotation(1)
        frame2_annotation = track.get_annotation(2)
        self.assertIsNotNone(frame1_annotation)
        self.assertIsNotNone(frame2_annotation)
        self.assertEqual(frame1_annotation.source, AnnotationSource.SAMURAI)
        self.assertEqual(frame2_annotation.source, AnnotationSource.SAMURAI)
        self.assertEqual(frame1_annotation.bbox, BBoxXYXY(11.0, 10.0, 18.0, 16.0))
        self.assertEqual(frame2_annotation.bbox, BBoxXYXY(12.0, 11.0, 19.0, 17.0))
        self.assertTrue(frame1_annotation.mask.any())
        expected_metrics = compute_particle_metrics(frame1_annotation.mask, sequence.raw_frames[1])
        self.assertEqual(frame1_annotation.metrics.area_px, expected_metrics.area_px)
        self.assertEqual(frame1_annotation.metrics.perimeter_px, expected_metrics.perimeter_px)
        self.assertGreater(len(self.window.viewer.viewer._overlay_items), 0)
        self.assertTrue(self.window.track_list_panel.btn_run_selected.isEnabled())
        self.assertIn("SAMURAI finished for Track 1.", self.window.statusBar().currentMessage())

    def test_run_selected_dam4sam_updates_track_annotations_with_dam4sam_source(self) -> None:
        sequence = load_mpp_sequence(str(SAMPLE_MPP))
        self.assertGreaterEqual(sequence.frame_count, 3)
        self.window.set_sequence(sequence)
        self.window.slider_frame.setValue(1)
        bbox = self.window.viewer.place_bbox_at_pixel(24.0, 24.0)
        self.window.bbox_tools_panel.btn_add_seed.click()
        self.window.track_list_panel.set_mask_tracker_kind(MaskTrackerKind.DAM4SAM)

        repaired = np.full_like(sequence.raw_frames, 0.45, dtype=np.float32)
        self.window._repair_frames = repaired

        frame_count = sequence.frame_count - 1
        masks = np.zeros((frame_count, *sequence.frame_shape), dtype=bool)
        masks[0, 12:20, 14:23] = True
        masks[1, 13:21, 15:24] = True
        visible_mask = np.zeros((frame_count,), dtype=bool)
        visible_mask[:2] = True
        mask_bboxes = np.zeros((frame_count, 4), dtype=np.float32)
        mask_bboxes[0] = np.asarray([14.0, 12.0, 23.0, 20.0], dtype=np.float32)
        mask_bboxes[1] = np.asarray([15.0, 13.0, 24.0, 21.0], dtype=np.float32)
        run_output = MaskTrackerRunOutput(
            tracker_kind=MaskTrackerKind.DAM4SAM,
            track_id=1,
            frame_index_offset=1,
            masks=masks,
            visible_mask=visible_mask,
            mask_bboxes_xyxy=mask_bboxes,
            mask_scores=visible_mask.astype(np.float32),
            model_name="dam4sam",
            model_variant="sam21pp-B",
            checkpoint_name="sam2.1_hiera_base_plus.pt",
        )

        observed_inputs = []

        def fake_run(run_input):
            time.sleep(0.05)
            observed_inputs.append(run_input)
            self.assertEqual(run_input.tracker_kind, MaskTrackerKind.DAM4SAM)
            self.assertEqual(run_input.track_id, 1)
            self.assertEqual(run_input.frame_index_offset, 1)
            self.assertEqual(run_input.source_view, "repair")
            np.testing.assert_array_equal(run_input.frames, repaired[1:])
            np.testing.assert_array_equal(run_input.query_box_xyxy, np.asarray(bbox.as_tuple(), dtype=np.float32))
            return run_output

        dam4sam_backend = self.window._mask_tracker_backends[MaskTrackerKind.DAM4SAM]
        with patch.object(dam4sam_backend, "run", side_effect=fake_run) as run_mock:
            self.window.track_list_panel.btn_run_selected.click()
            self._wait_until(
                lambda: (
                    run_mock.called
                    and self.window.current_tracks()[0].get_annotation(2) is not None
                    and not self.window._is_tracking
                )
            )

        run_mock.assert_called_once()
        self.assertEqual(len(observed_inputs), 1)
        track = self.window.current_tracks()[0]
        frame1_annotation = track.get_annotation(1)
        frame2_annotation = track.get_annotation(2)
        self.assertIsNotNone(frame1_annotation)
        self.assertIsNotNone(frame2_annotation)
        self.assertEqual(frame1_annotation.source, AnnotationSource.DAM4SAM)
        self.assertEqual(frame2_annotation.source, AnnotationSource.DAM4SAM)
        self.assertEqual(frame1_annotation.bbox, BBoxXYXY(14.0, 12.0, 23.0, 20.0))
        self.assertEqual(frame2_annotation.bbox, BBoxXYXY(15.0, 13.0, 24.0, 21.0))
        self.assertTrue(frame1_annotation.mask.any())
        expected_metrics = compute_particle_metrics(frame1_annotation.mask, sequence.raw_frames[1])
        self.assertEqual(frame1_annotation.metrics.area_px, expected_metrics.area_px)
        self.assertEqual(frame1_annotation.metrics.perimeter_px, expected_metrics.perimeter_px)
        self.assertGreater(len(self.window.viewer.viewer._overlay_items), 0)
        self.assertTrue(self.window.track_list_panel.btn_run_selected.isEnabled())
        self.assertIn("DAM4SAM finished for Track 1.", self.window.statusBar().currentMessage())

    @patch("nanotrack.ui.main_window.QMessageBox.critical")
    def test_run_selected_dam4sam_failure_uses_backend_label_and_keeps_seed_only(self, critical_mock) -> None:
        sequence = load_mpp_sequence(str(SAMPLE_MPP))
        self.assertGreaterEqual(sequence.frame_count, 3)
        self.window.set_sequence(sequence)
        self.window.slider_frame.setValue(1)
        self.window.viewer.place_bbox_at_pixel(24.0, 24.0)
        self.window.bbox_tools_panel.btn_add_seed.click()
        self.window.track_list_panel.set_mask_tracker_kind(MaskTrackerKind.DAM4SAM)

        dam4sam_backend = self.window._mask_tracker_backends[MaskTrackerKind.DAM4SAM]
        with patch.object(dam4sam_backend, "run", side_effect=RuntimeError("DAM4SAM worker failed.")) as run_mock:
            self.window.track_list_panel.btn_run_selected.click()
            self._wait_until(lambda: critical_mock.called and not self.window._is_tracking, attempts=350)

        run_mock.assert_called_once()
        critical_mock.assert_called_once()
        self.assertEqual(critical_mock.call_args.args[1], "DAM4SAM error")
        self.assertIn("DAM4SAM worker failed.", critical_mock.call_args.args[2])
        self.assertEqual(self.window.statusBar().currentMessage(), "DAM4SAM run failed.")
        track = self.window.current_tracks()[0]
        self.assertIsNotNone(track.get_annotation(1))
        self.assertIsNone(track.get_annotation(2))
        self.assertIsNone(track.get_annotation(sequence.frame_count - 1))
        self.assertTrue(self.window.track_list_panel.btn_run_selected.isEnabled())

    @patch("nanotrack.ui.main_window.QMessageBox.critical")
    def test_run_selected_samurai_failure_uses_backend_label_and_keeps_seed_only(self, critical_mock) -> None:
        sequence = load_mpp_sequence(str(SAMPLE_MPP))
        self.assertGreaterEqual(sequence.frame_count, 3)
        self.window.set_sequence(sequence)
        self.window.slider_frame.setValue(1)
        self.window.viewer.place_bbox_at_pixel(24.0, 24.0)
        self.window.bbox_tools_panel.btn_add_seed.click()
        self.window.track_list_panel.set_mask_tracker_kind(MaskTrackerKind.SAMURAI)

        samurai_backend = self.window._mask_tracker_backends[MaskTrackerKind.SAMURAI]
        with patch.object(samurai_backend, "run", side_effect=RuntimeError("SAMURAI worker failed.")) as run_mock:
            self.window.track_list_panel.btn_run_selected.click()
            self._wait_until(lambda: critical_mock.called and not self.window._is_tracking, attempts=350)

        run_mock.assert_called_once()
        critical_mock.assert_called_once()
        self.assertEqual(critical_mock.call_args.args[1], "SAMURAI error")
        self.assertIn("SAMURAI worker failed.", critical_mock.call_args.args[2])
        self.assertEqual(self.window.statusBar().currentMessage(), "SAMURAI run failed.")
        track = self.window.current_tracks()[0]
        self.assertIsNotNone(track.get_annotation(1))
        self.assertIsNone(track.get_annotation(2))
        self.assertIsNone(track.get_annotation(sequence.frame_count - 1))
        self.assertTrue(self.window.track_list_panel.btn_run_selected.isEnabled())

    def test_default_mask_tracker_selection_runs_existing_sam2_backend_and_writes_source(self) -> None:
        sequence = load_mpp_sequence(str(SAMPLE_MPP))
        self.window.set_sequence(sequence)
        self.window.slider_frame.setValue(0)
        bbox = self.window.viewer.place_bbox_at_pixel(24.0, 24.0)
        self.window.bbox_tools_panel.btn_add_seed.click()

        self.assertEqual(self.window.track_list_panel.current_mask_tracker_kind(), MaskTrackerKind.SAM2)
        self.assertEqual(self.window.track_list_panel.btn_run_selected.text(), "Run for Selected")

        frame_count = sequence.frame_count
        masks = np.zeros((frame_count, *sequence.frame_shape), dtype=bool)
        masks[1, 12:18, 14:21] = True
        visible_mask = np.zeros((frame_count,), dtype=bool)
        visible_mask[1] = True
        mask_bboxes = np.zeros((frame_count, 4), dtype=np.float32)
        mask_bboxes[1] = np.asarray([14.0, 12.0, 21.0, 18.0], dtype=np.float32)
        mask_areas = np.asarray([float(np.count_nonzero(mask)) for mask in masks], dtype=np.float32)
        mask_scores = visible_mask.astype(np.float32) * 0.93
        mask_component_counts = visible_mask.astype(np.int32)
        run_output = Sam2RunOutput(
            track_id=1,
            frame_index_offset=0,
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
            observed_inputs.append(run_input)
            return run_output

        with patch.object(self.window._sam2_backend, "run", side_effect=fake_run) as run_mock:
            self.window.track_list_panel.btn_run_selected.click()
            self._wait_until(
                lambda: (
                    run_mock.called
                    and self.window.current_tracks()[0].get_annotation(1) is not None
                    and self.window.current_tracks()[0].get_annotation(1).source is AnnotationSource.SAM2
                    and not self.window._is_tracking
                )
            )

        run_mock.assert_called_once()
        self.assertEqual(len(observed_inputs), 1)
        run_input = observed_inputs[0]
        self.assertEqual(run_input.track_id, 1)
        self.assertEqual(run_input.frame_index_offset, 0)
        self.assertEqual(run_input.source_view, "raw")
        np.testing.assert_array_equal(run_input.frames, np.asarray(sequence.raw_frames, dtype=np.float32))
        np.testing.assert_array_equal(run_input.query_box_xyxy, np.asarray(bbox.as_tuple(), dtype=np.float32))
        track = self.window.current_tracks()[0]
        self.assertEqual(track.get_annotation(0).source, AnnotationSource.SAM2)
        annotation = track.get_annotation(1)
        self.assertEqual(annotation.source, AnnotationSource.SAM2)
        self.assertEqual(annotation.bbox, BBoxXYXY(14.0, 12.0, 21.0, 18.0))
        self.assertTrue(annotation.mask.any())
        self.assertIn("SAM2 finished for Track 1.", self.window.statusBar().currentMessage())

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

    def test_run_all_dam4sam_updates_multiple_tracks_with_dam4sam_source(self) -> None:
        sequence = load_mpp_sequence(str(SAMPLE_MPP))
        self.assertGreaterEqual(sequence.frame_count, 4)
        self.window.set_sequence(sequence)

        self.window.slider_frame.setValue(0)
        self.window.viewer.place_bbox_at_pixel(20.0, 20.0)
        self.window.bbox_tools_panel.btn_add_seed.click()

        self.window.slider_frame.setValue(2)
        self.window.viewer.place_bbox_at_pixel(32.0, 28.0)
        self.window.bbox_tools_panel.btn_add_seed.click()
        self.window.track_list_panel.set_mask_tracker_kind(MaskTrackerKind.DAM4SAM)

        observed_inputs = []

        def fake_run(run_input):
            time.sleep(0.05)
            observed_inputs.append((run_input.tracker_kind, run_input.track_id, run_input.frame_index_offset))
            self.assertEqual(run_input.tracker_kind, MaskTrackerKind.DAM4SAM)
            if run_input.track_id == 1:
                return self._mask_tracker_output(
                    MaskTrackerKind.DAM4SAM,
                    track_id=1,
                    frame_index_offset=0,
                    frame_count=int(run_input.frames.shape[0]),
                    frame_shape=tuple(run_input.frames.shape[1:3]),
                    row=8,
                    col=10,
                )
            return self._mask_tracker_output(
                MaskTrackerKind.DAM4SAM,
                track_id=2,
                frame_index_offset=2,
                frame_count=int(run_input.frames.shape[0]),
                frame_shape=tuple(run_input.frames.shape[1:3]),
                row=18,
                col=22,
            )

        dam4sam_backend = self.window._mask_tracker_backends[MaskTrackerKind.DAM4SAM]
        with patch.object(dam4sam_backend, "run", side_effect=fake_run) as run_mock:
            self.window.track_list_panel.btn_run_all.click()
            self._wait_until(
                lambda: (
                    run_mock.call_count == 2
                    and self.window.current_tracks()[0].get_annotation(1) is not None
                    and self.window.current_tracks()[1].get_annotation(3) is not None
                    and not self.window._is_tracking
                ),
                attempts=350,
            )

        self.assertEqual(observed_inputs, [(MaskTrackerKind.DAM4SAM, 1, 0), (MaskTrackerKind.DAM4SAM, 2, 2)])
        tracks = self.window.current_tracks()
        self.assertEqual(tracks[0].get_annotation(0).source, AnnotationSource.DAM4SAM)
        self.assertEqual(tracks[0].get_annotation(1).source, AnnotationSource.DAM4SAM)
        self.assertEqual(tracks[1].get_annotation(2).source, AnnotationSource.DAM4SAM)
        self.assertEqual(tracks[1].get_annotation(3).source, AnnotationSource.DAM4SAM)
        self.assertEqual(tracks[0].get_annotation(1).bbox, BBoxXYXY(11.0, 9.0, 18.0, 15.0))
        self.assertEqual(tracks[1].get_annotation(3).bbox, BBoxXYXY(23.0, 19.0, 30.0, 25.0))
        self.assertTrue(self.window.track_list_panel.btn_run_all.isEnabled())
        self.assertTrue(
            self.window.statusBar().currentMessage()
            in {"DAM4SAM finished for all 2 seeds.", "DAM4SAM batch 2/2 finished: Track 2"}
        )

    @patch("nanotrack.ui.main_window.QMessageBox.warning")
    def test_run_all_samurai_continues_after_single_track_failure(self, warning_mock) -> None:
        sequence = load_mpp_sequence(str(SAMPLE_MPP))
        self.assertGreaterEqual(sequence.frame_count, 4)
        self.window.set_sequence(sequence)

        self.window.slider_frame.setValue(0)
        self.window.viewer.place_bbox_at_pixel(20.0, 20.0)
        self.window.bbox_tools_panel.btn_add_seed.click()

        self.window.slider_frame.setValue(2)
        self.window.viewer.place_bbox_at_pixel(32.0, 28.0)
        self.window.bbox_tools_panel.btn_add_seed.click()
        self.window.track_list_panel.set_mask_tracker_kind(MaskTrackerKind.SAMURAI)

        def fake_run(run_input):
            time.sleep(0.05)
            self.assertEqual(run_input.tracker_kind, MaskTrackerKind.SAMURAI)
            if run_input.track_id == 1:
                raise RuntimeError("simulated SAMURAI crash")
            return self._mask_tracker_output(
                MaskTrackerKind.SAMURAI,
                track_id=2,
                frame_index_offset=2,
                frame_count=int(run_input.frames.shape[0]),
                frame_shape=tuple(run_input.frames.shape[1:3]),
                row=18,
                col=22,
            )

        samurai_backend = self.window._mask_tracker_backends[MaskTrackerKind.SAMURAI]
        with patch.object(samurai_backend, "run", side_effect=fake_run) as run_mock:
            self.window.track_list_panel.btn_run_all.click()
            self._wait_until(
                lambda: (
                    run_mock.call_count == 2
                    and self.window.current_tracks()[1].get_annotation(2) is not None
                    and not self.window._is_tracking
                ),
                attempts=350,
            )
            self._wait_until(lambda: warning_mock.called, attempts=50)

        self.assertEqual(run_mock.call_count, 2)
        tracks = self.window.current_tracks()
        self.assertIsNone(tracks[0].get_annotation(1))
        self.assertEqual(tracks[1].get_annotation(2).source, AnnotationSource.SAMURAI)
        self.assertEqual(tracks[1].get_annotation(2).bbox, BBoxXYXY(22.0, 18.0, 29.0, 24.0))
        warning_mock.assert_called_once()
        self.assertIn("SAMURAI finished with failures for 1/2 seeds", warning_mock.call_args.args[2])
        self.assertIn("Failed track IDs: 1", warning_mock.call_args.args[2])
        self.assertTrue(self.window.track_list_panel.btn_run_all.isEnabled())

    @patch("nanotrack.ui.main_window.QMessageBox.warning")
    def test_run_all_sam2_continues_after_single_track_failure(self, warning_mock) -> None:
        sequence = load_mpp_sequence(str(SAMPLE_MPP))
        self.assertGreaterEqual(sequence.frame_count, 4)
        self.window.set_sequence(sequence)

        self.window.slider_frame.setValue(0)
        self.window.viewer.place_bbox_at_pixel(20.0, 20.0)
        self.window.bbox_tools_panel.btn_add_seed.click()

        self.window.slider_frame.setValue(2)
        self.window.viewer.place_bbox_at_pixel(32.0, 28.0)
        self.window.bbox_tools_panel.btn_add_seed.click()

        def build_output(track_id: int, frame_index_offset: int, frame_count: int, frame_shape: tuple[int, int]):
            masks = np.zeros((frame_count, *frame_shape), dtype=bool)
            visible_mask = np.zeros((frame_count,), dtype=bool)
            mask_bboxes = np.zeros((frame_count, 4), dtype=np.float32)
            masks[0, 18:24, 22:29] = True
            visible_mask[0] = True
            mask_bboxes[0] = np.asarray([22.0, 18.0, 29.0, 24.0], dtype=np.float32)
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

        def fake_run(run_input):
            time.sleep(0.05)
            if run_input.track_id == 1:
                raise RuntimeError("simulated native crash")
            return build_output(
                run_input.track_id,
                run_input.frame_index_offset,
                int(run_input.frames.shape[0]),
                tuple(run_input.frames.shape[1:3]),
            )

        with patch.object(self.window._sam2_backend, "run", side_effect=fake_run) as run_mock:
            self.window.track_list_panel.btn_run_all.click()
            for _ in range(300):
                self.__class__._app.processEvents()
                track2 = self.window.current_tracks()[1]
                if run_mock.call_count == 2 and track2.get_annotation(2) is not None:
                    break
                time.sleep(0.01)
            for _ in range(20):
                self.__class__._app.processEvents()
                if warning_mock.called:
                    break
                time.sleep(0.01)

        self.assertEqual(run_mock.call_count, 2)
        tracks = self.window.current_tracks()
        self.assertIsNone(tracks[0].get_annotation(1))
        self.assertIsNotNone(tracks[1].get_annotation(2))
        warning_mock.assert_called_once()
        self.assertIn("1/2 seeds", warning_mock.call_args.args[2])
        self.assertIn("Failed track IDs: 1", warning_mock.call_args.args[2])
        self.assertIn(
            self.window.statusBar().currentMessage(),
            {"SAM2 finished with failures for 1/2 seeds.", "SAM2 batch 2/2 finished: Track 2"},
        )
        self.assertTrue(self.window.track_list_panel.btn_run_all.isEnabled())


if __name__ == "__main__":
    unittest.main()
