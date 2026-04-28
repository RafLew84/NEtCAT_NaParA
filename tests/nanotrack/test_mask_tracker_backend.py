import sys
import textwrap
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from nanotrack.mask_trackers import (
    MASK_TRACKER_BACKEND_REGISTRY,
    MaskTrackerBackendConfig,
    MaskTrackerBackendCancelledError,
    MaskTrackerBackendError,
    MaskTrackerBackendTimeoutError,
    MaskTrackerBackendUnavailableError,
    MaskTrackerKind,
    MaskTrackerRunInput,
    MaskTrackerSubprocessBackend,
    Sam2MaskTrackerBackend,
    create_mask_tracker_backend,
    validate_mask_tracker_backend_config,
)
from nanotrack.subprocess_utils import SubprocessCancelledError


def _write_worker_script(path: Path, body: str) -> None:
    path.write_text(textwrap.dedent(body), encoding="utf-8")


def _valid_config(
    *,
    temp_path: Path,
    kind: str | MaskTrackerKind,
    worker_script: Path | None = None,
) -> MaskTrackerBackendConfig:
    models_dir = temp_path / "models"
    models_dir.mkdir(exist_ok=True)
    repo_dir = temp_path / "repo"
    repo_dir.mkdir(exist_ok=True)
    checkpoint_path = models_dir / "checkpoint.pt"
    checkpoint_path.write_bytes(b"checkpoint")
    if worker_script is None:
        worker_script = temp_path / "worker.py"
        worker_script.write_text("raise SystemExit(0)\n", encoding="utf-8")
    return MaskTrackerBackendConfig(
        kind=kind,
        python_executable=sys.executable,
        worker_script=worker_script,
        models_dir=models_dir,
        checkpoint_path=checkpoint_path,
        repo_path=repo_dir,
        variant="variant-a" if MaskTrackerKind.from_value(kind) is not MaskTrackerKind.SAM2 else None,
        config_identifier="config.yaml" if MaskTrackerKind.from_value(kind) is not MaskTrackerKind.SAM2 else None,
        device="cpu",
        timeout_sec=5.0,
        working_directory=temp_path,
    )


class MaskTrackerBackendFactoryTests(unittest.TestCase):
    def test_registry_maps_all_tracker_kinds_to_backend_classes(self) -> None:
        self.assertEqual(MASK_TRACKER_BACKEND_REGISTRY[MaskTrackerKind.SAM2], Sam2MaskTrackerBackend)
        self.assertEqual(MASK_TRACKER_BACKEND_REGISTRY[MaskTrackerKind.DAM4SAM], MaskTrackerSubprocessBackend)
        self.assertEqual(MASK_TRACKER_BACKEND_REGISTRY[MaskTrackerKind.SAMURAI], MaskTrackerSubprocessBackend)

    def test_factory_selects_sam2_adapter(self) -> None:
        with TemporaryDirectory() as temp_dir:
            config = _valid_config(temp_path=Path(temp_dir), kind="sam2")

            backend = create_mask_tracker_backend(config)

            self.assertIsInstance(backend, Sam2MaskTrackerBackend)

    def test_factory_selects_common_subprocess_backend_for_optional_trackers(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            dam4sam_config = _valid_config(temp_path=temp_path, kind="dam4sam")
            samurai_config = _valid_config(temp_path=temp_path, kind="samurai")

            dam4sam_backend = create_mask_tracker_backend(dam4sam_config)
            samurai_backend = create_mask_tracker_backend(samurai_config)

            self.assertIsInstance(dam4sam_backend, MaskTrackerSubprocessBackend)
            self.assertIsInstance(samurai_backend, MaskTrackerSubprocessBackend)
            self.assertEqual(dam4sam_backend.config.kind, MaskTrackerKind.DAM4SAM)
            self.assertEqual(samurai_backend.config.kind, MaskTrackerKind.SAMURAI)

    def test_validation_reports_missing_env_repo_worker_models_and_checkpoint(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = MaskTrackerBackendConfig(
                kind="dam4sam",
                python_executable=root / "missing_python.exe",
                worker_script=root / "missing_worker.py",
                models_dir=root / "missing_models",
                checkpoint_path=root / "missing_checkpoint.pt",
                repo_path=root / "missing_repo",
            )

            with self.assertRaises(MaskTrackerBackendUnavailableError) as exc_info:
                validate_mask_tracker_backend_config(config)

        message = str(exc_info.exception)
        self.assertIn("Mask tracker backend 'dam4sam' is not available", message)
        self.assertIn("python_executable", message)
        self.assertIn("worker_script", message)
        self.assertIn("models_dir", message)
        self.assertIn("checkpoint_path", message)
        self.assertIn("repo_path", message)

    def test_common_subprocess_backend_roundtrip_executes_worker_and_parses_output(self) -> None:
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
                parser.add_argument("--variant", default=None)
                parser.add_argument("--config", default=None)
                parser.add_argument("--device", default=None)
                args = parser.parse_args()

                assert args.checkpoint.endswith("checkpoint.pt")
                assert args.repo_path is not None
                assert args.variant == "sam21pp-B"
                assert args.config == "sam21pp_hiera_b+.yaml"
                assert args.device == "cpu"

                with np.load(args.input_npz, allow_pickle=False) as payload:
                    assert payload["tracker_kind"].item() == "dam4sam"
                    frames = payload["frames"]
                    track_id = int(payload["track_id"])
                    frame_index_offset = int(payload["frame_index_offset"])

                masks = np.zeros((frames.shape[0], frames.shape[1], frames.shape[2]), dtype=np.uint8)
                masks[:, 1:3, 2:4] = 1
                np.savez_compressed(
                    args.output_npz,
                    contract_version=np.asarray(1, dtype=np.int64),
                    tracker_kind=np.asarray("dam4sam"),
                    track_id=np.asarray(track_id, dtype=np.int64),
                    frame_index_offset=np.asarray(frame_index_offset, dtype=np.int64),
                    masks=masks,
                    visible_mask=np.asarray([1, 1, 0], dtype=np.uint8),
                    mask_scores=np.asarray([0.9, 0.8, 0.2], dtype=np.float32),
                    model_name=np.asarray("dam4sam"),
                    model_variant=np.asarray("sam21pp-B"),
                    checkpoint_name=np.asarray("checkpoint.pt"),
                )
                """,
            )
            config = _valid_config(temp_path=temp_path, kind="dam4sam", worker_script=worker_script)
            config = MaskTrackerBackendConfig(
                kind=config.kind,
                python_executable=config.python_executable,
                worker_script=config.worker_script,
                models_dir=config.models_dir,
                checkpoint_path=config.checkpoint_path,
                repo_path=config.repo_path,
                variant="sam21pp-B",
                config_identifier="sam21pp_hiera_b+.yaml",
                device="cpu",
                timeout_sec=config.timeout_sec,
                working_directory=config.working_directory,
            )
            backend = create_mask_tracker_backend(config)
            run_input = MaskTrackerRunInput(
                tracker_kind="dam4sam",
                track_id=3,
                frame_index_offset=5,
                frames=np.zeros((3, 6, 8), dtype=np.float32),
                query_box_xyxy=np.asarray([1.0, 2.0, 5.0, 4.0], dtype=np.float32),
            )

            result = backend.run(run_input)

            self.assertEqual(result.tracker_kind, MaskTrackerKind.DAM4SAM)
            self.assertEqual(result.track_id, 3)
            self.assertEqual(result.frame_index_offset, 5)
            self.assertEqual(result.model_name, "dam4sam")
            self.assertEqual(result.model_variant, "sam21pp-B")
            self.assertEqual(result.checkpoint_name, "checkpoint.pt")
            np.testing.assert_array_equal(result.visible_mask, np.asarray([True, True, False]))
            np.testing.assert_array_equal(result.mask_scores, np.asarray([0.9, 0.8, 0.2], dtype=np.float32))

    def test_common_subprocess_backend_raises_timeout_error(self) -> None:
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
                parser.add_argument("--variant", default=None)
                parser.add_argument("--config", default=None)
                parser.add_argument("--device", default=None)
                parser.parse_args()
                time.sleep(1.0)
                """,
            )
            config = _valid_config(temp_path=temp_path, kind="samurai", worker_script=worker_script)
            config = MaskTrackerBackendConfig(
                kind=config.kind,
                python_executable=config.python_executable,
                worker_script=config.worker_script,
                models_dir=config.models_dir,
                checkpoint_path=config.checkpoint_path,
                repo_path=config.repo_path,
                variant="sam2.1_hiera_base_plus",
                config_identifier="configs/samurai/sam2.1_hiera_b+.yaml",
                device="cpu",
                timeout_sec=0.1,
                working_directory=config.working_directory,
            )
            backend = create_mask_tracker_backend(config)
            run_input = MaskTrackerRunInput(
                tracker_kind="samurai",
                track_id=3,
                frame_index_offset=5,
                frames=np.zeros((3, 6, 8), dtype=np.float32),
                query_box_xyxy=np.asarray([1.0, 2.0, 5.0, 4.0], dtype=np.float32),
            )

            with self.assertRaises(MaskTrackerBackendTimeoutError):
                backend.run(run_input)

    def test_common_subprocess_backend_translates_cancelled_runner_error(self) -> None:
        class FakeRunner:
            def __init__(self) -> None:
                self.cancel_called = False

            def run(self, command, *, cwd, timeout):
                raise SubprocessCancelledError("stopped")

            def cancel(self) -> None:
                self.cancel_called = True

        with TemporaryDirectory() as temp_dir:
            config = _valid_config(temp_path=Path(temp_dir), kind="dam4sam")
            backend = create_mask_tracker_backend(config)
            fake_runner = FakeRunner()
            backend._runner = fake_runner
            run_input = MaskTrackerRunInput(
                tracker_kind="dam4sam",
                track_id=3,
                frame_index_offset=5,
                frames=np.zeros((3, 6, 8), dtype=np.float32),
                query_box_xyxy=np.asarray([1.0, 2.0, 5.0, 4.0], dtype=np.float32),
            )

            with self.assertRaises(MaskTrackerBackendCancelledError) as exc_info:
                backend.run(run_input)

            self.assertIn("canceled", str(exc_info.exception))
            backend.cancel()
            self.assertTrue(fake_runner.cancel_called)

    def test_common_subprocess_backend_rejects_mismatched_input_kind(self) -> None:
        with TemporaryDirectory() as temp_dir:
            config = _valid_config(temp_path=Path(temp_dir), kind="dam4sam")
            backend = create_mask_tracker_backend(config)
            run_input = MaskTrackerRunInput(
                tracker_kind="samurai",
                track_id=3,
                frame_index_offset=5,
                frames=np.zeros((3, 6, 8), dtype=np.float32),
                query_box_xyxy=np.asarray([1.0, 2.0, 5.0, 4.0], dtype=np.float32),
            )

            with self.assertRaises(ValueError):
                backend.run(run_input)

    def test_common_subprocess_backend_reports_nonzero_worker_exit(self) -> None:
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
            config = _valid_config(temp_path=temp_path, kind="dam4sam", worker_script=worker_script)
            backend = create_mask_tracker_backend(config)
            run_input = MaskTrackerRunInput(
                tracker_kind="dam4sam",
                track_id=3,
                frame_index_offset=5,
                frames=np.zeros((3, 6, 8), dtype=np.float32),
                query_box_xyxy=np.asarray([1.0, 2.0, 5.0, 4.0], dtype=np.float32),
            )

            with self.assertRaises(MaskTrackerBackendError) as exc_info:
                backend.run(run_input)

            self.assertIn("Exit code: 4", str(exc_info.exception))
            self.assertIn("worker exploded", str(exc_info.exception))


if __name__ == "__main__":
    unittest.main()
