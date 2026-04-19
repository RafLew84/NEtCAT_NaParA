import unittest
from pathlib import Path

import numpy as np

from nanotrack.sam2 import Sam2RunInput
from nanotrack.sam2.run_sam2_subprocess import (
    _build_output_from_frame_logits,
    _prepare_frames_rgb,
    _resolve_config_identifier,
)


class Sam2WorkerHelperTests(unittest.TestCase):
    def test_prepare_frames_rgb_normalizes_grayscale_frames_to_uint8_rgb(self) -> None:
        frames = np.asarray(
            [
                [[0.0, 1.0], [2.0, 3.0]],
                [[10.0, 10.0], [10.0, 10.0]],
            ],
            dtype=np.float32,
        )

        frames_rgb = _prepare_frames_rgb(frames)

        self.assertEqual(frames_rgb.shape, (2, 2, 2, 3))
        self.assertEqual(frames_rgb.dtype, np.uint8)
        np.testing.assert_array_equal(frames_rgb[0, :, :, 0], np.asarray([[0, 85], [170, 255]], dtype=np.uint8))
        np.testing.assert_array_equal(frames_rgb[0, :, :, 1], frames_rgb[0, :, :, 0])
        np.testing.assert_array_equal(frames_rgb[1], np.zeros((2, 2, 3), dtype=np.uint8))

    def test_resolve_config_identifier_uses_checkpoint_mapping(self) -> None:
        config_identifier = _resolve_config_identifier(
            config_path=None,
            repo_path=Path("/tmp/sam2"),
            checkpoint_path=Path("sam2.1_hiera_small.pt"),
        )

        self.assertEqual(config_identifier, "configs/sam2.1/sam2.1_hiera_s.yaml")

    def test_build_output_from_frame_logits_parses_masks_and_summary(self) -> None:
        logits_frame0 = np.full((4, 5), -10.0, dtype=np.float32)
        logits_frame0[1:3, 2:4] = 10.0
        logits_frame2 = np.full((4, 5), -10.0, dtype=np.float32)
        logits_frame2[0, 1] = 10.0

        run_output = _build_output_from_frame_logits(
            track_id=8,
            frame_index_offset=12,
            frame_logits={
                0: logits_frame0,
                2: logits_frame2,
            },
            frame_count=3,
            frame_shape=(4, 5),
        )

        self.assertEqual(run_output.track_id, 8)
        self.assertEqual(run_output.frame_index_offset, 12)
        self.assertTrue(run_output.visible_mask[0])
        self.assertFalse(run_output.visible_mask[1])
        self.assertTrue(run_output.visible_mask[2])
        self.assertEqual(run_output.mask_areas[0], 4.0)
        self.assertEqual(run_output.mask_areas[2], 1.0)
        np.testing.assert_array_equal(
            run_output.mask_bboxes_xyxy[0],
            np.asarray([2.0, 1.0, 4.0, 3.0], dtype=np.float32),
        )
        np.testing.assert_array_equal(
            run_output.mask_bboxes_xyxy[2],
            np.asarray([1.0, 0.0, 2.0, 1.0], dtype=np.float32),
        )
        self.assertGreater(run_output.mask_scores[0], 0.99)
        self.assertEqual(run_output.mask_component_counts[1], 0)
        self.assertEqual(run_output.mask_component_counts[2], 1)

    def test_build_output_from_frame_logits_rejects_wrong_shape(self) -> None:
        with self.assertRaises(ValueError):
            _build_output_from_frame_logits(
                track_id=1,
                frame_index_offset=0,
                frame_logits={0: np.zeros((2, 2), dtype=np.float32)},
                frame_count=1,
                frame_shape=(3, 3),
            )

    def test_run_input_with_point_prompt_can_target_later_local_frame(self) -> None:
        run_input = Sam2RunInput(
            track_id=4,
            frame_index_offset=5,
            frames=np.zeros((4, 6, 7), dtype=np.float32),
            query_point_tyx=np.asarray([2.0, 3.0, 4.0], dtype=np.float32),
        )

        self.assertEqual(int(run_input.query_point_tyx[0]), 2)


if __name__ == "__main__":
    unittest.main()
