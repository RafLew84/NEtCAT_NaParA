from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar


@dataclass(frozen=True)
class NetworkFirstShellEvidence:
    evidence_kind: ClassVar[str] = "first_shell_graph_v1"
    neighbor_count: int
    construction_method: str
    graph_qc_status: str
    physical_duplicate_qc: bool
    geometry_duplicate_qc: bool
    edge_truncated_neighborhood: bool


@dataclass(frozen=True)
class NetworkLocalOrderEvidence:
    evidence_kind: ClassVar[str] = "local_multisymmetry_bond_order_v1"
    q3: float | None
    q6: float | None
    theta3_lattice_deg: float | None
    theta6_deg: float | None
    m3_orientation_status: str
    m6_orientation_status: str
    m3_orientation_confidence: float | None
    m6_orientation_confidence: float | None
    computation_status: str
    symmetry_resolvability_status: str


@dataclass(frozen=True)
class NetworkLocalSymmetryEvidence:
    evidence_kind: ClassVar[str] = "local_symmetry_evidence_v1"
    trifold_model_score: float | None
    sixfold_model_score: float | None
    mixed_model_score: float | None
    disordered_model_score: float | None
    best_model: str
    second_best_margin: float | None
    expected_direction_coverage: float | None
    classification_confidence: float | None
    classification_reason: str
    winning_model_orientation_deg: float | None


@dataclass(frozen=True)
class NetworkDomainEdgesEvidence:
    evidence_kind: ClassVar[str] = "lattice_domain_edge_compatibility_v2"
    incident_edge_count: int
    decisions: tuple[str, ...]
    rejection_reasons: tuple[str, ...]
    retained_edge_count: int
    core_eligible_edge_count: int


@dataclass(frozen=True)
class NetworkSeedGrowthEvidence:
    evidence_kind: ClassVar[str] = "lattice_domain_seed_growth_v1"
    point_role: str
    seed_component_id: int | None
    seed_state: str | None
    boundary_reason: str | None
    growth_iteration_count: int
    stable_threshold_offsets: tuple[int, ...] | None


@dataclass(frozen=True)
class NetworkDomainPartitionEvidence:
    evidence_kind: ClassVar[str] = "automatic_domain_membership_v1"
    partition: str
    lattice_domain_id: str | None
    point_role: str
    component_type: str | None
    domain_qc_flags: tuple[str, ...] | None


@dataclass(frozen=True)
class NetworkDomainSizeEvidence:
    evidence_kind: ClassVar[str] = "domain_size_decision_v1"
    component_type: str | None
    component_molecule_count: int | None
    minimum_domain_size: int
    core_size: int | None
    halo_size: int | None
    adjacent_boundary_point_count: int | None
    domain_qc_flags: tuple[str, ...] | None
