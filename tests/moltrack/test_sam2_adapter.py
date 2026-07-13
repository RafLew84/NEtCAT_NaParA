import unittest
from pathlib import Path

import numpy as np

from moltrack.core import MolecularDetection, RegisteredFrameTransform
from moltrack.sam2 import MolTrackSam2SegmentationError, MolTrackSam2Segmenter
from nanotrack.sam2 import Sam2ImageBatchOutput, Sam2RunOutput


class MolTrackSam2AdapterTests(unittest.TestCase):
    def test_persistent_image_session_reuses_one_backend_session_across_frames(self) -> None:
        class FakeBackendSession:
            def __init__(self) -> None:
                self.inputs = []

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_value, traceback) -> None:
                pass

            def segment_frame(self, run_input):
                self.inputs.append(run_input)
                masks = np.zeros(
                    (run_input.bbox_count, *run_input.frame.shape[:2]),
                    dtype=bool,
                )
                mask_boxes = np.zeros((run_input.bbox_count, 4), dtype=np.float32)
                for index, box in enumerate(run_input.boxes_xyxy.astype(int)):
                    x0, y0, x1, y1 = box
                    masks[index, y0:y1, x0:x1] = True
                    mask_boxes[index] = box
                return Sam2ImageBatchOutput(
                    frame_index=run_input.frame_index,
                    source_view=run_input.source_view,
                    prompt_detection_ids=run_input.prompt_detection_ids,
                    masks=masks,
                    mask_scores=np.full((run_input.bbox_count,), 0.9, dtype=np.float32),
                    mask_bboxes_xyxy=mask_boxes,
                    mask_component_counts=np.ones((run_input.bbox_count,), dtype=np.int64),
                )

        class FakePersistentBackend:
            def __init__(self) -> None:
                self.open_count = 0
                self.session = FakeBackendSession()

            def open_session(self):
                self.open_count += 1
                return self.session

        checkpoint_path = Path(r"C:\models\sam2.1_hiera_base_plus.pt")
        created_checkpoints = []
        backend = FakePersistentBackend()

        def persistent_backend_factory(selected_checkpoint):
            created_checkpoints.append(Path(selected_checkpoint))
            return backend

        segmenter = MolTrackSam2Segmenter(
            persistent_image_batch_backend_factory=persistent_backend_factory,
        )
        first_detections = [
            MolecularDetection(0, (1, 1, 3, 3), 0.9, detection_id="first-a"),
            MolecularDetection(0, (3, 1, 5, 3), 0.8, detection_id="first-b"),
        ]
        second_detections = [
            MolecularDetection(2, (2, 2, 4, 4), 0.7, detection_id="second-a")
        ]

        with segmenter.open_persistent_image_session(
            checkpoint_path=checkpoint_path
        ) as session:
            first_results = session.segment_frame_detections(
                np.zeros((6, 6), dtype=np.float32),
                first_detections,
                mask_probability_threshold=0.62,
            )
            second_results = session.segment_frame_detections(
                np.ones((6, 6), dtype=np.float32),
                second_detections,
                mask_probability_threshold=0.62,
            )

        self.assertEqual(created_checkpoints, [checkpoint_path])
        self.assertEqual(backend.open_count, 1)
        self.assertEqual(len(backend.session.inputs), 2)
        self.assertEqual(
            [run_input.prompt_detection_ids for run_input in backend.session.inputs],
            [("first-a", "first-b"), ("second-a",)],
        )
        self.assertTrue(all(run_input.chunk_size == 1 for run_input in backend.session.inputs))
        self.assertEqual([len(first_results), len(second_results)], [2, 1])
        self.assertEqual(first_results[0].model_name, checkpoint_path.name)
        self.assertEqual(second_results[0].metadata["checkpoint_name"], checkpoint_path.name)

    def test_segment_frame_detections_maps_ordered_raw_batch_in_one_backend_call(self) -> None:
        class FakeImageBatchBackend:
            def __init__(self) -> None:
                self.inputs = []

            def run(self, run_input):
                self.inputs.append(run_input)
                masks = np.zeros((2, 6, 8), dtype=bool)
                masks[0, 1:3, 2:4] = True
                masks[1, 3:5, 5:7] = True
                return Sam2ImageBatchOutput(
                    frame_index=run_input.frame_index,
                    source_view=run_input.source_view,
                    prompt_detection_ids=run_input.prompt_detection_ids,
                    masks=masks,
                    mask_scores=np.asarray((0.91, 0.82), dtype=np.float32),
                    mask_bboxes_xyxy=np.asarray(
                        ((2.0, 1.0, 4.0, 3.0), (5.0, 3.0, 7.0, 5.0)),
                        dtype=np.float32,
                    ),
                    mask_component_counts=np.asarray((1, 1), dtype=np.int64),
                )

        batch_backend = FakeImageBatchBackend()
        segmenter = MolTrackSam2Segmenter(
            image_batch_backend=batch_backend,
            model_name="sam2-batch-test",
        )
        frame = np.arange(48, dtype=np.float32).reshape(6, 8)
        detections = [
            MolecularDetection(
                frame_index=3,
                bbox_xyxy=(1.0, 1.0, 4.0, 4.0),
                confidence=0.9,
                source_view="raw",
                detection_id="bbox-first",
            ),
            MolecularDetection(
                frame_index=3,
                bbox_xyxy=(4.0, 2.0, 7.0, 5.0),
                confidence=0.8,
                source_view="raw",
                detection_id="bbox-second",
            ),
        ]

        results = segmenter.segment_frame_detections(
            frame,
            detections,
            mask_probability_threshold=0.64,
        )

        self.assertEqual(len(batch_backend.inputs), 1)
        run_input = batch_backend.inputs[0]
        self.assertEqual(run_input.frame_index, 3)
        self.assertEqual(run_input.source_view, "raw")
        self.assertEqual(run_input.prompt_detection_ids, ("bbox-first", "bbox-second"))
        np.testing.assert_array_equal(
            run_input.boxes_xyxy,
            np.asarray((detections[0].bbox_xyxy, detections[1].bbox_xyxy)),
        )
        self.assertAlmostEqual(run_input.mask_probability_threshold, 0.64)
        self.assertEqual([item.prompt_detection_ids for item in results], [
            ("bbox-first",),
            ("bbox-second",),
        ])
        self.assertEqual([item.bbox_xyxy for item in results], [
            (2.0, 1.0, 4.0, 3.0),
            (5.0, 3.0, 7.0, 5.0),
        ])
        self.assertEqual([item.model_name for item in results], [
            "sam2-batch-test",
            "sam2-batch-test",
        ])
        self.assertAlmostEqual(results[0].score, 0.91)
        self.assertAlmostEqual(results[1].score, 0.82)

    def test_frame_batch_postprocesses_each_mask_independently(self) -> None:
        class FakeImageBatchBackend:
            def run(self, run_input):
                masks = np.zeros((2, 7, 8), dtype=bool)
                masks[0, 0, 0] = True
                masks[0, 2:4, 2:4] = True
                masks[1, 0, 7] = True
                masks[1, 4:6, 4:7] = True
                return Sam2ImageBatchOutput(
                    frame_index=run_input.frame_index,
                    source_view=run_input.source_view,
                    prompt_detection_ids=run_input.prompt_detection_ids,
                    masks=masks,
                    mask_scores=np.asarray((0.9, 0.8), dtype=np.float32),
                    mask_bboxes_xyxy=np.asarray(
                        ((0.0, 0.0, 4.0, 4.0), (4.0, 0.0, 8.0, 6.0)),
                        dtype=np.float32,
                    ),
                    mask_component_counts=np.asarray((2, 2), dtype=np.int64),
                )

        detections = [
            MolecularDetection(
                frame_index=0,
                bbox_xyxy=(0.0, 0.0, 4.0, 4.0),
                confidence=0.9,
                detection_id="bbox-left",
            ),
            MolecularDetection(
                frame_index=0,
                bbox_xyxy=(4.0, 0.0, 8.0, 7.0),
                confidence=0.8,
                detection_id="bbox-right",
            ),
        ]
        segmenter = MolTrackSam2Segmenter(
            image_batch_backend=FakeImageBatchBackend(),
        )

        results = segmenter.segment_frame_detections(
            np.zeros((7, 8), dtype=np.float32),
            detections,
            keep_largest_component=True,
            min_mask_area_px=3,
        )

        expected_left = np.zeros((7, 8), dtype=bool)
        expected_left[2:4, 2:4] = True
        expected_right = np.zeros((7, 8), dtype=bool)
        expected_right[4:6, 4:7] = True
        np.testing.assert_array_equal(results[0].mask, expected_left)
        np.testing.assert_array_equal(results[1].mask, expected_right)
        self.assertEqual(results[0].bbox_xyxy, (2.0, 2.0, 4.0, 4.0))
        self.assertEqual(results[1].bbox_xyxy, (4.0, 4.0, 7.0, 6.0))
        self.assertEqual(results[0].metadata["mask_area_px"], 4.0)
        self.assertEqual(results[1].metadata["mask_area_px"], 6.0)
        self.assertEqual(results[0].metadata["mask_component_count"], 2)
        self.assertEqual(results[1].metadata["mask_component_count"], 2)

    def test_frame_batch_maps_expanded_prompts_to_raw_and_results_back_to_canvas(self) -> None:
        class FakeImageBatchBackend:
            def __init__(self) -> None:
                self.inputs = []

            def run(self, run_input):
                self.inputs.append(run_input)
                masks = np.zeros((2, 5, 6), dtype=bool)
                masks[0, 1:3, 1:3] = True
                masks[1, 2:4, 3:5] = True
                return Sam2ImageBatchOutput(
                    frame_index=run_input.frame_index,
                    source_view=run_input.source_view,
                    prompt_detection_ids=run_input.prompt_detection_ids,
                    masks=masks,
                    mask_scores=np.asarray((0.93, 0.84), dtype=np.float32),
                    mask_bboxes_xyxy=np.asarray(
                        ((1.0, 1.0, 3.0, 3.0), (3.0, 2.0, 5.0, 4.0)),
                        dtype=np.float32,
                    ),
                    mask_component_counts=np.asarray((1, 1), dtype=np.int64),
                )

        transform = RegisteredFrameTransform(
            raw_shape=(5, 6),
            expanded_shape=(9, 10),
            frame_origin_xy=(2.0, 1.0),
        )
        raw_detections = [
            MolecularDetection(
                frame_index=4,
                bbox_xyxy=(1.0, 1.0, 3.0, 3.0),
                confidence=0.9,
                source_view="raw",
                detection_id="expanded-first",
            ),
            MolecularDetection(
                frame_index=4,
                bbox_xyxy=(3.0, 2.0, 5.0, 4.0),
                confidence=0.8,
                source_view="raw",
                detection_id="expanded-second",
            ),
        ]
        expanded_detections = [
            transform.raw_detection_to_expanded(detection)
            for detection in raw_detections
        ]
        backend = FakeImageBatchBackend()
        segmenter = MolTrackSam2Segmenter(image_batch_backend=backend)

        results = segmenter.segment_frame_detections(
            np.zeros((5, 6), dtype=np.float32),
            expanded_detections,
            registered_transform=transform,
        )

        self.assertEqual(len(backend.inputs), 1)
        self.assertEqual(backend.inputs[0].source_view, "raw")
        np.testing.assert_array_equal(
            backend.inputs[0].boxes_xyxy,
            np.asarray([detection.bbox_xyxy for detection in raw_detections]),
        )
        self.assertEqual([result.source_view for result in results], [
            "expanded_aligned",
            "expanded_aligned",
        ])
        self.assertEqual([result.bbox_xyxy for result in results], [
            (3.0, 2.0, 5.0, 4.0),
            (5.0, 3.0, 7.0, 5.0),
        ])
        self.assertTrue(all(result.mask.shape == (9, 10) for result in results))
        self.assertTrue(all(result.original_mask.shape == (9, 10) for result in results))
        self.assertEqual(results[0].metadata["inference_source_view"], "raw")
        self.assertEqual(results[0].metadata["registered_frame_origin_xy"], [2.0, 1.0])
        self.assertEqual(results[1].prompt_detection_ids, ("expanded-second",))

    def test_frame_batch_preserves_checkpoint_threshold_and_policy_metadata(self) -> None:
        class FakeImageBatchBackend:
            def run(self, run_input):
                mask = np.zeros((1, 4, 5), dtype=bool)
                mask[0, 1:3, 2:4] = True
                return Sam2ImageBatchOutput(
                    frame_index=run_input.frame_index,
                    source_view=run_input.source_view,
                    prompt_detection_ids=run_input.prompt_detection_ids,
                    masks=mask,
                    mask_scores=np.asarray((0.88,), dtype=np.float32),
                    mask_bboxes_xyxy=np.asarray(
                        ((2.0, 1.0, 4.0, 3.0),),
                        dtype=np.float32,
                    ),
                    mask_component_counts=np.asarray((3,), dtype=np.int64),
                )

        created_checkpoints = []

        def batch_backend_factory(checkpoint_path):
            created_checkpoints.append(Path(checkpoint_path))
            return FakeImageBatchBackend()

        checkpoint_path = Path(r"C:\models\sam2.1_hiera_small.pt")
        segmenter = MolTrackSam2Segmenter(
            image_batch_backend_factory=batch_backend_factory,
        )
        detection = MolecularDetection(
            frame_index=1,
            bbox_xyxy=(1.0, 1.0, 4.0, 3.0),
            confidence=0.9,
            detection_id="bbox-metadata",
        )

        result = segmenter.segment_frame_detections(
            np.zeros((4, 5), dtype=np.float32),
            [detection],
            checkpoint_path=checkpoint_path,
            mask_probability_threshold=0.63,
            existing_masks_policy="append",
        )[0]

        self.assertEqual(created_checkpoints, [checkpoint_path])
        self.assertEqual(result.model_name, "sam2.1_hiera_small.pt")
        self.assertEqual(result.metadata["checkpoint_name"], "sam2.1_hiera_small.pt")
        self.assertEqual(Path(result.metadata["checkpoint_path"]), checkpoint_path)
        self.assertAlmostEqual(result.metadata["sam2_threshold"], 0.63)
        self.assertEqual(result.metadata["existing_sam2_masks_policy"], "append")
        self.assertEqual(result.metadata["mask_component_count"], 3)

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
