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
        self.assertEqual(detection.original_bbox_xyxy, detection.bbox_xyxy)
        self.assertTrue(detection.detection_id)
        self.assertEqual(detection.origin, "yolo")

    def test_molecular_detection_keeps_explicit_original_bbox_for_reset(self) -> None:
        detection = MolecularDetection(
            frame_index=0,
            bbox_xyxy=(2, 3, 8, 9),
            original_bbox_xyxy=(1, 2, 5, 6),
            confidence=0.9,
        )

        self.assertEqual(detection.bbox_xyxy, (2.0, 3.0, 8.0, 9.0))
        self.assertEqual(detection.original_bbox_xyxy, (1.0, 2.0, 5.0, 6.0))

    def test_molecular_detection_tracks_detection_id_and_origin(self) -> None:
        detection = MolecularDetection(
            frame_index=0,
            bbox_xyxy=(1, 1, 4, 4),
            confidence=1.0,
            model_name="manual",
            detection_id=" manual-1 ",
            origin=" manual ",
        )

        self.assertEqual(detection.detection_id, "manual-1")
        self.assertEqual(detection.origin, "manual")

        detections = MolecularDetectionSet(frame_count=1)
        detections.set_detections(0, [detection], source_view="raw", frame_shape=(5, 5))

        detections.resize_all(margin_px=1.0, source_view="raw", frame_shape=(5, 5))
        detections.reset_all_to_original(source_view="raw", frame_shape=(5, 5))

        self.assertEqual(detection.detection_id, "manual-1")
        self.assertEqual(detection.origin, "manual")

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
        with self.assertRaisesRegex(ValueError, "detection_id"):
            MolecularDetection(frame_index=0, bbox_xyxy=(0, 1, 4, 3), confidence=0.5, detection_id=" ")
        with self.assertRaisesRegex(ValueError, "origin"):
            MolecularDetection(frame_index=0, bbox_xyxy=(0, 1, 4, 3), confidence=0.5, origin="user")
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

    def test_detection_set_adds_manual_detection_for_frame_and_source_view(self) -> None:
        detections = MolecularDetectionSet(frame_count=2)

        detection = detections.add_detection(
            1,
            (1, 1, 4, 3),
            source_view="expanded_aligned",
            frame_shape=(5, 6),
        )

        self.assertEqual(detection.frame_index, 1)
        self.assertEqual(detection.bbox_xyxy, (1.0, 1.0, 4.0, 3.0))
        self.assertEqual(detection.original_bbox_xyxy, detection.bbox_xyxy)
        self.assertEqual(detection.confidence, 1.0)
        self.assertEqual(detection.model_name, "manual")
        self.assertEqual(detection.checkpoint_path, "")
        self.assertEqual(detection.source_view, "expanded_aligned")
        self.assertEqual(detection.origin, "manual")
        self.assertTrue(detection.detection_id)
        self.assertEqual(detections.get_detections(1, source_view="expanded_aligned"), [detection])
        self.assertEqual(detections.get_detections(0, source_view="expanded_aligned"), [])

    def test_detection_set_rejects_duplicate_detection_id_when_adding(self) -> None:
        detections = MolecularDetectionSet(frame_count=1)
        detections.add_detection(
            0,
            (0, 0, 2, 2),
            source_view="raw",
            frame_shape=(4, 4),
            detection_id="duplicate",
        )

        with self.assertRaisesRegex(ValueError, "detection_id"):
            detections.add_detection(
                0,
                (1, 1, 3, 3),
                source_view="raw",
                frame_shape=(4, 4),
                detection_id="duplicate",
            )

        self.assertEqual(len(detections.get_detections(0, source_view="raw")), 1)

    def test_detection_set_gets_and_removes_detection_by_id_without_cross_view_side_effects(self) -> None:
        detections = MolecularDetectionSet(frame_count=2)
        target = detections.add_detection(
            0,
            (0, 0, 2, 2),
            source_view="raw",
            frame_shape=(4, 4),
            detection_id="target",
        )
        same_frame_other_view = detections.add_detection(
            0,
            (1, 1, 3, 3),
            source_view="expanded_aligned",
            frame_shape=(4, 4),
            detection_id="expanded",
        )
        other_frame = detections.add_detection(
            1,
            (1, 1, 2, 2),
            source_view="raw",
            frame_shape=(4, 4),
            detection_id="other-frame",
        )

        self.assertIs(detections.get_detection("target"), target)

        removed = detections.remove_detection("target")

        self.assertIs(removed, target)
        self.assertIsNone(detections.get_detection("target"))
        self.assertEqual(detections.get_detections(0, source_view="raw"), [])
        self.assertEqual(detections.get_detections(0, source_view="expanded_aligned"), [same_frame_other_view])
        self.assertEqual(detections.get_detections(1, source_view="raw"), [other_frame])
        with self.assertRaisesRegex(KeyError, "missing"):
            detections.remove_detection("missing")

    def test_detection_set_updates_detection_bbox_by_id_with_validation(self) -> None:
        detections = MolecularDetectionSet(frame_count=1)
        detection = detections.add_detection(
            0,
            (1, 1, 3, 3),
            source_view="raw",
            frame_shape=(5, 5),
            detection_id="manual-1",
        )

        updated = detections.update_detection_bbox("manual-1", (0, 0, 4, 4), frame_shape=(5, 5))

        self.assertIs(updated, detection)
        self.assertEqual(detection.bbox_xyxy, (0.0, 0.0, 4.0, 4.0))
        self.assertEqual(detection.original_bbox_xyxy, (1.0, 1.0, 3.0, 3.0))

        with self.assertRaisesRegex(ValueError, "within frame"):
            detections.update_detection_bbox("manual-1", (0, 0, 6, 4), frame_shape=(5, 5))
        self.assertEqual(detection.bbox_xyxy, (0.0, 0.0, 4.0, 4.0))

        detections.update_detection_bbox(
            "manual-1",
            (1, 1, 2, 2),
            frame_shape=(5, 5),
            update_original=True,
        )

        self.assertEqual(detection.bbox_xyxy, (1.0, 1.0, 2.0, 2.0))
        self.assertEqual(detection.original_bbox_xyxy, (1.0, 1.0, 2.0, 2.0))
        with self.assertRaisesRegex(KeyError, "missing"):
            detections.update_detection_bbox("missing", (1, 1, 2, 2), frame_shape=(5, 5))

    def test_detection_set_resizes_detections_for_source_view(self) -> None:
        detections = MolecularDetectionSet(frame_count=2)
        raw_detection = MolecularDetection(frame_index=0, bbox_xyxy=(2, 2, 6, 6), confidence=0.9)
        expanded_detection = MolecularDetection(
            frame_index=0,
            bbox_xyxy=(0, 0, 2, 2),
            confidence=0.8,
            source_view="expanded_aligned",
        )
        detections.set_detections(0, [raw_detection], source_view="raw", frame_shape=(10, 10))
        detections.set_detections(
            0,
            [expanded_detection],
            source_view="expanded_aligned",
            frame_shape=(10, 10),
        )

        changed = detections.resize_all(scale_factor=1.5, source_view="raw", frame_shape=(10, 10))

        self.assertEqual(changed, 1)
        self.assertEqual(raw_detection.bbox_xyxy, (1.0, 1.0, 7.0, 7.0))
        self.assertEqual(raw_detection.original_bbox_xyxy, (2.0, 2.0, 6.0, 6.0))
        self.assertEqual(expanded_detection.bbox_xyxy, (0.0, 0.0, 2.0, 2.0))

    def test_detection_set_clamps_resized_bbox_and_resets_to_original(self) -> None:
        detections = MolecularDetectionSet(frame_count=1)
        detection = MolecularDetection(frame_index=0, bbox_xyxy=(0, 0, 2, 2), confidence=0.9)
        detections.set_detections(0, [detection], source_view="raw", frame_shape=(5, 5))

        changed = detections.resize_all(scale_factor=2.0, source_view="raw", frame_shape=(5, 5))

        self.assertEqual(changed, 1)
        self.assertEqual(detection.bbox_xyxy, (0.0, 0.0, 4.0, 4.0))

        changed = detections.resize_all(scale_factor=0.1, source_view="raw", frame_shape=(5, 5), min_size_px=1.0)

        self.assertEqual(changed, 1)
        self.assertEqual(detection.bbox_xyxy, (1.5, 1.5, 2.5, 2.5))

        changed = detections.reset_all_to_original(source_view="raw", frame_shape=(5, 5))

        self.assertEqual(changed, 1)
        self.assertEqual(detection.bbox_xyxy, (0.0, 0.0, 2.0, 2.0))

    def test_detection_set_resizes_with_pixel_margin(self) -> None:
        detections = MolecularDetectionSet(frame_count=1)
        detection = MolecularDetection(frame_index=0, bbox_xyxy=(2, 2, 6, 6), confidence=0.9)
        detections.set_detections(0, [detection], source_view="raw", frame_shape=(10, 10))

        changed = detections.resize_all(margin_px=1.0, source_view="raw", frame_shape=(10, 10))

        self.assertEqual(changed, 1)
        self.assertEqual(detection.bbox_xyxy, (1.0, 1.0, 7.0, 7.0))

        changed = detections.resize_all(margin_px=-2.0, source_view="raw", frame_shape=(10, 10))

        self.assertEqual(changed, 1)
        self.assertEqual(detection.bbox_xyxy, (3.0, 3.0, 5.0, 5.0))

    def test_detection_set_validates_resize_arguments(self) -> None:
        detections = MolecularDetectionSet(frame_count=1)
        detections.set_detections(
            0,
            [MolecularDetection(frame_index=0, bbox_xyxy=(0, 0, 2, 2), confidence=0.9)],
            source_view="raw",
            frame_shape=(5, 5),
        )

        with self.assertRaisesRegex(ValueError, "scale_factor"):
            detections.resize_all(scale_factor=0.0, source_view="raw", frame_shape=(5, 5))
        with self.assertRaisesRegex(ValueError, "min_size_px"):
            detections.resize_all(scale_factor=1.0, source_view="raw", frame_shape=(5, 5), min_size_px=0.0)
        with self.assertRaisesRegex(ValueError, "positive height and width"):
            detections.resize_all(scale_factor=1.0, source_view="raw", frame_shape=(0, 5))


if __name__ == "__main__":
    unittest.main()
