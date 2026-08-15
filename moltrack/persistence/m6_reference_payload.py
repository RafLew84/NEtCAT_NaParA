from __future__ import annotations

from dataclasses import asdict, dataclass
from math import hypot
from typing import Any

from moltrack.analysis.domain_analysis import (
    DomainAnalysisSessionState,
    M6FrameGate,
    M6PublishedMolecule,
    ReferenceReviewDecision,
)
from moltrack.analysis.domain_analysis.diagnostic_funnel import (
    build_molecule_diagnostic_funnels,
)
from .domain_analysis_payload_validation import json_compatible_value
from .domain_backend_payload import backend_identity_to_payload
from .m6_reference_identity import (
    M6ReferenceStateIdentity,
    m6_reference_state_identity,
)
from .m6_reference_schema import M6ReferenceMeasurementGroup, M6ReferenceSplit
from .reference_dataset import (
    reference_measurement_group_fingerprint,
    reference_partition_fingerprint,
    reference_source_revision_row,
    validated_reference_measurements,
)
from .reference_dataset_readiness import validate_reference_snapshot_readiness


M6_REFERENCE_TABLE_FILES = (
    "measurements.jsonl",
    "frames.jsonl",
    "molecules.jsonl",
    "source_geometry.jsonl",
    "review_signoffs.jsonl",
    "diagnostic_stages.jsonl",
    "m6_assignments.jsonl",
    "m6_first_shell_edges.jsonl",
)
_M6_DIAGNOSTIC_STAGE_IDS = {
    "source_input",
    "centroid",
    "sample_coordinates",
    "first_shell",
    "local_order",
    "local_symmetry",
    "domain_edges",
    "seed_growth",
    "domain_partition",
    "domain_size",
}


@dataclass(frozen=True)
class M6ReferencePackageTables:
    tables: dict[str, list[dict[str, Any]]]

    def partition_fingerprint(self, split: M6ReferenceSplit) -> str:
        return reference_partition_fingerprint("m6", split, self.tables)

    def measurement_group_count(self, split: M6ReferenceSplit) -> int:
        return sum(
            row["split"] == split
            for row in self.tables["measurements.jsonl"]
        )


def build_m6_reference_tables(
    measurements: tuple[M6ReferenceMeasurementGroup, ...],
) -> M6ReferencePackageTables:
    measurements = _validated_measurements(measurements)
    tables: dict[str, list[dict[str, Any]]] = {
        name: [] for name in M6_REFERENCE_TABLE_FILES
    }
    for measurement in measurements:
        _append_measurement_tables(tables, measurement)
    return M6ReferencePackageTables(tables)


def _validated_measurements(
    measurements: tuple[M6ReferenceMeasurementGroup, ...],
) -> tuple[M6ReferenceMeasurementGroup, ...]:
    values = validated_reference_measurements(
        measurements,
        measurement_type=M6ReferenceMeasurementGroup,
        dataset_label="M6 Reference Dataset",
    )
    for value in values:
        _validate_ready_measurement(value)
    return values


def _validate_ready_measurement(measurement: M6ReferenceMeasurementGroup) -> None:
    state = measurement.snapshot
    validate_reference_snapshot_readiness(state, "m6")
    publication = state.published_result
    assert publication is not None and publication.result.m6_gate is not None
    _validate_edges(measurement, publication.result.m6_gate.frames)


def _validate_edges(
    measurement: M6ReferenceMeasurementGroup,
    frames: tuple[M6FrameGate, ...],
) -> None:
    source_ids = {
        frame.physical_frame_id: set(frame.analyzed_source_ids)
        for frame in frames
    }
    for edge in measurement.first_shell_edges:
        available = source_ids.get(edge.physical_frame_id)
        if available is None:
            raise ValueError("First-shell edge references an unknown frame.")
        if edge.source_id_a not in available or edge.source_id_b not in available:
            raise ValueError("First-shell edge references an unknown source_id.")


def _append_measurement_tables(
    tables: dict[str, list[dict[str, Any]]],
    measurement: M6ReferenceMeasurementGroup,
) -> None:
    state = measurement.snapshot
    publication = state.published_result
    correction_set = state.domain_corrections.correction_set
    projection = state.domain_corrections.effective_projection
    assert publication is not None and publication.result.m6_gate is not None
    assert correction_set is not None and projection is not None
    state_identity = m6_reference_state_identity(
        publication,
        correction_set,
        projection,
    )
    source = reference_source_revision_row("m6", measurement.source_revision)
    tables["measurements.jsonl"].append(_measurement_row(
        measurement,
        source,
        state_identity,
    ))
    review_decisions = _m6_review_decisions(state)
    for frame in publication.result.m6_gate.frames:
        _append_frame_tables(
            tables,
            measurement,
            frame,
            state_identity,
            review_decisions,
        )
    _append_diagnostic_stages(tables, measurement)
    _append_first_shell_edges(tables, measurement)


def _measurement_row(
    measurement: M6ReferenceMeasurementGroup,
    source: dict[str, Any],
    state_identity: M6ReferenceStateIdentity,
) -> dict[str, Any]:
    publication = measurement.snapshot.published_result
    assert publication is not None and publication.result.m6_gate is not None
    body = {
        "measurement_group_id": measurement.measurement_group_id,
        "split": measurement.split,
        **source,
        "physical_frame_ids": [
            frame.physical_frame_id
            for frame in publication.result.m6_gate.frames
        ],
        "automatic_snapshot_fingerprint": (
            state_identity.automatic_snapshot_fingerprint
        ),
        "effective_projection_fingerprint": (
            state_identity.effective_projection_fingerprint
        ),
    }
    return {
        **body,
        "measurement_group_fingerprint": (
            reference_measurement_group_fingerprint("m6", body)
        ),
    }


def _append_frame_tables(
    tables: dict[str, list[dict[str, Any]]],
    measurement: M6ReferenceMeasurementGroup,
    frame: M6FrameGate,
    state_identity: M6ReferenceStateIdentity,
    review_decisions: dict[tuple[str, str], ReferenceReviewDecision],
) -> None:
    state = measurement.snapshot
    projection = state.domain_corrections.effective_projection
    assert projection is not None
    prefix = _row_prefix(measurement, frame.physical_frame_id)
    tables["frames.jsonl"].append({
        **prefix,
        "working_frame_index": frame.frame_index,
        "m6_gate_fingerprint": frame.m6_gate_fingerprint,
        "backend_identity": backend_identity_to_payload(frame.backend_identity),
        "automatic_snapshot_fingerprint": (
            state_identity.automatic_snapshot_fingerprint
        ),
        "m6_correction_revision": state_identity.correction_revision,
        "effective_projection_fingerprint": (
            state_identity.effective_projection_fingerprint
        ),
    })
    molecules = _frame_molecules(frame)
    for molecule in molecules:
        _append_molecule_tables(
            tables,
            measurement,
            frame,
            molecule,
            projection.molecule(frame.physical_frame_id, molecule.source_id),
            review_decisions[(frame.physical_frame_id, molecule.source_id)],
        )
    tables["review_signoffs.jsonl"].append(
        _m6_signoff_row(state, measurement, frame)
    )


def _append_molecule_tables(
    tables: dict[str, list[dict[str, Any]]],
    measurement: M6ReferenceMeasurementGroup,
    frame: M6FrameGate,
    molecule: M6PublishedMolecule,
    effective: Any,
    review: ReferenceReviewDecision,
) -> None:
    prefix = {
        **_row_prefix(measurement, frame.physical_frame_id),
        "source_id": molecule.source_id,
    }
    tables["molecules.jsonl"].append({
        **prefix,
        "source_kind": molecule.source_kind,
    })
    tables["source_geometry.jsonl"].append(
        _source_geometry_row(prefix, frame, molecule)
    )
    tables["m6_assignments.jsonl"].append(
        _m6_assignment_row(prefix, effective, review)
    )


def _source_geometry_row(
    prefix: dict[str, Any],
    frame: M6FrameGate,
    molecule: M6PublishedMolecule,
) -> dict[str, Any]:
    provenance = frame.presentation_provenance
    return {
        **prefix,
        "coordinate_frame": frame.coordinate_frame,
        "coordinate_transform_fingerprint": frame.coordinate_transform_fingerprint,
        "source_geometry_fingerprint": frame.source_geometry_fingerprint,
        "point_xy_nm": list(molecule.point_xy_nm),
        "raw_centroid_xy": (
            None if molecule.raw_centroid_xy is None else list(molecule.raw_centroid_xy)
        ),
        "footprint_pixels_xy": (
            None
            if molecule.footprint_pixels_xy is None
            else [list(value) for value in molecule.footprint_pixels_xy]
        ),
        "raw_shape": list(provenance.raw_shape),
        "expanded_shape": list(provenance.expanded_shape),
        "source_view": provenance.source_view,
        "frame_origin_xy": list(provenance.frame_origin_xy),
        "canvas_offset_xy": list(provenance.canvas_offset_xy),
        "registration_fingerprint": provenance.registration_fingerprint,
    }


def _m6_assignment_row(
    prefix: dict[str, Any],
    effective: Any,
    review: ReferenceReviewDecision,
) -> dict[str, Any]:
    return {
        **prefix,
        "effective_m6_partition": effective.m6_partition,
        "effective_domain_id": effective.effective_domain_id,
        "effective_boundary": effective.is_boundary,
        "review_eligibility": review.eligibility,
        "review_disposition": review.disposition,
        "review_abstention": review.abstention,
        "review_reason_code": review.reason_code,
    }


def _frame_molecules(frame: M6FrameGate) -> tuple[M6PublishedMolecule, ...]:
    values = tuple(
        member
        for component in frame.full_domains + frame.small_ordered_islands
        for member in component.members
    ) + frame.outside_members
    by_source_id = {value.source_id: value for value in values}
    if set(by_source_id) != set(frame.analyzed_source_ids) or len(values) != len(
        by_source_id
    ):
        raise ValueError("Published M6 frame does not contain one row per source_id.")
    return tuple(by_source_id[value] for value in sorted(by_source_id))


def _m6_review_decisions(
    state: DomainAnalysisSessionState,
) -> dict[tuple[str, str], ReferenceReviewDecision]:
    values = {
        (frame.scope.physical_frame_id, decision.source_id): decision
        for frame in state.reference_reviews.frames
        if frame.scope.target == "m6"
        for decision in frame.decisions
    }
    return values


def _m6_signoff_row(
    state: DomainAnalysisSessionState,
    measurement: M6ReferenceMeasurementGroup,
    frame: M6FrameGate,
) -> dict[str, Any]:
    review = state.reference_reviews.review_for(frame.physical_frame_id, "m6")
    signoff = review.sign_off
    assert signoff is not None
    return {
        **_row_prefix(measurement, frame.physical_frame_id),
        "target": "m6",
        "scope_fingerprint": review.scope.fingerprint,
        "review_state_fingerprint": review.state_fingerprint,
        "signed_at_utc": signoff.signed_at_utc,
        "signed_state_fingerprint": signoff.signed_state_fingerprint,
    }


def _append_diagnostic_stages(
    tables: dict[str, list[dict[str, Any]]],
    measurement: M6ReferenceMeasurementGroup,
) -> None:
    publication = measurement.snapshot.published_result
    assert publication is not None
    for funnel in build_molecule_diagnostic_funnels(publication.result):
        prefix = {
            **_row_prefix(measurement, funnel.physical_frame_id),
            "source_id": funnel.source_id,
        }
        for stage in funnel.stages:
            if stage.stage_id in _M6_DIAGNOSTIC_STAGE_IDS:
                tables["diagnostic_stages.jsonl"].append({
                    **prefix,
                    **json_compatible_value(asdict(stage)),
                })


def _append_first_shell_edges(
    tables: dict[str, list[dict[str, Any]]],
    measurement: M6ReferenceMeasurementGroup,
) -> None:
    publication = measurement.snapshot.published_result
    assert publication is not None and publication.result.m6_gate is not None
    points = {
        (frame.physical_frame_id, molecule.source_id): molecule.point_xy_nm
        for frame in publication.result.m6_gate.frames
        for molecule in _frame_molecules(frame)
    }
    for edge in measurement.first_shell_edges:
        first = points[(edge.physical_frame_id, edge.source_id_a)]
        second = points[(edge.physical_frame_id, edge.source_id_b)]
        tables["m6_first_shell_edges.jsonl"].append({
            **_row_prefix(measurement, edge.physical_frame_id),
            "source_id_a": edge.source_id_a,
            "source_id_b": edge.source_id_b,
            "distance_nm": hypot(first[0] - second[0], first[1] - second[1]),
        })


def _row_prefix(
    measurement: M6ReferenceMeasurementGroup,
    physical_frame_id: str,
) -> dict[str, str]:
    return {
        "measurement_group_id": measurement.measurement_group_id,
        "split": measurement.split,
        "physical_frame_id": physical_frame_id,
    }


__all__ = [
    "M6_REFERENCE_TABLE_FILES",
    "M6ReferencePackageTables",
    "build_m6_reference_tables",
]
