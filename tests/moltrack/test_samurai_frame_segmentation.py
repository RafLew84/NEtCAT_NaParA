import unittest

import numpy as np


class MolTrackSamuraiFrameSegmentationTests(unittest.TestCase):
    def test_samurai_frame_segmentation_maps_prompts_to_mask_tracker_runs_and_returns_instance_masks(self) -> None:
        from moltrack.core import SegmentationPrompt
        from moltrack.masks import SamuraiFrameSegmentationBackend, SamuraiFrameSegmentationConfig
        from nanotrack.mask_trackers import MaskTrackerKind, MaskTrackerRunOutput

        class FakeSamuraiBackend:
            def __init__(self) -> None:
                self.inputs = []

            def run(self, run_input):
                self.inputs.append(run_input)
                mask = np.zeros((1, 6, 8), dtype=bool)
                if run_input.track_id == 0:
                    mask[0, 2:4, 3:5] = True
                    score = 1.0
                else:
                    mask[0, 1:3, 1:4] = True
                    score = 0.67
                return MaskTrackerRunOutput(
                    tracker_kind=MaskTrackerKind.SAMURAI,
                    track_id=run_input.track_id,
                    frame_index_offset=run_input.frame_index_offset,
                    masks=mask,
                    visible_mask=np.asarray([True]),
                    mask_scores=np.asarray([score], dtype=np.float32),
                    model_name="samurai",
                    model_variant="sam2.1_hiera_base_plus",
                    checkpoint_name="sam2.1_hiera_base_plus.pt",
                )

        frame = np.zeros((6, 8), dtype=np.float32)
        prompts = (
            SegmentationPrompt(
                detection_id="mol-a",
                working_frame_index=4,
                source_frame_index=10,
                bbox_prompt_xyxy=(2.0, 1.0, 5.0, 4.0),
                center_point_xy=(3.5, 2.5),
            ),
            SegmentationPrompt(
                detection_id="mol-b",
                working_frame_index=4,
                source_frame_index=10,
                bbox_prompt_xyxy=(0.0, 0.0, 4.0, 3.0),
                center_point_xy=(2.0, 1.5),
            ),
        )
        fake_backend = FakeSamuraiBackend()

        masks = SamuraiFrameSegmentationBackend(
            mask_tracker_backend=fake_backend,
            config=SamuraiFrameSegmentationConfig(
                source_view="registered",
                mask_probability_threshold=0.6,
            ),
        ).segment_frame(frame, prompts)

        self.assertEqual([mask.detection_id for mask in masks], ["mol-a", "mol-b"])
        self.assertEqual([mask.backend_name for mask in masks], ["samurai", "samurai"])
        self.assertEqual([mask.working_frame_index for mask in masks], [4, 4])
        self.assertEqual([mask.source_frame_index for mask in masks], [10, 10])
        self.assertAlmostEqual(masks[0].score, 1.0)
        self.assertAlmostEqual(masks[1].score, 0.67)
        self.assertEqual(masks[0].measurement_area_px2, 4)
        self.assertEqual(masks[1].measurement_area_px2, 6)
        self.assertEqual(dict(masks[0].backend_params)["source_view"], "registered")
        self.assertEqual(dict(masks[0].backend_params)["mask_probability_threshold"], 0.6)
        self.assertEqual(dict(masks[0].backend_params)["temporal_propagation_role"], "temporal_proposal")
        self.assertEqual(dict(masks[0].backend_params)["model_variant"], "sam2.1_hiera_base_plus")
        self.assertEqual(dict(masks[0].backend_params)["checkpoint_name"], "sam2.1_hiera_base_plus.pt")

        self.assertEqual(len(fake_backend.inputs), 2)
        first_input = fake_backend.inputs[0]
        self.assertEqual(first_input.tracker_kind, MaskTrackerKind.SAMURAI)
        np.testing.assert_array_equal(first_input.frames, frame[np.newaxis, ...])
        np.testing.assert_allclose(first_input.query_box_xyxy, np.asarray([2.0, 1.0, 5.0, 4.0], dtype=np.float32))
        np.testing.assert_allclose(first_input.query_point_tyx, np.asarray([0.0, 2.5, 3.5], dtype=np.float32))
        self.assertEqual(first_input.frame_index_offset, 4)
        self.assertEqual(first_input.source_view, "registered")
        self.assertEqual(first_input.mask_probability_threshold, 0.6)

    def test_samurai_frame_segmentation_validates_prompt_scope_and_handles_invisible_output(self) -> None:
        from moltrack.core import SegmentationPrompt
        from moltrack.masks import SamuraiFrameSegmentationBackend
        from nanotrack.mask_trackers import MaskTrackerKind, MaskTrackerRunOutput

        class InvisibleSamuraiBackend:
            def run(self, run_input):
                mask = np.ones((1, 4, 4), dtype=bool)
                return MaskTrackerRunOutput(
                    tracker_kind=MaskTrackerKind.SAMURAI,
                    track_id=run_input.track_id,
                    frame_index_offset=run_input.frame_index_offset,
                    masks=mask,
                    visible_mask=np.asarray([False]),
                    mask_scores=np.asarray([0.92], dtype=np.float32),
                    model_name="samurai",
                    model_variant="sam2.1_hiera_base_plus",
                    checkpoint_name="sam2.1_hiera_base_plus.pt",
                )

        prompt = SegmentationPrompt(
            detection_id="mol-a",
            working_frame_index=1,
            source_frame_index=5,
            bbox_prompt_xyxy=(0.0, 0.0, 3.0, 3.0),
            center_point_xy=(1.5, 1.5),
        )
        other_frame_prompt = SegmentationPrompt(
            detection_id="mol-b",
            working_frame_index=2,
            source_frame_index=6,
            bbox_prompt_xyxy=(0.0, 0.0, 3.0, 3.0),
            center_point_xy=(1.5, 1.5),
        )
        backend = SamuraiFrameSegmentationBackend(mask_tracker_backend=InvisibleSamuraiBackend())

        self.assertEqual(backend.segment_frame(np.zeros((4, 4), dtype=np.float32), ()), ())
        with self.assertRaises(ValueError):
            backend.segment_frame(np.zeros((4, 4), dtype=np.float32), (prompt, other_frame_prompt))

        result = backend.segment_frame(np.zeros((4, 4), dtype=np.float32), (prompt,))[0]
        self.assertEqual(result.measurement_area_px2, 0)
        self.assertEqual(result.score, 0.0)
        self.assertEqual(dict(result.backend_params)["temporal_propagation_role"], "temporal_proposal")


if __name__ == "__main__":
    unittest.main()
