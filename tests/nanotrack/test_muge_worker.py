import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from nanotrack.edges.contract import DexiNedRunInput
from nanotrack.edges import run_muge_subprocess as worker
from nanotrack.edges.run_muge_subprocess import (
    DEFAULT_GRANULARITY,
    _clip_prob_map,
    _frame_to_rgb_uint8,
    _prepare_frame_tensor,
    _resolve_granularity,
    _resolve_inference_shape,
    _resolve_polygon_bbox,
    _resolve_repo_root,
    _strip_module_prefix,
)


class MugeWorkerHelperTests(unittest.TestCase):
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

    def test_resolve_granularity_uses_default_aliases(self) -> None:
        self.assertEqual(_resolve_granularity(None), DEFAULT_GRANULARITY)
        self.assertEqual(_resolve_granularity("default"), DEFAULT_GRANULARITY)
        self.assertEqual(_resolve_granularity("medium"), DEFAULT_GRANULARITY)

    def test_resolve_granularity_supports_numeric_and_named_values(self) -> None:
        self.assertEqual(_resolve_granularity("0.25"), 0.25)
        self.assertEqual(_resolve_granularity(0.75), 0.75)
        self.assertEqual(_resolve_granularity("coarse"), 0.0)
        self.assertEqual(_resolve_granularity("fine"), 1.0)

    def test_resolve_granularity_rejects_out_of_range_values(self) -> None:
        with self.assertRaises(ValueError):
            _resolve_granularity("-0.1")
        with self.assertRaises(ValueError):
            _resolve_granularity("1.1")
        with self.assertRaises(ValueError):
            _resolve_granularity("nan")

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

    def test_clip_prob_map_clips_without_dynamic_renormalization(self) -> None:
        edge_prob = np.asarray([[-0.2, 0.2], [0.6, 1.4]], dtype=np.float32)

        clipped = _clip_prob_map(edge_prob)

        expected = np.asarray([[0.0, 0.2], [0.6, 1.0]], dtype=np.float32)
        np.testing.assert_allclose(clipped, expected, atol=1e-6)

    def test_strip_module_prefix_removes_dataparallel_prefix(self) -> None:
        state_dict = {
            "module.encoder.weight": np.asarray([1.0], dtype=np.float32),
            "decoder.bias": np.asarray([2.0], dtype=np.float32),
        }

        stripped = _strip_module_prefix(state_dict)

        self.assertIn("encoder.weight", stripped)
        self.assertIn("decoder.bias", stripped)
        self.assertNotIn("module.encoder.weight", stripped)
        self.assertIn("module.encoder.weight", state_dict)

    def test_resolve_repo_root_requires_muge_model_file(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            model_dir = temp_path / "model"
            model_dir.mkdir()
            (model_dir / "sigma_logit_unetpp_alpha_ffthalf_feat.py").write_text("# test model\n", encoding="utf-8")

            resolved = _resolve_repo_root(temp_path)

        self.assertEqual(resolved, temp_path.resolve())

    def test_resolve_repo_root_rejects_incomplete_muge_repo(self) -> None:
        with TemporaryDirectory() as temp_dir:
            with self.assertRaises(FileNotFoundError) as exc_info:
                _resolve_repo_root(temp_dir)

        self.assertIn("sigma_logit_unetpp_alpha_ffthalf_feat.py", str(exc_info.exception))

    def test_run_real_inference_uses_granularity_and_common_contract(self) -> None:
        polygon_mask = np.zeros((4, 5), dtype=bool)
        polygon_mask[1:3, 2:5] = True
        frames = np.arange(20, dtype=np.float32).reshape(1, 4, 5)
        run_input = DexiNedRunInput(
            frames=frames,
            polygon_mask=polygon_mask,
            inference_resolution_hw=np.asarray([2, 3], dtype=np.int32),
            threshold=0.6,
        )
        crop_prob = np.asarray([[0.1, 0.7, 1.2], [0.6, -0.5, 0.8]], dtype=np.float32)
        observed_granularities: list[float] = []

        def fake_run_model(_model, _torch_module, _device, chw_frame, *, granularity):
            self.assertEqual(chw_frame.shape, (3, 2, 3))
            observed_granularities.append(float(granularity))
            return crop_prob

        with (
            patch.object(worker, "_load_model", return_value=(object(), SimpleNamespace(cuda=None), "cpu")),
            patch.object(worker, "_run_model_on_tensor", side_effect=fake_run_model),
        ):
            output = worker._run_real_inference(
                run_input,
                checkpoint_path=Path("muge-epoch-19-checkpoint.pth"),
                repo_root=Path("."),
                requested_device="cpu",
                distribution="gs",
                granularity=0.75,
            )

        self.assertEqual(observed_granularities, [0.75])
        self.assertEqual(output.model_name, "muge")
        self.assertEqual(output.checkpoint_name, "muge-epoch-19-checkpoint.pth")
        self.assertEqual(output.edge_prob.shape, (1, 4, 5))
        expected_frame = np.zeros((4, 5), dtype=np.float32)
        expected_frame[1:3, 2:5] = np.asarray([[0.1, 0.7, 1.0], [0.6, 0.0, 0.8]], dtype=np.float32)
        np.testing.assert_allclose(output.edge_prob[0], expected_frame, atol=1e-6)
        np.testing.assert_array_equal(output.edge_binary[0], expected_frame >= 0.6)


if __name__ == "__main__":
    unittest.main()
