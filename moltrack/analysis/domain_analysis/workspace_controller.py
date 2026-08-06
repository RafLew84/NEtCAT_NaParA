from __future__ import annotations

from dataclasses import dataclass, field, replace
from threading import RLock
from typing import cast

from .classifier_contract import (
    validated_non_negative_integer,
    validated_text,
)
from .fingerprints import canonical_sha256
from .models import (
    DomainAnalysisRequest,
    DomainAnalysisResult,
)
from .workspace_lifecycle import (
    DomainAnalysisWorkspaceExecution,
    reduce_domain_analysis_lifecycle,
)
from .workspace_lifecycle_actions import (
    CancelDomainAnalysis,
    DomainAnalysisLifecycleAction,
    DomainAnalysisWorkspaceIntentError,
    DomainAnalysisWorkspaceRunState,
    ShutdownDomainAnalysis,
    StartDomainAnalysis,
)
from .workspace_notifications import DomainAnalysisWorkspaceStateChanged


class DomainAnalysisWorkspaceNotificationError(RuntimeError):
    """An adapter notification failed after workspace state was committed."""

    def __init__(
        self,
        committed_snapshot: DomainAnalysisWorkspaceSnapshot,
    ) -> None:
        super().__init__(
            "Workspace state was committed, but its state_changed "
            "notification failed."
        )
        self.committed_snapshot = committed_snapshot


@dataclass(frozen=True, order=True)
class DomainComponentKey:
    """Canonical frame-local identity shared by tables and overlays."""

    physical_frame_id: str
    lattice_domain_id: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "physical_frame_id",
            validated_text(self.physical_frame_id, "physical_frame_id"),
        )
        object.__setattr__(
            self,
            "lattice_domain_id",
            validated_text(self.lattice_domain_id, "lattice_domain_id"),
        )


@dataclass(frozen=True)
class DomainAnalysisPublication:
    """A result paired atomically with its declared immutable request."""

    request: DomainAnalysisRequest
    result: DomainAnalysisResult
    request_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.request, DomainAnalysisRequest):
            raise TypeError("request must be a DomainAnalysisRequest.")
        if not isinstance(self.result, DomainAnalysisResult):
            raise TypeError("result must be a DomainAnalysisResult.")
        if self.result.run_status not in {"completed", "completed_with_errors"}:
            raise DomainAnalysisWorkspaceIntentError(
                "Only a completed Domain Analysis result can be published."
            )
        gate = self.result.m6_gate
        if gate is None or tuple(
            frame.frame_index for frame in gate.frames
        ) != self.request.frame_indices:
            raise DomainAnalysisWorkspaceIntentError(
                "Published result frames must match the frozen request."
            )
        object.__setattr__(
            self,
            "request_fingerprint",
            _request_fingerprint(self.request),
        )


@dataclass(frozen=True)
class DomainAnalysisWorkspaceSnapshot:
    """Immutable state rendered by every Domain Analysis adapter."""

    series_generation: int
    physical_frame_ids: tuple[str, ...]
    revision: int
    draft_revision: int
    published_revision: int
    draft: DomainAnalysisRequest
    published: DomainAnalysisPublication | None
    active_frame_index: int
    selected_component: DomainComponentKey | None = None
    run: DomainAnalysisWorkspaceRunState = field(
        default_factory=DomainAnalysisWorkspaceRunState
    )
    is_shutdown: bool = False
    draft_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        for field_name in (
            "series_generation",
            "revision",
            "draft_revision",
            "published_revision",
        ):
            object.__setattr__(
                self,
                field_name,
                validated_non_negative_integer(
                    getattr(self, field_name),
                    field_name,
                ),
            )
        physical_frame_ids = _validated_physical_frame_ids(
            self.physical_frame_ids
        )
        object.__setattr__(self, "physical_frame_ids", physical_frame_ids)
        _validate_draft(self.draft, self.frame_count)
        active_frame_index = validated_non_negative_integer(
            self.active_frame_index,
            "active_frame_index",
        )
        if active_frame_index >= self.frame_count:
            raise ValueError("active_frame_index must identify a series frame.")
        object.__setattr__(self, "active_frame_index", active_frame_index)
        if not isinstance(self.run, DomainAnalysisWorkspaceRunState):
            raise TypeError("run must be a DomainAnalysisWorkspaceRunState.")
        if not isinstance(self.is_shutdown, bool):
            raise TypeError("is_shutdown must be a bool.")
        _validate_snapshot_references(self)
        object.__setattr__(
            self,
            "draft_fingerprint",
            _request_fingerprint(self.draft),
        )

    @property
    def frame_count(self) -> int:
        return len(self.physical_frame_ids)

    @property
    def active_physical_frame_id(self) -> str:
        return self.physical_frame_ids[self.active_frame_index]


@dataclass(frozen=True)
class ReplaceDomainAnalysisDraft:
    draft: DomainAnalysisRequest


@dataclass(frozen=True)
class PublishDomainAnalysisResult:
    request: DomainAnalysisRequest
    result: DomainAnalysisResult


@dataclass(frozen=True)
class SelectDomainComponent:
    component: DomainComponentKey | None


@dataclass(frozen=True)
class SetDomainAnalysisFrame:
    frame_index: int


DomainAnalysisWorkspaceAction = (
    ReplaceDomainAnalysisDraft
    | PublishDomainAnalysisResult
    | SelectDomainComponent
    | SetDomainAnalysisFrame
    | DomainAnalysisLifecycleAction
)
class DomainAnalysisWorkspaceController:
    """Qt-free owner of the draft, publication, and frame-local selection."""

    def __init__(
        self,
        draft: DomainAnalysisRequest,
        *,
        physical_frame_ids: tuple[str, ...],
        series_generation: int = 0,
        execution: DomainAnalysisWorkspaceExecution | None = None,
    ) -> None:
        self._lock = RLock()
        self._snapshot = DomainAnalysisWorkspaceSnapshot(
            series_generation=series_generation,
            physical_frame_ids=physical_frame_ids,
            revision=0,
            draft_revision=0,
            published_revision=0,
            draft=draft,
            published=None,
            active_frame_index=draft.frame_range.start,
        )
        self._state_changed = DomainAnalysisWorkspaceStateChanged[
            DomainAnalysisWorkspaceSnapshot
        ]()
        if execution is not None and not isinstance(
            execution,
            DomainAnalysisWorkspaceExecution,
        ):
            raise TypeError("execution must be a DomainAnalysisWorkspaceExecution.")
        self._execution = execution

    @property
    def snapshot(self) -> DomainAnalysisWorkspaceSnapshot:
        with self._lock:
            return self._snapshot

    @property
    def state_changed(
        self,
    ) -> DomainAnalysisWorkspaceStateChanged[DomainAnalysisWorkspaceSnapshot]:
        return self._state_changed

    def dispatch(
        self,
        action: DomainAnalysisWorkspaceAction,
    ) -> DomainAnalysisWorkspaceSnapshot:
        deferred_shutdown: DomainAnalysisWorkspaceExecution | None = None
        notification_error: Exception | None = None
        with self._lock:
            if isinstance(action, StartDomainAnalysis) and self._execution is None:
                raise DomainAnalysisWorkspaceIntentError(
                    "Domain Analysis execution is not configured."
                )
            updated = _reduce_workspace(self._snapshot, action)
            if updated is self._snapshot:
                return updated
            self._snapshot = updated
            if isinstance(
                action,
                (StartDomainAnalysis, CancelDomainAnalysis, ShutdownDomainAnalysis),
            ) and self._execution is not None:
                if isinstance(action, ShutdownDomainAnalysis):
                    deferred_shutdown = self._execution
                else:
                    self._execution.perform(action, updated, self.dispatch)
            if self._snapshot is not updated:
                return self._snapshot
            try:
                self._state_changed.emit(updated)
            except Exception as error:
                notification_error = error
        if deferred_shutdown is not None:
            deferred_shutdown.perform(
                cast(DomainAnalysisLifecycleAction, action),
                updated,
                self.dispatch,
            )
        if notification_error is not None:
            raise DomainAnalysisWorkspaceNotificationError(
                updated
            ) from notification_error
        return self.snapshot


def _reduce_workspace(
    snapshot: DomainAnalysisWorkspaceSnapshot,
    action: DomainAnalysisWorkspaceAction,
) -> DomainAnalysisWorkspaceSnapshot:
    if isinstance(action, ReplaceDomainAnalysisDraft):
        if snapshot.run.status == "running":
            raise DomainAnalysisWorkspaceIntentError(
                "The Domain Analysis draft cannot be edited while a run is active."
            )
        if action.draft == snapshot.draft:
            return snapshot
        return replace(
            snapshot,
            revision=snapshot.revision + 1,
            draft_revision=snapshot.draft_revision + 1,
            draft=action.draft,
        )
    if isinstance(action, PublishDomainAnalysisResult):
        if snapshot.run.status == "running":
            raise DomainAnalysisWorkspaceIntentError(
                "A result cannot be published directly while a run is active."
            )
        return _publish_result(snapshot, action.request, action.result)
    if isinstance(action, SelectDomainComponent):
        return _select_component(snapshot, action.component)
    if isinstance(action, SetDomainAnalysisFrame):
        return _set_active_frame(snapshot, action.frame_index)
    return reduce_domain_analysis_lifecycle(
        snapshot,
        cast(DomainAnalysisLifecycleAction, action),
        _publish_result,
    )


def _publish_result(
    snapshot: DomainAnalysisWorkspaceSnapshot,
    request: DomainAnalysisRequest,
    result: DomainAnalysisResult,
) -> DomainAnalysisWorkspaceSnapshot:
    _validate_series_request(
        request,
        snapshot.frame_count,
        label="Published request",
    )
    publication = DomainAnalysisPublication(request, result)
    _validate_publication_series(publication, snapshot.physical_frame_ids)
    selection = snapshot.selected_component
    if selection is not None and not _publication_contains(
        publication,
        selection,
    ):
        selection = None
    return replace(
        snapshot,
        revision=snapshot.revision + 1,
        published_revision=snapshot.published_revision + 1,
        published=publication,
        selected_component=selection,
    )


def _select_component(
    snapshot: DomainAnalysisWorkspaceSnapshot,
    component: DomainComponentKey | None,
) -> DomainAnalysisWorkspaceSnapshot:
    if component is not None and not isinstance(component, DomainComponentKey):
        raise TypeError("component must be a DomainComponentKey.")
    if component == snapshot.selected_component:
        return snapshot
    if component is not None:
        diagnosis = _component_reference_diagnosis(snapshot, component)
        if diagnosis is not None:
            raise DomainAnalysisWorkspaceIntentError(diagnosis)
    return replace(
        snapshot,
        revision=snapshot.revision + 1,
        selected_component=component,
    )


def _set_active_frame(
    snapshot: DomainAnalysisWorkspaceSnapshot,
    frame_index: int,
) -> DomainAnalysisWorkspaceSnapshot:
    frame_index = validated_non_negative_integer(frame_index, "frame_index")
    if frame_index >= snapshot.frame_count:
        raise DomainAnalysisWorkspaceIntentError(
            "Active frame must identify a Working Image Series frame."
        )
    if frame_index == snapshot.active_frame_index:
        return snapshot
    return replace(
        snapshot,
        revision=snapshot.revision + 1,
        active_frame_index=frame_index,
        selected_component=None,
    )


def _validate_snapshot_references(
    snapshot: DomainAnalysisWorkspaceSnapshot,
) -> None:
    if snapshot.published is not None and not isinstance(
        snapshot.published,
        DomainAnalysisPublication,
    ):
        raise TypeError("published must be a DomainAnalysisPublication.")
    if snapshot.published is not None:
        _validate_series_request(
            snapshot.published.request,
            snapshot.frame_count,
            label="Published request",
        )
        _validate_publication_series(
            snapshot.published,
            snapshot.physical_frame_ids,
        )
    selection = snapshot.selected_component
    if selection is None:
        return
    if not isinstance(selection, DomainComponentKey):
        raise TypeError("selected_component must be a DomainComponentKey.")
    diagnosis = _component_reference_diagnosis(snapshot, selection)
    if diagnosis is not None:
        raise ValueError(diagnosis)


def _component_reference_diagnosis(
    snapshot: DomainAnalysisWorkspaceSnapshot,
    component: DomainComponentKey,
) -> str | None:
    if component.physical_frame_id != snapshot.active_physical_frame_id:
        return "Selected component must belong to the active frame."
    if snapshot.published is None or not _publication_contains(
        snapshot.published,
        component,
    ):
        return "Selected component does not exist in the published result."
    return None


def _publication_contains(
    publication: DomainAnalysisPublication,
    component: DomainComponentKey,
) -> bool:
    gate = publication.result.m6_gate
    if gate is None:
        return False
    frame = next(
        (
            value
            for value in gate.frames
            if value.physical_frame_id == component.physical_frame_id
        ),
        None,
    )
    if frame is None:
        return False
    return component.lattice_domain_id in {
        value.lattice_domain_id
        for value in frame.full_domains + frame.small_ordered_islands
    }


def _validate_draft(draft: DomainAnalysisRequest, frame_count: int) -> None:
    _validate_series_request(draft, frame_count, label="Draft")


def _validate_series_request(
    request: DomainAnalysisRequest,
    frame_count: int,
    *,
    label: str,
) -> None:
    if not isinstance(request, DomainAnalysisRequest):
        raise TypeError(f"{label} must be a DomainAnalysisRequest.")
    if request.frame_range.stop > frame_count:
        raise DomainAnalysisWorkspaceIntentError(
            f"{label} frame range must stay within the Working Image Series."
        )


def _validated_physical_frame_ids(
    physical_frame_ids: tuple[str, ...],
) -> tuple[str, ...]:
    if not isinstance(physical_frame_ids, tuple):
        raise TypeError("physical_frame_ids must be a tuple.")
    validated = tuple(
        validated_text(value, "physical_frame_id")
        for value in physical_frame_ids
    )
    if not validated:
        raise ValueError("physical_frame_ids must not be empty.")
    if len(set(validated)) != len(validated):
        raise ValueError("physical_frame_ids must be unique.")
    return validated


def _validate_publication_series(
    publication: DomainAnalysisPublication,
    physical_frame_ids: tuple[str, ...],
) -> None:
    gate = publication.result.m6_gate
    if gate is None:
        raise DomainAnalysisWorkspaceIntentError(
            "Published result must contain the M6 gate."
        )
    for frame in gate.frames:
        if frame.physical_frame_id != physical_frame_ids[frame.frame_index]:
            raise DomainAnalysisWorkspaceIntentError(
                "Published result frames must belong to the current "
                "Working Image Series."
            )


def _request_fingerprint(request: DomainAnalysisRequest) -> str:
    return canonical_sha256({
        "schema_version": "domain-analysis-workspace-draft-v1",
        "frame_indices": request.frame_indices,
        "geometry_mode": request.geometry_mode,
        "classifier_ids": request.classifier_ids,
    })
