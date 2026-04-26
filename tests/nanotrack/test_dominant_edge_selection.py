import unittest

import numpy as np

from nanotrack.edges.selection import rank_edge_component_candidates, select_dominant_edge


class DominantEdgeSelectionTests(unittest.TestCase):
    def test_selects_component_with_highest_probability_sum(self) -> None:
        polygon_mask = np.ones((8, 10), dtype=bool)
        edge_prob = np.zeros((8, 10), dtype=np.float32)
        edge_prob[1, 1:7] = 0.55  # sum 3.3
        edge_prob[4, 0:9] = 0.8   # sum 7.2

        selection = select_dominant_edge(edge_prob, polygon_mask, threshold=0.5)

        self.assertEqual(selection.selection_mode, "component")
        self.assertEqual(selection.pixel_count, 9)
        self.assertAlmostEqual(selection.score, 7.2, places=4)
        self.assertAlmostEqual(selection.mean_probability, 0.8, places=4)
        self.assertEqual(len(selection.candidates), 2)
        self.assertIs(selection.selected_candidates[0], selection.candidates[0])
        self.assertGreater(selection.quality_score, 0.0)
        expected_mask = np.zeros_like(polygon_mask, dtype=bool)
        expected_mask[4, 0:9] = True
        np.testing.assert_array_equal(selection.edge_mask, expected_mask)

    def test_scores_thin_continuous_candidate_above_larger_blob(self) -> None:
        polygon_mask = np.ones((12, 14), dtype=bool)
        edge_prob = np.zeros((12, 14), dtype=np.float32)
        edge_prob[2, 1:11] = 0.55       # thin continuous edge, sum 5.5
        edge_prob[6:11, 7:12] = 0.65    # larger blob, sum 16.25

        selection = select_dominant_edge(edge_prob, polygon_mask, threshold=0.5)

        self.assertEqual(selection.selection_mode, "component")
        expected_mask = np.zeros_like(polygon_mask, dtype=bool)
        expected_mask[2, 1:11] = True
        np.testing.assert_array_equal(selection.edge_mask, expected_mask)
        self.assertEqual(len(selection.candidates), 2)
        self.assertLess(selection.candidates[0].sum_probability, selection.candidates[1].sum_probability)
        self.assertGreater(selection.candidates[0].skeleton_length_px, selection.candidates[1].skeleton_length_px)
        self.assertLess(selection.candidates[0].thickness_penalty, selection.candidates[1].thickness_penalty)
        self.assertIn("thickness_penalty", selection.candidates[0].reason)

    def test_returns_ranked_component_candidates_with_quality_metadata(self) -> None:
        polygon_mask = np.ones((9, 12), dtype=bool)
        edge_prob = np.zeros((9, 12), dtype=np.float32)
        edge_prob[1, 1:8] = 0.7
        edge_prob[4:7, 8:11] = 0.62

        candidates = rank_edge_component_candidates(edge_prob, polygon_mask, threshold=0.5)

        self.assertEqual(len(candidates), 2)
        self.assertGreaterEqual(candidates[0].score, candidates[1].score)
        self.assertEqual(candidates[0].bbox, (1, 1, 2, 8))
        self.assertEqual(candidates[0].pixel_count, 7)
        self.assertAlmostEqual(candidates[0].mean_probability, 0.7, places=5)
        self.assertAlmostEqual(candidates[0].median_probability, 0.7, places=5)
        self.assertGreater(candidates[0].skeleton_length_px, 0.0)
        self.assertEqual(candidates[0].branch_count, 0)
        self.assertGreater(candidates[0].continuity_score, 0.0)

    def test_prior_overlap_can_promote_temporally_consistent_candidate(self) -> None:
        polygon_mask = np.ones((8, 12), dtype=bool)
        edge_prob = np.zeros((8, 12), dtype=np.float32)
        edge_prob[2, 1:7] = 0.7
        edge_prob[5, 4:10] = 0.68
        prior_mask = np.zeros_like(polygon_mask, dtype=bool)
        prior_mask[5, 4:10] = True

        selection_without_prior = select_dominant_edge(edge_prob, polygon_mask, threshold=0.5)
        selection_with_prior = select_dominant_edge(edge_prob, polygon_mask, threshold=0.5, prior_mask=prior_mask)

        expected_without_prior = np.zeros_like(polygon_mask, dtype=bool)
        expected_without_prior[2, 1:7] = True
        expected_with_prior = np.zeros_like(polygon_mask, dtype=bool)
        expected_with_prior[5, 4:10] = True
        np.testing.assert_array_equal(selection_without_prior.edge_mask, expected_without_prior)
        np.testing.assert_array_equal(selection_with_prior.edge_mask, expected_with_prior)
        self.assertAlmostEqual(selection_with_prior.selected_candidates[0].prior_overlap, 1.0, places=6)

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
        self.assertEqual(selection.candidates, ())
        expected_mask = np.zeros_like(polygon_mask, dtype=bool)
        expected_mask[3, 4] = True
        np.testing.assert_array_equal(selection.edge_mask, expected_mask)

    def test_can_merge_top_k_components_before_polyline_extraction(self) -> None:
        polygon_mask = np.ones((8, 12), dtype=bool)
        edge_prob = np.zeros((8, 12), dtype=np.float32)
        edge_prob[1:3, 1:4] = 0.7
        edge_prob[4:6, 7:10] = 0.65
        edge_prob[6:8, 0:2] = 0.2

        selection = select_dominant_edge(edge_prob, polygon_mask, threshold=0.5, max_components=2)

        self.assertEqual(selection.selection_mode, "top_2_components")
        self.assertEqual(selection.pixel_count, 12)
        self.assertEqual(len(selection.candidates), 2)
        self.assertEqual(len(selection.selected_candidates), 2)
        expected_mask = np.zeros_like(polygon_mask, dtype=bool)
        expected_mask[1:3, 1:4] = True
        expected_mask[4:6, 7:10] = True
        np.testing.assert_array_equal(selection.edge_mask, expected_mask)

    def test_validates_shape_mismatch(self) -> None:
        with self.assertRaises(ValueError):
            select_dominant_edge(
                np.zeros((4, 5), dtype=np.float32),
                np.zeros((5, 4), dtype=bool),
            )

    def test_validates_prior_shape_mismatch(self) -> None:
        with self.assertRaises(ValueError):
            select_dominant_edge(
                np.zeros((4, 5), dtype=np.float32),
                np.ones((4, 5), dtype=bool),
                prior_mask=np.ones((5, 4), dtype=bool),
            )


if __name__ == "__main__":
    unittest.main()
