import unittest

import numpy as np

from nanotrack.edges import DexiNedRunInput
from nanotrack.edges.run_dexined_subprocess import (
    _frame_to_rgb_uint8,
    _prepare_frame_tensor,
    _resolve_inference_shape,
    _resolve_polygon_bbox,
)


class DexiNedWorkerHelperTests(unittest.TestCase):
    def test_resolve_polygon_bbox_returns_minimal_xy_bounds(self) -> None:
        polygon_mask = np.zeros((6, 8), dtype=bool)
        polygon_mask[1:5, 2:7] = True

        bbox = _resolve_polygon_bbox(polygon_mask)

        self.assertEqual(bbox, (1, 5, 2, 7))

    def test_resolve_inference_shape_rounds_up_to_multiple_of_16(self) -> None:
        resolved = _resolve_inference_shape((19, 34), inference_resolution_hw=None)
        self.assertEqual(resolved, (32, 48))

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

    def test_prepare_frame_tensor_crops_roi_and_subtracts_mean(self) -> None:
        polygon_mask = np.zeros((6, 8), dtype=bool)
        polygon_mask[1:5, 2:7] = True
        bbox = _resolve_polygon_bbox(polygon_mask)
        frame = np.arange(6 * 8, dtype=np.float32).reshape(6, 8)

        chw_frame, source_hw, target_hw = _prepare_frame_tensor(
            frame,
            polygon_bbox=bbox,
            inference_resolution_hw=np.asarray([16, 32], dtype=np.int32),
        )

        self.assertEqual(source_hw, (4, 5))
        self.assertEqual(target_hw, (16, 32))
        self.assertEqual(chw_frame.shape, (3, 16, 32))
        self.assertEqual(chw_frame.dtype, np.float32)

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
        self.assertEqual(target_hw, (16, 16))
        self.assertEqual(chw_frame.shape, (3, 16, 16))


if __name__ == "__main__":
    unittest.main()
