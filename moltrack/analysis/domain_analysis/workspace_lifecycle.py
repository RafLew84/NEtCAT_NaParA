from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from threading import Event, RLock
from typing import TYPE_CHECKING, Protocol

from .geometry import DomainAnalysisSeries
from .models import (
    DomainAnalysisEvent,
    DomainAnalysisRequest,
    DomainAnalysisResult,
)
from .module import DomainAnalysisModule
from .workspace_lifecycle_actions import (
    CancelDomainAnalysis,
    DomainAnalysisLifecycleAction,
    DomainAnalysisWorkspaceIntentError,
    DomainAnalysisWorkspaceRunIdentity,
    DomainAnalysisWorkspaceRunState,
    ReceiveDomainAnalysisEvent,
    ReceiveDomainAnalysisFailure,
    ReceiveDomainAnalysisResult,
    ShutdownDomainAnalysis,
    StartDomainAnalysis,
)

if TYPE_CHECKING:
    from .workspace_controller import DomainAnalysisWorkspaceSnapshot


class DomainAnalysisExecutor(Protocol):
    """Schedules controller-owned work outside the caller's event loop."""

    def submit(self, job: Callable[[], None]) -> None: ...

    def shutdown(self) -> None: ...


DispatchLifecycleAction = Callable[[DomainAnalysisLifecycleAction], object]
PublishLifecycleResult = Callable[
    [
        "DomainAnalysisWorkspaceSnapshot",
        DomainAnalysisRequest,
        DomainAnalysisResult,
    ],
    "DomainAnalysisWorkspaceSnapshot",
]


class DomainAnalysisWorkspaceExecution:
    """Execute module work and return every outcome through dispatch."""

    def __init__(
        self,
        module: DomainAnalysisModule,
        series: DomainAnalysisSeries,
        executor: DomainAnalysisExecutor,
    ) -> None:
        self._module = module
        self._series = series
        self._executor = executor
        self._lock = RLock()
        self._active_identity: DomainAnalysisWorkspaceRunIdentity | None = None
        self._cancel_requested: Event | None = None
        self._is_shutdown = False

    def perform(
        self,
        action: DomainAnalysisLifecycleAction,
        snapshot: DomainAnalysisWorkspaceSnapshot,
        dispatch: DispatchLifecycleAction,
    ) -> None:
        if isinstance(action, StartDomainAnalysis):
            identity = snapshot.run.identity
            request = snapshot.run.request
            if identity is None or request is None:
                raise AssertionError("A started run must identify its request.")
            self._start(identity, request, dispatch)
        elif isinstance(action, CancelDomainAnalysis):
            if snapshot.run.identity is not None:
                self._cancel(snapshot.run.identity)
        elif isinstance(action, ShutdownDomainAnalysis):
            self._shutdown()

    def _start(
        self,
        identity: DomainAnalysisWorkspaceRunIdentity,
        request: DomainAnalysisRequest,
        dispatch: DispatchLifecycleAction,
    ) -> None:
        with self._lock:
            if self._is_shutdown:
                raise RuntimeError("Domain Analysis execution is shut down.")
            cancel_requested = Event()
            self._active_identity = identity
            self._cancel_requested = cancel_requested

        def deliver(action: DomainAnalysisLifecycleAction) -> None:
            with self._lock:
                can_deliver = not self._is_shutdown
            if can_deliver:
                dispatch(action)

        try:
            self._executor.submit(lambda: self._run(
                identity,
                request,
                cancel_requested,
                deliver,
            ))
        except Exception as error:
            self._finish(identity)
            deliver(ReceiveDomainAnalysisFailure(
                identity,
                str(error) or error.__class__.__name__,
            ))

    def _run(
        self,
        identity: DomainAnalysisWorkspaceRunIdentity,
        request: DomainAnalysisRequest,
        cancel_requested: Event,
        deliver: Callable[[DomainAnalysisLifecycleAction], None],
    ) -> None:
        try:
            result = self._module.run(
                self._series,
                request,
                on_event=lambda event: deliver(
                    ReceiveDomainAnalysisEvent(identity, event)
                ),
                is_cancelled=cancel_requested.is_set,
            )
        except Exception as error:
            deliver(ReceiveDomainAnalysisFailure(
                identity,
                str(error) or error.__class__.__name__,
            ))
        else:
            deliver(ReceiveDomainAnalysisResult(identity, result))
        finally:
            self._finish(identity)

    def _finish(self, identity: DomainAnalysisWorkspaceRunIdentity) -> None:
        with self._lock:
            if self._active_identity == identity:
                self._active_identity = None
                self._cancel_requested = None

    def _cancel(self, identity: DomainAnalysisWorkspaceRunIdentity) -> None:
        with self._lock:
            if (
                self._active_identity == identity
                and self._cancel_requested is not None
            ):
                self._cancel_requested.set()

    def _shutdown(self) -> None:
        with self._lock:
            if self._is_shutdown:
                return
            self._is_shutdown = True
            if self._cancel_requested is not None:
                self._cancel_requested.set()
            self._active_identity = None
            self._cancel_requested = None
        self._executor.shutdown()


def reduce_domain_analysis_lifecycle(
    snapshot: DomainAnalysisWorkspaceSnapshot,
    action: DomainAnalysisLifecycleAction,
    publish_result: PublishLifecycleResult,
) -> DomainAnalysisWorkspaceSnapshot:
    """Reduce one lifecycle action without executing external work."""
    if snapshot.is_shutdown and isinstance(
        action,
        (
            ReceiveDomainAnalysisEvent,
            ReceiveDomainAnalysisResult,
            ReceiveDomainAnalysisFailure,
        ),
    ):
        return snapshot
    if isinstance(action, StartDomainAnalysis):
        return _start_run(snapshot)
    if isinstance(action, CancelDomainAnalysis):
        return _cancel_run(snapshot)
    if isinstance(action, ShutdownDomainAnalysis):
        return _shutdown_workspace(snapshot)
    if isinstance(action, ReceiveDomainAnalysisEvent):
        return _receive_run_event(snapshot, action)
    if isinstance(action, ReceiveDomainAnalysisResult):
        return _receive_run_result(snapshot, action, publish_result)
    if isinstance(action, ReceiveDomainAnalysisFailure):
        return _receive_run_failure(snapshot, action)
    raise TypeError(f"Unsupported lifecycle action: {type(action).__name__}.")


def _start_run(
    snapshot: DomainAnalysisWorkspaceSnapshot,
) -> DomainAnalysisWorkspaceSnapshot:
    if snapshot.is_shutdown:
        raise DomainAnalysisWorkspaceIntentError(
            "A shut-down Domain Analysis workspace cannot start a run."
        )
    if snapshot.run.status == "running":
        raise DomainAnalysisWorkspaceIntentError(
            "A Domain Analysis request is already running."
        )
    previous_identity = snapshot.run.identity
    identity = DomainAnalysisWorkspaceRunIdentity(
        series_generation=snapshot.series_generation,
        run_id=1 if previous_identity is None else previous_identity.run_id + 1,
        request_fingerprint=snapshot.draft_fingerprint,
    )
    return replace(
        snapshot,
        revision=snapshot.revision + 1,
        run=DomainAnalysisWorkspaceRunState(
            status="running",
            identity=identity,
            request=snapshot.draft,
            event=DomainAnalysisEvent(
                stage_id="run",
                status="started",
                message="Domain Analysis request scheduled.",
            ),
        ),
    )


def _cancel_run(
    snapshot: DomainAnalysisWorkspaceSnapshot,
) -> DomainAnalysisWorkspaceSnapshot:
    if snapshot.run.status != "running":
        return snapshot
    return replace(
        snapshot,
        revision=snapshot.revision + 1,
        run=replace(
            snapshot.run,
            status="canceled",
            event=DomainAnalysisEvent(
                stage_id="run",
                status="canceled",
                message="Domain Analysis cancellation requested.",
            ),
            diagnosis=None,
        ),
    )


def _shutdown_workspace(
    snapshot: DomainAnalysisWorkspaceSnapshot,
) -> DomainAnalysisWorkspaceSnapshot:
    if snapshot.is_shutdown:
        return snapshot
    run = snapshot.run
    if run.status == "running":
        run = replace(
            run,
            status="canceled",
            event=DomainAnalysisEvent(
                stage_id="run",
                status="canceled",
                message="Domain Analysis workspace shut down.",
            ),
            diagnosis=None,
        )
    return replace(
        snapshot,
        revision=snapshot.revision + 1,
        run=run,
        is_shutdown=True,
    )


def _receive_run_event(
    snapshot: DomainAnalysisWorkspaceSnapshot,
    action: ReceiveDomainAnalysisEvent,
) -> DomainAnalysisWorkspaceSnapshot:
    if action.identity != snapshot.run.identity:
        return _record_stale_response(snapshot, action.identity, "event")
    if snapshot.run.status != "running":
        return snapshot
    return replace(
        snapshot,
        revision=snapshot.revision + 1,
        run=replace(snapshot.run, event=action.event, diagnosis=None),
    )


def _receive_run_result(
    snapshot: DomainAnalysisWorkspaceSnapshot,
    action: ReceiveDomainAnalysisResult,
    publish_result: PublishLifecycleResult,
) -> DomainAnalysisWorkspaceSnapshot:
    if action.identity != snapshot.run.identity:
        return _record_stale_response(snapshot, action.identity, "result")
    if snapshot.run.status != "running":
        return snapshot
    if action.result.run_status in {"completed", "completed_with_errors"}:
        request = snapshot.run.request
        if request is None:
            raise AssertionError("A running workspace must retain its request.")
        published = publish_result(snapshot, request, action.result)
        return replace(
            published,
            run=replace(
                snapshot.run,
                status=action.result.run_status,
                diagnosis=None,
            ),
        )
    return replace(
        snapshot,
        revision=snapshot.revision + 1,
        run=replace(
            snapshot.run,
            status=action.result.run_status,
            diagnosis=(
                None
                if action.result.failure is None
                else action.result.failure.message
            ),
        ),
    )


def _receive_run_failure(
    snapshot: DomainAnalysisWorkspaceSnapshot,
    action: ReceiveDomainAnalysisFailure,
) -> DomainAnalysisWorkspaceSnapshot:
    if action.identity != snapshot.run.identity:
        return _record_stale_response(snapshot, action.identity, "failure")
    if snapshot.run.status != "running":
        return snapshot
    return replace(
        snapshot,
        revision=snapshot.revision + 1,
        run=replace(
            snapshot.run,
            status="failed",
            event=DomainAnalysisEvent(
                stage_id="run",
                status="failed",
                message=action.message,
            ),
            diagnosis=action.message,
        ),
    )


def _record_stale_response(
    snapshot: DomainAnalysisWorkspaceSnapshot,
    identity: DomainAnalysisWorkspaceRunIdentity,
    response_kind: str,
) -> DomainAnalysisWorkspaceSnapshot:
    return replace(
        snapshot,
        revision=snapshot.revision + 1,
        run=replace(
            snapshot.run,
            diagnosis=(
                f"Ignored stale {response_kind} for run {identity.run_id}."
            ),
        ),
    )
