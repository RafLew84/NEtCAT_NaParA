import tempfile
import unittest
from pathlib import Path

import numpy as np

from moltrack.core import MolecularDetection
from moltrack.yolo import MolTrackYoloDetector, MolTrackYoloError, YoloModelInfo, discover_yolo_models
from nanotrack.core import BBoxXYXY
from nanotrack.yolo import YoloRuntimeDetection


class MolTrackYoloAdapterTests(unittest.TestCase):
    def test_discovers_yolo_checkpoints_like_nanotrack(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "z-last.engine").write_bytes(b"engine")
            (root / "a-first.pt").write_bytes(b"pt")
            (root / "middle.onnx").write_bytes(b"onnx")
            (root / "notes.txt").write_text("ignore", encoding="utf-8")
            (root / "nested").mkdir()
            (root / "nested" / "ignored.pt").write_bytes(b"pt")

            models = discover_yolo_models(root)

        self.assertEqual([model.name for model in models], ["a-first.pt", "middle.onnx", "z-last.engine"])
        self.assertTrue(all(isinstance(model, YoloModelInfo) for model in models))
        self.assertTrue(all(model.path.is_absolute() for model in models))

    def test_detector_maps_runtime_detections_to_molecular_detections(self) -> None:
        class FakeRuntime:
            def __init__(self):
                self.calls = []

            def predict_frame(self, frame, *, model_path, conf_threshold, iou_threshold):
                self.calls.append(
                    {
                        "frame": np.asarray(frame).copy(),
                        "model_path": model_path,
                        "conf_threshold": conf_threshold,
                        "iou_threshold": iou_threshold,
                    }
                )
                return [
                    YoloRuntimeDetection(
                        bbox=BBoxXYXY(1.0, 2.0, 5.0, 7.0),
                        confidence=0.91,
                        model_name=Path(model_path).name,
                    )
                ]

        runtime = FakeRuntime()
        detector = MolTrackYoloDetector(runtime=runtime)
        frame = np.arange(64, dtype=np.float32).reshape(8, 8)

        detections = detector.detect_frame(
            frame,
            frame_index=3,
            checkpoint_path="C:/models/molecules.pt",
            confidence_threshold=0.3,
            iou_threshold=0.4,
            source_view="expanded_aligned",
        )

        self.assertEqual(len(detections), 1)
        self.assertTrue(all(isinstance(detection, MolecularDetection) for detection in detections))
        self.assertEqual(detections[0].frame_index, 3)
        self.assertEqual(detections[0].bbox_xyxy, (1.0, 2.0, 5.0, 7.0))
        self.assertEqual(detections[0].confidence, 0.91)
        self.assertTrue(detections[0].selected)
        self.assertEqual(detections[0].model_name, "molecules.pt")
        self.assertEqual(detections[0].checkpoint_path, "C:/models/molecules.pt")
        self.assertEqual(detections[0].source_view, "expanded_aligned")
        self.assertEqual(runtime.calls[0]["model_path"], "C:/models/molecules.pt")
        self.assertEqual(runtime.calls[0]["conf_threshold"], 0.3)
        self.assertEqual(runtime.calls[0]["iou_threshold"], 0.4)
        np.testing.assert_array_equal(runtime.calls[0]["frame"], frame)

    def test_detector_reports_missing_checkpoint_with_moltrack_error(self) -> None:
        detector = MolTrackYoloDetector()
        frame = np.zeros((8, 8), dtype=np.float32)

        with self.assertRaisesRegex(MolTrackYoloError, "YOLO checkpoint does not exist"):
            detector.detect_frame(
                frame,
                frame_index=0,
                checkpoint_path="/tmp/definitely_missing_moltrack_yolo_model.pt",
            )

    def test_detector_maps_multiple_frames_to_per_frame_molecular_detections(self) -> None:
        class FakeRuntime:
            def __init__(self):
                self.calls = []

            def predict_frames(self, frames, *, model_path, conf_threshold, iou_threshold):
                self.calls.append((np.asarray(frames).shape, model_path, conf_threshold, iou_threshold))
                return [
                    [
                        YoloRuntimeDetection(
                            bbox=BBoxXYXY(0.0, 0.0, 2.0, 2.0),
                            confidence=0.6,
                            model_name=Path(model_path).name,
                        )
                    ],
                    [
                        YoloRuntimeDetection(
                            bbox=BBoxXYXY(1.0, 1.0, 3.0, 3.0),
                            confidence=0.7,
                            model_name=Path(model_path).name,
                        )
                    ],
                ]

        runtime = FakeRuntime()
        detector = MolTrackYoloDetector(runtime=runtime)
        frames = np.zeros((2, 4, 4), dtype=np.float32)

        detections_by_frame = detector.detect_frames(
            frames,
            frame_indices=[4, 5],
            checkpoint_path="model.pt",
            confidence_threshold=0.2,
            iou_threshold=0.5,
            source_view="raw",
        )

        self.assertEqual(runtime.calls, [((2, 4, 4), "model.pt", 0.2, 0.5)])
        self.assertEqual([[detection.frame_index for detection in frame] for frame in detections_by_frame], [[4], [5]])
        self.assertEqual(detections_by_frame[0][0].bbox_xyxy, (0.0, 0.0, 2.0, 2.0))
        self.assertEqual(detections_by_frame[1][0].bbox_xyxy, (1.0, 1.0, 3.0, 3.0))


if __name__ == "__main__":
    unittest.main()
