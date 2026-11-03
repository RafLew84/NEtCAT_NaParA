"""Order gate settings shared by observations and generated null controls."""

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from math import isfinite
from typing import Any


@dataclass(frozen=True)
class OrderSettings:
    order_quantile: float = .95
    order_minimum_local_count: int = 10
    order_minimum_effective_count: float = 8.
    order_radius_factor: float = 3.
    order_sigma_factor: float = 4 / 3

    def __post_init__(self) -> None:
        limits = (("Kwantyl kontroli", self.order_quantile, .5, .999),
                  ("Minimum efektywne", self.order_minimum_effective_count, 2., 200.),
                  ("Promień otoczenia", self.order_radius_factor, .5, 6.),
                  ("Sigma otoczenia", self.order_sigma_factor, .25, 4.))
        for name, value, lower, upper in limits:
            if not isfinite(value) or not lower <= value <= upper:
                raise ValueError(f"{name}: dozwolony zakres {lower:g}–{upper:g}.")
        if type(self.order_minimum_local_count) is not int or not 3 <= self.order_minimum_local_count <= 200:
            raise ValueError("Minimum punktów lokalnych musi być liczbą całkowitą od 3 do 200.")

    def parameters(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_parameters(cls, parameters: Mapping[str, Any]) -> "OrderSettings":
        return cls(**{key: parameters[key] for key in cls().parameters() if key in parameters})
