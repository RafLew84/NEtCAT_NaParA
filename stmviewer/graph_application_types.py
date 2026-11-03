"""Frozen applied graph and one image-free predecessor for explicit restore."""
from dataclasses import dataclass

from stmviewer.correspondence_types import CorrespondenceDiagnostics
from stmviewer.deep_ecc import HybridDiagnostics
from stmviewer.graph_types import GraphSource, GraphTrial, XY
from stmviewer.local_consensus import LocalDiagnostics
from stmviewer.manual_movie_types import MovieBaselineFrame, MovieCorrection, MovieSource

SourceGeometry = tuple[float | None, float | None, float | None, float | None]


@dataclass(frozen=True)
class GraphApplication:
    graph: GraphTrial
    robust_revision: str | None = None
    settings_version: int = 1

    @property
    def positions(self) -> tuple[XY, ...]:
        if self.robust_revision is None:
            positions = self.graph.positions
        else:
            variants = [item for item in self.graph.robust_trials
                        if item.revision == self.robust_revision]
            if len(variants) != 1 or variants[0].status != 'converged':
                raise ValueError('Graf: wybrany wariant Hubera nie jest kompletny.')
            positions = variants[0].positions
        if positions is None:
            raise ValueError('Graf: brak kompletnego rozwiązania.')
        return positions

    @property
    def solver(self) -> str:
        if self.robust_revision is None:
            return self.graph.solver
        return next(item.config.solver for item in self.graph.robust_trials
                    if item.revision == self.robust_revision)


@dataclass(frozen=True)
class MovieSnapshot:
    sources: tuple[GraphSource, ...]
    source_geometry: tuple[SourceGeometry, ...]
    final_frames: tuple[MovieBaselineFrame, ...]
    reference: MovieSource
    canvas_shape: tuple[int, int]
    padding_ltrb: tuple[int, int, int, int]
    pixel_size_nm: tuple[float, float] | None
    method: str
    device: str
    settings_version: int
    revision: str
    baseline: tuple[MovieBaselineFrame, ...]
    corrections: tuple[MovieCorrection, ...]
    corrections_editable: bool
    pair_diagnostics: tuple[HybridDiagnostics | None, ...]
    local_diagnostics: tuple[LocalDiagnostics | None, ...]
    graph_application: GraphApplication | None = None
    correspondence_diagnostics: tuple[CorrespondenceDiagnostics | None, ...] = ()

    @property
    def final_positions(self) -> tuple[XY, ...]:
        return tuple(item.shift_xy for item in self.final_frames)
