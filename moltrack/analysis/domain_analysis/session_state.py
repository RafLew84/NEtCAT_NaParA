from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .workspace_controller import DomainAnalysisPublication


DOMAIN_ANALYSIS_SESSION_SCHEMA_VERSION = 1
DomainAnalysisSavedClassifierStatus = Literal["not_requested", "not_run"]


@dataclass(frozen=True)
class DomainAnalysisSessionState:
    """Minimal schema-v2 Domain Analysis state owned by a MolTrack session."""

    published_result: DomainAnalysisPublication | None = None
    schema_version: int = DOMAIN_ANALYSIS_SESSION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != DOMAIN_ANALYSIS_SESSION_SCHEMA_VERSION:
            raise ValueError(
                "Unsupported Domain Analysis session schema_version: "
                f"{self.schema_version}."
            )
        publication = self.published_result
        if publication is None:
            return
        if not isinstance(publication, DomainAnalysisPublication):
            raise TypeError(
                "published_result must be a DomainAnalysisPublication."
            )
        if publication.request.classifier_ids:
            raise ValueError(
                "The minimal Domain Analysis session supports M6-only results."
            )
        result = publication.result
        if (
            result.run_status != "completed"
            or result.classifier_status != "not_requested"
            or result.classifier_outcomes is not None
        ):
            raise ValueError(
                "An M6-only published result must explicitly have classifiers "
                "not requested."
            )

    @property
    def classifier_status(self) -> DomainAnalysisSavedClassifierStatus:
        return "not_run" if self.published_result is None else "not_requested"
