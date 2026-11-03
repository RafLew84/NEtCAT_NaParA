import unittest

import numpy as np

from moltrack.core import MolecularSegmentation, MolecularSegmentationSet


class MolecularSegmentationModelTests(unittest.TestCase):
    def test_segmentation_set_adds_gets_and_removes_by_frame_view_and_stable_id(self) -> None:
        mask = np.array([[False, True, True], [False, False, True]], dtype=bool)
        segmentations = MolecularSegmentationSet(frame_count=2)
        raw_segmentation = MolecularSegmentation(
            frame_index=0,
            source_view="raw",
            bbox_xyxy=(1, 0, 3, 2),
            mask=mask,
            polygon_xy=[(1, 0), (3, 0), (3, 2), (1, 2)],
            score=0.91,
            origin="sam2",
            prompt_detection_ids=("bbox-1",),
            model_name="sam2-hiera",
            metadata={"checkpoint": "sam2.pt"},
            segmentation_id="seg-raw",
        )
        expanded_segmentation = MolecularSegmentation(
            frame_index=0,
            source_view="expanded_aligned",
            mask=np.ones((2, 2), dtype=bool),
            origin="sam3",
            segmentation_id="seg-expanded",
        )
        other_frame_segmentation = MolecularSegmentation(
            frame_index=1,
            source_view="raw",
            polygon_xy=[(0, 0), (2, 0), (1, 2)],
            origin="manual",
            segmentation_id="seg-other-frame",
        )

        added = segmentations.add_segmentation(raw_segmentation)
        segmentations.add_segmentation(expanded_segmentation)
        segmentations.add_segmentation(other_frame_segmentation)

        self.assertIs(added, raw_segmentation)
        self.assertEqual(raw_segmentation.segmentation_id, "seg-raw")
        self.assertEqual(raw_segmentation.frame_index, 0)
        self.assertEqual(raw_segmentation.source_view, "raw")
        self.assertEqual(raw_segmentation.bbox_xyxy, (1.0, 0.0, 3.0, 2.0))
        np.testing.assert_array_equal(raw_segmentation.mask, mask)
        self.assertEqual(raw_segmentation.polygon_xy, ((1.0, 0.0), (3.0, 0.0), (3.0, 2.0), (1.0, 2.0)))
        self.assertEqual(raw_segmentation.score, 0.91)
        self.assertEqual(raw_segmentation.origin, "sam2")
        self.assertEqual(raw_segmentation.prompt_detection_ids, ("bbox-1",))
        self.assertEqual(raw_segmentation.model_name, "sam2-hiera")
        self.assertEqual(raw_segmentation.metadata, {"checkpoint": "sam2.pt"})

        self.assertIs(segmentations.get_segmentation("seg-raw"), raw_segmentation)
        self.assertEqual(segmentations.get_segmentations(0, source_view="raw"), [raw_segmentation])
        self.assertEqual(segmentations.get_segmentations(0, source_view="expanded_aligned"), [expanded_segmentation])
        self.assertEqual(segmentations.get_segmentations(1, source_view="raw"), [other_frame_segmentation])
        self.assertEqual(segmentations.segmentation_count, 3)

        removed = segmentations.remove_segmentation("seg-raw")

        self.assertIs(removed, raw_segmentation)
        self.assertIsNone(segmentations.get_segmentation("seg-raw"))
        self.assertEqual(segmentations.get_segmentations(0, source_view="raw"), [])
        self.assertEqual(segmentations.get_segmentations(0, source_view="expanded_aligned"), [expanded_segmentation])
        self.assertEqual(segmentations.get_segmentations(1, source_view="raw"), [other_frame_segmentation])
        self.assertEqual(segmentations.segmentation_count, 2)


if __name__ == "__main__":
    unittest.main()
