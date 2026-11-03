from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from moltrack.analysis.domain_analysis import DomainAnalysisModule


def domain_analysis_module(
    adapter_or_registry: Any,
    classifier_adapters: Mapping[str, Any],
    **kwargs: Any,
) -> DomainAnalysisModule:
    """Build the production registry seam from one focused test adapter."""

    registry = (
        adapter_or_registry
        if isinstance(adapter_or_registry, Mapping)
        else {
            adapter_or_registry.backend_identity.backend_id: adapter_or_registry
        }
    )
    return DomainAnalysisModule(registry, classifier_adapters, **kwargs)


def as_legacy_session_v2(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Return the pre-correction outer-v2/Domain-Analysis-v1 envelope."""

    legacy = deepcopy(dict(payload))
    legacy["schema_version"] = 2
    domain_analysis = legacy["domain_analysis"]
    domain_analysis["schema_version"] = 1
    domain_analysis.pop("correction_workspace")
    publication = domain_analysis.get("published_result")
    if publication is not None:
        publication.pop("diagnostic_funnels")
    return legacy
