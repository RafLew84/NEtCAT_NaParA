from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import replace
from typing import Any

from moltrack.analysis.domain_analysis import (
    DOMAIN_ANALYSIS_SESSION_SCHEMA_VERSION,
    CorrectionWorkspaceQuarantine,
    CorrectionWorkspaceQuarantineReason,
    DomainAnalysisPublication,
    DomainCorrectionWorkspaceState,
    DomainAnalysisSessionDiagnostic,
    DomainAnalysisSessionState,
    ReferenceReviewWorkspace,
)

from .correction_workspace_session import correction_workspace_from_payload
from .domain_analysis_cache_payload import domain_analysis_cache_from_payload
from .domain_analysis_payload_validation import integer_field, required
from .effective_projection_checkpoint import (
    EffectiveProjectionCheckpointMismatch,
)


CorrectionWorkspaceRestore = tuple[
    DomainAnalysisSessionState,
    tuple[DomainAnalysisSessionDiagnostic, ...],
]


def validated_domain_analysis_version(
    section: Mapping[str, Any],
    *,
    require_legacy_v1: bool,
) -> int:
    version = integer_field(section, "schema_version", "domain_analysis")
    expected = 1 if require_legacy_v1 else DOMAIN_ANALYSIS_SESSION_SCHEMA_VERSION
    if version != expected:
        raise ValueError(f"Unsupported domain_analysis schema_version: {version}.")
    return version


def restore_v2_correction_workspace(
    state: DomainAnalysisSessionState,
    section: Mapping[str, Any],
    *,
    schema_version: int,
    publication: DomainAnalysisPublication | None,
    publication_was_rejected: bool,
    publication_has_diagnostics: bool,
) -> CorrectionWorkspaceRestore:
    if schema_version != DOMAIN_ANALYSIS_SESSION_SCHEMA_VERSION:
        return state, ()
    if publication_was_rejected:
        return _quarantine_rejected_publication(state, section)
    correction_payload = required(
        section,
        "correction_workspace",
        "domain_analysis",
    )
    try:
        restored = correction_workspace_from_payload(
            correction_payload,
            publication,
            allow_pristine_reinitialization=publication_has_diagnostics,
        )
    except (TypeError, ValueError) as exc:
        if publication is None:
            raise
        return _quarantine_correction_error(
            state,
            section,
            publication,
            correction_payload,
            exc,
        )
    state = replace(
        state,
        orientation_class_catalog=restored.orientation_class_catalog,
        domain_corrections=restored.domain_corrections,
        reference_reviews=restored.reference_reviews,
    )
    if not restored.reinitialized_from_automatic:
        return state, ()
    return state, (_correction_diagnostic(
        "Pristine corrections were reinitialized after an incompatible "
        "classifier component was rejected."
    ),)


def _quarantine_rejected_publication(
    state: DomainAnalysisSessionState,
    section: Mapping[str, Any],
) -> CorrectionWorkspaceRestore:
    reason = (
        "Correction workspace was not activated because its automatic "
        "snapshot was rejected."
    )
    quarantine = CorrectionWorkspaceQuarantine.from_payload(
        automatic_snapshot=None,
        automatic_snapshot_payload=section.get("published_result"),
        reason_code="automatic_snapshot_invariant_violation",
        reason=reason,
        correction_workspace_payload=section.get("correction_workspace"),
    )
    return replace(
        state,
        correction_workspace_quarantine=quarantine,
    ), (_correction_diagnostic(
        reason,
        identifier="automatic_snapshot_invariant_violation",
    ),)


def _quarantine_correction_error(
    state: DomainAnalysisSessionState,
    section: Mapping[str, Any],
    publication: DomainAnalysisPublication,
    correction_payload: Any,
    error: TypeError | ValueError,
) -> CorrectionWorkspaceRestore:
    reason_code: CorrectionWorkspaceQuarantineReason = (
        "effective_projection_checkpoint_mismatch"
        if isinstance(error, EffectiveProjectionCheckpointMismatch)
        else "correction_workspace_invariant_violation"
    )
    quarantine = CorrectionWorkspaceQuarantine.from_payload(
        automatic_snapshot=publication,
        automatic_snapshot_payload=section.get("published_result"),
        reason_code=reason_code,
        reason=str(error),
        correction_workspace_payload=deepcopy(correction_payload),
    )
    return replace(
        state,
        published_result=None,
        selected_component=None,
        domain_corrections=DomainCorrectionWorkspaceState(),
        reference_reviews=ReferenceReviewWorkspace(),
        correction_workspace_quarantine=quarantine,
    ), (_correction_diagnostic(str(error), identifier=reason_code),)


def _correction_diagnostic(
    reason: str,
    *,
    identifier: str = "correction-workspace-v1",
) -> DomainAnalysisSessionDiagnostic:
    return DomainAnalysisSessionDiagnostic(
        component="correction_workspace",
        identifier=identifier,
        schema_version="1",
        reason=reason,
    )


def restore_domain_analysis_cache(
    section: Mapping[str, Any],
) -> tuple[
    tuple[Any, ...],
    tuple[Any, ...],
    tuple[DomainAnalysisSessionDiagnostic, ...],
]:
    try:
        return domain_analysis_cache_from_payload(section.get("cache"))
    except (TypeError, ValueError) as exc:
        return (), (), (DomainAnalysisSessionDiagnostic(
            component="cache",
            identifier="domain-analysis-cache",
            schema_version="unknown",
            reason=str(exc),
        ),)


__all__ = [
    "restore_domain_analysis_cache",
    "restore_v2_correction_workspace",
    "validated_domain_analysis_version",
]
