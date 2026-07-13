import sys
import textwrap
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from nanotrack.sam2 import (
    Sam2ImageBatchBackendConfig,
    Sam2ImageBatchBackendError,
    Sam2ImageBatchBackendTimeoutError,
    Sam2ImageBatchInput,
    Sam2ImageBatchSubprocessBackend,
)


def _write_worker_script(path: Path, source: str) -> None:
    path.write_text(textwrap.dedent(source), encoding="utf-8")


class Sam2ImageBatchSubprocessBackendTests(unittest.TestCase):
    def _make_input(self) -> Sam2ImageBatchInput:
        return Sam2ImageBatchInput(
            frame=np.arange(48, dtype=np.float32).reshape(6, 8),
            frame_index=7,
            source_view="raw",
            boxes_xyxy=np.asarray(
                ((1.0, 1.0, 4.0, 4.0), (4.0, 2.0, 7.0, 5.0)),
                dtype=np.float32,
            ),
            prompt_detection_ids=("bbox-alpha", "bbox-beta"),
            mask_probability_threshold=0.65,
            chunk_size=16,
        )

    def test_backend_runs_one_frame_worker_with_selected_checkpoint_and_contract(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            worker_script = temp_path / "fake_batch_worker.py"
            _write_worker_script(
                worker_script,
                """
                import argparse
                import numpy as np

                parser = argparse.ArgumentParser()
                parser.add_argument("--input-npz", required=True)
                parser.add_argument("--output-npz", required=True)
                parser.add_argument("--checkpoint", required=True)
                parser.add_argument("--repo-path", required=True)
                parser.add_argument("--config", required=True)
                parser.add_argument("--device", required=True)
                parser.add_argument("--apply-postprocessing", action="store_true")
                parser.add_argument("--disable-postprocessing", action="store_true")
                args = parser.parse_args()

                assert args.checkpoint == "selected-checkpoint.pt"
                assert args.repo_path == "sam2-repo"
                assert args.config == "configs/sam2.1/model.yaml"
                assert args.device == "cuda:0"
                assert args.apply_postprocessing
                assert not args.disable_postprocessing

                with np.load(args.input_npz, allow_pickle=False) as payload:
                    assert int(payload["frame_index"]) == 7
                    assert payload["source_view"].item() == "raw"
                    assert payload["boxes_xyxy"].shape == (2, 4)
                    assert payload["prompt_detection_ids"].tolist() == ["bbox-alpha", "bbox-beta"]
                    assert abs(float(payload["mask_probability_threshold"]) - 0.65) < 1e-6
                    assert int(payload["chunk_size"]) == 16
                    contract_version = payload["contract_version"].copy()
                    frame_index = payload["frame_index"].copy()
                    source_view = payload["source_view"].copy()
                    prompt_ids = payload["prompt_detection_ids"].copy()

                masks = np.zeros((2, 6, 8), dtype=np.uint8)
                masks[0, 1:3, 2:4] = 1
                masks[1, 3:5, 5:7] = 1
                np.savez_compressed(
                    args.output_npz,
                    contract_version=contract_version,
                    frame_index=frame_index,
                    source_view=source_view,
                    prompt_detection_ids=prompt_ids,
                    masks=masks,
                    mask_scores=np.asarray((0.9, 0.8), dtype=np.float32),
                    mask_bboxes_xyxy=np.asarray(
                        ((2.0, 1.0, 4.0, 3.0), (5.0, 3.0, 7.0, 5.0)),
                        dtype=np.float32,
                    ),
                    mask_component_counts=np.asarray((1, 1), dtype=np.int64),
                )
                """,
            )
            backend = Sam2ImageBatchSubprocessBackend(
                Sam2ImageBatchBackendConfig(
                    python_executable=sys.executable,
                    worker_script=worker_script,
                    checkpoint_path="selected-checkpoint.pt",
                    repo_path="sam2-repo",
                    config_path="configs/sam2.1/model.yaml",
                    device="cuda:0",
                    timeout_sec=5.0,
                    working_directory=temp_path,
                )
            )

            result = backend.run(self._make_input())

        self.assertEqual(result.prompt_detection_ids, ("bbox-alpha", "bbox-beta"))
        self.assertEqual(result.masks.shape, (2, 6, 8))
        np.testing.assert_array_equal(result.mask_component_counts, np.asarray((1, 1)))
        np.testing.assert_allclose(result.mask_scores, np.asarray((0.9, 0.8)))

    def test_backend_reports_worker_that_finishes_without_output_file(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            worker_script = temp_path / "no_output.py"
            _write_worker_script(worker_script, "pass")
            backend = Sam2ImageBatchSubprocessBackend(
                Sam2ImageBatchBackendConfig(
                    python_executable=sys.executable,
                    worker_script=worker_script,
                    checkpoint_path="checkpoint.pt",
                    repo_path=None,
                    timeout_sec=5.0,
                    working_directory=temp_path,
                )
            )

            with self.assertRaisesRegex(
                Sam2ImageBatchBackendError,
                "without creating output.npz",
            ):
                backend.run(self._make_input())

    def test_backend_reports_and_stops_worker_timeout(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            worker_script = temp_path / "slow_worker.py"
            _write_worker_script(
                worker_script,
                """
                import time
                time.sleep(1.0)
                """,
            )
            backend = Sam2ImageBatchSubprocessBackend(
                Sam2ImageBatchBackendConfig(
                    python_executable=sys.executable,
                    worker_script=worker_script,
                    checkpoint_path="checkpoint.pt",
                    repo_path=None,
                    timeout_sec=0.05,
                    working_directory=temp_path,
                )
            )

            with self.assertRaises(Sam2ImageBatchBackendTimeoutError) as context:
                backend.run(self._make_input())

        self.assertIn("timed out after 0.050 s", str(context.exception))
        self.assertIn("slow_worker.py", str(context.exception))

    def test_backend_preserves_nonzero_exit_code_and_worker_stderr(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            worker_script = temp_path / "failed_worker.py"
            _write_worker_script(
                worker_script,
                """
                import sys
                sys.stderr.write("checkpoint could not be loaded\\n")
                raise SystemExit(4)
                """,
            )
            backend = Sam2ImageBatchSubprocessBackend(
                Sam2ImageBatchBackendConfig(
                    python_executable=sys.executable,
                    worker_script=worker_script,
                    checkpoint_path="checkpoint.pt",
                    repo_path=None,
                    timeout_sec=5.0,
                    working_directory=temp_path,
                )
            )

            with self.assertRaises(Sam2ImageBatchBackendError) as context:
                backend.run(self._make_input())

        message = str(context.exception)
        self.assertIn("Exit code: 4", message)
        self.assertIn("checkpoint could not be loaded", message)

    def test_backend_rejects_output_with_prompt_ids_in_wrong_order(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            worker_script = temp_path / "wrong_order_worker.py"
            _write_worker_script(
                worker_script,
                """
                import argparse
                import numpy as np

                parser = argparse.ArgumentParser()
                parser.add_argument("--input-npz")
                parser.add_argument("--output-npz")
                parser.add_argument("--checkpoint")
                parser.add_argument("--device")
                parser.add_argument("--apply-postprocessing", action="store_true")
                parser.add_argument("--disable-postprocessing", action="store_true")
                args = parser.parse_args()
                np.savez_compressed(
                    args.output_npz,
                    contract_version=np.asarray(1, dtype=np.int64),
                    frame_index=np.asarray(7, dtype=np.int64),
                    source_view=np.asarray("raw"),
                    prompt_detection_ids=np.asarray(("bbox-beta", "bbox-alpha")),
                    masks=np.zeros((2, 6, 8), dtype=np.uint8),
                    mask_scores=np.zeros((2,), dtype=np.float32),
                    mask_bboxes_xyxy=np.zeros((2, 4), dtype=np.float32),
                    mask_component_counts=np.zeros((2,), dtype=np.int64),
                )
                """,
            )
            backend = Sam2ImageBatchSubprocessBackend(
                Sam2ImageBatchBackendConfig(
                    python_executable=sys.executable,
                    worker_script=worker_script,
                    checkpoint_path="checkpoint.pt",
                    repo_path=None,
                    timeout_sec=5.0,
                    working_directory=temp_path,
                )
            )

            with self.assertRaisesRegex(
                Sam2ImageBatchBackendError,
                "prompt ID order",
            ):
                backend.run(self._make_input())


if __name__ == "__main__":
    unittest.main()
