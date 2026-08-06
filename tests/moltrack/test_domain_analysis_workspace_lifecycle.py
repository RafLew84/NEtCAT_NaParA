from __future__ import annotations

from collections.abc import Callable

import pytest

from moltrack.analysis.domain_analysis import (
    CancelDomainAnalysis,
    DomainAnalysisExecutor,
    DomainAnalysisFrame,
    DomainAnalysisModule,
    DomainAnalysisRequest,
    DomainAnalysisSeries,
    DomainAnalysisWorkspaceController,
    DomainAnalysisWorkspaceExecution,
    DomainAnalysisWorkspaceIntentError,
    DomainAnalysisWorkspaceSnapshot,
    DomainAnalysisWorkspaceSubscription,
    M6CanonicalFrame,
    M6ComponentMembership,
    M6FrameComputation,
    M6FrameAnalysisError,
    M6FrameGeometry,
    M6SourceAnnotation,
    PublishDomainAnalysisResult,
    ReceiveDomainAnalysisFailure,
    ReplaceDomainAnalysisDraft,
    ShutdownDomainAnalysis,
    StartDomainAnalysis,
)


class _ManualExecutor:
    def __init__(self) -> None:
        self.jobs: list[Callable[[], None]] = []
        self.is_shutdown = False

    def submit(self, job: Callable[[], None]) -> None:
        if self.is_shutdown:
            raise RuntimeError("executor is shut down")
        self.jobs.append(job)

    def shutdown(self) -> None:
        self.is_shutdown = True
        self.jobs.clear()

    def run_next(self) -> None:
        self.jobs.pop(0)()


class _RejectingExecutor:
    def submit(self, job: Callable[[], None]) -> None:
        del job
        raise RuntimeError("executor queue unavailable")

    def shutdown(self) -> None:
        pass


class _SingleDomainM6Adapter:
    m6_settings_fingerprint = "m6-settings-v1"
    m6_algorithm_version = "m6-algorithm-v1"

    def __init__(self, failure_message: str | None = None) -> None:
        self.failure_message = failure_message

    def analyze_frame(
        self,
        frame: M6CanonicalFrame,
        *,
        frame_index: int,
        geometry_mode: str,
    ) -> M6FrameComputation:
        del geometry_mode
        if self.failure_message is not None:
            raise M6FrameAnalysisError(self.failure_message)
        source_ids = tuple(value.source_id for value in frame.molecules)
        return M6FrameComputation(
            frame_index=frame_index,
            molecules=frame.molecules,
            analyzed_pixels_xy=frame.analyzed_pixels_xy,
            pixel_area_nm2=frame.pixel_area_nm2,
            full_domains=(M6ComponentMembership(
                lattice_domain_id="backend-domain",
                source_ids=source_ids,
                core_source_ids=source_ids,
            ),),
            small_ordered_islands=(),
            coordinate_frame=frame.coordinate_frame,
            coordinate_transform_fingerprint=(
                frame.coordinate_transform_fingerprint
            ),
            m6_settings_fingerprint=self.m6_settings_fingerprint,
        )


def _series(frame_count: int = 2) -> DomainAnalysisSeries:
    annotation = M6SourceAnnotation(
        source_id="molecule-1",
        source_view="raw",
        bbox_xyxy=(0.0, 0.0, 1.0, 1.0),
    )
    return DomainAnalysisSeries(frames=tuple(
        DomainAnalysisFrame(
            frame_index=frame_index,
            source_view="raw",
            geometry=M6FrameGeometry(
                physical_frame_id=f"physical-frame-{frame_index}",
                raw_shape=(1, 1),
                expanded_shape=(1, 1),
                frame_origin_xy=(0.0, 0.0),
                canvas_offset_xy=(0.0, 0.0),
                pixel_size_nm=(1.0, 1.0),
                scan_angle_deg=0.0,
                registration_fingerprint="registration-v1",
            ),
            annotations=(annotation,),
        )
        for frame_index in range(frame_count)
    ))


def _controller(
    request: DomainAnalysisRequest,
    series: DomainAnalysisSeries,
    executor: DomainAnalysisExecutor,
    *,
    failure_message: str | None = None,
    series_generation: int = 0,
) -> DomainAnalysisWorkspaceController:
    return DomainAnalysisWorkspaceController(
        request,
        physical_frame_ids=tuple(
            frame.geometry.physical_frame_id for frame in series.frames
        ),
        series_generation=series_generation,
        execution=DomainAnalysisWorkspaceExecution(
            DomainAnalysisModule(
                _SingleDomainM6Adapter(failure_message),
                classifier_adapters={},
            ),
            series,
            executor,
        ),
    )


def test_workspace_runs_current_request_through_progress_to_publication() -> None:
    series = _series()
    request = DomainAnalysisRequest(frame_range=range(2))
    executor = _ManualExecutor()
    changed: list[DomainAnalysisWorkspaceSnapshot] = []
    controller = _controller(
        request,
        series,
        executor,
        series_generation=4,
    )
    controller.state_changed.connect(changed.append)

    started = controller.dispatch(StartDomainAnalysis())

    assert started.run.status == "running"
    assert started.run.request == request
    assert started.run.identity is not None
    assert started.run.identity.series_generation == 4
    assert started.run.identity.run_id == 1
    assert started.run.identity.request_fingerprint == started.draft_fingerprint
    assert started.published is None
    assert len(executor.jobs) == 1

    executor.run_next()

    completed = controller.snapshot
    assert completed.run.status == "completed"
    assert completed.run.event is not None
    assert completed.run.event.status == "completed"
    assert completed.published is not None
    assert completed.published.request == request
    assert completed.published.request_fingerprint == (
        started.run.identity.request_fingerprint
    )
    assert completed.published_revision == 1
    assert any(
        snapshot.run.event is not None
        and snapshot.run.event.status == "progress"
        for snapshot in changed
    )


def test_workspace_ignores_a_canceled_response_after_a_newer_run_starts() -> None:
    series = _series()
    first_request = DomainAnalysisRequest(frame_range=range(1))
    second_request = DomainAnalysisRequest(
        frame_range=range(2),
        geometry_mode="bbox_centers",
    )
    executor = _ManualExecutor()
    changed: list[DomainAnalysisWorkspaceSnapshot] = []
    controller = _controller(
        first_request,
        series,
        executor,
    )
    controller.state_changed.connect(changed.append)
    first_run = controller.dispatch(StartDomainAnalysis())

    with pytest.raises(
        DomainAnalysisWorkspaceIntentError,
        match="cannot be edited while",
    ):
        controller.dispatch(ReplaceDomainAnalysisDraft(second_request))
    assert controller.snapshot is first_run

    canceled = controller.dispatch(CancelDomainAnalysis())
    repeated_cancel = controller.dispatch(CancelDomainAnalysis())
    assert canceled.run.status == "canceled"
    assert repeated_cancel is canceled

    controller.dispatch(ReplaceDomainAnalysisDraft(second_request))
    second_run = controller.dispatch(StartDomainAnalysis())
    assert second_run.run.identity is not None
    assert second_run.run.identity.run_id == 2
    before_stale_publication = second_run.published

    executor.run_next()

    ignored = controller.snapshot
    assert ignored.run.status == "running"
    assert ignored.run.identity == second_run.run.identity
    assert ignored.run.diagnosis == "Ignored stale result for run 1."
    assert ignored.published is before_stale_publication

    executor.run_next()

    assert controller.snapshot.run.status == "completed"
    assert controller.snapshot.run.diagnosis is None
    assert controller.snapshot.published is not None
    assert controller.snapshot.published.request == second_request


def test_workspace_shutdown_cancels_work_and_detaches_worker_callbacks() -> None:
    series = _series()
    executor = _ManualExecutor()
    changed: list[DomainAnalysisWorkspaceSnapshot] = []
    controller = _controller(
        DomainAnalysisRequest(frame_range=range(2)),
        series,
        executor,
    )
    controller.state_changed.connect(changed.append)
    controller.dispatch(StartDomainAnalysis())

    shut_down = controller.dispatch(ShutdownDomainAnalysis())

    assert shut_down.is_shutdown is True
    assert shut_down.run.status == "canceled"
    assert executor.is_shutdown is True
    assert executor.jobs == []
    assert controller.dispatch(ShutdownDomainAnalysis()) is shut_down
    assert changed[-1] is shut_down


def test_workspace_exposes_a_failed_run_without_publishing_a_result() -> None:
    series = _series(frame_count=1)
    executor = _ManualExecutor()
    controller = _controller(
        DomainAnalysisRequest(frame_range=range(1)),
        series,
        executor,
        failure_message="controlled M6 failure",
    )
    assert controller.snapshot.run.status == "idle"
    controller.dispatch(StartDomainAnalysis())

    executor.run_next()

    failed = controller.snapshot
    assert failed.run.status == "failed"
    assert failed.run.event is not None
    assert failed.run.event.status == "failed"
    assert failed.run.diagnosis == "controlled M6 failure"
    assert failed.published is None


def test_cancel_keeps_the_previous_publication_unchanged() -> None:
    series = _series()
    first_request = DomainAnalysisRequest(frame_range=range(1))
    second_request = DomainAnalysisRequest(
        frame_range=range(2),
        geometry_mode="bbox_centers",
    )
    executor = _ManualExecutor()
    controller = _controller(
        first_request,
        series,
        executor,
    )
    controller.dispatch(StartDomainAnalysis())
    executor.run_next()
    first_publication = controller.snapshot.published
    assert first_publication is not None
    controller.dispatch(ReplaceDomainAnalysisDraft(second_request))
    running = controller.dispatch(StartDomainAnalysis())

    with pytest.raises(
        DomainAnalysisWorkspaceIntentError,
        match="cannot be published directly while",
    ):
        controller.dispatch(PublishDomainAnalysisResult(
            first_publication.request,
            first_publication.result,
        ))
    assert controller.snapshot is running

    canceled = controller.dispatch(CancelDomainAnalysis())

    assert canceled.run.status == "canceled"
    assert canceled.published is first_publication
    assert canceled.published_revision == 1


def test_detaching_one_consumer_does_not_cancel_the_shared_run() -> None:
    series = _series(frame_count=1)
    executor = _ManualExecutor()
    controller = _controller(
        DomainAnalysisRequest(frame_range=range(1)),
        series,
        executor,
    )
    first: list[DomainAnalysisWorkspaceSnapshot] = []
    second: list[DomainAnalysisWorkspaceSnapshot] = []
    first_subscription = controller.state_changed.connect(first.append)
    controller.state_changed.connect(second.append)
    controller.dispatch(StartDomainAnalysis())

    assert first_subscription.disconnect() is True
    assert first_subscription.disconnect() is False
    executor.run_next()

    assert first[-1].run.status == "running"
    assert second[-1].run.status == "completed"
    assert controller.snapshot.run.status == "completed"
    assert executor.is_shutdown is False


def test_disconnect_removes_a_callback_queued_for_the_same_emission() -> None:
    controller = DomainAnalysisWorkspaceController(
        DomainAnalysisRequest(frame_range=range(1)),
        physical_frame_ids=("physical-frame-0",),
    )
    closed_consumer: list[DomainAnalysisWorkspaceSnapshot] = []
    subscription_holder: list[DomainAnalysisWorkspaceSubscription] = []

    def close_other_consumer(_snapshot: DomainAnalysisWorkspaceSnapshot) -> None:
        assert subscription_holder[0].disconnect() is True

    controller.state_changed.connect(close_other_consumer)
    subscription_holder.append(
        controller.state_changed.connect(closed_consumer.append)
    )

    controller.dispatch(ReplaceDomainAnalysisDraft(DomainAnalysisRequest(
        frame_range=range(1),
        geometry_mode="bbox_centers",
    )))

    assert closed_consumer == []


def test_workspace_ignores_an_in_flight_stale_event_after_shutdown() -> None:
    series = _series()
    executor = _ManualExecutor()
    controller = _controller(
        DomainAnalysisRequest(frame_range=range(1)),
        series,
        executor,
    )
    changed: list[DomainAnalysisWorkspaceSnapshot] = []
    controller.state_changed.connect(changed.append)
    first_run = controller.dispatch(StartDomainAnalysis())
    assert first_run.run.identity is not None
    controller.dispatch(CancelDomainAnalysis())
    controller.dispatch(ReplaceDomainAnalysisDraft(DomainAnalysisRequest(
        frame_range=range(2),
        geometry_mode="bbox_centers",
    )))
    controller.dispatch(StartDomainAnalysis())
    shut_down = controller.dispatch(ShutdownDomainAnalysis())
    notification_count = len(changed)

    after_stale = controller.dispatch(ReceiveDomainAnalysisFailure(
        first_run.run.identity,
        "late worker failure",
    ))

    assert after_stale is shut_down
    assert after_stale.run.diagnosis is None
    assert len(changed) == notification_count


def test_executor_rejection_becomes_an_explicit_failed_run() -> None:
    series = _series(frame_count=1)
    controller = _controller(
        DomainAnalysisRequest(frame_range=range(1)),
        series,
        _RejectingExecutor(),
    )

    failed = controller.dispatch(StartDomainAnalysis())

    assert failed is controller.snapshot
    assert failed.run.status == "failed"
    assert failed.run.event is not None
    assert failed.run.event.status == "failed"
    assert failed.run.diagnosis == "executor queue unavailable"
    assert failed.published is None
