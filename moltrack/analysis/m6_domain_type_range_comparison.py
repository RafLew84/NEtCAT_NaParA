from __future__ import annotations

from dataclasses import dataclass, field, fields
from math import isclose, isfinite
from typing import Literal

from .frame_ranges import MolecularFrameRange
from .m6_domain_type_aggregates import (
    M6DomainTypeRangeAggregate,
    aggregate_m6_domain_types_for_range,
)
from .m6_domain_type_results import (
    M6DomainType,
    M6DomainTypeClassificationResult,
)
from .m6_single_range_domain_type_summary import (
    M6SingleRangeDomainTypeSummary,
    M6SingleRangeFrameMapping,
    build_m6_single_range_domain_type_summary,
)
from .range_analysis import MolecularFrameRangeAnalysis


@dataclass(frozen=True)
class M6DomainTypeRangeSide:
    """One shared type's frame-normalized values in one comparison range."""

    range_aggregate: M6DomainTypeRangeAggregate
    frames_with_type_percent: float | None

    def __post_init__(self) -> None:
        if not isinstance(self.range_aggregate, M6DomainTypeRangeAggregate):
            raise TypeError("range_aggregate must be M6DomainTypeRangeAggregate.")
        available_count = self.range_aggregate.available_frame_count
        percent = _optional_finite_float(
            self.frames_with_type_percent,
            "frames_with_type_percent",
        )
        if available_count == 0:
            if percent is not None:
                raise ValueError("No available frames require undefined type presence.")
        else:
            expected = 100.0 * self.frames_with_type_count / available_count
            if percent is None or not isclose(
                percent,
                expected,
                rel_tol=1e-12,
                abs_tol=1e-12,
            ):
                raise ValueError("frames_with_type_percent has the wrong denominator.")
        object.__setattr__(self, "frames_with_type_percent", percent)

    @property
    def domain_instance_count(self) -> int:
        return self.range_aggregate.observation_count

    @property
    def frames_with_type_count(self) -> int:
        return self.range_aggregate.frames_with_type_count

    @property
    def mean_domain_instances_per_available_frame(self) -> float | None:
        return self.range_aggregate.mean_instances_per_available_frame

    @property
    def mean_molecule_fraction(self) -> float | None:
        return self.range_aggregate.mean_molecule_fraction_of_valid_representatives

    @property
    def mean_footprint_fraction(self) -> float | None:
        return self.range_aggregate.mean_footprint_fraction_of_valid_fov

    @property
    def mean_domain_coherent_q6(self) -> float | None:
        return self.range_aggregate.mean_domain_coherent_q6

    @property
    def mean_molecule_count(self) -> float | None:
        return self.range_aggregate.mean_molecule_count

    @property
    def mean_footprint_area_nm2(self) -> float | None:
        return self.range_aggregate.mean_footprint_area_nm2


@dataclass(frozen=True)
class M6DomainTypeRangeDeltas:
    """Second-minus-first differences for one shared structural type."""

    domain_instance_count: int
    frames_with_type_count: int
    frames_with_type_percentage_points: float | None
    mean_domain_instances_per_available_frame: float | None
    mean_molecule_fraction_percentage_points: float | None
    mean_footprint_fraction_percentage_points: float | None
    mean_domain_coherent_q6: float | None
    mean_molecule_count: float | None
    mean_footprint_area_nm2: float | None

    def __post_init__(self) -> None:
        for field_name in ("domain_instance_count", "frames_with_type_count"):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{field_name} must be an integer.")
        for field_name in (
            "frames_with_type_percentage_points",
            "mean_domain_instances_per_available_frame",
            "mean_molecule_fraction_percentage_points",
            "mean_footprint_fraction_percentage_points",
            "mean_domain_coherent_q6",
            "mean_molecule_count",
            "mean_footprint_area_nm2",
        ):
            object.__setattr__(
                self,
                field_name,
                _optional_finite_float(getattr(self, field_name), field_name),
            )


@dataclass(frozen=True)
class M6DomainTypeRangeComparisonRow:
    """One jointly classified domain type shown in both ranges."""

    domain_type: M6DomainType
    first: M6DomainTypeRangeSide
    second: M6DomainTypeRangeSide
    deltas: M6DomainTypeRangeDeltas

    def __post_init__(self) -> None:
        if not isinstance(self.domain_type, M6DomainType):
            raise TypeError("domain_type must be M6DomainType.")
        if not isinstance(self.first, M6DomainTypeRangeSide):
            raise TypeError("first must be M6DomainTypeRangeSide.")
        if not isinstance(self.second, M6DomainTypeRangeSide):
            raise TypeError("second must be M6DomainTypeRangeSide.")
        if not isinstance(self.deltas, M6DomainTypeRangeDeltas):
            raise TypeError("deltas must be M6DomainTypeRangeDeltas.")
        expected_identity = (self.domain_type.domain_type_id, self.domain_type.label)
        for side in (self.first, self.second):
            actual_identity = (
                side.range_aggregate.domain_type_id,
                side.range_aggregate.label,
            )
            if actual_identity != expected_identity:
                raise ValueError("Both range sides must describe the shared type.")
        expected_deltas = _range_deltas(self.first, self.second)
        if not _deltas_equal(self.deltas, expected_deltas):
            raise ValueError("Range deltas must use second-minus-first values.")

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


@dataclass(frozen=True)
class M6DomainTypeRangeComparison:
    """UI-ready table data for two jointly classified M6 frame ranges."""

    first_summary: M6SingleRangeDomainTypeSummary
    second_summary: M6SingleRangeDomainTypeSummary
    rows: tuple[M6DomainTypeRangeComparisonRow, ...]
    direction: Literal["second_minus_first"] = field(
        default="second_minus_first",
        init=False,
    )
    analysis_mode: Literal["joint_structural_domain_type_range_comparison"] = field(
        default="joint_structural_domain_type_range_comparison",
        init=False,
    )
    uses_tracking: bool = field(default=False, init=False)
    domain_type_identity: Literal["shared_structural_type"] = field(
        default="shared_structural_type",
        init=False,
    )
    domain_instance_identity: Literal[
        "one_full_m6_domain_component_in_one_frame"
    ] = field(
        default="one_full_m6_domain_component_in_one_frame",
        init=False,
    )
    local_m6_domain_id_scope: Literal["frame_local"] = field(
        default="frame_local",
        init=False,
    )

    def __post_init__(self) -> None:
        if not isinstance(self.first_summary, M6SingleRangeDomainTypeSummary):
            raise TypeError("first_summary must be a single-range summary.")
        if not isinstance(self.second_summary, M6SingleRangeDomainTypeSummary):
            raise TypeError("second_summary must be a single-range summary.")
        if self.first_summary.frame_range == self.second_summary.frame_range:
            raise ValueError("Comparison summaries must describe distinct ranges.")
        if self.first_summary.source_view != self.second_summary.source_view:
            raise ValueError("Comparison summaries must use one source view.")
        if (
            self.first_summary.classification_input_fingerprint
            != self.second_summary.classification_input_fingerprint
        ):
            raise ValueError("Comparison summaries must use one classification.")
        rows = tuple(self.rows)
        if any(not isinstance(row, M6DomainTypeRangeComparisonRow) for row in rows):
            raise TypeError("rows must contain range comparison rows.")
        if tuple(row.domain_type_id for row in rows) != tuple(range(len(rows))):
            raise ValueError("Comparison rows must cover ordered shared type IDs.")
        _validate_sides_against_summary(
            tuple(row.first for row in rows),
            self.first_summary,
            side_name="first",
        )
        _validate_sides_against_summary(
            tuple(row.second for row in rows),
            self.second_summary,
            side_name="second",
        )
        object.__setattr__(self, "rows", rows)
        object.__setattr__(self, "direction", "second_minus_first")
        object.__setattr__(
            self,
            "analysis_mode",
            "joint_structural_domain_type_range_comparison",
        )
        object.__setattr__(self, "uses_tracking", False)
        object.__setattr__(self, "domain_type_identity", "shared_structural_type")
        object.__setattr__(
            self,
            "domain_instance_identity",
            "one_full_m6_domain_component_in_one_frame",
        )
        object.__setattr__(self, "local_m6_domain_id_scope", "frame_local")

    @property
    def first_range(self) -> MolecularFrameRange:
        return self.first_summary.frame_range

    @property
    def second_range(self) -> MolecularFrameRange:
        return self.second_summary.frame_range

    @property
    def first_range_name(self) -> str:
        return self.first_summary.range_name

    @property
    def second_range_name(self) -> str:
        return self.second_summary.range_name

    @property
    def source_view(self) -> str:
        return self.first_summary.source_view

    @property
    def classification_input_fingerprint(self) -> str:
        return self.first_summary.classification_input_fingerprint

    @property
    def first_frame_mapping(self) -> tuple[M6SingleRangeFrameMapping, ...]:
        return self.first_summary.frame_mapping

    @property
    def second_frame_mapping(self) -> tuple[M6SingleRangeFrameMapping, ...]:
        return self.second_summary.frame_mapping


def build_m6_domain_type_range_comparison(
    classification: M6DomainTypeClassificationResult,
    first_analysis: MolecularFrameRangeAnalysis,
    second_analysis: MolecularFrameRangeAnalysis,
) -> M6DomainTypeRangeComparison:
    """Build complete before/after table data without cross-frame tracking."""

    if not isinstance(classification, M6DomainTypeClassificationResult):
        raise TypeError("classification must be M6DomainTypeClassificationResult.")
    if not isinstance(first_analysis, MolecularFrameRangeAnalysis):
        raise TypeError("first_analysis must be MolecularFrameRangeAnalysis.")
    if not isinstance(second_analysis, MolecularFrameRangeAnalysis):
        raise TypeError("second_analysis must be MolecularFrameRangeAnalysis.")
    if classification.analysis_mode != "compare_ranges":
        raise ValueError("Range comparison requires a joint two-range classification.")
    expected_ranges = classification.analysis_scope.comparison_ranges
    actual_ranges = (first_analysis.frame_range, second_analysis.frame_range)
    if actual_ranges != expected_ranges:
        raise ValueError("Analyses must follow the classification range order.")

    first_summary = build_m6_single_range_domain_type_summary(
        classification,
        first_analysis,
    )
    second_summary = build_m6_single_range_domain_type_summary(
        classification,
        second_analysis,
    )
    first_aggregates = aggregate_m6_domain_types_for_range(
        classification,
        first_analysis,
        component_scope="full_domain",
    )
    second_aggregates = aggregate_m6_domain_types_for_range(
        classification,
        second_analysis,
        component_scope="full_domain",
    )
    rows = tuple(
        _comparison_row(domain_type, first_aggregate, second_aggregate)
        for domain_type, first_aggregate, second_aggregate in zip(
            classification.domain_types,
            first_aggregates.type_aggregates,
            second_aggregates.type_aggregates,
            strict=True,
        )
    )
    return M6DomainTypeRangeComparison(
        first_summary=first_summary,
        second_summary=second_summary,
        rows=rows,
    )


def _comparison_row(
    domain_type: M6DomainType,
    first_aggregate: M6DomainTypeRangeAggregate,
    second_aggregate: M6DomainTypeRangeAggregate,
) -> M6DomainTypeRangeComparisonRow:
    first = _range_side(first_aggregate)
    second = _range_side(second_aggregate)
    return M6DomainTypeRangeComparisonRow(
        domain_type=domain_type,
        first=first,
        second=second,
        deltas=_range_deltas(first, second),
    )


def _range_side(aggregate: M6DomainTypeRangeAggregate) -> M6DomainTypeRangeSide:
    available_count = aggregate.available_frame_count
    return M6DomainTypeRangeSide(
        range_aggregate=aggregate,
        frames_with_type_percent=(
            None
            if available_count == 0
            else 100.0 * aggregate.frames_with_type_count / available_count
        ),
    )


def _range_deltas(
    first: M6DomainTypeRangeSide,
    second: M6DomainTypeRangeSide,
) -> M6DomainTypeRangeDeltas:
    return M6DomainTypeRangeDeltas(
        domain_instance_count=(
            second.domain_instance_count - first.domain_instance_count
        ),
        frames_with_type_count=(
            second.frames_with_type_count - first.frames_with_type_count
        ),
        frames_with_type_percentage_points=_optional_delta(
            second.frames_with_type_percent,
            first.frames_with_type_percent,
        ),
        mean_domain_instances_per_available_frame=_optional_delta(
            second.mean_domain_instances_per_available_frame,
            first.mean_domain_instances_per_available_frame,
        ),
        mean_molecule_fraction_percentage_points=_optional_delta(
            second.mean_molecule_fraction,
            first.mean_molecule_fraction,
            scale=100.0,
        ),
        mean_footprint_fraction_percentage_points=_optional_delta(
            second.mean_footprint_fraction,
            first.mean_footprint_fraction,
            scale=100.0,
        ),
        mean_domain_coherent_q6=_optional_delta(
            second.mean_domain_coherent_q6,
            first.mean_domain_coherent_q6,
        ),
        mean_molecule_count=_optional_delta(
            second.mean_molecule_count,
            first.mean_molecule_count,
        ),
        mean_footprint_area_nm2=_optional_delta(
            second.mean_footprint_area_nm2,
            first.mean_footprint_area_nm2,
        ),
    )


def _optional_delta(
    second: float | None,
    first: float | None,
    *,
    scale: float = 1.0,
) -> float | None:
    if second is None or first is None:
        return None
    return float(scale * (second - first))


def _deltas_equal(
    actual: M6DomainTypeRangeDeltas,
    expected: M6DomainTypeRangeDeltas,
) -> bool:
    for model_field in fields(M6DomainTypeRangeDeltas):
        field_name = model_field.name
        actual_value = getattr(actual, field_name)
        expected_value = getattr(expected, field_name)
        if actual_value is None or expected_value is None:
            if actual_value is not expected_value:
                return False
        elif isinstance(actual_value, int) and isinstance(expected_value, int):
            if actual_value != expected_value:
                return False
        elif not isclose(
            float(actual_value),
            float(expected_value),
            rel_tol=1e-12,
            abs_tol=1e-12,
        ):
            return False
    return True


def _validate_sides_against_summary(
    sides: tuple[M6DomainTypeRangeSide, ...],
    summary: M6SingleRangeDomainTypeSummary,
    *,
    side_name: str,
) -> None:
    expected_denominators = (
        summary.available_frame_count,
        summary.valid_representative_fraction_frame_count,
        summary.valid_fov_fraction_frame_count,
    )
    for side in sides:
        aggregate = side.range_aggregate
        actual_denominators = (
            aggregate.available_frame_count,
            aggregate.valid_representative_fraction_frame_count,
            aggregate.valid_fov_fraction_frame_count,
        )
        if actual_denominators != expected_denominators:
            raise ValueError(
                f"{side_name} type statistics must use its summary denominators."
            )
    expected_present = tuple(
        row.range_aggregate for row in summary.type_summaries
    )
    actual_present = tuple(
        side.range_aggregate
        for side in sides
        if side.domain_instance_count > 0
    )
    if actual_present != expected_present:
        raise ValueError(
            f"{side_name} type statistics must match its summary's present types."
        )


def _optional_finite_float(value: object, field_name: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field_name} must be a finite number or None.")
    normalized = float(value)
    if not isfinite(normalized):
        raise ValueError(f"{field_name} must be finite.")
    return normalized
