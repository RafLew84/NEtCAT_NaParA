from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar


@dataclass(frozen=True)
class OrientationDescriptorEvidence:
    evidence_kind: ClassVar[str] = "abc_orientation_descriptor_v1"
    raw_centroid_x: float | None
    raw_centroid_y: float | None
    classifier_id: str


@dataclass(frozen=True)
class RawOrientationEvidence:
    evidence_kind: ClassVar[str] = "abc_raw_prediction_v1"
    raw_orientation_label: str | None
    nearest_distance: float | None
    margin: float | None


@dataclass(frozen=True)
class OrientationThresholdEvidence:
    evidence_kind: ClassVar[str] = "abc_threshold_decision_v1"
    candidate_label: str | None
    candidate_distance: float | None
    distance_threshold: float | None
    margin: float | None
    minimum_margin: float


@dataclass(frozen=True)
class OrientationComponentFilterEvidence:
    evidence_kind: ClassVar[str] = "abc_component_filter_v1"
    component_id: str | None
    orientation_label: str | None


@dataclass(frozen=True)
class AutomaticOrientationEvidence:
    evidence_kind: ClassVar[str] = "automatic_orientation_result_v1"
    classification_status: str
    orientation_label: str | None
    evidence_strength: float
    component_id: str | None
    raw_orientation_label: str | None


@dataclass(frozen=True)
class ManualOrientationDecisionEvidence:
    evidence_kind: ClassVar[str] = "manual_orientation_decision_v1"
    orientation_label: str | None
    operator_id: str


@dataclass(frozen=True)
class EffectiveOrientationEvidence:
    evidence_kind: ClassVar[str] = "effective_orientation_result_v1"
    source: str
    orientation_label: str | None
    classification_status: str
