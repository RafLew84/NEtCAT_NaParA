from __future__ import annotations

from dataclasses import asdict

from moltrack.analysis._first_shell_graph_fingerprint import (
    first_shell_graph_fingerprint,
)
from moltrack.analysis.domain_analysis import (
    M3M6LatticeDomainEvidence,
    M3M6LatticeNetworkEvidence,
    M3M6LatticePointEvidence,
)
from moltrack.analysis.domain_analysis.fingerprints import canonical_sha256
from moltrack.analysis.lattice_domain_models import (
    LatticeDomain,
    lattice_domain_analysis_fingerprint,
)
from moltrack.analysis.lattice_domain_seed_growth_models import (
    lattice_domain_seed_growth_result_fingerprint,
)
from moltrack.analysis.molecular_m6_analysis import MolecularM6OrientationAnalysis
from moltrack.analysis.local_multisymmetry_bond_order import (
    local_multisymmetry_bond_order_fingerprint,
)
from moltrack.analysis.local_symmetry_evidence_models import (
    local_symmetry_evidence_fingerprint,
)


def lattice_network_evidence(
    analysis: MolecularM6OrientationAnalysis,
) -> M3M6LatticeNetworkEvidence:
    """Retain source-aligned outputs from the already-completed network pipeline."""

    lattice = analysis.lattice_domain_analysis
    local = analysis.local_multisymmetry_order
    symmetry = analysis.local_symmetry_evidence
    edges = analysis.lattice_domain_edge_compatibility
    seeds = analysis.lattice_domain_seed_growth
    if any(value is None for value in (lattice, local, symmetry, edges, seeds)):
        raise RuntimeError("M3/M6 lattice analysis did not publish native evidence.")
    assert lattice is not None
    assert local is not None
    assert symmetry is not None
    assert edges is not None
    assert seeds is not None
    graph = analysis.first_shell_graph
    points = tuple(
        _point_evidence(index, analysis)
        for index in range(graph.point_count)
    )
    return M3M6LatticeNetworkEvidence(
        point_roles=tuple(zip(lattice.source_ids, lattice.point_role)),
        boundary_reasons=tuple(zip(lattice.source_ids, lattice.boundary_reason)),
        point_domain_ids=tuple(zip(
            lattice.source_ids, lattice.point_lattice_domain_id
        )),
        domains=tuple(
            M3M6LatticeDomainEvidence(
                lattice_domain_id=component.lattice_domain_id,
                dominant_symmetry=component.dominant_symmetry,
                confidence=component.confidence,
                qc_flags=network_qc_flags(component),
                orientation_reference_channel=(
                    component.orientation_reference_channel
                ),
                m3_m6_orientation_relation_status=(
                    component.m3_m6_orientation_relation_status
                ),
                provenance_fingerprint=canonical_sha256(asdict(component)),
                component_type=component.component_type,
                molecule_count=component.molecule_count,
                core_size=component.core_size,
                halo_size=component.halo_size,
                adjacent_boundary_point_count=(
                    component.adjacent_boundary_point_count
                ),
            )
            for component in lattice.components
        ),
        producer_fingerprints=(
            ("first_shell_graph", first_shell_graph_fingerprint(graph)),
            ("local_order", local_multisymmetry_bond_order_fingerprint(local)),
            ("local_symmetry", local_symmetry_evidence_fingerprint(symmetry)),
            ("domain_edges", canonical_sha256(asdict(edges))),
            ("seed_growth", lattice_domain_seed_growth_result_fingerprint(seeds)),
            ("lattice_domain", lattice_domain_analysis_fingerprint(lattice)),
        ),
        point_evidence=points,
        minimum_domain_size=lattice.settings.min_domain_size,
    )


def _point_evidence(
    index: int,
    analysis: MolecularM6OrientationAnalysis,
) -> M3M6LatticePointEvidence:
    graph = analysis.first_shell_graph
    local = analysis.local_multisymmetry_order
    symmetry = analysis.local_symmetry_evidence
    edges = analysis.lattice_domain_edge_compatibility
    seeds = analysis.lattice_domain_seed_growth
    assert local is not None and symmetry is not None
    assert edges is not None and seeds is not None
    incident = tuple(
        edge_index
        for edge_index, (left, right) in enumerate(edges.edges_ij)
        if index in (left, right)
    )
    component_id = seeds.component_id[index]
    component = None if component_id < 0 else seeds.components[component_id]
    stable_offsets = None if component is None else tuple(
        item.threshold_offset for item in seeds.seed_support_stability
        if component_id in item.validated_component_ids
    )
    return M3M6LatticePointEvidence(
        source_id=graph.point_ids[index],
        neighbor_count=graph.degree[index],
        first_shell_construction_method=graph.construction_method,
        first_shell_qc_status=graph.qc_status,
        physical_duplicate_qc=graph.physical_duplicate_qc[index],
        geometry_duplicate_qc=graph.geometry_duplicate_qc[index],
        edge_truncated_neighborhood=local.edge_truncated_neighborhood[index],
        q3=local.q3[index],
        q6=local.q6[index],
        theta3_lattice_deg=local.theta3_lattice_deg[index],
        theta6_deg=local.theta6_deg[index],
        m3_orientation_status=local.m3_orientation_status[index],
        m6_orientation_status=local.m6_orientation_status[index],
        m3_orientation_confidence=local.m3_orientation_confidence[index],
        m6_orientation_confidence=local.m6_orientation_confidence[index],
        computation_status=local.computation_status[index],
        symmetry_resolvability_status=local.symmetry_resolvability_status[index],
        trifold_model_score=symmetry.trifold_model_score[index],
        sixfold_model_score=symmetry.sixfold_model_score[index],
        mixed_model_score=symmetry.mixed_model_score[index],
        disordered_model_score=symmetry.disordered_model_score[index],
        best_model=symmetry.best_model[index],
        second_best_margin=symmetry.second_best_margin[index],
        expected_direction_coverage=symmetry.expected_direction_coverage[index],
        classification_confidence=symmetry.classification_confidence[index],
        classification_reason=symmetry.classification_reason[index],
        winning_model_orientation_deg=(
            symmetry.winning_model_orientation_deg[index]
        ),
        incident_edge_decisions=tuple(edges.decision[value] for value in incident),
        incident_edge_rejection_reasons=tuple(
            reason for value in incident
            if (reason := edges.rejection_reason[value]) is not None
        ),
        retained_edge_count=sum(
            edges.retained_for_domain_growth[value] for value in incident
        ),
        core_eligible_edge_count=sum(
            edges.core_connectivity_eligible[value] for value in incident
        ),
        seed_component_id=None if component_id < 0 else component_id,
        seed_state=None if component is None else component.seed_state,
        growth_iteration_count=seeds.growth_iteration_count,
        stable_threshold_offsets=stable_offsets,
    )


def network_qc_flags(component: LatticeDomain) -> tuple[str, ...]:
    return tuple(sorted(
        name for name, value in asdict(component.qc).items() if value is True
    ))
