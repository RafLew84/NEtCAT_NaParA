from __future__ import annotations

from dataclasses import asdict, dataclass, field
from math import isfinite
from typing import Literal

from .classifier_contract import (
    ClassifierConfiguration,
    ClassifierIdentity,
    DomainLabelSummary,
    validated_finite_pair,
    validated_non_negative_integer,
    validated_text,
    validated_unit_interval,
)
from .events import ClassifierOutcomeStatus
from .fingerprints import canonical_sha256


OrientationLabel = Literal["A", "B", "C", "Unknown orientation"]
MoleculeClassificationStatus = Literal[
    "classified",
    "unknown_orientation",
    "not_gated",
]
M6Partition = Literal["full_domain", "small_ordered_island", "outside"]
OrientationThresholdDecision = Literal["accepted", "rejected"]
OrientationComponentFilterDecision = Literal[
    "accepted", "filtered", "not_evaluated"
]


@dataclass(frozen=True)
class ClassifierMoleculeInput:
    """Canonical detection geometry supplied to one gated classifier call."""

    source_id: str
    raw_centroid_xy: tuple[float, float]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "source_id",
            validated_text(self.source_id, "source_id"),
        )
        object.__setattr__(
            self,
            "raw_centroid_xy",
            validated_finite_pair(self.raw_centroid_xy, "raw_centroid_xy"),
        )


@dataclass(frozen=True)
class ABCOrientationDiagnosticEvidence:
    """Raw A/B/C evidence and the two independent rejection decisions."""

    raw_orientation_label: Literal["A", "B", "C"] | None
    threshold_candidate_label: Literal["A", "B", "C"] | None
    nearest_distance: float | None
    threshold_candidate_distance: float | None
    margin: float | None
    distance_threshold: float | None
    minimum_margin: float
    threshold_decision: OrientationThresholdDecision
    threshold_reason_code: str
    component_filter_decision: OrientationComponentFilterDecision
    component_filter_reason_code: str

    def __post_init__(self) -> None:
        for field_name in (
            "raw_orientation_label",
            "threshold_candidate_label",
        ):
            if getattr(self, field_name) not in {"A", "B", "C", None}:
                raise ValueError(f"Unsupported {field_name}.")
        for field_name in (
            "nearest_distance", "threshold_candidate_distance", "margin",
            "distance_threshold",
        ):
            object.__setattr__(
                self,
                field_name,
                _optional_non_negative_float(getattr(self, field_name), field_name),
            )
        object.__setattr__(
            self,
            "minimum_margin",
            _non_negative_float(self.minimum_margin, "minimum_margin"),
        )
        if self.threshold_decision not in {"accepted", "rejected"}:
            raise ValueError("Unsupported threshold_decision.")
        if self.component_filter_decision not in {
            "accepted", "filtered", "not_evaluated"
        }:
            raise ValueError("Unsupported component_filter_decision.")
        for field_name in (
            "threshold_reason_code", "component_filter_reason_code"
        ):
            object.__setattr__(
                self,
                field_name,
                validated_text(getattr(self, field_name), field_name),
            )
        if self.threshold_decision == "accepted" and (
            self.threshold_candidate_label is None
            or self.component_filter_decision == "not_evaluated"
        ):
            raise ValueError(
                "Accepted threshold evidence must reach the component filter."
            )
        if self.threshold_decision == "rejected" and (
            self.component_filter_decision != "not_evaluated"
        ):
            raise ValueError("Rejected threshold evidence cannot be component-filtered.")


@dataclass(frozen=True)
class ClassifierMoleculePrediction:
    """Adapter-owned A/B/C evidence before result provenance is attached."""

    source_id: str
    orientation_label: Literal["A", "B", "C"] | None
    evidence_strength: float
    component_id: str | None = None
    diagnostic_evidence: ABCOrientationDiagnosticEvidence | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "source_id",
            validated_text(self.source_id, "source_id"),
        )
        if self.orientation_label not in {"A", "B", "C", None}:
            raise ValueError(
                f"Unsupported orientation_label: {self.orientation_label!r}."
            )
        strength = validated_unit_interval(
            self.evidence_strength,
            "evidence_strength",
        )
        component_id = self.component_id
        if self.orientation_label is None:
            if strength != 0.0 or component_id is not None:
                raise ValueError(
                    "Unknown orientation must carry no accepted evidence."
                )
        elif component_id is None or not str(component_id).strip():
            raise ValueError("Classified molecules require a component_id.")
        object.__setattr__(self, "evidence_strength", strength)
        object.__setattr__(
            self,
            "component_id",
            None if component_id is None else str(component_id).strip(),
        )
        diagnostic = self.diagnostic_evidence
        if diagnostic is not None and not isinstance(
            diagnostic, ABCOrientationDiagnosticEvidence
        ):
            raise TypeError(
                "diagnostic_evidence must be ABCOrientationDiagnosticEvidence."
            )
        if diagnostic is not None:
            accepted = (
                diagnostic.threshold_decision == "accepted"
                and diagnostic.component_filter_decision == "accepted"
            )
            if (self.orientation_label is not None) != accepted:
                raise ValueError(
                    "Accepted diagnostic decisions must match the final prediction."
                )


@dataclass(frozen=True)
class MoleculeClassification:
    """One auditable classifier result linked to an M6-gated detection."""

    frame_index: int
    physical_frame_id: str
    m6_gate_fingerprint: str
    lattice_domain_id: str | None
    source_id: str
    m6_partition: M6Partition
    classification_status: MoleculeClassificationStatus
    orientation_label: OrientationLabel | None
    evidence_strength: float
    component_id: str | None
    identity: ClassifierIdentity
    diagnostic_evidence: ABCOrientationDiagnosticEvidence | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "frame_index",
            validated_non_negative_integer(self.frame_index, "frame_index"),
        )
        for field_name in (
            "physical_frame_id",
            "m6_gate_fingerprint",
            "source_id",
        ):
            object.__setattr__(
                self,
                field_name,
                validated_text(getattr(self, field_name), field_name),
            )
        if self.lattice_domain_id is not None:
            object.__setattr__(
                self,
                "lattice_domain_id",
                validated_text(self.lattice_domain_id, "lattice_domain_id"),
            )
        if not isinstance(self.identity, ClassifierIdentity):
            raise TypeError("identity must be ClassifierIdentity.")
        if self.m6_partition not in {
            "full_domain",
            "small_ordered_island",
            "outside",
        }:
            raise ValueError(f"Unsupported m6_partition: {self.m6_partition!r}.")
        if self.classification_status not in {
            "classified",
            "unknown_orientation",
            "not_gated",
        }:
            raise ValueError(
                "Unsupported classification_status: "
                f"{self.classification_status!r}."
            )
        _validate_classification(self)

    @property
    def classifier_id(self) -> str:
        return self.identity.classifier_id

    @property
    def classifier_settings_fingerprint(self) -> str:
        return self.identity.settings_fingerprint

    @property
    def classifier_algorithm_version(self) -> str:
        return self.identity.algorithm_version


@dataclass(frozen=True)
class ClassifierFrameResultProvenance:
    """One ordered frame key and complete frame-result fingerprint."""

    frame_index: int
    physical_frame_id: str
    cache_key_fingerprint: str
    frame_result_fingerprint: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "frame_index",
            validated_non_negative_integer(self.frame_index, "frame_index"),
        )
        for field_name in (
            "physical_frame_id",
            "cache_key_fingerprint",
            "frame_result_fingerprint",
        ):
            object.__setattr__(
                self,
                field_name,
                validated_text(getattr(self, field_name), field_name),
            )


@dataclass(frozen=True)
class ClassifierOutcome:
    """Atomic payload or readable failure for one requested classifier."""

    status: ClassifierOutcomeStatus
    configuration: ClassifierConfiguration
    molecule_classifications: tuple[MoleculeClassification, ...]
    frame_result_provenance: tuple[ClassifierFrameResultProvenance, ...] = ()
    domain_summaries: tuple[DomainLabelSummary, ...] = ()
    error_message: str | None = None
    failure_frame_index: int | None = None
    classifier_result_fingerprint: str | None = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.configuration, ClassifierConfiguration):
            raise TypeError("configuration must be ClassifierConfiguration.")
        if self.status not in {"completed", "canceled", "failed", "not_run"}:
            raise ValueError(f"Unsupported classifier outcome: {self.status!r}.")
        classifications = _validated_classifications(
            self.molecule_classifications,
            self.configuration,
        )
        provenance = _validated_frame_result_provenance(
            self.frame_result_provenance,
            classifications,
        )
        summaries = _validated_domain_summaries(
            self.domain_summaries,
            classifications,
            self.configuration,
        )
        error_message, failure_frame_index = _validated_outcome_error(
            self.status, self.error_message, self.failure_frame_index,
            classifications, summaries, provenance,
        )
        object.__setattr__(self, "molecule_classifications", classifications)
        object.__setattr__(self, "frame_result_provenance", provenance)
        object.__setattr__(self, "domain_summaries", summaries)
        object.__setattr__(self, "error_message", error_message)
        object.__setattr__(self, "failure_frame_index", failure_frame_index)
        object.__setattr__(
            self,
            "classifier_result_fingerprint",
            _classifier_result_fingerprint(self, provenance),
        )

    @property
    def classifier_id(self) -> str:
        return self.configuration.identity.classifier_id

    @property
    def classifier_settings_fingerprint(self) -> str:
        return self.configuration.identity.settings_fingerprint

    @property
    def classifier_algorithm_version(self) -> str:
        return self.configuration.identity.algorithm_version

    @property
    def aggregation_preset_id(self) -> str:
        return self.configuration.aggregation_preset.preset_id

    @property
    def aggregation_preset_fingerprint(self) -> str:
        return self.configuration.aggregation_preset.fingerprint

    @property
    def classifier_configuration_fingerprint(self) -> str:
        return self.configuration.fingerprint


def _validated_outcome_error(
    status: ClassifierOutcomeStatus,
    error_message: str | None,
    failure_frame_index: int | None,
    classifications: tuple[MoleculeClassification, ...],
    summaries: tuple[DomainLabelSummary, ...],
    provenance: tuple[ClassifierFrameResultProvenance, ...],
) -> tuple[str | None, int | None]:
    if status == "completed" and error_message is not None:
        raise ValueError("A completed classifier cannot contain an error.")
    if status in {"canceled", "failed", "not_run"} and (
        classifications or summaries or provenance
    ):
        raise ValueError(
            "An incomplete classifier cannot publish a partial payload."
        )
    if status != "failed" and error_message is not None:
        raise ValueError("Only a failed classifier can contain an error.")
    if status == "completed" and not provenance:
        raise ValueError("A completed classifier requires frame provenance.")
    if status == "failed":
        if failure_frame_index is None:
            raise ValueError("A failed classifier requires a failure frame index.")
        return (
            validated_text(error_message, "error_message"),
            validated_non_negative_integer(
                failure_frame_index,
                "failure_frame_index",
            ),
        )
    if failure_frame_index is not None:
        raise ValueError("Only a failed classifier can identify a failure frame.")
    return None, None


def _validated_classifications(
    values: tuple[MoleculeClassification, ...],
    configuration: ClassifierConfiguration,
) -> tuple[MoleculeClassification, ...]:
    classifications = tuple(values)
    if any(not isinstance(value, MoleculeClassification) for value in classifications):
        raise TypeError(
            "molecule_classifications must contain MoleculeClassification values."
        )
    classifications = tuple(sorted(
        classifications,
        key=lambda value: (value.frame_index, value.source_id),
    ))
    keys = tuple(
        (value.frame_index, value.source_id) for value in classifications
    )
    if len(set(keys)) != len(keys):
        raise ValueError("Molecule classification keys must be unique.")
    if any(
        value.identity != configuration.identity for value in classifications
    ):
        raise ValueError("Molecule classifier identity must match its outcome.")
    return classifications


def _validated_frame_result_provenance(
    values: tuple[ClassifierFrameResultProvenance, ...],
    classifications: tuple[MoleculeClassification, ...],
) -> tuple[ClassifierFrameResultProvenance, ...]:
    provenance = tuple(values)
    if any(
        not isinstance(value, ClassifierFrameResultProvenance)
        for value in provenance
    ):
        raise TypeError(
            "frame_result_provenance must contain provenance values."
        )
    if provenance != tuple(sorted(
        provenance,
        key=lambda value: value.physical_frame_id,
    )):
        raise ValueError("Frame result provenance must use physical-frame order.")
    frame_keys = tuple(
        (value.frame_index, value.physical_frame_id) for value in provenance
    )
    if len(set(frame_keys)) != len(frame_keys):
        raise ValueError("Frame result provenance keys must be unique.")
    if any(
        (value.frame_index, value.physical_frame_id) not in frame_keys
        for value in classifications
    ):
        raise ValueError("Classifier results require matching frame provenance.")
    _validate_frame_result_fingerprints(provenance, classifications)
    return provenance


def _validate_frame_result_fingerprints(
    provenance: tuple[ClassifierFrameResultProvenance, ...],
    classifications: tuple[MoleculeClassification, ...],
) -> None:
    for value in provenance:
        frame_classifications = tuple(
            classification
            for classification in classifications
            if classification.frame_index == value.frame_index
            and classification.physical_frame_id == value.physical_frame_id
        )
        if (
            classifier_frame_result_fingerprint(frame_classifications)
            != value.frame_result_fingerprint
        ):
            raise ValueError(
                "Frame result fingerprint must match classifier results."
            )


def classifier_frame_result_fingerprint(
    classifications: tuple[MoleculeClassification, ...],
) -> str:
    payload = []
    for value in classifications:
        item = asdict(value)
        item.pop("frame_index")
        if item.get("diagnostic_evidence") is None:
            item.pop("diagnostic_evidence")
        payload.append(item)
    return canonical_sha256({
        "schema_version": "domain-analysis-classifier-frame-v1",
        "classifications": payload,
    })


def _classifier_result_fingerprint(
    outcome: ClassifierOutcome,
    provenance: tuple[ClassifierFrameResultProvenance, ...],
) -> str | None:
    if outcome.status != "completed":
        return None
    return canonical_sha256({
        "schema_version": "domain-analysis-classifier-range-v1",
        "classifier_configuration_fingerprint": outcome.configuration.fingerprint,
        "requested_frame_indices": sorted(
            value.frame_index for value in provenance
        ),
        "ordered_frame_results": [
            {
                "frame_index": value.frame_index,
                "physical_frame_id": value.physical_frame_id,
                "cache_key_fingerprint": value.cache_key_fingerprint,
                "frame_result_fingerprint": value.frame_result_fingerprint,
            }
            for value in provenance
        ],
    })


def _validated_domain_summaries(
    summaries: tuple[DomainLabelSummary, ...],
    classifications: tuple[MoleculeClassification, ...],
    configuration: ClassifierConfiguration,
) -> tuple[DomainLabelSummary, ...]:
    values = tuple(summaries)
    if any(not isinstance(value, DomainLabelSummary) for value in values):
        raise TypeError("domain_summaries must contain DomainLabelSummary values.")
    values = tuple(sorted(
        values,
        key=lambda value: (value.frame_index, value.lattice_domain_id),
    ))
    keys = tuple((value.frame_index, value.lattice_domain_id) for value in values)
    if len(set(keys)) != len(keys):
        raise ValueError("Domain summary keys must be unique.")
    if any(value.configuration != configuration for value in values):
        raise ValueError("Domain summary configuration must match its outcome.")
    full_domain_counts: dict[tuple[int, str], int] = {}
    for classification in classifications:
        if classification.m6_partition != "full_domain":
            continue
        if classification.lattice_domain_id is None:
            raise ValueError("Full-domain classifications require a domain ID.")
        key = (classification.frame_index, classification.lattice_domain_id)
        full_domain_counts[key] = full_domain_counts.get(key, 0) + 1
    if set(keys) != set(full_domain_counts):
        raise ValueError("Domain summaries must cover exactly the full M6 domains.")
    if any(
        value.molecule_count
        != full_domain_counts[(value.frame_index, value.lattice_domain_id)]
        for value in values
    ):
        raise ValueError("Domain summary denominators must match gated molecules.")
    return values


def _validate_classification(value: MoleculeClassification) -> None:
    strength = validated_unit_interval(
        value.evidence_strength,
        "evidence_strength",
    )
    component_id = value.component_id
    diagnostic = value.diagnostic_evidence
    if diagnostic is not None and not isinstance(
        diagnostic, ABCOrientationDiagnosticEvidence
    ):
        raise TypeError(
            "diagnostic_evidence must be ABCOrientationDiagnosticEvidence."
        )
    if value.classification_status == "classified":
        if (
            value.m6_partition != "full_domain"
            or value.lattice_domain_id is None
            or value.orientation_label not in {"A", "B", "C"}
            or component_id is None
        ):
            raise ValueError("A classified molecule requires full-domain evidence.")
    elif value.classification_status == "unknown_orientation":
        if (
            value.m6_partition != "full_domain"
            or value.lattice_domain_id is None
            or value.orientation_label != "Unknown orientation"
            or strength != 0.0
            or component_id is not None
        ):
            raise ValueError("Unknown orientation must remain inside a full domain.")
    else:
        island_link_is_invalid = (
            value.m6_partition == "small_ordered_island"
            and value.lattice_domain_id is None
        )
        outside_link_is_invalid = (
            value.m6_partition == "outside"
            and value.lattice_domain_id is not None
        )
        if (
            value.m6_partition == "full_domain"
            or island_link_is_invalid
            or outside_link_is_invalid
            or value.orientation_label is not None
            or strength != 0.0
            or component_id is not None
            or diagnostic is not None
        ):
            raise ValueError("Not-gated molecules cannot carry classifier evidence.")
    object.__setattr__(value, "evidence_strength", strength)
    object.__setattr__(
        value,
        "component_id",
        (
            None
            if component_id is None
            else validated_text(component_id, "component_id")
        ),
    )


def _optional_non_negative_float(value: object, field_name: str) -> float | None:
    if value is None:
        return None
    return _non_negative_float(value, field_name)


def _non_negative_float(value: object, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field_name} must be numeric.")
    normalized = float(value)
    if not isfinite(normalized) or normalized < 0.0:
        raise ValueError(f"{field_name} must be finite and non-negative.")
    return normalized
