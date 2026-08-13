from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
from collections.abc import Callable
from uuid import uuid4

from .classifier_models import MoleculeClassification
from .domain_correction_models import (
    ApplyPreparedDomainCorrection,
    DomainCorrectionWorkspace,
    EffectiveDomainProjection,
    EffectiveMoleculeOrientation,
    EffectiveOrientationSubdomain,
    EffectiveOrientationSource,
    ManualOrientationDecision,
    ManualOrientationIntent,
    PreparedDomainCorrection,
)
from .manual_domain_models import ManualDomainIntent, ManualDomainRecord
from .manual_domain_projection import (
    active_manual_memberships,
    project_effective_domains,
    source_footprints_for_frame,
)
from .fingerprints import canonical_sha256
from .models import DomainAnalysisResult, M6FrameGate
from .network_backend_evidence import M3M6LatticeNetworkEvidence
from .texture_abc_adapter import ABC_ORIENTATION_CLASSIFIER_ID


class DomainCorrectionModule:
    """Prepare orientation corrections and derive one effective projection."""

    def __init__(
        self,
        manual_domain_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._manual_domain_id_factory = manual_domain_id_factory or (
            lambda: str(uuid4())
        )

    def initialize(
        self,
        automatic: DomainAnalysisResult,
    ) -> DomainCorrectionWorkspace:
        _validate_automatic(automatic)
        return DomainCorrectionWorkspace(
            automatic_fingerprint=_automatic_fingerprint(automatic),
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
        if isinstance(intent, ManualDomainIntent):
            intent = _prepared_manual_domain_intent(
                workspace,
                intent,
                self._manual_domain_id_factory,
                tuple(
                    value.lattice_domain_id
                    for value in frame.full_domains + frame.small_ordered_islands
                ),
            )
        available = set(frame.analyzed_source_ids)
        missing = tuple(value for value in intent.source_ids if value not in available)
        if missing:
            raise ValueError(f"Unknown source_ids for correction: {missing!r}.")
        if isinstance(intent, ManualDomainIntent):
            prospective = replace(
                workspace,
                manual_domains=_apply_manual_domain_intent(workspace, intent),
            )
            self.project(automatic, prospective)
        changed = (
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
        return PreparedDomainCorrection(
            expected_revision=workspace.revision,
            automatic_fingerprint=workspace.automatic_fingerprint,
            intent=intent,
            changed_source_ids=changed,
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
        intent = preview.intent
        if isinstance(intent, ManualDomainIntent):
            return replace(
                workspace,
                revision=workspace.revision + 1,
                manual_domains=_apply_manual_domain_intent(workspace, intent),
            )
        decisions = _decision_index(workspace)
        for source_id in intent.source_ids:
            key = (intent.physical_frame_id, source_id)
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
        return replace(
            workspace,
            revision=workspace.revision + 1,
            orientation_decisions=tuple(decisions[key] for key in sorted(decisions)),
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
            (domain.physical_frame_id, source_id)
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
        molecules = tuple(
            _project_molecule(
                frame,
                source_id,
                classifications,
                decisions,
                manual_memberships,
                (frame.physical_frame_id, source_id) in tombstoned_sources,
                _effective_boundary_role(
                    boundary_ids[frame.physical_frame_id],
                    source_id,
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
    classifications: dict[tuple[str, str], MoleculeClassification],
    decisions: dict[tuple[str, str], ManualOrientationDecision],
    manual_memberships: dict[tuple[str, str], str],
    is_tombstoned_member: bool,
    automatic_boundary: bool | None,
    footprint_pixels_xy: tuple[tuple[int, int], ...] | None,
) -> EffectiveMoleculeOrientation:
    key = (frame.physical_frame_id, source_id)
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
    automatic_label = _compatible_automatic_label(frame, classification, domain_id)
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
) -> bool | None:
    return (
        None
        if boundary_source_ids is None
        else source_id in boundary_source_ids
    )


def _compatible_automatic_label(
    frame: M6FrameGate,
    classification: MoleculeClassification | None,
    effective_domain_id: str | None,
) -> str | None:
    if (
        classification is None
        or classification.m6_gate_fingerprint != frame.m6_gate_fingerprint
        or classification.physical_frame_id != frame.physical_frame_id
        or classification.m6_partition != "full_domain"
        or classification.lattice_domain_id != effective_domain_id
    ):
        return None
    return classification.orientation_label


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
) -> dict[tuple[str, str], MoleculeClassification]:
    return {
        (classification.physical_frame_id, classification.source_id): classification
        for outcome in automatic.classifier_outcomes or ()
        if outcome.classifier_id == ABC_ORIENTATION_CLASSIFIER_ID
        for classification in outcome.molecule_classifications
    }


def _decision_index(
    workspace: DomainCorrectionWorkspace,
) -> dict[tuple[str, str], ManualOrientationDecision]:
    return {
        (value.physical_frame_id, value.source_id): value
        for value in workspace.orientation_decisions
    }


def _decision_would_change(
    decisions: dict[tuple[str, str], ManualOrientationDecision],
    intent: ManualOrientationIntent,
    source_id: str,
) -> bool:
    current = decisions.get((intent.physical_frame_id, source_id))
    if intent.operation == "reset":
        return current is not None
    return current != ManualOrientationDecision(
        intent.physical_frame_id,
        source_id,
        intent.orientation_label or "",
        intent.reason_code,
    )


def _prepared_manual_domain_intent(
    workspace: DomainCorrectionWorkspace,
    intent: ManualDomainIntent,
    id_factory: Callable[[], str],
    automatic_domain_ids: tuple[str, ...],
) -> ManualDomainIntent:
    domain_ids = {value.manual_domain_id for value in workspace.manual_domains}
    if intent.operation == "create":
        domain_id = intent.manual_domain_id or id_factory()
        if (
            domain_id in domain_ids
            or domain_id in automatic_domain_ids
        ):
            raise ValueError("Manual domain ID already exists.")
        return ManualDomainIntent(
            physical_frame_id=intent.physical_frame_id,
            operation="create",
            source_ids=intent.source_ids,
            manual_domain_id=domain_id,
        )
    assert intent.manual_domain_id is not None
    key = (intent.physical_frame_id, intent.manual_domain_id)
    record = _manual_domain_index(workspace).get(key)
    if record is None:
        raise ValueError("Manual domain does not exist in this frame.")
    if intent.operation == "move" and record.is_deleted:
        raise ValueError("Cannot move molecules into a deleted manual domain.")
    if intent.operation == "delete" and record.is_deleted:
        raise ValueError("Manual domain is already deleted.")
    if intent.operation == "restore" and not record.is_deleted:
        raise ValueError("Only a manual-domain tombstone can be restored.")
    return intent


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
            if memberships.get((intent.physical_frame_id, source_id))
            != intent.manual_domain_id
        )
    record = _manual_domain_index(workspace)[
        (intent.physical_frame_id, intent.manual_domain_id or "")
    ]
    return record.source_ids if intent.operation == "delete" else record.restore_source_ids


def _apply_manual_domain_intent(
    workspace: DomainCorrectionWorkspace,
    intent: ManualDomainIntent,
) -> tuple[ManualDomainRecord, ...]:
    domains = _manual_domain_index(workspace)
    domain_id = intent.manual_domain_id
    assert domain_id is not None
    key = (intent.physical_frame_id, domain_id)
    if intent.operation == "create":
        domains = _remove_sources_from_manual_domains(
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
        domains = _remove_sources_from_manual_domains(
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
        domains = _remove_sources_from_manual_domains(
            domains,
            intent.physical_frame_id,
            current.restore_source_ids,
            except_domain_id=domain_id,
        )
        domains[key] = replace(
            current,
            source_ids=current.restore_source_ids,
            is_deleted=False,
        )
    return tuple(domains[value] for value in sorted(domains))


def _remove_sources_from_manual_domains(
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
    if workspace.automatic_fingerprint != _automatic_fingerprint(automatic):
        raise ValueError("Domain Correction Workspace automatic anchor is stale.")


def _automatic_fingerprint(automatic: DomainAnalysisResult) -> str:
    assert automatic.m6_gate is not None
    return canonical_sha256({
        "schema_version": "domain-correction-automatic-anchor-v1",
        "m6_frames": [
            (frame.physical_frame_id, frame.m6_gate_fingerprint)
            for frame in automatic.m6_gate.frames
        ],
        "classifiers": [
            (outcome.classifier_id, outcome.classifier_result_fingerprint)
            for outcome in automatic.classifier_outcomes or ()
        ],
    })


__all__ = ["DomainCorrectionModule"]
