import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from nanotrack.core.data_models import STMSequence
from nanotrack.io.mpp_loader import load_mpp_sequence
from napara.core.data_models import STMImage


REPO_ROOT = Path(__file__).resolve().parents[2]
SAMPLE_MPP = REPO_ROOT / "data" / "MOVIE_3.MPP"


class MPPLoaderTests(unittest.TestCase):
    def test_loads_sample_mpp_as_sequence(self) -> None:
        sequence = load_mpp_sequence(str(SAMPLE_MPP))

        self.assertIsInstance(sequence, STMSequence)
        self.assertEqual(sequence.file_name, "MOVIE_3.MPP")
        self.assertGreater(sequence.frame_count, 1)
        self.assertEqual(sequence.raw_frames.ndim, 3)
        self.assertEqual(sequence.frame_shape, (sequence.metadata.pixels_y, sequence.metadata.pixels_x))
        self.assertIn("General Info", sequence.metadata.raw_header)
        self.assertEqual(
            int(sequence.metadata.raw_header["General Info"]["Number of Frames"]),
            sequence.frame_count,
        )
        self.assertIsNotNone(sequence.metadata.frame_times_s)
        self.assertEqual(len(sequence.metadata.frame_times_s), sequence.frame_count)
        np.testing.assert_array_equal(sequence.active_frame, sequence.raw_frames[0])

    @patch("nanotrack.io.mpp_loader.read_mpp_file")
    def test_sorts_frames_by_frame_index_and_extracts_sync_times(self, read_mpp_file_mock) -> None:
        header = {
            "General Info": {
                "Number of columns": "3",
                "Number of rows": "2",
                "Number of Frames": "2",
            },
            "Frames Synchronization": {
                "Frame 0000": "0.5 s",
                "Frame 0001": "1.5 s",
            },
        }
        read_mpp_file_mock.return_value = [
            STMImage(
                file_name="movie.mpp",
                raw_header=header,
                data=np.array([[1, 2, 3], [4, 5, 6]], dtype=np.float32),
                pixels_x=3,
                pixels_y=2,
                size_nm_x=30.0,
                size_nm_y=20.0,
                frame_index=1,
            ),
            STMImage(
                file_name="movie.mpp",
                raw_header=header,
                data=np.array([[7, 8, 9], [10, 11, 12]], dtype=np.float32),
                pixels_x=3,
                pixels_y=2,
                size_nm_x=30.0,
                size_nm_y=20.0,
                frame_index=0,
            ),
        ]

        sequence = load_mpp_sequence("movie.mpp")

        np.testing.assert_array_equal(
            sequence.get_frame(0),
            np.array([[12, 11, 10], [9, 8, 7]], dtype=np.float32),
        )
        np.testing.assert_array_equal(
            sequence.get_frame(1),
            np.array([[6, 5, 4], [3, 2, 1]], dtype=np.float32),
        )
        np.testing.assert_allclose(sequence.metadata.frame_times_s, [0.5, 1.5])
        self.assertEqual(sequence.metadata.frame_interval_s, 1.0)

    def test_rejects_non_mpp_extension(self) -> None:
        with self.assertRaises(ValueError):
            load_mpp_sequence("image.stp")


if __name__ == "__main__":
    unittest.main()
