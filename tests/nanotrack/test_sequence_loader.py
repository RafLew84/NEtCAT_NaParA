import unittest
from unittest.mock import patch

import numpy as np

from nanotrack.core.data_models import STMSequence, STMSequenceMetadata
from nanotrack.io.sequence_loader import load_stm_sequence
from napara.core.data_models import STMImage


def _stm_image(path: str, data: np.ndarray, *, image_type: str = "Topography") -> STMImage:
    pixels_y, pixels_x = data.shape
    return STMImage(
        file_name=path,
        raw_header={"source": path, "image_type": image_type},
        data=data,
        pixels_x=pixels_x,
        pixels_y=pixels_y,
        size_nm_x=10.0,
        size_nm_y=20.0,
        offset_nm_x=1.0,
        offset_nm_y=2.0,
        scan_angle_deg=3.0,
        bias_v=0.5,
        setpoint_a=1e-9,
        image_type=image_type,
    )


class STMSequenceLoaderTests(unittest.TestCase):
    def test_single_mpp_delegates_to_mpp_loader(self) -> None:
        expected = STMSequence(
            source_path="movie.mpp",
            raw_frames=np.zeros((1, 2, 3), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=3, pixels_y=2),
        )

        with patch("nanotrack.io.sequence_loader.load_mpp_sequence", return_value=expected) as load_mpp_mock:
            sequence = load_stm_sequence("movie.mpp", reverse_frame_order=True)

        self.assertIs(sequence, expected)
        load_mpp_mock.assert_called_once_with("movie.mpp", reverse_frame_order=True)

    def test_loads_stp_s94_series_strictly_in_input_order(self) -> None:
        images_by_path = {
            "frame_a.stp": [_stm_image("frame_a.stp", np.array([[1, 2], [3, 4]], dtype=np.float32))],
            "frame_b.s94": [_stm_image("frame_b.s94", np.array([[5, 6], [7, 8]], dtype=np.float32))],
            "frame_c.stp": [_stm_image("frame_c.stp", np.array([[9, 10], [11, 12]], dtype=np.float32))],
        }

        with patch("nanotrack.io.sequence_loader.load_stm_path", side_effect=lambda path: images_by_path[path]):
            sequence = load_stm_sequence(["frame_a.stp", "frame_b.s94", "frame_c.stp"])

        self.assertIsInstance(sequence, STMSequence)
        self.assertEqual(sequence.frame_count, 3)
        np.testing.assert_array_equal(
            sequence.raw_frames,
            np.array(
                [
                    [[1, 2], [3, 4]],
                    [[5, 6], [7, 8]],
                    [[9, 10], [11, 12]],
                ],
                dtype=np.float32,
            ),
        )
        self.assertEqual(sequence.frame_shape, (2, 2))
        self.assertEqual(sequence.metadata.pixels_x, 2)
        self.assertEqual(sequence.metadata.pixels_y, 2)
        self.assertEqual(sequence.metadata.size_nm_x, 10.0)
        self.assertEqual(sequence.metadata.size_nm_y, 20.0)
        self.assertIsNone(sequence.metadata.frame_times_s)
        self.assertIsNone(sequence.metadata.frame_interval_s)
        self.assertEqual(sequence.metadata.raw_header["NanoTrack Source"]["source_files"], ["frame_a.stp", "frame_b.s94", "frame_c.stp"])
        self.assertEqual(sequence.metadata.raw_header["NanoTrack Source"]["source_extensions"], [".stp", ".s94", ".stp"])
        self.assertEqual(len(sequence.metadata.raw_header["NanoTrack Frame Headers"]), 3)

    def test_can_reverse_stp_s94_series_order(self) -> None:
        images_by_path = {
            "frame_a.stp": [_stm_image("frame_a.stp", np.array([[1]], dtype=np.float32))],
            "frame_b.s94": [_stm_image("frame_b.s94", np.array([[2]], dtype=np.float32))],
        }

        with patch("nanotrack.io.sequence_loader.load_stm_path", side_effect=lambda path: images_by_path[path]):
            sequence = load_stm_sequence(["frame_a.stp", "frame_b.s94"], reverse_frame_order=True)

        self.assertTrue(sequence.reverse_frame_order)
        np.testing.assert_array_equal(sequence.raw_frames[:, 0, 0], np.asarray([2, 1], dtype=np.float32))
        self.assertEqual(sequence.metadata.raw_header["NanoTrack Source"]["source_files"], ["frame_b.s94", "frame_a.stp"])

    def test_rejects_empty_source_list(self) -> None:
        with self.assertRaisesRegex(ValueError, "At least one STM source path"):
            load_stm_sequence([])

    def test_rejects_mpp_inside_frame_series(self) -> None:
        with self.assertRaisesRegex(ValueError, "MPP loading accepts a single"):
            load_stm_sequence(["movie_a.mpp", "movie_b.mpp"])

    def test_rejects_unsupported_extension(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unsupported STM source extension"):
            load_stm_sequence("image.txt")

    def test_reader_failure_is_strict(self) -> None:
        with patch("nanotrack.io.sequence_loader.load_stm_path", side_effect=RuntimeError("bad file")):
            with self.assertRaisesRegex(ValueError, "Cannot load STM source: broken.stp") as exc_info:
                load_stm_sequence("broken.stp")

        self.assertIsInstance(exc_info.exception.__cause__, RuntimeError)

    def test_empty_reader_result_is_strict(self) -> None:
        with patch("nanotrack.io.sequence_loader.load_stm_path", return_value=[]):
            with self.assertRaisesRegex(ValueError, "did not contain any frames"):
                load_stm_sequence("empty.s94")

    def test_rejects_shape_mismatch(self) -> None:
        images_by_path = {
            "frame_a.stp": [_stm_image("frame_a.stp", np.zeros((2, 2), dtype=np.float32))],
            "frame_b.stp": [_stm_image("frame_b.stp", np.zeros((3, 2), dtype=np.float32))],
        }

        with patch("nanotrack.io.sequence_loader.load_stm_path", side_effect=lambda path: images_by_path[path]):
            with self.assertRaisesRegex(ValueError, "STM frame shapes must match"):
                load_stm_sequence(["frame_a.stp", "frame_b.stp"])

    def test_rejects_non_2d_frames(self) -> None:
        image = _stm_image("frame_a.stp", np.zeros((2, 2), dtype=np.float32))
        image.data = np.zeros((1, 2, 2), dtype=np.float32)

        with patch("nanotrack.io.sequence_loader.load_stm_path", return_value=[image]):
            with self.assertRaisesRegex(ValueError, "must be a 2D image"):
                load_stm_sequence("frame_a.stp")


if __name__ == "__main__":
    unittest.main()
