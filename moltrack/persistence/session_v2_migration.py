from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from typing import Any

from moltrack.analysis.domain_analysis import (
    DomainAnalysisPublication,
    DomainAnalysisSessionDiagnostic,
    DomainAnalysisSessionState,
    DomainCorrectionWorkspaceState,
    OrientationClassCatalog,
    ReferenceReviewWorkspace,
)

from .domain_analysis_session import domain_analysis_state_from_payload


def migrate_v2_domain_analysis(payload: Any) -> DomainAnalysisSessionState:
    """Translate legacy Domain Analysis v1 into correction-aware state."""

    _require_raw_historical_backend_identity(payload)
    legacy = domain_analysis_state_from_payload(
        payload,
        require_legacy_v1=True,
    )
    if isinstance(payload, Mapping) and "correction_workspace" in payload:
        raise ValueError(
            "Legacy Domain Analysis schema v1 cannot contain correction_workspace."
        )
    diagnostics = legacy.diagnostics + _migration_diagnostics(
        legacy.published_result
    )
    return replace(
        legacy,
        orientation_class_catalog=OrientationClassCatalog(),
        domain_corrections=DomainCorrectionWorkspaceState(),
        reference_reviews=ReferenceReviewWorkspace(),
        diagnostics=diagnostics,
    )


def _require_raw_historical_backend_identity(payload: Any) -> None:
    if not isinstance(payload, Mapping):
        return
    publication = payload.get("published_result")
    if publication is None:
        return
    if not isinstance(publication, Mapping):
        raise ValueError(
            "Legacy automatic result does not prove one historical domain backend."
        )
    request = publication.get("request")
    gate = publication.get("m6_gate")
    if not isinstance(request, Mapping) or not isinstance(gate, Mapping):
        raise ValueError(
            "Legacy automatic result does not prove one historical domain backend."
        )
    backend_id = request.get("backend_id")
    frames = gate.get("frames")
    if not isinstance(backend_id, str) or not isinstance(frames, list):
        raise ValueError(
            "Legacy automatic result does not prove one historical domain backend."
        )
    frame_backend_ids = {
        identity.get("backend_id")
        for frame in frames
        if isinstance(frame, Mapping)
        for identity in (frame.get("backend_identity"),)
        if isinstance(identity, Mapping)
    }
    if frame_backend_ids != {backend_id}:
        raise ValueError(
            "Legacy automatic result does not prove one historical domain backend."
        )


def _migration_diagnostics(
    publication: DomainAnalysisPublication | None,
) -> tuple[DomainAnalysisSessionDiagnostic, ...]:
    correction_reason = (
        "Session v2 was migrated with no active automatic result and an empty "
        "correction history."
        if publication is None
        else "Session v2 was migrated with an empty correction history "
        "anchored to its compatible automatic result."
    )
    values = [
        DomainAnalysisSessionDiagnostic(
            component="correction_workspace",
            identifier="migrated-session-v2-without-corrections",
            schema_version="1",
            reason=correction_reason,
        ),
        DomainAnalysisSessionDiagnostic(
            component="reference_review",
            identifier="review-not-inferred-from-legacy",
            schema_version="1",
            reason=(
                "M6 and orientation reviews remain draft; no decisions or "
                "sign-off were inferred from the legacy automatic result."
            ),
        ),
    ]
    if publication is not None:
        values.append(_historical_backend_diagnostic(publication))
    return tuple(values)


def _historical_backend_diagnostic(
    publication: DomainAnalysisPublication,
) -> DomainAnalysisSessionDiagnostic:
    backend_id = publication.request.backend_id
    gate = publication.result.m6_gate
    frame_backend_ids = {
        frame.backend_identity.backend_id
        for frame in (() if gate is None else gate.frames)
    }
    if frame_backend_ids != {backend_id}:
        raise ValueError(
            "Legacy automatic result does not prove one historical domain backend."
        )
    return DomainAnalysisSessionDiagnostic(
        component="domain_backend",
        identifier=f"historical-backend:{backend_id}",
        schema_version="1",
        reason=(
            "The historical backend was explicitly assigned from matching "
            "request and automatic-result provenance."
        ),
    )


__all__ = ["migrate_v2_domain_analysis"]
