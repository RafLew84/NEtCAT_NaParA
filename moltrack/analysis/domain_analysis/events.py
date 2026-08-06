from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal


ClassifierOutcomeStatus = Literal["completed", "canceled", "failed", "not_run"]
ClassifierStatus = Literal[
    "not_requested",
    "completed",
    "completed_with_errors",
    "canceled",
    "not_run",
]
DomainAnalysisEventStatus = Literal[
    "started",
    "progress",
    "published",
    "completed",
    "completed_with_errors",
    "canceled",
    "failed",
    "ignored",
    "not_run",
]
DomainAnalysisRunStatus = Literal[
    "completed",
    "completed_with_errors",
    "canceled",
    "failed",
]


@dataclass(frozen=True)
class DomainAnalysisEvent:
    """Transient progress emitted by a synchronous analysis run."""

    stage_id: str
    status: DomainAnalysisEventStatus
    message: str
    frame_index: int | None = None


def emit_event(
    on_event: Callable[[DomainAnalysisEvent], None] | None,
    stage_id: str,
    status: DomainAnalysisEventStatus,
    message: str,
    *,
    frame_index: int | None = None,
) -> None:
    if on_event is not None:
        on_event(
            DomainAnalysisEvent(
                stage_id=stage_id,
                status=status,
                message=message,
                frame_index=frame_index,
            )
        )


def cancellation_requested(is_cancelled: Callable[[], bool] | None) -> bool:
    return is_cancelled is not None and bool(is_cancelled())


def validate_domain_analysis_lifecycle(
    run_status: DomainAnalysisRunStatus,
    *,
    m6_published: bool,
    classifier_status: ClassifierStatus,
    outcome_statuses: tuple[ClassifierOutcomeStatus, ...] | None,
) -> None:
    if classifier_status == "not_requested":
        if outcome_statuses is not None:
            raise ValueError("A request without classifiers cannot contain outcomes.")
        if run_status == "completed_with_errors":
            raise ValueError("completed_with_errors requires requested classifiers.")
        if run_status == "canceled" and m6_published:
            raise ValueError("Canceled run status must match its publication stage.")
        return
    if not outcome_statuses:
        raise ValueError("Requested classifiers require outcomes.")
    if not _lifecycle_matches(
        run_status,
        m6_published=m6_published,
        classifier_status=classifier_status,
        statuses=outcome_statuses,
    ):
        raise ValueError("Domain Analysis run and classifier statuses must agree.")


def _lifecycle_matches(
    run_status: DomainAnalysisRunStatus,
    *,
    m6_published: bool,
    classifier_status: ClassifierStatus,
    statuses: tuple[ClassifierOutcomeStatus, ...],
) -> bool:
    if classifier_status == "completed":
        return run_status == "completed" and all(
            status == "completed" for status in statuses
        )
    if classifier_status == "completed_with_errors":
        return (
            run_status == "completed_with_errors"
            and "failed" in statuses
            and all(status in {"completed", "failed"} for status in statuses)
        )
    if classifier_status == "canceled":
        return (
            run_status == "canceled"
            and m6_published
            and _valid_canceled_sequence(statuses)
        )
    return (
        classifier_status == "not_run"
        and run_status in {"canceled", "failed"}
        and not m6_published
        and all(status == "not_run" for status in statuses)
    )


def _valid_canceled_sequence(
    statuses: tuple[ClassifierOutcomeStatus, ...],
) -> bool:
    pending_at = next(
        (
            index
            for index, status in enumerate(statuses)
            if status not in {"completed", "failed"}
        ),
        None,
    )
    if pending_at is None:
        return False
    pending = statuses[pending_at:]
    return (
        pending[0] == "canceled"
        and all(status == "not_run" for status in pending[1:])
    ) or all(status == "not_run" for status in pending)
