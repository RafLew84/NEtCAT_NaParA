"""Public session saves either publish a complete archive or preserve the old file."""
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import threading
import time
from unittest.mock import patch
import zipfile

import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from nanotrack.io import load_mpp_sequence
from nanotrack.persistence import NanoTrackSessionSnapshot, load_session_snapshot, save_session_snapshot


def session(directory: Path, shape=(3, 6, 8)) -> NanoTrackSessionSnapshot:
    source = directory / "źródło próbki.MPP"
    count, height, width = shape
    header = (f"[General Info]\nNumber of columns: {width}\nNumber of rows: {height}\nNumber of Frames: {count}\n"
              f"[Control]\nX Amplitude: {width} nm\nY Amplitude: {height} nm\n[Header end]\n")
    frames = np.full(shape, 10.125, dtype="<f8")
    source.write_bytes(header.encode("ascii") + frames.tobytes())
    return NanoTrackSessionSnapshot(load_mpp_sequence(str(source)),
                                   repair_frames=frames + .25, preview_source="processed")


class SessionSaveTests(unittest.TestCase):
    def test_publication_failure_restores_old_name_and_next_save_succeeds(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            snapshot = session(root)
            target = root / "previous.nanotrack"
            save_session_snapshot(str(target), snapshot)
            previous = target.read_bytes()
            files = set(root.iterdir())
            snapshot.sequence.set_active_frame(2)
            with patch.object(os, "rename", side_effect=PermissionError("publication denied")):
                with self.assertRaisesRegex(PermissionError, "publication denied"):
                    save_session_snapshot(str(target), snapshot)
            self.assertEqual(target.read_bytes(), previous)
            self.assertEqual(set(root.iterdir()), files)
            receipt = save_session_snapshot(str(target), snapshot)
            self.assertIsNone(receipt.recovery_path)
            self.assertEqual(load_session_snapshot(str(target)).sequence.active_frame_index, 2)
            self.assertEqual(set(root.iterdir()), files)

    def test_write_failure_preserves_previous_bytes_and_only_cleans_own_files(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            snapshot = session(root)
            target = root / "sesja żółta.nanotrack"
            save_session_snapshot(str(target), snapshot)
            previous = target.read_bytes()
            unrelated = root / "cudza.tmp"
            unrelated.write_bytes(b"do not remove")
            files = set(root.iterdir())
            with patch.object(zipfile.ZipFile, "writestr", side_effect=OSError("disk full")):
                with self.assertRaisesRegex(OSError, "disk full"):
                    save_session_snapshot(str(target), snapshot)
            self.assertEqual(target.read_bytes(), previous)
            self.assertEqual(set(root.iterdir()), files)
            self.assertEqual(unrelated.read_bytes(), b"do not remove")
            reopened = load_session_snapshot(str(target))
            np.testing.assert_array_equal(reopened.repair_frames, np.full((3, 6, 8), 10.375))

    def test_manifest_corruption_is_rejected_before_replacing_previous_session(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            snapshot = session(root)
            target = root / "poprzednia.nanotrack"
            save_session_snapshot(str(target), snapshot)
            previous = target.read_bytes()
            write = zipfile.ZipFile.writestr

            def corrupt(archive, name, data, *args, **kwargs):
                if name == "manifest.json":
                    manifest = json.loads(data)
                    manifest["sequence"]["active_frame_index"] = 2
                    data = json.dumps(manifest)
                return write(archive, name, data, *args, **kwargs)

            with patch.object(zipfile.ZipFile, "writestr", corrupt):
                with self.assertRaisesRegex(ValueError, "[Mm]anifest"):
                    save_session_snapshot(str(target), snapshot)
            self.assertEqual(target.read_bytes(), previous)
            self.assertEqual(load_session_snapshot(str(target)).sequence.active_frame_index, 0)

    def test_cancel_during_writing_or_verifying_preserves_previous_file(self):
        from nanotrack.persistence import SessionSaveCancelled, SessionSaveControl

        for phase in ("write", "verify"):
            with self.subTest(phase=phase), TemporaryDirectory() as directory:
                root = Path(directory)
                snapshot = session(root, (3, 256, 256))
                target = root / "anulowanie.nanotrack"
                save_session_snapshot(str(target), snapshot)
                previous = target.read_bytes()
                files = set(root.iterdir())
                snapshot.sequence.set_active_frame(2)
                control = SessionSaveControl()
                observed = []

                def progress(stage, completed, total):
                    observed.append((stage, completed, total))
                    if stage == phase and 0 < completed < total:
                        self.assertTrue(control.cancel())

                with self.assertRaises(SessionSaveCancelled):
                    save_session_snapshot(str(target), snapshot, control=control, progress=progress)
                self.assertTrue(any(stage == phase and 0 < done < total for stage, done, total in observed))
                self.assertEqual(target.read_bytes(), previous)
                self.assertEqual(set(root.iterdir()), files)
                self.assertEqual(snapshot.sequence.active_frame_index, 2)
                self.assertEqual(load_session_snapshot(str(target)).sequence.active_frame_index, 0)

    def test_target_changed_after_confirmation_is_not_overwritten(self):
        for existing in (False, True):
            with self.subTest(existing=existing), TemporaryDirectory() as directory:
                root = Path(directory)
                snapshot = session(root)
                target = root / "wspólna sesja.nanotrack"
                if existing:
                    save_session_snapshot(str(target), snapshot)
                replacement = b"another writer's file"
                confirmed = []

                def confirm(path):
                    confirmed.append(path)
                    return True

                def progress(stage, completed, total):
                    if stage == "verify" and completed == 0:
                        target.write_bytes(replacement)

                with self.assertRaisesRegex(FileExistsError, "[Cc]el|zmieni"):
                    save_session_snapshot(str(target), snapshot, progress=progress, confirm_overwrite=confirm)
                self.assertEqual(target.read_bytes(), replacement)
                self.assertEqual(len(confirmed), int(existing))
                self.assertFalse(list(root.glob("*.tmp")))

    def test_collision_at_publication_preserves_foreign_file_and_reports_previous_session(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            snapshot = session(root)
            target = root / "publication.nanotrack"
            save_session_snapshot(str(target), snapshot)
            previous = target.read_bytes()
            snapshot.sequence.set_active_frame(1)
            other = root / "other.nanotrack"
            save_session_snapshot(str(other), snapshot)
            foreign = other.read_bytes()
            rename, replace = os.rename, os.replace

            def collide(operation, source, destination, *args, **kwargs):
                if Path(destination) == target:
                    target.write_bytes(foreign)
                return operation(source, destination, *args, **kwargs)

            with patch.object(os, "rename", lambda *a, **kw: collide(rename, *a, **kw)), \
                 patch.object(os, "replace", lambda *a, **kw: collide(replace, *a, **kw)):
                with self.assertRaises(FileExistsError) as failed:
                    save_session_snapshot(str(target), snapshot)
            self.assertEqual(target.read_bytes(), foreign)
            recovery = failed.exception.recovery_path
            self.assertIsNotNone(recovery)
            self.assertEqual(Path(recovery).read_bytes(), previous)
            self.assertEqual(load_session_snapshot(str(recovery)).sequence.active_frame_index, 0)


class SessionSaveGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        from nanotrack.app import configure_pyqtgraph
        cls.app = QApplication.instance() or QApplication([])
        configure_pyqtgraph()

    def test_successful_gui_save_opens_with_the_same_working_settings(self):
        from PyQt6.QtTest import QTest
        from PyQt6.QtWidgets import QFileDialog
        from nanotrack.ui.main_window import NanoTrackMainWindow
        from nanotrack.core import BBoxXYXY, ParticleTrack, EdgeTrack, PolygonROI, TrackFrameAnnotation, EdgeFrameAnnotation
        from nanotrack.core import ParticleMetrics, EdgeMetrics

        with TemporaryDirectory() as directory:
            root = Path(directory)
            initial = root / "initial.nanotrack"
            snapshot = session(root)
            snapshot.tracks = [ParticleTrack(1, 0, BBoxXYXY(1, 1, 4, 4))]
            snapshot.edge_tracks = [EdgeTrack(1, 0, PolygonROI(np.array([[1., 1.], [4., 1.], [4., 4.]])),
                                              np.array([[1., 1.], [4., 1.]]))]
            snapshot.tracks[0].add_annotation(TrackFrameAnnotation(0, bbox=BBoxXYXY(1, 1, 4, 4),
                metrics=ParticleMetrics(area_px=9., perimeter_px=12., intensity_sum=91.125,
                                        intensity_mean=10.125, intensity_max=10.125)))
            snapshot.edge_tracks[0].add_annotation(EdgeFrameAnnotation(0, polyline=np.array([[1., 1.], [4., 1.]]),
                metrics=EdgeMetrics(length_px=3., roughness_rms_px=0., mean_curvature=0., max_curvature=0.,
                                    waviness_amplitude_px=0.)))
            save_session_snapshot(str(initial), snapshot)
            window, reopened = NanoTrackMainWindow(), NanoTrackMainWindow()
            try:
                window.load_session_from_path(str(initial))
                window.spin_frame.setValue(2)
                window.track_list_panel.sp_run_frame_limit.setValue(2)
                window.track_list_panel.sp_mask_probability_threshold.setValue(.27)
                window.polygon_tools_panel.cmb_edge_backend.setCurrentIndex(1)
                window.polygon_tools_panel.sp_dexined_threshold.setValue(.6)
                window.polygon_tools_panel.sp_run_end_frame.setValue(2)
                window.bbox_tools_panel.sp_width.setValue(14)
                window.preprocessing_panel.sp_bm3d_sigma.setValue(1.7)
                window.cmb_registration_backend.setCurrentIndex(3)
                window.viewer.viewer.slider_gamma.setValue(135)
                window.viewer.viewer.hist.setLevels(10., 11.)
                window.action_open_results.trigger()
                results = window.current_results_dialog()
                self.assertIsNotNone(results)
                results.chk_exclude_boundary_pixels.setChecked(True)
                results.spn_boundary_pixel_weight.setValue(.2)
                results.cmb_units.setCurrentIndex(1)
                results.close()
                window.action_open_edge_results.trigger()
                edges = window.current_edge_results_dialog()
                self.assertIsNotNone(edges)
                edges.cmb_trend.setCurrentIndex(2)
                edges.cmb_units.setCurrentIndex(1)
                edges.close()
                target = root / "żółta kopia sesji.nanotrack"
                with patch.object(QFileDialog, "getSaveFileName", return_value=(str(target), "")):
                    window.action_save_session.trigger()
                deadline = time.monotonic() + 5
                while not window.action_save_session.isEnabled() and time.monotonic() < deadline:
                    QTest.qWait(10)
                self.assertTrue(window.action_save_session.isEnabled())
                self.assertIn("Zapisano", window.statusBar().currentMessage())
                reopened.load_session_from_path(str(target))
                self.assertEqual(reopened.spin_frame.value(), 2)
                self.assertEqual(reopened.current_session_snapshot().preview_source, "processed")
                self.assertEqual(reopened.track_list_panel.sp_run_frame_limit.value(), 2)
                self.assertEqual(reopened.track_list_panel.sp_mask_probability_threshold.value(), .27)
                self.assertEqual(reopened.polygon_tools_panel.cmb_edge_backend.currentData(), "teed")
                self.assertEqual(reopened.polygon_tools_panel.sp_dexined_threshold.value(), .6)
                self.assertEqual(reopened.polygon_tools_panel.sp_run_end_frame.value(), 2)
                self.assertEqual(reopened.bbox_tools_panel.sp_width.value(), 14)
                self.assertEqual(reopened.preprocessing_panel.sp_bm3d_sigma.value(), 1.7)
                self.assertEqual(reopened.cmb_registration_backend.currentData(), "optical_flow_median")
                self.assertEqual(reopened.viewer.viewer.slider_gamma.value(), 135)
                self.assertEqual(tuple(reopened.viewer.viewer.hist.getLevels()), (10., 11.))
                reopened.action_open_results.trigger()
                results = reopened.current_results_dialog()
                self.assertTrue(results.chk_exclude_boundary_pixels.isChecked())
                self.assertEqual(results.spn_boundary_pixel_weight.value(), .2)
                self.assertEqual(results.cmb_units.currentData(), "nm")
                reopened.action_open_edge_results.trigger()
                self.assertEqual(reopened.current_edge_results_dialog().cmb_trend.currentData(), "roughness")
                self.assertEqual(reopened.current_edge_results_dialog().cmb_units.currentData(), "nm")
                np.testing.assert_array_equal(reopened.current_repair_frames(), np.full((3, 6, 8), 10.375))
            finally:
                window.close()
                reopened.close()

    def test_gui_refusal_io_errors_and_changed_target_preserve_work(self):
        from PyQt6.QtTest import QTest
        from PyQt6.QtWidgets import QFileDialog, QMessageBox
        from nanotrack.ui.main_window import NanoTrackMainWindow

        for case in ("declined", "disk_full", "permission", "changed_target"):
            with self.subTest(case=case), TemporaryDirectory() as directory:
                root = Path(directory)
                snapshot = session(root)
                target = root / "existing.nanotrack"
                save_session_snapshot(str(target), snapshot)
                previous = target.read_bytes()
                snapshot.sequence.set_active_frame(1)
                foreign = root / "foreign.nanotrack"
                save_session_snapshot(str(foreign), snapshot)
                replacement = foreign.read_bytes()
                window = NanoTrackMainWindow()
                window.load_session_from_path(str(target))
                window.spin_frame.setValue(3)
                before = window.current_session_snapshot().tool_settings
                flush = os.fsync

                def confirm(*args, **kwargs):
                    if case == "changed_target":
                        target.write_bytes(replacement)
                    return QMessageBox.StandardButton.No if case == "declined" else QMessageBox.StandardButton.Yes

                def storage_flush(descriptor):
                    if case == "disk_full":
                        raise OSError(28, "No space left on device")
                    if case == "permission":
                        raise PermissionError(13, "Permission denied")
                    return flush(descriptor)

                try:
                    with patch.object(QFileDialog, "getSaveFileName", return_value=(str(target), "")), \
                         patch.object(QMessageBox, "question", confirm), \
                         patch.object(QMessageBox, "critical") as errors, patch.object(os, "fsync", storage_flush):
                        window.action_save_session.trigger()
                        deadline = time.monotonic() + 5
                        while not window.action_save_session.isEnabled() and time.monotonic() < deadline:
                            QTest.qWait(10)
                        self.assertTrue(window.action_save_session.isEnabled())
                        self.assertEqual(errors.called, case != "declined")
                    self.assertNotIn("Zapisano", window.statusBar().currentMessage())
                    self.assertEqual(window.spin_frame.value(), 3)
                    self.assertEqual(window.current_session_snapshot().tool_settings, before)
                    self.assertEqual(target.read_bytes(), replacement if case == "changed_target" else previous)
                    self.assertEqual(load_session_snapshot(str(target)).sequence.active_frame_index,
                                     1 if case == "changed_target" else 0)
                    self.assertFalse(list(root.glob("*.tmp")))
                finally:
                    window.close()

    def test_gui_cancel_during_verification_keeps_work_and_previous_file(self):
        from PyQt6.QtCore import QTimer, Qt
        from PyQt6.QtTest import QTest
        from PyQt6.QtWidgets import QFileDialog, QMessageBox, QProgressDialog, QPushButton
        from nanotrack.ui.main_window import NanoTrackMainWindow

        with TemporaryDirectory() as directory:
            root = Path(directory)
            snapshot = session(root, (3, 256, 256))
            target = root / "bezpieczna sesja ą.nanotrack"
            save_session_snapshot(str(target), snapshot)
            previous = target.read_bytes()
            window = NanoTrackMainWindow()
            window.show()
            window.load_session_from_path(str(target))
            window.spin_frame.setValue(3)
            blocked, release = threading.Event(), threading.Event()
            archive_open = zipfile.ZipFile.open
            ticks = []
            heartbeat = QTimer()
            heartbeat.timeout.connect(lambda: ticks.append(1))
            heartbeat.start(10)

            def delayed_read(archive, name, mode="r", *args, **kwargs):
                if name == "preprocessing/repair_frames.npz" and mode == "r":
                    blocked.set()
                    release.wait(2)
                return archive_open(archive, name, mode, *args, **kwargs)

            try:
                with patch.object(QFileDialog, "getSaveFileName", return_value=(str(target), "")), \
                     patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes), \
                     patch.object(zipfile.ZipFile, "open", delayed_read):
                    window.action_save_session.trigger()
                    self.assertFalse(window.action_save_session.isEnabled())
                    deadline = time.monotonic() + 5
                    while not blocked.is_set() and time.monotonic() < deadline:
                        QTest.qWait(10)
                    self.assertTrue(blocked.is_set())
                    QTest.qWait(60)
                    self.assertGreater(len(ticks), 2)
                    self.assertFalse(window.spin_frame.isEnabled())
                    self.assertFalse(window.action_open_session.isEnabled())
                    with self.assertRaises(RuntimeError):
                        window.start_session_save(str(root / "second.nanotrack"))
                    with self.assertRaises(RuntimeError):
                        window.load_session_from_path(str(target))
                    dialog = next(d for d in window.findChildren(QProgressDialog) if d.isVisible())
                    button = next(b for b in dialog.findChildren(QPushButton) if b.text() == "Anuluj")
                    QTest.mouseClick(button, Qt.MouseButton.LeftButton)
                    release.set()
                    while not window.action_save_session.isEnabled() and time.monotonic() < deadline:
                        QTest.qWait(10)
                    self.assertTrue(window.action_save_session.isEnabled())
                    self.assertIn("anulowan", window.statusBar().currentMessage().lower())
                self.assertEqual(window.spin_frame.value(), 3)
                self.assertEqual(window.current_session_snapshot().preview_source, "processed")
                self.assertEqual(target.read_bytes(), previous)
                self.assertEqual(load_session_snapshot(str(target)).sequence.active_frame_index, 0)
            finally:
                release.set()
                heartbeat.stop()
                QTest.qWait(100)
                window.close()
