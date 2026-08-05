from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Literal

from .domain_label_models import (
    DomainLabelSummary,
    classifier_configuration_fingerprint,
)


OrientationLabel = Literal["A", "B", "C", "Unknown orientation"]
MoleculeClassificationStatus = Literal[
    "classified",
    "unknown_orientation",
    "not_gated",
]
ClassifierOutcomeStatus = Literal["completed", "failed"]
M6Partition = Literal["full_domain", "small_ordered_island", "outside"]


@dataclass(frozen=True)
class ClassifierIdentity:
    """Versioned classifier identity copied into every published record."""

    classifier_id: str
    settings_fingerprint: str
    algorithm_version: str

    def __post_init__(self) -> None:
        for field_name in (
            "classifier_id",
            "settings_fingerprint",
            "algorithm_version",
        ):
            object.__setattr__(
                self,
                field_name,
                _text(getattr(self, field_name), field_name),
            )


@dataclass(frozen=True)
class ClassifierMoleculeInput:
    """Canonical detection geometry supplied to one gated classifier call."""

    source_id: str
    raw_centroid_xy: tuple[float, float]

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_id", _text(self.source_id, "source_id"))
        object.__setattr__(
            self,
            "raw_centroid_xy",
            _finite_pair(self.raw_centroid_xy, "raw_centroid_xy"),
        )


@dataclass(frozen=True)
class ClassifierMoleculePrediction:
    """Adapter-owned A/B/C evidence before result provenance is attached."""

    source_id: str
    orientation_label: Literal["A", "B", "C"] | None
    evidence_strength: float
    component_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_id", _text(self.source_id, "source_id"))
        if self.orientation_label not in {"A", "B", "C", None}:
            raise ValueError(
                f"Unsupported orientation_label: {self.orientation_label!r}."
            )
        strength = _evidence_strength(self.evidence_strength)
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
    classifier_id: str
    classifier_settings_fingerprint: str
    classifier_algorithm_version: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "frame_index",
            _frame_index(self.frame_index),
        )
        for field_name in (
            "physical_frame_id",
            "m6_gate_fingerprint",
            "source_id",
            "classifier_id",
            "classifier_settings_fingerprint",
            "classifier_algorithm_version",
        ):
            object.__setattr__(
                self,
                field_name,
                _text(getattr(self, field_name), field_name),
            )
        if self.lattice_domain_id is not None:
            object.__setattr__(
                self,
                "lattice_domain_id",
                _text(self.lattice_domain_id, "lattice_domain_id"),
            )
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


@dataclass(frozen=True)
class ClassifierOutcome:
    """Atomic payload or readable failure for one requested classifier."""

    classifier_id: str
    status: ClassifierOutcomeStatus
    classifier_settings_fingerprint: str
    classifier_algorithm_version: str
    aggregation_preset_id: str
    aggregation_preset_fingerprint: str
    classifier_configuration_fingerprint: str
    molecule_classifications: tuple[MoleculeClassification, ...]
    domain_summaries: tuple[DomainLabelSummary, ...] = ()
    error_message: str | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "classifier_id",
            "classifier_settings_fingerprint",
            "classifier_algorithm_version",
            "aggregation_preset_id",
            "aggregation_preset_fingerprint",
            "classifier_configuration_fingerprint",
        ):
            object.__setattr__(
                self,
                field_name,
                _text(getattr(self, field_name), field_name),
            )
        expected_configuration_fingerprint = classifier_configuration_fingerprint(
            classifier_id=self.classifier_id,
            classifier_settings_fingerprint=self.classifier_settings_fingerprint,
            classifier_algorithm_version=self.classifier_algorithm_version,
            aggregation_preset_id=self.aggregation_preset_id,
            aggregation_preset_fingerprint=self.aggregation_preset_fingerprint,
        )
        if self.classifier_configuration_fingerprint != (
            expected_configuration_fingerprint
        ):
            raise ValueError("Classifier configuration fingerprint does not match.")
        if self.status not in {"completed", "failed"}:
            raise ValueError(f"Unsupported classifier outcome: {self.status!r}.")
        values = tuple(self.molecule_classifications)
        if any(not isinstance(value, MoleculeClassification) for value in values):
            raise TypeError(
                "molecule_classifications must contain MoleculeClassification values."
            )
        values = tuple(sorted(
            values,
            key=lambda value: (value.frame_index, value.source_id),
        ))
        keys = tuple((value.frame_index, value.source_id) for value in values)
        if len(set(keys)) != len(keys):
            raise ValueError("Molecule classification keys must be unique.")
        if any(value.classifier_id != self.classifier_id for value in values):
            raise ValueError("Molecule classifier IDs must match their outcome.")
        summaries = _validated_domain_summaries(
            self.domain_summaries,
            values,
            ClassifierIdentity(
                classifier_id=self.classifier_id,
                settings_fingerprint=self.classifier_settings_fingerprint,
                algorithm_version=self.classifier_algorithm_version,
            ),
            self.aggregation_preset_id,
            self.aggregation_preset_fingerprint,
        )
        if self.status == "completed" and self.error_message is not None:
            raise ValueError("A completed classifier cannot contain an error.")
        if self.status == "failed":
            if values or summaries:
                raise ValueError("A failed classifier cannot publish a partial payload.")
            object.__setattr__(
                self,
                "error_message",
                _text(self.error_message, "error_message"),
            )
        object.__setattr__(self, "molecule_classifications", values)
        object.__setattr__(self, "domain_summaries", summaries)


def _validated_domain_summaries(
    summaries: tuple[DomainLabelSummary, ...],
    classifications: tuple[MoleculeClassification, ...],
    identity: ClassifierIdentity,
    aggregation_preset_id: str,
    aggregation_preset_fingerprint: str,
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
    for value in values:
        if (
            value.classifier_id != identity.classifier_id
            or value.classifier_settings_fingerprint != identity.settings_fingerprint
            or value.classifier_algorithm_version != identity.algorithm_version
            or value.aggregation_preset_id != aggregation_preset_id
            or value.aggregation_preset_fingerprint
            != aggregation_preset_fingerprint
        ):
            raise ValueError("Domain summary configuration must match its outcome.")
    preset_versions = {
        (value.aggregation_preset_id, value.aggregation_preset_fingerprint)
        for value in values
    }
    if len(preset_versions) > 1:
        raise ValueError("One classifier outcome requires one aggregation preset.")
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
    strength = _evidence_strength(value.evidence_strength)
    component_id = value.component_id
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
        ):
            raise ValueError("Not-gated molecules cannot carry classifier evidence.")
    object.__setattr__(value, "evidence_strength", strength)
    object.__setattr__(
        value,
        "component_id",
        None if component_id is None else _text(component_id, "component_id"),
    )


def _evidence_strength(value: float) -> float:
    normalized = float(value)
    if not isfinite(normalized) or not 0.0 <= normalized <= 1.0:
        raise ValueError("evidence_strength must lie between 0 and 1.")
    return normalized


def _finite_pair(value: tuple[float, float], name: str) -> tuple[float, float]:
    pair = tuple(float(item) for item in value)
    if len(pair) != 2 or not all(isfinite(item) for item in pair):
        raise ValueError(f"{name} must be a finite pair.")
    return pair


def _frame_index(value: int) -> int:
    if isinstance(value, bool) or int(value) != value or int(value) < 0:
        raise ValueError("frame_index must be a non-negative integer.")
    return int(value)


def _text(value: str | None, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string.")
    return value.strip()
