import unittest
from pathlib import Path

import numpy as np

from moltrack.core import MolecularDetection
from moltrack.sam2 import MolTrackSam2SegmentationError, MolTrackSam2Segmenter
from nanotrack.sam2 import Sam2RunOutput


class MolTrackSam2AdapterTests(unittest.TestCase):
    def test_segmenter_converts_active_frame_and_bbox_to_single_frame_sam2_input(self) -> None:
        class FakeSam2Backend:
            def __init__(self) -> None:
                self.inputs = []

            def run(self, run_input):
                self.inputs.append(run_input)
                mask = np.zeros((1, 4, 5), dtype=bool)
                mask[0, 1:3, 2:4] = True
                return Sam2RunOutput(
                    track_id=run_input.track_id,
                    frame_index_offset=run_input.frame_index_offset,
                    masks=mask,
                    visible_mask=np.asarray([True]),
                    mask_bboxes_xyxy=np.asarray([[2.0, 1.0, 4.0, 3.0]], dtype=np.float32),
                    mask_scores=np.asarray([0.87], dtype=np.float32),
                    mask_areas=np.asarray([4.0], dtype=np.float32),
                )

        backend = FakeSam2Backend()
        segmenter = MolTrackSam2Segmenter(backend=backend, model_name="sam2-test")
        frame = np.arange(20, dtype=np.float32).reshape(4, 5)
        expected_mask = np.zeros((4, 5), dtype=bool)
        expected_mask[1:3, 2:4] = True
        detection = MolecularDetection(
            frame_index=2,
            bbox_xyxy=(1, 1, 4, 3),
            confidence=0.9,
            source_view="expanded_aligned",
            detection_id="bbox-2",
        )

        segmentation = segmenter.segment_detection(frame, detection)

        self.assertEqual(len(backend.inputs), 1)
        run_input = backend.inputs[0]
        self.assertEqual(run_input.frame_index_offset, 2)
        self.assertEqual(run_input.frames.shape, (1, 4, 5))
        np.testing.assert_array_equal(run_input.frames[0], frame)
        np.testing.assert_array_equal(
            run_input.query_box_xyxy,
            np.asarray([1.0, 1.0, 4.0, 3.0], dtype=np.float32),
        )
        self.assertEqual(run_input.source_view, "expanded_aligned")

        self.assertEqual(segmentation.frame_index, 2)
        self.assertEqual(segmentation.source_view, "expanded_aligned")
        self.assertEqual(segmentation.bbox_xyxy, (2.0, 1.0, 4.0, 3.0))
        np.testing.assert_array_equal(segmentation.mask, expected_mask)
        self.assertAlmostEqual(segmentation.score, 0.87)
        self.assertEqual(segmentation.origin, "sam2")
        self.assertEqual(segmentation.prompt_detection_ids, ("bbox-2",))
        self.assertEqual(segmentation.model_name, "sam2-test")
        self.assertEqual(segmentation.metadata["mask_area_px"], 4.0)

    def test_segmenter_uses_selected_checkpoint_path_for_backend_and_result_metadata(self) -> None:
        class FakeSam2Backend:
            def __init__(self) -> None:
                self.inputs = []

            def run(self, run_input):
                self.inputs.append(run_input)
                mask = np.zeros((1, 4, 5), dtype=bool)
                mask[0, 1:3, 2:4] = True
                return Sam2RunOutput(
                    track_id=run_input.track_id,
                    frame_index_offset=run_input.frame_index_offset,
                    masks=mask,
                    visible_mask=np.asarray([True]),
                    mask_bboxes_xyxy=np.asarray([[2.0, 1.0, 4.0, 3.0]], dtype=np.float32),
                    mask_scores=np.asarray([0.87], dtype=np.float32),
                    mask_areas=np.asarray([4.0], dtype=np.float32),
                )

        created_checkpoints = []

        def backend_factory(checkpoint_path):
            created_checkpoints.append(Path(checkpoint_path))
            return FakeSam2Backend()

        checkpoint_path = Path(r"C:\models\sam2.1_hiera_tiny.pt")
        segmenter = MolTrackSam2Segmenter(backend_factory=backend_factory)
        frame = np.arange(20, dtype=np.float32).reshape(4, 5)
        detection = MolecularDetection(
            frame_index=2,
            bbox_xyxy=(1, 1, 4, 3),
            confidence=0.9,
            source_view="expanded_aligned",
            detection_id="bbox-2",
        )

        segmentation = segmenter.segment_detection(frame, detection, checkpoint_path=checkpoint_path)

        self.assertEqual(created_checkpoints, [checkpoint_path])
        self.assertEqual(segmentation.model_name, "sam2.1_hiera_tiny.pt")
        self.assertEqual(segmentation.metadata["checkpoint_name"], "sam2.1_hiera_tiny.pt")
        self.assertEqual(Path(segmentation.metadata["checkpoint_path"]), checkpoint_path)

    def test_segmenter_keep_largest_component_removes_small_mask_components(self) -> None:
        class FakeSam2Backend:
            def run(self, run_input):
                mask = np.zeros((1, 5, 6), dtype=bool)
                mask[0, 0, 0] = True
                mask[0, 2:4, 3:5] = True
                return Sam2RunOutput(
                    track_id=run_input.track_id,
                    frame_index_offset=run_input.frame_index_offset,
                    masks=mask,
                    visible_mask=np.asarray([True]),
                    mask_bboxes_xyxy=np.asarray([[0.0, 0.0, 5.0, 4.0]], dtype=np.float32),
                    mask_scores=np.asarray([0.9], dtype=np.float32),
                    mask_areas=np.asarray([5.0], dtype=np.float32),
                )

        segmenter = MolTrackSam2Segmenter(backend=FakeSam2Backend(), model_name="sam2-test")
        frame = np.zeros((5, 6), dtype=np.float32)
        detection = MolecularDetection(
            frame_index=0,
            bbox_xyxy=(0, 0, 6, 5),
            confidence=0.9,
            source_view="raw",
            detection_id="bbox-1",
        )
        expected_mask = np.zeros((5, 6), dtype=bool)
        expected_mask[2:4, 3:5] = True

        segmentation = segmenter.segment_detection(
            frame,
            detection,
            keep_largest_component=True,
        )

        np.testing.assert_array_equal(segmentation.mask, expected_mask)
        self.assertEqual(segmentation.bbox_xyxy, (3.0, 2.0, 5.0, 4.0))
        self.assertEqual(segmentation.metadata["mask_area_px"], 4.0)
        self.assertTrue(segmentation.metadata["keep_largest_component"])

    def test_segmenter_rejects_mask_below_min_area_px(self) -> None:
        class FakeSam2Backend:
            def run(self, run_input):
                mask = np.zeros((1, 4, 4), dtype=bool)
                mask[0, 1, 1] = True
                return Sam2RunOutput(
                    track_id=run_input.track_id,
                    frame_index_offset=run_input.frame_index_offset,
                    masks=mask,
                    visible_mask=np.asarray([True]),
                    mask_bboxes_xyxy=np.asarray([[1.0, 1.0, 2.0, 2.0]], dtype=np.float32),
                    mask_scores=np.asarray([0.9], dtype=np.float32),
                    mask_areas=np.asarray([1.0], dtype=np.float32),
                )

        segmenter = MolTrackSam2Segmenter(backend=FakeSam2Backend(), model_name="sam2-test")
        frame = np.zeros((4, 4), dtype=np.float32)
        detection = MolecularDetection(
            frame_index=0,
            bbox_xyxy=(0, 0, 4, 4),
            confidence=0.9,
            source_view="raw",
            detection_id="bbox-1",
        )

        with self.assertRaisesRegex(MolTrackSam2SegmentationError, "below Min mask area"):
            segmenter.segment_detection(frame, detection, min_mask_area_px=2)

    def test_segmenter_records_sam2_settings_in_metadata(self) -> None:
        class FakeSam2Backend:
            def run(self, run_input):
                mask = np.zeros((1, 4, 4), dtype=bool)
                mask[0, 1:3, 1:3] = True
                return Sam2RunOutput(
                    track_id=run_input.track_id,
                    frame_index_offset=run_input.frame_index_offset,
                    masks=mask,
                    visible_mask=np.asarray([True]),
                    mask_bboxes_xyxy=np.asarray([[1.0, 1.0, 3.0, 3.0]], dtype=np.float32),
                    mask_scores=np.asarray([0.9], dtype=np.float32),
                    mask_areas=np.asarray([4.0], dtype=np.float32),
                )

        segmenter = MolTrackSam2Segmenter(backend_factory=lambda _checkpoint_path: FakeSam2Backend())
        frame = np.zeros((4, 4), dtype=np.float32)
        detection = MolecularDetection(
            frame_index=0,
            bbox_xyxy=(0, 0, 4, 4),
            confidence=0.9,
            source_view="raw",
            detection_id="bbox-1",
        )
        checkpoint_path = Path(r"C:\models\sam2.1_hiera_base_plus.pt")

        segmentation = segmenter.segment_detection(
            frame,
            detection,
            mask_probability_threshold=0.61,
            checkpoint_path=checkpoint_path,
            existing_masks_policy="append",
            keep_largest_component=True,
            min_mask_area_px=3,
        )

        self.assertEqual(segmentation.metadata["checkpoint_name"], "sam2.1_hiera_base_plus.pt")
        self.assertEqual(Path(segmentation.metadata["checkpoint_path"]), checkpoint_path)
        self.assertAlmostEqual(segmentation.metadata["sam2_threshold"], 0.61)
        self.assertEqual(segmentation.metadata["existing_sam2_masks_policy"], "append")
        self.assertTrue(segmentation.metadata["keep_largest_component"])
        self.assertEqual(segmentation.metadata["min_mask_area_px"], 3)
        self.assertEqual(segmentation.metadata["mask_area_px"], 4.0)


if __name__ == "__main__":
    unittest.main()
