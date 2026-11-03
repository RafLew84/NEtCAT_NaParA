from __future__ import annotations

from dataclasses import replace

from .detection_identity import DetectionIdentity
from .domain_correction_history import (
    DomainCorrectionHistoryRecord,
    active_operation_ids,
)
from .domain_correction_models import (
    DomainCorrectionAtom,
    DomainCorrectionWorkspace,
    ManualOrientationDecision,
    ManualOrientationIntent,
)
from .manual_domain_models import ManualDomainIntent, ManualDomainRecord


class DomainCorrectionEngine:
    """Own every immutable correction-state transition and audit replay."""

    def apply(
        self,
        workspace: DomainCorrectionWorkspace,
        atom: DomainCorrectionAtom,
        record: DomainCorrectionHistoryRecord,
    ) -> DomainCorrectionWorkspace:
        if record.action != "apply" or record.operation_id != atom.operation_id:
            raise ValueError("Apply history must describe the correction atom.")
        workspace = _with_boundary_baseline(workspace)
        transitioned = self._apply_atom(workspace, atom)
        return _record_transition(
            transitioned,
            atom,
            record,
        )

    def record_history(
        self,
        workspace: DomainCorrectionWorkspace,
        record: DomainCorrectionHistoryRecord,
    ) -> DomainCorrectionWorkspace:
        if record.action not in {"undo", "redo"}:
            raise ValueError("History transition must be undo or redo.")
        try:
            atom = next(
                value for value in workspace.atoms
                if value.operation_id == record.operation_id
            )
        except StopIteration as error:
            raise ValueError("History transition must reference an atom.") from error
        recorded = _record_transition(
            _with_boundary_baseline(workspace),
            atom,
            record,
        )
        return self.replay(recorded)

    def replay(
        self,
        workspace: DomainCorrectionWorkspace,
    ) -> DomainCorrectionWorkspace:
        active_ids = set(active_operation_ids(
            workspace.atoms,
            workspace.history_records,
        ))
        replayed = replace(
            workspace,
            orientation_decisions=workspace.baseline_orientation_decisions,
            manual_domains=workspace.baseline_manual_domains,
            cleared_boundary_source_keys=_legacy_boundary_baseline(workspace),
        )
        for atom in workspace.atoms:
            if atom.operation_id in active_ids:
                replayed = self._apply_atom(replayed, atom)
        return replayed

    def apply_manual_intent(
        self,
        workspace: DomainCorrectionWorkspace,
        intent: ManualDomainIntent,
    ) -> tuple[ManualDomainRecord, ...]:
        domains = _manual_domain_index(workspace)
        domain_id = intent.manual_domain_id
        assert domain_id is not None
        key = (intent.physical_frame_id, domain_id)
        if intent.operation == "create":
            domains = _remove_sources(
                domains,
                intent.physical_frame_id,
                intent.source_ids,
            )
            domains[key] = ManualDomainRecord(
                intent.physical_frame_id,
                domain_id,
                intent.source_ids,
                intent.source_ids,
            )
        elif intent.operation == "move":
            domains = _remove_sources(
                domains,
                intent.physical_frame_id,
                intent.source_ids,
                except_domain_id=domain_id,
            )
            current = domains[key]
            source_ids = tuple(sorted(set(current.source_ids).union(intent.source_ids)))
            domains[key] = replace(
                current,
                source_ids=source_ids,
                restore_source_ids=source_ids,
            )
        elif intent.operation == "delete":
            current = domains[key]
            domains[key] = replace(
                current,
                source_ids=(),
                restore_source_ids=current.source_ids,
                is_deleted=True,
            )
        else:
            current = domains[key]
            resolutions = dict(intent.member_resolutions)
            restored = tuple(
                source_id
                for source_id in current.restore_source_ids
                if resolutions.get(source_id) != "keep_current"
            )
            domains = _remove_sources(
                domains,
                intent.physical_frame_id,
                restored,
                except_domain_id=domain_id,
            )
            domains[key] = replace(
                current,
                source_ids=restored,
                restore_source_ids=(
                    current.restore_source_ids if not restored else restored
                ),
                is_deleted=not restored,
            )
        return tuple(domains[value] for value in sorted(domains))

    def manual_domain(
        self,
        workspace: DomainCorrectionWorkspace,
        physical_frame_id: str,
        manual_domain_id: str,
    ) -> ManualDomainRecord | None:
        return _manual_domain_index(workspace).get((
            physical_frame_id,
            manual_domain_id,
        ))

    def orientation_decisions(
        self,
        workspace: DomainCorrectionWorkspace,
    ) -> dict[DetectionIdentity, ManualOrientationDecision]:
        return {
            DetectionIdentity(
                physical_frame_id=value.physical_frame_id,
                source_id=value.source_id,
            ): value
            for value in workspace.orientation_decisions
        }

    def _apply_atom(
        self,
        workspace: DomainCorrectionWorkspace,
        atom: DomainCorrectionAtom,
    ) -> DomainCorrectionWorkspace:
        intent = atom.intent
        if isinstance(intent, ManualDomainIntent):
            return replace(
                workspace,
                manual_domains=self.apply_manual_intent(workspace, intent),
                cleared_boundary_source_keys=_boundary_keys(workspace, atom),
            )
        return replace(
            workspace,
            orientation_decisions=self._apply_orientation_intent(workspace, intent),
        )

    def _apply_orientation_intent(
        self,
        workspace: DomainCorrectionWorkspace,
        intent: ManualOrientationIntent,
    ) -> tuple[ManualOrientationDecision, ...]:
        decisions = self.orientation_decisions(workspace)
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
        return tuple(decisions[key] for key in sorted(decisions))


def _with_boundary_baseline(
    workspace: DomainCorrectionWorkspace,
) -> DomainCorrectionWorkspace:
    if workspace.legacy_boundary_source_keys is not None:
        return workspace
    return replace(
        workspace,
        legacy_boundary_source_keys=_legacy_boundary_baseline(workspace),
    )


def _record_transition(
    workspace: DomainCorrectionWorkspace,
    atom: DomainCorrectionAtom,
    record: DomainCorrectionHistoryRecord,
) -> DomainCorrectionWorkspace:
    revisions = dict(workspace.review_revisions)
    for target in atom.invalidates_review_targets:
        revisions[target] += 1
    return replace(
        workspace,
        revision=workspace.revision + 1,
        atoms=workspace.atoms + ((atom,) if record.action == "apply" else ()),
        history_records=workspace.history_records + (record,),
        review_revisions=tuple(sorted(revisions.items())),
    )


def _legacy_boundary_baseline(
    workspace: DomainCorrectionWorkspace,
) -> tuple[DetectionIdentity, ...]:
    baseline = workspace.legacy_boundary_source_keys
    if baseline is not None:
        return baseline
    keys = set(workspace.cleared_boundary_source_keys)
    active_ids = set(active_operation_ids(workspace.atoms, workspace.history_records))
    for atom in reversed(workspace.atoms):
        if atom.operation_id not in active_ids:
            continue
        for effect in reversed(atom.effects):
            if effect.before_boundary is not True or effect.after_boundary is None:
                continue
            key = DetectionIdentity(
                physical_frame_id=atom.physical_frame_id,
                source_id=effect.source_id,
            )
            if effect.before_boundary:
                keys.discard(key)
            else:
                keys.add(key)
    return tuple(sorted(keys))


def _boundary_keys(
    workspace: DomainCorrectionWorkspace,
    atom: DomainCorrectionAtom,
) -> tuple[DetectionIdentity, ...]:
    keys = set(workspace.cleared_boundary_source_keys)
    for effect in atom.effects:
        if effect.before_boundary is not True or effect.after_boundary is None:
            continue
        key = DetectionIdentity(
            physical_frame_id=atom.physical_frame_id,
            source_id=effect.source_id,
        )
        if effect.after_boundary:
            keys.discard(key)
        else:
            keys.add(key)
    return tuple(sorted(keys))


def _remove_sources(
    domains: dict[tuple[str, str], ManualDomainRecord],
    physical_frame_id: str,
    source_ids: tuple[str, ...],
    *,
    except_domain_id: str | None = None,
) -> dict[tuple[str, str], ManualDomainRecord]:
    updated = dict(domains)
    removed = set(source_ids)
    for key, domain in domains.items():
        if (
            domain.physical_frame_id != physical_frame_id
            or domain.manual_domain_id == except_domain_id
            or domain.is_deleted
            or removed.isdisjoint(domain.source_ids)
        ):
            continue
        retained = tuple(value for value in domain.source_ids if value not in removed)
        updated[key] = replace(
            domain,
            source_ids=retained,
            restore_source_ids=(domain.source_ids if not retained else retained),
            is_deleted=not retained,
        )
    return updated


def _manual_domain_index(
    workspace: DomainCorrectionWorkspace,
) -> dict[tuple[str, str], ManualDomainRecord]:
    return {
        (value.physical_frame_id, value.manual_domain_id): value
        for value in workspace.manual_domains
    }


__all__ = ["DomainCorrectionEngine"]
