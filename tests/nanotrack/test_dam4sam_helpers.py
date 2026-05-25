import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from nanotrack.mask_trackers import (
    DAM4SAM_TRACKER_VARIANTS,
    DEFAULT_DAM4SAM_CHECKPOINT,
    DEFAULT_DAM4SAM_MODELS_DIR,
    DEFAULT_DAM4SAM_PYTHON,
    DEFAULT_DAM4SAM_REPO_PATH,
    MaskTrackerBackendConfig,
    MaskTrackerBackendUnavailableError,
    MaskTrackerKind,
    MaskTrackerRunInput,
    MaskTrackerSubprocessBackend,
    checkpoint_name_for_kind,
    config_identifier_for_kind,
    default_mask_tracker_config,
    validate_mask_tracker_backend_config,
)
from nanotrack.mask_trackers.run_dam4sam_subprocess import _coerce_pred_mask


class Dam4SamVariantMappingTests(unittest.TestCase):
    def test_all_dam4sam_variants_map_to_expected_checkpoint_and_config(self) -> None:
        expected = {
            "sam21pp-L": ("sam2.1_hiera_large.pt", "sam21pp_hiera_l.yaml"),
            "sam21pp-B": ("sam2.1_hiera_base_plus.pt", "sam21pp_hiera_b+.yaml"),
            "sam21pp-S": ("sam2.1_hiera_small.pt", "sam21pp_hiera_s.yaml"),
            "sam21pp-T": ("sam2.1_hiera_tiny.pt", "sam21pp_hiera_t.yaml"),
        }

        self.assertEqual(DAM4SAM_TRACKER_VARIANTS, expected)
        for variant, (checkpoint_name, config_identifier) in expected.items():
            self.assertEqual(checkpoint_name_for_kind(MaskTrackerKind.DAM4SAM, variant), checkpoint_name)
            self.assertEqual(config_identifier_for_kind(MaskTrackerKind.DAM4SAM, variant), config_identifier)

    def test_dam4sam_variant_aliases_map_to_base_plus(self) -> None:
        for alias in ("sam21pp-B+", "sam21pp-b_plus", "sam21pp-base-plus", "sam21pp-base"):
            self.assertEqual(
                checkpoint_name_for_kind(MaskTrackerKind.DAM4SAM, alias),
                "sam2.1_hiera_base_plus.pt",
            )
            self.assertEqual(
                config_identifier_for_kind(MaskTrackerKind.DAM4SAM, alias),
                "sam21pp_hiera_b+.yaml",
            )

    def test_unknown_dam4sam_variant_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            checkpoint_name_for_kind(MaskTrackerKind.DAM4SAM, "sam21pp-missing")


class Dam4SamBackendValidationTests(unittest.TestCase):
    def test_default_config_uses_dam4sam_env_repo_worker_and_base_plus_paths(self) -> None:
        config = default_mask_tracker_config(MaskTrackerKind.DAM4SAM)

        self.assertEqual(config.kind, MaskTrackerKind.DAM4SAM)
        self.assertEqual(Path(config.python_executable), DEFAULT_DAM4SAM_PYTHON)
        self.assertEqual(Path(config.repo_path), DEFAULT_DAM4SAM_REPO_PATH)
        self.assertEqual(Path(config.models_dir), DEFAULT_DAM4SAM_MODELS_DIR)
        self.assertEqual(Path(config.checkpoint_path), DEFAULT_DAM4SAM_CHECKPOINT)
        self.assertEqual(Path(config.worker_script).name, "run_dam4sam_subprocess.py")
        self.assertEqual(config.variant, "sam21pp-B")
        self.assertEqual(config.config_identifier, "sam21pp_hiera_b+.yaml")

    def test_missing_dam4sam_env_repo_models_checkpoint_and_worker_are_reported(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = MaskTrackerBackendConfig(
                kind=MaskTrackerKind.DAM4SAM,
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

    def test_dam4sam_validation_rejects_file_where_directory_is_required(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            python_executable = root / "python.exe"
            python_executable.write_text("", encoding="utf-8")
            worker_script = root / "worker.py"
            worker_script.write_text("", encoding="utf-8")
            checkpoint = root / "checkpoint.pt"
            checkpoint.write_bytes(b"checkpoint")
            models_file = root / "models_file"
            models_file.write_text("", encoding="utf-8")
            repo_file = root / "repo_file"
            repo_file.write_text("", encoding="utf-8")
            config = MaskTrackerBackendConfig(
                kind=MaskTrackerKind.DAM4SAM,
                python_executable=python_executable,
                worker_script=worker_script,
                models_dir=models_file,
                checkpoint_path=checkpoint,
                repo_path=repo_file,
            )

            with self.assertRaises(MaskTrackerBackendUnavailableError) as exc_info:
                validate_mask_tracker_backend_config(config)

        message = str(exc_info.exception)
        self.assertIn("models_dir", message)
        self.assertIn("repo_path", message)
        self.assertIn("expected directory", message)


class Dam4SamMaskThresholdTests(unittest.TestCase):
    def test_coerce_pred_mask_applies_probability_threshold_for_soft_masks(self) -> None:
        probabilities = np.asarray(
            [
                [0.20, 0.60],
                [0.75, 0.90],
            ],
            dtype=np.float32,
        )

        mask = _coerce_pred_mask(probabilities, frame_shape=(2, 2), probability_threshold=0.7)

        np.testing.assert_array_equal(mask, np.asarray([[False, False], [True, True]]))

    def test_coerce_pred_mask_preserves_binary_scaled_masks(self) -> None:
        binary_scaled = np.asarray([[0.0, 255.0], [0.0, 255.0]], dtype=np.float32)

        mask = _coerce_pred_mask(binary_scaled, frame_shape=(2, 2), probability_threshold=0.9)

        np.testing.assert_array_equal(mask, np.asarray([[False, True], [False, True]]))


def _default_dam4sam_runtime_available() -> bool:
    config = default_mask_tracker_config(MaskTrackerKind.DAM4SAM)
    try:
        validate_mask_tracker_backend_config(config)
    except MaskTrackerBackendUnavailableError:
        return False
    return True


@unittest.skipUnless(_default_dam4sam_runtime_available(), "Default DAM4SAM env/repo/checkpoint paths are not available.")
class Dam4SamRuntimeSmokeTests(unittest.TestCase):
    def test_default_dam4sam_worker_smoke_runs_if_runtime_is_available(self) -> None:
        config = default_mask_tracker_config(MaskTrackerKind.DAM4SAM)
        backend = MaskTrackerSubprocessBackend(config)
        frames = np.zeros((2, 64, 64), dtype=np.float32)
        frames[:, 20:44, 22:46] = 1.0
        run_input = MaskTrackerRunInput(
            tracker_kind=MaskTrackerKind.DAM4SAM,
            track_id=1,
            frame_index_offset=0,
            frames=frames,
            query_box_xyxy=np.asarray([20.0, 18.0, 48.0, 46.0], dtype=np.float32),
        )

        result = backend.run(run_input)

        self.assertEqual(result.tracker_kind, MaskTrackerKind.DAM4SAM)
        self.assertEqual(result.track_id, 1)
        self.assertEqual(result.frame_index_offset, 0)
        self.assertEqual(result.model_name, "dam4sam")
        self.assertEqual(result.model_variant, config.variant)
        self.assertEqual(result.checkpoint_name, Path(config.checkpoint_path).name)
        self.assertEqual(result.masks.shape, (2, 64, 64))
        self.assertEqual(result.visible_mask.shape, (2,))


if __name__ == "__main__":
    unittest.main()
