import unittest

import numpy as np

from nanotrack.core.data_models import (
    RegistrationFrameResult,
    RegistrationResultSet,
    RegistrationSettings,
    STMSequence,
    STMSequenceMetadata,
)


class STMSequenceMetadataTests(unittest.TestCase):
    def test_normalizes_frame_times_to_1d_float_array(self) -> None:
        metadata = STMSequenceMetadata(frame_times_s=[0, 1, 2])

        self.assertIsInstance(metadata.frame_times_s, np.ndarray)
        self.assertEqual(metadata.frame_times_s.dtype, np.float64)
        np.testing.assert_allclose(metadata.frame_times_s, [0.0, 1.0, 2.0])

    def test_rejects_non_1d_frame_times(self) -> None:
        with self.assertRaises(ValueError):
            STMSequenceMetadata(frame_times_s=[[0.0, 1.0]])


class STMSequenceTests(unittest.TestCase):
    def test_infers_missing_pixel_dimensions_from_raw_frames(self) -> None:
        frames = np.zeros((3, 5, 7), dtype=np.float32)
        sequence = STMSequence(
            source_path="movie.mpp",
            raw_frames=frames,
            metadata=STMSequenceMetadata(),
        )

        self.assertEqual(sequence.file_name, "movie.mpp")
        self.assertEqual(sequence.frame_count, 3)
        self.assertEqual(sequence.frame_shape, (5, 7))
        self.assertEqual(sequence.metadata.pixels_y, 5)
        self.assertEqual(sequence.metadata.pixels_x, 7)
        np.testing.assert_array_equal(sequence.active_frame, frames[0])

    def test_uses_explicit_frame_times_for_active_frame_time(self) -> None:
        frames = np.ones((3, 4, 4), dtype=np.float32)
        sequence = STMSequence(
            source_path="/tmp/sequence.mpp",
            raw_frames=frames,
            metadata=STMSequenceMetadata(
                pixels_x=4,
                pixels_y=4,
                frame_times_s=np.array([0.25, 0.75, 1.5]),
            ),
            active_frame_index=1,
        )

        self.assertEqual(sequence.active_frame_time_s, 0.75)

    def test_falls_back_to_frame_interval_when_frame_times_missing(self) -> None:
        frames = np.ones((4, 2, 2), dtype=np.float32)
        sequence = STMSequence(
            source_path="sequence.mpp",
            raw_frames=frames,
            metadata=STMSequenceMetadata(
                pixels_x=2,
                pixels_y=2,
                frame_interval_s=0.4,
            ),
        )

        self.assertAlmostEqual(sequence.get_frame_time_s(3), 1.2)

    def test_set_active_frame_updates_current_frame(self) -> None:
        frames = np.arange(27, dtype=np.float32).reshape(3, 3, 3)
        sequence = STMSequence(
            source_path="sequence.mpp",
            raw_frames=frames,
            metadata=STMSequenceMetadata(pixels_x=3, pixels_y=3),
        )

        sequence.set_active_frame(2)

        self.assertEqual(sequence.active_frame_index, 2)
        np.testing.assert_array_equal(sequence.active_frame, frames[2])

    def test_rejects_shape_mismatch_between_metadata_and_frames(self) -> None:
        frames = np.zeros((2, 4, 5), dtype=np.float32)

        with self.assertRaises(ValueError):
            STMSequence(
                source_path="sequence.mpp",
                raw_frames=frames,
                metadata=STMSequenceMetadata(pixels_x=6, pixels_y=4),
            )

    def test_rejects_invalid_active_frame_index(self) -> None:
        frames = np.zeros((2, 4, 5), dtype=np.float32)

        with self.assertRaises(IndexError):
            STMSequence(
                source_path="sequence.mpp",
                raw_frames=frames,
                metadata=STMSequenceMetadata(pixels_x=5, pixels_y=4),
                active_frame_index=2,
            )

    def test_rejects_frame_time_count_mismatch(self) -> None:
        frames = np.zeros((2, 4, 5), dtype=np.float32)

        with self.assertRaises(ValueError):
            STMSequence(
                source_path="sequence.mpp",
                raw_frames=frames,
                metadata=STMSequenceMetadata(
                    pixels_x=5,
                    pixels_y=4,
                    frame_times_s=np.array([0.0]),
                ),
            )


class RegistrationSettingsTests(unittest.TestCase):
    def test_normalizes_registration_settings(self) -> None:
        roi_mask = np.asarray([[0, 1], [2, 0]], dtype=np.uint8)

        settings = RegistrationSettings(
            backend=" phase_correlation ",
            reference_strategy=" adjacent ",
            registration_view=" gradient ",
            roi_mask=roi_mask,
            backend_params={"upsample_factor": 20},
        )

        self.assertEqual(settings.backend, "phase_correlation")
        self.assertEqual(settings.reference_strategy, "adjacent")
        self.assertEqual(settings.registration_view, "gradient")
        self.assertEqual(settings.backend_params, {"upsample_factor": 20})
        self.assertEqual(settings.roi_mask.dtype, np.bool_)
        np.testing.assert_array_equal(settings.roi_mask, [[False, True], [True, False]])

    def test_rejects_invalid_registration_settings(self) -> None:
        with self.assertRaises(ValueError):
            RegistrationSettings(backend="")
        with self.assertRaises(ValueError):
            RegistrationSettings(reference_strategy="")
        with self.assertRaises(ValueError):
            RegistrationSettings(registration_view="")
        with self.assertRaises(ValueError):
            RegistrationSettings(roi_mask=np.zeros((1, 2, 2), dtype=bool))


class RegistrationFrameResultTests(unittest.TestCase):
    def test_normalizes_registration_frame_result(self) -> None:
        result = RegistrationFrameResult(
            frame_index=2,
            shift_xy=np.asarray([1.25, -0.5], dtype=np.float32),
            method=" phase_correlation ",
            quality_score=0.82,
            phase_peak_ratio=3.4,
            ecc_score=0.91,
            num_inlier_tiles=7,
            num_total_tiles=9,
            median_tile_residual=0.2,
            flow_mad=0.15,
            status="ok",
        )

        self.assertEqual(result.frame_index, 2)
        self.assertEqual(result.shift_xy, (1.25, -0.5))
        self.assertEqual(result.dx, 1.25)
        self.assertEqual(result.dy, -0.5)
        self.assertEqual(result.method, "phase_correlation")
        self.assertEqual(result.quality_score, 0.82)
        self.assertEqual(result.num_inlier_tiles, 7)
        self.assertEqual(result.num_total_tiles, 9)

    def test_rejects_invalid_registration_frame_result(self) -> None:
        base = {
            "frame_index": 0,
            "shift_xy": (0.0, 0.0),
            "method": "phase_correlation",
        }
        invalid_cases = [
            {"frame_index": -1},
            {"shift_xy": (1.0,)},
            {"shift_xy": (1.0, np.nan)},
            {"method": ""},
            {"quality_score": 1.5},
            {"phase_peak_ratio": -0.1},
            {"num_inlier_tiles": -1},
            {"num_total_tiles": -1},
            {"median_tile_residual": -0.1},
            {"flow_mad": -0.1},
            {"status": "unknown"},
        ]

        for override in invalid_cases:
            payload = {**base, **override}
            with self.subTest(override=override):
                with self.assertRaises(ValueError):
                    RegistrationFrameResult(**payload)

        with self.assertRaises(ValueError):
            RegistrationFrameResult(**base, num_inlier_tiles=5, num_total_tiles=4)


class RegistrationResultSetTests(unittest.TestCase):
    def test_normalizes_result_set_and_exposes_helpers(self) -> None:
        settings = RegistrationSettings(backend="phase_correlation")
        result0 = RegistrationFrameResult(
            frame_index=0,
            shift_xy=(0.0, 0.0),
            method="phase_correlation",
            quality_score=1.0,
        )
        result2 = RegistrationFrameResult(
            frame_index=2,
            shift_xy=(1.5, -0.25),
            method="phase_correlation",
            quality_score=0.4,
            status="low_confidence",
        )

        result_set = RegistrationResultSet(
            settings=settings,
            results_by_frame={2: result2, 0: result0},
            reference_frame_index=0,
            template_frame_indices=[0, 2],
        )

        self.assertEqual(result_set.frame_indices, [0, 2])
        self.assertEqual(result_set.result_count, 2)
        self.assertIs(result_set.get_result(2), result2)
        self.assertIsNone(result_set.get_result(1))
        np.testing.assert_array_equal(result_set.shifts_xy_array(), np.asarray([[0.0, 0.0], [1.5, -0.25]]))
        self.assertEqual(result_set.template_frame_indices, (0, 2))
        self.assertEqual(result_set.status_counts()["ok"], 1)
        self.assertEqual(result_set.status_counts()["low_confidence"], 1)

    def test_rejects_invalid_result_set(self) -> None:
        settings = RegistrationSettings()
        result = RegistrationFrameResult(frame_index=1, shift_xy=(0.0, 0.0), method="phase_correlation")

        with self.assertRaises(TypeError):
            RegistrationResultSet(settings="bad", results_by_frame={})
        with self.assertRaises(ValueError):
            RegistrationResultSet(settings=settings, reference_frame_index=-1)
        with self.assertRaises(ValueError):
            RegistrationResultSet(settings=settings, results_by_frame={2: result})
        with self.assertRaises(TypeError):
            RegistrationResultSet(settings=settings, results_by_frame={1: object()})
        with self.assertRaises(ValueError):
            RegistrationResultSet(settings=settings, template_frame_indices=[0, -1])


if __name__ == "__main__":
    unittest.main()
