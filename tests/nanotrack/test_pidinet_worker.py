import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from nanotrack.edges.run_pidinet_subprocess import (
    PIDINET_RGB_MEAN,
    PIDINET_RGB_STD,
    _frame_to_rgb_uint8,
    _prepare_frame_tensor,
    _resolve_inference_shape,
    _resolve_polygon_bbox,
    _resolve_repo_root,
    _strip_module_prefix,
)


class PidinetWorkerHelperTests(unittest.TestCase):
    def test_resolve_polygon_bbox_returns_minimal_xy_bounds(self) -> None:
        polygon_mask = np.zeros((6, 8), dtype=bool)
        polygon_mask[1:5, 2:7] = True

        bbox = _resolve_polygon_bbox(polygon_mask)

        self.assertEqual(bbox, (1, 5, 2, 7))

    def test_resolve_inference_shape_rounds_up_to_multiple_of_8(self) -> None:
        resolved = _resolve_inference_shape((19, 34), inference_resolution_hw=None)
        self.assertEqual(resolved, (24, 40))

    def test_resolve_inference_shape_uses_explicit_resolution_when_provided(self) -> None:
        resolved = _resolve_inference_shape((19, 34), inference_resolution_hw=np.asarray([256, 384]))
        self.assertEqual(resolved, (256, 384))

    def test_frame_to_rgb_uint8_expands_grayscale_frame(self) -> None:
        frame = np.asarray([[0.0, 1.0], [2.0, 3.0]], dtype=np.float32)

        rgb = _frame_to_rgb_uint8(frame)

        self.assertEqual(rgb.shape, (2, 2, 3))
        self.assertEqual(rgb.dtype, np.uint8)
        np.testing.assert_array_equal(rgb[..., 0], np.asarray([[0, 85], [170, 255]], dtype=np.uint8))
        np.testing.assert_array_equal(rgb[..., 1], rgb[..., 0])
        np.testing.assert_array_equal(rgb[..., 2], rgb[..., 0])

    def test_prepare_frame_tensor_crops_roi_and_applies_pidinet_imagenet_normalization(self) -> None:
        polygon_mask = np.ones((2, 2), dtype=bool)
        bbox = _resolve_polygon_bbox(polygon_mask)
        frame = np.asarray([[0.0, 1.0], [2.0, 3.0]], dtype=np.float32)

        chw_frame, source_hw, target_hw = _prepare_frame_tensor(
            frame,
            polygon_bbox=bbox,
            inference_resolution_hw=np.asarray([2, 2], dtype=np.int32),
        )

        normalized_gray = np.asarray([[0.0, 85.0], [170.0, 255.0]], dtype=np.float32) / 255.0
        expected = (normalized_gray[None, :, :] - PIDINET_RGB_MEAN[:, None, None]) / PIDINET_RGB_STD[:, None, None]
        self.assertEqual(source_hw, (2, 2))
        self.assertEqual(target_hw, (2, 2))
        self.assertEqual(chw_frame.shape, (3, 2, 2))
        self.assertEqual(chw_frame.dtype, np.float32)
        np.testing.assert_allclose(chw_frame, expected, atol=1e-6)

    def test_prepare_frame_tensor_supports_multichannel_input(self) -> None:
        polygon_mask = np.zeros((5, 6), dtype=bool)
        polygon_mask[1:4, 1:5] = True
        bbox = _resolve_polygon_bbox(polygon_mask)
        frame = np.zeros((5, 6, 3), dtype=np.float32)
        frame[..., 0] = np.arange(6, dtype=np.float32)[None, :]
        frame[..., 1] = np.arange(5, dtype=np.float32)[:, None]
        frame[..., 2] = 1.0

        chw_frame, source_hw, target_hw = _prepare_frame_tensor(
            frame,
            polygon_bbox=bbox,
            inference_resolution_hw=None,
        )

        self.assertEqual(source_hw, (3, 4))
        self.assertEqual(target_hw, (8, 8))
        self.assertEqual(chw_frame.shape, (3, 8, 8))

    def test_strip_module_prefix_removes_dataparallel_prefix(self) -> None:
        state_dict = {
            "module.init_block.weight": np.asarray([1.0], dtype=np.float32),
            "classifier.bias": np.asarray([2.0], dtype=np.float32),
        }

        stripped = _strip_module_prefix(state_dict)

        self.assertIn("init_block.weight", stripped)
        self.assertIn("classifier.bias", stripped)
        self.assertNotIn("module.init_block.weight", stripped)
        self.assertIn("module.init_block.weight", state_dict)

    def test_resolve_repo_root_requires_pidinet_files(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            models_dir = temp_path / "models"
            models_dir.mkdir()
            (models_dir / "pidinet.py").write_text("# test model\n", encoding="utf-8")
            (models_dir / "convert_pidinet.py").write_text("# test converter\n", encoding="utf-8")

            resolved = _resolve_repo_root(temp_path)

        self.assertEqual(resolved, temp_path.resolve())

    def test_resolve_repo_root_rejects_incomplete_pidinet_repo(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            models_dir = temp_path / "models"
            models_dir.mkdir()
            (models_dir / "pidinet.py").write_text("# test model\n", encoding="utf-8")

            with self.assertRaises(FileNotFoundError) as exc_info:
                _resolve_repo_root(temp_path)

        self.assertIn("models/convert_pidinet.py", str(exc_info.exception).replace("\\", "/"))


if __name__ == "__main__":
    unittest.main()
