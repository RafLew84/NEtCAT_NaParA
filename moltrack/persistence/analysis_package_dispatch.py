from __future__ import annotations

from .analysis_package import (
    AnalysisExportSettings,
    export_analysis_package as export_legacy_analysis_package,
)
from .domain_analysis_export import (
    DomainAnalysisExportSettings,
    export_domain_analysis_package,
)


def export_analysis_package(source, settings, **kwargs):
    """Route legacy and Domain Analysis package requests through one seam."""

    if isinstance(settings, DomainAnalysisExportSettings):
        if kwargs:
            unexpected = ", ".join(sorted(kwargs))
            raise TypeError(
                "Domain Analysis export received unsupported options: "
                f"{unexpected}."
            )
        return export_domain_analysis_package(source, settings)
    if isinstance(settings, AnalysisExportSettings):
        return export_legacy_analysis_package(source, settings, **kwargs)
    raise TypeError(
        "settings must be AnalysisExportSettings or DomainAnalysisExportSettings."
    )
