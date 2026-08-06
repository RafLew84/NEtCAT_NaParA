from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from moltrack.analysis.domain_analysis import (
    DomainAnalysisPublication,
    DomainAnalysisRequest,
    DomainAnalysisResult,
    DomainAnalysisWorkspaceController,
    DomainAnalysisWorkspaceIntentError,
    DomainAnalysisWorkspaceNotificationError,
    DomainAnalysisWorkspaceSnapshot,
    DomainComponentKey,
    M6FrameGate,
    M6Gate,
    M6PresentationProvenance,
    M6PublishedComponent,
    M6PublishedMolecule,
    PublishDomainAnalysisResult,
    ReplaceDomainAnalysisDraft,
    SelectDomainComponent,
    SetDomainAnalysisFrame,
)


def _frame_gate(
    frame_index: int,
    *,
    physical_id_prefix: str = "physical-frame",
) -> M6FrameGate:
    source_id = f"molecule-{frame_index}"
    component = M6PublishedComponent(
        lattice_domain_id="local-domain-1",
        component_type="full_domain",
        members=(M6PublishedMolecule(
            source_id=source_id,
            source_kind="segmentation",
            point_xy_nm=(0.0, 0.0),
        ),),
        core_source_ids=(source_id,),
        halo_source_ids=(),
        footprint_pixels_xy=((0, 0),),
        footprint_area_nm2=1.0,
        centroid_xy_nm=(0.0, 0.0),
        bounds_xyxy_nm=(0.0, 0.0, 0.0, 0.0),
    )
    return M6FrameGate(
        frame_index=frame_index,
        physical_frame_id=f"{physical_id_prefix}-{frame_index}",
        coordinate_frame="series_physical_nm",
        coordinate_transform_fingerprint="transform-v1",
        presentation_provenance=M6PresentationProvenance(
            raw_shape=(1, 1),
            expanded_shape=(1, 1),
            source_view="raw",
            frame_origin_xy=(0.0, 0.0),
            canvas_offset_xy=(0.0, 0.0),
            registration_fingerprint="registration-v1",
        ),
        source_geometry_fingerprint=f"geometry-{frame_index}",
        m6_settings_fingerprint="m6-settings-v1",
        m6_algorithm_version="m6-algorithm-v1",
        pixel_area_nm2=1.0,
        full_domains=(component,),
        small_ordered_islands=(),
        outside_members=(),
        outside_pixels_xy=(),
        outside_area_nm2=0.0,
        analyzed_source_ids=(source_id,),
        analyzed_pixels_xy=((0, 0),),
        analyzed_area_nm2=1.0,
    )


def _completed_result(
    frame_range: range,
    *,
    physical_id_prefix: str = "physical-frame",
) -> DomainAnalysisResult:
    return DomainAnalysisResult(
        run_status="completed",
        m6_gate=M6Gate(frames=tuple(
            _frame_gate(frame_index, physical_id_prefix=physical_id_prefix)
            for frame_index in frame_range
        )),
        classifier_status="not_requested",
    )


def test_workspace_dispatch_keeps_draft_publication_and_selection_separate() -> None:
    published_request = DomainAnalysisRequest(frame_range=range(2))
    edited_request = DomainAnalysisRequest(
        frame_range=range(2),
        geometry_mode="bbox_centers",
    )
    changed: list[DomainAnalysisWorkspaceSnapshot] = []
    controller = DomainAnalysisWorkspaceController(
        published_request,
        physical_frame_ids=("physical-frame-0", "physical-frame-1"),
        series_generation=7,
    )
    controller.state_changed.connect(changed.append)

    published = controller.dispatch(PublishDomainAnalysisResult(
        request=published_request,
        result=_completed_result(range(2)),
    ))
    edited = controller.dispatch(ReplaceDomainAnalysisDraft(edited_request))
    selected = controller.dispatch(SelectDomainComponent(
        DomainComponentKey(
            physical_frame_id="physical-frame-0",
            lattice_domain_id="local-domain-1",
        ),
    ))

    assert isinstance(published.published, DomainAnalysisPublication)
    assert published.published.request == published_request
    assert edited.draft == edited_request
    assert edited.published == published.published
    assert selected.selected_component == DomainComponentKey(
        physical_frame_id="physical-frame-0",
        lattice_domain_id="local-domain-1",
    )
    assert selected.series_generation == 7
    assert selected.revision == 3
    assert selected.draft_revision == 1
    assert selected.published_revision == 1
    assert changed == [published, edited, selected]
    assert controller.snapshot is selected

    with pytest.raises(FrozenInstanceError):
        selected.revision = 99  # type: ignore[misc]


def test_workspace_selection_is_local_to_the_active_frame() -> None:
    request = DomainAnalysisRequest(frame_range=range(2))
    controller = DomainAnalysisWorkspaceController(
        request,
        physical_frame_ids=("physical-frame-0", "physical-frame-1"),
    )
    controller.dispatch(PublishDomainAnalysisResult(
        request=request,
        result=_completed_result(range(2)),
    ))
    frame_zero = DomainComponentKey("physical-frame-0", "local-domain-1")
    frame_one = DomainComponentKey("physical-frame-1", "local-domain-1")
    controller.dispatch(SelectDomainComponent(frame_zero))

    changed_frame = controller.dispatch(SetDomainAnalysisFrame(1))

    assert changed_frame.active_frame_index == 1
    assert changed_frame.selected_component is None
    before_invalid = controller.snapshot
    with pytest.raises(
        DomainAnalysisWorkspaceIntentError,
        match="must belong to the active frame",
    ):
        controller.dispatch(SelectDomainComponent(frame_zero))
    assert controller.snapshot is before_invalid

    selected = controller.dispatch(SelectDomainComponent(frame_one))
    assert selected.selected_component == frame_one
    returned = controller.dispatch(SetDomainAnalysisFrame(0))
    assert returned.selected_component is None


def test_workspace_rejects_invalid_references_without_partial_state() -> None:
    initial_request = DomainAnalysisRequest(frame_range=range(2))
    out_of_series_request = DomainAnalysisRequest(frame_range=range(1, 3))
    changed: list[DomainAnalysisWorkspaceSnapshot] = []
    controller = DomainAnalysisWorkspaceController(
        initial_request,
        physical_frame_ids=("physical-frame-0", "physical-frame-1"),
    )
    controller.state_changed.connect(changed.append)
    initial = controller.snapshot

    with pytest.raises(
        DomainAnalysisWorkspaceIntentError,
        match="Published request frame range must stay within",
    ):
        controller.dispatch(PublishDomainAnalysisResult(
            request=out_of_series_request,
            result=_completed_result(range(1, 3)),
        ))

    assert controller.snapshot is initial
    assert changed == []
    with pytest.raises(
        DomainAnalysisWorkspaceIntentError,
        match="must belong to the current Working Image Series",
    ):
        controller.dispatch(PublishDomainAnalysisResult(
            request=initial_request,
            result=_completed_result(
                range(2),
                physical_id_prefix="stale-frame",
            ),
        ))

    assert controller.snapshot is initial
    assert changed == []
    controller.dispatch(PublishDomainAnalysisResult(
        request=initial_request,
        result=_completed_result(range(2)),
    ))
    before_missing = controller.snapshot
    with pytest.raises(
        DomainAnalysisWorkspaceIntentError,
        match="does not exist in the published result",
    ):
        controller.dispatch(SelectDomainComponent(
            DomainComponentKey("physical-frame-0", "missing-domain"),
        ))
    assert controller.snapshot is before_missing
    assert changed == [before_missing]


def test_workspace_reports_notification_failure_after_committing_state() -> None:
    request = DomainAnalysisRequest(frame_range=range(1))

    def fail_notification(_snapshot: object) -> None:
        raise RuntimeError("adapter failed")

    controller = DomainAnalysisWorkspaceController(
        request,
        physical_frame_ids=("physical-frame-0",),
    )
    controller.state_changed.connect(fail_notification)

    with pytest.raises(
        DomainAnalysisWorkspaceNotificationError,
        match="state was committed",
    ) as raised:
        controller.dispatch(ReplaceDomainAnalysisDraft(
            DomainAnalysisRequest(
                frame_range=range(1),
                geometry_mode="bbox_centers",
            ),
        ))

    assert raised.value.committed_snapshot is controller.snapshot
    assert controller.snapshot.draft.geometry_mode == "bbox_centers"
