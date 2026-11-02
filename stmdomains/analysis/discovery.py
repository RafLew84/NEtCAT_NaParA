"""Bounded class discovery across an explicit scope, followed by one-frame analysis."""

from collections.abc import Callable
from typing import Any

import numpy as np

from stmdomains.analysis.class_settings import ClassFitSettings
from stmdomains.analysis.clustering import fit_model
from stmdomains.analysis.config import model_parameters
from stmdomains.analysis.domain_settings import DomainSettings
from stmdomains.analysis.pipeline import analyze_frame, apply_prepared
from stmdomains.analysis.preparation import PreparedFrame, prepare_frame
from stmdomains.core.analysis_result import AnalysisCancelled, AnalysisInput, FrameAnalysis
from stmdomains.core.class_catalogue import ClassCatalogue

MAX_FIT_SAMPLES = 6000


def discover_classes(
    read_frame: Callable[[int], AnalysisInput], *, frame_count: int, current_index: int,
    settings: ClassFitSettings, domain_settings: DomainSettings = DomainSettings(),
    cancelled: Callable[[], bool] = lambda: False,
    progress: Callable[[str], None] = lambda text: None,
) -> FrameAnalysis:
    def check() -> None:
        if cancelled():
            raise AnalysisCancelled()

    check()
    indices = settings.indices(current_index, frame_count)
    if settings.scope == "current_frame":
        result = analyze_frame(read_frame(current_index), k=settings.k, settings=domain_settings,
                               cancelled=cancelled, progress=progress)
        if result.catalogue is None:
            raise ValueError(result.message)
        return result
    if len(indices) > MAX_FIT_SAMPLES:
        raise ValueError(f"Wybierz najwyżej {MAX_FIT_SAMPLES} klatek do jednego dopasowania.")
    per_frame_limit = MAX_FIT_SAMPLES // len(indices)
    parts = []
    records: list[dict[str, Any]] = []
    target: PreparedFrame | FrameAnalysis | None = None
    series_id: str | None = None
    for ordinal, index in enumerate(indices, 1):
        check()
        data = read_frame(index)
        if data.frame.working_index != index or (series_id is not None and data.series_id != series_id):
            raise ValueError("Dane zakresu pochodzą z innej klatki lub serii.")
        series_id = data.series_id

        def report(text: str) -> None:
            progress(f"Odkrywanie klas {ordinal}/{len(indices)} · klatka {index + 1}: {text}")

        report("przygotowanie danych…")
        prepared = prepare_frame(data, settings.k, domain_settings, check, report)
        if index == current_index:
            target = prepared
        if isinstance(prepared, FrameAnalysis):
            records.append({"working_index": index, "source_index": data.frame.source_index,
                            "input_sha256": prepared.metadata.get("input_sha256"), "used_samples": 0,
                            "status": prepared.status, "reason": prepared.message})
            continue
        rows = np.flatnonzero(prepared.fit_mask)
        if len(rows) > per_frame_limit:
            rows = rows[np.linspace(0, len(rows) - 1, per_frame_limit, dtype=int)]
        parts.append(prepared.features[rows])
        records.append(prepared.fit_record(rows))
    check()
    if not parts or not sum(len(part) for part in parts):
        raise ValueError("Brak użytecznych otoczeń w wybranym zakresie. Katalog klas nie został zmieniony.")
    selected = np.concatenate(parts)
    progress(f"Dopasowanie wspólnego K{settings.k} z {len(selected)} otoczeń…")
    state = fit_model(selected, settings.k, check)
    if state is None:
        raise ValueError(f"Za mało użytecznych lub różnych otoczeń dla K{settings.k}. Zmniejsz K lub zmień zakres.")
    state["fit_scope"] = settings.scope
    assert series_id is not None
    catalogue = ClassCatalogue(series_id, settings.scope, indices, state,
                               {"frames": records, "sampling": {"rule": "evenly_spaced_per_frame",
                                "maximum_total_samples": MAX_FIT_SAMPLES, "maximum_per_frame": per_frame_limit}},
                               model_parameters(settings.k))
    check()
    if target is None:
        data = read_frame(current_index)
        if data.series_id != series_id or data.frame.working_index != current_index:
            raise ValueError("Bieżąca klatka pochodzi z innej serii.")
        target = prepare_frame(data, settings.k, domain_settings, check, progress)
    return apply_prepared(target, catalogue, domain_settings, check, progress)
