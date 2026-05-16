import unittest

import numpy as np

from nanotrack.core.data_models import RegistrationSettings
from nanotrack.registration.view import (
    SUPPORTED_REGISTRATION_VIEWS,
    RegistrationViewResult,
    build_registration_view,
    build_registration_view_from_settings,
)


class RegistrationViewTests(unittest.TestCase):
    def test_raw_view_returns_independent_float32_stack(self) -> None:
        frames = np.arange(2 * 4 * 5, dtype=np.float64).reshape(2, 4, 5)

        result = build_registration_view(frames, view_name="raw")

        self.assertIsInstance(result, RegistrationViewResult)
        self.assertEqual(result.view_name, "raw")
        self.assertEqual(result.frames.dtype, np.float32)
        self.assertFalse(np.shares_memory(frames, result.frames))
        np.testing.assert_array_equal(result.frames, frames.astype(np.float32))

        result.frames[0, 0, 0] = -99.0
        self.assertNotEqual(frames[0, 0, 0], -99.0)

    def test_normalized_view_is_per_frame_and_constant_safe(self) -> None:
        frames = np.stack(
            [
                np.full((5, 5), 7.0, dtype=np.float32),
                np.arange(25, dtype=np.float32).reshape(5, 5),
            ]
        )

        result = build_registration_view(frames, view_name="normalized")

        np.testing.assert_array_equal(result.frames[0], np.zeros((5, 5), dtype=np.float32))
        self.assertAlmostEqual(float(result.frames[1].min()), 0.0)
        self.assertAlmostEqual(float(result.frames[1].max()), 1.0)

    def test_gradient_magnitude_highlights_intensity_step(self) -> None:
        frames = np.zeros((1, 12, 12), dtype=np.float32)
        frames[:, :, 6:] = 10.0

        result = build_registration_view(frames, view_name="gradient_magnitude")

        edge_band = float(result.frames[0, :, 5:7].mean())
        flat_band = float(result.frames[0, :, :3].mean())
        self.assertGreater(edge_band, flat_band)

    def test_high_pass_and_dog_views_are_finite_float32_stacks(self) -> None:
        y, x = np.mgrid[0:16, 0:16]
        frame = (x + y).astype(np.float32)
        frame[6:10, 6:10] += 20.0
        frames = frame[None, :, :]

        high_pass = build_registration_view(frames, view_name="high_pass", high_pass_sigma=2.0)
        dog = build_registration_view(
            frames,
            view_name="dog",
            dog_sigma_low=1.0,
            dog_sigma_high=3.0,
        )

        for result in (high_pass, dog):
            self.assertEqual(result.frames.shape, frames.shape)
            self.assertEqual(result.frames.dtype, np.float32)
            self.assertTrue(np.all(np.isfinite(result.frames)))
            self.assertGreater(float(result.frames.max()), float(result.frames.min()))

        self.assertEqual(high_pass.metadata["high_pass_sigma"], 2.0)
        self.assertEqual(dog.metadata["dog_sigma_low"], 1.0)
        self.assertEqual(dog.metadata["dog_sigma_high"], 3.0)

    def test_roi_mask_fills_outside_mask_with_inside_median(self) -> None:
        frames = np.arange(16, dtype=np.float32).reshape(1, 4, 4)
        mask = np.zeros((4, 4), dtype=bool)
        mask[1:3, 1:3] = True

        result = build_registration_view(frames, view_name="raw", roi_mask=mask)

        self.assertTrue(result.roi_mask_applied)
        expected_fill = float(np.median(frames[0][mask]))
        self.assertEqual(float(result.frames[0, 0, 0]), expected_fill)
        np.testing.assert_array_equal(result.frames[0][mask], frames[0][mask])

    def test_hann_window_is_optional_and_keeps_shape(self) -> None:
        frames = np.ones((1, 5, 5), dtype=np.float32)

        result = build_registration_view(frames, view_name="raw", apply_hann_window=True)

        self.assertTrue(result.hann_window_applied)
        self.assertEqual(result.frames.shape, frames.shape)
        self.assertAlmostEqual(float(result.frames[0, 0, 0]), 0.0)
        self.assertGreater(float(result.frames[0, 2, 2]), 0.9)

    def test_builds_from_registration_settings_backend_params(self) -> None:
        frames = np.arange(25, dtype=np.float32).reshape(1, 5, 5)
        settings = RegistrationSettings(
            registration_view=" dog ",
            backend_params={
                "dog_sigma_low": 1.0,
                "dog_sigma_high": 2.0,
                "apply_hann_window": True,
            },
        )

        result = build_registration_view_from_settings(frames, settings)

        self.assertEqual(result.view_name, "dog")
        self.assertTrue(result.hann_window_applied)
        self.assertEqual(result.metadata["dog_sigma_low"], 1.0)
        self.assertEqual(result.metadata["dog_sigma_high"], 2.0)

    def test_rejects_invalid_inputs(self) -> None:
        frames = np.zeros((1, 4, 4), dtype=np.float32)

        with self.assertRaises(ValueError):
            build_registration_view(frames[0], view_name="raw")
        with self.assertRaises(ValueError):
            build_registration_view(frames, view_name="unknown")
        with self.assertRaises(ValueError):
            build_registration_view(frames, roi_mask=np.ones((3, 4), dtype=bool))
        with self.assertRaises(ValueError):
            build_registration_view(frames, roi_mask=np.zeros((4, 4), dtype=bool))
        with self.assertRaises(ValueError):
            build_registration_view(np.array([[[np.nan]]], dtype=np.float32))
        with self.assertRaises(ValueError):
            build_registration_view(frames, view_name="high_pass", high_pass_sigma=0.0)
        with self.assertRaises(ValueError):
            build_registration_view(frames, view_name="dog", dog_sigma_low=3.0, dog_sigma_high=1.0)
        with self.assertRaises(TypeError):
            build_registration_view_from_settings(frames, settings=object())  # type: ignore[arg-type]

    def test_supported_view_list_is_stable(self) -> None:
        self.assertEqual(
            SUPPORTED_REGISTRATION_VIEWS,
            ("raw", "normalized", "gradient_magnitude", "high_pass", "dog"),
        )


if __name__ == "__main__":
    unittest.main()
