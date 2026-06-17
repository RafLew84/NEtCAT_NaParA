import unittest

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
from nanotrack.core import STMSequenceMetadata


class MolTrackSessionTests(unittest.TestCase):
    def test_session_captures_working_series_state_after_removal_and_registration(self) -> None:
        frames = np.arange(32, dtype=np.float32).reshape(4, 2, 4)
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames.copy(),
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=2),
            active_frame_index=2,
        )
        series.remove_frame(1)
        settings = MolTrackRegistrationSettings(backend="optical_flow_median")
        series.registration_results = MolTrackRegistrationResultSet(
            settings=settings,
            results_by_frame={
                frame_index: MolTrackRegistrationFrameResult(
                    frame_index=frame_index,
                    shift_xy=(float(frame_index), -float(frame_index)),
                    method="optical_flow_median",
                    quality_score=0.8,
                )
                for frame_index in range(series.frame_count)
            },
        )
        detections = MolecularDetectionSet(frame_count=series.frame_count)
        detections.set_detections(
            1,
            [
                MolecularDetection(
                    frame_index=1,
                    bbox_xyxy=(0, 0, 2, 1),
                    confidence=0.8,
                    model_name="model-a.pt",
                    checkpoint_path="nanotrack/yolo_models/model-a.pt",
                    source_view="raw",
                )
            ],
            source_view="raw",
            frame_shape=(2, 4),
        )
        series.molecular_detections = detections

        session = MolTrackSession.from_image_series(
            series,
            registration_view_mode="Show expanded aligned",
            source_size_bytes=1234,
            source_mtime_ns=5678,
        )

        self.assertEqual(session.schema_version, 1)
        self.assertEqual(session.source_path, "movie.mpp")
        self.assertEqual(session.source_size_bytes, 1234)
        self.assertEqual(session.source_mtime_ns, 5678)
        self.assertEqual(session.source_frame_indices, (0, 2, 3))
        self.assertEqual(session.active_frame_index, 1)
        self.assertFalse(session.reverse_frame_order)
        self.assertEqual(session.registration_view_mode, "Show expanded aligned")
        self.assertIs(session.registration_settings, settings)
        self.assertIs(session.registration_results, series.registration_results)
        self.assertIs(session.molecular_detections, detections)

    def test_session_rejects_invalid_state_for_later_restore(self) -> None:
        with self.assertRaises(IndexError):
            MolTrackSession(
                source_path="movie.mpp",
                source_frame_indices=(0, 2),
                active_frame_index=2,
            )

        with self.assertRaisesRegex(ValueError, "Unsupported registration_view_mode"):
            MolTrackSession(
                source_path="movie.mpp",
                source_frame_indices=(0, 2),
                active_frame_index=1,
                registration_view_mode="Show aligned",
            )

        result_set = MolTrackRegistrationResultSet(
            settings=MolTrackRegistrationSettings(),
            results_by_frame={
                0: MolTrackRegistrationFrameResult(
                    frame_index=0,
                    shift_xy=(0.0, 0.0),
                    method="identity",
                ),
            },
        )

        with self.assertRaisesRegex(ValueError, "do not match source_frame_indices length"):
            MolTrackSession(
                source_path="movie.mpp",
                source_frame_indices=(0, 2),
                active_frame_index=1,
                registration_results=result_set,
            )

        with self.assertRaisesRegex(ValueError, "molecular_detections do not match"):
            MolTrackSession(
                source_path="movie.mpp",
                source_frame_indices=(0, 2),
                active_frame_index=1,
                molecular_detections=MolecularDetectionSet(frame_count=1),
            )


if __name__ == "__main__":
    unittest.main()
