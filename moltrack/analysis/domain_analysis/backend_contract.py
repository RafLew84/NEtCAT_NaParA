from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Literal, TypeAlias

from .network_backend_evidence import (
    M3M6LatticeDomainEvidence,
    M3M6LatticeNetworkEvidence,
    M3M6LatticePointEvidence,
)


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
    neighbor_count: tuple[tuple[str, int | None], ...] = ()
    orientation_deg: tuple[tuple[str, float | None], ...] = ()
    local_order_status: tuple[tuple[str, str | None], ...] = ()
    component_type: tuple[tuple[str, str | None], ...] = ()
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
        source_ids = tuple(value[0] for value in assignments)
        neighbor_counts = _optional_integer_pairs(
            self.neighbor_count, source_ids, "neighbor_count"
        )
        orientations = _optional_float_pairs(
            self.orientation_deg, source_ids, "orientation_deg"
        )
        local_statuses = _optional_text_pairs(
            self.local_order_status, source_ids, "local_order_status"
        )
        component_types = _optional_text_pairs(
            self.component_type, source_ids, "component_type"
        )
        object.__setattr__(self, "assignment_status", assignments)
        object.__setattr__(self, "q6", q6_values)
        object.__setattr__(self, "neighbor_count", neighbor_counts)
        object.__setattr__(self, "orientation_deg", orientations)
        object.__setattr__(self, "local_order_status", local_statuses)
        object.__setattr__(self, "component_type", component_types)


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


def strip_empty_classic_diagnostic_evidence(
    payload: dict[str, object],
) -> None:
    """Keep legacy classic-M6 fingerprints stable when detail is absent."""

    evidence = payload.get("native_evidence")
    if not isinstance(evidence, dict) or evidence.get("kind") != (
        "m6_orientation_evidence_v1"
    ):
        return
    for field_name in (
        "neighbor_count",
        "orientation_deg",
        "local_order_status",
        "component_type",
    ):
        if not evidence.get(field_name):
            evidence.pop(field_name, None)


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


def _optional_float_pairs(
    values: tuple[tuple[str, float | None], ...],
    source_ids: tuple[str, ...],
    name: str,
) -> tuple[tuple[str, float | None], ...]:
    if not values:
        return ()
    normalized = tuple(sorted(
        (_text(source_id, f"{name} source_id"), _optional_finite(value, name))
        for source_id, value in values
    ))
    _aligned_source_ids(normalized, source_ids, name)
    return normalized


def _optional_integer_pairs(
    values: tuple[tuple[str, int | None], ...],
    source_ids: tuple[str, ...],
    name: str,
) -> tuple[tuple[str, int | None], ...]:
    if not values:
        return ()
    normalized = tuple(sorted(
        (
            _text(source_id, f"{name} source_id"),
            None if value is None else _non_negative_integer(value, name),
        )
        for source_id, value in values
    ))
    _aligned_source_ids(normalized, source_ids, name)
    return normalized


def _optional_text_pairs(
    values: tuple[tuple[str, str | None], ...],
    source_ids: tuple[str, ...],
    name: str,
) -> tuple[tuple[str, str | None], ...]:
    if not values:
        return ()
    normalized = tuple(sorted(
        (
            _text(source_id, f"{name} source_id"),
            None if value is None else _text(value, name),
        )
        for source_id, value in values
    ))
    _aligned_source_ids(normalized, source_ids, name)
    return normalized


def _aligned_source_ids(
    values: tuple[tuple[str, object], ...],
    source_ids: tuple[str, ...],
    name: str,
) -> None:
    _unique_first_values(values, name)
    if tuple(source_id for source_id, _ in values) != source_ids:
        raise ValueError(f"{name} must align with assignment_status.")


def _non_negative_integer(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer or None.")
    return value
