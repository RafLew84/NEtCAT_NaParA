"""Rebuild domains from verified inputs while retaining the fitted class catalogue.

Descriptors and image barriers are cheap to reproduce. Only class assignments and
order decisions are reused; large intermediate arrays are not cached per frame.
"""

from collections.abc import Callable
from dataclasses import replace
import json

import numpy as np

from stmdomains.analysis.barriers import image_barriers
from stmdomains.analysis.domain_settings import DomainSettings
from stmdomains.analysis.features import pair_features, prepare_points
from stmdomains.analysis.pipeline import PARAMETERS, analyze_frame
from stmdomains.analysis.config import model_parameters
from stmdomains.analysis.provenance import input_fingerprint
from stmdomains.analysis.segmentation import segment_domains
from stmdomains.core.analysis_result import AnalysisCancelled, AnalysisInput, FrameAnalysis


def recalculate_domains(
    data: AnalysisInput, previous: FrameAnalysis, settings: DomainSettings, *,
    cancelled: Callable[[], bool] = lambda: False,
    progress: Callable[[str], None] = lambda text: None,
) -> FrameAnalysis:
    def check() -> None:
        if cancelled():
            raise AnalysisCancelled()

    check()
    image = np.asarray(data.frame.image, dtype=float)
    identity_matches = (data.series_id == previous.series_id
                        and data.frame.working_index == previous.working_index
                        and data.frame.source_index == previous.source_index
                        and all(item.frame_index == data.frame.working_index for item in data.annotations.detections))
    if not identity_matches:
        raise ValueError("Wynik pochodzi z innej klatki. Wykonaj ponownie «Analizuj klatkę».")
    if previous.status != "complete":
        # There is no fitted catalogue to reuse or fingerprint to require after
        # a resource-limit refusal. Repeat validation and report its real cause.
        return analyze_frame(data, settings=settings, k=int(previous.parameters.get("k", 5)),
                             catalogue=previous.catalogue, cancelled=cancelled, progress=progress)
    upstream_matches = all(json.dumps(previous.parameters.get(key), sort_keys=True) == json.dumps(value, sort_keys=True)
                           for key, value in model_parameters(int(previous.parameters.get("k", 5))).items())
    bounded = (image.size <= PARAMETERS["maximum_image_pixels"]
               and len(data.annotations.detections) <= PARAMETERS["maximum_input_detections"])
    if (not upstream_matches or not bounded
            or input_fingerprint(data) != previous.metadata.get("input_sha256")):
        raise ValueError("Dane lub metoda różnią się od poprzedniego wyniku. Wykonaj ponownie «Analizuj klatkę».")
    progress("Przeliczanie domen przy zachowanych klasach…")
    active, points, spacing, _ = prepare_points(data.annotations.detections, (image.shape[0], image.shape[1]), check)
    if spacing is None or spacing != previous.parameters.get("spacing_px"):
        raise ValueError("Skala danych uległa zmianie. Wykonaj ponownie «Analizuj klatkę».")
    members = [previous.assignments[item.detection_id] for item in active]
    labels = np.array([int(member.provisional_class_id) - 1 for member in members])
    accepted = np.array([bool(member.metadata["class_reliable"] and member.metadata["order_supported"])
                         for member in members])
    features, _, _ = pair_features(points, spacing, check)
    barrier, barrier_metadata = image_barriers(image, spacing, check)
    ids, regions, geometry_metadata = segment_domains(
        points, labels, accepted, features, spacing, barrier, check, settings=settings,
    )
    assignments = dict(previous.assignments)
    for member, identifier in zip(members, ids):
        check()
        domain = int(identifier)
        assignments[member.detection_id] = replace(
            member, domain_local_id=domain, class_id=member.provisional_class_id if domain else "",
            status="domain" if domain else "unassigned",
            rejection_reason="" if domain else member.rejection_reason or "small_or_fragmented_component",
        )
    check()
    return replace(previous, assignments=assignments, domain_labels=regions,
                   parameters={**previous.parameters, **settings.parameters()},
                   metadata={**previous.metadata, "barriers": barrier_metadata, "domain_construction": geometry_metadata})
