import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import numpy as np

from nanotrack.trackers import PointTrackerRunInput, PointTrackerRunOutput
from nanotrack.trackers.run_trackonr_subprocess import (
    _build_stub_output,
    _frames_to_rgb_uint8,
    _query_points_tyx_to_txy,
)


class TrackOnRWorkerHelperTests(unittest.TestCase):
    def test_frames_to_rgb_uint8_expands_grayscale_video(self) -> None:
        frames = np.asarray(
            [
                [[0.0, 1.0], [2.0, 3.0]],
                [[4.0, 5.0], [6.0, 7.0]],
            ],
            dtype=np.float32,
        )

        rgb = _frames_to_rgb_uint8(frames)

        self.assertEqual(rgb.shape, (2, 2, 2, 3))
        self.assertEqual(rgb.dtype, np.uint8)
        np.testing.assert_array_equal(rgb[..., 0], rgb[..., 1])
        np.testing.assert_array_equal(rgb[..., 1], rgb[..., 2])

    def test_query_points_tyx_to_txy_reorders_spatial_axes(self) -> None:
        query_points_tyx = np.asarray([[1.0, 10.0, 20.0], [3.0, 5.5, 7.25]], dtype=np.float32)

        converted = _query_points_tyx_to_txy(query_points_tyx)

        np.testing.assert_allclose(
            converted,
            np.asarray([[1.0, 20.0, 10.0], [3.0, 7.25, 5.5]], dtype=np.float32),
        )

    def test_build_stub_output_keeps_points_fixed_and_visible_after_seed(self) -> None:
        run_input = PointTrackerRunInput(
            frames=np.zeros((4, 6, 8), dtype=np.float32),
            query_points_tyx=np.asarray([[0.0, 2.0, 3.0], [2.0, 4.0, 5.0]], dtype=np.float32),
            source_view="raw",
        )

        output = _build_stub_output(run_input, model_name="trackonr_stub", checkpoint_name=None)

        self.assertEqual(output.model_name, "trackonr_stub")
        self.assertEqual(output.tracks_xy.shape, (2, 4, 2))
        np.testing.assert_array_equal(output.tracks_xy[0, :, 0], np.asarray([3.0, 3.0, 3.0, 3.0], dtype=np.float32))
        np.testing.assert_array_equal(output.tracks_xy[0, :, 1], np.asarray([2.0, 2.0, 2.0, 2.0], dtype=np.float32))
        np.testing.assert_array_equal(output.visible_mask[0], np.asarray([True, True, True, True]))
        np.testing.assert_array_equal(output.visible_mask[1], np.asarray([False, False, True, True]))


class TrackOnRWorkerScriptTests(unittest.TestCase):
    def test_worker_script_runs_stub_mode_without_checkpoint(self) -> None:
        worker_script = (
            Path(__file__).resolve().parents[2]
            / "nanotrack"
            / "trackers"
            / "run_trackonr_subprocess.py"
        )

        run_input = PointTrackerRunInput(
            frames=np.zeros((3, 5, 7), dtype=np.float32),
            query_points_tyx=np.asarray([[1.0, 2.0, 4.0]], dtype=np.float32),
            source_view="raw",
        )

        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            input_path = temp_path / "input.npz"
            output_path = temp_path / "output.npz"
            np.savez_compressed(input_path, **run_input.to_npz_payload())

            completed = subprocess.run(
                [
                    sys.executable,
                    str(worker_script),
                    "--input-npz",
                    str(input_path),
                    "--output-npz",
                    str(output_path),
                    "--model-name",
                    "trackonr",
                    "--device",
                    "cpu",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, msg=completed.stderr)
            self.assertTrue(output_path.exists())

            with np.load(output_path, allow_pickle=False) as payload:
                output_payload = {key: payload[key] for key in payload.files}
            result = PointTrackerRunOutput.from_npz_payload(output_payload)

            self.assertEqual(result.model_name, "trackonr_stub")
            self.assertIsNone(result.checkpoint_name)
            np.testing.assert_array_equal(result.visible_mask[0], np.asarray([False, True, True]))
            np.testing.assert_array_equal(result.tracks_xy[0, :, 0], np.asarray([4.0, 4.0, 4.0], dtype=np.float32))
            np.testing.assert_array_equal(result.tracks_xy[0, :, 1], np.asarray([2.0, 2.0, 2.0], dtype=np.float32))


if __name__ == "__main__":
    unittest.main()
