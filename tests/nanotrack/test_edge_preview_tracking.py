"""Selected scientific input and canonical edge results through public Qt controls."""
import os
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import time
import threading
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import numpy as np
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtTest import QTest

from nanotrack.app import configure_pyqtgraph
from nanotrack.core import EdgeTrack, EdgeFrameAnnotation, PolygonROI, RegistrationFrameResult, RegistrationResultSet, RegistrationSettings
from nanotrack.core.preview_sources import PreprocessingProvenance, PreprocessingStep
from nanotrack.edges.contract import DexiNedRunOutput
from nanotrack.io import load_mpp_sequence
from nanotrack.persistence.session_store import NanoTrackSessionSnapshot, save_session_snapshot
from nanotrack.ui.main_window import NanoTrackMainWindow
from nanotrack.ui.dialogs.edge_preview_dialog import EdgePreviewDialog
from nanotrack.trackers.contract import PointTrackerRunOutput


def sample_session(directory, *, empty_last=False, gap_last=False, active=1):
    source = directory / "edge.MPP"
    raw = np.full((3, 24, 32), 10.125, dtype=np.float64)
    if empty_last:
        raw[2] = np.nan
    if gap_last:
        raw[2, :, 14:16] = np.nan
    header = "[General Info]\nNumber of columns: 32\nNumber of rows: 24\nNumber of Frames: 3\n[Header end]\n"
    source.write_bytes(header.encode("ascii") + raw[:, ::-1, ::-1].astype("<f8").tobytes())
    sequence = load_mpp_sequence(str(source))
    sequence.set_active_frame(active)
    polygon = PolygonROI(((5., 7.), (25., 7.), (25., 14.), (5., 14.)))
    path = directory / "edge.nanotrack"
    save_session_snapshot(str(path), NanoTrackSessionSnapshot(
        sequence, draft_polygons_by_frame={active: polygon}, denoised_frames=raw + 1000.,
        preprocessing_provenance=PreprocessingProvenance(
            steps=(PreprocessingStep("fixture", "Known offset"),), revision="edge-processed-1",
        ),
        registration_results=RegistrationResultSet(RegistrationSettings(), {
            0: RegistrationFrameResult(0, (-1., 0.), "manual"),
            1: RegistrationFrameResult(1, (2., -1.), "manual"),
            2: RegistrationFrameResult(2, (-1., 1.), "manual"),
        }), preview_source="original", show_aligned_in_viewer=True,
    ))
    return path


class EdgePreviewTrackingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        configure_pyqtgraph()

    def window(self, path):
        window = NanoTrackMainWindow()
        self.addCleanup(window.close)
        window.load_session_from_path(str(path))
        window.polygon_tools_panel.sp_run_end_frame.setValue(2)
        window.polygon_tools_panel.cmb_refine_score_mode.setCurrentIndex(1)
        return window

    def run_button(self, button):
        self.assertTrue(button.isEnabled())
        button.click()
        deadline = time.monotonic() + 15
        while not button.isEnabled() and time.monotonic() < deadline:
            QTest.qWait(10)
        self.assertTrue(button.isEnabled(), "Operation did not finish")
        QTest.qWait(30)  # Deliver the completed worker's thread-finished signal.

    def test_start_uses_selected_raw_and_aligned_roi_and_returns_source_polyline(self):
        with TemporaryDirectory() as directory:
            window = self.window(sample_session(Path(directory)))
            calls = []

            def model(_backend, run):
                calls.append(run)
                probability = np.zeros((1, 24, 32), np.float32)
                probability[0, 9, 7:27] = 1.  # source x=5..24, y=10; offset (2,-1)
                probability[0, 0, :] = 1.  # outside ROI/valid data
                return DexiNedRunOutput(probability)

            with patch("nanotrack.edges.backend.DexiNedSubprocessBackend.run", model), patch.object(QMessageBox, "critical") as errors:
                self.run_button(window.polygon_tools_panel.btn_run_sequence)
                self.assertFalse(errors.called, errors.call_args)
            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0].source_view, "raw+registration")
            self.assertEqual(float(calls[0].frames[0, 9, 7]), 10.125)
            expected_roi = np.zeros((1, 24, 32), bool)
            expected_roi[0, 6:14, 7:28] = True
            np.testing.assert_array_equal(calls[0].polygon_mask, expected_roi)
            annotation = window.current_edge_tracks()[0].get_annotation(1)
            np.testing.assert_allclose(annotation.polyline[:, 1], 10., atol=1e-8)
            self.assertAlmostEqual(float(annotation.polyline[:, 0].min()), 5.)
            self.assertAlmostEqual(float(annotation.polyline[:, 0].max()), 24.)
            self.assertAlmostEqual(annotation.metrics.length_px, 19.)
            expected_mask = np.zeros((24, 32), bool)
            expected_mask[10, 5:25] = True
            np.testing.assert_array_equal(annotation.edge_mask, expected_mask)

    def test_processed_preview_resume_and_range_redetect_preserve_geometry_and_history(self):
        with TemporaryDirectory() as directory:
            window = self.window(sample_session(Path(directory)))
            window.cmb_preview_source.setCurrentIndex(1)
            window.action_show_expanded_aligned_registration.setChecked(True)
            panel = window.polygon_tools_panel
            panel.sp_run_end_frame.setValue(3)
            # Explicit display positions for source line x=5..24, y=10.
            requests = [([(1, 8, 10)], (26, 35)), ([(1, 8, 10), (2, 5, 12)], (26, 35)),
                        ([(2, 4, 11)], (24, 32)), ([(1, 7, 9), (2, 4, 11)], (24, 32))]
            calls = []

            def model(_backend, run):
                positions, shape = requests[len(calls)]
                calls.append(run)
                probability = np.zeros((len(positions), *shape), np.float32)
                for local, (_, x, y) in enumerate(positions):
                    probability[local, y, x:x+20] = 1.
                return DexiNedRunOutput(probability, model_name="dexined", checkpoint_name="known.pth")

            with patch("nanotrack.edges.backend.DexiNedSubprocessBackend.run", model), patch.object(QMessageBox, "critical") as errors:
                self.run_button(panel.btn_preview)
                self.assertFalse(errors.called, errors.call_args)
                self.assertEqual(calls[0].source_view, "bm3d+expanded_registration")
                self.assertEqual(float(calls[0].frames[0, 10, 8]), 1010.125)
                self.run_button(panel.btn_run_sequence)
                self.assertFalse(errors.called, errors.call_args)
                saved = deepcopy(window.current_edge_tracks()[0])
                for index, offset in [(1, (3., 0.)), (2, (0., 2.))]:
                    annotation = saved.get_annotation(index)
                    np.testing.assert_allclose(annotation.polyline[:, 1], 10., atol=1e-8)
                    self.assertAlmostEqual(annotation.metrics.length_px, 19.)
                    self.assertEqual(annotation.shape_provenance.offset_xy, offset)
                    self.assertEqual(annotation.shape_provenance.source_revision, "edge-processed-1")
                    self.assertEqual(annotation.measurement_provenance.coordinate_space, "original")

                window.cmb_preview_source.setCurrentIndex(0)
                window.action_show_aligned_registration.setChecked(True)
                self.run_button(panel.btn_load_edge)
                self.run_button(panel.btn_resume_edge)
                self.assertFalse(errors.called, errors.call_args)
                resumed = window.current_edge_tracks()[0].get_annotation(2)
                np.testing.assert_allclose(resumed.polyline[:, 1], 10., atol=1e-8)
                self.assertEqual(calls[2].source_view, "raw+registration")
                self.assertEqual(resumed.shape_provenance.source_view, "raw+registration")
                self.run_button(panel.btn_redetect_edge_range)
                self.assertFalse(errors.called, errors.call_args)
                self.assertEqual(calls[3].frame_indices.tolist(), [1, 2])
                track = deepcopy(window.current_edge_tracks()[0])
                window.action_apply_registration.setChecked(False)
                window.action_show_expanded_aligned_registration.setChecked(True)
                path = Path(directory) / "result.nanotrack"
                window.save_session_to_path(str(path))
                window.load_session_from_path(str(path))
                for index in [1, 2]:
                    before, after = track.get_annotation(index), window.current_edge_tracks()[0].get_annotation(index)
                    np.testing.assert_array_equal(after.polyline, before.polyline)
                    self.assertEqual(after.metrics, before.metrics)
                    self.assertEqual(after.shape_provenance, before.shape_provenance)
                    self.assertEqual(after.measurement_provenance, before.measurement_provenance)

    def test_empty_support_produces_lost_edge_and_no_geometric_measurement(self):
        with TemporaryDirectory() as directory:
            window = self.window(sample_session(Path(directory), empty_last=True))
            window.polygon_tools_panel.sp_run_end_frame.setValue(3)
            calls = []

            def model(_backend, run):
                calls.append(run)
                probability = np.zeros((2, 24, 32), np.float32)
                probability[0, 9, 7:27] = 1.
                probability[1, 11, :] = 1.  # no measured input anywhere on this frame
                return DexiNedRunOutput(probability)

            with patch("nanotrack.edges.backend.DexiNedSubprocessBackend.run", model), patch.object(QMessageBox, "critical") as errors:
                self.run_button(window.polygon_tools_panel.btn_run_sequence)
                self.assertFalse(errors.called, errors.call_args)
            self.assertTrue(np.isfinite(calls[0].frames).all())
            self.assertFalse(calls[0].polygon_mask[1].any())
            lost = window.current_edge_tracks()[0].get_annotation(2)
            self.assertEqual(lost.visibility.value, "lost")
            self.assertIsNone(lost.polyline)
            self.assertIsNone(lost.metrics.length_px)
            self.assertEqual(lost.shape_provenance.source_view, "raw+registration")

    def test_point_tracker_freezes_input_and_recovers_only_valid_source_points(self):
        with TemporaryDirectory() as directory:
            window = self.window(sample_session(Path(directory)))
            polyline = np.array([[5., 10.], [24., 10.]])
            window.set_edge_tracks([EdgeTrack(1, 1, window.current_draft_polygon_roi(), polyline,
                annotations={1: EdgeFrameAnnotation(1, polyline=polyline)})], selected_track_id=1)
            window.cmb_preview_source.setCurrentIndex(1)
            window.action_show_expanded_aligned_registration.setChecked(True)
            window.polygon_tools_panel.sp_tracker_points.setValue(4)
            entered, release = threading.Event(), threading.Event()
            self.addCleanup(release.set)
            calls = []

            def model(_backend, run):
                calls.append(run)
                entered.set()
                if not release.wait(10):
                    raise TimeoutError("Test did not release model")
                tracks = np.array([[[8,10], [5,12]], [[43/3,10], [34/3,12]],
                                   [[62/3,10], [53/3,12]], [[27,10], [-10,-10]]], dtype=np.float32)
                return PointTrackerRunOutput(tracks_xy=tracks, visible_mask=np.ones((4,2), bool), model_name="tapir")

            with patch("nanotrack.trackers.backend.PointTrackerSubprocessBackend.run", model), patch.object(QMessageBox, "critical") as errors:
                button = window.polygon_tools_panel.btn_hybrid
                self.assertTrue(button.isEnabled())
                button.click()
                deadline = time.monotonic()+10
                while not entered.is_set() and time.monotonic()<deadline:
                    QTest.qWait(10)
                self.assertTrue(entered.is_set())
                window.action_apply_registration.setChecked(False)
                window.cmb_preview_source.setCurrentIndex(0)
                release.set()
                while not button.isEnabled() and time.monotonic()<deadline:
                    QTest.qWait(10)
                QTest.qWait(30)
                self.assertFalse(errors.called, errors.call_args)
            self.assertEqual(calls[0].source_view, "bm3d+expanded_registration")
            np.testing.assert_allclose(calls[0].query_points_tyx[[0,-1]], [[0,10,8], [0,10,27]])
            self.assertEqual(float(calls[0].frames[0,10,8]), 1010.125)
            annotation = window.current_edge_tracks()[0].get_annotation(2)
            np.testing.assert_allclose(annotation.polyline, [[5,10], [34/3,10], [53/3,10]], atol=1e-5)
            self.assertAlmostEqual(annotation.metrics.length_px, 38/3, places=5)
            self.assertEqual(annotation.shape_provenance.offset_xy, (0.,2.))
            self.assertEqual(annotation.shape_provenance.source_view, "bm3d+expanded_registration")

    def test_point_tracker_does_not_bridge_a_gap_without_measurements(self):
        with TemporaryDirectory() as directory:
            window = self.window(sample_session(Path(directory), gap_last=True))
            polyline = np.array([[5.,10.], [24.,10.]])
            window.set_edge_tracks([EdgeTrack(1, 1, window.current_draft_polygon_roi(), polyline,
                annotations={1: EdgeFrameAnnotation(1, polyline=polyline)})], selected_track_id=1)
            window.polygon_tools_panel.sp_tracker_points.setValue(4)

            def model(_backend, run):
                tracks = np.array([[[7,9], [4,11]], [[12,9], [9,11]],
                                   [[21,9], [18,11]], [[26,9], [23,11]]], dtype=np.float32)
                return PointTrackerRunOutput(tracks_xy=tracks, visible_mask=np.ones((4,2), bool), model_name="tapir")

            with patch("nanotrack.trackers.backend.PointTrackerSubprocessBackend.run", model), patch.object(QMessageBox, "critical") as errors:
                self.run_button(window.polygon_tools_panel.btn_hybrid)
                self.assertFalse(errors.called, errors.call_args)
            annotation = window.current_edge_tracks()[0].get_annotation(2)
            self.assertLessEqual(float(annotation.polyline[:,0].max()), 13.)
            self.assertAlmostEqual(annotation.metrics.length_px, 8.)

    def test_stitch_and_full_redetect_use_selected_geometry_and_explain_input(self):
        with TemporaryDirectory() as directory:
            window = self.window(sample_session(Path(directory)))
            line = np.array([[5.,10.], [24.,10.]])
            window.set_edge_tracks([EdgeTrack(1, 1, window.current_draft_polygon_roi(), line,
                annotations={1: EdgeFrameAnnotation(1, polyline=line), 2: EdgeFrameAnnotation(2, polyline=line)})], selected_track_id=1)
            window.cmb_preview_source.setCurrentIndex(1)
            window.action_show_expanded_aligned_registration.setChecked(True)
            panel = window.polygon_tools_panel
            panel.sp_run_end_frame.setValue(3)
            panel.chk_stitch_active.setChecked(True)
            calls = []

            def model(_backend, run):
                calls.append(run)
                positions = [(5,12)] if len(calls)==1 else [(8,10), (5,12)]
                probability = np.zeros((len(positions),26,35), np.float32)
                for index, (x,y) in enumerate(positions):
                    probability[index,y,x:x+20] = 1.
                return DexiNedRunOutput(probability)

            with patch("nanotrack.edges.backend.DexiNedSubprocessBackend.run", model), patch.object(QMessageBox, "critical") as errors:
                self.run_button(panel.btn_run_sequence)
                self.assertFalse(errors.called, errors.call_args)
                self.assertEqual(calls[0].source_view, "bm3d+expanded_registration")
                self.assertEqual(calls[0].frame_indices.tolist(), [2])
                self.assertIn("Expanded", panel.lbl_input.text())
                self.assertIn("Wynik preprocessingu", panel.lbl_input.text())
                self.run_button(panel.btn_redetect_edge)
                self.assertFalse(errors.called, errors.call_args)
            self.assertEqual(calls[1].frame_indices.tolist(), [1,2])
            annotation = window.current_edge_tracks()[0].get_annotation(2)
            np.testing.assert_allclose(annotation.polyline[:,1], 10., atol=1e-8)
            self.assertIn("Kształt", window.edge_track_list_panel.lbl_analysis.text())
            self.assertIn("geometria", window.edge_track_list_panel.lbl_analysis.text())

    def test_preview_without_support_shows_no_edge_and_finishes(self):
        with TemporaryDirectory() as directory:
            window = self.window(sample_session(Path(directory), empty_last=True, active=2))
            def model(_backend, run):
                return DexiNedRunOutput(np.ones((1,24,32), np.float32))
            with patch("nanotrack.edges.backend.DexiNedSubprocessBackend.run", model), patch.object(QMessageBox, "critical") as errors:
                self.run_button(window.polygon_tools_panel.btn_preview)
                self.assertFalse(errors.called, errors.call_args)
            dialog = window.findChildren(EdgePreviewDialog)[0]
            self.assertIn("Brak krawędzi w ważnym obszarze", dialog.edge_view.lbl_meta.text())
            self.assertEqual(window.current_edge_tracks(), [])
