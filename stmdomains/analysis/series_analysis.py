"""Stream one shared catalogue then frame outcomes, without retaining image results."""

from collections.abc import Callable, Iterator
from dataclasses import dataclass, replace
from uuid import uuid4

from stmdomains.analysis.config import model_parameters
from stmdomains.analysis.discovery import fit_shared_catalogue
from stmdomains.analysis.pipeline import analyze_frame
from stmdomains.analysis.series_settings import SeriesAnalysisPlan
from stmdomains.core.analysis_result import AnalysisCancelled, AnalysisInput, FrameAnalysis
from stmdomains.core.class_catalogue import ClassCatalogue
from stmdomains.core.immutable import plain_metadata


@dataclass(frozen=True)
class FrameOutcome:
    index: int
    result: FrameAnalysis | None = None
    error: str = ""


def validate_shared_catalogue(catalogue: ClassCatalogue | None, series_id: str, k: int) -> None:
    if catalogue is None or catalogue.scope == "current_frame":
        raise ValueError("Wybierz wspólny katalog z 07 albo dopasuj klasy z zakresu.")
    if catalogue.series_id != series_id or catalogue.k != k:
        raise ValueError("Wybrany katalog ma inną serię lub K. Dopasuj klasy ponownie.")
    if plain_metadata(catalogue.parameters) != model_parameters(k):
        raise ValueError("Katalog używa innych parametrów metody. Dopasuj klasy ponownie.")


def analyze_series(
    read_frame: Callable[[int], AnalysisInput], *, frame_count: int, series_id: str,
    plan: SeriesAnalysisPlan, catalogue: ClassCatalogue | None = None,
    run_id: str = "",
    cancelled: Callable[[], bool] = lambda: False, progress: Callable[[str], None] = lambda text: None,
) -> Iterator[ClassCatalogue | FrameOutcome]:
    def check() -> None:
        if cancelled():
            raise AnalysisCancelled()

    check()
    run_id = run_id or uuid4().hex
    indices, fit = plan.indices(frame_count), plan.fit_settings(frame_count)
    if fit is not None:
        catalogue = fit_shared_catalogue(read_frame, frame_count=frame_count, settings=fit,
                                         order_settings=plan.order_settings,
                                         cancelled=cancelled, progress=progress)
    validate_shared_catalogue(catalogue, series_id, plan.k)
    assert catalogue is not None
    check()
    yield catalogue
    for ordinal, index in enumerate(indices, 1):
        check()

        def report(text: str) -> None:
            progress(f"Analiza {ordinal}/{len(indices)} · klatka {index + 1}: {text}")

        report("odczyt…")
        try:
            data = read_frame(index)
            if data.series_id != series_id or data.frame.working_index != index:
                raise ValueError("Dane należą do innej serii lub klatki.")
            result = analyze_frame(data, catalogue=catalogue, settings=plan.domain_settings,
                                    order_settings=plan.order_settings,
                                    cancelled=cancelled, progress=report)
            result = replace(result, metadata={**result.metadata, "series_analysis": {
                "run_id": run_id, "working_indices": indices, "fit_source": plan.fit_source}})
            check()
            outcome = FrameOutcome(index, result)
        except AnalysisCancelled:
            raise
        except Exception as error:
            check()
            outcome = FrameOutcome(index, error=f"{type(error).__name__}: {error}")
        yield outcome
