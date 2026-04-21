import unittest

import numpy as np

from nanotrack.edges.selection import select_dominant_edge


class DominantEdgeSelectionTests(unittest.TestCase):
    def test_selects_component_with_highest_probability_sum(self) -> None:
        polygon_mask = np.ones((8, 10), dtype=bool)
        edge_prob = np.zeros((8, 10), dtype=np.float32)
        edge_prob[1:3, 1:5] = 0.55  # sum 4.4
        edge_prob[4:7, 6:9] = 0.8   # sum 7.2

        selection = select_dominant_edge(edge_prob, polygon_mask, threshold=0.5)

        self.assertEqual(selection.selection_mode, "component")
        self.assertEqual(selection.pixel_count, 9)
        self.assertAlmostEqual(selection.score, 7.2, places=4)
        self.assertAlmostEqual(selection.mean_probability, 0.8, places=4)
        expected_mask = np.zeros_like(polygon_mask, dtype=bool)
        expected_mask[4:7, 6:9] = True
        np.testing.assert_array_equal(selection.edge_mask, expected_mask)

    def test_falls_back_to_single_peak_when_thresholded_components_are_empty(self) -> None:
        polygon_mask = np.zeros((6, 7), dtype=bool)
        polygon_mask[1:5, 1:6] = True
        edge_prob = np.zeros((6, 7), dtype=np.float32)
        edge_prob[3, 4] = 0.42
        edge_prob[2, 2] = 0.37

        selection = select_dominant_edge(edge_prob, polygon_mask, threshold=0.5)

        self.assertEqual(selection.selection_mode, "peak")
        self.assertEqual(selection.pixel_count, 1)
        self.assertAlmostEqual(selection.score, 0.42, places=6)
        expected_mask = np.zeros_like(polygon_mask, dtype=bool)
        expected_mask[3, 4] = True
        np.testing.assert_array_equal(selection.edge_mask, expected_mask)

    def test_validates_shape_mismatch(self) -> None:
        with self.assertRaises(ValueError):
            select_dominant_edge(
                np.zeros((4, 5), dtype=np.float32),
                np.zeros((5, 4), dtype=bool),
            )


if __name__ == "__main__":
    unittest.main()
