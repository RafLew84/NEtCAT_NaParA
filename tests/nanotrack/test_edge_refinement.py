import math
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
        self.assertEqual(result.refinement_mode, "normal_dp_edge_prob")
        self.assertEqual(result.subpixel_mode, "parabolic")
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
        self.assertEqual(result.refinement_mode, "normal_dp_gradient")
        self.assertGreater(float(np.mean(result.polyline_xy[:, 1])), 8.0)
        self.assertGreater(result.mean_shift_px, 1.0)

    def test_global_dp_suppresses_alternating_offset_jitter(self) -> None:
        polygon_mask = np.ones((28, 32), dtype=bool)
        coarse_polyline = np.asarray([[4.0, 12.0], [27.0, 12.0]], dtype=np.float64)
        edge_prob = np.zeros((28, 32), dtype=np.float32)
        input_frame = np.zeros_like(edge_prob, dtype=np.float32)

        edge_prob[12, 4:28] = 0.90
        for x in range(4, 28):
            edge_prob[10 if x % 2 == 0 else 14, x] = 1.0

        result = refine_edge_polyline(
            coarse_polyline,
            edge_prob=edge_prob,
            input_frame=input_frame,
            polygon_mask=polygon_mask,
            score_mode="edge_prob",
            search_radius_px=4,
            max_points=32,
        )

        self.assertEqual(result.refinement_mode, "normal_dp_edge_prob")
        self.assertLess(float(np.std(result.polyline_xy[:, 1])), 0.75)
        self.assertGreater(float(np.mean(result.polyline_xy[:, 1])), 11.25)
        self.assertLess(float(np.mean(result.polyline_xy[:, 1])), 12.75)

    def test_temporal_prior_can_break_parallel_edge_ties(self) -> None:
        polygon_mask = np.ones((24, 28), dtype=bool)
        coarse_polyline = np.asarray([[3.0, 11.0], [24.0, 11.0]], dtype=np.float64)
        prior_polyline = np.asarray([[3.0, 14.0], [24.0, 14.0]], dtype=np.float64)
        edge_prob = np.zeros((24, 28), dtype=np.float32)
        input_frame = np.zeros_like(edge_prob, dtype=np.float32)
        edge_prob[8, 3:25] = 1.0
        edge_prob[14, 3:25] = 1.0

        result = refine_edge_polyline(
            coarse_polyline,
            edge_prob=edge_prob,
            input_frame=input_frame,
            polygon_mask=polygon_mask,
            score_mode="edge_prob",
            search_radius_px=4,
            max_points=32,
            prior_polyline_xy=prior_polyline,
            temporal_lambda=0.25,
        )

        self.assertGreater(float(np.mean(result.polyline_xy[:, 1])), 13.0)

    def test_parabolic_subpixel_fit_improves_fractional_edge_position(self) -> None:
        polygon_mask = np.ones((24, 30), dtype=bool)
        coarse_polyline = np.asarray([[4.0, 8.0], [25.0, 8.0]], dtype=np.float64)
        edge_prob = np.zeros((24, 30), dtype=np.float32)
        input_frame = np.zeros_like(edge_prob, dtype=np.float32)

        target_y = 10.3
        profile_y = np.arange(edge_prob.shape[0], dtype=np.float64)
        smooth_peak = np.maximum(0.0, 1.0 - np.square((profile_y - target_y) / 2.5))
        edge_prob[:, 4:26] = smooth_peak[:, None].astype(np.float32)

        pixel_result = refine_edge_polyline(
            coarse_polyline,
            edge_prob=edge_prob,
            input_frame=input_frame,
            polygon_mask=polygon_mask,
            score_mode="edge_prob",
            search_radius_px=4,
            max_points=32,
            subpixel_mode="none",
        )
        subpixel_result = refine_edge_polyline(
            coarse_polyline,
            edge_prob=edge_prob,
            input_frame=input_frame,
            polygon_mask=polygon_mask,
            score_mode="edge_prob",
            search_radius_px=4,
            max_points=32,
            subpixel_mode="parabolic",
        )

        pixel_error = abs(float(np.mean(pixel_result.polyline_xy[:, 1])) - target_y)
        subpixel_error = abs(float(np.mean(subpixel_result.polyline_xy[:, 1])) - target_y)
        self.assertEqual(pixel_result.subpixel_mode, "none")
        self.assertEqual(subpixel_result.subpixel_mode, "parabolic")
        self.assertGreater(subpixel_result.mean_subpixel_correction_px, 0.0)
        self.assertLess(subpixel_error, pixel_error)
        self.assertLess(subpixel_error, 0.16)

    def test_step_tanh_profile_fit_estimates_physical_step_position(self) -> None:
        polygon_mask = np.ones((28, 32), dtype=bool)
        coarse_polyline = np.asarray([[4.0, 8.0], [27.0, 8.0]], dtype=np.float64)
        true_y = 10.35
        step_sigma = 0.65
        y_coords = np.arange(28, dtype=np.float64)[:, None]
        x_coords = np.arange(32, dtype=np.float64)[None, :]
        input_frame = (
            0.15
            + 0.01 * x_coords
            + 2.0 * 0.5 * (1.0 + np.tanh((y_coords - true_y) / step_sigma))
        ).astype(np.float32)
        edge_profile = 1.0 / np.cosh((np.arange(28, dtype=np.float64) - true_y) / step_sigma) ** 2
        edge_prob = np.zeros((28, 32), dtype=np.float32)
        edge_prob[:, 4:28] = edge_profile[:, None].astype(np.float32)

        result = refine_edge_polyline(
            coarse_polyline,
            edge_prob=edge_prob,
            input_frame=input_frame,
            polygon_mask=polygon_mask,
            score_mode="edge_prob",
            search_radius_px=5,
            max_points=32,
            subpixel_mode="step_tanh",
        )

        self.assertEqual(result.subpixel_mode, "step_tanh")
        self.assertGreater(result.profile_fit_success_rate, 0.80)
        self.assertGreater(result.mean_step_height, 1.0)
        self.assertGreater(result.mean_step_width_px, 0.0)
        self.assertLess(abs(float(np.mean(result.polyline_xy[:, 1])) - true_y), 0.12)

    def test_step_erf_profile_fit_runs_on_erf_step_profile(self) -> None:
        polygon_mask = np.ones((28, 32), dtype=bool)
        coarse_polyline = np.asarray([[4.0, 8.0], [27.0, 8.0]], dtype=np.float64)
        true_y = 10.4
        step_sigma = 0.75
        y_values = np.arange(28, dtype=np.float64)
        erf_profile = np.asarray(
            [0.5 * (1.0 + math.erf((float(y) - true_y) / step_sigma)) for y in y_values],
            dtype=np.float64,
        )
        input_frame = np.repeat(erf_profile[:, None], 32, axis=1).astype(np.float32)
        edge_prob = np.zeros((28, 32), dtype=np.float32)
        edge_prob[:, 4:28] = np.gradient(erf_profile).clip(min=0.0)[:, None].astype(np.float32)

        result = refine_edge_polyline(
            coarse_polyline,
            edge_prob=edge_prob,
            input_frame=input_frame,
            polygon_mask=polygon_mask,
            score_mode="edge_prob",
            search_radius_px=5,
            max_points=32,
            subpixel_mode="step_erf",
        )

        self.assertEqual(result.subpixel_mode, "step_erf")
        self.assertGreater(result.profile_fit_success_rate, 0.80)
        self.assertLess(abs(float(np.mean(result.polyline_xy[:, 1])) - true_y), 0.15)

    def test_validates_unknown_subpixel_mode(self) -> None:
        with self.assertRaises(ValueError):
            refine_edge_polyline(
                np.asarray([[0.0, 0.0], [5.0, 0.0]], dtype=np.float64),
                edge_prob=np.zeros((8, 8), dtype=np.float32),
                input_frame=np.zeros((8, 8), dtype=np.float32),
                polygon_mask=np.ones((8, 8), dtype=bool),
                subpixel_mode="unknown",
            )

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
