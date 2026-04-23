import tempfile
import unittest
from pathlib import Path

from nanotrack.yolo import YoloModelInfo, default_yolo_models_dir, discover_yolo_models


class YoloDiscoveryTests(unittest.TestCase):
    def test_discovers_supported_model_files_and_ignores_sidecars(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "yolo11s.pt").write_bytes(b"pt")
            (root / "yolo11m.pth").write_bytes(b"pth")
            (root / "yolo11x.engine").write_bytes(b"engine")
            (root / "notes.json").write_text("{}", encoding="utf-8")
            (root / "nested").mkdir()
            (root / "nested" / "inner.pt").write_bytes(b"pt")

            models = discover_yolo_models(root)

        self.assertEqual(
            [model.name for model in models],
            ["yolo11m.pth", "yolo11s.pt", "yolo11x.engine"],
        )
        self.assertTrue(all(isinstance(model, YoloModelInfo) for model in models))
        self.assertTrue(all(model.path.is_absolute() for model in models))

    def test_returns_empty_list_for_missing_directory(self) -> None:
        models = discover_yolo_models("/tmp/definitely_missing_nanotrack_yolo_models")

        self.assertEqual(models, [])

    def test_default_models_dir_points_to_repo_yolo_models_directory(self) -> None:
        models_dir = default_yolo_models_dir()

        self.assertEqual(models_dir.name, "yolo_models")
        self.assertEqual(models_dir.parent.name, "nanotrack")


if __name__ == "__main__":
    unittest.main()
