from __future__ import annotations

import csv
import os
from pathlib import Path

from moltrack.core import DetectionReviewStatus, MolTrackProject, MolecularDetection, PopulationMetrics


DETECTIONS_CSV_COLUMNS = (
    "working_frame_index",
    "source_frame_index",
    "detection_id",
    "review_status",
    "bbox_x0",
    "bbox_y0",
    "bbox_x1",
    "bbox_y1",
    "centroid_x",
    "centroid_y",
    "confidence",
    "model_name",
    "region_name",
)

REGIONAL_METRICS_CSV_COLUMNS = (
    "working_frame_index",
    "source_frame_index",
    "region_name",
    "region_kind",
    "detection_count",
    "region_area_px2",
    "detection_footprint_area_px2",
    "density_per_px2",
    "detection_footprint_coverage",
)

PROJECT_SUMMARY_CSV_COLUMNS = ("metric", "value")

YOLO_LABEL_DEFAULT_STATUSES = (
    DetectionReviewStatus.ACCEPTED,
    DetectionReviewStatus.EDITED,
    DetectionReviewStatus.MANUAL,
)
YOLO_LABEL_CANDIDATE_UNCERTAIN_STATUSES = (
    DetectionReviewStatus.CANDIDATE,
    DetectionReviewStatus.UNCERTAIN,
)


def export_detections_csv(project: MolTrackProject, path: str | os.PathLike[str]) -> None:
    """Export all molecular detections from a MolTrack project to CSV."""

    output_path = _prepare_output_path(path)

    with open(output_path, mode="w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=DETECTIONS_CSV_COLUMNS)
        writer.writeheader()
        for detection in sorted(project.molecular_detections, key=_detection_sort_key):
            writer.writerow(_detection_csv_row(detection))


def export_regional_metrics_csv(project: MolTrackProject, path: str | os.PathLike[str]) -> None:
    """Export population metrics per working frame and active analysis region."""

    output_path = _prepare_output_path(path)
    metrics = PopulationMetrics.from_project(project)

    with open(output_path, mode="w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=REGIONAL_METRICS_CSV_COLUMNS)
        writer.writeheader()
        for row in metrics.rows:
            writer.writerow(
                {
                    "working_frame_index": row.working_frame_index,
                    "source_frame_index": row.source_frame_index,
                    "region_name": row.region_name,
                    "region_kind": row.region_kind,
                    "detection_count": row.detection_count,
                    "region_area_px2": row.region_area_px2,
                    "detection_footprint_area_px2": row.detection_footprint_area_px2,
                    "density_per_px2": row.density_per_px2,
                    "detection_footprint_coverage": row.detection_footprint_coverage,
                }
            )


def export_project_summary_csv(project: MolTrackProject, path: str | os.PathLike[str]) -> None:
    """Export one-row-per-metric project summary values."""

    output_path = _prepare_output_path(path)

    with open(output_path, mode="w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=PROJECT_SUMMARY_CSV_COLUMNS)
        writer.writeheader()
        for metric, value in _project_summary_rows(project):
            writer.writerow({"metric": metric, "value": value})


def _project_summary_rows(project: MolTrackProject) -> list[tuple[str, object]]:
    status_counts = {status: 0 for status in DetectionReviewStatus}
    for detection in project.molecular_detections:
        status_counts[detection.review_status] += 1

    yolo_models = sorted(
        {
            detection.model_name
            for detection in project.molecular_detections
            if detection.backend_name == "yolo"
        }
    )
    removed_source_frame_indices = project.working_series.removed_source_frame_indices()

    rows: list[tuple[str, object]] = [
        ("project_name", project.project_name),
        ("source_frame_count", project.source_series.frame_count),
        ("working_frame_count", project.working_series.frame_count),
        ("removed_source_frame_count", len(removed_source_frame_indices)),
        ("removed_source_frame_indices", ";".join(str(index) for index in removed_source_frame_indices)),
        ("detection_count_total", len(project.molecular_detections)),
    ]
    rows.extend(
        (f"detection_count_{status.value}", status_counts[status])
        for status in DetectionReviewStatus
    )
    rows.extend(
        (
            ("yolo_model_count", len(yolo_models)),
            ("yolo_models", ";".join(yolo_models)),
        )
    )
    return rows


def export_yolo_labels(
    project: MolTrackProject,
    output_dir: str | os.PathLike[str],
    *,
    mode: str = "default",
    class_id: int = 0,
    image_shape: tuple[int, int] | None = None,
) -> tuple[Path, ...]:
    """Export YOLO bbox label files for the MolTrack working series."""

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    height, width = _yolo_label_image_shape(project, image_shape)
    statuses = _yolo_label_statuses(mode)
    class_id = int(class_id)

    written_paths = []
    for working_frame in project.working_series.frames:
        label_path = output_path / (
            f"working_{working_frame.working_frame_index:04d}_source_{working_frame.source_frame_index:04d}.txt"
        )
        detections = [
            detection
            for detection in project.molecular_detections_for_working_frame(working_frame.working_frame_index)
            if detection.review_status in statuses
        ]
        with label_path.open(mode="w", encoding="utf-8", newline="\n") as fh:
            for detection in sorted(detections, key=_detection_sort_key):
                fh.write(_yolo_label_line(detection, image_width=width, image_height=height, class_id=class_id))
                fh.write("\n")
        written_paths.append(label_path)
    return tuple(written_paths)


def _yolo_label_image_shape(
    project: MolTrackProject,
    image_shape: tuple[int, int] | None,
) -> tuple[int, int]:
    shape = project.source_series.frame_shape if image_shape is None else image_shape
    if shape is None:
        raise ValueError("YOLO label export requires loaded source frames or explicit image_shape=(height, width).")
    height, width = (int(value) for value in shape)
    if height <= 0 or width <= 0:
        raise ValueError("YOLO label image shape must be positive.")
    return height, width


def _yolo_label_statuses(mode: str) -> tuple[DetectionReviewStatus, ...]:
    normalized = str(mode).strip().lower()
    if normalized == "default":
        return YOLO_LABEL_DEFAULT_STATUSES
    if normalized in {"candidate_uncertain", "candidate-uncertain", "review"}:
        return YOLO_LABEL_CANDIDATE_UNCERTAIN_STATUSES
    raise ValueError("mode must be 'default' or 'candidate_uncertain'.")


def _yolo_label_line(
    detection: MolecularDetection,
    *,
    image_width: int,
    image_height: int,
    class_id: int,
) -> str:
    x0, y0, x1, y1 = detection.bbox_xyxy
    center_x = ((x0 + x1) / 2.0) / image_width
    center_y = ((y0 + y1) / 2.0) / image_height
    width = (x1 - x0) / image_width
    height = (y1 - y0) / image_height
    return f"{class_id} {center_x:.6f} {center_y:.6f} {width:.6f} {height:.6f}"


def _prepare_output_path(path: str | os.PathLike[str]) -> str:
    output_path = os.fspath(path)
    parent = os.path.dirname(output_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    return output_path


def _detection_sort_key(detection: MolecularDetection) -> tuple[int, int, str]:
    return detection.working_frame_index, detection.source_frame_index, detection.detection_id


def _detection_csv_row(detection: MolecularDetection) -> dict[str, object]:
    x0, y0, x1, y1 = detection.bbox_xyxy
    centroid_x, centroid_y = detection.centroid_xy
    return {
        "working_frame_index": detection.working_frame_index,
        "source_frame_index": detection.source_frame_index,
        "detection_id": detection.detection_id,
        "review_status": detection.review_status.value,
        "bbox_x0": x0,
        "bbox_y0": y0,
        "bbox_x1": x1,
        "bbox_y1": y1,
        "centroid_x": centroid_x,
        "centroid_y": centroid_y,
        "confidence": detection.confidence,
        "model_name": detection.model_name,
        "region_name": "" if detection.region_name is None else detection.region_name,
    }
