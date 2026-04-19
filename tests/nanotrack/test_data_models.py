import unittest

import numpy as np

from nanotrack.core.data_models import STMSequence, STMSequenceMetadata


class STMSequenceMetadataTests(unittest.TestCase):
    def test_normalizes_frame_times_to_1d_float_array(self) -> None:
        metadata = STMSequenceMetadata(frame_times_s=[0, 1, 2])

        self.assertIsInstance(metadata.frame_times_s, np.ndarray)
        self.assertEqual(metadata.frame_times_s.dtype, np.float64)
        np.testing.assert_allclose(metadata.frame_times_s, [0.0, 1.0, 2.0])

    def test_rejects_non_1d_frame_times(self) -> None:
        with self.assertRaises(ValueError):
            STMSequenceMetadata(frame_times_s=[[0.0, 1.0]])


class STMSequenceTests(unittest.TestCase):
    def test_infers_missing_pixel_dimensions_from_raw_frames(self) -> None:
        frames = np.zeros((3, 5, 7), dtype=np.float32)
        sequence = STMSequence(
            source_path="movie.mpp",
            raw_frames=frames,
            metadata=STMSequenceMetadata(),
        )

        self.assertEqual(sequence.file_name, "movie.mpp")
        self.assertEqual(sequence.frame_count, 3)
        self.assertEqual(sequence.frame_shape, (5, 7))
        self.assertEqual(sequence.metadata.pixels_y, 5)
        self.assertEqual(sequence.metadata.pixels_x, 7)
        np.testing.assert_array_equal(sequence.active_frame, frames[0])

    def test_uses_explicit_frame_times_for_active_frame_time(self) -> None:
        frames = np.ones((3, 4, 4), dtype=np.float32)
        sequence = STMSequence(
            source_path="/tmp/sequence.mpp",
            raw_frames=frames,
            metadata=STMSequenceMetadata(
                pixels_x=4,
                pixels_y=4,
                frame_times_s=np.array([0.25, 0.75, 1.5]),
            ),
            active_frame_index=1,
        )

        self.assertEqual(sequence.active_frame_time_s, 0.75)

    def test_falls_back_to_frame_interval_when_frame_times_missing(self) -> None:
        frames = np.ones((4, 2, 2), dtype=np.float32)
        sequence = STMSequence(
            source_path="sequence.mpp",
            raw_frames=frames,
            metadata=STMSequenceMetadata(
                pixels_x=2,
                pixels_y=2,
                frame_interval_s=0.4,
            ),
        )

        self.assertAlmostEqual(sequence.get_frame_time_s(3), 1.2)

    def test_set_active_frame_updates_current_frame(self) -> None:
        frames = np.arange(27, dtype=np.float32).reshape(3, 3, 3)
        sequence = STMSequence(
            source_path="sequence.mpp",
            raw_frames=frames,
            metadata=STMSequenceMetadata(pixels_x=3, pixels_y=3),
        )

        sequence.set_active_frame(2)

        self.assertEqual(sequence.active_frame_index, 2)
        np.testing.assert_array_equal(sequence.active_frame, frames[2])

    def test_rejects_shape_mismatch_between_metadata_and_frames(self) -> None:
        frames = np.zeros((2, 4, 5), dtype=np.float32)

        with self.assertRaises(ValueError):
            STMSequence(
                source_path="sequence.mpp",
                raw_frames=frames,
                metadata=STMSequenceMetadata(pixels_x=6, pixels_y=4),
            )

    def test_rejects_invalid_active_frame_index(self) -> None:
        frames = np.zeros((2, 4, 5), dtype=np.float32)

        with self.assertRaises(IndexError):
            STMSequence(
                source_path="sequence.mpp",
                raw_frames=frames,
                metadata=STMSequenceMetadata(pixels_x=5, pixels_y=4),
                active_frame_index=2,
            )

    def test_rejects_frame_time_count_mismatch(self) -> None:
        frames = np.zeros((2, 4, 5), dtype=np.float32)

        with self.assertRaises(ValueError):
            STMSequence(
                source_path="sequence.mpp",
                raw_frames=frames,
                metadata=STMSequenceMetadata(
                    pixels_x=5,
                    pixels_y=4,
                    frame_times_s=np.array([0.0]),
                ),
            )


if __name__ == "__main__":
    unittest.main()
