from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class MolecularFrameRange:
    """One named, inclusive frame range used as an experimental condition."""

    name: str
    start_frame: int
    end_frame: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", str(self.name).strip())
        object.__setattr__(self, "start_frame", int(self.start_frame))
        object.__setattr__(self, "end_frame", int(self.end_frame))
        if self.start_frame > self.end_frame:
            raise ValueError("start_frame must not be greater than end_frame.")

    @property
    def frame_indices(self) -> tuple[int, ...]:
        return tuple(range(self.start_frame, self.end_frame + 1))


@dataclass(frozen=True)
class MolecularFrameRangeSelection:
    """Two experimental conditions selected from one series and source view."""

    frame_count: int
    source_view: str
    first_range: MolecularFrameRange
    second_range: MolecularFrameRange

    def __post_init__(self) -> None:
        object.__setattr__(self, "frame_count", int(self.frame_count))
        object.__setattr__(self, "source_view", str(self.source_view).strip())
        for frame_range in (self.first_range, self.second_range):
            if frame_range.start_frame < 0 or frame_range.end_frame >= self.frame_count:
                raise ValueError("Frame range must fit within frame_count.")

    def to_analysis_scope(self) -> "MolecularFrameRangeAnalysisScope":
        return MolecularFrameRangeAnalysisScope.from_frame_range_selection(self)


@dataclass(frozen=True)
class MolecularFrameRangeAnalysisScope:
    """One or two named frame ranges selected for analysis in one source view."""

    analysis_mode: Literal["single_range", "compare_ranges"]
    frame_count: int
    source_view: str
    ranges: tuple[MolecularFrameRange, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.analysis_mode, str):
            raise ValueError("analysis_mode must be a string.")
        if isinstance(self.frame_count, bool) or not isinstance(self.frame_count, int):
            raise ValueError("frame_count must be an integer.")
        if not isinstance(self.source_view, str):
            raise ValueError("source_view must be a string.")
        mode = self.analysis_mode.strip().lower()
        frame_count = self.frame_count
        source_view = self.source_view.strip()
        ranges = tuple(self.ranges)
        if mode not in {"single_range", "compare_ranges"}:
            raise ValueError(
                "analysis_mode must be 'single_range' or 'compare_ranges'."
            )
        if frame_count <= 0:
            raise ValueError("frame_count must be positive.")
        if not source_view:
            raise ValueError("source_view must not be empty.")
        expected_range_count = 1 if mode == "single_range" else 2
        if len(ranges) != expected_range_count:
            raise ValueError(
                f"{mode} analysis requires exactly {expected_range_count} frame "
                f"range{'s' if expected_range_count != 1 else ''}."
            )
        for frame_range in ranges:
            if not isinstance(frame_range, MolecularFrameRange):
                raise TypeError("ranges must contain MolecularFrameRange instances.")
            if frame_range.start_frame < 0 or frame_range.end_frame >= frame_count:
                raise ValueError("Frame range must fit within frame_count.")
        if mode == "compare_ranges":
            first_range, second_range = ranges
            if (
                first_range.start_frame == second_range.start_frame
                and first_range.end_frame == second_range.end_frame
            ):
                raise ValueError("Comparison frame ranges must be distinct.")
        object.__setattr__(self, "analysis_mode", mode)
        object.__setattr__(self, "frame_count", frame_count)
        object.__setattr__(self, "source_view", source_view)
        object.__setattr__(self, "ranges", ranges)

    @property
    def single_range(self) -> MolecularFrameRange:
        if self.analysis_mode != "single_range":
            raise ValueError("single_range is only available in single_range mode.")
        return self.ranges[0]

    @property
    def comparison_ranges(self) -> tuple[MolecularFrameRange, MolecularFrameRange]:
        if self.analysis_mode != "compare_ranges":
            raise ValueError(
                "comparison_ranges is only available in compare_ranges mode."
            )
        return self.ranges[0], self.ranges[1]

    @classmethod
    def from_frame_range_selection(
        cls,
        selection: MolecularFrameRangeSelection,
    ) -> "MolecularFrameRangeAnalysisScope":
        if not isinstance(selection, MolecularFrameRangeSelection):
            raise TypeError("selection must be a MolecularFrameRangeSelection.")
        return cls(
            analysis_mode="compare_ranges",
            frame_count=selection.frame_count,
            source_view=selection.source_view,
            ranges=(selection.first_range, selection.second_range),
        )

    def to_frame_range_selection(self) -> MolecularFrameRangeSelection:
        first_range, second_range = self.comparison_ranges
        return MolecularFrameRangeSelection(
            frame_count=self.frame_count,
            source_view=self.source_view,
            first_range=first_range,
            second_range=second_range,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "analysis_mode": self.analysis_mode,
            "frame_count": self.frame_count,
            "source_view": self.source_view,
            "ranges": [
                {
                    "name": frame_range.name,
                    "start_frame": frame_range.start_frame,
                    "end_frame": frame_range.end_frame,
                }
                for frame_range in self.ranges
            ],
        }

    @classmethod
    def from_dict(
        cls,
        payload: Mapping[str, object],
    ) -> "MolecularFrameRangeAnalysisScope":
        if not isinstance(payload, Mapping):
            raise TypeError("Frame range analysis scope payload must be a mapping.")
        _validate_exact_mapping_fields(
            payload,
            required={"analysis_mode", "frame_count", "source_view", "ranges"},
            label="frame range analysis scope",
        )
        ranges_payload = payload["ranges"]
        if not isinstance(ranges_payload, (list, tuple)):
            raise TypeError("ranges must be a sequence of mappings.")
        normalized_ranges = []
        for index, frame_range in enumerate(ranges_payload):
            if not isinstance(frame_range, Mapping):
                raise TypeError(f"ranges[{index}] must be a mapping.")
            _validate_exact_mapping_fields(
                frame_range,
                required={"name", "start_frame", "end_frame"},
                label=f"ranges[{index}]",
            )
            _validate_serialized_frame_range(frame_range, index=index)
            normalized_ranges.append(
                MolecularFrameRange(
                    name=frame_range["name"],
                    start_frame=frame_range["start_frame"],
                    end_frame=frame_range["end_frame"],
                )
            )
        return cls(
            analysis_mode=payload["analysis_mode"],
            frame_count=payload["frame_count"],
            source_view=payload["source_view"],
            ranges=tuple(normalized_ranges),
        )


def _validate_exact_mapping_fields(
    payload: Mapping[object, object],
    *,
    required: set[str],
    label: str,
) -> None:
    non_string_keys = [key for key in payload if not isinstance(key, str)]
    if non_string_keys:
        raise ValueError(f"{label} field names must be strings.")
    fields = set(payload)
    unknown = sorted(fields - required)
    if unknown:
        raise ValueError(f"Unknown {label} fields: {', '.join(unknown)}")
    missing = sorted(required - fields)
    if missing:
        raise ValueError(f"Missing {label} fields: {', '.join(missing)}")


def _validate_serialized_frame_range(
    payload: Mapping[str, object],
    *,
    index: int,
) -> None:
    if not isinstance(payload["name"], str):
        raise ValueError(f"ranges[{index}].name must be a string.")
    for field_name in ("start_frame", "end_frame"):
        value = payload[field_name]
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"ranges[{index}].{field_name} must be an integer.")
