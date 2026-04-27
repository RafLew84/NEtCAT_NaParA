import unittest

import numpy as np
from scipy.ndimage import fourier_shift

from nanotrack.core.data_models import RegistrationFrameResult
from nanotrack.registration import (
    PhaseCorrelationBackendError,
    PhaseCorrelationShiftBackend,
    PhaseCorrelationShiftConfig,
    build_registration_view,
)


class PhaseCorrelationShiftBackendTests(unittest.TestCase):
    def _textured_frame(self, shape: tuple[int, int] = (64, 64)) -> np.ndarray:
        rng = np.random.default_rng(42)
        frame = rng.normal(0.0, 0.15, shape).astype(np.float32)
        frame[12:26, 18:31] += 2.5
        frame[35:45, 8:21] -= 1.2
        frame[38:58, 43:52] += 1.8
        return frame

    def test_estimates_integer_shift_to_apply_to_moving_frame(self) -> None:
        reference = self._textured_frame()
        moving = np.roll(reference, shift=(5, -7), axis=(0, 1))
        backend = PhaseCorrelationShiftBackend(PhaseCorrelationShiftConfig(upsample_factor=10))

        result = backend.estimate(reference, moving, moving_frame_index=3)

        self.assertIsInstance(result, RegistrationFrameResult)
        self.assertEqual(result.frame_index, 3)
        self.assertEqual(result.method, "phase_correlation")
        self.assertEqual(result.status, "ok")
        self.assertAlmostEqual(result.dx, 7.0, places=3)
        self.assertAlmostEqual(result.dy, -5.0, places=3)
        self.assertGreater(result.phase_peak_ratio or 0.0, 3.0)
        self.assertGreater(result.quality_score, 0.5)

    def test_estimates_subpixel_shift(self) -> None:
        reference = self._textured_frame()
        moving = np.fft.ifftn(
            fourier_shift(np.fft.fftn(reference), shift=(2.4, -3.25))
        ).real.astype(np.float32)
        backend = PhaseCorrelationShiftBackend(PhaseCorrelationShiftConfig(upsample_factor=40))

        result = backend.estimate(reference, moving, moving_frame_index=1)

        self.assertAlmostEqual(result.dx, 3.25, delta=0.05)
        self.assertAlmostEqual(result.dy, -2.4, delta=0.05)

    def test_estimate_pair_uses_registration_view_stack(self) -> None:
        reference = self._textured_frame()
        moving = np.roll(reference, shift=(-2, 4), axis=(0, 1))
        registration_view = build_registration_view(
            np.stack([reference, moving]).astype(np.float32),
            view_name="normalized",
        )
        backend = PhaseCorrelationShiftBackend()

        result = backend.estimate_pair(registration_view, reference_index=0, moving_index=1)

        self.assertEqual(result.frame_index, 1)
        self.assertAlmostEqual(result.dx, -4.0, places=3)
        self.assertAlmostEqual(result.dy, 2.0, places=3)

    def test_can_accept_plain_registration_view_array(self) -> None:
        reference = self._textured_frame()
        moving = np.roll(reference, shift=(1, 2), axis=(0, 1))
        stack = np.stack([moving, reference]).astype(np.float32)

        result = PhaseCorrelationShiftBackend().estimate_pair(
            stack,
            reference_index=1,
            moving_index=0,
        )

        self.assertEqual(result.frame_index, 0)
        self.assertAlmostEqual(result.dx, -2.0, places=3)
        self.assertAlmostEqual(result.dy, -1.0, places=3)

    def test_low_peak_ratio_marks_low_confidence(self) -> None:
        y, x = np.mgrid[0:48, 0:48]
        reference = (((x // 4) + (y // 4)) % 2).astype(np.float32)
        moving = np.roll(reference, shift=(4, 4), axis=(0, 1))
        backend = PhaseCorrelationShiftBackend(
            PhaseCorrelationShiftConfig(low_confidence_peak_ratio=1_000.0)
        )

        result = backend.estimate(reference, moving, moving_frame_index=2)

        self.assertEqual(result.status, "low_confidence")
        self.assertLess(result.quality_score, 0.5)

    def test_rejects_invalid_config_and_inputs(self) -> None:
        with self.assertRaises(ValueError):
            PhaseCorrelationShiftConfig(upsample_factor=0)
        with self.assertRaises(ValueError):
            PhaseCorrelationShiftConfig(normalization="bad")
        with self.assertRaises(ValueError):
            PhaseCorrelationShiftConfig(min_texture_std=-1.0)
        with self.assertRaises(ValueError):
            PhaseCorrelationShiftConfig(peak_exclusion_radius=-1)
        with self.assertRaises(ValueError):
            PhaseCorrelationShiftConfig(low_confidence_peak_ratio=0.0)

        backend = PhaseCorrelationShiftBackend()
        frame = self._textured_frame()
        with self.assertRaises(ValueError):
            backend.estimate(frame[0], frame, moving_frame_index=0)
        with self.assertRaises(ValueError):
            backend.estimate(frame, frame[:32, :32], moving_frame_index=0)
        with self.assertRaises(ValueError):
            backend.estimate(frame, np.full_like(frame, np.nan), moving_frame_index=0)
        with self.assertRaises(ValueError):
            backend.estimate(frame, frame, moving_frame_index=-1)
        with self.assertRaises(PhaseCorrelationBackendError):
            backend.estimate(np.ones((8, 8), dtype=np.float32), frame[:8, :8], moving_frame_index=0)
        with self.assertRaises(ValueError):
            backend.estimate_pair(frame, reference_index=0, moving_index=1)
        with self.assertRaises(IndexError):
            backend.estimate_pair(np.stack([frame]), reference_index=0, moving_index=1)


if __name__ == "__main__":
    unittest.main()
