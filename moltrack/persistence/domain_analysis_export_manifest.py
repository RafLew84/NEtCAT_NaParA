from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from moltrack import __version__ as moltrack_version
from moltrack.analysis.domain_analysis import DomainAnalysisSessionState, M6FrameGate
from moltrack.analysis.domain_analysis.fingerprints import canonical_sha256

from .domain_analysis_export_schema import (
    DOMAIN_ANALYSIS_EXPORT_SCHEMA_VERSION,
    DOMAIN_ANALYSIS_PUBLISHED_RESULT_SCHEMA_VERSION,
    DOMAIN_ANALYSIS_TABLE_FILES,
    DOMAIN_ANALYSIS_TABLE_HEADERS,
    DOMAIN_ANALYSIS_TABLE_SCHEMA_VERSION,
    DomainAnalysisExportSettings,
)
from .package_io import file_sha256


def write_domain_analysis_manifest(
    root: Path,
    snapshot: DomainAnalysisSessionState,
    settings: DomainAnalysisExportSettings,
    record_counts: tuple[tuple[str, int], ...],
) -> None:
    publication = snapshot.published_result
    assert publication is not None and publication.result.m6_gate is not None
    gate = publication.result.m6_gate
    exported_frames = [
        domain_analysis_frame_identity(
            frame,
            settings.source_frame_indices[frame.frame_index],
        )
        for frame in gate.frames
    ]
    manifest = {
        "export_schema_version": DOMAIN_ANALYSIS_EXPORT_SCHEMA_VERSION,
        "package_kind": "moltrack_analysis",
        "application": {"name": "MolTrack", "version": moltrack_version},
        "source": _source_manifest(settings),
        "working_series": _working_series_manifest(settings, exported_frames),
        "analysis": {
            "analysis_mode": "domain_analysis_published_snapshot",
            "uses_tracking": False,
            "domain_analysis": _domain_analysis_manifest(snapshot, settings),
        },
        "table_schemas": _table_schemas(),
        "files": _file_entries(root, record_counts),
    }
    (root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def domain_analysis_frame_identity(
    frame: M6FrameGate,
    source_frame_index: int,
) -> dict[str, Any]:
    return {
        "physical_frame_id": frame.physical_frame_id,
        "working_frame_index": frame.frame_index,
        "source_frame_index": source_frame_index,
    }


def _source_manifest(settings: DomainAnalysisExportSettings) -> dict[str, Any]:
    identity = settings.source_identity.to_dict()
    return {
        "identity": identity,
        "identity_fingerprint": canonical_sha256(identity),
    }


def _working_series_manifest(
    settings: DomainAnalysisExportSettings,
    exported_frames: list[dict[str, Any]],
) -> dict[str, Any]:
    identity = {
        "physical_frame_ids": list(settings.physical_frame_ids),
        "source_frame_indices": list(settings.source_frame_indices),
    }
    return {
        "frame_count": len(settings.source_frame_indices),
        **identity,
        "exported_frames": exported_frames,
        "identity_fingerprint": canonical_sha256(identity),
    }


def _domain_analysis_manifest(
    snapshot: DomainAnalysisSessionState,
    settings: DomainAnalysisExportSettings,
) -> dict[str, Any]:
    publication = snapshot.published_result
    assert publication is not None and publication.result.m6_gate is not None
    request = publication.request
    return {
        "session_schema_version": snapshot.schema_version,
        "published_result_schema_version": (
            DOMAIN_ANALYSIS_PUBLISHED_RESULT_SCHEMA_VERSION
        ),
        "request": {
            "frame_start": request.frame_range.start,
            "frame_stop": request.frame_range.stop,
            "geometry_mode": request.geometry_mode,
            "classifier_ids": list(request.classifier_ids),
            "request_fingerprint": publication.request_fingerprint,
        },
        "m6_settings": settings.m6_settings.to_dict(),
        "result": {
            "run_status": publication.result.run_status,
            "classifier_status": publication.result.classifier_status,
        },
        "m6_gate": _m6_gate_manifest(
            publication.result.m6_gate.frames,
            settings.source_frame_indices,
        ),
    }


def _m6_gate_manifest(
    frames: tuple[M6FrameGate, ...],
    source_frame_indices: tuple[int, ...],
) -> dict[str, Any]:
    frame_fingerprints = [frame.m6_gate_fingerprint for frame in frames]
    return {
        "range_fingerprint": canonical_sha256({
            "schema_version": "domain-analysis-m6-range-export-v1",
            "frame_fingerprints": frame_fingerprints,
        }),
        "frames": [
            _m6_frame_manifest(frame, source_frame_indices[frame.frame_index])
            for frame in frames
        ],
    }


def _m6_frame_manifest(
    frame: M6FrameGate,
    source_frame_index: int,
) -> dict[str, Any]:
    provenance = frame.presentation_provenance
    return {
        **domain_analysis_frame_identity(frame, source_frame_index),
        "m6_gate_fingerprint": frame.m6_gate_fingerprint,
        "source_geometry_fingerprint": frame.source_geometry_fingerprint,
        "m6_settings_fingerprint": frame.m6_settings_fingerprint,
        "m6_algorithm_version": frame.m6_algorithm_version,
        "coordinate_frame": frame.coordinate_frame,
        "coordinate_transform_fingerprint": frame.coordinate_transform_fingerprint,
        "presentation_provenance": {
            "raw_shape": list(provenance.raw_shape),
            "expanded_shape": list(provenance.expanded_shape),
            "source_view": provenance.source_view,
            "frame_origin_xy": list(provenance.frame_origin_xy),
            "canvas_offset_xy": list(provenance.canvas_offset_xy),
            "registration_fingerprint": provenance.registration_fingerprint,
        },
    }


def _table_schemas() -> dict[str, dict[str, Any]]:
    return {
        name: {
            "schema_version": DOMAIN_ANALYSIS_TABLE_SCHEMA_VERSION,
            "columns": list(DOMAIN_ANALYSIS_TABLE_HEADERS[name]),
        }
        for name in sorted(DOMAIN_ANALYSIS_TABLE_FILES)
    }


def _file_entries(
    root: Path,
    record_counts: tuple[tuple[str, int], ...],
) -> list[dict[str, Any]]:
    counts = dict(record_counts)
    return [
        {
            "path": name,
            "record_count": counts[name],
            "sha256": file_sha256(root / name),
        }
        for name in sorted(DOMAIN_ANALYSIS_TABLE_FILES)
    ]
