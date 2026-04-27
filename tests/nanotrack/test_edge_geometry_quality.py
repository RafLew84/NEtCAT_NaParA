import unittest

import numpy as np

from nanotrack.edges import assess_edge_geometry_quality, format_edge_geometry_review
from nanotrack.edges.polyline import EdgePolylineExtraction
from nanotrack.edges.refinement import EdgeRefinementResult
from nanotrack.edges.selection import DominantEdgeSelection


class EdgeGeometryQualityTests(unittest.TestCase):
    def test_reports_ok_quality_for_stable_geometry(self) -> None:
        selection = DominantEdgeSelection(
            edge_mask=np.ones((4, 8), dtype=bool),
            score=12.0,
            pixel_count=32,
            mean_probability=0.82,
            selection_mode="geometry_component",
            quality_score=12.0,
        )
        coarse = EdgePolylineExtraction(
            polyline_xy=np.asarray([[1.0, 2.0], [12.0, 2.0]], dtype=np.float64),
            point_count=2,
            axis_length_px=11.0,
            extraction_mode="graph_path",
        )
        refined = EdgeRefinementResult(
            polyline_xy=np.asarray([[1.0, 2.1], [12.0, 2.1]], dtype=np.float64),
            point_count=2,
            score_mode="combined",
            search_radius_px=4,
            mean_score=0.78,
            mean_shift_px=0.4,
            refinement_mode="normal_dp_combined",
            shift_std_px=0.05,
            max_shift_px=0.6,
            stability_score=0.92,
        )

        quality = assess_edge_geometry_quality(
            selection,
            coarse,
            refined,
            polyline_method="graph",
            method_explicit=True,
        )

        self.assertEqual(quality.review_status, "ok")
        self.assertEqual(quality.warnings, ())
        self.assertEqual(quality.polyline_method, "graph")
        self.assertEqual(quality.extraction_mode, "graph_path")
        self.assertGreater(quality.confidence, 0.70)
        self.assertIn("geom graph->graph_path", format_edge_geometry_review(quality))

    def test_flags_low_confidence_geometry_for_review(self) -> None:
        selection = DominantEdgeSelection(
            edge_mask=np.eye(3, dtype=bool),
            score=0.1,
            pixel_count=3,
            mean_probability=0.1,
            selection_mode="peak",
            quality_score=0.1,
        )
        coarse = EdgePolylineExtraction(
            polyline_xy=np.asarray([[1.0, 1.0], [2.0, 2.0]], dtype=np.float64),
            point_count=2,
            axis_length_px=0.0,
            extraction_mode="endpoints",
        )
        refined = EdgeRefinementResult(
            polyline_xy=np.asarray([[1.0, 1.0], [2.0, 2.0]], dtype=np.float64),
            point_count=2,
            score_mode="edge_prob",
            search_radius_px=4,
            mean_score=0.1,
            mean_shift_px=3.5,
            refinement_mode="normal_dp_edge_prob",
            shift_std_px=2.5,
            max_shift_px=4.0,
            stability_score=0.2,
        )

        quality = assess_edge_geometry_quality(
            selection,
            coarse,
            refined,
            polyline_method="pca_bins",
            method_explicit=True,
        )

        self.assertEqual(quality.review_status, "needs_review")
        self.assertIn("degenerate_coarse_geometry", quality.warnings)
        self.assertIn("unstable_refinement", quality.warnings)
        self.assertIn("low_confidence", quality.warnings)
        self.assertLess(quality.confidence, 0.45)


if __name__ == "__main__":
    unittest.main()
