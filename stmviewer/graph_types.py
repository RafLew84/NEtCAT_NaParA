"""Lightweight graph attempt: measurements and positions, never a second image stack."""

from dataclasses import dataclass, field
from uuid import uuid4

XY = tuple[float, float]


@dataclass(frozen=True)
class GraphSource:
    source: str
    source_frame_index: int | None
    shape: tuple[int, int]
    pixels_sha256: str


@dataclass(frozen=True)
class GraphConfig:
    window: int
    weights_path: str
    weights_sha256: str
    requested_device: str
    device: str
    backend_settings: tuple[tuple[str, str], ...]
    libraries: tuple[tuple[str, str], ...]
    code_version: str
    settings_version: int = 1


@dataclass(frozen=True)
class GraphEdge:
    """d_ij moves j onto i; residual = solved Pj-Pi minus d_ij."""

    i: int
    j: int
    shift_xy: XY | None
    status: str
    reason: str | None = None
    quality_score: float | None = None
    residual_xy: XY | None = None


@dataclass(frozen=True)
class GraphTrial:
    sources: tuple[GraphSource, ...]
    config: GraphConfig
    edges: tuple[GraphEdge, ...]
    positions: tuple[XY, ...] | None
    chain_positions: tuple[XY, ...] | None
    components: tuple[tuple[int, ...], ...]
    bridges: tuple[tuple[int, int], ...]
    revision: str = field(default_factory=lambda: uuid4().hex)
    anchor: int = 0
    solver: str = 'equal-ls-v1'
    measured_pairs: int = 0
    reused_pairs: int = 0
    measurement_s: float = 0.
    solver_s: float = 0.
