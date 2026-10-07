"""User-visible image source selection and session persistence."""

import os
import json
import io
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from nanotrack.core import (
    BBoxXYXY, ParticleTrack, ParticleMetrics, TrackFrameAnnotation,
    RegistrationFrameResult, RegistrationResultSet, RegistrationSettings,
    STMSequence, STMSequenceMetadata,
)
from nanotrack.persistence import NanoTrackSessionSnapshot, load_session_snapshot, save_session_snapshot
from nanotrack.ui.main_window import NanoTrackMainWindow


class PreviewSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = NanoTrackMainWindow()
        y = np.linspace(0.0, 1.0, 16)[:, None]
        x = np.linspace(0.0, 0.2, 32)[None, :]
        frames = np.stack([y + x, y + x + 2.0])
        frames[:, 8, 8:14] += 3.0
        self.sequence = STMSequence(
            source_path="source.MPP",
            raw_frames=frames,
            metadata=STMSequenceMetadata(pixels_x=32, pixels_y=16),
        )
        self.window.set_sequence(self.sequence)

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()

    def test_user_selects_original_or_repaired_image_without_changing_raw(self):
        selector = self.window.cmb_preview_source
        self.assertEqual([selector.itemData(i) for i in range(selector.count())], ["original", "processed"])
        self.assertEqual(selector.currentData(), "original")
        self.assertFalse(selector.model().flags(selector.model().index(1, 0)) & Qt.ItemFlag.ItemIsEnabled)
        self.assertIn("Brak wyniku", self.window.lbl_preview_source.text())
        raw_before = self.sequence.raw_frames.copy()

        self.window.preprocessing_panel.btn_repair_apply_all.click()
        self.assertTrue(selector.model().flags(selector.model().index(1, 0)) & Qt.ItemFlag.ItemIsEnabled)
        selector.setCurrentIndex(selector.findData("processed"))
        self.assertAlmostEqual(float(self.window.viewer.viewer.image_item.image[8, 10]), 0.59784946, places=5)
        self.assertIn("Naprawa", self.window.lbl_preview_source.text())
        self.window.slider_frame.setValue(1)
        self.assertAlmostEqual(float(self.window.viewer.viewer.image_item.image[8, 10]), 2.59784946, places=5)

        selector.setCurrentIndex(selector.findData("original"))
        np.testing.assert_array_equal(self.window.viewer.viewer.image_item.image, raw_before[1])
        np.testing.assert_array_equal(self.sequence.raw_frames, raw_before)
        self.assertEqual(self.sequence.active_frame_index, 1)

    def test_save_open_preserves_source_frame_registration_and_analysis(self):
        with TemporaryDirectory() as directory:
            source = Path(directory) / "source.MPP"
            header = ("[General Info]\nNumber of columns: 32\nNumber of rows: 16\n"
                      "Number of Frames: 2\n[Control]\nX Amplitude: 32 nm\n"
                      "Y Amplitude: 16 nm\n[Header end]\n")
            source.write_bytes(header.encode("ascii") + self.sequence.raw_frames[:, ::-1, ::-1].astype("<f8").tobytes())
            self.sequence.source_path = str(source)
            track = ParticleTrack(7, 0, BBoxXYXY(8, 7, 14, 10), label="Znacznik")
            track.add_annotation(TrackFrameAnnotation(
                frame_index=1, bbox=BBoxXYXY(8, 7, 14, 10),
                metrics=ParticleMetrics(area_px=18, intensity_mean=2.5),
            ))
            registration = RegistrationResultSet(RegistrationSettings(), {
                0: RegistrationFrameResult(0, (0, 0), "reference"),
                1: RegistrationFrameResult(1, (1.25, -0.5), "manual"),
            })
            session = Path(directory) / "working.nanotrack"
            save_session_snapshot(str(session), NanoTrackSessionSnapshot(
                sequence=self.sequence, tracks=[track], registration_results=registration,
            ))
            # Opening a shorter session must discard the previous movie's out-of-range annotations.
            previous = STMSequence(
                source_path="previous.MPP", raw_frames=np.zeros((3, 16, 32)), metadata=self.sequence.metadata,
            )
            previous_track = ParticleTrack(9, 2, BBoxXYXY(1, 1, 4, 4))
            previous_track.add_annotation(TrackFrameAnnotation(
                frame_index=2, bbox=previous_track.seed_bbox, metrics=ParticleMetrics(area_px=9),
            ))
            self.window.set_sequence(previous)
            self.window.set_tracks([previous_track])
            self.window.load_session_from_path(str(session))
            self.window.preprocessing_panel.btn_repair_apply_all.click()
            self.window.cmb_preview_source.setCurrentIndex(1)
            self.window.slider_frame.setValue(1)
            description = self.window.lbl_preview_source.text()
            self.window.save_session_to_path(str(session))
            with zipfile.ZipFile(session) as archive:
                manifest = json.loads(archive.read("manifest.json"))
            self.assertEqual(manifest["schema"], "nanotrack.session.v2")
            self.window.set_sequence(self.sequence)
            self.window.load_session_from_path(str(session))
            self.assertEqual(self.window.cmb_preview_source.currentData(), "processed")
            self.assertEqual(self.window.lbl_preview_source.text(), description)
            self.assertAlmostEqual(float(self.window.viewer.viewer.image_item.image[8, 10]), 2.59784946, places=5)
            restored = self.window.current_session_snapshot()
            self.assertEqual(restored.sequence.active_frame_index, 1)
            self.assertEqual(restored.registration_results.get_result(1).shift_xy, (1.25, -0.5))
            self.assertEqual(restored.tracks[0].label, "Znacznik")
            self.assertEqual(restored.tracks[0].get_annotation(1).metrics.intensity_mean, 2.5)
            self.assertTrue(restored.preprocessing_provenance.history_known)
            self.assertEqual(restored.preprocessing_provenance.steps[0].method, "horizontal_repair")

            # Source is independent of the existing registration display mode.
            self.window.slider_frame.setValue(0)
            self.window.action_show_aligned_registration.setChecked(True)
            self.window.cmb_preview_source.setCurrentIndex(0)
            np.testing.assert_allclose(self.window.viewer.viewer.image_item.image, self.sequence.raw_frames[0], atol=1e-6)
            self.assertTrue(self.window.action_show_aligned_registration.isChecked())
            self.window.save_session_to_path(str(session))
            self.window.load_session_from_path(str(session))
            self.assertEqual(self.window.cmb_preview_source.currentData(), "original")
            np.testing.assert_allclose(self.window.viewer.viewer.image_item.image, self.sequence.raw_frames[0], atol=1e-6)
            self.window.cmb_preview_source.setCurrentIndex(1)
            self.assertAlmostEqual(float(self.window.viewer.viewer.image_item.image[8, 10]), 0.59784946, places=5)
            self.assertEqual(self.window.current_registration_results().get_result(1).shift_xy, (1.25, -0.5))

    def test_processing_description_follows_actual_inputs_and_replaces_previous_result(self):
        # Only the optional third-party numerical backend is substituted; GUI and pipeline are real.
        backend_inputs = []
        def denoise(image, *, sigma_psd):
            backend_inputs.append(image.copy())
            return image * 0.5

        backend = SimpleNamespace(bm3d=denoise)
        module_patch = patch.dict("sys.modules", {"bm3d": backend})
        module_patch.start()
        self.addCleanup(module_patch.stop)
        self.window.preprocessing_panel.btn_repair_apply_all.click()
        self.window.cmb_preview_source.setCurrentIndex(1)
        first_revision = self.window.current_session_snapshot().preprocessing_provenance.revision
        self.window.preprocessing_panel.btn_apply_all.click()
        self.assertEqual(len(backend_inputs), 2)
        self.assertAlmostEqual(float(backend_inputs[0][8, 10]), 0.59784946, places=5)
        self.assertAlmostEqual(float(backend_inputs[1][8, 10]), 0.49820788, places=5)
        snapshot = self.window.current_session_snapshot()
        self.assertEqual(
            [step.method for step in snapshot.preprocessing_provenance.steps],
            ["horizontal_repair", "bm3d"],
        )
        self.assertNotEqual(snapshot.preprocessing_provenance.revision, first_revision)
        self.assertIn("Naprawa artefaktów", self.window.lbl_preview_source.text())
        self.assertIn("BM3D", self.window.lbl_preview_source.text())
        np.testing.assert_array_equal(self.window.viewer.viewer.image_item.image, snapshot.denoised_frames[0])

        # Re-running BM3D uses the repaired input again, rather than the previous BM3D result.
        self.window.preprocessing_panel.btn_apply_all.click()
        self.assertEqual(len(self.window.current_session_snapshot().preprocessing_provenance.steps), 2)
        completed = self.window.current_denoised_frames().copy()
        with patch.object(backend, "bm3d", side_effect=RuntimeError("backend failed")), patch("PyQt6.QtWidgets.QMessageBox.critical"):
            self.window.preprocessing_panel.btn_apply_all.click()
        np.testing.assert_array_equal(self.window.current_denoised_frames(), completed)
        self.window.preprocessing_panel.btn_repair_apply_all.click()
        self.assertNotIn("BM3D", self.window.lbl_preview_source.text())
        self.assertIsNone(self.window.current_denoised_frames())
        self.assertAlmostEqual(float(self.window.viewer.viewer.image_item.image[8, 10]), 0.59784946, places=5)

    def test_legacy_cache_has_unknown_history_and_v2_keeps_its_precision(self):
        # Independent v1 input: the presence of both caches does not prove their execution order.
        manifest = {
            "schema": "nanotrack.session.v1",
            "sequence": {"source_path": "source.MPP", "active_frame_index": 1},
            "show_denoised_in_viewer": True,
        }
        frames = np.full((2, 16, 32), 1.000000000123, dtype=np.float64)
        with TemporaryDirectory() as directory:
            path = Path(directory) / "legacy.nanotrack"
            buffer = io.BytesIO()
            np.savez_compressed(buffer, frames=frames)
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("manifest.json", json.dumps(manifest))
                archive.writestr("preprocessing/repair_frames.npz", buffer.getvalue())
                archive.writestr("preprocessing/denoised_frames.npz", buffer.getvalue())
            snapshot = load_session_snapshot(str(path), sequence_loader=lambda *args, **kwargs: self.sequence)
            self.assertEqual(snapshot.preview_source, "processed")
            self.assertFalse(snapshot.preprocessing_provenance.history_known)
            self.assertEqual(snapshot.preprocessing_provenance.steps, ())
            save_session_snapshot(str(path), snapshot)
            restored = load_session_snapshot(str(path), sequence_loader=lambda *args, **kwargs: self.sequence)
            self.assertEqual(restored.preprocessing_provenance, snapshot.preprocessing_provenance)
            self.assertEqual(restored.denoised_frames.dtype, np.dtype("float64"))
            self.assertEqual(float(restored.denoised_frames[0, 0, 0]), 1.000000000123)

    def test_incomplete_processed_source_is_rejected_before_writing_session(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "incomplete.nanotrack"
            with self.assertRaisesRegex(ValueError, "klatek|kształt"):
                save_session_snapshot(str(path), NanoTrackSessionSnapshot(
                    sequence=self.sequence, repair_frames=np.zeros((1, 16, 32)), preview_source="processed",
                ))
            self.assertFalse(path.exists())

    def test_missing_latest_result_is_not_replaced_with_intermediate_repair(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "damaged.nanotrack"
            save_session_snapshot(str(path), NanoTrackSessionSnapshot(
                sequence=self.sequence, repair_frames=np.zeros((2, 16, 32)),
                denoised_frames=np.ones((2, 16, 32)), preview_source="processed",
            ))
            with zipfile.ZipFile(path) as archive:
                entries = {name: archive.read(name) for name in archive.namelist()
                           if name != "preprocessing/denoised_frames.npz"}
            with zipfile.ZipFile(path, "w") as archive:
                for name, data in entries.items():
                    archive.writestr(name, data)
            with self.assertRaisesRegex(ValueError, "Wynik preprocessingu.*niedostępny"):
                load_session_snapshot(str(path), sequence_loader=lambda *args, **kwargs: self.sequence)
