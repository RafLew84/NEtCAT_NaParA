import unittest

import numpy as np


class MolTrackDam4SamFrameSegmentationTests(unittest.TestCase):
    def test_dam4sam_frame_segmentation_maps_prompts_to_mask_tracker_runs_and_returns_instance_masks(self) -> None:
        from moltrack.core import SegmentationPrompt
        from moltrack.masks import Dam4SamFrameSegmentationBackend, Dam4SamFrameSegmentationConfig
        from nanotrack.mask_trackers import MaskTrackerKind, MaskTrackerRunOutput

        class FakeDam4SamBackend:
            def __init__(self) -> None:
                self.inputs = []

            def run(self, run_input):
                self.inputs.append(run_input)
                mask = np.zeros((1, 6, 8), dtype=bool)
                if run_input.track_id == 0:
                    mask[0, 2:4, 3:5] = True
                    score = 0.86
                else:
                    mask[0, 1:3, 1:4] = True
                    score = 0.72
                return MaskTrackerRunOutput(
                    tracker_kind=MaskTrackerKind.DAM4SAM,
                    track_id=run_input.track_id,
                    frame_index_offset=run_input.frame_index_offset,
                    masks=mask,
                    visible_mask=np.asarray([True]),
                    mask_scores=np.asarray([score], dtype=np.float32),
                    model_name="dam4sam",
                    model_variant="sam21pp-B",
                    checkpoint_name="sam2.1_hiera_base_plus.pt",
                )

        frame = np.zeros((6, 8), dtype=np.float32)
        prompts = (
            SegmentationPrompt(
                detection_id="mol-a",
                working_frame_index=3,
                source_frame_index=9,
                bbox_prompt_xyxy=(2.0, 1.0, 5.0, 4.0),
                center_point_xy=(3.5, 2.5),
                negative_points_xy=((1.0, 1.0),),
            ),
            SegmentationPrompt(
                detection_id="mol-b",
                working_frame_index=3,
                source_frame_index=9,
                bbox_prompt_xyxy=(0.0, 0.0, 4.0, 3.0),
                center_point_xy=(2.0, 1.5),
            ),
        )
        fake_backend = FakeDam4SamBackend()

        masks = Dam4SamFrameSegmentationBackend(
            mask_tracker_backend=fake_backend,
            config=Dam4SamFrameSegmentationConfig(
                source_view="repair+registered",
                mask_probability_threshold=0.7,
            ),
        ).segment_frame(frame, prompts)

        self.assertEqual([mask.detection_id for mask in masks], ["mol-a", "mol-b"])
        self.assertEqual([mask.backend_name for mask in masks], ["dam4sam", "dam4sam"])
        self.assertEqual([mask.working_frame_index for mask in masks], [3, 3])
        self.assertEqual([mask.source_frame_index for mask in masks], [9, 9])
        self.assertAlmostEqual(masks[0].score, 0.86)
        self.assertAlmostEqual(masks[1].score, 0.72)
        self.assertEqual(masks[0].measurement_area_px2, 4)
        self.assertEqual(masks[1].measurement_area_px2, 6)
        self.assertEqual(dict(masks[0].backend_params)["source_view"], "repair+registered")
        self.assertEqual(dict(masks[0].backend_params)["mask_probability_threshold"], 0.7)
        self.assertEqual(dict(masks[0].backend_params)["temporal_propagation_role"], "proposal_only")
        self.assertEqual(dict(masks[0].backend_params)["model_variant"], "sam21pp-B")
        self.assertEqual(dict(masks[0].backend_params)["checkpoint_name"], "sam2.1_hiera_base_plus.pt")

        self.assertEqual(len(fake_backend.inputs), 2)
        first_input = fake_backend.inputs[0]
        self.assertEqual(first_input.tracker_kind, MaskTrackerKind.DAM4SAM)
        np.testing.assert_array_equal(first_input.frames, frame[np.newaxis, ...])
        np.testing.assert_allclose(first_input.query_box_xyxy, np.asarray([2.0, 1.0, 5.0, 4.0], dtype=np.float32))
        np.testing.assert_allclose(first_input.query_point_tyx, np.asarray([0.0, 2.5, 3.5], dtype=np.float32))
        self.assertEqual(first_input.frame_index_offset, 3)
        self.assertEqual(first_input.source_view, "repair+registered")
        self.assertEqual(first_input.mask_probability_threshold, 0.7)

    def test_dam4sam_frame_segmentation_validates_prompt_scope_and_handles_invisible_output(self) -> None:
        from moltrack.core import SegmentationPrompt
        from moltrack.masks import Dam4SamFrameSegmentationBackend
        from nanotrack.mask_trackers import MaskTrackerKind, MaskTrackerRunOutput

        class InvisibleDam4SamBackend:
            def run(self, run_input):
                mask = np.ones((1, 4, 4), dtype=bool)
                return MaskTrackerRunOutput(
                    tracker_kind=MaskTrackerKind.DAM4SAM,
                    track_id=run_input.track_id,
                    frame_index_offset=run_input.frame_index_offset,
                    masks=mask,
                    visible_mask=np.asarray([False]),
                    mask_scores=np.asarray([0.88], dtype=np.float32),
                    model_name="dam4sam",
                    model_variant="sam21pp-B",
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
        backend = Dam4SamFrameSegmentationBackend(mask_tracker_backend=InvisibleDam4SamBackend())

        self.assertEqual(backend.segment_frame(np.zeros((4, 4), dtype=np.float32), ()), ())
        with self.assertRaises(ValueError):
            backend.segment_frame(np.zeros((4, 4), dtype=np.float32), (prompt, other_frame_prompt))

        result = backend.segment_frame(np.zeros((4, 4), dtype=np.float32), (prompt,))[0]
        self.assertEqual(result.measurement_area_px2, 0)
        self.assertEqual(result.score, 0.0)
        self.assertEqual(dict(result.backend_params)["temporal_propagation_role"], "proposal_only")


if __name__ == "__main__":
    unittest.main()
