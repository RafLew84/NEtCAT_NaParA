"""Frame-range summaries of molecular stacking without domain tracking."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import isclose, isfinite
from typing import Literal

from .frame_ranges import MolecularFrameRange
from .molecular_stacking_models import MolecularStackingAnalysis


StackingComparedPattern = Literal["ABAB", "uniform", "mixed"]
_PATTERNS: tuple[StackingComparedPattern, ...] = ("ABAB", "uniform", "mixed")


@dataclass(frozen=True)
class MolecularStackingRangeSummary:
    frame_range: MolecularFrameRange
    analyzed_frame_count: int
    classified_domain_count: int
    excluded_domain_count: int
    ambiguous_domain_count: int
    unavailable_domain_count: int
    pattern_counts: tuple[tuple[StackingComparedPattern, int], ...]
    pattern_shares_percent: tuple[
        tuple[StackingComparedPattern, float | None], ...
    ]

    def __post_init__(self) -> None:
        if not isinstance(self.frame_range, MolecularFrameRange):
            raise TypeError("frame_range must be MolecularFrameRange.")
        for name in (
            "analyzed_frame_count",
            "classified_domain_count",
            "excluded_domain_count",
            "ambiguous_domain_count",
            "unavailable_domain_count",
        ):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer.")
        counts = tuple(self.pattern_counts)
        shares = tuple(self.pattern_shares_percent)
        if tuple(pattern for pattern, _count in counts) != _PATTERNS:
            raise ValueError("pattern_counts must use the stable pattern order.")
        if tuple(pattern for pattern, _share in shares) != _PATTERNS:
            raise ValueError("pattern_shares_percent must use stable pattern order.")
        if any(
            not isinstance(count, int) or isinstance(count, bool) or count < 0
            for _pattern, count in counts
        ):
            raise ValueError("Pattern counts must be non-negative integers.")
        if sum(count for _pattern, count in counts) != self.classified_domain_count:
            raise ValueError("Pattern counts must equal classified_domain_count.")
        if (
            self.ambiguous_domain_count + self.unavailable_domain_count
            != self.excluded_domain_count
        ):
            raise ValueError("Excluded-domain counts are inconsistent.")
        for (pattern, count), (share_pattern, share) in zip(
            counts,
            shares,
            strict=True,
        ):
            assert pattern == share_pattern
            expected = (
                None
                if self.classified_domain_count == 0
                else 100.0 * count / self.classified_domain_count
            )
            if expected is None:
                if share is not None:
                    raise ValueError("Empty classified side has undefined shares.")
            elif (
                share is None
                or not isfinite(float(share))
                or not isclose(float(share), expected, abs_tol=1e-12)
            ):
                raise ValueError("Pattern share has the wrong denominator.")
        object.__setattr__(self, "pattern_counts", counts)
        object.__setattr__(self, "pattern_shares_percent", shares)

    def count_for(self, pattern: StackingComparedPattern) -> int:
        return dict(self.pattern_counts)[pattern]

    def share_for(self, pattern: StackingComparedPattern) -> float | None:
        return dict(self.pattern_shares_percent)[pattern]


@dataclass(frozen=True)
class MolecularStackingRangeComparisonRow:
    pattern: StackingComparedPattern
    first_count: int
    first_share_percent: float | None
    second_count: int
    second_share_percent: float | None
    count_delta: int
    share_delta_percentage_points: float | None

    def __post_init__(self) -> None:
        if self.pattern not in _PATTERNS:
            raise ValueError("Unsupported stacking comparison pattern.")
        for name in ("first_count", "second_count"):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer.")
        if self.count_delta != self.second_count - self.first_count:
            raise ValueError("count_delta must use second-minus-first direction.")
        for name in ("first_share_percent", "second_share_percent"):
            value = getattr(self, name)
            if value is not None and (
                not isfinite(float(value)) or not 0.0 <= float(value) <= 100.0
            ):
                raise ValueError(f"{name} must be between 0 and 100.")
        expected_share_delta = (
            None
            if (
                self.first_share_percent is None
                or self.second_share_percent is None
            )
            else self.second_share_percent - self.first_share_percent
        )
        if expected_share_delta is None:
            if self.share_delta_percentage_points is not None:
                raise ValueError(
                    "Undefined shares require an undefined share delta."
                )
        elif (
            self.share_delta_percentage_points is None
            or not isfinite(float(self.share_delta_percentage_points))
            or not isclose(
                float(self.share_delta_percentage_points),
                expected_share_delta,
                abs_tol=1e-12,
            )
        ):
            raise ValueError(
                "share_delta_percentage_points must use second-minus-first."
            )


@dataclass(frozen=True)
class MolecularStackingRangeComparison:
    first: MolecularStackingRangeSummary
    second: MolecularStackingRangeSummary
    rows: tuple[MolecularStackingRangeComparisonRow, ...]
    denominator: Literal["classified_domain_instances"] = field(
        default="classified_domain_instances",
        init=False,
    )
    direction: Literal["second_minus_first"] = field(
        default="second_minus_first",
        init=False,
    )
    uses_tracking: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.first, MolecularStackingRangeSummary):
            raise TypeError("first must be a stacking range summary.")
        if not isinstance(self.second, MolecularStackingRangeSummary):
            raise TypeError("second must be a stacking range summary.")
        if self.first.frame_range == self.second.frame_range:
            raise ValueError("Comparison frame ranges must be distinct.")
        rows = tuple(self.rows)
        if tuple(row.pattern for row in rows) != _PATTERNS:
            raise ValueError("Comparison rows must use stable pattern order.")
        for row in rows:
            if (
                row.first_count != self.first.count_for(row.pattern)
                or row.first_share_percent != self.first.share_for(row.pattern)
                or row.second_count != self.second.count_for(row.pattern)
                or row.second_share_percent != self.second.share_for(row.pattern)
            ):
                raise ValueError(
                    "Comparison row does not match its range summaries."
                )
        object.__setattr__(self, "rows", rows)
        object.__setattr__(self, "uses_tracking", False)


def build_molecular_stacking_range_summary(
    analysis: MolecularStackingAnalysis,
    frame_range: MolecularFrameRange,
) -> MolecularStackingRangeSummary:
    if not isinstance(analysis, MolecularStackingAnalysis):
        raise TypeError("analysis must be MolecularStackingAnalysis.")
    if not isinstance(frame_range, MolecularFrameRange):
        raise TypeError("frame_range must be MolecularFrameRange.")
    orders = tuple(
        order
        for order in analysis.orders
        if frame_range.start_frame <= order.frame_index <= frame_range.end_frame
    )
    pattern_counts = tuple(
        (pattern, sum(order.pattern == pattern for order in orders))
        for pattern in _PATTERNS
    )
    classified_count = sum(count for _pattern, count in pattern_counts)
    ambiguous_count = sum(order.pattern == "ambiguous" for order in orders)
    unavailable_count = sum(order.pattern == "unavailable" for order in orders)
    return MolecularStackingRangeSummary(
        frame_range=frame_range,
        analyzed_frame_count=sum(
            frame_range.start_frame <= frame_index <= frame_range.end_frame
            for frame_index in analysis.input_frame_indices
        ),
        classified_domain_count=classified_count,
        excluded_domain_count=ambiguous_count + unavailable_count,
        ambiguous_domain_count=ambiguous_count,
        unavailable_domain_count=unavailable_count,
        pattern_counts=pattern_counts,
        pattern_shares_percent=tuple(
            (
                pattern,
                None
                if classified_count == 0
                else 100.0 * count / classified_count,
            )
            for pattern, count in pattern_counts
        ),
    )


def build_molecular_stacking_range_comparison(
    analysis: MolecularStackingAnalysis,
    first_range: MolecularFrameRange,
    second_range: MolecularFrameRange,
) -> MolecularStackingRangeComparison:
    """Compare domain-instance shares; no cross-frame identity is inferred."""

    first = build_molecular_stacking_range_summary(analysis, first_range)
    second = build_molecular_stacking_range_summary(analysis, second_range)
    rows = []
    for pattern in _PATTERNS:
        first_share = first.share_for(pattern)
        second_share = second.share_for(pattern)
        rows.append(
            MolecularStackingRangeComparisonRow(
                pattern=pattern,
                first_count=first.count_for(pattern),
                first_share_percent=first_share,
                second_count=second.count_for(pattern),
                second_share_percent=second_share,
                count_delta=second.count_for(pattern) - first.count_for(pattern),
                share_delta_percentage_points=(
                    None
                    if first_share is None or second_share is None
                    else second_share - first_share
                ),
            )
        )
    return MolecularStackingRangeComparison(
        first=first,
        second=second,
        rows=tuple(rows),
    )


__all__ = [
    "MolecularStackingRangeComparison",
    "MolecularStackingRangeComparisonRow",
    "MolecularStackingRangeSummary",
    "StackingComparedPattern",
    "build_molecular_stacking_range_comparison",
    "build_molecular_stacking_range_summary",
]
