from __future__ import annotations

from moltrack.analysis.first_shell_graph import FIRST_SHELL_GRAPH_ALGORITHM_VERSION
from moltrack.analysis.lattice_domain_edge_models import (
    LATTICE_DOMAIN_EDGE_COMPATIBILITY_ALGORITHM_VERSION,
)
from moltrack.analysis.lattice_domain_models import (
    LATTICE_DOMAIN_ANALYSIS_ALGORITHM_VERSION,
)
from moltrack.analysis.lattice_domain_seed_growth_models import (
    LATTICE_DOMAIN_SEED_GROWTH_ALGORITHM_VERSION,
)
from moltrack.analysis.local_multisymmetry_bond_order import (
    LOCAL_MULTI_SYMMETRY_BOND_ORDER_ALGORITHM_VERSION,
)
from moltrack.analysis.local_symmetry_evidence_models import (
    LOCAL_SYMMETRY_EVIDENCE_ALGORITHM_VERSION,
)

from .backend_contract import (
    M3M6LatticeDomainEvidence,
    M3M6LatticeNetworkEvidence,
    M3M6LatticePointEvidence,
)
from .classifier_models import ClassifierOutcome, MoleculeClassification
from .classic_orientation_diagnostic import (
    abc_classifier_outcome,
    classic_effective_result_stage,
    classic_orientation_stages,
)
from .diagnostic_funnel_builders import (
    completed_diagnostic_stage,
    molecules_by_id,
    not_run_diagnostic_stage,
    published_partition,
    source_coordinate_stages,
    unavailable_diagnostic_stage,
)
from .diagnostic_funnel_models import (
    DiagnosticDecision,
    DiagnosticEvidence,
    DiagnosticProvenanceContext,
    DiagnosticReason,
    DiagnosticReasonCategory,
    DiagnosticStageResult,
    MoleculeDiagnosticFunnel,
)
from .diagnostic_network_evidence import (
    NetworkDomainEdgesEvidence,
    NetworkDomainPartitionEvidence,
    NetworkDomainSizeEvidence,
    NetworkFirstShellEvidence,
    NetworkLocalOrderEvidence,
    NetworkLocalSymmetryEvidence,
    NetworkSeedGrowthEvidence,
)
from .geometry import M6PublishedMolecule
from .models import DomainAnalysisResult, M6FrameGate


_ALGORITHM_VERSION_BY_FINGERPRINT = {
    "first_shell_graph": FIRST_SHELL_GRAPH_ALGORITHM_VERSION,
    "local_order": LOCAL_MULTI_SYMMETRY_BOND_ORDER_ALGORITHM_VERSION,
    "local_symmetry": LOCAL_SYMMETRY_EVIDENCE_ALGORITHM_VERSION,
    "domain_edges": LATTICE_DOMAIN_EDGE_COMPATIBILITY_ALGORITHM_VERSION,
    "seed_growth": LATTICE_DOMAIN_SEED_GROWTH_ALGORITHM_VERSION,
    "lattice_domain": LATTICE_DOMAIN_ANALYSIS_ALGORITHM_VERSION,
}


def build_network_molecule_diagnostic_funnels(
    result: DomainAnalysisResult,
) -> tuple[MoleculeDiagnosticFunnel, ...]:
    """Materialize the network backend trace from retained native outputs."""

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
        native = frame.native_evidence
        if not isinstance(native, M3M6LatticeNetworkEvidence):
            continue
        molecules = molecules_by_id(frame)
        point_by_id = {value.source_id: value for value in native.point_evidence}
        for source_id in frame.analyzed_source_ids:
            funnels.append(_build_funnel(
                frame,
                molecules[source_id],
                native,
                point_by_id.get(source_id),
                classifications.get((frame.frame_index, source_id)),
                abc_outcome,
            ))
    return tuple(funnels)


def _build_funnel(
    frame: M6FrameGate,
    molecule: M6PublishedMolecule,
    native: M3M6LatticeNetworkEvidence,
    point: M3M6LatticePointEvidence | None,
    classification: MoleculeClassification | None,
    abc_outcome: ClassifierOutcome | None,
) -> MoleculeDiagnosticFunnel:
    partition, component = published_partition(frame, molecule.source_id)
    native_domain_id = dict(native.point_domain_ids).get(molecule.source_id)
    domain = _domain(native, native_domain_id)
    fingerprints = dict(native.producer_fingerprints)
    if point is None:
        native_stages = tuple(
            unavailable_diagnostic_stage(stage_id, "evidence_not_retained")
            for stage_id in (
                "first_shell", "local_order", "local_symmetry", "domain_edges",
                "seed_growth", "domain_partition", "domain_size",
            )
        )
    else:
        native_stages = (
            _first_shell_stage(frame, point, fingerprints),
            _local_order_stage(frame, point, fingerprints),
            _local_symmetry_stage(frame, point, fingerprints),
            _domain_edges_stage(frame, point, fingerprints),
            _seed_growth_stage(frame, point, native, fingerprints),
            _partition_stage(
                frame, native, point, partition, native_domain_id, domain,
                fingerprints,
            ),
            _domain_size_stage(frame, partition, domain, native, fingerprints),
        )
    stages = [*source_coordinate_stages(frame, molecule), *native_stages]
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
        source_id=molecule.source_id,
        backend_identity=frame.backend_identity,
        stages=tuple(stages),
    )


def _first_shell_stage(
    frame: M6FrameGate,
    point: M3M6LatticePointEvidence,
    fingerprints: dict[str, str],
) -> DiagnosticStageResult:
    rejected = point.computation_status != "valid_order"
    return completed_diagnostic_stage(
        frame, "first_shell", "rejected" if rejected else "accepted",
        reason=DiagnosticReason(
            "insufficient_evidence" if rejected else "accepted",
            point.computation_status if rejected else "accepted_result",
        ),
        evidence=DiagnosticEvidence(NetworkFirstShellEvidence(
            point.neighbor_count,
            point.first_shell_construction_method,
            point.first_shell_qc_status,
            point.physical_duplicate_qc,
            point.geometry_duplicate_qc,
            point.edge_truncated_neighborhood,
        )),
        provenance=_provenance(
            "build_first_shell_graph", "first_shell_graph", fingerprints
        ),
    )


def _local_order_stage(
    frame: M6FrameGate,
    point: M3M6LatticePointEvidence,
    fingerprints: dict[str, str],
) -> DiagnosticStageResult:
    rejected = point.computation_status != "valid_order"
    return completed_diagnostic_stage(
        frame, "local_order", "rejected" if rejected else "accepted",
        reason=DiagnosticReason(
            "insufficient_evidence" if rejected else "accepted",
            point.computation_status if rejected else "local_m3_m6_available",
            point.computation_status,
        ),
        evidence=DiagnosticEvidence(NetworkLocalOrderEvidence(
            point.q3, point.q6, point.theta3_lattice_deg, point.theta6_deg,
            point.m3_orientation_status, point.m6_orientation_status,
            point.m3_orientation_confidence, point.m6_orientation_confidence,
            point.computation_status, point.symmetry_resolvability_status,
        )),
        provenance=_provenance(
            "compute_local_multisymmetry_bond_order", "local_order", fingerprints
        ),
    )


def _local_symmetry_stage(
    frame: M6FrameGate,
    point: M3M6LatticePointEvidence,
    fingerprints: dict[str, str],
) -> DiagnosticStageResult:
    if point.best_model == "ambiguous":
        decision: DiagnosticDecision = "ambiguous"
        category: DiagnosticReasonCategory = "conflict"
    elif point.best_model == "unavailable":
        decision, category = "rejected", "insufficient_evidence"
    else:
        decision, category = "accepted", "accepted"
    return completed_diagnostic_stage(
        frame, "local_symmetry", decision,
        reason=DiagnosticReason(
            category, point.classification_reason, point.classification_reason
        ),
        evidence=DiagnosticEvidence(NetworkLocalSymmetryEvidence(
            point.trifold_model_score, point.sixfold_model_score,
            point.mixed_model_score, point.disordered_model_score,
            point.best_model, point.second_best_margin,
            point.expected_direction_coverage, point.classification_confidence,
            point.classification_reason, point.winning_model_orientation_deg,
        )),
        provenance=_provenance(
            "classify_local_symmetry_evidence", "local_symmetry", fingerprints
        ),
    )


def _domain_edges_stage(
    frame: M6FrameGate,
    point: M3M6LatticePointEvidence,
    fingerprints: dict[str, str],
) -> DiagnosticStageResult:
    if point.retained_edge_count:
        decision: DiagnosticDecision = "accepted"
        category: DiagnosticReasonCategory = "accepted"
        reason = "retained_domain_edge"
    else:
        decision, category = "rejected", "insufficient_evidence"
        reason = (
            point.incident_edge_rejection_reasons[0]
            if point.incident_edge_rejection_reasons
            else "no_incident_first_shell_edges"
        )
    return completed_diagnostic_stage(
        frame, "domain_edges", decision,
        reason=DiagnosticReason(category, reason, reason),
        evidence=DiagnosticEvidence(NetworkDomainEdgesEvidence(
            len(point.incident_edge_decisions), point.incident_edge_decisions,
            point.incident_edge_rejection_reasons, point.retained_edge_count,
            point.core_eligible_edge_count,
        )),
        provenance=_provenance(
            "build_lattice_domain_edge_compatibility", "domain_edges", fingerprints
        ),
    )


def _seed_growth_stage(
    frame: M6FrameGate,
    point: M3M6LatticePointEvidence,
    native: M3M6LatticeNetworkEvidence,
    fingerprints: dict[str, str],
) -> DiagnosticStageResult:
    role = dict(native.point_roles)[point.source_id]
    boundary_reason = dict(native.boundary_reasons)[point.source_id]
    if role in {"core", "halo"}:
        decision: DiagnosticDecision = "accepted"
        category: DiagnosticReasonCategory = "accepted"
        reason = f"assigned_{role}"
    elif role == "boundary":
        decision, category = "rejected", "conflict"
        reason = boundary_reason or "explicit_boundary"
    else:
        decision, category = "rejected", "insufficient_evidence"
        reason = "unassigned_by_seed_growth"
    return completed_diagnostic_stage(
        frame, "seed_growth", decision,
        reason=DiagnosticReason(category, reason, boundary_reason),
        evidence=DiagnosticEvidence(NetworkSeedGrowthEvidence(
            role, point.seed_component_id, point.seed_state, boundary_reason,
            point.growth_iteration_count, point.stable_threshold_offsets,
        )),
        provenance=_provenance(
            "build_lattice_domain_seed_growth", "seed_growth", fingerprints
        ),
    )


def _partition_stage(
    frame: M6FrameGate,
    native: M3M6LatticeNetworkEvidence,
    point: M3M6LatticePointEvidence,
    partition: str,
    domain_id: str | None,
    domain: M3M6LatticeDomainEvidence | None,
    fingerprints: dict[str, str],
) -> DiagnosticStageResult:
    if partition == "full_domain":
        decision: DiagnosticDecision = "accepted"
        category: DiagnosticReasonCategory = "accepted"
        reason = "accepted_result"
    elif partition == "small_ordered_island":
        decision, category, reason = "filtered", "postprocess", partition
    else:
        decision, category, reason = (
            "rejected", "insufficient_evidence", "not_a_domain_member"
        )
    return completed_diagnostic_stage(
        frame, "domain_partition", decision,
        reason=DiagnosticReason(category, reason),
        evidence=DiagnosticEvidence(NetworkDomainPartitionEvidence(
            partition, domain_id,
            point_role=dict(native.point_roles)[point.source_id],
            component_type=None if domain is None else domain.component_type,
            domain_qc_flags=None if domain is None else domain.qc_flags,
        )),
        provenance=_provenance(
            "build_lattice_domain_analysis", "lattice_domain", fingerprints
        ),
    )


def _domain_size_stage(
    frame: M6FrameGate,
    partition: str,
    domain: M3M6LatticeDomainEvidence | None,
    native: M3M6LatticeNetworkEvidence,
    fingerprints: dict[str, str],
) -> DiagnosticStageResult:
    if native.minimum_domain_size is None:
        return unavailable_diagnostic_stage(
            "domain_size", "threshold_not_retained"
        )
    if partition == "full_domain":
        decision: DiagnosticDecision = "accepted"
        category: DiagnosticReasonCategory = "accepted"
        reason = "accepted_result"
    elif partition == "small_ordered_island":
        decision, category, reason = (
            "filtered", "postprocess", "component_below_minimum_size"
        )
    else:
        decision, category, reason = (
            "rejected", "insufficient_evidence", "not_a_domain_member"
        )
    return completed_diagnostic_stage(
        frame, "domain_size", decision,
        reason=DiagnosticReason(category, reason),
        evidence=DiagnosticEvidence(NetworkDomainSizeEvidence(
            component_type=None if domain is None else domain.component_type,
            component_molecule_count=None if domain is None else domain.molecule_count,
            minimum_domain_size=native.minimum_domain_size,
            core_size=None if domain is None else domain.core_size,
            halo_size=None if domain is None else domain.halo_size,
            adjacent_boundary_point_count=(
                None if domain is None else domain.adjacent_boundary_point_count
            ),
            domain_qc_flags=None if domain is None else domain.qc_flags,
        )),
        provenance=_provenance(
            "build_lattice_domain_analysis", "lattice_domain", fingerprints
        ),
    )


def _domain(
    native: M3M6LatticeNetworkEvidence,
    domain_id: str | None,
) -> M3M6LatticeDomainEvidence | None:
    return next(
        (value for value in native.domains if value.lattice_domain_id == domain_id),
        None,
    )


def _provenance(
    producer: str,
    fingerprint_key: str,
    fingerprints: dict[str, str],
) -> DiagnosticProvenanceContext:
    return DiagnosticProvenanceContext(
        producer,
        algorithm_version=_ALGORITHM_VERSION_BY_FINGERPRINT[fingerprint_key],
        output_fingerprint=fingerprints.get(fingerprint_key),
    )
