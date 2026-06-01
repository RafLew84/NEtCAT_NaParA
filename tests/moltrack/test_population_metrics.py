import unittest


class MolTrackPopulationMetricsTests(unittest.TestCase):
    def test_population_metrics_count_density_and_coverage_per_frame_region_with_default_filter(self) -> None:
        from moltrack.core import (
            AnalysisRegion,
            DetectionReviewStatus,
            MolTrackProject,
            MolecularDetection,
            PopulationMetrics,
            SourceImageSeries,
        )

        source = SourceImageSeries(source_uri="C:/data/movie.mpp", frame_count=1)
        terrace = AnalysisRegion.rectangle(
            kind="terrace",
            name="Terrace A",
            color_rgb=(20, 120, 240),
            rect_xyxy=(0.0, 0.0, 10.0, 5.0),
        )
        ignore = AnalysisRegion.rectangle(
            kind="ignore",
            name="Ignore artifact",
            color_rgb=(220, 30, 30),
            rect_xyxy=(0.0, 0.0, 2.0, 2.0),
        )
        accepted = MolecularDetection(
            detection_id="accepted",
            working_frame_index=0,
            source_frame_index=0,
            bbox_xyxy=(2.0, 1.0, 4.0, 3.0),
            confidence=0.9,
            model_name="manual",
            review_status=DetectionReviewStatus.ACCEPTED,
            backend_name="manual",
            run_mode="full_frame",
            region_name="Terrace A",
        )
        manual = MolecularDetection(
            detection_id="manual",
            working_frame_index=0,
            source_frame_index=0,
            bbox_xyxy=(5.0, 1.0, 7.0, 2.0),
            confidence=1.0,
            model_name="manual",
            review_status=DetectionReviewStatus.MANUAL,
            backend_name="manual",
            run_mode="full_frame",
            region_name="Terrace A",
        )
        edited = MolecularDetection(
            detection_id="edited",
            working_frame_index=0,
            source_frame_index=0,
            bbox_xyxy=(8.0, 1.0, 9.0, 2.0),
            confidence=0.95,
            model_name="manual",
            review_status=DetectionReviewStatus.EDITED,
            backend_name="manual",
            run_mode="full_frame",
            region_name="Terrace A",
        )
        candidate = MolecularDetection(
            detection_id="candidate",
            working_frame_index=0,
            source_frame_index=0,
            bbox_xyxy=(7.0, 1.0, 9.0, 2.0),
            confidence=0.8,
            model_name="yolo",
            review_status=DetectionReviewStatus.CANDIDATE,
            backend_name="yolo",
            run_mode="full_frame",
            region_name="Terrace A",
        )
        ignored = MolecularDetection(
            detection_id="ignored",
            working_frame_index=0,
            source_frame_index=0,
            bbox_xyxy=(0.25, 0.25, 1.25, 1.25),
            confidence=0.9,
            model_name="manual",
            review_status=DetectionReviewStatus.ACCEPTED,
            backend_name="manual",
            run_mode="full_frame",
            region_name="Ignore artifact",
        )
        project = MolTrackProject.from_source_series(source).with_analysis_regions(
            (terrace, ignore),
            molecular_detections=(accepted, manual, edited, candidate, ignored),
        )

        metrics = PopulationMetrics.from_project(project)

        self.assertEqual(len(metrics.rows), 1)
        row = metrics.rows[0]
        self.assertEqual(row.working_frame_index, 0)
        self.assertEqual(row.source_frame_index, 0)
        self.assertEqual(row.region_name, "Terrace A")
        self.assertEqual(row.region_kind, "terrace")
        self.assertEqual(row.detection_count, 3)
        self.assertEqual(row.region_area_px2, 50.0)
        self.assertEqual(row.detection_footprint_area_px2, 7.0)
        self.assertAlmostEqual(row.density_per_px2, 0.06)
        self.assertAlmostEqual(row.detection_footprint_coverage, 0.14)

    def test_population_metrics_emit_zero_rows_for_each_working_frame_active_region_geometry(self) -> None:
        from moltrack.core import AnalysisRegion, FrameScopedAnalysisRegion, MolTrackProject, PopulationMetrics, SourceImageSeries

        source = SourceImageSeries(source_uri="C:/data/movie.mpp", frame_count=2)
        terrace_early = AnalysisRegion.rectangle(
            kind="terrace",
            name="Terrace A",
            color_rgb=(20, 120, 240),
            rect_xyxy=(0.0, 0.0, 10.0, 5.0),
        )
        terrace_late = AnalysisRegion.rectangle(
            kind="terrace",
            name="Terrace A",
            color_rgb=(20, 120, 240),
            rect_xyxy=(0.0, 0.0, 4.0, 4.0),
        )
        project = MolTrackProject.from_source_series(source).with_analysis_regions(
            (terrace_early,),
            frame_scoped_analysis_regions=(
                FrameScopedAnalysisRegion(region=terrace_early, working_frame_indices=(0,)),
                FrameScopedAnalysisRegion(region=terrace_late, working_frame_indices=(1,)),
            ),
        )

        metrics = PopulationMetrics.from_project(project)

        self.assertEqual(
            [
                (
                    row.working_frame_index,
                    row.source_frame_index,
                    row.region_name,
                    row.detection_count,
                    row.region_area_px2,
                    row.density_per_px2,
                    row.detection_footprint_coverage,
                )
                for row in metrics.rows
            ],
            [
                (0, 0, "Terrace A", 0, 50.0, 0.0, 0.0),
                (1, 1, "Terrace A", 0, 16.0, 0.0, 0.0),
            ],
        )

    def test_population_metrics_assign_unassigned_yolo_detections_by_centroid_before_counting(self) -> None:
        from moltrack.core import (
            AnalysisRegion,
            DetectionReviewStatus,
            MolTrackProject,
            MolecularDetection,
            PopulationMetrics,
            SourceImageSeries,
        )

        source = SourceImageSeries(source_uri="C:/data/movie.mpp", frame_count=1)
        full_frame_region = AnalysisRegion.rectangle(
            kind="terrace",
            name="Whole image",
            color_rgb=(20, 120, 240),
            rect_xyxy=(0.0, 0.0, 256.0, 256.0),
        )
        detected_inside_region = MolecularDetection(
            detection_id="yolo-unassigned",
            working_frame_index=0,
            source_frame_index=0,
            bbox_xyxy=(20.0, 30.0, 28.0, 40.0),
            confidence=0.92,
            model_name="molecules.pt",
            review_status=DetectionReviewStatus.ACCEPTED,
            backend_name="yolo",
            run_mode="full_frame",
            region_name=None,
        )
        project = MolTrackProject.from_source_series(source).with_analysis_regions(
            (full_frame_region,),
            molecular_detections=(detected_inside_region,),
        )

        metrics = PopulationMetrics.from_project(project)

        self.assertEqual(len(metrics.rows), 1)
        self.assertEqual(metrics.rows[0].region_name, "Whole image")
        self.assertEqual(metrics.rows[0].detection_count, 1)
        self.assertEqual(metrics.rows[0].detection_footprint_area_px2, 80.0)

    def test_population_metrics_respect_explicit_region_name_when_regions_overlap(self) -> None:
        from moltrack.core import (
            AnalysisRegion,
            DetectionReviewStatus,
            MolTrackProject,
            MolecularDetection,
            PopulationMetrics,
            SourceImageSeries,
        )

        source = SourceImageSeries(source_uri="C:/data/movie.mpp", frame_count=1)
        terrace = AnalysisRegion.rectangle(
            kind="terrace",
            name="Terrace A",
            color_rgb=(20, 120, 240),
            rect_xyxy=(0.0, 0.0, 10.0, 5.0),
        )
        ignore = AnalysisRegion.rectangle(
            kind="ignore",
            name="Ignore A",
            color_rgb=(220, 30, 30),
            rect_xyxy=(0.0, 0.0, 10.0, 10.0),
        )
        explicitly_assigned = MolecularDetection(
            detection_id="explicit-terrace",
            working_frame_index=0,
            source_frame_index=0,
            bbox_xyxy=(1.0, 2.0, 3.0, 5.0),
            confidence=0.91,
            model_name="manual",
            review_status=DetectionReviewStatus.ACCEPTED,
            backend_name="manual",
            run_mode="full_frame",
            region_name="Terrace A",
        )
        project = MolTrackProject.from_source_series(source).with_analysis_regions(
            (ignore, terrace),
            molecular_detections=(explicitly_assigned,),
        )

        metrics = PopulationMetrics.from_project(project)

        self.assertEqual(len(metrics.rows), 1)
        self.assertEqual(metrics.rows[0].region_name, "Terrace A")
        self.assertEqual(metrics.rows[0].detection_count, 1)
        self.assertEqual(metrics.rows[0].detection_footprint_area_px2, 6.0)


if __name__ == "__main__":
    unittest.main()
