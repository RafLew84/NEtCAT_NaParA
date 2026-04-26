import unittest

import numpy as np

from nanotrack.edges.polyline import (
    dominant_edge_to_polyline,
    rank_edge_polyline_candidates,
    select_best_edge_polyline_candidate,
)
from nanotrack.edges.selection import EdgeComponentCandidate


class EdgePolylineExtractionTests(unittest.TestCase):
    def _candidate(
        self,
        mask: np.ndarray,
        *,
        label_id: int,
        score: float,
        probability: float,
    ) -> EdgeComponentCandidate:
        return EdgeComponentCandidate(
            edge_mask=mask,
            label_id=label_id,
            score=score,
            sum_probability=float(np.count_nonzero(mask) * probability),
            mean_probability=probability,
            median_probability=probability,
            pixel_count=int(np.count_nonzero(mask)),
            skeleton_length_px=float(np.count_nonzero(mask)),
            branch_count=0,
            bbox=(
                int(np.nonzero(mask)[0].min()),
                int(np.nonzero(mask)[1].min()),
                int(np.nonzero(mask)[0].max()) + 1,
                int(np.nonzero(mask)[1].max()) + 1,
            ),
            continuity_score=1.0,
            thickness_penalty=0.0,
            fragmentation_penalty=0.0,
            prior_overlap=0.0,
            reason="test",
        )

    def test_extracts_centerline_for_horizontal_band(self) -> None:
        edge_mask = np.zeros((20, 30), dtype=bool)
        edge_mask[8:11, 5:24] = True
        edge_prob = np.zeros_like(edge_mask, dtype=np.float32)
        edge_prob[edge_mask] = 0.8

        extraction = dominant_edge_to_polyline(edge_mask, edge_prob=edge_prob)

        self.assertEqual(extraction.extraction_mode, "graph_path")
        self.assertGreaterEqual(extraction.point_count, 3)
        self.assertTrue(np.all(np.diff(extraction.polyline_xy[:, 0]) >= -1e-6))
        mean_y = float(np.mean(extraction.polyline_xy[:, 1]))
        self.assertGreater(mean_y, 8.0)
        self.assertLess(mean_y, 10.5)

    def test_can_force_previous_pca_binning_extractor(self) -> None:
        edge_mask = np.zeros((20, 30), dtype=bool)
        edge_mask[8:11, 5:24] = True
        edge_prob = np.zeros_like(edge_mask, dtype=np.float32)
        edge_prob[edge_mask] = 0.8

        extraction = dominant_edge_to_polyline(edge_mask, edge_prob=edge_prob, method="pca_bins")

        self.assertEqual(extraction.extraction_mode, "binned_pca")
        self.assertGreaterEqual(extraction.point_count, 3)

    def test_graph_path_follows_bent_edge_geometry(self) -> None:
        edge_mask = np.zeros((24, 24), dtype=bool)
        edge_mask[5, 4:17] = True
        edge_mask[5:18, 16] = True
        edge_prob = np.zeros_like(edge_mask, dtype=np.float32)
        edge_prob[edge_mask] = 0.85

        extraction = dominant_edge_to_polyline(edge_mask, edge_prob=edge_prob, max_points=32)

        self.assertEqual(extraction.extraction_mode, "graph_path")
        self.assertGreater(extraction.axis_length_px, 20.0)
        self.assertLess(np.min(np.linalg.norm(extraction.polyline_xy - np.asarray([16.0, 5.0]), axis=1)), 1.5)
        self.assertGreater(float(np.max(extraction.polyline_xy[:, 0])), 15.0)
        self.assertGreater(float(np.max(extraction.polyline_xy[:, 1])), 16.0)

    def test_selects_component_with_best_polyline_geometry_from_top_candidates(self) -> None:
        edge_prob = np.zeros((20, 30), dtype=np.float32)
        short_mask = np.zeros_like(edge_prob, dtype=bool)
        short_mask[14, 2:5] = True
        edge_prob[short_mask] = 0.95
        long_mask = np.zeros_like(edge_prob, dtype=bool)
        long_mask[5, 2:22] = True
        edge_prob[long_mask] = 0.62

        short_candidate = self._candidate(short_mask, label_id=1, score=14.0, probability=0.95)
        long_candidate = self._candidate(long_mask, label_id=2, score=8.0, probability=0.62)

        selected = select_best_edge_polyline_candidate(
            edge_prob,
            [short_candidate, long_candidate],
            candidate_limit=2,
            include_merged=False,
        )

        self.assertIs(selected.components[0], long_candidate)
        self.assertEqual(selected.selection_mode, "geometry_component")
        self.assertGreater(selected.polyline_length_px, 15.0)
        self.assertGreater(selected.geometry_score, 0.0)

    def test_can_rank_merged_top_k_component_geometry(self) -> None:
        edge_prob = np.zeros((16, 24), dtype=np.float32)
        left_mask = np.zeros_like(edge_prob, dtype=bool)
        left_mask[7, 2:8] = True
        right_mask = np.zeros_like(edge_prob, dtype=bool)
        right_mask[7, 10:16] = True
        edge_prob[left_mask | right_mask] = 0.7

        left_candidate = self._candidate(left_mask, label_id=1, score=6.0, probability=0.7)
        right_candidate = self._candidate(right_mask, label_id=2, score=5.8, probability=0.7)

        ranked = rank_edge_polyline_candidates(edge_prob, [left_candidate, right_candidate], candidate_limit=2)

        self.assertEqual(ranked[0].selection_mode, "geometry_top_2_components")
        self.assertEqual(len(ranked[0].components), 2)
        np.testing.assert_array_equal(ranked[0].edge_mask, left_mask | right_mask)
        self.assertGreater(ranked[0].polyline_length_px, ranked[1].polyline_length_px)

    def test_candidate_ranking_can_use_pca_binning_method(self) -> None:
        edge_prob = np.zeros((20, 30), dtype=np.float32)
        edge_mask = np.zeros_like(edge_prob, dtype=bool)
        edge_mask[8:11, 5:24] = True
        edge_prob[edge_mask] = 0.8
        candidate = self._candidate(edge_mask, label_id=1, score=8.0, probability=0.8)

        selected = select_best_edge_polyline_candidate(
            edge_prob,
            [candidate],
            polyline_method="pca_bins",
        )

        self.assertEqual(selected.extraction.extraction_mode, "binned_pca")

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
