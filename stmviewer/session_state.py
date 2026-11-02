"""A portable snapshot of the open movie, active alignment, and presentation."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from stmviewer.frame import ImageFrame
from stmviewer.registration import RegistrationResult

if TYPE_CHECKING:
    from stmviewer.graph_types import GraphTrial


@dataclass(frozen=True)
class ViewTransform:
    zoom: float = 1.0
    pan_xy: tuple[float, float] = (0.0, 0.0)


@dataclass(frozen=True)
class SessionViewState:
    index: int = 0
    view: str = 'original'
    gamma: float = 1.0
    pixel_proportions: bool = False
    fps: int = 5
    loop: bool = False
    method: str = 'phase_correlation'
    deep_weights: str | None = None
    deep_device: str = 'auto'
    navigation: dict[str, ViewTransform] = field(default_factory=dict)
    deep_source: str | None = None
    deep_interpreter: str | None = None
    deep_preset: str = 'turbo'
    deep_samples: int = 1000
    deep_seed: int = 20261102


@dataclass(frozen=True)
class SessionState:
    frames: tuple[ImageFrame, ...]
    registration: RegistrationResult | None = None
    display: SessionViewState = field(default_factory=SessionViewState)
    graph: GraphTrial | None = None
