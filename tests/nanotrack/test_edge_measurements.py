import unittest

import numpy as np

from nanotrack.analysis import compute_edge_metrics


class ComputeEdgeMetricsTests(unittest.TestCase):
    def test_computes_length_and_zero_roughness_for_straight_polyline(self) -> None:
        polyline = np.asarray(
            [
                [0.0, 0.0],
                [3.0, 4.0],
                [6.0, 8.0],
            ],
            dtype=np.float64,
        )

        metrics = compute_edge_metrics(polyline, pixel_size_nm=(2.0, 3.0))

        self.assertAlmostEqual(metrics.length_px, 10.0)
        self.assertAlmostEqual(metrics.length_nm, 2.0 * np.hypot(3.0 * 2.0, 4.0 * 3.0))
        self.assertAlmostEqual(metrics.roughness_rms_px, 0.0)
        self.assertAlmostEqual(metrics.roughness_rms_nm, 0.0)
        self.assertAlmostEqual(metrics.mean_curvature, 0.0)
        self.assertAlmostEqual(metrics.max_curvature, 0.0)
        self.assertAlmostEqual(metrics.waviness_amplitude_px, 0.0)
        self.assertAlmostEqual(metrics.waviness_amplitude_nm, 0.0)

    def test_computes_positive_roughness_curvature_and_waviness_for_non_linear_polyline(self) -> None:
        polyline = np.asarray(
            [
                [0.0, 0.0],
                [1.0, 1.0],
                [2.0, -1.0],
                [3.0, 1.0],
                [4.0, 0.0],
            ],
            dtype=np.float64,
        )

        metrics = compute_edge_metrics(polyline)

        self.assertGreater(metrics.length_px, 4.0)
        self.assertGreater(metrics.roughness_rms_px, 0.0)
        self.assertGreater(metrics.mean_curvature, 0.0)
        self.assertGreater(metrics.max_curvature, 0.0)
        self.assertGreater(metrics.waviness_amplitude_px, 0.0)
        self.assertIsNone(metrics.length_nm)
        self.assertIsNone(metrics.roughness_rms_nm)
        self.assertIsNone(metrics.waviness_amplitude_nm)

    def test_rejects_invalid_polyline_shape(self) -> None:
        with self.assertRaises(ValueError):
            compute_edge_metrics(np.asarray([1.0, 2.0, 3.0], dtype=np.float64))


if __name__ == "__main__":
    unittest.main()
