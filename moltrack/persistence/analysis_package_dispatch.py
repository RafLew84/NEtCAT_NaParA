from __future__ import annotations

from .domain_analysis_export import (
    DomainAnalysisExportSettings,
    export_domain_analysis_package,
)
from .correction_aware_export import export_correction_aware_package
from .correction_aware_export_schema import CorrectionAwareExportSettings


def export_analysis_package(source, settings, **kwargs):
    """Export the package schema selected by its explicit settings policy."""

    if kwargs:
        unexpected = ", ".join(sorted(kwargs))
        raise TypeError(
            f"Domain Analysis export received unsupported options: {unexpected}."
        )
    if isinstance(settings, DomainAnalysisExportSettings):
        return export_domain_analysis_package(source, settings)
    if isinstance(settings, CorrectionAwareExportSettings):
        return export_correction_aware_package(source, settings)
    raise TypeError(
        "settings must be DomainAnalysisExportSettings or "
        "CorrectionAwareExportSettings."
    )


__all__ = ["export_analysis_package"]
