from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .domain_analysis_export_schema import CanonicalJsonObject


CORRECTION_AWARE_EXPORT_SCHEMA_VERSION = 10
CorrectionAwareExportMode = Literal["reference", "audit"]
CorrectionAwareActivationStatus = Literal["active", "inactive", "quarantined"]
CorrectionAwareCorrectionStatus = Literal[
    "current",
    "draft",
    "stale",
    "conflicted",
]

AUTOMATIC_SNAPSHOT_FILE = "automatic_snapshot.json"
ORIENTATION_CLASS_CATALOG_FILE = "orientation_class_catalog.json"
CORRECTION_STATE_FILE = "domain_correction_state.json"
CORRECTION_REVISIONS_FILE = "domain_correction_revisions.jsonl"
CORRECTION_OPERATIONS_FILE = "domain_correction_operations.jsonl"
EFFECTIVE_PROJECTION_FILE = "domain_effective_projection.json"
EFFECTIVE_MOLECULES_FILE = "domain_effective_molecules.csv"
REFERENCE_REVIEWS_FILE = "domain_reference_reviews.json"
DIAGNOSTIC_FUNNELS_FILE = "domain_diagnostic_funnels.json"
REBASE_DIAGNOSTICS_FILE = "domain_rebase_diagnostics.json"
QUARANTINE_FILE = "correction_workspace_quarantine.json"
DRAFT_STATE_FILE = "domain_analysis_draft.json"

EFFECTIVE_MOLECULE_HEADERS = (
    "physical_frame_id",
    "source_id",
    "automatic_m6_partition",
    "automatic_domain_id",
    "automatic_boundary",
    "automatic_orientation_raw",
    "automatic_orientation_status",
    "raw_automatic_evidence",
    "effective_m6_partition",
    "effective_domain_id",
    "effective_boundary",
    "effective_orientation",
    "effective_orientation_source",
    "effective_confidence",
    "m6_review_eligibility",
    "m6_review_disposition",
    "m6_review_abstention",
    "m6_review_reason_code",
    "orientation_review_eligibility",
    "orientation_review_disposition",
    "orientation_review_abstention",
    "orientation_review_reason_code",
)


@dataclass(frozen=True)
class CorrectionAwareExportSettings:
    """Destination, source identity and policy for schema-v10 export."""

    destination: Path
    source_identity: CanonicalJsonObject
    export_mode: CorrectionAwareExportMode = "reference"
    overwrite: bool = False

    def __post_init__(self) -> None:
        destination = Path(self.destination)
        if not str(destination).strip():
            raise ValueError("Correction-aware export destination must not be empty.")
        if not isinstance(self.source_identity, CanonicalJsonObject):
            raise TypeError("source_identity must be a CanonicalJsonObject.")
        if self.export_mode not in {"reference", "audit"}:
            raise ValueError(
                f"Unsupported correction-aware export_mode: {self.export_mode!r}."
            )
        if not isinstance(self.overwrite, bool):
            raise TypeError("overwrite must be a bool.")
        object.__setattr__(self, "destination", destination)


__all__ = [
    "CORRECTION_AWARE_EXPORT_SCHEMA_VERSION",
    "CorrectionAwareExportMode",
    "CorrectionAwareActivationStatus",
    "CorrectionAwareCorrectionStatus",
    "CorrectionAwareExportSettings",
]
