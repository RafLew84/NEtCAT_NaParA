import unittest

import numpy as np

from moltrack.core import MolTrackImageSeries
from moltrack.core.registration import (
    MolTrackRegistrationFrameResult,
    MolTrackRegistrationResultSet,
    MolTrackRegistrationSettings,
    build_moltrack_expanded_aligned_stack,
    run_moltrack_registration,
)
from nanotrack.core import (
    RegistrationFrameResult,
    RegistrationResultSet,
    STMSequenceMetadata,
)


class MolTrackRegistrationTests(unittest.TestCase):
    def test_registration_runs_on_current_working_frames_and_stores_moltrack_results(self) -> None:
        frames = np.arange(24, dtype=np.float32).reshape(3, 2, 4)
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames.copy(),
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=2),
        )
        series.remove_frame(1)
        calls = []

        def fake_runner(source_frames, *, settings, progress_callback=None):
            calls.append((source_frames.copy(), settings.backend, settings.reference_strategy, settings.registration_view))
            return RegistrationResultSet(
                settings=settings,
                results_by_frame={
                    0: RegistrationFrameResult(
                        frame_index=0,
                        shift_xy=(0.0, 0.0),
                        method="identity",
                        quality_score=1.0,
                    ),
                    1: RegistrationFrameResult(
                        frame_index=1,
                        shift_xy=(2.5, -1.0),
                        method="phase_correlation",
                        quality_score=0.75,
                    ),
                },
            )

        result_set = run_moltrack_registration(
            series,
            settings=MolTrackRegistrationSettings(backend="phase_correlation"),
            registration_runner=fake_runner,
        )

        self.assertEqual(len(calls), 1)
        passed_frames, backend, reference_strategy, registration_view = calls[0]
        np.testing.assert_array_equal(passed_frames, frames[[0, 2]])
        self.assertEqual((backend, reference_strategy, registration_view), ("phase_correlation", "adjacent", "raw"))
        self.assertIs(series.registration_results, result_set)
        self.assertEqual(result_set.result_count, 2)
        self.assertEqual(result_set.frame_indices, (0, 1))
        self.assertEqual(result_set.get_result(1).shift_xy, (2.5, -1.0))
        self.assertEqual(result_set.get_result(1).status, "ok")

    def test_registration_rejects_results_that_do_not_match_working_frame_count(self) -> None:
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.zeros((2, 2, 4), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=2),
        )

        def incomplete_runner(source_frames, *, settings, progress_callback=None):
            return RegistrationResultSet(
                settings=settings,
                results_by_frame={
                    0: RegistrationFrameResult(
                        frame_index=0,
                        shift_xy=(0.0, 0.0),
                        method="identity",
                        quality_score=1.0,
                    ),
                },
            )

        with self.assertRaisesRegex(ValueError, "registration results do not match working frame count"):
            run_moltrack_registration(series, registration_runner=incomplete_runner)

        self.assertIsNone(series.registration_results)

    def test_removing_frame_clears_stale_registration_results(self) -> None:
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.zeros((2, 2, 4), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=2),
        )
        series.registration_results = MolTrackRegistrationResultSet(
            settings=MolTrackRegistrationSettings(),
            results_by_frame={
                0: MolTrackRegistrationFrameResult(
                    frame_index=0,
                    shift_xy=(0.0, 0.0),
                    method="identity",
                    quality_score=1.0,
                ),
                1: MolTrackRegistrationFrameResult(
                    frame_index=1,
                    shift_xy=(1.0, 0.0),
                    method="phase_correlation",
                    quality_score=0.8,
                ),
            },
        )
        series.expanded_aligned_stack = object()

        series.remove_frame(1)

        self.assertIsNone(series.registration_results)
        self.assertIsNone(series.expanded_aligned_stack)

    def test_builds_expanded_aligned_stack_from_moltrack_registration_results(self) -> None:
        frames = np.zeros((3, 3, 4), dtype=np.float32)
        frames[0, 0, 0] = 10.0
        frames[0, -1, -1] = 11.0
        frames[1, 0, 0] = 20.0
        frames[1, -1, -1] = 21.0
        frames[2, 0, 0] = 30.0
        frames[2, -1, -1] = 31.0
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames.copy(),
            metadata=STMSequenceMetadata(
                pixels_x=4,
                pixels_y=3,
                size_nm_x=8.0,
                size_nm_y=6.0,
            ),
            registration_results=MolTrackRegistrationResultSet(
                settings=MolTrackRegistrationSettings(),
                results_by_frame={
                    0: MolTrackRegistrationFrameResult(
                        frame_index=0,
                        shift_xy=(-2.0, 1.0),
                        method="manual",
                    ),
                    1: MolTrackRegistrationFrameResult(
                        frame_index=1,
                        shift_xy=(0.0, 0.0),
                        method="identity",
                    ),
                    2: MolTrackRegistrationFrameResult(
                        frame_index=2,
                        shift_xy=(3.0, -1.0),
                        method="manual",
                    ),
                },
            ),
        )

        expanded = build_moltrack_expanded_aligned_stack(
            series,
            interpolation_order=0,
            fill_value=-1.0,
        )

        self.assertIs(series.expanded_aligned_stack, expanded)
        self.assertEqual(expanded.padding_ltrb, (2, 1, 3, 1))
        self.assertEqual(expanded.frames.shape, (3, 5, 9))
        np.testing.assert_allclose(
            expanded.frame_origins_xy,
            np.asarray([[0.0, 2.0], [2.0, 1.0], [5.0, 0.0]], dtype=np.float64),
        )
        self.assertEqual(expanded.metadata.pixels_x, 9)
        self.assertEqual(expanded.metadata.pixels_y, 5)
        self.assertAlmostEqual(expanded.metadata.size_nm_x, 18.0)
        self.assertAlmostEqual(expanded.metadata.size_nm_y, 10.0)
        self.assertEqual(expanded.frames[0, 2, 0], 10.0)
        self.assertEqual(expanded.frames[0, 4, 3], 11.0)
        self.assertEqual(expanded.frames[1, 1, 2], 20.0)
        self.assertEqual(expanded.frames[1, 3, 5], 21.0)
        self.assertEqual(expanded.frames[2, 0, 5], 30.0)
        self.assertEqual(expanded.frames[2, 2, 8], 31.0)


if __name__ == "__main__":
    unittest.main()
