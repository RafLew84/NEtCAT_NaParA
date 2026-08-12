from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Literal, TypeAlias


M6_ORIENTATION_COMPONENTS_BACKEND_ID = "m6_orientation_components"
M3_M6_LATTICE_NETWORK_BACKEND_ID = "m3_m6_lattice_network"

DomainBackendId = Literal[
    "m6_orientation_components",
    "m3_m6_lattice_network",
]
NativeEvidenceKind = Literal[
    "m6_orientation_evidence_v1",
    "m3_m6_lattice_evidence_v1",
]


@dataclass(frozen=True)
class DomainBackendIdentity:
    """Complete computational identity of one domain backend adapter."""

    backend_id: str
    result_schema_version: str
    algorithm_version: str
    settings_fingerprint: str
    adapter_owner: str
    native_evidence_kind: NativeEvidenceKind
    capabilities: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in (
            "backend_id",
            "result_schema_version",
            "algorithm_version",
            "settings_fingerprint",
            "adapter_owner",
            "native_evidence_kind",
        ):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        if self.backend_id not in {
            M6_ORIENTATION_COMPONENTS_BACKEND_ID,
            M3_M6_LATTICE_NETWORK_BACKEND_ID,
        }:
            raise ValueError(f"Unsupported domain backend ID: {self.backend_id!r}.")
        expected_kind = (
            "m6_orientation_evidence_v1"
            if self.backend_id == M6_ORIENTATION_COMPONENTS_BACKEND_ID
            else "m3_m6_lattice_evidence_v1"
        )
        if self.native_evidence_kind != expected_kind:
            raise ValueError(
                "native_evidence_kind does not match the stable backend ID."
            )
        capabilities = tuple(sorted({_text(value, "capability") for value in self.capabilities}))
        object.__setattr__(self, "capabilities", capabilities)


@dataclass(frozen=True)
class M6OrientationComponentsEvidence:
    """Backend-native point evidence from orientation-component analysis."""

    assignment_status: tuple[tuple[str, str], ...]
    q6: tuple[tuple[str, float | None], ...]
    kind: Literal["m6_orientation_evidence_v1"] = (
        "m6_orientation_evidence_v1"
    )

    def __post_init__(self) -> None:
        assignments = _text_pairs(self.assignment_status, "assignment_status")
        q6_values = tuple(sorted(
            (
                _text(source_id, "q6 source_id"),
                _optional_finite(value, "q6 value"),
            )
            for source_id, value in self.q6
        ))
        _unique_first_values(assignments, "assignment_status")
        _unique_first_values(q6_values, "q6")
        if tuple(value[0] for value in assignments) != tuple(
            value[0] for value in q6_values
        ):
            raise ValueError("Classic native evidence fields must align by source ID.")
        object.__setattr__(self, "assignment_status", assignments)
        object.__setattr__(self, "q6", q6_values)


@dataclass(frozen=True)
class M3M6LatticeDomainEvidence:
    """Readable native classification and QC for one lattice-domain component."""

    lattice_domain_id: str
    dominant_symmetry: str
    confidence: float
    qc_flags: tuple[str, ...]
    orientation_reference_channel: str
    m3_m6_orientation_relation_status: str
    provenance_fingerprint: str

    def __post_init__(self) -> None:
        for name in (
            "lattice_domain_id",
            "dominant_symmetry",
            "orientation_reference_channel",
            "m3_m6_orientation_relation_status",
            "provenance_fingerprint",
        ):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        confidence = _optional_finite(self.confidence, "confidence")
        if confidence is None or not 0.0 <= confidence <= 1.0:
            raise ValueError("confidence must be between zero and one.")
        object.__setattr__(self, "confidence", confidence)
        object.__setattr__(
            self,
            "qc_flags",
            tuple(sorted({_text(value, "qc_flag") for value in self.qc_flags})),
        )


@dataclass(frozen=True)
class M3M6LatticeNetworkEvidence:
    """Backend-native point, domain, and producer evidence from lattice analysis."""

    point_roles: tuple[tuple[str, str], ...]
    boundary_reasons: tuple[tuple[str, str | None], ...]
    point_domain_ids: tuple[tuple[str, str | None], ...]
    domains: tuple[M3M6LatticeDomainEvidence, ...]
    producer_fingerprints: tuple[tuple[str, str], ...]
    kind: Literal["m3_m6_lattice_evidence_v1"] = (
        "m3_m6_lattice_evidence_v1"
    )

    def __post_init__(self) -> None:
        roles = _text_pairs(self.point_roles, "point_roles")
        reasons = tuple(sorted(
            (
                _text(source_id, "boundary source_id"),
                None if reason is None else _text(reason, "boundary reason"),
            )
            for source_id, reason in self.boundary_reasons
        ))
        domain_ids = tuple(sorted(
            (
                _text(source_id, "point domain source_id"),
                None if domain_id is None else _text(domain_id, "point domain ID"),
            )
            for source_id, domain_id in self.point_domain_ids
        ))
        domains = tuple(sorted(self.domains, key=lambda value: value.lattice_domain_id))
        if any(not isinstance(value, M3M6LatticeDomainEvidence) for value in domains):
            raise TypeError("domains must contain M3M6LatticeDomainEvidence values.")
        producer_fingerprints = _text_pairs(
            self.producer_fingerprints,
            "producer_fingerprints",
        )
        for name, values in (
            ("point_roles", roles),
            ("boundary_reasons", reasons),
            ("point_domain_ids", domain_ids),
            ("producer_fingerprints", producer_fingerprints),
        ):
            _unique_first_values(values, name)
        point_keys = tuple(value[0] for value in roles)
        if any(
            point_keys != tuple(value[0] for value in values)
            for values in (reasons, domain_ids)
        ):
            raise ValueError("Network point evidence fields must align by source ID.")
        if len({value.lattice_domain_id for value in domains}) != len(domains):
            raise ValueError("Network domain evidence IDs must be unique.")
        object.__setattr__(self, "point_roles", roles)
        object.__setattr__(self, "boundary_reasons", reasons)
        object.__setattr__(self, "point_domain_ids", domain_ids)
        object.__setattr__(self, "domains", domains)
        object.__setattr__(self, "producer_fingerprints", producer_fingerprints)


DomainBackendEvidence: TypeAlias = (
    M6OrientationComponentsEvidence | M3M6LatticeNetworkEvidence
)


def m6_orientation_components_identity(
    *,
    settings_fingerprint: str,
    algorithm_version: str,
    adapter_owner: str,
    capabilities: tuple[str, ...] = ("common_partition",),
) -> DomainBackendIdentity:
    """Build the complete identity shared by classic M6 adapter fixtures."""

    return DomainBackendIdentity(
        backend_id=M6_ORIENTATION_COMPONENTS_BACKEND_ID,
        result_schema_version="domain-backend-result-v1",
        algorithm_version=algorithm_version,
        settings_fingerprint=settings_fingerprint,
        adapter_owner=adapter_owner,
        native_evidence_kind="m6_orientation_evidence_v1",
        capabilities=capabilities,
    )


def validate_backend_evidence(
    identity: DomainBackendIdentity,
    evidence: DomainBackendEvidence,
) -> None:
    if not isinstance(identity, DomainBackendIdentity):
        raise TypeError("backend_identity must be a DomainBackendIdentity.")
    expected_type = (
        M6OrientationComponentsEvidence
        if identity.native_evidence_kind == "m6_orientation_evidence_v1"
        else M3M6LatticeNetworkEvidence
    )
    if not isinstance(evidence, expected_type):
        raise TypeError("Native evidence type does not match backend identity.")


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be non-empty text.")
    return value.strip()


def _text_pairs(
    values: tuple[tuple[str, str], ...],
    name: str,
) -> tuple[tuple[str, str], ...]:
    return tuple(sorted(
        (_text(first, f"{name} key"), _text(second, f"{name} value"))
        for first, second in values
    ))


def _unique_first_values(values: tuple[tuple[object, object], ...], name: str) -> None:
    keys = tuple(value[0] for value in values)
    if len(set(keys)) != len(keys):
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
