import tempfile
import unittest
from pathlib import Path


class MolTrackYoloDiscoveryTests(unittest.TestCase):
    def test_discovers_nanotrack_yolo_models_as_single_class_molecule_models(self) -> None:
        from moltrack.yolo import (
            MolTrackYoloModelInfo,
            default_moltrack_yolo_models_dir,
            discover_moltrack_yolo_models,
        )
        from nanotrack.yolo import default_yolo_models_dir

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "yolo11s.pt").write_bytes(b"pt")
            (root / "yolo11m.pth").write_bytes(b"pth")
            (root / "yolo11x.engine").write_bytes(b"engine")
            (root / "sidecar.json").write_text("{}", encoding="utf-8")
            (root / "nested").mkdir()
            (root / "nested" / "inner.pt").write_bytes(b"pt")

            models = discover_moltrack_yolo_models(root)

        self.assertEqual(
            [model.name for model in models],
            ["yolo11m.pth", "yolo11s.pt", "yolo11x.engine"],
        )
        self.assertTrue(all(isinstance(model, MolTrackYoloModelInfo) for model in models))
        self.assertTrue(all(model.path.is_absolute() for model in models))
        self.assertTrue(all(model.class_names == ("molecule",) for model in models))
        self.assertTrue(all(model.class_count == 1 for model in models))
        self.assertEqual(default_moltrack_yolo_models_dir(), default_yolo_models_dir())

    def test_yolo_detection_config_maps_to_nanotrack_runtime_config(self) -> None:
        from moltrack.yolo import MolTrackYoloDetectionConfig

        config = MolTrackYoloDetectionConfig(
            confidence_threshold=0.33,
            iou_threshold=0.44,
            device="cuda:0",
        )

        runtime_config = config.to_nanotrack_runtime_config()

        self.assertEqual(config.class_names, ("molecule",))
        self.assertEqual(runtime_config.default_conf_threshold, 0.33)
        self.assertEqual(runtime_config.default_iou_threshold, 0.44)
        self.assertEqual(runtime_config.device, "cuda:0")

    def test_yolo_detection_config_rejects_invalid_thresholds_and_device(self) -> None:
        from moltrack.yolo import MolTrackYoloDetectionConfig

        invalid_overrides = (
            {"confidence_threshold": -0.01},
            {"confidence_threshold": 1.01},
            {"iou_threshold": -0.01},
            {"iou_threshold": 1.01},
            {"device": " "},
            {"class_names": ("molecule", "artifact")},
            {"class_names": ()},
        )

        for overrides in invalid_overrides:
            with self.subTest(overrides=overrides):
                payload = {
                    "confidence_threshold": 0.25,
                    "iou_threshold": 0.45,
                    "device": "auto",
                    **overrides,
                }
                with self.assertRaises(ValueError):
                    MolTrackYoloDetectionConfig(**payload)


if __name__ == "__main__":
    unittest.main()
