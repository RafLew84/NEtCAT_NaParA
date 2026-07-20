from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Literal, Mapping

from moltrack.analysis import (
    M6_DOMAIN_TYPE_ALGORITHM_VERSION,
    M6DomainType,
    M6DomainTypeClassificationResult,
    M6DomainTypeRangeAggregate,
    M6DomainTypeRangeComparison,
    M6DomainTypeRangeSide,
    M6SingleRangeDomainTypeSummary,
)


DOMAIN_TYPES_CSV_FIELDS = (
    "domain_type_id",
    "domain_type_label",
    "prototype_orientation_deg",
    "prototype_bond_length_nm",
    "orientation_circular_spread_deg",
    "bond_length_iqr_nm",
    "observation_count",
    "classification_observation_count",
    "classified_observation_count",
    "unclassified_observation_count",
    "unclassified_small_ordered_island_excluded_count",
    "unclassified_missing_bond_length_statistics_count",
    "unclassified_bond_length_heterogeneity_qc_count",
    "unclassified_below_minimum_observations_per_type_count",
)

DOMAIN_TYPE_RANGES_CSV_FIELDS = (
    "condition_order",
    "range_name",
    "range_start_working_frame_index",
    "range_start_working_frame_number",
    "range_end_working_frame_index",
    "range_end_working_frame_number",
    "working_frame_indices_json",
    "source_frame_indices_json",
    "available_working_frame_indices_json",
    "available_source_frame_indices_json",
    "source_view",
    "component_scope",
    "domain_type_id",
    "domain_type_label",
    "classification_status",
    "analyzed_frame_count",
    "available_frame_count",
    "valid_representative_fraction_frame_count",
    "valid_fov_fraction_frame_count",
    "frames_with_full_domain_count",
    "frames_with_full_domain_percent",
    "mean_full_domains_per_available_frame",
    "median_full_domains_per_available_frame",
    "max_full_domains_per_available_frame",
    "domain_observation_count",
    "domain_type_count",
    "unclassified_observation_count",
    "full_domain_molecule_fraction",
    "full_domain_footprint_fraction",
    "observation_count",
    "frames_with_type_count",
    "frames_with_type_percent",
    "mean_instances_per_available_frame",
    "mean_molecule_fraction_of_valid_representatives",
    "mean_footprint_fraction_of_valid_fov",
    "mean_domain_coherent_q6",
    "mean_molecule_count",
    "mean_footprint_area_nm2",
)

DOMAIN_TYPE_COMPARISON_CSV_FIELDS = (
    "direction",
    "domain_type_id",
    "domain_type_label",
    "prototype_orientation_deg",
    "prototype_bond_length_nm",
    "orientation_circular_spread_deg",
    "bond_length_iqr_nm",
    "first_range_name",
    "second_range_name",
    "first_domain_instance_count",
    "first_frames_with_type_count",
    "first_frames_with_type_percent",
    "first_mean_domain_instances_per_available_frame",
    "first_mean_molecule_fraction",
    "first_mean_footprint_fraction",
    "first_mean_domain_coherent_q6",
    "first_mean_molecule_count",
    "first_mean_footprint_area_nm2",
    "first_available_frame_count",
    "first_valid_representative_fraction_frame_count",
    "first_valid_fov_fraction_frame_count",
    "second_domain_instance_count",
    "second_frames_with_type_count",
    "second_frames_with_type_percent",
    "second_mean_domain_instances_per_available_frame",
    "second_mean_molecule_fraction",
    "second_mean_footprint_fraction",
    "second_mean_domain_coherent_q6",
    "second_mean_molecule_count",
    "second_mean_footprint_area_nm2",
    "second_available_frame_count",
    "second_valid_representative_fraction_frame_count",
    "second_valid_fov_fraction_frame_count",
    "domain_instance_count_delta",
    "frames_with_type_count_delta",
    "frames_with_type_percentage_points_delta",
    "mean_domain_instances_per_available_frame_delta",
    "mean_molecule_fraction_percentage_points_delta",
    "mean_footprint_fraction_percentage_points_delta",
    "mean_domain_coherent_q6_delta",
    "mean_molecule_count_delta",
    "mean_footprint_area_nm2_delta",
)

DOMAIN_TYPES_CSV_FILE = "domain_types.csv"
DOMAIN_TYPE_RANGES_CSV_FILE = "domain_type_ranges.csv"
DOMAIN_TYPE_COMPARISON_CSV_FILE = "domain_type_comparison.csv"
DOMAIN_TYPE_TABLE_FILES = (
    DOMAIN_TYPES_CSV_FILE,
    DOMAIN_TYPE_RANGES_CSV_FILE,
    DOMAIN_TYPE_COMPARISON_CSV_FILE,
)

_UNCLASSIFIED_REASON_COLUMNS = {
    "small_ordered_island_excluded": (
        "unclassified_small_ordered_island_excluded_count"
    ),
    "missing_bond_length_statistics": (
        "unclassified_missing_bond_length_statistics_count"
    ),
    "bond_length_heterogeneity_qc": (
        "unclassified_bond_length_heterogeneity_qc_count"
    ),
    "below_minimum_observations_per_type": (
        "unclassified_below_minimum_observations_per_type_count"
    ),
}

_RangeOrder = Literal["single", "first", "second"]


@dataclass(frozen=True)
class M6DomainTypeExportData:
    domain_type_rows: tuple[Mapping[str, object], ...]
    range_rows: tuple[Mapping[str, object], ...]
    comparison_rows: tuple[Mapping[str, object], ...]
    manifest: Mapping[str, object]


def build_m6_domain_type_export_data(
    classification: M6DomainTypeClassificationResult | None,
    table_result: M6SingleRangeDomainTypeSummary | M6DomainTypeRangeComparison | None,
    *,
    tables_included: bool,
) -> M6DomainTypeExportData:
    """Build deterministic tabular rows and provenance for one classification."""

    if classification is None:
        if table_result is not None:
            raise ValueError("A domain type table result requires a classification.")
        return M6DomainTypeExportData(
            domain_type_rows=(),
            range_rows=(),
            comparison_rows=(),
            manifest=_empty_manifest(tables_included=tables_included),
        )
    if not isinstance(classification, M6DomainTypeClassificationResult):
        raise TypeError("classification must be a domain type result or None.")
    if table_result is None:
        raise ValueError("A classification requires its range table result.")
    _validate_table_result(classification, table_result)

    summaries = _ordered_summaries(table_result)
    return M6DomainTypeExportData(
        domain_type_rows=_domain_type_rows(classification),
        range_rows=_range_rows(classification, table_result, summaries),
        comparison_rows=_comparison_rows(table_result),
        manifest=_classification_manifest(
            classification,
            summaries,
            tables_included=tables_included,
        ),
    )


def write_m6_domain_type_tables(
    destination_dir: str | Path,
    export_data: M6DomainTypeExportData,
) -> dict[str, Path]:
    if not isinstance(export_data, M6DomainTypeExportData):
        raise TypeError("export_data must be M6DomainTypeExportData.")
    destination = Path(destination_dir)
    destination.mkdir(parents=True, exist_ok=True)
    paths = {
        "domain_types_csv": destination / DOMAIN_TYPES_CSV_FILE,
        "domain_type_ranges_csv": destination / DOMAIN_TYPE_RANGES_CSV_FILE,
        "domain_type_comparison_csv": destination / DOMAIN_TYPE_COMPARISON_CSV_FILE,
    }
    _write_csv(
        paths["domain_types_csv"],
        export_data.domain_type_rows,
        DOMAIN_TYPES_CSV_FIELDS,
    )
    _write_csv(
        paths["domain_type_ranges_csv"],
        export_data.range_rows,
        DOMAIN_TYPE_RANGES_CSV_FIELDS,
    )
    _write_csv(
        paths["domain_type_comparison_csv"],
        export_data.comparison_rows,
        DOMAIN_TYPE_COMPARISON_CSV_FIELDS,
    )
    return paths


def _validate_table_result(
    classification: M6DomainTypeClassificationResult,
    table_result: M6SingleRangeDomainTypeSummary | M6DomainTypeRangeComparison,
) -> None:
    if not isinstance(
        table_result,
        (M6SingleRangeDomainTypeSummary, M6DomainTypeRangeComparison),
    ):
        raise TypeError("table_result must be a domain type summary or comparison.")
    if table_result.classification_input_fingerprint != classification.input_fingerprint:
        raise ValueError("Domain type table result uses a different classification.")
    if table_result.source_view != classification.source_view:
        raise ValueError("Domain type table result uses a different source view.")
    if isinstance(table_result, M6SingleRangeDomainTypeSummary):
        actual_ranges = (table_result.frame_range,)
        expected_mode = "single_range"
    else:
        actual_ranges = (table_result.first_range, table_result.second_range)
        expected_mode = "compare_ranges"
    if classification.analysis_scope.analysis_mode != expected_mode:
        raise ValueError("Domain type table result uses a different analysis mode.")
    if actual_ranges != classification.analysis_scope.ranges:
        raise ValueError("Domain type table result uses different frame ranges.")
    if table_result.uses_tracking is not False:
        raise ValueError("Domain type export does not support tracking results.")


def _domain_type_rows(
    classification: M6DomainTypeClassificationResult,
) -> tuple[Mapping[str, object], ...]:
    qc = classification.qc_report
    reason_counts = dict(qc.unclassified_reason_counts)
    common = {
        "classification_observation_count": qc.observation_count,
        "classified_observation_count": qc.classified_observation_count,
        "unclassified_observation_count": qc.unclassified_observation_count,
        **{
            column: reason_counts[reason]
            for reason, column in _UNCLASSIFIED_REASON_COLUMNS.items()
        },
    }
    return tuple(
        {
            "domain_type_id": domain_type.domain_type_id,
            "domain_type_label": domain_type.label,
            "prototype_orientation_deg": domain_type.prototype_orientation_deg,
            "prototype_bond_length_nm": domain_type.prototype_bond_length_nm,
            "orientation_circular_spread_deg": (
                domain_type.orientation_circular_spread_deg
            ),
            "bond_length_iqr_nm": domain_type.bond_length_iqr_nm,
            "observation_count": domain_type.observation_count,
            **common,
        }
        for domain_type in classification.domain_types
    )


def _ordered_summaries(
    table_result: M6SingleRangeDomainTypeSummary | M6DomainTypeRangeComparison,
) -> tuple[tuple[_RangeOrder, M6SingleRangeDomainTypeSummary], ...]:
    if isinstance(table_result, M6SingleRangeDomainTypeSummary):
        return (("single", table_result),)
    return (
        ("first", table_result.first_summary),
        ("second", table_result.second_summary),
    )


def _range_rows(
    classification: M6DomainTypeClassificationResult,
    table_result: M6SingleRangeDomainTypeSummary | M6DomainTypeRangeComparison,
    summaries: tuple[tuple[_RangeOrder, M6SingleRangeDomainTypeSummary], ...],
) -> tuple[Mapping[str, object], ...]:
    rows = []
    for condition_order, summary in summaries:
        aggregates = _range_aggregates(
            classification,
            table_result,
            condition_order=condition_order,
            summary=summary,
        )
        frame_mapping = summary.frame_mapping
        available_mapping = tuple(
            value
            for value in frame_mapping
            if value.m6_availability_status == "available"
        )
        common = {
            "condition_order": condition_order,
            "range_name": summary.range_name,
            "range_start_working_frame_index": summary.frame_range.start_frame,
            "range_start_working_frame_number": summary.frame_range.start_frame + 1,
            "range_end_working_frame_index": summary.frame_range.end_frame,
            "range_end_working_frame_number": summary.frame_range.end_frame + 1,
            "working_frame_indices_json": _json_indices(
                value.working_frame_index for value in frame_mapping
            ),
            "source_frame_indices_json": _json_indices(
                value.source_frame_index for value in frame_mapping
            ),
            "available_working_frame_indices_json": _json_indices(
                value.working_frame_index for value in available_mapping
            ),
            "available_source_frame_indices_json": _json_indices(
                value.source_frame_index for value in available_mapping
            ),
            "source_view": summary.source_view,
            "component_scope": "full_domain",
            "analyzed_frame_count": summary.analyzed_frame_count,
            "available_frame_count": summary.available_frame_count,
            "valid_representative_fraction_frame_count": (
                summary.valid_representative_fraction_frame_count
            ),
            "valid_fov_fraction_frame_count": (
                summary.valid_fov_fraction_frame_count
            ),
            "frames_with_full_domain_count": summary.frames_with_full_domain_count,
            "frames_with_full_domain_percent": summary.frames_with_full_domain_percent,
            "mean_full_domains_per_available_frame": (
                summary.mean_full_domains_per_available_frame
            ),
            "median_full_domains_per_available_frame": (
                summary.median_full_domains_per_available_frame
            ),
            "max_full_domains_per_available_frame": (
                summary.max_full_domains_per_available_frame
            ),
            "domain_observation_count": summary.domain_observation_count,
            "domain_type_count": summary.domain_type_count,
            "unclassified_observation_count": (
                summary.unclassified_observation_count
            ),
            "full_domain_molecule_fraction": summary.full_domain_molecule_fraction,
            "full_domain_footprint_fraction": (
                summary.full_domain_footprint_fraction
            ),
        }
        for aggregate in aggregates:
            rows.append(
                {
                    **common,
                    "domain_type_id": aggregate.domain_type_id,
                    "domain_type_label": aggregate.label,
                    "classification_status": (
                        "unclassified"
                        if aggregate.domain_type_id is None
                        else "classified"
                    ),
                    **_aggregate_values(aggregate),
                    "frames_with_type_percent": _frames_with_type_percent(
                        aggregate
                    ),
                }
            )
    return tuple(rows)


def _range_aggregates(
    classification: M6DomainTypeClassificationResult,
    table_result: M6SingleRangeDomainTypeSummary | M6DomainTypeRangeComparison,
    *,
    condition_order: _RangeOrder,
    summary: M6SingleRangeDomainTypeSummary,
) -> tuple[M6DomainTypeRangeAggregate, ...]:
    if isinstance(table_result, M6SingleRangeDomainTypeSummary):
        present_by_id = {
            value.domain_type_id: value.range_aggregate
            for value in table_result.type_summaries
        }
        classified = tuple(
            present_by_id.get(
                domain_type.domain_type_id,
                _absent_range_aggregate(domain_type, summary),
            )
            for domain_type in classification.domain_types
        )
    elif condition_order in ("first", "second"):
        classified = tuple(
            (
                row.first.range_aggregate
                if condition_order == "first"
                else row.second.range_aggregate
            )
            for row in table_result.rows
        )
    else:
        raise ValueError("A comparison range must be first or second.")
    expected_ids = tuple(
        domain_type.domain_type_id for domain_type in classification.domain_types
    )
    if tuple(value.domain_type_id for value in classified) != expected_ids:
        raise ValueError("Range aggregates do not cover all classified type IDs.")
    return (*classified, summary.unclassified_aggregate)


def _absent_range_aggregate(
    domain_type: M6DomainType,
    summary: M6SingleRangeDomainTypeSummary,
) -> M6DomainTypeRangeAggregate:
    return M6DomainTypeRangeAggregate(
        domain_type_id=domain_type.domain_type_id,
        label=domain_type.label,
        available_frame_count=summary.available_frame_count,
        valid_representative_fraction_frame_count=(
            summary.valid_representative_fraction_frame_count
        ),
        valid_fov_fraction_frame_count=summary.valid_fov_fraction_frame_count,
        observation_count=0,
        frames_with_type_count=0,
        mean_instances_per_available_frame=(
            None if summary.available_frame_count == 0 else 0.0
        ),
        mean_molecule_fraction_of_valid_representatives=(
            None
            if summary.valid_representative_fraction_frame_count == 0
            else 0.0
        ),
        mean_footprint_fraction_of_valid_fov=(
            None if summary.valid_fov_fraction_frame_count == 0 else 0.0
        ),
        mean_domain_coherent_q6=None,
        mean_molecule_count=None,
        mean_footprint_area_nm2=None,
    )


def _aggregate_values(
    aggregate: M6DomainTypeRangeAggregate,
) -> dict[str, object]:
    return {
        "observation_count": aggregate.observation_count,
        "frames_with_type_count": aggregate.frames_with_type_count,
        "mean_instances_per_available_frame": (
            aggregate.mean_instances_per_available_frame
        ),
        "mean_molecule_fraction_of_valid_representatives": (
            aggregate.mean_molecule_fraction_of_valid_representatives
        ),
        "mean_footprint_fraction_of_valid_fov": (
            aggregate.mean_footprint_fraction_of_valid_fov
        ),
        "mean_domain_coherent_q6": aggregate.mean_domain_coherent_q6,
        "mean_molecule_count": aggregate.mean_molecule_count,
        "mean_footprint_area_nm2": aggregate.mean_footprint_area_nm2,
    }


def _frames_with_type_percent(
    aggregate: M6DomainTypeRangeAggregate,
) -> float | None:
    if aggregate.available_frame_count == 0:
        return None
    return 100.0 * aggregate.frames_with_type_count / aggregate.available_frame_count


def _comparison_rows(
    table_result: M6SingleRangeDomainTypeSummary | M6DomainTypeRangeComparison,
) -> tuple[Mapping[str, object], ...]:
    if isinstance(table_result, M6SingleRangeDomainTypeSummary):
        return ()
    return tuple(
        {
            "direction": table_result.direction,
            "domain_type_id": row.domain_type_id,
            "domain_type_label": row.label,
            "prototype_orientation_deg": row.prototype_orientation_deg,
            "prototype_bond_length_nm": row.prototype_bond_length_nm,
            "orientation_circular_spread_deg": row.orientation_circular_spread_deg,
            "bond_length_iqr_nm": row.bond_length_iqr_nm,
            "first_range_name": table_result.first_range_name,
            "second_range_name": table_result.second_range_name,
            **_comparison_side_values("first", row.first),
            **_comparison_side_values("second", row.second),
            "domain_instance_count_delta": row.deltas.domain_instance_count,
            "frames_with_type_count_delta": row.deltas.frames_with_type_count,
            "frames_with_type_percentage_points_delta": (
                row.deltas.frames_with_type_percentage_points
            ),
            "mean_domain_instances_per_available_frame_delta": (
                row.deltas.mean_domain_instances_per_available_frame
            ),
            "mean_molecule_fraction_percentage_points_delta": (
                row.deltas.mean_molecule_fraction_percentage_points
            ),
            "mean_footprint_fraction_percentage_points_delta": (
                row.deltas.mean_footprint_fraction_percentage_points
            ),
            "mean_domain_coherent_q6_delta": row.deltas.mean_domain_coherent_q6,
            "mean_molecule_count_delta": row.deltas.mean_molecule_count,
            "mean_footprint_area_nm2_delta": row.deltas.mean_footprint_area_nm2,
        }
        for row in table_result.rows
    )


def _comparison_side_values(
    prefix: str,
    side: M6DomainTypeRangeSide,
) -> dict[str, object]:
    aggregate = side.range_aggregate
    return {
        f"{prefix}_domain_instance_count": side.domain_instance_count,
        f"{prefix}_frames_with_type_count": side.frames_with_type_count,
        f"{prefix}_frames_with_type_percent": side.frames_with_type_percent,
        f"{prefix}_mean_domain_instances_per_available_frame": (
            side.mean_domain_instances_per_available_frame
        ),
        f"{prefix}_mean_molecule_fraction": side.mean_molecule_fraction,
        f"{prefix}_mean_footprint_fraction": side.mean_footprint_fraction,
        f"{prefix}_mean_domain_coherent_q6": side.mean_domain_coherent_q6,
        f"{prefix}_mean_molecule_count": side.mean_molecule_count,
        f"{prefix}_mean_footprint_area_nm2": side.mean_footprint_area_nm2,
        f"{prefix}_available_frame_count": aggregate.available_frame_count,
        f"{prefix}_valid_representative_fraction_frame_count": (
            aggregate.valid_representative_fraction_frame_count
        ),
        f"{prefix}_valid_fov_fraction_frame_count": (
            aggregate.valid_fov_fraction_frame_count
        ),
    }


def _classification_manifest(
    classification: M6DomainTypeClassificationResult,
    summaries: tuple[tuple[_RangeOrder, M6SingleRangeDomainTypeSummary], ...],
    *,
    tables_included: bool,
) -> Mapping[str, object]:
    qc = classification.qc_report
    return {
        "available": True,
        "reason": None,
        "algorithm": "deterministic_complete_linkage",
        "algorithm_version": M6_DOMAIN_TYPE_ALGORITHM_VERSION,
        "analysis_mode": classification.analysis_scope.analysis_mode,
        "classification_mode": classification.classification_mode,
        "uses_tracking": False,
        "component_scope": "full_domain",
        "classification_input_fingerprint": classification.input_fingerprint,
        "m6_context_fingerprint": classification.m6_context_fingerprint,
        "classification_settings": classification.classification_settings.to_dict(),
        "m6_orientation_settings": classification.m6_settings.to_dict(),
        "qc": {
            "observation_count": qc.observation_count,
            "classified_observation_count": qc.classified_observation_count,
            "unclassified_observation_count": qc.unclassified_observation_count,
            "unclassified_reason_counts": dict(qc.unclassified_reason_counts),
        },
        "ranges": [
            _range_manifest(condition_order, summary)
            for condition_order, summary in summaries
        ],
        "tables_included": bool(tables_included),
        "table_files": (
            list(DOMAIN_TYPE_TABLE_FILES)
            if tables_included
            else []
        ),
    }


def _empty_manifest(*, tables_included: bool) -> Mapping[str, object]:
    return {
        "available": False,
        "reason": "domain_type_classification_not_available",
        "algorithm": "deterministic_complete_linkage",
        "algorithm_version": M6_DOMAIN_TYPE_ALGORITHM_VERSION,
        "analysis_mode": None,
        "classification_mode": None,
        "uses_tracking": False,
        "component_scope": "full_domain",
        "classification_input_fingerprint": None,
        "m6_context_fingerprint": None,
        "classification_settings": None,
        "m6_orientation_settings": None,
        "qc": None,
        "ranges": [],
        "tables_included": bool(tables_included),
        "table_files": (
            list(DOMAIN_TYPE_TABLE_FILES)
            if tables_included
            else []
        ),
    }


def _range_manifest(
    condition_order: _RangeOrder,
    summary: M6SingleRangeDomainTypeSummary,
) -> Mapping[str, object]:
    available_mapping = tuple(
        value
        for value in summary.frame_mapping
        if value.m6_availability_status == "available"
    )
    return {
        "condition_order": condition_order,
        "range_name": summary.range_name,
        "start_working_frame_index": summary.frame_range.start_frame,
        "end_working_frame_index": summary.frame_range.end_frame,
        "working_frame_indices": [
            value.working_frame_index for value in summary.frame_mapping
        ],
        "source_frame_indices": [
            value.source_frame_index for value in summary.frame_mapping
        ],
        "available_working_frame_indices": [
            value.working_frame_index for value in available_mapping
        ],
        "available_source_frame_indices": [
            value.source_frame_index for value in available_mapping
        ],
        "analyzed_frame_count": summary.analyzed_frame_count,
        "available_frame_count": summary.available_frame_count,
        "valid_representative_fraction_frame_count": (
            summary.valid_representative_fraction_frame_count
        ),
        "valid_fov_fraction_frame_count": summary.valid_fov_fraction_frame_count,
    }


def _json_indices(values: Iterable[int]) -> str:
    return json.dumps([int(value) for value in values], separators=(",", ":"))


def _write_csv(
    path: Path,
    rows: tuple[Mapping[str, object], ...],
    fieldnames: tuple[str, ...],
) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
