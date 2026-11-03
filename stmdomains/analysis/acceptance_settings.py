"""Acceptance thresholds are independent of the fitted descriptor catalogue."""

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from math import isfinite
from typing import Any


@dataclass(frozen=True)
class ClassAcceptanceSettings:
    class_margin: float = .075
    class_radius_multiplier: float = 1.10

    def __post_init__(self) -> None:
        if not isfinite(self.class_margin) or not 0 <= self.class_margin <= 1:
            raise ValueError("Minimalny margines musi mieścić się w zakresie 0–1.")
        if not isfinite(self.class_radius_multiplier) or not .05 <= self.class_radius_multiplier <= 10:
            raise ValueError("Mnożnik promienia klasy musi mieścić się w zakresie 0,05–10.")

    def parameters(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_parameters(cls, parameters: Mapping[str, Any]) -> "ClassAcceptanceSettings":
        return cls(**{key: parameters[key] for key in cls().parameters() if key in parameters})
