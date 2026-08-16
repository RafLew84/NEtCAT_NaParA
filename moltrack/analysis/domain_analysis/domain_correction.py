from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
from collections.abc import Callable
from datetime import datetime, timezone
from uuid import uuid4

from .classifier_models import MoleculeClassification
from .detection_identity import DetectionIdentity
from .domain_correction_actions import ApplyPreparedDomainCorrection
from .domain_correction_models import (
    DomainCorrectionAtom,
    DomainCorrectionConflict,
    DomainCorrectionReviewTarget,
    DomainCorrectionWorkspace,
    EffectiveDomainProjection,
    EffectiveMoleculeOrientation,
    EffectiveOrientationSubdomain,
    EffectiveOrientationSource,
    ManualOrientationDecision,
    ManualOrientationIntent,
    PreparedDomainCorrection,
)
from .domain_correction_history import (
    DomainCorrectionHistoryAction,
    DomainCorrectionHistoryAvailability,
    DomainCorrectionHistoryRecord,
)
from .domain_correction_replay import (
    _legacy_boundary_baseline,
    apply_manual_domain_intent,
    replay_active_atoms,
)
from .domain_correction_policy import (
    compatible_automatic_orientation,
    prepared_correction_report,
)
from .manual_domain_models import ManualDomainIntent, ManualDomainRecord
from .manual_domain_projection import (
    active_manual_memberships,
    project_effective_domains,
    source_footprints_for_frame,
)
from .correction_rebase import correction_anchor_fingerprint
from .models import DomainAnalysisResult, M6FrameGate
from .network_backend_evidence import M3M6LatticeNetworkEvidence
from .texture_abc_adapter import ABC_ORIENTATION_CLASSIFIER_ID


class DomainCorrectionModule:
    """Prepare orientation corrections and derive one effective projection."""

    def __init__(
        self,
        manual_domain_id_factory: Callable[[], str] | None = None,
        correction_operation_id_factory: Callable[[], str] | None = None,
        correction_history_id_factory: Callable[[], str] | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._manual_domain_id_factory = manual_domain_id_factory or (
            lambda: str(uuid4())
        )
        self._correction_operation_id_factory = (
            correction_operation_id_factory or (lambda: str(uuid4()))
        )
        self._correction_history_id_factory = (
            correction_history_id_factory or (lambda: str(uuid4()))
        )
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def initialize(
        self,
        automatic: DomainAnalysisResult,
    ) -> DomainCorrectionWorkspace:
        _validate_automatic(automatic)
        return DomainCorrectionWorkspace(
            automatic_fingerprint=correction_anchor_fingerprint(automatic),
            revision=0,
        )

    def prepare(
        self,
        workspace: DomainCorrectionWorkspace,
        automatic: DomainAnalysisResult,
        intent: ManualOrientationIntent | ManualDomainIntent,
    ) -> PreparedDomainCorrection:
        _validate_workspace_anchor(workspace, automatic)
        if not isinstance(intent, (ManualOrientationIntent, ManualDomainIntent)):
            raise TypeError("intent must be a supported Domain Correction intent.")
        frame = _frame(automatic, intent.physical_frame_id)
        blocked: tuple[DomainCorrectionConflict, ...] = ()
        if isinstance(intent, ManualDomainIntent):
            intent, blocked = _prepared_manual_domain_intent(
                workspace,
                intent,
                self._manual_domain_id_factory,
                tuple(
                    value.lattice_domain_id
                    for value in frame.full_domains + frame.small_ordered_islands
                ),
            )
        missing = tuple(
            value for value in intent.source_ids
            if value not in set(frame.analyzed_source_ids)
        )
        if missing:
            blocked += (DomainCorrectionConflict(
                "blocked",
                "unknown_source_ids",
                "The prepared batch contains unknown source IDs.",
                missing,
            ),)
        if isinstance(intent, ManualDomainIntent) and not blocked:
            prospective = replace(
                workspace,
                manual_domains=apply_manual_domain_intent(workspace, intent),
            )
            self.project(automatic, prospective)
        changed = () if blocked else (
            _manual_domain_changed_source_ids(workspace, intent)
            if isinstance(intent, ManualDomainIntent)
            else tuple(
                source_id
                for source_id in intent.source_ids
                if _decision_would_change(
                    _decision_index(workspace),
                    intent,
                    source_id,
                )
            )
        )
        return prepared_correction_report(
            workspace,
            frame,
            intent,
            changed,
            self.project(automatic, workspace),
            source_ids=_manual_domain_source_ids(workspace, intent),
            blocked=blocked,
        )

    def dispatch(
        self,
        workspace: DomainCorrectionWorkspace,
        automatic: DomainAnalysisResult,
        action: ApplyPreparedDomainCorrection,
    ) -> DomainCorrectionWorkspace:
        _validate_workspace_anchor(workspace, automatic)
        if not isinstance(action, ApplyPreparedDomainCorrection):
            raise TypeError("action must be ApplyPreparedDomainCorrection.")
        preview = action.preview
        if (
            preview.expected_revision != workspace.revision
            or preview.automatic_fingerprint != workspace.automatic_fingerprint
        ):
            raise ValueError("Prepared Domain Correction is stale.")
        if preview != self.prepare(workspace, automatic, preview.intent):
            raise ValueError("Prepared Domain Correction does not match its intent.")
        if preview.is_blocked:
            raise ValueError("Prepared Domain Correction is blocked.")
        if not preview.changed_source_ids:
            return workspace
        if (
            preview.requires_confirmation
            and action.confirmed_prepared_fingerprint
            != preview.prepared_fingerprint
        ):
            raise ValueError(
                "Prepared Domain Correction requires confirmation."
            )
        if workspace.legacy_boundary_source_keys is None:
            workspace = replace(
                workspace,
                legacy_boundary_source_keys=_legacy_boundary_baseline(workspace),
            )
        intent = preview.intent
        if isinstance(intent, ManualDomainIntent):
            boundary_keys = set(workspace.cleared_boundary_source_keys)
            if intent.operation == "move" and intent.boundary_resolution is not None:
                intent_keys = {
                    DetectionIdentity(
                        physical_frame_id=intent.physical_frame_id,
                        source_id=effect.source_id,
                    )
                    for effect in preview.effects
                    if effect.before_boundary is True
                    and effect.after_boundary is not None
                }
                if intent.boundary_resolution == "clear":
                    boundary_keys.update(intent_keys)
                else:
                    boundary_keys.difference_update(intent_keys)
            return self._append_atom(replace(
                workspace,
                manual_domains=apply_manual_domain_intent(workspace, intent),
                cleared_boundary_source_keys=tuple(sorted(boundary_keys)),
            ), preview)
        decisions = _decision_index(workspace)
        for source_id in intent.source_ids:
            key = DetectionIdentity(
                physical_frame_id=intent.physical_frame_id,
                source_id=source_id,
            )
            if intent.operation == "reset":
                decisions.pop(key, None)
            else:
                assert intent.orientation_label is not None
                decisions[key] = ManualOrientationDecision(
                    physical_frame_id=intent.physical_frame_id,
                    source_id=source_id,
                    orientation_label=intent.orientation_label,
                    reason_code=intent.reason_code,
                )
        return self._append_atom(replace(
            workspace,
            orientation_decisions=tuple(decisions[key] for key in sorted(decisions)),
        ), preview)

    def _append_atom(
        self,
        workspace: DomainCorrectionWorkspace,
        preview: PreparedDomainCorrection,
    ) -> DomainCorrectionWorkspace:
        legacy_boundary_source_keys = workspace.legacy_boundary_source_keys
        assert legacy_boundary_source_keys is not None
        targets: tuple[DomainCorrectionReviewTarget, ...] = (
            ("m6", "orientation")
            if preview.axis == "m6"
            else ("orientation",)
        )
        revisions = dict(workspace.review_revisions)
        for target in targets:
            revisions[target] += 1
        atom = DomainCorrectionAtom(
            operation_id=self._correction_operation_id_factory(),
            prepared_fingerprint=preview.prepared_fingerprint,
            axis=preview.axis,
            physical_frame_id=preview.intent.physical_frame_id,
            source_ids=preview.source_ids,
            intent=preview.intent,
            invalidates_review_targets=targets,
            effects=preview.effects,
        )
        record = self._history_record("apply", atom)
        return replace(
            workspace,
            revision=workspace.revision + 1,
            atoms=workspace.atoms + (atom,),
            history_records=workspace.history_records + (record,),
            legacy_boundary_source_keys=legacy_boundary_source_keys,
            review_revisions=tuple(sorted(revisions.items())),
        )

    def history_availability(
        self,
        workspace: DomainCorrectionWorkspace,
        physical_frame_id: str,
    ) -> DomainCorrectionHistoryAvailability:
        if not isinstance(workspace, DomainCorrectionWorkspace):
            raise TypeError("workspace must be a DomainCorrectionWorkspace.")
        return workspace.history_for(physical_frame_id)

    def undo(
        self,
        workspace: DomainCorrectionWorkspace,
        automatic: DomainAnalysisResult,
        physical_frame_id: str,
    ) -> DomainCorrectionWorkspace:
        return self._change_history(
            workspace,
            automatic,
            physical_frame_id,
            action="undo",
        )

    def redo(
        self,
        workspace: DomainCorrectionWorkspace,
        automatic: DomainAnalysisResult,
        physical_frame_id: str,
    ) -> DomainCorrectionWorkspace:
        return self._change_history(
            workspace,
            automatic,
            physical_frame_id,
            action="redo",
        )

    def _change_history(
        self,
        workspace: DomainCorrectionWorkspace,
        automatic: DomainAnalysisResult,
        physical_frame_id: str,
        *,
        action: DomainCorrectionHistoryAction,
    ) -> DomainCorrectionWorkspace:
        _validate_workspace_anchor(workspace, automatic)
        availability = workspace.history_for(physical_frame_id)
        target = availability.undo if action == "undo" else availability.redo
        if target is None:
            raise ValueError(f"No correction is available to {action} in this frame.")
        atom = next(
            value for value in workspace.atoms
            if value.operation_id == target.operation_id
        )
        record = self._history_record(action, atom)
        legacy_boundary_source_keys = workspace.legacy_boundary_source_keys
        if legacy_boundary_source_keys is None:
            legacy_boundary_source_keys = _legacy_boundary_baseline(workspace)
        revisions = dict(workspace.review_revisions)
        for review_target in atom.invalidates_review_targets:
            revisions[review_target] += 1
        recorded = replace(
            workspace,
            revision=workspace.revision + 1,
            history_records=workspace.history_records + (record,),
            legacy_boundary_source_keys=legacy_boundary_source_keys,
            review_revisions=tuple(sorted(revisions.items())),
        )
        return replay_active_atoms(recorded)

    def _history_record(
        self,
        action: DomainCorrectionHistoryAction,
        atom: DomainCorrectionAtom,
    ) -> DomainCorrectionHistoryRecord:
        return DomainCorrectionHistoryRecord(
            record_id=self._correction_history_id_factory(),
            action=action,
            operation_id=atom.operation_id,
            physical_frame_id=atom.physical_frame_id,
            recorded_at=self._clock(),
        )

    def project(
        self,
        automatic: DomainAnalysisResult,
        workspace: DomainCorrectionWorkspace,
    ) -> EffectiveDomainProjection:
        _validate_workspace_anchor(workspace, automatic)
        decisions = _decision_index(workspace)
        manual_memberships = active_manual_memberships(workspace.manual_domains)
        tombstoned_sources = {
            DetectionIdentity(
                physical_frame_id=domain.physical_frame_id,
                source_id=source_id,
            )
            for domain in workspace.manual_domains
            if domain.is_deleted
            for source_id in domain.restore_source_ids
        }.difference(manual_memberships)
        classifications = _classification_index(automatic)
        assert automatic.m6_gate is not None
        footprints = {
            frame.physical_frame_id: source_footprints_for_frame(frame)
            for frame in automatic.m6_gate.frames
        }
        boundary_ids = {
            frame.physical_frame_id: _automatic_boundary_source_ids(frame)
            for frame in automatic.m6_gate.frames
        }
        cleared_boundary_keys = set(workspace.cleared_boundary_source_keys)
        molecules = tuple(
            _project_molecule(
                frame,
                source_id,
                classifications,
                decisions,
                manual_memberships,
                DetectionIdentity(
                    physical_frame_id=frame.physical_frame_id,
                    source_id=source_id,
                ) in tombstoned_sources,
                _effective_boundary_role(
                    boundary_ids[frame.physical_frame_id],
                    source_id,
                    DetectionIdentity(
                        physical_frame_id=frame.physical_frame_id,
                        source_id=source_id,
                    ) in cleared_boundary_keys,
                ),
                footprints[frame.physical_frame_id][source_id],
            )
            for frame in automatic.m6_gate.frames
            for source_id in frame.analyzed_source_ids
        )
        domains = project_effective_domains(
            automatic.m6_gate.frames,
            workspace.manual_domains,
            molecules,
        )
        return EffectiveDomainProjection(
            automatic_result=automatic,
            correction_revision=workspace.revision,
            molecules=molecules,
            orientation_subdomains=_orientation_subdomains(molecules),
            domains=domains,
        )


def _project_molecule(
    frame: M6FrameGate,
    source_id: str,
    classifications: dict[DetectionIdentity, MoleculeClassification],
    decisions: dict[DetectionIdentity, ManualOrientationDecision],
    manual_memberships: dict[DetectionIdentity, str],
    is_tombstoned_member: bool,
    automatic_boundary: bool | None,
    footprint_pixels_xy: tuple[tuple[int, int], ...] | None,
) -> EffectiveMoleculeOrientation:
    key = DetectionIdentity(
        physical_frame_id=frame.physical_frame_id,
        source_id=source_id,
    )
    classification = classifications.get(key)
    decision = decisions.get(key)
    manual_domain_id = manual_memberships.get(key)
    partition, domain_id = (
        ("full_domain", manual_domain_id)
        if manual_domain_id is not None
        else (("outside", None) if is_tombstoned_member else _membership(
            frame,
            source_id,
        ))
    )
    automatic_label = compatible_automatic_orientation(
        frame,
        classification,
        domain_id,
    )
    if decision is not None:
        label = decision.orientation_label
        source: EffectiveOrientationSource = "manual"
        confidence = None
    elif automatic_label is not None:
        label = automatic_label
        source = "automatic"
        confidence = classification.evidence_strength if classification else None
    else:
        label = None
        source = "none"
        confidence = None
    return EffectiveMoleculeOrientation(
        physical_frame_id=frame.physical_frame_id,
        source_id=source_id,
        m6_partition=partition,
        effective_domain_id=domain_id if partition == "full_domain" else None,
        automatic_classification=classification,
        manual_decision=decision,
        effective_orientation=label,
        effective_orientation_source=source,
        effective_confidence=confidence,
        raw_orientation_evidence=(
            None if classification is None else classification.diagnostic_evidence
        ),
        is_boundary=(
            None
            if automatic_boundary is None
            else automatic_boundary and partition == "full_domain"
        ),
        footprint_pixels_xy=footprint_pixels_xy,
    )


def _membership(frame: M6FrameGate, source_id: str) -> tuple[str, str | None]:
    for component in frame.full_domains + frame.small_ordered_islands:
        if source_id in component.source_ids:
            return component.component_type, component.lattice_domain_id
    return "outside", None


def _automatic_boundary_source_ids(frame: M6FrameGate) -> set[str] | None:
    evidence = frame.native_evidence
    if not isinstance(evidence, M3M6LatticeNetworkEvidence):
        return None
    return {
        source_id
        for source_id, point_role in evidence.point_roles
        if point_role == "boundary"
    }


def _effective_boundary_role(
    boundary_source_ids: set[str] | None,
    source_id: str,
    is_cleared: bool,
) -> bool | None:
    if is_cleared:
        return False
    return (
        None
        if boundary_source_ids is None
        else source_id in boundary_source_ids
    )


def _orientation_subdomains(
    molecules: tuple[EffectiveMoleculeOrientation, ...],
) -> tuple[EffectiveOrientationSubdomain, ...]:
    grouped: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    for molecule in molecules:
        label = molecule.effective_orientation
        if (
            molecule.m6_partition == "full_domain"
            and molecule.effective_domain_id is not None
            and label is not None
            and len(label) == 1
            and "A" <= label <= "Z"
        ):
            grouped[(
                molecule.physical_frame_id,
                molecule.effective_domain_id,
                label,
            )].append(molecule.source_id)
    return tuple(
        EffectiveOrientationSubdomain(*key, tuple(sorted(source_ids)))
        for key, source_ids in sorted(grouped.items())
    )


def _classification_index(
    automatic: DomainAnalysisResult,
) -> dict[DetectionIdentity, MoleculeClassification]:
    return {
        DetectionIdentity(
            physical_frame_id=classification.physical_frame_id,
            source_id=classification.source_id,
        ): classification
        for outcome in automatic.classifier_outcomes or ()
        if outcome.classifier_id == ABC_ORIENTATION_CLASSIFIER_ID
        for classification in outcome.molecule_classifications
    }


def _decision_index(
    workspace: DomainCorrectionWorkspace,
) -> dict[DetectionIdentity, ManualOrientationDecision]:
    return {
        DetectionIdentity(
            physical_frame_id=value.physical_frame_id,
            source_id=value.source_id,
        ): value
        for value in workspace.orientation_decisions
    }


def _decision_would_change(
    decisions: dict[DetectionIdentity, ManualOrientationDecision],
    intent: ManualOrientationIntent,
    source_id: str,
) -> bool:
    current = decisions.get(DetectionIdentity(
        physical_frame_id=intent.physical_frame_id,
        source_id=source_id,
    ))
    if intent.operation == "reset":
        return current is not None
    return (
        current is None
        or current.orientation_label != intent.orientation_label
        or current.reason_code != intent.reason_code
    )


def _prepared_manual_domain_intent(
    workspace: DomainCorrectionWorkspace,
    intent: ManualDomainIntent,
    id_factory: Callable[[], str],
    automatic_domain_ids: tuple[str, ...],
) -> tuple[
    ManualDomainIntent,
    tuple[DomainCorrectionConflict, ...],
]:
    if intent.operation == "create":
        return _prepared_create_domain_intent(
            workspace,
            intent,
            id_factory,
            automatic_domain_ids,
        )
    assert intent.manual_domain_id is not None
    key = (intent.physical_frame_id, intent.manual_domain_id)
    record = _manual_domain_index(workspace).get(key)
    if record is None:
        return intent, (DomainCorrectionConflict(
            "blocked",
            "manual_domain_target_missing",
            "Manual domain does not exist in this frame.",
            intent.source_ids,
        ),)
    if intent.operation == "move" and record.is_deleted:
        return intent, (DomainCorrectionConflict(
            "blocked",
            "manual_domain_target_deleted",
            "Cannot move molecules into a deleted manual domain.",
            intent.source_ids,
        ),)
    if intent.operation == "delete" and record.is_deleted:
        return intent, (DomainCorrectionConflict(
            "blocked",
            "manual_domain_already_deleted",
            "Manual domain is already deleted.",
            (),
        ),)
    if intent.operation == "restore" and not record.is_deleted:
        return intent, (DomainCorrectionConflict(
            "blocked",
            "manual_domain_not_deleted",
            "Only a manual-domain tombstone can be restored.",
            (),
        ),)
    if intent.operation == "restore":
        return intent, _restore_conflicts(workspace, intent, record)
    return intent, ()


def _restore_conflicts(
    workspace: DomainCorrectionWorkspace,
    intent: ManualDomainIntent,
    record: ManualDomainRecord,
) -> tuple[DomainCorrectionConflict, ...]:
    memberships = active_manual_memberships(workspace.manual_domains)
    resolutions = dict(intent.member_resolutions)
    invalid_resolutions = tuple(
        source_id
        for source_id in resolutions
        if source_id not in record.restore_source_ids
    )
    if invalid_resolutions:
        return (DomainCorrectionConflict(
            "blocked",
            "invalid_restore_resolution",
            "Restore resolutions must identify saved domain members.",
            invalid_resolutions,
        ),)
    conflicts = tuple(
        source_id
        for source_id in record.restore_source_ids
        if memberships.get(DetectionIdentity(
            physical_frame_id=intent.physical_frame_id,
            source_id=source_id,
        )) not in {None, intent.manual_domain_id}
        and source_id not in resolutions
    )
    if not conflicts:
        return ()
    return (DomainCorrectionConflict(
        "blocked",
        "restore_membership_conflict",
        "Restore members already belong to another manual domain.",
        conflicts,
    ),)


def _manual_domain_source_ids(
    workspace: DomainCorrectionWorkspace,
    intent: ManualOrientationIntent | ManualDomainIntent,
) -> tuple[str, ...] | None:
    if not isinstance(intent, ManualDomainIntent):
        return None
    if intent.operation in {"create", "move"}:
        return intent.source_ids
    record = _manual_domain_index(workspace).get((
        intent.physical_frame_id,
        intent.manual_domain_id or "",
    ))
    if record is None:
        return None
    return (
        record.source_ids
        if intent.operation == "delete"
        else record.restore_source_ids
    )


def _prepared_create_domain_intent(
    workspace: DomainCorrectionWorkspace,
    intent: ManualDomainIntent,
    id_factory: Callable[[], str],
    automatic_domain_ids: tuple[str, ...],
) -> tuple[ManualDomainIntent, tuple[DomainCorrectionConflict, ...]]:
    domain_id = intent.manual_domain_id or id_factory()
    prepared = ManualDomainIntent(
        physical_frame_id=intent.physical_frame_id,
        operation="create",
        source_ids=intent.source_ids,
        manual_domain_id=domain_id,
        boundary_resolution=intent.boundary_resolution,
        member_resolutions=intent.member_resolutions,
    )
    known_ids = {
        value.manual_domain_id for value in workspace.manual_domains
    }.union(automatic_domain_ids)
    if domain_id not in known_ids:
        return prepared, ()
    return prepared, (DomainCorrectionConflict(
        "blocked",
        "manual_domain_id_conflict",
        "Manual domain ID already exists.",
        intent.source_ids,
    ),)


def _manual_domain_changed_source_ids(
    workspace: DomainCorrectionWorkspace,
    intent: ManualDomainIntent,
) -> tuple[str, ...]:
    if intent.operation == "create":
        return intent.source_ids
    if intent.operation == "move":
        memberships = active_manual_memberships(workspace.manual_domains)
        return tuple(
            source_id
            for source_id in intent.source_ids
            if memberships.get(DetectionIdentity(
                physical_frame_id=intent.physical_frame_id,
                source_id=source_id,
            ))
            != intent.manual_domain_id
        )
    record = _manual_domain_index(workspace)[
        (intent.physical_frame_id, intent.manual_domain_id or "")
    ]
    if intent.operation == "delete":
        return record.source_ids
    resolutions = dict(intent.member_resolutions)
    return tuple(
        source_id
        for source_id in record.restore_source_ids
        if resolutions.get(source_id) != "keep_current"
    )


def _manual_domain_index(
    workspace: DomainCorrectionWorkspace,
) -> dict[tuple[str, str], ManualDomainRecord]:
    return {
        (value.physical_frame_id, value.manual_domain_id): value
        for value in workspace.manual_domains
    }


def _frame(automatic: DomainAnalysisResult, physical_frame_id: str) -> M6FrameGate:
    assert automatic.m6_gate is not None
    try:
        return next(
            value
            for value in automatic.m6_gate.frames
            if value.physical_frame_id == physical_frame_id
        )
    except StopIteration as error:
        raise ValueError(f"Unknown physical_frame_id: {physical_frame_id!r}.") from error


def _validate_automatic(automatic: DomainAnalysisResult) -> None:
    if not isinstance(automatic, DomainAnalysisResult):
        raise TypeError("automatic must be a DomainAnalysisResult.")
    if automatic.m6_gate is None:
        raise ValueError("Domain corrections require a published M6 gate.")


def _validate_workspace_anchor(
    workspace: DomainCorrectionWorkspace,
    automatic: DomainAnalysisResult,
) -> None:
    if not isinstance(workspace, DomainCorrectionWorkspace):
        raise TypeError("workspace must be a DomainCorrectionWorkspace.")
    _validate_automatic(automatic)
    if workspace.automatic_fingerprint != correction_anchor_fingerprint(automatic):
        raise ValueError("Domain Correction Workspace automatic anchor is stale.")


__all__ = ["DomainCorrectionModule"]
