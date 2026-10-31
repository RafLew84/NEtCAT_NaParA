"""A portable snapshot of the open movie, active alignment, and presentation."""
from dataclasses import dataclass, field

from stmviewer.frame import ImageFrame
from stmviewer.registration import RegistrationResult


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


@dataclass(frozen=True)
class SessionState:
    frames: tuple[ImageFrame, ...]
    registration: RegistrationResult | None = None
    display: SessionViewState = field(default_factory=SessionViewState)
