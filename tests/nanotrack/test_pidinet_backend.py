import sys
import textwrap
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from nanotrack.edges import (
    DexiNedRunInput,
    PidinetBackendConfig,
    PidinetBackendError,
    PidinetBackendTimeoutError,
    PidinetSubprocessBackend,
)


def _write_worker_script(path: Path, body: str) -> None:
    path.write_text(textwrap.dedent(body), encoding="utf-8")


class PidinetSubprocessBackendTests(unittest.TestCase):
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
        config = PidinetBackendConfig()

        self.assertEqual(str(config.python_executable), r"C:\Users\rlewa\anaconda3\envs\pidinet_gpu\python.exe")
        self.assertEqual(str(config.repo_path), r"C:\Users\rlewa\Documents\PROJEKTY\PiDiNet")
        self.assertEqual(
            str(config.checkpoint_path),
            r"C:\Users\rlewa\Documents\PROJEKTY\PiDiNet\trained_models\table5_pidinet.pth",
        )
        self.assertEqual(Path(config.worker_script).name, "run_pidinet_subprocess.py")
        self.assertEqual(config.model_name, "pidinet_converted")
        self.assertEqual(config.model_config, "carv4")
        self.assertTrue(config.use_sa)
        self.assertTrue(config.use_dil)
        self.assertTrue(config.evaluate_converted)
        self.assertEqual(config.device, "auto")

    def test_build_command_omits_optional_pidinet_flags_when_disabled(self) -> None:
        backend = PidinetSubprocessBackend(
            PidinetBackendConfig(
                python_executable="python.exe",
                worker_script="run_pidinet_subprocess.py",
                checkpoint_path="pidinet_checkpoint.pth",
                repo_path=None,
                model_name="pidinet_small_converted",
                model_config="carv4",
                use_sa=False,
                use_dil=False,
                evaluate_converted=False,
                device="cpu",
            )
        )

        command = backend._build_command(Path("input.npz"), Path("output.npz"))

        self.assertIn("--model", command)
        self.assertIn("pidinet_small_converted", command)
        self.assertIn("--model-config", command)
        self.assertIn("carv4", command)
        self.assertIn("--device", command)
        self.assertIn("cpu", command)
        self.assertNotIn("--sa", command)
        self.assertNotIn("--dil", command)
        self.assertNotIn("--evaluate-converted", command)
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
                parser.add_argument("--model", required=True)
                parser.add_argument("--model-config", required=True)
                parser.add_argument("--sa", action="store_true")
                parser.add_argument("--dil", action="store_true")
                parser.add_argument("--evaluate-converted", action="store_true")
                parser.add_argument("--repo-path", default=None)
                parser.add_argument("--device", default=None)
                args = parser.parse_args()

                assert args.checkpoint == "pidinet_checkpoint.pth"
                assert args.model == "pidinet_converted"
                assert args.model_config == "carv4"
                assert args.sa
                assert args.dil
                assert args.evaluate_converted
                assert args.repo_path == "pidinet-repo"
                assert args.device == "cuda:0"

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
                    model_name=np.asarray("pidinet"),
                    checkpoint_name=np.asarray("table5_pidinet.pth"),
                )
                """,
            )

            backend = PidinetSubprocessBackend(
                PidinetBackendConfig(
                    python_executable=sys.executable,
                    worker_script=worker_script,
                    checkpoint_path="pidinet_checkpoint.pth",
                    repo_path="pidinet-repo",
                    model_name="pidinet_converted",
                    model_config="carv4",
                    use_sa=True,
                    use_dil=True,
                    evaluate_converted=True,
                    device="cuda:0",
                    timeout_sec=5.0,
                    working_directory=temp_path,
                )
            )

            result = backend.run(self._make_run_input())

            self.assertEqual(result.model_name, "pidinet")
            self.assertEqual(result.checkpoint_name, "table5_pidinet.pth")
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
                sys.stderr.write("pidinet exploded\\n")
                raise SystemExit(4)
                """,
            )

            backend = PidinetSubprocessBackend(
                PidinetBackendConfig(
                    python_executable=sys.executable,
                    worker_script=worker_script,
                    checkpoint_path="pidinet_checkpoint.pth",
                    repo_path=None,
                    timeout_sec=5.0,
                    working_directory=temp_path,
                )
            )

            with self.assertRaises(PidinetBackendError) as exc_info:
                backend.run(self._make_run_input())

            self.assertIn("Exit code: 4", str(exc_info.exception))
            self.assertIn("pidinet exploded", str(exc_info.exception))

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
                parser.add_argument("--model", required=True)
                parser.add_argument("--model-config", required=True)
                parser.add_argument("--sa", action="store_true")
                parser.add_argument("--dil", action="store_true")
                parser.add_argument("--evaluate-converted", action="store_true")
                parser.add_argument("--repo-path", default=None)
                parser.add_argument("--device", default=None)
                parser.parse_args()
                """,
            )

            backend = PidinetSubprocessBackend(
                PidinetBackendConfig(
                    python_executable=sys.executable,
                    worker_script=worker_script,
                    checkpoint_path="pidinet_checkpoint.pth",
                    repo_path=None,
                    timeout_sec=5.0,
                    working_directory=temp_path,
                )
            )

            with self.assertRaises(PidinetBackendError) as exc_info:
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
                parser.add_argument("--model", required=True)
                parser.add_argument("--model-config", required=True)
                parser.add_argument("--sa", action="store_true")
                parser.add_argument("--dil", action="store_true")
                parser.add_argument("--evaluate-converted", action="store_true")
                parser.add_argument("--repo-path", default=None)
                parser.add_argument("--device", default=None)
                parser.parse_args()
                time.sleep(1.0)
                """,
            )

            backend = PidinetSubprocessBackend(
                PidinetBackendConfig(
                    python_executable=sys.executable,
                    worker_script=worker_script,
                    checkpoint_path="pidinet_checkpoint.pth",
                    repo_path=None,
                    timeout_sec=0.1,
                    working_directory=temp_path,
                )
            )

            with self.assertRaises(PidinetBackendTimeoutError) as exc_info:
                backend.run(self._make_run_input())

            self.assertIn("timed out", str(exc_info.exception))

    def test_backend_config_validates_timeout(self) -> None:
        with self.assertRaises(ValueError):
            PidinetBackendConfig(timeout_sec=0.0)


if __name__ == "__main__":
    unittest.main()
