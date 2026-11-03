"""Analyze raw inputs using either a new local catalogue or an explicit saved one."""

from collections.abc import Callable
from dataclasses import replace
from typing import Any, Literal

import numpy as np

from stmdomains.analysis.automatic_classes import AutoSelectionUnavailable, fit_auto_model
from stmdomains.analysis.class_settings import ClassFitSettings
from stmdomains.analysis.barriers import image_barriers
from stmdomains.analysis.acceptance_settings import ClassAcceptanceSettings
from stmdomains.analysis.clustering import apply_classes, fit_model
from stmdomains.analysis.config import COLORS, PARAMETERS, model_parameters
from stmdomains.analysis.domain_settings import DomainSettings
from stmdomains.analysis.order_settings import OrderSettings
from stmdomains.analysis.preparation import PreparedFrame, prepare_frame
from stmdomains.analysis.provenance import input_fingerprint
from stmdomains.analysis.segmentation import segment_domains
from stmdomains.core.analysis_result import AnalysisCancelled, AnalysisInput, FrameAnalysis, MoleculeAssignment, ResultClass
from stmdomains.core.class_catalogue import ClassCatalogue
from stmdomains.core.immutable import plain_metadata


def analyze_frame(
    data: AnalysisInput, *, settings: DomainSettings = DomainSettings(), k: int = 5,
    catalogue: ClassCatalogue | None = None,
    class_count_mode: Literal["manual", "auto"] = "manual", auto_max_k: int = 8,
    acceptance: ClassAcceptanceSettings = ClassAcceptanceSettings(),
    order_settings: OrderSettings = OrderSettings(),
    cancelled: Callable[[], bool] = lambda: False,
    progress: Callable[[str], None] = lambda text: None,
) -> FrameAnalysis:
    def check() -> None:
        if cancelled():
            raise AnalysisCancelled()

    check()
    if catalogue is not None:
        k = catalogue.k
        validate_catalogue(data, catalogue)
    request = ClassFitSettings(k=k, class_count_mode=class_count_mode, auto_max_k=auto_max_k)
    prepared = prepare_frame(data, k if catalogue else request.preparation_k, settings, check, progress,
                             order_settings=order_settings)
    state: dict[str, Any] | None
    if catalogue is None:
        base = prepared if isinstance(prepared, FrameAnalysis) else prepared.base
        if class_count_mode == "auto":
            samples = np.empty((0, 0)) if isinstance(prepared, FrameAnalysis) else prepared.features[prepared.fit_mask]
            try:
                state = fit_auto_model(samples, auto_max_k, check, active_count=base.active_count,
                                       useful_count=len(samples), progress=progress)
            except AutoSelectionUnavailable as error:
                decision = {**error.decision, "fit_scope": "current_frame",
                            "fit_working_indices": (data.frame.working_index,),
                            "fit_frames": [{"working_index": data.frame.working_index,
                                            "source_index": data.frame.source_index,
                                            "input_sha256": base.metadata.get("input_sha256"),
                                            "preparation_reason": base.message}]}
                return replace(base, message=str(error) + (" " + base.message if base.message else ""),
                               parameters={**base.parameters, **acceptance.parameters(), "k": None,
                                           "class_count_mode": "auto", "auto_max_k": auto_max_k},
                               metadata={**base.metadata, "class_selection": decision})
        else:
            if isinstance(prepared, FrameAnalysis):
                return replace(prepared, parameters={**prepared.parameters, **acceptance.parameters()})
            progress(f"Dopasowanie lokalnych klas K{k}…")
            state = fit_model(prepared.features[prepared.fit_mask], k, check)
        if state is None:
            result = replace(base, message=f"Za mało użytecznych lub różnych otoczeń do dopasowania K{k}.")
            return replace(result, parameters={**result.parameters, **acceptance.parameters()})
        assert isinstance(prepared, PreparedFrame)
        catalogue = ClassCatalogue(
            data.series_id, "current_frame", (data.frame.working_index,), state,
            {"frames": [prepared.fit_record(np.flatnonzero(prepared.fit_mask))], "sampling": "all_useful_samples"},
            model_parameters(state["k"]),
        )
    return apply_prepared(prepared, catalogue, settings, check, progress, acceptance=acceptance)


def validate_catalogue(data: AnalysisInput, catalogue: ClassCatalogue) -> None:
    if data.series_id != catalogue.series_id:
        raise ValueError("Katalog klas pochodzi z innej serii. Dopasuj klasy ponownie.")
    if plain_metadata(catalogue.parameters) != model_parameters(catalogue.k):
        raise ValueError("Katalog klas używa innych parametrów metody. Dopasuj klasy ponownie.")
    if catalogue.scope == "current_frame":
        source = catalogue.provenance["frames"][0]
        bounded = (data.frame.image.size <= PARAMETERS["maximum_image_pixels"]
                   and len(data.annotations.detections) <= PARAMETERS["maximum_input_detections"])
        if (catalogue.frame_indices != (data.frame.working_index,) or source["source_index"] != data.frame.source_index
                or not bounded or source["input_sha256"] != input_fingerprint(data)):
            raise ValueError("Lokalny katalog należy do danych jednej klatki. Dopasuj klasy dla bieżącej klatki lub zakresu.")


def apply_prepared(
    prepared: PreparedFrame | FrameAnalysis, catalogue: ClassCatalogue, settings: DomainSettings,
    check: Callable[[], None], progress: Callable[[str], None], *,
    acceptance: ClassAcceptanceSettings = ClassAcceptanceSettings(),
) -> FrameAnalysis:
    count_parameters: dict[str, Any] = {"k": catalogue.k, "class_count_mode": "manual"}
    if "class_selection" in catalogue.state:
        count_parameters.update(class_count_mode="auto", auto_max_k=catalogue.state["class_selection"]["max_k"])
    classes = tuple(ResultClass(str(index + 1), color) for index, color in enumerate(COLORS[:catalogue.k]))
    if isinstance(prepared, FrameAnalysis):
        return replace(prepared, catalogue=catalogue, classes=classes,
                       parameters={**prepared.parameters, **acceptance.parameters(), **count_parameters},
                       metadata={**prepared.metadata, **catalogue.metadata()})
    data = prepared.data
    labels, reliable, class_details = apply_classes(prepared.features, prepared.valid, catalogue.state, check,
                                                    acceptance=acceptance)
    progress("Wyznaczanie barier obrazu i domen…")
    barrier, barrier_metadata = image_barriers(np.asarray(data.frame.image, float), prepared.spacing, check)
    order = prepared.order
    domain_ids, domain_labels, geometry_metadata = segment_domains(
        prepared.points, labels, reliable & order["supported"], prepared.features,
        prepared.spacing, barrier, check, settings=settings,
    )
    metadata = {**prepared.base.metadata, **catalogue.metadata(),
                "barriers": barrier_metadata, "domain_construction": geometry_metadata}
    assignments = dict(prepared.base.assignments)
    for index, detection in enumerate(prepared.active):
        check()
        domain = int(domain_ids[index])
        class_reason = ("" if reliable[index] else "invalid_descriptor" if not prepared.valid[index]
                        else "class_low_margin" if not class_details["class_margin_passed"][index]
                        else "class_outside_radius")
        reason = ("" if domain else "insufficient_local_support" if not order["sufficient"][index]
                  else "periodicity_not_confirmed" if not order["supported"][index]
                  else class_reason if not reliable[index] else "small_or_fragmented_component")
        flags = {"class_margin_passed", "class_radius_passed", "descriptor_valid"}
        details: dict[str, Any] = {key: bool(values[index]) if key in flags else float(values[index])
                                   for key, values in class_details.items()}
        details.update({"order_score": float(order["score"][index]), "order_threshold": float(order["threshold"][index]),
                        "local_point_count": int(order["local_n"][index]),
                        "effective_point_count": float(order["effective_n"][index]),
                        "order_supported": bool(order["supported"][index]),
                        "order_support_sufficient": bool(order["sufficient"][index]),
                        "class_reliable": bool(reliable[index]),
                        "class_rejection_reason": class_reason,
                        "centroid_margin_applicable": catalogue.k > 1,
                        "x_px": detection.center_xy[0], "y_px": detection.center_xy[1]})
        clazz = str(int(labels[index]) + 1)
        assignments[detection.detection_id] = MoleculeAssignment(
            detection.detection_id, domain, clazz if domain else "", clazz,
            "domain" if domain else "unassigned", reason, details,
        )
    check()
    return replace(prepared.base, status="complete", message=f"Obliczono klasy K{catalogue.k} i domeny.",
                   assignments=assignments, classes=classes, metadata=metadata,
                   domain_labels=domain_labels, catalogue=catalogue,
                   parameters={**prepared.base.parameters, **acceptance.parameters(), **count_parameters})
