import unittest

import numpy as np

from nanotrack.edges.polyline import dominant_edge_to_polyline


class EdgePolylineExtractionTests(unittest.TestCase):
    def test_extracts_centerline_for_horizontal_band(self) -> None:
        edge_mask = np.zeros((20, 30), dtype=bool)
        edge_mask[8:11, 5:24] = True
        edge_prob = np.zeros_like(edge_mask, dtype=np.float32)
        edge_prob[edge_mask] = 0.8

        extraction = dominant_edge_to_polyline(edge_mask, edge_prob=edge_prob)

        self.assertEqual(extraction.extraction_mode, "binned_pca")
        self.assertGreaterEqual(extraction.point_count, 3)
        self.assertTrue(np.all(np.diff(extraction.polyline_xy[:, 0]) >= -1e-6))
        mean_y = float(np.mean(extraction.polyline_xy[:, 1]))
        self.assertGreater(mean_y, 8.0)
        self.assertLess(mean_y, 10.5)

    def test_extracts_ordered_polyline_for_diagonal_edge(self) -> None:
        edge_mask = np.zeros((24, 24), dtype=bool)
        for offset in range(4, 18):
            edge_mask[offset, offset] = True
            edge_mask[offset, offset + 1] = True
        edge_prob = np.zeros_like(edge_mask, dtype=np.float32)
        edge_prob[edge_mask] = 0.9

        extraction = dominant_edge_to_polyline(edge_mask, edge_prob=edge_prob, max_points=12)

        self.assertGreaterEqual(extraction.point_count, 4)
        self.assertTrue(np.all(np.diff(extraction.polyline_xy[:, 0]) >= -1e-6))
        self.assertTrue(np.all(np.diff(extraction.polyline_xy[:, 1]) >= -1e-6))
        self.assertGreater(extraction.axis_length_px, 10.0)

    def test_falls_back_to_endpoints_for_tiny_component(self) -> None:
        edge_mask = np.zeros((8, 8), dtype=bool)
        edge_mask[2, 2] = True
        edge_mask[3, 3] = True

        extraction = dominant_edge_to_polyline(edge_mask)

        self.assertEqual(extraction.point_count, 2)
        self.assertGreaterEqual(extraction.axis_length_px, 0.0)
        np.testing.assert_array_equal(extraction.polyline_xy, np.asarray([[2.0, 2.0], [3.0, 3.0]]))

    def test_validates_shape_mismatch(self) -> None:
        with self.assertRaises(ValueError):
            dominant_edge_to_polyline(
                np.ones((5, 5), dtype=bool),
                edge_prob=np.ones((4, 5), dtype=np.float32),
            )


if __name__ == "__main__":
    unittest.main()
