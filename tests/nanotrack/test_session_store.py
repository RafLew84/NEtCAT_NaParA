import tempfile
import unittest

import numpy as np

from nanotrack.core import (
    AnnotationSource,
    BBoxXYXY,
    FrameVisibility,
    ParticleMetrics,
    ParticleTrack,
    STMSequence,
    STMSequenceMetadata,
    TrackFrameAnnotation,
    TrackQuality,
)
from nanotrack.persistence import NanoTrackSessionSnapshot, load_session_snapshot, save_session_snapshot


class SessionStoreTests(unittest.TestCase):
    def test_roundtrip_preserves_tracks_masks_metrics_and_preprocessing(self) -> None:
        sequence = STMSequence(
            source_path="/tmp/source.mpp",
            raw_frames=np.arange(3 * 4 * 5, dtype=np.float32).reshape(3, 4, 5),
            metadata=STMSequenceMetadata(
                pixels_x=5,
                pixels_y=4,
                size_nm_x=10.0,
                size_nm_y=8.0,
                frame_interval_s=0.5,
            ),
            active_frame_index=2,
            reverse_frame_order=True,
        )
        track = ParticleTrack(
            track_id=7,
            seed_frame_index=1,
            seed_bbox=BBoxXYXY(1.0, 1.0, 4.0, 3.0),
            quality=TrackQuality.NEEDS_REVIEW,
            label="NP-7",
        )
        track.add_annotation(
            TrackFrameAnnotation(
                frame_index=2,
                bbox=BBoxXYXY(1.5, 1.0, 4.5, 3.5),
                mask=np.asarray(
                    [
                        [False, True, True, False, False],
                        [False, True, True, False, False],
                        [False, False, False, False, False],
                        [False, False, False, False, False],
                    ],
                    dtype=bool,
                ),
                visibility=FrameVisibility.VISIBLE,
                source=AnnotationSource.SAM2,
                metrics=ParticleMetrics(
                    area_px=4.0,
                    perimeter_px=8.0,
                    area_nm2=32.0,
                    perimeter_nm=14.0,
                    intensity_sum=18.0,
                    intensity_mean=4.5,
                    intensity_max=7.0,
                ),
            )
        )
        track.add_annotation(
            TrackFrameAnnotation(
                frame_index=3,
                mask=np.zeros((4, 5), dtype=bool),
                visibility=FrameVisibility.LOST,
                source=AnnotationSource.RESUME,
            )
        )
        snapshot = NanoTrackSessionSnapshot(
            sequence=sequence,
            tracks=[track],
            selected_track_id=7,
            draft_bboxes_by_frame={2: BBoxXYXY(0.0, 0.0, 3.0, 2.0)},
            repair_frames=np.full_like(sequence.raw_frames, 0.25, dtype=np.float32),
            repair_params={"threshold_sigma": 3.0, "repair_mode": "vertical_interp"},
            denoised_frames=np.full_like(sequence.raw_frames, 0.75, dtype=np.float32),
            denoised_sigma_factor=1.4,
            show_denoised_in_viewer=True,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            session_path = f"{tmpdir}/roundtrip.nanotrack"
            save_session_snapshot(session_path, snapshot)

            loaded = load_session_snapshot(
                session_path,
                sequence_loader=lambda _path, reverse_frame_order=False: STMSequence(
                    source_path="/tmp/source.mpp",
                    raw_frames=np.arange(3 * 4 * 5, dtype=np.float32).reshape(3, 4, 5),
                    metadata=STMSequenceMetadata(
                        pixels_x=5,
                        pixels_y=4,
                        size_nm_x=10.0,
                        size_nm_y=8.0,
                        frame_interval_s=0.5,
                    ),
                    reverse_frame_order=reverse_frame_order,
                ),
            )

        self.assertEqual(loaded.sequence.source_path, "/tmp/source.mpp")
        self.assertEqual(loaded.sequence.active_frame_index, 2)
        self.assertTrue(loaded.sequence.reverse_frame_order)
        self.assertEqual(loaded.selected_track_id, 7)
        self.assertTrue(loaded.show_denoised_in_viewer)
        self.assertEqual(loaded.draft_bboxes_by_frame[2], BBoxXYXY(0.0, 0.0, 3.0, 2.0))
        np.testing.assert_array_equal(loaded.repair_frames, snapshot.repair_frames)
        np.testing.assert_array_equal(loaded.denoised_frames, snapshot.denoised_frames)
        self.assertEqual(loaded.repair_params, snapshot.repair_params)
        self.assertEqual(loaded.denoised_sigma_factor, 1.4)

        restored_track = loaded.tracks[0]
        self.assertEqual(restored_track.track_id, 7)
        self.assertEqual(restored_track.label, "NP-7")
        self.assertEqual(restored_track.quality, TrackQuality.NEEDS_REVIEW)
        restored_visible = restored_track.get_annotation(2)
        self.assertEqual(restored_visible.source, AnnotationSource.SAM2)
        np.testing.assert_array_equal(restored_visible.mask, track.get_annotation(2).mask)
        self.assertEqual(restored_visible.metrics.area_px, 4.0)
        self.assertEqual(restored_visible.metrics.perimeter_px, 8.0)
        self.assertEqual(restored_visible.metrics.area_nm2, 32.0)
        self.assertEqual(restored_visible.metrics.perimeter_nm, 14.0)
        self.assertEqual(restored_visible.metrics.intensity_sum, 18.0)
        restored_lost = restored_track.get_annotation(3)
        self.assertEqual(restored_lost.visibility, FrameVisibility.LOST)
        np.testing.assert_array_equal(restored_lost.mask, np.zeros((4, 5), dtype=bool))


if __name__ == "__main__":
    unittest.main()
