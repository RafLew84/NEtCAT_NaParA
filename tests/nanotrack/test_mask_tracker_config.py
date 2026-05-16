import unittest
from pathlib import Path

from nanotrack.mask_trackers import (
    DEFAULT_DAM4SAM_CHECKPOINT,
    DEFAULT_DAM4SAM_MODELS_DIR,
    DEFAULT_DAM4SAM_PYTHON,
    DEFAULT_DAM4SAM_REPO_PATH,
    DEFAULT_SAM2_CHECKPOINT,
    DEFAULT_SAM2_MODELS_DIR,
    DEFAULT_SAM2_PYTHON,
    DEFAULT_SAM2_REPO_PATH,
    DEFAULT_SAMURAI_CHECKPOINT,
    DEFAULT_SAMURAI_MODELS_DIR,
    DEFAULT_SAMURAI_PYTHON,
    DEFAULT_SAMURAI_REPO_PATH,
    MASK_TRACKER_KINDS,
    MaskTrackerBackendConfig,
    MaskTrackerKind,
    checkpoint_name_for_kind,
    config_identifier_for_kind,
    default_mask_tracker_config,
)
from nanotrack.sam2 import Sam2BackendConfig


class MaskTrackerConfigTests(unittest.TestCase):
    def test_kind_from_value_accepts_enum_and_lowercase_string(self) -> None:
        self.assertEqual(MaskTrackerKind.from_value(MaskTrackerKind.SAM2), MaskTrackerKind.SAM2)
        self.assertEqual(MaskTrackerKind.from_value("dam4sam"), MaskTrackerKind.DAM4SAM)
        self.assertEqual(MaskTrackerKind.from_value(" samurai "), MaskTrackerKind.SAMURAI)

    def test_kind_from_value_rejects_unknown_tracker(self) -> None:
        with self.assertRaises(ValueError):
            MaskTrackerKind.from_value("unknown")

    def test_supported_kinds_are_frozen_in_ui_order(self) -> None:
        self.assertEqual(
            MASK_TRACKER_KINDS,
            (MaskTrackerKind.SAM2, MaskTrackerKind.DAM4SAM, MaskTrackerKind.SAMURAI),
        )

    def test_default_sam2_config_matches_existing_backend_defaults(self) -> None:
        config = default_mask_tracker_config(MaskTrackerKind.SAM2)
        legacy = Sam2BackendConfig()

        self.assertEqual(config.kind, MaskTrackerKind.SAM2)
        self.assertEqual(Path(config.python_executable), DEFAULT_SAM2_PYTHON)
        self.assertEqual(Path(config.repo_path), DEFAULT_SAM2_REPO_PATH)
        self.assertEqual(Path(config.models_dir), DEFAULT_SAM2_MODELS_DIR)
        self.assertEqual(Path(config.checkpoint_path), DEFAULT_SAM2_CHECKPOINT)
        self.assertEqual(Path(config.python_executable), Path(legacy.python_executable))
        self.assertEqual(Path(config.repo_path), Path(legacy.repo_path))
        self.assertEqual(Path(config.checkpoint_path), Path(legacy.checkpoint_path))
        self.assertEqual(Path(config.worker_script), Path(legacy.worker_script))
        self.assertIsNone(config.variant)
        self.assertIsNone(config.config_identifier)

    def test_default_dam4sam_config_uses_dedicated_env_repo_and_base_plus_checkpoint(self) -> None:
        config = default_mask_tracker_config("dam4sam")

        self.assertEqual(config.kind, MaskTrackerKind.DAM4SAM)
        self.assertEqual(Path(config.python_executable), DEFAULT_DAM4SAM_PYTHON)
        self.assertEqual(Path(config.repo_path), DEFAULT_DAM4SAM_REPO_PATH)
        self.assertEqual(Path(config.models_dir), DEFAULT_DAM4SAM_MODELS_DIR)
        self.assertEqual(Path(config.checkpoint_path), DEFAULT_DAM4SAM_CHECKPOINT)
        self.assertEqual(config.variant, "sam21pp-B")
        self.assertEqual(config.config_identifier, "sam21pp_hiera_b+.yaml")
        self.assertEqual(Path(config.worker_script).name, "run_dam4sam_subprocess.py")
        self.assertEqual(config.timeout_sec, 1800.0)

    def test_default_samurai_config_uses_dedicated_env_repo_and_base_plus_checkpoint(self) -> None:
        config = default_mask_tracker_config("samurai")

        self.assertEqual(config.kind, MaskTrackerKind.SAMURAI)
        self.assertEqual(Path(config.python_executable), DEFAULT_SAMURAI_PYTHON)
        self.assertEqual(Path(config.repo_path), DEFAULT_SAMURAI_REPO_PATH)
        self.assertEqual(Path(config.models_dir), DEFAULT_SAMURAI_MODELS_DIR)
        self.assertEqual(Path(config.checkpoint_path), DEFAULT_SAMURAI_CHECKPOINT)
        self.assertEqual(config.variant, "sam2.1_hiera_base_plus")
        self.assertEqual(config.config_identifier, "configs/samurai/sam2.1_hiera_b+.yaml")
        self.assertEqual(Path(config.worker_script).name, "run_samurai_subprocess.py")
        self.assertEqual(config.timeout_sec, 1800.0)

    def test_variant_helpers_resolve_dam4sam_aliases(self) -> None:
        self.assertEqual(checkpoint_name_for_kind("dam4sam", "sam21pp-B+"), "sam2.1_hiera_base_plus.pt")
        self.assertEqual(config_identifier_for_kind("dam4sam", "sam21pp-B+"), "sam21pp_hiera_b+.yaml")
        self.assertEqual(checkpoint_name_for_kind("dam4sam", "sam21pp-L"), "sam2.1_hiera_large.pt")

    def test_variant_helpers_resolve_samurai_aliases(self) -> None:
        self.assertEqual(checkpoint_name_for_kind("samurai", "b+"), "sam2.1_hiera_base_plus.pt")
        self.assertEqual(config_identifier_for_kind("samurai", "b+"), "configs/samurai/sam2.1_hiera_b+.yaml")
        self.assertEqual(checkpoint_name_for_kind("samurai", "tiny"), "sam2.1_hiera_tiny.pt")

    def test_config_validates_kind_timeout_and_variant(self) -> None:
        with self.assertRaises(ValueError):
            MaskTrackerBackendConfig(
                kind="missing",
                python_executable="python",
                worker_script="worker.py",
                models_dir="models",
                checkpoint_path="checkpoint.pt",
            )
        with self.assertRaises(ValueError):
            MaskTrackerBackendConfig(
                kind="sam2",
                python_executable="python",
                worker_script="worker.py",
                models_dir="models",
                checkpoint_path="checkpoint.pt",
                timeout_sec=0.0,
            )
        with self.assertRaises(ValueError):
            MaskTrackerBackendConfig(
                kind="samurai",
                python_executable="python",
                worker_script="worker.py",
                models_dir="models",
                checkpoint_path="checkpoint.pt",
                variant=" ",
            )


if __name__ == "__main__":
    unittest.main()
