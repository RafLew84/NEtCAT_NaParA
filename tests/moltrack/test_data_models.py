import unittest

import numpy as np

from moltrack.core import (
    MolecularDetection,
    MolecularDetectionSet,
    MolecularSegmentation,
    MolecularSegmentationSet,
    MolTrackImageSeries,
)
from nanotrack.core import STMSequence, STMSequenceMetadata


class MolTrackImageSeriesTests(unittest.TestCase):
    def test_image_series_exposes_frames_and_physical_pixel_size(self) -> None:
        frames = np.arange(24, dtype=np.float32).reshape(3, 2, 4)
        metadata = STMSequenceMetadata(
            pixels_x=4,
            pixels_y=2,
            size_nm_x=8.0,
            size_nm_y=1.0,
        )

        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames,
            metadata=metadata,
        )

        self.assertEqual(series.frame_count, 3)
        self.assertEqual(series.frame_shape, (2, 4))
        np.testing.assert_array_equal(series.active_frame, frames[0])
        self.assertEqual(series.pixel_size_nm, (2.0, 0.5))

    def test_image_series_can_select_active_frame(self) -> None:
        frames = np.arange(24, dtype=np.float32).reshape(3, 2, 4)
        metadata = STMSequenceMetadata(pixels_x=4, pixels_y=2)
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames,
            metadata=metadata,
        )

        series.set_active_frame(2)

        self.assertEqual(series.active_frame_index, 2)
        np.testing.assert_array_equal(series.active_frame, frames[2])
        np.testing.assert_array_equal(series.get_frame(1), frames[1])

    def test_image_series_removes_active_frame_from_working_series(self) -> None:
        frames = np.arange(24, dtype=np.float32).reshape(3, 2, 4)
        metadata = STMSequenceMetadata(pixels_x=4, pixels_y=2)
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames,
            metadata=metadata,
            active_frame_index=1,
        )

        series.remove_frame()

        self.assertEqual(series.frame_count, 2)
        self.assertEqual(series.active_frame_index, 1)
        np.testing.assert_array_equal(series.raw_frames, frames[[0, 2]])
        np.testing.assert_array_equal(series.active_frame, frames[2])

    def test_image_series_tracks_source_frame_indices_when_removing_frames(self) -> None:
        frames = np.arange(32, dtype=np.float32).reshape(4, 2, 4)
        metadata = STMSequenceMetadata(pixels_x=4, pixels_y=2)
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames,
            metadata=metadata,
        )

        self.assertEqual(series.source_frame_indices, (0, 1, 2, 3))

        series.remove_frame(1)
        series.remove_frame(2)

        self.assertEqual(series.source_frame_indices, (0, 2))
        np.testing.assert_array_equal(series.raw_frames, frames[[0, 2]])

    def test_image_series_clears_molecular_detections_when_removing_frame(self) -> None:
        frames = np.arange(24, dtype=np.float32).reshape(3, 2, 4)
        detections = MolecularDetectionSet(frame_count=3)
        detections.set_detections(
            1,
            [MolecularDetection(frame_index=1, bbox_xyxy=(0, 0, 2, 1), confidence=0.9)],
            source_view="raw",
            frame_shape=(2, 4),
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames,
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=2),
            molecular_detections=detections,
        )

        series.remove_frame(0)

        self.assertIsNone(series.molecular_detections)

    def test_image_series_clears_molecular_segmentations_when_removing_frame(self) -> None:
        frames = np.arange(24, dtype=np.float32).reshape(3, 2, 4)
        segmentations = MolecularSegmentationSet(frame_count=3)
        segmentations.add_segmentation(
            MolecularSegmentation(
                frame_index=1,
                source_view="raw",
                mask=np.ones((2, 4), dtype=bool),
                segmentation_id="seg-1",
            )
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames,
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=2),
            molecular_segmentations=segmentations,
        )

        series.remove_frame(0)

        self.assertIsNone(series.molecular_segmentations)

    def test_image_series_defaults_reversed_source_frame_indices_for_reverse_order(self) -> None:
        frames = np.arange(24, dtype=np.float32).reshape(3, 2, 4)
        metadata = STMSequenceMetadata(pixels_x=4, pixels_y=2)

        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames,
            metadata=metadata,
            reverse_frame_order=True,
        )

        self.assertEqual(series.source_frame_indices, (2, 1, 0))

    def test_image_series_rejects_invalid_source_frame_indices(self) -> None:
        frames = np.arange(24, dtype=np.float32).reshape(3, 2, 4)
        metadata = STMSequenceMetadata(pixels_x=4, pixels_y=2)

        with self.assertRaisesRegex(ValueError, "length must match"):
            MolTrackImageSeries(
                source_path="movie.mpp",
                raw_frames=frames,
                metadata=metadata,
                source_frame_indices=(0, 1),
            )

        with self.assertRaisesRegex(ValueError, "must not contain duplicates"):
            MolTrackImageSeries(
                source_path="movie.mpp",
                raw_frames=frames,
                metadata=metadata,
                source_frame_indices=(0, 1, 1),
            )

    def test_image_series_keeps_at_least_one_frame_active(self) -> None:
        frames = np.arange(16, dtype=np.float32).reshape(2, 2, 4)
        metadata = STMSequenceMetadata(pixels_x=4, pixels_y=2)
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames,
            metadata=metadata,
        )

        series.remove_frame(0)

        with self.assertRaises(ValueError):
            series.remove_frame(0)

        self.assertEqual(series.frame_count, 1)
        self.assertEqual(series.active_frame_index, 0)
        np.testing.assert_array_equal(series.active_frame, frames[1])

    def test_image_series_rejects_frame_indexes_outside_series(self) -> None:
        frames = np.arange(24, dtype=np.float32).reshape(3, 2, 4)
        metadata = STMSequenceMetadata(pixels_x=4, pixels_y=2)
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames,
            metadata=metadata,
            active_frame_index=1,
        )

        with self.assertRaises(IndexError):
            series.get_frame(3)

        with self.assertRaises(IndexError):
            series.set_active_frame(-1)

        self.assertEqual(series.active_frame_index, 1)

    def test_image_series_rejects_metadata_dimensions_that_do_not_match_frames(self) -> None:
        frames = np.zeros((3, 2, 4), dtype=np.float32)
        metadata = STMSequenceMetadata(pixels_x=5, pixels_y=2)

        with self.assertRaises(ValueError):
            MolTrackImageSeries(
                source_path="movie.mpp",
                raw_frames=frames,
                metadata=metadata,
            )

    def test_image_series_can_be_created_from_nanotrack_sequence(self) -> None:
        frames = np.arange(24, dtype=np.float32).reshape(3, 2, 4)
        metadata = STMSequenceMetadata(pixels_x=4, pixels_y=2)
        sequence = STMSequence(
            source_path="movie.mpp",
            raw_frames=frames,
            metadata=metadata,
            active_frame_index=1,
            reverse_frame_order=True,
        )

        series = MolTrackImageSeries.from_stm_sequence(sequence)

        self.assertEqual(series.source_path, "movie.mpp")
        self.assertEqual(series.active_frame_index, 1)
        self.assertTrue(series.reverse_frame_order)
        np.testing.assert_array_equal(series.active_frame, frames[1])


if __name__ == "__main__":
    unittest.main()
