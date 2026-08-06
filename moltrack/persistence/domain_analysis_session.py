from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from moltrack.analysis.domain_analysis import (
    DOMAIN_ANALYSIS_SESSION_SCHEMA_VERSION,
    DomainAnalysisPublication,
    DomainAnalysisRequest,
    DomainAnalysisResult,
    DomainAnalysisSessionState,
    M6FrameGate,
    M6Gate,
    M6PresentationProvenance,
    M6PublishedComponent,
)
from moltrack.analysis.domain_analysis.events import (
    ClassifierStatus,
    DomainAnalysisRunStatus,
)
from moltrack.analysis.domain_analysis.geometry import (
    CoordinateView,
    GeometryMode,
)
from moltrack.analysis.domain_analysis.models import M6ComponentType


_PUBLISHED_RESULT_SCHEMA_VERSION = 1
_M6_GATE_SCHEMA_VERSION = 1
_CACHE_SCHEMA_VERSION = 1


def domain_analysis_state_from_ui_state(
    ui_state: Any | None,
) -> DomainAnalysisSessionState | None:
    if isinstance(ui_state, Mapping):
        candidate = ui_state.get("domain_analysis")
    else:
        candidate = getattr(ui_state, "domain_analysis", None)
    if candidate is None:
        return None
    if not isinstance(candidate, DomainAnalysisSessionState):
        raise TypeError(
            "domain_analysis must be a DomainAnalysisSessionState."
        )
    return candidate


def domain_analysis_state_to_payload(
    state: DomainAnalysisSessionState | None,
) -> dict[str, Any]:
    saved = DomainAnalysisSessionState() if state is None else state
    return {
        "schema_version": saved.schema_version,
        "classifier_status": saved.classifier_status,
        "published_result": (
            None
            if saved.published_result is None
            else _publication_to_payload(saved.published_result)
        ),
        "cache": {
            "schema_version": _CACHE_SCHEMA_VERSION,
            "m6_frames": [],
            "classifier_frames": [],
        },
    }


def domain_analysis_state_from_payload(
    payload: Any,
) -> DomainAnalysisSessionState:
    section = _require_mapping(payload, "domain_analysis")
    _require_version(
        section,
        DOMAIN_ANALYSIS_SESSION_SCHEMA_VERSION,
        "domain_analysis",
    )
    _validate_empty_cache(section.get("cache"))
    classifier_status = _require_text(
        section,
        "classifier_status",
        "domain_analysis",
    )
    publication_payload = _required(section, "published_result", "domain_analysis")
    if publication_payload is None:
        if classifier_status != "not_run":
            raise ValueError(
                "domain_analysis.classifier_status must be 'not_run' when "
                "there is no published result."
            )
        return DomainAnalysisSessionState()
    if classifier_status != "not_requested":
        raise ValueError(
            "An M6-only published result requires classifier_status "
            "'not_requested'."
        )
    return DomainAnalysisSessionState(
        published_result=_publication_from_payload(publication_payload)
    )


def _publication_to_payload(
    publication: DomainAnalysisPublication,
) -> dict[str, Any]:
    request = publication.request
    gate = publication.result.m6_gate
    if gate is None:
        raise ValueError("A published Domain Analysis result requires an M6 gate.")
    return {
        "schema_version": _PUBLISHED_RESULT_SCHEMA_VERSION,
        "request": {
            "frame_start": request.frame_range.start,
            "frame_stop": request.frame_range.stop,
            "geometry_mode": request.geometry_mode,
            "classifier_ids": list(request.classifier_ids),
        },
        "request_fingerprint": publication.request_fingerprint,
        "run_status": publication.result.run_status,
        "classifier_status": publication.result.classifier_status,
        "m6_gate": _gate_to_payload(gate),
    }


def _publication_from_payload(payload: Any) -> DomainAnalysisPublication:
    saved = _require_mapping(payload, "domain_analysis.published_result")
    _require_version(
        saved,
        _PUBLISHED_RESULT_SCHEMA_VERSION,
        "domain_analysis.published_result",
    )
    request_payload = _require_mapping(
        _required(saved, "request", "domain_analysis.published_result"),
        "domain_analysis.published_result.request",
    )
    classifier_ids = tuple(_require_text_list(
        request_payload,
        "classifier_ids",
        "domain_analysis.published_result.request",
    ))
    request = DomainAnalysisRequest(
        frame_range=range(
            _require_integer(
                request_payload,
                "frame_start",
                "domain_analysis.published_result.request",
            ),
            _require_integer(
                request_payload,
                "frame_stop",
                "domain_analysis.published_result.request",
            ),
        ),
        geometry_mode=cast(GeometryMode, _require_text(
            request_payload,
            "geometry_mode",
            "domain_analysis.published_result.request",
        )),
        classifier_ids=classifier_ids,
    )
    result = DomainAnalysisResult(
        run_status=cast(DomainAnalysisRunStatus, _require_text(
            saved,
            "run_status",
            "domain_analysis.published_result",
        )),
        m6_gate=_gate_from_payload(
            _required(saved, "m6_gate", "domain_analysis.published_result")
        ),
        classifier_status=cast(ClassifierStatus, _require_text(
            saved,
            "classifier_status",
            "domain_analysis.published_result",
        )),
        classifier_outcomes=None,
    )
    publication = DomainAnalysisPublication(request=request, result=result)
    expected_fingerprint = _require_text(
        saved,
        "request_fingerprint",
        "domain_analysis.published_result",
    )
    if publication.request_fingerprint != expected_fingerprint:
        raise ValueError(
            "domain_analysis.published_result request_fingerprint does not "
            "match its request."
        )
    return publication


def _gate_to_payload(gate: M6Gate) -> dict[str, Any]:
    return {
        "schema_version": _M6_GATE_SCHEMA_VERSION,
        "frames": [_frame_to_payload(frame) for frame in gate.frames],
    }


def _gate_from_payload(payload: Any) -> M6Gate:
    saved = _require_mapping(payload, "domain_analysis.published_result.m6_gate")
    _require_version(
        saved,
        _M6_GATE_SCHEMA_VERSION,
        "domain_analysis.published_result.m6_gate",
    )
    frames = _require_list(
        saved,
        "frames",
        "domain_analysis.published_result.m6_gate",
    )
    return M6Gate(frames=tuple(
        _frame_from_payload(value, index=index)
        for index, value in enumerate(frames)
    ))


def _frame_to_payload(frame: M6FrameGate) -> dict[str, Any]:
    provenance = frame.presentation_provenance
    return {
        "frame_index": frame.frame_index,
        "physical_frame_id": frame.physical_frame_id,
        "coordinate_frame": frame.coordinate_frame,
        "coordinate_transform_fingerprint": (
            frame.coordinate_transform_fingerprint
        ),
        "presentation_provenance": {
            "raw_shape": list(provenance.raw_shape),
            "expanded_shape": list(provenance.expanded_shape),
            "source_view": provenance.source_view,
            "frame_origin_xy": list(provenance.frame_origin_xy),
            "canvas_offset_xy": list(provenance.canvas_offset_xy),
            "registration_fingerprint": provenance.registration_fingerprint,
        },
        "source_geometry_fingerprint": frame.source_geometry_fingerprint,
        "m6_settings_fingerprint": frame.m6_settings_fingerprint,
        "m6_algorithm_version": frame.m6_algorithm_version,
        "pixel_area_nm2": frame.pixel_area_nm2,
        "full_domains": [
            _component_to_payload(value) for value in frame.full_domains
        ],
        "small_ordered_islands": [
            _component_to_payload(value)
            for value in frame.small_ordered_islands
        ],
        "outside_source_ids": list(frame.outside_source_ids),
        "outside_points_xy_nm": _pairs_to_lists(frame.outside_points_xy_nm),
        "outside_pixels_xy": _pairs_to_lists(frame.outside_pixels_xy),
        "outside_area_nm2": frame.outside_area_nm2,
        "analyzed_source_ids": list(frame.analyzed_source_ids),
        "analyzed_pixels_xy": _pairs_to_lists(frame.analyzed_pixels_xy),
        "analyzed_area_nm2": frame.analyzed_area_nm2,
        "m6_gate_fingerprint": frame.m6_gate_fingerprint,
    }


def _frame_from_payload(payload: Any, *, index: int) -> M6FrameGate:
    path = f"domain_analysis.published_result.m6_gate.frames[{index}]"
    saved = _require_mapping(payload, path)
    provenance_payload = _require_mapping(
        _required(saved, "presentation_provenance", path),
        f"{path}.presentation_provenance",
    )
    frame = M6FrameGate(
        frame_index=_require_integer(saved, "frame_index", path),
        physical_frame_id=_require_text(saved, "physical_frame_id", path),
        coordinate_frame=_require_text(saved, "coordinate_frame", path),
        coordinate_transform_fingerprint=_require_text(
            saved, "coordinate_transform_fingerprint", path
        ),
        presentation_provenance=_provenance_from_payload(
            provenance_payload,
            path=f"{path}.presentation_provenance",
        ),
        source_geometry_fingerprint=_require_text(
            saved, "source_geometry_fingerprint", path
        ),
        m6_settings_fingerprint=_require_text(
            saved, "m6_settings_fingerprint", path
        ),
        m6_algorithm_version=_require_text(
            saved, "m6_algorithm_version", path
        ),
        pixel_area_nm2=_require_number(saved, "pixel_area_nm2", path),
        full_domains=_components_from_payload(saved, "full_domains", path),
        small_ordered_islands=_components_from_payload(
            saved, "small_ordered_islands", path
        ),
        outside_source_ids=tuple(_require_text_list(
            saved, "outside_source_ids", path
        )),
        outside_points_xy_nm=_float_pairs(saved, "outside_points_xy_nm", path),
        outside_pixels_xy=_integer_pairs(saved, "outside_pixels_xy", path),
        outside_area_nm2=_require_number(saved, "outside_area_nm2", path),
        analyzed_source_ids=tuple(_require_text_list(
            saved, "analyzed_source_ids", path
        )),
        analyzed_pixels_xy=_integer_pairs(saved, "analyzed_pixels_xy", path),
        analyzed_area_nm2=_require_number(saved, "analyzed_area_nm2", path),
    )
    expected_fingerprint = _require_text(
        saved, "m6_gate_fingerprint", path
    )
    if frame.m6_gate_fingerprint != expected_fingerprint:
        raise ValueError(f"{path}.m6_gate_fingerprint does not match its frame.")
    return frame


def _provenance_from_payload(
    saved: Mapping[str, Any],
    *,
    path: str,
) -> M6PresentationProvenance:
    return M6PresentationProvenance(
        raw_shape=_integer_pair(saved, "raw_shape", path),
        expanded_shape=_integer_pair(saved, "expanded_shape", path),
        source_view=cast(
            CoordinateView,
            _require_text(saved, "source_view", path),
        ),
        frame_origin_xy=_float_pair(saved, "frame_origin_xy", path),
        canvas_offset_xy=_float_pair(saved, "canvas_offset_xy", path),
        registration_fingerprint=_require_text(
            saved, "registration_fingerprint", path
        ),
    )


def _component_to_payload(component: M6PublishedComponent) -> dict[str, Any]:
    return {
        "lattice_domain_id": component.lattice_domain_id,
        "component_type": component.component_type,
        "source_ids": list(component.source_ids),
        "core_source_ids": list(component.core_source_ids),
        "halo_source_ids": list(component.halo_source_ids),
        "points_xy_nm": _pairs_to_lists(component.points_xy_nm),
        "footprint_pixels_xy": _pairs_to_lists(
            component.footprint_pixels_xy
        ),
        "footprint_area_nm2": component.footprint_area_nm2,
        "centroid_xy_nm": list(component.centroid_xy_nm),
        "bounds_xyxy_nm": list(component.bounds_xyxy_nm),
    }


def _components_from_payload(
    saved: Mapping[str, Any],
    field_name: str,
    path: str,
) -> tuple[M6PublishedComponent, ...]:
    values = _require_list(saved, field_name, path)
    return tuple(
        _component_from_payload(
            value,
            path=f"{path}.{field_name}[{index}]",
        )
        for index, value in enumerate(values)
    )


def _component_from_payload(
    payload: Any,
    *,
    path: str,
) -> M6PublishedComponent:
    saved = _require_mapping(payload, path)
    return M6PublishedComponent(
        lattice_domain_id=_require_text(saved, "lattice_domain_id", path),
        component_type=cast(
            M6ComponentType,
            _require_text(saved, "component_type", path),
        ),
        source_ids=tuple(_require_text_list(saved, "source_ids", path)),
        core_source_ids=tuple(_require_text_list(
            saved, "core_source_ids", path
        )),
        halo_source_ids=tuple(_require_text_list(
            saved, "halo_source_ids", path
        )),
        points_xy_nm=_float_pairs(saved, "points_xy_nm", path),
        footprint_pixels_xy=_integer_pairs(
            saved, "footprint_pixels_xy", path
        ),
        footprint_area_nm2=_require_number(
            saved, "footprint_area_nm2", path
        ),
        centroid_xy_nm=_float_pair(saved, "centroid_xy_nm", path),
        bounds_xyxy_nm=_float_quad(saved, "bounds_xyxy_nm", path),
    )


def _validate_empty_cache(payload: Any) -> None:
    cache = _require_mapping(payload, "domain_analysis.cache")
    _require_version(cache, _CACHE_SCHEMA_VERSION, "domain_analysis.cache")
    for field_name in ("m6_frames", "classifier_frames"):
        if _require_list(cache, field_name, "domain_analysis.cache"):
            raise ValueError(
                f"domain_analysis.cache.{field_name} is not supported by the "
                "minimal M6-only schema."
            )


def _require_version(
    payload: Mapping[str, Any],
    expected: int,
    path: str,
) -> None:
    version = _require_integer(payload, "schema_version", path)
    if version != expected:
        raise ValueError(f"Unsupported {path} schema_version: {version}.")


def _required(payload: Mapping[str, Any], field_name: str, path: str) -> Any:
    if field_name not in payload:
        raise ValueError(f"{path}.{field_name} is required.")
    return payload[field_name]


def _require_mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{path} must be an object.")
    return value


def _require_list(
    payload: Mapping[str, Any],
    field_name: str,
    path: str,
) -> list[Any]:
    value = _required(payload, field_name, path)
    if not isinstance(value, list):
        raise ValueError(f"{path}.{field_name} must be a list.")
    return value


def _require_text(
    payload: Mapping[str, Any],
    field_name: str,
    path: str,
) -> str:
    value = _required(payload, field_name, path)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{path}.{field_name} must be a non-empty string.")
    return value


def _require_text_list(
    payload: Mapping[str, Any],
    field_name: str,
    path: str,
) -> list[str]:
    values = _require_list(payload, field_name, path)
    if any(not isinstance(value, str) or not value.strip() for value in values):
        raise ValueError(
            f"{path}.{field_name} must contain non-empty strings."
        )
    return cast(list[str], values)


def _require_integer(
    payload: Mapping[str, Any],
    field_name: str,
    path: str,
) -> int:
    value = _required(payload, field_name, path)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{path}.{field_name} must be an integer.")
    return value


def _require_number(
    payload: Mapping[str, Any],
    field_name: str,
    path: str,
) -> float:
    value = _required(payload, field_name, path)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{path}.{field_name} must be numeric.")
    return float(value)


def _integer_pair(
    payload: Mapping[str, Any],
    field_name: str,
    path: str,
) -> tuple[int, int]:
    values = _require_list(payload, field_name, path)
    if len(values) != 2 or any(
        isinstance(value, bool) or not isinstance(value, int)
        for value in values
    ):
        raise ValueError(f"{path}.{field_name} must be an integer pair.")
    return cast(tuple[int, int], tuple(values))


def _float_pair(
    payload: Mapping[str, Any],
    field_name: str,
    path: str,
) -> tuple[float, float]:
    return cast(
        tuple[float, float],
        _float_values(payload, field_name, path, length=2),
    )


def _float_quad(
    payload: Mapping[str, Any],
    field_name: str,
    path: str,
) -> tuple[float, float, float, float]:
    return cast(
        tuple[float, float, float, float],
        _float_values(payload, field_name, path, length=4),
    )


def _float_values(
    payload: Mapping[str, Any],
    field_name: str,
    path: str,
    *,
    length: int,
) -> tuple[float, ...]:
    values = _require_list(payload, field_name, path)
    if len(values) != length or any(
        isinstance(value, bool) or not isinstance(value, (int, float))
        for value in values
    ):
        raise ValueError(
            f"{path}.{field_name} must contain {length} numeric values."
        )
    return tuple(float(value) for value in values)


def _integer_pairs(
    payload: Mapping[str, Any],
    field_name: str,
    path: str,
) -> tuple[tuple[int, int], ...]:
    values = _require_list(payload, field_name, path)
    pairs: list[tuple[int, int]] = []
    for index, value in enumerate(values):
        if not isinstance(value, list) or len(value) != 2 or any(
            isinstance(item, bool) or not isinstance(item, int)
            for item in value
        ):
            raise ValueError(
                f"{path}.{field_name}[{index}] must be an integer pair."
            )
        pairs.append((value[0], value[1]))
    return tuple(pairs)


def _float_pairs(
    payload: Mapping[str, Any],
    field_name: str,
    path: str,
) -> tuple[tuple[float, float], ...]:
    values = _require_list(payload, field_name, path)
    pairs: list[tuple[float, float]] = []
    for index, value in enumerate(values):
        if not isinstance(value, list) or len(value) != 2 or any(
            isinstance(item, bool) or not isinstance(item, (int, float))
            for item in value
        ):
            raise ValueError(
                f"{path}.{field_name}[{index}] must be a numeric pair."
            )
        pairs.append((float(value[0]), float(value[1])))
    return tuple(pairs)


def _pairs_to_lists(values: tuple[tuple[Any, Any], ...]) -> list[list[Any]]:
    return [[first, second] for first, second in values]
