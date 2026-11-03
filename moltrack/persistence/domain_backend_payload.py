from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict
from typing import Any, cast

from moltrack.analysis.domain_analysis.backend_contract import (
    DomainBackendEvidence,
    DomainBackendIdentity,
    M3M6LatticeDomainEvidence,
    M3M6LatticeNetworkEvidence,
    M3M6LatticePointEvidence,
    M6OrientationComponentsEvidence,
    NativeEvidenceKind,
)

from .domain_analysis_payload_validation import (
    boolean_field,
    integer_field,
    list_field,
    mapping,
    number_field,
    optional_integer_field,
    optional_text_field,
    required,
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
        point_evidence = []
        for item in value.point_evidence:
            saved_point = asdict(item)
            for field_name in (
                "incident_edge_decisions",
                "incident_edge_rejection_reasons",
            ):
                saved_point[field_name] = list(saved_point[field_name])
            offsets = saved_point["stable_threshold_offsets"]
            if offsets is not None:
                saved_point["stable_threshold_offsets"] = list(offsets)
            point_evidence.append(saved_point)
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
                    "component_type": item.component_type,
                    "molecule_count": item.molecule_count,
                    "core_size": item.core_size,
                    "halo_size": item.halo_size,
                    "adjacent_boundary_point_count": (
                        item.adjacent_boundary_point_count
                    ),
                }
                for item in value.domains
            ],
            "producer_fingerprints": [
                list(item) for item in value.producer_fingerprints
            ],
            "point_evidence": point_evidence,
            "minimum_domain_size": value.minimum_domain_size,
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
            point_evidence=tuple(
                _lattice_point_from_payload(
                    item,
                    path=f"{path}.point_evidence[{index}]",
                )
                for index, item in enumerate(
                    [] if "point_evidence" not in saved else list_field(
                        saved, "point_evidence", path
                    )
                )
            ),
            minimum_domain_size=_optional_saved_integer(
                saved, "minimum_domain_size", path
            ),
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
        component_type=_optional_saved_text(saved, "component_type", path),
        molecule_count=_optional_saved_integer(saved, "molecule_count", path),
        core_size=_optional_saved_integer(saved, "core_size", path),
        halo_size=_optional_saved_integer(saved, "halo_size", path),
        adjacent_boundary_point_count=_optional_saved_integer(
            saved, "adjacent_boundary_point_count", path
        ),
    )


def _lattice_point_from_payload(
    payload: Any,
    *,
    path: str,
) -> M3M6LatticePointEvidence:
    saved = mapping(payload, path)
    optional_numbers = (
        "q3", "q6", "theta3_lattice_deg", "theta6_deg",
        "m3_orientation_confidence", "m6_orientation_confidence",
        "trifold_model_score", "sixfold_model_score", "mixed_model_score",
        "disordered_model_score", "second_best_margin",
        "expected_direction_coverage", "classification_confidence",
        "winning_model_orientation_deg",
    )
    values = {
        name: _required_optional_number(saved, name, path)
        for name in optional_numbers
    }
    return M3M6LatticePointEvidence(
        source_id=text_field(saved, "source_id", path),
        neighbor_count=integer_field(saved, "neighbor_count", path),
        first_shell_construction_method=text_field(
            saved, "first_shell_construction_method", path
        ),
        first_shell_qc_status=text_field(saved, "first_shell_qc_status", path),
        physical_duplicate_qc=boolean_field(saved, "physical_duplicate_qc", path),
        geometry_duplicate_qc=boolean_field(saved, "geometry_duplicate_qc", path),
        edge_truncated_neighborhood=boolean_field(
            saved, "edge_truncated_neighborhood", path
        ),
        m3_orientation_status=text_field(saved, "m3_orientation_status", path),
        m6_orientation_status=text_field(saved, "m6_orientation_status", path),
        computation_status=text_field(saved, "computation_status", path),
        symmetry_resolvability_status=text_field(
            saved, "symmetry_resolvability_status", path
        ),
        best_model=text_field(saved, "best_model", path),
        classification_reason=text_field(saved, "classification_reason", path),
        incident_edge_decisions=tuple(text_list_field(
            saved, "incident_edge_decisions", path
        )),
        incident_edge_rejection_reasons=tuple(text_list_field(
            saved, "incident_edge_rejection_reasons", path
        )),
        retained_edge_count=integer_field(saved, "retained_edge_count", path),
        core_eligible_edge_count=integer_field(
            saved, "core_eligible_edge_count", path
        ),
        seed_component_id=optional_integer_field(
            saved, "seed_component_id", path
        ),
        seed_state=optional_text_field(saved, "seed_state", path),
        growth_iteration_count=integer_field(
            saved, "growth_iteration_count", path
        ),
        stable_threshold_offsets=_optional_integer_tuple(
            saved, "stable_threshold_offsets", path
        ),
        **values,
    )


def _required_optional_number(
    saved: Mapping[str, Any], field: str, path: str
) -> float | None:
    value = required(saved, field, path)
    return None if value is None else number_field(saved, field, path)


def _integer_list(
    saved: Mapping[str, Any], field: str, path: str
) -> list[int]:
    values = list_field(saved, field, path)
    if any(isinstance(value, bool) or not isinstance(value, int) for value in values):
        raise ValueError(f"{path}.{field} must contain integers.")
    return cast(list[int], values)


def _optional_integer_tuple(
    saved: Mapping[str, Any], field: str, path: str
) -> tuple[int, ...] | None:
    return None if required(saved, field, path) is None else tuple(
        _integer_list(saved, field, path)
    )


def _optional_saved_text(
    saved: Mapping[str, Any], field: str, path: str
) -> str | None:
    return None if field not in saved else optional_text_field(saved, field, path)


def _optional_saved_integer(
    saved: Mapping[str, Any], field: str, path: str
) -> int | None:
    return None if field not in saved else optional_integer_field(saved, field, path)


def _pair(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError(f"{path} must be a two-item list.")
    return value


def _pair_text(value: Any, path: str) -> str:
    return text_field({"value": value}, "value", path)
