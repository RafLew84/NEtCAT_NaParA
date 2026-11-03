import tempfile
import unittest
from pathlib import Path

import numpy as np

from nanotrack.sam2 import (
    SAM2_IMAGE_BATCH_CONTRACT_VERSION,
    Sam2ImageBatchInput,
    Sam2ImageBatchOutput,
    empty_sam2_image_batch_output,
    read_sam2_image_batch_input_npz,
    read_sam2_image_batch_output_npz,
    validate_sam2_image_batch_pair,
    write_sam2_image_batch_input_npz,
    write_sam2_image_batch_output_npz,
)


class Sam2ImageBatchInputTests(unittest.TestCase):
    def test_input_npz_roundtrip_preserves_frame_boxes_and_prompt_order_without_pickle(self) -> None:
        frame = np.arange(4 * 5, dtype=np.float32).reshape(4, 5)
        boxes = np.asarray(
            (
                (0.0, 0.0, 2.0, 2.0),
                (2.0, 1.0, 5.0, 4.0),
            ),
            dtype=np.float32,
        )
        run_input = Sam2ImageBatchInput(
            frame=frame,
            frame_index=8,
            source_view="raw",
            boxes_xyxy=boxes,
            prompt_detection_ids=("bbox-first", "bbox-second"),
            mask_probability_threshold=0.65,
            chunk_size=32,
        )

        payload = run_input.to_npz_payload()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "input.npz"
            np.savez_compressed(path, **payload)
            with np.load(path, allow_pickle=False) as stored:
                restored = Sam2ImageBatchInput.from_npz_payload(
                    {key: stored[key] for key in stored.files}
                )

        self.assertEqual(int(payload["contract_version"]), SAM2_IMAGE_BATCH_CONTRACT_VERSION)
        self.assertNotEqual(payload["prompt_detection_ids"].dtype.kind, "O")
        self.assertEqual(restored.frame_index, 8)
        self.assertEqual(restored.source_view, "raw")
        self.assertEqual(restored.prompt_detection_ids, ("bbox-first", "bbox-second"))
        self.assertEqual(restored.bbox_count, 2)
        self.assertAlmostEqual(restored.mask_probability_threshold, 0.65)
        self.assertEqual(restored.chunk_size, 32)
        np.testing.assert_array_equal(restored.frame, frame)
        np.testing.assert_array_equal(restored.boxes_xyxy, boxes)

    def test_contract_rejects_counts_that_do_not_match_batch_size(self) -> None:
        with self.assertRaisesRegex(ValueError, "prompt_detection_ids length"):
            Sam2ImageBatchInput(
                frame=np.zeros((4, 5), dtype=np.float32),
                frame_index=0,
                source_view="raw",
                boxes_xyxy=np.asarray(((0, 0, 2, 2), (2, 1, 5, 4)), dtype=np.float32),
                prompt_detection_ids=("only-one-id",),
            )

        with self.assertRaisesRegex(ValueError, "mask_scores"):
            Sam2ImageBatchOutput(
                frame_index=0,
                source_view="raw",
                prompt_detection_ids=("bbox-first", "bbox-second"),
                masks=np.zeros((2, 4, 5), dtype=bool),
                mask_scores=np.asarray((0.8,), dtype=np.float32),
                mask_bboxes_xyxy=np.zeros((2, 4), dtype=np.float32),
                mask_component_counts=np.asarray((0, 0), dtype=np.int64),
            )

    def test_input_rejects_duplicate_prompt_ids_and_boxes_outside_frame(self) -> None:
        with self.assertRaisesRegex(ValueError, "unique"):
            Sam2ImageBatchInput(
                frame=np.zeros((4, 5), dtype=np.float32),
                frame_index=0,
                source_view="raw",
                boxes_xyxy=np.asarray(((0, 0, 2, 2), (2, 1, 5, 4)), dtype=np.float32),
                prompt_detection_ids=("duplicate", "duplicate"),
            )

        with self.assertRaisesRegex(ValueError, "fit within"):
            Sam2ImageBatchInput(
                frame=np.zeros((4, 5), dtype=np.float32),
                frame_index=0,
                source_view="raw",
                boxes_xyxy=np.asarray(((0, 0, 6, 2),), dtype=np.float32),
                prompt_detection_ids=("outside",),
            )

    def test_empty_input_has_matching_empty_output_without_requiring_inference(self) -> None:
        run_input = Sam2ImageBatchInput(
            frame=np.zeros((4, 5), dtype=np.float32),
            frame_index=3,
            source_view="raw",
            boxes_xyxy=np.empty((0, 4), dtype=np.float32),
            prompt_detection_ids=(),
        )

        run_output = empty_sam2_image_batch_output(run_input)

        self.assertEqual(run_input.bbox_count, 0)
        self.assertFalse(run_input.requires_inference)
        self.assertEqual(run_output.result_count, 0)
        self.assertEqual(run_output.masks.shape, (0, 4, 5))
        self.assertEqual(run_output.mask_scores.shape, (0,))
        self.assertEqual(run_output.mask_bboxes_xyxy.shape, (0, 4))
        self.assertEqual(run_output.mask_component_counts.shape, (0,))
        self.assertIs(validate_sam2_image_batch_pair(run_input, run_output), run_output)

    def test_public_npz_helpers_roundtrip_and_validate_matching_input_and_output(self) -> None:
        run_input = Sam2ImageBatchInput(
            frame=np.zeros((4, 5), dtype=np.float32),
            frame_index=3,
            source_view="raw",
            boxes_xyxy=np.asarray(((1, 1, 3, 3),), dtype=np.float32),
            prompt_detection_ids=("bbox-1",),
        )
        mask = np.zeros((1, 4, 5), dtype=bool)
        mask[0, 1:3, 1:3] = True
        run_output = Sam2ImageBatchOutput(
            frame_index=3,
            source_view="raw",
            prompt_detection_ids=("bbox-1",),
            masks=mask,
            mask_scores=np.asarray((0.9,), dtype=np.float32),
            mask_bboxes_xyxy=np.asarray(((1, 1, 3, 3),), dtype=np.float32),
            mask_component_counts=np.asarray((1,), dtype=np.int64),
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "input.npz"
            output_path = Path(tmpdir) / "output.npz"
            write_sam2_image_batch_input_npz(input_path, run_input)
            write_sam2_image_batch_output_npz(output_path, run_output)
            restored_input = read_sam2_image_batch_input_npz(input_path)
            restored_output = read_sam2_image_batch_output_npz(output_path)

        self.assertEqual(restored_input.prompt_detection_ids, ("bbox-1",))
        self.assertEqual(restored_output.prompt_detection_ids, ("bbox-1",))
        self.assertIs(
            validate_sam2_image_batch_pair(restored_input, restored_output),
            restored_output,
        )


class Sam2ImageBatchOutputTests(unittest.TestCase):
    def test_output_npz_roundtrip_preserves_ordered_masks_scores_and_mask_boxes(self) -> None:
        masks = np.zeros((2, 4, 5), dtype=bool)
        masks[0, 0:2, 0:2] = True
        masks[1, 1:4, 2:5] = True
        scores = np.asarray((0.91, 0.82), dtype=np.float32)
        mask_boxes = np.asarray(
            (
                (0.0, 0.0, 2.0, 2.0),
                (2.0, 1.0, 5.0, 4.0),
            ),
            dtype=np.float32,
        )
        run_output = Sam2ImageBatchOutput(
            frame_index=8,
            source_view="raw",
            prompt_detection_ids=("bbox-first", "bbox-second"),
            masks=masks,
            mask_scores=scores,
            mask_bboxes_xyxy=mask_boxes,
            mask_component_counts=np.asarray((1, 1), dtype=np.int64),
        )

        payload = run_output.to_npz_payload()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "output.npz"
            np.savez_compressed(path, **payload)
            with np.load(path, allow_pickle=False) as stored:
                restored = Sam2ImageBatchOutput.from_npz_payload(
                    {key: stored[key] for key in stored.files}
                )

        self.assertEqual(int(payload["contract_version"]), SAM2_IMAGE_BATCH_CONTRACT_VERSION)
        self.assertNotEqual(payload["prompt_detection_ids"].dtype.kind, "O")
        self.assertEqual(restored.frame_index, 8)
        self.assertEqual(restored.source_view, "raw")
        self.assertEqual(restored.prompt_detection_ids, ("bbox-first", "bbox-second"))
        self.assertEqual(restored.result_count, 2)
        np.testing.assert_array_equal(restored.masks, masks)
        np.testing.assert_allclose(restored.mask_scores, scores)
        np.testing.assert_allclose(restored.mask_bboxes_xyxy, mask_boxes)
        np.testing.assert_array_equal(restored.mask_component_counts, np.asarray((1, 1)))

    def test_pair_validation_rejects_output_with_reordered_prompt_ids(self) -> None:
        run_input = Sam2ImageBatchInput(
            frame=np.zeros((4, 5), dtype=np.float32),
            frame_index=8,
            source_view="raw",
            boxes_xyxy=np.asarray(((0, 0, 2, 2), (2, 1, 5, 4)), dtype=np.float32),
            prompt_detection_ids=("bbox-first", "bbox-second"),
        )
        run_output = Sam2ImageBatchOutput(
            frame_index=8,
            source_view="raw",
            prompt_detection_ids=("bbox-second", "bbox-first"),
            masks=np.zeros((2, 4, 5), dtype=bool),
            mask_scores=np.asarray((0.8, 0.7), dtype=np.float32),
            mask_bboxes_xyxy=np.zeros((2, 4), dtype=np.float32),
            mask_component_counts=np.asarray((0, 0), dtype=np.int64),
        )

        with self.assertRaisesRegex(ValueError, "order"):
            validate_sam2_image_batch_pair(run_input, run_output)


if __name__ == "__main__":
    unittest.main()
