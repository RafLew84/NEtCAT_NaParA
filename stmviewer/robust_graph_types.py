"""Immutable Huber attempts over the existing graph's unchanged measurements."""
from dataclasses import dataclass, field
from uuid import uuid4

from stmviewer.graph_types import XY


@dataclass(frozen=True)
class RobustConfig:
    threshold_px: float = 2.0
    max_iterations: int = 200
    position_tolerance_px: float = 1e-5
    objective_relative_tolerance: float = 1e-8
    gradient_tolerance: float = 1e-6
    max_condition: float = 1e12
    solver: str = 'block-huber-irls-v1'
    condition_method: str = 'anchored-laplacian-1norm-v1'


@dataclass(frozen=True)
class RobustTrial:
    measurement_id: str
    config: RobustConfig
    # Only converged attempts expose positions suitable for candidate playback.
    positions: tuple[XY, ...] | None
    # Diagnostic last finite iterate may exist even when convergence was refused.
    last_positions: tuple[XY, ...] | None
    residuals: tuple[XY | None, ...]
    weights: tuple[float | None, ...]
    status: str
    reason: str
    iterations: int
    objective: float | None
    ls_objective: float | None
    max_step_px: float | None
    relative_cost_change: float | None
    gradient_inf: float | None
    condition_estimate: float | None
    solver_s: float
    revision: str = field(default_factory=lambda: uuid4().hex)
