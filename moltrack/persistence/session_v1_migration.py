from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from moltrack.analysis.domain_analysis import (
    DomainAnalysisRequest,
    DomainAnalysisSessionDiagnostic,
    DomainAnalysisSessionState,
    GeometryMode,
)
from moltrack.core import (
    MOLTRACK_SESSION_SCHEMA_VERSION,
    SUPPORTED_MOLTRACK_SESSION_SCHEMA_VERSIONS,
)

from .domain_analysis_session import domain_analysis_state_from_payload


@dataclass(frozen=True)
class MigratedV1Session:
    """Schema-v2 load inputs produced without changing the source file."""

    payload: Mapping[str, Any]
    domain_analysis_state: DomainAnalysisSessionState


def resolve_session_load_payload(
    payload: Mapping[str, Any],
) -> tuple[int, DomainAnalysisSessionState, Mapping[str, Any]]:
    """Validate the outer schema and return schema-v2 loader inputs."""

    schema_version = payload.get("schema_version")
    if isinstance(schema_version, bool) or not isinstance(schema_version, int):
        raise ValueError("MolTrack session schema_version must be an integer.")
    if schema_version not in SUPPORTED_MOLTRACK_SESSION_SCHEMA_VERSIONS:
        raise ValueError(
            f"Unsupported MolTrack session schema_version: {schema_version}."
        )
    _source_frame_indices(payload)
    if schema_version == 1:
        migrated = migrate_v1_session_payload(payload)
        return (
            MOLTRACK_SESSION_SCHEMA_VERSION,
            migrated.domain_analysis_state,
            migrated.payload,
        )
    return (
        schema_version,
        domain_analysis_state_from_payload(payload.get("domain_analysis")),
        payload,
    )


def migrate_v1_session_payload(
    payload: Mapping[str, Any],
) -> MigratedV1Session:
    """Translate the supported v1 workspace into its single v2 owner."""

    source_frame_indices = _source_frame_indices(payload)
    frame_count = len(source_frame_indices)
    position_analysis = payload.get("position_analysis")
    frame_range, geometry_mode, diagnostics = _migrate_position_analysis(
        position_analysis,
        frame_count=frame_count,
    )
    diagnostics.extend(_legacy_result_diagnostics(payload))
    state = DomainAnalysisSessionState(
        draft=DomainAnalysisRequest(
            frame_range=frame_range,
            geometry_mode=geometry_mode,
        ),
        diagnostics=tuple(diagnostics),
    )
    migrated = dict(payload)
    migrated.update({
        "schema_version": 2,
        "position_analysis": None,
        "molecular_m6_analysis": None,
        "m6_domain_type_analysis": None,
        "molecular_stacking_analysis": None,
        "molecular_order_type_analysis": None,
        "texture_domain_analysis": None,
    })
    return MigratedV1Session(
        payload=migrated,
        domain_analysis_state=state,
    )


def _migrate_position_analysis(
    payload: Any,
    *,
    frame_count: int,
) -> tuple[range, GeometryMode, list[DomainAnalysisSessionDiagnostic]]:
    if payload is None:
        return range(frame_count), "segmentation_preferred", []
    position = _mapping(payload, "position_analysis")
    first_range = _mapping(
        position.get("first_range"),
        "position_analysis.first_range",
    )
    start = _integer(
        first_range.get("start_frame"),
        "position_analysis.first_range.start_frame",
    )
    end = _integer(
        first_range.get("end_frame"),
        "position_analysis.first_range.end_frame",
    )
    if start < 0 or start > end or end >= frame_count:
        raise ValueError(
            "position_analysis.first_range must be within the Working Image "
            "Series."
        )
    geometry_mode = (
        "segmentation_preferred"
        if position.get("use_segmentation_centroids", True) is not False
        else "bbox_centers"
    )
    diagnostics: list[DomainAnalysisSessionDiagnostic] = []
    second_range = position.get("second_range")
    if second_range is not None:
        second = _mapping(second_range, "position_analysis.second_range")
        identifier = str(second.get("name", "historical-second-range")).strip()
        diagnostics.append(DomainAnalysisSessionDiagnostic(
            component="position_analysis.second_range",
            identifier=identifier or "historical-second-range",
            schema_version="1",
            reason=(
                "Historical second range and comparison result were omitted "
                "during the single-range v1 to v2 migration."
            ),
        ))
    return range(start, end + 1), geometry_mode, diagnostics


def _legacy_result_diagnostics(
    payload: Mapping[str, Any],
) -> list[DomainAnalysisSessionDiagnostic]:
    diagnostics: list[DomainAnalysisSessionDiagnostic] = []
    for component, description in (
        ("molecular_m6_analysis", "legacy M6 result"),
        ("m6_domain_type_analysis", "legacy domain-type result"),
        ("texture_domain_analysis", "legacy ungated Texture Domains result"),
    ):
        if payload.get(component) is None:
            continue
        diagnostics.append(DomainAnalysisSessionDiagnostic(
            component=component,
            identifier=component,
            schema_version="1",
            reason=(
                f"The {description} is not a compatible v2 cache entry and "
                "was not activated."
            ),
        ))
    return diagnostics


def _mapping(value: Any, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be a JSON object.")
    return value


def _integer(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name} must be an integer.")
    return value


def _source_frame_indices(payload: Mapping[str, Any]) -> list[Any]:
    working_series = _mapping(payload.get("working_series"), "working_series")
    source_frame_indices = working_series.get("source_frame_indices")
    if not isinstance(source_frame_indices, list) or not source_frame_indices:
        raise ValueError(
            "working_series.source_frame_indices must be a non-empty list."
        )
    return source_frame_indices
