from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from moltrack.analysis.domain_analysis import (
    DomainAnalysisRequest,
    DomainAnalysisM6CacheRecord,
    DomainAnalysisSessionDiagnostic,
    DomainAnalysisSessionState,
    GeometryMode,
)
from moltrack.core import (
    MOLTRACK_SESSION_SCHEMA_VERSION,
    SUPPORTED_MOLTRACK_SESSION_SCHEMA_VERSIONS,
)

from .domain_analysis_session import domain_analysis_state_from_payload
from .domain_analysis_cache_payload import (
    CACHE_SCHEMA_VERSION,
    domain_analysis_cache_from_payload,
)


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
    physical_frame_ids = tuple(
        f"source-frame-{source_frame_indices[index]}" for index in frame_range
    )
    m6_records, m6_diagnostics = _migrate_m6_cache(
        payload.get("molecular_m6_analysis"),
        frame_range=frame_range,
        geometry_mode=geometry_mode,
        physical_frame_ids=physical_frame_ids,
    )
    diagnostics.extend(m6_diagnostics)
    diagnostics.extend(_legacy_result_diagnostics(payload))
    state = DomainAnalysisSessionState(
        draft=DomainAnalysisRequest(
            frame_range=frame_range,
            geometry_mode=geometry_mode,
        ),
        draft_physical_frame_ids=physical_frame_ids,
        m6_cache_records=m6_records,
        diagnostics=tuple(diagnostics),
    )
    migrated = dict(payload)
    migrated.update({
        "schema_version": 2,
        "position_analysis": None,
        "molecular_m6_analysis": None,
        "m6_domain_type_analysis": None,
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
    use_segmentation_centroids = position.get(
        "use_segmentation_centroids", True
    )
    if not isinstance(use_segmentation_centroids, bool):
        raise ValueError(
            "position_analysis.use_segmentation_centroids must be boolean."
        )
    geometry_mode: GeometryMode = (
        "segmentation_preferred"
        if use_segmentation_centroids
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
        ("m6_domain_type_analysis", "legacy domain-type result"),
        ("molecular_order_type_analysis", "legacy molecular-order result"),
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


def _migrate_m6_cache(
    payload: Any,
    *,
    frame_range: range,
    geometry_mode: GeometryMode,
    physical_frame_ids: tuple[str, ...],
) -> tuple[
    tuple[DomainAnalysisM6CacheRecord, ...],
    list[DomainAnalysisSessionDiagnostic],
]:
    if payload is None:
        return (), []
    if not isinstance(payload, Mapping):
        return (), [_m6_diagnostic(
            "molecular_m6_analysis",
            "molecular_m6_analysis must be a JSON object.",
        )]
    records = payload.get("reproducible_cache", [])
    if not isinstance(records, list):
        return (), [_m6_diagnostic(
            "molecular_m6_analysis.reproducible_cache",
            "molecular_m6_analysis.reproducible_cache must be a list.",
        )]
    candidates = []
    candidate_positions = []
    migrated_diagnostics: list[DomainAnalysisSessionDiagnostic] = []
    expected_frame_ids = dict(zip(frame_range, physical_frame_ids, strict=True))
    for index, record in enumerate(records):
        identifier = f"molecular_m6_analysis.reproducible_cache[{index}]"
        if _is_v1_reproducible_m6_input(record):
            migrated_diagnostics.append(_m6_diagnostic(
                identifier,
                "Legacy reproducible M6 input does not contain a completed "
                "M6 computation required by v2 and was skipped without "
                "running M6.",
            ))
            continue
        scope = _v2_m6_cache_scope(record)
        if scope is not None:
            frame_index, record_geometry_mode, physical_frame_id = scope
            if (
                record_geometry_mode != geometry_mode
                or expected_frame_ids.get(frame_index) != physical_frame_id
            ):
                migrated_diagnostics.append(_m6_diagnostic(
                    identifier,
                    "M6 cache key is outside the migrated v2 workspace.",
                ))
                continue
        candidates.append(record)
        candidate_positions.append(index)
    restored, _, diagnostics = domain_analysis_cache_from_payload({
        "schema_version": CACHE_SCHEMA_VERSION,
        "m6_frames": candidates,
        "classifier_frames": [],
    })
    migrated_diagnostics.extend(
        _legacy_m6_diagnostic(value, candidate_positions=candidate_positions)
        for value in diagnostics
    )
    return restored, migrated_diagnostics


def _legacy_m6_diagnostic(
    diagnostic: DomainAnalysisSessionDiagnostic,
    *,
    candidate_positions: list[int],
) -> DomainAnalysisSessionDiagnostic:
    current = "domain_analysis.cache.m6_frames"
    legacy = "molecular_m6_analysis.reproducible_cache"
    identifier = diagnostic.identifier
    reason = diagnostic.reason
    for candidate_index, original_index in enumerate(candidate_positions):
        candidate = f"{current}[{candidate_index}]"
        original = f"{legacy}[{original_index}]"
        identifier = identifier.replace(candidate, original)
        reason = reason.replace(candidate, original)
    return DomainAnalysisSessionDiagnostic(
        component="m6_cache",
        identifier=identifier.replace(current, legacy),
        schema_version="1",
        reason=reason.replace(current, legacy),
    )


def _is_v1_reproducible_m6_input(value: Any) -> bool:
    return isinstance(value, Mapping) and {
        "cache_record_schema_version",
        "cache_key",
        "settings",
        "sample_coordinates",
    }.issubset(value)


def _v2_m6_cache_scope(value: Any) -> tuple[int, str, str] | None:
    if not isinstance(value, Mapping):
        return None
    key = value.get("key")
    computation = value.get("computation")
    if not isinstance(key, Mapping) or not isinstance(computation, Mapping):
        return None
    frame_index = computation.get("frame_index")
    geometry_mode = key.get("geometry_mode")
    physical_frame_id = key.get("physical_frame_id")
    if (
        isinstance(frame_index, bool)
        or not isinstance(frame_index, int)
        or not isinstance(geometry_mode, str)
        or not isinstance(physical_frame_id, str)
    ):
        return None
    return frame_index, geometry_mode, physical_frame_id


def _m6_diagnostic(
    identifier: str,
    reason: str,
) -> DomainAnalysisSessionDiagnostic:
    return DomainAnalysisSessionDiagnostic(
        component="m6_cache",
        identifier=identifier,
        schema_version="1",
        reason=reason,
    )


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
    if (
        any(
            isinstance(value, bool)
            or not isinstance(value, int)
            or value < 0
            for value in source_frame_indices
        )
        or len(set(source_frame_indices)) != len(source_frame_indices)
    ):
        raise ValueError(
            "working_series.source_frame_indices must contain unique "
            "non-negative integers."
        )
    return source_frame_indices
