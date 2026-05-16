import unittest

import numpy as np

from nanotrack.core import RegistrationFrameResult, RegistrationResultSet, RegistrationSettings, STMSequenceMetadata
from nanotrack.registration import (
    ExpandedAlignedStack,
    build_aligned_frames,
    build_expanded_aligned_frames,
    run_adjacent_phase_registration,
)


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

    def test_materialized_aligned_view_does_not_mutate_raw_stack(self) -> None:
        frames = np.arange(2 * 5 * 6, dtype=np.float32).reshape(2, 5, 6)
        original = frames.copy()
        result_set = RegistrationResultSet(
            settings=RegistrationSettings(registration_view="raw"),
            results_by_frame={
                0: RegistrationFrameResult(frame_index=0, shift_xy=(0.0, 0.0), method="identity"),
                1: RegistrationFrameResult(frame_index=1, shift_xy=(1.0, -1.0), method="manual"),
            },
        )

        aligned = build_aligned_frames(frames, result_set, interpolation_order=0)

        np.testing.assert_array_equal(frames, original)
        self.assertFalse(np.shares_memory(aligned, frames))
        self.assertEqual(aligned.dtype, np.float32)
        np.testing.assert_array_equal(aligned[0], original[0])
        self.assertFalse(np.array_equal(aligned[1], original[1]))

    def test_builds_expanded_aligned_stack_api_surface(self) -> None:
        frames = np.arange(2 * 3 * 4, dtype=np.float32).reshape(2, 3, 4)
        result_set = RegistrationResultSet(
            settings=RegistrationSettings(registration_view="raw"),
            results_by_frame={
                0: RegistrationFrameResult(frame_index=0, shift_xy=(0.0, 0.0), method="identity"),
                1: RegistrationFrameResult(frame_index=1, shift_xy=(2.0, -1.0), method="manual"),
            },
        )

        expanded = build_expanded_aligned_frames(
            frames,
            result_set,
            interpolation_order=0,
            fill_value=-1.0,
        )

        self.assertIsInstance(expanded, ExpandedAlignedStack)
        self.assertEqual(expanded.frames.shape, (2, 4, 6))
        self.assertEqual(expanded.padding_ltrb, (0, 1, 2, 0))
        self.assertEqual(expanded.canvas_offset_xy, (0.0, 1.0))
        np.testing.assert_allclose(expanded.frame_origins_xy, np.asarray([[0.0, 1.0], [2.0, 0.0]]))
        self.assertEqual(expanded.metadata.pixels_x, 6)
        self.assertEqual(expanded.metadata.pixels_y, 4)

    def test_expanded_aligned_canvas_preserves_integer_shifted_edge_pixels(self) -> None:
        frames = np.zeros((3, 3, 4), dtype=np.float32)
        frames[0, 0, 0] = 10.0
        frames[0, -1, -1] = 11.0
        frames[1, 0, 0] = 20.0
        frames[1, -1, -1] = 21.0
        frames[2, 0, 0] = 30.0
        frames[2, -1, -1] = 31.0
        result_set = RegistrationResultSet(
            settings=RegistrationSettings(registration_view="raw"),
            results_by_frame={
                0: RegistrationFrameResult(frame_index=0, shift_xy=(-2.0, 1.0), method="manual"),
                1: RegistrationFrameResult(frame_index=1, shift_xy=(0.0, 0.0), method="identity"),
                2: RegistrationFrameResult(frame_index=2, shift_xy=(3.0, -1.0), method="manual"),
            },
        )

        expanded = build_expanded_aligned_frames(
            frames,
            result_set,
            interpolation_order=0,
            fill_value=-1.0,
        )

        self.assertEqual(expanded.padding_ltrb, (2, 1, 3, 1))
        self.assertEqual(expanded.frames.shape, (3, 5, 9))
        np.testing.assert_allclose(
            expanded.frame_origins_xy,
            np.asarray([[0.0, 2.0], [2.0, 1.0], [5.0, 0.0]], dtype=np.float64),
        )
        self.assertEqual(expanded.frames[0, 2, 0], 10.0)
        self.assertEqual(expanded.frames[0, 4, 3], 11.0)
        self.assertEqual(expanded.frames[1, 1, 2], 20.0)
        self.assertEqual(expanded.frames[1, 3, 5], 21.0)
        self.assertEqual(expanded.frames[2, 0, 5], 30.0)
        self.assertEqual(expanded.frames[2, 2, 8], 31.0)

    def test_expanded_aligned_canvas_uses_ceiling_padding_for_subpixel_shifts(self) -> None:
        frames = np.zeros((3, 5, 7), dtype=np.float32)
        result_set = RegistrationResultSet(
            settings=RegistrationSettings(registration_view="raw"),
            results_by_frame={
                0: RegistrationFrameResult(frame_index=0, shift_xy=(-1.25, 3.4), method="manual"),
                1: RegistrationFrameResult(frame_index=1, shift_xy=(0.0, 0.0), method="identity"),
                2: RegistrationFrameResult(frame_index=2, shift_xy=(2.01, -0.1), method="manual"),
            },
        )

        expanded = build_expanded_aligned_frames(frames, result_set, interpolation_order=1)

        self.assertEqual(expanded.padding_ltrb, (2, 1, 3, 4))
        self.assertEqual(expanded.frames.shape, (3, 10, 12))
        self.assertEqual(expanded.canvas_offset_xy, (2.0, 1.0))
        np.testing.assert_allclose(
            expanded.frame_origins_xy,
            np.asarray([[0.75, 4.4], [2.0, 1.0], [4.01, 0.9]], dtype=np.float64),
        )

    def test_expanded_aligned_view_does_not_mutate_raw_stack_or_share_memory(self) -> None:
        frames = np.arange(2 * 4 * 5, dtype=np.float32).reshape(2, 4, 5)
        original = frames.copy()
        result_set = RegistrationResultSet(
            settings=RegistrationSettings(registration_view="raw"),
            results_by_frame={
                0: RegistrationFrameResult(frame_index=0, shift_xy=(0.0, 0.0), method="identity"),
                1: RegistrationFrameResult(frame_index=1, shift_xy=(-1.0, 2.0), method="manual"),
            },
        )

        expanded = build_expanded_aligned_frames(
            frames,
            result_set,
            interpolation_order=0,
            fill_value=-1.0,
        )

        np.testing.assert_array_equal(frames, original)
        self.assertFalse(np.shares_memory(expanded.frames, frames))
        self.assertEqual(expanded.frames.dtype, np.float32)

    def test_expanded_metadata_updates_physical_size_and_offsets(self) -> None:
        frames = np.zeros((2, 3, 4), dtype=np.float32)
        metadata = STMSequenceMetadata(
            pixels_x=4,
            pixels_y=3,
            size_nm_x=8.0,
            size_nm_y=6.0,
            offset_nm_x=10.0,
            offset_nm_y=20.0,
            scan_angle_deg=15.0,
            bias_v=1.2,
            setpoint_a=2e-9,
            image_type="Topography",
            frame_interval_s=0.5,
        )
        result_set = RegistrationResultSet(
            settings=RegistrationSettings(registration_view="raw"),
            results_by_frame={
                0: RegistrationFrameResult(frame_index=0, shift_xy=(-2.0, 1.0), method="manual"),
                1: RegistrationFrameResult(frame_index=1, shift_xy=(3.0, -1.0), method="manual"),
            },
        )

        expanded = build_expanded_aligned_frames(frames, result_set, metadata=metadata)

        self.assertEqual(expanded.padding_ltrb, (2, 1, 3, 1))
        self.assertEqual(expanded.metadata.pixels_x, 9)
        self.assertEqual(expanded.metadata.pixels_y, 5)
        self.assertAlmostEqual(expanded.metadata.size_nm_x, 18.0)
        self.assertAlmostEqual(expanded.metadata.size_nm_y, 10.0)
        self.assertAlmostEqual(expanded.metadata.offset_nm_x, 6.0)
        self.assertAlmostEqual(expanded.metadata.offset_nm_y, 18.0)
        self.assertEqual(expanded.metadata.scan_angle_deg, 15.0)
        self.assertEqual(expanded.metadata.bias_v, 1.2)
        self.assertEqual(expanded.metadata.setpoint_a, 2e-9)
        self.assertEqual(expanded.metadata.image_type, "Topography")
        self.assertEqual(expanded.metadata.frame_interval_s, 0.5)

    def test_expanded_metadata_does_not_guess_missing_physical_scale(self) -> None:
        frames = np.zeros((2, 3, 4), dtype=np.float32)
        metadata = STMSequenceMetadata(
            pixels_x=4,
            pixels_y=3,
            size_nm_x=0.0,
            size_nm_y=0.0,
            offset_nm_x=10.0,
            offset_nm_y=20.0,
        )
        result_set = RegistrationResultSet(
            settings=RegistrationSettings(registration_view="raw"),
            results_by_frame={
                0: RegistrationFrameResult(frame_index=0, shift_xy=(-2.0, 1.0), method="manual"),
                1: RegistrationFrameResult(frame_index=1, shift_xy=(3.0, -1.0), method="manual"),
            },
        )

        expanded = build_expanded_aligned_frames(frames, result_set, metadata=metadata)

        self.assertEqual(expanded.metadata.pixels_x, 9)
        self.assertEqual(expanded.metadata.pixels_y, 5)
        self.assertEqual(expanded.metadata.size_nm_x, 0.0)
        self.assertEqual(expanded.metadata.size_nm_y, 0.0)
        self.assertEqual(expanded.metadata.offset_nm_x, 10.0)
        self.assertEqual(expanded.metadata.offset_nm_y, 20.0)

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
