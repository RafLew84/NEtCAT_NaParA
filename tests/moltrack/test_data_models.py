import unittest

import numpy as np

from moltrack.core import MolTrackImageSeries
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
