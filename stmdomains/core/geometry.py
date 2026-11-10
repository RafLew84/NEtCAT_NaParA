"""Independent, immutable measurements of positional order; angles are axial."""

from collections.abc import Mapping
from dataclasses import dataclass
from math import isfinite
from types import MappingProxyType
from typing import Any

from stmdomains.core.immutable import freeze_metadata


@dataclass(frozen=True)
class PixelCalibration:
    x: float = 1.
    y: float = 1.
    unit: str = 'px'
    source: str = 'Brak kalibracji fizycznej; metryka pikselowa.'

    def __post_init__(self) -> None:
        if self.unit not in ('px', 'nm') or any(not isfinite(v) or v <= 0 for v in (self.x, self.y)):
            raise ValueError('Kalibracja wymaga dodatnich skończonych skal X/Y i jednostki px albo nm.')
        if self.unit == 'px' and (self.x, self.y) != (1., 1.):
            raise ValueError('Bez kalibracji fizycznej obie osie mają jednostkę 1 px.')


@dataclass(frozen=True)
class RowAxis:
    row_angle_deg: float
    normal_angle_deg: float
    period: float
    coherence: float


@dataclass(frozen=True)
class MoleculeGeometry:
    detection_id: str
    center_xy: tuple[float, float]
    status: str
    reason: str = ''
    axes: tuple[RowAxis, ...] = ()
    local_count: int = 0
    effective_count: float = 0.
    radius: float | None = None
    angle_stability_deg: float | None = None
    period_stability_fraction: float | None = None
    touches_edge: bool = False


@dataclass(frozen=True)
class FrameGeometry:
    series_id: str
    working_index: int
    source_index: int
    calibration: PixelCalibration
    molecules: Mapping[str, MoleculeGeometry]
    parameters: Mapping[str, Any]
    metadata: Mapping[str, Any]
    message: str = ''

    def __post_init__(self) -> None:
        object.__setattr__(self, 'molecules', MappingProxyType(dict(self.molecules)))
        object.__setattr__(self, 'parameters', freeze_metadata(self.parameters))
        object.__setattr__(self, 'metadata', freeze_metadata(self.metadata))
