"""Prepare one frame for discovery or application, without fitting a catalogue."""

from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Any, Literal

import numpy as np
from numpy.typing import NDArray

from stmdomains.analysis.config import PARAMETERS
from stmdomains.analysis.domain_settings import DomainSettings
from stmdomains.analysis.features import pair_features, prepare_points
from stmdomains.analysis.order import evaluate_order
from stmdomains.analysis.provenance import input_fingerprint
from stmdomains.core.analysis_result import AnalysisInput, FrameAnalysis, MoleculeAssignment
from stmdomains.core.annotations import Detection


@dataclass
class PreparedFrame:
    data: AnalysisInput
    active: list[Detection]
    points: NDArray[np.float64]
    spacing: float
    features: NDArray[np.float64]
    valid: NDArray[np.bool_]
    fit_mask: NDArray[np.bool_]
    order: dict[str, NDArray[Any]]
    base: FrameAnalysis

    def fit_record(self, rows: NDArray[Any]) -> dict[str, Any]:
        return {"working_index": self.data.frame.working_index, "source_index": self.data.frame.source_index,
                "input_sha256": self.base.metadata["input_sha256"], "spacing_px": self.spacing,
                "useful_samples": int(self.fit_mask.sum()), "used_samples": len(rows),
                "sample_detection_ids": [self.active[int(row)].detection_id for row in rows],
                "status": "used" if len(rows) else "no_useful_samples"}

    def unavailable(self, message: str) -> FrameAnalysis:
        return replace(self.base, message=message)


def prepare_frame(
    data: AnalysisInput, k: int, settings: DomainSettings,
    check: Callable[[], None], progress: Callable[[str], None],
) -> PreparedFrame | FrameAnalysis:
    image = np.asarray(data.frame.image, dtype=float)
    detections = data.annotations.detections
    parameters = {**PARAMETERS, **settings.parameters(), "k": k}
    metadata: dict[str, Any] = {
        "fit_scope": "current_frame", "working_index": data.frame.working_index,
        "source_index": data.frame.source_index, "annotation_state": data.annotations.detection_state,
        "coordinate_system": "raw image pixels: x=column, y=row",
        "interpretation": "Experimental local descriptor classes and domains; no temporal tracking or confirmed physical types.",
    }
    if image.size <= PARAMETERS["maximum_image_pixels"] and len(detections) <= PARAMETERS["maximum_input_detections"]:
        metadata["input_sha256"] = input_fingerprint(data)
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
    if spacing is None or not np.isfinite(spacing) or spacing <= 1e-9 or len(points) < max(2, k):
        return unavailable("insufficient_data", f"Za mało różnych molekuł do wyznaczenia skali i K{k}.", "insufficient_samples")
    parameters["spacing_px"] = spacing
    progress("Obliczanie opisów otoczeń…")
    features, valid, support = pair_features(points, spacing, check)
    progress("Ocena lokalnego porządku…")
    order, calibration = evaluate_order(points, spacing, check, progress)
    metadata["order_calibration"] = calibration
    fit_mask = valid & (support["neighbors"] >= 6) & (support["first_shell"] >= 2) & order["supported"]
    metadata["fit_count"] = int(fit_mask.sum())
    metadata["order_supported_count"] = int(order["supported"].sum())
    base = unavailable("insufficient_data", "", "insufficient_training_samples")
    return PreparedFrame(data, active, points, spacing, features, valid, fit_mask, order, base)
