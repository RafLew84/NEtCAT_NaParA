import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
from PIL import Image

from nanotrack.mask_trackers import (
    DEFAULT_SAMURAI_MODEL_VARIANT,
    DEFAULT_SAMURAI_MODELS_DIR,
    DEFAULT_SAMURAI_PYTHON,
    DEFAULT_SAMURAI_REPO_PATH,
    SAMURAI_MODEL_VARIANTS,
    MaskTrackerBackendConfig,
    MaskTrackerBackendError,
    MaskTrackerBackendUnavailableError,
    MaskTrackerKind,
    MaskTrackerRunInput,
    MaskTrackerSubprocessBackend,
    config_identifier_for_kind,
    validate_mask_tracker_backend_config,
)
from nanotrack.mask_trackers.run_samurai_subprocess import (
    _coerce_samurai_mask,
    _materialize_samurai_inputs,
    _record_samurai_output_tuple,
    _resolve_samurai_config_identifier,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
SAMURAI_WORKER = REPO_ROOT / "nanotrack" / "mask_trackers" / "run_samurai_subprocess.py"


class _FakeTensor:
    def __init__(self, array: np.ndarray) -> None:
        self._array = np.asarray(array)

    def detach(self):
        return self

    def cpu(self):
        return self

    def numpy(self) -> np.ndarray:
        return self._array


def _samurai_smoke_config() -> MaskTrackerBackendConfig | None:
    if not Path(DEFAULT_SAMURAI_PYTHON).exists():
        return None
    if not Path(DEFAULT_SAMURAI_REPO_PATH).exists():
        return None
    if not Path(DEFAULT_SAMURAI_MODELS_DIR).exists():
        return None

    variants = ("sam2.1_hiera_tiny", DEFAULT_SAMURAI_MODEL_VARIANT)
    for variant in variants:
        checkpoint_name, config_identifier = SAMURAI_MODEL_VARIANTS[variant]
        checkpoint_path = Path(DEFAULT_SAMURAI_MODELS_DIR) / checkpoint_name
        if not checkpoint_path.exists():
            continue
        config = MaskTrackerBackendConfig(
            kind=MaskTrackerKind.SAMURAI,
            python_executable=DEFAULT_SAMURAI_PYTHON,
            worker_script=SAMURAI_WORKER,
            models_dir=DEFAULT_SAMURAI_MODELS_DIR,
            checkpoint_path=checkpoint_path,
            repo_path=DEFAULT_SAMURAI_REPO_PATH,
            variant=variant,
            config_identifier=config_identifier,
            device="auto",
            timeout_sec=1800.0,
            working_directory=REPO_ROOT,
        )
        try:
            validate_mask_tracker_backend_config(config)
        except MaskTrackerBackendUnavailableError:
            continue
        return config
    return None


class SamuraiWorkerTests(unittest.TestCase):
    def _make_fake_samurai_repo(self, root: Path) -> Path:
        repo_path = root / "samurai_repo"
        (repo_path / "scripts").mkdir(parents=True)
        (repo_path / "scripts" / "demo.py").write_text("# fake demo marker\n", encoding="utf-8")
        sam2_root = repo_path / "sam2"
        (sam2_root / "sam2" / "configs" / "samurai").mkdir(parents=True)
        (sam2_root / "sam2" / "__init__.py").write_text("", encoding="utf-8")
        (sam2_root / "sam2" / "configs" / "samurai" / "sam2.1_hiera_b+.yaml").write_text(
            "model: {}\n",
            encoding="utf-8",
        )
        (sam2_root / "torch.py").write_text(
            "\n".join(
                [
                    "class _Context:",
                    "    def __enter__(self): return self",
                    "    def __exit__(self, exc_type, exc, tb): return False",
                    "class _Cuda:",
                    "    @staticmethod",
                    "    def is_available(): return False",
                    "    @staticmethod",
                    "    def empty_cache(): pass",
                    "cuda = _Cuda()",
                    "float16 = 'float16'",
                    "def inference_mode(): return _Context()",
                    "def autocast(*args, **kwargs): return _Context()",
                    "def clear_autocast_cache(): pass",
                ]
            ),
            encoding="utf-8",
        )
        (sam2_root / "sam2" / "build_sam.py").write_text(
            "\n".join(
                [
                    "from pathlib import Path",
                    "import numpy as np",
                    "from PIL import Image",
                    "",
                    "class _Tensor:",
                    "    def __init__(self, arr): self._arr = arr",
                    "    def detach(self): return self",
                    "    def cpu(self): return self",
                    "    def numpy(self): return self._arr",
                    "",
                    "class _Predictor:",
                    "    def __init__(self): self.calls = []",
                    "    def init_state(self, frame_dir, offload_video_to_cpu=True):",
                    "        paths = sorted(Path(frame_dir).glob('*.jpg'))",
                    "        with Image.open(paths[0]) as image:",
                    "            width, height = image.size",
                    "        return {'count': len(paths), 'height': height, 'width': width}",
                    "    def add_new_points_or_box(self, state, box, frame_idx, obj_id):",
                    "        return frame_idx, [obj_id], [_Tensor(self._mask(state, int(frame_idx)))]",
                    "    def propagate_in_video(self, state):",
                    "        for frame_idx in range(state['count']):",
                    "            yield frame_idx, [0], [_Tensor(self._mask(state, frame_idx))]",
                    "    def _mask(self, state, frame_idx):",
                    "        mask = np.zeros((1, state['height'], state['width']), dtype=np.float32)",
                    "        row0 = min(state['height'], 1 + frame_idx)",
                    "        col0 = min(state['width'], 2 + frame_idx)",
                    "        row1 = min(state['height'], row0 + 3)",
                    "        col1 = min(state['width'], col0 + 3)",
                    "        mask[0, row0:row1, col0:col1] = 1.0",
                    "        return mask",
                    "",
                    "def build_sam2_video_predictor(config, checkpoint, device='cpu'):",
                    "    if config != 'configs/samurai/sam2.1_hiera_b+.yaml':",
                    "        raise RuntimeError(f'unexpected config: {config}')",
                    "    if not str(checkpoint).endswith('sam2.1_hiera_base_plus.pt'):",
                    "        raise RuntimeError(f'unexpected checkpoint: {checkpoint}')",
                    "    if device != 'cpu':",
                    "        raise RuntimeError(f'unexpected device: {device}')",
                    "    return _Predictor()",
                ]
            ),
            encoding="utf-8",
        )
        return repo_path

    def test_materializes_frames_and_bbox_txt_for_samurai_file_interface(self) -> None:
        frames = np.stack(
            [
                np.arange(24, dtype=np.float32).reshape(4, 6),
                np.arange(24, dtype=np.float32).reshape(4, 6)[::-1],
            ],
            axis=0,
        )
        run_input = MaskTrackerRunInput(
            tracker_kind=MaskTrackerKind.SAMURAI,
            track_id=3,
            frame_index_offset=1,
            frames=frames,
            query_box_xyxy=np.asarray([2.0, 1.0, 5.0, 4.0], dtype=np.float32),
        )

        with TemporaryDirectory() as temp_dir:
            materialized = _materialize_samurai_inputs(run_input, Path(temp_dir))

            self.assertEqual(materialized.frame_dir, Path(temp_dir) / "frames")
            self.assertEqual(materialized.bbox_path, Path(temp_dir) / "bbox.txt")
            self.assertEqual(materialized.bbox_xywh, (2, 1, 3, 3))
            self.assertEqual(materialized.bbox_path.read_text(encoding="utf-8"), "2,1,3,3\n")
            self.assertEqual([path.name for path in materialized.frame_paths], ["000000.jpg", "000001.jpg"])
            self.assertTrue(all(path.exists() for path in materialized.frame_paths))

            with Image.open(materialized.frame_paths[0]) as image:
                self.assertEqual(image.mode, "RGB")
                self.assertEqual(image.size, (6, 4))

    def test_materializes_bbox_from_initial_mask_prompt(self) -> None:
        initial_mask = np.zeros((5, 7), dtype=bool)
        initial_mask[1:4, 2:6] = True
        run_input = MaskTrackerRunInput(
            tracker_kind=MaskTrackerKind.SAMURAI,
            track_id=3,
            frame_index_offset=1,
            frames=np.zeros((1, 5, 7), dtype=np.float32),
            initial_mask=initial_mask,
        )

        with TemporaryDirectory() as temp_dir:
            materialized = _materialize_samurai_inputs(run_input, Path(temp_dir))

            self.assertEqual(materialized.bbox_xywh, (2, 1, 4, 3))
            self.assertEqual(materialized.bbox_path.read_text(encoding="utf-8"), "2,1,4,3\n")

    def test_resolves_samurai_config_from_variant_alias_and_checkpoint(self) -> None:
        checkpoint = Path("sam2.1_hiera_base_plus.pt")

        self.assertEqual(
            _resolve_samurai_config_identifier(None, variant="b+", checkpoint_path=checkpoint),
            "configs/samurai/sam2.1_hiera_b+.yaml",
        )
        self.assertEqual(
            _resolve_samurai_config_identifier(
                "configs/custom.yaml",
                variant="unknown",
                checkpoint_path=checkpoint,
            ),
            "configs/custom.yaml",
        )
        self.assertEqual(
            config_identifier_for_kind(MaskTrackerKind.SAMURAI, "tiny"),
            "configs/samurai/sam2.1_hiera_t.yaml",
        )

    def test_parses_samurai_output_tuple_into_mask_array(self) -> None:
        masks = np.zeros((2, 4, 6), dtype=bool)
        ignored = np.ones((1, 4, 6), dtype=np.float32)
        selected = np.zeros((1, 4, 6), dtype=np.float32)
        selected[0, 1:3, 2:5] = 1.0

        _record_samurai_output_tuple(
            (1, [7, 0], [_FakeTensor(ignored), _FakeTensor(selected)]),
            masks=masks,
        )

        expected = np.zeros((2, 4, 6), dtype=bool)
        expected[1, 1:3, 2:5] = True
        np.testing.assert_array_equal(masks, expected)

    def test_coerces_resized_samurai_mask_to_frame_shape(self) -> None:
        source = np.zeros((1, 2, 3), dtype=np.float32)
        source[0, 0, 1] = 1.0

        mask = _coerce_samurai_mask(_FakeTensor(source), frame_shape=(4, 6))

        self.assertEqual(mask.shape, (4, 6))
        self.assertGreater(int(np.count_nonzero(mask)), 0)

    def test_samurai_validation_reports_missing_env_repo_models_checkpoint_and_worker(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = MaskTrackerBackendConfig(
                kind=MaskTrackerKind.SAMURAI,
                python_executable=root / "missing_python.exe",
                worker_script=root / "missing_worker.py",
                models_dir=root / "missing_models",
                checkpoint_path=root / "missing_checkpoint.pt",
                repo_path=root / "missing_repo",
            )

            with self.assertRaises(MaskTrackerBackendUnavailableError) as exc_info:
                validate_mask_tracker_backend_config(config)

        message = str(exc_info.exception)
        self.assertIn("Mask tracker backend 'samurai' is not available", message)
        self.assertIn("python_executable", message)
        self.assertIn("worker_script", message)
        self.assertIn("models_dir", message)
        self.assertIn("checkpoint_path", message)
        self.assertIn("repo_path", message)

    def test_real_worker_reports_invalid_repo_layout(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            models_dir = temp_path / "models"
            models_dir.mkdir()
            checkpoint = models_dir / "sam2.1_hiera_base_plus.pt"
            checkpoint.write_bytes(b"fake checkpoint")
            invalid_repo = temp_path / "invalid_samurai_repo"
            invalid_repo.mkdir()

            backend = MaskTrackerSubprocessBackend(
                MaskTrackerBackendConfig(
                    kind=MaskTrackerKind.SAMURAI,
                    python_executable=sys.executable,
                    worker_script=SAMURAI_WORKER,
                    models_dir=models_dir,
                    checkpoint_path=checkpoint,
                    repo_path=invalid_repo,
                    variant="sam2.1_hiera_base_plus",
                    config_identifier="configs/samurai/sam2.1_hiera_b+.yaml",
                    device="cpu",
                    timeout_sec=10.0,
                    working_directory=REPO_ROOT,
                )
            )
            run_input = MaskTrackerRunInput(
                tracker_kind=MaskTrackerKind.SAMURAI,
                track_id=7,
                frame_index_offset=0,
                frames=np.zeros((1, 6, 8), dtype=np.float32),
                query_box_xyxy=np.asarray([2.0, 1.0, 5.0, 4.0], dtype=np.float32),
            )

            with self.assertRaises(MaskTrackerBackendError) as exc_info:
                backend.run(run_input)

        self.assertIn("Invalid SAMURAI repo_path", str(exc_info.exception))

    def test_stub_worker_runs_through_common_subprocess_backend(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            models_dir = temp_path / "models"
            models_dir.mkdir()
            checkpoint = models_dir / "sam2.1_hiera_base_plus.pt"
            checkpoint.write_bytes(b"stub checkpoint")
            repo_path = temp_path / "samurai_repo"
            repo_path.mkdir()

            backend = MaskTrackerSubprocessBackend(
                MaskTrackerBackendConfig(
                    kind=MaskTrackerKind.SAMURAI,
                    python_executable=sys.executable,
                    worker_script=SAMURAI_WORKER,
                    models_dir=models_dir,
                    checkpoint_path=checkpoint,
                    repo_path=repo_path,
                    variant="stub",
                    config_identifier="stub",
                    device="cpu",
                    timeout_sec=10.0,
                    working_directory=REPO_ROOT,
                )
            )
            frames = np.zeros((3, 6, 8), dtype=np.float32)
            run_input = MaskTrackerRunInput(
                tracker_kind=MaskTrackerKind.SAMURAI,
                track_id=7,
                frame_index_offset=4,
                frames=frames,
                query_box_xyxy=np.asarray([2.0, 1.0, 5.0, 4.0], dtype=np.float32),
                source_view="raw",
            )

            result = backend.run(run_input)

        expected_mask = np.zeros((6, 8), dtype=bool)
        expected_mask[1:4, 2:5] = True
        self.assertEqual(result.tracker_kind, MaskTrackerKind.SAMURAI)
        self.assertEqual(result.track_id, 7)
        self.assertEqual(result.frame_index_offset, 4)
        self.assertEqual(result.model_name, "samurai_stub")
        self.assertEqual(result.model_variant, "stub")
        self.assertEqual(result.checkpoint_name, "sam2.1_hiera_base_plus.pt")
        np.testing.assert_array_equal(result.masks, np.repeat(expected_mask[None, :, :], 3, axis=0))
        np.testing.assert_array_equal(result.visible_mask, np.asarray([True, True, True]))
        np.testing.assert_array_equal(result.mask_areas, np.asarray([9.0, 9.0, 9.0], dtype=np.float32))
        np.testing.assert_array_equal(
            result.mask_bboxes_xyxy,
            np.asarray(
                [
                    [2.0, 1.0, 5.0, 4.0],
                    [2.0, 1.0, 5.0, 4.0],
                    [2.0, 1.0, 5.0, 4.0],
                ],
                dtype=np.float32,
            ),
        )
        np.testing.assert_array_equal(result.mask_scores, np.asarray([1.0, 1.0, 1.0], dtype=np.float32))
        np.testing.assert_array_equal(result.mask_component_counts, np.asarray([1, 1, 1], dtype=np.int32))

    def test_real_worker_runs_fake_samurai_repo_and_parses_masks(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            repo_path = self._make_fake_samurai_repo(temp_path)
            models_dir = temp_path / "models"
            models_dir.mkdir()
            checkpoint = models_dir / "sam2.1_hiera_base_plus.pt"
            checkpoint.write_bytes(b"fake checkpoint")

            backend = MaskTrackerSubprocessBackend(
                MaskTrackerBackendConfig(
                    kind=MaskTrackerKind.SAMURAI,
                    python_executable=sys.executable,
                    worker_script=SAMURAI_WORKER,
                    models_dir=models_dir,
                    checkpoint_path=checkpoint,
                    repo_path=repo_path,
                    variant="sam2.1_hiera_base_plus",
                    config_identifier="configs/samurai/sam2.1_hiera_b+.yaml",
                    device="cpu",
                    timeout_sec=10.0,
                    working_directory=REPO_ROOT,
                )
            )
            frames = np.zeros((2, 6, 8), dtype=np.float32)
            run_input = MaskTrackerRunInput(
                tracker_kind=MaskTrackerKind.SAMURAI,
                track_id=11,
                frame_index_offset=2,
                frames=frames,
                query_box_xyxy=np.asarray([1.0, 1.0, 5.0, 5.0], dtype=np.float32),
            )

            result = backend.run(run_input)

        expected_masks = np.zeros((2, 6, 8), dtype=bool)
        expected_masks[0, 1:4, 2:5] = True
        expected_masks[1, 2:5, 3:6] = True
        self.assertEqual(result.tracker_kind, MaskTrackerKind.SAMURAI)
        self.assertEqual(result.track_id, 11)
        self.assertEqual(result.frame_index_offset, 2)
        self.assertEqual(result.model_name, "samurai")
        self.assertEqual(result.model_variant, "sam2.1_hiera_base_plus")
        self.assertEqual(result.checkpoint_name, "sam2.1_hiera_base_plus.pt")
        np.testing.assert_array_equal(result.masks, expected_masks)
        np.testing.assert_array_equal(result.visible_mask, np.asarray([True, True]))
        np.testing.assert_array_equal(result.mask_areas, np.asarray([9.0, 9.0], dtype=np.float32))
        np.testing.assert_array_equal(
            result.mask_bboxes_xyxy,
            np.asarray([[2.0, 1.0, 5.0, 4.0], [3.0, 2.0, 6.0, 5.0]], dtype=np.float32),
        )
        np.testing.assert_array_equal(result.mask_scores, np.asarray([1.0, 1.0], dtype=np.float32))
        np.testing.assert_array_equal(result.mask_component_counts, np.asarray([1, 1], dtype=np.int32))

    def test_materialization_rejects_non_samurai_input(self) -> None:
        run_input = MaskTrackerRunInput(
            tracker_kind=MaskTrackerKind.DAM4SAM,
            track_id=3,
            frame_index_offset=1,
            frames=np.zeros((1, 4, 6), dtype=np.float32),
            query_box_xyxy=np.asarray([1.0, 1.0, 3.0, 3.0], dtype=np.float32),
        )

        with TemporaryDirectory() as temp_dir:
            with self.assertRaises(ValueError):
                _materialize_samurai_inputs(run_input, Path(temp_dir))


_SAMURAI_SMOKE_CONFIG = _samurai_smoke_config()


@unittest.skipUnless(_SAMURAI_SMOKE_CONFIG is not None, "Default SAMURAI env/repo/checkpoint paths are not available.")
class SamuraiRuntimeSmokeTests(unittest.TestCase):
    def test_default_samurai_worker_smoke_runs_if_runtime_is_available(self) -> None:
        assert _SAMURAI_SMOKE_CONFIG is not None
        backend = MaskTrackerSubprocessBackend(_SAMURAI_SMOKE_CONFIG)
        frames = np.zeros((2, 64, 64), dtype=np.float32)
        frames[:, 20:44, 22:46] = 1.0
        run_input = MaskTrackerRunInput(
            tracker_kind=MaskTrackerKind.SAMURAI,
            track_id=1,
            frame_index_offset=0,
            frames=frames,
            query_box_xyxy=np.asarray([20.0, 18.0, 48.0, 46.0], dtype=np.float32),
        )

        result = backend.run(run_input)

        self.assertEqual(result.tracker_kind, MaskTrackerKind.SAMURAI)
        self.assertEqual(result.track_id, 1)
        self.assertEqual(result.frame_index_offset, 0)
        self.assertEqual(result.model_name, "samurai")
        self.assertEqual(result.model_variant, _SAMURAI_SMOKE_CONFIG.variant)
        self.assertEqual(result.checkpoint_name, Path(_SAMURAI_SMOKE_CONFIG.checkpoint_path).name)
        self.assertEqual(result.masks.shape, (2, 64, 64))
        self.assertEqual(result.visible_mask.shape, (2,))
        self.assertEqual(result.mask_bboxes_xyxy.shape, (2, 4))


if __name__ == "__main__":
    unittest.main()
