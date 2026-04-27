import unittest

import numpy as np

from nanotrack.core import RegistrationSettings
from nanotrack.registration import (
    PhaseCorrelationBackendError,
    TileCorrelationRansacBackend,
    TileCorrelationRansacConfig,
    build_registration_view,
    run_adjacent_phase_registration,
)


class TileCorrelationRansacBackendTests(unittest.TestCase):
    def _textured_frame(self, shape: tuple[int, int] = (80, 80)) -> np.ndarray:
        y, x = np.mgrid[0 : shape[0], 0 : shape[1]]
        frame = (
            0.3 * np.sin(x / 3.0)
            + 0.2 * np.cos(y / 5.0)
            + 0.15 * np.sin((x + y) / 7.0)
        ).astype(np.float32)
        frame[10:25, 12:31] += 2.5
        frame[36:53, 40:63] -= 1.6
        frame[57:72, 14:28] += 1.3
        rng = np.random.default_rng(17)
        frame += rng.normal(0.0, 0.03, shape).astype(np.float32)
        return frame

    def _backend(self) -> TileCorrelationRansacBackend:
        return TileCorrelationRansacBackend(
            TileCorrelationRansacConfig(
                tile_size=20,
                stride=20,
                upsample_factor=1,
                residual_threshold_px=1.25,
                min_inlier_tiles=4,
            )
        )

    def test_estimates_global_shift_from_tile_consensus_with_local_outlier(self) -> None:
        reference = self._textured_frame()
        moving = np.roll(reference, shift=(2, -3), axis=(0, 1))
        moving[60:80, 60:80] = np.roll(moving[60:80, 60:80], shift=(7, 5), axis=(0, 1))

        result = self._backend().estimate(reference, moving, moving_frame_index=4)

        self.assertEqual(result.frame_index, 4)
        self.assertEqual(result.method, "tile_correlation_ransac")
        self.assertEqual(result.status, "ok")
        self.assertAlmostEqual(result.dx, 3.0, delta=0.25)
        self.assertAlmostEqual(result.dy, -2.0, delta=0.25)
        self.assertIsNotNone(result.num_total_tiles)
        self.assertIsNotNone(result.num_inlier_tiles)
        self.assertGreaterEqual(result.num_inlier_tiles or 0, 4)
        self.assertLess(result.num_inlier_tiles or 0, result.num_total_tiles or 0)
        self.assertIsNotNone(result.median_tile_residual)
        self.assertLessEqual(result.median_tile_residual, 1.25)
        self.assertGreater(result.quality_score, 0.5)

    def test_estimate_pair_uses_registration_view_stack_and_optional_mask(self) -> None:
        reference = self._textured_frame()
        moving = np.roll(reference, shift=(-1, 4), axis=(0, 1))
        registration_view = build_registration_view(
            np.stack([reference, moving]).astype(np.float32),
            view_name="normalized",
        )
        mask = np.zeros(reference.shape, dtype=bool)
        mask[:60, :60] = True

        result = self._backend().estimate_pair(
            registration_view,
            reference_index=0,
            moving_index=1,
            reference_mask=mask,
        )

        self.assertEqual(result.frame_index, 1)
        self.assertAlmostEqual(result.dx, -4.0, delta=0.25)
        self.assertAlmostEqual(result.dy, 1.0, delta=0.25)
        self.assertGreaterEqual(result.num_inlier_tiles or 0, 4)

    def test_adjacent_batch_uses_tile_backend_from_settings(self) -> None:
        frame0 = self._textured_frame()
        frame1 = np.roll(frame0, shift=(2, -3), axis=(0, 1))
        frame2 = np.roll(frame1, shift=(-1, 5), axis=(0, 1))

        result_set = run_adjacent_phase_registration(
            np.stack([frame0, frame1, frame2]).astype(np.float32),
            settings=RegistrationSettings(
                backend="tile_correlation_ransac",
                registration_view="normalized",
                backend_params={
                    "tile_size": 20,
                    "stride": 20,
                    "upsample_factor": 1,
                    "residual_threshold_px": 1.25,
                    "min_inlier_tiles": 4,
                },
            ),
        )

        self.assertEqual(result_set.settings.backend, "tile_correlation_ransac")
        np.testing.assert_allclose(
            result_set.shifts_xy_array(),
            np.asarray([[0.0, 0.0], [3.0, -2.0], [-2.0, -1.0]], dtype=np.float64),
            atol=0.25,
        )
        self.assertEqual(result_set.get_result(2).method, "tile_correlation_ransac_adjacent")
        self.assertIsNotNone(result_set.get_result(2).num_inlier_tiles)
        self.assertIsNotNone(result_set.get_result(2).num_total_tiles)
        self.assertIsNotNone(result_set.get_result(2).median_tile_residual)

    def test_rejects_invalid_config_inputs_and_unusable_tiles(self) -> None:
        with self.assertRaises(ValueError):
            TileCorrelationRansacConfig(tile_size=1)
        with self.assertRaises(ValueError):
            TileCorrelationRansacConfig(stride=0)
        with self.assertRaises(ValueError):
            TileCorrelationRansacConfig(upsample_factor=0)
        with self.assertRaises(ValueError):
            TileCorrelationRansacConfig(normalization="bad")
        with self.assertRaises(ValueError):
            TileCorrelationRansacConfig(min_texture_std=-1.0)
        with self.assertRaises(ValueError):
            TileCorrelationRansacConfig(min_tile_valid_fraction=0.0)
        with self.assertRaises(ValueError):
            TileCorrelationRansacConfig(residual_threshold_px=0.0)
        with self.assertRaises(ValueError):
            TileCorrelationRansacConfig(min_inlier_tiles=0)
        with self.assertRaises(ValueError):
            TileCorrelationRansacConfig(low_confidence_inlier_ratio=0.0)

        frame = self._textured_frame()
        backend = self._backend()
        with self.assertRaises(ValueError):
            backend.estimate(frame[0], frame, moving_frame_index=0)
        with self.assertRaises(ValueError):
            backend.estimate(frame, frame[:40, :40], moving_frame_index=0)
        with self.assertRaises(ValueError):
            backend.estimate(frame, np.full_like(frame, np.nan), moving_frame_index=0)
        with self.assertRaises(ValueError):
            backend.estimate(frame, frame, moving_frame_index=-1)
        with self.assertRaises(ValueError):
            backend.estimate(frame[:10, :10], frame[:10, :10], moving_frame_index=0)
        with self.assertRaises(ValueError):
            backend.estimate(frame, frame, moving_frame_index=0, reference_mask=np.ones((4, 4), dtype=bool))
        with self.assertRaises(ValueError):
            backend.estimate(frame, frame, moving_frame_index=0, reference_mask=np.zeros_like(frame, dtype=bool))
        with self.assertRaises(PhaseCorrelationBackendError):
            backend.estimate(np.ones_like(frame), frame, moving_frame_index=0)


if __name__ == "__main__":
    unittest.main()
