from __future__ import annotations

from typing import Literal, cast

import numpy as np

from moltrack.analysis.texture_domain_analysis import (
    TEXTURE_DOMAIN_ANALYSIS_ALGORITHM_VERSION,
    TEXTURE_DOMAIN_UNKNOWN_CLASS_KEY,
    TTMAPP_TEXTURE_DOMAIN_PRESET,
    TextureDomainAnalysisSettings,
    TextureDomainPointInput,
    TextureDomainPointResult,
    analyze_texture_domain_frame,
)

from .classifier_models import (
    ABCOrientationDiagnosticEvidence,
    ClassifierMoleculeInput,
    ClassifierMoleculePrediction,
)
from .classifier_contract import (
    ABC_DOMAIN_SUMMARY_CONSERVATIVE_V1,
    DomainAggregationPreset,
)


ABC_ORIENTATION_CLASSIFIER_ID = "abc_orientation"
ABC_ORIENTATION_CLASSIFIER_SCHEMA_VERSION = "m6-gated-abc-classifier-v1"


class TextureABCClassifierAdapter:
    """Adapt the existing raw texture backend to M6-gated A/B/C evidence."""

    classifier_id = ABC_ORIENTATION_CLASSIFIER_ID
    classifier_schema_version = ABC_ORIENTATION_CLASSIFIER_SCHEMA_VERSION
    classifier_algorithm_version = TEXTURE_DOMAIN_ANALYSIS_ALGORITHM_VERSION

    def __init__(
        self,
        settings: TextureDomainAnalysisSettings = TTMAPP_TEXTURE_DOMAIN_PRESET,
        aggregation_preset: DomainAggregationPreset = (
            ABC_DOMAIN_SUMMARY_CONSERVATIVE_V1
        ),
    ) -> None:
        if not isinstance(settings, TextureDomainAnalysisSettings):
            raise TypeError("settings must be TextureDomainAnalysisSettings.")
        if not isinstance(aggregation_preset, DomainAggregationPreset):
            raise TypeError("aggregation_preset must be DomainAggregationPreset.")
        self._settings = settings
        self._aggregation_preset = aggregation_preset

    @property
    def classifier_settings_fingerprint(self) -> str:
        return self._settings.fingerprint

    @property
    def domain_aggregation_preset(self) -> DomainAggregationPreset:
        return self._aggregation_preset

    def classify_domain(
        self,
        raw_frame: np.ndarray,
        *,
        frame_index: int,
        physical_frame_id: str,
        lattice_domain_id: str,
        molecules: tuple[ClassifierMoleculeInput, ...],
    ) -> tuple[ClassifierMoleculePrediction, ...]:
        del physical_frame_id, lattice_domain_id
        points = tuple(
            TextureDomainPointInput(
                source_id=value.source_id,
                x_px=value.raw_centroid_xy[0],
                y_px=value.raw_centroid_xy[1],
            )
            for value in molecules
        )
        result = analyze_texture_domain_frame(
            frame_index=frame_index,
            source_view="raw",
            frame=raw_frame,
            points=points,
            settings=self._settings,
        )
        label_by_key = {
            value.key: value.short_label for value in self._settings.classes
        }
        threshold_by_key = {
            value.key: self._settings.distance_thresholds[index]
            for index, value in enumerate(self._settings.classes)
        }
        return tuple(
            _prediction(
                value,
                label_by_key,
                threshold_by_key,
                minimum_margin=self._settings.minimum_margin,
            )
            for value in result.points
        )


def _prediction(
    value: TextureDomainPointResult,
    label_by_key: dict[str, str],
    threshold_by_key: dict[str, float],
    *,
    minimum_margin: float,
) -> ClassifierMoleculePrediction:
    raw_label = _orientation_label(value.nearest_class_key, label_by_key)
    final_label = _orientation_label(value.class_key, label_by_key)
    threshold_label = _orientation_label(
        value.threshold_candidate_class_key,
        label_by_key,
    )
    threshold_key = value.threshold_candidate_class_key
    distance_threshold = (
        None
        if threshold_key == TEXTURE_DOMAIN_UNKNOWN_CLASS_KEY
        else threshold_by_key[threshold_key]
    )
    threshold_reason = value.threshold_reason
    threshold_accepted = threshold_reason == "accepted_result"
    component_accepted = final_label is not None
    diagnostic = ABCOrientationDiagnosticEvidence(
        raw_orientation_label=raw_label,
        threshold_candidate_label=threshold_label,
        nearest_distance=value.nearest_distance,
        threshold_candidate_distance=value.threshold_candidate_distance,
        margin=value.margin,
        distance_threshold=distance_threshold,
        minimum_margin=minimum_margin,
        threshold_decision="accepted" if threshold_accepted else "rejected",
        threshold_reason_code=threshold_reason,
        component_filter_decision=(
            "accepted"
            if component_accepted
            else "filtered"
            if threshold_accepted
            else "not_evaluated"
        ),
        component_filter_reason_code=(
            "accepted_result"
            if component_accepted
            else "component_below_minimum_size"
            if threshold_accepted
            else "upstream_threshold_rejected"
        ),
    )
    if value.class_key == TEXTURE_DOMAIN_UNKNOWN_CLASS_KEY:
        return ClassifierMoleculePrediction(
            source_id=value.source_id,
            orientation_label=None,
            evidence_strength=0.0,
            component_id=None,
            diagnostic_evidence=diagnostic,
        )
    label = label_by_key[value.class_key]
    if label not in {"A", "B", "C"}:
        raise ValueError(f"Unsupported A/B/C preset label: {label!r}.")
    distance = value.threshold_candidate_distance
    if distance is None:
        raise ValueError("A classified texture point requires a distance.")
    threshold = threshold_by_key[value.class_key]
    evidence = (
        float(distance <= 0.0)
        if threshold <= 0.0
        else max(0.0, min(1.0, 1.0 - distance / threshold))
    )
    return ClassifierMoleculePrediction(
        source_id=value.source_id,
        orientation_label=cast(Literal["A", "B", "C"], label),
        evidence_strength=evidence,
        component_id=value.component_id,
        diagnostic_evidence=diagnostic,
    )


def _orientation_label(
    class_key: str,
    label_by_key: dict[str, str],
) -> Literal["A", "B", "C"] | None:
    if class_key == TEXTURE_DOMAIN_UNKNOWN_CLASS_KEY:
        return None
    label = label_by_key[class_key]
    if label not in {"A", "B", "C"}:
        raise ValueError(f"Unsupported A/B/C preset label: {label!r}.")
    return cast(Literal["A", "B", "C"], label)
