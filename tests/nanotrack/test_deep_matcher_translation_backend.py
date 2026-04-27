import unittest

import numpy as np

from nanotrack.core import RegistrationSettings
from nanotrack.registration import (
    DeepMatcherTranslationBackend,
    DeepMatcherTranslationConfig,
    PhaseCorrelationBackendError,
    build_registration_view,
    run_adjacent_phase_registration,
)


class FakeMatcher:
    def __init__(self, translation_xy: tuple[float, float], *, outlier: bool = False):
        self.translation_xy = np.asarray(translation_xy, dtype=np.float64)
        self.outlier = bool(outlier)

    def match(self, reference_frame: np.ndarray, moving_frame: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        reference_xy = np.asarray(
            [
                [10.0, 10.0],
                [20.0, 12.0],
                [30.0, 18.0],
                [14.0, 32.0],
                [40.0, 38.0],
                [54.0, 22.0],
                [61.0, 49.0],
                [25.0, 55.0],
            ],
            dtype=np.float64,
        )
        moving_xy = reference_xy - self.translation_xy
        scores = np.linspace(0.8, 1.0, reference_xy.shape[0], dtype=np.float64)
        if self.outlier:
            moving_xy = np.vstack([moving_xy, np.asarray([[2.0, 70.0], [75.0, 4.0]], dtype=np.float64)])
            reference_xy = np.vstack([reference_xy, np.asarray([[70.0, 2.0], [4.0, 75.0]], dtype=np.float64)])
            scores = np.concatenate([scores, np.asarray([0.1, 0.1], dtype=np.float64)])
        return reference_xy, moving_xy, scores


class DeepMatcherTranslationBackendTests(unittest.TestCase):
    def _frame(self) -> np.ndarray:
        y, x = np.mgrid[0:80, 0:80]
        return (np.sin(x / 5.0) + np.cos(y / 7.0)).astype(np.float32)

    def test_estimates_translation_from_injected_matcher_with_outliers(self) -> None:
        backend = DeepMatcherTranslationBackend(
            DeepMatcherTranslationConfig(
                matcher="injected",
                min_matches=6,
                min_inliers=5,
                residual_threshold_px=0.5,
            ),
            matcher=FakeMatcher((3.0, -2.0), outlier=True),
        )

        result = backend.estimate(self._frame(), self._frame(), moving_frame_index=4)

        self.assertEqual(result.frame_index, 4)
        self.assertEqual(result.method, "deep_matcher_translation")
        self.assertEqual(result.status, "ok")
        self.assertAlmostEqual(result.dx, 3.0, delta=1e-9)
        self.assertAlmostEqual(result.dy, -2.0, delta=1e-9)
        self.assertGreater(result.quality_score, 0.7)

    def test_estimate_pair_uses_registration_view_and_masks(self) -> None:
        frame0 = self._frame()
        frame1 = self._frame()
        view = build_registration_view(np.stack([frame0, frame1]), view_name="normalized")
        mask = np.zeros(frame0.shape, dtype=bool)
        mask[5:70, 5:70] = True
        backend = DeepMatcherTranslationBackend(
            DeepMatcherTranslationConfig(matcher="injected", min_matches=6, min_inliers=5),
            matcher=FakeMatcher((-4.0, 1.5)),
        )

        result = backend.estimate_pair(
            view,
            reference_index=0,
            moving_index=1,
            reference_mask=mask,
            moving_mask=mask,
        )

        self.assertEqual(result.frame_index, 1)
        self.assertAlmostEqual(result.dx, -4.0, delta=1e-9)
        self.assertAlmostEqual(result.dy, 1.5, delta=1e-9)

    def test_adjacent_batch_accepts_injected_deep_matcher_backend(self) -> None:
        frame0 = self._frame()
        stack = np.stack([frame0, frame0, frame0]).astype(np.float32)
        backend = DeepMatcherTranslationBackend(
            DeepMatcherTranslationConfig(matcher="injected", min_matches=6, min_inliers=5),
            matcher=FakeMatcher((2.0, -1.0)),
        )

        result_set = run_adjacent_phase_registration(
            stack,
            settings=RegistrationSettings(
                backend="deep_matcher_translation",
                registration_view="normalized",
            ),
            backend=backend,
        )

        np.testing.assert_allclose(
            result_set.shifts_xy_array(),
            np.asarray([[0.0, 0.0], [2.0, -1.0], [4.0, -2.0]], dtype=np.float64),
            atol=1e-9,
        )
        self.assertEqual(result_set.get_result(2).method, "deep_matcher_translation_adjacent")

    def test_rejects_invalid_config_inputs_and_bad_matcher_outputs(self) -> None:
        with self.assertRaises(ValueError):
            DeepMatcherTranslationConfig(matcher="bad")
        with self.assertRaises(ValueError):
            DeepMatcherTranslationConfig(device="bad")
        with self.assertRaises(ValueError):
            DeepMatcherTranslationConfig(pretrained="")
        with self.assertRaises(ValueError):
            DeepMatcherTranslationConfig(min_matches=0)
        with self.assertRaises(ValueError):
            DeepMatcherTranslationConfig(min_inliers=0)
        with self.assertRaises(ValueError):
            DeepMatcherTranslationConfig(residual_threshold_px=0.0)
        with self.assertRaises(ValueError):
            DeepMatcherTranslationConfig(low_confidence_inlier_ratio=0.0)
        with self.assertRaises(ValueError):
            DeepMatcherTranslationBackend(DeepMatcherTranslationConfig(matcher="injected"))

        frame = self._frame()
        backend = DeepMatcherTranslationBackend(
            DeepMatcherTranslationConfig(matcher="injected"),
            matcher=FakeMatcher((1.0, 1.0)),
        )
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

        with self.assertRaises(TypeError):
            DeepMatcherTranslationBackend(
                DeepMatcherTranslationConfig(matcher="injected"),
                matcher=object(),
            )

        sparse_backend = DeepMatcherTranslationBackend(
            DeepMatcherTranslationConfig(matcher="injected", min_matches=12),
            matcher=FakeMatcher((1.0, 1.0)),
        )
        with self.assertRaises(PhaseCorrelationBackendError):
            sparse_backend.estimate(frame, frame, moving_frame_index=0)


if __name__ == "__main__":
    unittest.main()
