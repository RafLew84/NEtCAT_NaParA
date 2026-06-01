import unittest


class MolTrackRowOrientationMetricsTests(unittest.TestCase):
    def test_row_orientation_metrics_estimate_diagonal_orientation_from_centroids(self) -> None:
        from moltrack.core import (
            AnalysisRegion,
            DetectionReviewStatus,
            MolTrackProject,
            MolecularDetection,
            MolecularRowOrientationMetrics,
            SourceImageSeries,
        )

        source = SourceImageSeries(source_uri="C:/data/diagonal_rows.stp", frame_count=1)
        terrace = AnalysisRegion.rectangle(
            kind="terrace",
            name="Terrace A",
            color_rgb=(20, 120, 240),
            rect_xyxy=(0.0, 0.0, 64.0, 64.0),
        )
        detections = tuple(
            MolecularDetection(
                detection_id=f"diag-{index}",
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
                    (8.0, 8.0),
                    (18.0, 18.0),
                    (28.0, 28.0),
                    (38.0, 38.0),
                )
            )
        )
        project = MolTrackProject.from_source_series(source).with_analysis_regions(
            (terrace,),
            molecular_detections=detections,
        )

        metrics = MolecularRowOrientationMetrics.from_project(project)

        self.assertEqual(len(metrics.rows), 1)
        row = metrics.rows[0]
        self.assertEqual(row.working_frame_index, 0)
        self.assertEqual(row.source_frame_index, 0)
        self.assertEqual(row.region_name, "Terrace A")
        self.assertEqual(row.detection_count, 4)
        self.assertAlmostEqual(row.orientation_degrees, 45.0)
        self.assertAlmostEqual(row.orientation_confidence, 1.0)


if __name__ == "__main__":
    unittest.main()
