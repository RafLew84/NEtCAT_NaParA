from __future__ import annotations

import csv
import shutil
import tempfile
from pathlib import Path
from typing import Any

from moltrack.analysis.domain_analysis import (
    ClassifierOutcome,
    DOMAIN_ANALYSIS_SESSION_SCHEMA_VERSION,
    DomainAnalysisSessionState,
    M6FrameGate,
    M6PublishedComponent,
)
from moltrack.analysis.domain_analysis.fingerprints import canonical_sha256

from .analysis_package import AnalysisExportPackageResult
from .domain_analysis_classifier_export import classifier_export_tables
from .domain_analysis_export_manifest import (
    domain_analysis_frame_identity,
    write_domain_analysis_manifest,
)
from .domain_analysis_export_schema import (
    DOMAIN_ANALYSIS_TABLE_FILES,
    DOMAIN_ANALYSIS_TABLE_HEADERS,
    DomainAnalysisExportSettings,
)
from .package_io import (
    csv_json_cell,
    path_exists,
    publish_path,
    relative_package_files,
)


def export_domain_analysis_package(
    snapshot: DomainAnalysisSessionState,
    settings: DomainAnalysisExportSettings,
) -> AnalysisExportPackageResult:
    """Publish schema v9 from one authoritative Domain Analysis snapshot."""

    publication = _validated_publication(snapshot, settings)
    gate = publication.result.m6_gate
    assert gate is not None
    tables = _analysis_tables(
        gate.frames,
        settings,
        publication.result.classifier_status,
        publication.result.classifier_outcomes,
    )
    destination = settings.destination
    if path_exists(destination) and not settings.overwrite:
        raise FileExistsError(
            f"Domain Analysis package destination already exists: {destination}"
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    ))
    try:
        record_counts = _write_tables(staging, tables)
        write_domain_analysis_manifest(
            staging,
            snapshot,
            settings,
            record_counts,
        )
        relative_files = relative_package_files(staging)
        publish_path(staging, destination, overwrite=settings.overwrite)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return AnalysisExportPackageResult(
        package_path=destination,
        package_format="directory",
        relative_files=relative_files,
        record_counts=record_counts,
    )


def _validated_publication(snapshot, settings):
    if not isinstance(snapshot, DomainAnalysisSessionState):
        raise TypeError("snapshot must be a DomainAnalysisSessionState instance.")
    if not isinstance(settings, DomainAnalysisExportSettings):
        raise TypeError("settings must be DomainAnalysisExportSettings.")
    if snapshot.schema_version != DOMAIN_ANALYSIS_SESSION_SCHEMA_VERSION:
        raise ValueError(
            "Unsupported Domain Analysis snapshot schema_version: "
            f"{snapshot.schema_version}."
        )
    publication = snapshot.published_result
    if publication is None or publication.result.m6_gate is None:
        raise ValueError(
            "Domain Analysis export requires a published M6 result."
        )
    frame_indices = publication.request.frame_indices
    if not frame_indices or frame_indices[-1] >= len(settings.source_frame_indices):
        raise ValueError(
            "source_frame_indices do not cover the published frame range."
        )
    gate = publication.result.m6_gate
    _validate_classifier_failure_frames(
        publication.result.classifier_outcomes,
        gate.frames,
    )
    for frame in gate.frames:
        if settings.physical_frame_ids[frame.frame_index] != frame.physical_frame_id:
            raise ValueError(
                "physical_frame_ids do not match the published M6 snapshot."
            )
    settings_fingerprint = canonical_sha256(settings.m6_settings.to_dict())
    if any(
        frame.backend_identity.settings_fingerprint != settings_fingerprint
        for frame in gate.frames
    ):
        raise ValueError("M6 settings do not match the published M6 snapshot.")
    return publication


def _analysis_tables(
    frames: tuple[M6FrameGate, ...],
    settings: DomainAnalysisExportSettings,
    classifier_status: str,
    classifier_outcomes: tuple[ClassifierOutcome, ...] | None,
) -> dict[str, list[dict[str, Any]]]:
    tables: dict[str, list[dict[str, Any]]] = {
        name: [] for name in DOMAIN_ANALYSIS_TABLE_FILES
    }
    for frame in frames:
        source_frame_index = settings.source_frame_indices[frame.frame_index]
        tables["domain_analysis_frames.csv"].append(
            _frame_row(frame, source_frame_index, classifier_status)
        )
        for component in frame.full_domains + frame.small_ordered_islands:
            tables["domain_analysis_domains.csv"].append(
                _domain_row(frame, component, source_frame_index)
            )
            tables["domain_analysis_memberships.csv"].extend(
                _component_membership_rows(frame, component, source_frame_index)
            )
        tables["domain_analysis_memberships.csv"].extend(
            _outside_membership_rows(frame, source_frame_index)
        )
    tables.update(classifier_export_tables(
        classifier_outcomes,
        settings,
    ))
    return tables


def _validate_classifier_failure_frames(
    outcomes: tuple[ClassifierOutcome, ...] | None,
    frames: tuple[M6FrameGate, ...],
) -> None:
    frame_indices = {frame.frame_index for frame in frames}
    for outcome in outcomes or ():
        if (
            outcome.failure_frame_index is not None
            and outcome.failure_frame_index not in frame_indices
        ):
            raise ValueError(
                "Classifier failure frame is outside the published M6 gate."
            )


def _frame_row(
    frame: M6FrameGate,
    source_frame_index: int,
    classifier_status: str,
) -> dict[str, Any]:
    provenance = frame.presentation_provenance
    return {
        **domain_analysis_frame_identity(frame, source_frame_index),
        "m6_status": "completed",
        "classifier_status": classifier_status,
        "m6_gate_fingerprint": frame.m6_gate_fingerprint,
        "source_geometry_fingerprint": frame.source_geometry_fingerprint,
        "coordinate_frame": frame.coordinate_frame,
        "coordinate_transform_fingerprint": frame.coordinate_transform_fingerprint,
        "m6_settings_fingerprint": frame.backend_identity.settings_fingerprint,
        "m6_algorithm_version": frame.backend_identity.algorithm_version,
        "analyzed_molecule_count": frame.analyzed_molecule_count,
        "full_domain_count": len(frame.full_domains),
        "small_ordered_island_count": len(frame.small_ordered_islands),
        "outside_molecule_count": len(frame.outside_members),
        "analyzed_area_nm2": frame.analyzed_area_nm2,
        "full_domain_area_nm2": frame.full_domain_area_nm2,
        "small_ordered_island_area_nm2": frame.small_ordered_island_area_nm2,
        "outside_area_nm2": frame.outside_area_nm2,
        "pixel_area_nm2": frame.pixel_area_nm2,
        "analyzed_pixels_xy": csv_json_cell(frame.analyzed_pixels_xy),
        "outside_pixels_xy": csv_json_cell(frame.outside_pixels_xy),
        "raw_height_px": provenance.raw_shape[0],
        "raw_width_px": provenance.raw_shape[1],
        "expanded_height_px": provenance.expanded_shape[0],
        "expanded_width_px": provenance.expanded_shape[1],
        "source_view": provenance.source_view,
        "frame_origin_x_px": provenance.frame_origin_xy[0],
        "frame_origin_y_px": provenance.frame_origin_xy[1],
        "canvas_offset_x_px": provenance.canvas_offset_xy[0],
        "canvas_offset_y_px": provenance.canvas_offset_xy[1],
        "registration_fingerprint": provenance.registration_fingerprint,
    }


def _domain_row(
    frame: M6FrameGate,
    component: M6PublishedComponent,
    source_frame_index: int,
) -> dict[str, Any]:
    return {
        **domain_analysis_frame_identity(frame, source_frame_index),
        "lattice_domain_id": component.lattice_domain_id,
        "component_type": component.component_type,
        "molecule_count": len(component.members),
        "footprint_area_nm2": component.footprint_area_nm2,
        "centroid_x_nm": component.centroid_xy_nm[0],
        "centroid_y_nm": component.centroid_xy_nm[1],
        "bounds_x1_nm": component.bounds_xyxy_nm[0],
        "bounds_y1_nm": component.bounds_xyxy_nm[1],
        "bounds_x2_nm": component.bounds_xyxy_nm[2],
        "bounds_y2_nm": component.bounds_xyxy_nm[3],
        "points_xy_nm": csv_json_cell(
            tuple(value.point_xy_nm for value in component.members)
        ),
        "footprint_pixels_xy": csv_json_cell(component.footprint_pixels_xy),
        "m6_qc_flags": csv_json_cell(component.qc_flags),
        "m6_gate_fingerprint": frame.m6_gate_fingerprint,
    }


def _component_membership_rows(
    frame: M6FrameGate,
    component: M6PublishedComponent,
    source_frame_index: int,
) -> list[dict[str, Any]]:
    rows = []
    for member in component.members:
        source_id = member.source_id
        role = "member"
        if source_id in component.core_source_ids:
            role = "core"
        elif source_id in component.halo_source_ids:
            role = "halo"
        rows.append(_membership_row(
            frame,
            source_frame_index,
            source_id=source_id,
            source_kind=member.source_kind,
            partition=component.component_type,
            lattice_domain_id=component.lattice_domain_id,
            membership_role=role,
            point=member.point_xy_nm,
        ))
    return rows


def _outside_membership_rows(
    frame: M6FrameGate,
    source_frame_index: int,
) -> list[dict[str, Any]]:
    return [
        _membership_row(
            frame,
            source_frame_index,
            source_id=member.source_id,
            source_kind=member.source_kind,
            partition="outside",
            lattice_domain_id="",
            membership_role="outside",
            point=member.point_xy_nm,
        )
        for member in frame.outside_members
    ]


def _membership_row(
    frame: M6FrameGate,
    source_frame_index: int,
    *,
    source_id: str,
    source_kind: str,
    partition: str,
    lattice_domain_id: str,
    membership_role: str,
    point: tuple[float, float],
) -> dict[str, Any]:
    return {
        **domain_analysis_frame_identity(frame, source_frame_index),
        "source_id": source_id,
        "source_kind": source_kind,
        "partition": partition,
        "lattice_domain_id": lattice_domain_id,
        "membership_role": membership_role,
        "point_x_nm": point[0],
        "point_y_nm": point[1],
        "m6_gate_fingerprint": frame.m6_gate_fingerprint,
    }


def _write_tables(
    root: Path,
    tables: dict[str, list[dict[str, Any]]],
) -> tuple[tuple[str, int], ...]:
    for name in DOMAIN_ANALYSIS_TABLE_FILES:
        with (root / name).open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=DOMAIN_ANALYSIS_TABLE_HEADERS[name],
            )
            writer.writeheader()
            writer.writerows(tables[name])
    return tuple(sorted((name, len(rows)) for name, rows in tables.items()))
