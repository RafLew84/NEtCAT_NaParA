from __future__ import annotations

from collections import defaultdict

from .classifier_models import MoleculeClassification
from .detection_identity import DetectionIdentity
from .domain_correction_models import (
    DomainCorrectionConflict,
    DomainCorrectionConflictSeverity,
    DomainCorrectionEffect,
    DomainCorrectionWorkspace,
    EffectiveDomainProjection,
    ManualOrientationIntent,
    PreparedDomainCorrection,
)
from .manual_domain_models import ManualDomainIntent
from .models import M6FrameGate
from .network_backend_evidence import M3M6LatticeNetworkEvidence


def prepared_correction_report(
    workspace: DomainCorrectionWorkspace,
    frame: M6FrameGate,
    intent: ManualOrientationIntent | ManualDomainIntent,
    changed_source_ids: tuple[str, ...],
    projection: EffectiveDomainProjection,
    *,
    source_ids: tuple[str, ...] | None = None,
    blocked: tuple[DomainCorrectionConflict, ...] = (),
) -> PreparedDomainCorrection:
    """Build one deterministic effects/conflicts report for a frozen batch."""

    frozen_source_ids = source_ids or intent.source_ids or changed_source_ids
    known_source_ids = tuple(
        value for value in frozen_source_ids if value in frame.analyzed_source_ids
    )
    effects = tuple(
        _effect(frame, projection, intent, source_id)
        for source_id in known_source_ids
    )
    conflicts = list(blocked)
    conflicts.extend(_reason_conflicts(intent))
    conflicts.extend(_network_qc_conflicts(
        frame,
        intent,
        frozen_source_ids,
        projection,
    ))
    conflicts.extend(_impact_conflicts(
        workspace,
        intent,
        effects,
        changed_source_ids,
        projection,
    ))
    conflicts.extend(_information_conflicts(intent, effects, changed_source_ids))
    return PreparedDomainCorrection(
        expected_revision=workspace.revision,
        automatic_fingerprint=workspace.automatic_fingerprint,
        intent=intent,
        changed_source_ids=changed_source_ids,
        source_ids=frozen_source_ids,
        effects=effects,
        conflicts=_combined_conflicts(tuple(conflicts)),
    )


def _effect(
    frame: M6FrameGate,
    projection: EffectiveDomainProjection,
    intent: ManualOrientationIntent | ManualDomainIntent,
    source_id: str,
) -> DomainCorrectionEffect:
    molecule = projection.molecule(frame.physical_frame_id, source_id)
    source_group = molecule.effective_domain_id or molecule.m6_partition
    if isinstance(intent, ManualOrientationIntent):
        before = molecule.effective_orientation
        after = (
            compatible_automatic_orientation(
                frame,
                molecule.automatic_classification,
                molecule.effective_domain_id,
            )
            if intent.operation == "reset"
            else intent.orientation_label
        )
    else:
        before = molecule.effective_domain_id or molecule.m6_partition
        boundary_transfer = (
            intent.operation == "move"
            and molecule.is_boundary is True
            and before not in {
                "outside",
                "small_ordered_island",
                intent.manual_domain_id,
            }
        )
        before_boundary = True if boundary_transfer else None
        after_boundary = (
            intent.boundary_resolution == "preserve"
            if boundary_transfer and intent.boundary_resolution is not None
            else None
        )
        if (
            intent.operation == "restore"
            and dict(intent.member_resolutions).get(source_id) == "keep_current"
        ):
            after = before
        else:
            after = (
                "outside"
                if intent.operation == "delete"
                else intent.manual_domain_id
            )
        return DomainCorrectionEffect(
            source_id,
            source_group,
            before,
            after,
            before_boundary,
            after_boundary,
        )
    return DomainCorrectionEffect(source_id, source_group, before, after)


def compatible_automatic_orientation(
    frame: M6FrameGate,
    classification: MoleculeClassification | None,
    effective_domain_id: str | None,
) -> str | None:
    """Return the automatic label only while its M6 gate remains compatible."""

    if classification is None:
        return None
    if (
        classification.physical_frame_id != frame.physical_frame_id
        or classification.m6_gate_fingerprint != frame.m6_gate_fingerprint
        or classification.m6_partition != "full_domain"
        or classification.lattice_domain_id != effective_domain_id
    ):
        return None
    return classification.orientation_label


def _reason_conflicts(
    intent: ManualOrientationIntent | ManualDomainIntent,
) -> tuple[DomainCorrectionConflict, ...]:
    if (
        isinstance(intent, ManualOrientationIntent)
        and intent.operation == "assign"
        and intent.orientation_label == "Unresolvable"
        and intent.reason_code is None
    ):
        return (DomainCorrectionConflict(
            "blocked",
            "reason_required",
            "Unresolvable orientation requires a reason code.",
            intent.source_ids,
        ),)
    return ()


def _network_qc_conflicts(
    frame: M6FrameGate,
    intent: ManualOrientationIntent | ManualDomainIntent,
    frozen_source_ids: tuple[str, ...],
    projection: EffectiveDomainProjection,
) -> tuple[DomainCorrectionConflict, ...]:
    evidence = frame.native_evidence
    if (
        not isinstance(intent, ManualDomainIntent)
        or intent.operation not in {"create", "move", "restore"}
        or not isinstance(evidence, M3M6LatticeNetworkEvidence)
    ):
        return ()
    affected = set(frozen_source_ids)
    if intent.manual_domain_id is not None:
        affected.update(
            molecule.source_id
            for molecule in projection.molecules
            if molecule.physical_frame_id == intent.physical_frame_id
            and molecule.effective_domain_id == intent.manual_domain_id
        )
    source_domains = {
        domain_id
        for source_id, domain_id in evidence.point_domain_ids
        if source_id in affected and domain_id is not None
    }
    qc_flags = sorted({
        flag
        for domain in evidence.domains
        if domain.lattice_domain_id in source_domains
        for flag in domain.qc_flags
    })
    warnings = []
    if len(source_domains) > 1:
        warnings.append("the batch crosses native network domains")
    if qc_flags:
        warnings.append("native QC: " + ", ".join(qc_flags))
    if not warnings:
        return ()
    return (DomainCorrectionConflict(
        "confirmation_required",
        "manual_domain_qc_warning",
        "Manual-domain QC warning: " + "; ".join(warnings) + ".",
        tuple(sorted(affected)),
    ),)


def _impact_conflicts(
    workspace: DomainCorrectionWorkspace,
    intent: ManualOrientationIntent | ManualDomainIntent,
    effects: tuple[DomainCorrectionEffect, ...],
    changed_source_ids: tuple[str, ...],
    projection: EffectiveDomainProjection,
) -> tuple[DomainCorrectionConflict, ...]:
    return (
        *_batch_impact_conflicts(intent, effects, changed_source_ids),
        *_membership_impact_conflicts(
            workspace,
            intent,
            effects,
            changed_source_ids,
            projection,
        ),
        *_manual_orientation_conflicts(
            workspace,
            intent,
            changed_source_ids,
        ),
    )


def _batch_impact_conflicts(
    intent: ManualOrientationIntent | ManualDomainIntent,
    effects: tuple[DomainCorrectionEffect, ...],
    changed_source_ids: tuple[str, ...],
) -> tuple[DomainCorrectionConflict, ...]:
    conflicts = []
    if isinstance(intent, ManualDomainIntent) and intent.operation in {"create", "delete"}:
        conflicts.append(DomainCorrectionConflict(
            "confirmation_required",
            f"domain_{intent.operation}",
            f"Manual domain {intent.operation} is a high-impact change.",
            changed_source_ids,
        ))
    if len({
        value.source_group for value in effects if value.source_id in changed_source_ids
    }) > 1:
        conflicts.append(DomainCorrectionConflict(
            "confirmation_required",
            "multiple_source_groups",
            "The batch spans multiple source groups.",
            changed_source_ids,
        ))
    if len(changed_source_ids) >= 5:
        conflicts.append(DomainCorrectionConflict(
            "confirmation_required",
            "large_batch",
            "Five or more molecules will change.",
            changed_source_ids,
        ))
    return tuple(conflicts)


def _membership_impact_conflicts(
    workspace: DomainCorrectionWorkspace,
    intent: ManualOrientationIntent | ManualDomainIntent,
    effects: tuple[DomainCorrectionEffect, ...],
    changed_source_ids: tuple[str, ...],
    projection: EffectiveDomainProjection,
) -> tuple[DomainCorrectionConflict, ...]:
    if not isinstance(intent, ManualDomainIntent):
        return ()
    conflicts = []
    if intent.operation == "move":
        transfers = tuple(
            value.source_id
            for value in effects
            if value.source_id in changed_source_ids
            and value.before_value not in {
                "outside",
                "small_ordered_island",
                intent.manual_domain_id,
            }
        )
        if transfers:
            conflicts.append(DomainCorrectionConflict(
                "confirmation_required",
                "membership_transfer",
                "Molecules will move between M6 domains.",
                transfers,
            ))
    if intent.operation == "move":
        boundary_sources = tuple(
            value.source_id
            for value in effects
            if value.source_id in changed_source_ids
            and value.before_value not in {
                "outside",
                "small_ordered_island",
                intent.manual_domain_id,
            }
            and projection.molecule(
                intent.physical_frame_id,
                value.source_id,
            ).is_boundary is True
        )
        if boundary_sources and intent.boundary_resolution is None:
            conflicts.append(DomainCorrectionConflict(
                "blocked",
                "boundary_resolution_required",
                "Moving boundary molecules between domains requires an explicit "
                "preserve or clear choice.",
                boundary_sources,
            ))
    emptied = _emptied_manual_domain_members(workspace, intent, changed_source_ids)
    if emptied:
        conflicts.append(DomainCorrectionConflict(
            "confirmation_required",
            "manual_domain_tombstone",
            "The change will leave a manual domain as a tombstone.",
            emptied,
        ))
    lost_automatic = _lost_automatic_orientation(
        intent,
        changed_source_ids,
        projection,
    )
    if lost_automatic:
        conflicts.append(DomainCorrectionConflict(
            "confirmation_required",
            "automatic_orientation_lost",
            "Changing M6 membership removes a compatible automatic orientation.",
            lost_automatic,
        ))
    return tuple(conflicts)


def _manual_orientation_conflicts(
    workspace: DomainCorrectionWorkspace,
    intent: ManualOrientationIntent | ManualDomainIntent,
    changed_source_ids: tuple[str, ...],
) -> tuple[DomainCorrectionConflict, ...]:
    if not isinstance(intent, ManualOrientationIntent):
        return ()
    manual_keys = {
        DetectionIdentity(
            physical_frame_id=value.physical_frame_id,
            source_id=value.source_id,
        )
        for value in workspace.orientation_decisions
    }
    replaced_manual = tuple(
        source_id
        for source_id in changed_source_ids
        if DetectionIdentity(
            physical_frame_id=intent.physical_frame_id,
            source_id=source_id,
        ) in manual_keys
    )
    if replaced_manual:
        return (DomainCorrectionConflict(
            "confirmation_required",
            "manual_decision_replaced",
            "An earlier manual orientation decision will be replaced.",
            replaced_manual,
        ),)
    return ()


def _emptied_manual_domain_members(
    workspace: DomainCorrectionWorkspace,
    intent: ManualOrientationIntent | ManualDomainIntent,
    changed_source_ids: tuple[str, ...],
) -> tuple[str, ...]:
    if not isinstance(intent, ManualDomainIntent) or intent.operation not in {
        "create",
        "move",
    }:
        return ()
    moved = set(changed_source_ids)
    return tuple(sorted({
        source_id
        for domain in workspace.manual_domains
        if not domain.is_deleted
        and domain.manual_domain_id != intent.manual_domain_id
        and set(domain.source_ids).issubset(moved)
        for source_id in domain.source_ids
    }))


def _lost_automatic_orientation(
    intent: ManualOrientationIntent | ManualDomainIntent,
    changed_source_ids: tuple[str, ...],
    projection: EffectiveDomainProjection,
) -> tuple[str, ...]:
    if not isinstance(intent, ManualDomainIntent) or intent.operation not in {
        "create",
        "move",
    }:
        return ()
    changed = set(changed_source_ids)
    return tuple(
        molecule.source_id
        for molecule in projection.molecules
        if molecule.physical_frame_id == intent.physical_frame_id
        and molecule.source_id in changed
        and molecule.effective_orientation_source == "automatic"
        and molecule.effective_domain_id != intent.manual_domain_id
    )


def _information_conflicts(
    intent: ManualOrientationIntent | ManualDomainIntent,
    effects: tuple[DomainCorrectionEffect, ...],
    changed_source_ids: tuple[str, ...],
) -> tuple[DomainCorrectionConflict, ...]:
    conflicts = []
    no_ops = tuple(
        value.source_id for value in effects if value.source_id not in changed_source_ids
    )
    if no_ops:
        conflicts.append(DomainCorrectionConflict(
            "informational",
            "no_op",
            "Some selected molecules already have the requested value.",
            no_ops,
        ))
    changed = tuple(
        value.source_id for value in effects if value.source_id in changed_source_ids
    )
    if changed:
        conflicts.append(DomainCorrectionConflict(
            "informational",
            "automatic_override",
            "The preserved automatic result remains available for audit.",
            changed,
        ))
    outside = tuple(
        value.source_id
        for value in effects
        if isinstance(intent, ManualOrientationIntent)
        and value.source_group in {"outside", "small_ordered_island"}
    )
    if outside:
        conflicts.append(DomainCorrectionConflict(
            "informational",
            "orientation_only",
            "Orientation changes without changing M6 membership.",
            outside,
        ))
    return tuple(conflicts)


def _combined_conflicts(
    conflicts: tuple[DomainCorrectionConflict, ...],
) -> tuple[DomainCorrectionConflict, ...]:
    grouped: dict[
        tuple[DomainCorrectionConflictSeverity, str, str],
        set[str],
    ] = defaultdict(set)
    for conflict in conflicts:
        grouped[(conflict.severity, conflict.code, conflict.message)].update(
            conflict.source_ids
        )
    severity_order: dict[DomainCorrectionConflictSeverity, int] = {
        "blocked": 0,
        "confirmation_required": 1,
        "informational": 2,
    }
    return tuple(
        DomainCorrectionConflict(severity, code, message, tuple(sorted(source_ids)))
        for (severity, code, message), source_ids in sorted(
            grouped.items(),
            key=lambda value: (severity_order[value[0][0]], value[0][1]),
        )
    )


__all__ = ["compatible_automatic_orientation", "prepared_correction_report"]
