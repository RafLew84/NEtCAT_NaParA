"""Single-frame entry point; no model files, package paths or other frames."""

from collections.abc import Callable
import hashlib
import json
from typing import Any, Literal

import numpy as np

from stmdomains.analysis.barriers import image_barriers
from stmdomains.analysis.clustering import fit_classes
from stmdomains.analysis.features import pair_features, prepare_points
from stmdomains.analysis.order import evaluate_order
from stmdomains.analysis.segmentation import segment_domains
from stmdomains.core.analysis_result import (
    AnalysisCancelled, AnalysisInput, FrameAnalysis, MoleculeAssignment, ResultClass,
)


PARAMETERS: dict[str, Any] = {
    "method_version": "stm-domains-local-1", "k": 5, "seed": 24,
    "descriptor_radial_bins": 14, "descriptor_angle_bins": 36, "descriptor_sigma_factor": 1.25,
    "descriptor_pair_distance_range": [.55, 2.8], "pca_max_components": 24,
    "minimum_domain_size": 8, "edge_distance_factor": 1.5,
    "edge_max_hellinger": .20, "region_max_hellinger_diameter": .50,
    "class_margin": .075, "class_radius_quantile": .95, "class_radius_multiplier": 1.10,
    "order_radius_factor": 3., "order_sigma_factor": 4 / 3,
    "order_frequency_range_in_inverse_spacings": [.5, 2.], "order_frequency_count": 22,
    "order_angle_count": 48, "order_minimum_local_count": 10, "order_minimum_effective_count": 8.,
    "raster_radius_factor": .85, "maximum_input_detections": 3000,
    "maximum_image_pixels": 4_194_304,
}
COLORS = ("#10b9bd", "#f5b343", "#e366b6", "#9075db", "#66c26d")


def analyze_frame(
    data: AnalysisInput, *, cancelled: Callable[[], bool] = lambda: False,
    progress: Callable[[str], None] = lambda text: None,
) -> FrameAnalysis:
    def check() -> None:
        if cancelled():
            raise AnalysisCancelled()

    check()
    image = np.asarray(data.frame.image, dtype=float)
    detections = data.annotations.detections
    parameters = dict(PARAMETERS)
    metadata: dict[str, Any] = {
        "fit_scope": "current_frame", "working_index": data.frame.working_index,
        "source_index": data.frame.source_index, "annotation_state": data.annotations.detection_state,
        "coordinate_system": "raw image pixels: x=column, y=row",
        "interpretation": "Experimental local descriptor classes and domains; no temporal tracking or confirmed physical types.",
    }
    if image.size <= PARAMETERS["maximum_image_pixels"] and len(detections) <= PARAMETERS["maximum_input_detections"]:
        digest = hashlib.sha256()
        digest.update(str(image.shape).encode())
        digest.update(np.ascontiguousarray(image, dtype="<f8").tobytes())
        digest.update(data.annotations.detection_state.encode())
        for item in sorted(detections, key=lambda item: item.detection_id):
            digest.update(json.dumps((item.detection_id, item.center_xy, item.outside_field,
                                      item.metadata.get("origin"), item.metadata.get("confidence")),
                                     ensure_ascii=False, default=str).encode())
        metadata["input_sha256"] = digest.hexdigest()
    else:
        metadata["fingerprint_status"] = "not_computed_input_exceeds_resource_limit"
    excluded: dict[str, tuple[str, dict[str, Any]]] = {}

    def unavailable(status: Literal["no_annotations", "insufficient_data"], message: str, reason: str) -> FrameAnalysis:
        assignments = {}
        for detection in detections:
            record_status, details = excluded.get(detection.detection_id, ("unassigned", {}))
            record_reason = record_status if record_status != "unassigned" else reason
            assignments[detection.detection_id] = MoleculeAssignment(
                detection.detection_id, status=record_status, rejection_reason=record_reason, metadata=details,
            )
        return FrameAnalysis(data.series_id, data.frame.working_index, data.frame.source_index,
                             status, message, assignments, parameters=parameters, metadata=metadata)

    if data.annotations.detection_state in ("missing", "invalid", "partial"):
        return unavailable("insufficient_data", "Oznaczenia są niedostępne lub niepełne; analiza nie została wykonana.", "invalid_annotations")
    if not detections:
        return unavailable("no_annotations", "Brak oznaczeń do analizy.", "no_annotations")
    if len(detections) > PARAMETERS["maximum_input_detections"]:
        return unavailable("insufficient_data", "Przekroczono limit 3000 oznaczeń dla analizy jednej klatki.", "resource_limit")
    if image.ndim != 2 or image.size > PARAMETERS["maximum_image_pixels"] or not image.size or not np.isfinite(image).all():
        return unavailable("insufficient_data", "Analiza wymaga skończonego obrazu 2D, do 4 milionów pikseli.", "invalid_image")
    identifiers = [item.detection_id for item in detections]
    if len(set(identifiers)) != len(identifiers) or any(not identifier for identifier in identifiers):
        raise ValueError("Analiza wymaga jednoznacznych ID oznaczeń molekuł.")
    if any(item.frame_index != data.frame.working_index for item in detections):
        raise ValueError("Oznaczenia analizy pochodzą z innej klatki.")
    progress("Wyznaczanie skali i usuwanie duplikatów…")
    active, points, spacing, excluded = prepare_points(detections, (image.shape[0], image.shape[1]), check)
    metadata["scale_method"] = "median nearest-neighbour distance after priority-based duplicate suppression; coarse third-neighbour scale"
    metadata["active_count"] = len(active)
    if spacing is None or not np.isfinite(spacing) or spacing <= 1e-9 or len(points) < 5:
        return unavailable("insufficient_data", "Za mało różnych molekuł do wyznaczenia skali i K5.", "insufficient_samples")
    parameters["spacing_px"] = spacing
    progress("Obliczanie opisów otoczeń…")
    features, valid, support = pair_features(points, spacing, check)
    progress("Ocena lokalnego porządku…")
    order, calibration = evaluate_order(points, spacing, check, progress)
    metadata["order_calibration"] = calibration
    fit_mask = valid & (support["neighbors"] >= 6) & (support["first_shell"] >= 2) & order["supported"]
    metadata["fit_count"] = int(fit_mask.sum())
    metadata["order_supported_count"] = int(order["supported"].sum())
    progress("Dopasowanie pięciu lokalnych klas…")
    fitted = fit_classes(features, valid, fit_mask, check)
    if fitted is None:
        return unavailable("insufficient_data", "Za mało użytecznych lub różnych otoczeń do dopasowania K5.", "insufficient_training_samples")
    labels, reliable, class_details, model_state = fitted
    metadata["model_state"] = model_state
    model_bytes = json.dumps(model_state, sort_keys=True, allow_nan=False).encode()
    metadata["model_id"] = hashlib.sha256(model_bytes).hexdigest()
    progress("Wyznaczanie barier obrazu i domen…")
    barrier, barrier_metadata = image_barriers(image, spacing, check)
    domain_ids, domain_labels, geometry_metadata = segment_domains(
        points, labels, reliable & order["supported"], features, spacing, barrier, check,
    )
    metadata["barriers"] = barrier_metadata
    metadata["domain_construction"] = geometry_metadata
    classes = tuple(ResultClass(str(index + 1), color) for index, color in enumerate(COLORS))
    assignments = {}
    for identifier, (status, details) in excluded.items():
        assignments[identifier] = MoleculeAssignment(identifier, status=status, rejection_reason=status, metadata=details)
    for index, detection in enumerate(active):
        check()
        domain = int(domain_ids[index])
        reason = ("" if domain else "insufficient_local_support" if not order["sufficient"][index]
                  else "periodicity_not_confirmed" if not order["supported"][index]
                  else "class_ambiguous" if not reliable[index] else "small_or_fragmented_component")
        details = {key: float(values[index]) for key, values in class_details.items()}
        details.update({"order_score": float(order["score"][index]),
                        "order_threshold": float(order["threshold"][index]),
                        "local_point_count": int(order["local_n"][index]),
                        "effective_point_count": float(order["effective_n"][index]),
                        "order_supported": bool(order["supported"][index]),
                        "order_support_sufficient": bool(order["sufficient"][index]),
                        "class_reliable": bool(reliable[index]),
                        "x_px": detection.center_xy[0], "y_px": detection.center_xy[1]})
        clazz = str(int(labels[index]) + 1)
        assignments[detection.detection_id] = MoleculeAssignment(
            detection.detection_id, domain, clazz if domain else "", clazz,
            "domain" if domain else "unassigned", reason, details,
        )
    check()
    return FrameAnalysis(data.series_id, data.frame.working_index, data.frame.source_index,
                         "complete", "Obliczono lokalne klasy K5 i domeny.", assignments, classes, parameters,
                         metadata, domain_labels)
