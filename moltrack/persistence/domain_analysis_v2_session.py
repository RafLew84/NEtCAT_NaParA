from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from typing import Any

from moltrack.analysis.domain_analysis import (
    DOMAIN_ANALYSIS_SESSION_SCHEMA_VERSION,
    DomainAnalysisPublication,
    DomainAnalysisSessionDiagnostic,
    DomainAnalysisSessionState,
)

from .correction_workspace_session import correction_workspace_from_payload
from .domain_analysis_cache_payload import domain_analysis_cache_from_payload
from .domain_analysis_payload_validation import integer_field, required


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
) -> tuple[
    DomainAnalysisSessionState,
    tuple[DomainAnalysisSessionDiagnostic, ...],
]:
    if schema_version != DOMAIN_ANALYSIS_SESSION_SCHEMA_VERSION:
        return state, ()
    if publication_was_rejected:
        return state, (_correction_diagnostic(
            "Correction workspace was not activated because its automatic "
            "snapshot was rejected."
        ),)
    restored = correction_workspace_from_payload(
        required(section, "correction_workspace", "domain_analysis"),
        publication,
        allow_pristine_reinitialization=publication_has_diagnostics,
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


def _correction_diagnostic(reason: str) -> DomainAnalysisSessionDiagnostic:
    return DomainAnalysisSessionDiagnostic(
        component="correction_workspace",
        identifier="correction-workspace-v1",
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
