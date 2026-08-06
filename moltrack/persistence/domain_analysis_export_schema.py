from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DOMAIN_ANALYSIS_EXPORT_SCHEMA_VERSION = 9
DOMAIN_ANALYSIS_PUBLISHED_RESULT_SCHEMA_VERSION = 1
DOMAIN_ANALYSIS_TABLE_SCHEMA_VERSION = 1
DOMAIN_ANALYSIS_TABLE_FILES = (
    "domain_analysis_frames.csv",
    "domain_analysis_domains.csv",
    "domain_analysis_memberships.csv",
    "domain_analysis_molecule_classifications.csv",
    "domain_analysis_domain_classifications.csv",
    "domain_analysis_classifier_outcomes.csv",
)

DOMAIN_ANALYSIS_TABLE_HEADERS = {
    "domain_analysis_frames.csv": (
        "physical_frame_id", "working_frame_index", "source_frame_index",
        "m6_status", "classifier_status", "m6_gate_fingerprint",
        "source_geometry_fingerprint", "coordinate_frame",
        "coordinate_transform_fingerprint", "m6_settings_fingerprint",
        "m6_algorithm_version", "analyzed_molecule_count",
        "full_domain_count", "small_ordered_island_count",
        "outside_molecule_count", "analyzed_area_nm2",
        "full_domain_area_nm2", "small_ordered_island_area_nm2",
        "outside_area_nm2", "pixel_area_nm2", "analyzed_pixels_xy",
        "outside_pixels_xy", "raw_height_px", "raw_width_px",
        "expanded_height_px", "expanded_width_px", "source_view",
        "frame_origin_x_px", "frame_origin_y_px", "canvas_offset_x_px",
        "canvas_offset_y_px", "registration_fingerprint",
    ),
    "domain_analysis_domains.csv": (
        "physical_frame_id", "working_frame_index", "source_frame_index",
        "lattice_domain_id", "component_type", "molecule_count",
        "footprint_area_nm2", "centroid_x_nm", "centroid_y_nm",
        "bounds_x1_nm", "bounds_y1_nm", "bounds_x2_nm", "bounds_y2_nm",
        "points_xy_nm", "footprint_pixels_xy", "m6_qc_flags",
        "m6_gate_fingerprint",
    ),
    "domain_analysis_memberships.csv": (
        "physical_frame_id", "working_frame_index", "source_frame_index",
        "source_id", "source_kind", "partition", "lattice_domain_id",
        "membership_role", "point_x_nm", "point_y_nm",
        "m6_gate_fingerprint",
    ),
    "domain_analysis_molecule_classifications.csv": (
        "physical_frame_id", "working_frame_index", "source_frame_index",
        "classifier_id", "lattice_domain_id", "source_id",
        "classification_status", "orientation_label", "evidence_strength",
        "component_id", "m6_gate_fingerprint", "classifier_schema_version",
        "classifier_algorithm_version", "classifier_settings_fingerprint",
    ),
    "domain_analysis_domain_classifications.csv": (
        "physical_frame_id", "working_frame_index", "source_frame_index",
        "classifier_id", "lattice_domain_id", "label", "molecule_count",
        "counts", "evidence_fraction_of_domain",
        "coherent_evidence_fraction_of_domain", "resolved_fraction",
        "resolved_evidence_fraction_of_domain", "dominant_class",
        "dominance_margin", "reason", "m6_gate_fingerprint",
        "classifier_schema_version", "classifier_algorithm_version",
        "classifier_settings_fingerprint", "aggregation_policy_version",
    ),
    "domain_analysis_classifier_outcomes.csv": (
        "classifier_id", "status", "classifier_schema_version",
        "classifier_algorithm_version", "classifier_settings_fingerprint",
        "aggregation_policy_version", "result_fingerprint",
        "failure_physical_frame_id", "failure_frame_index",
        "failure_source_frame_index", "error_message",
    ),
}


def exported_frame_identity(
    physical_frame_id: str,
    working_frame_index: int,
    source_frame_index: int,
) -> dict[str, str | int]:
    return {
        "physical_frame_id": physical_frame_id,
        "working_frame_index": working_frame_index,
        "source_frame_index": source_frame_index,
    }


@dataclass(frozen=True)
class CanonicalJsonObject:
    """Deeply immutable, deterministic snapshot of one JSON object."""

    _canonical_json: str

    def __init__(self, value: Mapping[str, Any]) -> None:
        if not isinstance(value, Mapping) or not value:
            raise ValueError("Canonical JSON value must be a non-empty mapping.")
        try:
            encoded = json.dumps(dict(value), ensure_ascii=False, sort_keys=True)
            normalized = json.loads(encoded)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "Canonical JSON value must contain JSON-compatible values."
            ) from exc
        if not isinstance(normalized, dict):
            raise ValueError("Canonical JSON value must be a JSON object.")
        object.__setattr__(
            self,
            "_canonical_json",
            json.dumps(
                normalized,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return json.loads(self._canonical_json)


@dataclass(frozen=True)
class DomainAnalysisExportSettings:
    """Destination and immutable series provenance for schema-v9 export."""

    destination: Path
    source_frame_indices: tuple[int, ...]
    physical_frame_ids: tuple[str, ...]
    source_identity: CanonicalJsonObject
    m6_settings: CanonicalJsonObject
    overwrite: bool = False

    def __post_init__(self) -> None:
        destination = Path(self.destination)
        if not str(destination).strip():
            raise ValueError("Domain Analysis export destination must not be empty.")
        source_indices = tuple(self.source_frame_indices)
        if not source_indices or any(
            isinstance(value, bool) or not isinstance(value, int) or value < 0
            for value in source_indices
        ):
            raise ValueError(
                "source_frame_indices must contain non-negative integer values."
            )
        if len(set(source_indices)) != len(source_indices):
            raise ValueError("source_frame_indices must not contain duplicates.")
        physical_ids = tuple(
            str(value).strip() for value in self.physical_frame_ids
        )
        if len(physical_ids) != len(source_indices) or any(
            not value for value in physical_ids
        ):
            raise ValueError(
                "physical_frame_ids must identify every working-series frame."
            )
        if len(set(physical_ids)) != len(physical_ids):
            raise ValueError("physical_frame_ids must not contain duplicates.")
        if not isinstance(self.overwrite, bool):
            raise TypeError("overwrite must be a bool.")
        if not isinstance(self.source_identity, CanonicalJsonObject):
            raise TypeError("source_identity must be a CanonicalJsonObject.")
        if not isinstance(self.m6_settings, CanonicalJsonObject):
            raise TypeError("m6_settings must be a CanonicalJsonObject.")
        object.__setattr__(self, "destination", destination)
        object.__setattr__(self, "source_frame_indices", source_indices)
        object.__setattr__(self, "physical_frame_ids", physical_ids)
