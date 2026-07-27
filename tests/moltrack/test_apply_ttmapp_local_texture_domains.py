import unittest
from types import SimpleNamespace

import numpy as np

from scripts.apply_ttmapp_local_texture_domains import (
    InferencePoint,
    _build_domain_components,
    _partition_metrics,
    _segmentation_centroid,
    _validate_unique_segmentation_prompts,
    _validate_prototype_provenance,
    _validate_reference_scope,
)
from scripts.experiment_ttmapp_local_texture_domains import ReferencePoint


class AutonomousDomainComponentsTests(unittest.TestCase):
    @staticmethod
    def _reference(frame_number, split):
        return ReferencePoint(
            frame_number=frame_number,
            split=split,
            class_name="BLACK",
            instance_label="BLACK_01",
            source_id=f"source-{frame_number}",
            x_px=10.0,
            y_px=20.0,
        )

    def test_reference_scope_rejects_a_holdout_frame_marked_as_calibration(self):
        reference = (
            self._reference(250, "calibration"),
            self._reference(263, "calibration"),
        )
        report = {
            "calibration_frames": list(range(250, 263)),
            "holdout_frames": list(range(263, 269)),
        }

        with self.assertRaisesRegex(ValueError, "split"):
            _validate_reference_scope(
                reference,
                report,
                first_frame=250,
                last_frame=268,
                holdout_start=263,
            )

    def test_reference_scope_rejects_a_report_with_holdout_leakage(self):
        reference = (
            self._reference(250, "calibration"),
            self._reference(263, "holdout"),
        )
        report = {
            "calibration_frames": list(range(250, 264)),
            "holdout_frames": list(range(264, 269)),
        }

        with self.assertRaisesRegex(ValueError, "calibration_frames"):
            _validate_reference_scope(
                reference,
                report,
                first_frame=250,
                last_frame=268,
                holdout_start=263,
            )

    def test_prototype_provenance_rejects_a_different_calibration(self):
        stored = np.zeros((3, 90), dtype=np.float64)
        recomputed = stored.copy()
        recomputed[0, 0] = 1e-4

        with self.assertRaisesRegex(ValueError, "prototype"):
            _validate_prototype_provenance(stored, recomputed)

    def test_cropped_segmentation_centroid_includes_bbox_origin(self):
        mask = np.asarray(
            (
                (False, False, False),
                (False, True, True),
            ),
            dtype=bool,
        )
        segmentation = SimpleNamespace(
            mask=mask,
            bbox_xyxy=(100.0, 50.0, 103.0, 52.0),
        )

        self.assertEqual(
            _segmentation_centroid(segmentation),
            (102.0, 51.5),
        )

    def test_duplicate_segmentation_prompt_is_rejected(self):
        segmentations = (
            SimpleNamespace(
                segmentation_id="mask-a",
                prompt_detection_ids=("detection-1",),
            ),
            SimpleNamespace(
                segmentation_id="mask-b",
                prompt_detection_ids=("detection-1",),
            ),
        )

        with self.assertRaisesRegex(ValueError, "detection-1"):
            _validate_unique_segmentation_prompts(
                segmentations,
                frame_number=250,
            )

    def test_small_components_are_rejected_as_unknown(self):
        points = (
            InferencePoint(263, "a", 10.0, 10.0),
            InferencePoint(263, "b", 20.0, 10.0),
            InferencePoint(263, "c", 30.0, 10.0),
            InferencePoint(263, "d", 80.0, 10.0),
            InferencePoint(263, "e", 90.0, 10.0),
            InferencePoint(263, "f", 120.0, 10.0),
        )
        predictions = np.asarray((0, 0, 0, 1, 1, -1), dtype=np.int64)
        neighbors = (
            np.asarray((1,), dtype=np.int64),
            np.asarray((0, 2), dtype=np.int64),
            np.asarray((1,), dtype=np.int64),
            np.asarray((4,), dtype=np.int64),
            np.asarray((3,), dtype=np.int64),
            np.asarray((), dtype=np.int64),
        )

        filtered, assignments, components = _build_domain_components(
            points,
            predictions,
            neighbors,
            minimum_component_size=3,
        )

        self.assertEqual(filtered.tolist(), [0, 0, 0, -1, -1, -1])
        self.assertEqual(assignments[:3], ("BLACK_01",) * 3)
        self.assertEqual(assignments[3:], ("", "", ""))
        self.assertEqual(len(components), 1)
        self.assertEqual(components[0].component_id, "BLACK_01")
        self.assertEqual(components[0].member_indices, (0, 1, 2))

    def test_component_ids_are_scoped_per_frame_and_class(self):
        points = (
            InferencePoint(263, "a", 10.0, 10.0),
            InferencePoint(263, "b", 20.0, 10.0),
            InferencePoint(264, "c", 10.0, 10.0),
            InferencePoint(264, "d", 20.0, 10.0),
        )
        predictions = np.asarray((0, 0, 0, 0), dtype=np.int64)
        neighbors = (
            np.asarray((1,), dtype=np.int64),
            np.asarray((0,), dtype=np.int64),
            np.asarray((3,), dtype=np.int64),
            np.asarray((2,), dtype=np.int64),
        )

        _filtered, assignments, components = _build_domain_components(
            points,
            predictions,
            neighbors,
            minimum_component_size=2,
        )

        self.assertEqual(
            assignments,
            ("BLACK_01", "BLACK_01", "BLACK_01", "BLACK_01"),
        )
        self.assertEqual(
            [(value.frame_number, value.component_id) for value in components],
            [(263, "BLACK_01"), (264, "BLACK_01")],
        )

    def test_partition_metrics_report_a_merge_of_manual_instances(self):
        points = (
            InferencePoint(263, "a", 10.0, 10.0),
            InferencePoint(263, "b", 20.0, 10.0),
            InferencePoint(263, "c", 30.0, 10.0),
            InferencePoint(263, "d", 40.0, 10.0),
        )
        reference = tuple(
            ReferencePoint(
                frame_number=263,
                split="holdout",
                class_name="BLACK",
                instance_label=("BLACK_01" if index < 2 else "BLACK_02"),
                source_id=point.source_id,
                x_px=point.x_px,
                y_px=point.y_px,
            )
            for index, point in enumerate(points)
        )

        metrics = _partition_metrics(
            reference,
            points,
            np.asarray((0, 0, 0, 0), dtype=np.int64),
            ("BLACK_01", "BLACK_01", "BLACK_01", "BLACK_01"),
        )

        self.assertEqual(metrics["manual_instance_count"], 2)
        self.assertEqual(metrics["predicted_component_count"], 1)
        self.assertEqual(metrics["merged_component_count"], 1)
        self.assertAlmostEqual(metrics["mean_manual_instance_recovery"], 1.0)
        self.assertAlmostEqual(metrics["mean_predicted_component_purity"], 0.5)


if __name__ == "__main__":
    unittest.main()
