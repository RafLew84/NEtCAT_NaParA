import unittest

import numpy as np
from scipy.ndimage import fourier_shift

try:
    import cv2  # noqa: F401

    CV2_AVAILABLE = True
except ModuleNotFoundError:
    CV2_AVAILABLE = False

from nanotrack.core import RegistrationSettings
from nanotrack.registration import (
    ECCTranslationBackend,
    ECCTranslationBackendError,
    ECCTranslationConfig,
    build_registration_view,
    run_adjacent_phase_registration,
)


@unittest.skipUnless(CV2_AVAILABLE, "OpenCV cv2 is required for ECC backend tests.")
class ECCTranslationBackendTests(unittest.TestCase):
    def _textured_frame(self, shape: tuple[int, int] = (80, 80)) -> np.ndarray:
        rng = np.random.default_rng(23)
        y, x = np.mgrid[0 : shape[0], 0 : shape[1]]
        frame = (
            0.25 * np.sin(x / 4.0)
            + 0.2 * np.cos(y / 6.0)
            + 0.15 * np.sin((x - y) / 9.0)
        ).astype(np.float32)
        frame[13:28, 18:35] += 2.3
        frame[39:57, 42:66] -= 1.5
        frame[58:73, 12:30] += 1.1
        frame += rng.normal(0.0, 0.02, shape).astype(np.float32)
        return frame

    def _subpixel_shift(self, frame: np.ndarray, shift_yx: tuple[float, float]) -> np.ndarray:
        shifted = np.fft.ifftn(fourier_shift(np.fft.fftn(frame), shift=shift_yx)).real
        return np.asarray(shifted, dtype=np.float32)

    def _backend(self) -> ECCTranslationBackend:
        return ECCTranslationBackend(
            ECCTranslationConfig(
                max_iterations=100,
                epsilon=1e-6,
                gaussian_filter_size=5,
                low_confidence_ecc_score=0.6,
                coarse_upsample_factor=20,
            )
        )

    def test_refines_subpixel_shift_from_phase_initialization(self) -> None:
        reference = self._textured_frame()
        moving = self._subpixel_shift(reference, shift_yx=(2.4, -3.25))

        result = self._backend().estimate(reference, moving, moving_frame_index=2)

        self.assertEqual(result.frame_index, 2)
        self.assertEqual(result.method, "ecc_translation")
        self.assertEqual(result.status, "ok")
        self.assertAlmostEqual(result.dx, 3.25, delta=0.08)
        self.assertAlmostEqual(result.dy, -2.4, delta=0.08)
        self.assertIsNotNone(result.ecc_score)
        self.assertGreater(result.ecc_score or 0.0, 0.9)
        self.assertIsNotNone(result.phase_peak_ratio)

    def test_accepts_explicit_initial_shift_and_mask(self) -> None:
        reference = self._textured_frame()
        moving = self._subpixel_shift(reference, shift_yx=(-1.5, 2.0))
        registration_view = build_registration_view(
            np.stack([reference, moving]).astype(np.float32),
            view_name="normalized",
        )
        mask = np.zeros(reference.shape, dtype=bool)
        mask[8:70, 8:70] = True

        result = self._backend().estimate_pair(
            registration_view,
            reference_index=0,
            moving_index=1,
            initial_shift_xy=(-2.0, 1.5),
            reference_mask=mask,
        )

        self.assertEqual(result.frame_index, 1)
        self.assertAlmostEqual(result.dx, -2.0, delta=0.08)
        self.assertAlmostEqual(result.dy, 1.5, delta=0.12)
        self.assertIsNone(result.phase_peak_ratio)
        self.assertGreater(result.ecc_score or 0.0, 0.85)

    def test_adjacent_batch_uses_ecc_backend_from_settings(self) -> None:
        frame0 = self._textured_frame()
        frame1 = self._subpixel_shift(frame0, shift_yx=(1.5, -2.25))
        frame2 = self._subpixel_shift(frame1, shift_yx=(-0.75, 1.25))

        result_set = run_adjacent_phase_registration(
            np.stack([frame0, frame1, frame2]).astype(np.float32),
            settings=RegistrationSettings(
                backend="ecc_translation",
                registration_view="normalized",
                backend_params={
                    "coarse_upsample_factor": 20,
                    "low_confidence_ecc_score": 0.6,
                },
            ),
        )

        self.assertEqual(result_set.settings.backend, "ecc_translation")
        np.testing.assert_allclose(
            result_set.shifts_xy_array(),
            np.asarray([[0.0, 0.0], [2.25, -1.5], [1.0, -0.75]], dtype=np.float64),
            atol=0.1,
        )
        self.assertEqual(result_set.get_result(2).method, "ecc_translation_adjacent")
        self.assertIsNotNone(result_set.get_result(2).ecc_score)

    def test_rejects_invalid_config_inputs_and_unusable_frames(self) -> None:
        with self.assertRaises(ValueError):
            ECCTranslationConfig(max_iterations=0)
        with self.assertRaises(ValueError):
            ECCTranslationConfig(epsilon=0.0)
        with self.assertRaises(ValueError):
            ECCTranslationConfig(gaussian_filter_size=4)
        with self.assertRaises(ValueError):
            ECCTranslationConfig(min_texture_std=-1.0)
        with self.assertRaises(ValueError):
            ECCTranslationConfig(min_mask_pixels=0)
        with self.assertRaises(ValueError):
            ECCTranslationConfig(low_confidence_ecc_score=-0.1)
        with self.assertRaises(ValueError):
            ECCTranslationConfig(coarse_upsample_factor=0)
        with self.assertRaises(ValueError):
            ECCTranslationConfig(coarse_normalization="bad")
        with self.assertRaises(ValueError):
            ECCTranslationConfig(coarse_peak_exclusion_radius=-1)
        with self.assertRaises(ValueError):
            ECCTranslationConfig(coarse_low_confidence_peak_ratio=0.0)

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
            backend.estimate(frame, frame, moving_frame_index=0, initial_shift_xy=(1.0,))
        with self.assertRaises(ValueError):
            backend.estimate(frame, frame, moving_frame_index=0, reference_mask=np.ones((4, 4), dtype=bool))
        with self.assertRaises(ValueError):
            backend.estimate(frame, frame, moving_frame_index=0, reference_mask=np.zeros_like(frame, dtype=bool))
        with self.assertRaises(ECCTranslationBackendError):
            backend.estimate(np.ones_like(frame), frame, moving_frame_index=0)


if __name__ == "__main__":
    unittest.main()
