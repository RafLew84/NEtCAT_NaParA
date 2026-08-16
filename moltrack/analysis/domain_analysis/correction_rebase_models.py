from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from typing import Literal

from .detection_identity import CorrectionSourceMapping, DetectionIdentity
from .domain_correction_models import DomainCorrectionWorkspace
from .diagnostic_funnel import build_molecule_diagnostic_funnels
from .fingerprints import canonical_sha256
from .models import DomainAnalysisRequest, DomainAnalysisResult


CorrectionRebaseIssueKind = Literal[
    "changed_geometry",
    "missing_target",
    "split",
    "merge",
]
CorrectionRebaseResolutionAction = Literal["reapplied", "remapped", "dropped"]
@dataclass(frozen=True)
class PendingAutomaticCandidate:
    request: DomainAnalysisRequest
    result: DomainAnalysisResult
    automatic_fingerprint: str

    def __post_init__(self) -> None:
        if not isinstance(self.request, DomainAnalysisRequest):
            raise TypeError("request must be a DomainAnalysisRequest.")
        if not isinstance(self.result, DomainAnalysisResult):
            raise TypeError("result must be a DomainAnalysisResult.")
        expected = automatic_candidate_fingerprint(self.request, self.result)
        if self.automatic_fingerprint != expected:
            raise ValueError("Pending automatic fingerprint does not match its result.")


@dataclass(frozen=True)
class CorrectionRebaseIssue:
    issue_id: str
    physical_frame_id: str
    source_id: str
    kind: CorrectionRebaseIssueKind
    candidate_source_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("issue_id", "physical_frame_id", "source_id"):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        if self.kind not in {
            "changed_geometry",
            "missing_target",
            "split",
            "merge",
        }:
            raise ValueError(f"Unsupported rebase issue: {self.kind!r}.")
        object.__setattr__(
            self,
            "candidate_source_ids",
            _source_ids(self.candidate_source_ids),
        )


@dataclass(frozen=True)
class CorrectionRebaseResolution:
    issue_id: str
    action: CorrectionRebaseResolutionAction
    reason_code: str
    target_source_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "issue_id", _text(self.issue_id, "issue_id"))
        if self.action not in {"reapplied", "remapped", "dropped"}:
            raise ValueError(f"Unsupported rebase resolution: {self.action!r}.")
        object.__setattr__(
            self,
            "reason_code",
            _text(self.reason_code, "reason_code"),
        )
        targets = _source_ids(self.target_source_ids)
        if self.action == "dropped" and targets:
            raise ValueError("A dropped correction cannot identify target sources.")
        if self.action == "remapped" and not targets:
            raise ValueError("A remapped correction requires target sources.")
        if self.action == "reapplied" and targets:
            raise ValueError("A reapplied correction keeps its original source ID.")
        object.__setattr__(self, "target_source_ids", targets)


@dataclass(frozen=True)
class PreparedCorrectionRebase:
    expected_correction_revision: int
    active_automatic_fingerprint: str
    candidate_automatic_fingerprint: str
    portable_source_keys: tuple[DetectionIdentity, ...]
    issues: tuple[CorrectionRebaseIssue, ...]
    resolutions: tuple[CorrectionRebaseResolution, ...]
    source_mapping: tuple[CorrectionSourceMapping, ...]
    blocking_reasons: tuple[str, ...] = ()
    prepared_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        if (
            isinstance(self.expected_correction_revision, bool)
            or self.expected_correction_revision < 0
        ):
            raise ValueError("expected_correction_revision must be non-negative.")
        for name in (
            "active_automatic_fingerprint",
            "candidate_automatic_fingerprint",
        ):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        if any(
            not isinstance(value, DetectionIdentity)
            for value in self.portable_source_keys
        ):
            raise TypeError("portable_source_keys must contain DetectionIdentity values.")
        portable = tuple(sorted(set(self.portable_source_keys)))
        issues = tuple(sorted(self.issues, key=lambda value: value.issue_id))
        resolutions = tuple(sorted(
            self.resolutions,
            key=lambda value: value.issue_id,
        ))
        if any(
            not isinstance(value, CorrectionSourceMapping)
            for value in self.source_mapping
        ):
            raise TypeError("source_mapping must contain CorrectionSourceMapping values.")
        mapping = tuple(sorted(self.source_mapping))
        if len({value.issue_id for value in issues}) != len(issues):
            raise ValueError("Rebase issue IDs must be unique.")
        if len({value.issue_id for value in resolutions}) != len(resolutions):
            raise ValueError("Rebase resolutions must be unique per issue.")
        object.__setattr__(self, "portable_source_keys", portable)
        object.__setattr__(self, "issues", issues)
        object.__setattr__(self, "resolutions", resolutions)
        object.__setattr__(self, "source_mapping", mapping)
        object.__setattr__(
            self,
            "blocking_reasons",
            tuple(_text(value, "blocking_reason") for value in self.blocking_reasons),
        )
        object.__setattr__(self, "prepared_fingerprint", canonical_sha256({
            "schema_version": "prepared-correction-rebase-v1",
            "expected_correction_revision": self.expected_correction_revision,
            "active_automatic_fingerprint": self.active_automatic_fingerprint,
            "candidate_automatic_fingerprint": self.candidate_automatic_fingerprint,
            "portable_source_keys": [
                (value.physical_frame_id, value.source_id)
                for value in portable
            ],
            "issues": [asdict(value) for value in issues],
            "resolutions": [asdict(value) for value in resolutions],
            "source_mapping": [
                (
                    value.source_identity.physical_frame_id,
                    value.source_identity.source_id,
                    value.target_source_ids,
                )
                for value in mapping
            ],
            "blocking_reasons": self.blocking_reasons,
        }))

    @property
    def is_ready(self) -> bool:
        resolved = {value.issue_id for value in self.resolutions}
        return (
            not self.blocking_reasons
            and all(value.issue_id in resolved for value in self.issues)
        )


@dataclass(frozen=True)
class CorrectionRebaseRecord:
    record_id: str
    recorded_at: datetime
    previous_request: DomainAnalysisRequest
    previous_result: DomainAnalysisResult
    previous_correction_set: DomainCorrectionWorkspace
    promoted_automatic_fingerprint: str
    source_mapping: tuple[CorrectionSourceMapping, ...]
    resolutions: tuple[CorrectionRebaseResolution, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "record_id", _text(self.record_id, "record_id"))
        if not isinstance(self.recorded_at, datetime) or self.recorded_at.tzinfo is None:
            raise ValueError("recorded_at must be timezone-aware.")
        object.__setattr__(
            self,
            "recorded_at",
            self.recorded_at.astimezone(timezone.utc),
        )
        if any(
            not isinstance(value, CorrectionSourceMapping)
            for value in self.source_mapping
        ):
            raise TypeError("source_mapping must contain CorrectionSourceMapping values.")
        object.__setattr__(self, "source_mapping", tuple(sorted(self.source_mapping)))


@dataclass(frozen=True)
class CorrectionRebasePromotion:
    correction_set: DomainCorrectionWorkspace
    record: CorrectionRebaseRecord


@dataclass(frozen=True)
class PrepareCorrectionRebase:
    resolutions: tuple[CorrectionRebaseResolution, ...] = ()

    def __post_init__(self) -> None:
        if any(
            not isinstance(value, CorrectionRebaseResolution)
            for value in self.resolutions
        ):
            raise TypeError("resolutions must contain CorrectionRebaseResolution values.")


@dataclass(frozen=True)
class ApplyPreparedCorrectionRebase:
    preview: PreparedCorrectionRebase

    def __post_init__(self) -> None:
        if not isinstance(self.preview, PreparedCorrectionRebase):
            raise TypeError("preview must be a PreparedCorrectionRebase.")


def automatic_candidate_fingerprint(
    request: DomainAnalysisRequest,
    result: DomainAnalysisResult,
) -> str:
    result = replace(
        result,
        molecule_diagnostic_funnels=build_molecule_diagnostic_funnels(result),
    )
    gate = result.m6_gate
    return canonical_sha256({
        "schema_version": "domain-analysis-automatic-candidate-v1",
        "request": {
            "frame_indices": request.frame_indices,
            "backend_id": request.backend_id,
            "geometry_mode": request.geometry_mode,
            "classifier_ids": request.classifier_ids,
            "m6_configuration_fingerprint": (
                None
                if request.m6_configuration is None
                else request.m6_configuration.configuration_fingerprint
            ),
        },
        "run_status": result.run_status,
        "classifier_status": result.classifier_status,
        "m6_frames": [] if gate is None else [
            (frame.frame_index, frame.physical_frame_id, frame.m6_gate_fingerprint)
            for frame in gate.frames
        ],
        "classifier_outcomes": [
            (outcome.classifier_id, outcome.status, outcome.classifier_result_fingerprint)
            for outcome in result.classifier_outcomes or ()
        ],
        "failure": None if result.failure is None else asdict(result.failure),
        "diagnostic_funnels": [
            asdict(value) for value in result.molecule_diagnostic_funnels
        ],
    })


def _source_ids(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(sorted({_text(value, "source_id") for value in values}))


def _text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be non-empty text.")
    return value.strip()


__all__ = [
    "ApplyPreparedCorrectionRebase",
    "CorrectionRebaseIssue",
    "CorrectionRebaseIssueKind",
    "CorrectionRebasePromotion",
    "CorrectionRebaseRecord",
    "CorrectionRebaseResolution",
    "CorrectionRebaseResolutionAction",
    "CorrectionSourceMapping",
    "PendingAutomaticCandidate",
    "PrepareCorrectionRebase",
    "PreparedCorrectionRebase",
    "automatic_candidate_fingerprint",
]
