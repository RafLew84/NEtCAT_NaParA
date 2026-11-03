"""Reapply acceptance to the displayed result's catalogue, never discover classes."""

from collections.abc import Callable

from stmdomains.analysis.acceptance_settings import ClassAcceptanceSettings
from stmdomains.analysis.domain_settings import DomainSettings
from stmdomains.analysis.order_settings import OrderSettings
from stmdomains.analysis.pipeline import analyze_frame
from stmdomains.analysis.provenance import input_fingerprint
from stmdomains.core.analysis_result import AnalysisCancelled, AnalysisInput, FrameAnalysis


def recalculate_class_acceptance(
    data: AnalysisInput, previous: FrameAnalysis, settings: ClassAcceptanceSettings, *,
    cancelled: Callable[[], bool] = lambda: False,
    progress: Callable[[str], None] = lambda text: None,
) -> FrameAnalysis:
    if cancelled():
        raise AnalysisCancelled()
    if previous.status != "complete" or previous.catalogue is None:
        raise ValueError("Najpierw oblicz klasy i domeny tej klatki w aplikacji.")
    if (data.series_id != previous.series_id or data.frame.working_index != previous.working_index
            or data.frame.source_index != previous.source_index
            or input_fingerprint(data) != previous.metadata.get("input_sha256")):
        raise ValueError("Dane różnią się od wyświetlanego wyniku. Wykonaj ponownie «Analizuj klatkę».")
    progress("Przeliczanie akceptacji przy zachowanym katalogu klas…")
    return analyze_frame(data, catalogue=previous.catalogue,
                         settings=DomainSettings.from_parameters(previous.parameters), acceptance=settings,
                         order_settings=OrderSettings.from_parameters(previous.parameters),
                         cancelled=cancelled, progress=progress)
