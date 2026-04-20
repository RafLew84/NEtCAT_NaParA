import sys
import subprocess
import textwrap
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from nanotrack.sam2 import (
    SAM2_CONTRACT_VERSION,
    Sam2BackendConfig,
    Sam2BackendError,
    Sam2BackendTimeoutError,
    Sam2RunInput,
    Sam2SubprocessBackend,
)


def _write_worker_script(path: Path, body: str) -> None:
    path.write_text(textwrap.dedent(body), encoding="utf-8")


class Sam2SubprocessBackendTests(unittest.TestCase):
    def _make_run_input(self) -> Sam2RunInput:
        return Sam2RunInput(
            track_id=5,
            frame_index_offset=7,
            frames=np.zeros((3, 6, 8), dtype=np.float32),
            query_box_xyxy=np.asarray([1.0, 2.0, 5.0, 4.0], dtype=np.float32),
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
                parser.add_argument("--checkpoint", required=True)
                parser.add_argument("--repo-path", default=None)
                parser.add_argument("--config", default=None)
                parser.add_argument("--device", default=None)
                parser.add_argument("--apply-postprocessing", dest="apply_postprocessing", action="store_true")
                parser.add_argument("--disable-postprocessing", dest="apply_postprocessing", action="store_false")
                parser.set_defaults(apply_postprocessing=True)
                parser.add_argument("--offload-video-to-cpu", action="store_true")
                parser.add_argument("--offload-state-to-cpu", action="store_true")
                parser.add_argument("--async-loading-frames", action="store_true")
                args = parser.parse_args()

                assert args.checkpoint == "checkpoint.pt"
                assert args.repo_path == "repo-dir"
                assert args.config == "config.yaml"
                assert args.device == "cuda:0"
                assert args.apply_postprocessing is True
                assert args.offload_video_to_cpu is True
                assert args.offload_state_to_cpu is False
                assert args.async_loading_frames is False

                with np.load(args.input_npz, allow_pickle=False) as payload:
                    frames = payload["frames"]
                    track_id = int(payload["track_id"])
                    frame_index_offset = int(payload["frame_index_offset"])
                    assert payload["source_view"].item() == "repair+bm3d"
                    assert payload["query_box_xyxy"].shape == (4,)

                masks = np.zeros((frames.shape[0], frames.shape[1], frames.shape[2]), dtype=np.uint8)
                masks[:, 1:3, 2:4] = 1
                visible_mask = np.asarray([1, 1, 0], dtype=np.uint8)
                mask_scores = np.asarray([0.9, 0.8, 0.2], dtype=np.float32)
                np.savez_compressed(
                    args.output_npz,
                    contract_version=np.asarray(1, dtype=np.int64),
                    track_id=np.asarray(track_id, dtype=np.int64),
                    frame_index_offset=np.asarray(frame_index_offset, dtype=np.int64),
                    masks=masks,
                    visible_mask=visible_mask,
                    mask_scores=mask_scores,
                )
                """,
            )

            backend = Sam2SubprocessBackend(
                Sam2BackendConfig(
                    python_executable=sys.executable,
                    worker_script=worker_script,
                    checkpoint_path="checkpoint.pt",
                    repo_path="repo-dir",
                    config_path="config.yaml",
                    device="cuda:0",
                    timeout_sec=5.0,
                    working_directory=temp_path,
                )
            )

            result = backend.run(self._make_run_input())

            self.assertEqual(result.track_id, 5)
            self.assertEqual(result.frame_index_offset, 7)
            self.assertEqual(result.masks.shape, (3, 6, 8))
            np.testing.assert_array_equal(result.visible_mask, np.asarray([True, True, False]))
            np.testing.assert_array_equal(result.mask_scores, np.asarray([0.9, 0.8, 0.2], dtype=np.float32))

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

            backend = Sam2SubprocessBackend(
                Sam2BackendConfig(
                    python_executable=sys.executable,
                    worker_script=worker_script,
                    checkpoint_path="checkpoint.pt",
                    repo_path=None,
                    timeout_sec=5.0,
                    working_directory=temp_path,
                )
            )

            with self.assertRaises(Sam2BackendError) as exc_info:
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
                parser.add_argument("--checkpoint", required=True)
                parser.add_argument("--repo-path", default=None)
                parser.add_argument("--config", default=None)
                parser.add_argument("--device", default=None)
                parser.add_argument("--apply-postprocessing", dest="apply_postprocessing", action="store_true")
                parser.add_argument("--disable-postprocessing", dest="apply_postprocessing", action="store_false")
                parser.set_defaults(apply_postprocessing=True)
                parser.add_argument("--offload-video-to-cpu", action="store_true")
                parser.add_argument("--offload-state-to-cpu", action="store_true")
                parser.add_argument("--async-loading-frames", action="store_true")
                parser.parse_args()
                """,
            )

            backend = Sam2SubprocessBackend(
                Sam2BackendConfig(
                    python_executable=sys.executable,
                    worker_script=worker_script,
                    checkpoint_path="checkpoint.pt",
                    repo_path=None,
                    timeout_sec=5.0,
                    working_directory=temp_path,
                )
            )

            with self.assertRaises(Sam2BackendError) as exc_info:
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
                parser.add_argument("--config", default=None)
                parser.add_argument("--device", default=None)
                parser.add_argument("--apply-postprocessing", dest="apply_postprocessing", action="store_true")
                parser.add_argument("--disable-postprocessing", dest="apply_postprocessing", action="store_false")
                parser.set_defaults(apply_postprocessing=True)
                parser.add_argument("--offload-video-to-cpu", action="store_true")
                parser.add_argument("--offload-state-to-cpu", action="store_true")
                parser.add_argument("--async-loading-frames", action="store_true")
                parser.parse_args()
                time.sleep(1.0)
                """,
            )

            backend = Sam2SubprocessBackend(
                Sam2BackendConfig(
                    python_executable=sys.executable,
                    worker_script=worker_script,
                    checkpoint_path="checkpoint.pt",
                    repo_path=None,
                    timeout_sec=0.1,
                    working_directory=temp_path,
                )
            )

            with self.assertRaises(Sam2BackendTimeoutError) as exc_info:
                backend.run(self._make_run_input())

            self.assertIn("timed out", str(exc_info.exception))

    def test_backend_config_validates_timeout(self) -> None:
        with self.assertRaises(ValueError):
            Sam2BackendConfig(timeout_sec=0.0)

    def test_backend_formats_windows_native_crash_hint(self) -> None:
        backend = Sam2SubprocessBackend(
            Sam2BackendConfig(
                python_executable=sys.executable,
                worker_script="worker.py",
                checkpoint_path="checkpoint.pt",
            )
        )

        message = backend._format_subprocess_error(
            ["python", "worker.py"],
            completed=subprocess.CompletedProcess(
                args=["python", "worker.py"],
                returncode=3221226505,
                stdout="",
                stderr="",
            ),
        )

        self.assertIn("0xC0000409", message)
        self.assertIn("memory-pressure", message)


if __name__ == "__main__":
    unittest.main()
