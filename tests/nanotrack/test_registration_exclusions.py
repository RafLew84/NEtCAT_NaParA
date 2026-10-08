"""Registration exclusions preserve analyses through public GUI workflows."""
import os
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import time
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import numpy as np
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtTest import QTest

from nanotrack.app import configure_pyqtgraph
from nanotrack.core import (
    BBoxXYXY, EdgeFrameAnnotation, EdgeMetrics, EdgeTrack, ParticleMetrics,
    ParticleTrack, PolygonROI, RegistrationFrameResult, RegistrationResultSet,
    RegistrationSettings, TrackFrameAnnotation, YoloDetection, YoloDetectionSet,
)
from nanotrack.io import load_mpp_sequence
from nanotrack.persistence import NanoTrackSessionSnapshot, save_session_snapshot
from nanotrack.ui.main_window import NanoTrackMainWindow
from nanotrack.sam2 import Sam2RunOutput
from nanotrack.edges import DexiNedRunOutput
from nanotrack.trackers import PointTrackerRunOutput


def sample_session(directory: Path, *, invalid_excluded=False) -> Path:
    source = directory / "exclusions.MPP"
    base = np.random.default_rng(7).normal(size=(64, 64))
    # Known image translations for GUI frames 9, 10, 11. Frame 10 is deliberately unrelated.
    frames = np.stack([base.copy() for _ in range(12)])
    frames[8] = np.roll(base, (1, -2), axis=(0, 1))
    frames[9] = np.random.default_rng(8).normal(size=(64, 64))
    if invalid_excluded:
        frames[9] = np.nan
    frames[10] = np.roll(base, (-2, 3), axis=(0, 1))
    header = "[General Info]\nNumber of columns: 64\nNumber of rows: 64\nNumber of Frames: 12\n[Header end]\n"
    source.write_bytes(header.encode("ascii") + frames[:, ::-1, ::-1].astype("<f8").tobytes())
    sequence = load_mpp_sequence(str(source))
    sequence.set_active_frame(9)
    bbox = BBoxXYXY(12., 15., 16., 19.)
    polygon = PolygonROI(((8., 8.), (40., 8.), (40., 40.), (8., 40.)))
    line = np.array([[12., 24.], [32., 24.]])
    mask = np.zeros((64, 64), bool)
    mask[15:19, 12:16] = True
    particle = ParticleTrack(1, 8, bbox, annotations={9: TrackFrameAnnotation(
        9, bbox=bbox, mask=mask, metrics=ParticleMetrics(area_px=16.),
    )})
    edge = EdgeTrack(1, 8, polygon, line, annotations={9: EdgeFrameAnnotation(
        9, polyline=line, edge_mask=mask, metrics=EdgeMetrics(length_px=20.),
    )})
    path = directory / "exclusions.nanotrack"
    save_session_snapshot(str(path), NanoTrackSessionSnapshot(
        sequence, tracks=[particle, ParticleTrack(2, 9, bbox)],
        edge_tracks=[edge, EdgeTrack(2, 9, polygon, line)],
        selected_track_id=1, selected_edge_track_id=1,
        yolo_detections=YoloDetectionSet("fixture", str(source), {9: [YoloDetection(9, bbox, .8, model_name="fixture")]}),
        draft_bboxes_by_frame={9: bbox}, draft_polygons_by_frame={8: polygon, 9: polygon},
        draft_edge_polylines_by_frame={9: line},
        registration_results=RegistrationResultSet(RegistrationSettings(), {
            8: RegistrationFrameResult(8, (2., -1.), "manual"),
            9: RegistrationFrameResult(9, (-7.25, 4.5), "manual", quality_score=.75),
            10: RegistrationFrameResult(10, (-3., 2.), "manual"),
        }),
    ))
    return path


class RegistrationExclusionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        configure_pyqtgraph()

    def window(self, path):
        window = NanoTrackMainWindow()
        self.addCleanup(window.close)
        window.load_session_from_path(str(path))
        return window

    def assert_analyses_equal(self, before, after):
        for field in ("tracks", "edge_tracks", "yolo_detections", "draft_bboxes_by_frame",
                      "draft_polygons_by_frame", "draft_edge_polylines_by_frame", "registration_results"):
            np.testing.assert_equal(asdict(before)[field], asdict(after)[field], err_msg=field)

    def test_exclude_restore_and_save_open_preserve_all_existing_analysis(self):
        with TemporaryDirectory() as directory:
            window = self.window(sample_session(Path(directory)))
            before = deepcopy(window.current_session_snapshot())
            window.chk_exclude_frame.setChecked(True)
            self.assert_analyses_equal(before, window.current_session_snapshot())

            self.assertEqual(window.chk_exclude_frame.text(), "Wyklucz z rejestracji")
            window.chk_hide_excluded_frames.setChecked(True)
            self.assertEqual(window.spin_frame.value(), 9)
            window.btn_next.click()
            self.assertEqual(window.spin_frame.value(), 11)
            saved = Path(directory) / "saved.nanotrack"
            window.save_session_to_path(str(saved))
            window.load_session_from_path(str(saved))
            self.assertTrue(window.chk_hide_excluded_frames.isChecked())
            self.assertEqual(window.current_session_snapshot().sequence.sorted_excluded_frame_indices(), [9])
            self.assert_analyses_equal(before, window.current_session_snapshot())
            window.chk_hide_excluded_frames.setChecked(False)
            window.spin_frame.setValue(10)
            window.chk_exclude_frame.setChecked(False)
            self.assertEqual(window.current_session_snapshot().sequence.sorted_excluded_frame_indices(), [])
            self.assert_analyses_equal(before, window.current_session_snapshot())

    def test_new_registration_skips_excluded_pairs_and_preserves_only_own_result(self):
        with TemporaryDirectory() as directory:
            window = self.window(sample_session(Path(directory)))
            window.chk_exclude_frame.setChecked(True)  # Frame 10 has its own manual dx/dy.
            window.spin_frame.setValue(12)
            window.chk_exclude_frame.setChecked(True)  # Frame 12 has no previous result.
            window.action_run_registration.trigger()
            snapshot = window.current_session_snapshot()
            result = snapshot.registration_results
            np.testing.assert_allclose(result.get_result(8).shift_xy, (2., -1.), atol=.05)
            np.testing.assert_allclose(result.get_result(10).shift_xy, (-3., 2.), atol=.05)
            self.assertEqual(result.get_result(9).shift_xy, (-7.25, 4.5))
            self.assertEqual(result.get_result(9).method, "manual")
            self.assertEqual(result.get_result(9).quality_score, .75)
            self.assertFalse(result.get_result(9).recomputed)
            self.assertIsNone(result.get_result(11))
            self.assertTrue(result.get_result(10).recomputed)
            saved = Path(directory) / "registered.nanotrack"
            window.save_session_to_path(str(saved))
            window.load_session_from_path(str(saved))
            np.testing.assert_equal(asdict(result), asdict(window.current_session_snapshot().registration_results))

    def run_button(self, button):
        self.assertTrue(button.isEnabled())
        button.click()
        deadline = time.monotonic() + 10
        while not button.isEnabled() and time.monotonic() < deadline:
            QTest.qWait(10)
        self.assertTrue(button.isEnabled(), "Operation did not finish")
        QTest.qWait(30)

    def test_particle_and_edge_ranges_include_hidden_excluded_frame(self):
        with TemporaryDirectory() as directory:
            window = self.window(sample_session(Path(directory)))
            window.chk_exclude_frame.setChecked(True)
            window.chk_hide_excluded_frames.setChecked(True)
            self.assertEqual(window.spin_frame.value(), 9)
            window.track_list_panel.sp_run_frame_limit.setValue(3)
            window.polygon_tools_panel.sp_run_end_frame.setValue(11)
            particle_calls, edge_calls = [], []

            def particle_model(_backend, run):
                particle_calls.append(run)
                masks = np.zeros((3, 64, 64), bool)
                masks[:, 15:19, 12:16] = True
                return Sam2RunOutput(1, 8, masks, np.ones(3, bool))

            def edge_model(_backend, run):
                edge_calls.append(run)
                probability = np.zeros((3, 64, 64), np.float32)
                probability[:, 24, 12:33] = 1.
                return DexiNedRunOutput(probability)

            with patch("nanotrack.sam2.backend.Sam2SubprocessBackend.run", particle_model), \
                 patch("nanotrack.edges.backend.DexiNedSubprocessBackend.run", edge_model), \
                 patch.object(QMessageBox, "critical") as errors:
                self.run_button(window.track_list_panel.btn_run_selected)
                self.run_button(window.polygon_tools_panel.btn_run_sequence)
                self.assertFalse(errors.called, errors.call_args)
            self.assertEqual(len(particle_calls), 1)
            self.assertEqual(particle_calls[0].frames.shape[0], 3)
            np.testing.assert_array_equal(edge_calls[0].frame_indices, [8, 9, 10])
            particle = window.current_tracks()[0]
            edge = window.current_edge_tracks()[-1]
            self.assertEqual(particle.frame_indices, [8, 9, 10])
            self.assertEqual(edge.frame_indices, [8, 9, 10])
            self.assertEqual(particle.get_annotation(9).metrics.valid_sample_count, 16)
            self.assertIsNotNone(edge.get_annotation(9).metrics.length_px)
            saved = Path(directory) / "tracked.nanotrack"
            window.save_session_to_path(str(saved))
            before = deepcopy(window.current_session_snapshot())
            window.load_session_from_path(str(saved))
            self.assert_analyses_equal(before, window.current_session_snapshot())

    def test_point_tracking_accepts_excluded_anchor_and_excluded_interior_frame(self):
        for start in (8, 9):
            with self.subTest(start=start), TemporaryDirectory() as directory:
                window = self.window(sample_session(Path(directory)))
                window.chk_exclude_frame.setChecked(True)
                window.spin_frame.setValue(start + 1)
                window.polygon_tools_panel.btn_load_edge.click()
                window.polygon_tools_panel.sp_tracker_points.setValue(4)
                calls = []

                def model(_backend, run):
                    calls.append(run)
                    tracks = np.zeros((4, len(run.frames), 2), np.float32)
                    tracks[:, :, 0] = np.linspace(12, 32, 4)[:, None]
                    tracks[:, :, 1] = 24 + np.arange(len(run.frames))[None, :]
                    return PointTrackerRunOutput(tracks, np.ones(tracks.shape[:2], bool), model_name="tapir")

                with patch("nanotrack.trackers.backend.PointTrackerSubprocessBackend.run", model), \
                     patch.object(QMessageBox, "warning") as warnings, patch.object(QMessageBox, "critical") as errors:
                    self.run_button(window.polygon_tools_panel.btn_hybrid)
                    self.assertFalse(warnings.called, warnings.call_args)
                    self.assertFalse(errors.called, errors.call_args)
                self.assertEqual(len(calls), 1)
                track = window.current_edge_tracks()[0]
                self.assertEqual(track.frame_indices, list(range(8, 12)))
                self.assertEqual(track.get_annotation(10).source.value, "tracker_refine")
                if start == 8:
                    self.assertEqual(track.get_annotation(9).source.value, "tracker_refine")

    def test_detection_on_all_frames_includes_registration_exclusions(self):
        from nanotrack.yolo import YoloModelInfo
        from nanotrack.yolo.runtime import YoloRuntimeDetection

        with TemporaryDirectory() as directory:
            window = self.window(sample_session(Path(directory)))
            window.chk_exclude_frame.setChecked(True)
            window.chk_hide_excluded_frames.setChecked(True)
            window.yolo_panel.refresh_models([YoloModelInfo("fixture.pt", str(Path(directory) / "fixture.pt"))])
            detection = YoloRuntimeDetection(BBoxXYXY(12., 15., 16., 19.), .9, "fixture.pt")
            with patch("nanotrack.yolo.runtime.YoloRuntime.predict_frame", return_value=[detection]):
                window.yolo_panel.btn_detect_all.click()
            result = window.current_yolo_detection_set()
            self.assertEqual(result.detection_count, 12)
            self.assertEqual(result.get_detections(9)[0].bbox.as_tuple(), (12., 15., 16., 19.))

    def test_registration_does_not_read_invalid_pixels_of_excluded_frame(self):
        with TemporaryDirectory() as directory:
            window = self.window(sample_session(Path(directory), invalid_excluded=True))
            window.chk_exclude_frame.setChecked(True)
            with patch.object(QMessageBox, "critical") as errors:
                window.action_run_registration.trigger()
                self.assertFalse(errors.called, errors.call_args)
            snapshot = window.current_session_snapshot()
            self.assertEqual(snapshot.registration_results.get_result(9).shift_xy, (-7.25, 4.5))
            np.testing.assert_allclose(snapshot.registration_results.get_result(10).shift_xy, (-3., 2.), atol=.05)
            self.assertTrue(np.isnan(snapshot.sequence.get_frame(9)).all())
