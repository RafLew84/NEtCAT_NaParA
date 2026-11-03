"""One immutable request separates class discovery from the frames to analyse."""

from dataclasses import dataclass
from typing import Literal

from stmdomains.analysis.class_settings import ClassFitSettings
from stmdomains.analysis.domain_settings import DomainSettings
from stmdomains.analysis.order_settings import OrderSettings


@dataclass(frozen=True)
class SeriesAnalysisPlan:
    start: int = 0
    end: int = 0
    whole_series: bool = False
    k: int = 5
    fit_source: Literal["same_range", "selected_range", "whole_series", "existing"] = "same_range"
    fit_start: int = 0
    fit_end: int = 0
    domain_settings: DomainSettings = DomainSettings()
    order_settings: OrderSettings = OrderSettings()

    def indices(self, frame_count: int) -> tuple[int, ...]:
        return ClassFitSettings(self.k, "whole_series" if self.whole_series else "selected_range",
                                0 if self.whole_series else self.start,
                                0 if self.whole_series else self.end).indices(0, frame_count)

    def fit_settings(self, frame_count: int) -> ClassFitSettings | None:
        indices = self.indices(frame_count)
        if self.fit_source == "existing":
            return None
        if self.fit_source == "same_range":
            return ClassFitSettings(self.k, "whole_series" if self.whole_series else "selected_range",
                                    indices[0], indices[-1])
        if self.fit_source not in ("selected_range", "whole_series"):
            raise ValueError("Nieznane źródło klas dla analizy serii.")
        settings = ClassFitSettings(self.k, self.fit_source,
                                    self.fit_start if self.fit_source == "selected_range" else 0,
                                    self.fit_end if self.fit_source == "selected_range" else 0)
        settings.indices(0, frame_count)
        return settings
