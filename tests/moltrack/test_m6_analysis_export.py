import csv
import json
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from moltrack.analysis import (
    M6_ORIENTATION_ALGORITHM_VERSION,
    MolecularFrameRange,
    MolecularFrameRangeSelection,
    MolecularM6OrientationAnalysisSettings,
    analyze_molecular_frame_range,
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
from nanotrack.core import STMSequenceMetadata


_M6_MOLECULE_FIELDS = (
    "neighbor_count",
    "psi6_real",
    "psi6_imag",
    "q6",
    "lattice_orientation_deg",
    "orientation_status",
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
    "spatial_calibration_fingerprint",
    "registration_fingerprint",
    "point_coordinate_fingerprint",
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


def _domain_export_series() -> MolTrackImageSeries:
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
        detections.set_detections(
            frame_index,
            [
                MolecularDetection(
                    frame_index,
                    (x - 0.2, frame_size - y - 0.2, x + 0.2, frame_size - y + 0.2),
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
    local_index = local.source_ids.index(source_id)
    segmentation_index = segmentation.source_ids.index(source_id)
    graph_index = graph.point_ids.index(source_id)
    psi6 = local.psi6[local_index]
    ordered_component_id = segmentation.ordered_component_id[segmentation_index]
    domain_id = segmentation.m6_orientation_domain_id[segmentation_index]
    return {
        "neighbor_count": local.neighbor_count[local_index],
        "psi6_real": None if psi6 is None else psi6.real,
        "psi6_imag": None if psi6 is None else psi6.imag,
        "q6": local.q6[local_index],
        "lattice_orientation_deg": local.lattice_orientation_deg[local_index],
        "orientation_status": local.orientation_status[local_index],
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


class M6AnalysisExportTests(unittest.TestCase):
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

        self.assertEqual(len(captured_results), 3)
        self.assertEqual(
            [
                result.m6_orientation_analysis.frame_aggregates.full_domain_count
                for result in captured_results
            ],
            [2, 0, 1],
        )
        self.assertEqual(domain_fields, _DOMAIN_FIELDS)
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
