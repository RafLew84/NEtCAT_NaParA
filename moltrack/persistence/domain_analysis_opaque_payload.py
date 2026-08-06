from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from moltrack.analysis.domain_analysis import DomainAnalysisSessionDiagnostic


def opaque_components_from_payload(
    section: Mapping[str, Any],
    *,
    known_fields: frozenset[str],
) -> tuple[
    tuple[tuple[str, object], ...],
    tuple[DomainAnalysisSessionDiagnostic, ...],
]:
    """Preserve compatible extensions and report every inactive component."""

    components: list[tuple[str, object]] = []
    diagnostics: list[DomainAnalysisSessionDiagnostic] = []
    for key, value in section.items():
        if key in known_fields:
            continue
        component_id, schema_version = _component_metadata(key, value)
        if _contains_raw_pixels(value):
            reason = "Unsupported component contains raw pixels and was skipped."
        else:
            components.append((key, deepcopy(value)))
            reason = (
                "Compatible unsupported component was preserved but not activated."
            )
        diagnostics.append(DomainAnalysisSessionDiagnostic(
            component=key,
            identifier=component_id,
            schema_version=schema_version,
            reason=reason,
        ))
    return tuple(components), tuple(diagnostics)


def _component_metadata(key: str, value: object) -> tuple[str, str]:
    component_id = key
    schema_version = "unknown"
    if not isinstance(value, Mapping):
        return component_id, schema_version
    saved_id = value.get("component_id")
    if isinstance(saved_id, str) and saved_id.strip():
        component_id = saved_id
    saved_version = value.get("schema_version")
    if (
        isinstance(saved_version, (str, int))
        and not isinstance(saved_version, bool)
    ):
        schema_version = str(saved_version)
    return component_id, schema_version


def _contains_raw_pixels(value: object) -> bool:
    if isinstance(value, list):
        return any(_contains_raw_pixels(item) for item in value)
    if isinstance(value, Mapping):
        return any(
            key in {"raw_frame", "raw_image", "raw_pixels"}
            or _contains_raw_pixels(item)
            for key, item in value.items()
        )
    return False
