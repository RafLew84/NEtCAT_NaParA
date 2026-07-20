from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from moltrack.analysis import (
    M6DomainTypeClassificationResult,
    M6DomainTypeRangeAggregate,
    M6DomainTypeRangeComparison,
    M6DomainTypeRangeSide,
    M6SingleRangeDomainTypeRow,
    M6SingleRangeDomainTypeSummary,
)
from moltrack.ui.m6_domain_type_colors import (
    M6_DOMAIN_TYPE_UNCLASSIFIED_COLOR,
    m6_domain_type_color,
)


M6DomainTypeShareMetric = Literal[
    "instances_per_frame",
    "molecule_fraction",
    "footprint_fraction",
]

_RANGE_SYMBOLS = ("o", "s", "t", "d")


@dataclass(frozen=True)
class M6DomainTypeLegendEntry:
    label: str
    color: tuple[int, int, int, int]
    symbol: str


@dataclass(frozen=True)
class M6DomainTypeScatterPoint:
    orientation_deg: float
    median_bond_length_nm: float
    type_id: int | None
    type_label: str
    range_name: str
    range_index: int
    color: tuple[int, int, int, int]
    symbol: str
    observation_key: tuple


@dataclass(frozen=True)
class M6DomainTypeScatterData:
    points: tuple[M6DomainTypeScatterPoint, ...]
    type_legend: tuple[M6DomainTypeLegendEntry, ...]
    range_legend: tuple[M6DomainTypeLegendEntry, ...]
    omitted_missing_bond_length_count: int
    axis_labels: tuple[str, str] = (
        "M6 orientation [deg]",
        "Median bond length [nm]",
    )


@dataclass(frozen=True)
class M6DomainTypeShareSeries:
    name: str
    values: tuple[float | None, ...]


@dataclass(frozen=True)
class M6DomainTypeSharePlotData:
    metric: M6DomainTypeShareMetric
    axis_label: str
    type_labels: tuple[str, ...]
    type_colors: tuple[tuple[int, int, int, int], ...]
    series: tuple[M6DomainTypeShareSeries, ...]


@dataclass(frozen=True)
class M6DomainTypeShareMetricSpec:
    key: M6DomainTypeShareMetric
    label: str
    axis_label: str
    single_value: Callable[[M6SingleRangeDomainTypeRow], float | None]
    side_value: Callable[[M6DomainTypeRangeSide], float | None]
    unclassified_value: Callable[[M6DomainTypeRangeAggregate], float | None]
    scale: float = 1.0

    def value_for_single(self, row: M6SingleRangeDomainTypeRow) -> float | None:
        return _scaled_optional(self.single_value(row), self.scale)

    def value_for_side(self, side: M6DomainTypeRangeSide) -> float | None:
        return _scaled_optional(self.side_value(side), self.scale)

    def value_for_unclassified(
        self,
        aggregate: M6DomainTypeRangeAggregate,
    ) -> float | None:
        return _scaled_optional(self.unclassified_value(aggregate), self.scale)


M6_DOMAIN_TYPE_SHARE_METRICS = (
    M6DomainTypeShareMetricSpec(
        "instances_per_frame",
        "Instances/frame",
        "Instances/frame",
        single_value=lambda row: row.mean_instances_per_available_frame,
        side_value=lambda side: side.mean_domain_instances_per_available_frame,
        unclassified_value=lambda aggregate: (
            aggregate.mean_instances_per_available_frame
        ),
    ),
    M6DomainTypeShareMetricSpec(
        "molecule_fraction",
        "Molecule fraction",
        "Molecule fraction [%]",
        single_value=lambda row: (
            row.mean_molecule_fraction_of_valid_representatives
        ),
        side_value=lambda side: side.mean_molecule_fraction,
        unclassified_value=lambda aggregate: (
            aggregate.mean_molecule_fraction_of_valid_representatives
        ),
        scale=100.0,
    ),
    M6DomainTypeShareMetricSpec(
        "footprint_fraction",
        "Footprint fraction",
        "Footprint fraction [%]",
        single_value=lambda row: row.mean_footprint_fraction_of_valid_fov,
        side_value=lambda side: side.mean_footprint_fraction,
        unclassified_value=lambda aggregate: (
            aggregate.mean_footprint_fraction_of_valid_fov
        ),
        scale=100.0,
    ),
)
_SHARE_METRICS_BY_KEY = {
    metric.key: metric for metric in M6_DOMAIN_TYPE_SHARE_METRICS
}


def build_m6_domain_type_scatter_data(
    classification: M6DomainTypeClassificationResult,
) -> M6DomainTypeScatterData:
    if not isinstance(classification, M6DomainTypeClassificationResult):
        raise TypeError("classification must be an M6 domain type classification.")
    ranges = classification.analysis_scope.ranges
    range_names = tuple(frame_range.name for frame_range in ranges)
    range_index_by_identity = {
        (frame_range.name, frame_range.start_frame, frame_range.end_frame): index
        for index, frame_range in enumerate(ranges)
    }
    assignment_by_key = {
        assignment.observation_key: assignment
        for assignment in classification.assignments
    }
    type_by_id = {
        domain_type.domain_type_id: domain_type
        for domain_type in classification.domain_types
    }
    points = []
    omitted_count = 0
    has_unclassified = False
    for observation in classification.observations:
        assignment = assignment_by_key[observation.stable_key]
        if assignment.status == "classified":
            type_id = assignment.domain_type_id
            domain_type = type_by_id[type_id]
            type_label = domain_type.label
            color = m6_domain_type_color(type_id)
        else:
            type_id = None
            type_label = "Unclassified"
            color = M6_DOMAIN_TYPE_UNCLASSIFIED_COLOR
            has_unclassified = True
        bond_length = observation.domain_median_bond_length_nm
        if bond_length is None:
            omitted_count += 1
            continue
        range_index = range_index_by_identity[
            (
                observation.range_name,
                observation.range_start_frame,
                observation.range_end_frame,
            )
        ]
        symbol = _RANGE_SYMBOLS[range_index % len(_RANGE_SYMBOLS)]
        points.append(
            M6DomainTypeScatterPoint(
                orientation_deg=float(observation.orientation_deg) % 60.0,
                median_bond_length_nm=float(bond_length),
                type_id=type_id,
                type_label=type_label,
                range_name=observation.range_name,
                range_index=range_index,
                color=color,
                symbol=symbol,
                observation_key=observation.stable_key,
            )
        )
    type_legend = tuple(
        M6DomainTypeLegendEntry(
            label=domain_type.label,
            color=m6_domain_type_color(domain_type.domain_type_id),
            symbol="o",
        )
        for domain_type in classification.domain_types
    )
    if has_unclassified:
        type_legend += (
            M6DomainTypeLegendEntry(
                label="Unclassified",
                color=M6_DOMAIN_TYPE_UNCLASSIFIED_COLOR,
                symbol="o",
            ),
        )
    range_legend = ()
    if classification.analysis_scope.analysis_mode == "compare_ranges":
        range_legend = tuple(
            M6DomainTypeLegendEntry(
                label=name,
                color=M6_DOMAIN_TYPE_UNCLASSIFIED_COLOR,
                symbol=_RANGE_SYMBOLS[index % len(_RANGE_SYMBOLS)],
            )
            for index, name in enumerate(range_names)
        )
    return M6DomainTypeScatterData(
        points=tuple(points),
        type_legend=type_legend,
        range_legend=range_legend,
        omitted_missing_bond_length_count=omitted_count,
    )


def build_m6_domain_type_share_plot_data(
    table_result: M6SingleRangeDomainTypeSummary | M6DomainTypeRangeComparison,
    metric: M6DomainTypeShareMetric,
) -> M6DomainTypeSharePlotData:
    if not isinstance(
        table_result,
        (M6SingleRangeDomainTypeSummary, M6DomainTypeRangeComparison),
    ):
        raise TypeError("table_result must be a domain type table result.")
    try:
        metric_spec = _SHARE_METRICS_BY_KEY[metric]
    except KeyError as exc:
        raise ValueError(f"Unsupported domain type share metric: {metric!r}.") from exc

    if isinstance(table_result, M6SingleRangeDomainTypeSummary):
        rows = tuple(
            sorted(table_result.type_summaries, key=lambda row: row.domain_type_id)
        )
        labels = tuple(row.label for row in rows) + ("Unclassified",)
        series = (
            M6DomainTypeShareSeries(
                name=table_result.range_name,
                values=(
                    *tuple(metric_spec.value_for_single(row) for row in rows),
                    metric_spec.value_for_unclassified(
                        table_result.unclassified_aggregate
                    ),
                ),
            ),
        )
        type_ids = tuple(row.domain_type_id for row in rows)
    else:
        rows = tuple(sorted(table_result.rows, key=lambda row: row.domain_type_id))
        labels = tuple(row.label for row in rows) + ("Unclassified",)
        series = (
            M6DomainTypeShareSeries(
                name=table_result.first_range_name,
                values=(
                    *tuple(metric_spec.value_for_side(row.first) for row in rows),
                    metric_spec.value_for_unclassified(
                        table_result.first_summary.unclassified_aggregate
                    ),
                ),
            ),
            M6DomainTypeShareSeries(
                name=table_result.second_range_name,
                values=(
                    *tuple(metric_spec.value_for_side(row.second) for row in rows),
                    metric_spec.value_for_unclassified(
                        table_result.second_summary.unclassified_aggregate
                    ),
                ),
            ),
        )
        type_ids = tuple(row.domain_type_id for row in rows)
    return M6DomainTypeSharePlotData(
        metric=metric,
        axis_label=metric_spec.axis_label,
        type_labels=labels,
        type_colors=(
            *tuple(m6_domain_type_color(type_id) for type_id in type_ids),
            M6_DOMAIN_TYPE_UNCLASSIFIED_COLOR,
        ),
        series=series,
    )


def _scaled_optional(value: float | None, scale: float) -> float | None:
    return None if value is None else float(value) * scale
