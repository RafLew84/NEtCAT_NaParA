from __future__ import annotations

from typing import Any

from moltrack.analysis.domain_analysis import (
    ClassifierFrameResultProvenance,
    ClassifierIdentity,
    ClassifierOutcome,
    DomainLabelSummary,
    M6FrameGate,
    MoleculeClassification,
)

from .domain_analysis_classifier_payload import (
    classifier_configuration_to_payload,
)
from .domain_analysis_export_schema import (
    DomainAnalysisExportSettings,
    exported_frame_identity,
)
from .package_io import csv_json_cell


def classifier_export_tables(
    outcomes: tuple[ClassifierOutcome, ...] | None,
    settings: DomainAnalysisExportSettings,
) -> dict[str, list[dict[str, Any]]]:
    """Serialize frozen classifier outcomes without running classifiers again."""

    tables: dict[str, list[dict[str, Any]]] = {
        "domain_analysis_molecule_classifications.csv": [],
        "domain_analysis_domain_classifications.csv": [],
        "domain_analysis_classifier_outcomes.csv": [],
    }
    for outcome in outcomes or ():
        tables["domain_analysis_classifier_outcomes.csv"].append(
            _outcome_row(outcome, settings)
        )
        if outcome.status != "completed":
            continue
        tables["domain_analysis_molecule_classifications.csv"].extend(
            _molecule_row(value, settings)
            for value in outcome.molecule_classifications
            if value.m6_partition == "full_domain"
        )
        tables["domain_analysis_domain_classifications.csv"].extend(
            _domain_row(value, settings)
            for value in outcome.domain_summaries
        )
    return tables


def classifier_outcomes_manifest(
    outcomes: tuple[ClassifierOutcome, ...] | None,
    frames: tuple[M6FrameGate, ...],
    settings: DomainAnalysisExportSettings,
) -> list[dict[str, Any]]:
    return [
        {
            "classifier_id": outcome.classifier_id,
            "status": outcome.status,
            "configuration": classifier_configuration_to_payload(
                outcome.configuration
            ),
            "classifier_result_fingerprint": (
                outcome.classifier_result_fingerprint
            ),
            "frame_outcomes": _frame_outcomes(outcome, frames, settings),
            "failure": _failure_manifest(outcome, frames, settings),
        }
        for outcome in outcomes or ()
    ]


def _molecule_row(
    value: MoleculeClassification,
    settings: DomainAnalysisExportSettings,
) -> dict[str, Any]:
    identity = value.identity
    return {
        **_frame_identity(value, settings),
        **_classifier_identity_fields(identity),
        "lattice_domain_id": value.lattice_domain_id,
        "source_id": value.source_id,
        "classification_status": value.classification_status,
        "orientation_label": value.orientation_label,
        "evidence_strength": value.evidence_strength,
        "component_id": value.component_id,
        "m6_gate_fingerprint": value.m6_gate_fingerprint,
    }


def _domain_row(
    value: DomainLabelSummary,
    settings: DomainAnalysisExportSettings,
) -> dict[str, Any]:
    configuration = value.configuration
    identity = configuration.identity
    return {
        **_frame_identity(value, settings),
        **_classifier_identity_fields(identity),
        "lattice_domain_id": value.lattice_domain_id,
        "label": value.label,
        "molecule_count": value.molecule_count,
        "counts": csv_json_cell(value.counts),
        "evidence_fraction_of_domain": csv_json_cell(
            value.evidence_fraction_of_domain
        ),
        "coherent_evidence_fraction_of_domain": csv_json_cell(
            value.coherent_evidence_fraction_of_domain
        ),
        "resolved_fraction": value.resolved_fraction,
        "resolved_evidence_fraction_of_domain": (
            value.resolved_evidence_fraction_of_domain
        ),
        "dominant_class": value.dominant_class,
        "dominance_margin": value.dominance_margin,
        "reason": value.reason,
        "m6_gate_fingerprint": value.m6_gate_fingerprint,
        "aggregation_policy_version": configuration.aggregation_preset.preset_id,
    }


def _outcome_row(
    outcome: ClassifierOutcome,
    settings: DomainAnalysisExportSettings,
) -> dict[str, Any]:
    configuration = outcome.configuration
    identity = configuration.identity
    frame_index = outcome.failure_frame_index
    return {
        **_classifier_identity_fields(identity),
        "status": outcome.status,
        "aggregation_policy_version": configuration.aggregation_preset.preset_id,
        "result_fingerprint": outcome.classifier_result_fingerprint,
        "failure_physical_frame_id": (
            None if frame_index is None else settings.physical_frame_ids[frame_index]
        ),
        "failure_frame_index": frame_index,
        "failure_source_frame_index": (
            None if frame_index is None else settings.source_frame_indices[frame_index]
        ),
        "error_message": outcome.error_message,
    }


def _failure_manifest(
    outcome: ClassifierOutcome,
    frames: tuple[M6FrameGate, ...],
    settings: DomainAnalysisExportSettings,
) -> dict[str, Any] | None:
    frame_index = outcome.failure_frame_index
    if frame_index is None:
        return None
    frame = next(value for value in frames if value.frame_index == frame_index)
    return {
        **_frame_identity(frame, settings),
        "error_message": outcome.error_message,
    }


def _frame_outcomes(
    outcome: ClassifierOutcome,
    frames: tuple[M6FrameGate, ...],
    settings: DomainAnalysisExportSettings,
) -> list[dict[str, Any]]:
    if outcome.status == "completed":
        return [
            {
                **_frame_identity(value, settings),
                "status": "completed",
                "cache_key_fingerprint": value.cache_key_fingerprint,
                "frame_result_fingerprint": value.frame_result_fingerprint,
            }
            for value in outcome.frame_result_provenance
        ]
    if outcome.status == "not_run":
        return [
            {**_frame_identity(frame, settings), "status": "not_run"}
            for frame in sorted(frames, key=lambda value: value.physical_frame_id)
        ]
    if outcome.status != "failed":
        return []
    ordered_frames = tuple(sorted(
        frames,
        key=lambda frame: frame.physical_frame_id,
    ))
    failure_index = outcome.failure_frame_index
    failure_position = next(
        index for index, frame in enumerate(ordered_frames)
        if frame.frame_index == failure_index
    )
    return [
        {
            **_frame_identity(frame, settings),
            "status": "failed" if index == failure_position else "not_run",
            **(
                {"error_message": outcome.error_message}
                if index == failure_position else {}
            ),
        }
        for index, frame in enumerate(ordered_frames)
        if index >= failure_position
    ]


def _classifier_identity_fields(
    identity: ClassifierIdentity,
) -> dict[str, str]:
    return {
        "classifier_id": identity.classifier_id,
        "classifier_schema_version": identity.schema_version,
        "classifier_algorithm_version": identity.algorithm_version,
        "classifier_settings_fingerprint": identity.settings_fingerprint,
    }


def _frame_identity(
    value: (
        ClassifierFrameResultProvenance
        | DomainLabelSummary
        | M6FrameGate
        | MoleculeClassification
    ),
    settings: DomainAnalysisExportSettings,
) -> dict[str, Any]:
    return exported_frame_identity(
        value.physical_frame_id,
        value.frame_index,
        settings.source_frame_indices[value.frame_index],
    )
