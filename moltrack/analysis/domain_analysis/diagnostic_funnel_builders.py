from __future__ import annotations

from .diagnostic_funnel_models import (
    DiagnosticDecision,
    DiagnosticEvidence,
    DiagnosticProvenance,
    DiagnosticProvenanceContext,
    DiagnosticReason,
    DiagnosticStageResult,
    MoleculeDiagnosticStageId,
)
from .fingerprints import canonical_sha256
from .geometry import M6PublishedMolecule
from .models import M6FrameGate, M6PublishedComponent
from .diagnostic_m6_evidence import (
    CentroidEvidence,
    SampleCoordinatesEvidence,
    SourceInputEvidence,
)


def completed_diagnostic_stage(
    frame: M6FrameGate,
    stage_id: MoleculeDiagnosticStageId,
    decision: DiagnosticDecision,
    *,
    reason: DiagnosticReason,
    evidence: DiagnosticEvidence,
    provenance: DiagnosticProvenanceContext,
) -> DiagnosticStageResult:
    output_fingerprint = provenance.output_fingerprint or canonical_sha256({
        "kind": evidence.kind,
        "values": evidence.values,
    })
    return DiagnosticStageResult(
        stage_id=stage_id,
        execution_status="completed",
        decision=decision,
        reason=reason,
        evidence=evidence,
        provenance=DiagnosticProvenance(
            producer=provenance.producer,
            algorithm_version=(
                provenance.algorithm_version
                or frame.backend_identity.algorithm_version
            ),
            settings_fingerprint=(
                provenance.settings_fingerprint
                or frame.backend_identity.settings_fingerprint
            ),
            input_fingerprint=(
                provenance.input_fingerprint
                or frame.source_geometry_fingerprint
            ),
            output_fingerprint=output_fingerprint,
        ),
    )


def unavailable_diagnostic_stage(
    stage_id: MoleculeDiagnosticStageId,
    reason_code: str,
) -> DiagnosticStageResult:
    return DiagnosticStageResult(
        stage_id=stage_id,
        execution_status="unavailable",
        decision="not_evaluated",
        reason=DiagnosticReason("missing_data", reason_code),
    )


def not_run_diagnostic_stage(
    stage_id: MoleculeDiagnosticStageId,
    reason_code: str,
) -> DiagnosticStageResult:
    return DiagnosticStageResult(
        stage_id=stage_id,
        execution_status="not_run",
        decision="not_evaluated",
        reason=DiagnosticReason("not_run", reason_code),
    )


def failed_diagnostic_stage(
    stage_id: MoleculeDiagnosticStageId,
    reason_code: str,
    *,
    native_code: str | None = None,
) -> DiagnosticStageResult:
    return DiagnosticStageResult(
        stage_id=stage_id,
        execution_status="failed",
        decision="not_evaluated",
        reason=DiagnosticReason("execution_error", reason_code, native_code),
    )


def raw_centroid_values(
    molecule: M6PublishedMolecule,
) -> tuple[float | None, float | None]:
    if molecule.raw_centroid_xy is None:
        return None, None
    return molecule.raw_centroid_xy


def source_coordinate_stages(
    frame: M6FrameGate,
    molecule: M6PublishedMolecule,
) -> tuple[DiagnosticStageResult, ...]:
    raw_x, raw_y = raw_centroid_values(molecule)
    accepted = DiagnosticReason("accepted", "accepted_result")
    producer = DiagnosticProvenanceContext("canonicalize_frame")
    return (
        completed_diagnostic_stage(
            frame, "source_input", "accepted", reason=accepted,
            evidence=DiagnosticEvidence(SourceInputEvidence(
                molecule.source_kind, raw_x, raw_y
            )),
            provenance=producer,
        ),
        completed_diagnostic_stage(
            frame, "centroid", "accepted", reason=accepted,
            evidence=DiagnosticEvidence(CentroidEvidence(
                molecule.point_xy_nm[0], molecule.point_xy_nm[1],
                frame.coordinate_frame,
            )),
            provenance=producer,
        ),
        completed_diagnostic_stage(
            frame, "sample_coordinates", "accepted", reason=accepted,
            evidence=DiagnosticEvidence(SampleCoordinatesEvidence(
                molecule.point_xy_nm[0], molecule.point_xy_nm[1],
                frame.coordinate_transform_fingerprint,
            )),
            provenance=producer,
        ),
    )


def molecules_by_id(frame: M6FrameGate) -> dict[str, M6PublishedMolecule]:
    members = tuple(
        member
        for component in frame.full_domains + frame.small_ordered_islands
        for member in component.members
    ) + frame.outside_members
    return {molecule.source_id: molecule for molecule in members}


def published_partition(
    frame: M6FrameGate,
    source_id: str,
) -> tuple[str, M6PublishedComponent | None]:
    for component in frame.full_domains:
        if source_id in component.source_ids:
            return "full_domain", component
    for component in frame.small_ordered_islands:
        if source_id in component.source_ids:
            return "small_ordered_island", component
    return "outside", None
