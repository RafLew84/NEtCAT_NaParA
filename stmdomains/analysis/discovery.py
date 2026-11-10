"""Bounded class discovery across an explicit scope, followed by one-frame analysis."""

from collections.abc import Callable
from typing import Any

import numpy as np

from stmdomains.analysis.automatic_classes import AutoSelectionUnavailable, fit_auto_model
from stmdomains.analysis.class_settings import ClassFitSettings
from stmdomains.analysis.clustering import fit_model
from stmdomains.analysis.config import model_parameters
from stmdomains.analysis.domain_settings import DomainSettings
from stmdomains.analysis.descriptor_settings import DescriptorSettings
from stmdomains.analysis.order_settings import OrderSettings
from stmdomains.analysis.pipeline import analyze_frame, apply_prepared
from stmdomains.analysis.preparation import PreparedFrame, prepare_frame
from stmdomains.core.analysis_result import AnalysisCancelled, AnalysisInput, FrameAnalysis
from stmdomains.core.class_catalogue import ClassCatalogue

MAX_FIT_SAMPLES = 6000


def discover_classes(
    read_frame: Callable[[int], AnalysisInput], *, frame_count: int, current_index: int,
    settings: ClassFitSettings, domain_settings: DomainSettings = DomainSettings(),
    order_settings: OrderSettings = OrderSettings(),
    descriptor_settings: DescriptorSettings = DescriptorSettings(),
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
                               order_settings=order_settings, descriptor_settings=descriptor_settings, cancelled=cancelled, progress=progress,
                               class_count_mode=settings.class_count_mode, auto_max_k=settings.auto_max_k)
        if result.catalogue is None:
            raise ValueError(result.message)
        return result
    catalogue, target = _fit_shared(read_frame, indices, settings, domain_settings, check, progress,
                                    current_index, order_settings=order_settings, descriptor_settings=descriptor_settings)
    if target is None:
        data = read_frame(current_index)
        if data.series_id != catalogue.series_id or data.frame.working_index != current_index:
            raise ValueError("Bieżąca klatka pochodzi z innej serii.")
        target = prepare_frame(data, settings.preparation_k, domain_settings, check, progress, order_settings=order_settings, descriptor_settings=descriptor_settings)
    return apply_prepared(target, catalogue, domain_settings, check, progress)


def fit_shared_catalogue(
    read_frame: Callable[[int], AnalysisInput], *, frame_count: int, settings: ClassFitSettings,
    order_settings: OrderSettings = OrderSettings(),
    descriptor_settings: DescriptorSettings = DescriptorSettings(),
    cancelled: Callable[[], bool] = lambda: False, progress: Callable[[str], None] = lambda text: None,
) -> ClassCatalogue:
    """Discover once without computing domains on any target frame."""
    if settings.scope == "current_frame":
        raise ValueError("Analiza serii wymaga wspólnego katalogu z jawnego zakresu.")

    def check() -> None:
        if cancelled():
            raise AnalysisCancelled()

    check()
    catalogue, _ = _fit_shared(read_frame, settings.indices(0, frame_count), settings,
                                DomainSettings(), check, progress, order_settings=order_settings, descriptor_settings=descriptor_settings)
    return catalogue


def _fit_shared(
    read_frame: Callable[[int], AnalysisInput], indices: tuple[int, ...], settings: ClassFitSettings,
    domain_settings: DomainSettings, check: Callable[[], None], progress: Callable[[str], None],
    current_index: int | None = None,
    *, order_settings: OrderSettings = OrderSettings(),
    descriptor_settings: DescriptorSettings = DescriptorSettings(),
) -> tuple[ClassCatalogue, PreparedFrame | FrameAnalysis | None]:
    if len(indices) > MAX_FIT_SAMPLES:
        raise ValueError(f"Wybierz najwyżej {MAX_FIT_SAMPLES} klatek do jednego dopasowania.")
    per_frame_limit = MAX_FIT_SAMPLES // len(indices)
    parts = []
    active_count = useful_count = 0
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
        prepared = prepare_frame(data, settings.preparation_k, domain_settings, check, report, order_settings=order_settings, descriptor_settings=descriptor_settings)
        active_count += prepared.active_count if isinstance(prepared, FrameAnalysis) else len(prepared.active)
        if index == current_index:
            target = prepared
        if isinstance(prepared, FrameAnalysis):
            records.append({"working_index": index, "source_index": data.frame.source_index,
                            "input_sha256": prepared.metadata.get("input_sha256"), "used_samples": 0,
                            "status": prepared.status, "reason": prepared.message})
            continue
        rows = np.flatnonzero(prepared.fit_mask)
        useful_count += len(rows)
        if len(rows) > per_frame_limit:
            rows = rows[np.linspace(0, len(rows) - 1, per_frame_limit, dtype=int)]
        parts.append(prepared.features[rows])
        records.append(prepared.fit_record(rows))
    check()
    state: dict[str, Any] | None
    if settings.class_count_mode == "auto":
        selected = np.concatenate(parts) if parts else np.empty((0, 0))
        try:
            state = fit_auto_model(selected, settings.auto_max_k, check, active_count=active_count,
                                   useful_count=useful_count, progress=progress,
                                   pca_max_components=descriptor_settings.pca_max_components)
        except AutoSelectionUnavailable as error:
            raise AutoSelectionUnavailable({**error.decision, "fit_scope": settings.scope,
                                            "fit_working_indices": indices, "fit_frames": records}) from error
    else:
        if not parts or not sum(len(part) for part in parts):
            raise ValueError("Brak użytecznych otoczeń w wybranym zakresie. Katalog klas nie został zmieniony.")
        selected = np.concatenate(parts)
        progress(f"Dopasowanie wspólnego K{settings.k} z {len(selected)} otoczeń…")
        state = fit_model(selected, settings.k, check, pca_max_components=descriptor_settings.pca_max_components)
    if state is None:
        raise ValueError(f"Za mało użytecznych lub różnych otoczeń dla K{settings.k}. Zmniejsz K lub zmień zakres.")
    state["fit_scope"] = settings.scope
    assert series_id is not None
    catalogue = ClassCatalogue(series_id, settings.scope, indices, state,
                               {"frames": records, "sampling": {"rule": "evenly_spaced_per_frame",
                                "maximum_total_samples": MAX_FIT_SAMPLES, "maximum_per_frame": per_frame_limit}},
                               model_parameters(state["k"], descriptor_settings))
    check()
    return catalogue, target
