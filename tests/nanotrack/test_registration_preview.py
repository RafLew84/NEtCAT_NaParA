import unittest

import numpy as np

from nanotrack.core import RegistrationSettings
from nanotrack.registration import (
    apply_translation_to_frame,
    build_registration_pair_preview,
)


class RegistrationPairPreviewTests(unittest.TestCase):
    def _textured_frame(self) -> np.ndarray:
        rng = np.random.default_rng(7)
        frame = rng.normal(0.0, 0.1, (64, 64)).astype(np.float32)
        frame[10:26, 14:27] += 2.0
        frame[35:52, 41:50] -= 1.5
        return frame

    def test_builds_pair_preview_and_improves_alignment(self) -> None:
        reference = self._textured_frame()
        moving = np.roll(reference, shift=(3, -4), axis=(0, 1))
        frames = np.stack([reference, moving]).astype(np.float32)

        preview = build_registration_pair_preview(
            frames,
            reference_index=0,
            moving_index=1,
            settings=RegistrationSettings(registration_view="normalized"),
            interpolation_order=0,
        )

        self.assertEqual(preview.reference_index, 0)
        self.assertEqual(preview.moving_index, 1)
        self.assertEqual(preview.registration_view.view_name, "normalized")
        self.assertAlmostEqual(preview.result.dx, 4.0, places=3)
        self.assertAlmostEqual(preview.result.dy, -3.0, places=3)
        before_mse = float(np.mean((preview.reference_frame - preview.moving_frame) ** 2))
        after_mse = float(np.mean((preview.reference_frame - preview.aligned_moving_frame) ** 2))
        self.assertLess(after_mse, before_mse)

    def test_apply_translation_validates_inputs(self) -> None:
        frame = np.zeros((8, 8), dtype=np.float32)
        shifted = apply_translation_to_frame(frame, (1.0, -1.0))
        self.assertEqual(shifted.shape, frame.shape)

        with self.assertRaises(ValueError):
            apply_translation_to_frame(frame[0], (1.0, 0.0))
        with self.assertRaises(ValueError):
            apply_translation_to_frame(np.full((2, 2), np.nan, dtype=np.float32), (1.0, 0.0))
        with self.assertRaises(ValueError):
            apply_translation_to_frame(frame, (np.nan, 0.0))
        with self.assertRaises(ValueError):
            apply_translation_to_frame(frame, (1.0, 0.0), interpolation_order=6)

    def test_rejects_invalid_pair(self) -> None:
        frames = np.zeros((2, 8, 8), dtype=np.float32)

        with self.assertRaises(ValueError):
            build_registration_pair_preview(frames[:1], reference_index=0, moving_index=0)
        with self.assertRaises(ValueError):
            build_registration_pair_preview(frames, reference_index=0, moving_index=0)
        with self.assertRaises(IndexError):
            build_registration_pair_preview(frames, reference_index=0, moving_index=2)


if __name__ == "__main__":
    unittest.main()
