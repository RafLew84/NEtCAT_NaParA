import unittest

import numpy as np


class MolTrackClassicalLocalRefinementTests(unittest.TestCase):
    def test_classical_local_refinement_segments_bright_particle_component_from_detection_prompt(self) -> None:
        from moltrack.core import DetectionReviewStatus, MolecularDetection, SegmentationPrompt
        from moltrack.masks import ClassicalLocalRefinementBackend, ClassicalLocalRefinementConfig

        frame = np.full((12, 12), 10.0, dtype=np.float32)
        frame[5:8, 5:8] = 80.0
        detection = MolecularDetection(
            detection_id="mol-001",
            working_frame_index=0,
            source_frame_index=0,
            bbox_xyxy=(4.0, 4.0, 8.0, 8.0),
            confidence=0.9,
            model_name="manual",
            review_status=DetectionReviewStatus.ACCEPTED,
            backend_name="manual",
            run_mode="full_frame",
        )
        prompt = SegmentationPrompt.from_detection(detection)

        instance_mask = ClassicalLocalRefinementBackend(
            ClassicalLocalRefinementConfig(
                polarity="bright",
                crop_margin_px=2,
                threshold_k=2.5,
            )
        ).segment(frame, prompt)

        expected = np.zeros_like(frame, dtype=bool)
        expected[5:8, 5:8] = True
        self.assertEqual(instance_mask.detection_id, "mol-001")
        self.assertEqual(instance_mask.working_frame_index, 0)
        self.assertEqual(instance_mask.source_frame_index, 0)
        self.assertEqual(instance_mask.backend_name, "classical_local_refinement")
        self.assertEqual(dict(instance_mask.backend_params)["polarity"], "bright")
        self.assertEqual(instance_mask.mask_shape, frame.shape)
        self.assertEqual(instance_mask.candidate_count, 3)
        self.assertEqual(instance_mask.measurement_area_px2, 9)
        self.assertGreater(instance_mask.score, 0.0)
        np.testing.assert_array_equal(instance_mask.measurement_mask, expected)

    def test_classical_local_refinement_segments_dark_particle_with_clipped_crop(self) -> None:
        from moltrack.core import DetectionReviewStatus, MolecularDetection, SegmentationPrompt
        from moltrack.masks import ClassicalLocalRefinementConfig, run_classical_local_refinement

        frame = np.full((8, 8), 100.0, dtype=np.float32)
        frame[1:3, 1:3] = 5.0
        detection = MolecularDetection(
            detection_id="dark-mol",
            working_frame_index=0,
            source_frame_index=0,
            bbox_xyxy=(0.0, 0.0, 3.0, 3.0),
            confidence=0.9,
            model_name="manual",
            review_status=DetectionReviewStatus.ACCEPTED,
            backend_name="manual",
            run_mode="full_frame",
        )
        prompt = SegmentationPrompt.from_detection(detection)

        instance_mask = run_classical_local_refinement(
            frame,
            prompt,
            ClassicalLocalRefinementConfig(
                polarity="dark",
                crop_margin_px=3,
                threshold_k=2.5,
            ),
        )

        expected = np.zeros_like(frame, dtype=bool)
        expected[1:3, 1:3] = True
        self.assertEqual(instance_mask.backend_name, "classical_local_refinement")
        self.assertEqual(dict(instance_mask.backend_params)["polarity"], "dark")
        self.assertEqual(instance_mask.measurement_area_px2, 4)
        np.testing.assert_array_equal(instance_mask.measurement_mask, expected)


if __name__ == "__main__":
    unittest.main()
