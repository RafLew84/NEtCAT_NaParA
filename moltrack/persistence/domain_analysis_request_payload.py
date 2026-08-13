from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from moltrack.analysis.domain_analysis import (
    DomainAnalysisRequest,
    M6RunConfiguration,
)
from moltrack.analysis.domain_analysis.geometry import GeometryMode

from .domain_analysis_payload_validation import (
    integer_field,
    text_field,
    text_list_field,
)


def domain_analysis_request_to_payload(
    request: DomainAnalysisRequest,
) -> dict[str, object]:
    if not isinstance(request, DomainAnalysisRequest):
        raise TypeError("request must be a DomainAnalysisRequest.")
    configuration = request.m6_configuration
    return {
        "frame_start": request.frame_range.start,
        "frame_stop": request.frame_range.stop,
        "backend_id": request.backend_id,
        "geometry_mode": request.geometry_mode,
        "classifier_ids": list(request.classifier_ids),
        "m6_configuration": (
            None if configuration is None else configuration.to_payload()
        ),
    }


def domain_analysis_request_from_payload(
    payload: Mapping[str, Any],
    *,
    path: str,
) -> DomainAnalysisRequest:
    configuration_payload = payload.get("m6_configuration")
    configuration = (
        None
        if configuration_payload is None
        else M6RunConfiguration.from_payload(configuration_payload)
    )
    return DomainAnalysisRequest(
        frame_range=range(
            integer_field(payload, "frame_start", path),
            integer_field(payload, "frame_stop", path),
        ),
        backend_id=text_field(payload, "backend_id", path),
        geometry_mode=cast(
            GeometryMode,
            text_field(payload, "geometry_mode", path),
        ),
        classifier_ids=tuple(text_list_field(payload, "classifier_ids", path)),
        m6_configuration=configuration,
    )


__all__ = [
    "domain_analysis_request_from_payload",
    "domain_analysis_request_to_payload",
]
