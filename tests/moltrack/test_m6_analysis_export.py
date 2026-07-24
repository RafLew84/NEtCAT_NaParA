import csv
import json
import math
import tempfile
import unittest
import xml.etree.ElementTree as ET
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import numpy as np

from moltrack.analysis import (
    LOCAL_MULTI_SYMMETRY_BOND_ORDER_SCHEMA_VERSION,
    LOCAL_SYMMETRY_EVIDENCE_ALGORITHM_VERSION,
    LOCAL_SYMMETRY_EVIDENCE_SCHEMA_VERSION,
    M6DomainTypeAnalysisStore,
    M6DomainTypeClassificationSettings,
    M6_DOMAIN_TYPE_ALGORITHM_VERSION,
    M6_ORIENTATION_ALGORITHM_VERSION,
    MolecularFrameRange,
    MolecularFrameRangeSelection,
    MolecularM6OrientationAnalysisSettings,
    adapt_m6_domain_type_analysis_source,
    analyze_molecular_frame_range,
    compare_molecular_frame_ranges,
)
from moltrack.core import (
    MolTrackImageSeries,
    MolecularDetection,
    MolecularDetectionSet,
)
from moltrack.persistence import (
    AnalysisExportSettings,
    export_analysis_package,
    export_current_frame_analysis_csv,
    export_full_working_series_analysis_csv,
    export_selected_ranges_analysis_csv,
)
from moltrack.persistence import analysis_export as analysis_export_module
from moltrack.persistence import analysis_environment as analysis_environment_module
from moltrack.persistence.analysis_plots import export_m6_domain_type_plots
from moltrack.visualization.m6_domain_type_colors import (
    M6_DOMAIN_TYPE_UNCLASSIFIED_COLOR,
    m6_domain_type_color,
)
from nanotrack.core import STMSequenceMetadata


_M6_MOLECULE_FIELDS = (
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

_M6_FRAME_FIELDS = (
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

_DOMAIN_FIELDS = (
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

_DOMAIN_TYPES_FIELDS = (
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

_DOMAIN_TYPE_RANGES_FIELDS = (
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

_DOMAIN_TYPE_COMPARISON_FIELDS = (
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


def _settings() -> MolecularM6OrientationAnalysisSettings:
    return MolecularM6OrientationAnalysisSettings(
        duplicate_max_distance_nm=0.5,
        first_shell_r_min_nm=1.5,
        first_shell_r_max_nm=2.3,
        min_ordered_component_size=3,
        min_seed_size=5,
        min_domain_size=8,
        footprint_support_radius_nm=1.2,
        gr_bin_width_nm=0.25,
        gr_max_nm=10.0,
        gr_min_expected_pair_exposure=0.1,
    )


def _triangular_points() -> list[tuple[float, float]]:
    points = []
    for row in range(4):
        for column in range(4):
            points.append(
                (
                    8.0 + 2.0 * column + (row % 2),
                    8.0 + math.sqrt(3.0) * row,
                )
            )
    # This observation exercises the physical-duplicate export fields.
    points.append((8.2, 8.0))
    return points


def _series(*, frame_count: int) -> MolTrackImageSeries:
    points = _triangular_points()
    detections = MolecularDetectionSet(frame_count=frame_count)
    for frame_index in range(frame_count):
        frame_detections = []
        for point_index in reversed(range(len(points))):
            x, y = points[point_index]
            frame_detections.append(
                MolecularDetection(
                    frame_index,
                    (x - 0.2, y - 0.2, x + 0.2, y + 0.2),
                    0.5 + point_index / 100.0,
                    detection_id=f"frame-{frame_index}-point-{point_index:02d}",
                )
            )
        detections.set_detections(
            frame_index,
            frame_detections,
            source_view="raw",
            frame_shape=(40, 40),
        )
    return MolTrackImageSeries(
        source_path="movie.mpp",
        raw_frames=np.zeros((frame_count, 40, 40), dtype=np.float32),
        metadata=STMSequenceMetadata(
            pixels_x=40,
            pixels_y=40,
            size_nm_x=40.0,
            size_nm_y=40.0,
            scan_angle_deg=0.0,
        ),
        molecular_detections=detections,
    )


def _triangular_patch(
    angle_deg: float,
    shift_xy_nm: tuple[float, float],
    *,
    width: int = 8,
    height: int = 8,
) -> np.ndarray:
    points = np.asarray(
        [
            (2.0 * (column + 0.5 * (row % 2)), math.sqrt(3.0) * row)
            for row in range(height)
            for column in range(width)
        ],
        dtype=np.float64,
    )
    angle = math.radians(angle_deg)
    rotation = np.asarray(
        ((math.cos(angle), -math.sin(angle)), (math.sin(angle), math.cos(angle)))
    )
    return points @ rotation.T + np.asarray(shift_xy_nm)


def _domain_export_series(
    *,
    x_offset_nm: float = 0.0,
    frame_x_offsets_nm: tuple[float, ...] | None = None,
) -> MolTrackImageSeries:
    two_domains = np.vstack(
        (
            _triangular_patch(0.0, (6.0, 6.0)),
            _triangular_patch(22.0, (38.0, 6.0)),
        )
    )
    no_domains = np.asarray(
        [(18.0 + 2.0 * column, 18.0 + 2.0 * row) for row in range(3) for column in range(3)],
        dtype=np.float64,
    )
    one_domain = _triangular_patch(0.0, (6.0, 6.0))
    frame_points = (two_domains, no_domains, one_domain)
    frame_size = 72
    detections = MolecularDetectionSet(frame_count=len(frame_points))
    for frame_index, points in enumerate(frame_points):
        frame_x_offset_nm = (
            x_offset_nm
            if frame_x_offsets_nm is None
            else frame_x_offsets_nm[frame_index]
        )
        detections.set_detections(
            frame_index,
            [
                MolecularDetection(
                    frame_index,
                    (
                        x + frame_x_offset_nm - 0.2,
                        frame_size - y - 0.2,
                        x + frame_x_offset_nm + 0.2,
                        frame_size - y + 0.2,
                    ),
                    0.9,
                    detection_id=f"frame-{frame_index}-point-{point_index:03d}",
                )
                for point_index, (x, y) in enumerate(points)
            ],
            source_view="raw",
            frame_shape=(frame_size, frame_size),
        )
    return MolTrackImageSeries(
        source_path="domain-series.mpp",
        raw_frames=np.zeros((len(frame_points), frame_size, frame_size), dtype=np.float32),
        metadata=STMSequenceMetadata(
            pixels_x=frame_size,
            pixels_y=frame_size,
            size_nm_x=float(frame_size),
            size_nm_y=float(frame_size),
            scan_angle_deg=0.0,
        ),
        molecular_detections=detections,
    )


def _expected_m6_fields(analysis, source_id: str) -> dict[str, object | None]:
    m6 = analysis.m6_orientation_analysis
    assert m6 is not None
    local = m6.local_order
    segmentation = m6.segmentation
    graph = m6.first_shell_graph
    multisymmetry = m6.local_multisymmetry_order
    evidence = m6.local_symmetry_evidence
    assert multisymmetry is not None
    assert evidence is not None
    local_index = local.source_ids.index(source_id)
    segmentation_index = segmentation.source_ids.index(source_id)
    graph_index = graph.point_ids.index(source_id)
    psi6 = local.psi6[local_index]
    psi3 = multisymmetry.psi3[local_index]
    ordered_component_id = segmentation.ordered_component_id[segmentation_index]
    domain_id = segmentation.m6_orientation_domain_id[segmentation_index]
    return {
        "neighbor_count": local.neighbor_count[local_index],
        "psi3_real": None if psi3 is None else psi3.real,
        "psi3_imag": None if psi3 is None else psi3.imag,
        "q3": multisymmetry.q3[local_index],
        "m3_lattice_orientation_deg": multisymmetry.theta3_lattice_deg[local_index],
        "m3_orientation_status": multisymmetry.m3_orientation_status[local_index],
        "m3_orientation_confidence": multisymmetry.m3_orientation_confidence[local_index],
        "m3_sublattice_phase": multisymmetry.m3_sublattice_phase[local_index],
        "m3_sublattice_phase_status": multisymmetry.m3_sublattice_phase_status[local_index],
        "m3_phase_gauge_anchor": multisymmetry.m3_phase_gauge_anchor[local_index],
        "m3_qualified_trifold": multisymmetry.m3_qualified_trifold[local_index],
        "m3_sublattice_assignment_ambiguous": (
            multisymmetry.m3_sublattice_assignment_ambiguous[local_index]
        ),
        "m3_gauge_inconsistent_cycle": multisymmetry.m3_gauge_inconsistent_cycle[local_index],
        "m3_gauge_frustration_qc": multisymmetry.m3_gauge_frustration_qc[local_index],
        "symmetry_resolvability_status": multisymmetry.symmetry_resolvability_status[local_index],
        "edge_truncated_neighborhood": multisymmetry.edge_truncated_neighborhood[local_index],
        "psi6_real": None if psi6 is None else psi6.real,
        "psi6_imag": None if psi6 is None else psi6.imag,
        "q6": local.q6[local_index],
        "lattice_orientation_deg": local.lattice_orientation_deg[local_index],
        "orientation_status": local.orientation_status[local_index],
        "m6_orientation_confidence": multisymmetry.m6_orientation_confidence[local_index],
        "trifold_model_score": evidence.trifold_model_score[local_index],
        "sixfold_model_score": evidence.sixfold_model_score[local_index],
        "mixed_model_score": evidence.mixed_model_score[local_index],
        "disordered_model_score": evidence.disordered_model_score[local_index],
        "symmetry_best_model": evidence.best_model[local_index],
        "symmetry_second_best_margin": evidence.second_best_margin[local_index],
        "symmetry_observed_direction_count": evidence.observed_direction_count[local_index],
        "symmetry_expected_direction_coverage": evidence.expected_direction_coverage[local_index],
        "symmetry_classification_confidence": evidence.classification_confidence[local_index],
        "symmetry_classification_reason": evidence.classification_reason[local_index],
        "ordered_component_id": None if ordered_component_id < 0 else ordered_component_id,
        "m6_orientation_domain_id": None if domain_id < 0 else domain_id,
        "component_type": segmentation.component_type[segmentation_index],
        "order_qc": local.computation_status[local_index],
        "local_median_bond_length_nm": local.local_median_bond_length_nm[local_index],
        "local_bond_length_mad_nm": local.local_bond_length_mad_nm[local_index],
        "local_bond_length_iqr_nm": local.local_bond_length_iqr_nm[local_index],
        "local_bond_length_robust_cv": local.local_bond_length_robust_cv[local_index],
        "representative_source_id": graph.representative_source_ids[graph_index],
        "duplicate_parent_component_id": graph.duplicate_parent_component_ids[graph_index],
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
    }


def _assert_csv_value(
    test_case: unittest.TestCase,
    actual: str,
    expected: object | None,
) -> None:
    if expected is None:
        test_case.assertEqual(actual, "")
    elif isinstance(expected, float):
        test_case.assertAlmostEqual(float(actual), expected)
    else:
        test_case.assertEqual(actual, str(expected))


def _read_csv_table(path: Path) -> tuple[tuple[str, ...], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return tuple(reader.fieldnames or ()), list(reader)


def _rgb_hex(color: tuple[int, int, int, int]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*color[:3])


def _svg_group_text(svg_text: str, group_id: str) -> str:
    root = ET.fromstring(svg_text)
    group = next(
        element
        for element in root.iter()
        if element.attrib.get("id") == group_id
    )
    return " ".join(value.strip() for value in group.itertext() if value.strip())


class M6AnalysisExportTests(unittest.TestCase):
    @staticmethod
    def _analyze_domain_types(series, frame_range, *, minimum_observations=1):
        analysis = analyze_molecular_frame_range(
            series,
            frame_range,
            source_view="raw",
            m6_orientation_settings=_settings(),
        )
        source = adapt_m6_domain_type_analysis_source(
            analysis,
            frame_count=series.frame_count,
        )
        return M6DomainTypeAnalysisStore().analyze(
            source,
            classification_settings=M6DomainTypeClassificationSettings(
                orientation_tolerance_deg=5.0,
                bond_length_tolerance_mode="absolute_nm",
                bond_length_tolerance_value=0.5,
                minimum_observations_per_type=minimum_observations,
            ),
        )

    @classmethod
    def _classify_domain_types(cls, series, frame_range, *, minimum_observations=1):
        return cls._analyze_domain_types(
            series,
            frame_range,
            minimum_observations=minimum_observations,
        ).classification

    def test_domain_type_assignments_follow_component_keys_after_row_permutation(self) -> None:
        series = _domain_export_series()
        classification = self._classify_domain_types(
            series,
            MolecularFrameRange("all domains", 0, 2),
        )
        original_builder = analysis_export_module._ordered_component_rows

        def permuted_rows(*args, **kwargs):
            return list(reversed(original_builder(*args, **kwargs)))

        with tempfile.TemporaryDirectory() as tmpdir, patch.object(
            analysis_export_module,
            "_ordered_component_rows",
            side_effect=permuted_rows,
        ):
            paths = export_full_working_series_analysis_csv(
                series,
                tmpdir,
                m6_orientation_settings=_settings(),
                m6_domain_type_classification=classification,
            )
            with paths["domains_csv"].open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                rows = list(csv.DictReader(handle))

        assignments = {
            assignment.observation_key: assignment
            for assignment in classification.assignments
        }
        observations = {
            (
                observation.frame_index,
                observation.source_frame_index,
                observation.ordered_component_id,
                observation.m6_orientation_domain_id,
            ): observation
            for observation in classification.observations
        }
        labels = {
            domain_type.domain_type_id: domain_type.label
            for domain_type in classification.domain_types
        }
        self.assertEqual(len(rows), len(observations))
        for row in rows:
            key = (
                int(row["working_frame_index"]),
                int(row["source_frame_index"]),
                int(row["ordered_component_id"]),
                (
                    None
                    if row["m6_orientation_domain_id"] == ""
                    else int(row["m6_orientation_domain_id"])
                ),
            )
            observation = observations[key]
            assignment = assignments[observation.stable_key]
            self.assertEqual(
                row["domain_type_id"],
                (
                    ""
                    if assignment.domain_type_id is None
                    else str(assignment.domain_type_id)
                ),
            )
            self.assertEqual(
                row["domain_type_label"],
                "Unclassified"
                if assignment.domain_type_id is None
                else labels[assignment.domain_type_id],
            )
            self.assertEqual(
                row["domain_type_qualification_status"],
                observation.qualification_status,
            )
            self.assertEqual(
                row["domain_type_unclassified_reason"],
                assignment.unclassified_reason or "",
            )
            _assert_csv_value(
                self,
                row["molecular_mask_area_nm2"],
                observation.molecular_mask_area_nm2,
            )
            self.assertEqual(
                row["m6_settings_fingerprint"],
                observation.m6_settings_fingerprint,
            )
            self.assertEqual(
                row["m6_context_fingerprint"],
                observation.m6_context_fingerprint,
            )

    def test_domain_type_export_keeps_outside_and_absent_analysis_fields_empty(self) -> None:
        series = _domain_export_series()
        classification = self._classify_domain_types(
            series,
            MolecularFrameRange("first frame", 0, 0),
            minimum_observations=2,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            typed_paths = export_full_working_series_analysis_csv(
                series,
                Path(tmpdir) / "typed",
                m6_orientation_settings=_settings(),
                m6_domain_type_classification=classification,
            )
            plain_paths = export_full_working_series_analysis_csv(
                series,
                Path(tmpdir) / "plain",
                m6_orientation_settings=_settings(),
            )
            with typed_paths["domains_csv"].open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                typed_rows = list(csv.DictReader(handle))
            with plain_paths["domains_csv"].open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                plain_rows = list(csv.DictReader(handle))

        type_fields = _DOMAIN_FIELDS[-7:]
        first_frame_rows = [
            row for row in typed_rows if row["working_frame_index"] == "0"
        ]
        outside_rows = [
            row for row in typed_rows if row["working_frame_index"] != "0"
        ]
        self.assertTrue(first_frame_rows)
        self.assertTrue(outside_rows)
        self.assertTrue(
            all(
                row["domain_type_label"] == "Unclassified"
                for row in first_frame_rows
            )
        )
        self.assertTrue(
            all(row["domain_type_unclassified_reason"] for row in first_frame_rows)
        )
        self.assertTrue(
            all(row[field] == "" for row in outside_rows for field in type_fields)
        )
        self.assertTrue(
            all(row[field] == "" for row in plain_rows for field in type_fields)
        )

    def test_analysis_package_forwards_domain_type_snapshot_to_domains_csv(self) -> None:
        series = _domain_export_series()
        classification = self._classify_domain_types(
            series,
            MolecularFrameRange("all domains", 0, 2),
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            destination = Path(tmpdir) / "package"
            export_analysis_package(
                series,
                AnalysisExportSettings(
                    scope="full_working_series",
                    destination=destination,
                    package_format="directory",
                    include_tables=True,
                    include_spatial_grids=False,
                    include_plots=False,
                    frame_count=series.frame_count,
                    active_frame_index=series.active_frame_index,
                    source_view="raw",
                    use_segmentation_centroids=True,
                    intensity_metric="mean",
                    intensity_unit="a.u.",
                    background_inner_radius_px=1,
                    background_outer_radius_px=3,
                    density_grid_shape=(4, 4),
                    m6_orientation_settings=_settings(),
                    m6_domain_type_classification=classification,
                ),
                environment_provider=lambda: {},
            )
            with (destination / "domains.csv").open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                rows = list(csv.DictReader(handle))

        self.assertTrue(rows)
        self.assertTrue(all(row["domain_type_label"] for row in rows))

    def test_single_range_package_exports_domain_type_tables_and_manifest(self) -> None:
        series = _domain_export_series()
        outcome = self._analyze_domain_types(
            series,
            MolecularFrameRange("whole experiment", 0, 2),
        )
        classification = outcome.classification
        self.assertIsNotNone(classification)
        self.assertIsNotNone(outcome.table_result)

        with tempfile.TemporaryDirectory() as tmpdir:
            destination = Path(tmpdir) / "single-range-package"
            export_analysis_package(
                series,
                AnalysisExportSettings(
                    scope="full_working_series",
                    destination=destination,
                    package_format="directory",
                    include_tables=True,
                    include_spatial_grids=False,
                    include_plots=True,
                    frame_count=series.frame_count,
                    active_frame_index=series.active_frame_index,
                    source_view="raw",
                    use_segmentation_centroids=True,
                    intensity_metric="mean",
                    intensity_unit="a.u.",
                    background_inner_radius_px=1,
                    background_outer_radius_px=3,
                    density_grid_shape=(4, 4),
                    m6_orientation_settings=_settings(),
                    m6_domain_type_classification=classification,
                    m6_domain_type_table_result=outcome.table_result,
                ),
                environment_provider=lambda: {},
            )
            type_fields, type_rows = _read_csv_table(
                destination / "domain_types.csv"
            )
            range_fields, range_rows = _read_csv_table(
                destination / "domain_type_ranges.csv"
            )
            comparison_fields, comparison_rows = _read_csv_table(
                destination / "domain_type_comparison.csv"
            )
            manifest = json.loads(
                (destination / "manifest.json").read_text(encoding="utf-8")
            )

        self.assertEqual(type_fields, _DOMAIN_TYPES_FIELDS)
        self.assertEqual(range_fields, _DOMAIN_TYPE_RANGES_FIELDS)
        self.assertEqual(comparison_fields, _DOMAIN_TYPE_COMPARISON_FIELDS)
        self.assertEqual(
            [int(row["domain_type_id"]) for row in type_rows],
            list(range(len(classification.domain_types))),
        )
        self.assertEqual(
            [row["domain_type_label"] for row in range_rows],
            [
                *(domain_type.label for domain_type in classification.domain_types),
                "Unclassified",
            ],
        )
        self.assertTrue(all(row["condition_order"] == "single" for row in range_rows))
        self.assertEqual(comparison_rows, [])
        domain_manifest = manifest["analysis"]["m6_domain_types"]
        self.assertEqual(manifest["export_schema_version"], 7)
        self.assertTrue(domain_manifest["available"])
        self.assertEqual(domain_manifest["algorithm"], "deterministic_complete_linkage")
        self.assertEqual(
            domain_manifest["algorithm_version"],
            M6_DOMAIN_TYPE_ALGORITHM_VERSION,
        )
        self.assertEqual(domain_manifest["analysis_mode"], "single_range")
        self.assertFalse(domain_manifest["uses_tracking"])
        self.assertEqual(
            domain_manifest["classification_input_fingerprint"],
            classification.input_fingerprint,
        )
        self.assertEqual(
            domain_manifest["classification_settings"],
            classification.classification_settings.to_dict(),
        )
        self.assertEqual(len(domain_manifest["ranges"]), 1)
        self.assertEqual(
            domain_manifest["ranges"][0]["source_frame_indices"],
            [0, 1, 2],
        )
        self.assertEqual(
            [entry["kind"] for entry in manifest["plots"]["generated"]],
            [
                "current_frame_positions",
                "domain_type_scatter",
                "domain_type_shares",
            ],
        )
        self.assertEqual(manifest["plots"]["skipped"], [])

    def test_comparison_package_exports_ordered_range_rows_and_deltas(self) -> None:
        series = _domain_export_series()
        selection = MolecularFrameRangeSelection(
            frame_count=series.frame_count,
            source_view="raw",
            first_range=MolecularFrameRange("before", 0, 0),
            second_range=MolecularFrameRange("after", 2, 2),
        )
        comparison = compare_molecular_frame_ranges(
            series,
            selection,
            m6_orientation_settings=_settings(),
        )
        outcome = M6DomainTypeAnalysisStore().analyze(
            adapt_m6_domain_type_analysis_source(
                comparison,
                frame_count=series.frame_count,
            ),
            classification_settings=M6DomainTypeClassificationSettings(
                orientation_tolerance_deg=5.0,
                bond_length_tolerance_mode="absolute_nm",
                bond_length_tolerance_value=0.5,
                minimum_observations_per_type=1,
            ),
        )
        classification = outcome.classification
        self.assertIsNotNone(classification)

        with tempfile.TemporaryDirectory() as tmpdir:
            destination = Path(tmpdir) / "comparison-package"
            export_analysis_package(
                series,
                AnalysisExportSettings(
                    scope="selected_ranges",
                    destination=destination,
                    package_format="directory",
                    include_tables=True,
                    include_spatial_grids=False,
                    include_plots=False,
                    frame_count=series.frame_count,
                    active_frame_index=series.active_frame_index,
                    source_view="raw",
                    use_segmentation_centroids=True,
                    intensity_metric="mean",
                    intensity_unit="a.u.",
                    background_inner_radius_px=1,
                    background_outer_radius_px=3,
                    density_grid_shape=(4, 4),
                    selected_ranges=selection,
                    m6_orientation_settings=_settings(),
                    m6_domain_type_classification=classification,
                    m6_domain_type_table_result=outcome.table_result,
                ),
                environment_provider=lambda: {},
            )
            _, range_rows = _read_csv_table(
                destination / "domain_type_ranges.csv"
            )
            _, comparison_rows = _read_csv_table(
                destination / "domain_type_comparison.csv"
            )
            manifest = json.loads(
                (destination / "manifest.json").read_text(encoding="utf-8")
            )

        expected_labels = [
            *(domain_type.label for domain_type in classification.domain_types),
            "Unclassified",
        ]
        self.assertEqual(
            [
                (row["condition_order"], row["domain_type_label"])
                for row in range_rows
            ],
            [
                *(("first", label) for label in expected_labels),
                *(("second", label) for label in expected_labels),
            ],
        )
        self.assertEqual(len(comparison_rows), len(classification.domain_types))
        self.assertTrue(
            all(row["direction"] == "second_minus_first" for row in comparison_rows)
        )
        for row in comparison_rows:
            self.assertEqual(
                int(row["domain_instance_count_delta"]),
                int(row["second_domain_instance_count"])
                - int(row["first_domain_instance_count"]),
            )
        domain_manifest = manifest["analysis"]["m6_domain_types"]
        self.assertEqual(domain_manifest["analysis_mode"], "compare_ranges")
        self.assertEqual(
            [entry["condition_order"] for entry in domain_manifest["ranges"]],
            ["first", "second"],
        )
        self.assertEqual(
            [entry["source_frame_indices"] for entry in domain_manifest["ranges"]],
            [[0], [2]],
        )

    def test_package_without_domain_types_writes_stable_empty_tables(self) -> None:
        series = _domain_export_series()

        with tempfile.TemporaryDirectory() as tmpdir:
            destination = Path(tmpdir) / "plain-package"
            export_analysis_package(
                series,
                AnalysisExportSettings(
                    scope="full_working_series",
                    destination=destination,
                    package_format="directory",
                    include_tables=True,
                    include_spatial_grids=False,
                    include_plots=False,
                    frame_count=series.frame_count,
                    active_frame_index=series.active_frame_index,
                    source_view="raw",
                    use_segmentation_centroids=True,
                    intensity_metric="mean",
                    intensity_unit="a.u.",
                    background_inner_radius_px=1,
                    background_outer_radius_px=3,
                    density_grid_shape=(4, 4),
                    m6_orientation_settings=_settings(),
                ),
                environment_provider=lambda: {},
            )
            type_fields, type_rows = _read_csv_table(
                destination / "domain_types.csv"
            )
            range_fields, range_rows = _read_csv_table(
                destination / "domain_type_ranges.csv"
            )
            comparison_fields, comparison_rows = _read_csv_table(
                destination / "domain_type_comparison.csv"
            )
            manifest = json.loads(
                (destination / "manifest.json").read_text(encoding="utf-8")
            )

        self.assertEqual(type_fields, _DOMAIN_TYPES_FIELDS)
        self.assertEqual(range_fields, _DOMAIN_TYPE_RANGES_FIELDS)
        self.assertEqual(comparison_fields, _DOMAIN_TYPE_COMPARISON_FIELDS)
        self.assertEqual(type_rows, [])
        self.assertEqual(range_rows, [])
        self.assertEqual(comparison_rows, [])
        domain_manifest = manifest["analysis"]["m6_domain_types"]
        self.assertFalse(domain_manifest["available"])
        self.assertEqual(
            domain_manifest["reason"],
            "domain_type_classification_not_available",
        )
        self.assertEqual(domain_manifest["ranges"], [])

    def test_single_range_domain_type_plots_are_headless_labeled_and_sized(self) -> None:
        series = _domain_export_series()
        outcome = self._analyze_domain_types(
            series,
            MolecularFrameRange("whole experiment", 0, 2),
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            result = export_m6_domain_type_plots(
                outcome.classification,
                outcome.table_result,
                tmpdir,
                dpi=100,
                size_inches=(4.0, 3.0),
            )
            generated = dict(result.generated)
            scatter_svg = generated["domain_type_scatter"][0].read_text(
                encoding="utf-8"
            )
            scatter_png_bytes = generated["domain_type_scatter"][1].read_bytes()
            shares_svg = generated["domain_type_shares"][0].read_text(
                encoding="utf-8"
            )
            png_bytes = generated["domain_type_shares"][1].read_bytes()

        self.assertEqual(
            tuple(generated),
            ("domain_type_scatter", "domain_type_shares"),
        )
        self.assertEqual(result.skipped, ())
        self.assertIn("M6 orientation [deg]", scatter_svg)
        self.assertIn("Median bond length [nm]", scatter_svg)
        self.assertIn("whole experiment", scatter_svg)
        for domain_type in outcome.classification.domain_types:
            expected_color = _rgb_hex(
                m6_domain_type_color(domain_type.domain_type_id)
            )
            self.assertIn(expected_color, scatter_svg.lower())
            self.assertIn(expected_color, shares_svg.lower())
        self.assertIn("Instances/frame", shares_svg)
        self.assertIn("Molecule fraction [%]", shares_svg)
        self.assertIn("Footprint fraction [%]", shares_svg)
        self.assertIn("whole experiment", shares_svg)
        self.assertEqual(png_bytes[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(scatter_png_bytes[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(
            (
                int.from_bytes(scatter_png_bytes[16:20], "big"),
                int.from_bytes(scatter_png_bytes[20:24], "big"),
            ),
            (400, 300),
        )
        self.assertEqual(
            (
                int.from_bytes(png_bytes[16:20], "big"),
                int.from_bytes(png_bytes[20:24], "big"),
            ),
            (400, 300),
        )

    def test_comparison_package_exports_two_series_domain_type_plots(self) -> None:
        series = _domain_export_series()
        selection = MolecularFrameRangeSelection(
            frame_count=series.frame_count,
            source_view="raw",
            first_range=MolecularFrameRange("before", 0, 0),
            second_range=MolecularFrameRange("after", 2, 2),
        )
        comparison = compare_molecular_frame_ranges(
            series,
            selection,
            m6_orientation_settings=_settings(),
        )
        outcome = M6DomainTypeAnalysisStore().analyze(
            adapt_m6_domain_type_analysis_source(
                comparison,
                frame_count=series.frame_count,
            ),
            classification_settings=M6DomainTypeClassificationSettings(
                orientation_tolerance_deg=5.0,
                bond_length_tolerance_mode="absolute_nm",
                bond_length_tolerance_value=0.5,
                minimum_observations_per_type=1,
            ),
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            destination = Path(tmpdir) / "comparison-plots-package"
            export_analysis_package(
                series,
                AnalysisExportSettings(
                    scope="selected_ranges",
                    destination=destination,
                    package_format="directory",
                    include_tables=True,
                    include_spatial_grids=False,
                    include_plots=True,
                    frame_count=series.frame_count,
                    active_frame_index=series.active_frame_index,
                    source_view="raw",
                    use_segmentation_centroids=True,
                    intensity_metric="mean",
                    intensity_unit="a.u.",
                    background_inner_radius_px=1,
                    background_outer_radius_px=3,
                    density_grid_shape=(4, 4),
                    selected_ranges=selection,
                    m6_orientation_settings=_settings(),
                    m6_domain_type_classification=outcome.classification,
                    m6_domain_type_table_result=outcome.table_result,
                ),
                environment_provider=lambda: {},
            )
            shares_svg = (
                destination / "plots" / "domain_type_shares.svg"
            ).read_text(encoding="utf-8")
            scatter_svg = (
                destination / "plots" / "domain_type_scatter.svg"
            ).read_text(encoding="utf-8")
            scatter_png_bytes = (
                destination / "plots" / "domain_type_scatter.png"
            ).read_bytes()
            manifest = json.loads(
                (destination / "manifest.json").read_text(encoding="utf-8")
            )

        self.assertIn("before", shares_svg)
        self.assertIn("after", shares_svg)
        self.assertIn("before", scatter_svg)
        self.assertIn("after", scatter_svg)
        scatter_legend_text = _svg_group_text(scatter_svg, "legend_1")
        self.assertIn("before", scatter_legend_text)
        self.assertIn("after", scatter_legend_text)
        for domain_type in outcome.classification.domain_types:
            self.assertIn(domain_type.label, scatter_svg)
            expected_color = _rgb_hex(
                m6_domain_type_color(domain_type.domain_type_id)
            )
            self.assertIn(expected_color, scatter_svg.lower())
            self.assertIn(expected_color, shares_svg.lower())
        self.assertIn(
            _rgb_hex(M6_DOMAIN_TYPE_UNCLASSIFIED_COLOR),
            scatter_svg.lower(),
        )
        self.assertEqual(
            (
                int.from_bytes(scatter_png_bytes[16:20], "big"),
                int.from_bytes(scatter_png_bytes[20:24], "big"),
            ),
            (1200, 900),
        )
        generated = {
            entry["kind"]: entry["files"] for entry in manifest["plots"]["generated"]
        }
        self.assertEqual(
            generated["domain_type_scatter"],
            [
                "plots/domain_type_scatter.svg",
                "plots/domain_type_scatter.png",
            ],
        )
        self.assertEqual(
            generated["domain_type_shares"],
            [
                "plots/domain_type_shares.svg",
                "plots/domain_type_shares.png",
            ],
        )

    def test_plot_manifest_reports_skipped_domain_type_plots_without_classification(self) -> None:
        series = _domain_export_series()
        selection = MolecularFrameRangeSelection(
            frame_count=series.frame_count,
            source_view="raw",
            first_range=MolecularFrameRange("before", 0, 0),
            second_range=MolecularFrameRange("after", 2, 2),
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            paths = export_selected_ranges_analysis_csv(
                series,
                selection,
                tmpdir,
                include_plots=True,
                m6_orientation_settings=_settings(),
            )
            manifest = json.loads(
                paths["manifest_json"].read_text(encoding="utf-8")
            )

        skipped = {
            entry["kind"]: entry["reason"] for entry in manifest["plots"]["skipped"]
        }
        self.assertEqual(
            skipped["domain_type_scatter"],
            "Domain type classification is not available.",
        )
        self.assertEqual(
            skipped["domain_type_shares"],
            "Domain type classification is not available.",
        )

    def test_selected_range_export_rejects_orphaned_domain_type_table(self) -> None:
        series = _domain_export_series()
        outcome = self._analyze_domain_types(
            series,
            MolecularFrameRange("whole experiment", 0, 2),
        )
        selection = MolecularFrameRangeSelection(
            frame_count=series.frame_count,
            source_view="raw",
            first_range=MolecularFrameRange("before", 0, 0),
            second_range=MolecularFrameRange("after", 2, 2),
        )

        with tempfile.TemporaryDirectory() as tmpdir, self.assertRaisesRegex(
            ValueError,
            "requires a classification",
        ):
            export_selected_ranges_analysis_csv(
                series,
                selection,
                tmpdir,
                m6_orientation_settings=_settings(),
                m6_domain_type_table_result=outcome.table_result,
            )

    def test_selected_ranges_join_uses_exact_range_and_component_identity(self) -> None:
        series = _domain_export_series()
        selection = MolecularFrameRangeSelection(
            frame_count=series.frame_count,
            source_view="raw",
            first_range=MolecularFrameRange("before", 0, 0),
            second_range=MolecularFrameRange("after", 2, 2),
        )
        comparison = compare_molecular_frame_ranges(
            series,
            selection,
            m6_orientation_settings=_settings(),
        )
        classification = M6DomainTypeAnalysisStore().analyze(
            adapt_m6_domain_type_analysis_source(
                comparison,
                frame_count=series.frame_count,
            ),
            classification_settings=M6DomainTypeClassificationSettings(
                orientation_tolerance_deg=5.0,
                bond_length_tolerance_mode="absolute_nm",
                bond_length_tolerance_value=0.5,
                minimum_observations_per_type=1,
            ),
        ).classification

        with tempfile.TemporaryDirectory() as tmpdir:
            paths = export_selected_ranges_analysis_csv(
                series,
                selection,
                tmpdir,
                m6_orientation_settings=_settings(),
                m6_domain_type_classification=classification,
            )
            with paths["domains_csv"].open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                rows = list(csv.DictReader(handle))

        self.assertTrue(rows)
        self.assertEqual(
            {row["condition_name"] for row in rows},
            {"before", "after"},
        )
        self.assertEqual(
            {row["condition_order"] for row in rows},
            {"first", "second"},
        )
        self.assertEqual(
            {
                (
                    row["domain_type_range_name"],
                    row["domain_type_range_start_frame"],
                    row["domain_type_range_end_frame"],
                )
                for row in rows
            },
            {("before", "0", "0"), ("after", "2", "2")},
        )
        self.assertTrue(all(row["domain_type_label"] for row in rows))

    def test_overlapping_ranges_keep_each_observation_identity_in_full_export(self) -> None:
        series = _domain_export_series()
        selection = MolecularFrameRangeSelection(
            frame_count=series.frame_count,
            source_view="raw",
            first_range=MolecularFrameRange("condition", 0, 2),
            second_range=MolecularFrameRange("condition", 1, 2),
        )
        comparison = compare_molecular_frame_ranges(
            series,
            selection,
            m6_orientation_settings=_settings(),
        )
        classification = M6DomainTypeAnalysisStore().analyze(
            adapt_m6_domain_type_analysis_source(
                comparison,
                frame_count=series.frame_count,
            ),
            classification_settings=M6DomainTypeClassificationSettings(
                orientation_tolerance_deg=5.0,
                bond_length_tolerance_mode="absolute_nm",
                bond_length_tolerance_value=0.5,
                minimum_observations_per_type=1,
            ),
        ).classification

        with tempfile.TemporaryDirectory() as tmpdir:
            paths = export_full_working_series_analysis_csv(
                series,
                tmpdir,
                m6_orientation_settings=_settings(),
                m6_domain_type_classification=classification,
            )
            with paths["domains_csv"].open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                rows = list(csv.DictReader(handle))

        overlapping_rows = [
            row for row in rows if row["working_frame_index"] == "2"
        ]
        observation_count = sum(
            observation.frame_index == 2
            for observation in classification.observations
        )
        self.assertEqual(len(overlapping_rows), observation_count)
        self.assertEqual(
            {row["domain_type_range_start_frame"] for row in overlapping_rows},
            {"0", "1"},
        )
        self.assertTrue(all(row["domain_type_label"] for row in overlapping_rows))

    def test_stale_domain_type_snapshot_does_not_assign_types_to_new_domains(self) -> None:
        original_series = _domain_export_series()
        classification = self._classify_domain_types(
            original_series,
            MolecularFrameRange("all domains", 0, 2),
        )
        shifted_series = _domain_export_series(x_offset_nm=1.0)

        with tempfile.TemporaryDirectory() as tmpdir:
            paths = export_full_working_series_analysis_csv(
                shifted_series,
                tmpdir,
                m6_orientation_settings=_settings(),
                m6_domain_type_classification=classification,
            )
            with paths["domains_csv"].open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                rows = list(csv.DictReader(handle))

        self.assertTrue(rows)
        self.assertTrue(
            all(row[field] == "" for row in rows for field in _DOMAIN_FIELDS[-7:])
        )

    def test_package_rejects_stale_domain_type_summary_snapshot(self) -> None:
        original_series = _domain_export_series()
        outcome = self._analyze_domain_types(
            original_series,
            MolecularFrameRange("all domains", 0, 2),
        )
        changed_series = _domain_export_series(x_offset_nm=1.0)

        with tempfile.TemporaryDirectory() as tmpdir:
            destination = Path(tmpdir) / "stale-domain-type-package"
            export_analysis_package(
                changed_series,
                AnalysisExportSettings(
                    scope="full_working_series",
                    destination=destination,
                    package_format="directory",
                    include_tables=True,
                    include_spatial_grids=False,
                    include_plots=False,
                    frame_count=changed_series.frame_count,
                    active_frame_index=changed_series.active_frame_index,
                    source_view="raw",
                    use_segmentation_centroids=True,
                    intensity_metric="mean",
                    intensity_unit="a.u.",
                    background_inner_radius_px=1,
                    background_outer_radius_px=3,
                    density_grid_shape=(4, 4),
                    m6_orientation_settings=_settings(),
                    m6_domain_type_classification=outcome.classification,
                    m6_domain_type_table_result=outcome.table_result,
                ),
                environment_provider=lambda: {},
            )
            _, type_rows = _read_csv_table(destination / "domain_types.csv")
            _, range_rows = _read_csv_table(
                destination / "domain_type_ranges.csv"
            )
            _, comparison_rows = _read_csv_table(
                destination / "domain_type_comparison.csv"
            )
            manifest = json.loads(
                (destination / "manifest.json").read_text(encoding="utf-8")
            )

        self.assertEqual(type_rows, [])
        self.assertEqual(range_rows, [])
        self.assertEqual(comparison_rows, [])
        domain_manifest = manifest["analysis"]["m6_domain_types"]
        self.assertFalse(domain_manifest["available"])
        self.assertEqual(
            domain_manifest["reason"],
            "domain_type_classification_not_available",
        )

    def test_package_refreshes_domain_type_range_denominators(self) -> None:
        original_series = _domain_export_series()
        outcome = self._analyze_domain_types(
            original_series,
            MolecularFrameRange("all domains", 0, 2),
        )
        changed_series = _domain_export_series()
        changed_series.molecular_detections.set_detections(
            1,
            (),
            source_view="raw",
            frame_shape=(72, 72),
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            destination = Path(tmpdir) / "refreshed-domain-type-package"
            export_analysis_package(
                changed_series,
                AnalysisExportSettings(
                    scope="full_working_series",
                    destination=destination,
                    package_format="directory",
                    include_tables=True,
                    include_spatial_grids=False,
                    include_plots=False,
                    frame_count=changed_series.frame_count,
                    active_frame_index=changed_series.active_frame_index,
                    source_view="raw",
                    use_segmentation_centroids=True,
                    intensity_metric="mean",
                    intensity_unit="a.u.",
                    background_inner_radius_px=1,
                    background_outer_radius_px=3,
                    density_grid_shape=(4, 4),
                    m6_orientation_settings=_settings(),
                    m6_domain_type_classification=outcome.classification,
                    m6_domain_type_table_result=outcome.table_result,
                ),
                environment_provider=lambda: {},
            )
            _, range_rows = _read_csv_table(
                destination / "domain_type_ranges.csv"
            )

        self.assertTrue(range_rows)
        self.assertEqual(
            {
                int(row["valid_representative_fraction_frame_count"])
                for row in range_rows
            },
            {2},
        )

    def test_current_frame_export_rejects_snapshot_stale_in_another_frame(self) -> None:
        original_series = _domain_export_series()
        classification = self._classify_domain_types(
            original_series,
            MolecularFrameRange("all domains", 0, 2),
        )
        changed_series = _domain_export_series(
            frame_x_offsets_nm=(0.0, 0.0, 1.0),
        )
        current_analysis = analyze_molecular_frame_range(
            changed_series,
            MolecularFrameRange("current", 0, 0),
            source_view="raw",
            m6_orientation_settings=_settings(),
        ).frame_results[0]

        with tempfile.TemporaryDirectory() as tmpdir:
            paths = export_current_frame_analysis_csv(
                changed_series,
                current_analysis,
                tmpdir,
                m6_domain_type_classification=classification,
            )
            with paths["domains_csv"].open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                rows = list(csv.DictReader(handle))

        self.assertTrue(rows)
        self.assertTrue(
            all(row[field] == "" for row in rows for field in _DOMAIN_FIELDS[-7:])
        )

    def test_molecule_fields_are_aligned_by_source_id_after_row_permutation(self) -> None:
        series = _series(frame_count=1)
        frame_analysis = analyze_molecular_frame_range(
            series,
            MolecularFrameRange("current", 0, 0),
            source_view="raw",
            m6_orientation_settings=_settings(),
        ).frame_results[0]
        original_rows = analysis_export_module._molecule_rows(
            series,
            frame_analysis.plot_data,
        )
        permuted_rows = original_rows[::2] + original_rows[1::2]

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(
                analysis_export_module,
                "_molecule_rows",
                return_value=permuted_rows,
            ):
                paths = export_current_frame_analysis_csv(
                    series,
                    frame_analysis,
                    tmpdir,
                )
            with paths["molecules_csv"].open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                rows = list(csv.DictReader(handle))

        self.assertEqual(
            [row["source_id"] for row in rows],
            [row["source_id"] for row in permuted_rows],
        )
        self.assertEqual(set(_M6_MOLECULE_FIELDS), set(rows[0]).intersection(_M6_MOLECULE_FIELDS))
        for row in rows:
            expected = _expected_m6_fields(frame_analysis, row["source_id"])
            for field_name, expected_value in expected.items():
                with self.subTest(source_id=row["source_id"], field=field_name):
                    if expected_value is None:
                        self.assertEqual(row[field_name], "")
                    elif isinstance(expected_value, float):
                        self.assertAlmostEqual(float(row[field_name]), expected_value)
                    else:
                        self.assertEqual(row[field_name], str(expected_value))

    def test_export_without_m6_keeps_new_columns_empty(self) -> None:
        series = _series(frame_count=1)
        frame_analysis = analyze_molecular_frame_range(
            series,
            MolecularFrameRange("current", 0, 0),
            source_view="raw",
        ).frame_results[0]

        with tempfile.TemporaryDirectory() as tmpdir:
            paths = export_current_frame_analysis_csv(series, frame_analysis, tmpdir)
            with paths["molecules_csv"].open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                rows = list(csv.DictReader(handle))
            with paths["frames_csv"].open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                frame_rows = list(csv.DictReader(handle))
            with paths["domains_csv"].open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                domain_reader = csv.DictReader(handle)
                domain_fields = tuple(domain_reader.fieldnames or ())
                domain_rows = list(domain_reader)

        self.assertTrue(rows)
        for row in rows:
            self.assertTrue(all(row[field_name] == "" for field_name in _M6_MOLECULE_FIELDS))
        self.assertEqual(domain_fields, _DOMAIN_FIELDS)
        self.assertEqual(domain_rows, [])
        self.assertEqual(frame_rows[0]["m6_analysis_availability_status"], "disabled")
        self.assertTrue(
            all(
                frame_rows[0][field_name] == ""
                for field_name in _M6_FRAME_FIELDS
                if field_name != "m6_analysis_availability_status"
            )
        )

    def test_legacy_m6_only_result_exports_old_fields_and_empty_m3_fields(self) -> None:
        series = _series(frame_count=1)
        frame_analysis = analyze_molecular_frame_range(
            series,
            MolecularFrameRange("legacy", 0, 0),
            source_view="raw",
            m6_orientation_settings=_settings(),
        ).frame_results[0]
        assert frame_analysis.m6_orientation_analysis is not None
        legacy_m6 = replace(
            frame_analysis.m6_orientation_analysis,
            local_multisymmetry_order=None,
            local_symmetry_evidence=None,
            local_symmetry_evidence_settings=None,
            lattice_domain_edge_compatibility=None,
            lattice_domain_seed_growth=None,
            lattice_domain_analysis=None,
            lattice_row_assignment_analysis=None,
        )
        legacy_frame = replace(
            frame_analysis,
            m6_orientation_analysis=legacy_m6,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            paths = export_current_frame_analysis_csv(series, legacy_frame, tmpdir)
            with paths["molecules_csv"].open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                rows = list(csv.DictReader(handle))

        self.assertTrue(any(row["q6"] for row in rows))
        self.assertTrue(all(row["q3"] == "" for row in rows))
        self.assertTrue(all(row["symmetry_best_model"] == "" for row in rows))

    def test_full_series_exports_domains_and_complete_frame_aggregates(self) -> None:
        series = _domain_export_series()
        captured_results = []

        with tempfile.TemporaryDirectory() as tmpdir:
            paths = export_full_working_series_analysis_csv(
                series,
                tmpdir,
                m6_orientation_settings=_settings(),
                analysis_results_callback=captured_results.extend,
            )
            with paths["domains_csv"].open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                domain_reader = csv.DictReader(handle)
                domain_fields = tuple(domain_reader.fieldnames or ())
                domain_rows = list(domain_reader)
            with paths["frames_csv"].open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                frame_reader = csv.DictReader(handle)
                frame_fields = tuple(frame_reader.fieldnames or ())
                frame_rows = list(frame_reader)
            with paths["lattice_domains_csv"].open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                lattice_rows = list(csv.DictReader(handle))

        self.assertEqual(len(captured_results), 3)
        self.assertEqual(
            [
                result.m6_orientation_analysis.frame_aggregates.full_domain_count
                for result in captured_results
            ],
            [2, 0, 1],
        )
        self.assertEqual(domain_fields, _DOMAIN_FIELDS)
        self.assertTrue(lattice_rows)
        self.assertTrue(
            {
                "lattice_domain_id",
                "dominant_symmetry",
                "core_size",
                "halo_size",
                "confidence",
                "seed_growth_result_fingerprint",
            }.issubset(lattice_rows[0])
        )
        self.assertTrue(all(row["lattice_domain_id"] for row in lattice_rows))
        self.assertTrue(set(_M6_FRAME_FIELDS).issubset(frame_fields))
        self.assertEqual(
            [
                (
                    int(row["working_frame_index"]),
                    int(row["ordered_component_id"]),
                    row["m6_orientation_domain_id"],
                )
                for row in domain_rows
            ],
            sorted(
                (
                    int(row["working_frame_index"]),
                    int(row["ordered_component_id"]),
                    row["m6_orientation_domain_id"],
                )
                for row in domain_rows
            ),
        )
        self.assertEqual(
            [
                sum(
                    int(row["working_frame_index"]) == index
                    for row in domain_rows
                )
                for index in range(3)
            ],
            [2, 0, 1],
        )

        for result, frame_row in zip(captured_results, frame_rows):
            m6 = result.m6_orientation_analysis
            assert m6 is not None
            aggregates = m6.frame_aggregates
            graph = m6.first_shell_graph
            footprint = aggregates.footprint_partition
            expected_frame_values = {
                field_name: getattr(aggregates, field_name)
                for field_name in _M6_FRAME_FIELDS
                if hasattr(aggregates, field_name)
            }
            expected_frame_values.update(
                {
                    "m6_analysis_availability_status": "available",
                    "m6_analysis_unavailability_reason": None,
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
            self.assertEqual(set(expected_frame_values), set(_M6_FRAME_FIELDS))
            for field_name, expected_value in expected_frame_values.items():
                with self.subTest(frame=result.frame_index, field=field_name):
                    _assert_csv_value(self, frame_row[field_name], expected_value)

            expected_components = {
                component.ordered_component_id: component
                for component in aggregates.domain_metrics.components
            }
            expected_footprints = {
                component.ordered_component_id: component
                for component in footprint.components
            }
            rows_for_frame = [
                row
                for row in domain_rows
                if int(row["working_frame_index"]) == result.frame_index
            ]
            for row in rows_for_frame:
                component = expected_components[int(row["ordered_component_id"])]
                component_footprint = expected_footprints[component.ordered_component_id]
                expected_domain_values = {
                    "m6_orientation_domain_id": component.m6_orientation_domain_id,
                    "component_type": component.component_type,
                    "molecule_count": component.molecule_count,
                    "molecule_fraction_of_valid_representatives": (
                        component.molecule_fraction_of_valid_representatives
                    ),
                    "footprint_area_nm2": component_footprint.footprint_area_nm2,
                    "footprint_fraction_of_valid_fov": (
                        component_footprint.footprint_fraction_of_valid_fov
                    ),
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
                    "edge_truncated": component_footprint.edge_truncated,
                    "insufficient_bonds_for_length_stats_qc": (
                        component.insufficient_bonds_for_length_stats_qc
                    ),
                    "bond_length_heterogeneity_qc": (
                        component.bond_length_heterogeneity_qc
                    ),
                    "footprint_disconnected_qc": (
                        component_footprint.footprint_disconnected_qc
                    ),
                    "coordinate_frame": m6.coordinate_frame,
                    "orientation_reference": m6.orientation_reference,
                    "spatial_calibration_fingerprint": m6.spatial_calibration_fingerprint,
                    "registration_fingerprint": m6.registration_fingerprint,
                    "point_coordinate_fingerprint": graph.point_coordinate_fingerprint,
                }
                for field_name, expected_value in expected_domain_values.items():
                    with self.subTest(
                        frame=result.frame_index,
                        component=component.ordered_component_id,
                        field=field_name,
                    ):
                        _assert_csv_value(self, row[field_name], expected_value)

    def test_manifest_records_m6_reproducibility_and_injected_environment(self) -> None:
        series = _series(frame_count=2)
        selection = MolecularFrameRangeSelection(
            frame_count=2,
            source_view="raw",
            first_range=MolecularFrameRange("before", 0, 0),
            second_range=MolecularFrameRange("after", 1, 1),
        )
        settings = _settings()
        environment = {
            "moltrack_version": "test-moltrack",
            "git_commit": None,
            "git_dirty": None,
            "python_version": "3.test",
            "numpy_version": "numpy-test",
            "scipy_version": "scipy-test",
            "qhull_version": None,
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            paths = export_selected_ranges_analysis_csv(
                series,
                selection,
                tmpdir,
                m6_orientation_settings=settings,
                environment_provider=lambda: environment,
            )
            manifest = json.loads(paths["manifest_json"].read_text(encoding="utf-8"))

        self.assertEqual(manifest["environment"], environment)
        m6_manifest = manifest["analysis"]["m6_orientation"]
        self.assertTrue(m6_manifest["enabled"])
        self.assertEqual(m6_manifest["algorithm_version"], M6_ORIENTATION_ALGORITHM_VERSION)
        self.assertEqual(m6_manifest["settings"], settings.to_dict())
        self.assertEqual(m6_manifest["symmetry_m"], 6)
        self.assertEqual(m6_manifest["bond_weighting"], "uniform")
        multisymmetry_manifest = m6_manifest["local_multisymmetry"]
        self.assertTrue(multisymmetry_manifest["enabled"])
        self.assertEqual(multisymmetry_manifest["symmetry_channels"], [3, 6])
        self.assertEqual(
            multisymmetry_manifest["bond_order_schema_version"],
            LOCAL_MULTI_SYMMETRY_BOND_ORDER_SCHEMA_VERSION,
        )
        self.assertEqual(
            multisymmetry_manifest["evidence_algorithm_version"],
            LOCAL_SYMMETRY_EVIDENCE_ALGORITHM_VERSION,
        )
        self.assertEqual(
            multisymmetry_manifest["evidence_schema_version"],
            LOCAL_SYMMETRY_EVIDENCE_SCHEMA_VERSION,
        )
        self.assertEqual(
            m6_manifest["duplicate_policy"]["representative"],
            settings.duplicate_policy,
        )
        self.assertEqual(
            m6_manifest["delaunay_policy"]["degeneracy"],
            settings.delaunay_degeneracy_policy,
        )
        self.assertEqual(
            m6_manifest["pair_correlation"]["bin_width_nm"],
            settings.gr_bin_width_nm,
        )
        self.assertEqual(
            m6_manifest["coordinate_convention"]["coordinate_frame"],
            "sample_nm",
        )
        self.assertEqual(
            m6_manifest["coordinate_convention"]["analysis_coordinate_context"],
            "native",
        )
        self.assertNotIn("construction_method", m6_manifest)
        self.assertEqual(len(m6_manifest["frame_results"]), 2)
        for frame_result in m6_manifest["frame_results"]:
            self.assertIn("construction_method", frame_result)
            self.assertEqual(frame_result["availability_status"], "available")
            self.assertTrue(frame_result["cache_fingerprints"]["settings"])
            self.assertTrue(frame_result["cache_fingerprints"]["point_coordinates"])
            self.assertTrue(frame_result["cache_fingerprints"]["annotations"])
            self.assertTrue(frame_result["cache_fingerprints"]["sample_geometry"])
            self.assertTrue(frame_result["cache_fingerprints"]["valid_fov"])
            self.assertTrue(
                frame_result["cache_fingerprints"]["multisymmetry_settings"]
            )
            self.assertTrue(
                frame_result["cache_fingerprints"]["symmetry_evidence_settings"]
            )
            self.assertTrue(
                frame_result["cache_fingerprints"]["symmetry_bond_evidence"]
            )
            self.assertEqual(
                frame_result["cache_key"]["settings_hash"],
                frame_result["cache_fingerprints"]["settings"],
            )

    def test_current_frame_package_runs_requested_m6_and_records_its_result(self) -> None:
        series = _series(frame_count=1)
        m6_settings = _settings()
        environment = {
            "moltrack_version": "package-test",
            "python_version": "3.test",
            "numpy_version": "numpy-test",
            "scipy_version": None,
            "qhull_version": None,
            "git_commit": "abc123",
            "git_dirty": False,
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            destination = Path(tmpdir) / "analysis-package"
            export_analysis_package(
                series,
                AnalysisExportSettings(
                    scope="current_frame",
                    destination=destination,
                    package_format="directory",
                    include_tables=True,
                    include_spatial_grids=False,
                    include_plots=False,
                    frame_count=1,
                    active_frame_index=0,
                    source_view="raw",
                    use_segmentation_centroids=True,
                    intensity_metric="mean",
                    intensity_unit="a.u.",
                    background_inner_radius_px=1,
                    background_outer_radius_px=3,
                    density_grid_shape=(4, 4),
                    m6_orientation_settings=m6_settings,
                ),
                environment_provider=lambda: environment,
            )
            with (destination / "molecules.csv").open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                rows = list(csv.DictReader(handle))
            manifest = json.loads(
                (destination / "manifest.json").read_text(encoding="utf-8")
            )

        self.assertTrue(any(row["q6"] for row in rows))
        self.assertTrue(all(row["coordinate_frame"] == "sample_nm" for row in rows))
        self.assertEqual(manifest["environment"], environment)
        self.assertEqual(manifest["analysis"]["analysis_coordinate_context"], "native")
        m6_manifest = manifest["analysis"]["m6_orientation"]
        self.assertEqual(m6_manifest["settings"], m6_settings.to_dict())
        self.assertEqual(len(m6_manifest["frame_results"]), 1)
        self.assertEqual(
            m6_manifest["frame_results"][0]["availability_status"],
            "available",
        )

    def test_full_working_series_package_records_each_m6_cache_identity(self) -> None:
        series = _series(frame_count=2)
        m6_settings = _settings()

        with tempfile.TemporaryDirectory() as tmpdir:
            destination = Path(tmpdir) / "full-analysis-package"
            export_analysis_package(
                series,
                AnalysisExportSettings(
                    scope="full_working_series",
                    destination=destination,
                    package_format="directory",
                    include_tables=True,
                    include_spatial_grids=False,
                    include_plots=False,
                    frame_count=2,
                    active_frame_index=0,
                    source_view="raw",
                    use_segmentation_centroids=True,
                    intensity_metric="mean",
                    intensity_unit="a.u.",
                    background_inner_radius_px=1,
                    background_outer_radius_px=3,
                    density_grid_shape=(4, 4),
                    m6_orientation_settings=m6_settings,
                ),
                environment_provider=lambda: {},
            )
            manifest = json.loads(
                (destination / "manifest.json").read_text(encoding="utf-8")
            )

        frame_results = manifest["analysis"]["m6_orientation"]["frame_results"]
        self.assertEqual(len(frame_results), 2)
        self.assertEqual(
            [entry["working_frame_index"] for entry in frame_results],
            [0, 1],
        )
        self.assertTrue(all(entry["construction_method"] for entry in frame_results))
        self.assertTrue(
            all(entry["cache_key"]["annotation_fingerprint"] for entry in frame_results)
        )
        self.assertTrue(all(entry["cache_key"]["valid_fov_fingerprint"] for entry in frame_results))
        self.assertIsNone(manifest["environment"]["qhull_version"])
        self.assertIsNone(manifest["environment"]["git_commit"])

    def test_git_dirty_includes_untracked_files(self) -> None:
        calls = []

        def fake_run_git(_root, *arguments):
            calls.append(arguments)
            return "abc123" if arguments[0] == "rev-parse" else "?? new_file.py"

        with patch.object(analysis_environment_module, "_run_git", side_effect=fake_run_git):
            commit, dirty = analysis_environment_module._git_environment()

        self.assertEqual(commit, "abc123")
        self.assertTrue(dirty)
        self.assertEqual(calls[1], ("status", "--porcelain"))


if __name__ == "__main__":
    unittest.main()
