import sys
import textwrap
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from nanotrack.mask_trackers import (
    MaskTrackerBackendConfig,
    MaskTrackerKind,
    MaskTrackerRunInput,
    Sam2MaskTrackerBackend,
    sam2_backend_config_from_mask_config,
    sam2_run_input_from_mask_input,
)


def _write_worker_script(path: Path, body: str) -> None:
    path.write_text(textwrap.dedent(body), encoding="utf-8")


class Sam2MaskTrackerAdapterTests(unittest.TestCase):
    def _make_mask_input(self) -> MaskTrackerRunInput:
        return MaskTrackerRunInput(
            tracker_kind=MaskTrackerKind.SAM2,
            track_id=5,
            frame_index_offset=7,
            frames=np.zeros((3, 6, 8), dtype=np.float32),
            query_box_xyxy=np.asarray([1.0, 2.0, 5.0, 4.0], dtype=np.float32),
            source_view="repair+bm3d",
        )

    def test_sam2_input_conversion_preserves_existing_contract_fields(self) -> None:
        run_input = self._make_mask_input()

        sam2_input = sam2_run_input_from_mask_input(run_input)

        self.assertEqual(sam2_input.track_id, 5)
        self.assertEqual(sam2_input.frame_index_offset, 7)
        self.assertEqual(sam2_input.source_view, "repair+bm3d")
        np.testing.assert_array_equal(sam2_input.frames, run_input.frames)
        np.testing.assert_array_equal(sam2_input.query_box_xyxy, run_input.query_box_xyxy)

    def test_sam2_input_conversion_rejects_other_tracker_kind(self) -> None:
        run_input = MaskTrackerRunInput(
            tracker_kind=MaskTrackerKind.DAM4SAM,
            track_id=5,
            frame_index_offset=7,
            frames=np.zeros((3, 6, 8), dtype=np.float32),
            query_box_xyxy=np.asarray([1.0, 2.0, 5.0, 4.0], dtype=np.float32),
        )

        with self.assertRaises(ValueError):
            sam2_run_input_from_mask_input(run_input)

    def test_shared_config_maps_to_existing_sam2_backend_config(self) -> None:
        shared_config = MaskTrackerBackendConfig(
            kind="sam2",
            python_executable="python.exe",
            worker_script="worker.py",
            models_dir="models",
            checkpoint_path="checkpoint.pt",
            repo_path="repo",
            config_identifier="sam2_config.yaml",
            device="cuda:0",
            timeout_sec=12.5,
            working_directory="cwd",
        )

        sam2_config = sam2_backend_config_from_mask_config(shared_config)

        self.assertEqual(sam2_config.python_executable, "python.exe")
        self.assertEqual(sam2_config.worker_script, "worker.py")
        self.assertEqual(sam2_config.checkpoint_path, "checkpoint.pt")
        self.assertEqual(sam2_config.repo_path, "repo")
        self.assertEqual(sam2_config.config_path, "sam2_config.yaml")
        self.assertEqual(sam2_config.device, "cuda:0")
        self.assertEqual(sam2_config.timeout_sec, 12.5)
        self.assertEqual(sam2_config.working_directory, "cwd")
        self.assertTrue(sam2_config.apply_postprocessing)
        self.assertTrue(sam2_config.offload_video_to_cpu)

    def test_shared_config_rejects_non_sam2_kind(self) -> None:
        with self.assertRaises(ValueError):
            sam2_backend_config_from_mask_config(
                MaskTrackerBackendConfig(
                    kind="samurai",
                    python_executable="python.exe",
                    worker_script="worker.py",
                    models_dir="models",
                    checkpoint_path="checkpoint.pt",
                )
            )

    def test_facade_runs_existing_sam2_backend_without_changing_worker_contract(self) -> None:
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

                with np.load(args.input_npz, allow_pickle=False) as payload:
                    assert "tracker_kind" not in payload.files
                    assert int(payload["contract_version"]) == 1
                    frames = payload["frames"]
                    track_id = int(payload["track_id"])
                    frame_index_offset = int(payload["frame_index_offset"])
                    assert payload["source_view"].item() == "repair+bm3d"
                    assert payload["query_box_xyxy"].shape == (4,)

                masks = np.zeros((frames.shape[0], frames.shape[1], frames.shape[2]), dtype=np.uint8)
                masks[:, 1:3, 2:4] = 1
                np.savez_compressed(
                    args.output_npz,
                    contract_version=np.asarray(1, dtype=np.int64),
                    track_id=np.asarray(track_id, dtype=np.int64),
                    frame_index_offset=np.asarray(frame_index_offset, dtype=np.int64),
                    masks=masks,
                    visible_mask=np.asarray([1, 1, 0], dtype=np.uint8),
                    mask_scores=np.asarray([0.9, 0.8, 0.2], dtype=np.float32),
                )
                """,
            )

            backend = Sam2MaskTrackerBackend(
                MaskTrackerBackendConfig(
                    kind="sam2",
                    python_executable=sys.executable,
                    worker_script=worker_script,
                    models_dir="models",
                    checkpoint_path="checkpoint.pt",
                    repo_path="repo-dir",
                    config_identifier="config.yaml",
                    device="cuda:0",
                    timeout_sec=5.0,
                    working_directory=temp_path,
                )
            )

            result = backend.run(self._make_mask_input())

            self.assertEqual(result.tracker_kind, MaskTrackerKind.SAM2)
            self.assertEqual(result.track_id, 5)
            self.assertEqual(result.frame_index_offset, 7)
            self.assertEqual(result.masks.shape, (3, 6, 8))
            self.assertEqual(result.model_name, "sam2")
            self.assertEqual(result.checkpoint_name, "checkpoint.pt")
            np.testing.assert_array_equal(result.visible_mask, np.asarray([True, True, False]))
            np.testing.assert_array_equal(result.mask_scores, np.asarray([0.9, 0.8, 0.2], dtype=np.float32))

    def test_facade_cancel_delegates_to_existing_sam2_backend(self) -> None:
        class FakeSam2Backend:
            def __init__(self) -> None:
                self.cancel_called = False

            def cancel(self) -> None:
                self.cancel_called = True

        fake_backend = FakeSam2Backend()
        backend = Sam2MaskTrackerBackend(backend=fake_backend)

        backend.cancel()

        self.assertTrue(fake_backend.cancel_called)


if __name__ == "__main__":
    unittest.main()
