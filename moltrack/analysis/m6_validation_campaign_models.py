"""Immutable shortlist contracts for one-shot M6 Validation."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

from .domain_analysis import (
    DomainBackendIdentity,
    M3_M6_LATTICE_NETWORK_BACKEND_ID,
    M6_ORIENTATION_COMPONENTS_BACKEND_ID,
)
from .domain_analysis.fingerprints import canonical_sha256
from .lattice_domain_calibration_models import LatticeDomainCalibrationSweepSettings
from .m6_calibration_campaign_models import (
    M6CalibrationAggregateMetrics,
    M6CalibrationCandidateResult,
    M6CalibrationGroupMetrics,
    M6CalibrationObjective,
)


M6_CANDIDATE_SHORTLIST_SCHEMA_VERSION = "m6-candidate-shortlist-v1"
M6_CALIBRATION_TIE_BREAK_RULE = "objective-stability-distance-variant-v1"
M6_CAMPAIGN_REPORT_SCHEMA_VERSION = "m6-campaign-report-v2"
M6_VALIDATION_ACCESS_SCHEMA_VERSION = "m6-validation-access-v1"
M6_VALIDATION_RECEIPT_SCHEMA_VERSION = "m6-validation-access-receipt-v1"
_BACKEND_IDS = {
    M6_ORIENTATION_COMPONENTS_BACKEND_ID,
    M3_M6_LATTICE_NETWORK_BACKEND_ID,
}


@dataclass(frozen=True)
class M6CandidateShortlistEntry:
    backend_identity: DomainBackendIdentity
    candidate: M6CalibrationCandidateResult
    candidate_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.backend_identity, DomainBackendIdentity):
            raise TypeError("backend_identity must be a DomainBackendIdentity.")
        if not isinstance(self.candidate, M6CalibrationCandidateResult):
            raise TypeError("candidate must be an M6CalibrationCandidateResult.")
        if not self.candidate.eligible:
            raise ValueError("A shortlisted M6 candidate must be eligible.")
        object.__setattr__(
            self,
            "candidate_fingerprint",
            canonical_sha256({
                "backend_identity": asdict(self.backend_identity),
                "candidate": asdict(self.candidate),
            }),
        )


@dataclass(frozen=True)
class M6CandidateShortlist:
    dataset_id: str
    dataset_version_id: str
    dataset_version_fingerprint: str
    validation_epoch_id: str
    geometry_fingerprint: str
    objective: M6CalibrationObjective
    tie_break_rule: str
    entries: tuple[M6CandidateShortlistEntry, ...]
    objective_fingerprint: str = field(init=False)
    shortlist_fingerprint: str = field(init=False)
    validation_opened: Literal[False] = False
    schema_version: str = M6_CANDIDATE_SHORTLIST_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for field_name in (
            "dataset_id",
            "dataset_version_id",
            "dataset_version_fingerprint",
            "validation_epoch_id",
            "geometry_fingerprint",
            "tie_break_rule",
        ):
            object.__setattr__(
                self,
                field_name,
                _text(getattr(self, field_name), field_name),
            )
        if not isinstance(self.objective, M6CalibrationObjective):
            raise TypeError("objective must be an M6CalibrationObjective.")
        entries = tuple(self.entries)
        if any(not isinstance(value, M6CandidateShortlistEntry) for value in entries):
            raise TypeError("entries must contain M6CandidateShortlistEntry values.")
        entries = tuple(sorted(
            entries,
            key=lambda value: value.backend_identity.backend_id,
        ))
        backend_ids = {value.backend_identity.backend_id for value in entries}
        if len(entries) != 2 or backend_ids != _BACKEND_IDS:
            raise ValueError("An M6 shortlist requires one candidate per backend.")
        if self.validation_opened is not False:
            raise ValueError("A frozen shortlist cannot have Validation opened.")
        if self.schema_version != M6_CANDIDATE_SHORTLIST_SCHEMA_VERSION:
            raise ValueError("Unsupported M6 candidate shortlist schema.")
        objective_fingerprint = canonical_sha256(asdict(self.objective))
        object.__setattr__(self, "entries", entries)
        object.__setattr__(self, "objective_fingerprint", objective_fingerprint)
        object.__setattr__(
            self,
            "shortlist_fingerprint",
            canonical_sha256({
                "schema_version": self.schema_version,
                "dataset_id": self.dataset_id,
                "dataset_version_id": self.dataset_version_id,
                "dataset_version_fingerprint": self.dataset_version_fingerprint,
                "validation_epoch_id": self.validation_epoch_id,
                "geometry_fingerprint": self.geometry_fingerprint,
                "objective_fingerprint": objective_fingerprint,
                "tie_break_rule": self.tie_break_rule,
                "entries": [
                    {
                        "backend_id": value.backend_identity.backend_id,
                        "candidate_fingerprint": value.candidate_fingerprint,
                    }
                    for value in entries
                ],
            }),
        )


@dataclass(frozen=True)
class M6ValidationAccessReceipt:
    dataset_id: str
    dataset_version_id: str
    dataset_version_fingerprint: str
    validation_epoch_id: str
    geometry_fingerprint: str
    objective_fingerprint: str
    shortlist_fingerprint: str
    access_fingerprint: str
    opened_at_utc: str
    open_count: Literal[1] = 1
    schema_version: str = M6_VALIDATION_RECEIPT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for field_name in (
            "dataset_id",
            "dataset_version_id",
            "dataset_version_fingerprint",
            "validation_epoch_id",
            "geometry_fingerprint",
            "objective_fingerprint",
            "shortlist_fingerprint",
            "access_fingerprint",
            "opened_at_utc",
        ):
            object.__setattr__(
                self,
                field_name,
                _text(getattr(self, field_name), field_name),
            )
        if self.open_count != 1:
            raise ValueError("A Validation receipt must record exactly one open.")
        if self.schema_version != M6_VALIDATION_RECEIPT_SCHEMA_VERSION:
            raise ValueError("Unsupported M6 Validation receipt schema.")
        expected_fingerprint = canonical_sha256({
            "schema_version": M6_VALIDATION_ACCESS_SCHEMA_VERSION,
            "dataset_id": self.dataset_id,
            "dataset_version_id": self.dataset_version_id,
            "dataset_version_fingerprint": self.dataset_version_fingerprint,
            "validation_epoch_id": self.validation_epoch_id,
            "geometry_fingerprint": self.geometry_fingerprint,
            "objective_fingerprint": self.objective_fingerprint,
            "shortlist_fingerprint": self.shortlist_fingerprint,
        })
        if self.access_fingerprint != expected_fingerprint:
            raise ValueError("M6 Validation receipt identity is invalid.")


@dataclass(frozen=True)
class M6ValidationBackendResult:
    backend_identity: DomainBackendIdentity
    candidate_fingerprint: str
    candidate: M6CalibrationCandidateResult
    metrics: M6CalibrationAggregateMetrics
    group_metrics: tuple[M6CalibrationGroupMetrics, ...]
    objective_loss: float | None
    passed_constraints: bool
    constraint_failures: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.backend_identity, DomainBackendIdentity):
            raise TypeError("backend_identity must be a DomainBackendIdentity.")
        if not isinstance(self.candidate, M6CalibrationCandidateResult):
            raise TypeError("candidate must be an M6CalibrationCandidateResult.")
        object.__setattr__(
            self,
            "candidate_fingerprint",
            _text(self.candidate_fingerprint, "candidate_fingerprint"),
        )
        object.__setattr__(self, "group_metrics", tuple(self.group_metrics))
        object.__setattr__(
            self,
            "constraint_failures",
            tuple(self.constraint_failures),
        )
        if self.passed_constraints == bool(self.constraint_failures):
            raise ValueError("Validation constraint status is inconsistent.")


@dataclass(frozen=True)
class M6CampaignReportV2:
    dataset_id: str
    dataset_version_id: str
    dataset_version_fingerprint: str
    validation_epoch_id: str
    geometry_fingerprint: str
    objective: M6CalibrationObjective
    sweep: LatticeDomainCalibrationSweepSettings
    calibration_shortlist: M6CandidateShortlist
    receipt: M6ValidationAccessReceipt
    validation_results: tuple[M6ValidationBackendResult, ...]
    status: Literal["validated", "validation_failed"] = field(init=False)
    recommended_backend_id: str | None = field(init=False)
    failure_reason: str | None = field(init=False)
    preset_modified: Literal[False] = False
    schema_version: str = M6_CAMPAIGN_REPORT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _normalize_report_text(self)
        _require_report_inputs(self)
        if self.schema_version != M6_CAMPAIGN_REPORT_SCHEMA_VERSION:
            raise ValueError("Unsupported M6 campaign report schema.")
        if self.preset_modified is not False:
            raise ValueError("Validation reporting cannot modify the runtime preset.")
        _require_report_identity(self)
        results = _ordered_validation_results(self)
        object.__setattr__(self, "validation_results", results)
        passing = tuple(value for value in results if value.passed_constraints)
        recommended = min(passing, key=_validation_result_sort_key) if passing else None
        object.__setattr__(
            self,
            "status",
            "validated" if recommended is not None else "validation_failed",
        )
        object.__setattr__(
            self,
            "recommended_backend_id",
            None if recommended is None else recommended.backend_identity.backend_id,
        )
        object.__setattr__(
            self,
            "failure_reason",
            (
                None
                if recommended is not None
                else "No shortlisted backend satisfied the predeclared Validation constraints."
            ),
        )


@dataclass(frozen=True)
class M6CampaignReportV2Publication:
    report: M6CampaignReportV2
    output_directory: Path
    report_json_path: Path
    report_markdown_path: Path
    metrics_csv_path: Path
    receipt_path: Path


def _normalize_report_text(report: M6CampaignReportV2) -> None:
    for field_name in (
        "dataset_id",
        "dataset_version_id",
        "dataset_version_fingerprint",
        "validation_epoch_id",
        "geometry_fingerprint",
    ):
        object.__setattr__(
            report,
            field_name,
            _text(getattr(report, field_name), field_name),
        )
def _require_report_inputs(report: M6CampaignReportV2) -> None:
    if not isinstance(report.objective, M6CalibrationObjective):
        raise TypeError("objective must be an M6CalibrationObjective.")
    if not isinstance(report.sweep, LatticeDomainCalibrationSweepSettings):
        raise TypeError("sweep must be LatticeDomainCalibrationSweepSettings.")
    if not isinstance(report.calibration_shortlist, M6CandidateShortlist):
        raise TypeError("calibration_shortlist must be an M6CandidateShortlist.")
    if not isinstance(report.receipt, M6ValidationAccessReceipt):
        raise TypeError("receipt must be an M6ValidationAccessReceipt.")


def _require_report_identity(report: M6CampaignReportV2) -> None:
    identity = (
        report.dataset_id,
        report.dataset_version_id,
        report.dataset_version_fingerprint,
        report.validation_epoch_id,
        report.geometry_fingerprint,
    )
    shortlist = report.calibration_shortlist
    shortlist_identity = (
        shortlist.dataset_id,
        shortlist.dataset_version_id,
        shortlist.dataset_version_fingerprint,
        shortlist.validation_epoch_id,
        shortlist.geometry_fingerprint,
    )
    receipt = report.receipt
    receipt_identity = (
        receipt.dataset_id,
        receipt.dataset_version_id,
        receipt.dataset_version_fingerprint,
        receipt.validation_epoch_id,
        receipt.geometry_fingerprint,
    )
    if (
        identity != shortlist_identity
        or identity != receipt_identity
        or report.objective != shortlist.objective
        or receipt.objective_fingerprint != shortlist.objective_fingerprint
        or receipt.shortlist_fingerprint != shortlist.shortlist_fingerprint
    ):
        raise ValueError("M6 campaign report identities are inconsistent.")


def _ordered_validation_results(
    report: M6CampaignReportV2,
) -> tuple[M6ValidationBackendResult, ...]:
    results = tuple(report.validation_results)
    if any(not isinstance(value, M6ValidationBackendResult) for value in results):
        raise TypeError(
            "validation_results must contain M6ValidationBackendResult values."
        )
    ordered = tuple(sorted(
        results,
        key=lambda value: value.backend_identity.backend_id,
    ))
    if len(ordered) != 2 or {
        value.backend_identity.backend_id for value in ordered
    } != _BACKEND_IDS:
        raise ValueError("Validation results require both stable M6 backends.")
    shortlist_by_backend = {
        value.backend_identity.backend_id: value
        for value in report.calibration_shortlist.entries
    }
    for result in ordered:
        entry = shortlist_by_backend[result.backend_identity.backend_id]
        if (
            result.backend_identity != entry.backend_identity
            or result.candidate_fingerprint != entry.candidate_fingerprint
            or result.candidate != entry.candidate
        ):
            raise ValueError("Validation results do not match the frozen shortlist.")
    return ordered


def _validation_result_sort_key(
    value: M6ValidationBackendResult,
) -> tuple[object, ...]:
    return (
        value.objective_loss is None,
        value.objective_loss or 0.0,
        -value.metrics.macro_adjusted_rand_index,
        value.metrics.macro_variation_of_information_nats,
        value.backend_identity.backend_id,
    )


def _text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be non-empty text.")
    return value.strip()


__all__ = [
    "M6_CAMPAIGN_REPORT_SCHEMA_VERSION",
    "M6_CALIBRATION_TIE_BREAK_RULE",
    "M6_CANDIDATE_SHORTLIST_SCHEMA_VERSION",
    "M6_VALIDATION_ACCESS_SCHEMA_VERSION",
    "M6_VALIDATION_RECEIPT_SCHEMA_VERSION",
    "M6CampaignReportV2",
    "M6CampaignReportV2Publication",
    "M6CandidateShortlist",
    "M6CandidateShortlistEntry",
    "M6ValidationAccessReceipt",
    "M6ValidationBackendResult",
]
