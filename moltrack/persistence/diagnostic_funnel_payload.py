from __future__ import annotations

from dataclasses import asdict
from typing import Any

from moltrack.analysis.domain_analysis import MoleculeDiagnosticFunnel

from .domain_analysis_payload_validation import json_compatible_value


def diagnostic_funnels_to_payload(
    funnels: tuple[MoleculeDiagnosticFunnel, ...],
) -> list[dict[str, Any]]:
    return json_compatible_value([asdict(value) for value in funnels])


def validate_diagnostic_funnels_payload(
    payload: Any,
    funnels: tuple[MoleculeDiagnosticFunnel, ...],
    *,
    path: str,
) -> None:
    if not isinstance(payload, list):
        raise ValueError(f"{path} must be a list.")
    expected = diagnostic_funnels_to_payload(funnels)
    if payload != expected:
        raise ValueError(
            f"{path} does not match funnels recomputed from the automatic snapshot."
        )

__all__ = [
    "diagnostic_funnels_to_payload",
    "validate_diagnostic_funnels_payload",
]
