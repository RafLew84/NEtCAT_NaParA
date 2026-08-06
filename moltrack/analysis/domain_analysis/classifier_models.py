from __future__ import annotations

from dataclasses import dataclass
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


OrientationLabel = Literal["A", "B", "C", "Unknown orientation"]
MoleculeClassificationStatus = Literal[
    "classified",
    "unknown_orientation",
    "not_gated",
]
ClassifierOutcomeStatus = Literal["completed", "failed"]
M6Partition = Literal["full_domain", "small_ordered_island", "outside"]


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
class ClassifierMoleculePrediction:
    """Adapter-owned A/B/C evidence before result provenance is attached."""

    source_id: str
    orientation_label: Literal["A", "B", "C"] | None
    evidence_strength: float
    component_id: str | None = None

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
class ClassifierOutcome:
    """Atomic payload or readable failure for one requested classifier."""

    status: ClassifierOutcomeStatus
    configuration: ClassifierConfiguration
    molecule_classifications: tuple[MoleculeClassification, ...]
    domain_summaries: tuple[DomainLabelSummary, ...] = ()
    error_message: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.configuration, ClassifierConfiguration):
            raise TypeError("configuration must be ClassifierConfiguration.")
        if self.status not in {"completed", "failed"}:
            raise ValueError(f"Unsupported classifier outcome: {self.status!r}.")
        classifications = _validated_classifications(
            self.molecule_classifications,
            self.configuration,
        )
        summaries = _validated_domain_summaries(
            self.domain_summaries,
            classifications,
            self.configuration,
        )
        if self.status == "completed" and self.error_message is not None:
            raise ValueError("A completed classifier cannot contain an error.")
        if self.status == "failed":
            if classifications or summaries:
                raise ValueError("A failed classifier cannot publish a partial payload.")
            object.__setattr__(
                self,
                "error_message",
                validated_text(self.error_message, "error_message"),
            )
        object.__setattr__(self, "molecule_classifications", classifications)
        object.__setattr__(self, "domain_summaries", summaries)

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
        (
            None
            if component_id is None
            else validated_text(component_id, "component_id")
        ),
    )
