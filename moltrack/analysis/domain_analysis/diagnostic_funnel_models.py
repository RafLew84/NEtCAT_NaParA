from __future__ import annotations

from dataclasses import asdict, dataclass
from math import isfinite
from typing import Literal, TypeAlias

from .backend_contract import DomainBackendIdentity
from .diagnostic_m6_evidence import (
    CentroidEvidence,
    DomainPartitionEvidence,
    DomainSizeEvidence,
    FirstShellEvidence,
    LocalOrderEvidence,
    SampleCoordinatesEvidence,
    SeedGrowthEvidence,
    SourceInputEvidence,
)
from .diagnostic_orientation_evidence import (
    AutomaticOrientationEvidence,
    EffectiveOrientationEvidence,
    ManualOrientationDecisionEvidence,
    OrientationComponentFilterEvidence,
    OrientationDescriptorEvidence,
    OrientationThresholdEvidence,
    RawOrientationEvidence,
)
from .diagnostic_network_evidence import (
    NetworkDomainEdgesEvidence,
    NetworkDomainPartitionEvidence,
    NetworkDomainSizeEvidence,
    NetworkFirstShellEvidence,
    NetworkLocalOrderEvidence,
    NetworkLocalSymmetryEvidence,
    NetworkSeedGrowthEvidence,
)


MoleculeDiagnosticStageId = Literal[
    "source_input",
    "centroid",
    "sample_coordinates",
    "first_shell",
    "local_order",
    "local_symmetry",
    "domain_edges",
    "seed_growth",
    "domain_partition",
    "domain_size",
    "orientation_descriptor",
    "orientation_raw",
    "orientation_threshold",
    "orientation_component_filter",
    "automatic_result",
    "manual_correction",
    "effective_result",
]
DiagnosticExecutionStatus = Literal[
    "completed", "not_run", "unavailable", "failed"
]
DiagnosticDecision = Literal[
    "accepted", "rejected", "ambiguous", "filtered", "not_evaluated"
]
DiagnosticReasonCategory = Literal[
    "accepted",
    "not_run",
    "missing_data",
    "threshold",
    "insufficient_evidence",
    "conflict",
    "postprocess",
    "manual_override",
    "execution_error",
]
DiagnosticEvidenceScalar: TypeAlias = str | int | float | bool | None
DiagnosticEvidenceValue: TypeAlias = (
    DiagnosticEvidenceScalar | tuple[DiagnosticEvidenceScalar, ...]
)


DiagnosticEvidencePayload: TypeAlias = (
    SourceInputEvidence
    | CentroidEvidence
    | SampleCoordinatesEvidence
    | FirstShellEvidence
    | LocalOrderEvidence
    | SeedGrowthEvidence
    | DomainPartitionEvidence
    | DomainSizeEvidence
    | OrientationDescriptorEvidence
    | RawOrientationEvidence
    | OrientationThresholdEvidence
    | OrientationComponentFilterEvidence
    | AutomaticOrientationEvidence
    | ManualOrientationDecisionEvidence
    | EffectiveOrientationEvidence
    | NetworkFirstShellEvidence
    | NetworkLocalOrderEvidence
    | NetworkLocalSymmetryEvidence
    | NetworkDomainEdgesEvidence
    | NetworkSeedGrowthEvidence
    | NetworkDomainPartitionEvidence
    | NetworkDomainSizeEvidence
)


_STAGE_DEFINITIONS: tuple[
    tuple[
        MoleculeDiagnosticStageId,
        str,
        type[DiagnosticEvidencePayload]
        | tuple[type[DiagnosticEvidencePayload], ...]
        | None,
    ],
    ...,
] = (
    ("source_input", "Detection / segmentation", SourceInputEvidence),
    ("centroid", "Source centroid", CentroidEvidence),
    ("sample_coordinates", "Sample coordinates", SampleCoordinatesEvidence),
    ("first_shell", "First shell", (FirstShellEvidence, NetworkFirstShellEvidence)),
    ("local_order", "Local M3/M6", (LocalOrderEvidence, NetworkLocalOrderEvidence)),
    ("local_symmetry", "Local symmetry model", NetworkLocalSymmetryEvidence),
    ("domain_edges", "Domain-edge compatibility", NetworkDomainEdgesEvidence),
    ("seed_growth", "Seed / growth / role", (
        SeedGrowthEvidence, NetworkSeedGrowthEvidence,
    )),
    ("domain_partition", "Domain / island / outside", (
        DomainPartitionEvidence, NetworkDomainPartitionEvidence,
    )),
    ("domain_size", "Minimum domain size", (
        DomainSizeEvidence, NetworkDomainSizeEvidence,
    )),
    ("orientation_descriptor", "Orientation descriptor", OrientationDescriptorEvidence),
    ("orientation_raw", "Raw A/B/C", RawOrientationEvidence),
    ("orientation_threshold", "Confidence / margin", OrientationThresholdEvidence),
    ("orientation_component_filter", "Component filter", OrientationComponentFilterEvidence),
    ("automatic_result", "Automatic result", AutomaticOrientationEvidence),
    ("manual_correction", "Manual correction", ManualOrientationDecisionEvidence),
    ("effective_result", "Effective result", EffectiveOrientationEvidence),
)
MOLECULE_DIAGNOSTIC_STAGE_IDS = tuple(
    stage_id for stage_id, _, _ in _STAGE_DEFINITIONS
)
MOLECULE_DIAGNOSTIC_STAGE_LABELS = {
    stage_id: label for stage_id, label, _ in _STAGE_DEFINITIONS
}
_EVIDENCE_KINDS_BY_STAGE = {
    stage_id: tuple(
        value.evidence_kind
        for value in (
            payload_type if isinstance(payload_type, tuple) else (payload_type,)
        )
    )
    for stage_id, _, payload_type in _STAGE_DEFINITIONS
    if payload_type is not None
}


@dataclass(frozen=True)
class DiagnosticReason:
    category: DiagnosticReasonCategory
    code: str
    native_code: str | None = None

    def __post_init__(self) -> None:
        if self.category not in {
            "accepted", "not_run", "missing_data", "threshold",
            "insufficient_evidence", "conflict", "postprocess",
            "manual_override",
            "execution_error",
        }:
            raise ValueError(f"Unsupported diagnostic reason: {self.category!r}.")
        object.__setattr__(self, "code", _text(self.code, "reason code"))
        if self.native_code is not None:
            object.__setattr__(
                self,
                "native_code",
                _text(self.native_code, "native reason code"),
            )


@dataclass(frozen=True)
class DiagnosticEvidence:
    payload: DiagnosticEvidencePayload

    def __post_init__(self) -> None:
        for key, value in asdict(self.payload).items():
            _text(key, "evidence key")
            _evidence_value(value)

    @property
    def kind(self) -> str:
        return self.payload.evidence_kind

    @property
    def values(self) -> tuple[tuple[str, DiagnosticEvidenceValue], ...]:
        return tuple(sorted(
            (key, _evidence_value(value))
            for key, value in asdict(self.payload).items()
        ))

    def value(self, key: str) -> DiagnosticEvidenceValue:
        for candidate, value in self.values:
            if candidate == key:
                return value
        raise KeyError(key)


@dataclass(frozen=True)
class DiagnosticProvenanceContext:
    """Producer identity plus optional classifier-owned provenance overrides."""

    producer: str
    algorithm_version: str | None = None
    settings_fingerprint: str | None = None
    input_fingerprint: str | None = None
    output_fingerprint: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "producer", _text(self.producer, "producer"))
        for field_name in (
            "algorithm_version", "settings_fingerprint", "input_fingerprint",
            "output_fingerprint",
        ):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, _text(value, field_name))


@dataclass(frozen=True)
class DiagnosticProvenance:
    producer: str
    algorithm_version: str
    settings_fingerprint: str
    input_fingerprint: str
    output_fingerprint: str

    def __post_init__(self) -> None:
        for field_name in (
            "producer",
            "algorithm_version",
            "settings_fingerprint",
            "input_fingerprint",
            "output_fingerprint",
        ):
            object.__setattr__(
                self,
                field_name,
                _text(getattr(self, field_name), field_name),
            )


@dataclass(frozen=True)
class DiagnosticStageResult:
    stage_id: MoleculeDiagnosticStageId
    execution_status: DiagnosticExecutionStatus
    decision: DiagnosticDecision
    reason: DiagnosticReason
    evidence: DiagnosticEvidence | None = None
    provenance: DiagnosticProvenance | None = None

    def __post_init__(self) -> None:
        if self.stage_id not in MOLECULE_DIAGNOSTIC_STAGE_IDS:
            raise ValueError(f"Unsupported diagnostic stage: {self.stage_id!r}.")
        if self.execution_status not in {
            "completed", "not_run", "unavailable", "failed"
        }:
            raise ValueError(
                f"Unsupported execution status: {self.execution_status!r}."
            )
        if self.decision not in {
            "accepted", "rejected", "ambiguous", "filtered", "not_evaluated"
        }:
            raise ValueError(f"Unsupported decision: {self.decision!r}.")
        if not isinstance(self.reason, DiagnosticReason):
            raise TypeError("reason must be a DiagnosticReason.")
        if self.execution_status == "completed":
            if not isinstance(self.evidence, DiagnosticEvidence):
                raise TypeError("Completed diagnostic stages require typed evidence.")
            if not isinstance(self.provenance, DiagnosticProvenance):
                raise TypeError("Completed diagnostic stages require provenance.")
            expected_kinds = _EVIDENCE_KINDS_BY_STAGE.get(self.stage_id, ())
            if self.evidence.kind not in expected_kinds:
                raise ValueError("Diagnostic evidence kind does not match its stage.")
            if self.decision == "not_evaluated":
                raise ValueError("A completed stage requires a scientific decision.")
        elif self.evidence is not None or self.provenance is not None:
            raise ValueError("Unexecuted stages cannot invent evidence or provenance.")
        elif self.execution_status in {"not_run", "unavailable"} and (
            self.decision != "not_evaluated"
        ):
            raise ValueError("An unexecuted stage must remain not_evaluated.")

    @property
    def label(self) -> str:
        return MOLECULE_DIAGNOSTIC_STAGE_LABELS[self.stage_id]


@dataclass(frozen=True)
class MoleculeDiagnosticFunnel:
    frame_index: int
    physical_frame_id: str
    source_id: str
    backend_identity: DomainBackendIdentity
    stages: tuple[DiagnosticStageResult, ...]
    schema_version: str = "molecule-domain-orientation-diagnostic-v1"

    def __post_init__(self) -> None:
        if isinstance(self.frame_index, bool) or self.frame_index < 0:
            raise ValueError("frame_index must be a non-negative integer.")
        object.__setattr__(
            self,
            "physical_frame_id",
            _text(self.physical_frame_id, "physical_frame_id"),
        )
        object.__setattr__(self, "source_id", _text(self.source_id, "source_id"))
        if not isinstance(self.backend_identity, DomainBackendIdentity):
            raise TypeError("backend_identity must be a DomainBackendIdentity.")
        stages = tuple(self.stages)
        if any(not isinstance(value, DiagnosticStageResult) for value in stages):
            raise TypeError("stages must contain DiagnosticStageResult values.")
        if tuple(value.stage_id for value in stages) != (
            MOLECULE_DIAGNOSTIC_STAGE_IDS
        ):
            raise ValueError("A molecule diagnostic funnel requires all 17 stages.")
        object.__setattr__(self, "stages", stages)
        object.__setattr__(
            self,
            "schema_version",
            _text(self.schema_version, "schema_version"),
        )

    def stage(self, stage_id: MoleculeDiagnosticStageId) -> DiagnosticStageResult:
        return self.stages[MOLECULE_DIAGNOSTIC_STAGE_IDS.index(stage_id)]

    @property
    def terminal_domain_miss(self) -> DiagnosticStageResult | None:
        """Return the one terminal miss counted for later M6 evaluation."""

        if self.stage("domain_partition").decision == "accepted":
            return None
        domain_size = self.stage("domain_size")
        if domain_size.decision == "filtered":
            return domain_size
        for stage_id in (
            "first_shell", "local_order", "local_symmetry", "domain_edges",
            "seed_growth", "domain_partition",
        ):
            stage = self.stage(stage_id)
            if stage.execution_status in {"completed", "failed"} and (
                stage.decision != "accepted"
            ):
                return stage
        return self.stage("domain_partition")


def _text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be non-empty text.")
    return value.strip()


def _evidence_value(value: object) -> DiagnosticEvidenceValue:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float) and isfinite(value):
        return value
    if isinstance(value, tuple):
        normalized = tuple(_evidence_scalar(item) for item in value)
        return normalized
    raise TypeError(
        "Diagnostic evidence values must be finite scalars or flat scalar tuples."
    )


def _evidence_scalar(value: object) -> DiagnosticEvidenceScalar:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float) and isfinite(value):
        return value
    raise TypeError("Diagnostic evidence tuples must contain finite scalars.")
