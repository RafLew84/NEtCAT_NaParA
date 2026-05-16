import sys
import textwrap
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from nanotrack.trackers import (
    PointTrackerBackendConfig,
    PointTrackerBackendError,
    PointTrackerBackendTimeoutError,
    PointTrackerRunInput,
    PointTrackerSubprocessBackend,
)


def _write_worker_script(path: Path, body: str) -> None:
    path.write_text(textwrap.dedent(body), encoding="utf-8")


class PointTrackerSubprocessBackendTests(unittest.TestCase):
    def _make_run_input(self) -> PointTrackerRunInput:
        return PointTrackerRunInput(
            frames=np.zeros((4, 6, 8), dtype=np.float32),
            query_points_tyx=np.asarray([[0.0, 2.0, 3.0], [1.0, 4.0, 5.0]], dtype=np.float32),
            inference_resolution_hw=np.asarray([256, 256], dtype=np.int32),
            device="cuda:0",
            query_chunk_size=8,
            causal=True,
            window_size=12,
            window_overlap=4,
            source_view="repair+bm3d",
        )

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
                parser.add_argument("--model-name", required=True)
                parser.add_argument("--device", default=None)
                parser.add_argument("--repo-path", default=None)
                parser.add_argument("--checkpoint", default=None)
                args = parser.parse_args()

                assert args.model_name == "tapir"
                assert args.device == "cuda:0"
                assert args.repo_path == "repo-dir"
                assert args.checkpoint == "checkpoint.pt"

                with np.load(args.input_npz, allow_pickle=False) as payload:
                    frames = payload["frames"]
                    query_points_tyx = payload["query_points_tyx"]
                    inference_resolution_hw = payload["inference_resolution_hw"]
                    query_chunk_size = int(payload["query_chunk_size"])
                    causal = bool(payload["causal"])
                    window_size = int(payload["window_size"])
                    window_overlap = int(payload["window_overlap"])
                    assert payload["source_view"].item() == "repair+bm3d"
                    assert payload["device"].item() == "cuda:0"
                    assert query_points_tyx.shape == (2, 3)
                    assert inference_resolution_hw.tolist() == [256, 256]
                    assert query_chunk_size == 8
                    assert causal is True
                    assert window_size == 12
                    assert window_overlap == 4

                tracks_xy = np.zeros((query_points_tyx.shape[0], frames.shape[0], 2), dtype=np.float32)
                tracks_xy[0, :, 0] = [1.0, 2.0, 3.0, 4.0]
                tracks_xy[0, :, 1] = [5.0, 5.5, 6.0, 6.5]
                tracks_xy[1, :, 0] = [2.0, 2.5, 3.0, 3.5]
                tracks_xy[1, :, 1] = [4.0, 4.5, 5.0, 5.5]
                visible_mask = np.asarray([[1, 1, 1, 0], [1, 1, 0, 0]], dtype=np.uint8)
                confidence_scores = np.asarray([[0.9, 0.8, 0.7, 0.1], [0.95, 0.85, 0.3, 0.2]], dtype=np.float32)
                np.savez_compressed(
                    args.output_npz,
                    contract_version=np.asarray(1, dtype=np.int64),
                    tracks_xy=tracks_xy,
                    visible_mask=visible_mask,
                    confidence_scores=confidence_scores,
                    model_name=np.asarray("tapir"),
                    checkpoint_name=np.asarray("checkpoint.pt"),
                )
                """,
            )

            backend = PointTrackerSubprocessBackend(
                PointTrackerBackendConfig(
                    model_name="tapir",
                    python_executable=sys.executable,
                    worker_script=worker_script,
                    checkpoint_path="checkpoint.pt",
                    repo_path="repo-dir",
                    device="cuda:0",
                    timeout_sec=5.0,
                    working_directory=temp_path,
                )
            )

            result = backend.run(self._make_run_input())

            self.assertEqual(result.model_name, "tapir")
            self.assertEqual(result.checkpoint_name, "checkpoint.pt")
            self.assertEqual(result.tracks_xy.shape, (2, 4, 2))
            np.testing.assert_array_equal(result.visible_mask, np.asarray([[True, True, True, False], [True, True, False, False]]))
            np.testing.assert_array_equal(
                result.confidence_scores,
                np.asarray([[0.9, 0.8, 0.7, 0.1], [0.95, 0.85, 0.3, 0.2]], dtype=np.float32),
            )

    def test_backend_raises_on_nonzero_worker_exit(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            worker_script = temp_path / "worker_fail.py"
            _write_worker_script(
                worker_script,
                """
                import sys
                sys.stderr.write("worker exploded\\n")
                raise SystemExit(4)
                """,
            )

            backend = PointTrackerSubprocessBackend(
                PointTrackerBackendConfig(
                    model_name="tapir",
                    python_executable=sys.executable,
                    worker_script=worker_script,
                    timeout_sec=5.0,
                    working_directory=temp_path,
                )
            )

            with self.assertRaises(PointTrackerBackendError) as exc_info:
                backend.run(self._make_run_input())

            self.assertIn("Exit code: 4", str(exc_info.exception))
            self.assertIn("worker exploded", str(exc_info.exception))

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
                parser.add_argument("--model-name", required=True)
                parser.add_argument("--device", default=None)
                parser.add_argument("--repo-path", default=None)
                parser.add_argument("--checkpoint", default=None)
                parser.parse_args()
                """,
            )

            backend = PointTrackerSubprocessBackend(
                PointTrackerBackendConfig(
                    model_name="tapir",
                    python_executable=sys.executable,
                    worker_script=worker_script,
                    timeout_sec=5.0,
                    working_directory=temp_path,
                )
            )

            with self.assertRaises(PointTrackerBackendError) as exc_info:
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
                parser.add_argument("--model-name", required=True)
                parser.add_argument("--device", default=None)
                parser.add_argument("--repo-path", default=None)
                parser.add_argument("--checkpoint", default=None)
                parser.parse_args()
                time.sleep(1.0)
                """,
            )

            backend = PointTrackerSubprocessBackend(
                PointTrackerBackendConfig(
                    model_name="tapir",
                    python_executable=sys.executable,
                    worker_script=worker_script,
                    timeout_sec=0.1,
                    working_directory=temp_path,
                )
            )

            with self.assertRaises(PointTrackerBackendTimeoutError) as exc_info:
                backend.run(self._make_run_input())

            self.assertIn("timed out", str(exc_info.exception))

    def test_backend_config_validates_timeout(self) -> None:
        with self.assertRaises(ValueError):
            PointTrackerBackendConfig(
                model_name="tapir",
                python_executable=sys.executable,
                worker_script="worker.py",
                timeout_sec=0.0,
            )


if __name__ == "__main__":
    unittest.main()
