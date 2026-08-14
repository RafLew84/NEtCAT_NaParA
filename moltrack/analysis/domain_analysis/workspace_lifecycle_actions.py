from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .classifier_contract import (
    validated_non_negative_integer,
    validated_text,
)
from .models import (
    DomainAnalysisEvent,
    DomainAnalysisRequest,
    DomainAnalysisResult,
)
from .fingerprints import canonical_sha256


DomainAnalysisWorkspaceRunStatus = Literal[
    "idle",
    "running",
    "completed",
    "completed_with_errors",
    "canceled",
    "failed",
    "retry_required",
]


class DomainAnalysisWorkspaceIntentError(ValueError):
    """A rejected workspace intent that leaves the snapshot unchanged."""


@dataclass(frozen=True)
class DomainAnalysisWorkspaceRunIdentity:
    series_generation: int
    run_id: int
    request_fingerprint: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "series_generation",
            validated_non_negative_integer(
                self.series_generation,
                "series_generation",
            ),
        )
        run_id = validated_non_negative_integer(self.run_id, "run_id")
        if run_id == 0:
            raise ValueError("run_id must be positive.")
        object.__setattr__(self, "run_id", run_id)
        object.__setattr__(
            self,
            "request_fingerprint",
            validated_text(
                self.request_fingerprint,
                "request_fingerprint",
            ),
        )


@dataclass(frozen=True)
class DomainAnalysisWorkspaceRunState:
    status: DomainAnalysisWorkspaceRunStatus = "idle"
    identity: DomainAnalysisWorkspaceRunIdentity | None = None
    request: DomainAnalysisRequest | None = None
    event: DomainAnalysisEvent | None = None
    diagnosis: str | None = None

    def __post_init__(self) -> None:
        if self.status not in {
            "idle",
            "running",
            "completed",
            "completed_with_errors",
            "canceled",
            "failed",
            "retry_required",
        }:
            raise ValueError(f"Unsupported workspace run status: {self.status!r}.")
        if self.status == "idle":
            if self.identity is not None or self.request is not None:
                raise ValueError("An idle workspace cannot reference a run.")
        elif not isinstance(
            self.identity,
            DomainAnalysisWorkspaceRunIdentity,
        ) or not isinstance(self.request, DomainAnalysisRequest):
            raise ValueError("A non-idle workspace must identify its frozen request.")
        if self.event is not None and not isinstance(
            self.event,
            DomainAnalysisEvent,
        ):
            raise TypeError("event must be a DomainAnalysisEvent.")
        if self.diagnosis is not None:
            object.__setattr__(
                self,
                "diagnosis",
                validated_text(self.diagnosis, "diagnosis"),
            )


@dataclass(frozen=True)
class StartDomainAnalysis:
    """Freeze and execute the current workspace draft."""


@dataclass(frozen=True)
class CancelDomainAnalysis:
    """Cooperatively cancel the current workspace run."""


@dataclass(frozen=True)
class ShutdownDomainAnalysis:
    """Dispose controller-owned execution after its final consumer closes."""


@dataclass(frozen=True)
class ReceiveDomainAnalysisEvent:
    identity: DomainAnalysisWorkspaceRunIdentity
    event: DomainAnalysisEvent


@dataclass(frozen=True)
class ReceiveDomainAnalysisResult:
    identity: DomainAnalysisWorkspaceRunIdentity
    result: DomainAnalysisResult


@dataclass(frozen=True)
class ReceiveDomainAnalysisFailure:
    identity: DomainAnalysisWorkspaceRunIdentity
    message: str


DomainAnalysisLifecycleAction = (
    StartDomainAnalysis
    | CancelDomainAnalysis
    | ShutdownDomainAnalysis
    | ReceiveDomainAnalysisEvent
    | ReceiveDomainAnalysisResult
    | ReceiveDomainAnalysisFailure
)


def domain_analysis_request_fingerprint(request: DomainAnalysisRequest) -> str:
    payload: dict[str, object] = {
        "schema_version": "domain-analysis-workspace-draft-v1",
        "frame_indices": request.frame_indices,
        "geometry_mode": request.geometry_mode,
        "classifier_ids": request.classifier_ids,
    }
    if request.m6_configuration is not None:
        payload.update({
            "schema_version": "domain-analysis-workspace-draft-v2",
            "backend_id": request.backend_id,
            "m6_configuration_fingerprint": (
                request.m6_configuration.configuration_fingerprint
            ),
        })
    return canonical_sha256(payload)
