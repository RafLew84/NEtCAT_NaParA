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

        self.assertTrue(rows)
        for row in rows:
            self.assertTrue(all(row[field_name] == "" for field_name in _M6_MOLECULE_FIELDS))

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
