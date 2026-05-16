import unittest

import numpy as np

from nanotrack.core import RegistrationFrameResult, RegistrationResultSet, RegistrationSettings
from nanotrack.registration import (
    GlobalShiftGraphOptimizer,
    GlobalShiftGraphOptimizerConfig,
    GlobalShiftGraphOptimizerError,
    PairwiseShiftMeasurement,
)


class GlobalShiftGraphOptimizerTests(unittest.TestCase):
    def test_solves_consistent_multi_edge_graph(self) -> None:
        true_shifts = np.asarray(
            [
                [0.0, 0.0],
                [2.0, -1.0],
                [4.0, -1.5],
                [6.0, -2.0],
            ],
            dtype=np.float64,
        )
        measurements = [
            self._measurement(0, 1, true_shifts),
            self._measurement(1, 2, true_shifts),
            self._measurement(2, 3, true_shifts),
            self._measurement(0, 2, true_shifts),
            self._measurement(1, 3, true_shifts),
        ]

        result_set = GlobalShiftGraphOptimizer().optimize(frame_count=4, measurements=measurements)

        self.assertEqual(result_set.settings.backend, "global_shift_graph")
        self.assertEqual(result_set.reference_frame_index, 0)
        np.testing.assert_allclose(result_set.shifts_xy_array(), true_shifts, atol=1e-9)
        self.assertEqual(result_set.get_result(0).method, "identity")
        self.assertEqual(result_set.get_result(3).method, "global_shift_graph")
        self.assertEqual(result_set.status_counts()["ok"], 4)

    def test_weighted_graph_downweights_outlier_edge(self) -> None:
        true_shifts = np.asarray([[0.0, 0.0], [1.0, 0.0], [2.0, 0.0]], dtype=np.float64)
        measurements = [
            self._measurement(0, 1, true_shifts, weight=1.0),
            self._measurement(1, 2, true_shifts, weight=1.0),
            PairwiseShiftMeasurement(0, 2, shift_xy=(20.0, 0.0), weight=0.001),
        ]

        result_set = GlobalShiftGraphOptimizer().optimize(frame_count=3, measurements=measurements)

        np.testing.assert_allclose(result_set.shifts_xy_array(), true_shifts, atol=0.05)

    def test_smoothness_regularization_damps_noisy_middle_shift(self) -> None:
        measurements = [
            PairwiseShiftMeasurement(0, 1, shift_xy=(1.0, 0.0)),
            PairwiseShiftMeasurement(1, 2, shift_xy=(5.0, 0.0)),
            PairwiseShiftMeasurement(2, 3, shift_xy=(1.0, 0.0)),
        ]
        unsmoothed = GlobalShiftGraphOptimizer().optimize(frame_count=4, measurements=measurements)
        smoothed = GlobalShiftGraphOptimizer(
            GlobalShiftGraphOptimizerConfig(smoothness_lambda=10.0)
        ).optimize(frame_count=4, measurements=measurements)

        self.assertGreater(unsmoothed.get_result(2).dx - unsmoothed.get_result(1).dx, 4.5)
        self.assertLess(smoothed.get_result(2).dx - smoothed.get_result(1).dx, 4.0)

    def test_optimize_result_set_converts_cumulative_shifts_to_adjacent_edges(self) -> None:
        settings = RegistrationSettings(backend="phase_correlation")
        source = RegistrationResultSet(
            settings=settings,
            results_by_frame={
                0: RegistrationFrameResult(0, (0.0, 0.0), "identity", quality_score=1.0),
                1: RegistrationFrameResult(1, (3.0, -2.0), "phase_correlation_adjacent", quality_score=0.9),
                2: RegistrationFrameResult(2, (-2.0, -1.0), "phase_correlation_adjacent", quality_score=0.8),
            },
            reference_frame_index=0,
            template_frame_indices=(0,),
        )

        optimized = GlobalShiftGraphOptimizer().optimize_result_set(source)

        np.testing.assert_allclose(
            optimized.shifts_xy_array(),
            np.asarray([[0.0, 0.0], [3.0, -2.0], [-2.0, -1.0]], dtype=np.float64),
            atol=1e-9,
        )
        self.assertEqual(optimized.settings.backend, "global_shift_graph")
        self.assertEqual(optimized.settings.backend_params["source_backend"], "phase_correlation")

    def test_rejects_invalid_config_measurements_and_disconnected_graph(self) -> None:
        with self.assertRaises(ValueError):
            GlobalShiftGraphOptimizerConfig(reference_frame_index=-1)
        with self.assertRaises(ValueError):
            GlobalShiftGraphOptimizerConfig(smoothness_lambda=-1.0)
        with self.assertRaises(ValueError):
            GlobalShiftGraphOptimizerConfig(huber_delta_px=0.0)
        with self.assertRaises(ValueError):
            GlobalShiftGraphOptimizerConfig(robust_iterations=0)
        with self.assertRaises(ValueError):
            GlobalShiftGraphOptimizerConfig(low_confidence_residual_px=-1.0)
        with self.assertRaises(ValueError):
            GlobalShiftGraphOptimizerConfig(min_measurements=0)
        with self.assertRaises(ValueError):
            PairwiseShiftMeasurement(0, 0, (0.0, 0.0))
        with self.assertRaises(ValueError):
            PairwiseShiftMeasurement(0, 1, (0.0,))
        with self.assertRaises(ValueError):
            PairwiseShiftMeasurement(0, 1, (0.0, 0.0), weight=0.0)
        with self.assertRaises(TypeError):
            GlobalShiftGraphOptimizer().optimize(frame_count=2, measurements=[object()])
        with self.assertRaises(ValueError):
            GlobalShiftGraphOptimizer().optimize(
                frame_count=2,
                measurements=[PairwiseShiftMeasurement(0, 2, (1.0, 0.0))],
            )
        with self.assertRaises(GlobalShiftGraphOptimizerError):
            GlobalShiftGraphOptimizer().optimize(
                frame_count=3,
                measurements=[PairwiseShiftMeasurement(0, 1, (1.0, 0.0))],
            )

    @staticmethod
    def _measurement(
        reference_index: int,
        moving_index: int,
        shifts: np.ndarray,
        *,
        weight: float = 1.0,
    ) -> PairwiseShiftMeasurement:
        return PairwiseShiftMeasurement(
            reference_index=reference_index,
            moving_index=moving_index,
            shift_xy=shifts[moving_index] - shifts[reference_index],
            weight=weight,
        )


if __name__ == "__main__":
    unittest.main()
