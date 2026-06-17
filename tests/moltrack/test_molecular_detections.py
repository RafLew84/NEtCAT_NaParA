import unittest

from moltrack.core import MolecularDetection, MolecularDetectionSet


class MolecularDetectionModelTests(unittest.TestCase):
    def test_molecular_detection_captures_bbox_model_and_source_view(self) -> None:
        detection = MolecularDetection(
            frame_index=2,
            bbox_xyxy=(1, 2, 5, 7),
            confidence=0.85,
            selected=False,
            model_name="molecules.pt",
            checkpoint_path="C:/models/molecules.pt",
            source_view="expanded_aligned",
        )

        self.assertEqual(detection.frame_index, 2)
        self.assertEqual(detection.bbox_xyxy, (1.0, 2.0, 5.0, 7.0))
        self.assertEqual(detection.confidence, 0.85)
        self.assertFalse(detection.selected)
        self.assertEqual(detection.model_name, "molecules.pt")
        self.assertEqual(detection.checkpoint_path, "C:/models/molecules.pt")
        self.assertEqual(detection.source_view, "expanded_aligned")

    def test_molecular_detection_validates_bbox_and_frame_bounds(self) -> None:
        detection = MolecularDetection(
            frame_index=0,
            bbox_xyxy=(0, 1, 4, 3),
            confidence=1.0,
        )

        detection.validate_within_frame((3, 4))

        with self.assertRaisesRegex(ValueError, "x2 > x1"):
            MolecularDetection(frame_index=0, bbox_xyxy=(4, 1, 4, 3), confidence=0.5)
        with self.assertRaisesRegex(ValueError, "confidence"):
            MolecularDetection(frame_index=0, bbox_xyxy=(0, 1, 4, 3), confidence=1.5)
        with self.assertRaisesRegex(ValueError, "source_view"):
            MolecularDetection(frame_index=0, bbox_xyxy=(0, 1, 4, 3), confidence=0.5, source_view="aligned")
        with self.assertRaisesRegex(ValueError, "within frame"):
            detection.validate_within_frame((3, 3))

    def test_detection_set_replaces_detections_per_frame_and_source_view(self) -> None:
        detections = MolecularDetectionSet(frame_count=3)
        raw_detection = MolecularDetection(
            frame_index=1,
            bbox_xyxy=(0, 0, 3, 2),
            confidence=0.7,
            model_name="raw.pt",
            source_view="raw",
        )
        expanded_detection = MolecularDetection(
            frame_index=1,
            bbox_xyxy=(1, 1, 4, 3),
            confidence=0.9,
            model_name="expanded.pt",
            source_view="expanded_aligned",
        )

        detections.set_detections(1, [raw_detection], source_view="raw", frame_shape=(2, 3))
        detections.set_detections(
            1,
            [expanded_detection],
            source_view="expanded_aligned",
            frame_shape=(3, 4),
        )
        detections.set_detections(
            1,
            [
                MolecularDetection(
                    frame_index=1,
                    bbox_xyxy=(1, 0, 2, 1),
                    confidence=0.8,
                    model_name="raw-v2.pt",
                    source_view="raw",
                )
            ],
            source_view="raw",
            frame_shape=(2, 3),
        )

        self.assertEqual([item.model_name for item in detections.get_detections(1, source_view="raw")], ["raw-v2.pt"])
        self.assertEqual(
            [item.model_name for item in detections.get_detections(1, source_view="expanded_aligned")],
            ["expanded.pt"],
        )
        self.assertEqual(detections.detection_count, 2)
        self.assertEqual(detections.get_detections(0), [])
        with self.assertRaisesRegex(IndexError, "frame_index"):
            detections.set_detections(3, [], source_view="raw")
        with self.assertRaisesRegex(ValueError, "frame key"):
            detections.set_detections(0, [raw_detection], source_view="raw", frame_shape=(2, 3))

    def test_detection_set_can_clear_and_select_detections(self) -> None:
        detections = MolecularDetectionSet(frame_count=2)
        detections.set_detections(
            0,
            [
                MolecularDetection(frame_index=0, bbox_xyxy=(0, 0, 1, 1), confidence=0.6, selected=False),
            ],
            source_view="raw",
            frame_shape=(2, 2),
        )
        detections.set_detections(
            0,
            [
                MolecularDetection(
                    frame_index=0,
                    bbox_xyxy=(1, 0, 2, 1),
                    confidence=0.7,
                    selected=False,
                    source_view="expanded_aligned",
                ),
            ],
            source_view="expanded_aligned",
            frame_shape=(2, 2),
        )
        detections.set_detections(
            1,
            [MolecularDetection(frame_index=1, bbox_xyxy=(0, 0, 1, 1), confidence=0.8, selected=False)],
            source_view="raw",
            frame_shape=(2, 2),
        )

        changed = detections.set_frame_selected(0, True, source_view="raw")

        self.assertEqual(changed, 1)
        self.assertTrue(detections.get_detections(0, source_view="raw")[0].selected)
        self.assertFalse(detections.get_detections(0, source_view="expanded_aligned")[0].selected)

        changed = detections.set_all_selected(True)

        self.assertEqual(changed, 2)
        self.assertTrue(all(detection.selected for detection in detections.get_detections(0)))
        self.assertTrue(all(detection.selected for detection in detections.get_detections(1)))

        removed = detections.clear_frame(0, source_view="expanded_aligned")

        self.assertEqual(removed, 1)
        self.assertEqual(detections.detection_count, 2)

        removed = detections.clear_all(source_view="raw")

        self.assertEqual(removed, 2)
        self.assertEqual(detections.detection_count, 0)


if __name__ == "__main__":
    unittest.main()
