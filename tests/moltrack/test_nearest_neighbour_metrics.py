import unittest


class MolTrackNearestNeighbourMetricsTests(unittest.TestCase):
    def test_centroid_nearest_neighbour_metrics_measure_synthetic_grid_spacing(self) -> None:
        from moltrack.core import (
            AnalysisRegion,
            CentroidNearestNeighbourMetrics,
            DetectionReviewStatus,
            MolTrackProject,
            MolecularDetection,
            SourceImageSeries,
        )

        source = SourceImageSeries(source_uri="C:/data/grid.stp", frame_count=1)
        terrace = AnalysisRegion.rectangle(
            kind="terrace",
            name="Terrace A",
            color_rgb=(20, 120, 240),
            rect_xyxy=(0.0, 0.0, 32.0, 32.0),
        )
        detections = tuple(
            MolecularDetection(
                detection_id=f"grid-{index}",
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
                    (10.0, 20.0),
                    (20.0, 20.0),
                )
            )
        )
        project = MolTrackProject.from_source_series(source).with_analysis_regions(
            (terrace,),
            molecular_detections=detections,
        )

        metrics = CentroidNearestNeighbourMetrics.from_project(project)

        self.assertEqual(len(metrics.rows), 1)
        row = metrics.rows[0]
        self.assertEqual(row.working_frame_index, 0)
        self.assertEqual(row.source_frame_index, 0)
        self.assertEqual(row.region_name, "Terrace A")
        self.assertEqual(row.detection_count, 4)
        self.assertEqual(row.nearest_neighbour_count, 4)
        self.assertEqual(row.nearest_neighbour_distances_px, (10.0, 10.0, 10.0, 10.0))
        self.assertEqual(row.mean_nearest_neighbour_distance_px, 10.0)
        self.assertEqual(row.median_nearest_neighbour_distance_px, 10.0)


if __name__ == "__main__":
    unittest.main()
