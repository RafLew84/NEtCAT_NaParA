from dataclasses import replace

import pytest

from moltrack.analysis.domain_analysis import (
    ApplyPreparedCorrectionRebase,
    ApplyPreparedDomainCorrection,
    CorrectionRebaseResolution,
    DomainAnalysisRequest,
    DomainAnalysisWorkspaceController,
    DomainAnalysisWorkspaceIntentError,
    M6Gate,
    PrepareCorrectionRebase,
    PreviewCreateManualDomain,
    PreviewManualOrientation,
    PublishDomainAnalysisResult,
    SelectDomainMolecules,
    UndoDomainCorrection,
)
from test_domain_correction_orientation import _automatic_result


def test_changed_rerun_stays_pending_without_replacing_effective_projection() -> None:
    request = DomainAnalysisRequest(frame_range=range(1))
    automatic = _automatic_result()
    controller = DomainAnalysisWorkspaceController(
        request,
        physical_frame_ids=("frame-0",),
    )
    controller.dispatch(PublishDomainAnalysisResult(request, automatic))
    controller.dispatch(SelectDomainMolecules(("outside",)))
    controller.dispatch(PreviewManualOrientation("D"))
    preview = controller.snapshot.domain_corrections.prepared
    assert preview is not None
    controller.dispatch(ApplyPreparedDomainCorrection(preview))
    active_publication = controller.snapshot.published
    active_corrections = controller.snapshot.domain_corrections.correction_set

    unchanged = controller.dispatch(PublishDomainAnalysisResult(
        request,
        automatic,
    ))

    assert unchanged.published is active_publication
    assert unchanged.domain_corrections.correction_set is active_corrections
    assert unchanged.domain_corrections.pending_automatic_candidate is None

    frame = automatic.m6_gate.frames[0]  # type: ignore[union-attr]
    candidate = replace(
        automatic,
        m6_gate=M6Gate((replace(
            frame,
            source_geometry_fingerprint="geometry-rerun",
        ),)),
    )
    pending = controller.dispatch(PublishDomainAnalysisResult(
        request,
        candidate,
    ))

    assert pending.published is active_publication
    assert pending.published_revision == 1
    assert pending.domain_corrections.correction_set is active_corrections
    assert pending.domain_corrections.effective_projection is not None
    assert pending.domain_corrections.effective_projection.molecule(
        "frame-0",
        "outside",
    ).effective_orientation == "D"
    assert pending.domain_corrections.pending_automatic_candidate is not None
    assert pending.domain_corrections.pending_automatic_candidate.result is candidate


def test_compatible_sources_promote_atomically_to_a_successor_revision() -> None:
    request = DomainAnalysisRequest(frame_range=range(1))
    automatic = _automatic_result()
    controller = DomainAnalysisWorkspaceController(
        request,
        physical_frame_ids=("frame-0",),
    )
    controller.dispatch(PublishDomainAnalysisResult(request, automatic))
    controller.dispatch(SelectDomainMolecules(("outside",)))
    controller.dispatch(PreviewManualOrientation("D"))
    correction_preview = controller.snapshot.domain_corrections.prepared
    assert correction_preview is not None
    controller.dispatch(ApplyPreparedDomainCorrection(correction_preview))
    previous_correction_set = controller.snapshot.domain_corrections.correction_set
    assert previous_correction_set is not None
    frame = automatic.m6_gate.frames[0]  # type: ignore[union-attr]
    candidate = replace(
        automatic,
        m6_gate=M6Gate((replace(
            frame,
            source_geometry_fingerprint="geometry-rerun",
        ),)),
    )
    controller.dispatch(PublishDomainAnalysisResult(request, candidate))

    compared = controller.dispatch(PrepareCorrectionRebase())
    rebase_preview = compared.domain_corrections.prepared_rebase

    assert rebase_preview is not None
    assert rebase_preview.is_ready
    assert rebase_preview.issues == ()
    assert rebase_preview.portable_source_keys == (("frame-0", "outside"),)

    promoted = controller.dispatch(ApplyPreparedCorrectionRebase(rebase_preview))

    assert promoted.published is not None
    assert promoted.published.result is candidate
    assert promoted.published_revision == 2
    assert promoted.domain_corrections.pending_automatic_candidate is None
    assert promoted.domain_corrections.prepared_rebase is None
    assert promoted.domain_corrections.effective_projection is not None
    assert promoted.domain_corrections.effective_projection.molecule(
        "frame-0",
        "outside",
    ).effective_orientation == "D"
    successor = promoted.domain_corrections.correction_set
    assert successor is not None
    assert successor.automatic_fingerprint != previous_correction_set.automatic_fingerprint
    assert successor.history_for("frame-0").undo is None
    assert len(promoted.domain_corrections.rebase_records) == 1
    assert (
        promoted.domain_corrections.rebase_records[0].previous_correction_set
        is previous_correction_set
    )


def test_changed_geometry_requires_an_explicit_reasoned_resolution() -> None:
    request = DomainAnalysisRequest(frame_range=range(1))
    automatic = _automatic_result()
    controller = DomainAnalysisWorkspaceController(
        request,
        physical_frame_ids=("frame-0",),
    )
    controller.dispatch(PublishDomainAnalysisResult(request, automatic))
    controller.dispatch(SelectDomainMolecules(("outside",)))
    controller.dispatch(PreviewManualOrientation("D"))
    correction_preview = controller.snapshot.domain_corrections.prepared
    assert correction_preview is not None
    controller.dispatch(ApplyPreparedDomainCorrection(correction_preview))
    frame = automatic.m6_gate.frames[0]  # type: ignore[union-attr]
    moved = replace(
        frame.outside_members[0],
        point_xy_nm=(3.0, 0.0),
        raw_centroid_xy=(3.0, 0.0),
        footprint_pixels_xy=((3, 0),),
    )
    candidate = replace(
        automatic,
        m6_gate=M6Gate((replace(
            frame,
            source_geometry_fingerprint="geometry-moved",
            outside_members=(moved,),
            outside_pixels_xy=((3, 0),),
            analyzed_pixels_xy=((0, 0), (1, 0), (3, 0)),
        ),)),
    )
    controller.dispatch(PublishDomainAnalysisResult(request, candidate))
    compared = controller.dispatch(PrepareCorrectionRebase())
    preview = compared.domain_corrections.prepared_rebase
    assert preview is not None
    assert not preview.is_ready
    assert tuple(value.kind for value in preview.issues) == ("changed_geometry",)

    before_apply = controller.snapshot
    with pytest.raises(
        DomainAnalysisWorkspaceIntentError,
        match="must be resolved",
    ):
        controller.dispatch(ApplyPreparedCorrectionRebase(preview))
    assert controller.snapshot is before_apply
    assert controller.snapshot.published is not None
    assert controller.snapshot.published.result is automatic

    with pytest.raises(ValueError, match="reason_code"):
        CorrectionRebaseResolution(
            preview.issues[0].issue_id,
            "reapplied",
            "",
        )
    resolution = CorrectionRebaseResolution(
        preview.issues[0].issue_id,
        "reapplied",
        "geometry_verified",
    )
    resolved = controller.dispatch(PrepareCorrectionRebase((resolution,)))
    resolved_preview = resolved.domain_corrections.prepared_rebase
    assert resolved_preview is not None
    assert resolved_preview.is_ready

    promoted = controller.dispatch(ApplyPreparedCorrectionRebase(resolved_preview))
    assert promoted.published is not None
    assert promoted.published.result is candidate
    assert promoted.domain_corrections.effective_projection is not None
    assert promoted.domain_corrections.effective_projection.molecule(
        "frame-0",
        "outside",
    ).effective_orientation == "D"


def test_same_coordinates_never_remap_a_changed_source_identity_implicitly() -> None:
    request = DomainAnalysisRequest(frame_range=range(1))
    automatic = _automatic_result()
    controller = DomainAnalysisWorkspaceController(
        request,
        physical_frame_ids=("frame-0",),
    )
    controller.dispatch(PublishDomainAnalysisResult(request, automatic))
    controller.dispatch(SelectDomainMolecules(("outside",)))
    controller.dispatch(PreviewManualOrientation("D"))
    correction_preview = controller.snapshot.domain_corrections.prepared
    assert correction_preview is not None
    controller.dispatch(ApplyPreparedDomainCorrection(correction_preview))
    frame = automatic.m6_gate.frames[0]  # type: ignore[union-attr]
    renamed = replace(frame.outside_members[0], source_id="replacement")
    candidate = replace(
        automatic,
        m6_gate=M6Gate((replace(
            frame,
            source_geometry_fingerprint="geometry-renamed",
            outside_members=(renamed,),
            analyzed_source_ids=("full", "island", "replacement"),
        ),)),
    )
    controller.dispatch(PublishDomainAnalysisResult(request, candidate))

    compared = controller.dispatch(PrepareCorrectionRebase())
    preview = compared.domain_corrections.prepared_rebase
    assert preview is not None
    assert not preview.is_ready
    assert preview.portable_source_keys == ()
    assert tuple(value.kind for value in preview.issues) == ("missing_target",)

    resolution = CorrectionRebaseResolution(
        preview.issues[0].issue_id,
        "remapped",
        "stable_identity_changed_after_source_reimport",
        ("replacement",),
    )
    resolved = controller.dispatch(PrepareCorrectionRebase((resolution,)))
    resolved_preview = resolved.domain_corrections.prepared_rebase
    assert resolved_preview is not None and resolved_preview.is_ready
    promoted = controller.dispatch(ApplyPreparedCorrectionRebase(resolved_preview))

    assert promoted.domain_corrections.effective_projection is not None
    assert promoted.domain_corrections.effective_projection.molecule(
        "frame-0",
        "replacement",
    ).effective_orientation == "D"


def test_split_is_reported_and_requires_an_explicit_multi_target_remap() -> None:
    request = DomainAnalysisRequest(frame_range=range(1))
    base = _automatic_result()
    frame = base.m6_gate.frames[0]  # type: ignore[union-attr]
    old_source = replace(
        frame.outside_members[0],
        point_xy_nm=(2.5, 0.0),
        footprint_pixels_xy=((2, 0), (3, 0)),
    )
    automatic = replace(
        base,
        m6_gate=M6Gate((replace(
            frame,
            source_geometry_fingerprint="geometry-before-split",
            outside_members=(old_source,),
            outside_pixels_xy=((2, 0), (3, 0)),
            outside_area_nm2=2.0,
            analyzed_pixels_xy=((0, 0), (1, 0), (2, 0), (3, 0)),
            analyzed_area_nm2=4.0,
        ),)),
    )
    controller = DomainAnalysisWorkspaceController(
        request,
        physical_frame_ids=("frame-0",),
    )
    controller.dispatch(PublishDomainAnalysisResult(request, automatic))
    controller.dispatch(SelectDomainMolecules(("outside",)))
    controller.dispatch(PreviewManualOrientation("D"))
    correction_preview = controller.snapshot.domain_corrections.prepared
    assert correction_preview is not None
    controller.dispatch(ApplyPreparedDomainCorrection(correction_preview))
    left = replace(
        old_source,
        source_id="outside-left",
        point_xy_nm=(2.0, 0.0),
        raw_centroid_xy=(2.0, 0.0),
        footprint_pixels_xy=((2, 0),),
    )
    right = replace(
        old_source,
        source_id="outside-right",
        point_xy_nm=(3.0, 0.0),
        raw_centroid_xy=(3.0, 0.0),
        footprint_pixels_xy=((3, 0),),
    )
    candidate = replace(
        automatic,
        m6_gate=M6Gate((replace(
            automatic.m6_gate.frames[0],  # type: ignore[union-attr]
            source_geometry_fingerprint="geometry-after-split",
            outside_members=(left, right),
            analyzed_source_ids=(
                "full",
                "island",
                "outside-left",
                "outside-right",
            ),
        ),)),
    )
    controller.dispatch(PublishDomainAnalysisResult(request, candidate))

    preview = controller.dispatch(
        PrepareCorrectionRebase()
    ).domain_corrections.prepared_rebase

    assert preview is not None
    assert not preview.is_ready
    assert len(preview.issues) == 1
    assert preview.issues[0].kind == "split"
    assert preview.issues[0].candidate_source_ids == (
        "outside-left",
        "outside-right",
    )
    resolution = CorrectionRebaseResolution(
        preview.issues[0].issue_id,
        "remapped",
        "segmentation_split_verified",
        ("outside-left", "outside-right"),
    )
    resolved = controller.dispatch(
        PrepareCorrectionRebase((resolution,))
    ).domain_corrections.prepared_rebase
    assert resolved is not None and resolved.is_ready

    promoted = controller.dispatch(ApplyPreparedCorrectionRebase(resolved))
    projection = promoted.domain_corrections.effective_projection
    assert projection is not None
    assert projection.molecule(
        "frame-0",
        "outside-left",
    ).effective_orientation == "D"
    assert projection.molecule(
        "frame-0",
        "outside-right",
    ).effective_orientation == "D"


def test_merge_requires_explicit_resolutions_and_deduplicates_equal_decisions() -> None:
    request = DomainAnalysisRequest(frame_range=range(1))
    base = _automatic_result()
    frame = base.m6_gate.frames[0]  # type: ignore[union-attr]
    source = frame.outside_members[0]
    left = replace(
        source,
        source_id="outside-left",
        point_xy_nm=(2.0, 0.0),
        raw_centroid_xy=(2.0, 0.0),
        footprint_pixels_xy=((2, 0),),
    )
    right = replace(
        source,
        source_id="outside-right",
        point_xy_nm=(3.0, 0.0),
        raw_centroid_xy=(3.0, 0.0),
        footprint_pixels_xy=((3, 0),),
    )
    automatic = replace(
        base,
        m6_gate=M6Gate((replace(
            frame,
            source_geometry_fingerprint="geometry-before-merge",
            outside_members=(left, right),
            outside_pixels_xy=((2, 0), (3, 0)),
            outside_area_nm2=2.0,
            analyzed_source_ids=(
                "full",
                "island",
                "outside-left",
                "outside-right",
            ),
            analyzed_pixels_xy=((0, 0), (1, 0), (2, 0), (3, 0)),
            analyzed_area_nm2=4.0,
        ),)),
    )
    controller = DomainAnalysisWorkspaceController(
        request,
        physical_frame_ids=("frame-0",),
    )
    controller.dispatch(PublishDomainAnalysisResult(request, automatic))
    controller.dispatch(SelectDomainMolecules(("outside-left", "outside-right")))
    controller.dispatch(PreviewManualOrientation("D"))
    correction_preview = controller.snapshot.domain_corrections.prepared
    assert correction_preview is not None
    controller.dispatch(ApplyPreparedDomainCorrection(correction_preview))
    merged = replace(
        source,
        source_id="outside-merged",
        point_xy_nm=(2.5, 0.0),
        raw_centroid_xy=(2.5, 0.0),
        footprint_pixels_xy=((2, 0), (3, 0)),
    )
    candidate = replace(
        automatic,
        m6_gate=M6Gate((replace(
            automatic.m6_gate.frames[0],  # type: ignore[union-attr]
            source_geometry_fingerprint="geometry-after-merge",
            outside_members=(merged,),
            analyzed_source_ids=("full", "island", "outside-merged"),
        ),)),
    )
    controller.dispatch(PublishDomainAnalysisResult(request, candidate))

    preview = controller.dispatch(
        PrepareCorrectionRebase()
    ).domain_corrections.prepared_rebase

    assert preview is not None
    assert tuple(value.kind for value in preview.issues) == ("merge", "merge")
    assert all(
        value.candidate_source_ids == ("outside-merged",)
        for value in preview.issues
    )
    resolutions = tuple(
        CorrectionRebaseResolution(
            issue.issue_id,
            "remapped",
            "segmentation_merge_verified",
            ("outside-merged",),
        )
        for issue in preview.issues
    )
    resolved = controller.dispatch(
        PrepareCorrectionRebase(resolutions)
    ).domain_corrections.prepared_rebase
    assert resolved is not None and resolved.is_ready

    promoted = controller.dispatch(ApplyPreparedCorrectionRebase(resolved))
    successor = promoted.domain_corrections.correction_set
    assert successor is not None
    assert tuple(
        (value.source_id, value.orientation_label)
        for value in successor.orientation_decisions
    ) == (("outside-merged", "D"),)


def test_new_pending_candidate_invalidates_a_prepared_rebase() -> None:
    request = DomainAnalysisRequest(frame_range=range(1))
    automatic = _automatic_result()
    controller = DomainAnalysisWorkspaceController(
        request,
        physical_frame_ids=("frame-0",),
    )
    controller.dispatch(PublishDomainAnalysisResult(request, automatic))
    frame = automatic.m6_gate.frames[0]  # type: ignore[union-attr]
    first_candidate = replace(
        automatic,
        m6_gate=M6Gate((replace(
            frame,
            source_geometry_fingerprint="candidate-1",
        ),)),
    )
    controller.dispatch(PublishDomainAnalysisResult(request, first_candidate))
    first_preview = controller.dispatch(
        PrepareCorrectionRebase()
    ).domain_corrections.prepared_rebase
    assert first_preview is not None and first_preview.is_ready
    second_candidate = replace(
        automatic,
        m6_gate=M6Gate((replace(
            frame,
            source_geometry_fingerprint="candidate-2",
        ),)),
    )

    replaced_candidate = controller.dispatch(PublishDomainAnalysisResult(
        request,
        second_candidate,
    ))

    assert replaced_candidate.domain_corrections.prepared_rebase is None
    assert (
        replaced_candidate.domain_corrections.pending_automatic_candidate.result
        is second_candidate
    )
    before_stale_apply = controller.snapshot
    with pytest.raises(
        DomainAnalysisWorkspaceIntentError,
        match="current prepared",
    ):
        controller.dispatch(ApplyPreparedCorrectionRebase(first_preview))
    assert controller.snapshot is before_stale_apply


def test_rebase_preserves_manual_domain_identity_as_successor_baseline() -> None:
    request = DomainAnalysisRequest(frame_range=range(1))
    automatic = _automatic_result()
    controller = DomainAnalysisWorkspaceController(
        request,
        physical_frame_ids=("frame-0",),
    )
    controller.dispatch(PublishDomainAnalysisResult(request, automatic))
    controller.dispatch(SelectDomainMolecules(("outside",)))
    controller.dispatch(PreviewCreateManualDomain())
    create_preview = controller.snapshot.domain_corrections.prepared
    assert create_preview is not None
    created = controller.dispatch(
        ApplyPreparedDomainCorrection.confirmed(create_preview)
    )
    created_set = created.domain_corrections.correction_set
    assert created_set is not None
    manual_domain_id = created_set.manual_domains[0].manual_domain_id
    frame = automatic.m6_gate.frames[0]  # type: ignore[union-attr]
    candidate = replace(
        automatic,
        m6_gate=M6Gate((replace(
            frame,
            source_geometry_fingerprint="geometry-domain-rebase",
        ),)),
    )
    controller.dispatch(PublishDomainAnalysisResult(request, candidate))
    rebase_preview = controller.dispatch(
        PrepareCorrectionRebase()
    ).domain_corrections.prepared_rebase
    assert rebase_preview is not None and rebase_preview.is_ready

    promoted = controller.dispatch(ApplyPreparedCorrectionRebase(rebase_preview))
    successor = promoted.domain_corrections.correction_set
    assert successor is not None
    assert tuple(
        (value.manual_domain_id, value.source_ids)
        for value in successor.manual_domains
    ) == ((manual_domain_id, ("outside",)),)
    assert successor.history_for("frame-0").undo is None

    controller.dispatch(SelectDomainMolecules(("outside",)))
    controller.dispatch(PreviewManualOrientation("D"))
    orientation_preview = controller.snapshot.domain_corrections.prepared
    assert orientation_preview is not None
    controller.dispatch(ApplyPreparedDomainCorrection(orientation_preview))
    undone = controller.dispatch(UndoDomainCorrection())

    undone_set = undone.domain_corrections.correction_set
    assert undone_set is not None
    assert undone_set.manual_domains[0].manual_domain_id == manual_domain_id
    assert undone_set.manual_domains[0].source_ids == ("outside",)
    assert undone_set.orientation_decisions == ()


def test_dropping_every_member_preserves_manual_domain_uuid_as_tombstone() -> None:
    request = DomainAnalysisRequest(frame_range=range(1))
    automatic = _automatic_result()
    controller = DomainAnalysisWorkspaceController(
        request,
        physical_frame_ids=("frame-0",),
    )
    controller.dispatch(PublishDomainAnalysisResult(request, automatic))
    controller.dispatch(SelectDomainMolecules(("outside",)))
    controller.dispatch(PreviewCreateManualDomain())
    create_preview = controller.snapshot.domain_corrections.prepared
    assert create_preview is not None
    created = controller.dispatch(
        ApplyPreparedDomainCorrection.confirmed(create_preview)
    )
    created_set = created.domain_corrections.correction_set
    assert created_set is not None
    manual_domain_id = created_set.manual_domains[0].manual_domain_id
    frame = automatic.m6_gate.frames[0]  # type: ignore[union-attr]
    replacement = replace(frame.outside_members[0], source_id="replacement")
    candidate = replace(
        automatic,
        m6_gate=M6Gate((replace(
            frame,
            source_geometry_fingerprint="geometry-domain-dropped",
            outside_members=(replacement,),
            analyzed_source_ids=("full", "island", "replacement"),
        ),)),
    )
    controller.dispatch(PublishDomainAnalysisResult(request, candidate))
    preview = controller.dispatch(
        PrepareCorrectionRebase()
    ).domain_corrections.prepared_rebase
    assert preview is not None and len(preview.issues) == 1
    dropped = CorrectionRebaseResolution(
        preview.issues[0].issue_id,
        "dropped",
        "manual_domain_has_no_successor_member",
    )
    resolved = controller.dispatch(
        PrepareCorrectionRebase((dropped,))
    ).domain_corrections.prepared_rebase
    assert resolved is not None and resolved.is_ready

    promoted = controller.dispatch(ApplyPreparedCorrectionRebase(resolved))

    successor = promoted.domain_corrections.correction_set
    assert successor is not None
    assert len(successor.manual_domains) == 1
    tombstone = successor.manual_domains[0]
    assert tombstone.manual_domain_id == manual_domain_id
    assert tombstone.is_deleted
    assert tombstone.source_ids == ()
    assert tombstone.restore_source_ids == ("outside",)
