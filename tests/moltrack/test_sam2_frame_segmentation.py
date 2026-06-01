import unittest

import numpy as np


class MolTrackSam2FrameSegmentationTests(unittest.TestCase):
    def test_sam2_frame_segmentation_maps_prompts_to_subprocess_runs_and_returns_instance_masks(self) -> None:
        from moltrack.core import SegmentationPrompt
        from moltrack.masks import Sam2FrameSegmentationBackend, Sam2FrameSegmentationConfig
        from nanotrack.sam2 import Sam2RunOutput

        class FakeSam2Backend:
            def __init__(self) -> None:
                self.inputs = []

            def run(self, run_input):
                self.inputs.append(run_input)
                mask = np.zeros((1, 6, 8), dtype=bool)
                if run_input.track_id == 0:
                    mask[0, 2:4, 3:5] = True
                    score = 0.91
                else:
                    mask[0, 1:3, 1:4] = True
                    score = 0.73
                return Sam2RunOutput(
                    track_id=run_input.track_id,
                    frame_index_offset=run_input.frame_index_offset,
                    masks=mask,
                    visible_mask=np.asarray([True]),
                    mask_scores=np.asarray([score], dtype=np.float32),
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
        fake_backend = FakeSam2Backend()

        masks = Sam2FrameSegmentationBackend(
            sam2_backend=fake_backend,
            config=Sam2FrameSegmentationConfig(
                source_view="bm3d+registered",
                mask_probability_threshold=0.65,
            ),
        ).segment_frame(frame, prompts)

        self.assertEqual([mask.detection_id for mask in masks], ["mol-a", "mol-b"])
        self.assertEqual([mask.backend_name for mask in masks], ["sam2", "sam2"])
        self.assertEqual([mask.working_frame_index for mask in masks], [3, 3])
        self.assertEqual([mask.source_frame_index for mask in masks], [9, 9])
        self.assertAlmostEqual(masks[0].score, 0.91)
        self.assertAlmostEqual(masks[1].score, 0.73)
        self.assertEqual(dict(masks[0].backend_params)["source_view"], "bm3d+registered")
        self.assertEqual(dict(masks[0].backend_params)["mask_probability_threshold"], 0.65)
        self.assertEqual(masks[0].measurement_area_px2, 4)
        self.assertEqual(masks[1].measurement_area_px2, 6)

        self.assertEqual(len(fake_backend.inputs), 2)
        first_input = fake_backend.inputs[0]
        np.testing.assert_array_equal(first_input.frames, frame[np.newaxis, ...])
        np.testing.assert_allclose(first_input.query_box_xyxy, np.asarray([2.0, 1.0, 5.0, 4.0], dtype=np.float32))
        np.testing.assert_allclose(first_input.query_point_tyx, np.asarray([0.0, 2.5, 3.5], dtype=np.float32))
        self.assertEqual(first_input.frame_index_offset, 3)
        self.assertEqual(first_input.source_view, "bm3d+registered")
        self.assertEqual(first_input.mask_probability_threshold, 0.65)

    def test_sam2_frame_segmentation_validates_prompt_scope_and_handles_invisible_output(self) -> None:
        from moltrack.core import SegmentationPrompt
        from moltrack.masks import Sam2FrameSegmentationBackend
        from nanotrack.sam2 import Sam2RunOutput

        class InvisibleSam2Backend:
            def run(self, run_input):
                mask = np.ones((1, 4, 4), dtype=bool)
                return Sam2RunOutput(
                    track_id=run_input.track_id,
                    frame_index_offset=run_input.frame_index_offset,
                    masks=mask,
                    visible_mask=np.asarray([False]),
                    mask_scores=np.asarray([0.88], dtype=np.float32),
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
        backend = Sam2FrameSegmentationBackend(sam2_backend=InvisibleSam2Backend())

        self.assertEqual(backend.segment_frame(np.zeros((4, 4), dtype=np.float32), ()), ())
        with self.assertRaises(ValueError):
            backend.segment_frame(np.zeros((4, 4), dtype=np.float32), (prompt, other_frame_prompt))

        result = backend.segment_frame(np.zeros((4, 4), dtype=np.float32), (prompt,))[0]
        self.assertEqual(result.measurement_area_px2, 0)
        self.assertEqual(result.score, 0.0)


if __name__ == "__main__":
    unittest.main()
