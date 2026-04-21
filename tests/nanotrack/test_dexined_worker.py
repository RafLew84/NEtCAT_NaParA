import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from nanotrack.edges import DexiNedRunInput, DexiNedRunOutput
from nanotrack.edges.run_dexined_subprocess import _build_stub_output, _compute_polygon_edge_mask


class DexiNedWorkerHelperTests(unittest.TestCase):
    def test_compute_polygon_edge_mask_returns_boundary_of_roi(self) -> None:
        polygon_mask = np.zeros((6, 8), dtype=bool)
        polygon_mask[1:5, 2:7] = True

        edge_mask = _compute_polygon_edge_mask(polygon_mask)

        expected = np.zeros((6, 8), dtype=bool)
        expected[1:5, 2:7] = True
        expected[2:4, 3:6] = False
        np.testing.assert_array_equal(edge_mask, expected)

    def test_build_stub_output_repeats_edge_map_for_each_frame(self) -> None:
        polygon_mask = np.zeros((5, 6), dtype=bool)
        polygon_mask[1:4, 1:5] = True
        run_input = DexiNedRunInput(
            frames=np.zeros((3, 5, 6), dtype=np.float32),
            polygon_mask=polygon_mask,
            threshold=0.5,
        )

        run_output = _build_stub_output(run_input, "DexiNed_BIPED_10.pth")

        self.assertEqual(run_output.model_name, "dexined_stub")
        self.assertEqual(run_output.checkpoint_name, "DexiNed_BIPED_10.pth")
        self.assertEqual(run_output.edge_prob.shape, (3, 5, 6))
        self.assertEqual(run_output.edge_binary.shape, (3, 5, 6))
        np.testing.assert_array_equal(run_output.edge_binary[0], run_output.edge_binary[1])
        self.assertTrue(np.any(run_output.edge_binary[0]))


class DexiNedWorkerSubprocessTests(unittest.TestCase):
    def test_worker_script_roundtrip_writes_expected_output(self) -> None:
        worker_script = Path("nanotrack/edges/run_dexined_subprocess.py").resolve()

        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            input_path = temp_path / "input.npz"
            output_path = temp_path / "output.npz"

            polygon_mask = np.zeros((6, 8), dtype=bool)
            polygon_mask[1:5, 2:7] = True
            run_input = DexiNedRunInput(
                frames=np.zeros((2, 6, 8), dtype=np.float32),
                polygon_mask=polygon_mask,
                threshold=0.4,
                source_view="bm3d",
            )
            np.savez_compressed(input_path, **run_input.to_npz_payload())

            completed = subprocess.run(
                [
                    sys.executable,
                    str(worker_script),
                    "--input-npz",
                    str(input_path),
                    "--output-npz",
                    str(output_path),
                    "--checkpoint",
                    "DexiNed_BIPED_10.pth",
                    "--device",
                    "cuda:0",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, msg=completed.stderr)
            self.assertTrue(output_path.exists())

            with np.load(output_path, allow_pickle=False) as payload:
                output_payload = {key: payload[key] for key in payload.files}
            run_output = DexiNedRunOutput.from_npz_payload(output_payload)

            self.assertEqual(run_output.model_name, "dexined_stub")
            self.assertEqual(run_output.checkpoint_name, "DexiNed_BIPED_10.pth")
            self.assertEqual(run_output.edge_prob.shape, (2, 6, 8))
            self.assertTrue(np.any(run_output.edge_binary))


if __name__ == "__main__":
    unittest.main()
