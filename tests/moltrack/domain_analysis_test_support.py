from __future__ import annotations

from collections.abc import Mapping
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
