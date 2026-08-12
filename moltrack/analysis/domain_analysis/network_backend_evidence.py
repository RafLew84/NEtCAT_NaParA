from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Literal, cast, get_args

from moltrack.analysis.first_shell_graph import FirstShellConstructionMethod
from moltrack.analysis.lattice_domain_edge_models import (
    LatticeDomainEdgeDecision,
    LatticeDomainEdgeRejectionReason,
    lattice_domain_edge_is_retained,
)
from moltrack.analysis.lattice_domain_models import (
    LatticeDomainComponentType,
    LatticeDomainDominantSymmetry,
    LatticeDomainOrientationReferenceChannel,
    M3M6OrientationRelationStatus,
)
from moltrack.analysis.lattice_domain_seed_growth_models import (
    LatticeDomainBoundaryReason,
    LatticeDomainPointRole,
    LatticeDomainSeedState,
)
from moltrack.analysis.local_multisymmetry_bond_order import (
    LocalMultiSymmetryOrientationStatus,
    SymmetryResolvabilityStatus,
)
from moltrack.analysis.local_sixfold_bond_order import LocalOrderComputationStatus
from moltrack.analysis.local_symmetry_evidence_models import (
    LocalSymmetryClassificationReason,
    LocalSymmetryModel,
)


_ALLOWED_VALUES = {
    "first_shell_construction_method": set(get_args(FirstShellConstructionMethod)),
    "m3_orientation_status": set(get_args(LocalMultiSymmetryOrientationStatus)),
    "m6_orientation_status": set(get_args(LocalMultiSymmetryOrientationStatus)),
    "computation_status": set(get_args(LocalOrderComputationStatus)),
    "symmetry_resolvability_status": set(get_args(SymmetryResolvabilityStatus)),
    "best_model": set(get_args(LocalSymmetryModel)),
    "classification_reason": set(get_args(LocalSymmetryClassificationReason)),
    "seed_state": set(get_args(LatticeDomainSeedState)),
}
_POINT_ROLES = set(get_args(LatticeDomainPointRole))
_BOUNDARY_REASONS = set(get_args(LatticeDomainBoundaryReason))
_EDGE_DECISIONS = set(get_args(LatticeDomainEdgeDecision))
_EDGE_REJECTION_REASONS = set(get_args(LatticeDomainEdgeRejectionReason))
_DOMAIN_VALUES = {
    "component_type": set(get_args(LatticeDomainComponentType)),
    "dominant_symmetry": set(get_args(LatticeDomainDominantSymmetry)),
    "orientation_reference_channel": set(
        get_args(LatticeDomainOrientationReferenceChannel)
    ),
    "m3_m6_orientation_relation_status": set(
        get_args(M3M6OrientationRelationStatus)
    ),
}


@dataclass(frozen=True)
class M3M6LatticeDomainEvidence:
    """Readable native classification, size, and QC for one component."""

    lattice_domain_id: str
    dominant_symmetry: str
    confidence: float
    qc_flags: tuple[str, ...]
    orientation_reference_channel: str
    m3_m6_orientation_relation_status: str
    provenance_fingerprint: str
    component_type: str | None = None
    molecule_count: int | None = None
    core_size: int | None = None
    halo_size: int | None = None
    adjacent_boundary_point_count: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "lattice_domain_id", _text(self.lattice_domain_id, "lattice_domain_id")
        )
        object.__setattr__(
            self, "provenance_fingerprint",
            _text(self.provenance_fingerprint, "provenance_fingerprint"),
        )
        for name in (
            "dominant_symmetry", "orientation_reference_channel",
            "m3_m6_orientation_relation_status",
        ):
            object.__setattr__(
                self, name, _choice(getattr(self, name), name, _DOMAIN_VALUES[name])
            )
        confidence = _optional_finite(self.confidence, "confidence")
        if confidence is None or not 0.0 <= confidence <= 1.0:
            raise ValueError("confidence must be between zero and one.")
        object.__setattr__(self, "confidence", confidence)
        object.__setattr__(self, "qc_flags", tuple(sorted({
            _text(value, "qc_flag") for value in self.qc_flags
        })))
        if self.component_type is not None:
            object.__setattr__(self, "component_type", _choice(
                self.component_type, "component_type", _DOMAIN_VALUES["component_type"]
            ))
        for name in (
            "molecule_count", "core_size", "halo_size",
            "adjacent_boundary_point_count",
        ):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, _non_negative_integer(value, name))


@dataclass(frozen=True)
class M3M6LatticePointEvidence:
    """Source-aligned observations retained from every network stage."""

    source_id: str
    neighbor_count: int
    first_shell_construction_method: str
    first_shell_qc_status: str
    physical_duplicate_qc: bool
    geometry_duplicate_qc: bool
    edge_truncated_neighborhood: bool
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
    incident_edge_decisions: tuple[str, ...]
    incident_edge_rejection_reasons: tuple[str, ...]
    retained_edge_count: int
    core_eligible_edge_count: int
    seed_component_id: int | None
    seed_state: str | None
    growth_iteration_count: int
    stable_threshold_offsets: tuple[int, ...] | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_id", _text(self.source_id, "source_id"))
        object.__setattr__(
            self, "first_shell_qc_status",
            _text(self.first_shell_qc_status, "first_shell_qc_status"),
        )
        for name, allowed in _ALLOWED_VALUES.items():
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, _choice(value, name, allowed))
        for name in (
            "neighbor_count", "retained_edge_count", "core_eligible_edge_count",
            "growth_iteration_count",
        ):
            object.__setattr__(self, name, _non_negative_integer(getattr(self, name), name))
        if self.seed_component_id is not None:
            object.__setattr__(self, "seed_component_id", _non_negative_integer(
                self.seed_component_id, "seed_component_id"
            ))
        for name in (
            "q3", "q6", "theta3_lattice_deg", "theta6_deg",
            "m3_orientation_confidence", "m6_orientation_confidence",
            "trifold_model_score", "sixfold_model_score", "mixed_model_score",
            "disordered_model_score", "second_best_margin",
            "expected_direction_coverage", "classification_confidence",
            "winning_model_orientation_deg",
        ):
            object.__setattr__(self, name, _optional_finite(getattr(self, name), name))
        for name in (
            "physical_duplicate_qc", "geometry_duplicate_qc",
            "edge_truncated_neighborhood",
        ):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} must be a boolean.")
        object.__setattr__(self, "incident_edge_decisions", tuple(
            _choice(value, "incident_edge_decision", _EDGE_DECISIONS)
            for value in self.incident_edge_decisions
        ))
        object.__setattr__(self, "incident_edge_rejection_reasons", tuple(
            _choice(value, "incident_edge_rejection_reason", _EDGE_REJECTION_REASONS)
            for value in self.incident_edge_rejection_reasons
        ))
        offsets = (
            None if self.stable_threshold_offsets is None
            else tuple(self.stable_threshold_offsets)
        )
        if offsets is not None and (
            any(value not in {-1, 0, 1} for value in offsets)
            or len(set(offsets)) != len(offsets)
        ):
            raise ValueError(
                "stable_threshold_offsets must contain unique -1, 0, or 1 values."
            )
        object.__setattr__(self, "stable_threshold_offsets", offsets)


@dataclass(frozen=True)
class M3M6LatticeNetworkEvidence:
    """Backend-native point, domain, and producer evidence."""

    point_roles: tuple[tuple[str, str], ...]
    boundary_reasons: tuple[tuple[str, str | None], ...]
    point_domain_ids: tuple[tuple[str, str | None], ...]
    domains: tuple[M3M6LatticeDomainEvidence, ...]
    producer_fingerprints: tuple[tuple[str, str], ...]
    point_evidence: tuple[M3M6LatticePointEvidence, ...] = ()
    minimum_domain_size: int | None = None
    kind: Literal["m3_m6_lattice_evidence_v1"] = "m3_m6_lattice_evidence_v1"

    def __post_init__(self) -> None:
        roles = tuple(sorted(
            (_text(key, "point role source_id"), _choice(value, "point_role", _POINT_ROLES))
            for key, value in self.point_roles
        ))
        reasons = tuple(sorted(
            (_text(key, "boundary source_id"), None if value is None else _choice(
                value, "boundary_reason", _BOUNDARY_REASONS
            ))
            for key, value in self.boundary_reasons
        ))
        domain_ids = tuple(sorted(
            (_text(key, "point domain source_id"), None if value is None else _text(
                value, "point domain ID"
            ))
            for key, value in self.point_domain_ids
        ))
        domains = tuple(sorted(self.domains, key=lambda value: value.lattice_domain_id))
        if any(not isinstance(value, M3M6LatticeDomainEvidence) for value in domains):
            raise TypeError("domains must contain M3M6LatticeDomainEvidence values.")
        fingerprints = _text_pairs(self.producer_fingerprints, "producer_fingerprints")
        points = tuple(sorted(self.point_evidence, key=lambda value: value.source_id))
        if any(not isinstance(value, M3M6LatticePointEvidence) for value in points):
            raise TypeError("point_evidence must contain M3M6LatticePointEvidence values.")
        for name, values in (
            ("point_roles", roles), ("boundary_reasons", reasons),
            ("point_domain_ids", domain_ids), ("producer_fingerprints", fingerprints),
        ):
            _unique_first_values(values, name)
        source_ids = tuple(value[0] for value in roles)
        if any(source_ids != tuple(value[0] for value in values) for values in (
            reasons, domain_ids
        )):
            raise ValueError("Network point evidence fields must align by source ID.")
        if len({value.lattice_domain_id for value in domains}) != len(domains):
            raise ValueError("Network domain evidence IDs must be unique.")
        if points and tuple(value.source_id for value in points) != source_ids:
            raise ValueError("point_evidence must align with network source IDs.")
        minimum_size = self.minimum_domain_size
        if minimum_size is not None:
            minimum_size = _non_negative_integer(minimum_size, "minimum_domain_size")
            if minimum_size == 0:
                raise ValueError("minimum_domain_size must be positive.")
        _validate_detail(
            roles, reasons, domain_ids, domains, fingerprints, points, minimum_size
        )
        for name, value in (
            ("point_roles", roles), ("boundary_reasons", reasons),
            ("point_domain_ids", domain_ids), ("domains", domains),
            ("producer_fingerprints", fingerprints), ("point_evidence", points),
            ("minimum_domain_size", minimum_size),
        ):
            object.__setattr__(self, name, value)


def _validate_detail(
    roles: tuple[tuple[str, str], ...],
    reasons: tuple[tuple[str, str | None], ...],
    domain_ids: tuple[tuple[str, str | None], ...],
    domains: tuple[M3M6LatticeDomainEvidence, ...],
    fingerprints: tuple[tuple[str, str], ...],
    points: tuple[M3M6LatticePointEvidence, ...],
    minimum_size: int | None,
) -> None:
    if not points:
        return
    required = {
        "first_shell_graph", "local_order", "local_symmetry", "domain_edges",
        "seed_growth", "lattice_domain",
    }
    if not required.issubset(dict(fingerprints)):
        raise ValueError("Detailed network evidence requires every stage producer fingerprint.")
    if minimum_size is None:
        raise ValueError("Detailed network evidence requires minimum_domain_size.")
    domain_by_id = {value.lattice_domain_id: value for value in domains}
    role_by_id = dict(roles)
    reason_by_id = dict(reasons)
    point_by_id = {value.source_id: value for value in points}
    for source_id, domain_id in domain_ids:
        role = role_by_id[source_id]
        point = point_by_id[source_id]
        reason = reason_by_id[source_id]
        if (role == "boundary") != (reason is not None):
            raise ValueError("Only boundary points require a boundary_reason.")
        if (role in {"core", "halo"}) != (domain_id is not None):
            raise ValueError("Only core/halo points may reference a lattice domain.")
        if domain_id is not None and domain_id not in domain_by_id:
            raise ValueError("point_domain_ids references an unknown lattice domain.")
        assigned = role in {"core", "halo"}
        if assigned != (
            point.seed_component_id is not None and point.seed_state is not None
        ):
            raise ValueError("Core/halo points require seed component and state.")
        if not assigned and point.stable_threshold_offsets is not None:
            raise ValueError("Unassigned points cannot publish seed stability.")
    for domain_id, domain in domain_by_id.items():
        members = tuple(key for key, value in domain_ids if value == domain_id)
        core_size = sum(role_by_id[value] == "core" for value in members)
        halo_size = sum(role_by_id[value] == "halo" for value in members)
        if None in (
            domain.component_type, domain.molecule_count, domain.core_size,
            domain.halo_size,
        ):
            raise ValueError("Detailed domain evidence requires size and type metrics.")
        if (
            domain.molecule_count != len(members) or domain.core_size != core_size
            or domain.halo_size != halo_size
            or domain.molecule_count != domain.core_size + domain.halo_size
        ):
            raise ValueError("Domain size metrics must match point roles and membership.")
    for point in points:
        edge_count = len(point.incident_edge_decisions)
        retained_count = sum(
            lattice_domain_edge_is_retained(
                cast(LatticeDomainEdgeDecision, value)
            )
            for value in point.incident_edge_decisions
        )
        core_candidate_count = sum(
            value in {
                "compatible_trifold", "compatible_sixfold", "compatible_mixed"
            }
            for value in point.incident_edge_decisions
        )
        if (
            point.retained_edge_count != retained_count
            or point.core_eligible_edge_count > core_candidate_count
            or point.core_eligible_edge_count > point.retained_edge_count
            or len(point.incident_edge_rejection_reasons)
            != edge_count - retained_count
        ):
            raise ValueError("Point edge aggregates contradict incident edge evidence.")


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be non-empty text.")
    return value.strip()


def _choice(value: object, name: str, allowed: set[object]) -> str:
    normalized = _text(value, name)
    if normalized not in allowed:
        raise ValueError(f"Unsupported {name}: {normalized!r}.")
    return normalized


def _text_pairs(
    values: tuple[tuple[str, str], ...], name: str
) -> tuple[tuple[str, str], ...]:
    return tuple(sorted(
        (_text(first, f"{name} key"), _text(second, f"{name} value"))
        for first, second in values
    ))


def _unique_first_values(values: tuple[tuple[object, object], ...], name: str) -> None:
    if len({value[0] for value in values}) != len(values):
        raise ValueError(f"{name} keys must be unique.")


def _optional_finite(value: object, name: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be numeric or None.")
    normalized = float(value)
    if not isfinite(normalized):
        raise ValueError(f"{name} must be finite.")
    return normalized


def _non_negative_integer(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer.")
    return value
