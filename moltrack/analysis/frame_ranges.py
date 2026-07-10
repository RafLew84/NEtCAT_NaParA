from __future__ import annotations

from dataclasses import dataclass


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
