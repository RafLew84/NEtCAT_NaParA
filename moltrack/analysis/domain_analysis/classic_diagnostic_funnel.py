from __future__ import annotations

from .backend_contract import (
    M6_ORIENTATION_COMPONENTS_BACKEND_ID,
    M6OrientationComponentsEvidence,
)
from .classifier_models import ClassifierOutcome, MoleculeClassification
from .classic_orientation_diagnostic import (
    abc_classifier_outcome,
    classic_effective_result_stage,
    classic_orientation_stages,
)
from .diagnostic_funnel_builders import (
    completed_diagnostic_stage,
    not_run_diagnostic_stage,
    raw_centroid_values,
    unavailable_diagnostic_stage,
)
from .diagnostic_funnel_models import (
    DiagnosticDecision,
    CentroidEvidence,
    DiagnosticEvidence,
    DiagnosticProvenanceContext,
    DiagnosticReason,
    DiagnosticReasonCategory,
    DiagnosticStageResult,
    DomainPartitionEvidence,
    DomainSizeEvidence,
    FirstShellEvidence,
    LocalOrderEvidence,
    MoleculeDiagnosticFunnel,
    SampleCoordinatesEvidence,
    SeedGrowthEvidence,
    SourceInputEvidence,
)
from .geometry import M6PublishedMolecule
from .models import (
    DomainAnalysisResult,
    M6FrameGate,
    M6PublishedComponent,
)


def build_classic_molecule_diagnostic_funnels(
    result: DomainAnalysisResult,
) -> tuple[MoleculeDiagnosticFunnel, ...]:
    """Materialize one complete immutable trace per classic-M6 molecule."""

    gate = result.m6_gate
    if gate is None:
        return ()
    abc_outcome = abc_classifier_outcome(result.classifier_outcomes)
    classifications = {
        (value.frame_index, value.source_id): value
        for value in (() if abc_outcome is None else abc_outcome.molecule_classifications)
    }
    funnels = []
    for frame in gate.frames:
        if (
            frame.backend_identity.backend_id
            != M6_ORIENTATION_COMPONENTS_BACKEND_ID
        ):
            continue
        if not isinstance(frame.native_evidence, M6OrientationComponentsEvidence):
            raise TypeError("Classic M6 diagnostics require classic native evidence.")
        molecules = _molecules_by_id(frame)
        for source_id in frame.analyzed_source_ids:
            funnels.append(_build_funnel(
                frame,
                molecules[source_id],
                frame.native_evidence,
                classifications.get((frame.frame_index, source_id)),
                abc_outcome,
            ))
    return tuple(funnels)


def _build_funnel(
    frame: M6FrameGate,
    molecule: M6PublishedMolecule,
    native: M6OrientationComponentsEvidence,
    classification: MoleculeClassification | None,
    abc_outcome: ClassifierOutcome | None,
) -> MoleculeDiagnosticFunnel:
    source_id = molecule.source_id
    assignment = dict(native.assignment_status).get(source_id)
    local_status = dict(native.local_order_status).get(source_id)
    neighbor_count = dict(native.neighbor_count).get(source_id)
    q6 = dict(native.q6).get(source_id)
    orientation_deg = dict(native.orientation_deg).get(source_id)
    native_component_type = dict(native.component_type).get(source_id)
    partition, component = _partition(frame, source_id)
    raw_centroid_x, raw_centroid_y = raw_centroid_values(molecule)
    stages = [
        completed_diagnostic_stage(
            frame, "source_input", "accepted",
            reason=DiagnosticReason("accepted", "accepted_result"),
            evidence=DiagnosticEvidence(SourceInputEvidence(
                molecule.source_kind, raw_centroid_x, raw_centroid_y
            )),
            provenance=DiagnosticProvenanceContext("canonicalize_frame"),
        ),
        completed_diagnostic_stage(
            frame, "centroid", "accepted",
            reason=DiagnosticReason("accepted", "accepted_result"),
            evidence=DiagnosticEvidence(CentroidEvidence(
                molecule.point_xy_nm[0], molecule.point_xy_nm[1],
                frame.coordinate_frame,
            )),
            provenance=DiagnosticProvenanceContext("canonicalize_frame"),
        ),
        completed_diagnostic_stage(
            frame, "sample_coordinates", "accepted",
            reason=DiagnosticReason("accepted", "accepted_result"),
            evidence=DiagnosticEvidence(SampleCoordinatesEvidence(
                molecule.point_xy_nm[0], molecule.point_xy_nm[1],
                frame.coordinate_transform_fingerprint,
            )),
            provenance=DiagnosticProvenanceContext("canonicalize_frame"),
        ),
        _first_shell_stage(frame, neighbor_count, local_status),
        _local_order_stage(frame, q6, orientation_deg, local_status),
        unavailable_diagnostic_stage(
            "local_symmetry", "backend_capability_absent"
        ),
        unavailable_diagnostic_stage(
            "domain_edges", "backend_capability_absent"
        ),
        _seed_growth_stage(frame, assignment),
        _partition_stage(
            frame, partition, component, assignment, native_component_type
        ),
        _domain_size_stage(frame, partition, component),
    ]
    stages.extend(classic_orientation_stages(
        frame, molecule, partition, classification, abc_outcome
    ))
    stages.append(not_run_diagnostic_stage(
        "manual_correction", "no_manual_decision"
    ))
    stages.append(classic_effective_result_stage(
        frame, partition, classification, abc_outcome
    ))
    return MoleculeDiagnosticFunnel(
        frame_index=frame.frame_index,
        physical_frame_id=frame.physical_frame_id,
        source_id=source_id,
        backend_identity=frame.backend_identity,
        stages=tuple(stages),
    )


def _first_shell_stage(
    frame: M6FrameGate,
    neighbor_count: int | None,
    local_status: str | None,
) -> DiagnosticStageResult:
    if neighbor_count is None:
        return unavailable_diagnostic_stage(
            "first_shell", "evidence_not_retained"
        )
    rejected = local_status == "insufficient_neighbors"
    return completed_diagnostic_stage(
        frame, "first_shell", "rejected" if rejected else "accepted",
        reason=DiagnosticReason(
            "threshold" if rejected else "accepted",
            "below_minimum_neighbors" if rejected else "accepted_result",
        ),
        evidence=DiagnosticEvidence(FirstShellEvidence(neighbor_count)),
        provenance=DiagnosticProvenanceContext("build_first_shell_graph"),
    )


def _local_order_stage(
    frame: M6FrameGate,
    q6: float | None,
    orientation_deg: float | None,
    local_status: str | None,
) -> DiagnosticStageResult:
    if local_status is None and q6 is None:
        return unavailable_diagnostic_stage(
            "local_order", "evidence_not_retained"
        )
    accepted = local_status in {None, "valid_order"} and q6 is not None
    reason_code = "accepted_result" if accepted else (
        local_status or "local_order_unavailable"
    )
    return completed_diagnostic_stage(
        frame, "local_order", "accepted" if accepted else "rejected",
        reason=DiagnosticReason(
            "accepted" if accepted else "insufficient_evidence", reason_code
        ),
        evidence=DiagnosticEvidence(LocalOrderEvidence(
            q6, orientation_deg, local_status
        )),
        provenance=DiagnosticProvenanceContext(
            "compute_local_sixfold_bond_order"
        ),
    )


def _seed_growth_stage(
    frame: M6FrameGate,
    assignment_status: str | None,
) -> DiagnosticStageResult:
    if assignment_status is None:
        return unavailable_diagnostic_stage(
            "seed_growth", "evidence_not_retained"
        )
    decision: DiagnosticDecision = "accepted"
    category: DiagnosticReasonCategory = "accepted"
    reason_code = "accepted_result"
    if assignment_status == "boundary_or_disordered":
        decision = "ambiguous"
        category = "insufficient_evidence"
        reason_code = assignment_status
    elif assignment_status != "assigned":
        decision = "rejected"
        category = "insufficient_evidence"
        reason_code = assignment_status
    return completed_diagnostic_stage(
        frame, "seed_growth", decision,
        reason=DiagnosticReason(category, reason_code, assignment_status),
        evidence=DiagnosticEvidence(SeedGrowthEvidence(assignment_status)),
        provenance=DiagnosticProvenanceContext(
            "analyze_m6_orientation_domains"
        ),
    )


def _partition_stage(
    frame: M6FrameGate,
    partition: str,
    component: M6PublishedComponent | None,
    assignment_status: str | None,
    native_component_type: str | None,
) -> DiagnosticStageResult:
    if partition == "full_domain":
        decision: DiagnosticDecision = "accepted"
        category: DiagnosticReasonCategory = "accepted"
        code = "accepted_result"
    elif partition == "small_ordered_island":
        decision, category, code = (
            "filtered", "postprocess", "small_ordered_island"
        )
    else:
        decision, category, code = (
            "rejected",
            "insufficient_evidence" if assignment_status else "missing_data",
            assignment_status or "native_assignment_not_retained",
        )
    return completed_diagnostic_stage(
        frame, "domain_partition", decision,
        reason=DiagnosticReason(category, code, assignment_status),
        evidence=DiagnosticEvidence(DomainPartitionEvidence(
            partition,
            (
                None if component is None else component.lattice_domain_id
            ),
            native_component_type,
        )),
        provenance=DiagnosticProvenanceContext(
            "analyze_m6_orientation_domains"
        ),
    )


def _domain_size_stage(
    frame: M6FrameGate,
    partition: str,
    component: M6PublishedComponent | None,
) -> DiagnosticStageResult:
    if component is None:
        return not_run_diagnostic_stage(
            "domain_size", "upstream_not_assigned"
        )
    filtered = partition == "small_ordered_island"
    return completed_diagnostic_stage(
        frame, "domain_size", "filtered" if filtered else "accepted",
        reason=DiagnosticReason(
            "postprocess" if filtered else "accepted",
            "component_below_minimum_size" if filtered else "accepted_result",
        ),
        evidence=DiagnosticEvidence(DomainSizeEvidence(
            component.component_type, len(component.source_ids)
        )),
        provenance=DiagnosticProvenanceContext(
            "finalize_m6_orientation_domains"
        ),
    )


def _molecules_by_id(frame: M6FrameGate) -> dict[str, M6PublishedMolecule]:
    return {
        molecule.source_id: molecule
        for molecule in (
            tuple(
                member
                for component in frame.full_domains + frame.small_ordered_islands
                for member in component.members
            )
            + frame.outside_members
        )
    }


def _partition(
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
