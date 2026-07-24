"""Deterministic tables for hierarchical molecular-order classification."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from moltrack.analysis import (
    MolecularOrderHierarchy,
    MolecularOrderTypeClassificationResult,
    build_molecular_order_type_summary,
    molecular_order_hierarchy_fingerprint,
    molecular_order_type_classification_fingerprint,
)


MOLECULAR_ORDER_HIERARCHY_CSV_FILE = "molecular_order_hierarchy.csv"
MOLECULAR_ORDER_TYPES_CSV_FILE = "molecular_order_types.csv"
MOLECULAR_ORDER_ASSIGNMENTS_CSV_FILE = "molecular_order_assignments.csv"
MOLECULAR_ORDER_RANGE_SHARES_CSV_FILE = "molecular_order_range_shares.csv"
MOLECULAR_ORDER_TYPE_TABLE_FILES = (
    MOLECULAR_ORDER_HIERARCHY_CSV_FILE,
    MOLECULAR_ORDER_TYPES_CSV_FILE,
    MOLECULAR_ORDER_ASSIGNMENTS_CSV_FILE,
    MOLECULAR_ORDER_RANGE_SHARES_CSV_FILE,
)

MOLECULAR_ORDER_HIERARCHY_CSV_FIELDS = (
    "working_frame_index",
    "working_frame_number",
    "lattice_domain_id",
    "component_type",
    "dominant_symmetry",
    "theta3_lattice_deg",
    "theta6_lattice_deg",
    "molecule_count",
    "source_ids_json",
    "unresolved_source_ids_json",
    "orientational_subdomain_ids_json",
    "stacking_pattern",
    "stacking_mode",
    "stacking_phase",
    "lattice_domain_analysis_fingerprint",
    "row_assignment_fingerprint",
    "hierarchy_fingerprint",
    "uses_tracking",
)
MOLECULAR_ORDER_TYPES_CSV_FIELDS = (
    "layer",
    "type_id",
    "type_label",
    "dominant_symmetry",
    "prototype_theta3_lattice_deg",
    "prototype_theta6_lattice_deg",
    "prototype_angles_deg_json",
    "periodicity_deg",
    "stacking_pattern",
    "stacking_mode",
    "stacking_phase",
    "observation_count",
    "settings_fingerprint",
    "classification_fingerprint",
    "uses_tracking",
)
MOLECULAR_ORDER_ASSIGNMENTS_CSV_FIELDS = (
    "range_name",
    "range_start_working_frame_index",
    "range_end_working_frame_index",
    "working_frame_index",
    "working_frame_number",
    "lattice_domain_id",
    "component_type",
    "dominant_symmetry",
    "theta3_lattice_deg",
    "theta6_lattice_deg",
    "molecular_orientation_prototypes_deg_json",
    "molecular_orientation_periodicity_deg",
    "stacking_pattern",
    "stacking_mode",
    "stacking_phase",
    "molecule_count",
    "representative_source_ids_json",
    "geometry_status",
    "geometry_type_id",
    "geometry_type_label",
    "geometry_unclassified_reason",
    "orientation_status",
    "orientation_type_id",
    "orientation_type_label",
    "orientation_unclassified_reason",
    "stacking_status",
    "stacking_type_id",
    "stacking_type_label",
    "stacking_unclassified_reason",
    "source_view",
    "settings_fingerprint",
    "hierarchy_fingerprint",
    "classification_fingerprint",
    "uses_tracking",
)
MOLECULAR_ORDER_RANGE_SHARES_CSV_FIELDS = (
    "layer",
    "type_ids_json",
    "type_label",
    "description",
    "range_name",
    "range_start_working_frame_index",
    "range_end_working_frame_index",
    "denominator_count",
    "excluded_observation_count",
    "count",
    "share_percent",
    "share_delta_percentage_points",
    "representative_observation_key_json",
    "classification_fingerprint",
    "uses_tracking",
)


@dataclass(frozen=True)
class MolecularOrderTypeExportData:
    hierarchy_rows: tuple[Mapping[str, object], ...]
    type_rows: tuple[Mapping[str, object], ...]
    assignment_rows: tuple[Mapping[str, object], ...]
    range_share_rows: tuple[Mapping[str, object], ...]
    manifest: Mapping[str, object]
    classification_fingerprint: str | None

    @property
    def available(self) -> bool:
        return bool(self.manifest["available"])


def build_molecular_order_type_export_data(
    hierarchy: MolecularOrderHierarchy | None,
    classification: MolecularOrderTypeClassificationResult | None,
    *,
    frame_indices: tuple[int, ...],
    tables_included: bool,
) -> MolecularOrderTypeExportData:
    normalized_frames = tuple(sorted(set(int(value) for value in frame_indices)))
    if any(value < 0 for value in normalized_frames):
        raise ValueError("frame_indices must be non-negative.")
    if hierarchy is None or classification is None:
        if hierarchy is not None or classification is not None:
            raise ValueError(
                "Hierarchy and classification must be exported together."
            )
        return MolecularOrderTypeExportData(
            hierarchy_rows=(),
            type_rows=(),
            assignment_rows=(),
            range_share_rows=(),
            classification_fingerprint=None,
            manifest={
                "available": False,
                "reason": "hierarchical_type_classification_not_available",
                "uses_tracking": False,
                "tables_included": False,
                "table_files": [],
                "exported_frame_indices": list(normalized_frames),
                "record_counts": {
                    "hierarchy": 0,
                    "types": 0,
                    "assignments": 0,
                    "range_shares": 0,
                },
            },
        )
    if not isinstance(hierarchy, MolecularOrderHierarchy):
        raise TypeError("hierarchy must be MolecularOrderHierarchy or None.")
    if not isinstance(
        classification,
        MolecularOrderTypeClassificationResult,
    ):
        raise TypeError(
            "classification must be a molecular-order result or None."
        )
    hierarchy_fingerprint = molecular_order_hierarchy_fingerprint(hierarchy)
    if classification.hierarchy_fingerprint != hierarchy_fingerprint:
        raise ValueError(
            "Classification does not reference the exported hierarchy."
        )
    if any(
        frame_index not in hierarchy.input_frame_indices
        for frame_index in normalized_frames
    ):
        raise ValueError("frame_indices must belong to the hierarchy.")

    classification_fingerprint = (
        molecular_order_type_classification_fingerprint(classification)
    )
    if not normalized_frames:
        return MolecularOrderTypeExportData(
            hierarchy_rows=(),
            type_rows=(),
            assignment_rows=(),
            range_share_rows=(),
            classification_fingerprint=classification_fingerprint,
            manifest={
                "available": False,
                "reason": "no_hierarchical_results_for_exported_frames",
                "uses_tracking": False,
                "tables_included": False,
                "table_files": [],
                "analysis_scope": classification.analysis_scope.to_dict(),
                "classification_settings": classification.settings.to_dict(),
                "settings_fingerprint": (
                    classification.settings_fingerprint
                ),
                "hierarchy_fingerprint": hierarchy_fingerprint,
                "classification_fingerprint": classification_fingerprint,
                "exported_frame_indices": [],
                "record_counts": {
                    "hierarchy": 0,
                    "types": 0,
                    "assignments": 0,
                    "range_shares": 0,
                },
            },
        )
    hierarchy_rows = _hierarchy_rows(
        hierarchy,
        normalized_frames,
        hierarchy_fingerprint,
    )
    type_rows = _type_rows(classification, classification_fingerprint)
    assignment_rows = _assignment_rows(
        hierarchy,
        classification,
        normalized_frames,
        classification_fingerprint,
    )
    range_share_rows = _range_share_rows(
        classification,
        classification_fingerprint,
    )
    return MolecularOrderTypeExportData(
        hierarchy_rows=hierarchy_rows,
        type_rows=type_rows,
        assignment_rows=assignment_rows,
        range_share_rows=range_share_rows,
        classification_fingerprint=classification_fingerprint,
        manifest={
            "available": True,
            "reason": None,
            "uses_tracking": False,
            "tables_included": bool(tables_included),
            "table_files": (
                list(MOLECULAR_ORDER_TYPE_TABLE_FILES)
                if tables_included
                else []
            ),
            "analysis_scope": classification.analysis_scope.to_dict(),
            "classification_settings": classification.settings.to_dict(),
            "settings_fingerprint": classification.settings_fingerprint,
            "hierarchy_fingerprint": hierarchy_fingerprint,
            "classification_fingerprint": classification_fingerprint,
            "exported_frame_indices": list(normalized_frames),
            "hierarchy_row_scope": "exported_frame_indices",
            "assignment_row_scope": "exported_frame_indices",
            "type_catalog_scope": "classification_analysis_scope",
            "range_share_scope": "classification_analysis_scope",
            "record_counts": {
                "hierarchy": len(hierarchy_rows),
                "types": len(type_rows),
                "assignments": len(assignment_rows),
                "range_shares": len(range_share_rows),
            },
        },
    )


def write_molecular_order_type_tables(
    destination_dir: str | Path,
    export_data: MolecularOrderTypeExportData,
) -> dict[str, Path]:
    if not isinstance(export_data, MolecularOrderTypeExportData):
        raise TypeError(
            "export_data must be MolecularOrderTypeExportData."
        )
    destination = Path(destination_dir)
    destination.mkdir(parents=True, exist_ok=True)
    paths = {
        "molecular_order_hierarchy_csv": (
            destination / MOLECULAR_ORDER_HIERARCHY_CSV_FILE
        ),
        "molecular_order_types_csv": (
            destination / MOLECULAR_ORDER_TYPES_CSV_FILE
        ),
        "molecular_order_assignments_csv": (
            destination / MOLECULAR_ORDER_ASSIGNMENTS_CSV_FILE
        ),
        "molecular_order_range_shares_csv": (
            destination / MOLECULAR_ORDER_RANGE_SHARES_CSV_FILE
        ),
    }
    _write_csv(
        paths["molecular_order_hierarchy_csv"],
        export_data.hierarchy_rows,
        MOLECULAR_ORDER_HIERARCHY_CSV_FIELDS,
    )
    _write_csv(
        paths["molecular_order_types_csv"],
        export_data.type_rows,
        MOLECULAR_ORDER_TYPES_CSV_FIELDS,
    )
    _write_csv(
        paths["molecular_order_assignments_csv"],
        export_data.assignment_rows,
        MOLECULAR_ORDER_ASSIGNMENTS_CSV_FIELDS,
    )
    _write_csv(
        paths["molecular_order_range_shares_csv"],
        export_data.range_share_rows,
        MOLECULAR_ORDER_RANGE_SHARES_CSV_FIELDS,
    )
    return paths


def _hierarchy_rows(
    hierarchy: MolecularOrderHierarchy,
    frame_indices: tuple[int, ...],
    hierarchy_fingerprint: str,
) -> tuple[Mapping[str, object], ...]:
    selected = set(frame_indices)
    rows = []
    for frame in hierarchy.frames:
        if frame.frame_index not in selected:
            continue
        for domain in frame.lattice_domains:
            lattice = domain.lattice_domain
            order = domain.stacking_order
            rows.append({
                "working_frame_index": frame.frame_index,
                "working_frame_number": frame.frame_index + 1,
                "lattice_domain_id": lattice.lattice_domain_id,
                "component_type": lattice.component_type,
                "dominant_symmetry": lattice.dominant_symmetry,
                "theta3_lattice_deg": (
                    lattice.theta3_lattice_prototype_deg
                ),
                "theta6_lattice_deg": lattice.theta6_prototype_deg,
                "molecule_count": lattice.molecule_count,
                "source_ids_json": _json(lattice.source_ids),
                "unresolved_source_ids_json": _json(
                    domain.unresolved_source_ids
                ),
                "orientational_subdomain_ids_json": _json(
                    tuple(
                        value.orientational_subdomain_id
                        for value in domain.orientational_subdomains
                    )
                ),
                "stacking_pattern": order.pattern,
                "stacking_mode": order.mode,
                "stacking_phase": order.phase,
                "lattice_domain_analysis_fingerprint": (
                    frame.lattice_domain_analysis_fingerprint
                ),
                "row_assignment_fingerprint": (
                    frame.row_assignment_fingerprint
                ),
                "hierarchy_fingerprint": hierarchy_fingerprint,
                "uses_tracking": False,
            })
    return tuple(rows)


def _type_rows(
    classification: MolecularOrderTypeClassificationResult,
    classification_fingerprint: str,
) -> tuple[Mapping[str, object], ...]:
    common = {
        "settings_fingerprint": classification.settings_fingerprint,
        "classification_fingerprint": classification_fingerprint,
        "uses_tracking": False,
    }
    rows = []
    for value in classification.geometry_types:
        rows.append({
            **common,
            "layer": "geometry",
            "type_id": value.type_id,
            "type_label": value.label,
            "dominant_symmetry": value.dominant_symmetry,
            "prototype_theta3_lattice_deg": (
                value.prototype_theta3_lattice_deg
            ),
            "prototype_theta6_lattice_deg": (
                value.prototype_theta6_lattice_deg
            ),
            "prototype_angles_deg_json": "",
            "periodicity_deg": "",
            "stacking_pattern": "",
            "stacking_mode": "",
            "stacking_phase": "",
            "observation_count": value.observation_count,
        })
    for value in classification.orientation_types:
        rows.append({
            **common,
            "layer": "orientation",
            "type_id": value.type_id,
            "type_label": value.label,
            "dominant_symmetry": "",
            "prototype_theta3_lattice_deg": "",
            "prototype_theta6_lattice_deg": "",
            "prototype_angles_deg_json": _json(
                value.prototype_angles_deg
            ),
            "periodicity_deg": value.periodicity_deg,
            "stacking_pattern": "",
            "stacking_mode": "",
            "stacking_phase": "",
            "observation_count": value.observation_count,
        })
    for value in classification.stacking_types:
        rows.append({
            **common,
            "layer": "stacking",
            "type_id": value.type_id,
            "type_label": value.label,
            "dominant_symmetry": "",
            "prototype_theta3_lattice_deg": "",
            "prototype_theta6_lattice_deg": "",
            "prototype_angles_deg_json": "",
            "periodicity_deg": "",
            "stacking_pattern": value.pattern,
            "stacking_mode": value.mode,
            "stacking_phase": value.phase,
            "observation_count": value.observation_count,
        })
    return tuple(rows)


def _assignment_rows(
    hierarchy: MolecularOrderHierarchy,
    classification: MolecularOrderTypeClassificationResult,
    frame_indices: tuple[int, ...],
    classification_fingerprint: str,
) -> tuple[Mapping[str, object], ...]:
    selected = set(frame_indices)
    assignment_by_key = {
        value.observation_key: value for value in classification.assignments
    }
    rows = []
    for observation in classification.observations:
        if observation.frame_index not in selected:
            continue
        assignment = assignment_by_key[observation.stable_key]
        domain = hierarchy.frame_for_index(
            observation.frame_index
        ).domain_for_id(observation.lattice_domain_id)
        rows.append({
            "range_name": observation.range_name,
            "range_start_working_frame_index": (
                observation.range_start_frame
            ),
            "range_end_working_frame_index": observation.range_end_frame,
            "working_frame_index": observation.frame_index,
            "working_frame_number": observation.frame_index + 1,
            "lattice_domain_id": observation.lattice_domain_id,
            "component_type": observation.component_type,
            "dominant_symmetry": observation.dominant_symmetry,
            "theta3_lattice_deg": observation.theta3_lattice_deg,
            "theta6_lattice_deg": observation.theta6_lattice_deg,
            "molecular_orientation_prototypes_deg_json": _json(
                observation.molecular_orientation_prototypes_deg
            ),
            "molecular_orientation_periodicity_deg": (
                observation.molecular_orientation_periodicity_deg
            ),
            "stacking_pattern": observation.stacking_pattern,
            "stacking_mode": observation.stacking_mode,
            "stacking_phase": observation.stacking_phase,
            "molecule_count": observation.molecule_count,
            "representative_source_ids_json": _json(
                domain.lattice_domain.source_ids
            ),
            **_layer_columns("geometry", assignment.geometry),
            **_layer_columns("orientation", assignment.orientation),
            **_layer_columns("stacking", assignment.stacking),
            "source_view": observation.source_view,
            "settings_fingerprint": classification.settings_fingerprint,
            "hierarchy_fingerprint": classification.hierarchy_fingerprint,
            "classification_fingerprint": classification_fingerprint,
            "uses_tracking": False,
        })
    return tuple(rows)


def _layer_columns(prefix, assignment) -> dict[str, object]:
    return {
        f"{prefix}_status": assignment.status,
        f"{prefix}_type_id": assignment.type_id,
        f"{prefix}_type_label": assignment.type_label,
        f"{prefix}_unclassified_reason": assignment.unclassified_reason,
    }


def _range_share_rows(
    classification: MolecularOrderTypeClassificationResult,
    classification_fingerprint: str,
) -> tuple[Mapping[str, object], ...]:
    summary = build_molecular_order_type_summary(classification)
    summary_by_name = {
        value.range_name: value for value in summary.range_summaries
    }
    rows = []
    for row in summary.rows:
        for share in row.range_shares:
            denominator = share.denominator_count
            range_summary = summary_by_name[share.range_name]
            rows.append({
                "layer": row.layer,
                "type_ids_json": _json(row.key.type_ids),
                "type_label": row.label,
                "description": row.description,
                "range_name": share.range_name,
                "range_start_working_frame_index": (
                    share.frame_range.start_frame
                ),
                "range_end_working_frame_index": (
                    share.frame_range.end_frame
                ),
                "denominator_count": denominator,
                "excluded_observation_count": (
                    range_summary.total_observation_count - denominator
                ),
                "count": share.count,
                "share_percent": share.share_percent,
                "share_delta_percentage_points": (
                    row.share_delta_percentage_points
                ),
                "representative_observation_key_json": (
                    ""
                    if share.representative_observation_key is None
                    else _json(share.representative_observation_key)
                ),
                "classification_fingerprint": classification_fingerprint,
                "uses_tracking": False,
            })
    return tuple(rows)


def _write_csv(
    path: Path,
    rows: tuple[Mapping[str, object], ...],
    fieldnames: tuple[str, ...],
) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
            extrasaction="raise",
        )
        writer.writeheader()
        writer.writerows(rows)


def _json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=True,
        separators=(",", ":"),
    )


__all__ = [
    "MOLECULAR_ORDER_TYPE_TABLE_FILES",
    "MolecularOrderTypeExportData",
    "build_molecular_order_type_export_data",
    "write_molecular_order_type_tables",
]
