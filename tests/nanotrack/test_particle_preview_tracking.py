"""Start and Save/Open through Qt, with only the external model replaced."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import time
import threading
from copy import deepcopy
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import numpy as np
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtTest import QTest

from nanotrack.app import configure_pyqtgraph
from nanotrack.core import BBoxXYXY, ParticleTrack, RegistrationFrameResult, RegistrationResultSet, RegistrationSettings
from nanotrack.core.preview_sources import PreprocessingProvenance, PreprocessingStep
from nanotrack.io import load_mpp_sequence
from nanotrack.persistence.session_store import NanoTrackSessionSnapshot, save_session_snapshot, load_session_snapshot
from nanotrack.sam2 import Sam2RunOutput
from nanotrack.ui.main_window import NanoTrackMainWindow
from nanotrack.yolo import YoloModelInfo
from nanotrack.yolo.runtime import YoloRuntimeDetection


def sample_session(directory: Path) -> Path:
    source = directory / "known.MPP"
    raw = np.arange(128, dtype=np.float64).reshape(2, 8, 8) + 0.125
    header = "[General Info]\nNumber of columns: 8\nNumber of rows: 8\nNumber of Frames: 2\n[Header end]\n"
    source.write_bytes(header.encode("ascii") + raw[:, ::-1, ::-1].astype("<f8").tobytes())
    sequence = load_mpp_sequence(str(source))
    sequence.set_active_frame(1)
    session = directory / "known.nanotrack"
    save_session_snapshot(str(session), NanoTrackSessionSnapshot(
        sequence, tracks=[ParticleTrack(1, 1, BBoxXYXY(1., 2., 3., 4.))], selected_track_id=1,
        denoised_frames=raw + 1000.,
        preprocessing_provenance=PreprocessingProvenance(
            steps=(PreprocessingStep("fixture", "Known preprocessing"),), revision="known-processed-1",
        ),
        registration_results=RegistrationResultSet(RegistrationSettings(), {
            0: RegistrationFrameResult(0, (-1., 0.), "manual"),
            1: RegistrationFrameResult(1, (2., -1.), "manual"),
        }),
        show_aligned_in_viewer=True,
    ))
    return session


class ParticlePreviewTrackingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        configure_pyqtgraph()
        cls.app = QApplication.instance() or QApplication([])

    def test_start_uses_selected_raw_aligned_and_returns_clipped_source_mask(self):
        with TemporaryDirectory() as directory:
            window = NanoTrackMainWindow()
            self.addCleanup(window.close)
            window.load_session_from_path(str(sample_session(Path(directory))))
            calls = []

            def model(_backend, run):
                calls.append(run)
                mask = np.zeros((1, 8, 8), bool)
                mask[0, 1:3, 3:5] = True  # source rectangle (1,2)-(3,4)
                mask[0, 7, 0] = True  # missing input: must be discarded
                return Sam2RunOutput(1, 1, mask, np.array([True]))

            with patch("nanotrack.sam2.backend.Sam2SubprocessBackend.run", model), patch.object(QMessageBox, "critical") as errors:
                window.track_list_panel.btn_run_selected.click()
                deadline = time.monotonic() + 10
                while not window.track_list_panel.btn_run_selected.isEnabled() and time.monotonic() < deadline:
                    QTest.qWait(10)
                self.assertFalse(errors.called, errors.call_args)
                self.assertTrue(window.track_list_panel.btn_run_selected.isEnabled())
            self.assertEqual(len(calls), 1)
            run = calls[0]
            self.assertEqual(run.source_view, "raw+registration")
            np.testing.assert_array_equal(run.query_box_xyxy, [3., 1., 5., 3.])
            self.assertEqual(float(run.frames[0, 1, 3]), 81.125)
            self.assertTrue(np.isfinite(run.frames).all())
            annotation = window.current_session_snapshot().tracks[0].get_annotation(1)
            expected = np.zeros((8, 8), bool)
            expected[2:4, 1:3] = True
            np.testing.assert_array_equal(annotation.mask, expected)
            self.assertEqual(annotation.bbox.as_tuple(), (1., 2., 3., 4.))
            self.assertEqual(annotation.metrics.intensity_sum, 342.5)
            self.assertEqual(annotation.metrics.valid_sample_count, 4)

    def test_subpixel_masks_keep_nearest_samples_at_both_source_edges_in_both_canvases(self):
        cases = [(.25, False, 7, 8, (7., 3., 8., 5.)), (-.25, False, 0, 8, (0., 3., 1., 5.)),
                 (.25, True, 8, 10, (7., 3., 8., 5.)), (-.25, True, 1, 9, (0., 3., 1., 5.))]
        for dx, expanded, edge, width, expected_box in cases:
            with self.subTest(dx=dx, expanded=expanded), TemporaryDirectory() as directory:
                session = sample_session(Path(directory))
                snapshot = load_session_snapshot(str(session))
                snapshot.registration_results.results_by_frame[1] = RegistrationFrameResult(1, (dx, 0.), "manual")
                save_session_snapshot(str(session), snapshot)
                window = NanoTrackMainWindow()
                self.addCleanup(window.close)
                window.load_session_from_path(str(session))
                if expanded:
                    window.action_show_expanded_aligned_registration.setChecked(True)

                def model(_backend, run):
                    mask = np.zeros((1, 8, width), bool)
                    mask[0, 3:5, edge] = True
                    return Sam2RunOutput(1, 1, mask, np.array([True]))

                with patch("nanotrack.sam2.backend.Sam2SubprocessBackend.run", model):
                    window.track_list_panel.btn_run_selected.click()
                    deadline = time.monotonic() + 10
                    while not window.track_list_panel.btn_run_selected.isEnabled() and time.monotonic() < deadline:
                        QTest.qWait(10)
                    self.assertTrue(window.track_list_panel.btn_run_selected.isEnabled())
                annotation = window.current_tracks()[0].get_annotation(1)
                self.assertIsNotNone(annotation.bbox)
                self.assertEqual(annotation.bbox.as_tuple(), expected_box)
                self.assertEqual(annotation.metrics.valid_sample_count, 2)

    def test_detect_current_uses_selected_aligned_frame_and_rejects_missing_area(self):
        with TemporaryDirectory() as directory:
            window = NanoTrackMainWindow()
            self.addCleanup(window.close)
            window.load_session_from_path(str(sample_session(Path(directory))))
            window.yolo_panel.refresh_models([YoloModelInfo("known.pt", str(Path(directory) / "known.pt"))])
            calls = []

            def detect(_runtime, frame, **kwargs):
                calls.append(frame.copy())
                return [YoloRuntimeDetection(BBoxXYXY(3., 1., 5., 3.), .9, "known.pt"),
                        YoloRuntimeDetection(BBoxXYXY(0., 7., 2., 8.), .9, "known.pt")]

            with patch("nanotrack.yolo.runtime.YoloRuntime.predict_frame", detect):
                window.yolo_panel.btn_detect_current.click()
            self.assertEqual(float(calls[0][1, 3]), 81.125)
            detections = window.current_yolo_detection_set().get_detections(1)
            self.assertEqual(len(detections), 1)
            self.assertEqual(detections[0].bbox.as_tuple(), (1., 2., 3., 4.))
            self.assertEqual(detections[0].shape_provenance.offset_xy, (2., -1.))
            result = Path(directory) / "detections.nanotrack"
            window.save_session_to_path(str(result))
            window.load_session_from_path(str(result))
            restored = window.current_yolo_detection_set().get_detections(1)[0]
            self.assertEqual(restored.shape_provenance, detections[0].shape_provenance)
            window.yolo_panel.btn_convert_current.click()
            seed = window.current_tracks()[-1].get_annotation(1)
            self.assertEqual(seed.shape_provenance, restored.shape_provenance)
            self.assertEqual(seed.source.value, "yolo")

    def test_processed_expanded_execution_keeps_provenance_and_measurements_after_view_changes_and_open(self):
        with TemporaryDirectory() as directory:
            window = NanoTrackMainWindow()
            self.addCleanup(window.close)
            window.load_session_from_path(str(sample_session(Path(directory))))
            window.cmb_preview_source.setCurrentIndex(1)
            window.action_show_expanded_aligned_registration.setChecked(True)
            self.assertIn("Expanded", window.track_list_panel.lbl_input.text())
            started, release = threading.Event(), threading.Event()
            self.addCleanup(release.set)
            calls = []

            def model(_backend, run):
                calls.append(run)
                started.set()
                release.wait(5)
                mask = np.zeros((1, 9, 11), bool)
                mask[0, 2:4, 4:6] = True
                return Sam2RunOutput(1, 1, mask, np.array([True]))

            with patch("nanotrack.sam2.backend.Sam2SubprocessBackend.run", model), patch.object(QMessageBox, "critical") as errors:
                window.track_list_panel.btn_run_selected.click()
                deadline = time.monotonic() + 10
                while not started.is_set() and time.monotonic() < deadline:
                    QTest.qWait(10)
                self.assertTrue(started.is_set())
                window.action_show_expanded_aligned_registration.setChecked(False)
                window.cmb_preview_source.setCurrentIndex(0)
                release.set()
                while not window.track_list_panel.btn_run_selected.isEnabled() and time.monotonic() < deadline:
                    QTest.qWait(10)
                self.assertFalse(errors.called, errors.call_args)
                self.assertTrue(window.track_list_panel.btn_run_selected.isEnabled())
            np.testing.assert_array_equal(calls[0].query_box_xyxy, [4., 2., 6., 4.])
            self.assertEqual(float(calls[0].frames[0, 2, 4]), 1081.125)
            annotation = window.current_tracks()[0].get_annotation(1)
            self.assertEqual(annotation.bbox.as_tuple(), (1., 2., 3., 4.))
            self.assertEqual(annotation.metrics.intensity_sum, 342.5)
            self.assertEqual(annotation.shape_provenance.source_revision, "known-processed-1")
            self.assertEqual(annotation.shape_provenance.offset_xy, (3., 0.))
            self.assertEqual(annotation.shape_provenance.canvas_shape_hw, (9, 11))
            self.assertEqual(annotation.measurement_provenance.source_view, "raw")
            self.assertEqual(annotation.metrics.valid_sample_count, 4)
            saved = deepcopy(annotation)
            window.action_show_aligned_registration.setChecked(True)
            window.preprocessing_panel.btn_repair_apply_all.click()
            result = Path(directory) / "result.nanotrack"
            window.save_session_to_path(str(result))
            window.load_session_from_path(str(result))
            restored = window.current_tracks()[0].get_annotation(1)
            self.assertEqual(restored.metrics, saved.metrics)
            self.assertEqual(restored.shape_provenance, saved.shape_provenance)
            self.assertEqual(restored.measurement_provenance, saved.measurement_provenance)
            np.testing.assert_array_equal(restored.mask, saved.mask)
