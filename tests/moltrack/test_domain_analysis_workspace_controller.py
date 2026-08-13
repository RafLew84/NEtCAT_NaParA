from __future__ import annotations

from dataclasses import FrozenInstanceError
from functools import partial

import pytest

from moltrack.analysis.domain_analysis import (
    ApplyPreparedDomainCorrection,
    DomainAnalysisPublication,
    DomainAnalysisRequest,
    DomainAnalysisResult,
    DomainAnalysisWorkspaceController,
    DomainAnalysisWorkspaceIntentError,
    DomainAnalysisWorkspaceNotificationError,
    DomainAnalysisWorkspaceSnapshot,
    DomainComponentKey,
    DomainHierarchyHighlight,
    DiscardPreparedDomainCorrection,
    DomainBackendIdentity,
    M6_ORIENTATION_COMPONENTS_BACKEND_ID,
    M6FrameGate,
    M6Gate,
    M6PresentationProvenance,
    M6OrientationComponentsEvidence,
    M6PublishedComponent,
    M6PublishedMolecule,
    PublishDomainAnalysisResult,
    PreviewManualOrientation,
    PreviewCreateManualDomain,
    ReplaceDomainAnalysisDraft,
    SelectDomainComponent,
    SelectDomainMolecules,
    SelectDomainMoleculesByPolygons,
    ToggleDomainMoleculeSelection,
    ClearDomainMoleculeSelection,
    SetDomainHierarchyHighlight,
    SetDomainAnalysisFrame,
    StartDomainAnalysis,
)
from moltrack.analysis.domain_analysis.domain_selection import DomainSelectionPolygon
from test_domain_correction_orientation import _automatic_result

DomainAnalysisRequest = partial(
    DomainAnalysisRequest, backend_id=M6_ORIENTATION_COMPONENTS_BACKEND_ID
)


def test_discarding_absent_correction_preview_before_publication_is_a_noop() -> None:
    request = DomainAnalysisRequest(frame_range=range(1))
    controller = DomainAnalysisWorkspaceController(
        request,
        physical_frame_ids=("physical-frame-0",),
    )

    assert controller.dispatch(DiscardPreparedDomainCorrection()) is controller.snapshot
    assert controller.snapshot.revision == 0


def test_workspace_owns_manual_orientation_preview_and_effective_projection() -> None:
    request = DomainAnalysisRequest(frame_range=range(1))
    automatic = _completed_result(range(1))
    controller = DomainAnalysisWorkspaceController(
        request,
        physical_frame_ids=("physical-frame-0",),
    )
    controller.dispatch(PublishDomainAnalysisResult(request, automatic))

    selected = controller.dispatch(SelectDomainMolecules(("molecule-0",)))
    assert selected.domain_corrections.selected_source_ids == ("molecule-0",)

    previewed = controller.dispatch(PreviewManualOrientation("D"))
    preview = previewed.domain_corrections.prepared
    assert preview is not None
    assert preview.changed_source_ids == ("molecule-0",)

    applied = controller.dispatch(ApplyPreparedDomainCorrection.confirmed(preview))
    projection = applied.domain_corrections.effective_projection
    assert projection is not None
    molecule = projection.molecule("physical-frame-0", "molecule-0")
    assert molecule.effective_orientation == "D"
    assert molecule.effective_confidence is None
    assert projection.automatic_result is automatic


def test_manual_domain_apply_clears_only_a_highlight_removed_by_projection() -> None:
    request = DomainAnalysisRequest(frame_range=range(1))
    automatic = _completed_result(range(1))
    controller = DomainAnalysisWorkspaceController(
        request,
        physical_frame_ids=("physical-frame-0",),
    )
    controller.dispatch(PublishDomainAnalysisResult(request, automatic))
    controller.dispatch(SelectDomainMolecules(("molecule-0",)))
    controller.dispatch(SetDomainHierarchyHighlight(DomainHierarchyHighlight(
        "physical-frame-0",
        "domain",
        "local-domain-1",
    )))
    previewed = controller.dispatch(PreviewCreateManualDomain())
    preview = previewed.domain_corrections.prepared
    assert preview is not None

    applied = controller.dispatch(ApplyPreparedDomainCorrection.confirmed(preview))

    assert applied.hierarchy_highlight is None
    projection = applied.domain_corrections.effective_projection
    assert projection is not None
    assert projection.molecule(
        "physical-frame-0",
        "molecule-0",
    ).effective_domain_id == preview.intent.manual_domain_id


def test_polygons_freeze_deduplicated_centroid_selection_until_apply_or_clear() -> None:
    automatic = _automatic_result()
    request = DomainAnalysisRequest(frame_range=range(1))
    controller = DomainAnalysisWorkspaceController(
        request,
        physical_frame_ids=("frame-0",),
    )
    controller.dispatch(PublishDomainAnalysisResult(request, automatic))
    controller.dispatch(ToggleDomainMoleculeSelection("outside"))

    selected = controller.dispatch(SelectDomainMoleculesByPolygons(
        polygons=(
            ((-0.5, -0.5), (1.5, -0.5), (1.5, 1.5), (-0.5, 1.5)),
            ((-0.25, -0.25), (0.75, -0.25), (0.75, 1.25), (-0.25, 1.25)),
        ),
        target_view="raw",
    ))

    correction = selected.domain_corrections
    assert correction.selected_source_ids == ("full", "island", "outside")
    assert correction.selection_polygons == (
        DomainSelectionPolygon(
            ((-0.5, -0.5), (1.5, -0.5), (1.5, 1.5), (-0.5, 1.5)),
        ),
        DomainSelectionPolygon(
            ((-0.25, -0.25), (0.75, -0.25), (0.75, 1.25), (-0.25, 1.25)),
        ),
    )
    previewed = controller.dispatch(PreviewManualOrientation("Z"))
    preview = previewed.domain_corrections.prepared
    assert preview is not None
    assert preview.source_ids == ("full", "island", "outside")
    assert preview.requires_confirmation

    changed = controller.dispatch(ToggleDomainMoleculeSelection("island"))
    assert changed.domain_corrections.prepared is None
    assert changed.domain_corrections.selected_source_ids == (
        "full",
        "outside",
    )
    previewed = controller.dispatch(PreviewManualOrientation("Z"))
    preview = previewed.domain_corrections.prepared
    assert preview is not None
    applied = controller.dispatch(ApplyPreparedDomainCorrection.confirmed(preview))
    assert applied.domain_corrections.selected_source_ids == (
        "full",
        "outside",
    )
    assert applied.domain_corrections.selection_polygons == ()
    assert len(applied.domain_corrections.correction_set.atoms) == 1

    cleared = controller.dispatch(ClearDomainMoleculeSelection())
    assert cleared.domain_corrections.selected_source_ids == ()


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
        backend_identity=DomainBackendIdentity(
            backend_id="m6_orientation_components",
            result_schema_version="domain-backend-result-v1",
            algorithm_version="m6-algorithm-v1",
            settings_fingerprint="m6-settings-v1",
            adapter_owner="workspace-controller-test",
            native_evidence_kind="m6_orientation_evidence_v1",
            capabilities=("common_partition",),
        ),
        native_evidence=M6OrientationComponentsEvidence((), ()),
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


def test_workspace_highlight_is_navigation_independent_from_selection() -> None:
    request = DomainAnalysisRequest(frame_range=range(2))
    controller = DomainAnalysisWorkspaceController(
        request,
        physical_frame_ids=("physical-frame-0", "physical-frame-1"),
    )
    controller.dispatch(PublishDomainAnalysisResult(
        request=request,
        result=_completed_result(range(2)),
    ))
    selection = DomainComponentKey("physical-frame-0", "local-domain-1")
    controller.dispatch(SelectDomainComponent(selection))
    publication = controller.snapshot.published

    highlighted = controller.dispatch(SetDomainHierarchyHighlight(
        DomainHierarchyHighlight(
            physical_frame_id="physical-frame-0",
            target_kind="domain",
            lattice_domain_id="local-domain-1",
        )
    ))

    assert highlighted.hierarchy_highlight == DomainHierarchyHighlight(
        physical_frame_id="physical-frame-0",
        target_kind="domain",
        lattice_domain_id="local-domain-1",
    )
    assert highlighted.selected_component == selection
    assert highlighted.published is publication

    changed_frame = controller.dispatch(SetDomainAnalysisFrame(1))

    assert changed_frame.hierarchy_highlight is None
    assert changed_frame.selected_component is None
    assert changed_frame.published is publication


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
