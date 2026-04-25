import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from nanotrack.edges.run_ddn_subprocess import (
    _frame_to_rgb_uint8,
    _load_yaml_config,
    _normalize_prob_map,
    _prepare_frame_tensor,
    _resolve_inference_shape,
    _resolve_polygon_bbox,
    _resolve_repo_root,
)


class DdnWorkerHelperTests(unittest.TestCase):
    def test_resolve_polygon_bbox_returns_minimal_xy_bounds(self) -> None:
        polygon_mask = np.zeros((6, 8), dtype=bool)
        polygon_mask[1:5, 2:7] = True

        bbox = _resolve_polygon_bbox(polygon_mask)

        self.assertEqual(bbox, (1, 5, 2, 7))

    def test_resolve_inference_shape_rounds_up_to_multiple_of_32(self) -> None:
        resolved = _resolve_inference_shape((19, 34), inference_resolution_hw=None)
        self.assertEqual(resolved, (32, 64))

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

    def test_prepare_frame_tensor_crops_roi_and_scales_to_zero_one(self) -> None:
        polygon_mask = np.ones((2, 2), dtype=bool)
        bbox = _resolve_polygon_bbox(polygon_mask)
        frame = np.asarray([[0.0, 1.0], [2.0, 3.0]], dtype=np.float32)

        chw_frame, source_hw, target_hw = _prepare_frame_tensor(
            frame,
            polygon_bbox=bbox,
            inference_resolution_hw=np.asarray([2, 2], dtype=np.int32),
        )

        expected = np.asarray([[0.0, 1.0 / 3.0], [2.0 / 3.0, 1.0]], dtype=np.float32)
        self.assertEqual(source_hw, (2, 2))
        self.assertEqual(target_hw, (2, 2))
        self.assertEqual(chw_frame.shape, (3, 2, 2))
        self.assertEqual(chw_frame.dtype, np.float32)
        np.testing.assert_allclose(chw_frame[0], expected, atol=1e-6)
        np.testing.assert_allclose(chw_frame[1], expected, atol=1e-6)
        np.testing.assert_allclose(chw_frame[2], expected, atol=1e-6)

    def test_prepare_frame_tensor_supports_multichannel_input(self) -> None:
        polygon_mask = np.zeros((5, 6), dtype=bool)
        polygon_mask[1:4, 1:5] = True
        bbox = _resolve_polygon_bbox(polygon_mask)
        frame = np.zeros((5, 6, 3), dtype=np.float32)
        frame[..., 0] = 1.0
        frame[..., 1] = 2.0
        frame[..., 2] = 3.0

        chw_frame, source_hw, target_hw = _prepare_frame_tensor(
            frame,
            polygon_bbox=bbox,
            inference_resolution_hw=None,
        )

        self.assertEqual(source_hw, (3, 4))
        self.assertEqual(target_hw, (32, 32))
        self.assertEqual(chw_frame.shape, (3, 32, 32))

    def test_normalize_prob_map_scales_dynamic_range(self) -> None:
        edge_prob = np.asarray([[2.0, 4.0], [6.0, 10.0]], dtype=np.float32)

        normalized = _normalize_prob_map(edge_prob)

        expected = np.asarray([[0.0, 0.25], [0.5, 1.0]], dtype=np.float32)
        np.testing.assert_allclose(normalized, expected, atol=1e-6)

    def test_normalize_prob_map_returns_zero_for_constant_input(self) -> None:
        edge_prob = np.full((3, 4), 7.0, dtype=np.float32)

        normalized = _normalize_prob_map(edge_prob)

        np.testing.assert_array_equal(normalized, np.zeros((3, 4), dtype=np.float32))

    def test_load_yaml_config_overrides_caformer_m36_backbone(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            config_path = temp_path / "config.yaml"
            backbone_path = temp_path / "caformer_m36.pth"
            config_path.write_text(
                "ckpt:\n  caformer_m36: old-path.pth\ntrain_cfg:\n  encoder: DDN-M36\n",
                encoding="utf-8",
            )

            config = _load_yaml_config(config_path, backbone_path)

        self.assertEqual(config["ckpt"]["caformer_m36"], str(backbone_path))
        self.assertEqual(config["train_cfg"]["encoder"], "DDN-M36")

    def test_resolve_repo_root_requires_sigma_logit_unet(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            model_dir = temp_path / "model"
            model_dir.mkdir()
            (model_dir / "sigma_logit_unet.py").write_text("# test model\n", encoding="utf-8")

            resolved = _resolve_repo_root(temp_path)

        self.assertEqual(resolved, temp_path.resolve())


if __name__ == "__main__":
    unittest.main()
