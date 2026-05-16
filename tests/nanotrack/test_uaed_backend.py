import sys
import textwrap
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from nanotrack.edges import (
    DexiNedRunInput,
    UaedBackendConfig,
    UaedBackendError,
    UaedBackendTimeoutError,
    UaedSubprocessBackend,
)


def _write_worker_script(path: Path, body: str) -> None:
    path.write_text(textwrap.dedent(body), encoding="utf-8")


class UaedSubprocessBackendTests(unittest.TestCase):
    def _make_run_input(self) -> DexiNedRunInput:
        polygon_mask = np.zeros((6, 8), dtype=bool)
        polygon_mask[1:5, 2:7] = True
        return DexiNedRunInput(
            frames=np.zeros((3, 6, 8), dtype=np.float32),
            polygon_mask=polygon_mask,
            frame_indices=np.asarray([4, 5, 6], dtype=np.int32),
            inference_resolution_hw=np.asarray([256, 256], dtype=np.int32),
            device="cuda:0",
            threshold=0.35,
            source_view="repair+bm3d",
        )

    def test_default_config_matches_frozen_runtime_contract(self) -> None:
        config = UaedBackendConfig()

        self.assertEqual(str(config.python_executable), r"C:\Users\rlewa\anaconda3\envs\uaed_gpu\python.exe")
        self.assertEqual(str(config.repo_path), r"C:\Users\rlewa\Documents\PROJEKTY\UAED_MuGE")
        self.assertEqual(
            str(config.checkpoint_path),
            r"C:\Users\rlewa\Documents\PROJEKTY\UAED_MuGE\checkpoints\UAED\epoch-19-checkpoint.pth",
        )
        self.assertEqual(Path(config.worker_script).name, "run_uaed_subprocess.py")
        self.assertEqual(config.distribution, "gs")
        self.assertEqual(config.device, "auto")

    def test_build_command_omits_repo_path_when_disabled(self) -> None:
        backend = UaedSubprocessBackend(
            UaedBackendConfig(
                python_executable="python.exe",
                worker_script="run_uaed_subprocess.py",
                checkpoint_path="uaed_checkpoint.pth",
                repo_path=None,
                distribution="beta",
                device="cpu",
            )
        )

        command = backend._build_command(Path("input.npz"), Path("output.npz"))

        self.assertIn("--distribution", command)
        self.assertIn("beta", command)
        self.assertIn("--device", command)
        self.assertIn("cpu", command)
        self.assertNotIn("--repo-path", command)

    def test_backend_roundtrip_executes_worker_and_parses_output(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            worker_script = temp_path / "worker_success.py"
            _write_worker_script(
                worker_script,
                """
                import argparse
                import numpy as np

                parser = argparse.ArgumentParser()
                parser.add_argument("--input-npz", required=True)
                parser.add_argument("--output-npz", required=True)
                parser.add_argument("--checkpoint", required=True)
                parser.add_argument("--repo-path", default=None)
                parser.add_argument("--device", default=None)
                parser.add_argument("--distribution", required=True)
                args = parser.parse_args()

                assert args.checkpoint == "uaed_checkpoint.pth"
                assert args.repo_path == "uaed-repo"
                assert args.device == "cuda:0"
                assert args.distribution == "gs"

                with np.load(args.input_npz, allow_pickle=False) as payload:
                    frames = payload["frames"]
                    polygon_mask = payload["polygon_mask"]
                    frame_indices = payload["frame_indices"]
                    threshold = float(payload["threshold"])
                    assert payload["source_view"].item() == "repair+bm3d"
                    assert payload["device"].item() == "cuda:0"
                    assert payload["inference_resolution_hw"].tolist() == [256, 256]
                    assert polygon_mask.shape == (6, 8)
                    assert frame_indices.tolist() == [4, 5, 6]
                    assert abs(threshold - 0.35) < 1e-6

                edge_prob = np.zeros((frames.shape[0], frames.shape[1], frames.shape[2]), dtype=np.float32)
                edge_prob[:, 2:4, 3:5] = 0.8
                edge_binary = edge_prob > 0.5
                np.savez_compressed(
                    args.output_npz,
                    contract_version=np.asarray(1, dtype=np.int64),
                    edge_prob=edge_prob,
                    edge_binary=edge_binary.astype(np.uint8),
                    model_name=np.asarray("uaed"),
                    checkpoint_name=np.asarray("epoch-19-checkpoint.pth"),
                )
                """,
            )

            backend = UaedSubprocessBackend(
                UaedBackendConfig(
                    python_executable=sys.executable,
                    worker_script=worker_script,
                    checkpoint_path="uaed_checkpoint.pth",
                    repo_path="uaed-repo",
                    distribution="gs",
                    device="cuda:0",
                    timeout_sec=5.0,
                    working_directory=temp_path,
                )
            )

            result = backend.run(self._make_run_input())

            self.assertEqual(result.model_name, "uaed")
            self.assertEqual(result.checkpoint_name, "epoch-19-checkpoint.pth")
            self.assertEqual(result.edge_prob.shape, (3, 6, 8))
            np.testing.assert_array_equal(result.edge_binary, result.edge_prob > 0.5)

    def test_backend_raises_on_nonzero_worker_exit(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            worker_script = temp_path / "worker_fail.py"
            _write_worker_script(
                worker_script,
                """
                import sys
                sys.stderr.write("uaed exploded\\n")
                raise SystemExit(4)
                """,
            )

            backend = UaedSubprocessBackend(
                UaedBackendConfig(
                    python_executable=sys.executable,
                    worker_script=worker_script,
                    checkpoint_path="uaed_checkpoint.pth",
                    repo_path=None,
                    timeout_sec=5.0,
                    working_directory=temp_path,
                )
            )

            with self.assertRaises(UaedBackendError) as exc_info:
                backend.run(self._make_run_input())

            self.assertIn("Exit code: 4", str(exc_info.exception))
            self.assertIn("uaed exploded", str(exc_info.exception))

    def test_backend_raises_if_worker_finishes_without_output_npz(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            worker_script = temp_path / "worker_no_output.py"
            _write_worker_script(
                worker_script,
                """
                import argparse

                parser = argparse.ArgumentParser()
                parser.add_argument("--input-npz", required=True)
                parser.add_argument("--output-npz", required=True)
                parser.add_argument("--checkpoint", required=True)
                parser.add_argument("--repo-path", default=None)
                parser.add_argument("--device", default=None)
                parser.add_argument("--distribution", required=True)
                parser.parse_args()
                """,
            )

            backend = UaedSubprocessBackend(
                UaedBackendConfig(
                    python_executable=sys.executable,
                    worker_script=worker_script,
                    checkpoint_path="uaed_checkpoint.pth",
                    repo_path=None,
                    timeout_sec=5.0,
                    working_directory=temp_path,
                )
            )

            with self.assertRaises(UaedBackendError) as exc_info:
                backend.run(self._make_run_input())

            self.assertIn("without creating output.npz", str(exc_info.exception))

    def test_backend_raises_timeout_error(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            worker_script = temp_path / "worker_sleep.py"
            _write_worker_script(
                worker_script,
                """
                import argparse
                import time

                parser = argparse.ArgumentParser()
                parser.add_argument("--input-npz", required=True)
                parser.add_argument("--output-npz", required=True)
                parser.add_argument("--checkpoint", required=True)
                parser.add_argument("--repo-path", default=None)
                parser.add_argument("--device", default=None)
                parser.add_argument("--distribution", required=True)
                parser.parse_args()
                time.sleep(1.0)
                """,
            )

            backend = UaedSubprocessBackend(
                UaedBackendConfig(
                    python_executable=sys.executable,
                    worker_script=worker_script,
                    checkpoint_path="uaed_checkpoint.pth",
                    repo_path=None,
                    timeout_sec=0.1,
                    working_directory=temp_path,
                )
            )

            with self.assertRaises(UaedBackendTimeoutError) as exc_info:
                backend.run(self._make_run_input())

            self.assertIn("timed out", str(exc_info.exception))

    def test_backend_config_validates_timeout_and_distribution(self) -> None:
        with self.assertRaises(ValueError):
            UaedBackendConfig(timeout_sec=0.0)
        with self.assertRaises(ValueError):
            UaedBackendConfig(distribution=" ")


if __name__ == "__main__":
    unittest.main()
