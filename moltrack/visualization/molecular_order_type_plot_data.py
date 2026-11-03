"""GUI-independent plot data for hierarchical molecular-order types."""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil, isclose, isfinite
from numbers import Real
from typing import Literal

from moltrack.analysis.molecular_order_type_models import (
    MolecularOrderTypeClassificationResult,
    MolecularOrderTypeObservationKey,
)
from moltrack.analysis.molecular_order_type_summary import (
    MolecularOrderTypeSummary,
)
from moltrack.analysis.molecular_stacking_overlay import (
    MolecularStackingDisplayResult,
)

from .m6_domain_type_colors import m6_domain_type_color


MolecularOrderGeometryChannel = Literal["m3", "m6"]


@dataclass(frozen=True)
class MolecularOrderGeometryScatterPoint:
    channel: MolecularOrderGeometryChannel
    angle_deg: float
    molecule_count: int
    geometry_type_id: int
    geometry_type_label: str
    range_name: str
    range_index: int
    color: tuple[int, int, int, int]
    observation_key: MolecularOrderTypeObservationKey


@dataclass(frozen=True)
class MolecularOrderGeometryScatterData:
    m3_points: tuple[MolecularOrderGeometryScatterPoint, ...]
    m6_points: tuple[MolecularOrderGeometryScatterPoint, ...]
    omitted_m3_count: int
    omitted_m6_count: int
    range_names: tuple[str, ...]
    type_labels: tuple[str, ...]
    type_colors: tuple[tuple[int, int, int, int], ...]
    axis_labels: tuple[str, str] = (
        "Lattice angle [deg]",
        "Molecules",
    )


@dataclass(frozen=True)
class MolecularOrderOrientationDistributionSeries:
    range_name: str
    counts: tuple[int, ...]


@dataclass(frozen=True)
class MolecularOrderOrientationDistributionData:
    bin_edges_deg: tuple[float, ...]
    series: tuple[MolecularOrderOrientationDistributionSeries, ...]
    excluded_observation_count: int
    distribution_basis: Literal[
        "molecular_measurements",
        "domain_prototypes",
    ]
    axis_labels: tuple[str, str] = (
        "Molecular orientation [deg]",
        "Count",
    )


@dataclass(frozen=True)
class MolecularOrderStackingShareSeries:
    range_name: str
    values_percent: tuple[float | None, ...]


@dataclass(frozen=True)
class MolecularOrderStackingShareData:
    type_labels: tuple[str, ...]
    type_descriptions: tuple[str, ...]
    type_colors: tuple[tuple[int, int, int, int], ...]
    series: tuple[MolecularOrderStackingShareSeries, ...]
    reliable_denominators: tuple[int, ...]
    excluded_counts: tuple[int, ...]
    axis_label: str = "Share of reliable stacking observations [%]"


def build_molecular_order_geometry_scatter_data(
    classification: MolecularOrderTypeClassificationResult,
) -> MolecularOrderGeometryScatterData:
    if not isinstance(
        classification,
        MolecularOrderTypeClassificationResult,
    ):
        raise TypeError(
            "classification must be MolecularOrderTypeClassificationResult."
        )
    assignment_by_key = {
        value.observation_key: value
        for value in classification.assignments
    }
    range_index_by_identity = {
        (value.name, value.start_frame, value.end_frame): index
        for index, value in enumerate(classification.analysis_scope.ranges)
    }
    points = {"m3": [], "m6": []}
    omitted = {"m3": 0, "m6": 0}
    for observation in classification.observations:
        assignment = assignment_by_key[observation.stable_key].geometry
        for channel, angle in (
            ("m3", observation.theta3_lattice_deg),
            ("m6", observation.theta6_lattice_deg),
        ):
            if assignment.status != "classified" or angle is None:
                omitted[channel] += 1
                continue
            type_id = assignment.type_id
            type_value = classification.geometry_types[type_id]
            points[channel].append(
                MolecularOrderGeometryScatterPoint(
                    channel=channel,
                    angle_deg=float(angle),
                    molecule_count=observation.molecule_count,
                    geometry_type_id=type_id,
                    geometry_type_label=type_value.label,
                    range_name=observation.range_name,
                    range_index=range_index_by_identity[
                        (
                            observation.range_name,
                            observation.range_start_frame,
                            observation.range_end_frame,
                        )
                    ],
                    color=m6_domain_type_color(type_id),
                    observation_key=observation.stable_key,
                )
            )
    return MolecularOrderGeometryScatterData(
        m3_points=tuple(points["m3"]),
        m6_points=tuple(points["m6"]),
        omitted_m3_count=omitted["m3"],
        omitted_m6_count=omitted["m6"],
        range_names=tuple(
            value.name for value in classification.analysis_scope.ranges
        ),
        type_labels=tuple(
            value.label for value in classification.geometry_types
        ),
        type_colors=tuple(
            m6_domain_type_color(value.type_id)
            for value in classification.geometry_types
        ),
    )


def build_molecular_order_orientation_distribution_data(
    classification: MolecularOrderTypeClassificationResult,
    *,
    bin_width_deg: object = 5.0,
    display_result: MolecularStackingDisplayResult | None = None,
) -> MolecularOrderOrientationDistributionData:
    if not isinstance(
        classification,
        MolecularOrderTypeClassificationResult,
    ):
        raise TypeError(
            "classification must be MolecularOrderTypeClassificationResult."
        )
    width = _positive_float(bin_width_deg, "bin_width_deg")
    assignment_by_key = {
        value.observation_key: value
        for value in classification.assignments
    }
    classified = tuple(
        observation
        for observation in classification.observations
        if assignment_by_key[
            observation.stable_key
        ].orientation.status
        == "classified"
    )
    maximum_period = max(
        (
            observation.molecular_orientation_periodicity_deg
            for observation in classified
            if observation.molecular_orientation_periodicity_deg is not None
        ),
        default=180.0,
    )
    bin_count = max(1, int(ceil(maximum_period / width)))
    edges = tuple(
        min(float(index) * width, maximum_period)
        for index in range(bin_count + 1)
    )
    if edges[-1] != maximum_period:
        edges = (*edges[:-1], maximum_period)
    samples_by_range = _orientation_samples_by_range(
        classification,
        classified,
        display_result=display_result,
    )
    series = []
    for frame_range in classification.analysis_scope.ranges:
        counts = [0] * bin_count
        identity = (
            frame_range.name,
            frame_range.start_frame,
            frame_range.end_frame,
        )
        for angle in samples_by_range[identity]:
            index = min(int(angle / width), bin_count - 1)
            counts[index] += 1
        series.append(
            MolecularOrderOrientationDistributionSeries(
                range_name=frame_range.name,
                counts=tuple(counts),
            )
        )
    return MolecularOrderOrientationDistributionData(
        bin_edges_deg=edges,
        series=tuple(series),
        excluded_observation_count=(
            len(classification.observations) - len(classified)
        ),
        distribution_basis=(
            "molecular_measurements"
            if display_result is not None
            else "domain_prototypes"
        ),
    )


def _orientation_samples_by_range(
    classification: MolecularOrderTypeClassificationResult,
    classified_observations,
    *,
    display_result: MolecularStackingDisplayResult | None,
) -> dict[tuple[str, int, int], list[float]]:
    samples = {
        (value.name, value.start_frame, value.end_frame): []
        for value in classification.analysis_scope.ranges
    }
    if display_result is None:
        for observation in classified_observations:
            samples[
                (
                    observation.range_name,
                    observation.range_start_frame,
                    observation.range_end_frame,
                )
            ].extend(observation.molecular_orientation_prototypes_deg)
        return samples
    if not isinstance(display_result, MolecularStackingDisplayResult):
        raise TypeError(
            "display_result must be MolecularStackingDisplayResult or None."
        )
    minimum_confidence = (
        display_result.prototype_analysis.settings.minimum_confidence
    )
    for observation in classified_observations:
        frame = display_result.frame_data(observation.frame_index)
        domain = frame.row_assignment.assignment_for_domain(
            observation.lattice_domain_id
        )
        source_ids = set(domain.source_ids)
        periodicity = observation.molecular_orientation_periodicity_deg
        if periodicity is None:
            continue
        destination = samples[
            (
                observation.range_name,
                observation.range_start_frame,
                observation.range_end_frame,
            )
        ]
        for measurement in frame.measurements:
            if (
                measurement.provenance.source_id not in source_ids
                or measurement.status != "available"
                or measurement.angle_deg is None
                or measurement.confidence is None
                or measurement.confidence < minimum_confidence
                or not isclose(
                    measurement.periodicity_deg,
                    periodicity,
                    abs_tol=1e-9,
                    rel_tol=1e-9,
                )
            ):
                continue
            destination.append(float(measurement.angle_deg) % periodicity)
    return samples


def build_molecular_order_stacking_share_data(
    summary: MolecularOrderTypeSummary,
) -> MolecularOrderStackingShareData:
    if not isinstance(summary, MolecularOrderTypeSummary):
        raise TypeError("summary must be MolecularOrderTypeSummary.")
    rows = summary.rows_for_layer("stacking")
    return MolecularOrderStackingShareData(
        type_labels=tuple(value.label for value in rows),
        type_descriptions=tuple(value.description for value in rows),
        type_colors=tuple(
            m6_domain_type_color(value.key.type_ids[0])
            for value in rows
        ),
        series=tuple(
            MolecularOrderStackingShareSeries(
                range_name=range_summary.range_name,
                values_percent=tuple(
                    row.range_shares[range_index].share_percent
                    for row in rows
                ),
            )
            for range_index, range_summary in enumerate(
                summary.range_summaries
            )
        ),
        reliable_denominators=tuple(
            value.stacking_reliable_count
            for value in summary.range_summaries
        ),
        excluded_counts=tuple(
            value.excluded_for_layer("stacking")
            for value in summary.range_summaries
        ),
    )


def _positive_float(value: object, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{field_name} must be a real number.")
    normalized = float(value)
    if not isfinite(normalized) or normalized <= 0.0:
        raise ValueError(f"{field_name} must be positive.")
    return normalized


__all__ = [
    "MolecularOrderGeometryChannel",
    "MolecularOrderGeometryScatterData",
    "MolecularOrderGeometryScatterPoint",
    "MolecularOrderOrientationDistributionData",
    "MolecularOrderOrientationDistributionSeries",
    "MolecularOrderStackingShareData",
    "MolecularOrderStackingShareSeries",
    "build_molecular_order_geometry_scatter_data",
    "build_molecular_order_orientation_distribution_data",
    "build_molecular_order_stacking_share_data",
]
