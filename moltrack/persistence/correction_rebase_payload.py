from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any, cast

from moltrack.analysis.domain_analysis import (
    CorrectionRebaseIssue,
    CorrectionRebaseRecord,
    CorrectionRebaseResolution,
    PendingAutomaticCandidate,
    PreparedCorrectionRebase,
)
from moltrack.analysis.domain_analysis.correction_rebase_models import (
    CorrectionRebaseIssueKind,
    CorrectionRebaseResolutionAction,
    CorrectionSourceMapping,
)
from moltrack.analysis.domain_analysis.workspace_controller import (
    DomainAnalysisPublication,
)

from .domain_analysis_payload_validation import (
    integer_field,
    list_field,
    mapping,
    required,
    text_field,
    text_list_field,
)
from .domain_correction_set_payload import (
    correction_set_from_payload,
    correction_set_to_payload,
)


def pending_candidate_to_payload(
    candidate: PendingAutomaticCandidate | None,
) -> dict[str, Any] | None:
    if candidate is None:
        return None
    return {
        "automatic_fingerprint": candidate.automatic_fingerprint,
        "automatic_snapshot": _publication_to_payload(
            DomainAnalysisPublication(candidate.request, candidate.result)
        ),
    }


def pending_candidate_from_payload(payload: Any) -> PendingAutomaticCandidate | None:
    if payload is None:
        return None
    path = "domain_analysis.correction_workspace.pending_rebase"
    saved = mapping(payload, path)
    publication = _publication_from_payload(
        required(saved, "automatic_snapshot", path)
    )
    return PendingAutomaticCandidate(
        request=publication.request,
        result=publication.result,
        automatic_fingerprint=text_field(saved, "automatic_fingerprint", path),
    )


def prepared_rebase_to_payload(
    prepared: PreparedCorrectionRebase | None,
) -> dict[str, Any] | None:
    if prepared is None:
        return None
    return {
        "expected_correction_revision": prepared.expected_correction_revision,
        "active_automatic_fingerprint": prepared.active_automatic_fingerprint,
        "candidate_automatic_fingerprint": prepared.candidate_automatic_fingerprint,
        "portable_source_keys": _pairs(prepared.portable_source_keys),
        "issues": [asdict(value) for value in prepared.issues],
        "resolutions": [asdict(value) for value in prepared.resolutions],
        "source_mapping": _mapping_to_payload(prepared.source_mapping),
        "blocking_reasons": list(prepared.blocking_reasons),
        "prepared_fingerprint": prepared.prepared_fingerprint,
    }


def prepared_rebase_from_payload(payload: Any) -> PreparedCorrectionRebase | None:
    if payload is None:
        return None
    path = "domain_analysis.correction_workspace.prepared_rebase"
    saved = mapping(payload, path)
    prepared = PreparedCorrectionRebase(
        expected_correction_revision=integer_field(
            saved, "expected_correction_revision", path
        ),
        active_automatic_fingerprint=text_field(
            saved, "active_automatic_fingerprint", path
        ),
        candidate_automatic_fingerprint=text_field(
            saved, "candidate_automatic_fingerprint", path
        ),
        portable_source_keys=_text_pairs(
            required(saved, "portable_source_keys", path),
            f"{path}.portable_source_keys",
        ),
        issues=tuple(
            _issue(value, f"{path}.issues[{index}]")
            for index, value in enumerate(list_field(saved, "issues", path))
        ),
        resolutions=tuple(
            _resolution(value, f"{path}.resolutions[{index}]")
            for index, value in enumerate(list_field(saved, "resolutions", path))
        ),
        source_mapping=_mapping_from_payload(
            required(saved, "source_mapping", path),
            f"{path}.source_mapping",
        ),
        blocking_reasons=tuple(text_list_field(saved, "blocking_reasons", path)),
    )
    if prepared.prepared_fingerprint != text_field(
        saved, "prepared_fingerprint", path
    ):
        raise ValueError(f"{path}.prepared_fingerprint does not match its payload.")
    return prepared


def rebase_records_to_payload(
    records: tuple[CorrectionRebaseRecord, ...],
) -> list[dict[str, Any]]:
    return [
        {
            "record_id": value.record_id,
            "recorded_at": value.recorded_at.isoformat(),
            "previous_automatic_snapshot": _publication_to_payload(
                DomainAnalysisPublication(value.previous_request, value.previous_result)
            ),
            "previous_correction_set": correction_set_to_payload(
                value.previous_correction_set
            ),
            "promoted_automatic_fingerprint": value.promoted_automatic_fingerprint,
            "source_mapping": _mapping_to_payload(value.source_mapping),
            "resolutions": [asdict(item) for item in value.resolutions],
        }
        for value in records
    ]


def rebase_records_from_payload(payload: Any) -> tuple[CorrectionRebaseRecord, ...]:
    if not isinstance(payload, list):
        raise ValueError("domain_analysis.correction_workspace.rebase_records must be a list.")
    records = []
    for index, value in enumerate(payload):
        path = f"domain_analysis.correction_workspace.rebase_records[{index}]"
        saved = mapping(value, path)
        publication = _publication_from_payload(
            required(saved, "previous_automatic_snapshot", path)
        )
        records.append(CorrectionRebaseRecord(
            record_id=text_field(saved, "record_id", path),
            recorded_at=datetime.fromisoformat(text_field(saved, "recorded_at", path)),
            previous_request=publication.request,
            previous_result=publication.result,
            previous_correction_set=correction_set_from_payload(
                required(saved, "previous_correction_set", path)
            ),
            promoted_automatic_fingerprint=text_field(
                saved, "promoted_automatic_fingerprint", path
            ),
            source_mapping=_mapping_from_payload(
                required(saved, "source_mapping", path),
                f"{path}.source_mapping",
            ),
            resolutions=tuple(
                _resolution(item, f"{path}.resolutions[{item_index}]")
                for item_index, item in enumerate(list_field(saved, "resolutions", path))
            ),
        ))
    return tuple(records)


def _issue(payload: Any, path: str) -> CorrectionRebaseIssue:
    saved = mapping(payload, path)
    return CorrectionRebaseIssue(
        issue_id=text_field(saved, "issue_id", path),
        physical_frame_id=text_field(saved, "physical_frame_id", path),
        source_id=text_field(saved, "source_id", path),
        kind=cast(CorrectionRebaseIssueKind, text_field(saved, "kind", path)),
        candidate_source_ids=tuple(text_list_field(saved, "candidate_source_ids", path)),
    )


def _resolution(payload: Any, path: str) -> CorrectionRebaseResolution:
    saved = mapping(payload, path)
    return CorrectionRebaseResolution(
        issue_id=text_field(saved, "issue_id", path),
        action=cast(
            CorrectionRebaseResolutionAction,
            text_field(saved, "action", path),
        ),
        reason_code=text_field(saved, "reason_code", path),
        target_source_ids=tuple(text_list_field(saved, "target_source_ids", path)),
    )


def _pairs(values: tuple[tuple[str, str], ...]) -> list[list[str]]:
    return [[first, second] for first, second in values]


def _text_pairs(payload: Any, path: str) -> tuple[tuple[str, str], ...]:
    if not isinstance(payload, list) or any(
        not isinstance(value, list)
        or len(value) != 2
        or any(not isinstance(item, str) or not item for item in value)
        for value in payload
    ):
        raise ValueError(f"{path} must contain text pairs.")
    return tuple((value[0], value[1]) for value in payload)


def _mapping_to_payload(values: tuple[CorrectionSourceMapping, ...]) -> list[list[Any]]:
    return [[frame_id, source_id, list(targets)] for frame_id, source_id, targets in values]


def _mapping_from_payload(payload: Any, path: str) -> tuple[CorrectionSourceMapping, ...]:
    if not isinstance(payload, list):
        raise ValueError(f"{path} must be a list.")
    values: list[CorrectionSourceMapping] = []
    for index, value in enumerate(payload):
        if (
            not isinstance(value, list)
            or len(value) != 3
            or not isinstance(value[0], str)
            or not isinstance(value[1], str)
            or not isinstance(value[2], list)
            or any(not isinstance(item, str) for item in value[2])
        ):
            raise ValueError(f"{path}[{index}] must be a source mapping.")
        values.append((value[0], value[1], tuple(value[2])))
    return tuple(values)


def _publication_to_payload(publication: DomainAnalysisPublication) -> dict[str, Any]:
    from .domain_analysis_session import _publication_to_payload as encode

    return encode(publication)


def _publication_from_payload(payload: Any) -> DomainAnalysisPublication:
    from .domain_analysis_session import _publication_from_payload as decode

    publication, diagnostics = decode(
        payload,
        fallback_configurations=(),
        require_diagnostic_funnels=True,
    )
    if diagnostics:
        raise ValueError("Correction audit automatic snapshot is not reproducible.")
    return publication


__all__ = [
    "pending_candidate_from_payload",
    "pending_candidate_to_payload",
    "prepared_rebase_from_payload",
    "prepared_rebase_to_payload",
    "rebase_records_from_payload",
    "rebase_records_to_payload",
]
