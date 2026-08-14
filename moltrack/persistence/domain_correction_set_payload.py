from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict
from datetime import datetime
from typing import Any, cast

from moltrack.analysis.domain_analysis import (
    DomainCorrectionAtom,
    DomainCorrectionEffect,
    DomainCorrectionHistoryRecord,
    DomainCorrectionReviewTarget,
    DomainCorrectionWorkspace,
    ManualOrientationDecision,
    ManualOrientationIntent,
)
from moltrack.analysis.domain_analysis.manual_domain_models import (
    BoundaryResolution,
    ManualDomainIntent,
    ManualDomainRecord,
    RestoreMemberResolution,
)

from .domain_analysis_payload_validation import (
    boolean_field,
    integer_field,
    list_field,
    mapping,
    optional_text_field,
    required,
    text_field,
    text_list_field,
)


def correction_set_to_payload(value: DomainCorrectionWorkspace) -> dict[str, Any]:
    return {
        "automatic_fingerprint": value.automatic_fingerprint,
        "revision": value.revision,
        "orientation_decisions": [asdict(item) for item in value.orientation_decisions],
        "manual_domains": [asdict(item) for item in value.manual_domains],
        "cleared_boundary_source_keys": _pairs(value.cleared_boundary_source_keys),
        "atoms": [_atom_to_payload(item) for item in value.atoms],
        "history_records": [
            {
                **asdict(item),
                "recorded_at": item.recorded_at.isoformat(),
            }
            for item in value.history_records
        ],
        "baseline_orientation_decisions": [
            asdict(item) for item in value.baseline_orientation_decisions
        ],
        "baseline_manual_domains": [
            asdict(item) for item in value.baseline_manual_domains
        ],
        "legacy_boundary_source_keys": (
            None
            if value.legacy_boundary_source_keys is None
            else _pairs(value.legacy_boundary_source_keys)
        ),
        "review_revisions": _pairs(value.review_revisions),
    }


def correction_set_from_payload(payload: Any) -> DomainCorrectionWorkspace:
    path = "domain_analysis.correction_workspace.active_correction_set"
    saved = mapping(payload, path)
    return DomainCorrectionWorkspace(
        automatic_fingerprint=text_field(saved, "automatic_fingerprint", path),
        revision=integer_field(saved, "revision", path),
        orientation_decisions=tuple(
            _orientation_decision(item, f"{path}.orientation_decisions[{index}]")
            for index, item in enumerate(list_field(saved, "orientation_decisions", path))
        ),
        manual_domains=tuple(
            _manual_domain(item, f"{path}.manual_domains[{index}]")
            for index, item in enumerate(list_field(saved, "manual_domains", path))
        ),
        cleared_boundary_source_keys=_text_pairs(
            required(saved, "cleared_boundary_source_keys", path),
            f"{path}.cleared_boundary_source_keys",
        ),
        atoms=tuple(
            _atom(item, f"{path}.atoms[{index}]")
            for index, item in enumerate(list_field(saved, "atoms", path))
        ),
        history_records=tuple(
            _history_record(item, f"{path}.history_records[{index}]")
            for index, item in enumerate(list_field(saved, "history_records", path))
        ),
        baseline_orientation_decisions=tuple(
            _orientation_decision(
                item,
                f"{path}.baseline_orientation_decisions[{index}]",
            )
            for index, item in enumerate(
                list_field(saved, "baseline_orientation_decisions", path)
            )
        ),
        baseline_manual_domains=tuple(
            _manual_domain(item, f"{path}.baseline_manual_domains[{index}]")
            for index, item in enumerate(
                list_field(saved, "baseline_manual_domains", path)
            )
        ),
        legacy_boundary_source_keys=_optional_text_pairs(
            required(saved, "legacy_boundary_source_keys", path),
            f"{path}.legacy_boundary_source_keys",
        ),
        review_revisions=cast(
            tuple[tuple[DomainCorrectionReviewTarget, int], ...],
            _text_integer_pairs(
                required(saved, "review_revisions", path),
                f"{path}.review_revisions",
            ),
        ),
    )


def _atom_to_payload(value: DomainCorrectionAtom) -> dict[str, Any]:
    return {
        "operation_id": value.operation_id,
        "prepared_fingerprint": value.prepared_fingerprint,
        "axis": value.axis,
        "physical_frame_id": value.physical_frame_id,
        "source_ids": list(value.source_ids),
        "intent_kind": (
            "orientation"
            if isinstance(value.intent, ManualOrientationIntent)
            else "manual_domain"
        ),
        "intent": asdict(value.intent),
        "invalidates_review_targets": list(value.invalidates_review_targets),
        "effects": [asdict(item) for item in value.effects],
    }


def _atom(payload: Any, path: str) -> DomainCorrectionAtom:
    saved = mapping(payload, path)
    intent_payload = required(saved, "intent", path)
    intent_kind = text_field(saved, "intent_kind", path)
    intent: ManualOrientationIntent | ManualDomainIntent
    if intent_kind == "orientation":
        intent = _orientation_intent(intent_payload, f"{path}.intent")
    elif intent_kind == "manual_domain":
        intent = _manual_domain_intent(intent_payload, f"{path}.intent")
    else:
        raise ValueError(f"Unsupported {path}.intent_kind: {intent_kind!r}.")
    return DomainCorrectionAtom(
        operation_id=text_field(saved, "operation_id", path),
        prepared_fingerprint=text_field(saved, "prepared_fingerprint", path),
        axis=cast(Any, text_field(saved, "axis", path)),
        physical_frame_id=text_field(saved, "physical_frame_id", path),
        source_ids=tuple(text_list_field(saved, "source_ids", path)),
        intent=intent,
        invalidates_review_targets=cast(
            Any,
            tuple(text_list_field(saved, "invalidates_review_targets", path)),
        ),
        effects=tuple(
            _effect(item, f"{path}.effects[{index}]")
            for index, item in enumerate(list_field(saved, "effects", path))
        ),
    )


def _orientation_decision(payload: Any, path: str) -> ManualOrientationDecision:
    saved = mapping(payload, path)
    return ManualOrientationDecision(
        physical_frame_id=text_field(saved, "physical_frame_id", path),
        source_id=text_field(saved, "source_id", path),
        orientation_label=text_field(saved, "orientation_label", path),
        reason_code=optional_text_field(saved, "reason_code", path),
    )


def _orientation_intent(payload: Any, path: str) -> ManualOrientationIntent:
    saved = mapping(payload, path)
    return ManualOrientationIntent(
        physical_frame_id=text_field(saved, "physical_frame_id", path),
        source_ids=tuple(text_list_field(saved, "source_ids", path)),
        operation=cast(Any, text_field(saved, "operation", path)),
        orientation_label=optional_text_field(saved, "orientation_label", path),
        reason_code=optional_text_field(saved, "reason_code", path),
    )


def _manual_domain(payload: Any, path: str) -> ManualDomainRecord:
    saved = mapping(payload, path)
    return ManualDomainRecord(
        physical_frame_id=text_field(saved, "physical_frame_id", path),
        manual_domain_id=text_field(saved, "manual_domain_id", path),
        source_ids=tuple(text_list_field(saved, "source_ids", path)),
        restore_source_ids=tuple(text_list_field(saved, "restore_source_ids", path)),
        is_deleted=boolean_field(saved, "is_deleted", path),
    )


def _manual_domain_intent(payload: Any, path: str) -> ManualDomainIntent:
    saved = mapping(payload, path)
    return ManualDomainIntent(
        physical_frame_id=text_field(saved, "physical_frame_id", path),
        operation=cast(Any, text_field(saved, "operation", path)),
        source_ids=tuple(text_list_field(saved, "source_ids", path)),
        manual_domain_id=optional_text_field(saved, "manual_domain_id", path),
        boundary_resolution=cast(
            BoundaryResolution | None,
            optional_text_field(saved, "boundary_resolution", path),
        ),
        member_resolutions=cast(
            tuple[tuple[str, RestoreMemberResolution], ...],
            _text_pairs(required(saved, "member_resolutions", path), f"{path}.member_resolutions"),
        ),
    )


def _effect(payload: Any, path: str) -> DomainCorrectionEffect:
    saved = mapping(payload, path)
    return DomainCorrectionEffect(
        source_id=text_field(saved, "source_id", path),
        source_group=text_field(saved, "source_group", path),
        before_value=optional_text_field(saved, "before_value", path),
        after_value=optional_text_field(saved, "after_value", path),
        before_boundary=_optional_bool(saved, "before_boundary", path),
        after_boundary=_optional_bool(saved, "after_boundary", path),
    )


def _history_record(payload: Any, path: str) -> DomainCorrectionHistoryRecord:
    saved = mapping(payload, path)
    return DomainCorrectionHistoryRecord(
        record_id=text_field(saved, "record_id", path),
        action=cast(Any, text_field(saved, "action", path)),
        operation_id=text_field(saved, "operation_id", path),
        physical_frame_id=text_field(saved, "physical_frame_id", path),
        recorded_at=datetime.fromisoformat(text_field(saved, "recorded_at", path)),
    )


def _optional_bool(payload: Mapping[str, Any], name: str, path: str) -> bool | None:
    value = required(payload, name, path)
    if value is None or isinstance(value, bool):
        return value
    raise ValueError(f"{path}.{name} must be null or a bool.")


def _pairs(values: tuple[tuple[Any, Any], ...]) -> list[list[Any]]:
    return [[first, second] for first, second in values]


def _text_pairs(payload: Any, path: str) -> tuple[tuple[str, str], ...]:
    return cast(tuple[tuple[str, str], ...], _pairs_from_payload(payload, path, str))


def _text_integer_pairs(payload: Any, path: str) -> tuple[tuple[str, int], ...]:
    return cast(tuple[tuple[str, int], ...], _pairs_from_payload(payload, path, int))


def _optional_text_pairs(payload: Any, path: str) -> tuple[tuple[str, str], ...] | None:
    return None if payload is None else _text_pairs(payload, path)


def _pairs_from_payload(payload: Any, path: str, second_type: type) -> tuple[tuple[Any, Any], ...]:
    values = payload if isinstance(payload, list) else None
    if values is None or any(
        not isinstance(item, list)
        or len(item) != 2
        or not isinstance(item[0], str)
        or not isinstance(item[1], second_type)
        for item in values
    ):
        raise ValueError(f"{path} must contain valid pairs.")
    return tuple((item[0], item[1]) for item in values)


__all__ = ["correction_set_from_payload", "correction_set_to_payload"]
