from __future__ import annotations

from .classic_diagnostic_funnel import build_classic_molecule_diagnostic_funnels
from .diagnostic_funnel_models import MoleculeDiagnosticFunnel
from .models import DomainAnalysisResult
from .network_diagnostic_funnel import build_network_molecule_diagnostic_funnels


def build_molecule_diagnostic_funnels(
    result: DomainAnalysisResult,
) -> tuple[MoleculeDiagnosticFunnel, ...]:
    """Dispatch complete traces from the backend-native evidence contract."""

    return (
        build_classic_molecule_diagnostic_funnels(result)
        + build_network_molecule_diagnostic_funnels(result)
    )
