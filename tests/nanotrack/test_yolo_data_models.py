import unittest

from nanotrack.core import BBoxXYXY, YoloDetection, YoloDetectionSet


class YoloDetectionTests(unittest.TestCase):
    def test_normalizes_confidence_and_selection(self) -> None:
        detection = YoloDetection(
            frame_index=3,
            bbox=BBoxXYXY(1.0, 2.0, 5.0, 7.0),
            confidence=0.85,
            selected=1,
            model_name="yolo11s.pt",
        )

        self.assertEqual(detection.frame_index, 3)
        self.assertEqual(detection.bbox, BBoxXYXY(1.0, 2.0, 5.0, 7.0))
        self.assertAlmostEqual(detection.confidence, 0.85, places=6)
        self.assertTrue(detection.selected)
        self.assertEqual(detection.model_name, "yolo11s.pt")

    def test_rejects_invalid_confidence(self) -> None:
        with self.assertRaises(ValueError):
            YoloDetection(
                frame_index=0,
                bbox=BBoxXYXY(1.0, 1.0, 2.0, 2.0),
                confidence=1.5,
                model_name="yolo11s.pt",
            )

    def test_rejects_empty_model_name(self) -> None:
        with self.assertRaises(ValueError):
            YoloDetection(
                frame_index=0,
                bbox=BBoxXYXY(1.0, 1.0, 2.0, 2.0),
                confidence=0.5,
                model_name="  ",
            )


class YoloDetectionSetTests(unittest.TestCase):
    def test_exposes_frame_indices_and_selected_counts(self) -> None:
        detection_a = YoloDetection(
            frame_index=2,
            bbox=BBoxXYXY(1.0, 1.0, 4.0, 4.0),
            confidence=0.8,
            selected=True,
            model_name="yolo11s.pt",
        )
        detection_b = YoloDetection(
            frame_index=2,
            bbox=BBoxXYXY(2.0, 2.0, 5.0, 5.0),
            confidence=0.6,
            selected=False,
            model_name="yolo11s.pt",
        )
        detection_c = YoloDetection(
            frame_index=4,
            bbox=BBoxXYXY(3.0, 3.0, 6.0, 6.0),
            confidence=0.9,
            selected=True,
            model_name="yolo11s.pt",
        )

        detection_set = YoloDetectionSet(
            model_name="yolo11s.pt",
            source_path="/tmp/sequence.mpp",
            detections_by_frame={
                4: [detection_c],
                2: [detection_a, detection_b],
            },
        )

        self.assertEqual(detection_set.frame_indices, [2, 4])
        self.assertEqual(detection_set.detection_count, 3)
        self.assertEqual(detection_set.selected_detection_count(), 2)
        self.assertEqual(detection_set.selected_detection_count(2), 1)
        self.assertEqual(detection_set.selected_detections(4), [detection_c])

    def test_set_selected_supports_current_frame_and_global(self) -> None:
        detection_a = YoloDetection(
            frame_index=1,
            bbox=BBoxXYXY(1.0, 1.0, 4.0, 4.0),
            confidence=0.8,
            selected=True,
            model_name="yolo11s.pt",
        )
        detection_b = YoloDetection(
            frame_index=2,
            bbox=BBoxXYXY(2.0, 2.0, 5.0, 5.0),
            confidence=0.7,
            selected=True,
            model_name="yolo11s.pt",
        )
        detection_set = YoloDetectionSet(
            model_name="yolo11s.pt",
            source_path="/tmp/sequence.mpp",
            detections_by_frame={1: [detection_a], 2: [detection_b]},
        )

        detection_set.set_selected(1, False)
        self.assertFalse(detection_a.selected)
        self.assertTrue(detection_b.selected)

        detection_set.set_selected(None, False)
        self.assertFalse(detection_a.selected)
        self.assertFalse(detection_b.selected)
        self.assertEqual(detection_set.selected_detection_count(), 0)

        detection_set.set_selected(None, True)
        self.assertTrue(detection_a.selected)
        self.assertTrue(detection_b.selected)
        self.assertEqual(detection_set.selected_detection_count(), 2)

    def test_add_detection_and_clear_frame_keep_structure_consistent(self) -> None:
        detection_set = YoloDetectionSet(
            model_name="yolo11s.pt",
            source_path="/tmp/sequence.mpp",
        )
        detection = YoloDetection(
            frame_index=3,
            bbox=BBoxXYXY(1.0, 2.0, 3.0, 4.0),
            confidence=0.55,
            model_name="yolo11s.pt",
        )

        detection_set.add_detection(detection)
        self.assertEqual(detection_set.frame_indices, [3])
        self.assertEqual(detection_set.get_detections(3), [detection])

        detection_set.clear_frame(3)
        self.assertEqual(detection_set.frame_indices, [])
        self.assertEqual(detection_set.get_detections(3), [])

    def test_rejects_mismatched_frame_key_or_model_name(self) -> None:
        with self.assertRaises(ValueError):
            YoloDetectionSet(
                model_name="yolo11s.pt",
                source_path="/tmp/sequence.mpp",
                detections_by_frame={
                    2: [
                        YoloDetection(
                            frame_index=3,
                            bbox=BBoxXYXY(1.0, 1.0, 2.0, 2.0),
                            confidence=0.5,
                            model_name="yolo11s.pt",
                        )
                    ]
                },
            )

        with self.assertRaises(ValueError):
            YoloDetectionSet(
                model_name="yolo11s.pt",
                source_path="/tmp/sequence.mpp",
                detections_by_frame={
                    2: [
                        YoloDetection(
                            frame_index=2,
                            bbox=BBoxXYXY(1.0, 1.0, 2.0, 2.0),
                            confidence=0.5,
                            model_name="yolo11m.pt",
                        )
                    ]
                },
            )


if __name__ == "__main__":
    unittest.main()
