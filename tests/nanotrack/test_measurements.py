import unittest

import numpy as np

from nanotrack.analysis import compute_particle_metrics


class ComputeParticleMetricsTests(unittest.TestCase):
    def test_counts_only_finite_raw_samples_without_quantizing_them(self) -> None:
        raw = np.array([[100000000.125, np.nan], [100000000.375, np.inf]])
        metrics = compute_particle_metrics(np.ones((2, 2), dtype=bool), raw)
        self.assertEqual(metrics.valid_sample_count, 2)
        self.assertEqual(metrics.intensity_sum, 200000000.5)
        self.assertEqual(metrics.intensity_mean, 100000000.25)
        self.assertEqual(metrics.intensity_max, 100000000.375)
        self.assertEqual(metrics.area_px, 4.)
        empty = compute_particle_metrics(np.array([[False, True], [False, True]]), raw)
        self.assertEqual(empty.valid_sample_count, 0)
        self.assertIsNone(empty.intensity_sum)
        self.assertIsNone(empty.intensity_mean)
        self.assertIsNone(empty.intensity_max)

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

        metrics = compute_particle_metrics(mask, raw_frame, pixel_size_nm=(2.0, 3.0))

        self.assertEqual(metrics.area_px, 4.0)
        self.assertEqual(metrics.perimeter_px, 8.0)
        self.assertEqual(metrics.area_nm2, 24.0)
        self.assertEqual(metrics.perimeter_nm, 20.0)
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
        self.assertIsNone(metrics.area_nm2)
        self.assertIsNone(metrics.perimeter_nm)
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
