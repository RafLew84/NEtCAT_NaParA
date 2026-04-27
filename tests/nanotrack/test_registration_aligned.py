import unittest

import numpy as np

from nanotrack.core import RegistrationFrameResult, RegistrationResultSet, RegistrationSettings
from nanotrack.registration import build_aligned_frames, run_adjacent_phase_registration


class RegistrationAlignedViewTests(unittest.TestCase):
    def _textured_frame(self) -> np.ndarray:
        rng = np.random.default_rng(19)
        frame = rng.normal(0.0, 0.05, (64, 64)).astype(np.float32)
        frame[12:25, 10:28] += 2.0
        frame[34:50, 38:52] -= 1.6
        frame[43:56, 8:18] += 1.1
        return frame

    def test_builds_aligned_stack_from_cumulative_shifts(self) -> None:
        frame0 = self._textured_frame()
        frame1 = np.roll(frame0, shift=(2, -3), axis=(0, 1))
        frame2 = np.roll(frame1, shift=(-1, 5), axis=(0, 1))
        frames = np.stack([frame0, frame1, frame2]).astype(np.float32)
        result_set = run_adjacent_phase_registration(
            frames,
            settings=RegistrationSettings(registration_view="normalized"),
        )

        aligned = build_aligned_frames(frames, result_set, interpolation_order=0)

        self.assertEqual(aligned.shape, frames.shape)
        self.assertEqual(aligned.dtype, np.float32)
        np.testing.assert_array_equal(aligned[0], frame0)
        self.assertLess(float(np.mean((aligned[1] - frame0) ** 2)), float(np.mean((frame1 - frame0) ** 2)))
        self.assertLess(float(np.mean((aligned[2] - frame0) ** 2)), float(np.mean((frame2 - frame0) ** 2)))

    def test_rejects_missing_or_extra_registration_results(self) -> None:
        frames = np.zeros((2, 8, 8), dtype=np.float32)
        settings = RegistrationSettings(registration_view="raw")
        missing = RegistrationResultSet(
            settings=settings,
            results_by_frame={
                0: RegistrationFrameResult(frame_index=0, shift_xy=(0.0, 0.0), method="identity"),
            },
        )
        extra = RegistrationResultSet(
            settings=settings,
            results_by_frame={
                0: RegistrationFrameResult(frame_index=0, shift_xy=(0.0, 0.0), method="identity"),
                1: RegistrationFrameResult(frame_index=1, shift_xy=(0.0, 0.0), method="identity"),
                2: RegistrationFrameResult(frame_index=2, shift_xy=(0.0, 0.0), method="identity"),
            },
        )

        with self.assertRaisesRegex(ValueError, "missing frame results"):
            build_aligned_frames(frames, missing)
        with self.assertRaisesRegex(ValueError, "out-of-range frame results"):
            build_aligned_frames(frames, extra)

    def test_validates_inputs(self) -> None:
        settings = RegistrationSettings(registration_view="raw")
        result_set = RegistrationResultSet(
            settings=settings,
            results_by_frame={
                0: RegistrationFrameResult(frame_index=0, shift_xy=(0.0, 0.0), method="identity"),
            },
        )

        with self.assertRaises(ValueError):
            build_aligned_frames(np.zeros((8, 8), dtype=np.float32), result_set)
        with self.assertRaises(ValueError):
            build_aligned_frames(np.array([[[np.nan]]], dtype=np.float32), result_set)
        with self.assertRaises(TypeError):
            build_aligned_frames(np.zeros((1, 8, 8), dtype=np.float32), object())  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
