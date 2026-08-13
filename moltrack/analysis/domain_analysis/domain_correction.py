from __future__ import annotations

from collections import defaultdict
from dataclasses import replace

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
from .fingerprints import canonical_sha256
from .models import DomainAnalysisResult, M6FrameGate
from .texture_abc_adapter import ABC_ORIENTATION_CLASSIFIER_ID


class DomainCorrectionModule:
    """Prepare orientation corrections and derive one effective projection."""

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
        intent: ManualOrientationIntent,
    ) -> PreparedDomainCorrection:
        _validate_workspace_anchor(workspace, automatic)
        if not isinstance(intent, ManualOrientationIntent):
            raise TypeError("intent must be a ManualOrientationIntent.")
        frame = _frame(automatic, intent.physical_frame_id)
        available = set(frame.analyzed_source_ids)
        missing = tuple(value for value in intent.source_ids if value not in available)
        if missing:
            raise ValueError(f"Unknown source_ids for correction: {missing!r}.")
        decisions = _decision_index(workspace)
        changed = tuple(
            source_id
            for source_id in intent.source_ids
            if _decision_would_change(decisions, intent, source_id)
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
        decisions = _decision_index(workspace)
        intent = preview.intent
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
        classifications = _classification_index(automatic)
        assert automatic.m6_gate is not None
        molecules = tuple(
            _project_molecule(frame, source_id, classifications, decisions)
            for frame in automatic.m6_gate.frames
            for source_id in frame.analyzed_source_ids
        )
        return EffectiveDomainProjection(
            automatic_result=automatic,
            correction_revision=workspace.revision,
            molecules=molecules,
            orientation_subdomains=_orientation_subdomains(molecules),
        )


def _project_molecule(
    frame: M6FrameGate,
    source_id: str,
    classifications: dict[tuple[str, str], MoleculeClassification],
    decisions: dict[tuple[str, str], ManualOrientationDecision],
) -> EffectiveMoleculeOrientation:
    key = (frame.physical_frame_id, source_id)
    classification = classifications.get(key)
    decision = decisions.get(key)
    partition, domain_id = _membership(frame, source_id)
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
    )


def _membership(frame: M6FrameGate, source_id: str) -> tuple[str, str | None]:
    for component in frame.full_domains + frame.small_ordered_islands:
        if source_id in component.source_ids:
            return component.component_type, component.lattice_domain_id
    return "outside", None


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
