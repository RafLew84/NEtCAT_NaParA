import unittest

import numpy as np

from nanotrack.analysis import compute_particle_metrics


class ComputeParticleMetricsTests(unittest.TestCase):
    def test_computes_area_perimeter_and_raw_intensity(self) -> None:
        raw_frame = np.asarray(
            [
                [1.0, 2.0, 3.0, 4.0],
                [5.0, 6.0, 7.0, 8.0],
                [9.0, 10.0, 11.0, 12.0],
            ],
            dtype=np.float32,
        )
        mask = np.asarray(
            [
                [False, True, True, False],
                [False, True, True, False],
                [False, False, False, False],
            ],
            dtype=bool,
        )

        metrics = compute_particle_metrics(mask, raw_frame)

        self.assertEqual(metrics.area_px, 4.0)
        self.assertEqual(metrics.perimeter_px, 8.0)
        self.assertEqual(metrics.intensity_sum, 18.0)
        self.assertEqual(metrics.intensity_mean, 4.5)
        self.assertEqual(metrics.intensity_max, 7.0)

    def test_returns_empty_metrics_for_empty_mask(self) -> None:
        metrics = compute_particle_metrics(
            np.zeros((2, 3), dtype=bool),
            np.ones((2, 3), dtype=np.float32),
        )

        self.assertIsNone(metrics.area_px)
        self.assertIsNone(metrics.perimeter_px)
        self.assertIsNone(metrics.intensity_sum)
        self.assertIsNone(metrics.intensity_mean)
        self.assertIsNone(metrics.intensity_max)

    def test_rejects_shape_mismatch(self) -> None:
        with self.assertRaises(ValueError):
            compute_particle_metrics(
                np.ones((2, 2), dtype=bool),
                np.ones((2, 3), dtype=np.float32),
            )


if __name__ == "__main__":
    unittest.main()
