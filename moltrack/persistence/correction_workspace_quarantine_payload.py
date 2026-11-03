from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import replace
from typing import Any, cast

from moltrack.analysis.domain_analysis import (
    CorrectionWorkspaceQuarantine,
    CorrectionWorkspaceQuarantineReason,
    DomainAnalysisPublication,
    DomainAnalysisSessionState,
)
from moltrack.analysis.domain_analysis.fingerprints import canonical_sha256


CORRECTION_WORKSPACE_QUARANTINE_SCHEMA_VERSION = 1
PublicationDecoder = Callable[[object], DomainAnalysisPublication]


def correction_workspace_quarantine_to_payload(
    quarantine: CorrectionWorkspaceQuarantine | None,
) -> dict[str, Any] | None:
    if quarantine is None:
        return None
    if not isinstance(quarantine, CorrectionWorkspaceQuarantine):
        raise TypeError("quarantine must be a CorrectionWorkspaceQuarantine or None.")
    payload: dict[str, Any] = {
        "schema_version": CORRECTION_WORKSPACE_QUARANTINE_SCHEMA_VERSION,
        "automatic_snapshot_available": quarantine.automatic_snapshot is not None,
        "automatic_snapshot": quarantine.automatic_snapshot_payload,
        "correction_workspace": quarantine.correction_workspace_payload,
        "reason_code": quarantine.reason_code,
        "reason": quarantine.reason,
        "activation_status": quarantine.activation_status,
        "correction_status": quarantine.correction_status,
        "reference_ready": quarantine.reference_ready,
    }
    payload["audit_fingerprint"] = canonical_sha256(payload)
    return payload


def correction_workspace_quarantine_from_payload(
    payload: object,
    *,
    decode_automatic_snapshot: PublicationDecoder,
) -> CorrectionWorkspaceQuarantine | None:
    if payload is None:
        return None
    saved = _mapping(payload)
    if saved.get("schema_version") != CORRECTION_WORKSPACE_QUARANTINE_SCHEMA_VERSION:
        raise ValueError("Unsupported correction workspace quarantine schema_version.")
    expected_fingerprint = saved.get("audit_fingerprint")
    fingerprinted = {
        key: value for key, value in saved.items() if key != "audit_fingerprint"
    }
    if expected_fingerprint != canonical_sha256(fingerprinted):
        raise ValueError("Correction workspace quarantine fingerprint is invalid.")
    if (
        saved.get("activation_status") != "quarantined"
        or saved.get("correction_status") != "conflicted"
        or saved.get("reference_ready") is not False
    ):
        raise ValueError("Correction workspace quarantine status is invalid.")
    available = saved.get("automatic_snapshot_available")
    if not isinstance(available, bool):
        raise TypeError("automatic_snapshot_available must be a bool.")
    automatic_payload = saved.get("automatic_snapshot")
    automatic_snapshot = (
        decode_automatic_snapshot(automatic_payload) if available else None
    )
    reason_code = saved.get("reason_code")
    reason = saved.get("reason")
    if not isinstance(reason_code, str) or not isinstance(reason, str):
        raise TypeError("Quarantine reason fields must be text.")
    return CorrectionWorkspaceQuarantine.from_payload(
        automatic_snapshot=automatic_snapshot,
        automatic_snapshot_payload=automatic_payload,
        reason_code=cast(CorrectionWorkspaceQuarantineReason, reason_code),
        reason=reason,
        correction_workspace_payload=saved.get("correction_workspace"),
    )


def restore_correction_workspace_quarantine(
    state: DomainAnalysisSessionState,
    payload: object,
    *,
    decode_automatic_snapshot: PublicationDecoder,
) -> DomainAnalysisSessionState:
    quarantine = correction_workspace_quarantine_from_payload(
        payload,
        decode_automatic_snapshot=decode_automatic_snapshot,
    )
    if quarantine is None:
        return state
    if state.correction_workspace_quarantine is not None:
        raise ValueError(
            "Session contains both a restored and newly detected quarantine."
        )
    return replace(state, correction_workspace_quarantine=quarantine)


def _mapping(payload: object) -> Mapping[str, Any]:
    if not isinstance(payload, Mapping) or any(
        not isinstance(key, str) for key in payload
    ):
        raise TypeError("correction_workspace_quarantine must be a JSON object.")
    return payload


__all__ = [
    "CORRECTION_WORKSPACE_QUARANTINE_SCHEMA_VERSION",
    "correction_workspace_quarantine_from_payload",
    "correction_workspace_quarantine_to_payload",
    "restore_correction_workspace_quarantine",
]
