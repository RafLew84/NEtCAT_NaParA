import unittest

import numpy as np

from moltrack.core import MolecularDetection
from moltrack.sam2 import MolTrackSam2Segmenter
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


if __name__ == "__main__":
    unittest.main()
