import unittest
from unittest.mock import patch

import numpy as np

from nanotrack.core import STMSequence, STMSequenceMetadata


def _sequence(source_path: str, raw_frames: np.ndarray) -> STMSequence:
    frame_count, pixels_y, pixels_x = raw_frames.shape
    return STMSequence(
        source_path=source_path,
        raw_frames=raw_frames,
        metadata=STMSequenceMetadata(
            pixels_x=pixels_x,
            pixels_y=pixels_y,
            raw_header={"test": "metadata", "frame_count": frame_count},
        ),
    )


class MolTrackImporterTests(unittest.TestCase):
    def test_imports_single_mpp_as_one_moltrack_project(self) -> None:
        from moltrack.io import import_image_series

        frames = np.arange(12, dtype=np.float32).reshape(2, 2, 3)
        loaded_sequence = _sequence("movie.mpp", frames)

        with patch("moltrack.io.importer.load_stm_sequence", return_value=loaded_sequence) as load_mock:
            project = import_image_series("movie.mpp", project_name="mpp project")

        load_mock.assert_called_once_with("movie.mpp")
        self.assertEqual(project.project_name, "mpp project")
        self.assertEqual(project.source_series.source_uri, "movie.mpp")
        self.assertEqual(project.source_series.source_uris, ("movie.mpp",))
        self.assertEqual(project.source_series.frame_count, 2)
        self.assertEqual(project.source_series.frame_shape, (2, 3))
        np.testing.assert_array_equal(project.source_series.get_frame(1), frames[1])
        self.assertEqual(project.working_series.source_frame_indices(), [0, 1])

    def test_imports_stp_s94_path_list_as_one_series(self) -> None:
        from moltrack.io import import_image_series

        frames = np.asarray([[[1.0]], [[2.0]], [[3.0]]], dtype=np.float32)
        loaded_sequence = _sequence("frame_a_series_3_frames", frames)

        with patch("moltrack.io.importer.load_stm_sequence", return_value=loaded_sequence) as load_mock:
            project = import_image_series(["frame_a.stp", "frame_b.s94", "frame_c.stp"])

        load_mock.assert_called_once_with(["frame_a.stp", "frame_b.s94", "frame_c.stp"])
        self.assertEqual(project.source_series.source_uri, "frame_a_series_3_frames")
        self.assertEqual(project.source_series.source_uris, ("frame_a.stp", "frame_b.s94", "frame_c.stp"))
        self.assertEqual(project.source_series.frame_count, 3)
        self.assertEqual(project.working_series.frame_count, 3)
        self.assertEqual(project.working_series.source_frame_indices(), [0, 1, 2])
        np.testing.assert_array_equal(project.source_series.get_frame(2), frames[2])

    def test_reversed_import_reverses_working_series_without_reversing_source_series(self) -> None:
        from moltrack.io import import_image_series

        frames = np.asarray([[[1.0]], [[2.0]], [[3.0]]], dtype=np.float32)
        loaded_sequence = _sequence("movie.mpp", frames)

        with patch("moltrack.io.importer.load_stm_sequence", return_value=loaded_sequence) as load_mock:
            project = import_image_series("movie.mpp", reverse_frame_order=True)

        load_mock.assert_called_once_with("movie.mpp")
        self.assertEqual(project.source_series.frame_count, 3)
        np.testing.assert_array_equal(project.source_series.get_frame(0), frames[0])
        np.testing.assert_array_equal(project.source_series.get_frame(2), frames[2])
        self.assertEqual(project.working_series.source_frame_indices(), [2, 1, 0])
        self.assertEqual(project.working_series.get_source_frame_index(0), 2)
        self.assertEqual(project.working_series.get_source_frame_index(2), 0)


if __name__ == "__main__":
    unittest.main()
