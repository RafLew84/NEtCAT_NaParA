from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Literal

from .workspace_controller import DomainAnalysisPublication


CorrectionWorkspaceQuarantineReason = Literal[
    "automatic_snapshot_invariant_violation",
    "effective_projection_checkpoint_mismatch",
    "correction_workspace_invariant_violation",
]


@dataclass(frozen=True)
class CorrectionWorkspaceQuarantine:
    """Audit-only correction payload that cannot become active semantics."""

    automatic_snapshot: DomainAnalysisPublication | None
    reason_code: CorrectionWorkspaceQuarantineReason
    reason: str
    _automatic_snapshot_payload_json: str = field(repr=False)
    _correction_workspace_payload_json: str = field(repr=False)
    activation_status: Literal["quarantined"] = field(
        default="quarantined",
        init=False,
    )
    correction_status: Literal["conflicted"] = field(
        default="conflicted",
        init=False,
    )
    reference_ready: Literal[False] = field(default=False, init=False)

    @classmethod
    def from_payload(
        cls,
        *,
        automatic_snapshot: DomainAnalysisPublication | None,
        automatic_snapshot_payload: Any,
        reason_code: CorrectionWorkspaceQuarantineReason,
        reason: str,
        correction_workspace_payload: Any,
    ) -> CorrectionWorkspaceQuarantine:
        if automatic_snapshot is not None and not isinstance(
            automatic_snapshot,
            DomainAnalysisPublication,
        ):
            raise TypeError(
                "automatic_snapshot must be a DomainAnalysisPublication or null."
            )
        if reason_code not in {
            "automatic_snapshot_invariant_violation",
            "effective_projection_checkpoint_mismatch",
            "correction_workspace_invariant_violation",
        }:
            raise ValueError(f"Unsupported quarantine reason_code: {reason_code!r}.")
        normalized_reason = str(reason).strip()
        if not normalized_reason:
            raise ValueError("Quarantine reason must be non-empty text.")
        return cls(
            automatic_snapshot=automatic_snapshot,
            reason_code=reason_code,
            reason=normalized_reason,
            _automatic_snapshot_payload_json=_audit_json(
                automatic_snapshot_payload,
                "automatic snapshot",
            ),
            _correction_workspace_payload_json=_audit_json(
                correction_workspace_payload,
                "correction workspace",
            ),
        )

    @property
    def automatic_snapshot_payload(self) -> Any:
        return json.loads(self._automatic_snapshot_payload_json)

    @property
    def correction_workspace_payload(self) -> Any:
        return json.loads(self._correction_workspace_payload_json)


def _audit_json(payload: Any, name: str) -> str:
    try:
        return json.dumps(
            payload,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"Quarantined {name} must contain JSON data."
        ) from exc


__all__ = [
    "CorrectionWorkspaceQuarantine",
    "CorrectionWorkspaceQuarantineReason",
]
