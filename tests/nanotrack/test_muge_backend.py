import sys
import textwrap
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from nanotrack.edges import (
    DexiNedRunInput,
    MugeBackendConfig,
    MugeBackendError,
    MugeBackendTimeoutError,
    MugeSubprocessBackend,
)


def _write_worker_script(path: Path, body: str) -> None:
    path.write_text(textwrap.dedent(body), encoding="utf-8")


class MugeSubprocessBackendTests(unittest.TestCase):
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
        config = MugeBackendConfig()

        self.assertEqual(str(config.python_executable), r"C:\Users\rlewa\anaconda3\envs\uaed_gpu\python.exe")
        self.assertEqual(str(config.repo_path), r"C:\Users\rlewa\Documents\PROJEKTY\UAED_MuGE")
        self.assertEqual(
            str(config.checkpoint_path),
            r"C:\Users\rlewa\Documents\PROJEKTY\UAED_MuGE\checkpoints\MuGE\muge-epoch-19-checkpoint.pth",
        )
        self.assertEqual(Path(config.worker_script).name, "run_muge_subprocess.py")
        self.assertEqual(config.distribution, "gs")
        self.assertEqual(config.device, "auto")
        self.assertEqual(config.granularity, 0.5)

    def test_build_command_includes_granularity_and_omits_repo_path_when_disabled(self) -> None:
        backend = MugeSubprocessBackend(
            MugeBackendConfig(
                python_executable="python.exe",
                worker_script="run_muge_subprocess.py",
                checkpoint_path="muge_checkpoint.pth",
                repo_path=None,
                distribution="beta",
                device="cpu",
                granularity=0.75,
            )
        )

        command = backend._build_command(Path("input.npz"), Path("output.npz"))

        self.assertIn("--distribution", command)
        self.assertIn("beta", command)
        self.assertIn("--device", command)
        self.assertIn("cpu", command)
        self.assertIn("--granularity", command)
        self.assertIn("0.75", command)
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
                parser.add_argument("--granularity", required=True)
                args = parser.parse_args()

                assert args.checkpoint == "muge_checkpoint.pth"
                assert args.repo_path == "uaed-muge-repo"
                assert args.device == "cuda:0"
                assert args.distribution == "gs"
                assert abs(float(args.granularity) - 0.75) < 1e-9

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
                    model_name=np.asarray("muge"),
                    checkpoint_name=np.asarray("muge-epoch-19-checkpoint.pth"),
                )
                """,
            )

            backend = MugeSubprocessBackend(
                MugeBackendConfig(
                    python_executable=sys.executable,
                    worker_script=worker_script,
                    checkpoint_path="muge_checkpoint.pth",
                    repo_path="uaed-muge-repo",
                    distribution="gs",
                    device="cuda:0",
                    granularity=0.75,
                    timeout_sec=5.0,
                    working_directory=temp_path,
                )
            )

            result = backend.run(self._make_run_input())

            self.assertEqual(result.model_name, "muge")
            self.assertEqual(result.checkpoint_name, "muge-epoch-19-checkpoint.pth")
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
                sys.stderr.write("muge exploded\\n")
                raise SystemExit(4)
                """,
            )

            backend = MugeSubprocessBackend(
                MugeBackendConfig(
                    python_executable=sys.executable,
                    worker_script=worker_script,
                    checkpoint_path="muge_checkpoint.pth",
                    repo_path=None,
                    timeout_sec=5.0,
                    working_directory=temp_path,
                )
            )

            with self.assertRaises(MugeBackendError) as exc_info:
                backend.run(self._make_run_input())

            self.assertIn("Exit code: 4", str(exc_info.exception))
            self.assertIn("muge exploded", str(exc_info.exception))

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
                parser.add_argument("--granularity", required=True)
                parser.parse_args()
                """,
            )

            backend = MugeSubprocessBackend(
                MugeBackendConfig(
                    python_executable=sys.executable,
                    worker_script=worker_script,
                    checkpoint_path="muge_checkpoint.pth",
                    repo_path=None,
                    timeout_sec=5.0,
                    working_directory=temp_path,
                )
            )

            with self.assertRaises(MugeBackendError) as exc_info:
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
                parser.add_argument("--granularity", required=True)
                parser.parse_args()
                time.sleep(1.0)
                """,
            )

            backend = MugeSubprocessBackend(
                MugeBackendConfig(
                    python_executable=sys.executable,
                    worker_script=worker_script,
                    checkpoint_path="muge_checkpoint.pth",
                    repo_path=None,
                    timeout_sec=0.1,
                    working_directory=temp_path,
                )
            )

            with self.assertRaises(MugeBackendTimeoutError) as exc_info:
                backend.run(self._make_run_input())

            self.assertIn("timed out", str(exc_info.exception))

    def test_backend_config_validates_timeout_distribution_and_granularity(self) -> None:
        with self.assertRaises(ValueError):
            MugeBackendConfig(timeout_sec=0.0)
        with self.assertRaises(ValueError):
            MugeBackendConfig(distribution=" ")
        with self.assertRaises(ValueError):
            MugeBackendConfig(granularity=-0.01)
        with self.assertRaises(ValueError):
            MugeBackendConfig(granularity=1.01)

    def test_real_backend_smoke_when_local_runtime_available(self) -> None:
        config = MugeBackendConfig(timeout_sec=180.0, granularity=0.5)
        required_paths = [
            Path(config.python_executable),
            Path(config.worker_script),
            Path(config.checkpoint_path),
        ]
        if config.repo_path is not None:
            required_paths.append(Path(config.repo_path))
        missing_paths = [str(path) for path in required_paths if not path.exists()]
        if missing_paths:
            self.skipTest("Local MuGE runtime is unavailable: " + ", ".join(missing_paths))

        size = 64
        y, x = np.mgrid[0:size, 0:size]
        frame = np.full((size, size), 0.1, dtype=np.float32)
        frame[y > (25 + 5 * np.sin(x / 8.0))] = 0.9
        frame = np.clip(frame + 0.03 * np.cos(y / 5.0), 0.0, 1.0).astype(np.float32)
        polygon_mask = np.zeros((size, size), dtype=bool)
        polygon_mask[8:56, 8:56] = True
        run_input = DexiNedRunInput(
            frames=frame[None, ...],
            polygon_mask=polygon_mask,
            inference_resolution_hw=np.asarray([64, 64], dtype=np.int32),
            threshold=0.5,
            source_view="real-smoke",
        )

        output = MugeSubprocessBackend(config).run(run_input)

        self.assertEqual(output.model_name, "muge")
        self.assertEqual(output.checkpoint_name, "muge-epoch-19-checkpoint.pth")
        self.assertEqual(output.edge_prob.shape, (1, size, size))
        self.assertEqual(output.edge_prob.dtype, np.float32)
        self.assertIsNotNone(output.edge_binary)
        self.assertGreater(float(output.edge_prob.max()), 0.0)
        self.assertLessEqual(float(output.edge_prob.max()), 1.0)
        self.assertGreater(int(np.count_nonzero(output.edge_prob > 1e-6)), 0)
        self.assertEqual(int(np.count_nonzero(output.edge_prob[:, ~polygon_mask])), 0)


if __name__ == "__main__":
    unittest.main()
