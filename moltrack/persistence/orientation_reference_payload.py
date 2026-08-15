from __future__ import annotations

from dataclasses import asdict, dataclass
from math import isclose, isfinite
from typing import Any

import numpy as np

from moltrack.analysis import MolecularSampleCoordinates
from moltrack.analysis.domain_analysis import (
    M6FrameGate,
    ReferenceReadinessPolicy,
    ReferenceReviewDecision,
)
from moltrack.core import (
    MolecularDetection,
    MolecularDetectionSet,
    MolecularSegmentation,
    MolecularSegmentationSet,
)

from .domain_analysis_payload_validation import json_compatible_value
from .orientation_reference_identity import (
    OrientationReferenceStateIdentity,
    orientation_reference_state_identity,
)
from .orientation_reference_objects import (
    OrientationArrayObject,
    deduplicated_orientation_objects,
    orientation_array_object,
    orientation_local_mask_object,
)
from .orientation_reference_rows import (
    orientation_assignment_row,
    orientation_coordinate_rows,
    orientation_frame_row,
    orientation_molecule_row,
    orientation_original_mask_object,
    orientation_row_prefix,
)
from .orientation_reference_schema import (
    OrientationReferenceMeasurementGroup,
    OrientationReferenceSplit,
)
from .reference_dataset import (
    ReferencePayloadFile,
    reference_measurement_group_fingerprint,
    reference_partition_fingerprint,
    reference_source_revision_row,
    validated_reference_measurements,
)
ORIENTATION_REFERENCE_TABLE_FILES = (
    "measurements.jsonl",
    "frames.jsonl",
    "molecules.jsonl",
    "review_signoffs.jsonl",
    "classifier_provenance.jsonl",
    "orientation_assignments.jsonl",
)


@dataclass(frozen=True)
class OrientationReferencePackagePayload:
    tables: dict[str, list[dict[str, Any]]]
    objects: tuple[ReferencePayloadFile, ...]

    def partition_fingerprint(self, split: OrientationReferenceSplit) -> str:
        return reference_partition_fingerprint("orientation", split, self.tables)

    def measurement_group_count(self, split: OrientationReferenceSplit) -> int:
        return sum(
            row["split"] == split
            for row in self.tables["measurements.jsonl"]
        )


@dataclass(frozen=True)
class _FrameInputs:
    gate: M6FrameGate
    coordinates: MolecularSampleCoordinates
    pixel_size_nm: tuple[float, float]
    segmentations: dict[str, MolecularSegmentation]
    parent_detections: dict[str, MolecularDetection]


def build_orientation_reference_payload(
    measurements: tuple[OrientationReferenceMeasurementGroup, ...],
) -> OrientationReferencePackagePayload:
    measurements = _validated_measurements(measurements)
    tables: dict[str, list[dict[str, Any]]] = {
        name: [] for name in ORIENTATION_REFERENCE_TABLE_FILES
    }
    objects: list[OrientationArrayObject] = []
    for measurement in measurements:
        _append_measurement_payload(tables, objects, measurement)
    return OrientationReferencePackagePayload(
        tables=tables,
        objects=deduplicated_orientation_objects(objects),
    )


def _validated_measurements(
    measurements: tuple[OrientationReferenceMeasurementGroup, ...],
) -> tuple[OrientationReferenceMeasurementGroup, ...]:
    values = validated_reference_measurements(
        measurements,
        measurement_type=OrientationReferenceMeasurementGroup,
        dataset_label="Orientation Reference Dataset",
    )
    ReferenceReadinessPolicy().evaluate_dataset(
        values,
        "orientation",
    ).require_ready()
    for value in values:
        _validated_frame_inputs(value)
    return values


def _validated_frame_inputs(
    measurement: OrientationReferenceMeasurementGroup,
) -> tuple[_FrameInputs, ...]:
    state = measurement.snapshot
    publication = state.published_result
    assert publication is not None and publication.result.m6_gate is not None
    coordinates = {
        value.frame_index: value for value in measurement.sample_coordinates
    }
    frames = tuple(sorted(
        publication.result.m6_gate.frames,
        key=lambda value: value.frame_index,
    ))
    if set(coordinates) != {value.frame_index for value in frames}:
        raise ValueError(
            "Orientation sample coordinates must cover every analyzed frame exactly once."
        )
    segmentation_set = measurement.series.molecular_segmentations
    if not isinstance(segmentation_set, MolecularSegmentationSet):
        raise ValueError("Orientation Reference Dataset requires molecular segmentations.")
    detection_set = measurement.series.molecular_detections
    if not isinstance(detection_set, MolecularDetectionSet):
        raise ValueError(
            "Orientation Reference Dataset requires parent Detection Identity."
        )
    pixel_size = _required_pixel_size(measurement)
    return tuple(
        _validate_frame_input(
            measurement,
            frame,
            coordinates[frame.frame_index],
            segmentation_set,
            detection_set,
            pixel_size,
        )
        for frame in frames
    )


def _validate_frame_input(
    measurement: OrientationReferenceMeasurementGroup,
    frame: M6FrameGate,
    coordinates: MolecularSampleCoordinates,
    segmentation_set: MolecularSegmentationSet,
    detection_set: MolecularDetectionSet,
    pixel_size: tuple[float, float],
) -> _FrameInputs:
    raw_frame = np.asarray(measurement.series.get_frame(frame.frame_index))
    if raw_frame.ndim != 2 or raw_frame.shape != measurement.series.frame_shape:
        raise ValueError("Orientation raw frame geometry is invalid.")
    if coordinates.source_view != "raw":
        raise ValueError("Orientation reference coordinates must use the raw source view.")
    expected_ids = tuple(sorted(frame.analyzed_source_ids))
    if tuple(sorted(coordinates.point_source_ids)) != expected_ids:
        raise ValueError("Orientation sample coordinates must cover analyzed source IDs.")
    if any(value != "segmentation" for value in coordinates.point_source_kinds):
        raise ValueError("Orientation training sources must be segmentations.")
    expected_window = (
        measurement.series.frame_shape[1] * pixel_size[0],
        measurement.series.frame_shape[0] * pixel_size[1],
    )
    if any(
        not isclose(actual, expected, rel_tol=1e-9, abs_tol=1e-12)
        for actual, expected in zip(coordinates.window_side_lengths_nm, expected_window)
    ):
        raise ValueError("Orientation pixel size conflicts with sample coordinates.")
    segmentations = {
        value.segmentation_id: value
        for value in segmentation_set.get_segmentations(
            frame.frame_index,
            source_view="raw",
        )
        if value.segmentation_id in expected_ids
    }
    if set(segmentations) != set(expected_ids):
        raise ValueError("Orientation reference requires one raw mask per source_id.")
    for segmentation in segmentations.values():
        mask = None if segmentation.mask is None else np.asarray(segmentation.mask)
        if mask is None or mask.shape != raw_frame.shape or not np.any(mask):
            raise ValueError("Orientation segmentation masks must match the raw frame.")
    parents = _validated_parent_detections(
        frame,
        segmentations,
        detection_set,
    )
    return _FrameInputs(frame, coordinates, pixel_size, segmentations, parents)


def _validated_parent_detections(
    frame: M6FrameGate,
    segmentations: dict[str, MolecularSegmentation],
    detection_set: MolecularDetectionSet,
) -> dict[str, MolecularDetection]:
    available = {
        value.detection_id: value
        for value in detection_set.get_detections(
            frame.frame_index,
            source_view="raw",
        )
    }
    parents: dict[str, MolecularDetection] = {}
    for source_id, segmentation in segmentations.items():
        if len(segmentation.prompt_detection_ids) != 1:
            raise ValueError(
                "Orientation segmentation requires one parent Detection Identity."
            )
        detection_id = segmentation.prompt_detection_ids[0]
        parent = available.get(detection_id)
        if parent is None:
            raise ValueError(
                "Orientation segmentation references an unknown parent Detection Identity."
            )
        parents[source_id] = parent
    if len({value.detection_id for value in parents.values()}) != len(parents):
        raise ValueError("Orientation segmentations must have distinct parent detections.")
    return parents


def _required_pixel_size(
    measurement: OrientationReferenceMeasurementGroup,
) -> tuple[float, float]:
    values = measurement.series.pixel_size_nm
    if any(
        value is None or not isfinite(float(value)) or float(value) <= 0.0
        for value in values
    ):
        raise ValueError("Orientation Reference Dataset requires positive pixel size.")
    return float(values[0]), float(values[1])  # type: ignore[arg-type]


def _append_measurement_payload(
    tables: dict[str, list[dict[str, Any]]],
    objects: list[OrientationArrayObject],
    measurement: OrientationReferenceMeasurementGroup,
) -> None:
    state = measurement.snapshot
    publication = state.published_result
    corrections = state.domain_corrections.correction_set
    projection = state.domain_corrections.effective_projection
    assert publication is not None and corrections is not None and projection is not None
    identity = orientation_reference_state_identity(
        publication,
        corrections,
        projection,
    )
    source = reference_source_revision_row(
        "orientation",
        measurement.source_revision,
    )
    tables["measurements.jsonl"].append(
        _measurement_row(measurement, source, identity)
    )
    decisions = _orientation_review_decisions(measurement)
    for inputs in _validated_frame_inputs(measurement):
        _append_frame_payload(
            tables,
            objects,
            measurement,
            inputs,
            identity,
            decisions,
        )
    _append_classifier_provenance(tables, measurement)


def _measurement_row(
    measurement: OrientationReferenceMeasurementGroup,
    source: dict[str, Any],
    identity: OrientationReferenceStateIdentity,
) -> dict[str, Any]:
    publication = measurement.snapshot.published_result
    assert publication is not None and publication.result.m6_gate is not None
    body = {
        "measurement_group_id": measurement.measurement_group_id,
        "split": measurement.split,
        **source,
        "physical_frame_ids": [
            value.physical_frame_id for value in publication.result.m6_gate.frames
        ],
        "automatic_snapshot_fingerprint": identity.automatic_snapshot_fingerprint,
        "effective_projection_fingerprint": identity.effective_projection_fingerprint,
    }
    return {
        **body,
        "measurement_group_fingerprint": reference_measurement_group_fingerprint(
            "orientation",
            body,
        ),
    }


def _append_frame_payload(
    tables: dict[str, list[dict[str, Any]]],
    objects: list[OrientationArrayObject],
    measurement: OrientationReferenceMeasurementGroup,
    inputs: _FrameInputs,
    identity: OrientationReferenceStateIdentity,
    decisions: dict[tuple[str, str], ReferenceReviewDecision],
) -> None:
    raw_frame = np.asarray(measurement.series.get_frame(inputs.gate.frame_index))
    raw_object = orientation_array_object("raw_frames", raw_frame)
    objects.append(raw_object)
    tables["frames.jsonl"].append(
        orientation_frame_row(
            measurement,
            inputs.gate.physical_frame_id,
            inputs.gate.frame_index,
            inputs.pixel_size_nm,
            inputs.coordinates,
            identity,
            raw_object,
        )
    )
    coordinate_rows = orientation_coordinate_rows(inputs.coordinates)
    projection = measurement.snapshot.domain_corrections.effective_projection
    assert projection is not None
    for source_id in sorted(inputs.segmentations):
        segmentation = inputs.segmentations[source_id]
        parent_detection = inputs.parent_detections[source_id]
        mask_object = orientation_local_mask_object(
            "segmentations",
            segmentation.mask,
            frame_shape=(int(raw_frame.shape[0]), int(raw_frame.shape[1])),
            detection_bbox_xyxy=parent_detection.bbox_xyxy,
        )
        objects.append(mask_object.array_object)
        original_object = orientation_original_mask_object(
            segmentation,
            parent_detection,
            (int(raw_frame.shape[0]), int(raw_frame.shape[1])),
            objects,
        )
        prefix = {
            **orientation_row_prefix(measurement, inputs.gate.physical_frame_id),
            "source_id": source_id,
        }
        tables["molecules.jsonl"].append(orientation_molecule_row(
            prefix,
            segmentation,
            parent_detection,
            coordinate_rows[source_id],
            mask_object,
            original_object,
        ))
        tables["orientation_assignments.jsonl"].append(
            orientation_assignment_row(
                prefix,
                projection.molecule(inputs.gate.physical_frame_id, source_id),
                decisions[(inputs.gate.physical_frame_id, source_id)],
            )
        )
    tables["review_signoffs.jsonl"].append(
        _orientation_signoff_row(measurement, inputs.gate)
    )


def _orientation_review_decisions(
    measurement: OrientationReferenceMeasurementGroup,
) -> dict[tuple[str, str], ReferenceReviewDecision]:
    return {
        (frame.scope.physical_frame_id, decision.source_id): decision
        for frame in measurement.snapshot.reference_reviews.frames
        if frame.scope.target == "orientation"
        for decision in frame.decisions
    }


def _orientation_signoff_row(
    measurement: OrientationReferenceMeasurementGroup,
    frame: M6FrameGate,
) -> dict[str, Any]:
    review = measurement.snapshot.reference_reviews.review_for(
        frame.physical_frame_id,
        "orientation",
    )
    signoff = review.sign_off
    assert signoff is not None
    return {
        **orientation_row_prefix(measurement, frame.physical_frame_id),
        "target": "orientation",
        "scope_fingerprint": review.scope.fingerprint,
        "review_state_fingerprint": review.state_fingerprint,
        "signed_at_utc": signoff.signed_at_utc,
        "signed_state_fingerprint": signoff.signed_state_fingerprint,
    }


def _append_classifier_provenance(
    tables: dict[str, list[dict[str, Any]]],
    measurement: OrientationReferenceMeasurementGroup,
) -> None:
    publication = measurement.snapshot.published_result
    assert publication is not None
    for outcome in publication.result.classifier_outcomes or ():
        tables["classifier_provenance.jsonl"].append({
            "measurement_group_id": measurement.measurement_group_id,
            "split": measurement.split,
            "classifier_id": outcome.classifier_id,
            "outcome": json_compatible_value(asdict(outcome)),
        })


__all__ = [
    "ORIENTATION_REFERENCE_TABLE_FILES",
    "OrientationReferencePackagePayload",
    "build_orientation_reference_payload",
]
