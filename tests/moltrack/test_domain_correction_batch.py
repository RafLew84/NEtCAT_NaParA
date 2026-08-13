from __future__ import annotations

import pytest

from moltrack.analysis.domain_analysis import (
    ApplyPreparedDomainCorrection,
    DomainCorrectionModule,
    ManualOrientationIntent,
)
from test_domain_correction_orientation import _automatic_result


def test_confirmed_multi_group_apply_commits_one_frozen_batch() -> None:
    automatic = _automatic_result()
    operation_ids = iter(("operation-1", "operation-2"))
    module = DomainCorrectionModule(
        correction_operation_id_factory=lambda: next(operation_ids),
    )
    workspace = module.initialize(automatic)
    preview = module.prepare(
        workspace,
        automatic,
        ManualOrientationIntent.assign(
            physical_frame_id="frame-0",
            source_ids=("outside", "full", "outside"),
            orientation_label="D",
        ),
    )

    assert preview.axis == "orientation"
    assert preview.source_ids == ("full", "outside")
    assert tuple(effect.source_id for effect in preview.effects) == (
        "full",
        "outside",
    )
    assert preview.source_groups == ("domain-1", "outside")
    assert {value.severity for value in preview.conflicts} == {
        "confirmation_required",
        "informational",
    }
    assert preview.requires_confirmation
    assert not preview.is_blocked

    with pytest.raises(ValueError, match="confirmation"):
        module.dispatch(
            workspace,
            automatic,
            ApplyPreparedDomainCorrection(preview),
        )
    assert workspace.revision == 0
    assert workspace.atoms == ()
    with pytest.raises(ValueError, match="confirmation"):
        module.dispatch(
            workspace,
            automatic,
            ApplyPreparedDomainCorrection(preview, "different-preview"),
        )

    updated = module.dispatch(
        workspace,
        automatic,
        ApplyPreparedDomainCorrection.confirmed(preview),
    )

    assert updated.revision == 1
    assert len(updated.atoms) == 1
    atom = updated.atoms[0]
    assert atom.operation_id == "operation-1"
    assert atom.source_ids == ("full", "outside")
    assert atom.prepared_fingerprint == preview.prepared_fingerprint
    assert atom.invalidates_review_targets == ("orientation",)
    assert updated.review_revision("m6") == 0
    assert updated.review_revision("orientation") == 1
    assert tuple(value.source_id for value in updated.orientation_decisions) == (
        "full",
        "outside",
    )


def test_blocked_or_stale_preview_never_applies_a_conflict_free_subset() -> None:
    automatic = _automatic_result()
    module = DomainCorrectionModule(
        correction_operation_id_factory=lambda: "operation-1",
    )
    workspace = module.initialize(automatic)
    blocked = module.prepare(
        workspace,
        automatic,
        ManualOrientationIntent.assign(
            physical_frame_id="frame-0",
            source_ids=("full", "outside"),
            orientation_label="Unresolvable",
        ),
    )

    assert blocked.is_blocked
    assert tuple(
        value.code for value in blocked.conflicts if value.severity == "blocked"
    ) == (
        "reason_required",
    )
    with pytest.raises(ValueError, match="blocked"):
        module.dispatch(
            workspace,
            automatic,
            ApplyPreparedDomainCorrection.confirmed(blocked),
        )
    assert workspace == module.initialize(automatic)

    current = module.prepare(
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
        ApplyPreparedDomainCorrection(current),
    )
    with pytest.raises(ValueError, match="stale"):
        module.dispatch(
            workspace,
            automatic,
            ApplyPreparedDomainCorrection.confirmed(blocked),
        )
    assert workspace.revision == 1
    assert tuple(value.source_id for value in workspace.orientation_decisions) == (
        "outside",
    )

    unknown = module.prepare(
        workspace,
        automatic,
        ManualOrientationIntent.assign(
            physical_frame_id="frame-0",
            source_ids=("full", "missing"),
            orientation_label="E",
        ),
    )
    assert unknown.is_blocked
    assert "unknown_source_ids" in {
        value.code for value in unknown.conflicts if value.severity == "blocked"
    }
    with pytest.raises(ValueError, match="blocked"):
        module.dispatch(
            workspace,
            automatic,
            ApplyPreparedDomainCorrection.confirmed(unknown),
        )
    assert workspace.revision == 1
    assert len(workspace.atoms) == 1


def test_replacing_manual_reason_requires_confirmation_only_on_orientation() -> None:
    automatic = _automatic_result()
    module = DomainCorrectionModule()
    workspace = module.initialize(automatic)
    first = module.prepare(
        workspace,
        automatic,
        ManualOrientationIntent.assign(
            physical_frame_id="frame-0",
            source_ids=("full",),
            orientation_label="Unresolvable",
            reason_code="overlap",
        ),
    )
    workspace = module.dispatch(
        workspace,
        automatic,
        ApplyPreparedDomainCorrection(first),
    )

    replacement = module.prepare(
        workspace,
        automatic,
        ManualOrientationIntent.assign(
            physical_frame_id="frame-0",
            source_ids=("full",),
            orientation_label="Unresolvable",
            reason_code="low_signal",
        ),
    )

    assert "manual_decision_replaced" in {
        value.code for value in replacement.conflicts
        if value.severity == "confirmation_required"
    }
