from __future__ import annotations

from dataclasses import dataclass, field
from math import fsum, isclose
from statistics import median
from typing import Literal

from ._m6_domain_type_validation import (
    non_empty_string as _non_empty_string,
    non_negative_float as _non_negative_float,
    non_negative_int as _non_negative_int,
    optional_unit_float as _optional_unit_float,
)
from .frame_ranges import MolecularFrameRange
from .m6_domain_type_aggregates import (
    M6DomainTypeRangeAggregate,
    aggregate_m6_domain_types_for_range,
)
from .m6_domain_type_observations import M6DomainTypeObservation
from .m6_domain_type_results import (
    M6DomainType,
    M6DomainTypeClassificationResult,
)
from .range_analysis import (
    MolecularFrameRangeAnalysis,
    MolecularM6FrameAvailabilityStatus,
)


@dataclass(frozen=True)
class M6SingleRangeFrameMapping:
    """Working/source frame identity and M6 availability for one range row."""

    working_frame_index: int
    source_frame_index: int
    m6_availability_status: MolecularM6FrameAvailabilityStatus
    m6_unavailability_reason: str | None

    def __post_init__(self) -> None:
        working_index = _non_negative_int(
            self.working_frame_index,
            "working_frame_index",
        )
        source_index = _non_negative_int(
            self.source_frame_index,
            "source_frame_index",
        )
        status = self.m6_availability_status
        allowed_statuses = {
            "disabled",
            "available",
            "unavailable_missing_analysis",
            "unavailable_blocking_graph_qc",
        }
        if status not in allowed_statuses:
            raise ValueError("Unsupported M6 availability status.")
        reason = self.m6_unavailability_reason
        if status == "available":
            if reason is not None:
                raise ValueError("Available M6 frame cannot have an unavailable reason.")
        elif status == "disabled":
            if reason is not None:
                raise ValueError("Disabled M6 frame cannot have an unavailable reason.")
        else:
            reason = _non_empty_string(reason, "m6_unavailability_reason")
        object.__setattr__(self, "working_frame_index", working_index)
        object.__setattr__(self, "source_frame_index", source_index)
        object.__setattr__(self, "m6_unavailability_reason", reason)


@dataclass(frozen=True)
class M6SingleRangeDomainTypeRow:
    """One structural type's prototype and statistics in one range."""

    domain_type: M6DomainType
    range_aggregate: M6DomainTypeRangeAggregate
    frames_with_type_percent: float

    def __post_init__(self) -> None:
        if not isinstance(self.domain_type, M6DomainType):
            raise TypeError("domain_type must be M6DomainType.")
        if not isinstance(self.range_aggregate, M6DomainTypeRangeAggregate):
            raise TypeError("range_aggregate must be M6DomainTypeRangeAggregate.")
        if self.range_aggregate.domain_type_id != self.domain_type.domain_type_id:
            raise ValueError("Type prototype and range aggregate IDs must match.")
        if self.range_aggregate.label != self.domain_type.label:
            raise ValueError("Type prototype and range aggregate labels must match.")
        if self.range_aggregate.observation_count <= 0:
            raise ValueError("A summary row requires a present type.")
        available_count = self.range_aggregate.available_frame_count
        if available_count <= 0:
            raise ValueError("A present type requires an available frame.")
        frames_percent = _percent(self.frames_with_type_percent, "frames_with_type_percent")
        expected_percent = (
            100.0 * self.range_aggregate.frames_with_type_count / available_count
        )
        if not isclose(frames_percent, expected_percent, rel_tol=1e-12, abs_tol=1e-12):
            raise ValueError("frames_with_type_percent has the wrong denominator.")
        required_aggregate_values = (
            self.range_aggregate.mean_instances_per_available_frame,
            self.range_aggregate.mean_molecule_fraction_of_valid_representatives,
            self.range_aggregate.mean_domain_coherent_q6,
            self.range_aggregate.mean_molecule_count,
            self.range_aggregate.mean_footprint_area_nm2,
        )
        if any(value is None for value in required_aggregate_values):
            raise ValueError("A present type requires complete aggregate values.")
        object.__setattr__(self, "frames_with_type_percent", frames_percent)

    @property
    def domain_type_id(self) -> int:
        return self.domain_type.domain_type_id

    @property
    def label(self) -> str:
        return self.domain_type.label

    @property
    def prototype_orientation_deg(self) -> float:
        return self.domain_type.prototype_orientation_deg

    @property
    def prototype_bond_length_nm(self) -> float:
        return self.domain_type.prototype_bond_length_nm

    @property
    def orientation_circular_spread_deg(self) -> float:
        return self.domain_type.orientation_circular_spread_deg

    @property
    def bond_length_iqr_nm(self) -> float:
        return self.domain_type.bond_length_iqr_nm

    @property
    def observation_count(self) -> int:
        return self.range_aggregate.observation_count

    @property
    def available_frame_count(self) -> int:
        return self.range_aggregate.available_frame_count

    @property
    def frames_with_type_count(self) -> int:
        return self.range_aggregate.frames_with_type_count

    @property
    def mean_instances_per_available_frame(self) -> float:
        return _required_aggregate_value(
            self.range_aggregate.mean_instances_per_available_frame
        )

    @property
    def mean_molecule_fraction_of_valid_representatives(self) -> float:
        return _required_aggregate_value(
            self.range_aggregate.mean_molecule_fraction_of_valid_representatives
        )

    @property
    def mean_footprint_fraction_of_valid_fov(self) -> float | None:
        return self.range_aggregate.mean_footprint_fraction_of_valid_fov

    @property
    def mean_domain_coherent_q6(self) -> float:
        return _required_aggregate_value(
            self.range_aggregate.mean_domain_coherent_q6
        )

    @property
    def mean_molecule_count(self) -> float:
        return _required_aggregate_value(self.range_aggregate.mean_molecule_count)

    @property
    def mean_footprint_area_nm2(self) -> float:
        return _required_aggregate_value(
            self.range_aggregate.mean_footprint_area_nm2
        )


@dataclass(frozen=True)
class M6SingleRangeDomainTypeSummary:
    """Complete structural-domain-type summary for one real frame range."""

    frame_range: MolecularFrameRange
    source_view: str
    classification_input_fingerprint: str
    frame_mapping: tuple[M6SingleRangeFrameMapping, ...]
    analyzed_frame_count: int
    available_frame_count: int
    valid_representative_fraction_frame_count: int
    valid_fov_fraction_frame_count: int
    frames_with_full_domain_count: int
    frames_with_full_domain_percent: float | None
    mean_full_domains_per_available_frame: float | None
    median_full_domains_per_available_frame: float | None
    max_full_domains_per_available_frame: int | None
    domain_observation_count: int
    domain_type_count: int
    unclassified_observation_count: int
    unclassified_aggregate: M6DomainTypeRangeAggregate
    full_domain_molecule_fraction: float | None
    full_domain_footprint_fraction: float | None
    type_summaries: tuple[M6SingleRangeDomainTypeRow, ...]
    analysis_mode: str = field(
        default="single_range_structural_domain_type_summary",
        init=False,
    )
    uses_tracking: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.frame_range, MolecularFrameRange):
            raise TypeError("frame_range must be MolecularFrameRange.")
        source_view = _non_empty_string(self.source_view, "source_view")
        fingerprint = _non_empty_string(
            self.classification_input_fingerprint,
            "classification_input_fingerprint",
        )
        frame_mapping = tuple(self.frame_mapping)
        if any(not isinstance(value, M6SingleRangeFrameMapping) for value in frame_mapping):
            raise TypeError("frame_mapping must contain frame mapping rows.")
        expected_working_indices = self.frame_range.frame_indices
        if tuple(value.working_frame_index for value in frame_mapping) != (
            expected_working_indices
        ):
            raise ValueError("frame_mapping must cover the range in working order.")
        if len({value.source_frame_index for value in frame_mapping}) != len(frame_mapping):
            raise ValueError("frame_mapping source indices must be unique.")
        analyzed_count = _non_negative_int(
            self.analyzed_frame_count,
            "analyzed_frame_count",
        )
        if analyzed_count != len(frame_mapping):
            raise ValueError("analyzed_frame_count must match frame_mapping.")
        available_count = _non_negative_int(
            self.available_frame_count,
            "available_frame_count",
        )
        actual_available_count = sum(
            value.m6_availability_status == "available" for value in frame_mapping
        )
        if available_count != actual_available_count:
            raise ValueError("available_frame_count must match frame_mapping.")
        representative_count = _bounded_frame_count(
            self.valid_representative_fraction_frame_count,
            "valid_representative_fraction_frame_count",
            available_count,
        )
        valid_fov_count = _bounded_frame_count(
            self.valid_fov_fraction_frame_count,
            "valid_fov_fraction_frame_count",
            available_count,
        )
        frames_with_domain_count = _bounded_frame_count(
            self.frames_with_full_domain_count,
            "frames_with_full_domain_count",
            available_count,
        )
        frames_percent = _optional_percent(
            self.frames_with_full_domain_percent,
            "frames_with_full_domain_percent",
        )
        mean_domains = _optional_non_negative(
            self.mean_full_domains_per_available_frame,
            "mean_full_domains_per_available_frame",
        )
        median_domains = _optional_non_negative(
            self.median_full_domains_per_available_frame,
            "median_full_domains_per_available_frame",
        )
        max_domains = (
            None
            if self.max_full_domains_per_available_frame is None
            else _non_negative_int(
                self.max_full_domains_per_available_frame,
                "max_full_domains_per_available_frame",
            )
        )
        if available_count == 0:
            if any(
                value is not None
                for value in (frames_percent, mean_domains, median_domains, max_domains)
            ):
                raise ValueError("No available frames require undefined frame statistics.")
        else:
            if any(
                value is None
                for value in (frames_percent, mean_domains, median_domains, max_domains)
            ):
                raise ValueError("Available frames require complete frame statistics.")
            expected_percent = 100.0 * frames_with_domain_count / available_count
            if not isclose(frames_percent, expected_percent, rel_tol=1e-12, abs_tol=1e-12):
                raise ValueError("Full-domain frame percent has the wrong denominator.")

        domain_observation_count = _non_negative_int(
            self.domain_observation_count,
            "domain_observation_count",
        )
        domain_type_count = _non_negative_int(
            self.domain_type_count,
            "domain_type_count",
        )
        unclassified_count = _non_negative_int(
            self.unclassified_observation_count,
            "unclassified_observation_count",
        )
        unclassified_aggregate = self.unclassified_aggregate
        if not isinstance(unclassified_aggregate, M6DomainTypeRangeAggregate):
            raise TypeError("unclassified_aggregate must be a range aggregate.")
        if (
            unclassified_aggregate.domain_type_id is not None
            or unclassified_aggregate.label != "Unclassified"
            or unclassified_aggregate.observation_count != unclassified_count
        ):
            raise ValueError("unclassified_aggregate has inconsistent identity or count.")
        if (
            unclassified_aggregate.available_frame_count,
            unclassified_aggregate.valid_representative_fraction_frame_count,
            unclassified_aggregate.valid_fov_fraction_frame_count,
        ) != (available_count, representative_count, valid_fov_count):
            raise ValueError("unclassified_aggregate uses inconsistent denominators.")
        type_summaries = tuple(self.type_summaries)
        if any(not isinstance(value, M6SingleRangeDomainTypeRow) for value in type_summaries):
            raise TypeError("type_summaries must contain type rows.")
        type_ids = tuple(value.domain_type_id for value in type_summaries)
        if type_ids != tuple(sorted(set(type_ids))):
            raise ValueError("Type summary IDs must be unique and ordered.")
        if domain_type_count != len(type_summaries):
            raise ValueError("domain_type_count must match present type rows.")
        classified_observation_count = sum(
            value.observation_count for value in type_summaries
        )
        if classified_observation_count + unclassified_count != (
            domain_observation_count
        ):
            raise ValueError("Domain observation counters are inconsistent.")
        if any(value.available_frame_count != available_count for value in type_summaries):
            raise ValueError("Every type row must use the range available-frame count.")
        if frames_with_domain_count > domain_observation_count:
            raise ValueError("A frame with a domain requires a domain observation.")
        if (domain_observation_count == 0) != (frames_with_domain_count == 0):
            raise ValueError("Domain observations and frame presence are inconsistent.")
        if available_count > 0 and not isclose(
            mean_domains,
            domain_observation_count / available_count,
            rel_tol=1e-12,
            abs_tol=1e-12,
        ):
            raise ValueError("Mean domains per frame has the wrong denominator.")

        molecule_fraction = _optional_unit_float(
            self.full_domain_molecule_fraction,
            "full_domain_molecule_fraction",
        )
        footprint_fraction = _optional_unit_float(
            self.full_domain_footprint_fraction,
            "full_domain_footprint_fraction",
        )
        if (representative_count == 0) != (molecule_fraction is None):
            raise ValueError("Global molecule fraction must match its denominator.")
        if (valid_fov_count == 0) != (footprint_fraction is None):
            raise ValueError("Global footprint fraction must match its denominator.")

        normalized = {
            "source_view": source_view,
            "classification_input_fingerprint": fingerprint,
            "frame_mapping": frame_mapping,
            "analyzed_frame_count": analyzed_count,
            "available_frame_count": available_count,
            "valid_representative_fraction_frame_count": representative_count,
            "valid_fov_fraction_frame_count": valid_fov_count,
            "frames_with_full_domain_count": frames_with_domain_count,
            "frames_with_full_domain_percent": frames_percent,
            "mean_full_domains_per_available_frame": mean_domains,
            "median_full_domains_per_available_frame": median_domains,
            "max_full_domains_per_available_frame": max_domains,
            "domain_observation_count": domain_observation_count,
            "domain_type_count": domain_type_count,
            "unclassified_observation_count": unclassified_count,
            "unclassified_aggregate": unclassified_aggregate,
            "full_domain_molecule_fraction": molecule_fraction,
            "full_domain_footprint_fraction": footprint_fraction,
            "type_summaries": type_summaries,
        }
        for field_name, value in normalized.items():
            object.__setattr__(self, field_name, value)
        object.__setattr__(
            self,
            "analysis_mode",
            "single_range_structural_domain_type_summary",
        )
        object.__setattr__(self, "uses_tracking", False)

    @property
    def range_name(self) -> str:
        return self.frame_range.name


def build_m6_single_range_domain_type_summary(
    classification: M6DomainTypeClassificationResult,
    range_analysis: MolecularFrameRangeAnalysis,
) -> M6SingleRangeDomainTypeSummary:
    """Build one range summary from existing M6 frames and shared type labels."""

    range_aggregates = aggregate_m6_domain_types_for_range(
        classification,
        range_analysis,
        component_scope="full_domain",
    )
    available_frame_aggregates = tuple(
        frame_result.m6_orientation_analysis.frame_aggregates
        for frame_result in range_analysis.frame_results
        if frame_result.m6_orientation_availability_status == "available"
    )
    full_domain_counts = tuple(
        _non_negative_int(value.full_domain_count, "full_domain_count")
        for value in available_frame_aggregates
    )
    domain_observations = tuple(
        observation
        for observation in classification.observations
        if observation.component_type == "full_domain"
        and _belongs_to_range(observation, range_analysis.frame_range)
    )
    frame_result_by_index = {
        frame_result.frame_index: frame_result
        for frame_result in range_analysis.frame_results
    }
    domain_observation_counts_by_frame = {
        frame_result.frame_index: 0
        for frame_result in range_analysis.frame_results
    }
    for observation in domain_observations:
        frame_result = frame_result_by_index[observation.frame_index]
        if observation.source_frame_index != frame_result.source_frame_index:
            raise ValueError("Domain observation uses a different source frame.")
        domain_observation_counts_by_frame[observation.frame_index] += 1
    for frame_result in range_analysis.frame_results:
        expected_count = (
            frame_result.m6_orientation_analysis.frame_aggregates.full_domain_count
            if frame_result.m6_orientation_availability_status == "available"
            else 0
        )
        if domain_observation_counts_by_frame[frame_result.frame_index] != (
            expected_count
        ):
            raise ValueError(
                "Full-domain observations disagree with per-frame M6 counts."
            )

    molecule_fractions = tuple(
        value.full_domain_molecule_fraction
        for value in available_frame_aggregates
        if value.full_domain_molecule_fraction is not None
    )
    footprint_fractions = tuple(
        value.full_domain_footprint_fraction
        for value in available_frame_aggregates
        if value.full_domain_footprint_fraction is not None
    )
    if len(molecule_fractions) != (
        range_aggregates.valid_representative_fraction_frame_count
    ):
        raise ValueError("Global molecule-fraction denominator is inconsistent.")
    if len(footprint_fractions) != range_aggregates.valid_fov_fraction_frame_count:
        raise ValueError("Global footprint-fraction denominator is inconsistent.")

    domain_type_by_id = {
        domain_type.domain_type_id: domain_type
        for domain_type in classification.domain_types
    }
    type_summaries = tuple(
        _type_summary(
            domain_type_by_id[aggregate.domain_type_id],
            aggregate,
        )
        for aggregate in range_aggregates.type_aggregates
        if aggregate.observation_count > 0 and aggregate.domain_type_id is not None
    )
    available_count = range_aggregates.available_frame_count
    frames_with_domain_count = sum(value > 0 for value in full_domain_counts)
    return M6SingleRangeDomainTypeSummary(
        frame_range=range_analysis.frame_range,
        source_view=range_analysis.source_view,
        classification_input_fingerprint=classification.input_fingerprint,
        frame_mapping=tuple(
            M6SingleRangeFrameMapping(
                working_frame_index=frame_result.frame_index,
                source_frame_index=frame_result.source_frame_index,
                m6_availability_status=(
                    frame_result.m6_orientation_availability_status
                ),
                m6_unavailability_reason=(
                    frame_result.m6_orientation_unavailability_reason
                ),
            )
            for frame_result in range_analysis.frame_results
        ),
        analyzed_frame_count=range_aggregates.analyzed_frame_count,
        available_frame_count=available_count,
        valid_representative_fraction_frame_count=(
            range_aggregates.valid_representative_fraction_frame_count
        ),
        valid_fov_fraction_frame_count=(
            range_aggregates.valid_fov_fraction_frame_count
        ),
        frames_with_full_domain_count=frames_with_domain_count,
        frames_with_full_domain_percent=(
            None
            if available_count == 0
            else 100.0 * frames_with_domain_count / available_count
        ),
        mean_full_domains_per_available_frame=_mean(full_domain_counts),
        median_full_domains_per_available_frame=(
            None if not full_domain_counts else float(median(full_domain_counts))
        ),
        max_full_domains_per_available_frame=(
            None if not full_domain_counts else max(full_domain_counts)
        ),
        domain_observation_count=len(domain_observations),
        domain_type_count=len(type_summaries),
        unclassified_observation_count=(
            range_aggregates.unclassified_aggregate.observation_count
        ),
        unclassified_aggregate=range_aggregates.unclassified_aggregate,
        full_domain_molecule_fraction=_mean(molecule_fractions),
        full_domain_footprint_fraction=_mean(footprint_fractions),
        type_summaries=type_summaries,
    )


def _type_summary(
    domain_type: M6DomainType,
    aggregate: M6DomainTypeRangeAggregate,
) -> M6SingleRangeDomainTypeRow:
    available_count = aggregate.available_frame_count
    if available_count <= 0:
        raise ValueError("A present type requires an available frame.")
    return M6SingleRangeDomainTypeRow(
        domain_type=domain_type,
        range_aggregate=aggregate,
        frames_with_type_percent=(
            100.0 * aggregate.frames_with_type_count / available_count
        ),
    )


def _belongs_to_range(
    observation: M6DomainTypeObservation,
    frame_range: MolecularFrameRange,
) -> bool:
    return (
        observation.range_name == frame_range.name
        and observation.range_start_frame == frame_range.start_frame
        and observation.range_end_frame == frame_range.end_frame
    )


def _mean(values: tuple[int | float, ...]) -> float | None:
    if not values:
        return None
    return fsum(float(value) for value in values) / len(values)


def _percent(value: object, field_name: str) -> float:
    normalized = _non_negative_float(value, field_name)
    if normalized > 100.0:
        raise ValueError(f"{field_name} must not exceed 100.")
    return normalized


def _optional_percent(value: object, field_name: str) -> float | None:
    return None if value is None else _percent(value, field_name)


def _optional_non_negative(value: object, field_name: str) -> float | None:
    return None if value is None else _non_negative_float(value, field_name)


def _bounded_frame_count(value: object, field_name: str, upper_bound: int) -> int:
    normalized = _non_negative_int(value, field_name)
    if normalized > upper_bound:
        raise ValueError(f"{field_name} cannot exceed available_frame_count.")
    return normalized


def _required_aggregate_value(value: float | None) -> float:
    if value is None:
        raise RuntimeError("Validated type aggregate value is unavailable.")
    return value
