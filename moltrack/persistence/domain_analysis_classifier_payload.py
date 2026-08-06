from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Callable, cast

from moltrack.analysis.domain_analysis.classifier_contract import (
    ABC_DOMAIN_SUMMARY_CONSERVATIVE_V1,
    ClassifierConfiguration,
    ClassifierIdentity,
    DomainAggregationPreset,
    DomainLabelSummary,
)
from moltrack.analysis.domain_analysis.session_state import (
    DomainAnalysisSessionDiagnostic,
)
from moltrack.analysis.domain_analysis.classifier_models import (
    ClassifierFrameResultProvenance,
    ClassifierOutcome,
    MoleculeClassification,
)

from .domain_analysis_payload_validation import (
    integer_field,
    list_field,
    list_value,
    mapping,
    number_field,
    optional_integer_field,
    optional_text_field,
    required,
    text_field,
)


def classifier_outcomes_to_payload(
    outcomes: tuple[ClassifierOutcome, ...] | None,
) -> list[dict[str, Any]] | None:
    if outcomes is None:
        return None
    return [_outcome_to_payload(value) for value in outcomes]


def classifier_outcomes_from_payload(
    payload: Any,
    *,
    path: str,
    requested_classifier_ids: tuple[str, ...],
    fallback_configurations: tuple[ClassifierConfiguration, ...] = (),
    failure_frame_index: int = 0,
    validate_outcome: Callable[[ClassifierOutcome], None] | None = None,
) -> tuple[
    tuple[ClassifierOutcome, ...] | None,
    tuple[DomainAnalysisSessionDiagnostic, ...],
]:
    values = [] if payload is None else list_value(payload, path)
    fallback_by_id = {
        value.identity.classifier_id: value
        for value in fallback_configurations
    }
    outcomes: list[ClassifierOutcome] = []
    diagnostics: list[DomainAnalysisSessionDiagnostic] = []
    for index, classifier_id in enumerate(requested_classifier_ids):
        item_path = f"{path}[{index}]"
        value = values[index] if index < len(values) else None
        try:
            if value is None:
                raise ValueError(f"{item_path} is missing.")
            outcome = _outcome_from_payload(value, path=item_path)
            if outcome.classifier_id != classifier_id:
                raise ValueError(
                    f"{item_path} does not match requested classifier "
                    f"{classifier_id!r}."
                )
            if validate_outcome is not None:
                validate_outcome(outcome)
        except (TypeError, ValueError) as exc:
            configuration = _recovered_configuration(
                value,
                classifier_id=classifier_id,
                fallback=fallback_by_id.get(classifier_id),
                path=item_path,
            )
            outcome = ClassifierOutcome(
                status="failed",
                configuration=configuration,
                molecule_classifications=(),
                error_message=f"Stored classifier outcome rejected: {exc}",
                failure_frame_index=failure_frame_index,
            )
            diagnostics.append(DomainAnalysisSessionDiagnostic(
                component="classifier_outcome",
                identifier=classifier_id,
                schema_version=configuration.identity.schema_version,
                reason=str(exc),
            ))
        outcomes.append(outcome)
    for index in range(len(requested_classifier_ids), len(values)):
        item_path = f"{path}[{index}]"
        diagnostics.append(DomainAnalysisSessionDiagnostic(
            component="classifier_outcome",
            identifier=item_path,
            schema_version="unknown",
            reason="Outcome was not requested and was skipped.",
        ))
    return (
        None if not requested_classifier_ids else tuple(outcomes),
        tuple(diagnostics),
    )


def _recovered_configuration(
    payload: Any,
    *,
    classifier_id: str,
    fallback: ClassifierConfiguration | None,
    path: str,
) -> ClassifierConfiguration:
    if fallback is not None:
        return fallback
    try:
        saved = mapping(payload, path)
        configuration = classifier_configuration_from_payload(
            required(saved, "configuration", path),
            path=f"{path}.configuration",
        )
        if configuration.identity.classifier_id == classifier_id:
            return configuration
    except (TypeError, ValueError):
        pass
    return ClassifierConfiguration(
        identity=ClassifierIdentity(
            classifier_id=classifier_id,
            schema_version="unavailable",
            settings_fingerprint="rejected-session-payload",
            algorithm_version="rejected-session-payload",
        ),
        aggregation_preset=ABC_DOMAIN_SUMMARY_CONSERVATIVE_V1,
    )


def classifier_configuration_to_payload(
    configuration: ClassifierConfiguration,
) -> dict[str, Any]:
    identity = configuration.identity
    preset = configuration.aggregation_preset
    return {
        "identity": {
            "classifier_id": identity.classifier_id,
            "schema_version": identity.schema_version,
            "settings_fingerprint": identity.settings_fingerprint,
            "algorithm_version": identity.algorithm_version,
        },
        "aggregation_preset": {
            **preset.as_dict(),
            "fingerprint": preset.fingerprint,
        },
        "fingerprint": configuration.fingerprint,
    }


def classifier_configuration_from_payload(
    payload: Any,
    *,
    path: str,
) -> ClassifierConfiguration:
    saved = mapping(payload, path)
    identity_payload = mapping(required(saved, "identity", path), f"{path}.identity")
    preset_path = f"{path}.aggregation_preset"
    preset_payload = mapping(
        required(saved, "aggregation_preset", path),
        preset_path,
    )
    preset = DomainAggregationPreset(
        preset_id=text_field(preset_payload, "preset_id", preset_path),
        minimum_resolved_evidence=number_field(
            preset_payload, "minimum_resolved_evidence", preset_path
        ),
        minimum_dominant_evidence=number_field(
            preset_payload, "minimum_dominant_evidence", preset_path
        ),
        minimum_dominance_margin=number_field(
            preset_payload, "minimum_dominance_margin", preset_path
        ),
        minimum_dominant_coherent_evidence=number_field(
            preset_payload,
            "minimum_dominant_coherent_evidence",
            preset_path,
        ),
        minimum_mixed_class_evidence=number_field(
            preset_payload, "minimum_mixed_class_evidence", preset_path
        ),
        minimum_mixed_coherent_evidence=number_field(
            preset_payload,
            "minimum_mixed_coherent_evidence",
            preset_path,
        ),
    )
    if preset.fingerprint != text_field(preset_payload, "fingerprint", preset_path):
        raise ValueError(f"{preset_path}.fingerprint does not match its preset.")
    configuration = ClassifierConfiguration(
        identity=ClassifierIdentity(
            classifier_id=text_field(
                identity_payload, "classifier_id", f"{path}.identity"
            ),
            schema_version=text_field(
                identity_payload, "schema_version", f"{path}.identity"
            ),
            settings_fingerprint=text_field(
                identity_payload,
                "settings_fingerprint",
                f"{path}.identity",
            ),
            algorithm_version=text_field(
                identity_payload, "algorithm_version", f"{path}.identity"
            ),
        ),
        aggregation_preset=preset,
    )
    if configuration.fingerprint != text_field(saved, "fingerprint", path):
        raise ValueError(f"{path}.fingerprint does not match its configuration.")
    return configuration


def molecule_classification_to_payload(
    value: MoleculeClassification,
) -> dict[str, Any]:
    return {
        "frame_index": value.frame_index,
        "physical_frame_id": value.physical_frame_id,
        "m6_gate_fingerprint": value.m6_gate_fingerprint,
        "lattice_domain_id": value.lattice_domain_id,
        "source_id": value.source_id,
        "m6_partition": value.m6_partition,
        "classification_status": value.classification_status,
        "orientation_label": value.orientation_label,
        "evidence_strength": value.evidence_strength,
        "component_id": value.component_id,
    }


def molecule_classification_from_payload(
    payload: Any,
    configuration: ClassifierConfiguration,
    *,
    path: str,
) -> MoleculeClassification:
    saved = mapping(payload, path)
    return MoleculeClassification(
        frame_index=integer_field(saved, "frame_index", path),
        physical_frame_id=text_field(saved, "physical_frame_id", path),
        m6_gate_fingerprint=text_field(saved, "m6_gate_fingerprint", path),
        lattice_domain_id=optional_text_field(saved, "lattice_domain_id", path),
        source_id=text_field(saved, "source_id", path),
        m6_partition=cast(Any, text_field(saved, "m6_partition", path)),
        classification_status=cast(
            Any,
            text_field(saved, "classification_status", path),
        ),
        orientation_label=cast(
            Any,
            optional_text_field(saved, "orientation_label", path),
        ),
        evidence_strength=number_field(saved, "evidence_strength", path),
        component_id=optional_text_field(saved, "component_id", path),
        identity=configuration.identity,
    )


def _outcome_to_payload(outcome: ClassifierOutcome) -> dict[str, Any]:
    return {
        "status": outcome.status,
        "configuration": classifier_configuration_to_payload(
            outcome.configuration
        ),
        "molecule_classifications": [
            molecule_classification_to_payload(value)
            for value in outcome.molecule_classifications
        ],
        "frame_result_provenance": [
            {
                "frame_index": value.frame_index,
                "physical_frame_id": value.physical_frame_id,
                "cache_key_fingerprint": value.cache_key_fingerprint,
                "frame_result_fingerprint": value.frame_result_fingerprint,
            }
            for value in outcome.frame_result_provenance
        ],
        "domain_summaries": [
            _domain_summary_to_payload(value)
            for value in outcome.domain_summaries
        ],
        "error_message": outcome.error_message,
        "failure_frame_index": outcome.failure_frame_index,
        "classifier_result_fingerprint": outcome.classifier_result_fingerprint,
    }


def _outcome_from_payload(payload: Any, *, path: str) -> ClassifierOutcome:
    saved = mapping(payload, path)
    configuration = classifier_configuration_from_payload(
        required(saved, "configuration", path),
        path=f"{path}.configuration",
    )
    classifications = tuple(
        molecule_classification_from_payload(
            value,
            configuration,
            path=f"{path}.molecule_classifications[{index}]",
        )
        for index, value in enumerate(
            list_field(saved, "molecule_classifications", path)
        )
    )
    provenance = tuple(
        _frame_provenance_from_payload(
            value,
            path=f"{path}.frame_result_provenance[{index}]",
        )
        for index, value in enumerate(
            list_field(saved, "frame_result_provenance", path)
        )
    )
    summaries = tuple(
        _domain_summary_from_payload(
            value,
            configuration,
            path=f"{path}.domain_summaries[{index}]",
        )
        for index, value in enumerate(list_field(saved, "domain_summaries", path))
    )
    outcome = ClassifierOutcome(
        status=cast(Any, text_field(saved, "status", path)),
        configuration=configuration,
        molecule_classifications=classifications,
        frame_result_provenance=provenance,
        domain_summaries=summaries,
        error_message=optional_text_field(saved, "error_message", path),
        failure_frame_index=optional_integer_field(
            saved, "failure_frame_index", path
        ),
    )
    if outcome.classifier_result_fingerprint != required(
        saved,
        "classifier_result_fingerprint",
        path,
    ):
        raise ValueError(
            f"{path}.classifier_result_fingerprint does not match its outcome."
        )
    return outcome


def _frame_provenance_from_payload(
    payload: Any,
    *,
    path: str,
) -> ClassifierFrameResultProvenance:
    saved = mapping(payload, path)
    return ClassifierFrameResultProvenance(
        frame_index=integer_field(saved, "frame_index", path),
        physical_frame_id=text_field(saved, "physical_frame_id", path),
        cache_key_fingerprint=text_field(saved, "cache_key_fingerprint", path),
        frame_result_fingerprint=text_field(
            saved, "frame_result_fingerprint", path
        ),
    )


def _domain_summary_to_payload(value: DomainLabelSummary) -> dict[str, Any]:
    return {
        "frame_index": value.frame_index,
        "physical_frame_id": value.physical_frame_id,
        "m6_gate_fingerprint": value.m6_gate_fingerprint,
        "lattice_domain_id": value.lattice_domain_id,
        "label": value.label,
        "molecule_count": value.molecule_count,
        "counts": [list(item) for item in value.counts],
        "evidence_fraction_of_domain": [
            list(item) for item in value.evidence_fraction_of_domain
        ],
        "coherent_evidence_fraction_of_domain": [
            list(item) for item in value.coherent_evidence_fraction_of_domain
        ],
        "resolved_fraction": value.resolved_fraction,
        "resolved_evidence_fraction_of_domain": (
            value.resolved_evidence_fraction_of_domain
        ),
        "dominant_class": value.dominant_class,
        "dominance_margin": value.dominance_margin,
        "reason": value.reason,
    }


def _domain_summary_from_payload(
    payload: Any,
    configuration: ClassifierConfiguration,
    *,
    path: str,
) -> DomainLabelSummary:
    saved = mapping(payload, path)
    return DomainLabelSummary(
        frame_index=integer_field(saved, "frame_index", path),
        physical_frame_id=text_field(saved, "physical_frame_id", path),
        m6_gate_fingerprint=text_field(saved, "m6_gate_fingerprint", path),
        lattice_domain_id=text_field(saved, "lattice_domain_id", path),
        label=cast(Any, text_field(saved, "label", path)),
        molecule_count=integer_field(saved, "molecule_count", path),
        counts=_integer_label_pairs(saved, "counts", path),
        evidence_fraction_of_domain=_float_label_pairs(
            saved, "evidence_fraction_of_domain", path
        ),
        coherent_evidence_fraction_of_domain=_float_label_pairs(
            saved, "coherent_evidence_fraction_of_domain", path
        ),
        resolved_fraction=number_field(saved, "resolved_fraction", path),
        resolved_evidence_fraction_of_domain=number_field(
            saved, "resolved_evidence_fraction_of_domain", path
        ),
        dominant_class=cast(
            Any,
            optional_text_field(saved, "dominant_class", path),
        ),
        dominance_margin=number_field(saved, "dominance_margin", path),
        reason=cast(Any, text_field(saved, "reason", path)),
        configuration=configuration,
    )


def _integer_label_pairs(
    payload: Mapping[str, Any],
    field_name: str,
    path: str,
) -> tuple[tuple[str, int], ...]:
    pairs = list_field(payload, field_name, path)
    if any(
        not isinstance(value, list)
        or len(value) != 2
        or not isinstance(value[0], str)
        or isinstance(value[1], bool)
        or not isinstance(value[1], int)
        for value in pairs
    ):
        raise ValueError(f"{path}.{field_name} must contain text/integer pairs.")
    return tuple((value[0], value[1]) for value in pairs)


def _float_label_pairs(
    payload: Mapping[str, Any],
    field_name: str,
    path: str,
) -> tuple[tuple[str, float], ...]:
    pairs = list_field(payload, field_name, path)
    if any(
        not isinstance(value, list)
        or len(value) != 2
        or not isinstance(value[0], str)
        or isinstance(value[1], bool)
        or not isinstance(value[1], (int, float))
        for value in pairs
    ):
        raise ValueError(f"{path}.{field_name} must contain text/numeric pairs.")
    return tuple((value[0], float(value[1])) for value in pairs)
