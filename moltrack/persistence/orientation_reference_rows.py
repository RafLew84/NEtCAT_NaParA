from __future__ import annotations

from dataclasses import asdict
from typing import Any

import numpy as np

from moltrack.analysis import MolecularSampleCoordinates
from moltrack.analysis.domain_analysis import ReferenceReviewDecision
from moltrack.core import MolecularDetection, MolecularSegmentation

from .domain_analysis_payload_validation import json_compatible_value
from .orientation_reference_identity import OrientationReferenceStateIdentity
from .orientation_reference_objects import (
    OrientationArrayObject,
    OrientationLocalMaskObject,
    orientation_local_mask_object,
)
from .orientation_reference_schema import OrientationReferenceMeasurementGroup


def orientation_frame_row(
    measurement: OrientationReferenceMeasurementGroup,
    physical_frame_id: str,
    frame_index: int,
    pixel_size_nm: tuple[float, float],
    coordinates: MolecularSampleCoordinates,
    identity: OrientationReferenceStateIdentity,
    raw_object: OrientationArrayObject,
) -> dict[str, Any]:
    raw_frame = np.asarray(measurement.series.get_frame(frame_index))
    source_frame_indices = measurement.series.source_frame_indices
    assert source_frame_indices is not None
    return {
        **orientation_row_prefix(measurement, physical_frame_id),
        "working_frame_index": frame_index,
        "source_frame_index": source_frame_indices[frame_index],
        "raw_frame_object_path": raw_object.path,
        "raw_frame_sha256": raw_object.sha256,
        "raw_shape": list(raw_frame.shape),
        "raw_dtype": str(raw_frame.dtype),
        "pixel_size_nm": list(pixel_size_nm),
        "source_view": coordinates.source_view,
        "coordinate_frame": coordinates.coordinate_frame,
        "orientation_reference": coordinates.orientation_reference,
        "scan_angle_deg": coordinates.scan_angle_deg,
        "scan_angle_missing_qc": coordinates.scan_angle_missing_qc,
        "coordinate_transform_fingerprint": (
            coordinates.coordinate_transform_fingerprint
        ),
        "spatial_calibration_fingerprint": (
            coordinates.spatial_calibration_fingerprint
        ),
        "registration_fingerprint": coordinates.registration_fingerprint,
        "valid_fov_polygon_xy_nm": [
            list(value) for value in coordinates.valid_fov_polygon_xy_nm
        ],
        "plot_canvas_polygon_xy_nm": [
            list(value) for value in coordinates.plot_canvas_polygon_xy_nm
        ],
        "window_side_lengths_nm": list(coordinates.window_side_lengths_nm),
        "automatic_snapshot_fingerprint": identity.automatic_snapshot_fingerprint,
        "orientation_correction_revision": identity.correction_revision,
        "effective_projection_fingerprint": identity.effective_projection_fingerprint,
    }


def orientation_coordinate_rows(
    coordinates: MolecularSampleCoordinates,
) -> dict[str, dict[str, Any]]:
    return {
        source_id: {
            "source_kind": source_kind,
            "source_point_xy_px": list(source_point),
            "point_xy_nm": list(point),
            "distance_to_valid_fov_boundary_nm": distance,
            "annotation_fingerprint": annotation,
        }
        for source_id, source_kind, source_point, point, distance, annotation in zip(
            coordinates.point_source_ids,
            coordinates.point_source_kinds,
            coordinates.source_points_xy_px,
            coordinates.points_xy_nm,
            coordinates.distance_to_valid_fov_boundary_nm,
            coordinates.point_annotation_fingerprints,
        )
    }


def orientation_molecule_row(
    prefix: dict[str, Any],
    segmentation: MolecularSegmentation,
    parent_detection: MolecularDetection,
    coordinates: dict[str, Any],
    mask_object: OrientationLocalMaskObject,
    original_object: OrientationLocalMaskObject | None,
) -> dict[str, Any]:
    return {
        **prefix,
        **coordinates,
        "segmentation_id": segmentation.segmentation_id,
        "segmentation_object_path": mask_object.path,
        "segmentation_sha256": mask_object.sha256,
        "segmentation_shape": list(mask_object.local_shape),
        "segmentation_frame_shape": list(mask_object.frame_shape),
        "segmentation_footprint_xyxy": list(mask_object.footprint_xyxy),
        "original_segmentation_object_path": (
            None if original_object is None else original_object.path
        ),
        "original_segmentation_sha256": (
            None if original_object is None else original_object.sha256
        ),
        "bbox_xyxy": (
            None if segmentation.bbox_xyxy is None else list(segmentation.bbox_xyxy)
        ),
        "polygon_xy": (
            None
            if segmentation.polygon_xy is None
            else [list(value) for value in segmentation.polygon_xy]
        ),
        "segmentation_score": segmentation.score,
        "segmentation_origin": segmentation.origin,
        "prompt_detection_ids": list(segmentation.prompt_detection_ids),
        "segmentation_model_name": segmentation.model_name,
        "segmentation_metadata": json_compatible_value(segmentation.metadata),
        "parent_detection_id": parent_detection.detection_id,
        "parent_detection_bbox_xyxy": list(parent_detection.bbox_xyxy),
        "parent_detection_original_bbox_xyxy": (
            None
            if parent_detection.original_bbox_xyxy is None
            else list(parent_detection.original_bbox_xyxy)
        ),
        "parent_detection_confidence": parent_detection.confidence,
        "parent_detection_selected": parent_detection.selected,
        "parent_detection_model_name": parent_detection.model_name,
        "parent_detection_checkpoint_path": parent_detection.checkpoint_path,
        "parent_detection_origin": parent_detection.origin,
    }


def orientation_original_mask_object(
    segmentation: MolecularSegmentation,
    parent_detection: MolecularDetection,
    frame_shape: tuple[int, int],
    objects: list[OrientationArrayObject],
) -> OrientationLocalMaskObject | None:
    if segmentation.original_mask is None:
        return None
    value = orientation_local_mask_object(
        "original_segmentations",
        segmentation.original_mask,
        frame_shape=frame_shape,
        detection_bbox_xyxy=parent_detection.bbox_xyxy,
    )
    objects.append(value.array_object)
    return value


def orientation_assignment_row(
    prefix: dict[str, Any],
    effective: Any,
    review: ReferenceReviewDecision,
) -> dict[str, Any]:
    return {
        **prefix,
        "effective_orientation": effective.effective_orientation,
        "effective_orientation_source": effective.effective_orientation_source,
        "effective_confidence": effective.effective_confidence,
        "manual_decision": (
            None
            if effective.manual_decision is None
            else json_compatible_value(asdict(effective.manual_decision))
        ),
        "automatic_classification": (
            None
            if effective.automatic_classification is None
            else json_compatible_value(asdict(effective.automatic_classification))
        ),
        "review_eligibility": review.eligibility,
        "review_disposition": review.disposition,
        "review_abstention": review.abstention,
        "review_reason_code": review.reason_code,
    }


def orientation_row_prefix(
    measurement: OrientationReferenceMeasurementGroup,
    physical_frame_id: str,
) -> dict[str, str]:
    return {
        "measurement_group_id": measurement.measurement_group_id,
        "split": measurement.split,
        "physical_frame_id": physical_frame_id,
    }


__all__ = [
    "orientation_assignment_row",
    "orientation_coordinate_rows",
    "orientation_frame_row",
    "orientation_molecule_row",
    "orientation_original_mask_object",
    "orientation_row_prefix",
]
