import unittest

from moltrack.core import MolecularDetection, MolecularDetectionSet
from moltrack.sam3 import (
    MolTrackSam3PromptValidationError,
    build_moltrack_sam3_prompt_batch,
)


class MolTrackSam3PromptBuilderTests(unittest.TestCase):
    def test_builds_prompt_batch_from_all_current_image_bboxes_only(self) -> None:
        detections = MolecularDetectionSet(frame_count=2)
        detections.set_detections(
            0,
            [
                MolecularDetection(
                    frame_index=0,
                    bbox_xyxy=(1, 2, 5, 6),
                    confidence=0.9,
                    source_view="raw",
                    detection_id="raw-1",
                ),
                MolecularDetection(
                    frame_index=0,
                    bbox_xyxy=(10, 11, 20, 21),
                    confidence=0.8,
                    source_view="raw",
                    detection_id="raw-2",
                ),
            ],
            source_view="raw",
        )
        detections.set_detections(
            0,
            [
                MolecularDetection(
                    frame_index=0,
                    bbox_xyxy=(100, 101, 120, 121),
                    confidence=0.7,
                    source_view="expanded_aligned",
                    detection_id="expanded-1",
                ),
            ],
            source_view="expanded_aligned",
        )
        detections.set_detections(
            1,
            [
                MolecularDetection(
                    frame_index=1,
                    bbox_xyxy=(30, 31, 40, 41),
                    confidence=0.6,
                    source_view="raw",
                    detection_id="other-frame",
                ),
            ],
            source_view="raw",
        )

        prompts = build_moltrack_sam3_prompt_batch(
            detections,
            frame_index=0,
            source_view="raw",
            positive_bbox_mode="all_current",
        )

        self.assertEqual([prompt.label for prompt in prompts], [1, 1])
        self.assertEqual(
            [prompt.bbox_xyxy for prompt in prompts],
            [(1.0, 2.0, 5.0, 6.0), (10.0, 11.0, 20.0, 21.0)],
        )
        self.assertEqual([prompt.detection_id for prompt in prompts], ["raw-1", "raw-2"])

    def test_builds_prompt_batch_from_selected_current_bboxes_and_manual_positive_prompt(self) -> None:
        detections = MolecularDetectionSet(frame_count=2)
        detections.set_detections(
            0,
            [
                MolecularDetection(
                    frame_index=0,
                    bbox_xyxy=(1, 2, 5, 6),
                    confidence=0.9,
                    source_view="raw",
                    detection_id="raw-1",
                ),
                MolecularDetection(
                    frame_index=0,
                    bbox_xyxy=(10, 11, 20, 21),
                    confidence=0.8,
                    source_view="raw",
                    detection_id="raw-2",
                ),
            ],
            source_view="raw",
        )
        detections.set_detections(
            0,
            [
                MolecularDetection(
                    frame_index=0,
                    bbox_xyxy=(100, 101, 120, 121),
                    confidence=0.7,
                    source_view="expanded_aligned",
                    detection_id="expanded-1",
                ),
            ],
            source_view="expanded_aligned",
        )
        detections.set_detections(
            1,
            [
                MolecularDetection(
                    frame_index=1,
                    bbox_xyxy=(30, 31, 40, 41),
                    confidence=0.6,
                    source_view="raw",
                    detection_id="other-frame",
                ),
            ],
            source_view="raw",
        )
        detection_count_before = detections.detection_count

        prompts = build_moltrack_sam3_prompt_batch(
            detections,
            frame_index=0,
            source_view="raw",
            positive_bbox_mode="selected_current",
            selected_detection_ids=("raw-2", "expanded-1", "other-frame"),
            manual_positive_bboxes=((2, 3, 8, 9),),
        )

        self.assertEqual(detections.detection_count, detection_count_before)
        self.assertEqual([prompt.label for prompt in prompts], [1, 1])
        self.assertEqual(
            [prompt.bbox_xyxy for prompt in prompts],
            [(10.0, 11.0, 20.0, 21.0), (2.0, 3.0, 8.0, 9.0)],
        )
        self.assertEqual([prompt.detection_id for prompt in prompts], ["raw-2", ""])

    def test_adds_manual_negative_prompt_and_rejects_negative_only_batch(self) -> None:
        detections = MolecularDetectionSet(frame_count=1)
        detections.set_detections(
            0,
            [
                MolecularDetection(
                    frame_index=0,
                    bbox_xyxy=(1, 2, 5, 6),
                    confidence=0.9,
                    source_view="raw",
                    detection_id="raw-1",
                ),
            ],
            source_view="raw",
        )

        prompts = build_moltrack_sam3_prompt_batch(
            detections,
            frame_index=0,
            source_view="raw",
            positive_bbox_mode="all_current",
            manual_negative_bboxes=((10, 11, 14, 15),),
        )

        self.assertEqual([prompt.label for prompt in prompts], [1, 0])
        self.assertEqual(
            [prompt.bbox_xyxy for prompt in prompts],
            [(1.0, 2.0, 5.0, 6.0), (10.0, 11.0, 14.0, 15.0)],
        )
        self.assertEqual([prompt.detection_id for prompt in prompts], ["raw-1", ""])

        with self.assertRaisesRegex(MolTrackSam3PromptValidationError, "at least one positive"):
            build_moltrack_sam3_prompt_batch(
                MolecularDetectionSet(frame_count=1),
                frame_index=0,
                source_view="raw",
                positive_bbox_mode="manual_only",
                manual_negative_bboxes=((10, 11, 14, 15),),
            )


if __name__ == "__main__":
    unittest.main()
