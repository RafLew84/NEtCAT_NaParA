"""Versioned settings of the single experimental hybrid level-set adaptation."""

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from math import isfinite
from typing import Any

METHOD = 'gibou_fedkiw_features_v1'


@dataclass(frozen=True)
class LevelSetSettings:
    regularization: float = .25
    iterations: int = 120

    def __post_init__(self) -> None:
        if (type(self.regularization) not in (int, float) or not isfinite(self.regularization)
                or not 0 <= self.regularization <= 2):
            raise ValueError('Siła regularyzacji: wymagany zakres 0–2.')
        if type(self.iterations) is not int or not 1 <= self.iterations <= 500:
            raise ValueError('Limit iteracji: liczba całkowita 1–500.')

    def parameters(self) -> dict[str, Any]:
        return {'domain_method': METHOD, 'levelset_settings': asdict(self)}

    @classmethod
    def from_parameters(cls, parameters: Mapping[str, Any]) -> 'LevelSetSettings':
        return cls(**parameters.get('levelset_settings', {}))
