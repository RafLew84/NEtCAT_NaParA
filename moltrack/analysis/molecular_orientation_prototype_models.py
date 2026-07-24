"""Versioned contracts for multi-frame molecular-orientation prototypes."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields
from hashlib import sha256
from math import isclose, isfinite
from typing import Literal, Mapping, get_args

from .lattice_row_models import LatticeRowAssignmentAnalysis
from .molecular_orientation_models import MolecularOrientationMeasurement


MOLECULAR_ORIENTATION_PROTOTYPE_SCHEMA_VERSION = 1
MOLECULAR_ORIENTATION_PROTOTYPE_ALGORITHM_VERSION = (
    "moltrack-molecular-orientation-prototypes-v1"
)

MolecularOrientationPrototypeStatus = Literal[
    "two_state",
    "one_state",
    "multi_state",
    "unavailable",
]
MolecularOrientationPrototypeReason = Literal[
    "two_supported_states",
    "one_supported_state",
    "more_than_two_supported_states",
    "no_lattice_measurements",
    "insufficient_observations",
    "insufficient_frame_coverage",
    "insufficient_state_support",
    "incompatible_periodicity",
]
MolecularOrientationStateLabel = Literal["A", "B"]
MolecularOrientationPatternMode = Literal[
    "along_rows",
    "between_rows",
    "checkerboard",
]
MolecularOrientationPatternPhase = Literal["ABAB", "BABA"]

_STATUSES = set(get_args(MolecularOrientationPrototypeStatus))
_REASONS = set(get_args(MolecularOrientationPrototypeReason))
_STATE_LABELS = set(get_args(MolecularOrientationStateLabel))
_PATTERN_MODES = set(get_args(MolecularOrientationPatternMode))
_PATTERN_PHASES = set(get_args(MolecularOrientationPatternPhase))
_EXPECTED_HYPOTHESES = tuple(
    (mode, phase)
    for mode in ("along_rows", "between_rows", "checkerboard")
    for phase in ("ABAB", "BABA")
)


@dataclass(frozen=True)
class MolecularOrientationPrototypeSettings:
    """Thresholds for clustering current multi-frame orientation data."""

    minimum_confidence: float = 0.5
    cluster_tolerance_deg: float = 12.0
    minimum_observation_count: int = 4
    minimum_frame_count: int = 2
    minimum_state_observation_count: int = 2
    minimum_state_frame_count: int = 2
    axis_aggregation_tolerance_deg: float = 5.0
    periodicity_tolerance_deg: float = 1e-6
    between_row_max_along_fraction: float = 0.75

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "minimum_confidence",
            _unit_float(self.minimum_confidence, "minimum_confidence"),
        )
        object.__setattr__(
            self,
            "cluster_tolerance_deg",
            _positive_float(
                self.cluster_tolerance_deg,
                "cluster_tolerance_deg",
            ),
        )
        object.__setattr__(
            self,
            "minimum_observation_count",
            _positive_integer(
                self.minimum_observation_count,
                "minimum_observation_count",
            ),
        )
        object.__setattr__(
            self,
            "minimum_frame_count",
            _at_least_two_integer(
                self.minimum_frame_count,
                "minimum_frame_count",
            ),
        )
        object.__setattr__(
            self,
            "minimum_state_observation_count",
            _positive_integer(
                self.minimum_state_observation_count,
                "minimum_state_observation_count",
            ),
        )
        object.__setattr__(
            self,
            "minimum_state_frame_count",
            _at_least_two_integer(
                self.minimum_state_frame_count,
                "minimum_state_frame_count",
            ),
        )
        axis_tolerance = _positive_float(
            self.axis_aggregation_tolerance_deg,
            "axis_aggregation_tolerance_deg",
        )
        if axis_tolerance >= 90.0:
            raise ValueError(
                "axis_aggregation_tolerance_deg must be less than 90."
            )
        object.__setattr__(
            self,
            "axis_aggregation_tolerance_deg",
            axis_tolerance,
        )
        object.__setattr__(
            self,
            "periodicity_tolerance_deg",
            _non_negative_float(
                self.periodicity_tolerance_deg,
                "periodicity_tolerance_deg",
            ),
        )
        object.__setattr__(
            self,
            "between_row_max_along_fraction",
            _positive_float(
                self.between_row_max_along_fraction,
                "between_row_max_along_fraction",
            ),
        )

    def to_dict(self) -> dict[str, int | float]:
        return {field.name: getattr(self, field.name) for field in fields(self)}

    @classmethod
    def from_dict(
        cls,
        payload: Mapping[str, object],
    ) -> "MolecularOrientationPrototypeSettings":
        if not isinstance(payload, Mapping):
            raise TypeError("Prototype settings must be a mapping.")
        names = {field.name for field in fields(cls)}
        if set(payload) != names:
            raise ValueError(
                "Prototype settings fields must match the schema."
            )
        return cls(**dict(payload))


def molecular_orientation_prototype_settings_fingerprint(
    settings: MolecularOrientationPrototypeSettings,
) -> str:
    if not isinstance(settings, MolecularOrientationPrototypeSettings):
        raise TypeError(
            "settings must be MolecularOrientationPrototypeSettings."
        )
    return _fingerprint(
        {
            "algorithm": (
                MOLECULAR_ORIENTATION_PROTOTYPE_ALGORITHM_VERSION
            ),
            "settings": settings.to_dict(),
        }
    )


@dataclass(frozen=True)
class MolecularOrientationFrameData:
    """Row geometry and orientation measurements from one current frame."""

    frame_index: int
    row_assignment: LatticeRowAssignmentAnalysis
    measurements: tuple[MolecularOrientationMeasurement, ...]

    def __post_init__(self) -> None:
        frame_index = _non_negative_integer(
            self.frame_index,
            "frame_index",
        )
        if not isinstance(
            self.row_assignment,
            LatticeRowAssignmentAnalysis,
        ):
            raise TypeError(
                "row_assignment must be LatticeRowAssignmentAnalysis."
            )
        measurements = tuple(self.measurements)
        if any(
            not isinstance(value, MolecularOrientationMeasurement)
            for value in measurements
        ):
            raise TypeError(
                "measurements must contain MolecularOrientationMeasurement."
            )
        if any(
            value.provenance.frame_index != frame_index
            for value in measurements
        ):
            raise ValueError(
                "Measurement frame_index must match frame data."
            )
        if any(
            value.provenance.orientation_reference
            != "sample_x_axis_counterclockwise"
            for value in measurements
        ):
            raise ValueError(
                "Prototype analysis requires sample-axis orientations."
            )
        source_ids = tuple(
            value.provenance.source_id for value in measurements
        )
        if len(set(source_ids)) != len(source_ids):
            raise ValueError(
                "Measurement source_ids must be unique within a frame."
            )
        measurements = tuple(
            sorted(
                measurements,
                key=lambda value: (
                    value.provenance.source_id,
                    value.measurement_id,
                ),
            )
        )
        object.__setattr__(self, "frame_index", frame_index)
        object.__setattr__(self, "measurements", measurements)


@dataclass(frozen=True)
class MolecularOrientationPrototype:
    """One confidence-weighted circular cluster."""

    prototype_index: int
    state_label: MolecularOrientationStateLabel | None
    angle_deg: float
    periodicity_deg: float
    observation_count: int
    frame_indices: tuple[int, ...]
    confidence_weight: float
    confidence_weight_fraction: float
    circular_spread_deg: float
    measurement_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        prototype_index = _non_negative_integer(
            self.prototype_index,
            "prototype_index",
        )
        if (
            self.state_label is not None
            and self.state_label not in _STATE_LABELS
        ):
            raise ValueError(
                f"Unsupported state_label: {self.state_label!r}."
            )
        periodicity = _positive_float(
            self.periodicity_deg,
            "periodicity_deg",
        )
        angle = _finite_float(self.angle_deg, "angle_deg") % periodicity
        observation_count = _positive_integer(
            self.observation_count,
            "observation_count",
        )
        frame_indices = tuple(self.frame_indices)
        if (
            not frame_indices
            or frame_indices
            != tuple(sorted(set(frame_indices)))
            or any(
                not isinstance(value, int)
                or isinstance(value, bool)
                or value < 0
                for value in frame_indices
            )
        ):
            raise ValueError(
                "frame_indices must be sorted unique non-negative integers."
            )
        measurement_ids = tuple(self.measurement_ids)
        if (
            len(measurement_ids) != observation_count
            or measurement_ids != tuple(sorted(set(measurement_ids)))
        ):
            raise ValueError(
                "measurement_ids must match observation_count."
            )
        confidence_weight = _positive_float(
            self.confidence_weight,
            "confidence_weight",
        )
        confidence_weight_fraction = _unit_float(
            self.confidence_weight_fraction,
            "confidence_weight_fraction",
        )
        spread = _non_negative_float(
            self.circular_spread_deg,
            "circular_spread_deg",
        )
        if spread > periodicity / 2.0:
            raise ValueError(
                "circular_spread_deg cannot exceed half the period."
            )
        object.__setattr__(self, "prototype_index", prototype_index)
        object.__setattr__(self, "angle_deg", angle)
        object.__setattr__(self, "periodicity_deg", periodicity)
        object.__setattr__(self, "observation_count", observation_count)
        object.__setattr__(self, "frame_indices", frame_indices)
        object.__setattr__(self, "confidence_weight", confidence_weight)
        object.__setattr__(
            self,
            "confidence_weight_fraction",
            confidence_weight_fraction,
        )
        object.__setattr__(self, "circular_spread_deg", spread)
        object.__setattr__(self, "measurement_ids", measurement_ids)


@dataclass(frozen=True)
class MolecularOrientationStateAssignment:
    """A/B state and lattice coordinates for one eligible molecule."""

    source_id: str
    measurement_id: str
    state_label: MolecularOrientationStateLabel
    angle_deg: float
    confidence: float
    prototype_distance_deg: float
    alternative_distance_deg: float
    row_index: int
    row_parity: int
    along_index: int
    along_parity: int

    def __post_init__(self) -> None:
        source_id = _non_empty_string(self.source_id, "source_id")
        measurement_id = _non_empty_string(
            self.measurement_id,
            "measurement_id",
        )
        if self.state_label not in _STATE_LABELS:
            raise ValueError(
                f"Unsupported state_label: {self.state_label!r}."
            )
        row_index = _integer(self.row_index, "row_index")
        along_index = _integer(self.along_index, "along_index")
        row_parity = _parity(self.row_parity, row_index, "row_parity")
        along_parity = _parity(
            self.along_parity,
            along_index,
            "along_parity",
        )
        object.__setattr__(self, "source_id", source_id)
        object.__setattr__(self, "measurement_id", measurement_id)
        object.__setattr__(
            self,
            "angle_deg",
            _finite_float(self.angle_deg, "angle_deg"),
        )
        object.__setattr__(
            self,
            "confidence",
            _unit_float(self.confidence, "confidence"),
        )
        for field_name in (
            "prototype_distance_deg",
            "alternative_distance_deg",
        ):
            object.__setattr__(
                self,
                field_name,
                _non_negative_float(
                    getattr(self, field_name),
                    field_name,
                ),
            )
        object.__setattr__(self, "row_index", row_index)
        object.__setattr__(self, "row_parity", row_parity)
        object.__setattr__(self, "along_index", along_index)
        object.__setattr__(self, "along_parity", along_parity)


@dataclass(frozen=True)
class MolecularOrientationPatternHypothesis:
    """Confidence-weighted agreement with one A/B phase and lattice mode."""

    mode: MolecularOrientationPatternMode
    phase: MolecularOrientationPatternPhase
    observation_count: int
    confidence_weight: float
    agreement_score: float | None

    def __post_init__(self) -> None:
        if self.mode not in _PATTERN_MODES:
            raise ValueError(f"Unsupported pattern mode: {self.mode!r}.")
        if self.phase not in _PATTERN_PHASES:
            raise ValueError(f"Unsupported pattern phase: {self.phase!r}.")
        observation_count = _non_negative_integer(
            self.observation_count,
            "observation_count",
        )
        confidence_weight = _non_negative_float(
            self.confidence_weight,
            "confidence_weight",
        )
        score = (
            None
            if self.agreement_score is None
            else _unit_float(self.agreement_score, "agreement_score")
        )
        if observation_count == 0:
            if confidence_weight != 0.0 or score is not None:
                raise ValueError(
                    "Empty hypothesis cannot contain weight or score."
                )
        elif confidence_weight <= 0.0 or score is None:
            raise ValueError(
                "Non-empty hypothesis requires weight and score."
            )
        object.__setattr__(self, "observation_count", observation_count)
        object.__setattr__(self, "confidence_weight", confidence_weight)
        object.__setattr__(self, "agreement_score", score)


@dataclass(frozen=True)
class MolecularOrientationAxisEvidence:
    """A/B evidence for one row-axis candidate in one lattice domain."""

    frame_index: int
    lattice_domain_id: str
    candidate_index: int
    axis_angle_deg: float
    domain_molecule_count: int
    assignments: tuple[MolecularOrientationStateAssignment, ...]
    coverage_fraction: float
    hypotheses: tuple[MolecularOrientationPatternHypothesis, ...]
    along_row_edge_count: int
    along_row_alternation_score: float | None
    between_row_edge_count: int
    between_row_alternation_score: float | None

    def __post_init__(self) -> None:
        frame_index = _non_negative_integer(
            self.frame_index,
            "frame_index",
        )
        domain_id = _non_empty_string(
            self.lattice_domain_id,
            "lattice_domain_id",
        )
        candidate_index = _non_negative_integer(
            self.candidate_index,
            "candidate_index",
        )
        domain_count = _positive_integer(
            self.domain_molecule_count,
            "domain_molecule_count",
        )
        assignments = tuple(self.assignments)
        if any(
            not isinstance(value, MolecularOrientationStateAssignment)
            for value in assignments
        ):
            raise TypeError(
                "assignments must contain state assignments."
            )
        if tuple(value.source_id for value in assignments) != tuple(
            sorted({value.source_id for value in assignments})
        ):
            raise ValueError(
                "assignments must be sorted and unique by source_id."
            )
        expected_coverage = len(assignments) / domain_count
        if not isclose(
            float(self.coverage_fraction),
            expected_coverage,
            abs_tol=1e-12,
        ):
            raise ValueError(
                "coverage_fraction must match assignment count."
            )
        hypotheses = tuple(self.hypotheses)
        if any(
            not isinstance(
                value,
                MolecularOrientationPatternHypothesis,
            )
            for value in hypotheses
        ):
            raise TypeError("hypotheses contain an invalid type.")
        if tuple((value.mode, value.phase) for value in hypotheses) != (
            _EXPECTED_HYPOTHESES
        ):
            raise ValueError(
                "hypotheses must contain every ordered mode/phase pair."
            )
        along_count = _non_negative_integer(
            self.along_row_edge_count,
            "along_row_edge_count",
        )
        between_count = _non_negative_integer(
            self.between_row_edge_count,
            "between_row_edge_count",
        )
        along_score = _optional_edge_score(
            self.along_row_alternation_score,
            along_count,
            "along_row_alternation_score",
        )
        between_score = _optional_edge_score(
            self.between_row_alternation_score,
            between_count,
            "between_row_alternation_score",
        )
        object.__setattr__(self, "frame_index", frame_index)
        object.__setattr__(self, "lattice_domain_id", domain_id)
        object.__setattr__(self, "candidate_index", candidate_index)
        object.__setattr__(
            self,
            "axis_angle_deg",
            _finite_float(self.axis_angle_deg, "axis_angle_deg") % 180.0,
        )
        object.__setattr__(self, "domain_molecule_count", domain_count)
        object.__setattr__(self, "assignments", assignments)
        object.__setattr__(self, "coverage_fraction", expected_coverage)
        object.__setattr__(self, "hypotheses", hypotheses)
        object.__setattr__(self, "along_row_edge_count", along_count)
        object.__setattr__(
            self,
            "along_row_alternation_score",
            along_score,
        )
        object.__setattr__(self, "between_row_edge_count", between_count)
        object.__setattr__(
            self,
            "between_row_alternation_score",
            between_score,
        )

    def hypothesis(
        self,
        mode: MolecularOrientationPatternMode,
        phase: MolecularOrientationPatternPhase,
    ) -> MolecularOrientationPatternHypothesis:
        for value in self.hypotheses:
            if value.mode == mode and value.phase == phase:
                return value
        raise KeyError(f"Unknown hypothesis: {mode}/{phase}.")


@dataclass(frozen=True)
class MolecularOrientationRangeAxisEvidence:
    """Phase evidence for one sample-axis family supported across frames."""

    axis_family_index: int
    axis_angle_deg: float
    candidate_keys: tuple[tuple[int, str, int], ...]
    frame_indices: tuple[int, ...]
    axis_evidence_count: int
    observation_count: int
    hypotheses: tuple[MolecularOrientationPatternHypothesis, ...]
    along_row_edge_count: int
    along_row_alternation_score: float | None
    between_row_edge_count: int
    between_row_alternation_score: float | None

    def __post_init__(self) -> None:
        family_index = _non_negative_integer(
            self.axis_family_index,
            "axis_family_index",
        )
        axis_angle = _finite_float(
            self.axis_angle_deg,
            "axis_angle_deg",
        ) % 180.0
        candidate_keys = tuple(self.candidate_keys)
        if any(
            not isinstance(value, tuple)
            or len(value) != 3
            or not isinstance(value[0], int)
            or isinstance(value[0], bool)
            or value[0] < 0
            or not isinstance(value[1], str)
            or not value[1]
            or not isinstance(value[2], int)
            or isinstance(value[2], bool)
            or value[2] < 0
            for value in candidate_keys
        ):
            raise ValueError("Invalid candidate axis key.")
        if candidate_keys != tuple(sorted(set(candidate_keys))):
            raise ValueError(
                "candidate_keys must be sorted and unique."
            )
        frame_indices = _frame_indices(
            self.frame_indices,
            "frame_indices",
            allow_empty=False,
        )
        evidence_count = _positive_integer(
            self.axis_evidence_count,
            "axis_evidence_count",
        )
        observation_count = _non_negative_integer(
            self.observation_count,
            "observation_count",
        )
        hypotheses = tuple(self.hypotheses)
        if any(
            not isinstance(
                value,
                MolecularOrientationPatternHypothesis,
            )
            for value in hypotheses
        ):
            raise TypeError("hypotheses contain an invalid type.")
        if tuple((value.mode, value.phase) for value in hypotheses) != (
            _EXPECTED_HYPOTHESES
        ):
            raise ValueError(
                "hypotheses must contain every ordered mode/phase pair."
            )
        if any(
            value.observation_count != observation_count
            for value in hypotheses
        ):
            raise ValueError(
                "Range hypotheses must cover every observation."
            )
        along_count = _non_negative_integer(
            self.along_row_edge_count,
            "along_row_edge_count",
        )
        between_count = _non_negative_integer(
            self.between_row_edge_count,
            "between_row_edge_count",
        )
        if tuple(sorted({value[0] for value in candidate_keys})) != (
            frame_indices
        ):
            raise ValueError(
                "candidate_keys must cover every aggregate frame."
            )
        object.__setattr__(self, "axis_family_index", family_index)
        object.__setattr__(self, "axis_angle_deg", axis_angle)
        object.__setattr__(self, "candidate_keys", candidate_keys)
        object.__setattr__(self, "frame_indices", frame_indices)
        object.__setattr__(self, "axis_evidence_count", evidence_count)
        object.__setattr__(self, "observation_count", observation_count)
        object.__setattr__(self, "hypotheses", hypotheses)
        object.__setattr__(self, "along_row_edge_count", along_count)
        object.__setattr__(
            self,
            "along_row_alternation_score",
            _optional_edge_score(
                self.along_row_alternation_score,
                along_count,
                "along_row_alternation_score",
            ),
        )
        object.__setattr__(self, "between_row_edge_count", between_count)
        object.__setattr__(
            self,
            "between_row_alternation_score",
            _optional_edge_score(
                self.between_row_alternation_score,
                between_count,
                "between_row_alternation_score",
            ),
        )

    def hypothesis(
        self,
        mode: MolecularOrientationPatternMode,
        phase: MolecularOrientationPatternPhase,
    ) -> MolecularOrientationPatternHypothesis:
        for value in self.hypotheses:
            if value.mode == mode and value.phase == phase:
                return value
        raise KeyError(f"Unknown hypothesis: {mode}/{phase}.")


@dataclass(frozen=True)
class MolecularOrientationPrototypeAnalysis:
    """Shared prototypes and per-axis evidence for one current frame set."""

    status: MolecularOrientationPrototypeStatus
    reason: MolecularOrientationPrototypeReason
    prototypes: tuple[MolecularOrientationPrototype, ...]
    axis_evidence: tuple[MolecularOrientationAxisEvidence, ...]
    range_axis_evidence: tuple[MolecularOrientationRangeAxisEvidence, ...]
    input_frame_indices: tuple[int, ...]
    eligible_frame_indices: tuple[int, ...]
    total_measurement_count: int
    eligible_observation_count: int
    unsupported_state_observation_count: int
    excluded_non_available_count: int
    excluded_low_confidence_count: int
    excluded_outside_lattice_count: int
    periodicity_deg: float | None
    source_file_sha256: str | None
    source_view: str | None
    row_assignment_fingerprints: tuple[tuple[int, str], ...]
    measurement_fingerprint: str
    settings: MolecularOrientationPrototypeSettings
    settings_fingerprint: str
    schema_version: int = MOLECULAR_ORIENTATION_PROTOTYPE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.status not in _STATUSES:
            raise ValueError(f"Unsupported prototype status: {self.status!r}.")
        if self.reason not in _REASONS:
            raise ValueError(f"Unsupported prototype reason: {self.reason!r}.")
        expected_reason = {
            "two_state": "two_supported_states",
            "one_state": "one_supported_state",
            "multi_state": "more_than_two_supported_states",
        }
        if self.status in expected_reason and (
            self.reason != expected_reason[self.status]
        ):
            raise ValueError("Prototype reason must match status.")
        if self.status == "unavailable" and self.reason in set(
            expected_reason.values()
        ):
            raise ValueError("Unavailable status requires a failure reason.")
        prototypes = tuple(self.prototypes)
        if any(
            not isinstance(value, MolecularOrientationPrototype)
            for value in prototypes
        ):
            raise TypeError("prototypes contain an invalid type.")
        if tuple(value.prototype_index for value in prototypes) != tuple(
            range(len(prototypes))
        ):
            raise ValueError(
                "prototype_index values must be contiguous and ordered."
            )
        axis_evidence = tuple(self.axis_evidence)
        if any(
            not isinstance(value, MolecularOrientationAxisEvidence)
            for value in axis_evidence
        ):
            raise TypeError("axis_evidence contains an invalid type.")
        if axis_evidence != tuple(
            sorted(
                axis_evidence,
                key=lambda value: (
                    value.frame_index,
                    value.lattice_domain_id,
                    value.candidate_index,
                ),
            )
        ):
            raise ValueError("axis_evidence must be deterministically sorted.")
        range_evidence = tuple(self.range_axis_evidence)
        if any(
            not isinstance(
                value,
                MolecularOrientationRangeAxisEvidence,
            )
            for value in range_evidence
        ):
            raise TypeError("range_axis_evidence contains an invalid type.")
        if tuple(
            value.axis_family_index for value in range_evidence
        ) != tuple(
            range(len(range_evidence))
        ):
            raise ValueError(
                "Range axis family indices must be contiguous and ordered."
            )
        axis_evidence_by_key = {
            (
                value.frame_index,
                value.lattice_domain_id,
                value.candidate_index,
            ): value
            for value in axis_evidence
        }
        aggregated_keys = []
        for aggregate in range_evidence:
            members = tuple(
                axis_evidence_by_key[value]
                for value in aggregate.candidate_keys
                if value in axis_evidence_by_key
            )
            if (
                len(aggregate.frame_indices) < 2
                or len(members) != len(aggregate.candidate_keys)
                or aggregate.axis_evidence_count != len(members)
                or aggregate.frame_indices
                != tuple(sorted({value.frame_index for value in members}))
                or aggregate.observation_count
                != sum(len(value.assignments) for value in members)
            ):
                raise ValueError(
                    "Range axis evidence must match per-frame evidence."
                )
            aggregated_keys.extend(aggregate.candidate_keys)
        if len(aggregated_keys) != len(set(aggregated_keys)):
            raise ValueError(
                "Per-frame axis evidence cannot belong to two families."
            )
        if self.status == "two_state":
            if (
                len(prototypes) != 2
                or tuple(value.state_label for value in prototypes)
                != ("A", "B")
            ):
                raise ValueError(
                    "two_state analysis requires ordered A/B prototypes."
                )
        elif self.status == "one_state":
            if len(prototypes) != 1 or prototypes[0].state_label is not None:
                raise ValueError(
                    "one_state analysis requires one unlabeled prototype."
                )
            if axis_evidence:
                raise ValueError("one_state analysis cannot contain A/B evidence.")
            if range_evidence:
                raise ValueError(
                    "one_state analysis cannot contain range A/B evidence."
                )
        elif self.status == "multi_state":
            if (
                len(prototypes) <= 2
                or any(value.state_label is not None for value in prototypes)
            ):
                raise ValueError(
                    "multi_state analysis requires unlabeled prototypes."
                )
            if axis_evidence:
                raise ValueError(
                    "multi_state analysis cannot contain A/B evidence."
                )
            if range_evidence:
                raise ValueError(
                    "multi_state analysis cannot contain range A/B evidence."
                )
        elif prototypes or axis_evidence or range_evidence:
            raise ValueError(
                "Unavailable analysis cannot contain prototypes or evidence."
            )
        if prototypes and not isclose(
            sum(value.confidence_weight_fraction for value in prototypes),
            1.0,
            abs_tol=1e-12,
        ):
            raise ValueError(
                "Prototype confidence weight fractions must sum to one."
            )
        input_frames = _frame_indices(
            self.input_frame_indices,
            "input_frame_indices",
            allow_empty=False,
        )
        eligible_frames = _frame_indices(
            self.eligible_frame_indices,
            "eligible_frame_indices",
            allow_empty=True,
        )
        if not set(eligible_frames).issubset(input_frames):
            raise ValueError(
                "eligible_frame_indices must be input frames."
            )
        counts = {}
        for field_name in (
            "total_measurement_count",
            "eligible_observation_count",
            "unsupported_state_observation_count",
            "excluded_non_available_count",
            "excluded_low_confidence_count",
            "excluded_outside_lattice_count",
        ):
            counts[field_name] = _non_negative_integer(
                getattr(self, field_name),
                field_name,
            )
            object.__setattr__(self, field_name, counts[field_name])
        if (
            counts["eligible_observation_count"]
            + counts["excluded_non_available_count"]
            + counts["excluded_low_confidence_count"]
            + counts["excluded_outside_lattice_count"]
            != counts["total_measurement_count"]
        ):
            raise ValueError(
                "Measurement inclusion/exclusion counts must be complete."
            )
        if prototypes and (
            sum(value.observation_count for value in prototypes)
            + counts["unsupported_state_observation_count"]
            != counts["eligible_observation_count"]
        ):
            raise ValueError(
                "Prototype and unsupported observations must cover every "
                "eligible observation."
            )
        if (
            not prototypes
            and counts["unsupported_state_observation_count"]
            not in (0, counts["eligible_observation_count"])
        ):
            raise ValueError(
                "Unavailable observations must be entirely supported or "
                "unsupported."
            )
        periodicity = (
            None
            if self.periodicity_deg is None
            else _positive_float(self.periodicity_deg, "periodicity_deg")
        )
        if prototypes and periodicity is None:
            raise ValueError("Prototype results require periodicity_deg.")
        if self.source_file_sha256 is not None:
            _sha256(self.source_file_sha256, "source_file_sha256")
        source_view = (
            None
            if self.source_view is None
            else _non_empty_string(self.source_view, "source_view")
        )
        row_fingerprints = tuple(self.row_assignment_fingerprints)
        if any(
            not isinstance(value, tuple)
            or len(value) != 2
            or not isinstance(value[0], int)
            or not isinstance(value[1], str)
            or not value[1]
            for value in row_fingerprints
        ):
            raise ValueError("Invalid row-assignment fingerprint entry.")
        if tuple(value[0] for value in row_fingerprints) != input_frames:
            raise ValueError(
                "Row-assignment fingerprints must cover every input frame."
            )
        if not isinstance(
            self.settings,
            MolecularOrientationPrototypeSettings,
        ):
            raise TypeError(
                "settings must be MolecularOrientationPrototypeSettings."
            )
        if self.settings_fingerprint != (
            molecular_orientation_prototype_settings_fingerprint(
                self.settings
            )
        ):
            raise ValueError("settings_fingerprint must match settings.")
        if (
            self.schema_version
            != MOLECULAR_ORIENTATION_PROTOTYPE_SCHEMA_VERSION
        ):
            raise ValueError("Unsupported prototype schema_version.")
        object.__setattr__(self, "prototypes", prototypes)
        object.__setattr__(self, "axis_evidence", axis_evidence)
        object.__setattr__(self, "range_axis_evidence", range_evidence)
        object.__setattr__(self, "input_frame_indices", input_frames)
        object.__setattr__(self, "eligible_frame_indices", eligible_frames)
        object.__setattr__(self, "periodicity_deg", periodicity)
        object.__setattr__(self, "source_view", source_view)
        object.__setattr__(
            self,
            "row_assignment_fingerprints",
            row_fingerprints,
        )
        object.__setattr__(
            self,
            "measurement_fingerprint",
            _non_empty_string(
                self.measurement_fingerprint,
                "measurement_fingerprint",
            ),
        )
        object.__setattr__(
            self,
            "settings_fingerprint",
            _non_empty_string(
                self.settings_fingerprint,
                "settings_fingerprint",
            ),
        )

    def prototype_for_state(
        self,
        state_label: MolecularOrientationStateLabel,
    ) -> MolecularOrientationPrototype:
        if state_label not in _STATE_LABELS:
            raise ValueError(f"Unsupported state_label: {state_label!r}.")
        for value in self.prototypes:
            if value.state_label == state_label:
                return value
        raise KeyError(f"Prototype state is unavailable: {state_label}.")


def molecular_orientation_prototype_analysis_fingerprint(
    analysis: MolecularOrientationPrototypeAnalysis,
) -> str:
    if not isinstance(analysis, MolecularOrientationPrototypeAnalysis):
        raise TypeError(
            "analysis must be MolecularOrientationPrototypeAnalysis."
        )
    return _fingerprint(
        {
            "algorithm": (
                MOLECULAR_ORIENTATION_PROTOTYPE_ALGORITHM_VERSION
            ),
            "analysis": asdict(analysis),
        }
    )


def _optional_edge_score(
    value: object,
    edge_count: int,
    field_name: str,
) -> float | None:
    if edge_count == 0:
        if value is not None:
            raise ValueError(
                f"{field_name} must be None when no edges are available."
            )
        return None
    if value is None:
        raise ValueError(
            f"{field_name} is required when edges are available."
        )
    return _unit_float(value, field_name)


def _parity(value: object, index: int, field_name: str) -> int:
    normalized = _non_negative_integer(value, field_name)
    if normalized not in (0, 1) or normalized != index % 2:
        raise ValueError(f"{field_name} must equal index modulo two.")
    return normalized


def _frame_indices(
    value: object,
    field_name: str,
    *,
    allow_empty: bool,
) -> tuple[int, ...]:
    normalized = tuple(value)  # type: ignore[arg-type]
    if (
        (not allow_empty and not normalized)
        or normalized != tuple(sorted(set(normalized)))
        or any(
            not isinstance(item, int)
            or isinstance(item, bool)
            or item < 0
            for item in normalized
        )
    ):
        raise ValueError(
            f"{field_name} must be sorted unique frame indices."
        )
    return normalized


def _fingerprint(payload: object) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def _sha256(value: object, field_name: str) -> str:
    normalized = _non_empty_string(value, field_name)
    if len(normalized) != 64:
        raise ValueError(f"{field_name} must be a SHA-256 digest.")
    try:
        int(normalized, 16)
    except ValueError as exc:
        raise ValueError(
            f"{field_name} must be a SHA-256 digest."
        ) from exc
    return normalized.lower()


def _positive_integer(value: object, field_name: str) -> int:
    normalized = _non_negative_integer(value, field_name)
    if normalized <= 0:
        raise ValueError(f"{field_name} must be positive.")
    return normalized


def _at_least_two_integer(value: object, field_name: str) -> int:
    normalized = _positive_integer(value, field_name)
    if normalized < 2:
        raise ValueError(f"{field_name} must be at least two.")
    return normalized


def _non_negative_integer(value: object, field_name: str) -> int:
    normalized = _integer(value, field_name)
    if normalized < 0:
        raise ValueError(f"{field_name} must be non-negative.")
    return normalized


def _integer(value: object, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{field_name} must be an integer.")
    return value


def _positive_float(value: object, field_name: str) -> float:
    normalized = _finite_float(value, field_name)
    if normalized <= 0.0:
        raise ValueError(f"{field_name} must be positive.")
    return normalized


def _non_negative_float(value: object, field_name: str) -> float:
    normalized = _finite_float(value, field_name)
    if normalized < 0.0:
        raise ValueError(f"{field_name} must be non-negative.")
    return normalized


def _unit_float(value: object, field_name: str) -> float:
    normalized = _finite_float(value, field_name)
    if not 0.0 <= normalized <= 1.0:
        raise ValueError(f"{field_name} must lie between zero and one.")
    return normalized


def _finite_float(value: object, field_name: str) -> float:
    try:
        normalized = float(value)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"{field_name} must be numeric.") from exc
    if not isfinite(normalized):
        raise ValueError(f"{field_name} must be finite.")
    return normalized


def _non_empty_string(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} must be a non-empty string.")
    return value


__all__ = [
    "MOLECULAR_ORIENTATION_PROTOTYPE_ALGORITHM_VERSION",
    "MOLECULAR_ORIENTATION_PROTOTYPE_SCHEMA_VERSION",
    "MolecularOrientationAxisEvidence",
    "MolecularOrientationFrameData",
    "MolecularOrientationPatternHypothesis",
    "MolecularOrientationPatternMode",
    "MolecularOrientationPatternPhase",
    "MolecularOrientationPrototype",
    "MolecularOrientationPrototypeAnalysis",
    "MolecularOrientationPrototypeReason",
    "MolecularOrientationPrototypeSettings",
    "MolecularOrientationPrototypeStatus",
    "MolecularOrientationRangeAxisEvidence",
    "MolecularOrientationStateAssignment",
    "MolecularOrientationStateLabel",
    "molecular_orientation_prototype_analysis_fingerprint",
    "molecular_orientation_prototype_settings_fingerprint",
]
