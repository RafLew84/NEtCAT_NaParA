from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from moltrack.analysis.domain_analysis.backend_contract import (
    DomainBackendEvidence,
    DomainBackendIdentity,
    M3M6LatticeDomainEvidence,
    M3M6LatticeNetworkEvidence,
    M6OrientationComponentsEvidence,
    NativeEvidenceKind,
)

from .domain_analysis_payload_validation import (
    list_field,
    mapping,
    number_field,
    text_field,
    text_list_field,
)


def backend_identity_to_payload(value: DomainBackendIdentity) -> dict[str, Any]:
    return {
        "backend_id": value.backend_id,
        "result_schema_version": value.result_schema_version,
        "algorithm_version": value.algorithm_version,
        "settings_fingerprint": value.settings_fingerprint,
        "adapter_owner": value.adapter_owner,
        "native_evidence_kind": value.native_evidence_kind,
        "capabilities": list(value.capabilities),
    }


def backend_identity_from_payload(
    payload: Any,
    *,
    path: str,
) -> DomainBackendIdentity:
    saved = mapping(payload, path)
    return DomainBackendIdentity(
        backend_id=text_field(saved, "backend_id", path),
        result_schema_version=text_field(saved, "result_schema_version", path),
        algorithm_version=text_field(saved, "algorithm_version", path),
        settings_fingerprint=text_field(saved, "settings_fingerprint", path),
        adapter_owner=text_field(saved, "adapter_owner", path),
        native_evidence_kind=cast(
            NativeEvidenceKind,
            text_field(saved, "native_evidence_kind", path),
        ),
        capabilities=tuple(text_list_field(saved, "capabilities", path)),
    )


def backend_evidence_to_payload(value: DomainBackendEvidence) -> dict[str, Any]:
    if isinstance(value, M6OrientationComponentsEvidence):
        return {
            "kind": value.kind,
            "assignment_status": [list(item) for item in value.assignment_status],
            "q6": [list(item) for item in value.q6],
            "neighbor_count": [list(item) for item in value.neighbor_count],
            "orientation_deg": [list(item) for item in value.orientation_deg],
            "local_order_status": [
                list(item) for item in value.local_order_status
            ],
            "component_type": [list(item) for item in value.component_type],
        }
    if isinstance(value, M3M6LatticeNetworkEvidence):
        return {
            "kind": value.kind,
            "point_roles": [list(item) for item in value.point_roles],
            "boundary_reasons": [list(item) for item in value.boundary_reasons],
            "point_domain_ids": [list(item) for item in value.point_domain_ids],
            "domains": [
                {
                    "lattice_domain_id": item.lattice_domain_id,
                    "dominant_symmetry": item.dominant_symmetry,
                    "confidence": item.confidence,
                    "qc_flags": list(item.qc_flags),
                    "orientation_reference_channel": item.orientation_reference_channel,
                    "m3_m6_orientation_relation_status": (
                        item.m3_m6_orientation_relation_status
                    ),
                    "provenance_fingerprint": item.provenance_fingerprint,
                }
                for item in value.domains
            ],
            "producer_fingerprints": [
                list(item) for item in value.producer_fingerprints
            ],
        }
    raise TypeError("Unsupported domain backend evidence value.")


def backend_evidence_from_payload(
    payload: Any,
    *,
    path: str,
) -> DomainBackendEvidence:
    saved = mapping(payload, path)
    kind = text_field(saved, "kind", path)
    if kind == "m6_orientation_evidence_v1":
        assignments = _pairs(saved, "assignment_status", path)
        q6_values: list[tuple[str, float | None]] = []
        for index, item in enumerate(list_field(saved, "q6", path)):
            item_path = f"{path}.q6[{index}]"
            pair = _pair(item, item_path)
            q6_values.append((
                _pair_text(pair[0], f"{item_path}[0]"),
                None
                if pair[1] is None
                else number_field({"value": pair[1]}, "value", item_path),
            ))
        return M6OrientationComponentsEvidence(
            assignment_status=assignments,
            q6=tuple(q6_values),
            neighbor_count=_optional_integer_pairs(
                saved, "neighbor_count", path
            ),
            orientation_deg=_optional_number_pairs(
                saved, "orientation_deg", path
            ),
            local_order_status=_missing_allowed_text_pairs(
                saved, "local_order_status", path
            ),
            component_type=_missing_allowed_text_pairs(
                saved, "component_type", path
            ),
        )
    if kind == "m3_m6_lattice_evidence_v1":
        roles = _pairs(saved, "point_roles", path)
        return M3M6LatticeNetworkEvidence(
            point_roles=roles,
            boundary_reasons=_optional_text_pairs(saved, "boundary_reasons", path),
            point_domain_ids=_optional_text_pairs(saved, "point_domain_ids", path),
            domains=tuple(
                _lattice_domain_from_payload(
                    item,
                    path=f"{path}.domains[{index}]",
                )
                for index, item in enumerate(list_field(saved, "domains", path))
            ),
            producer_fingerprints=_pairs(saved, "producer_fingerprints", path),
        )
    raise ValueError(f"Unsupported native evidence kind: {kind!r}.")


def _pairs(saved: Mapping[str, Any], field: str, path: str) -> tuple[tuple[str, str], ...]:
    return tuple(
        (
            _pair_text(pair[0], f"{path}.{field}[{index}][0]"),
            _pair_text(pair[1], f"{path}.{field}[{index}][1]"),
        )
        for index, value in enumerate(list_field(saved, field, path))
        for pair in (_pair(value, f"{path}.{field}[{index}]"),)
    )


def _optional_text_pairs(
    saved: Mapping[str, Any],
    field: str,
    path: str,
) -> tuple[tuple[str, str | None], ...]:
    values: list[tuple[str, str | None]] = []
    for index, item in enumerate(list_field(saved, field, path)):
        item_path = f"{path}.{field}[{index}]"
        pair = _pair(item, item_path)
        values.append((
            _pair_text(pair[0], f"{item_path}[0]"),
            None if pair[1] is None else _pair_text(pair[1], f"{item_path}[1]"),
        ))
    return tuple(values)


def _missing_allowed_text_pairs(
    saved: Mapping[str, Any],
    field: str,
    path: str,
) -> tuple[tuple[str, str | None], ...]:
    if field not in saved:
        return ()
    return _optional_text_pairs(saved, field, path)


def _optional_number_pairs(
    saved: Mapping[str, Any],
    field: str,
    path: str,
) -> tuple[tuple[str, float | None], ...]:
    if field not in saved:
        return ()
    values: list[tuple[str, float | None]] = []
    for index, item in enumerate(list_field(saved, field, path)):
        item_path = f"{path}.{field}[{index}]"
        pair = _pair(item, item_path)
        values.append((
            _pair_text(pair[0], f"{item_path}[0]"),
            None
            if pair[1] is None
            else number_field({"value": pair[1]}, "value", item_path),
        ))
    return tuple(values)


def _optional_integer_pairs(
    saved: Mapping[str, Any],
    field: str,
    path: str,
) -> tuple[tuple[str, int | None], ...]:
    if field not in saved:
        return ()
    values: list[tuple[str, int | None]] = []
    for index, item in enumerate(list_field(saved, field, path)):
        item_path = f"{path}.{field}[{index}]"
        pair = _pair(item, item_path)
        count = pair[1]
        if count is not None and (
            isinstance(count, bool) or not isinstance(count, int) or count < 0
        ):
            raise ValueError(f"{item_path}[1] must be a non-negative integer.")
        values.append((_pair_text(pair[0], f"{item_path}[0]"), count))
    return tuple(values)


def _lattice_domain_from_payload(
    payload: Any,
    *,
    path: str,
) -> M3M6LatticeDomainEvidence:
    saved = mapping(payload, path)
    return M3M6LatticeDomainEvidence(
        lattice_domain_id=text_field(saved, "lattice_domain_id", path),
        dominant_symmetry=text_field(saved, "dominant_symmetry", path),
        confidence=number_field(saved, "confidence", path),
        qc_flags=tuple(text_list_field(saved, "qc_flags", path)),
        orientation_reference_channel=text_field(
            saved, "orientation_reference_channel", path
        ),
        m3_m6_orientation_relation_status=text_field(
            saved, "m3_m6_orientation_relation_status", path
        ),
        provenance_fingerprint=text_field(saved, "provenance_fingerprint", path),
    )


def _pair(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError(f"{path} must be a two-item list.")
    return value


def _pair_text(value: Any, path: str) -> str:
    return text_field({"value": value}, "value", path)
