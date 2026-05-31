import unittest

import numpy as np


class MolTrackRegistrationWorkflowTests(unittest.TestCase):
    def _textured_frame(self) -> np.ndarray:
        rng = np.random.default_rng(123)
        frame = rng.normal(0.0, 0.05, (64, 64)).astype(np.float32)
        frame[10:24, 12:28] += 2.0
        frame[34:48, 40:55] -= 1.5
        frame[42:56, 8:18] += 1.2
        return frame

    def test_run_project_registration_reuses_nanotrack_adjacent_registration(self) -> None:
        from moltrack.core import MolTrackProject, SourceImageSeries
        from moltrack.registration import run_project_registration

        frame0 = self._textured_frame()
        frame1 = np.roll(frame0, shift=(3, -4), axis=(0, 1))
        frame2 = np.roll(frame1, shift=(-2, 1), axis=(0, 1))
        source = SourceImageSeries(
            source_uri="synthetic",
            frame_count=3,
            raw_frames=np.stack([frame0, frame1, frame2]),
        )
        project = MolTrackProject.from_source_series(source)

        registered = run_project_registration(project, backend="phase_correlation")

        self.assertIsNot(registered, project)
        self.assertEqual([shift.working_frame_index for shift in registered.registration_shifts], [0, 1, 2])
        self.assertEqual(registered.registration_shift_for_working_frame(0).shift_xy, (0.0, 0.0))
        self.assertAlmostEqual(registered.registration_shift_for_working_frame(1).dx, 4.0, places=3)
        self.assertAlmostEqual(registered.registration_shift_for_working_frame(1).dy, -3.0, places=3)
        self.assertAlmostEqual(registered.registration_shift_for_working_frame(2).dx, 3.0, places=3)
        self.assertAlmostEqual(registered.registration_shift_for_working_frame(2).dy, -1.0, places=3)
        self.assertEqual(registered.registration_shift_for_working_frame(2).method, "phase_correlation_adjacent")

    def test_registered_working_frame_materializes_shifted_view_without_mutating_native_frame(self) -> None:
        from moltrack.core import MolTrackProject, RegistrationShift, SourceImageSeries
        from moltrack.registration import registered_working_frame

        raw = np.zeros((2, 5, 5), dtype=np.float32)
        raw[1, 2, 2] = 1.0
        project = MolTrackProject.from_source_series(
            SourceImageSeries(source_uri="synthetic", frame_count=2, raw_frames=raw)
        ).with_registration_shifts(
            (
                RegistrationShift(working_frame_index=0, dx=0.0, dy=0.0, method="identity"),
                RegistrationShift(working_frame_index=1, dx=1.0, dy=-1.0, method="manual"),
            )
        )

        registered = registered_working_frame(project, 1, interpolation_order=0)

        expected = np.zeros((5, 5), dtype=np.float32)
        expected[1, 3] = 1.0
        np.testing.assert_array_equal(registered, expected)
        np.testing.assert_array_equal(project.source_series.get_frame(1), raw[1])

    def test_registered_working_stack_follows_working_frame_order(self) -> None:
        from moltrack.core import MolTrackProject, RegistrationShift, SourceImageSeries
        from moltrack.registration import registered_working_stack

        raw = np.zeros((3, 5, 5), dtype=np.float32)
        raw[0, 2, 2] = 1.0
        raw[1, 1, 1] = 2.0
        raw[2, 3, 3] = 3.0
        source = SourceImageSeries(source_uri="synthetic", frame_count=3, raw_frames=raw)
        project = MolTrackProject.from_source_series(source, reverse_frame_order=True).with_registration_shifts(
            (
                RegistrationShift(working_frame_index=0, dx=0.0, dy=0.0, method="identity"),
                RegistrationShift(working_frame_index=1, dx=1.0, dy=0.0, method="manual"),
                RegistrationShift(working_frame_index=2, dx=0.0, dy=1.0, method="manual"),
            )
        )

        stack = registered_working_stack(project, interpolation_order=0)

        self.assertEqual(stack.shape, (3, 5, 5))
        self.assertEqual(stack[0, 3, 3], 3.0)
        self.assertEqual(stack[1, 1, 2], 2.0)
        self.assertEqual(stack[2, 3, 2], 1.0)

    def test_expanded_registered_working_stack_adds_canvas_without_clipping(self) -> None:
        from moltrack.core import MolTrackProject, RegistrationShift, SourceImageSeries
        from moltrack.registration import expanded_registered_working_stack

        raw = np.zeros((3, 3, 4), dtype=np.float32)
        raw[0, 0, 0] = 10.0
        raw[0, -1, -1] = 11.0
        raw[1, 0, 0] = 20.0
        raw[1, -1, -1] = 21.0
        raw[2, 0, 0] = 30.0
        raw[2, -1, -1] = 31.0
        project = MolTrackProject.from_source_series(
            SourceImageSeries(source_uri="synthetic", frame_count=3, raw_frames=raw)
        ).with_registration_shifts(
            (
                RegistrationShift(working_frame_index=0, dx=-2.0, dy=1.0, method="manual"),
                RegistrationShift(working_frame_index=1, dx=0.0, dy=0.0, method="identity"),
                RegistrationShift(working_frame_index=2, dx=3.0, dy=-1.0, method="manual"),
            )
        )

        expanded = expanded_registered_working_stack(project, interpolation_order=0, fill_value=-1.0)

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
        np.testing.assert_array_equal(project.source_series.raw_frames, raw)

    def test_registered_coordinate_helpers_transform_points_and_bboxes_without_mutating_inputs(self) -> None:
        from moltrack.core import MolTrackProject, RegistrationShift, SourceImageSeries
        from moltrack.registration import (
            native_bbox_to_registered_xyxy,
            native_to_registered_xy,
            registered_bbox_to_native_xyxy,
            registered_to_native_xy,
        )

        project = MolTrackProject.from_source_series(
            SourceImageSeries(source_uri="synthetic", frame_count=2)
        ).with_registration_shifts(
            (
                RegistrationShift(working_frame_index=0, dx=0.0, dy=0.0, method="identity"),
                RegistrationShift(working_frame_index=1, dx=2.5, dy=-3.0, method="manual"),
            )
        )
        point = np.asarray([10.0, 20.0], dtype=np.float64)
        bbox = (1.0, 2.0, 5.0, 8.0)

        registered_point = native_to_registered_xy(project, 1, point)
        restored_point = registered_to_native_xy(project, 1, registered_point)
        registered_bbox = native_bbox_to_registered_xyxy(project, 1, bbox)
        restored_bbox = registered_bbox_to_native_xyxy(project, 1, registered_bbox)

        np.testing.assert_allclose(registered_point, np.asarray([12.5, 17.0]))
        np.testing.assert_allclose(restored_point, point)
        self.assertEqual(registered_bbox, (3.5, -1.0, 7.5, 5.0))
        self.assertEqual(restored_bbox, bbox)
        np.testing.assert_array_equal(point, np.asarray([10.0, 20.0]))

    def test_linking_xy_uses_registered_coordinates_only_when_available(self) -> None:
        from moltrack.core import MolTrackProject, RegistrationShift, SourceImageSeries
        from moltrack.registration import linking_xy

        project = MolTrackProject.from_source_series(
            SourceImageSeries(source_uri="synthetic", frame_count=3)
        ).with_registration_shifts(
            (
                RegistrationShift(working_frame_index=0, dx=0.0, dy=0.0, method="identity"),
                RegistrationShift(working_frame_index=1, dx=2.0, dy=-1.0, method="manual"),
            )
        )

        np.testing.assert_allclose(linking_xy(project, 1, (5.0, 7.0)), np.asarray([7.0, 6.0]))
        np.testing.assert_allclose(linking_xy(project, 2, (5.0, 7.0)), np.asarray([5.0, 7.0]))
        np.testing.assert_allclose(
            linking_xy(project, 1, (5.0, 7.0), use_registered=False),
            np.asarray([5.0, 7.0]),
        )


if __name__ == "__main__":
    unittest.main()
