import unittest

import numpy as np

from nanotrack.edges import refine_edge_polyline


class EdgeRefinementTests(unittest.TestCase):
    def test_edge_prob_mode_snaps_to_offset_edge_response(self) -> None:
        polygon_mask = np.ones((20, 24), dtype=bool)
        coarse_polyline = np.asarray([[2.0, 8.0], [21.0, 8.0]], dtype=np.float64)
        edge_prob = np.zeros((20, 24), dtype=np.float32)
        input_frame = np.zeros_like(edge_prob, dtype=np.float32)

        edge_prob[8, 2:12] = 1.0
        edge_prob[10, 12:22] = 1.0
        input_frame[8, 2:12] = 1.0
        input_frame[10, 12:22] = 1.0

        result = refine_edge_polyline(
            coarse_polyline,
            edge_prob=edge_prob,
            input_frame=input_frame,
            polygon_mask=polygon_mask,
            score_mode="edge_prob",
            search_radius_px=3,
            max_points=48,
        )

        self.assertEqual(result.score_mode, "edge_prob")
        self.assertEqual(result.refinement_mode, "normal_search_edge_prob")
        self.assertGreaterEqual(result.point_count, 10)
        left_half = result.polyline_xy[result.polyline_xy[:, 0] < 12.0]
        right_half = result.polyline_xy[result.polyline_xy[:, 0] >= 12.0]
        self.assertGreater(len(left_half), 0)
        self.assertGreater(len(right_half), 0)
        self.assertLess(float(np.mean(left_half[:, 1])), 9.0)
        self.assertGreater(float(np.mean(right_half[:, 1])), 9.0)

    def test_gradient_mode_uses_image_boundary(self) -> None:
        polygon_mask = np.ones((20, 24), dtype=bool)
        coarse_polyline = np.asarray([[2.0, 6.0], [21.0, 6.0]], dtype=np.float64)
        edge_prob = np.zeros((20, 24), dtype=np.float32)
        input_frame = np.zeros((20, 24), dtype=np.float32)
        input_frame[10:, :] = 1.0

        result = refine_edge_polyline(
            coarse_polyline,
            edge_prob=edge_prob,
            input_frame=input_frame,
            polygon_mask=polygon_mask,
            score_mode="gradient",
            search_radius_px=5,
            max_points=48,
        )

        self.assertEqual(result.score_mode, "gradient")
        self.assertEqual(result.refinement_mode, "normal_search_gradient")
        self.assertGreater(float(np.mean(result.polyline_xy[:, 1])), 8.0)
        self.assertGreater(result.mean_shift_px, 1.0)

    def test_validates_unknown_score_mode(self) -> None:
        with self.assertRaises(ValueError):
            refine_edge_polyline(
                np.asarray([[0.0, 0.0], [5.0, 0.0]], dtype=np.float64),
                edge_prob=np.zeros((8, 8), dtype=np.float32),
                input_frame=np.zeros((8, 8), dtype=np.float32),
                polygon_mask=np.ones((8, 8), dtype=bool),
                score_mode="unknown",
            )


if __name__ == "__main__":
    unittest.main()
