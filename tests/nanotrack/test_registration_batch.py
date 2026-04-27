import unittest

import numpy as np

from nanotrack.core import RegistrationSettings
from nanotrack.registration import run_adjacent_phase_registration


class AdjacentPhaseRegistrationTests(unittest.TestCase):
    def _textured_frame(self) -> np.ndarray:
        rng = np.random.default_rng(11)
        frame = rng.normal(0.0, 0.08, (64, 64)).astype(np.float32)
        frame[9:21, 12:28] += 2.0
        frame[32:46, 36:51] -= 1.5
        frame[45:56, 8:16] += 1.2
        return frame

    def test_accumulates_adjacent_shifts_to_frame_zero(self) -> None:
        frame0 = self._textured_frame()
        frame1 = np.roll(frame0, shift=(2, -3), axis=(0, 1))
        frame2 = np.roll(frame1, shift=(-1, 5), axis=(0, 1))
        progress: list[tuple[int, int, int, tuple[float, float]]] = []

        result_set = run_adjacent_phase_registration(
            np.stack([frame0, frame1, frame2]).astype(np.float32),
            settings=RegistrationSettings(registration_view="normalized"),
            progress_callback=lambda processed, total, result: progress.append(
                (processed, total, result.frame_index, result.shift_xy)
            ),
        )

        self.assertEqual(result_set.reference_frame_index, 0)
        self.assertEqual(result_set.template_frame_indices, (0,))
        self.assertEqual(result_set.frame_indices, [0, 1, 2])
        self.assertEqual(result_set.result_count, 3)
        np.testing.assert_allclose(
            result_set.shifts_xy_array(),
            np.asarray(
                [
                    [0.0, 0.0],
                    [3.0, -2.0],
                    [-2.0, -1.0],
                ],
                dtype=np.float64,
            ),
            atol=1e-6,
        )
        self.assertEqual(result_set.get_result(0).method, "identity")
        self.assertEqual(result_set.get_result(1).method, "phase_correlation_adjacent")
        self.assertEqual(result_set.status_counts()["ok"], 3)
        self.assertEqual([row[:3] for row in progress], [(1, 3, 0), (2, 3, 1), (3, 3, 2)])

    def test_single_frame_sequence_returns_identity_shift(self) -> None:
        result_set = run_adjacent_phase_registration(self._textured_frame()[None, :, :])

        self.assertEqual(result_set.frame_indices, [0])
        np.testing.assert_array_equal(result_set.shifts_xy_array(), np.asarray([[0.0, 0.0]], dtype=np.float64))
        self.assertEqual(result_set.get_result(0).quality_score, 1.0)

    def test_rejects_invalid_inputs_and_reference_strategy(self) -> None:
        frame = self._textured_frame()
        with self.assertRaises(ValueError):
            run_adjacent_phase_registration(frame)
        with self.assertRaises(ValueError):
            run_adjacent_phase_registration(np.array([[[np.nan]]], dtype=np.float32))
        with self.assertRaises(ValueError):
            run_adjacent_phase_registration(
                frame[None, :, :],
                settings=RegistrationSettings(reference_strategy="template"),
            )


if __name__ == "__main__":
    unittest.main()
