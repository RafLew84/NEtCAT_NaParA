import unittest

import numpy as np

from nanotrack.edges import hybrid_refine_polyline, resample_polyline_xy, sample_polyline_control_points


class EdgeHybridTests(unittest.TestCase):
    def test_resample_polyline_returns_requested_point_count_and_endpoints(self) -> None:
        polyline = np.asarray([[0.0, 0.0], [4.0, 0.0], [8.0, 4.0]], dtype=np.float64)

        resampled = resample_polyline_xy(polyline, 5)

        self.assertEqual(resampled.shape, (5, 2))
        np.testing.assert_allclose(resampled[0], polyline[0])
        np.testing.assert_allclose(resampled[-1], polyline[-1])

    def test_sample_polyline_control_points_aliases_resampling(self) -> None:
        polyline = np.asarray([[1.0, 2.0], [5.0, 2.0]], dtype=np.float64)

        control_points = sample_polyline_control_points(polyline, 4)

        self.assertEqual(control_points.shape, (4, 2))
        np.testing.assert_allclose(control_points[:, 1], np.full(4, 2.0))

    def test_hybrid_refine_polyline_blends_tracked_points_with_reference(self) -> None:
        reference = np.asarray([[0.0, 0.0], [5.0, 0.0], [10.0, 0.0]], dtype=np.float64)
        tracked = np.asarray([[0.0, 1.0], [5.0, 1.0], [10.0, 1.0]], dtype=np.float64)

        refined = hybrid_refine_polyline(reference, tracked, tracker_blend=0.5)

        self.assertEqual(refined.shape, tracked.shape)
        np.testing.assert_allclose(refined[:, 0], tracked[:, 0])
        np.testing.assert_allclose(refined[:, 1], np.full(3, 0.5))

    def test_hybrid_refine_polyline_matches_direction_before_blending(self) -> None:
        reference = np.asarray([[0.0, 0.0], [5.0, 0.0], [10.0, 0.0]], dtype=np.float64)
        tracked_reversed = np.asarray([[10.0, 2.0], [5.0, 2.0], [0.0, 2.0]], dtype=np.float64)

        refined = hybrid_refine_polyline(reference, tracked_reversed, tracker_blend=1.0)

        np.testing.assert_allclose(refined[:, 0], np.asarray([0.0, 5.0, 10.0], dtype=np.float64))
        np.testing.assert_allclose(refined[:, 1], np.full(3, 2.0))
