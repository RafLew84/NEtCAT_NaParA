"""Analyze raw inputs using either a new local catalogue or an explicit saved one."""

from collections.abc import Callable
from dataclasses import replace
from typing import Any

import numpy as np

from stmdomains.analysis.barriers import image_barriers
from stmdomains.analysis.acceptance_settings import ClassAcceptanceSettings
from stmdomains.analysis.clustering import apply_classes, fit_model, validate_k
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
    validate_k(k)
    prepared = prepare_frame(data, k, settings, check, progress, order_settings=order_settings)
    if catalogue is None:
        if isinstance(prepared, FrameAnalysis):
            return prepared
        progress(f"Dopasowanie lokalnych klas K{k}…")
        state = fit_model(prepared.features[prepared.fit_mask], k, check)
        if state is None:
            return prepared.unavailable(f"Za mało użytecznych lub różnych otoczeń do dopasowania K{k}.")
        catalogue = ClassCatalogue(
            data.series_id, "current_frame", (data.frame.working_index,), state,
            {"frames": [prepared.fit_record(np.flatnonzero(prepared.fit_mask))], "sampling": "all_useful_samples"},
            model_parameters(k),
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
    classes = tuple(ResultClass(str(index + 1), color) for index, color in enumerate(COLORS[:catalogue.k]))
    if isinstance(prepared, FrameAnalysis):
        return replace(prepared, catalogue=catalogue, classes=classes,
                       parameters={**prepared.parameters, **acceptance.parameters()},
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
                   parameters={**prepared.base.parameters, **acceptance.parameters()})
