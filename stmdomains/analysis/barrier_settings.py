"""Existing positive, near-horizontal image-step detector; lengths in NN spacings."""

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from math import isfinite
from typing import Any


@dataclass(frozen=True)
class BarrierSettings:
    low_percentile: float = 65.
    high_percentile: float = 90.
    minimum_span_factor: float = 3.
    maximum_gap_factor: float = 5 / 3
    maximum_tilt_degrees: float = 55.
    dilation_factor: float = 1 / 12

    def __post_init__(self) -> None:
        for name, low, high in (('low_percentile', 0, 99.9), ('high_percentile', 0, 100),
                                ('minimum_span_factor', .1, 100), ('maximum_gap_factor', 0, 3),
                                ('maximum_tilt_degrees', 1, 85), ('dilation_factor', 0, 2)):
            value = getattr(self, name)
            if type(value) not in (int, float) or not isfinite(value) or not low <= value <= high:
                raise ValueError(f'Bariery: {name} musi mieścić się w {low}–{high}.')
        if self.low_percentile >= self.high_percentile:
            raise ValueError('Dolny percentyl kontrastu musi być mniejszy od górnego.')

    def parameters(self) -> dict[str, Any]:
        return {'barrier_' + key: value for key, value in asdict(self).items()}

    @classmethod
    def from_parameters(cls, parameters: Mapping[str, Any]) -> 'BarrierSettings':
        return cls(**{key: parameters['barrier_' + key] for key in cls.__dataclass_fields__
                      if 'barrier_' + key in parameters})
