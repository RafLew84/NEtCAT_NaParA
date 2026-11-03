from __future__ import annotations

from .classifier_models import (
    ABCOrientationDiagnosticEvidence,
    ClassifierOutcome,
    MoleculeClassification,
)
from .diagnostic_funnel_builders import (
    completed_diagnostic_stage,
    failed_diagnostic_stage,
    not_run_diagnostic_stage,
    raw_centroid_values,
    unavailable_diagnostic_stage,
)
from .diagnostic_funnel_models import (
    AutomaticOrientationEvidence,
    DiagnosticDecision,
    DiagnosticEvidence,
    DiagnosticProvenanceContext,
    DiagnosticReason,
    DiagnosticReasonCategory,
    DiagnosticStageResult,
    EffectiveOrientationEvidence,
    MoleculeDiagnosticStageId,
    OrientationComponentFilterEvidence,
    OrientationDescriptorEvidence,
    OrientationThresholdEvidence,
    RawOrientationEvidence,
)
from .geometry import M6PublishedMolecule
from .models import M6ComponentType, M6FrameGate


def classic_orientation_stages(
    frame: M6FrameGate,
    molecule: M6PublishedMolecule,
    partition: M6ComponentType | str,
    classification: MoleculeClassification | None,
    outcome: ClassifierOutcome | None,
) -> list[DiagnosticStageResult]:
    if partition != "full_domain":
        return [
            not_run_diagnostic_stage(stage_id, "m6_gate_not_eligible")
            for stage_id in (
                "orientation_descriptor",
                "orientation_raw",
                "orientation_threshold",
                "orientation_component_filter",
                "automatic_result",
            )
        ]
    if classification is None:
        return _unpublished_orientation_stages(frame, outcome)
    diagnostic = classification.diagnostic_evidence
    raw_centroid_x, raw_centroid_y = raw_centroid_values(molecule)
    descriptor = completed_diagnostic_stage(
        frame, "orientation_descriptor", "accepted",
        reason=DiagnosticReason("accepted", "accepted_result"),
        evidence=DiagnosticEvidence(OrientationDescriptorEvidence(
            raw_centroid_x, raw_centroid_y, classification.classifier_id
        )),
        provenance=_classifier_provenance(
            classification, "texture_orientation_descriptor"
        ),
    )
    if diagnostic is None:
        return [
            descriptor,
            unavailable_diagnostic_stage(
                "orientation_raw", "evidence_not_retained"
            ),
            unavailable_diagnostic_stage(
                "orientation_threshold", "evidence_not_retained"
            ),
            unavailable_diagnostic_stage(
                "orientation_component_filter", "evidence_not_retained"
            ),
            _automatic_result_stage(frame, classification, None),
        ]
    raw_decision: DiagnosticDecision = (
        "accepted" if diagnostic.raw_orientation_label is not None else "ambiguous"
    )
    raw = completed_diagnostic_stage(
        frame, "orientation_raw", raw_decision,
        reason=DiagnosticReason(
            "accepted" if raw_decision == "accepted" else "insufficient_evidence",
            "accepted_result" if raw_decision == "accepted" else (
                "insufficient_descriptor_evidence"
            ),
        ),
        evidence=DiagnosticEvidence(RawOrientationEvidence(
            diagnostic.raw_orientation_label,
            diagnostic.nearest_distance,
            diagnostic.margin,
        )),
        provenance=_classifier_provenance(
            classification, "analyze_texture_domain_frame"
        ),
    )
    return [
        descriptor,
        raw,
        _threshold_stage(frame, classification, diagnostic),
        _component_filter_stage(frame, classification, diagnostic),
        _automatic_result_stage(frame, classification, diagnostic),
    ]


def classic_effective_result_stage(
    frame: M6FrameGate,
    partition: M6ComponentType | str,
    classification: MoleculeClassification | None,
    outcome: ClassifierOutcome | None,
) -> DiagnosticStageResult:
    if partition != "full_domain":
        return not_run_diagnostic_stage(
            "effective_result",
            "automatic_not_gated_and_no_manual_decision",
        )
    if classification is None:
        suffix = "not_requested" if outcome is None else outcome.status
        return not_run_diagnostic_stage(
            "effective_result", f"automatic_classifier_{suffix}"
        )
    classified = classification.classification_status == "classified"
    return completed_diagnostic_stage(
        frame, "effective_result", "accepted" if classified else "ambiguous",
        reason=DiagnosticReason(
            "accepted" if classified else "insufficient_evidence",
            "automatic_result_used",
        ),
        evidence=DiagnosticEvidence(EffectiveOrientationEvidence(
            "automatic", classification.orientation_label,
            classification.classification_status,
        )),
        provenance=_classifier_provenance(
            classification, "effective_orientation_projection"
        ),
    )


def abc_classifier_outcome(
    outcomes: tuple[ClassifierOutcome, ...] | None,
) -> ClassifierOutcome | None:
    for outcome in outcomes or ():
        if outcome.classifier_id == "abc_orientation":
            return outcome
    return None


def _unpublished_orientation_stages(
    frame: M6FrameGate,
    outcome: ClassifierOutcome | None,
) -> list[DiagnosticStageResult]:
    stage_ids: tuple[MoleculeDiagnosticStageId, ...] = (
        "orientation_descriptor",
        "orientation_raw",
        "orientation_threshold",
        "orientation_component_filter",
        "automatic_result",
    )
    if outcome is None:
        return [
            not_run_diagnostic_stage(stage_id, "not_requested")
            for stage_id in stage_ids
        ]
    if outcome.status == "failed":
        if outcome.failure_frame_index != frame.frame_index:
            return [
                unavailable_diagnostic_stage(
                    stage_id, "atomic_classifier_payload_discarded"
                )
                for stage_id in stage_ids
            ]
        return [
            failed_diagnostic_stage(
                "orientation_descriptor",
                "classifier_failed",
                native_code=outcome.error_message,
            ),
            *[
                not_run_diagnostic_stage(
                    stage_id, "upstream_classifier_failed"
                )
                for stage_id in stage_ids[1:]
            ],
        ]
    reason = (
        "classifier_canceled"
        if outcome.status == "canceled"
        else "classifier_not_run"
        if outcome.status == "not_run"
        else "classifier_result_missing"
    )
    stage = (
        unavailable_diagnostic_stage
        if outcome.status == "completed"
        else not_run_diagnostic_stage
    )
    return [stage(stage_id, reason) for stage_id in stage_ids]


def _threshold_stage(
    frame: M6FrameGate,
    classification: MoleculeClassification,
    diagnostic: ABCOrientationDiagnosticEvidence,
) -> DiagnosticStageResult:
    accepted = diagnostic.threshold_decision == "accepted"
    category: DiagnosticReasonCategory = (
        "accepted"
        if accepted
        else "insufficient_evidence"
        if diagnostic.threshold_reason_code == "insufficient_descriptor_evidence"
        else "threshold"
    )
    return completed_diagnostic_stage(
        frame, "orientation_threshold", "accepted" if accepted else "rejected",
        reason=DiagnosticReason(category, diagnostic.threshold_reason_code),
        evidence=DiagnosticEvidence(OrientationThresholdEvidence(
            diagnostic.threshold_candidate_label,
            diagnostic.threshold_candidate_distance,
            diagnostic.distance_threshold,
            diagnostic.margin,
            diagnostic.minimum_margin,
        )),
        provenance=_classifier_provenance(
            classification, "apply_orientation_thresholds"
        ),
    )


def _component_filter_stage(
    frame: M6FrameGate,
    classification: MoleculeClassification,
    diagnostic: ABCOrientationDiagnosticEvidence,
) -> DiagnosticStageResult:
    decision = diagnostic.component_filter_decision
    if decision == "not_evaluated":
        return not_run_diagnostic_stage(
            "orientation_component_filter",
            diagnostic.component_filter_reason_code,
        )
    return completed_diagnostic_stage(
        frame, "orientation_component_filter", decision,
        reason=DiagnosticReason(
            "accepted" if decision == "accepted" else "postprocess",
            diagnostic.component_filter_reason_code,
        ),
        evidence=DiagnosticEvidence(OrientationComponentFilterEvidence(
            classification.component_id, classification.orientation_label
        )),
        provenance=_classifier_provenance(
            classification, "filter_orientation_components"
        ),
    )


def _automatic_result_stage(
    frame: M6FrameGate,
    classification: MoleculeClassification,
    diagnostic: ABCOrientationDiagnosticEvidence | None,
) -> DiagnosticStageResult:
    classified = classification.classification_status == "classified"
    return completed_diagnostic_stage(
        frame, "automatic_result", "accepted" if classified else "ambiguous",
        reason=DiagnosticReason(
            "accepted" if classified else "insufficient_evidence",
            "accepted_result" if classified else "unknown_orientation",
        ),
        evidence=DiagnosticEvidence(AutomaticOrientationEvidence(
            classification.classification_status,
            classification.orientation_label,
            classification.evidence_strength,
            classification.component_id,
            (
                None if diagnostic is None else diagnostic.raw_orientation_label
            ),
        )),
        provenance=_classifier_provenance(
            classification, "domain_analysis_classifier_runner"
        ),
    )


def _classifier_provenance(
    classification: MoleculeClassification,
    producer: str,
) -> DiagnosticProvenanceContext:
    return DiagnosticProvenanceContext(
        producer=producer,
        algorithm_version=classification.classifier_algorithm_version,
        settings_fingerprint=classification.classifier_settings_fingerprint,
        input_fingerprint=classification.m6_gate_fingerprint,
    )
