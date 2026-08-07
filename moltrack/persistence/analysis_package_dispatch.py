from __future__ import annotations

from .domain_analysis_export import (
    DomainAnalysisExportSettings,
    export_domain_analysis_package,
)


def export_analysis_package(source, settings, **kwargs):
    """Export the one supported schema-v9 Domain Analysis package."""

    if not isinstance(settings, DomainAnalysisExportSettings):
        raise TypeError("settings must be DomainAnalysisExportSettings.")
    if kwargs:
        unexpected = ", ".join(sorted(kwargs))
        raise TypeError(
            f"Domain Analysis export received unsupported options: {unexpected}."
        )
    return export_domain_analysis_package(source, settings)


__all__ = ["export_analysis_package"]
