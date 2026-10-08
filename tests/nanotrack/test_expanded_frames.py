"""Expanded canvas and scientific samples through the public frame provider."""
import unittest
import tracemalloc

import numpy as np

from nanotrack.core import RegistrationFrameResult, RegistrationResultSet, RegistrationSettings, STMSequenceMetadata
from nanotrack.registration.scalar_frames import ScalarFrameProvider


class ExpandedFrameTests(unittest.TestCase):
    def test_sequence_canvas_includes_missing_frames_and_preserves_calibration(self):
        provider = ScalarFrameProvider(np.zeros((6, 64, 96)), STMSequenceMetadata(
            pixels_x=96, pixels_y=64, size_nm_x=192, size_nm_y=64, offset_nm_x=10, offset_nm_y=20,
        ))
        registration = RegistrationResultSet(RegistrationSettings(), {
            0: RegistrationFrameResult(0, (0., 0.), "identity"),
            1: RegistrationFrameResult(1, (3.25, -2.5), "manual"),
            2: RegistrationFrameResult(2, (-2., 3.), "manual"),
            3: RegistrationFrameResult(3, (-.5, .25), "manual"),
            5: RegistrationFrameResult(5, (99., 99.), "excluded_frame"),
        })

        canvas = provider.get_canvas(expanded=True, registration=registration)

        self.assertEqual(canvas.bounds_xyxy, (-2, -3, 100, 67))
        self.assertEqual(canvas.shape_hw, (70, 102))
        self.assertEqual(canvas.offset_xy, (2., 3.))
        self.assertEqual(canvas.metadata.get_pixel_size_nm(), (2., 1.))
        self.assertEqual((canvas.metadata.size_nm_x, canvas.metadata.size_nm_y), (204., 70.))
        self.assertEqual((canvas.metadata.offset_nm_x, canvas.metadata.offset_nm_y), (6., 17.))
        original = provider.get_canvas()
        self.assertEqual(original.bounds_xyxy, (0, 0, 96, 64))
        self.assertEqual((original.metadata.offset_nm_x, original.metadata.offset_nm_y), (10., 20.))

    def test_expanded_samples_once_from_source_and_maps_annotations_on_the_same_canvas(self):
        values = np.array([[10., 20., 30., 40.], [50., np.nan, 70., 80.], [90., 100., 110., 120.]])
        frames = np.stack([values, values, np.full((3, 4), 17.123456789)])
        provider = ScalarFrameProvider(frames, STMSequenceMetadata(pixels_x=4, pixels_y=3))
        registration = RegistrationResultSet(RegistrationSettings(), {
            0: RegistrationFrameResult(0, (-1., .5), "manual"),
            1: RegistrationFrameResult(1, (.5, -1.), "manual"),
        })

        frame = provider.get_frame(0, aligned=True, expanded=True, registration=registration)

        self.assertEqual(frame.values.shape, (5, 6))
        self.assertEqual(frame.values.dtype, np.float64)
        expected = np.full((5, 6), np.nan)
        expected[2:4, :4] = [[30., np.nan, 50., 60.], [70., np.nan, 90., 100.]]
        np.testing.assert_array_equal(frame.values, expected)
        np.testing.assert_array_equal(frame.valid_mask, np.isfinite(expected))
        np.testing.assert_array_equal(frame.geometry.source_to_display([2., 1.]), [2., 2.5])
        np.testing.assert_array_equal(frame.geometry.display_to_source([2., 2.5]), [2., 1.])
        missing = provider.get_frame(2, aligned=True, expanded=True, registration=registration)
        self.assertEqual(missing.registration_status, "missing")
        expected[:] = np.nan
        expected[1:4, 1:5] = 17.123456789
        np.testing.assert_array_equal(missing.values, expected)
        self.assertEqual(missing.metadata.get_pixel_size_nm(), (None, None))

    def test_canvas_rejects_excessive_memory_before_frame_materialization(self):
        provider = ScalarFrameProvider(np.ones((2, 4, 4)), STMSequenceMetadata(pixels_x=4, pixels_y=4))
        registration = RegistrationResultSet(RegistrationSettings(), {
            1: RegistrationFrameResult(1, (1e9, -1e9), "manual"),
        })
        with self.assertRaisesRegex(MemoryError, "512 MiB"):
            provider.get_canvas(expanded=True, registration=registration)

    def test_extreme_shift_and_source_changes_update_cached_frames_without_a_movie_allocation(self):
        frames = np.broadcast_to(np.full((1, 32, 48), 17.123456789), (1500, 32, 48))
        metadata = STMSequenceMetadata(pixels_x=48, pixels_y=32, size_nm_x=96, size_nm_y=32)
        provider = ScalarFrameProvider(frames, metadata, max_cache_bytes=40_000)
        registration = RegistrationResultSet(RegistrationSettings(), {
            1: RegistrationFrameResult(1, (-2., 3.), "manual"),
        })
        first = provider.get_frame(0, aligned=True, expanded=True, registration=registration)
        self.assertEqual(first.values.shape, (35, 50))
        self.assertEqual(first.values[0, 2], 17.123456789)
        registration.results_by_frame[1] = RegistrationFrameResult(1, (-7., 5.), "manual")
        changed = provider.get_frame(0, aligned=True, expanded=True, registration=registration)
        self.assertEqual(changed.values.shape, (37, 55))
        self.assertTrue(np.isnan(changed.values[0, 2]))
        self.assertEqual(changed.values[0, 7], 17.123456789)
        np.testing.assert_array_equal(changed.geometry.source_to_display([0., 0.]), [7., 0.])
        tracemalloc.start()
        try:
            for index in range(40):
                frame = provider.get_frame(index, aligned=True, expanded=True, registration=registration)
                self.assertEqual(frame.values.shape, (37, 55))
            self.assertLess(tracemalloc.get_traced_memory()[1], 1_000_000)
        finally:
            tracemalloc.stop()
        processed = ScalarFrameProvider(np.broadcast_to(np.full((1, 32, 48), 117.123456789), frames.shape),
                                        metadata, source_revision="processed-S1")
        frame = processed.get_frame(0, aligned=True, expanded=True, registration=registration)
        self.assertEqual(frame.values[0, 7], 117.123456789)
        self.assertEqual(frame.source_revision, "processed-S1")


if __name__ == "__main__":
    unittest.main()
