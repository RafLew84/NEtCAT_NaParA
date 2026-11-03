"""Stream a local or shared catalogue and outcomes from one complete configuration."""

from collections.abc import Callable, Iterator, Mapping
from typing import Any
from dataclasses import dataclass, replace
from uuid import uuid4

from stmdomains.analysis.automatic_classes import AutoSelectionUnavailable
from stmdomains.analysis.config import model_parameters
from stmdomains.analysis.discovery import fit_shared_catalogue
from stmdomains.analysis.pipeline import analyze_frame, validate_catalogue
from stmdomains.analysis.series_settings import SeriesAnalysisPlan
from stmdomains.core.analysis_result import AnalysisCancelled, AnalysisInput, FrameAnalysis
from stmdomains.core.class_catalogue import ClassCatalogue
from stmdomains.core.immutable import freeze_metadata, plain_metadata


@dataclass(frozen=True)
class FrameOutcome:
    index: int
    result: FrameAnalysis | None = None
    error: str = ""


@dataclass(frozen=True)
class ClassSelectionFailure:
    decision: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "decision", freeze_metadata(self.decision))


def validate_shared_catalogue(catalogue: ClassCatalogue | None, series_id: str, k: int) -> None:
    if catalogue is None or catalogue.scope == "current_frame":
        raise ValueError("Wybierz wspólny katalog albo dopasuj klasy z zakresu.")
    if catalogue.series_id != series_id or catalogue.k != k:
        raise ValueError("Wybrany katalog ma inną serię lub K. Dopasuj klasy ponownie.")
    if plain_metadata(catalogue.parameters) != model_parameters(k):
        raise ValueError("Katalog używa innych parametrów metody. Dopasuj klasy ponownie.")


def validate_plan_catalogue(
    catalogue: ClassCatalogue | None, series_id: str, plan: SeriesAnalysisPlan,
) -> None:
    """Cheap scope validation; exact local input identity is checked by the worker."""
    if catalogue is not None and catalogue.scope == "current_frame" and plan.current_frame:
        if catalogue.series_id != series_id or catalogue.k != plan.k or catalogue.frame_indices != (plan.start,):
            raise ValueError("Lokalny katalog należy do innej klatki. Dopasuj nowe klasy lub wybierz wspólny katalog.")
        if plain_metadata(catalogue.parameters) != model_parameters(plan.k):
            raise ValueError("Katalog używa innych parametrów metody. Dopasuj klasy ponownie.")
        return
    validate_shared_catalogue(catalogue, series_id, plan.k)


def analyze_series(
    read_frame: Callable[[int], AnalysisInput], *, frame_count: int, series_id: str,
    plan: SeriesAnalysisPlan, catalogue: ClassCatalogue | None = None,
    run_id: str = "",
    cancelled: Callable[[], bool] = lambda: False, progress: Callable[[str], None] = lambda text: None,
) -> Iterator[ClassCatalogue | FrameOutcome | ClassSelectionFailure]:
    def check() -> None:
        if cancelled():
            raise AnalysisCancelled()

    check()
    run_id = run_id or uuid4().hex
    indices, fit = plan.indices(frame_count), plan.fit_settings(frame_count)

    def result_with_run(result: FrameAnalysis) -> FrameAnalysis:
        return replace(result, metadata={**result.metadata, "series_analysis": {
            "run_id": run_id, "working_indices": indices, "fit_source": plan.fit_source}})

    if fit is not None and fit.scope == "current_frame":
        data = read_frame(indices[0])
        if data.series_id != series_id or data.frame.working_index != indices[0]:
            raise ValueError("Dane należą do innej serii lub klatki.")
        result = analyze_frame(data, k=plan.k, settings=plan.domain_settings, acceptance=plan.acceptance,
                               order_settings=plan.order_settings, cancelled=cancelled, progress=progress,
                               class_count_mode=plan.class_count_mode, auto_max_k=plan.auto_max_k)
        check()
        if result.catalogue is not None:
            yield result.catalogue
        check()
        yield FrameOutcome(indices[0], result_with_run(result))
        return
    if fit is not None:
        try:
            catalogue = fit_shared_catalogue(read_frame, frame_count=frame_count, settings=fit,
                                             order_settings=plan.order_settings,
                                             cancelled=cancelled, progress=progress)
        except AutoSelectionUnavailable as error:
            check()
            yield ClassSelectionFailure(error.decision)
            return
    validation_plan = replace(plan, k=catalogue.k) if fit is not None and catalogue is not None else plan
    validate_plan_catalogue(catalogue, series_id, validation_plan)
    assert catalogue is not None
    if catalogue.scope == "current_frame":
        validate_catalogue(read_frame(indices[0]), catalogue)
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
                                    acceptance=plan.acceptance,
                                    order_settings=plan.order_settings,
                                    cancelled=cancelled, progress=report)
            result = result_with_run(result)
            check()
            outcome = FrameOutcome(index, result)
        except AnalysisCancelled:
            raise
        except Exception as error:
            check()
            outcome = FrameOutcome(index, error=f"{type(error).__name__}: {error}")
        yield outcome
