"""Validated domain formation settings, shared by calculations and their provenance."""

from collections.abc import Mapping
from dataclasses import asdict, dataclass, fields
from math import isfinite
from typing import Any, Literal


@dataclass(frozen=True)
class DomainSettings:
    minimum_domain_size: int = 8
    edge_distance_factor: float = 1.5
    geometry_mode: Literal["off", "hellinger_region"] = "hellinger_region"
    edge_max_hellinger: float = .20
    region_max_hellinger_diameter: float = .50
    raster_radius_factor: float = .85

    def __post_init__(self) -> None:
        if type(self.minimum_domain_size) is not int or not 1 <= self.minimum_domain_size <= 3000:
            raise ValueError("Minimum molekuł musi być liczbą całkowitą od 1 do 3000.")
        for name, value in (("Odległość łączenia", self.edge_distance_factor),
                            ("Zasięg maski", self.raster_radius_factor)):
            if not isfinite(value) or not .05 <= value <= 10.:
                raise ValueError(f"{name}: dozwolony zakres to 0,05–10 odstępów molekuł.")
        if self.geometry_mode not in ("off", "hellinger_region"):
            raise ValueError("Nieznany tryb zgodności geometrii.")
        if not (isfinite(self.edge_max_hellinger) and isfinite(self.region_max_hellinger_diameter)
                and 0 <= self.edge_max_hellinger <= self.region_max_hellinger_diameter <= 1):
            raise ValueError("Próg krawędzi musi być ≤ średnicy regionu; oba w zakresie 0–1.")

    def parameters(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_parameters(cls, parameters: Mapping[str, Any]) -> "DomainSettings":
        return cls(**{field.name: parameters[field.name] for field in fields(cls) if field.name in parameters})
