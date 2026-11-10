"""A working series maps displayed frames onto one immutable MPP stack."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4
from tempfile import TemporaryDirectory

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True)
class FrameData:
    working_index: int
    source_index: int
    image: NDArray[np.float64] = field(repr=False)
    time_s: float | None = None


@dataclass(frozen=True)
class Series:
    session_path: Path
    source_path: Path
    source_frame_indices: tuple[int, ...]
    active_frame_index: int
    raw_frames: NDArray[np.float64] = field(repr=False)
    diagnostics: tuple[str, ...] = ()
    raw_payload: dict[str, Any] = field(default_factory=dict, repr=False)
    raw_header: dict[str, Any] = field(default_factory=dict, repr=False)
    source_times_s: tuple[float, ...] | None = None
    identity: str = field(default_factory=lambda: uuid4().hex)

    source_sha256: str = ""
    provenance: dict[str, Any] = field(default_factory=dict, repr=False)
    source_cache: TemporaryDirectory[str] | None = field(default=None, repr=False, compare=False)

    @property
    def frame_count(self) -> int:
        return len(self.source_frame_indices)

    @property
    def frame_shape(self) -> tuple[int, int]:
        return int(self.raw_frames.shape[1]), int(self.raw_frames.shape[2])

    def frame(self, index: int) -> FrameData:
        if not 0 <= index < self.frame_count:
            raise IndexError("Indeks klatki poza zakresem serii.")
        source_index = self.source_frame_indices[index]
        time_s = None if self.source_times_s is None else self.source_times_s[source_index]
        return FrameData(index, source_index, self.raw_frames[source_index], time_s)
