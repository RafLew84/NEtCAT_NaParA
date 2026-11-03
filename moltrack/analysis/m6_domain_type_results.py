from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from ._m6_domain_type_validation import (
    non_empty_string as _non_empty_string,
    non_negative_float as _non_negative_float,
    non_negative_int as _non_negative_int,
    normalize_m6_orientation as _normalize_m6_orientation,
    positive_float as _positive_float,
    positive_int as _positive_int,
)
from ._m6_settings_fingerprint import m6_settings_fingerprint
from .frame_ranges import MolecularFrameRange, MolecularFrameRangeAnalysisScope
from .m6_domain_type_observations import (
    M6DomainTypeObservation,
    M6DomainTypeObservationKey,
)
from .m6_domain_type_settings import M6DomainTypeClassificationSettings
from .m6_settings import MolecularM6OrientationAnalysisSettings


M6DomainTypeAssignmentStatus = Literal["classified", "unclassified"]
M6DomainTypeClassificationMode = Literal[
    "single_range_structural_domain_type_classification",
    "joint_structural_domain_type_classification",
]
M6DomainTypeAssignmentReason = Literal[
    "small_ordered_island_excluded",
    "missing_bond_length_statistics",
    "bond_length_heterogeneity_qc",
    "below_minimum_observations_per_type",
]

M6_DOMAIN_TYPE_UNCLASSIFIED_REASONS: tuple[
    M6DomainTypeAssignmentReason,
    ...,
] = (
    "small_ordered_island_excluded",
    "missing_bond_length_statistics",
    "bond_length_heterogeneity_qc",
    "below_minimum_observations_per_type",
)
_UNCLASSIFIED_REASONS = set(M6_DOMAIN_TYPE_UNCLASSIFIED_REASONS)


@dataclass(frozen=True)
class M6DomainType:
    """One structural domain type shared by all of its assigned observations."""

    domain_type_id: int
    prototype_orientation_deg: float
    prototype_bond_length_nm: float
    orientation_circular_spread_deg: float
    bond_length_iqr_nm: float
    observation_count: int

    def __post_init__(self) -> None:
        domain_type_id = _non_negative_int(self.domain_type_id, "domain_type_id")
        orientation = _normalize_m6_orientation(
            self.prototype_orientation_deg,
            "prototype_orientation_deg",
        )
        bond_length = _positive_float(
            self.prototype_bond_length_nm,
            "prototype_bond_length_nm",
        )
        orientation_spread = _non_negative_float(
            self.orientation_circular_spread_deg,
            "orientation_circular_spread_deg",
        )
        if orientation_spread > 30.0:
            raise ValueError("orientation_circular_spread_deg must not exceed 30.")
        bond_length_iqr = _non_negative_float(
            self.bond_length_iqr_nm,
            "bond_length_iqr_nm",
        )
        observation_count = _positive_int(
            self.observation_count,
            "observation_count",
        )
        object.__setattr__(self, "domain_type_id", domain_type_id)
        object.__setattr__(self, "prototype_orientation_deg", orientation)
        object.__setattr__(self, "prototype_bond_length_nm", bond_length)
        object.__setattr__(
            self,
            "orientation_circular_spread_deg",
            orientation_spread,
        )
        object.__setattr__(self, "bond_length_iqr_nm", bond_length_iqr)
        object.__setattr__(self, "observation_count", observation_count)

    @property
    def label(self) -> str:
        return _domain_type_label(self.domain_type_id)


@dataclass(frozen=True)
class M6DomainTypeAssignment:
    """Exactly one classified or unclassified outcome for an observation key."""

    observation_key: M6DomainTypeObservationKey
    status: M6DomainTypeAssignmentStatus
    domain_type_id: int | None
    unclassified_reason: M6DomainTypeAssignmentReason | None

    def __post_init__(self) -> None:
        observation_key = _observation_key(self.observation_key)
        if self.status not in {"classified", "unclassified"}:
            raise ValueError("Unsupported domain type assignment status.")
        if self.status == "classified":
            if self.domain_type_id is None:
                raise ValueError("A classified assignment requires domain_type_id.")
            domain_type_id = _non_negative_int(
                self.domain_type_id,
                "domain_type_id",
            )
            if self.unclassified_reason is not None:
                raise ValueError("A classified assignment cannot have a reason.")
            reason = None
        else:
            if self.domain_type_id is not None:
                raise ValueError("An unclassified assignment cannot have domain_type_id.")
            if self.unclassified_reason not in _UNCLASSIFIED_REASONS:
                raise ValueError("An unclassified assignment requires a supported reason.")
            domain_type_id = None
            reason = self.unclassified_reason
        object.__setattr__(self, "observation_key", observation_key)
        object.__setattr__(self, "domain_type_id", domain_type_id)
        object.__setattr__(self, "unclassified_reason", reason)

    @classmethod
    def classified(
        cls,
        observation_key: M6DomainTypeObservationKey,
        *,
        domain_type_id: int,
    ) -> "M6DomainTypeAssignment":
        return cls(
            observation_key=observation_key,
            status="classified",
            domain_type_id=domain_type_id,
            unclassified_reason=None,
        )

    @classmethod
    def unclassified(
        cls,
        observation_key: M6DomainTypeObservationKey,
        *,
        reason: M6DomainTypeAssignmentReason,
    ) -> "M6DomainTypeAssignment":
        return cls(
            observation_key=observation_key,
            status="unclassified",
            domain_type_id=None,
            unclassified_reason=reason,
        )


@dataclass(frozen=True)
class M6DomainTypeClassificationQcReport:
    """Auditable classification counts, including every rejection reason."""

    observation_count: int
    classified_observation_count: int
    unclassified_observation_count: int
    unclassified_reason_counts: tuple[
        tuple[M6DomainTypeAssignmentReason, int],
        ...,
    ]

    def __post_init__(self) -> None:
        observation_count = _non_negative_int(
            self.observation_count,
            "observation_count",
        )
        classified_count = _non_negative_int(
            self.classified_observation_count,
            "classified_observation_count",
        )
        unclassified_count = _non_negative_int(
            self.unclassified_observation_count,
            "unclassified_observation_count",
        )
        if observation_count != classified_count + unclassified_count:
            raise ValueError("QC observation counts must balance.")

        try:
            entries = tuple(self.unclassified_reason_counts)
        except TypeError as exc:
            raise TypeError(
                "unclassified_reason_counts must be an iterable of pairs."
            ) from exc
        counts: dict[M6DomainTypeAssignmentReason, int] = {}
        for entry in entries:
            if not isinstance(entry, (tuple, list)) or len(entry) != 2:
                raise TypeError(
                    "unclassified_reason_counts must contain reason/count pairs."
                )
            reason, raw_count = entry
            if reason not in _UNCLASSIFIED_REASONS:
                raise ValueError("Unsupported unclassified reason in QC report.")
            if reason in counts:
                raise ValueError("QC report cannot repeat an unclassified reason.")
            counts[reason] = _non_negative_int(
                raw_count,
                f"unclassified count for {reason}",
            )
        if set(counts) != _UNCLASSIFIED_REASONS:
            raise ValueError("QC report must contain every unclassified reason.")
        normalized_counts = tuple(
            (reason, counts[reason])
            for reason in M6_DOMAIN_TYPE_UNCLASSIFIED_REASONS
        )
        if sum(count for _, count in normalized_counts) != unclassified_count:
            raise ValueError("QC unclassified reason counts must balance.")

        object.__setattr__(self, "observation_count", observation_count)
        object.__setattr__(
            self,
            "classified_observation_count",
            classified_count,
        )
        object.__setattr__(
            self,
            "unclassified_observation_count",
            unclassified_count,
        )
        object.__setattr__(
            self,
            "unclassified_reason_counts",
            normalized_counts,
        )

    @classmethod
    def from_assignments(
        cls,
        assignments: tuple[M6DomainTypeAssignment, ...],
    ) -> "M6DomainTypeClassificationQcReport":
        normalized_assignments = tuple(assignments)
        if any(
            not isinstance(assignment, M6DomainTypeAssignment)
            for assignment in normalized_assignments
        ):
            raise TypeError("assignments must contain M6DomainTypeAssignment values.")
        counts = {reason: 0 for reason in M6_DOMAIN_TYPE_UNCLASSIFIED_REASONS}
        classified_count = 0
        for assignment in normalized_assignments:
            if assignment.status == "classified":
                classified_count += 1
            else:
                reason = assignment.unclassified_reason
                if reason is None:  # guarded by M6DomainTypeAssignment
                    raise ValueError("Unclassified assignment is missing its reason.")
                counts[reason] += 1
        return cls(
            observation_count=len(normalized_assignments),
            classified_observation_count=classified_count,
            unclassified_observation_count=(
                len(normalized_assignments) - classified_count
            ),
            unclassified_reason_counts=tuple(counts.items()),
        )


@dataclass(frozen=True)
class M6DomainTypeClassificationResult:
    """Validated partition of range observations into structural domain types."""

    analysis_scope: MolecularFrameRangeAnalysisScope
    classification_settings: M6DomainTypeClassificationSettings
    m6_settings: MolecularM6OrientationAnalysisSettings
    m6_context_fingerprint: str
    input_fingerprint: str
    observations: tuple[M6DomainTypeObservation, ...]
    domain_types: tuple[M6DomainType, ...]
    assignments: tuple[M6DomainTypeAssignment, ...]
    qc_report: M6DomainTypeClassificationQcReport
    classification_mode: M6DomainTypeClassificationMode = field(init=False)
    uses_tracking: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.analysis_scope, MolecularFrameRangeAnalysisScope):
            raise TypeError("analysis_scope must be MolecularFrameRangeAnalysisScope.")
        if not isinstance(
            self.classification_settings,
            M6DomainTypeClassificationSettings,
        ):
            raise TypeError(
                "classification_settings must be M6DomainTypeClassificationSettings."
            )
        if not isinstance(self.m6_settings, MolecularM6OrientationAnalysisSettings):
            raise TypeError("m6_settings must be MolecularM6OrientationAnalysisSettings.")
        m6_context_fingerprint = _non_empty_string(
            self.m6_context_fingerprint,
            "m6_context_fingerprint",
        )
        input_fingerprint = _non_empty_string(
            self.input_fingerprint,
            "input_fingerprint",
        )

        observations = tuple(self.observations)
        if any(not isinstance(value, M6DomainTypeObservation) for value in observations):
            raise TypeError("observations must contain M6DomainTypeObservation values.")
        observation_keys = tuple(value.stable_key for value in observations)
        if len(set(observation_keys)) != len(observation_keys):
            raise ValueError("Classification observations must have unique stable keys.")
        _validate_observation_context(
            observations,
            analysis_scope=self.analysis_scope,
            classification_settings=self.classification_settings,
            m6_settings=self.m6_settings,
            m6_context_fingerprint=m6_context_fingerprint,
        )

        domain_types = tuple(self.domain_types)
        if any(not isinstance(value, M6DomainType) for value in domain_types):
            raise TypeError("domain_types must contain M6DomainType values.")
        expected_type_ids = tuple(range(len(domain_types)))
        if tuple(value.domain_type_id for value in domain_types) != expected_type_ids:
            raise ValueError("domain_type_id values must be contiguous and ordered from zero.")
        if any(
            value.observation_count
            < self.classification_settings.minimum_observations_per_type
            for value in domain_types
        ):
            raise ValueError(
                "Domain types must reach minimum_observations_per_type."
            )

        assignments = tuple(self.assignments)
        if any(not isinstance(value, M6DomainTypeAssignment) for value in assignments):
            raise TypeError("assignments must contain M6DomainTypeAssignment values.")
        assignment_keys = tuple(value.observation_key for value in assignments)
        if len(set(assignment_keys)) != len(assignment_keys):
            raise ValueError("An observation cannot have more than one assignment.")
        if set(assignment_keys) != set(observation_keys):
            raise ValueError("Every observation must have exactly one assignment.")
        observation_by_key = {
            observation.stable_key: observation for observation in observations
        }
        type_ids = set(expected_type_ids)
        classified_counts = {type_id: 0 for type_id in expected_type_ids}
        for assignment in assignments:
            observation = observation_by_key[assignment.observation_key]
            _validate_assignment_for_observation(assignment, observation)
            if assignment.status == "classified":
                if assignment.domain_type_id not in type_ids:
                    raise ValueError("Assignment references an unknown domain type.")
                classified_counts[assignment.domain_type_id] += 1
        for domain_type in domain_types:
            if classified_counts[domain_type.domain_type_id] != (
                domain_type.observation_count
            ):
                raise ValueError("Domain type observation_count is inconsistent.")

        expected_mode: M6DomainTypeClassificationMode = (
            "single_range_structural_domain_type_classification"
            if self.analysis_scope.analysis_mode == "single_range"
            else "joint_structural_domain_type_classification"
        )
        if not isinstance(self.qc_report, M6DomainTypeClassificationQcReport):
            raise TypeError("qc_report must be M6DomainTypeClassificationQcReport.")
        expected_qc_report = M6DomainTypeClassificationQcReport.from_assignments(
            assignments
        )
        if self.qc_report != expected_qc_report:
            raise ValueError("Classification QC report is inconsistent.")

        object.__setattr__(self, "m6_context_fingerprint", m6_context_fingerprint)
        object.__setattr__(self, "input_fingerprint", input_fingerprint)
        object.__setattr__(self, "observations", observations)
        object.__setattr__(self, "domain_types", domain_types)
        object.__setattr__(self, "assignments", assignments)
        object.__setattr__(self, "classification_mode", expected_mode)
        object.__setattr__(self, "uses_tracking", False)

    @property
    def observation_count(self) -> int:
        return self.qc_report.observation_count

    @property
    def classified_observation_count(self) -> int:
        return self.qc_report.classified_observation_count

    @property
    def unclassified_observation_count(self) -> int:
        return self.qc_report.unclassified_observation_count

    @property
    def analysis_mode(self) -> Literal["single_range", "compare_ranges"]:
        return self.analysis_scope.analysis_mode

    @property
    def source_view(self) -> str:
        return self.analysis_scope.source_view

    @property
    def ranges(self) -> tuple[MolecularFrameRange, ...]:
        return self.analysis_scope.ranges


def _validate_observation_context(
    observations: tuple[M6DomainTypeObservation, ...],
    *,
    analysis_scope: MolecularFrameRangeAnalysisScope,
    classification_settings: M6DomainTypeClassificationSettings,
    m6_settings: MolecularM6OrientationAnalysisSettings,
    m6_context_fingerprint: str,
) -> None:
    range_identities = {
        (frame_range.name, frame_range.start_frame, frame_range.end_frame)
        for frame_range in analysis_scope.ranges
    }
    expected_m6_fingerprint = m6_settings_fingerprint(m6_settings)
    for observation in observations:
        observation_range = (
            observation.range_name,
            observation.range_start_frame,
            observation.range_end_frame,
        )
        if observation_range not in range_identities:
            raise ValueError("Observation does not belong to the analysis scope.")
        if observation.source_view != analysis_scope.source_view:
            raise ValueError("Observation source_view does not match the analysis scope.")
        if observation.m6_settings_fingerprint != expected_m6_fingerprint:
            raise ValueError("Observation comes from a different M6 settings context.")
        if observation.m6_context_fingerprint != m6_context_fingerprint:
            raise ValueError("Observation comes from a different M6 analysis context.")
        expected_qualification = observation.qualification_for(
            classification_settings
        )
        if expected_qualification != (
            observation.qualification_status,
            observation.unclassified_reason,
        ):
            raise ValueError(
                "Observation qualification does not match classification settings."
            )


def _validate_assignment_for_observation(
    assignment: M6DomainTypeAssignment,
    observation: M6DomainTypeObservation,
) -> None:
    if observation.qualification_status == "unclassified":
        if assignment.status != "unclassified" or (
            assignment.unclassified_reason != observation.unclassified_reason
        ):
            raise ValueError(
                "Pre-unclassified observation must preserve its qualification reason."
            )
    elif assignment.status == "unclassified" and (
        assignment.unclassified_reason != "below_minimum_observations_per_type"
    ):
        raise ValueError(
            "Qualified observations may only be unclassified by minimum type size."
        )


def _domain_type_label(domain_type_id: int) -> str:
    value = domain_type_id + 1
    characters = []
    while value > 0:
        value, remainder = divmod(value - 1, 26)
        characters.append(chr(ord("A") + remainder))
    return "".join(reversed(characters))


def _observation_key(value: object) -> M6DomainTypeObservationKey:
    if not isinstance(value, tuple) or len(value) != 7:
        raise TypeError("observation_key must be a seven-field stable key tuple.")
    range_name = _non_empty_string(value[0], "observation_key range_name")
    range_start = _non_negative_int(value[1], "observation_key range_start_frame")
    range_end = _non_negative_int(value[2], "observation_key range_end_frame")
    frame_index = _non_negative_int(value[3], "observation_key frame_index")
    source_frame_index = _non_negative_int(
        value[4],
        "observation_key source_frame_index",
    )
    ordered_component_id = _non_negative_int(
        value[5],
        "observation_key ordered_component_id",
    )
    domain_id = (
        None
        if value[6] is None
        else _non_negative_int(value[6], "observation_key domain ID")
    )
    if not range_start <= frame_index <= range_end:
        raise ValueError("Observation key frame must lie within its range.")
    return (
        range_name,
        range_start,
        range_end,
        frame_index,
        source_frame_index,
        ordered_component_id,
        domain_id,
    )
