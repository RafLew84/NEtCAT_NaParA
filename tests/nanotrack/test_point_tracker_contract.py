import unittest

import numpy as np

from nanotrack.trackers import POINT_TRACKER_CONTRACT_VERSION, PointTrackerRunInput, PointTrackerRunOutput


class PointTrackerRunInputTests(unittest.TestCase):
    def test_round_trip_preserves_optional_runtime_fields(self) -> None:
        run_input = PointTrackerRunInput(
            frames=np.zeros((4, 16, 16), dtype=np.float32),
            query_points_tyx=np.asarray([[0.0, 5.0, 6.0], [2.0, 8.0, 9.0]], dtype=np.float32),
            inference_resolution_hw=np.asarray([256, 256], dtype=np.int32),
            device="cuda",
            query_chunk_size=8,
            causal=True,
            window_size=12,
            window_overlap=4,
            source_view="repair+bm3d",
        )

        payload = run_input.to_npz_payload()

        self.assertEqual(int(payload["contract_version"].item()), POINT_TRACKER_CONTRACT_VERSION)
        restored = PointTrackerRunInput.from_npz_payload(payload)
        np.testing.assert_array_equal(restored.frames, run_input.frames)
        np.testing.assert_array_equal(restored.query_points_tyx, run_input.query_points_tyx)
        np.testing.assert_array_equal(restored.inference_resolution_hw, run_input.inference_resolution_hw)
        self.assertEqual(restored.device, "cuda")
        self.assertEqual(restored.query_chunk_size, 8)
        self.assertTrue(restored.causal)
        self.assertEqual(restored.window_size, 12)
        self.assertEqual(restored.window_overlap, 4)
        self.assertEqual(restored.source_view, "repair+bm3d")

    def test_rejects_query_points_outside_local_frame_range(self) -> None:
        with self.assertRaises(ValueError):
            PointTrackerRunInput(
                frames=np.zeros((3, 8, 8), dtype=np.float32),
                query_points_tyx=np.asarray([[3.0, 2.0, 2.0]], dtype=np.float32),
            )


class PointTrackerRunOutputTests(unittest.TestCase):
    def test_round_trip_preserves_optional_outputs(self) -> None:
        run_output = PointTrackerRunOutput(
            tracks_xy=np.asarray(
                [
                    [[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]],
                    [[2.0, 1.0], [4.0, 3.0], [6.0, 5.0]],
                ],
                dtype=np.float32,
            ),
            visible_mask=np.asarray([[1, 1, 0], [1, 0, 0]], dtype=bool),
            occlusion_scores=np.asarray([[0.1, 0.2, 0.8], [0.0, 0.7, 0.9]], dtype=np.float32),
            confidence_scores=np.asarray([[0.9, 0.8, 0.2], [0.95, 0.4, 0.1]], dtype=np.float32),
            expected_dist=np.asarray([[1.0, 1.2, 2.5], [0.8, 1.6, 3.1]], dtype=np.float32),
            model_name="tapir",
            checkpoint_name="tapir_checkpoint.pt",
        )

        payload = run_output.to_npz_payload()

        self.assertEqual(int(payload["contract_version"].item()), POINT_TRACKER_CONTRACT_VERSION)
        restored = PointTrackerRunOutput.from_npz_payload(payload)
        np.testing.assert_array_equal(restored.tracks_xy, run_output.tracks_xy)
        np.testing.assert_array_equal(restored.visible_mask, run_output.visible_mask)
        np.testing.assert_array_equal(restored.occlusion_scores, run_output.occlusion_scores)
        np.testing.assert_array_equal(restored.confidence_scores, run_output.confidence_scores)
        np.testing.assert_array_equal(restored.expected_dist, run_output.expected_dist)
        self.assertEqual(restored.model_name, "tapir")
        self.assertEqual(restored.checkpoint_name, "tapir_checkpoint.pt")

    def test_rejects_visible_mask_shape_mismatch(self) -> None:
        with self.assertRaises(ValueError):
            PointTrackerRunOutput(
                tracks_xy=np.zeros((2, 4, 2), dtype=np.float32),
                visible_mask=np.zeros((4,), dtype=bool),
            )


if __name__ == "__main__":
    unittest.main()
