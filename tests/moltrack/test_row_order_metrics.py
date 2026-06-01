import unittest


class MolTrackRowOrderMetricsTests(unittest.TestCase):
    def test_row_order_metrics_score_perfect_parallel_rows_as_ordered(self) -> None:
        """First-pass row order is locked for clean, straight centroid rows."""
        from moltrack.core import (
            AnalysisRegion,
            DetectionReviewStatus,
            MolTrackProject,
            MolecularDetection,
            MolecularRowOrderMetrics,
            SourceImageSeries,
        )

        source = SourceImageSeries(source_uri="C:/data/ordered_rows.stp", frame_count=1)
        terrace = AnalysisRegion.rectangle(
            kind="terrace",
            name="Terrace A",
            color_rgb=(20, 120, 240),
            rect_xyxy=(0.0, 0.0, 64.0, 64.0),
        )
        detections = tuple(
            MolecularDetection(
                detection_id=f"ordered-{index}",
                working_frame_index=0,
                source_frame_index=0,
                bbox_xyxy=(x - 0.5, y - 0.5, x + 0.5, y + 0.5),
                confidence=1.0,
                model_name="manual",
                review_status=DetectionReviewStatus.ACCEPTED,
                backend_name="manual",
                run_mode="full_frame",
                region_name="Terrace A",
            )
            for index, (x, y) in enumerate(
                (
                    (10.0, 10.0),
                    (20.0, 10.0),
                    (30.0, 10.0),
                    (10.0, 20.0),
                    (20.0, 20.0),
                    (30.0, 20.0),
                )
            )
        )
        project = MolTrackProject.from_source_series(source).with_analysis_regions(
            (terrace,),
            molecular_detections=detections,
        )

        metrics = MolecularRowOrderMetrics.from_project(project)

        self.assertEqual(len(metrics.rows), 1)
        row = metrics.rows[0]
        self.assertEqual(row.working_frame_index, 0)
        self.assertEqual(row.source_frame_index, 0)
        self.assertEqual(row.region_name, "Terrace A")
        self.assertEqual(row.detection_count, 6)
        self.assertEqual(row.assigned_detection_count, 6)
        self.assertEqual(row.row_count, 2)
        self.assertAlmostEqual(row.orientation_degrees, 0.0)
        self.assertAlmostEqual(row.row_spacing_px, 10.0)
        self.assertAlmostEqual(row.row_order_score, 1.0)


if __name__ == "__main__":
    unittest.main()
