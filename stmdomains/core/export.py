"""An explicit export scope and display choice, separate from prediction parameters."""

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class ExportOptions:
    csv: bool = True
    png: bool = True
    crop: tuple[float, float, float, float] | None = None
    image_width: int = 1200

    def __post_init__(self) -> None:
        if not self.csv and not self.png:
            raise ValueError('Wybierz CSV, PNG lub oba formaty.')
        if not 320 <= self.image_width <= 4096:
            raise ValueError('Szerokość obrazu musi mieścić się w 320–4096 px.')
        if self.crop is not None and (len(self.crop) != 4 or any(not isfinite(v) for v in self.crop)
                                      or self.crop[2] <= 0 or self.crop[3] <= 0):
            raise ValueError('Niepoprawny wycinek obrazu.')
