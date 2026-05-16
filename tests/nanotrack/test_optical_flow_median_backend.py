import unittest

import numpy as np
from scipy.ndimage import shift as ndimage_shift

from nanotrack.core import RegistrationSettings
from nanotrack.registration import (
    OpticalFlowMedianBackend,
    OpticalFlowMedianConfig,
    PhaseCorrelationBackendError,
    build_registration_view,
    run_adjacent_phase_registration,
)


class OpticalFlowMedianBackendTests(unittest.TestCase):
    def _textured_frame(self, shape: tuple[int, int] = (80, 80)) -> np.ndarray:
        rng = np.random.default_rng(29)
        y, x = np.mgrid[0 : shape[0], 0 : shape[1]]
        frame = (
            0.25 * np.sin(x / 4.0)
            + 0.2 * np.cos(y / 6.0)
            + 0.1 * np.sin((x + y) / 8.0)
        ).astype(np.float32)
        frame[12:27, 17:36] += 2.1
        frame[39:58, 44:66] -= 1.4
        frame[57:73, 11:29] += 1.2
        frame += rng.normal(0.0, 0.02, shape).astype(np.float32)
        return frame

    def _shift(self, frame: np.ndarray, shift_yx: tuple[float, float]) -> np.ndarray:
        return np.asarray(ndimage_shift(frame, shift=shift_yx, order=1, mode="nearest"), dtype=np.float32)

    def test_tvl1_reduces_dense_flow_to_global_shift_without_warp(self) -> None:
        reference = self._textured_frame()
        moving = self._shift(reference, shift_yx=(2.5, -3.25))
        moving[58:78, 58:78] = self._shift(moving[58:78, 58:78], shift_yx=(4.0, 3.0))
        backend = OpticalFlowMedianBackend(
            OpticalFlowMedianConfig(method="tvl1", tvl1_num_iter=20, low_confidence_flow_mad_px=1.5)
        )

        result = backend.estimate(reference, moving, moving_frame_index=3)

        self.assertEqual(result.frame_index, 3)
        self.assertEqual(result.method, "optical_flow_median")
        self.assertAlmostEqual(result.dx, 3.25, delta=0.2)
        self.assertAlmostEqual(result.dy, -2.5, delta=0.2)
        self.assertIsNotNone(result.flow_mad)
        self.assertGreater(result.quality_score, 0.4)

    def test_ilk_estimate_pair_uses_registration_view_and_mask(self) -> None:
        reference = self._textured_frame()
        moving = self._shift(reference, shift_yx=(-1.5, 2.0))
        registration_view = build_registration_view(
            np.stack([reference, moving]).astype(np.float32),
            view_name="normalized",
        )
        mask = np.zeros(reference.shape, dtype=bool)
        mask[8:70, 8:70] = True
        backend = OpticalFlowMedianBackend(OpticalFlowMedianConfig(method="ilk", low_confidence_flow_mad_px=1.0))

        result = backend.estimate_pair(
            registration_view,
            reference_index=0,
            moving_index=1,
            reference_mask=mask,
        )

        self.assertEqual(result.frame_index, 1)
        self.assertAlmostEqual(result.dx, -2.0, delta=0.2)
        self.assertAlmostEqual(result.dy, 1.5, delta=0.2)
        self.assertIsNotNone(result.flow_mad)

    def test_adjacent_batch_uses_optical_flow_backend_from_settings(self) -> None:
        frame0 = self._textured_frame()
        frame1 = self._shift(frame0, shift_yx=(1.5, -2.25))
        frame2 = self._shift(frame1, shift_yx=(-0.75, 1.25))

        result_set = run_adjacent_phase_registration(
            np.stack([frame0, frame1, frame2]).astype(np.float32),
            settings=RegistrationSettings(
                backend="optical_flow_median",
                registration_view="normalized",
                backend_params={
                    "method": "ilk",
                    "low_confidence_flow_mad_px": 1.0,
                },
            ),
        )

        self.assertEqual(result_set.settings.backend, "optical_flow_median")
        np.testing.assert_allclose(
            result_set.shifts_xy_array(),
            np.asarray([[0.0, 0.0], [2.25, -1.5], [1.0, -0.75]], dtype=np.float64),
            atol=0.25,
        )
        self.assertEqual(result_set.get_result(2).method, "optical_flow_median_adjacent")
        self.assertIsNotNone(result_set.get_result(2).flow_mad)

    def test_rejects_invalid_config_inputs_and_unusable_frames(self) -> None:
        with self.assertRaises(ValueError):
            OpticalFlowMedianConfig(method="bad")
        with self.assertRaises(ValueError):
            OpticalFlowMedianConfig(min_texture_std=-1.0)
        with self.assertRaises(ValueError):
            OpticalFlowMedianConfig(min_valid_fraction=0.0)
        with self.assertRaises(ValueError):
            OpticalFlowMedianConfig(low_confidence_flow_mad_px=-1.0)
        with self.assertRaises(ValueError):
            OpticalFlowMedianConfig(tvl1_attachment=0.0)
        with self.assertRaises(ValueError):
            OpticalFlowMedianConfig(tvl1_tightness=0.0)
        with self.assertRaises(ValueError):
            OpticalFlowMedianConfig(tvl1_num_warp=0)
        with self.assertRaises(ValueError):
            OpticalFlowMedianConfig(tvl1_num_iter=0)
        with self.assertRaises(ValueError):
            OpticalFlowMedianConfig(tvl1_tol=0.0)
        with self.assertRaises(ValueError):
            OpticalFlowMedianConfig(ilk_radius=0)
        with self.assertRaises(ValueError):
            OpticalFlowMedianConfig(ilk_num_warp=0)

        frame = self._textured_frame()
        backend = OpticalFlowMedianBackend()
        with self.assertRaises(ValueError):
            backend.estimate(frame[0], frame, moving_frame_index=0)
        with self.assertRaises(ValueError):
            backend.estimate(frame, frame[:40, :40], moving_frame_index=0)
        with self.assertRaises(ValueError):
            backend.estimate(frame, np.full_like(frame, np.nan), moving_frame_index=0)
        with self.assertRaises(ValueError):
            backend.estimate(frame, frame, moving_frame_index=-1)
        with self.assertRaises(ValueError):
            backend.estimate(frame, frame, moving_frame_index=0, reference_mask=np.ones((4, 4), dtype=bool))
        with self.assertRaises(ValueError):
            backend.estimate(frame, frame, moving_frame_index=0, reference_mask=np.zeros_like(frame, dtype=bool))
        with self.assertRaises(ValueError):
            backend.estimate(
                frame,
                frame,
                moving_frame_index=0,
                reference_mask=np.zeros_like(frame, dtype=bool),
                moving_mask=np.ones_like(frame, dtype=bool),
            )
        with self.assertRaises(PhaseCorrelationBackendError):
            backend.estimate(np.ones_like(frame), frame, moving_frame_index=0)


if __name__ == "__main__":
    unittest.main()
