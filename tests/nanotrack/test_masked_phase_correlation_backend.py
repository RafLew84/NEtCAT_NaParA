import unittest

import numpy as np

from nanotrack.core import RegistrationSettings
from nanotrack.registration import (
    MaskedPhaseCorrelationBackend,
    MaskedPhaseCorrelationConfig,
    PhaseCorrelationBackendError,
    build_registration_view,
    run_adjacent_phase_registration,
)


class MaskedPhaseCorrelationBackendTests(unittest.TestCase):
    def _textured_frame(self, shape: tuple[int, int] = (64, 64)) -> np.ndarray:
        rng = np.random.default_rng(31)
        frame = rng.normal(0.0, 0.12, shape).astype(np.float32)
        frame[11:25, 16:31] += 2.2
        frame[33:46, 9:23] -= 1.4
        frame[40:57, 42:53] += 1.7
        return frame

    def _stable_mask(self) -> np.ndarray:
        mask = np.zeros((64, 64), dtype=bool)
        mask[8:58, 8:58] = True
        return mask

    def test_estimates_integer_shift_with_valid_pixel_mask(self) -> None:
        reference = self._textured_frame()
        moving = np.roll(reference, shift=(5, -7), axis=(0, 1))
        reference[:8, :8] += 40.0
        moving[:8, :8] -= 40.0
        backend = MaskedPhaseCorrelationBackend()

        result = backend.estimate(
            reference,
            moving,
            moving_frame_index=3,
            reference_mask=self._stable_mask(),
        )

        self.assertEqual(result.frame_index, 3)
        self.assertEqual(result.method, "masked_phase_correlation")
        self.assertEqual(result.status, "ok")
        self.assertAlmostEqual(result.dx, 7.0, places=3)
        self.assertAlmostEqual(result.dy, -5.0, places=3)
        self.assertIsNone(result.phase_peak_ratio)
        self.assertGreater(result.quality_score, 0.5)

    def test_estimate_pair_uses_registration_view_stack_and_mask(self) -> None:
        reference = self._textured_frame()
        moving = np.roll(reference, shift=(-2, 4), axis=(0, 1))
        registration_view = build_registration_view(
            np.stack([reference, moving]).astype(np.float32),
            view_name="normalized",
        )

        result = MaskedPhaseCorrelationBackend().estimate_pair(
            registration_view,
            reference_index=0,
            moving_index=1,
            reference_mask=self._stable_mask(),
        )

        self.assertEqual(result.frame_index, 1)
        self.assertAlmostEqual(result.dx, -4.0, places=3)
        self.assertAlmostEqual(result.dy, 2.0, places=3)

    def test_adjacent_batch_uses_masked_backend_from_settings(self) -> None:
        frame0 = self._textured_frame()
        frame1 = np.roll(frame0, shift=(2, -3), axis=(0, 1))
        frame2 = np.roll(frame1, shift=(-1, 5), axis=(0, 1))

        result_set = run_adjacent_phase_registration(
            np.stack([frame0, frame1, frame2]).astype(np.float32),
            settings=RegistrationSettings(
                backend="masked_phase_correlation",
                registration_view="normalized",
                roi_mask=self._stable_mask(),
                backend_params={"overlap_ratio": 0.2},
            ),
        )

        self.assertEqual(result_set.settings.backend, "masked_phase_correlation")
        self.assertEqual(result_set.frame_indices, [0, 1, 2])
        np.testing.assert_allclose(
            result_set.shifts_xy_array(),
            np.asarray([[0.0, 0.0], [3.0, -2.0], [-2.0, -1.0]], dtype=np.float64),
            atol=1e-6,
        )
        self.assertEqual(result_set.get_result(2).method, "masked_phase_correlation_adjacent")

    def test_marks_low_confidence_when_mask_overlap_is_low(self) -> None:
        reference = self._textured_frame()
        moving = np.roll(reference, shift=(20, 20), axis=(0, 1))
        backend = MaskedPhaseCorrelationBackend(
            MaskedPhaseCorrelationConfig(
                overlap_ratio=0.1,
                low_confidence_overlap_ratio=0.9,
            )
        )

        result = backend.estimate(
            reference,
            moving,
            moving_frame_index=1,
            reference_mask=self._stable_mask(),
        )

        self.assertEqual(result.status, "low_confidence")
        self.assertLess(result.quality_score, 0.9)

    def test_rejects_invalid_config_inputs_and_missing_batch_mask(self) -> None:
        with self.assertRaises(ValueError):
            MaskedPhaseCorrelationConfig(overlap_ratio=0.0)
        with self.assertRaises(ValueError):
            MaskedPhaseCorrelationConfig(overlap_ratio=1.5)
        with self.assertRaises(ValueError):
            MaskedPhaseCorrelationConfig(min_mask_pixels=0)
        with self.assertRaises(ValueError):
            MaskedPhaseCorrelationConfig(min_texture_std=-1.0)
        with self.assertRaises(ValueError):
            MaskedPhaseCorrelationConfig(low_confidence_overlap_ratio=0.0)

        frame = self._textured_frame()
        backend = MaskedPhaseCorrelationBackend()
        with self.assertRaises(ValueError):
            backend.estimate(frame, frame, moving_frame_index=0, reference_mask=np.ones((8, 8), dtype=bool))
        with self.assertRaises(ValueError):
            backend.estimate(frame, frame, moving_frame_index=0, reference_mask=np.zeros_like(frame, dtype=bool))
        with self.assertRaises(ValueError):
            backend.estimate(frame, frame, moving_frame_index=-1, reference_mask=self._stable_mask())
        with self.assertRaises(PhaseCorrelationBackendError):
            backend.estimate(
                np.ones_like(frame),
                frame,
                moving_frame_index=0,
                reference_mask=self._stable_mask(),
            )
        with self.assertRaises(ValueError):
            run_adjacent_phase_registration(
                np.stack([frame, frame]).astype(np.float32),
                settings=RegistrationSettings(backend="masked_phase_correlation"),
            )


if __name__ == "__main__":
    unittest.main()
