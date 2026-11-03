"""Range shares and representative domains for molecular-order types."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import isclose, isfinite
from typing import Literal, get_args

from .frame_ranges import MolecularFrameRange
from .molecular_order_type_models import (
    MolecularOrderGeometryType,
    MolecularOrderOrientationType,
    MolecularOrderStackingType,
    MolecularOrderTypeClassificationResult,
    MolecularOrderTypeObservation,
    MolecularOrderTypeObservationKey,
)


MolecularOrderSummaryLayer = Literal[
    "geometry",
    "orientation",
    "stacking",
    "combination",
]
MolecularOrderShareDeltaDirection = Literal["second_minus_first"]

_LAYERS = tuple(get_args(MolecularOrderSummaryLayer))


@dataclass(frozen=True)
class MolecularOrderTypeSummaryRowKey:
    """Stable identity of one layer type or one three-layer combination."""

    layer: MolecularOrderSummaryLayer
    type_ids: tuple[int, ...]

    def __post_init__(self) -> None:
        if self.layer not in _LAYERS:
            raise ValueError("Unsupported molecular-order summary layer.")
        type_ids = tuple(
            _non_negative_integer(value, "type_id")
            for value in self.type_ids
        )
        expected_count = 3 if self.layer == "combination" else 1
        if len(type_ids) != expected_count:
            raise ValueError(
                f"{self.layer} row keys require {expected_count} type ID(s)."
            )
        object.__setattr__(self, "type_ids", type_ids)


@dataclass(frozen=True)
class MolecularOrderTypeRangeSummary:
    """Reliable denominators for one named range and each independent layer."""

    frame_range: MolecularFrameRange
    total_observation_count: int
    geometry_reliable_count: int
    orientation_reliable_count: int
    stacking_reliable_count: int
    combination_reliable_count: int

    def __post_init__(self) -> None:
        if not isinstance(self.frame_range, MolecularFrameRange):
            raise TypeError("frame_range must be MolecularFrameRange.")
        total = _non_negative_integer(
            self.total_observation_count,
            "total_observation_count",
        )
        for field_name in (
            "geometry_reliable_count",
            "orientation_reliable_count",
            "stacking_reliable_count",
            "combination_reliable_count",
        ):
            count = _non_negative_integer(
                getattr(self, field_name),
                field_name,
            )
            if count > total:
                raise ValueError(
                    f"{field_name} cannot exceed total observations."
                )

    @property
    def range_name(self) -> str:
        return self.frame_range.name

    def denominator_for_layer(
        self,
        layer: MolecularOrderSummaryLayer,
    ) -> int:
        normalized = _layer(layer)
        return {
            "geometry": self.geometry_reliable_count,
            "orientation": self.orientation_reliable_count,
            "stacking": self.stacking_reliable_count,
            "combination": self.combination_reliable_count,
        }[normalized]

    def excluded_for_layer(
        self,
        layer: MolecularOrderSummaryLayer,
    ) -> int:
        return self.total_observation_count - self.denominator_for_layer(layer)


@dataclass(frozen=True)
class MolecularOrderTypeRangeShare:
    """One row's count and share under one layer-specific denominator."""

    frame_range: MolecularFrameRange
    denominator_count: int
    count: int
    share_percent: float | None
    representative_observation_key: (
        MolecularOrderTypeObservationKey | None
    )

    def __post_init__(self) -> None:
        if not isinstance(self.frame_range, MolecularFrameRange):
            raise TypeError("frame_range must be MolecularFrameRange.")
        denominator = _non_negative_integer(
            self.denominator_count,
            "denominator_count",
        )
        count = _non_negative_integer(self.count, "count")
        if count > denominator:
            raise ValueError("count cannot exceed denominator_count.")
        if denominator == 0:
            if count != 0 or self.share_percent is not None:
                raise ValueError(
                    "A zero denominator requires zero count and undefined share."
                )
        else:
            share = _finite_float(self.share_percent, "share_percent")
            expected = 100.0 * count / denominator
            if not isclose(share, expected, abs_tol=1e-12, rel_tol=1e-12):
                raise ValueError("share_percent has the wrong denominator.")
            object.__setattr__(self, "share_percent", share)
        representative = self.representative_observation_key
        if (count == 0) != (representative is None):
            raise ValueError(
                "Exactly non-empty range shares require a representative."
            )
        if representative is not None:
            representative = _observation_key(representative)
            if representative[:3] != (
                self.frame_range.name,
                self.frame_range.start_frame,
                self.frame_range.end_frame,
            ):
                raise ValueError(
                    "Representative must belong to the range share."
                )
            object.__setattr__(
                self,
                "representative_observation_key",
                representative,
            )

    @property
    def range_name(self) -> str:
        return self.frame_range.name


@dataclass(frozen=True)
class MolecularOrderTypeSummaryRow:
    """One jointly defined type shown across one or two selected ranges."""

    key: MolecularOrderTypeSummaryRowKey
    label: str
    description: str
    range_shares: tuple[MolecularOrderTypeRangeShare, ...]
    share_delta_percentage_points: float | None

    def __post_init__(self) -> None:
        if not isinstance(self.key, MolecularOrderTypeSummaryRowKey):
            raise TypeError("key must be MolecularOrderTypeSummaryRowKey.")
        label = _non_empty_string(self.label, "label")
        description = _non_empty_string(self.description, "description")
        shares = tuple(self.range_shares)
        if len(shares) not in {1, 2} or any(
            not isinstance(value, MolecularOrderTypeRangeShare)
            for value in shares
        ):
            raise TypeError("range_shares must contain one or two shares.")
        identities = tuple(
            (
                value.frame_range.name,
                value.frame_range.start_frame,
                value.frame_range.end_frame,
            )
            for value in shares
        )
        if len(set(identities)) != len(identities):
            raise ValueError("range_shares must describe distinct ranges.")
        delta = self.share_delta_percentage_points
        if len(shares) == 1:
            if delta is not None:
                raise ValueError("A single-range row cannot have a delta.")
        else:
            expected = _optional_delta(
                shares[1].share_percent,
                shares[0].share_percent,
            )
            if expected is None:
                if delta is not None:
                    raise ValueError(
                        "Undefined range shares require an undefined delta."
                    )
            elif not isclose(
                _finite_float(delta, "share_delta_percentage_points"),
                expected,
                abs_tol=1e-12,
                rel_tol=1e-12,
            ):
                raise ValueError(
                    "share_delta_percentage_points must be second minus first."
                )
        object.__setattr__(self, "label", label)
        object.__setattr__(self, "description", description)
        object.__setattr__(self, "range_shares", shares)

    @property
    def layer(self) -> MolecularOrderSummaryLayer:
        return self.key.layer

    def side_for_range(
        self,
        range_name: str,
    ) -> MolecularOrderTypeRangeShare:
        normalized = _non_empty_string(range_name, "range_name")
        matches = tuple(
            value for value in self.range_shares
            if value.range_name == normalized
        )
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise KeyError(
                "Range name is ambiguous; use the ordered range_shares."
            )
        raise KeyError(f"Unknown range name: {normalized!r}.")

    def representative_for_range(
        self,
        range_name: str,
    ) -> MolecularOrderTypeObservationKey | None:
        return self.side_for_range(
            range_name
        ).representative_observation_key


@dataclass(frozen=True)
class MolecularOrderTypeSummary:
    """UI-ready shares for independent and combined order dimensions."""

    classification: MolecularOrderTypeClassificationResult
    range_summaries: tuple[MolecularOrderTypeRangeSummary, ...]
    rows: tuple[MolecularOrderTypeSummaryRow, ...]
    share_delta_direction: MolecularOrderShareDeltaDirection | None
    uses_tracking: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if not isinstance(
            self.classification,
            MolecularOrderTypeClassificationResult,
        ):
            raise TypeError(
                "classification must be MolecularOrderTypeClassificationResult."
            )
        summaries = tuple(self.range_summaries)
        expected_ranges = self.classification.analysis_scope.ranges
        if (
            len(summaries) != len(expected_ranges)
            or any(
                not isinstance(value, MolecularOrderTypeRangeSummary)
                for value in summaries
            )
            or tuple(value.frame_range for value in summaries)
            != expected_ranges
        ):
            raise ValueError(
                "range_summaries must follow classification ranges."
            )
        rows = tuple(self.rows)
        if any(
            not isinstance(value, MolecularOrderTypeSummaryRow)
            for value in rows
        ):
            raise TypeError("rows must contain molecular-order summary rows.")
        row_keys = tuple(value.key for value in rows)
        if len(set(row_keys)) != len(row_keys):
            raise ValueError("Summary row keys must be unique.")
        expected_direction = (
            None if len(expected_ranges) == 1 else "second_minus_first"
        )
        if self.share_delta_direction != expected_direction:
            raise ValueError(
                "share_delta_direction must match the analysis mode."
            )
        if any(
            tuple(side.frame_range for side in row.range_shares)
            != expected_ranges
            for row in rows
        ):
            raise ValueError(
                "Every row must contain shares in scope range order."
            )
        object.__setattr__(self, "range_summaries", summaries)
        object.__setattr__(self, "rows", rows)
        object.__setattr__(self, "uses_tracking", False)

    def rows_for_layer(
        self,
        layer: MolecularOrderSummaryLayer,
    ) -> tuple[MolecularOrderTypeSummaryRow, ...]:
        normalized = _layer(layer)
        return tuple(value for value in self.rows if value.layer == normalized)

    def range_summary_for_name(
        self,
        range_name: str,
    ) -> MolecularOrderTypeRangeSummary:
        normalized = _non_empty_string(range_name, "range_name")
        matches = tuple(
            value for value in self.range_summaries
            if value.range_name == normalized
        )
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise KeyError(
                "Range name is ambiguous; use the ordered range_summaries."
            )
        raise KeyError(f"Unknown range name: {normalized!r}.")


def build_molecular_order_type_summary(
    classification: MolecularOrderTypeClassificationResult,
) -> MolecularOrderTypeSummary:
    """Build range-normalized rows from one joint classification."""

    if not isinstance(
        classification,
        MolecularOrderTypeClassificationResult,
    ):
        raise TypeError(
            "classification must be MolecularOrderTypeClassificationResult."
        )
    observations_by_range = tuple(
        tuple(
            observation
            for observation in classification.observations
            if _observation_range_identity(observation)
            == (
                frame_range.name,
                frame_range.start_frame,
                frame_range.end_frame,
            )
        )
        for frame_range in classification.analysis_scope.ranges
    )
    assignment_by_key = {
        value.observation_key: value
        for value in classification.assignments
    }
    range_summaries = tuple(
        _range_summary(
            frame_range,
            observations,
            assignment_by_key=assignment_by_key,
        )
        for frame_range, observations in zip(
            classification.analysis_scope.ranges,
            observations_by_range,
            strict=True,
        )
    )
    rows = []
    for layer, type_values in (
        ("geometry", classification.geometry_types),
        ("orientation", classification.orientation_types),
        ("stacking", classification.stacking_types),
    ):
        for type_value in type_values:
            rows.append(
                _layer_row(
                    layer,
                    type_value,
                    classification=classification,
                    observations_by_range=observations_by_range,
                    range_summaries=range_summaries,
                    assignment_by_key=assignment_by_key,
                )
            )
    combination_keys = tuple(
        sorted(
            {
                _classified_combination(
                    assignment_by_key[observation.stable_key]
                )
                for observation in classification.observations
                if _classified_combination(
                    assignment_by_key[observation.stable_key]
                )
                is not None
            }
        )
    )
    for combination in combination_keys:
        if combination is None:
            continue
        rows.append(
            _combination_row(
                combination,
                classification=classification,
                observations_by_range=observations_by_range,
                range_summaries=range_summaries,
                assignment_by_key=assignment_by_key,
            )
        )
    return MolecularOrderTypeSummary(
        classification=classification,
        range_summaries=range_summaries,
        rows=tuple(rows),
        share_delta_direction=(
            None
            if classification.analysis_mode == "single_range"
            else "second_minus_first"
        ),
    )


def _range_summary(
    frame_range: MolecularFrameRange,
    observations: tuple[MolecularOrderTypeObservation, ...],
    *,
    assignment_by_key: dict,
) -> MolecularOrderTypeRangeSummary:
    layer_counts = {
        layer: sum(
            getattr(
                assignment_by_key[observation.stable_key],
                layer,
            ).status
            == "classified"
            for observation in observations
        )
        for layer in ("geometry", "orientation", "stacking")
    }
    combination_count = sum(
        _classified_combination(
            assignment_by_key[observation.stable_key]
        )
        is not None
        for observation in observations
    )
    return MolecularOrderTypeRangeSummary(
        frame_range=frame_range,
        total_observation_count=len(observations),
        geometry_reliable_count=layer_counts["geometry"],
        orientation_reliable_count=layer_counts["orientation"],
        stacking_reliable_count=layer_counts["stacking"],
        combination_reliable_count=combination_count,
    )


def _layer_row(
    layer: Literal["geometry", "orientation", "stacking"],
    type_value: (
        MolecularOrderGeometryType
        | MolecularOrderOrientationType
        | MolecularOrderStackingType
    ),
    *,
    classification: MolecularOrderTypeClassificationResult,
    observations_by_range: tuple[
        tuple[MolecularOrderTypeObservation, ...],
        ...,
    ],
    range_summaries: tuple[MolecularOrderTypeRangeSummary, ...],
    assignment_by_key: dict,
) -> MolecularOrderTypeSummaryRow:
    type_id = type_value.type_id
    members_by_range = tuple(
        tuple(
            observation
            for observation in observations
            if getattr(
                assignment_by_key[observation.stable_key],
                layer,
            ).type_id
            == type_id
        )
        for observations in observations_by_range
    )
    prefix = {"geometry": "G", "orientation": "O", "stacking": "S"}[
        layer
    ]
    shares = _range_shares(
        layer,
        members_by_range,
        classification=classification,
        range_summaries=range_summaries,
    )
    return MolecularOrderTypeSummaryRow(
        key=MolecularOrderTypeSummaryRowKey(layer, (type_id,)),
        label=f"{prefix}:{type_value.label}",
        description=_type_description(type_value),
        range_shares=shares,
        share_delta_percentage_points=_shares_delta(shares),
    )


def _combination_row(
    combination: tuple[int, int, int],
    *,
    classification: MolecularOrderTypeClassificationResult,
    observations_by_range: tuple[
        tuple[MolecularOrderTypeObservation, ...],
        ...,
    ],
    range_summaries: tuple[MolecularOrderTypeRangeSummary, ...],
    assignment_by_key: dict,
) -> MolecularOrderTypeSummaryRow:
    members_by_range = tuple(
        tuple(
            observation
            for observation in observations
            if _classified_combination(
                assignment_by_key[observation.stable_key]
            )
            == combination
        )
        for observations in observations_by_range
    )
    geometry = classification.geometry_types[combination[0]]
    orientation = classification.orientation_types[combination[1]]
    stacking = classification.stacking_types[combination[2]]
    shares = _range_shares(
        "combination",
        members_by_range,
        classification=classification,
        range_summaries=range_summaries,
    )
    return MolecularOrderTypeSummaryRow(
        key=MolecularOrderTypeSummaryRowKey("combination", combination),
        label=(
            f"G:{geometry.label} / O:{orientation.label} / "
            f"S:{stacking.label}"
        ),
        description=" | ".join(
            (
                _type_description(geometry),
                _type_description(orientation),
                _type_description(stacking),
            )
        ),
        range_shares=shares,
        share_delta_percentage_points=_shares_delta(shares),
    )


def _range_shares(
    layer: MolecularOrderSummaryLayer,
    members_by_range: tuple[
        tuple[MolecularOrderTypeObservation, ...],
        ...,
    ],
    *,
    classification: MolecularOrderTypeClassificationResult,
    range_summaries: tuple[MolecularOrderTypeRangeSummary, ...],
) -> tuple[MolecularOrderTypeRangeShare, ...]:
    return tuple(
        MolecularOrderTypeRangeShare(
            frame_range=frame_range,
            denominator_count=range_summary.denominator_for_layer(layer),
            count=len(members),
            share_percent=(
                None
                if range_summary.denominator_for_layer(layer) == 0
                else (
                    100.0
                    * len(members)
                    / range_summary.denominator_for_layer(layer)
                )
            ),
            representative_observation_key=_representative_key(members),
        )
        for frame_range, range_summary, members in zip(
            classification.analysis_scope.ranges,
            range_summaries,
            members_by_range,
            strict=True,
        )
    )


def _representative_key(
    observations: tuple[MolecularOrderTypeObservation, ...],
) -> MolecularOrderTypeObservationKey | None:
    if not observations:
        return None
    return min(
        observations,
        key=lambda value: (-value.molecule_count, value.stable_key),
    ).stable_key


def _classified_combination(assignment) -> tuple[int, int, int] | None:
    layers = (
        assignment.geometry,
        assignment.orientation,
        assignment.stacking,
    )
    if any(value.status != "classified" for value in layers):
        return None
    return tuple(value.type_id for value in layers)


def _type_description(
    value: (
        MolecularOrderGeometryType
        | MolecularOrderOrientationType
        | MolecularOrderStackingType
    ),
) -> str:
    if isinstance(value, MolecularOrderGeometryType):
        parts = []
        if value.dominant_symmetry is not None:
            parts.append(value.dominant_symmetry)
        if value.prototype_theta3_lattice_deg is not None:
            parts.append(
                f"M3 {value.prototype_theta3_lattice_deg:.2f} deg"
            )
        if value.prototype_theta6_lattice_deg is not None:
            parts.append(
                f"M6 {value.prototype_theta6_lattice_deg:.2f} deg"
            )
        return ", ".join(parts) or "Selected geometry features"
    if isinstance(value, MolecularOrderOrientationType):
        angles = ", ".join(
            f"{angle:.2f}" for angle in value.prototype_angles_deg
        )
        return f"Molecular orientation {angles} deg"
    parts = tuple(
        item
        for item in (value.pattern, value.mode, value.phase)
        if item is not None
    )
    return " / ".join(parts) or "Selected stacking features"


def _shares_delta(
    shares: tuple[MolecularOrderTypeRangeShare, ...],
) -> float | None:
    if len(shares) == 1:
        return None
    return _optional_delta(
        shares[1].share_percent,
        shares[0].share_percent,
    )


def _optional_delta(
    second: float | None,
    first: float | None,
) -> float | None:
    if first is None or second is None:
        return None
    return second - first


def _observation_range_identity(
    observation: MolecularOrderTypeObservation,
) -> tuple[str, int, int]:
    return (
        observation.range_name,
        observation.range_start_frame,
        observation.range_end_frame,
    )


def _observation_key(value: object) -> MolecularOrderTypeObservationKey:
    if not isinstance(value, tuple) or len(value) != 5:
        raise TypeError("observation key must contain five fields.")
    range_name = _non_empty_string(value[0], "range_name")
    start = _non_negative_integer(value[1], "range_start_frame")
    end = _non_negative_integer(value[2], "range_end_frame")
    frame = _non_negative_integer(value[3], "frame_index")
    domain_id = _non_empty_string(value[4], "lattice_domain_id")
    if not start <= frame <= end:
        raise ValueError("Representative frame must lie inside its range.")
    return range_name, start, end, frame, domain_id


def _layer(value: object) -> MolecularOrderSummaryLayer:
    if value not in _LAYERS:
        raise ValueError(f"Unsupported molecular-order layer: {value!r}.")
    return value


def _non_negative_integer(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer.")
    return value


def _finite_float(value: object, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field_name} must be a real number.")
    normalized = float(value)
    if not isfinite(normalized):
        raise ValueError(f"{field_name} must be finite.")
    return normalized


def _non_empty_string(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TypeError(f"{field_name} must be a non-empty string.")
    return value.strip()


__all__ = [
    "MolecularOrderShareDeltaDirection",
    "MolecularOrderSummaryLayer",
    "MolecularOrderTypeRangeShare",
    "MolecularOrderTypeRangeSummary",
    "MolecularOrderTypeSummary",
    "MolecularOrderTypeSummaryRow",
    "MolecularOrderTypeSummaryRowKey",
    "build_molecular_order_type_summary",
]
