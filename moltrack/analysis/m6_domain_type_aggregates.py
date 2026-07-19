from __future__ import annotations

from dataclasses import dataclass
from math import fsum, isclose

from ._m6_context_fingerprint import m6_context_fingerprint
from ._m6_domain_type_validation import (
    non_empty_string as _non_empty_string,
    non_negative_float as _non_negative_float,
    non_negative_int as _non_negative_int,
    optional_non_negative_float as _optional_non_negative_float,
    optional_unit_float as _optional_unit_float,
)
from .frame_ranges import MolecularFrameRange
from .m6_domain_type_observations import M6DomainTypeObservation
from .m6_domain_type_results import M6DomainTypeClassificationResult
from .range_analysis import MolecularFrameRangeAnalysis


@dataclass(frozen=True)
class _RangeFrameDenominators:
    available_frames: frozenset[int]
    valid_representative_frames: frozenset[int]
    valid_fov_frames: frozenset[int]

    def __post_init__(self) -> None:
        available_frames = _frame_index_set(
            self.available_frames,
            "available_frames",
        )
        representative_frames = _frame_index_set(
            self.valid_representative_frames,
            "valid_representative_frames",
        )
        valid_fov_frames = _frame_index_set(
            self.valid_fov_frames,
            "valid_fov_frames",
        )
        if not representative_frames <= available_frames:
            raise ValueError("Representative frames must be available.")
        if not valid_fov_frames <= available_frames:
            raise ValueError("Valid-FOV frames must be available.")
        object.__setattr__(self, "available_frames", available_frames)
        object.__setattr__(
            self,
            "valid_representative_frames",
            representative_frames,
        )
        object.__setattr__(self, "valid_fov_frames", valid_fov_frames)

    @property
    def counts(self) -> tuple[int, int, int]:
        return (
            len(self.available_frames),
            len(self.valid_representative_frames),
            len(self.valid_fov_frames),
        )


@dataclass(frozen=True)
class M6DomainTypeRangeAggregate:
    """One type's frame-normalized statistics within one selected range."""

    domain_type_id: int | None
    label: str
    available_frame_count: int
    valid_representative_fraction_frame_count: int
    valid_fov_fraction_frame_count: int
    observation_count: int
    frames_with_type_count: int
    mean_instances_per_available_frame: float | None
    mean_molecule_fraction_of_valid_representatives: float | None
    mean_footprint_fraction_of_valid_fov: float | None
    mean_domain_coherent_q6: float | None
    mean_molecule_count: float | None
    mean_footprint_area_nm2: float | None

    def __post_init__(self) -> None:
        if self.domain_type_id is None:
            domain_type_id = None
        else:
            domain_type_id = _non_negative_int(
                self.domain_type_id,
                "domain_type_id",
            )
        label = _non_empty_string(self.label, "label")
        available_count = _non_negative_int(
            self.available_frame_count,
            "available_frame_count",
        )
        representative_count = _non_negative_int(
            self.valid_representative_fraction_frame_count,
            "valid_representative_fraction_frame_count",
        )
        valid_fov_count = _non_negative_int(
            self.valid_fov_fraction_frame_count,
            "valid_fov_fraction_frame_count",
        )
        if representative_count > available_count or valid_fov_count > available_count:
            raise ValueError("Fraction denominator counts cannot exceed available frames.")
        observation_count = _non_negative_int(
            self.observation_count,
            "observation_count",
        )
        frames_with_type_count = _non_negative_int(
            self.frames_with_type_count,
            "frames_with_type_count",
        )
        if frames_with_type_count > available_count:
            raise ValueError("frames_with_type_count cannot exceed available frames.")
        if frames_with_type_count > observation_count:
            raise ValueError("A frame with a type requires at least one observation.")
        if (observation_count == 0) != (frames_with_type_count == 0):
            raise ValueError("Observation and frame-presence counts must agree.")

        mean_instances = _optional_non_negative_float(
            self.mean_instances_per_available_frame,
            "mean_instances_per_available_frame",
        )
        if available_count == 0:
            if mean_instances is not None:
                raise ValueError("No available frames require an undefined instance mean.")
        elif mean_instances is None or not isclose(
            mean_instances,
            observation_count / available_count,
            rel_tol=1e-12,
            abs_tol=1e-12,
        ):
            raise ValueError("Instance mean must use all available frames.")

        molecule_fraction = _optional_unit_float(
            self.mean_molecule_fraction_of_valid_representatives,
            "mean_molecule_fraction_of_valid_representatives",
        )
        footprint_fraction = _optional_unit_float(
            self.mean_footprint_fraction_of_valid_fov,
            "mean_footprint_fraction_of_valid_fov",
        )
        if (representative_count == 0) != (molecule_fraction is None):
            raise ValueError("Molecule fraction availability must match its denominator.")
        if (valid_fov_count == 0) != (footprint_fraction is None):
            raise ValueError("Footprint fraction availability must match its denominator.")
        if observation_count == 0 and any(
            value not in {None, 0.0}
            for value in (molecule_fraction, footprint_fraction)
        ):
            raise ValueError("An absent type cannot have nonzero fractions.")

        coherent_q6 = _optional_unit_float(
            self.mean_domain_coherent_q6,
            "mean_domain_coherent_q6",
        )
        mean_molecule_count = _optional_non_negative_float(
            self.mean_molecule_count,
            "mean_molecule_count",
        )
        mean_footprint_area = _optional_non_negative_float(
            self.mean_footprint_area_nm2,
            "mean_footprint_area_nm2",
        )
        observation_means = (
            coherent_q6,
            mean_molecule_count,
            mean_footprint_area,
        )
        if observation_count == 0:
            if any(value is not None for value in observation_means):
                raise ValueError("An absent type cannot have observation means.")
        elif any(value is None for value in observation_means):
            raise ValueError("Observed types require all observation means.")

        object.__setattr__(self, "domain_type_id", domain_type_id)
        object.__setattr__(self, "label", label)
        object.__setattr__(self, "available_frame_count", available_count)
        object.__setattr__(
            self,
            "valid_representative_fraction_frame_count",
            representative_count,
        )
        object.__setattr__(
            self,
            "valid_fov_fraction_frame_count",
            valid_fov_count,
        )
        object.__setattr__(self, "observation_count", observation_count)
        object.__setattr__(
            self,
            "frames_with_type_count",
            frames_with_type_count,
        )
        object.__setattr__(
            self,
            "mean_instances_per_available_frame",
            mean_instances,
        )
        object.__setattr__(
            self,
            "mean_molecule_fraction_of_valid_representatives",
            molecule_fraction,
        )
        object.__setattr__(
            self,
            "mean_footprint_fraction_of_valid_fov",
            footprint_fraction,
        )
        object.__setattr__(self, "mean_domain_coherent_q6", coherent_q6)
        object.__setattr__(self, "mean_molecule_count", mean_molecule_count)
        object.__setattr__(
            self,
            "mean_footprint_area_nm2",
            mean_footprint_area,
        )


@dataclass(frozen=True)
class M6DomainTypeRangeAggregates:
    """All classified types and unclassified observations for one range."""

    frame_range: MolecularFrameRange
    source_view: str
    classification_input_fingerprint: str
    analyzed_frame_count: int
    available_frame_count: int
    valid_representative_fraction_frame_count: int
    valid_fov_fraction_frame_count: int
    type_aggregates: tuple[M6DomainTypeRangeAggregate, ...]
    unclassified_aggregate: M6DomainTypeRangeAggregate

    def __post_init__(self) -> None:
        if not isinstance(self.frame_range, MolecularFrameRange):
            raise TypeError("frame_range must be MolecularFrameRange.")
        source_view = _non_empty_string(self.source_view, "source_view")
        fingerprint = _non_empty_string(
            self.classification_input_fingerprint,
            "classification_input_fingerprint",
        )
        analyzed_count = _non_negative_int(
            self.analyzed_frame_count,
            "analyzed_frame_count",
        )
        if analyzed_count != len(self.frame_range.frame_indices):
            raise ValueError("analyzed_frame_count must cover the complete range.")
        available_count = _non_negative_int(
            self.available_frame_count,
            "available_frame_count",
        )
        representative_count = _non_negative_int(
            self.valid_representative_fraction_frame_count,
            "valid_representative_fraction_frame_count",
        )
        valid_fov_count = _non_negative_int(
            self.valid_fov_fraction_frame_count,
            "valid_fov_fraction_frame_count",
        )
        if not 0 <= representative_count <= available_count <= analyzed_count:
            raise ValueError("Representative and available frame counts are inconsistent.")
        if valid_fov_count > available_count:
            raise ValueError("Valid-FOV frame count cannot exceed available frames.")

        type_aggregates = tuple(self.type_aggregates)
        if any(
            not isinstance(value, M6DomainTypeRangeAggregate)
            for value in type_aggregates
        ):
            raise TypeError("type_aggregates must contain range aggregates.")
        if tuple(value.domain_type_id for value in type_aggregates) != tuple(
            range(len(type_aggregates))
        ):
            raise ValueError("Type aggregates must be contiguous and ordered by type ID.")
        if any(value.label == "Unclassified" for value in type_aggregates):
            raise ValueError("Classified type aggregates cannot use Unclassified label.")
        if not isinstance(
            self.unclassified_aggregate,
            M6DomainTypeRangeAggregate,
        ):
            raise TypeError("unclassified_aggregate must be a range aggregate.")
        if (
            self.unclassified_aggregate.domain_type_id is not None
            or self.unclassified_aggregate.label != "Unclassified"
        ):
            raise ValueError("The unclassified aggregate requires its reserved identity.")
        all_aggregates = (*type_aggregates, self.unclassified_aggregate)
        expected_denominators = (
            available_count,
            representative_count,
            valid_fov_count,
        )
        if any(
            (
                value.available_frame_count,
                value.valid_representative_fraction_frame_count,
                value.valid_fov_fraction_frame_count,
            )
            != expected_denominators
            for value in all_aggregates
        ):
            raise ValueError("Every type aggregate must use the range denominators.")

        object.__setattr__(self, "source_view", source_view)
        object.__setattr__(
            self,
            "classification_input_fingerprint",
            fingerprint,
        )
        object.__setattr__(self, "analyzed_frame_count", analyzed_count)
        object.__setattr__(self, "available_frame_count", available_count)
        object.__setattr__(
            self,
            "valid_representative_fraction_frame_count",
            representative_count,
        )
        object.__setattr__(
            self,
            "valid_fov_fraction_frame_count",
            valid_fov_count,
        )
        object.__setattr__(self, "type_aggregates", type_aggregates)


def aggregate_m6_domain_types_for_range(
    classification: M6DomainTypeClassificationResult,
    range_analysis: MolecularFrameRangeAnalysis,
) -> M6DomainTypeRangeAggregates:
    """Aggregate shared structural types within one range without tracking."""

    if not isinstance(classification, M6DomainTypeClassificationResult):
        raise TypeError("classification must be M6DomainTypeClassificationResult.")
    if not isinstance(range_analysis, MolecularFrameRangeAnalysis):
        raise TypeError("range_analysis must be MolecularFrameRangeAnalysis.")
    frame_range = range_analysis.frame_range
    if frame_range not in classification.ranges:
        raise ValueError("range_analysis does not belong to the classification scope.")
    if range_analysis.source_view != classification.source_view:
        raise ValueError("range_analysis source_view does not match classification.")

    denominators = _range_frame_denominators(
        range_analysis,
        expected_m6_context_fingerprint=classification.m6_context_fingerprint,
    )
    range_observations = tuple(
        observation
        for observation in classification.observations
        if _observation_belongs_to_range(observation, frame_range)
    )
    _validate_observation_denominators(
        range_observations,
        denominators=denominators,
    )
    assignment_by_key = {
        assignment.observation_key: assignment
        for assignment in classification.assignments
    }
    observations_by_type = {
        domain_type.domain_type_id: []
        for domain_type in classification.domain_types
    }
    unclassified_observations = []
    for observation in range_observations:
        assignment = assignment_by_key[observation.stable_key]
        if assignment.status == "classified":
            type_id = assignment.domain_type_id
            if type_id is None:  # guarded by M6DomainTypeAssignment
                raise ValueError("Classified assignment is missing its type ID.")
            observations_by_type[type_id].append(observation)
        else:
            unclassified_observations.append(observation)

    type_aggregates = tuple(
        _aggregate_observations(
            observations_by_type[domain_type.domain_type_id],
            domain_type_id=domain_type.domain_type_id,
            label=domain_type.label,
            denominators=denominators,
        )
        for domain_type in classification.domain_types
    )
    return M6DomainTypeRangeAggregates(
        frame_range=frame_range,
        source_view=range_analysis.source_view,
        classification_input_fingerprint=classification.input_fingerprint,
        analyzed_frame_count=len(frame_range.frame_indices),
        available_frame_count=denominators.counts[0],
        valid_representative_fraction_frame_count=denominators.counts[1],
        valid_fov_fraction_frame_count=denominators.counts[2],
        type_aggregates=type_aggregates,
        unclassified_aggregate=_aggregate_observations(
            unclassified_observations,
            domain_type_id=None,
            label="Unclassified",
            denominators=denominators,
        ),
    )


def _range_frame_denominators(
    range_analysis: MolecularFrameRangeAnalysis,
    *,
    expected_m6_context_fingerprint: str,
) -> _RangeFrameDenominators:
    expected_indices = range_analysis.frame_range.frame_indices
    actual_indices = tuple(result.frame_index for result in range_analysis.frame_results)
    if actual_indices != expected_indices:
        raise ValueError("range_analysis frame results must cover the range in order.")
    available_frames: set[int] = set()
    representative_frames: set[int] = set()
    valid_fov_frames: set[int] = set()
    allowed_statuses = {
        "disabled",
        "available",
        "unavailable_missing_analysis",
        "unavailable_blocking_graph_qc",
    }
    for frame_result in range_analysis.frame_results:
        if frame_result.source_view != range_analysis.source_view:
            raise ValueError("Frame source_view does not match range_analysis.")
        status = frame_result.m6_orientation_availability_status
        if status not in allowed_statuses:
            raise ValueError("Unsupported M6 frame availability status.")
        if status != "available":
            continue
        analysis = frame_result.m6_orientation_analysis
        if analysis is None:
            raise ValueError("Available M6 frame requires an analysis result.")
        if m6_context_fingerprint(analysis) != expected_m6_context_fingerprint:
            raise ValueError("Available frame uses a different M6 context.")
        aggregates = analysis.frame_aggregates
        representative_count = _non_negative_int(
            aggregates.valid_representative_count,
            "valid_representative_count",
        )
        valid_fov_area = _non_negative_float(
            aggregates.valid_fov_area_nm2,
            "valid_fov_area_nm2",
        )
        available_frames.add(frame_result.frame_index)
        if representative_count > 0:
            representative_frames.add(frame_result.frame_index)
        if valid_fov_area > 0.0:
            valid_fov_frames.add(frame_result.frame_index)
    return _RangeFrameDenominators(
        available_frames=frozenset(available_frames),
        valid_representative_frames=frozenset(representative_frames),
        valid_fov_frames=frozenset(valid_fov_frames),
    )


def _validate_observation_denominators(
    observations: tuple[M6DomainTypeObservation, ...],
    *,
    denominators: _RangeFrameDenominators,
) -> None:
    for observation in observations:
        if observation.frame_index not in denominators.available_frames:
            raise ValueError("A classification observation requires available M6.")
        if observation.frame_index not in denominators.valid_representative_frames:
            raise ValueError("A domain observation requires valid representatives.")
        has_valid_fov = observation.frame_index in denominators.valid_fov_frames
        has_footprint_fraction = (
            observation.footprint_fraction_of_valid_fov is not None
        )
        if has_valid_fov != has_footprint_fraction:
            raise ValueError("Observation footprint fraction disagrees with valid FOV.")


def _aggregate_observations(
    observations: list[M6DomainTypeObservation],
    *,
    domain_type_id: int | None,
    label: str,
    denominators: _RangeFrameDenominators,
) -> M6DomainTypeRangeAggregate:
    available_count, representative_count, valid_fov_count = denominators.counts
    observation_count = len(observations)
    frames_with_type_count = len(
        {observation.frame_index for observation in observations}
    )
    molecule_fraction_sum = fsum(
        observation.molecule_fraction_of_valid_representatives
        for observation in observations
        if observation.frame_index in denominators.valid_representative_frames
    )
    footprint_fraction_sum = fsum(
        observation.footprint_fraction_of_valid_fov
        for observation in observations
        if observation.frame_index in denominators.valid_fov_frames
        and observation.footprint_fraction_of_valid_fov is not None
    )
    return M6DomainTypeRangeAggregate(
        domain_type_id=domain_type_id,
        label=label,
        available_frame_count=available_count,
        valid_representative_fraction_frame_count=representative_count,
        valid_fov_fraction_frame_count=valid_fov_count,
        observation_count=observation_count,
        frames_with_type_count=frames_with_type_count,
        mean_instances_per_available_frame=(
            None if available_count == 0 else observation_count / available_count
        ),
        mean_molecule_fraction_of_valid_representatives=(
            None
            if representative_count == 0
            else molecule_fraction_sum / representative_count
        ),
        mean_footprint_fraction_of_valid_fov=(
            None
            if valid_fov_count == 0
            else footprint_fraction_sum / valid_fov_count
        ),
        mean_domain_coherent_q6=_observation_mean(
            observations,
            "domain_coherent_q6",
        ),
        mean_molecule_count=_observation_mean(observations, "molecule_count"),
        mean_footprint_area_nm2=_observation_mean(
            observations,
            "footprint_area_nm2",
        ),
    )


def _observation_mean(
    observations: list[M6DomainTypeObservation],
    field_name: str,
) -> float | None:
    if not observations:
        return None
    return fsum(float(getattr(value, field_name)) for value in observations) / len(
        observations
    )


def _observation_belongs_to_range(
    observation: M6DomainTypeObservation,
    frame_range: MolecularFrameRange,
) -> bool:
    return (
        observation.range_name == frame_range.name
        and observation.range_start_frame == frame_range.start_frame
        and observation.range_end_frame == frame_range.end_frame
    )


def _frame_index_set(values: object, field_name: str) -> frozenset[int]:
    try:
        normalized = frozenset(values)
    except TypeError as exc:
        raise TypeError(f"{field_name} must be an iterable of frame indices.") from exc
    for value in normalized:
        _non_negative_int(value, field_name)
    return normalized
