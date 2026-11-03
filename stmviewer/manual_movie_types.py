"""Lightweight portable provenance of manual movie corrections; no image arrays."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from stmviewer.graph_movie_provenance import GraphMovieProvenance


@dataclass(frozen=True)
class MovieSource:
    source: str
    source_frame_index: int | None


@dataclass(frozen=True)
class MovieBaselineFrame:
    source: MovieSource
    shift_xy: tuple[float, float]
    status: str
    quality_score: float | None
    inherited_uncertainty: bool


@dataclass(frozen=True)
class MovieCorrection:
    reference: MovieSource
    moving: MovieSource
    baseline_xy: tuple[float, float]
    start_xy: tuple[float, float]
    correction_xy: tuple[int, int]
    source_label: str | None
    shift_xy: tuple[float, float]
    settings_version: int = 1


@dataclass(frozen=True)
class MovieHistory:
    revision: str
    settings_version: int
    baseline: tuple[MovieBaselineFrame, ...]
    corrections: tuple[MovieCorrection, ...]
    graph_provenance: 'GraphMovieProvenance | None' = None
