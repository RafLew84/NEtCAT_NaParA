from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

import pytest

from moltrack.analysis.domain_analysis import (
    ApplyPreparedDomainCorrection,
    DomainAnalysisResult,
    DomainBackendIdentity,
    DomainCorrectionModule,
    DomainCorrectionHistoryRecord,
    DomainCorrectionWorkspaceState,
    DetectionIdentity,
    DomainCorrectionWorkspace,
    M3M6LatticeNetworkEvidence,
    M6Gate,
    ManualDomainIntent,
    ManualOrientationIntent,
    ReferenceReviewPolicy,
)
from test_domain_correction_orientation import (
    MANUAL_DOMAIN_1,
    MANUAL_DOMAIN_2,
    _automatic_result,
    _frame_gate,
)


_NOW = datetime(2026, 8, 14, 9, 30, tzinfo=timezone.utc)


def test_apply_and_replay_of_one_log_have_the_same_public_contract() -> None:
    automatic, module, _, workspace = _boundary_workspace()
    preview = module.prepare(
        workspace,
        automatic,
        ManualOrientationIntent.assign(
            physical_frame_id="frame-0",
            source_ids=("island",),
            orientation_label="D",
        ),
    )
    applied = module.dispatch(
        workspace,
        automatic,
        ApplyPreparedDomainCorrection.confirmed(preview),
    )
    audit_log = replace(
        applied,
        orientation_decisions=applied.baseline_orientation_decisions,
        manual_domains=applied.baseline_manual_domains,
        cleared_boundary_source_keys=applied.legacy_boundary_source_keys or (),
    )

    replayed = module.replay(audit_log, automatic)

    assert replayed == applied
    assert replayed.revision == applied.revision == 4
    applied_projection = module.project(automatic, applied)
    replayed_projection = module.project(automatic, replayed)
    assert replayed_projection == applied_projection
    assert replayed_projection.molecule(
        "frame-0", "island"
    ).effective_orientation == "D"
    assert replayed_projection.molecule("frame-0", "outside").is_boundary is False
    conflicting_restore = ManualDomainIntent.restore(
        physical_frame_id="frame-0",
        manual_domain_id=MANUAL_DOMAIN_2,
    )
    applied_conflicts = module.prepare(
        applied, automatic, conflicting_restore
    ).conflicts
    replayed_conflicts = module.prepare(
        replayed, automatic, conflicting_restore
    ).conflicts
    assert tuple(value.code for value in applied_conflicts) == (
        "manual_domain_not_deleted",
        "no_op",
    )
    assert replayed_conflicts == applied_conflicts
    policy = ReferenceReviewPolicy()
    readiness = []
    for correction_set in (applied, replayed):
        corrections = DomainCorrectionWorkspaceState(
            correction_set=correction_set,
            effective_projection=module.project(automatic, correction_set),
        )
        reviews = policy.initialize(automatic, corrections)
        readiness.append(policy.readiness(reviews, "m6"))
    assert readiness[0] == readiness[1]
    assert readiness[0].ready is False
    assert tuple(value.code for value in readiness[0].blockers) == (
        "review_decisions_incomplete",
    )


def test_undo_and_redo_append_records_and_replay_the_whole_batch() -> None:
    automatic = _automatic_result()
    history_ids = iter(("history-apply", "history-undo", "history-redo"))
    module = DomainCorrectionModule(
        correction_operation_id_factory=lambda: "operation-1",
        correction_history_id_factory=history_ids.__next__,
        clock=lambda: _NOW,
    )
    workspace = module.initialize(automatic)
    preview = module.prepare(
        workspace,
        automatic,
        ManualOrientationIntent.assign(
            physical_frame_id="frame-0",
            source_ids=("full", "outside"),
            orientation_label="D",
        ),
    )
    workspace = module.dispatch(
        workspace,
        automatic,
        ApplyPreparedDomainCorrection.confirmed(preview),
    )

    availability = module.history_availability(workspace, "frame-0")
    assert availability.undo is not None
    assert availability.undo.operation_id == "operation-1"
    assert availability.undo.operation_label == "Assign orientation"
    assert availability.undo.source_count == 2
    assert availability.redo is None

    workspace = module.undo(workspace, automatic, "frame-0")
    assert workspace.orientation_decisions == ()
    assert len(workspace.atoms) == 1
    assert [record.action for record in workspace.history_records] == [
        "apply", "undo",
    ]
    assert workspace.history_records[-1].operation_id == "operation-1"
    assert workspace.history_records[-1].recorded_at == _NOW
    assert workspace.review_revision("m6") == 0
    assert workspace.review_revision("orientation") == 2
    availability = module.history_availability(workspace, "frame-0")
    assert availability.undo is None
    assert availability.redo is not None

    workspace = module.redo(workspace, automatic, "frame-0")
    assert tuple(
        decision.source_id for decision in workspace.orientation_decisions
    ) == ("full", "outside")
    assert [record.action for record in workspace.history_records] == [
        "apply", "undo", "redo",
    ]
    assert workspace.review_revision("m6") == 0
    assert workspace.review_revision("orientation") == 3


def test_manual_domain_undo_redo_restores_uuid_members_and_review_targets() -> None:
    automatic = _automatic_result()
    module = DomainCorrectionModule(
        manual_domain_id_factory=lambda: MANUAL_DOMAIN_1,
        correction_operation_id_factory=lambda: "operation-domain",
        correction_history_id_factory=iter(("apply", "undo", "redo")).__next__,
        clock=lambda: _NOW,
    )
    workspace = module.initialize(automatic)
    preview = module.prepare(
        workspace,
        automatic,
        ManualDomainIntent.create(
            physical_frame_id="frame-0",
            source_ids=("full", "outside"),
        ),
    )
    workspace = module.dispatch(
        workspace,
        automatic,
        ApplyPreparedDomainCorrection.confirmed(preview),
    )
    assert workspace.manual_domains[0].manual_domain_id == MANUAL_DOMAIN_1

    workspace = module.undo(workspace, automatic, "frame-0")
    assert workspace.manual_domains == ()
    assert workspace.review_revision("m6") == 2
    assert workspace.review_revision("orientation") == 2

    workspace = module.redo(workspace, automatic, "frame-0")
    restored = workspace.manual_domains[0]
    assert restored.manual_domain_id == MANUAL_DOMAIN_1
    assert restored.source_ids == ("full", "outside")
    assert workspace.review_revision("m6") == 3
    assert workspace.review_revision("orientation") == 3


def test_new_apply_after_undo_closes_redo_without_deleting_audit() -> None:
    automatic = _automatic_result()
    operation_ids = iter(("operation-a", "operation-b", "operation-c"))
    history_ids = iter(("apply-a", "apply-b", "undo-b", "apply-c"))
    module = DomainCorrectionModule(
        correction_operation_id_factory=operation_ids.__next__,
        correction_history_id_factory=history_ids.__next__,
        clock=lambda: _NOW,
    )
    workspace = module.initialize(automatic)
    for source_id, label in (("full", "D"), ("outside", "E")):
        preview = module.prepare(
            workspace,
            automatic,
            ManualOrientationIntent.assign(
                physical_frame_id="frame-0",
                source_ids=(source_id,),
                orientation_label=label,
            ),
        )
        workspace = module.dispatch(
            workspace,
            automatic,
            ApplyPreparedDomainCorrection(preview),
        )
    workspace = module.undo(workspace, automatic, "frame-0")
    assert module.history_availability(workspace, "frame-0").redo is not None

    preview = module.prepare(
        workspace,
        automatic,
        ManualOrientationIntent.assign(
            physical_frame_id="frame-0",
            source_ids=("island",),
            orientation_label="F",
        ),
    )
    workspace = module.dispatch(
        workspace,
        automatic,
        ApplyPreparedDomainCorrection(preview),
    )

    availability = module.history_availability(workspace, "frame-0")
    assert availability.redo is None
    assert tuple(atom.operation_id for atom in workspace.atoms) == (
        "operation-a", "operation-b", "operation-c",
    )
    assert [record.action for record in workspace.history_records] == [
        "apply", "apply", "undo", "apply",
    ]
    decisions = {
        decision.source_id: decision.orientation_label
        for decision in workspace.orientation_decisions
    }
    assert decisions == {"full": "D", "island": "F"}


def test_undo_replays_the_preceding_active_atom_in_the_frame() -> None:
    automatic = _automatic_result()
    module = DomainCorrectionModule(
        correction_operation_id_factory=iter(("frame-0-a", "frame-0-b")).__next__,
        correction_history_id_factory=iter(("apply-a", "apply-b", "undo-b")).__next__,
        clock=lambda: _NOW,
    )
    workspace = module.initialize(automatic)
    for source_id, label in (("full", "D"), ("outside", "E")):
        preview = module.prepare(
            workspace,
            automatic,
            ManualOrientationIntent.assign(
                physical_frame_id="frame-0",
                source_ids=(source_id,),
                orientation_label=label,
            ),
        )
        workspace = module.dispatch(
            workspace,
            automatic,
            ApplyPreparedDomainCorrection(preview),
        )

    workspace = module.undo(workspace, automatic, "frame-0")

    assert tuple(
        (decision.source_id, decision.orientation_label)
        for decision in workspace.orientation_decisions
    ) == (("full", "D"),)
    assert module.history_availability(workspace, "missing-frame").undo is None


def test_history_rejects_out_of_order_or_unknown_operation_references() -> None:
    automatic = _automatic_result()
    module = DomainCorrectionModule(
        correction_operation_id_factory=lambda: "operation-1",
        correction_history_id_factory=lambda: "apply-1",
        clock=lambda: _NOW,
    )
    workspace = module.initialize(automatic)
    preview = module.prepare(
        workspace,
        automatic,
        ManualOrientationIntent.assign(
            physical_frame_id="frame-0",
            source_ids=("outside",),
            orientation_label="D",
        ),
    )
    workspace = module.dispatch(
        workspace,
        automatic,
        ApplyPreparedDomainCorrection(preview),
    )

    unknown = DomainCorrectionHistoryRecord(
        "bad-unknown", "undo", "missing", "frame-0", _NOW,
    )
    with pytest.raises(ValueError, match="reference an atom"):
        replace(workspace, history_records=workspace.history_records + (unknown,))

    redo_without_undo = DomainCorrectionHistoryRecord(
        "bad-redo", "redo", "operation-1", "frame-0", _NOW,
    )
    with pytest.raises(ValueError, match="last undone"):
        replace(
            workspace,
            history_records=workspace.history_records + (redo_without_undo,),
        )


def test_first_undo_accepts_legacy_atoms_without_history_records() -> None:
    automatic = _automatic_result()
    module = DomainCorrectionModule(
        correction_operation_id_factory=lambda: "legacy-operation",
        correction_history_id_factory=iter(("apply", "undo")).__next__,
        clock=lambda: _NOW,
    )
    workspace = module.initialize(automatic)
    preview = module.prepare(
        workspace,
        automatic,
        ManualOrientationIntent.assign(
            physical_frame_id="frame-0",
            source_ids=("outside",),
            orientation_label="D",
        ),
    )
    workspace = module.dispatch(
        workspace,
        automatic,
        ApplyPreparedDomainCorrection(preview),
    )
    legacy = replace(workspace, history_records=())

    undone = module.undo(legacy, automatic, "frame-0")

    assert undone.orientation_decisions == ()
    assert [record.action for record in undone.history_records] == ["undo"]


def test_first_apply_accepts_legacy_atoms_without_history_records() -> None:
    automatic = _automatic_result()
    module = DomainCorrectionModule(
        correction_operation_id_factory=iter(("legacy", "new")).__next__,
        correction_history_id_factory=iter(("legacy-apply", "new-apply")).__next__,
        clock=lambda: _NOW,
    )
    workspace = module.initialize(automatic)
    first_preview = module.prepare(
        workspace,
        automatic,
        ManualOrientationIntent.assign(
            physical_frame_id="frame-0",
            source_ids=("full",),
            orientation_label="D",
        ),
    )
    workspace = module.dispatch(
        workspace,
        automatic,
        ApplyPreparedDomainCorrection(first_preview),
    )
    legacy = replace(workspace, history_records=())
    second_preview = module.prepare(
        legacy,
        automatic,
        ManualOrientationIntent.assign(
            physical_frame_id="frame-0",
            source_ids=("outside",),
            orientation_label="E",
        ),
    )

    updated = module.dispatch(
        legacy,
        automatic,
        ApplyPreparedDomainCorrection(second_preview),
    )

    assert [record.action for record in updated.history_records] == ["apply"]
    assert tuple(
        (decision.source_id, decision.orientation_label)
        for decision in updated.orientation_decisions
    ) == (("full", "D"), ("outside", "E"))


def test_history_rejects_apply_records_not_matching_the_atom_suffix() -> None:
    automatic = _automatic_result()
    module = DomainCorrectionModule(
        correction_operation_id_factory=iter(("operation-a", "operation-b")).__next__,
        correction_history_id_factory=iter(("apply-a", "apply-b")).__next__,
        clock=lambda: _NOW,
    )
    workspace = module.initialize(automatic)
    for source_id, label in (("full", "D"), ("outside", "E")):
        preview = module.prepare(
            workspace,
            automatic,
            ManualOrientationIntent.assign(
                physical_frame_id="frame-0",
                source_ids=(source_id,),
                orientation_label=label,
            ),
        )
        workspace = module.dispatch(
            workspace,
            automatic,
            ApplyPreparedDomainCorrection(preview),
        )

    with pytest.raises(ValueError, match="legacy prefix"):
        replace(workspace, history_records=workspace.history_records[:1])
    with pytest.raises(ValueError, match="legacy prefix"):
        replace(workspace, history_records=tuple(reversed(
            workspace.history_records
        )))


def test_replay_preserves_an_effectless_legacy_boundary_baseline() -> None:
    automatic, module, _, workspace = _boundary_workspace()
    legacy = DomainCorrectionWorkspace(
        automatic_fingerprint=workspace.automatic_fingerprint,
        revision=workspace.revision,
        orientation_decisions=workspace.orientation_decisions,
        manual_domains=workspace.manual_domains,
        cleared_boundary_source_keys=workspace.cleared_boundary_source_keys,
        atoms=tuple(replace(atom, effects=()) for atom in workspace.atoms),
        review_revisions=workspace.review_revisions,
    )
    assert legacy.cleared_boundary_source_keys == (DetectionIdentity(
        physical_frame_id="frame-0",
        source_id="outside",
    ),)
    assert module.history_availability(legacy, "frame-0").undo is None

    preview = module.prepare(
        legacy,
        automatic,
        ManualOrientationIntent.assign(
            physical_frame_id="frame-0",
            source_ids=("island",),
            orientation_label="D",
        ),
    )
    updated = module.dispatch(
        legacy,
        automatic,
        ApplyPreparedDomainCorrection(preview),
    )
    updated = module.undo(updated, automatic, "frame-0")

    assert updated.cleared_boundary_source_keys == (DetectionIdentity(
        physical_frame_id="frame-0",
        source_id="outside",
    ),)
    assert not module.project(automatic, updated).molecule(
        "frame-0", "outside"
    ).is_boundary


def test_undo_legacy_boundary_atom_with_effects_restores_boundary() -> None:
    automatic, module, _, workspace = _boundary_workspace()
    legacy = replace(workspace, history_records=())

    updated = module.undo(legacy, automatic, "frame-0")

    assert updated.cleared_boundary_source_keys == ()
    assert module.project(automatic, updated).molecule(
        "frame-0", "outside"
    ).is_boundary


def test_first_new_boundary_clear_does_not_pollute_empty_legacy_baseline() -> None:
    automatic, module, before_move, workspace = _boundary_workspace()
    legacy = replace(
        before_move,
        history_records=(),
        legacy_boundary_source_keys=None,
    )
    preview = module.prepare(
        legacy,
        automatic,
        workspace.atoms[-1].intent,
    )
    updated = module.dispatch(
        legacy,
        automatic,
        ApplyPreparedDomainCorrection.confirmed(preview),
    )

    assert updated.legacy_boundary_source_keys == ()
    updated = module.undo(updated, automatic, "frame-0")
    assert updated.cleared_boundary_source_keys == ()


def _boundary_workspace() -> tuple[
    DomainAnalysisResult,
    DomainCorrectionModule,
    DomainCorrectionWorkspace,
    DomainCorrectionWorkspace,
]:
    classic = _frame_gate()
    frame = replace(
        classic,
        backend_identity=DomainBackendIdentity(
            backend_id="m3_m6_lattice_network",
            result_schema_version="domain-backend-result-v1",
            algorithm_version="network-v1",
            settings_fingerprint="network-settings-v1",
            adapter_owner="correction-test",
            native_evidence_kind="m3_m6_lattice_evidence_v1",
            capabilities=("common_partition", "explicit_boundary"),
        ),
        native_evidence=M3M6LatticeNetworkEvidence(
            point_roles=(
                ("full", "boundary"),
                ("island", "unassigned"),
                ("outside", "boundary"),
            ),
            boundary_reasons=(
                ("full", "competing_domain_claim"),
                ("island", None),
                ("outside", "competing_domain_claim"),
            ),
            point_domain_ids=(
                ("full", None),
                ("island", None),
                ("outside", None),
            ),
            domains=(),
            producer_fingerprints=(),
        ),
    )
    automatic = DomainAnalysisResult(
        run_status="completed",
        m6_gate=M6Gate((frame,)),
        classifier_status="not_requested",
    )
    module = DomainCorrectionModule(
        manual_domain_id_factory=iter((MANUAL_DOMAIN_1, MANUAL_DOMAIN_2)).__next__,
        correction_operation_id_factory=iter((
            "create-a", "create-b", "move", "new-move",
        )).__next__,
        correction_history_id_factory=iter((
            "create-a-apply", "create-b-apply", "move-apply",
            "new-move-apply", "undo",
        )).__next__,
        clock=lambda: _NOW,
    )
    workspace = module.initialize(automatic)
    intents = (
        ManualDomainIntent.create(
            physical_frame_id="frame-0",
            source_ids=("outside",),
        ),
        ManualDomainIntent.create(
            physical_frame_id="frame-0",
            source_ids=("full",),
        ),
        ManualDomainIntent.move(
            physical_frame_id="frame-0",
            source_ids=("full", "outside"),
            manual_domain_id=MANUAL_DOMAIN_2,
            boundary_resolution="clear",
        ),
    )
    before_move: DomainCorrectionWorkspace | None = None
    for intent in intents:
        if intent.operation == "move":
            before_move = workspace
        preview = module.prepare(workspace, automatic, intent)
        workspace = module.dispatch(
            workspace,
            automatic,
            ApplyPreparedDomainCorrection.confirmed(preview),
        )
    assert before_move is not None
    return automatic, module, before_move, workspace
