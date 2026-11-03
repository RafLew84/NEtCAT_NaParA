"""A bounded descriptor definition; every field belongs to the fitted catalogue."""

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from math import isfinite
from typing import Any


@dataclass(frozen=True)
class DescriptorSettings:
    descriptor_radial_bins: int = 14
    descriptor_angle_bins: int = 36
    descriptor_sigma_factor: float = 1.25
    descriptor_pair_distance_range: tuple[float, float] = (.55, 2.8)
    pca_max_components: int = 24

    def __post_init__(self) -> None:
        for name, low, high in (('descriptor_radial_bins', 4, 32), ('descriptor_angle_bins', 8, 72),
                                ('pca_max_components', 1, 64)):
            value = getattr(self, name)
            if type(value) is not int or not low <= value <= high:
                raise ValueError(f'{name}: wymagana liczba całkowita {low}–{high}.')
        if self.dimension > 2048 or self.pca_max_components > self.dimension:
            raise ValueError('Histogram: maks. 2048 pól; liczba składowych PCA nie może przekraczać liczby pól.')
        if (type(self.descriptor_sigma_factor) not in (float, int) or not isfinite(self.descriptor_sigma_factor)
                or not .25 <= self.descriptor_sigma_factor <= 3):
            raise ValueError('Sigma opisu musi mieścić się w 0,25–3 rozstawów molekuł.')
        bounds = self.descriptor_pair_distance_range
        if (not isinstance(bounds, (tuple, list)) or len(bounds) != 2 or
                any(type(v) not in (int, float) or not isfinite(v) for v in bounds) or
                not .1 <= bounds[0] < bounds[1] <= 4 or bounds[1] - bounds[0] < .1):
            raise ValueError('Zakres odległości par: 0,1 ≤ minimum < maksimum ≤ 4, szerokość co najmniej 0,1 rozstawu.')
        object.__setattr__(self, 'descriptor_pair_distance_range', tuple(bounds))

    @property
    def dimension(self) -> int:
        return self.descriptor_radial_bins * self.descriptor_angle_bins

    def parameters(self) -> dict[str, Any]:
        values = asdict(self)
        values['descriptor_pair_distance_range'] = list(self.descriptor_pair_distance_range)
        return values

    @classmethod
    def from_parameters(cls, parameters: Mapping[str, Any]) -> 'DescriptorSettings':
        return cls(**{key: parameters[key] for key in cls.__dataclass_fields__ if key in parameters})
