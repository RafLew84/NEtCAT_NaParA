import csv
import tempfile
import unittest
from pathlib import Path

import numpy as np


class MolTrackExporterTests(unittest.TestCase):
    def test_export_detections_csv_writes_all_detection_rows_with_geometry_and_review_state(self) -> None:
        from moltrack.core import DetectionReviewStatus, MolTrackProject, MolecularDetection, SourceImageSeries
        from moltrack.io import export_detections_csv

        project = MolTrackProject.from_source_series(
            SourceImageSeries(source_uri="movie.mpp", frame_count=3),
            project_name="detections export",
        ).with_molecular_detections(
            (
                MolecularDetection(
                    detection_id="candidate-later-frame",
                    working_frame_index=2,
                    source_frame_index=2,
                    bbox_xyxy=(10.0, 20.0, 14.0, 26.0),
                    confidence=0.625,
                    model_name="yolo-small.pt",
                    review_status=DetectionReviewStatus.CANDIDATE,
                    backend_name="yolo",
                    run_mode="full_frame",
                    region_name=None,
                ),
                MolecularDetection(
                    detection_id="accepted-terrace",
                    working_frame_index=0,
                    source_frame_index=0,
                    bbox_xyxy=(1.0, 2.0, 5.0, 8.0),
                    confidence=0.91,
                    model_name="manual",
                    review_status=DetectionReviewStatus.ACCEPTED,
                    backend_name="manual",
                    run_mode="full_frame",
                    region_name="Terrace A",
                ),
            )
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "detections.csv"
            export_detections_csv(project, output_path)

            with output_path.open(newline="", encoding="utf-8") as fh:
                rows = list(csv.DictReader(fh))

        self.assertEqual(
            rows[0],
            {
                "working_frame_index": "0",
                "source_frame_index": "0",
                "detection_id": "accepted-terrace",
                "review_status": "accepted",
                "bbox_x0": "1.0",
                "bbox_y0": "2.0",
                "bbox_x1": "5.0",
                "bbox_y1": "8.0",
                "centroid_x": "3.0",
                "centroid_y": "5.0",
                "confidence": "0.91",
                "model_name": "manual",
                "region_name": "Terrace A",
            },
        )
        self.assertEqual(rows[1]["detection_id"], "candidate-later-frame")
        self.assertEqual(rows[1]["review_status"], "candidate")
        self.assertEqual(rows[1]["region_name"], "")

    def test_export_regional_metrics_csv_writes_population_metric_rows(self) -> None:
        from moltrack.core import (
            AnalysisRegion,
            DetectionReviewStatus,
            MolTrackProject,
            MolecularDetection,
            SourceImageSeries,
        )
        from moltrack.io import export_regional_metrics_csv

        terrace = AnalysisRegion.rectangle(
            kind="terrace",
            name="Terrace A",
            color_rgb=(255, 0, 0),
            rect_xyxy=(0.0, 0.0, 10.0, 5.0),
        )
        ignore = AnalysisRegion.rectangle(
            kind="ignore",
            name="Ignore A",
            color_rgb=(0, 0, 0),
            rect_xyxy=(0.0, 0.0, 10.0, 10.0),
        )
        project = MolTrackProject.from_source_series(
            SourceImageSeries(source_uri="movie.mpp", frame_count=2),
            project_name="regional metrics export",
        ).with_analysis_regions((ignore, terrace)).with_molecular_detections(
            (
                MolecularDetection(
                    detection_id="accepted-terrace",
                    working_frame_index=0,
                    source_frame_index=0,
                    bbox_xyxy=(1.0, 2.0, 3.0, 5.0),
                    confidence=0.91,
                    model_name="manual",
                    review_status=DetectionReviewStatus.ACCEPTED,
                    backend_name="manual",
                    run_mode="full_frame",
                    region_name="Terrace A",
                ),
                MolecularDetection(
                    detection_id="candidate-ignored",
                    working_frame_index=0,
                    source_frame_index=0,
                    bbox_xyxy=(1.0, 2.0, 9.0, 9.0),
                    confidence=0.8,
                    model_name="yolo",
                    review_status=DetectionReviewStatus.CANDIDATE,
                    backend_name="yolo",
                    run_mode="full_frame",
                    region_name="Terrace A",
                ),
                MolecularDetection(
                    detection_id="accepted-ignore-region",
                    working_frame_index=0,
                    source_frame_index=0,
                    bbox_xyxy=(1.0, 1.0, 9.0, 9.0),
                    confidence=0.8,
                    model_name="yolo",
                    review_status=DetectionReviewStatus.ACCEPTED,
                    backend_name="yolo",
                    run_mode="full_frame",
                    region_name="Ignore A",
                ),
            )
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "regional_metrics.csv"
            export_regional_metrics_csv(project, output_path)

            with output_path.open(newline="", encoding="utf-8") as fh:
                rows = list(csv.DictReader(fh))

        self.assertEqual(len(rows), 2)
        self.assertEqual(
            rows[0],
            {
                "working_frame_index": "0",
                "source_frame_index": "0",
                "region_name": "Terrace A",
                "region_kind": "terrace",
                "detection_count": "1",
                "region_area_px2": "50.0",
                "detection_footprint_area_px2": "6.0",
                "density_per_px2": "0.02",
                "detection_footprint_coverage": "0.12",
            },
        )
        self.assertEqual(rows[1]["working_frame_index"], "1")
        self.assertEqual(rows[1]["region_name"], "Terrace A")
        self.assertEqual(rows[1]["detection_count"], "0")

    def test_export_row_order_metrics_csv_writes_row_order_metric_rows(self) -> None:
        from moltrack.core import (
            AnalysisRegion,
            DetectionReviewStatus,
            MolTrackProject,
            MolecularDetection,
            SourceImageSeries,
        )
        from moltrack.io import export_row_order_metrics_csv

        terrace = AnalysisRegion.rectangle(
            kind="terrace",
            name="Terrace A",
            color_rgb=(255, 0, 0),
            rect_xyxy=(0.0, 0.0, 40.0, 30.0),
        )
        detections = tuple(
            MolecularDetection(
                detection_id=f"row-point-{x}-{y}",
                working_frame_index=0,
                source_frame_index=0,
                bbox_xyxy=(x - 1.0, y - 1.0, x + 1.0, y + 1.0),
                confidence=0.95,
                model_name="manual",
                review_status=DetectionReviewStatus.ACCEPTED,
                backend_name="manual",
                run_mode="full_frame",
                region_name="Terrace A",
            )
            for y in (10.0, 20.0)
            for x in (10.0, 20.0, 30.0)
        )
        project = MolTrackProject.from_source_series(
            SourceImageSeries(source_uri="movie.mpp", frame_count=1),
            project_name="row order export",
        ).with_analysis_regions((terrace,)).with_molecular_detections(detections)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "row_order_metrics.csv"
            export_row_order_metrics_csv(project, output_path)

            with output_path.open(newline="", encoding="utf-8") as fh:
                rows = list(csv.DictReader(fh))

        self.assertEqual(
            rows,
            [
                {
                    "working_frame_index": "0",
                    "source_frame_index": "0",
                    "region_name": "Terrace A",
                    "region_kind": "terrace",
                    "detection_count": "6",
                    "assigned_detection_count": "6",
                    "orientation_degrees": "0.0",
                    "row_count": "2",
                    "row_spacing_px": "10.0",
                    "row_order_score": "1.0",
                }
            ],
        )

    def test_export_project_summary_csv_writes_frame_counts_status_counts_and_yolo_models(self) -> None:
        from moltrack.core import DetectionReviewStatus, MolTrackProject, MolecularDetection, SourceImageSeries
        from moltrack.io import export_project_summary_csv

        project = MolTrackProject.from_source_series(
            SourceImageSeries(source_uri="movie.mpp", frame_count=4),
            project_name="summary export",
        )
        project = project.remove_working_frame(1).with_molecular_detections(
            (
                MolecularDetection(
                    detection_id="accepted-yolo-a",
                    working_frame_index=0,
                    source_frame_index=0,
                    bbox_xyxy=(1.0, 1.0, 2.0, 2.0),
                    confidence=0.9,
                    model_name="molecule-a.pt",
                    review_status=DetectionReviewStatus.ACCEPTED,
                    backend_name="yolo",
                    run_mode="full_frame",
                ),
                MolecularDetection(
                    detection_id="manual",
                    working_frame_index=1,
                    source_frame_index=2,
                    bbox_xyxy=(1.0, 1.0, 3.0, 3.0),
                    confidence=1.0,
                    model_name="manual",
                    review_status=DetectionReviewStatus.MANUAL,
                    backend_name="manual",
                    run_mode="full_frame",
                ),
                MolecularDetection(
                    detection_id="candidate-yolo-b",
                    working_frame_index=2,
                    source_frame_index=3,
                    bbox_xyxy=(1.0, 1.0, 4.0, 4.0),
                    confidence=0.7,
                    model_name="molecule-b.pt",
                    review_status=DetectionReviewStatus.CANDIDATE,
                    backend_name="yolo",
                    run_mode="full_frame",
                ),
                MolecularDetection(
                    detection_id="edited-yolo-a",
                    working_frame_index=2,
                    source_frame_index=3,
                    bbox_xyxy=(2.0, 2.0, 5.0, 5.0),
                    confidence=0.8,
                    model_name="molecule-a.pt",
                    review_status=DetectionReviewStatus.EDITED,
                    backend_name="yolo",
                    run_mode="roi_replace",
                ),
            )
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "project_summary.csv"
            export_project_summary_csv(project, output_path)

            with output_path.open(newline="", encoding="utf-8") as fh:
                summary = {row["metric"]: row["value"] for row in csv.DictReader(fh)}

        self.assertEqual(summary["project_name"], "summary export")
        self.assertEqual(summary["source_frame_count"], "4")
        self.assertEqual(summary["working_frame_count"], "3")
        self.assertEqual(summary["removed_source_frame_count"], "1")
        self.assertEqual(summary["removed_source_frame_indices"], "1")
        self.assertEqual(summary["detection_count_total"], "4")
        self.assertEqual(summary["detection_count_accepted"], "1")
        self.assertEqual(summary["detection_count_candidate"], "1")
        self.assertEqual(summary["detection_count_edited"], "1")
        self.assertEqual(summary["detection_count_manual"], "1")
        self.assertEqual(summary["detection_count_rejected"], "0")
        self.assertEqual(summary["detection_count_uncertain"], "0")
        self.assertEqual(summary["yolo_model_count"], "2")
        self.assertEqual(summary["yolo_models"], "molecule-a.pt;molecule-b.pt")

    def test_export_yolo_labels_default_mode_writes_accepted_edited_and_manual_bboxes(self) -> None:
        from moltrack.core import DetectionReviewStatus, MolTrackProject, MolecularDetection, SourceImageSeries
        from moltrack.io import export_yolo_labels

        source = SourceImageSeries(
            source_uri="movie.mpp",
            frame_count=2,
            raw_frames=np.zeros((2, 100, 200), dtype=np.float32),
        )
        project = MolTrackProject.from_source_series(source).with_molecular_detections(
            (
                MolecularDetection(
                    detection_id="accepted",
                    working_frame_index=0,
                    source_frame_index=0,
                    bbox_xyxy=(20.0, 10.0, 60.0, 50.0),
                    confidence=0.9,
                    model_name="yolo-a.pt",
                    review_status=DetectionReviewStatus.ACCEPTED,
                    backend_name="yolo",
                    run_mode="full_frame",
                ),
                MolecularDetection(
                    detection_id="candidate-excluded",
                    working_frame_index=0,
                    source_frame_index=0,
                    bbox_xyxy=(0.0, 0.0, 100.0, 100.0),
                    confidence=0.8,
                    model_name="yolo-a.pt",
                    review_status=DetectionReviewStatus.CANDIDATE,
                    backend_name="yolo",
                    run_mode="full_frame",
                ),
                MolecularDetection(
                    detection_id="manual",
                    working_frame_index=1,
                    source_frame_index=1,
                    bbox_xyxy=(50.0, 20.0, 70.0, 40.0),
                    confidence=1.0,
                    model_name="manual",
                    review_status=DetectionReviewStatus.MANUAL,
                    backend_name="manual",
                    run_mode="full_frame",
                ),
            )
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "labels"
            written_paths = export_yolo_labels(project, output_dir)

            frame_zero = (output_dir / "working_0000_source_0000.txt").read_text(encoding="utf-8").splitlines()
            frame_one = (output_dir / "working_0001_source_0001.txt").read_text(encoding="utf-8").splitlines()

        self.assertEqual(
            [path.name for path in written_paths],
            ["working_0000_source_0000.txt", "working_0001_source_0001.txt"],
        )
        self.assertEqual(frame_zero, ["0 0.200000 0.300000 0.200000 0.400000"])
        self.assertEqual(frame_one, ["0 0.300000 0.300000 0.100000 0.200000"])

    def test_export_yolo_labels_candidate_uncertain_mode_writes_review_bboxes_only(self) -> None:
        from moltrack.core import DetectionReviewStatus, MolTrackProject, MolecularDetection, SourceImageSeries
        from moltrack.io import export_yolo_labels

        source = SourceImageSeries(
            source_uri="movie.mpp",
            frame_count=1,
            raw_frames=np.zeros((1, 100, 100), dtype=np.float32),
        )
        project = MolTrackProject.from_source_series(source).with_molecular_detections(
            (
                MolecularDetection(
                    detection_id="accepted-excluded",
                    working_frame_index=0,
                    source_frame_index=0,
                    bbox_xyxy=(0.0, 0.0, 100.0, 100.0),
                    confidence=0.9,
                    model_name="yolo-a.pt",
                    review_status=DetectionReviewStatus.ACCEPTED,
                    backend_name="yolo",
                    run_mode="full_frame",
                ),
                MolecularDetection(
                    detection_id="candidate",
                    working_frame_index=0,
                    source_frame_index=0,
                    bbox_xyxy=(10.0, 10.0, 30.0, 30.0),
                    confidence=0.7,
                    model_name="yolo-a.pt",
                    review_status=DetectionReviewStatus.CANDIDATE,
                    backend_name="yolo",
                    run_mode="full_frame",
                ),
                MolecularDetection(
                    detection_id="uncertain",
                    working_frame_index=0,
                    source_frame_index=0,
                    bbox_xyxy=(40.0, 20.0, 60.0, 50.0),
                    confidence=0.6,
                    model_name="yolo-a.pt",
                    review_status=DetectionReviewStatus.UNCERTAIN,
                    backend_name="yolo",
                    run_mode="full_frame",
                ),
            )
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "labels"
            export_yolo_labels(project, output_dir, mode="candidate_uncertain", class_id=3)

            label_lines = (output_dir / "working_0000_source_0000.txt").read_text(encoding="utf-8").splitlines()

        self.assertEqual(
            label_lines,
            [
                "3 0.200000 0.200000 0.200000 0.200000",
                "3 0.500000 0.350000 0.200000 0.300000",
            ],
        )


if __name__ == "__main__":
    unittest.main()
