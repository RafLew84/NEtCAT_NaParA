import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from moltrack.core import (
    MolecularDetection,
    MolecularDetectionSet,
    MolTrackImageSeries,
    MolTrackRegistrationFrameResult,
    MolTrackRegistrationResultSet,
    MolTrackRegistrationSettings,
    MolTrackSession,
)
from moltrack.persistence import (
    load_moltrack_session,
    restore_moltrack_image_series_from_session,
    save_moltrack_session,
)
from nanotrack.core import STMSequenceMetadata


class MolTrackSessionStoreTests(unittest.TestCase):
    def test_save_and_load_session_round_trip_writes_readable_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            source_path = tmp_path / "movie.mpp"
            source_path.write_bytes(b"fake mpp bytes")
            session_path = tmp_path / "state.moltrack.json"

            frames = np.arange(32, dtype=np.float32).reshape(4, 2, 4)
            series = MolTrackImageSeries(
                source_path=str(source_path),
                raw_frames=frames.copy(),
                metadata=STMSequenceMetadata(pixels_x=4, pixels_y=2),
                active_frame_index=2,
            )
            series.remove_frame(1)
            settings = MolTrackRegistrationSettings(
                backend="optical_flow_median",
                backend_params={"method": "ilk", "low_confidence_flow_mad_px": 2.0},
            )
            series.registration_results = MolTrackRegistrationResultSet(
                settings=settings,
                results_by_frame={
                    frame_index: MolTrackRegistrationFrameResult(
                        frame_index=frame_index,
                        shift_xy=(float(frame_index), -float(frame_index)),
                        method="optical_flow_median",
                        quality_score=0.75,
                        status="ok",
                    )
                    for frame_index in range(series.frame_count)
                },
            )
            series.expanded_aligned_stack = object()
            detections = MolecularDetectionSet(frame_count=series.frame_count)
            detections.set_detections(
                0,
                [
                    MolecularDetection(
                        frame_index=0,
                        bbox_xyxy=(0.25, 0, 2.5, 1),
                        original_bbox_xyxy=(0, 0, 2, 1),
                        confidence=0.91,
                        selected=True,
                        model_name="model-a.pt",
                        checkpoint_path="nanotrack/yolo_models/model-a.pt",
                        source_view="raw",
                    )
                ],
                source_view="raw",
                frame_shape=(2, 4),
            )
            detections.set_detections(
                1,
                [
                    MolecularDetection(
                        frame_index=1,
                        bbox_xyxy=(1, 0, 4, 2),
                        confidence=0.72,
                        selected=False,
                        model_name="model-b.pt",
                        checkpoint_path="missing/model-b.pt",
                        source_view="expanded_aligned",
                    )
                ],
                source_view="expanded_aligned",
                frame_shape=(2, 4),
            )
            series.molecular_detections = detections

            save_moltrack_session(
                session_path,
                series,
                {"registration_view_mode": "Show expanded aligned"},
            )

            payload = json.loads(session_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["schema_version"], 1)
            self.assertEqual(payload["source"]["path"], str(source_path.resolve()))
            self.assertEqual(payload["source"]["path_relative_to_session"], "movie.mpp")
            self.assertEqual(payload["working_series"]["source_frame_indices"], [0, 2, 3])
            self.assertEqual(payload["working_series"]["active_frame_index"], 1)
            self.assertFalse(payload["working_series"]["reverse_frame_order"])
            self.assertEqual(payload["ui"]["registration_view_mode"], "Show expanded aligned")
            self.assertEqual(payload["registration"]["settings"]["backend"], "optical_flow_median")
            self.assertEqual(payload["registration"]["settings"]["backend_params"]["method"], "ilk")
            self.assertEqual(payload["registration"]["results_by_frame"][1]["shift_xy"], [1.0, -1.0])
            self.assertEqual(payload["molecular_detections"]["frame_count"], 3)
            self.assertEqual(payload["molecular_detections"]["detections"][0]["frame_index"], 0)
            self.assertEqual(payload["molecular_detections"]["detections"][0]["bbox_xyxy"], [0.25, 0.0, 2.5, 1.0])
            self.assertEqual(
                payload["molecular_detections"]["detections"][0]["original_bbox_xyxy"],
                [0.0, 0.0, 2.0, 1.0],
            )
            self.assertEqual(payload["molecular_detections"]["detections"][0]["confidence"], 0.91)
            self.assertTrue(payload["molecular_detections"]["detections"][0]["selected"])
            self.assertEqual(payload["molecular_detections"]["detections"][0]["model_name"], "model-a.pt")
            self.assertEqual(
                payload["molecular_detections"]["detections"][0]["checkpoint_path"],
                "nanotrack/yolo_models/model-a.pt",
            )
            self.assertEqual(payload["molecular_detections"]["detections"][1]["source_view"], "expanded_aligned")
            self.assertFalse(payload["molecular_detections"]["detections"][1]["selected"])
            self.assertNotIn("expanded_aligned_stack", payload)

            loaded = load_moltrack_session(session_path)

            self.assertEqual(loaded.source_path, str(source_path.resolve()))
            self.assertEqual(loaded.source_frame_indices, (0, 2, 3))
            self.assertEqual(loaded.active_frame_index, 1)
            self.assertFalse(loaded.reverse_frame_order)
            self.assertEqual(loaded.registration_view_mode, "Show expanded aligned")
            self.assertEqual(loaded.registration_settings.backend, "optical_flow_median")
            self.assertEqual(loaded.registration_settings.backend_params["method"], "ilk")
            self.assertEqual(loaded.registration_results.result_count, 3)
            self.assertEqual(loaded.registration_results.get_result(2).shift_xy, (2.0, -2.0))
            self.assertIsNotNone(loaded.molecular_detections)
            loaded_raw = loaded.molecular_detections.get_detections(0, source_view="raw")
            loaded_expanded = loaded.molecular_detections.get_detections(1, source_view="expanded_aligned")
            self.assertEqual(len(loaded_raw), 1)
            self.assertEqual(loaded_raw[0].bbox_xyxy, (0.25, 0.0, 2.5, 1.0))
            self.assertEqual(loaded_raw[0].original_bbox_xyxy, (0.0, 0.0, 2.0, 1.0))
            self.assertEqual(loaded_raw[0].confidence, 0.91)
            self.assertTrue(loaded_raw[0].selected)
            self.assertEqual(loaded_raw[0].model_name, "model-a.pt")
            self.assertEqual(loaded_raw[0].checkpoint_path, "nanotrack/yolo_models/model-a.pt")
            self.assertEqual(len(loaded_expanded), 1)
            self.assertFalse(loaded_expanded[0].selected)
            self.assertEqual(loaded_expanded[0].source_view, "expanded_aligned")

    def test_load_session_rejects_unknown_schema_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            session_path = Path(tmpdir) / "state.moltrack.json"
            session_path.write_text(
                json.dumps({"schema_version": 999}),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "Unsupported MolTrack session schema_version"):
                load_moltrack_session(session_path)

    def test_load_session_rejects_missing_or_changed_source_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            source_path = tmp_path / "movie.mpp"
            source_path.write_bytes(b"fake mpp bytes")
            session_path = tmp_path / "state.moltrack.json"
            series = MolTrackImageSeries(
                source_path=str(source_path),
                raw_frames=np.arange(16, dtype=np.float32).reshape(2, 2, 4),
                metadata=STMSequenceMetadata(pixels_x=4, pixels_y=2),
            )

            save_moltrack_session(session_path, series, None)
            source_path.unlink()

            with self.assertRaises(FileNotFoundError):
                load_moltrack_session(session_path)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            source_path = tmp_path / "movie.mpp"
            source_path.write_bytes(b"fake mpp bytes")
            session_path = tmp_path / "state.moltrack.json"
            series = MolTrackImageSeries(
                source_path=str(source_path),
                raw_frames=np.arange(16, dtype=np.float32).reshape(2, 2, 4),
                metadata=STMSequenceMetadata(pixels_x=4, pixels_y=2),
            )

            save_moltrack_session(session_path, series, None)
            source_path.write_bytes(b"changed mpp bytes with different size")

            with self.assertRaisesRegex(ValueError, "source file metadata does not match"):
                load_moltrack_session(session_path)

    def test_load_session_rejects_molecular_detection_frame_count_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            source_path = tmp_path / "movie.mpp"
            source_path.write_bytes(b"fake mpp bytes")
            session_path = tmp_path / "state.moltrack.json"
            series = MolTrackImageSeries(
                source_path=str(source_path),
                raw_frames=np.arange(16, dtype=np.float32).reshape(2, 2, 4),
                metadata=STMSequenceMetadata(pixels_x=4, pixels_y=2),
            )
            detections = MolecularDetectionSet(frame_count=2)
            detections.set_detections(
                0,
                [MolecularDetection(frame_index=0, bbox_xyxy=(0, 0, 2, 1), confidence=0.8)],
                source_view="raw",
                frame_shape=(2, 4),
            )
            series.molecular_detections = detections
            save_moltrack_session(session_path, series, None)
            payload = json.loads(session_path.read_text(encoding="utf-8"))
            payload["molecular_detections"]["frame_count"] = 3
            session_path.write_text(json.dumps(payload), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "molecular_detections frame_count"):
                load_moltrack_session(session_path)

    def test_load_session_uses_current_bbox_as_original_for_legacy_detections(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            source_path = tmp_path / "movie.mpp"
            source_path.write_bytes(b"fake mpp bytes")
            session_path = tmp_path / "state.moltrack.json"
            series = MolTrackImageSeries(
                source_path=str(source_path),
                raw_frames=np.arange(16, dtype=np.float32).reshape(2, 2, 4),
                metadata=STMSequenceMetadata(pixels_x=4, pixels_y=2),
            )
            detections = MolecularDetectionSet(frame_count=2)
            detections.set_detections(
                0,
                [MolecularDetection(frame_index=0, bbox_xyxy=(0.5, 0, 2.5, 1), confidence=0.8)],
                source_view="raw",
                frame_shape=(2, 4),
            )
            series.molecular_detections = detections
            save_moltrack_session(session_path, series, None)
            payload = json.loads(session_path.read_text(encoding="utf-8"))
            del payload["molecular_detections"]["detections"][0]["original_bbox_xyxy"]
            session_path.write_text(json.dumps(payload), encoding="utf-8")

            loaded = load_moltrack_session(session_path)

            self.assertIsNotNone(loaded.molecular_detections)
            loaded_detection = loaded.molecular_detections.get_detections(0, source_view="raw")[0]
            self.assertEqual(loaded_detection.bbox_xyxy, (0.5, 0.0, 2.5, 1.0))
            self.assertEqual(loaded_detection.original_bbox_xyxy, loaded_detection.bbox_xyxy)

    def test_restore_working_series_from_session_reloads_source_and_applies_saved_frame_indices(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            source_path = tmp_path / "movie.mpp"
            source_path.write_bytes(b"fake mpp bytes")
            session_path = tmp_path / "state.moltrack.json"
            full_frames = np.arange(40, dtype=np.float32).reshape(5, 2, 4)
            series = MolTrackImageSeries(
                source_path=str(source_path),
                raw_frames=full_frames.copy(),
                metadata=STMSequenceMetadata(pixels_x=4, pixels_y=2),
                active_frame_index=2,
            )
            series.remove_frame(1)
            series.remove_frame(2)
            settings = MolTrackRegistrationSettings()
            series.registration_results = MolTrackRegistrationResultSet(
                settings=settings,
                results_by_frame={
                    frame_index: MolTrackRegistrationFrameResult(
                        frame_index=frame_index,
                        shift_xy=(float(frame_index), 0.0),
                        method="phase_correlation",
                    )
                    for frame_index in range(series.frame_count)
                },
            )
            detections = MolecularDetectionSet(frame_count=series.frame_count)
            detections.set_detections(
                2,
                [
                    MolecularDetection(
                        frame_index=2,
                        bbox_xyxy=(0.5, 0, 2.5, 1),
                        original_bbox_xyxy=(0, 0, 2, 1),
                        confidence=0.83,
                        model_name="model-a.pt",
                        checkpoint_path="missing/model-a.pt",
                        source_view="expanded_aligned",
                    )
                ],
                source_view="expanded_aligned",
                frame_shape=(2, 4),
            )
            series.molecular_detections = detections
            series.expanded_aligned_stack = object()
            save_moltrack_session(session_path, series, {"registration_view_mode": "Show expanded aligned"})
            calls = []

            def fake_loader(source_path_arg, *, reverse_frame_order=False):
                calls.append((str(source_path_arg), reverse_frame_order))
                return MolTrackImageSeries(
                    source_path=str(source_path_arg),
                    raw_frames=full_frames.copy(),
                    metadata=STMSequenceMetadata(pixels_x=4, pixels_y=2),
                    reverse_frame_order=reverse_frame_order,
                )

            restored = restore_moltrack_image_series_from_session(
                session_path,
                series_loader=fake_loader,
            )

            self.assertEqual(calls, [(str(source_path.resolve()), False)])
            self.assertEqual(restored.source_frame_indices, (0, 2, 4))
            self.assertEqual(restored.active_frame_index, 1)
            np.testing.assert_array_equal(restored.raw_frames, full_frames[[0, 2, 4]])
            self.assertIsNotNone(restored.registration_results)
            self.assertEqual(restored.registration_results.result_count, 3)
            self.assertIsNone(restored.expanded_aligned_stack)
            self.assertIsNotNone(restored.molecular_detections)
            restored_expanded = restored.molecular_detections.get_detections(2, source_view="expanded_aligned")
            self.assertEqual(len(restored_expanded), 1)
            self.assertEqual(restored_expanded[0].bbox_xyxy, (0.5, 0.0, 2.5, 1.0))
            self.assertEqual(restored_expanded[0].original_bbox_xyxy, (0.0, 0.0, 2.0, 1.0))
            self.assertEqual(restored_expanded[0].model_name, "model-a.pt")
            self.assertEqual(restored_expanded[0].checkpoint_path, "missing/model-a.pt")

            restored.remove_frame(1)

            self.assertEqual(restored.source_frame_indices, (0, 4))
            self.assertIsNone(restored.registration_results)
            self.assertIsNone(restored.molecular_detections)

    def test_restore_working_series_maps_source_indices_for_reversed_sources(self) -> None:
        full_frames = np.arange(40, dtype=np.float32).reshape(5, 2, 4)

        def fake_loader(source_path_arg, *, reverse_frame_order=False):
            self.assertTrue(reverse_frame_order)
            loaded_frames = full_frames[::-1].copy()
            return MolTrackImageSeries(
                source_path=str(source_path_arg),
                raw_frames=loaded_frames,
                metadata=STMSequenceMetadata(pixels_x=4, pixels_y=2),
                reverse_frame_order=True,
            )

        restored = restore_moltrack_image_series_from_session(
            MolTrackSession(
                source_path="movie.mpp",
                source_frame_indices=(4, 2),
                active_frame_index=1,
                reverse_frame_order=True,
            ),
            series_loader=fake_loader,
        )

        self.assertEqual(restored.source_frame_indices, (4, 2))
        np.testing.assert_array_equal(restored.raw_frames, full_frames[[4, 2]])


if __name__ == "__main__":
    unittest.main()
