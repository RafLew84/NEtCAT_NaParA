"""Explicit manual class count and discovery scope; UI frame numbers are one-based."""

from dataclasses import dataclass

from stmdomains.analysis.clustering import validate_k
from stmdomains.core.class_catalogue import FitScope


@dataclass(frozen=True)
class ClassFitSettings:
    k: int = 5
    scope: FitScope = "current_frame"
    start: int = 0
    end: int = 0

    def __post_init__(self) -> None:
        validate_k(self.k)
        if self.scope not in ("current_frame", "selected_range", "whole_series"):
            raise ValueError("Nieznany zakres odkrywania klas.")
        if type(self.start) is not int or type(self.end) is not int or not 0 <= self.start <= self.end:
            raise ValueError("Początek zakresu musi być nie większy od końca.")

    def indices(self, current_index: int, frame_count: int) -> tuple[int, ...]:
        if not 0 <= current_index < frame_count:
            raise ValueError("Bieżąca klatka jest poza serią.")
        if self.scope == "current_frame":
            return (current_index,)
        if self.scope == "whole_series":
            return tuple(range(frame_count))
        if self.end >= frame_count:
            raise ValueError("Wybrany zakres wychodzi poza serię.")
        return tuple(range(self.start, self.end + 1))
