import types
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from nanotrack.core import BBoxXYXY
from nanotrack.yolo import (
    YoloRuntime,
    YoloRuntimeConfig,
    YoloRuntimeModelLoadError,
    YoloRuntimeUnavailableError,
)


class _FakeBoxes:
    def __init__(self, xyxy, conf):
        self.xyxy = np.asarray(xyxy, dtype=np.float32)
        self.conf = np.asarray(conf, dtype=np.float32)


class _FakeResult:
    def __init__(self, xyxy, conf):
        self.boxes = _FakeBoxes(xyxy, conf)


class _FakeModel:
    def __init__(self, path: str):
        self.path = path
        self.calls: list[dict[str, object]] = []

    def predict(self, source, **kwargs):
        self.calls.append({"source": np.asarray(source), "kwargs": dict(kwargs)})
        return [_FakeResult([[1.0, 2.0, 11.0, 12.0]], [0.91])]


class YoloRuntimeTests(unittest.TestCase):
    def _import_side_effect(self, ultralytics_module, torch_module):
        def _side_effect(module_name: str):
            if module_name == "ultralytics":
                return ultralytics_module
            if module_name == "torch":
                return torch_module
            raise ImportError(module_name)

        return _side_effect

    def test_load_model_raises_when_ultralytics_is_missing(self) -> None:
        runtime = YoloRuntime()
        with tempfile.TemporaryDirectory() as tmpdir:
            checkpoint = Path(tmpdir) / "model.pt"
            checkpoint.write_bytes(b"weights")

            with patch("nanotrack.yolo.runtime.importlib.import_module", side_effect=ImportError("missing")):
                with self.assertRaises(YoloRuntimeUnavailableError):
                    runtime.load_model(checkpoint)

    def test_predict_frame_loads_model_converts_grayscale_and_parses_boxes(self) -> None:
        fake_model = _FakeModel("fake.pt")
        ultralytics_module = types.SimpleNamespace(YOLO=lambda _path: fake_model)
        runtime = YoloRuntime(YoloRuntimeConfig(device="cpu", default_conf_threshold=0.35, default_iou_threshold=0.4))
        frame = np.asarray([[0.0, 1.0], [2.0, 3.0]], dtype=np.float32)

        with tempfile.TemporaryDirectory() as tmpdir:
            checkpoint = Path(tmpdir) / "model.pt"
            checkpoint.write_bytes(b"weights")

            with patch("nanotrack.yolo.runtime.importlib.import_module", return_value=ultralytics_module):
                detections = runtime.predict_frame(frame, model_path=checkpoint, imgsz=640)

        self.assertEqual(len(detections), 1)
        self.assertEqual(detections[0].bbox, BBoxXYXY(1.0, 2.0, 11.0, 12.0))
        self.assertAlmostEqual(detections[0].confidence, 0.91, places=6)
        self.assertEqual(detections[0].model_name, "model.pt")
        self.assertEqual(runtime.loaded_model_path(), checkpoint.resolve())
        self.assertEqual(len(fake_model.calls), 1)
        prepared = fake_model.calls[0]["source"]
        self.assertEqual(prepared.dtype, np.uint8)
        self.assertEqual(prepared.shape, (2, 2, 3))
        self.assertEqual(fake_model.calls[0]["kwargs"]["conf"], 0.35)
        self.assertEqual(fake_model.calls[0]["kwargs"]["iou"], 0.4)
        self.assertEqual(fake_model.calls[0]["kwargs"]["device"], "cpu")
        self.assertEqual(fake_model.calls[0]["kwargs"]["imgsz"], 640)

    def test_predict_frames_reuses_loaded_model(self) -> None:
        fake_model = _FakeModel("fake.pt")
        ultralytics_module = types.SimpleNamespace(YOLO=lambda _path: fake_model)
        runtime = YoloRuntime(YoloRuntimeConfig(device="cpu"))
        frames = np.zeros((2, 4, 4), dtype=np.float32)

        with tempfile.TemporaryDirectory() as tmpdir:
            checkpoint = Path(tmpdir) / "model.pt"
            checkpoint.write_bytes(b"weights")

            with patch("nanotrack.yolo.runtime.importlib.import_module", return_value=ultralytics_module) as import_mock:
                detections_by_frame = runtime.predict_frames(frames, model_path=checkpoint)

        self.assertEqual(len(detections_by_frame), 2)
        self.assertEqual(len(detections_by_frame[0]), 1)
        self.assertEqual(len(detections_by_frame[1]), 1)
        self.assertEqual(import_mock.call_count, 1)
        self.assertEqual(len(fake_model.calls), 2)

    def test_load_model_rejects_missing_checkpoint(self) -> None:
        runtime = YoloRuntime()

        with self.assertRaises(YoloRuntimeModelLoadError):
            runtime.load_model("/tmp/definitely_missing_nanotrack_model.pt")

    def test_auto_device_resolves_to_cuda_zero(self) -> None:
        fake_model = _FakeModel("fake.pt")
        ultralytics_module = types.SimpleNamespace(YOLO=lambda _path: fake_model)
        torch_module = types.SimpleNamespace(
            cuda=types.SimpleNamespace(is_available=lambda: True),
            backends=types.SimpleNamespace(mps=types.SimpleNamespace(is_available=lambda: False)),
        )
        runtime = YoloRuntime(YoloRuntimeConfig(device="auto"))
        frame = np.zeros((8, 8), dtype=np.float32)

        with tempfile.TemporaryDirectory() as tmpdir:
            checkpoint = Path(tmpdir) / "model.pt"
            checkpoint.write_bytes(b"weights")

            with patch(
                "nanotrack.yolo.runtime.importlib.import_module",
                side_effect=self._import_side_effect(ultralytics_module, torch_module),
            ):
                runtime.predict_frame(frame, model_path=checkpoint)

        self.assertEqual(fake_model.calls[0]["kwargs"]["device"], 0)

    def test_auto_device_falls_back_to_cpu_without_cuda(self) -> None:
        fake_model = _FakeModel("fake.pt")
        ultralytics_module = types.SimpleNamespace(YOLO=lambda _path: fake_model)
        torch_module = types.SimpleNamespace(
            cuda=types.SimpleNamespace(is_available=lambda: False),
            backends=types.SimpleNamespace(mps=types.SimpleNamespace(is_available=lambda: False)),
        )
        runtime = YoloRuntime(YoloRuntimeConfig(device="auto"))
        frame = np.zeros((8, 8), dtype=np.float32)

        with tempfile.TemporaryDirectory() as tmpdir:
            checkpoint = Path(tmpdir) / "model.pt"
            checkpoint.write_bytes(b"weights")

            with patch(
                "nanotrack.yolo.runtime.importlib.import_module",
                side_effect=self._import_side_effect(ultralytics_module, torch_module),
            ):
                runtime.predict_frame(frame, model_path=checkpoint)

        self.assertEqual(fake_model.calls[0]["kwargs"]["device"], "cpu")


if __name__ == "__main__":
    unittest.main()
