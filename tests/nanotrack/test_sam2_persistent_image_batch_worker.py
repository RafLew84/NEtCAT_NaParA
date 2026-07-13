import sys
import textwrap
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from nanotrack.sam2 import (
    DEFAULT_SAM2_PERSISTENT_IMAGE_BATCH_WORKER_SCRIPT,
    Sam2ImageBatchInput,
    Sam2PersistentImageBatchBackend,
    Sam2PersistentImageBatchBackendConfig,
)


def _write_fake_sam2_repo(
    repo_path: Path,
    *,
    require_inference_mode: bool = False,
    expected_device: str = "cpu",
    fake_cuda_runtime: bool = False,
) -> Path:
    package_path = repo_path / "sam2"
    package_path.mkdir(parents=True)
    (package_path / "__init__.py").write_text("", encoding="utf-8")
    events_path = repo_path / "events.txt"
    build_source = textwrap.dedent(
            """
            from pathlib import Path

            EVENTS = Path(__file__).resolve().parents[1] / "events.txt"
            EXPECTED_DEVICE = __EXPECTED_DEVICE__

            def build_sam2(config_identifier, checkpoint_path, **kwargs):
                assert config_identifier == "configs/fake.yaml"
                assert checkpoint_path == "selected-checkpoint.pt"
                assert kwargs["device"] == EXPECTED_DEVICE
                with EVENTS.open("a", encoding="utf-8") as stream:
                    stream.write("build_model\\n")
                return object()
            """
        ).replace("__EXPECTED_DEVICE__", repr(expected_device))
    (package_path / "build_sam.py").write_text(
        build_source,
        encoding="utf-8",
    )
    predictor_source = textwrap.dedent(
            """
            from pathlib import Path
            import numpy as np

            EVENTS = Path(__file__).resolve().parents[1] / "events.txt"
            REQUIRE_INFERENCE_MODE = __REQUIRE_INFERENCE_MODE__
            REQUIRE_CUDA_RUNTIME = __REQUIRE_CUDA_RUNTIME__

            def assert_inference_mode():
                if not REQUIRE_INFERENCE_MODE:
                    return
                import torch
                if not torch.is_inference_mode_enabled():
                    raise RuntimeError("persistent worker inference mode is disabled")

            def assert_cuda_runtime():
                if not REQUIRE_CUDA_RUNTIME:
                    return
                import torch
                if not torch.autocast_is_active():
                    raise RuntimeError("persistent worker CUDA autocast is disabled")
                if torch.autocast_dtype() != torch.bfloat16:
                    raise RuntimeError("persistent worker CUDA autocast is not bfloat16")
                if not torch.backends.cuda.matmul.allow_tf32:
                    raise RuntimeError("persistent worker matmul TF32 is disabled")
                if not torch.backends.cudnn.allow_tf32:
                    raise RuntimeError("persistent worker cudnn TF32 is disabled")

            class SAM2ImagePredictor:
                def __init__(self, model):
                    self.frame_shape = None
                    with EVENTS.open("a", encoding="utf-8") as stream:
                        stream.write("create_predictor\\n")

                def set_image(self, image):
                    assert_inference_mode()
                    assert_cuda_runtime()
                    self.frame_shape = image.shape[:2]
                    with EVENTS.open("a", encoding="utf-8") as stream:
                        stream.write(f"set_image:{image.shape[0]}x{image.shape[1]}\\n")

                def predict(self, *, box, multimask_output, return_logits):
                    assert_inference_mode()
                    assert_cuda_runtime()
                    boxes = np.asarray(box, dtype=np.float32).reshape(-1, 4)
                    with EVENTS.open("a", encoding="utf-8") as stream:
                        stream.write(f"predict:{len(boxes)}\\n")
                    height, width = self.frame_shape
                    logits = np.full((len(boxes), 1, height, width), -10.0, dtype=np.float32)
                    for index, (x1, y1, x2, y2) in enumerate(boxes.astype(int)):
                        logits[index, 0, y1:y2, x1:x2] = 10.0
                    if len(boxes) == 1:
                        logits = logits[0]
                    return (
                        logits,
                        np.ones((len(boxes), 1), dtype=np.float32),
                        np.zeros((len(boxes), 1, 2, 2), dtype=np.float32),
                    )
            """
        ).replace("__REQUIRE_INFERENCE_MODE__", repr(require_inference_mode)).replace(
            "__REQUIRE_CUDA_RUNTIME__",
            repr(fake_cuda_runtime),
        )
    (package_path / "sam2_image_predictor.py").write_text(
        predictor_source,
        encoding="utf-8",
    )
    if fake_cuda_runtime:
        (repo_path / "torch.py").write_text(
            textwrap.dedent(
                """
                from pathlib import Path
                from types import SimpleNamespace

                EVENTS = Path(__file__).resolve().parent / "events.txt"
                bfloat16 = "bfloat16"
                _inference_active = False
                _autocast_active = False
                _autocast_dtype = None

                class _Device:
                    def __init__(self, name):
                        self.name = str(name)
                        self.index = 0 if self.name.startswith("cuda") else None
                    def __str__(self):
                        return self.name

                def device(name):
                    return _Device(name)

                class _Context:
                    def __init__(self, kind, dtype=None):
                        self.kind = kind
                        self.dtype = dtype
                    def __enter__(self):
                        global _inference_active, _autocast_active, _autocast_dtype
                        if self.kind == "inference":
                            _inference_active = True
                        else:
                            _autocast_active = True
                            _autocast_dtype = self.dtype
                        return self
                    def __exit__(self, exc_type, exc_value, traceback):
                        global _inference_active, _autocast_active, _autocast_dtype
                        if self.kind == "inference":
                            _inference_active = False
                        else:
                            _autocast_active = False
                            _autocast_dtype = None

                def inference_mode():
                    return _Context("inference")

                def is_inference_mode_enabled():
                    return _inference_active

                def autocast(device_type, dtype):
                    if device_type != "cuda" or dtype != bfloat16:
                        raise RuntimeError("unexpected autocast configuration")
                    return _Context("autocast", dtype)

                def autocast_is_active():
                    return _autocast_active

                def autocast_dtype():
                    return _autocast_dtype

                class OutOfMemoryError(RuntimeError):
                    pass

                class _Cuda:
                    OutOfMemoryError = OutOfMemoryError
                    def is_available(self):
                        return True
                    def set_device(self, index):
                        with EVENTS.open("a", encoding="utf-8") as stream:
                            stream.write(f"set_device:{index}\\n")
                    def get_device_properties(self, device):
                        return SimpleNamespace(major=8)
                    def mem_get_info(self):
                        return (7 * 1024**3, 8 * 1024**3)
                    def empty_cache(self):
                        pass
                    def reset_peak_memory_stats(self, device):
                        with EVENTS.open("a", encoding="utf-8") as stream:
                            stream.write("reset_peak_vram\\n")
                    def memory_allocated(self, device):
                        return 1234
                    def max_memory_allocated(self, device):
                        return 5678

                cuda = _Cuda()
                backends = SimpleNamespace(
                    cuda=SimpleNamespace(matmul=SimpleNamespace(allow_tf32=False)),
                    cudnn=SimpleNamespace(allow_tf32=False),
                )
                """
            ),
            encoding="utf-8",
        )
    return events_path


class Sam2PersistentImageBatchWorkerTests(unittest.TestCase):
    def test_real_worker_loads_model_once_for_multiple_frames(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            fake_repo = temp_path / "fake-sam2-repo"
            events_path = _write_fake_sam2_repo(fake_repo)
            backend = Sam2PersistentImageBatchBackend(
                Sam2PersistentImageBatchBackendConfig(
                    python_executable=sys.executable,
                    worker_script=DEFAULT_SAM2_PERSISTENT_IMAGE_BATCH_WORKER_SCRIPT,
                    checkpoint_path="selected-checkpoint.pt",
                    repo_path=fake_repo,
                    config_path="configs/fake.yaml",
                    device="cpu",
                    startup_timeout_sec=10.0,
                    frame_timeout_sec=10.0,
                )
            )
            first_input = Sam2ImageBatchInput(
                frame=np.arange(48, dtype=np.float32).reshape(6, 8),
                frame_index=3,
                source_view="raw",
                boxes_xyxy=np.asarray(
                    ((1.0, 1.0, 4.0, 4.0), (4.0, 2.0, 7.0, 5.0)),
                    dtype=np.float32,
                ),
                prompt_detection_ids=("bbox-a", "bbox-b"),
                chunk_size=1,
            )
            second_input = Sam2ImageBatchInput(
                frame=np.arange(35, dtype=np.float32).reshape(5, 7),
                frame_index=4,
                source_view="raw",
                boxes_xyxy=np.asarray(((2.0, 1.0, 6.0, 4.0),), dtype=np.float32),
                prompt_detection_ids=("bbox-c",),
                chunk_size=1,
            )

            with backend.open_session() as session:
                first = session.segment_frame(first_input)
                second = session.segment_frame(second_input)

            self.assertEqual(first.prompt_detection_ids, ("bbox-a", "bbox-b"))
            self.assertEqual(first.masks.shape, (2, 6, 8))
            self.assertEqual(second.prompt_detection_ids, ("bbox-c",))
            self.assertEqual(second.masks.shape, (1, 5, 7))
            self.assertEqual(
                events_path.read_text(encoding="utf-8").splitlines(),
                [
                    "build_model",
                    "create_predictor",
                    "set_image:6x8",
                    "predict:1",
                    "predict:1",
                    "set_image:5x7",
                    "predict:1",
                ],
            )

    def test_empty_frame_returns_empty_result_without_creating_embedding(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            fake_repo = temp_path / "fake-sam2-repo"
            events_path = _write_fake_sam2_repo(fake_repo)
            backend = Sam2PersistentImageBatchBackend(
                Sam2PersistentImageBatchBackendConfig(
                    python_executable=sys.executable,
                    worker_script=DEFAULT_SAM2_PERSISTENT_IMAGE_BATCH_WORKER_SCRIPT,
                    checkpoint_path="selected-checkpoint.pt",
                    repo_path=fake_repo,
                    config_path="configs/fake.yaml",
                    device="cpu",
                    startup_timeout_sec=10.0,
                    frame_timeout_sec=10.0,
                )
            )
            empty_input = Sam2ImageBatchInput(
                frame=np.zeros((4, 5), dtype=np.float32),
                frame_index=8,
                source_view="raw",
                boxes_xyxy=np.empty((0, 4), dtype=np.float32),
                prompt_detection_ids=(),
            )

            with backend.open_session() as session:
                result = session.segment_frame(empty_input)

            self.assertEqual(result.result_count, 0)
            self.assertEqual(result.masks.shape, (0, 4, 5))
            self.assertEqual(
                events_path.read_text(encoding="utf-8").splitlines(),
                ["build_model", "create_predictor"],
            )

    def test_nonempty_frame_runs_predictor_inside_torch_inference_mode(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            fake_repo = temp_path / "fake-sam2-repo"
            _write_fake_sam2_repo(fake_repo, require_inference_mode=True)
            backend = Sam2PersistentImageBatchBackend(
                Sam2PersistentImageBatchBackendConfig(
                    python_executable=sys.executable,
                    worker_script=DEFAULT_SAM2_PERSISTENT_IMAGE_BATCH_WORKER_SCRIPT,
                    checkpoint_path="selected-checkpoint.pt",
                    repo_path=fake_repo,
                    config_path="configs/fake.yaml",
                    device="cpu",
                    startup_timeout_sec=10.0,
                    frame_timeout_sec=10.0,
                )
            )
            run_input = Sam2ImageBatchInput(
                frame=np.zeros((4, 5), dtype=np.float32),
                frame_index=9,
                source_view="raw",
                boxes_xyxy=np.asarray(((1.0, 1.0, 4.0, 3.0),), dtype=np.float32),
                prompt_detection_ids=("bbox-inference",),
            )

            with backend.open_session() as session:
                result = session.segment_frame(run_input)

            self.assertEqual(result.prompt_detection_ids, ("bbox-inference",))

    def test_frame_result_reports_current_host_ram_and_peak_vram(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            fake_repo = temp_path / "fake-sam2-repo"
            _write_fake_sam2_repo(fake_repo)
            backend = Sam2PersistentImageBatchBackend(
                Sam2PersistentImageBatchBackendConfig(
                    python_executable=sys.executable,
                    worker_script=DEFAULT_SAM2_PERSISTENT_IMAGE_BATCH_WORKER_SCRIPT,
                    checkpoint_path="selected-checkpoint.pt",
                    repo_path=fake_repo,
                    config_path="configs/fake.yaml",
                    device="cpu",
                    startup_timeout_sec=10.0,
                    frame_timeout_sec=10.0,
                )
            )
            run_input = Sam2ImageBatchInput(
                frame=np.zeros((4, 5), dtype=np.float32),
                frame_index=12,
                source_view="raw",
                boxes_xyxy=np.asarray(((1.0, 1.0, 4.0, 3.0),), dtype=np.float32),
                prompt_detection_ids=("bbox-memory",),
            )

            with backend.open_session() as session:
                session.segment_frame(run_input)
                diagnostics = session.last_diagnostics

            self.assertIsNotNone(diagnostics)
            assert diagnostics is not None
            self.assertGreaterEqual(diagnostics.host_rss_bytes, 0)
            self.assertGreaterEqual(
                diagnostics.peak_host_rss_bytes,
                diagnostics.host_rss_bytes,
            )
            self.assertEqual(diagnostics.current_vram_bytes, 0)
            self.assertEqual(diagnostics.peak_vram_bytes, 0)

    def test_cuda_frame_uses_bfloat16_autocast_tf32_and_reports_vram(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            fake_repo = temp_path / "fake-sam2-repo"
            events_path = _write_fake_sam2_repo(
                fake_repo,
                require_inference_mode=True,
                expected_device="cuda:0",
                fake_cuda_runtime=True,
            )
            backend = Sam2PersistentImageBatchBackend(
                Sam2PersistentImageBatchBackendConfig(
                    python_executable=sys.executable,
                    worker_script=DEFAULT_SAM2_PERSISTENT_IMAGE_BATCH_WORKER_SCRIPT,
                    checkpoint_path="selected-checkpoint.pt",
                    repo_path=fake_repo,
                    config_path="configs/fake.yaml",
                    device="cuda:0",
                    startup_timeout_sec=10.0,
                    frame_timeout_sec=10.0,
                )
            )
            run_input = Sam2ImageBatchInput(
                frame=np.zeros((4, 5), dtype=np.float32),
                frame_index=13,
                source_view="raw",
                boxes_xyxy=np.asarray(((1.0, 1.0, 4.0, 3.0),), dtype=np.float32),
                prompt_detection_ids=("bbox-cuda",),
            )

            with backend.open_session() as session:
                result = session.segment_frame(run_input)
                diagnostics = session.last_diagnostics

            self.assertEqual(result.prompt_detection_ids, ("bbox-cuda",))
            self.assertIsNotNone(diagnostics)
            assert diagnostics is not None
            self.assertEqual(diagnostics.current_vram_bytes, 1234)
            self.assertEqual(diagnostics.peak_vram_bytes, 5678)
            events = events_path.read_text(encoding="utf-8").splitlines()
            self.assertIn("set_device:0", events)
            self.assertIn("reset_peak_vram", events)


if __name__ == "__main__":
    unittest.main()
