import tempfile
import unittest
from pathlib import Path

import numpy as np

from moltrack.core import (
    MolecularDetection,
    MolecularDetectionSet,
    MolecularSegmentation,
    MolecularSegmentationSet,
    MolTrackImageSeries,
)
from moltrack.persistence import load_moltrack_session, save_moltrack_session
from moltrack.sam3 import (
    MolTrackSam3Preview,
    MolTrackSam3PreviewProposal,
    MolTrackSam3Proposal,
    build_moltrack_sam3_preview,
    commit_moltrack_sam3_preview,
)
from nanotrack.core import STMSequenceMetadata


class MolTrackSam3PreviewTests(unittest.TestCase):
    def test_builds_preview_from_sam3_proposals_without_changing_detections(self) -> None:
        detections = MolecularDetectionSet(frame_count=1)
        detections.set_detections(
            0,
            [
                MolecularDetection(
                    frame_index=0,
                    bbox_xyxy=(1, 1, 3, 3),
                    confidence=0.9,
                    source_view="raw",
                    detection_id="bbox-1",
                )
            ],
            source_view="raw",
            frame_shape=(5, 5),
        )
        proposal = MolTrackSam3Proposal(
            frame_index=0,
            source_view="raw",
            bbox_xyxy=(2, 2, 5, 5),
            score=0.82,
            mask=np.eye(5, dtype=bool),
            polygon_xy=((2, 2), (5, 2), (5, 5), (2, 5)),
            prompt_detection_ids=("bbox-1",),
            model_name="facebook/sam3",
            metadata={"backend": "transformers_sam3"},
        )

        preview = build_moltrack_sam3_preview(
            [proposal],
            frame_index=0,
            source_view="raw",
            existing_detections=detections.get_detections(0, source_view="raw"),
        )

        self.assertEqual(detections.detection_count, 1)
        self.assertEqual(detections.get_detections(0, source_view="raw")[0].bbox_xyxy, (1.0, 1.0, 3.0, 3.0))
        self.assertEqual(preview.frame_index, 0)
        self.assertEqual(preview.source_view, "raw")
        self.assertEqual(preview.proposal_count, 1)
        self.assertEqual(preview.proposals[0].bbox_xyxy, (2.0, 2.0, 5.0, 5.0))
        self.assertEqual(preview.proposals[0].prompt_detection_ids, ("bbox-1",))
        self.assertEqual(preview.proposals[0].model_name, "facebook/sam3")
        np.testing.assert_array_equal(preview.proposals[0].mask, np.eye(5, dtype=bool))

    def test_preview_filters_by_context_score_duplicate_iou_and_max_results(self) -> None:
        detections = MolecularDetectionSet(frame_count=2)
        detections.set_detections(
            0,
            [
                MolecularDetection(
                    frame_index=0,
                    bbox_xyxy=(0, 0, 4, 4),
                    confidence=0.9,
                    source_view="raw",
                    detection_id="existing",
                )
            ],
            source_view="raw",
        )
        proposals = [
            MolTrackSam3Proposal(
                frame_index=0,
                source_view="raw",
                bbox_xyxy=(0, 0, 4, 4),
                score=0.99,
            ),
            MolTrackSam3Proposal(
                frame_index=0,
                source_view="raw",
                bbox_xyxy=(5, 5, 8, 8),
                score=0.2,
            ),
            MolTrackSam3Proposal(
                frame_index=1,
                source_view="raw",
                bbox_xyxy=(10, 10, 13, 13),
                score=0.95,
            ),
            MolTrackSam3Proposal(
                frame_index=0,
                source_view="expanded_aligned",
                bbox_xyxy=(20, 20, 23, 23),
                score=0.94,
            ),
            MolTrackSam3Proposal(
                frame_index=0,
                source_view="raw",
                bbox_xyxy=(30, 30, 33, 33),
                score=0.93,
            ),
            MolTrackSam3Proposal(
                frame_index=0,
                source_view="raw",
                bbox_xyxy=(40, 40, 43, 43),
                score=0.92,
            ),
        ]

        preview = build_moltrack_sam3_preview(
            proposals,
            frame_index=0,
            source_view="raw",
            existing_detections=detections.get_detections(0, source_view="raw"),
            score_threshold=0.5,
            mask_threshold=0.6,
            max_results=1,
            duplicate_iou_threshold=0.5,
        )

        self.assertEqual(preview.settings.score_threshold, 0.5)
        self.assertEqual(preview.settings.mask_threshold, 0.6)
        self.assertEqual(preview.settings.max_results, 1)
        self.assertEqual(preview.settings.duplicate_iou_threshold, 0.5)
        self.assertEqual(preview.proposal_count, 1)
        self.assertEqual(preview.proposals[0].bbox_xyxy, (30.0, 30.0, 33.0, 33.0))

    def test_commit_preview_as_bboxes_appends_non_duplicates_only(self) -> None:
        detections = MolecularDetectionSet(frame_count=1)
        detections.set_detections(
            0,
            [
                MolecularDetection(
                    frame_index=0,
                    bbox_xyxy=(0, 0, 4, 4),
                    confidence=0.9,
                    source_view="raw",
                    detection_id="existing",
                    origin="yolo",
                )
            ],
            source_view="raw",
        )
        preview = MolTrackSam3Preview(
            frame_index=0,
            source_view="raw",
            proposals=(
                MolTrackSam3PreviewProposal(
                    frame_index=0,
                    source_view="raw",
                    bbox_xyxy=(0, 0, 4, 4),
                    score=0.99,
                    model_name="facebook/sam3",
                    proposal_id="duplicate",
                ),
                MolTrackSam3PreviewProposal(
                    frame_index=0,
                    source_view="raw",
                    bbox_xyxy=(10, 10, 14, 14),
                    score=0.81,
                    prompt_detection_ids=("prompt-1",),
                    model_name="facebook/sam3",
                    metadata={"backend": "transformers_sam3"},
                    proposal_id="new-box",
                ),
            ),
        )

        result = commit_moltrack_sam3_preview(
            preview,
            detection_set=detections,
            mode="bboxes",
            duplicate_iou_threshold=0.5,
        )

        self.assertEqual(result.added_bbox_count, 1)
        self.assertEqual(result.added_segmentation_count, 0)
        self.assertEqual(result.skipped_duplicate_count, 1)
        current = detections.get_detections(0, source_view="raw")
        self.assertEqual(len(current), 2)
        committed = current[1]
        self.assertEqual(committed.bbox_xyxy, (10.0, 10.0, 14.0, 14.0))
        self.assertEqual(committed.original_bbox_xyxy, (10.0, 10.0, 14.0, 14.0))
        self.assertEqual(committed.confidence, 0.81)
        self.assertEqual(committed.origin, "sam3_concept")
        self.assertEqual(committed.model_name, "facebook/sam3")
        self.assertEqual(committed.detection_id, "sam3-bbox-new-box")

    def test_commit_preview_as_segmentations_preserves_mask_polygon_and_prompt_metadata(self) -> None:
        segmentations = MolecularSegmentationSet(frame_count=1)
        mask = np.asarray(
            [
                [False, False, False, False],
                [False, True, True, False],
                [False, True, True, False],
                [False, False, False, False],
            ],
            dtype=bool,
        )
        preview = MolTrackSam3Preview(
            frame_index=0,
            source_view="raw",
            proposals=(
                MolTrackSam3PreviewProposal(
                    frame_index=0,
                    source_view="raw",
                    bbox_xyxy=(1, 1, 3, 3),
                    score=0.77,
                    mask=mask,
                    polygon_xy=((1, 1), (3, 1), (3, 3), (1, 3)),
                    prompt_detection_ids=("bbox-1",),
                    model_name="facebook/sam3",
                    metadata={"backend": "transformers_sam3"},
                    proposal_id="mask-1",
                ),
            ),
        )

        result = commit_moltrack_sam3_preview(
            preview,
            segmentation_set=segmentations,
            mode="segmentations",
        )

        self.assertEqual(result.added_bbox_count, 0)
        self.assertEqual(result.added_segmentation_count, 1)
        current = segmentations.get_segmentations(0, source_view="raw")
        self.assertEqual(len(current), 1)
        committed = current[0]
        self.assertEqual(committed.segmentation_id, "sam3-seg-mask-1")
        self.assertEqual(committed.bbox_xyxy, (1.0, 1.0, 3.0, 3.0))
        np.testing.assert_array_equal(committed.mask, mask)
        self.assertEqual(committed.polygon_xy, ((1.0, 1.0), (3.0, 1.0), (3.0, 3.0), (1.0, 3.0)))
        self.assertEqual(committed.score, 0.77)
        self.assertEqual(committed.origin, "sam3")
        self.assertEqual(committed.prompt_detection_ids, ("bbox-1",))
        self.assertEqual(committed.model_name, "facebook/sam3")
        self.assertEqual(committed.metadata["backend"], "transformers_sam3")

    def test_commit_preview_both_replace_removes_only_previous_sam3_results_in_current_context(self) -> None:
        detections = MolecularDetectionSet(frame_count=2)
        detections.set_detections(
            0,
            [
                MolecularDetection(
                    frame_index=0,
                    bbox_xyxy=(0, 0, 2, 2),
                    confidence=0.9,
                    source_view="raw",
                    detection_id="keep-yolo",
                    origin="yolo",
                ),
                MolecularDetection(
                    frame_index=0,
                    bbox_xyxy=(3, 3, 5, 5),
                    confidence=0.8,
                    source_view="raw",
                    detection_id="old-sam3",
                    origin="sam3_concept",
                ),
            ],
            source_view="raw",
        )
        detections.set_detections(
            0,
            [
                MolecularDetection(
                    frame_index=0,
                    bbox_xyxy=(3, 3, 5, 5),
                    confidence=0.7,
                    source_view="expanded_aligned",
                    detection_id="other-view-sam3",
                    origin="sam3_concept",
                ),
            ],
            source_view="expanded_aligned",
        )
        segmentations = MolecularSegmentationSet(frame_count=2)
        segmentations.add_segmentation(
            MolecularSegmentation(
                frame_index=0,
                source_view="raw",
                mask=np.ones((2, 2), dtype=bool),
                origin="sam3",
                segmentation_id="old-sam3-seg",
            )
        )
        segmentations.add_segmentation(
            MolecularSegmentation(
                frame_index=0,
                source_view="raw",
                mask=np.ones((2, 2), dtype=bool),
                origin="sam2",
                segmentation_id="keep-sam2-seg",
            )
        )
        segmentations.add_segmentation(
            MolecularSegmentation(
                frame_index=1,
                source_view="raw",
                mask=np.ones((2, 2), dtype=bool),
                origin="sam3",
                segmentation_id="other-frame-sam3-seg",
            )
        )
        preview = MolTrackSam3Preview(
            frame_index=0,
            source_view="raw",
            proposals=(
                MolTrackSam3PreviewProposal(
                    frame_index=0,
                    source_view="raw",
                    bbox_xyxy=(6, 6, 9, 9),
                    score=0.88,
                    mask=np.ones((4, 4), dtype=bool),
                    polygon_xy=((6, 6), (9, 6), (9, 9), (6, 9)),
                    model_name="facebook/sam3",
                    proposal_id="replacement",
                ),
            ),
        )

        result = commit_moltrack_sam3_preview(
            preview,
            detection_set=detections,
            segmentation_set=segmentations,
            mode="both",
            replace_existing=True,
        )

        self.assertEqual(result.replaced_bbox_count, 1)
        self.assertEqual(result.replaced_segmentation_count, 1)
        self.assertEqual(result.added_bbox_count, 1)
        self.assertEqual(result.added_segmentation_count, 1)
        self.assertIsNotNone(detections.get_detection("keep-yolo"))
        self.assertIsNone(detections.get_detection("old-sam3"))
        self.assertIsNotNone(detections.get_detection("other-view-sam3"))
        self.assertIsNotNone(detections.get_detection("sam3-bbox-replacement"))
        self.assertIsNone(segmentations.get_segmentation("old-sam3-seg"))
        self.assertIsNotNone(segmentations.get_segmentation("keep-sam2-seg"))
        self.assertIsNotNone(segmentations.get_segmentation("other-frame-sam3-seg"))
        self.assertIsNotNone(segmentations.get_segmentation("sam3-seg-replacement"))

    def test_committed_sam3_bboxes_and_segmentations_round_trip_through_session_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            source_path = tmp_path / "movie.mpp"
            source_path.write_bytes(b"fake mpp bytes")
            session_path = tmp_path / "state.moltrack.json"
            series = MolTrackImageSeries(
                source_path=str(source_path),
                raw_frames=np.arange(16, dtype=np.float32).reshape(1, 4, 4),
                metadata=STMSequenceMetadata(pixels_x=4, pixels_y=4),
            )
            detections = MolecularDetectionSet(frame_count=series.frame_count)
            segmentations = MolecularSegmentationSet(frame_count=series.frame_count)
            preview = MolTrackSam3Preview(
                frame_index=0,
                source_view="raw",
                proposals=(
                    MolTrackSam3PreviewProposal(
                        frame_index=0,
                        source_view="raw",
                        bbox_xyxy=(1, 1, 3, 3),
                        score=0.86,
                        mask=np.asarray(
                            [
                                [False, False, False, False],
                                [False, True, True, False],
                                [False, True, True, False],
                                [False, False, False, False],
                            ],
                            dtype=bool,
                        ),
                        polygon_xy=((1, 1), (3, 1), (3, 3), (1, 3)),
                        prompt_detection_ids=("prompt-bbox",),
                        model_name="facebook/sam3",
                        metadata={"backend": "transformers_sam3"},
                        proposal_id="roundtrip",
                    ),
                ),
            )
            commit_moltrack_sam3_preview(
                preview,
                detection_set=detections,
                segmentation_set=segmentations,
                mode="both",
            )
            series.molecular_detections = detections
            series.molecular_segmentations = segmentations

            save_moltrack_session(session_path, series)
            loaded = load_moltrack_session(session_path)

            self.assertIsNotNone(loaded.molecular_detections)
            loaded_detection = loaded.molecular_detections.get_detection("sam3-bbox-roundtrip")
            self.assertIsNotNone(loaded_detection)
            self.assertEqual(loaded_detection.origin, "sam3_concept")
            self.assertEqual(loaded_detection.bbox_xyxy, (1.0, 1.0, 3.0, 3.0))
            self.assertEqual(loaded_detection.confidence, 0.86)
            self.assertEqual(loaded_detection.model_name, "facebook/sam3")
            self.assertIsNotNone(loaded.molecular_segmentations)
            loaded_segmentation = loaded.molecular_segmentations.get_segmentation("sam3-seg-roundtrip")
            self.assertIsNotNone(loaded_segmentation)
            self.assertEqual(loaded_segmentation.origin, "sam3")
            self.assertEqual(loaded_segmentation.prompt_detection_ids, ("prompt-bbox",))
            self.assertEqual(loaded_segmentation.model_name, "facebook/sam3")
            self.assertEqual(loaded_segmentation.metadata["backend"], "transformers_sam3")
            np.testing.assert_array_equal(loaded_segmentation.mask, preview.proposals[0].mask)
            self.assertEqual(
                loaded_segmentation.polygon_xy,
                ((1.0, 1.0), (3.0, 1.0), (3.0, 3.0), (1.0, 3.0)),
            )


if __name__ == "__main__":
    unittest.main()
