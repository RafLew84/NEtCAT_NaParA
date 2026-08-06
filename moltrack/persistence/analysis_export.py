from __future__ import annotations

import csv
import json
import os
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from math import isclose
from pathlib import Path
from collections.abc import Callable, Mapping, Sequence
from typing import TYPE_CHECKING

import numpy as np

from moltrack import __version__ as moltrack_version
from moltrack.analysis._m6_context_fingerprint import m6_context_fingerprint
from moltrack.analysis._m6_settings_fingerprint import m6_settings_fingerprint
from moltrack.analysis import (
    LOCAL_MULTI_SYMMETRY_BOND_ORDER_SCHEMA_VERSION,
    LOCAL_SYMMETRY_EVIDENCE_ALGORITHM_VERSION,
    LOCAL_SYMMETRY_EVIDENCE_SCHEMA_VERSION,
    M6DomainTypeAssignment,
    M6DomainTypeClassificationResult,
    M6DomainTypeObservation,
    M6DomainTypeRangeComparison,
    M6SingleRangeDomainTypeSummary,
    M6_ORIENTATION_ALGORITHM_VERSION,
    SAMPLE_COORDINATE_TRANSFORM_VERSION,
    StructuralAnalysisCacheKey,
    MolecularFrameAnalysisResult,
    MolecularFrameRange,
    MolecularFrameRangeAnalysis,
    MolecularFrameRangeComparison,
    MolecularFrameRangeSelection,
    MolecularIntensityMeasurement,
    MolecularM6OrientationAnalysisSettings,
    MolecularOrientationStore,
    MolecularPositionPlotData,
    MolecularRangeSpatialComparisonData,
    MolecularStackingSessionState,
    analyze_molecular_frame_range,
    build_molecular_range_spatial_comparison_data,
    build_m6_domain_type_range_comparison,
    build_structural_analysis_cache_key,
    compare_molecular_frame_ranges,
    extract_m6_domain_type_observations,
)
from moltrack.core import MolTrackImageSeries, MolecularCentroid, build_molecular_centroids

from .analysis_environment import (
    resolve_analysis_export_environment,
)
from .m6_domain_type_export import (
    build_m6_domain_type_export_data,
    write_m6_domain_type_tables,
)
from .molecular_stacking_export import (
    build_molecular_stacking_export_data,
    write_molecular_stacking_tables,
)
from .package_io import file_sha256 as _sha256_file

if TYPE_CHECKING:
    from .analysis_plots import AnalysisPlotExportResult


ANALYSIS_EXPORT_SCHEMA_VERSION = 8


_MOLECULES_CSV_FIELDS = (
    "working_frame_index",
    "working_frame_number",
    "source_frame_index",
    "source_frame_number",
    "time_s",
    "source_view",
    "source_kind",
    "source_id",
    "origin",
    "position_x",
    "position_y",
    "position_unit",
    "x_px",
    "y_px",
    "x_nm",
    "y_nm",
    "molecular_orientation_status",
    "molecular_orientation_angle_deg",
    "molecular_orientation_periodicity_deg",
    "molecular_orientation_confidence",
    "molecular_orientation_method",
    "molecular_orientation_manual_corrected",
    "molecular_orientation_reviewer",
    "molecular_orientation_note",
    "molecular_orientation_automatic_status",
    "molecular_orientation_automatic_angle_deg",
    "molecular_orientation_automatic_confidence",
    "molecular_orientation_automatic_method",
    "molecular_orientation_reference",
)

_M6_MOLECULES_CSV_FIELDS = (
    "neighbor_count",
    "psi3_real",
    "psi3_imag",
    "q3",
    "m3_lattice_orientation_deg",
    "m3_orientation_status",
    "m3_orientation_confidence",
    "m3_sublattice_phase",
    "m3_sublattice_phase_status",
    "m3_phase_gauge_anchor",
    "m3_qualified_trifold",
    "m3_sublattice_assignment_ambiguous",
    "m3_gauge_inconsistent_cycle",
    "m3_gauge_frustration_qc",
    "symmetry_resolvability_status",
    "edge_truncated_neighborhood",
    "psi6_real",
    "psi6_imag",
    "q6",
    "lattice_orientation_deg",
    "orientation_status",
    "m6_orientation_confidence",
    "trifold_model_score",
    "sixfold_model_score",
    "mixed_model_score",
    "disordered_model_score",
    "symmetry_best_model",
    "symmetry_second_best_margin",
    "symmetry_observed_direction_count",
    "symmetry_expected_direction_coverage",
    "symmetry_classification_confidence",
    "symmetry_classification_reason",
    "ordered_component_id",
    "m6_orientation_domain_id",
    "component_type",
    "order_qc",
    "local_median_bond_length_nm",
    "local_bond_length_mad_nm",
    "local_bond_length_iqr_nm",
    "local_bond_length_robust_cv",
    "representative_source_id",
    "duplicate_parent_component_id",
    "duplicate_parent_component_diameter_nm",
    "duplicate_group_id",
    "duplicate_group_diameter_nm",
    "duplicate_chain_qc",
    "physical_duplicate_qc",
    "geometry_duplicate_qc",
    "coordinate_frame",
    "orientation_reference",
    "lattice_domain_id",
    "lattice_point_role",
    "lattice_boundary_reason",
    "lattice_domain_dominant_symmetry",
    "lattice_domain_confidence",
)

_FULL_MOLECULES_CSV_FIELDS = _MOLECULES_CSV_FIELDS + (
    "detection_id",
    "segmentation_id",
    "area_px",
    "bbox_x1",
    "bbox_y1",
    "bbox_x2",
    "bbox_y2",
    "confidence",
    "nearest_neighbor_distance",
    "nearest_neighbor_distance_unit",
    "nearest_neighbor_angle_deg",
    "intensity_pixel_count",
    "intensity_unit",
    "intensity_sum",
    "intensity_mean",
    "intensity_median",
    "intensity_max",
    "local_background_median",
    "background_corrected_mean",
    "background_corrected_median",
) + _M6_MOLECULES_CSV_FIELDS

_FRAMES_CSV_FIELDS = (
    "working_frame_index",
    "working_frame_number",
    "source_frame_index",
    "source_frame_number",
    "time_s",
    "source_view",
    "molecule_count",
    "nearest_neighbor_distance_unit",
    "mean_nearest_neighbor_distance",
    "median_nearest_neighbor_distance",
    "min_nearest_neighbor_distance",
    "max_nearest_neighbor_distance",
    "line_order_score",
    "intensity_metric",
    "intensity_unit",
    "mean_intensity",
    "median_intensity",
) + (
    "m6_analysis_availability_status",
    "m6_analysis_unavailability_reason",
    "full_domain_count",
    "small_ordered_island_count",
    "ordered_component_count",
    "original_observation_count",
    "valid_representative_count",
    "duplicate_excluded_count",
    "invalid_position_count",
    "valid_fov_area_nm2",
    "supported_area_nm2",
    "mean_local_q6_interior",
    "global_q6_interior",
    "mean_local_q6_all_valid",
    "global_q6_all_valid",
    "edge_truncated_fraction_of_valid_representatives",
    "full_domain_molecule_fraction",
    "small_island_molecule_fraction",
    "unassigned_molecule_fraction",
    "assigned_molecule_fraction",
    "largest_domain_molecule_fraction",
    "duplicate_excluded_fraction_of_original",
    "invalid_position_fraction_of_original",
    "full_domain_footprint_fraction",
    "small_island_footprint_fraction",
    "unassigned_supported_footprint_fraction",
    "unsupported_background_fraction",
    "assigned_footprint_fraction",
    "largest_domain_footprint_fraction",
    "footprint_overlap_error_nm2",
    "full_domain_molecule_weighted_coherent_q6",
    "full_domain_footprint_weighted_coherent_q6",
    "mean_full_domain_footprint_area_nm2",
    "median_full_domain_footprint_area_nm2",
    "domain_molecule_entropy",
    "domain_footprint_entropy",
    "construction_method",
    "footprint_construction_method",
    "geometry_collision_epsilon_nm",
    "delaunay_degeneracy_qc",
    "graph_qc_status",
    "coordinate_frame",
    "orientation_reference",
    "spatial_calibration_fingerprint",
    "registration_fingerprint",
    "point_coordinate_fingerprint",
    "pair_correlation_window_geometry_status",
    "non_positive_valid_fov_area_qc",
    "fewer_than_3_noncollinear_points_qc",
    "voronoi_degenerate_qc",
    "footprint_clipped_by_fov_qc",
    "footprint_disconnected_qc",
    "footprint_overlap_error_qc",
)

_DOMAINS_CSV_FIELDS = (
    "working_frame_index",
    "working_frame_number",
    "source_frame_index",
    "source_frame_number",
    "time_s",
    "source_view",
    "ordered_component_id",
    "m6_orientation_domain_id",
    "component_type",
    "molecule_count",
    "molecule_fraction_of_valid_representatives",
    "footprint_area_nm2",
    "footprint_fraction_of_valid_fov",
    "molecular_mask_area_nm2",
    "orientation_deg",
    "centroid_x_nm",
    "centroid_y_nm",
    "min_x_nm",
    "min_y_nm",
    "max_x_nm",
    "max_y_nm",
    "domain_mean_local_q6",
    "domain_coherent_q6",
    "internal_first_shell_bond_count",
    "domain_median_bond_length_nm",
    "domain_bond_length_mad_nm",
    "domain_bond_length_iqr_nm",
    "domain_bond_length_robust_cv",
    "edge_truncated",
    "insufficient_bonds_for_length_stats_qc",
    "bond_length_heterogeneity_qc",
    "footprint_disconnected_qc",
    "coordinate_frame",
    "orientation_reference",
    "m6_settings_fingerprint",
    "m6_context_fingerprint",
    "spatial_calibration_fingerprint",
    "registration_fingerprint",
    "point_coordinate_fingerprint",
    "domain_type_range_name",
    "domain_type_range_start_frame",
    "domain_type_range_end_frame",
    "domain_type_id",
    "domain_type_label",
    "domain_type_qualification_status",
    "domain_type_unclassified_reason",
)

_LATTICE_DOMAINS_CSV_FIELDS = (
    "working_frame_index",
    "working_frame_number",
    "source_frame_index",
    "source_frame_number",
    "time_s",
    "source_view",
    "lattice_domain_id",
    "source_component_id",
    "component_type",
    "dominant_symmetry",
    "molecule_count",
    "core_size",
    "halo_size",
    "molecule_fraction_of_valid_representatives",
    "adjacent_boundary_point_count",
    "adjacent_boundary_point_fraction",
    "theta3_lattice_prototype_deg",
    "theta6_prototype_deg",
    "theta3_lattice_spread_deg",
    "theta6_spread_deg",
    "orientation_reference_channel",
    "m3_m6_orientation_relation_status",
    "m3_m6_orientation_offset_deg",
    "confidence",
    "centroid_x_nm",
    "centroid_y_nm",
    "min_x_nm",
    "min_y_nm",
    "max_x_nm",
    "max_y_nm",
    "internal_first_shell_bond_count",
    "median_bond_length_nm",
    "bond_length_mad_nm",
    "bond_length_iqr_nm",
    "bond_length_robust_cv",
    "footprint_area_nm2",
    "footprint_fraction_of_valid_fov",
    "edge_truncated_neighborhood_qc",
    "graph_disconnected_qc",
    "insufficient_bonds_for_length_stats_qc",
    "bond_length_heterogeneity_qc",
    "footprint_unavailable_qc",
    "footprint_clipped_by_fov_qc",
    "symmetry_alias_unresolvable_from_centroids_qc",
    "coordinate_frame",
    "orientation_reference",
    "spatial_calibration_fingerprint",
    "registration_fingerprint",
    "point_coordinate_fingerprint",
    "first_shell_graph_fingerprint",
    "local_order_analysis_fingerprint",
    "local_symmetry_evidence_settings_fingerprint",
    "local_symmetry_bond_evidence_fingerprint",
    "seed_growth_settings_fingerprint",
    "seed_growth_result_fingerprint",
    "settings_fingerprint",
    "schema_version",
)

_DOMAIN_TYPE_CSV_FIELDS = (
    "domain_type_range_name",
    "domain_type_range_start_frame",
    "domain_type_range_end_frame",
    "domain_type_id",
    "domain_type_label",
    "domain_type_qualification_status",
    "domain_type_unclassified_reason",
)


@dataclass(frozen=True)
class _DomainComponentExportKey:
    source_view: str
    working_frame_index: int
    source_frame_index: int
    ordered_component_id: int
    m6_orientation_domain_id: int | None


@dataclass(frozen=True)
class _DomainTypeExportRecord:
    observation: M6DomainTypeObservation
    assignment: M6DomainTypeAssignment
    label: str


@dataclass(frozen=True)
class _DomainTypeExportLookup:
    source_view: str
    by_observation_key: Mapping[tuple[object, ...], _DomainTypeExportRecord]
    by_component_key: Mapping[
        _DomainComponentExportKey,
        tuple[_DomainTypeExportRecord, ...],
    ]


_M6_FRAMES_CSV_FIELDS = _FRAMES_CSV_FIELDS[
    _FRAMES_CSV_FIELDS.index("m6_analysis_availability_status") :
]

_RANGES_CSV_FIELDS = (
    "condition_order",
    "condition_name",
    "start_frame_index",
    "start_frame_number",
    "end_frame_index",
    "end_frame_number",
    "source_view",
    "analyzed_frame_count",
    "total_molecule_count",
    "mean_molecule_count",
    "nearest_neighbor_distance_unit",
    "mean_nearest_neighbor_distance",
    "mean_line_order_score",
    "intensity_metric",
    "intensity_unit",
    "mean_intensity",
    "median_intensity",
)

_COMPARISON_CSV_FIELDS = (
    "direction",
    "first_condition_name",
    "second_condition_name",
    "source_view",
    "analysis_mode",
    "uses_tracking",
    "nearest_neighbor_distance_unit",
    "intensity_metric",
    "intensity_unit",
    "mean_molecule_count_delta",
    "mean_nearest_neighbor_distance_delta",
    "mean_line_order_score_delta",
    "mean_intensity_delta",
    "median_intensity_delta",
)

_SPATIAL_BINS_CSV_FIELDS = (
    "condition_order",
    "condition_name",
    "row",
    "column",
    "x_min",
    "x_max",
    "y_min",
    "y_max",
    "position_unit",
    "molecules_per_frame",
    "density_unit",
    "intensity_metric",
    "intensity_unit",
    "mean_intensity",
)


def export_selected_ranges_analysis_csv(
    series: MolTrackImageSeries,
    selection: MolecularFrameRangeSelection,
    destination_dir: str | Path,
    *,
    use_segmentation_centroids: bool = True,
    intensity_metric: str = "background_corrected_median",
    intensity_unit: str = "a.u.",
    background_inner_radius_px: int = 1,
    background_outer_radius_px: int = 3,
    density_grid_shape: tuple[int, int] = (32, 32),
    include_plots: bool = False,
    plot_dpi: int = 150,
    plot_size_inches: tuple[float, float] = (8.0, 6.0),
    progress_callback=None,
    phase_callback=None,
    m6_orientation_settings: MolecularM6OrientationAnalysisSettings | None = None,
    m6_domain_type_classification: M6DomainTypeClassificationResult | None = None,
    m6_domain_type_table_result: (
        M6SingleRangeDomainTypeSummary | M6DomainTypeRangeComparison | None
    ) = None,
    molecular_stacking_state: MolecularStackingSessionState | None = None,
    environment_provider: Callable[[], Mapping[str, object]] | None = None,
) -> dict[str, Path]:
    """Analyze and export two named frame ranges without creating tracks."""

    if (
        m6_domain_type_table_result is not None
        and m6_domain_type_classification is None
    ):
        raise ValueError("A domain type table result requires a classification.")
    comparison = compare_molecular_frame_ranges(
        series,
        selection,
        use_segmentation_centroids=use_segmentation_centroids,
        intensity_metric=intensity_metric,
        intensity_unit=intensity_unit,
        background_inner_radius_px=background_inner_radius_px,
        background_outer_radius_px=background_outer_radius_px,
        progress_callback=progress_callback,
        m6_orientation_settings=m6_orientation_settings,
    )
    spatial_data = build_molecular_range_spatial_comparison_data(
        comparison,
        density_grid_shape=density_grid_shape,
    )
    if phase_callback is not None:
        phase_callback("writing_tables")
    molecule_rows = []
    frame_rows = []
    domain_rows = []
    lattice_domain_rows = []
    range_rows = []
    domain_type_lookup = _validated_domain_type_export_lookup(
        m6_domain_type_classification,
        (comparison.first_analysis, comparison.second_analysis),
    )
    effective_domain_type_classification = (
        m6_domain_type_classification
        if domain_type_lookup is not None
        else None
    )
    rebuilt_domain_type_table_result = (
        None
        if effective_domain_type_classification is None
        else build_m6_domain_type_range_comparison(
            effective_domain_type_classification,
            comparison.first_analysis,
            comparison.second_analysis,
        )
    )
    domain_type_table_result = (
        m6_domain_type_table_result
        if (
            m6_domain_type_table_result is not None
            and m6_domain_type_table_result == rebuilt_domain_type_table_result
        )
        else rebuilt_domain_type_table_result
    )
    domain_type_export = build_m6_domain_type_export_data(
        effective_domain_type_classification,
        domain_type_table_result,
        tables_included=True,
    )
    for condition_order, analysis in (
        ("first", comparison.first_analysis),
        ("second", comparison.second_analysis),
    ):
        condition_name = analysis.frame_range.name
        for frame_analysis in analysis.frame_results:
            analyzed_rows = _analyzed_molecule_rows(series, frame_analysis)
            for row in analyzed_rows:
                row["condition_name"] = condition_name
            molecule_rows.extend(analyzed_rows)
            frame_row = _frame_row(series, frame_analysis)
            frame_row["condition_name"] = condition_name
            frame_rows.append(frame_row)
            analyzed_domain_rows = _ordered_component_rows(series, frame_analysis)
            for row in analyzed_domain_rows:
                row["condition_order"] = condition_order
                row["condition_name"] = condition_name
            _apply_domain_type_export_fields(
                analyzed_domain_rows,
                domain_type_lookup,
                frame_range=analysis.frame_range,
            )
            domain_rows.extend(analyzed_domain_rows)
            analyzed_lattice_rows = _lattice_domain_rows(series, frame_analysis)
            for row in analyzed_lattice_rows:
                row["condition_order"] = condition_order
                row["condition_name"] = condition_name
            lattice_domain_rows.extend(analyzed_lattice_rows)
        range_rows.append(_range_row(condition_order, analysis))

    domain_rows.sort(key=_ordered_component_row_sort_key)
    lattice_domain_rows.sort(
        key=lambda row: (
            int(row["working_frame_index"]),
            str(row["lattice_domain_id"]),
        )
    )

    destination = Path(destination_dir)
    destination.mkdir(parents=True, exist_ok=True)
    molecules_path = destination / "molecules.csv"
    _write_csv(
        molecules_path,
        molecule_rows,
        fieldnames=("condition_name",) + _FULL_MOLECULES_CSV_FIELDS,
    )
    frames_path = destination / "frames.csv"
    _write_csv(
        frames_path,
        frame_rows,
        fieldnames=("condition_name",) + _FRAMES_CSV_FIELDS,
    )
    domains_path = destination / "domains.csv"
    _write_csv(
        domains_path,
        domain_rows,
        fieldnames=("condition_order", "condition_name") + _DOMAINS_CSV_FIELDS,
    )
    lattice_domains_path = destination / "lattice_domains.csv"
    _write_csv(
        lattice_domains_path,
        lattice_domain_rows,
        fieldnames=("condition_order", "condition_name")
        + _LATTICE_DOMAINS_CSV_FIELDS,
    )
    ranges_path = destination / "ranges.csv"
    _write_csv(ranges_path, range_rows, fieldnames=_RANGES_CSV_FIELDS)
    comparison_path = destination / "comparison.csv"
    _write_csv(
        comparison_path,
        [_comparison_row(comparison)],
        fieldnames=_COMPARISON_CSV_FIELDS,
    )
    spatial_bins_path = destination / "spatial_bins.csv"
    spatial_bin_rows = _spatial_bin_rows(spatial_data)
    _write_csv(
        spatial_bins_path,
        spatial_bin_rows,
        fieldnames=_SPATIAL_BINS_CSV_FIELDS,
    )
    domain_type_paths = write_m6_domain_type_tables(
        destination,
        domain_type_export,
    )
    stacking_export = build_molecular_stacking_export_data(
        series,
        molecular_stacking_state,
        frame_indices=tuple(
            sorted(
                {
                    *selection.first_range.frame_indices,
                    *selection.second_range.frame_indices,
                }
            )
        ),
        comparison_ranges=(
            selection.first_range,
            selection.second_range,
        ),
        expected_source_view=selection.source_view,
    )
    stacking_paths = write_molecular_stacking_tables(
        destination,
        stacking_export,
    )
    plots_dir = None
    plot_export = None
    if include_plots:
        if phase_callback is not None:
            phase_callback("rendering_plots")
        from .analysis_plots import export_selected_range_analysis_plots

        plots_dir = destination / "plots"
        current_analysis = _current_frame_analysis(
            series,
            comparison,
            use_segmentation_centroids=use_segmentation_centroids,
            intensity_metric=intensity_metric,
            intensity_unit=intensity_unit,
            background_inner_radius_px=background_inner_radius_px,
            background_outer_radius_px=background_outer_radius_px,
        )
        plot_export = export_selected_range_analysis_plots(
            current_analysis,
            comparison,
            spatial_data,
            plots_dir,
            dpi=plot_dpi,
            size_inches=plot_size_inches,
            m6_domain_type_classification=(
                effective_domain_type_classification
            ),
            m6_domain_type_table_result=domain_type_table_result,
        )
    file_entries = [
        {"path": molecules_path.name, "record_count": len(molecule_rows)},
        {"path": frames_path.name, "record_count": len(frame_rows)},
        {"path": domains_path.name, "record_count": len(domain_rows)},
        {
            "path": lattice_domains_path.name,
            "record_count": len(lattice_domain_rows),
        },
        {"path": ranges_path.name, "record_count": len(range_rows)},
        {"path": comparison_path.name, "record_count": 1},
        {
            "path": spatial_bins_path.name,
            "record_count": len(spatial_bin_rows),
        },
        {
            "path": domain_type_paths["domain_types_csv"].name,
            "record_count": len(domain_type_export.domain_type_rows),
        },
        {
            "path": domain_type_paths["domain_type_ranges_csv"].name,
            "record_count": len(domain_type_export.range_rows),
        },
        {
            "path": domain_type_paths["domain_type_comparison_csv"].name,
            "record_count": len(domain_type_export.comparison_rows),
        },
    ]
    if stacking_export.available:
        file_entries.extend(
            (
                {
                    "path": stacking_paths["stacking_molecules_csv"].name,
                    "record_count": len(stacking_export.molecule_rows),
                },
                {
                    "path": stacking_paths["stacking_domains_csv"].name,
                    "record_count": len(stacking_export.domain_rows),
                },
                {
                    "path": stacking_paths["stacking_subdomains_csv"].name,
                    "record_count": len(stacking_export.subdomain_rows),
                },
            )
        )
    if plot_export is not None:
        file_entries.extend(_plot_file_entries(plot_export, destination))
    manifest_path = destination / "manifest.json"
    _write_json(
        manifest_path,
        {
            "export_schema_version": ANALYSIS_EXPORT_SCHEMA_VERSION,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "application": {"name": "MolTrack", "version": moltrack_version},
            "environment": resolve_analysis_export_environment(environment_provider),
            "source": _source_manifest(series, destination),
            "stm_metadata": _stm_metadata_manifest(series),
            "working_series": {
                "frame_count": series.frame_count,
                "source_frame_indices": list(series.source_frame_indices),
                "reverse_frame_order": series.reverse_frame_order,
            },
            "ranges": _ranges_manifest(selection),
            "analysis": {
                **_analysis_manifest(
                    series,
                    comparison,
                    spatial_data,
                    use_segmentation_centroids=use_segmentation_centroids,
                    background_inner_radius_px=background_inner_radius_px,
                    background_outer_radius_px=background_outer_radius_px,
                    m6_orientation_settings=m6_orientation_settings,
                ),
                "m6_domain_types": dict(domain_type_export.manifest),
                "molecular_stacking": dict(stacking_export.manifest),
            },
            "registration": _registration_manifest(series),
            "plots": build_analysis_plots_manifest(plot_export, destination),
            "files": file_entries,
        },
    )
    paths = {
        "molecules_csv": molecules_path,
        "frames_csv": frames_path,
        "domains_csv": domains_path,
        "lattice_domains_csv": lattice_domains_path,
        "ranges_csv": ranges_path,
        "comparison_csv": comparison_path,
        "spatial_bins_csv": spatial_bins_path,
        **domain_type_paths,
        **stacking_paths,
        "manifest_json": manifest_path,
    }
    if plots_dir is not None:
        paths["plots_dir"] = plots_dir
    return paths


def _current_frame_analysis(
    series: MolTrackImageSeries,
    comparison: MolecularFrameRangeComparison,
    *,
    use_segmentation_centroids: bool,
    intensity_metric: str,
    intensity_unit: str,
    background_inner_radius_px: int,
    background_outer_radius_px: int,
) -> MolecularFrameAnalysisResult:
    for analysis in (comparison.first_analysis, comparison.second_analysis):
        for frame_analysis in analysis.frame_results:
            if frame_analysis.frame_index == series.active_frame_index:
                return frame_analysis
    return analyze_molecular_frame_range(
        series,
        MolecularFrameRange(
            "Current frame",
            series.active_frame_index,
            series.active_frame_index,
        ),
        source_view=comparison.source_view,
        use_segmentation_centroids=use_segmentation_centroids,
        intensity_metric=intensity_metric,
        intensity_unit=intensity_unit,
        background_inner_radius_px=background_inner_radius_px,
        background_outer_radius_px=background_outer_radius_px,
    ).frame_results[0]


def build_analysis_plots_manifest(
    plot_export: AnalysisPlotExportResult | None,
    destination: Path,
) -> dict[str, object]:
    if plot_export is None:
        return {
            "included": False,
            "formats": [],
            "png_dpi": None,
            "size_inches": None,
            "generated": [],
            "skipped": [],
        }
    width, height = plot_export.size_inches
    return {
        "included": True,
        "formats": ["svg", "png"],
        "png_dpi": plot_export.dpi,
        "size_inches": {"width": width, "height": height},
        "generated": [
            {
                "kind": kind,
                "files": [
                    path.relative_to(destination).as_posix() for path in paths
                ],
            }
            for kind, paths in plot_export.generated
        ],
        "skipped": [
            {"kind": kind, "reason": reason}
            for kind, reason in plot_export.skipped
        ],
    }


def _plot_file_entries(
    plot_export: AnalysisPlotExportResult,
    destination: Path,
) -> list[dict[str, object]]:
    return [
        {
            "path": path.relative_to(destination).as_posix(),
            "record_count": None,
        }
        for _kind, paths in plot_export.generated
        for path in paths
    ]


def _range_row(
    condition_order: str,
    analysis: MolecularFrameRangeAnalysis,
) -> dict[str, object]:
    frame_range = analysis.frame_range
    aggregates = analysis.aggregates
    return {
        "condition_order": condition_order,
        "condition_name": frame_range.name,
        "start_frame_index": frame_range.start_frame,
        "start_frame_number": frame_range.start_frame + 1,
        "end_frame_index": frame_range.end_frame,
        "end_frame_number": frame_range.end_frame + 1,
        "source_view": analysis.source_view,
        "analyzed_frame_count": aggregates.analyzed_frame_count,
        "total_molecule_count": aggregates.total_molecule_count,
        "mean_molecule_count": aggregates.mean_molecule_count,
        "nearest_neighbor_distance_unit": aggregates.distance_unit,
        "mean_nearest_neighbor_distance": aggregates.mean_nearest_neighbor_distance,
        "mean_line_order_score": aggregates.mean_line_order_score,
        "intensity_metric": analysis.intensity_metric,
        "intensity_unit": analysis.intensity_unit,
        "mean_intensity": aggregates.mean_intensity,
        "median_intensity": aggregates.median_intensity,
    }


def _comparison_row(
    comparison: MolecularFrameRangeComparison,
) -> dict[str, object]:
    first_analysis = comparison.first_analysis
    second_analysis = comparison.second_analysis
    differences = comparison.differences
    return {
        "direction": differences.direction,
        "first_condition_name": first_analysis.frame_range.name,
        "second_condition_name": second_analysis.frame_range.name,
        "source_view": comparison.source_view,
        "analysis_mode": comparison.analysis_mode,
        "uses_tracking": str(comparison.uses_tracking).lower(),
        "nearest_neighbor_distance_unit": differences.distance_unit,
        "intensity_metric": first_analysis.intensity_metric,
        "intensity_unit": first_analysis.intensity_unit,
        "mean_molecule_count_delta": differences.mean_molecule_count_delta,
        "mean_nearest_neighbor_distance_delta": (
            differences.mean_nearest_neighbor_distance_delta
        ),
        "mean_line_order_score_delta": differences.mean_line_order_score_delta,
        "mean_intensity_delta": differences.mean_intensity_delta,
        "median_intensity_delta": differences.median_intensity_delta,
    }


def _spatial_bin_rows(
    spatial_data: MolecularRangeSpatialComparisonData,
) -> list[dict[str, object]]:
    rows = []
    for condition_order, condition in (
        ("first", spatial_data.first),
        ("second", spatial_data.second),
    ):
        for row_index, (density_row, intensity_row) in enumerate(
            zip(condition.density_grid, condition.intensity_grid)
        ):
            for column_index, (density, intensity) in enumerate(
                zip(density_row, intensity_row)
            ):
                rows.append(
                    {
                        "condition_order": condition_order,
                        "condition_name": condition.condition_name,
                        "row": row_index,
                        "column": column_index,
                        "x_min": spatial_data.density_x_edges[column_index],
                        "x_max": spatial_data.density_x_edges[column_index + 1],
                        "y_min": spatial_data.density_y_edges[row_index],
                        "y_max": spatial_data.density_y_edges[row_index + 1],
                        "position_unit": spatial_data.unit,
                        "molecules_per_frame": density,
                        "density_unit": spatial_data.density_unit,
                        "intensity_metric": spatial_data.intensity_metric,
                        "intensity_unit": spatial_data.intensity_unit,
                        "mean_intensity": (
                            float(intensity) if np.isfinite(intensity) else None
                        ),
                    }
                )
    return rows


def _source_manifest(
    series: MolTrackImageSeries,
    destination: Path,
) -> dict[str, object]:
    source_path = Path(series.source_path)
    resolved_source = source_path.resolve(strict=False)
    try:
        relative_path = Path(
            os.path.relpath(resolved_source, destination.resolve(strict=False))
        ).as_posix()
    except ValueError:
        relative_path = source_path.name

    size_bytes = None
    modified_time_ns = None
    integrity = None
    try:
        source_stat = resolved_source.stat()
        if resolved_source.is_file():
            size_bytes = int(source_stat.st_size)
            modified_time_ns = int(source_stat.st_mtime_ns)
            integrity = {
                "algorithm": "sha256",
                "value": _sha256_file(resolved_source),
            }
    except OSError:
        pass
    return {
        "format": "MPP",
        "path": relative_path,
        "file_name": source_path.name,
        "size_bytes": size_bytes,
        "modified_time_ns": modified_time_ns,
        "integrity": integrity,
    }


def build_analysis_source_manifest(
    series: MolTrackImageSeries,
    destination: str | Path,
) -> dict[str, object]:
    """Build the portable source identity used by every analysis manifest."""

    return _source_manifest(series, Path(destination))


def _stm_metadata_manifest(series: MolTrackImageSeries) -> dict[str, object]:
    metadata = series.metadata
    pixel_size_x, pixel_size_y = series.pixel_size_nm
    frame_times = getattr(metadata, "frame_times_s", None)
    return {
        "pixels": {
            "x": int(getattr(metadata, "pixels_x", series.frame_shape[1])),
            "y": int(getattr(metadata, "pixels_y", series.frame_shape[0])),
        },
        "size_nm": {
            "x": _optional_finite_float(getattr(metadata, "size_nm_x", None)),
            "y": _optional_finite_float(getattr(metadata, "size_nm_y", None)),
        },
        "pixel_size_nm": {
            "x": _optional_finite_float(pixel_size_x),
            "y": _optional_finite_float(pixel_size_y),
        },
        "offset_nm": {
            "x": _optional_finite_float(getattr(metadata, "offset_nm_x", None)),
            "y": _optional_finite_float(getattr(metadata, "offset_nm_y", None)),
        },
        "scan_angle_deg": _optional_finite_float(
            getattr(metadata, "scan_angle_deg", None)
        ),
        "bias_v": _optional_finite_float(getattr(metadata, "bias_v", None)),
        "setpoint_a": _optional_finite_float(getattr(metadata, "setpoint_a", None)),
        "image_type": str(getattr(metadata, "image_type", "Unknown")),
        "frame_interval_s": _optional_finite_float(
            getattr(metadata, "frame_interval_s", None)
        ),
        "frame_times_s": (
            None
            if frame_times is None
            else [
                _optional_finite_float(value)
                for value in np.asarray(frame_times).reshape(-1)
            ]
        ),
    }


def _optional_finite_float(value: object | None) -> float | None:
    if value is None:
        return None
    numeric = float(value)
    return numeric if np.isfinite(numeric) else None


def _ranges_manifest(
    selection: MolecularFrameRangeSelection,
) -> list[dict[str, object]]:
    rows = []
    for condition_order, frame_range in (
        ("first", selection.first_range),
        ("second", selection.second_range),
    ):
        rows.append(
            {
                "condition_order": condition_order,
                "condition_name": frame_range.name,
                "start_frame_index": frame_range.start_frame,
                "start_frame_number": frame_range.start_frame + 1,
                "end_frame_index": frame_range.end_frame,
                "end_frame_number": frame_range.end_frame + 1,
            }
        )
    return rows


def _analysis_manifest(
    series: MolTrackImageSeries,
    comparison: MolecularFrameRangeComparison,
    spatial_data: MolecularRangeSpatialComparisonData,
    *,
    use_segmentation_centroids: bool,
    background_inner_radius_px: int,
    background_outer_radius_px: int,
    m6_orientation_settings: MolecularM6OrientationAnalysisSettings | None,
) -> dict[str, object]:
    frame_results = tuple(comparison.first_analysis.frame_results) + tuple(
        comparison.second_analysis.frame_results
    )
    return {
        "analysis_mode": comparison.analysis_mode,
        "uses_tracking": comparison.uses_tracking,
        "source_view": comparison.source_view,
        "analysis_coordinate_context": _analysis_coordinate_context(
            comparison.source_view
        ),
        "centroid_mode": (
            "segmentation_centroids_with_bbox_center_fallback"
            if use_segmentation_centroids
            else "bbox_centers"
        ),
        "density_grid_shape": {
            "rows": len(spatial_data.density_y_edges) - 1,
            "columns": len(spatial_data.density_x_edges) - 1,
        },
        "intensity": {
            "metric": spatial_data.intensity_metric,
            "unit": spatial_data.intensity_unit,
            "background_inner_radius_px": int(background_inner_radius_px),
            "background_outer_radius_px": int(background_outer_radius_px),
        },
        "coordinate_system": _coordinate_system_manifest(
            series,
            spatial_data,
            source_view=comparison.source_view,
        ),
        "m6_orientation": build_m6_analysis_manifest(
            series,
            frame_results,
            requested_settings=m6_orientation_settings,
            use_segmentation_centroids=use_segmentation_centroids,
            source_view=comparison.source_view,
        ),
    }


def build_m6_analysis_manifest(
    series: MolTrackImageSeries,
    frame_results: Sequence[MolecularFrameAnalysisResult],
    *,
    requested_settings: MolecularM6OrientationAnalysisSettings | None,
    use_segmentation_centroids: bool,
    source_view: str,
) -> dict[str, object]:
    """Build one reproducible M6 manifest without globalizing frame fallbacks."""

    if requested_settings is not None and not isinstance(
        requested_settings,
        MolecularM6OrientationAnalysisSettings,
    ):
        raise TypeError("requested_settings must be M6 settings or None.")
    results = tuple(frame_results)
    orientation_references = sorted(
        {
            result.m6_orientation_analysis.orientation_reference
            for result in results
            if result.m6_orientation_analysis is not None
        }
    )
    frame_entries = []
    for result in results:
        m6 = result.m6_orientation_analysis
        graph = None if m6 is None else m6.first_shell_graph
        multisymmetry = None if m6 is None else m6.local_multisymmetry_order
        evidence = None if m6 is None else m6.local_symmetry_evidence
        cache_key = (
            None
            if m6 is None
            else build_structural_analysis_cache_key(
                series,
                m6.sample_coordinates,
                use_segmentation_centroids=use_segmentation_centroids,
                settings=m6.settings,
            )
        )
        frame_entries.append(
            {
                "working_frame_index": result.frame_index,
                "source_frame_index": result.source_frame_index,
                "availability_status": result.m6_orientation_availability_status,
                "unavailability_reason": result.m6_orientation_unavailability_reason,
                "construction_method": None if graph is None else graph.construction_method,
                "cache_fingerprints": {
                    "coordinate_transform": (
                        None if m6 is None else m6.coordinate_transform_fingerprint
                    ),
                    "spatial_calibration": (
                        None if graph is None else graph.spatial_calibration_fingerprint
                    ),
                    "registration": (
                        None if graph is None else graph.registration_fingerprint
                    ),
                    "point_coordinates": (
                        None if graph is None else graph.point_coordinate_fingerprint
                    ),
                    "settings": (
                        None if cache_key is None else cache_key.settings_hash
                    ),
                    "annotations": (
                        None if cache_key is None else cache_key.annotation_fingerprint
                    ),
                    "sample_geometry": (
                        None if cache_key is None else cache_key.sample_geometry_fingerprint
                    ),
                    "valid_fov": (
                        None if cache_key is None else cache_key.valid_fov_fingerprint
                    ),
                    "multisymmetry_settings": (
                        None
                        if multisymmetry is None
                        else multisymmetry.provenance.analysis_settings_fingerprint
                    ),
                    "qualified_trifold_subgraph": (
                        None
                        if multisymmetry is None
                        else multisymmetry.provenance.qualified_trifold_subgraph_fingerprint
                    ),
                    "m3_phase_assignment": (
                        None
                        if multisymmetry is None
                        else multisymmetry.provenance.m3_phase_assignment_fingerprint
                    ),
                    "symmetry_evidence_settings": (
                        None if evidence is None else evidence.settings_fingerprint
                    ),
                    "symmetry_bond_evidence": (
                        None if evidence is None else evidence.bond_evidence_fingerprint
                    ),
                },
                "cache_key": _structural_cache_key_manifest(cache_key),
            }
        )
    settings_payload = (
        None if requested_settings is None else requested_settings.to_dict()
    )
    multisymmetry_analyses = tuple(
        result.m6_orientation_analysis
        for result in results
        if result.m6_orientation_analysis is not None
        and result.m6_orientation_analysis.local_multisymmetry_order is not None
        and result.m6_orientation_analysis.local_symmetry_evidence is not None
        and result.m6_orientation_analysis.local_symmetry_evidence_settings is not None
    )
    evidence_settings = (
        None
        if not multisymmetry_analyses
        else multisymmetry_analyses[0].local_symmetry_evidence_settings
    )
    evidence_settings_fingerprints = []
    for analysis in multisymmetry_analyses:
        evidence = analysis.local_symmetry_evidence
        if evidence is not None:
            evidence_settings_fingerprints.append(evidence.settings_fingerprint)
    evidence_settings_fingerprints = sorted(set(evidence_settings_fingerprints))
    return {
        "enabled": requested_settings is not None,
        "algorithm_version": M6_ORIENTATION_ALGORITHM_VERSION,
        "settings": settings_payload,
        "symmetry_m": (
            None if requested_settings is None else requested_settings.symmetry_m
        ),
        "bond_weighting": (
            None if requested_settings is None else requested_settings.bond_weighting
        ),
        "local_multisymmetry": {
            "enabled": bool(multisymmetry_analyses),
            "symmetry_channels": [3, 6],
            "bond_order_schema_version": (
                LOCAL_MULTI_SYMMETRY_BOND_ORDER_SCHEMA_VERSION
            ),
            "evidence_algorithm_version": (
                LOCAL_SYMMETRY_EVIDENCE_ALGORITHM_VERSION
            ),
            "evidence_schema_version": LOCAL_SYMMETRY_EVIDENCE_SCHEMA_VERSION,
            "evidence_settings": (
                None if evidence_settings is None else evidence_settings.to_dict()
            ),
            "evidence_settings_fingerprints": evidence_settings_fingerprints,
        },
        "duplicate_policy": (
            None
            if requested_settings is None
            else {
                "enabled": requested_settings.duplicate_detection_enabled,
                "max_distance_nm": requested_settings.duplicate_max_distance_nm,
                "representative": requested_settings.duplicate_policy,
                "chain": requested_settings.duplicate_chain_policy,
                "geometry_collision": requested_settings.geometry_collision_policy,
                "geometry_absolute_tolerance_nm": (
                    requested_settings.geometry_absolute_tolerance_nm
                ),
                "geometry_relative_tolerance": (
                    requested_settings.geometry_relative_tolerance
                ),
            }
        ),
        "delaunay_policy": (
            None
            if requested_settings is None
            else {"degeneracy": requested_settings.delaunay_degeneracy_policy}
        ),
        "pair_correlation": (
            None
            if requested_settings is None
            else {
                "bin_width_nm": requested_settings.gr_bin_width_nm,
                "max_nm": requested_settings.gr_max_nm,
                "min_expected_pair_exposure": (
                    requested_settings.gr_min_expected_pair_exposure
                ),
                "min_contributing_frames": (
                    requested_settings.gr_min_contributing_frames
                ),
                "smoothing_method": requested_settings.gr_smoothing_method,
                "smoothing_width": requested_settings.gr_smoothing_width,
                "peak_prominence": requested_settings.gr_peak_prominence,
            }
        ),
        "coordinate_convention": {
            "coordinate_frame": "sample_nm" if requested_settings is not None else None,
            "analysis_coordinate_context": _analysis_coordinate_context(source_view),
            "orientation_references": orientation_references,
            "coordinate_transform_version": SAMPLE_COORDINATE_TRANSFORM_VERSION,
        },
        "frame_results": frame_entries,
    }


def _structural_cache_key_manifest(
    cache_key: StructuralAnalysisCacheKey | None,
) -> dict[str, object] | None:
    if cache_key is None:
        return None
    return {
        "frame_id": cache_key.frame_id,
        "source_view": cache_key.source_view,
        "centroid_mode": cache_key.centroid_mode,
        "annotation_fingerprint": cache_key.annotation_fingerprint,
        "registration_fingerprint": cache_key.registration_fingerprint,
        "spatial_calibration_fingerprint": cache_key.spatial_calibration_fingerprint,
        "coordinate_transform_fingerprint": cache_key.coordinate_transform_fingerprint,
        "sample_geometry_fingerprint": cache_key.sample_geometry_fingerprint,
        "valid_fov_fingerprint": cache_key.valid_fov_fingerprint,
        "settings_hash": cache_key.settings_hash,
        "algorithm_version": cache_key.algorithm_version,
    }


def _analysis_coordinate_context(source_view: str) -> str:
    return "registered" if source_view == "expanded_aligned" else "native"


def _coordinate_system_manifest(
    series: MolTrackImageSeries,
    spatial_data: MolecularRangeSpatialComparisonData,
    *,
    source_view: str,
) -> dict[str, object]:
    stack = series.expanded_aligned_stack if source_view == "expanded_aligned" else None
    if stack is None:
        return {
            "convention": "image_xy_x_right_y_down",
            "origin": "raw_frame_top_left",
            "position_unit": spatial_data.unit,
            "expanded_canvas_offset_px": None,
            "padding_ltrb": None,
            "frame_origins_xy": None,
        }
    padding = tuple(int(value) for value in getattr(stack, "padding_ltrb", (0, 0, 0, 0)))
    canvas_offset = getattr(stack, "canvas_offset_xy", (padding[0], padding[1]))
    frame_origins = np.asarray(getattr(stack, "frame_origins_xy", ()), dtype=np.float64)
    return {
        "convention": "image_xy_x_right_y_down",
        "origin": "reference_raw_frame_top_left",
        "position_unit": spatial_data.unit,
        "expanded_canvas_offset_px": {
            "x": float(canvas_offset[0]),
            "y": float(canvas_offset[1]),
        },
        "padding_ltrb": list(padding),
        "frame_origins_xy": [
            [float(origin[0]), float(origin[1])] for origin in frame_origins
        ],
    }


def _registration_manifest(series: MolTrackImageSeries) -> dict[str, object]:
    results = series.registration_results
    if results is None:
        return {
            "available": False,
            "backend": None,
            "reference_strategy": None,
            "registration_view": None,
            "backend_params": None,
            "reference_frame_index": None,
        }
    settings = results.settings
    return {
        "available": True,
        "backend": settings.backend,
        "reference_strategy": settings.reference_strategy,
        "registration_view": settings.registration_view,
        "backend_params": _json_compatible(settings.backend_params),
        "reference_frame_index": results.reference_frame_index,
    }


def _json_compatible(value: object) -> object:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if np.isfinite(value) else None
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, np.ndarray):
        return _json_compatible(value.tolist())
    if isinstance(value, np.generic):
        return _json_compatible(value.item())
    if isinstance(value, dict):
        return {str(key): _json_compatible(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_compatible(item) for item in value]
    return str(value)


def export_full_working_series_analysis_csv(
    series: MolTrackImageSeries,
    destination_dir: str | Path,
    *,
    source_view: str = "raw",
    use_segmentation_centroids: bool = True,
    intensity_metric: str = "background_corrected_median",
    intensity_unit: str = "a.u.",
    background_inner_radius_px: int = 1,
    background_outer_radius_px: int = 3,
    progress_callback=None,
    phase_callback=None,
    m6_orientation_settings: MolecularM6OrientationAnalysisSettings | None = None,
    m6_domain_type_classification: M6DomainTypeClassificationResult | None = None,
    analysis_results_callback: Callable[
        [tuple[MolecularFrameAnalysisResult, ...]], None
    ]
    | None = None,
) -> dict[str, Path]:
    """Analyze and export every frame remaining in the working series."""

    if not isinstance(series, MolTrackImageSeries):
        raise TypeError("series must be a MolTrackImageSeries instance.")
    analysis = analyze_molecular_frame_range(
        series,
        MolecularFrameRange("Full working series", 0, series.frame_count - 1),
        source_view=source_view,
        use_segmentation_centroids=use_segmentation_centroids,
        intensity_metric=intensity_metric,
        intensity_unit=intensity_unit,
        background_inner_radius_px=background_inner_radius_px,
        background_outer_radius_px=background_outer_radius_px,
        progress_callback=progress_callback,
        m6_orientation_settings=m6_orientation_settings,
    )
    if analysis_results_callback is not None:
        analysis_results_callback(tuple(analysis.frame_results))
    molecule_rows = []
    frame_rows = []
    domain_rows = []
    lattice_domain_rows = []
    domain_type_lookup = _validated_domain_type_export_lookup(
        m6_domain_type_classification,
        _domain_type_range_slices(
            analysis,
            m6_domain_type_classification,
        ),
    )
    for frame_analysis in analysis.frame_results:
        molecule_rows.extend(_analyzed_molecule_rows(series, frame_analysis))
        frame_rows.append(_frame_row(series, frame_analysis))
        analyzed_domain_rows = _ordered_component_rows(series, frame_analysis)
        _apply_domain_type_export_fields(
            analyzed_domain_rows,
            domain_type_lookup,
        )
        domain_rows.extend(analyzed_domain_rows)
        lattice_domain_rows.extend(_lattice_domain_rows(series, frame_analysis))
    molecule_rows.sort(
        key=lambda row: (
            int(row["working_frame_index"]),
            str(row["source_kind"]),
            str(row["source_id"]),
        )
    )
    frame_rows.sort(key=lambda row: int(row["working_frame_index"]))
    domain_rows.sort(key=_ordered_component_row_sort_key)
    lattice_domain_rows.sort(
        key=lambda row: (
            int(row["working_frame_index"]),
            str(row["lattice_domain_id"]),
        )
    )
    if phase_callback is not None:
        phase_callback("writing_tables")
    return _write_analysis_tables(
        destination_dir,
        molecule_rows,
        frame_rows,
        domain_rows,
        lattice_domain_rows,
    )


def export_current_frame_analysis_csv(
    series: MolTrackImageSeries,
    frame_analysis: MolecularFrameAnalysisResult,
    destination_dir: str | Path,
    *,
    use_segmentation_centroids: bool = True,
    m6_domain_type_classification: M6DomainTypeClassificationResult | None = None,
) -> dict[str, Path]:
    """Export full per-molecule analysis for one working-series frame."""

    if not isinstance(frame_analysis, MolecularFrameAnalysisResult):
        raise TypeError("frame_analysis must be a MolecularFrameAnalysisResult instance.")
    rows = _analyzed_molecule_rows(series, frame_analysis)
    domain_rows = _ordered_component_rows(series, frame_analysis)
    lattice_domain_rows = _lattice_domain_rows(series, frame_analysis)
    _apply_domain_type_export_fields(
        domain_rows,
        _validated_domain_type_export_lookup(
            m6_domain_type_classification,
            _domain_type_range_analyses_from_series(
                series,
                m6_domain_type_classification,
                expected_source_view=frame_analysis.source_view,
                use_segmentation_centroids=use_segmentation_centroids,
            ),
        ),
    )
    return _write_analysis_tables(
        destination_dir,
        rows,
        [_frame_row(series, frame_analysis)],
        domain_rows,
        lattice_domain_rows,
    )


def _analyzed_molecule_rows(
    series: MolTrackImageSeries,
    frame_analysis: MolecularFrameAnalysisResult,
) -> list[dict[str, object]]:
    rows = _molecule_rows(series, frame_analysis.plot_data)
    distances = frame_analysis.distance_metrics.nearest_neighbor_distances
    angles = frame_analysis.angle_metrics.nearest_neighbor_angles_degrees
    point_index_by_source = {
        (source_kind, source_id): point_index
        for point_index, (source_kind, source_id) in enumerate(
            zip(
                frame_analysis.plot_data.point_source_kinds,
                frame_analysis.plot_data.point_source_ids,
            )
        )
    }
    intensity_by_source = {
        (measurement.source_kind, measurement.source_id): measurement
        for measurement in frame_analysis.intensity_measurements
    }
    m6_by_source_id = _m6_fields_by_source_id(frame_analysis)
    for row in rows:
        source_key = (str(row["source_kind"]), str(row["source_id"]))
        try:
            point_index = point_index_by_source[source_key]
        except KeyError as exc:
            raise ValueError(
                "Export row source is not available in Position Analysis: "
                f"{source_key[0]}:{source_key[1]}."
            ) from exc
        row.update(_annotation_fields(series, frame_analysis.plot_data, point_index))
        row["nearest_neighbor_distance"] = (
            None if not distances else distances[point_index]
        )
        row["nearest_neighbor_distance_unit"] = frame_analysis.distance_metrics.unit
        row["nearest_neighbor_angle_deg"] = None if not angles else angles[point_index]
        measurement = intensity_by_source.get(source_key)
        row.update(_intensity_fields(measurement))
        row.update(
            m6_by_source_id.get(
                str(row["source_id"]),
                _empty_m6_molecule_fields(),
            )
        )
    return rows


def _m6_fields_by_source_id(
    frame_analysis: MolecularFrameAnalysisResult,
) -> dict[str, dict[str, object]]:
    m6 = frame_analysis.m6_orientation_analysis
    if m6 is None:
        return {}
    local = m6.local_order
    multisymmetry = m6.local_multisymmetry_order
    evidence = m6.local_symmetry_evidence
    segmentation = m6.segmentation
    graph = m6.first_shell_graph
    lattice = m6.lattice_domain_analysis
    lattice_indices = (
        {}
        if lattice is None
        else {
            source_id: index for index, source_id in enumerate(lattice.source_ids)
        }
    )
    lattice_components = (
        {}
        if lattice is None
        else {
            component.lattice_domain_id: component
            for component in lattice.components
        }
    )
    local_indices = {source_id: index for index, source_id in enumerate(local.source_ids)}
    segmentation_indices = {
        source_id: index for index, source_id in enumerate(segmentation.source_ids)
    }
    graph_indices = {source_id: index for index, source_id in enumerate(graph.point_ids)}
    fields_by_source_id = {}
    for source_id in m6.point_source_ids:
        local_index = local_indices[source_id]
        segmentation_index = segmentation_indices[source_id]
        graph_index = graph_indices[source_id]
        psi6 = local.psi6[local_index]
        psi3 = None if multisymmetry is None else multisymmetry.psi3[local_index]
        ordered_component_id = segmentation.ordered_component_id[segmentation_index]
        domain_id = segmentation.m6_orientation_domain_id[segmentation_index]
        lattice_index = lattice_indices.get(source_id)
        lattice_domain_id = (
            None
            if lattice is None or lattice_index is None
            else lattice.point_lattice_domain_id[lattice_index]
        )
        lattice_component = lattice_components.get(lattice_domain_id)
        fields_by_source_id[source_id] = {
            "neighbor_count": local.neighbor_count[local_index],
            "psi3_real": None if psi3 is None else psi3.real,
            "psi3_imag": None if psi3 is None else psi3.imag,
            "q3": None if multisymmetry is None else multisymmetry.q3[local_index],
            "m3_lattice_orientation_deg": (
                None
                if multisymmetry is None
                else multisymmetry.theta3_lattice_deg[local_index]
            ),
            "m3_orientation_status": (
                None
                if multisymmetry is None
                else multisymmetry.m3_orientation_status[local_index]
            ),
            "m3_orientation_confidence": (
                None
                if multisymmetry is None
                else multisymmetry.m3_orientation_confidence[local_index]
            ),
            "m3_sublattice_phase": (
                None
                if multisymmetry is None
                else multisymmetry.m3_sublattice_phase[local_index]
            ),
            "m3_sublattice_phase_status": (
                None
                if multisymmetry is None
                else multisymmetry.m3_sublattice_phase_status[local_index]
            ),
            "m3_phase_gauge_anchor": (
                None
                if multisymmetry is None
                else multisymmetry.m3_phase_gauge_anchor[local_index]
            ),
            "m3_qualified_trifold": (
                None
                if multisymmetry is None
                else multisymmetry.m3_qualified_trifold[local_index]
            ),
            "m3_sublattice_assignment_ambiguous": (
                None
                if multisymmetry is None
                else multisymmetry.m3_sublattice_assignment_ambiguous[local_index]
            ),
            "m3_gauge_inconsistent_cycle": (
                None
                if multisymmetry is None
                else multisymmetry.m3_gauge_inconsistent_cycle[local_index]
            ),
            "m3_gauge_frustration_qc": (
                None
                if multisymmetry is None
                else multisymmetry.m3_gauge_frustration_qc[local_index]
            ),
            "symmetry_resolvability_status": (
                None
                if multisymmetry is None
                else multisymmetry.symmetry_resolvability_status[local_index]
            ),
            "edge_truncated_neighborhood": (
                None
                if multisymmetry is None
                else multisymmetry.edge_truncated_neighborhood[local_index]
            ),
            "psi6_real": None if psi6 is None else psi6.real,
            "psi6_imag": None if psi6 is None else psi6.imag,
            "q6": local.q6[local_index],
            "lattice_orientation_deg": local.lattice_orientation_deg[local_index],
            "orientation_status": local.orientation_status[local_index],
            "m6_orientation_confidence": (
                None
                if multisymmetry is None
                else multisymmetry.m6_orientation_confidence[local_index]
            ),
            "trifold_model_score": (
                None if evidence is None else evidence.trifold_model_score[local_index]
            ),
            "sixfold_model_score": (
                None if evidence is None else evidence.sixfold_model_score[local_index]
            ),
            "mixed_model_score": (
                None if evidence is None else evidence.mixed_model_score[local_index]
            ),
            "disordered_model_score": (
                None if evidence is None else evidence.disordered_model_score[local_index]
            ),
            "symmetry_best_model": (
                None if evidence is None else evidence.best_model[local_index]
            ),
            "symmetry_second_best_margin": (
                None if evidence is None else evidence.second_best_margin[local_index]
            ),
            "symmetry_observed_direction_count": (
                None if evidence is None else evidence.observed_direction_count[local_index]
            ),
            "symmetry_expected_direction_coverage": (
                None
                if evidence is None
                else evidence.expected_direction_coverage[local_index]
            ),
            "symmetry_classification_confidence": (
                None
                if evidence is None
                else evidence.classification_confidence[local_index]
            ),
            "symmetry_classification_reason": (
                None if evidence is None else evidence.classification_reason[local_index]
            ),
            "ordered_component_id": (
                None if ordered_component_id < 0 else ordered_component_id
            ),
            "m6_orientation_domain_id": None if domain_id < 0 else domain_id,
            "component_type": segmentation.component_type[segmentation_index],
            "order_qc": local.computation_status[local_index],
            "local_median_bond_length_nm": (
                local.local_median_bond_length_nm[local_index]
            ),
            "local_bond_length_mad_nm": local.local_bond_length_mad_nm[local_index],
            "local_bond_length_iqr_nm": local.local_bond_length_iqr_nm[local_index],
            "local_bond_length_robust_cv": (
                local.local_bond_length_robust_cv[local_index]
            ),
            "representative_source_id": graph.representative_source_ids[graph_index],
            "duplicate_parent_component_id": (
                graph.duplicate_parent_component_ids[graph_index]
            ),
            "duplicate_parent_component_diameter_nm": (
                graph.duplicate_parent_component_diameters_nm[graph_index]
            ),
            "duplicate_group_id": graph.duplicate_group_ids[graph_index],
            "duplicate_group_diameter_nm": graph.duplicate_group_diameters_nm[graph_index],
            "duplicate_chain_qc": graph.duplicate_chain_qc[graph_index],
            "physical_duplicate_qc": graph.physical_duplicate_qc[graph_index],
            "geometry_duplicate_qc": graph.geometry_duplicate_qc[graph_index],
            "coordinate_frame": m6.coordinate_frame,
            "orientation_reference": m6.orientation_reference,
            "lattice_domain_id": lattice_domain_id,
            "lattice_point_role": (
                None
                if lattice is None or lattice_index is None
                else lattice.point_role[lattice_index]
            ),
            "lattice_boundary_reason": (
                None
                if lattice is None or lattice_index is None
                else lattice.boundary_reason[lattice_index]
            ),
            "lattice_domain_dominant_symmetry": (
                None
                if lattice_component is None
                else lattice_component.dominant_symmetry
            ),
            "lattice_domain_confidence": (
                None if lattice_component is None else lattice_component.confidence
            ),
        }
    return fields_by_source_id


def _empty_m6_molecule_fields() -> dict[str, object]:
    return {field_name: None for field_name in _M6_MOLECULES_CSV_FIELDS}


def _write_analysis_tables(
    destination_dir: str | Path,
    molecule_rows: list[dict[str, object]],
    frame_rows: list[dict[str, object]],
    domain_rows: list[dict[str, object]],
    lattice_domain_rows: list[dict[str, object]],
) -> dict[str, Path]:
    destination = Path(destination_dir)
    destination.mkdir(parents=True, exist_ok=True)
    molecules_path = destination / "molecules.csv"
    _write_csv(molecules_path, molecule_rows, fieldnames=_FULL_MOLECULES_CSV_FIELDS)
    frames_path = destination / "frames.csv"
    _write_csv(frames_path, frame_rows, fieldnames=_FRAMES_CSV_FIELDS)
    domains_path = destination / "domains.csv"
    _write_csv(domains_path, domain_rows, fieldnames=_DOMAINS_CSV_FIELDS)
    lattice_domains_path = destination / "lattice_domains.csv"
    _write_csv(
        lattice_domains_path,
        lattice_domain_rows,
        fieldnames=_LATTICE_DOMAINS_CSV_FIELDS,
    )
    return {
        "molecules_csv": molecules_path,
        "frames_csv": frames_path,
        "domains_csv": domains_path,
        "lattice_domains_csv": lattice_domains_path,
    }


def export_current_frame_molecules_csv(
    series: MolTrackImageSeries,
    plot_data: MolecularPositionPlotData,
    destination_dir: str | Path,
) -> Path:
    """Export the plotted molecules from one working-series frame to CSV."""

    if not isinstance(series, MolTrackImageSeries):
        raise TypeError("series must be a MolTrackImageSeries instance.")
    if not isinstance(plot_data, MolecularPositionPlotData):
        raise TypeError("plot_data must be a MolecularPositionPlotData instance.")
    series.get_frame(plot_data.frame_index)
    if not plot_data.points_xy:
        raise RuntimeError("No molecular positions are available for the current frame.")

    rows = _molecule_rows(series, plot_data)
    for row in rows:
        row.update(_empty_m6_molecule_fields())
    destination = Path(destination_dir)
    destination.mkdir(parents=True, exist_ok=True)
    output_path = destination / "molecules.csv"
    _write_csv(
        output_path,
        rows,
        fieldnames=_MOLECULES_CSV_FIELDS + _M6_MOLECULES_CSV_FIELDS,
    )
    return output_path


def _molecule_rows(
    series: MolTrackImageSeries,
    plot_data: MolecularPositionPlotData,
) -> list[dict[str, object]]:
    if not isinstance(series, MolTrackImageSeries):
        raise TypeError("series must be a MolTrackImageSeries instance.")
    series.get_frame(plot_data.frame_index)
    frame_index = plot_data.frame_index
    source_frame_index = series.source_frame_indices[frame_index]
    centroids_by_source = _centroids_by_source(series, plot_data)
    rows = []
    for (position_x, position_y), source_id, source_kind in zip(
        plot_data.points_xy,
        plot_data.point_source_ids,
        plot_data.point_source_kinds,
    ):
        try:
            centroid = centroids_by_source[(source_kind, source_id)]
        except KeyError as exc:
            raise ValueError(
                f"Plot point source is not available in the series: {source_kind}:{source_id}."
            ) from exc
        row = {
                "working_frame_index": frame_index,
                "working_frame_number": frame_index + 1,
                "source_frame_index": source_frame_index,
                "source_frame_number": source_frame_index + 1,
                "time_s": _source_frame_time_s(series, frame_index),
                "source_view": plot_data.source_view,
                "source_kind": source_kind,
                "source_id": source_id,
                "origin": centroid.origin,
                "position_x": position_x,
                "position_y": position_y,
                "position_unit": plot_data.unit,
                "x_px": centroid.x_px,
                "y_px": centroid.y_px,
                "x_nm": centroid.x_nm,
                "y_nm": centroid.y_nm,
            }
        row.update(
            _molecular_orientation_fields(
                series,
                source_kind=source_kind,
                source_id=source_id,
            )
        )
        rows.append(row)
    return rows


def _molecular_orientation_fields(
    series: MolTrackImageSeries,
    *,
    source_kind: str,
    source_id: str,
) -> dict[str, object]:
    empty = {
        "molecular_orientation_status": None,
        "molecular_orientation_angle_deg": None,
        "molecular_orientation_periodicity_deg": None,
        "molecular_orientation_confidence": None,
        "molecular_orientation_method": None,
        "molecular_orientation_manual_corrected": None,
        "molecular_orientation_reviewer": None,
        "molecular_orientation_note": None,
        "molecular_orientation_automatic_status": None,
        "molecular_orientation_automatic_angle_deg": None,
        "molecular_orientation_automatic_confidence": None,
        "molecular_orientation_automatic_method": None,
        "molecular_orientation_reference": None,
    }
    store = getattr(series, "molecular_orientations", None)
    if not isinstance(store, MolecularOrientationStore):
        return empty
    orientation_source_kind = (
        "detection" if source_kind == "bbox" else source_kind
    )
    measurement = store.get(orientation_source_kind, source_id)
    if measurement is None:
        return empty
    correction = measurement.manual_correction
    automatic = (
        correction.original_result if correction is not None else measurement
    )
    return {
        "molecular_orientation_status": measurement.status,
        "molecular_orientation_angle_deg": measurement.angle_deg,
        "molecular_orientation_periodicity_deg": measurement.periodicity_deg,
        "molecular_orientation_confidence": measurement.confidence,
        "molecular_orientation_method": measurement.method,
        "molecular_orientation_manual_corrected": (
            measurement.is_manually_corrected
        ),
        "molecular_orientation_reviewer": (
            None if correction is None else correction.reviewer
        ),
        "molecular_orientation_note": (
            None if correction is None else correction.note
        ),
        "molecular_orientation_automatic_status": automatic.status,
        "molecular_orientation_automatic_angle_deg": automatic.angle_deg,
        "molecular_orientation_automatic_confidence": automatic.confidence,
        "molecular_orientation_automatic_method": automatic.method,
        "molecular_orientation_reference": (
            measurement.provenance.orientation_reference
        ),
    }


def _annotation_fields(
    series: MolTrackImageSeries,
    plot_data: MolecularPositionPlotData,
    point_index: int,
) -> dict[str, object]:
    source_kind = plot_data.point_source_kinds[point_index]
    source_id = plot_data.point_source_ids[point_index]
    if source_kind == "bbox" and series.molecular_detections is not None:
        matching_detections = [
            detection
            for detection in series.molecular_detections.get_detections(
                plot_data.frame_index,
                source_view=plot_data.source_view,
            )
            if detection.detection_id == source_id
        ]
        if not matching_detections:
            raise ValueError(f"Unknown molecular detection: {source_id}.")
        detection = matching_detections[0]
        x1, y1, x2, y2 = detection.bbox_xyxy
        return {
            "detection_id": detection.detection_id,
            "segmentation_id": None,
            "area_px": (x2 - x1) * (y2 - y1),
            "bbox_x1": x1,
            "bbox_y1": y1,
            "bbox_x2": x2,
            "bbox_y2": y2,
            "confidence": detection.confidence,
        }
    if source_kind == "segmentation" and series.molecular_segmentations is not None:
        matching_segmentations = [
            segmentation
            for segmentation in series.molecular_segmentations.get_segmentations(
                plot_data.frame_index,
                source_view=plot_data.source_view,
            )
            if segmentation.segmentation_id == source_id
        ]
        if not matching_segmentations:
            raise ValueError(f"Unknown molecular segmentation: {source_id}.")
        segmentation = matching_segmentations[0]
        mask = np.asarray(segmentation.mask, dtype=bool)
        active_y, active_x = np.nonzero(mask)
        if active_y.size == 0:
            raise ValueError(f"Molecular segmentation has an empty mask: {source_id}.")
        bbox_xyxy = segmentation.bbox_xyxy
        if bbox_xyxy is None:
            bbox_xyxy = (
                float(np.min(active_x)),
                float(np.min(active_y)),
                float(np.max(active_x) + 1),
                float(np.max(active_y) + 1),
            )
        x1, y1, x2, y2 = bbox_xyxy
        return {
            "detection_id": None,
            "segmentation_id": segmentation.segmentation_id,
            "area_px": float(active_y.size),
            "bbox_x1": x1,
            "bbox_y1": y1,
            "bbox_x2": x2,
            "bbox_y2": y2,
            "confidence": segmentation.score,
        }
    raise ValueError(f"Unsupported molecule annotation source: {source_kind}:{source_id}.")


def _intensity_fields(
    measurement: MolecularIntensityMeasurement | None,
) -> dict[str, object]:
    if measurement is None:
        return {
            "intensity_pixel_count": None,
            "intensity_unit": None,
            "intensity_sum": None,
            "intensity_mean": None,
            "intensity_median": None,
            "intensity_max": None,
            "local_background_median": None,
            "background_corrected_mean": None,
            "background_corrected_median": None,
        }
    return {
        "intensity_pixel_count": measurement.pixel_count,
        "intensity_unit": measurement.unit,
        "intensity_sum": measurement.sum,
        "intensity_mean": measurement.mean,
        "intensity_median": measurement.median,
        "intensity_max": measurement.max,
        "local_background_median": measurement.local_background_median,
        "background_corrected_mean": measurement.background_corrected_mean,
        "background_corrected_median": measurement.background_corrected_median,
    }


def _frame_row(
    series: MolTrackImageSeries,
    frame_analysis: MolecularFrameAnalysisResult,
) -> dict[str, object]:
    frame_index = frame_analysis.frame_index
    source_frame_index = series.source_frame_indices[frame_index]
    distance_metrics = frame_analysis.distance_metrics
    row = {
        "working_frame_index": frame_index,
        "working_frame_number": frame_index + 1,
        "source_frame_index": source_frame_index,
        "source_frame_number": source_frame_index + 1,
        "time_s": _source_frame_time_s(series, frame_index),
        "source_view": frame_analysis.source_view,
        "molecule_count": frame_analysis.point_count,
        "nearest_neighbor_distance_unit": distance_metrics.unit,
        "mean_nearest_neighbor_distance": distance_metrics.mean_distance,
        "median_nearest_neighbor_distance": distance_metrics.median_distance,
        "min_nearest_neighbor_distance": distance_metrics.min_distance,
        "max_nearest_neighbor_distance": distance_metrics.max_distance,
        "line_order_score": frame_analysis.angle_metrics.line_order_score,
        "intensity_metric": frame_analysis.intensity_metric,
        "intensity_unit": frame_analysis.intensity_unit,
        "mean_intensity": frame_analysis.mean_intensity,
        "median_intensity": frame_analysis.median_intensity,
    }
    row.update(_m6_frame_fields(frame_analysis))
    return row


def _m6_frame_fields(
    frame_analysis: MolecularFrameAnalysisResult,
) -> dict[str, object]:
    fields = {field_name: None for field_name in _M6_FRAMES_CSV_FIELDS}
    fields["m6_analysis_availability_status"] = (
        frame_analysis.m6_orientation_availability_status
    )
    fields["m6_analysis_unavailability_reason"] = (
        frame_analysis.m6_orientation_unavailability_reason
    )
    m6 = frame_analysis.m6_orientation_analysis
    if m6 is None:
        return fields

    aggregates = m6.frame_aggregates
    aggregate_field_names = (
        "full_domain_count",
        "small_ordered_island_count",
        "ordered_component_count",
        "original_observation_count",
        "valid_representative_count",
        "duplicate_excluded_count",
        "invalid_position_count",
        "valid_fov_area_nm2",
        "supported_area_nm2",
        "mean_local_q6_interior",
        "global_q6_interior",
        "mean_local_q6_all_valid",
        "global_q6_all_valid",
        "edge_truncated_fraction_of_valid_representatives",
        "full_domain_molecule_fraction",
        "small_island_molecule_fraction",
        "unassigned_molecule_fraction",
        "assigned_molecule_fraction",
        "largest_domain_molecule_fraction",
        "duplicate_excluded_fraction_of_original",
        "invalid_position_fraction_of_original",
        "full_domain_footprint_fraction",
        "small_island_footprint_fraction",
        "unassigned_supported_footprint_fraction",
        "unsupported_background_fraction",
        "assigned_footprint_fraction",
        "largest_domain_footprint_fraction",
        "footprint_overlap_error_nm2",
        "full_domain_molecule_weighted_coherent_q6",
        "full_domain_footprint_weighted_coherent_q6",
        "mean_full_domain_footprint_area_nm2",
        "median_full_domain_footprint_area_nm2",
        "domain_molecule_entropy",
        "domain_footprint_entropy",
        "non_positive_valid_fov_area_qc",
    )
    fields.update(
        {
            field_name: getattr(aggregates, field_name)
            for field_name in aggregate_field_names
        }
    )
    graph = m6.first_shell_graph
    footprint = aggregates.footprint_partition
    fields.update(
        {
            "construction_method": graph.construction_method,
            "footprint_construction_method": footprint.footprint_construction_method,
            "geometry_collision_epsilon_nm": graph.geometry_collision_epsilon_nm,
            "delaunay_degeneracy_qc": graph.delaunay_degeneracy_qc,
            "graph_qc_status": graph.qc_status,
            "coordinate_frame": m6.coordinate_frame,
            "orientation_reference": m6.orientation_reference,
            "spatial_calibration_fingerprint": m6.spatial_calibration_fingerprint,
            "registration_fingerprint": m6.registration_fingerprint,
            "point_coordinate_fingerprint": graph.point_coordinate_fingerprint,
            "pair_correlation_window_geometry_status": (
                m6.pair_correlation.window_geometry_status
            ),
            "fewer_than_3_noncollinear_points_qc": (
                footprint.fewer_than_3_noncollinear_points_qc
            ),
            "voronoi_degenerate_qc": footprint.voronoi_degenerate_qc,
            "footprint_clipped_by_fov_qc": footprint.footprint_clipped_by_fov_qc,
            "footprint_disconnected_qc": footprint.footprint_disconnected_qc,
            "footprint_overlap_error_qc": footprint.footprint_overlap_error_qc,
        }
    )
    return fields


def _ordered_component_rows(
    series: MolTrackImageSeries,
    frame_analysis: MolecularFrameAnalysisResult,
) -> list[dict[str, object]]:
    m6 = frame_analysis.m6_orientation_analysis
    if m6 is None:
        return []

    frame_index = frame_analysis.frame_index
    source_frame_index = series.source_frame_indices[frame_index]
    frame_fields = {
        "working_frame_index": frame_index,
        "working_frame_number": frame_index + 1,
        "source_frame_index": source_frame_index,
        "source_frame_number": source_frame_index + 1,
        "time_s": _source_frame_time_s(series, frame_index),
        "source_view": frame_analysis.source_view,
    }
    metrics_by_id = {
        component.ordered_component_id: component
        for component in m6.frame_aggregates.domain_metrics.components
    }
    footprints_by_id = {
        component.ordered_component_id: component
        for component in m6.frame_aggregates.footprint_partition.components
    }
    if metrics_by_id.keys() != footprints_by_id.keys():
        raise ValueError("M6 domain metrics and footprints must describe the same components.")

    rows = []
    for component_id in sorted(metrics_by_id):
        component = metrics_by_id[component_id]
        footprint = footprints_by_id[component_id]
        rows.append(
            {
                **frame_fields,
                "ordered_component_id": component.ordered_component_id,
                "m6_orientation_domain_id": component.m6_orientation_domain_id,
                "component_type": component.component_type,
                "molecule_count": component.molecule_count,
                "molecule_fraction_of_valid_representatives": (
                    component.molecule_fraction_of_valid_representatives
                ),
                "footprint_area_nm2": footprint.footprint_area_nm2,
                "footprint_fraction_of_valid_fov": (
                    footprint.footprint_fraction_of_valid_fov
                ),
                "molecular_mask_area_nm2": footprint.molecular_mask_area_nm2,
                "orientation_deg": component.orientation_deg,
                "centroid_x_nm": component.centroid_x_nm,
                "centroid_y_nm": component.centroid_y_nm,
                "min_x_nm": component.min_x_nm,
                "min_y_nm": component.min_y_nm,
                "max_x_nm": component.max_x_nm,
                "max_y_nm": component.max_y_nm,
                "domain_mean_local_q6": component.domain_mean_local_q6,
                "domain_coherent_q6": component.domain_coherent_q6,
                "internal_first_shell_bond_count": (
                    component.internal_first_shell_bond_count
                ),
                "domain_median_bond_length_nm": (
                    component.domain_median_bond_length_nm
                ),
                "domain_bond_length_mad_nm": component.domain_bond_length_mad_nm,
                "domain_bond_length_iqr_nm": component.domain_bond_length_iqr_nm,
                "domain_bond_length_robust_cv": component.domain_bond_length_robust_cv,
                "edge_truncated": footprint.edge_truncated,
                "insufficient_bonds_for_length_stats_qc": (
                    component.insufficient_bonds_for_length_stats_qc
                ),
                "bond_length_heterogeneity_qc": (
                    component.bond_length_heterogeneity_qc
                ),
                "footprint_disconnected_qc": footprint.footprint_disconnected_qc,
                "coordinate_frame": m6.coordinate_frame,
                "orientation_reference": m6.orientation_reference,
                "m6_settings_fingerprint": m6_settings_fingerprint(m6.settings),
                "m6_context_fingerprint": m6_context_fingerprint(m6),
                "spatial_calibration_fingerprint": m6.spatial_calibration_fingerprint,
                "registration_fingerprint": m6.registration_fingerprint,
                "point_coordinate_fingerprint": (
                    m6.first_shell_graph.point_coordinate_fingerprint
                ),
            }
        )
    return rows


def _lattice_domain_rows(
    series: MolTrackImageSeries,
    frame_analysis: MolecularFrameAnalysisResult,
) -> list[dict[str, object]]:
    m6 = frame_analysis.m6_orientation_analysis
    if m6 is None or m6.lattice_domain_analysis is None:
        return []
    lattice = m6.lattice_domain_analysis
    frame_index = frame_analysis.frame_index
    source_frame_index = series.source_frame_indices[frame_index]
    frame_fields = {
        "working_frame_index": frame_index,
        "working_frame_number": frame_index + 1,
        "source_frame_index": source_frame_index,
        "source_frame_number": source_frame_index + 1,
        "time_s": _source_frame_time_s(series, frame_index),
        "source_view": frame_analysis.source_view,
    }
    rows: list[dict[str, object]] = []
    for component in lattice.components:
        geometry = component.geometry
        qc = component.qc
        rows.append(
            {
                **frame_fields,
                "lattice_domain_id": component.lattice_domain_id,
                "source_component_id": component.source_component_id,
                "component_type": component.component_type,
                "dominant_symmetry": component.dominant_symmetry,
                "molecule_count": component.molecule_count,
                "core_size": component.core_size,
                "halo_size": component.halo_size,
                "molecule_fraction_of_valid_representatives": (
                    component.molecule_fraction_of_valid_representatives
                ),
                "adjacent_boundary_point_count": (
                    component.adjacent_boundary_point_count
                ),
                "adjacent_boundary_point_fraction": (
                    component.adjacent_boundary_point_fraction
                ),
                "theta3_lattice_prototype_deg": (
                    component.theta3_lattice_prototype_deg
                ),
                "theta6_prototype_deg": component.theta6_prototype_deg,
                "theta3_lattice_spread_deg": component.theta3_lattice_spread_deg,
                "theta6_spread_deg": component.theta6_spread_deg,
                "orientation_reference_channel": (
                    component.orientation_reference_channel
                ),
                "m3_m6_orientation_relation_status": (
                    component.m3_m6_orientation_relation_status
                ),
                "m3_m6_orientation_offset_deg": (
                    component.m3_m6_orientation_offset_deg
                ),
                "confidence": component.confidence,
                "centroid_x_nm": geometry.centroid_x_nm,
                "centroid_y_nm": geometry.centroid_y_nm,
                "min_x_nm": geometry.min_x_nm,
                "min_y_nm": geometry.min_y_nm,
                "max_x_nm": geometry.max_x_nm,
                "max_y_nm": geometry.max_y_nm,
                "internal_first_shell_bond_count": (
                    geometry.internal_first_shell_bond_count
                ),
                "median_bond_length_nm": geometry.median_bond_length_nm,
                "bond_length_mad_nm": geometry.bond_length_mad_nm,
                "bond_length_iqr_nm": geometry.bond_length_iqr_nm,
                "bond_length_robust_cv": geometry.bond_length_robust_cv,
                "footprint_area_nm2": geometry.footprint_area_nm2,
                "footprint_fraction_of_valid_fov": (
                    geometry.footprint_fraction_of_valid_fov
                ),
                "edge_truncated_neighborhood_qc": qc.edge_truncated_neighborhood,
                "graph_disconnected_qc": qc.graph_disconnected,
                "insufficient_bonds_for_length_stats_qc": (
                    qc.insufficient_bonds_for_length_stats
                ),
                "bond_length_heterogeneity_qc": qc.bond_length_heterogeneity,
                "footprint_unavailable_qc": qc.footprint_unavailable,
                "footprint_clipped_by_fov_qc": qc.footprint_clipped_by_fov,
                "symmetry_alias_unresolvable_from_centroids_qc": (
                    qc.symmetry_alias_unresolvable_from_centroids
                ),
                "coordinate_frame": lattice.coordinate_frame,
                "orientation_reference": lattice.orientation_reference,
                "spatial_calibration_fingerprint": (
                    lattice.spatial_calibration_fingerprint
                ),
                "registration_fingerprint": lattice.registration_fingerprint,
                "point_coordinate_fingerprint": (
                    lattice.point_coordinate_fingerprint
                ),
                "first_shell_graph_fingerprint": (
                    lattice.first_shell_graph_fingerprint
                ),
                "local_order_analysis_fingerprint": (
                    lattice.local_order_analysis_fingerprint
                ),
                "local_symmetry_evidence_settings_fingerprint": (
                    lattice.local_symmetry_evidence_settings_fingerprint
                ),
                "local_symmetry_bond_evidence_fingerprint": (
                    lattice.local_symmetry_bond_evidence_fingerprint
                ),
                "seed_growth_settings_fingerprint": (
                    lattice.seed_growth_settings_fingerprint
                ),
                "seed_growth_result_fingerprint": (
                    lattice.seed_growth_result_fingerprint
                ),
                "settings_fingerprint": lattice.settings_fingerprint,
                "schema_version": lattice.schema_version,
            }
        )
    return rows


def _ordered_component_row_sort_key(
    row: Mapping[str, object],
) -> tuple[int, int, int, str, int, int]:
    domain_id = row["m6_orientation_domain_id"]
    return (
        int(row["working_frame_index"]),
        int(row["ordered_component_id"]),
        -1 if domain_id is None else int(domain_id),
        str(row.get("domain_type_range_name") or ""),
        int(row.get("domain_type_range_start_frame") or -1),
        int(row.get("domain_type_range_end_frame") or -1),
    )


def _domain_type_range_slices(
    full_analysis: MolecularFrameRangeAnalysis,
    classification: M6DomainTypeClassificationResult | None,
) -> tuple[MolecularFrameRangeAnalysis, ...]:
    if classification is None:
        return ()
    if not isinstance(classification, M6DomainTypeClassificationResult):
        raise TypeError(
            "m6_domain_type_classification must be a domain type result or None."
        )
    return tuple(
        replace(
            full_analysis,
            frame_range=frame_range,
            frame_results=tuple(
                frame_result
                for frame_result in full_analysis.frame_results
                if frame_range.start_frame
                <= frame_result.frame_index
                <= frame_range.end_frame
            ),
        )
        for frame_range in classification.analysis_scope.ranges
    )


def _domain_type_range_analyses_from_series(
    series: MolTrackImageSeries,
    classification: M6DomainTypeClassificationResult | None,
    *,
    expected_source_view: str,
    use_segmentation_centroids: bool,
) -> tuple[MolecularFrameRangeAnalysis, ...]:
    if classification is None:
        return ()
    if not isinstance(classification, M6DomainTypeClassificationResult):
        raise TypeError(
            "m6_domain_type_classification must be a domain type result or None."
        )
    if (
        classification.analysis_scope.frame_count != series.frame_count
        or classification.source_view != expected_source_view
    ):
        return ()
    return tuple(
        analyze_molecular_frame_range(
            series,
            frame_range,
            source_view=classification.source_view,
            use_segmentation_centroids=use_segmentation_centroids,
            m6_orientation_settings=classification.m6_settings,
        )
        for frame_range in classification.analysis_scope.ranges
    )


def _validated_domain_type_export_lookup(
    classification: M6DomainTypeClassificationResult | None,
    range_analyses: Sequence[MolecularFrameRangeAnalysis],
) -> _DomainTypeExportLookup | None:
    lookup = _build_domain_type_export_lookup(classification)
    if lookup is None:
        return None
    normalized_analyses = tuple(range_analyses)
    if (
        tuple(value.frame_range for value in normalized_analyses)
        != classification.analysis_scope.ranges
        or any(value.source_view != classification.source_view for value in normalized_analyses)
    ):
        return None
    current_observations = tuple(
        sorted(
            (
                observation
                for analysis in normalized_analyses
                for observation in extract_m6_domain_type_observations(
                    analysis,
                    settings=classification.classification_settings,
                )
            ),
            key=lambda value: value.stable_key,
        )
    )
    if current_observations != classification.observations:
        return None
    return lookup


def _build_domain_type_export_lookup(
    classification: M6DomainTypeClassificationResult | None,
) -> _DomainTypeExportLookup | None:
    if classification is None:
        return None
    if not isinstance(classification, M6DomainTypeClassificationResult):
        raise TypeError(
            "m6_domain_type_classification must be a domain type result or None."
        )
    observations = {
        observation.stable_key: observation
        for observation in classification.observations
    }
    labels = {
        domain_type.domain_type_id: domain_type.label
        for domain_type in classification.domain_types
    }
    by_observation_key = {}
    component_records: dict[
        _DomainComponentExportKey,
        list[_DomainTypeExportRecord],
    ] = {}
    for assignment in classification.assignments:
        observation = observations[assignment.observation_key]
        label = (
            "Unclassified"
            if assignment.domain_type_id is None
            else labels[assignment.domain_type_id]
        )
        record = _DomainTypeExportRecord(observation, assignment, label)
        by_observation_key[observation.stable_key] = record
        component_key = _domain_component_export_key(
            source_view=observation.source_view,
            working_frame_index=observation.frame_index,
            source_frame_index=observation.source_frame_index,
            ordered_component_id=observation.ordered_component_id,
            m6_orientation_domain_id=observation.m6_orientation_domain_id,
        )
        component_records.setdefault(component_key, []).append(record)
    return _DomainTypeExportLookup(
        source_view=classification.source_view,
        by_observation_key=by_observation_key,
        by_component_key={
            key: tuple(records) for key, records in component_records.items()
        },
    )


def _apply_domain_type_export_fields(
    rows: list[dict[str, object]],
    lookup: _DomainTypeExportLookup | None,
    *,
    frame_range: MolecularFrameRange | None = None,
) -> None:
    expanded_rows = []
    for row in rows:
        row.update({field_name: None for field_name in _DOMAIN_TYPE_CSV_FIELDS})
        if lookup is None or str(row["source_view"]) != lookup.source_view:
            expanded_rows.append(row)
            continue
        component_key = _domain_component_export_key(
            source_view=str(row["source_view"]),
            working_frame_index=int(row["working_frame_index"]),
            source_frame_index=int(row["source_frame_index"]),
            ordered_component_id=int(row["ordered_component_id"]),
            m6_orientation_domain_id=(
                None
                if row["m6_orientation_domain_id"] is None
                else int(row["m6_orientation_domain_id"])
            ),
        )
        if frame_range is None:
            candidates = lookup.by_component_key.get(component_key, ())
        else:
            record = lookup.by_observation_key.get(
                (
                    frame_range.name,
                    frame_range.start_frame,
                    frame_range.end_frame,
                    component_key.working_frame_index,
                    component_key.source_frame_index,
                    component_key.ordered_component_id,
                    component_key.m6_orientation_domain_id,
                )
            )
            candidates = () if record is None else (record,)
        matching_records = tuple(
            record
            for record in candidates
            if _domain_row_matches_observation(row, record.observation)
        )
        if not matching_records:
            expanded_rows.append(row)
            continue
        for record in matching_records:
            assigned_row = dict(row)
            assignment = record.assignment
            observation = record.observation
            assigned_row.update(
                {
                    "domain_type_range_name": observation.range_name,
                    "domain_type_range_start_frame": observation.range_start_frame,
                    "domain_type_range_end_frame": observation.range_end_frame,
                    "domain_type_id": assignment.domain_type_id,
                    "domain_type_label": record.label,
                    "domain_type_qualification_status": (
                        observation.qualification_status
                    ),
                    "domain_type_unclassified_reason": (
                        assignment.unclassified_reason
                    ),
                }
            )
            expanded_rows.append(assigned_row)
    rows[:] = expanded_rows


def _domain_row_matches_observation(
    row: Mapping[str, object],
    observation: M6DomainTypeObservation,
) -> bool:
    expected_values = {
        "component_type": observation.component_type,
        "molecule_count": observation.molecule_count,
        "molecule_fraction_of_valid_representatives": (
            observation.molecule_fraction_of_valid_representatives
        ),
        "footprint_area_nm2": observation.footprint_area_nm2,
        "footprint_fraction_of_valid_fov": (
            observation.footprint_fraction_of_valid_fov
        ),
        "molecular_mask_area_nm2": observation.molecular_mask_area_nm2,
        "orientation_deg": observation.orientation_deg,
        "centroid_x_nm": observation.centroid_x_nm,
        "centroid_y_nm": observation.centroid_y_nm,
        "min_x_nm": observation.min_x_nm,
        "min_y_nm": observation.min_y_nm,
        "max_x_nm": observation.max_x_nm,
        "max_y_nm": observation.max_y_nm,
        "domain_mean_local_q6": observation.domain_mean_local_q6,
        "domain_coherent_q6": observation.domain_coherent_q6,
        "internal_first_shell_bond_count": (
            observation.internal_first_shell_bond_count
        ),
        "domain_median_bond_length_nm": (
            observation.domain_median_bond_length_nm
        ),
        "domain_bond_length_mad_nm": observation.domain_bond_length_mad_nm,
        "domain_bond_length_iqr_nm": observation.domain_bond_length_iqr_nm,
        "domain_bond_length_robust_cv": (
            observation.domain_bond_length_robust_cv
        ),
        "edge_truncated": observation.edge_truncated,
        "insufficient_bonds_for_length_stats_qc": (
            observation.insufficient_bonds_for_length_stats_qc
        ),
        "bond_length_heterogeneity_qc": (
            observation.bond_length_heterogeneity_qc
        ),
        "footprint_disconnected_qc": observation.footprint_disconnected_qc,
        "m6_settings_fingerprint": observation.m6_settings_fingerprint,
        "m6_context_fingerprint": observation.m6_context_fingerprint,
    }
    for field_name, expected in expected_values.items():
        actual = row[field_name]
        if isinstance(expected, float):
            if actual is None or not isclose(
                float(actual),
                expected,
                rel_tol=1e-12,
                abs_tol=1e-12,
            ):
                return False
        elif actual != expected:
            return False
    return True


def _domain_component_export_key(
    *,
    source_view: str,
    working_frame_index: int,
    source_frame_index: int,
    ordered_component_id: int,
    m6_orientation_domain_id: int | None,
) -> _DomainComponentExportKey:
    return _DomainComponentExportKey(
        source_view=str(source_view),
        working_frame_index=int(working_frame_index),
        source_frame_index=int(source_frame_index),
        ordered_component_id=int(ordered_component_id),
        m6_orientation_domain_id=(
            None
            if m6_orientation_domain_id is None
            else int(m6_orientation_domain_id)
        ),
    )


def _write_csv(
    path: Path,
    rows: list[dict[str, object]],
    *,
    fieldnames: tuple[str, ...],
) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, payload: dict[str, object]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def _centroids_by_source(
    series: MolTrackImageSeries,
    plot_data: MolecularPositionPlotData,
) -> dict[tuple[str, str], MolecularCentroid]:
    centroids_by_source: dict[tuple[str, str], MolecularCentroid] = {}
    for use_segmentation_centroids in (True, False):
        centroids = build_molecular_centroids(
            series,
            frame_index=plot_data.frame_index,
            source_view=plot_data.source_view,
            use_segmentation_centroids=use_segmentation_centroids,
        )
        for centroid in centroids:
            source_kind = (
                "segmentation" if centroid.source_kind == "segmentation" else "bbox"
            )
            centroids_by_source[(source_kind, centroid.source_id)] = centroid
    return centroids_by_source


def _source_frame_time_s(series: MolTrackImageSeries, frame_index: int) -> float | None:
    source_frame_index = series.source_frame_indices[frame_index]
    frame_times = getattr(series.metadata, "frame_times_s", None)
    if frame_times is not None:
        metadata_index = source_frame_index
        if series.reverse_frame_order:
            metadata_index = len(frame_times) - source_frame_index - 1
        if 0 <= metadata_index < len(frame_times):
            return float(frame_times[metadata_index])
    frame_interval_s = getattr(series.metadata, "frame_interval_s", None)
    if frame_interval_s is None:
        return None
    return float(source_frame_index * frame_interval_s)
