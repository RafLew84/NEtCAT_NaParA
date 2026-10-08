"""Scientific frame requests, independent of rendering or registration estimation."""
import unittest
import tracemalloc

import numpy as np

from nanotrack.core import RegistrationFrameResult, RegistrationResultSet, RegistrationSettings, STMSequenceMetadata
from nanotrack.registration.scalar_frames import ScalarFrameProvider


class ScalarFrameTests(unittest.TestCase):
    def test_integer_alignment_preserves_float64_samples_and_marks_empty_border(self):
        frames = np.array([[[17.123456789, 2., 3.], [4., 5., 6.], [7., 8., 9.]]])
        metadata = STMSequenceMetadata(pixels_x=3, pixels_y=3, size_nm_x=6, size_nm_y=3)
        registration = RegistrationResultSet(RegistrationSettings(), {
            0: RegistrationFrameResult(0, (1., -1.), "manual"),
        })
        provider = ScalarFrameProvider(frames, metadata)

        aligned = provider.get_frame(0, aligned=True, registration=registration)

        np.testing.assert_array_equal(aligned.values, [[np.nan, 4., 5.], [np.nan, 7., 8.], [np.nan]*3])
        np.testing.assert_array_equal(aligned.valid_mask, [[False, True, True], [False, True, True], [False]*3])
        self.assertEqual(aligned.values.dtype, np.float64)
        self.assertEqual(aligned.metadata.get_pixel_size_nm(), (2., 1.))
        original = provider.get_frame(0)
        self.assertEqual(original.values[0, 0], 17.123456789)
        self.assertEqual(frames[0, 0, 0], 17.123456789)

    def test_subpixel_alignment_requires_only_neighbors_with_nonzero_weight(self):
        frames = np.array([[[10., 20., 30.], [40., np.nan, 60.], [70., 80., 90.]]])
        provider = ScalarFrameProvider(frames, STMSequenceMetadata(pixels_x=3, pixels_y=3))
        registration = RegistrationResultSet(RegistrationSettings(), {
            0: RegistrationFrameResult(0, (-.5, .5), "manual"),
        })
        frame = provider.get_frame(0, aligned=True, registration=registration)
        np.testing.assert_array_equal(frame.values, np.full((3, 3), np.nan))
        # Only the x-neighbors contribute: NaN in the next row must not contaminate row 0.
        registration.results_by_frame[0] = RegistrationFrameResult(0, (.5, 0.), "manual")
        frame = provider.get_frame(0, aligned=True, registration=registration)
        np.testing.assert_array_equal(frame.values, [[np.nan, 15., 25.], [np.nan]*3, [np.nan, 75., 85.]])
        np.testing.assert_array_equal(frame.valid_mask, [[False, True, True], [False]*3, [False, True, True]])

    def test_geometry_and_missing_shift_have_distinct_meaning(self):
        frames = np.ones((3, 4, 5)) * 17.123456789
        provider = ScalarFrameProvider(frames, STMSequenceMetadata(pixels_x=5, pixels_y=4))
        registration = RegistrationResultSet(RegistrationSettings(), {
            0: RegistrationFrameResult(0, (-1.25, .5), "manual", status="low_confidence"),
            1: RegistrationFrameResult(1, (-1.25, .5), "excluded_frame", status="manual_review"),
        })
        frame = provider.get_frame(0, aligned=True, registration=registration)
        np.testing.assert_array_equal(frame.geometry.source_to_display([[2., 1.], [4., 2.]]), [[.75, 1.5], [2.75, 2.5]])
        np.testing.assert_array_equal(frame.geometry.display_to_source([.75, 1.5]), [2., 1.])
        self.assertEqual(frame.registration_status, "low_confidence")
        for index in (1, 2):
            frame = provider.get_frame(index, aligned=True, registration=registration)
            self.assertEqual(frame.registration_status, "missing")
            np.testing.assert_array_equal(frame.geometry.source_to_display([2., 1.]), [2., 1.])
            np.testing.assert_array_equal(frame.values, frames[index])
        registration.results_by_frame[2] = RegistrationFrameResult(2, (0., 0.), "manual")
        self.assertEqual(provider.get_frame(2, aligned=True, registration=registration).registration_status, "ok")

    def test_requesting_a_long_movie_has_bounded_memory_and_honors_changed_shifts(self):
        # A 196 MiB virtual source; allocating the whole aligned stack fails this budget.
        frames = np.broadcast_to(np.arange(128*128, dtype=np.float64).reshape(1, 128, 128), (1500, 128, 128))
        metadata = STMSequenceMetadata(pixels_x=128, pixels_y=128)
        registration = RegistrationResultSet(RegistrationSettings(), {0: RegistrationFrameResult(0, (1., 0.), "manual")})
        tracemalloc.start()
        try:
            provider = ScalarFrameProvider(frames, metadata, source_revision="S1-original", max_cache_bytes=300_000)
            for index in range(40):
                frame = provider.get_frame(index, aligned=True, registration=registration)
            self.assertLess(tracemalloc.get_traced_memory()[1], 3_000_000)
        finally:
            tracemalloc.stop()
        frame = provider.get_frame(0, aligned=True, registration=registration)
        self.assertEqual(frame.values[0, 2], 1.)
        self.assertEqual(frame.source_revision, "S1-original")
        registration.results_by_frame[0] = RegistrationFrameResult(0, (-1., 0.), "manual")
        self.assertEqual(provider.get_frame(0, aligned=True, registration=registration).values[0, 2], 3.)
        self.assertEqual(provider.get_frame(0).values[0, 2], 2.)
        with self.assertRaises(ValueError):
            frame.values[0, 2] = 100.  # A reader must not corrupt cached scientific data.

    def test_rejects_invalid_geometry_or_unbounded_frame_requests_before_allocation(self):
        metadata = STMSequenceMetadata(pixels_x=3, pixels_y=2)
        frames = np.ones((1, 2, 3))
        provider = ScalarFrameProvider(frames, metadata)
        with self.assertRaises(IndexError):
            provider.get_frame(-1)
        with self.assertRaises(ValueError):
            ScalarFrameProvider(np.ones((1, 3, 3)), metadata)
        with self.assertRaises(ValueError):
            ScalarFrameProvider(frames.astype(complex), metadata)
        huge = np.broadcast_to(np.ones((1, 1, 1)), (1, 100_000, 100_000))
        with self.assertRaises(MemoryError):
            ScalarFrameProvider(huge, STMSequenceMetadata(pixels_x=100_000, pixels_y=100_000)).get_frame(0)


if __name__ == "__main__":
    unittest.main()
