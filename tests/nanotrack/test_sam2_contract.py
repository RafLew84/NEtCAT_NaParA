import unittest

import numpy as np

from nanotrack.sam2 import SAM2_CONTRACT_VERSION, Sam2RunInput, Sam2RunOutput


class Sam2RunInputTests(unittest.TestCase):
    def test_input_roundtrip_with_box_and_point_prompts(self) -> None:
        frames = np.zeros((3, 8, 10), dtype=np.float32)
        contract = Sam2RunInput(
            track_id=7,
            frame_index_offset=12,
            frames=frames,
            query_box_xyxy=np.asarray([1.0, 2.0, 6.0, 7.0], dtype=np.float32),
            query_point_tyx=np.asarray([0.0, 4.0, 5.0], dtype=np.float32),
            source_view="bm3d",
        )

        payload = contract.to_npz_payload()
        restored = Sam2RunInput.from_npz_payload(payload)

        self.assertEqual(int(payload["contract_version"]), SAM2_CONTRACT_VERSION)
        self.assertEqual(restored.track_id, 7)
        self.assertEqual(restored.frame_index_offset, 12)
        self.assertEqual(restored.source_view, "bm3d")
        np.testing.assert_array_equal(restored.frames, frames)
        np.testing.assert_array_equal(restored.query_box_xyxy, np.asarray([1.0, 2.0, 6.0, 7.0], dtype=np.float32))
        np.testing.assert_array_equal(restored.query_point_tyx, np.asarray([0.0, 4.0, 5.0], dtype=np.float32))

    def test_input_accepts_initial_mask_prompt(self) -> None:
        frames = np.zeros((2, 5, 6), dtype=np.float32)
        mask = np.zeros((5, 6), dtype=bool)
        mask[1:3, 2:4] = True

        contract = Sam2RunInput(
            track_id=2,
            frame_index_offset=3,
            frames=frames,
            initial_mask=mask,
        )

        payload = contract.to_npz_payload()
        restored = Sam2RunInput.from_npz_payload(payload)
        np.testing.assert_array_equal(restored.initial_mask, mask)

    def test_input_requires_at_least_one_prompt(self) -> None:
        with self.assertRaises(ValueError):
            Sam2RunInput(
                track_id=1,
                frame_index_offset=0,
                frames=np.zeros((2, 4, 4), dtype=np.float32),
            )


class Sam2RunOutputTests(unittest.TestCase):
    def test_output_roundtrip_preserves_masks_and_summary_vectors(self) -> None:
        masks = np.zeros((3, 5, 6), dtype=bool)
        masks[:, 1:3, 2:4] = True
        contract = Sam2RunOutput(
            track_id=11,
            frame_index_offset=9,
            masks=masks,
            visible_mask=np.asarray([True, True, False]),
            mask_areas=np.asarray([4.0, 4.0, 0.0], dtype=np.float32),
            mask_bboxes_xyxy=np.asarray(
                [
                    [2.0, 1.0, 4.0, 3.0],
                    [2.0, 1.0, 4.0, 3.0],
                    [0.0, 0.0, 0.0, 0.0],
                ],
                dtype=np.float32,
            ),
            mask_scores=np.asarray([0.9, 0.8, 0.1], dtype=np.float32),
            mask_component_counts=np.asarray([1, 1, 0], dtype=np.int32),
        )

        payload = contract.to_npz_payload()
        restored = Sam2RunOutput.from_npz_payload(payload)

        self.assertEqual(restored.track_id, 11)
        self.assertEqual(restored.frame_index_offset, 9)
        np.testing.assert_array_equal(restored.masks, masks)
        np.testing.assert_array_equal(restored.visible_mask, np.asarray([True, True, False]))
        np.testing.assert_array_equal(restored.mask_areas, np.asarray([4.0, 4.0, 0.0], dtype=np.float32))
        np.testing.assert_array_equal(restored.mask_component_counts, np.asarray([1, 1, 0], dtype=np.int32))

    def test_output_validates_summary_lengths_against_mask_count(self) -> None:
        with self.assertRaises(ValueError):
            Sam2RunOutput(
                track_id=1,
                frame_index_offset=0,
                masks=np.zeros((2, 4, 4), dtype=bool),
                visible_mask=np.asarray([True, False]),
                mask_scores=np.asarray([0.5], dtype=np.float32),
            )


if __name__ == "__main__":
    unittest.main()
