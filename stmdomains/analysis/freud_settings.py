"""Units and limits for the optional, frame-local environment comparison."""

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from math import isfinite
from typing import Any

METHOD = 'freud_environments_v1'


@dataclass(frozen=True)
class FreudSettings:
    tolerance: float = .20
    neighbor_count: int = 4
    radius_factor: float = 2.
    registration: bool = False

    def __post_init__(self) -> None:
        for name, low, high in (('tolerance', .01, 1.), ('radius_factor', .5, 10.)):
            value = getattr(self, name)
            if type(value) not in (int, float) or not isfinite(value) or not low <= value <= high:
                raise ValueError(f'{name}: wymagany zakres {low}–{high}.')
        if type(self.neighbor_count) is not int or not 3 <= self.neighbor_count <= 8:
            raise ValueError('Liczba sąsiadów: liczba całkowita 3–8.')
        if type(self.registration) is not bool:
            raise ValueError('Dopasowanie obrotu musi być wartością logiczną.')

    def parameters(self) -> dict[str, Any]:
        return {'domain_method': METHOD, 'freud_settings': asdict(self)}

    @classmethod
    def from_parameters(cls, parameters: Mapping[str, Any]) -> 'FreudSettings':
        return cls(**parameters.get('freud_settings', {}))
