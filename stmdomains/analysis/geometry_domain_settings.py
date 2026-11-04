"""Explicit tolerances for experimental domain formation from measurement 16."""

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from math import isfinite
from typing import Any


METHOD = 'geometry_tolerances_v1'


@dataclass(frozen=True)
class GeometryDomainSettings:
    angle_degrees: float = 12.
    spacing_percent: float = 16.
    minimum_coherence: float = .75
    minimum_local_count: int = 10

    def __post_init__(self) -> None:
        for name, low, high in (('angle_degrees', .1, 45.), ('spacing_percent', .1, 100.),
                                ('minimum_coherence', .75, 1.)):
            value = getattr(self, name)
            if type(value) not in (int, float) or not isfinite(value) or not low <= value <= high:
                raise ValueError(f'{name}: wymagany zakres {low}–{high}.')
        if type(self.minimum_local_count) is not int or not 10 <= self.minimum_local_count <= 3000:
            raise ValueError('Minimum lokalnych punktów: liczba całkowita 10–3000.')

    def parameters(self) -> dict[str, Any]:
        return {'domain_method': METHOD, 'geometry_tolerances': asdict(self)}

    @classmethod
    def from_parameters(cls, parameters: Mapping[str, Any]) -> 'GeometryDomainSettings':
        return cls(**parameters.get('geometry_tolerances', {}))
