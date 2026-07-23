import csv
import hashlib
import json
import tempfile
import unittest
import zipfile
from dataclasses import FrozenInstanceError
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from moltrack.analysis import (
    MolecularFrameRange,
    MolecularFrameRangeSelection,
    MolecularOrientationMeasurement,
    MolecularOrientationProvenance,
    MolecularOrientationStore,
    analyze_molecular_frame_range,
    build_molecular_position_plot_data,
)
from moltrack.core import (
    MolTrackRegistrationFrameResult,
    MolTrackRegistrationResultSet,
    MolTrackRegistrationSettings,
    MolecularDetection,
    MolecularDetectionSet,
    MolecularSegmentation,
    MolecularSegmentationSet,
    MolTrackImageSeries,
    build_molecular_centroids,
)
from moltrack.persistence import (
    AnalysisExportProgress,
    AnalysisExportSettings,
    export_analysis_package,
    export_current_frame_analysis_csv,
    export_current_frame_molecules_csv,
    export_full_working_series_analysis_csv,
    export_selected_ranges_analysis_package,
    export_selected_ranges_analysis_csv,
)
from nanotrack.core import STMSequenceMetadata


class MolTrackAnalysisExportTests(unittest.TestCase):
    @staticmethod
    def _build_selected_ranges_fixture():
        detections = MolecularDetectionSet(frame_count=2)
        detections.set_detections(
            0,
            [
                MolecularDetection(0, (0, 0, 2, 2), 0.9, detection_id="before-a"),
                MolecularDetection(0, (2, 0, 4, 2), 0.8, detection_id="before-b"),
            ],
            source_view="raw",
            frame_shape=(8, 8),
        )
        detections.set_detections(
            1,
            [
                MolecularDetection(1, (0, 0, 2, 2), 0.9, detection_id="after-a"),
                MolecularDetection(1, (3, 0, 5, 2), 0.8, detection_id="after-b"),
                MolecularDetection(1, (0, 3, 2, 5), 0.7, detection_id="after-c"),
                MolecularDetection(1, (3, 3, 5, 5), 0.6, detection_id="after-d"),
            ],
            source_view="raw",
            frame_shape=(8, 8),
        )
        frames = np.empty((2, 8, 8), dtype=np.float32)
        frames[0].fill(2.0)
        frames[1].fill(6.0)
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames,
            metadata=STMSequenceMetadata(pixels_x=8, pixels_y=8),
            molecular_detections=detections,
        )
        selection = MolecularFrameRangeSelection(
            frame_count=2,
            source_view="raw",
            first_range=MolecularFrameRange("before desorption", 0, 0),
            second_range=MolecularFrameRange("after adsorption", 1, 1),
        )
        return series, selection

    def test_selected_ranges_export_assigns_conditions_and_writes_range_aggregates(self) -> None:
        series, selection = self._build_selected_ranges_fixture()

        with tempfile.TemporaryDirectory() as tmpdir:
            paths = export_selected_ranges_analysis_csv(
                series,
                selection,
                tmpdir,
                intensity_metric="mean",
            )
            with paths["molecules_csv"].open("r", encoding="utf-8", newline="") as handle:
                molecule_rows = list(csv.DictReader(handle))
            with paths["frames_csv"].open("r", encoding="utf-8", newline="") as handle:
                frame_rows = list(csv.DictReader(handle))
            with paths["ranges_csv"].open("r", encoding="utf-8", newline="") as handle:
                range_rows = list(csv.DictReader(handle))

        self.assertEqual(
            [row["condition_name"] for row in molecule_rows],
            ["before desorption"] * 2 + ["after adsorption"] * 4,
        )
        self.assertEqual(
            [row["condition_name"] for row in frame_rows],
            ["before desorption", "after adsorption"],
        )
        self.assertEqual(
            [row["condition_name"] for row in range_rows],
            ["before desorption", "after adsorption"],
        )
        self.assertEqual(
            [row["condition_order"] for row in range_rows],
            ["first", "second"],
        )
        self.assertEqual(
            [row["start_frame_index"] for row in range_rows],
            ["0", "1"],
        )
        self.assertEqual(
            [row["end_frame_index"] for row in range_rows],
            ["0", "1"],
        )
        self.assertEqual(
            [row["total_molecule_count"] for row in range_rows],
            ["2", "4"],
        )
        self.assertEqual(
            [row["mean_molecule_count"] for row in range_rows],
            ["2.0", "4.0"],
        )
        self.assertEqual(
            [row["mean_nearest_neighbor_distance"] for row in range_rows],
            ["2.0", "3.0"],
        )
        self.assertAlmostEqual(float(range_rows[0]["mean_line_order_score"]), 1.0)
        self.assertAlmostEqual(float(range_rows[1]["mean_line_order_score"]), 0.0)
        self.assertEqual(
            [row["mean_intensity"] for row in range_rows],
            ["2.0", "6.0"],
        )
        self.assertEqual(
            [row["median_intensity"] for row in range_rows],
            ["2.0", "6.0"],
        )

    def test_selected_ranges_export_writes_second_minus_first_comparison(self) -> None:
        series, selection = self._build_selected_ranges_fixture()

        with tempfile.TemporaryDirectory() as tmpdir:
            paths = export_selected_ranges_analysis_csv(
                series,
                selection,
                tmpdir,
                intensity_metric="mean",
            )
            with paths["comparison_csv"].open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                rows = list(csv.DictReader(handle))

        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["direction"], "second_minus_first")
        self.assertEqual(row["first_condition_name"], "before desorption")
        self.assertEqual(row["second_condition_name"], "after adsorption")
        self.assertEqual(row["source_view"], "raw")
        self.assertEqual(
            row["analysis_mode"],
            "frame_position_distributions_without_tracking",
        )
        self.assertEqual(row["uses_tracking"], "false")
        self.assertEqual(row["nearest_neighbor_distance_unit"], "px")
        self.assertEqual(row["intensity_metric"], "mean")
        self.assertEqual(row["intensity_unit"], "a.u.")
        self.assertEqual(row["mean_molecule_count_delta"], "2.0")
        self.assertEqual(row["mean_nearest_neighbor_distance_delta"], "1.0")
        self.assertAlmostEqual(float(row["mean_line_order_score_delta"]), -1.0)
        self.assertEqual(row["mean_intensity_delta"], "4.0")
        self.assertEqual(row["median_intensity_delta"], "4.0")

    def test_selected_ranges_export_leaves_unavailable_deltas_empty(self) -> None:
        detections = MolecularDetectionSet(frame_count=2)
        detections.set_detections(
            0,
            [MolecularDetection(0, (1, 1, 3, 3), 0.9, detection_id="only-one")],
            source_view="raw",
            frame_shape=(5, 5),
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.full((2, 5, 5), np.nan, dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=5, pixels_y=5),
            molecular_detections=detections,
        )
        selection = MolecularFrameRangeSelection(
            frame_count=2,
            source_view="raw",
            first_range=MolecularFrameRange("before", 0, 0),
            second_range=MolecularFrameRange("after", 1, 1),
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            paths = export_selected_ranges_analysis_csv(
                series,
                selection,
                tmpdir,
                intensity_metric="mean",
            )
            with paths["comparison_csv"].open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                row = next(csv.DictReader(handle))

        self.assertEqual(row["mean_molecule_count_delta"], "-1.0")
        self.assertEqual(row["mean_nearest_neighbor_distance_delta"], "")
        self.assertEqual(row["mean_line_order_score_delta"], "")
        self.assertEqual(row["mean_intensity_delta"], "")
        self.assertEqual(row["median_intensity_delta"], "")
        self.assertEqual(row["uses_tracking"], "false")

    def test_selected_ranges_export_writes_shared_spatial_bins_in_row_major_order(self) -> None:
        series, selection = self._build_selected_ranges_fixture()

        with tempfile.TemporaryDirectory() as tmpdir:
            paths = export_selected_ranges_analysis_csv(
                series,
                selection,
                tmpdir,
                intensity_metric="mean",
                density_grid_shape=(2, 2),
            )
            with paths["spatial_bins_csv"].open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                rows = list(csv.DictReader(handle))

        self.assertEqual(len(rows), 8)
        self.assertEqual(
            [
                (row["condition_order"], row["condition_name"], row["row"], row["column"])
                for row in rows
            ],
            [
                (condition_order, condition_name, str(row), str(column))
                for condition_order, condition_name in (
                    ("first", "before desorption"),
                    ("second", "after adsorption"),
                )
                for row in range(2)
                for column in range(2)
            ],
        )
        expected_bounds = [
            ("0.0", "4.0", "0.0", "4.0"),
            ("4.0", "8.0", "0.0", "4.0"),
            ("0.0", "4.0", "4.0", "8.0"),
            ("4.0", "8.0", "4.0", "8.0"),
        ]
        for condition_rows in (rows[:4], rows[4:]):
            self.assertEqual(
                [
                    (row["x_min"], row["x_max"], row["y_min"], row["y_max"])
                    for row in condition_rows
                ],
                expected_bounds,
            )
        self.assertTrue(all(row["position_unit"] == "px" for row in rows))
        self.assertTrue(
            all(row["density_unit"] == "molecules_per_frame_per_bin" for row in rows)
        )
        self.assertEqual(
            [row["molecules_per_frame"] for row in rows],
            ["2.0", "0.0", "0.0", "0.0", "1.0", "1.0", "1.0", "1.0"],
        )
        self.assertEqual(
            [row["mean_intensity"] for row in rows],
            ["2.0", "", "", "", "6.0", "6.0", "6.0", "6.0"],
        )
        self.assertTrue(all(row["intensity_metric"] == "mean" for row in rows))
        self.assertTrue(all(row["intensity_unit"] == "a.u." for row in rows))

    def test_selected_ranges_export_writes_versioned_manifest_with_relative_file_counts(self) -> None:
        series, selection = self._build_selected_ranges_fixture()

        with tempfile.TemporaryDirectory() as tmpdir:
            paths = export_selected_ranges_analysis_csv(
                series,
                selection,
                Path(tmpdir) / "portable-analysis",
                intensity_metric="mean",
                density_grid_shape=(2, 2),
            )
            with paths["manifest_json"].open("r", encoding="utf-8") as handle:
                manifest = json.load(handle)

        self.assertEqual(manifest["export_schema_version"], 6)
        created_at = datetime.fromisoformat(manifest["created_at_utc"])
        self.assertIsNotNone(created_at.tzinfo)
        self.assertEqual(created_at.utcoffset().total_seconds(), 0.0)
        self.assertEqual(manifest["application"]["name"], "MolTrack")
        self.assertEqual(manifest["application"]["version"], "0.1.0")
        self.assertEqual(
            manifest["files"],
            [
                {"path": "molecules.csv", "record_count": 6},
                {"path": "frames.csv", "record_count": 2},
                {"path": "domains.csv", "record_count": 0},
                {"path": "lattice_domains.csv", "record_count": 0},
                {"path": "ranges.csv", "record_count": 2},
                {"path": "comparison.csv", "record_count": 1},
                {"path": "spatial_bins.csv", "record_count": 8},
                {"path": "domain_types.csv", "record_count": 0},
                {"path": "domain_type_ranges.csv", "record_count": 0},
                {"path": "domain_type_comparison.csv", "record_count": 0},
            ],
        )
        self.assertTrue(
            all(not Path(file_info["path"]).is_absolute() for file_info in manifest["files"])
        )

    def test_selected_ranges_manifest_identifies_source_and_stm_metadata(self) -> None:
        series, selection = self._build_selected_ranges_fixture()
        source_bytes = b"controlled MPP source"
        series.metadata = STMSequenceMetadata(
            pixels_x=8,
            pixels_y=8,
            size_nm_x=16.0,
            size_nm_y=8.0,
            offset_nm_x=1.5,
            offset_nm_y=-2.0,
            scan_angle_deg=30.0,
            bias_v=1.2,
            setpoint_a=2.5e-10,
            image_type="STM topography",
            frame_interval_s=0.5,
            frame_times_s=np.asarray([0.0, 0.5]),
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source_path = root / "input" / "movie.mpp"
            source_path.parent.mkdir()
            source_path.write_bytes(source_bytes)
            series.source_path = str(source_path)
            destination = root / "portable-analysis"
            paths = export_selected_ranges_analysis_csv(
                series,
                selection,
                destination,
                intensity_metric="mean",
                density_grid_shape=(2, 2),
            )
            with paths["manifest_json"].open("r", encoding="utf-8") as handle:
                manifest = json.load(handle)
            source_stat = source_path.stat()

        self.assertEqual(
            manifest["source"],
            {
                "format": "MPP",
                "path": "../input/movie.mpp",
                "file_name": "movie.mpp",
                "size_bytes": len(source_bytes),
                "modified_time_ns": source_stat.st_mtime_ns,
                "integrity": {
                    "algorithm": "sha256",
                    "value": hashlib.sha256(source_bytes).hexdigest(),
                },
            },
        )
        self.assertEqual(
            manifest["stm_metadata"],
            {
                "pixels": {"x": 8, "y": 8},
                "size_nm": {"x": 16.0, "y": 8.0},
                "pixel_size_nm": {"x": 2.0, "y": 1.0},
                "offset_nm": {"x": 1.5, "y": -2.0},
                "scan_angle_deg": 30.0,
                "bias_v": 1.2,
                "setpoint_a": 2.5e-10,
                "image_type": "STM topography",
                "frame_interval_s": 0.5,
                "frame_times_s": [0.0, 0.5],
            },
        )
        self.assertNotIn(str(destination.resolve()), json.dumps(manifest))

    def test_selected_ranges_manifest_records_reproducible_registered_analysis_settings(self) -> None:
        series, _selection = self._build_selected_ranges_fixture()
        registration_settings = MolTrackRegistrationSettings(
            backend="optical_flow_median",
            backend_params={"winsize": 21, "levels": 4},
        )
        series.registration_results = MolTrackRegistrationResultSet(
            settings=registration_settings,
            reference_frame_index=0,
            results_by_frame={
                0: MolTrackRegistrationFrameResult(0, (0.0, 0.0), "optical_flow_median"),
                1: MolTrackRegistrationFrameResult(1, (2.0, -1.0), "optical_flow_median"),
            },
        )
        series.expanded_aligned_stack = SimpleNamespace(
            frames=np.zeros((2, 10, 12), dtype=np.float32),
            metadata=STMSequenceMetadata(
                pixels_x=12,
                pixels_y=10,
                size_nm_x=24.0,
                size_nm_y=10.0,
            ),
            canvas_offset_xy=(2.0, 1.0),
            padding_ltrb=(2, 1, 2, 1),
            frame_origins_xy=np.asarray(((2.0, 1.0), (0.0, 2.0))),
        )
        selection = MolecularFrameRangeSelection(
            frame_count=2,
            source_view="expanded_aligned",
            first_range=MolecularFrameRange("before desorption", 0, 0),
            second_range=MolecularFrameRange("after adsorption", 1, 1),
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            paths = export_selected_ranges_analysis_csv(
                series,
                selection,
                tmpdir,
                use_segmentation_centroids=False,
                intensity_metric="median",
                intensity_unit="nA",
                background_inner_radius_px=2,
                background_outer_radius_px=5,
                density_grid_shape=(3, 4),
            )
            with paths["manifest_json"].open("r", encoding="utf-8") as handle:
                manifest = json.load(handle)

        self.assertEqual(
            manifest["working_series"],
            {
                "frame_count": 2,
                "source_frame_indices": [0, 1],
                "reverse_frame_order": False,
            },
        )
        self.assertEqual(
            manifest["ranges"],
            [
                {
                    "condition_order": "first",
                    "condition_name": "before desorption",
                    "start_frame_index": 0,
                    "start_frame_number": 1,
                    "end_frame_index": 0,
                    "end_frame_number": 1,
                },
                {
                    "condition_order": "second",
                    "condition_name": "after adsorption",
                    "start_frame_index": 1,
                    "start_frame_number": 2,
                    "end_frame_index": 1,
                    "end_frame_number": 2,
                },
            ],
        )
        analysis_manifest = dict(manifest["analysis"])
        m6_manifest = analysis_manifest.pop("m6_orientation")
        domain_type_manifest = analysis_manifest.pop("m6_domain_types")
        self.assertFalse(m6_manifest["enabled"])
        self.assertIsNone(m6_manifest["settings"])
        self.assertEqual(
            [entry["availability_status"] for entry in m6_manifest["frame_results"]],
            ["disabled", "disabled"],
        )
        self.assertFalse(domain_type_manifest["available"])
        self.assertFalse(domain_type_manifest["uses_tracking"])
        self.assertEqual(domain_type_manifest["ranges"], [])
        self.assertEqual(
            analysis_manifest,
            {
                "analysis_mode": "frame_position_distributions_without_tracking",
                "uses_tracking": False,
                "source_view": "expanded_aligned",
                "analysis_coordinate_context": "registered",
                "centroid_mode": "bbox_centers",
                "density_grid_shape": {"rows": 3, "columns": 4},
                "intensity": {
                    "metric": "median",
                    "unit": "nA",
                    "background_inner_radius_px": 2,
                    "background_outer_radius_px": 5,
                },
                "coordinate_system": {
                    "convention": "image_xy_x_right_y_down",
                    "origin": "reference_raw_frame_top_left",
                    "position_unit": "nm",
                    "expanded_canvas_offset_px": {"x": 2.0, "y": 1.0},
                    "padding_ltrb": [2, 1, 2, 1],
                    "frame_origins_xy": [[2.0, 1.0], [0.0, 2.0]],
                },
            },
        )
        self.assertEqual(
            manifest["registration"],
            {
                "available": True,
                "backend": "optical_flow_median",
                "reference_strategy": "adjacent",
                "registration_view": "raw",
                "backend_params": {"winsize": 21, "levels": 4},
                "reference_frame_index": 0,
            },
        )

    def test_selected_ranges_export_renders_current_frame_as_labeled_svg_and_sized_png(self) -> None:
        series, selection = self._build_selected_ranges_fixture()

        with tempfile.TemporaryDirectory() as tmpdir:
            paths = export_selected_ranges_analysis_csv(
                series,
                selection,
                tmpdir,
                intensity_metric="mean",
                density_grid_shape=(2, 2),
                include_plots=True,
                plot_dpi=100,
                plot_size_inches=(4.0, 3.0),
            )
            svg_path = paths["plots_dir"] / "current_frame_positions.svg"
            png_path = paths["plots_dir"] / "current_frame_positions.png"
            svg_text = svg_path.read_text(encoding="utf-8")
            png_bytes = png_path.read_bytes()

        self.assertGreater(len(svg_text), 100)
        self.assertGreater(len(png_bytes), 100)
        self.assertEqual(png_bytes[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(
            (
                int.from_bytes(png_bytes[16:20], "big"),
                int.from_bytes(png_bytes[20:24], "big"),
            ),
            (400, 300),
        )
        self.assertIn("Current frame positions - frame 1", svg_text)
        self.assertIn("x [px]", svg_text)
        self.assertIn("y [px]", svg_text)
        self.assertIn("Molecules", svg_text)

    def test_selected_ranges_export_renders_all_available_analysis_plots(self) -> None:
        series, selection = self._build_selected_ranges_fixture()

        with tempfile.TemporaryDirectory() as tmpdir:
            paths = export_selected_ranges_analysis_csv(
                series,
                selection,
                tmpdir,
                intensity_metric="mean",
                density_grid_shape=(2, 2),
                include_plots=True,
                plot_dpi=100,
                plot_size_inches=(4.0, 3.0),
            )
            plot_files = {
                path.name: path.read_bytes()
                for path in paths["plots_dir"].iterdir()
                if path.is_file()
            }

        expected_stems = (
            "current_frame_positions",
            "range_trends",
            "spatial_comparison",
            "density_maps",
            "intensity_maps",
        )
        self.assertEqual(
            set(plot_files),
            {f"{stem}.{extension}" for stem in expected_stems for extension in ("svg", "png")},
        )
        for stem in expected_stems:
            png_bytes = plot_files[f"{stem}.png"]
            self.assertEqual(
                (
                    int.from_bytes(png_bytes[16:20], "big"),
                    int.from_bytes(png_bytes[20:24], "big"),
                ),
                (400, 300),
            )
        svg_text = {
            stem: plot_files[f"{stem}.svg"].decode("utf-8")
            for stem in expected_stems
        }
        self.assertIn("Range trends", svg_text["range_trends"])
        self.assertIn("Working frame number", svg_text["range_trends"])
        self.assertIn("Mean intensity [a.u.]", svg_text["range_trends"])
        self.assertIn("before desorption", svg_text["range_trends"])
        self.assertIn("after adsorption", svg_text["range_trends"])
        self.assertIn("Spatial comparison", svg_text["spatial_comparison"])
        self.assertIn("x [px]", svg_text["spatial_comparison"])
        self.assertIn("Density maps", svg_text["density_maps"])
        self.assertIn("Molecules per frame per bin", svg_text["density_maps"])
        self.assertIn("Mean intensity maps - mean", svg_text["intensity_maps"])
        self.assertIn("Mean intensity [a.u.]", svg_text["intensity_maps"])

    def test_selected_ranges_plot_export_skips_missing_intensity_and_preserves_csv_tables(self) -> None:
        series, selection = self._build_selected_ranges_fixture()
        series.raw_frames.fill(np.nan)

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            without_plots = export_selected_ranges_analysis_csv(
                series,
                selection,
                root / "without-plots",
                intensity_metric="mean",
                density_grid_shape=(2, 2),
            )
            with_plots = export_selected_ranges_analysis_csv(
                series,
                selection,
                root / "with-plots",
                intensity_metric="mean",
                density_grid_shape=(2, 2),
                include_plots=True,
                plot_dpi=100,
                plot_size_inches=(4.0, 3.0),
            )
            table_names = (
                "molecules_csv",
                "frames_csv",
                "ranges_csv",
                "comparison_csv",
                "spatial_bins_csv",
            )
            table_pairs = [
                (without_plots[name].read_bytes(), with_plots[name].read_bytes())
                for name in table_names
            ]
            with with_plots["manifest_json"].open("r", encoding="utf-8") as handle:
                manifest = json.load(handle)
            plot_file_names = sorted(path.name for path in with_plots["plots_dir"].iterdir())

        for without_plot_bytes, with_plot_bytes in table_pairs:
            self.assertEqual(without_plot_bytes, with_plot_bytes)
        self.assertEqual(
            plot_file_names,
            sorted(
                f"{stem}.{extension}"
                for stem in (
                    "current_frame_positions",
                    "range_trends",
                    "spatial_comparison",
                    "density_maps",
                )
                for extension in ("svg", "png")
            ),
        )
        self.assertEqual(
            manifest["plots"],
            {
                "included": True,
                "formats": ["svg", "png"],
                "png_dpi": 100,
                "size_inches": {"width": 4.0, "height": 3.0},
                "generated": [
                    {
                        "kind": stem,
                        "files": [f"plots/{stem}.svg", f"plots/{stem}.png"],
                    }
                    for stem in (
                        "current_frame_positions",
                        "range_trends",
                        "spatial_comparison",
                        "density_maps",
                    )
                ],
                "skipped": [
                    {
                        "kind": "intensity_maps",
                        "reason": "No finite intensity values are available.",
                    },
                    {
                        "kind": "domain_type_scatter",
                        "reason": "Domain type classification is not available.",
                    },
                    {
                        "kind": "domain_type_shares",
                        "reason": "Domain type classification is not available.",
                    },
                ],
            },
        )
        plot_entries = [
            file_info
            for file_info in manifest["files"]
            if file_info["path"].startswith("plots/")
        ]
        self.assertEqual(len(plot_entries), 8)
        self.assertTrue(all(file_info["record_count"] is None for file_info in plot_entries))
        self.assertTrue(all(not Path(file_info["path"]).is_absolute() for file_info in plot_entries))

    def test_selected_ranges_package_publishes_complete_directory(self) -> None:
        series, selection = self._build_selected_ranges_fixture()

        with tempfile.TemporaryDirectory() as tmpdir:
            destination = Path(tmpdir) / "analysis-package"
            result = export_selected_ranges_analysis_package(
                series,
                selection,
                destination,
                package_format="directory",
                intensity_metric="mean",
                density_grid_shape=(2, 2),
            )
            actual_files = tuple(
                sorted(
                    path.relative_to(destination).as_posix()
                    for path in destination.rglob("*")
                    if path.is_file()
                )
            )

        expected_files = (
            "comparison.csv",
            "domain_type_comparison.csv",
            "domain_type_ranges.csv",
            "domain_types.csv",
            "domains.csv",
            "frames.csv",
            "lattice_domains.csv",
            "manifest.json",
            "molecules.csv",
            "ranges.csv",
            "spatial_bins.csv",
        )
        self.assertEqual(result.package_path, destination)
        self.assertEqual(result.package_format, "directory")
        self.assertEqual(result.relative_files, expected_files)
        self.assertEqual(actual_files, expected_files)

    def test_selected_ranges_zip_package_has_same_structure_as_directory(self) -> None:
        series, selection = self._build_selected_ranges_fixture()

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            directory_result = export_selected_ranges_analysis_package(
                series,
                selection,
                root / "analysis-directory",
                package_format="directory",
                intensity_metric="mean",
                density_grid_shape=(2, 2),
                include_plots=True,
                plot_dpi=80,
                plot_size_inches=(4.0, 3.0),
            )
            zip_result = export_selected_ranges_analysis_package(
                series,
                selection,
                root / "analysis.zip",
                package_format="zip",
                intensity_metric="mean",
                density_grid_shape=(2, 2),
                include_plots=True,
                plot_dpi=80,
                plot_size_inches=(4.0, 3.0),
            )
            with zipfile.ZipFile(zip_result.package_path, "r") as archive:
                zip_names = tuple(sorted(archive.namelist()))
                zip_tables = {
                    name: archive.read(name)
                    for name in (
                        "molecules.csv",
                        "frames.csv",
                        "domains.csv",
                        "ranges.csv",
                        "comparison.csv",
                        "spatial_bins.csv",
                    )
                }
            directory_tables = {
                name: (directory_result.package_path / name).read_bytes()
                for name in zip_tables
            }

        self.assertEqual(zip_result.package_path, root / "analysis.zip")
        self.assertEqual(zip_result.package_format, "zip")
        self.assertEqual(zip_result.relative_files, directory_result.relative_files)
        self.assertEqual(zip_names, directory_result.relative_files)
        self.assertEqual(zip_tables, directory_tables)
        self.assertIn("plots/current_frame_positions.svg", zip_names)
        self.assertIn("plots/intensity_maps.png", zip_names)

    def test_selected_ranges_package_failure_leaves_no_partial_destination(self) -> None:
        series, selection = self._build_selected_ranges_fixture()

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            destination = root / "failed-package"

            with self.assertRaisesRegex(ValueError, "plot_dpi must be positive"):
                export_selected_ranges_analysis_package(
                    series,
                    selection,
                    destination,
                    package_format="directory",
                    intensity_metric="mean",
                    density_grid_shape=(2, 2),
                    include_plots=True,
                    plot_dpi=0,
                )

            self.assertFalse(destination.exists())
            self.assertEqual(list(root.iterdir()), [])

    def test_selected_ranges_package_requires_explicit_overwrite(self) -> None:
        series, selection = self._build_selected_ranges_fixture()

        with tempfile.TemporaryDirectory() as tmpdir:
            destination = Path(tmpdir) / "existing-package"
            destination.mkdir()
            marker = destination / "user-data.txt"
            marker.write_text("keep me", encoding="utf-8")

            with self.assertRaisesRegex(FileExistsError, "already exists"):
                export_selected_ranges_analysis_package(
                    series,
                    selection,
                    destination,
                    package_format="directory",
                    intensity_metric="mean",
                    density_grid_shape=(2, 2),
                )

            self.assertEqual(marker.read_text(encoding="utf-8"), "keep me")
            result = export_selected_ranges_analysis_package(
                series,
                selection,
                destination,
                package_format="directory",
                overwrite=True,
                intensity_metric="mean",
                density_grid_shape=(2, 2),
            )

            self.assertFalse(marker.exists())
            self.assertTrue((destination / "manifest.json").is_file())

        self.assertEqual(result.package_path, destination)

    def test_analysis_export_settings_preserve_an_immutable_persistence_request(self) -> None:
        _series, selection = self._build_selected_ranges_fixture()
        settings = AnalysisExportSettings(
            scope="selected_ranges",
            destination=Path("analysis.zip"),
            package_format="zip",
            include_tables=False,
            include_spatial_grids=True,
            include_plots=True,
            frame_count=2,
            active_frame_index=0,
            source_view="raw",
            use_segmentation_centroids=False,
            intensity_metric="mean",
            intensity_unit="a.u.",
            background_inner_radius_px=2,
            background_outer_radius_px=5,
            density_grid_shape=(3, 4),
            selected_ranges=selection,
        )

        self.assertEqual(settings.scope, "selected_ranges")
        self.assertEqual(settings.destination, Path("analysis.zip"))
        self.assertEqual(settings.package_format, "zip")
        self.assertFalse(settings.include_tables)
        self.assertTrue(settings.include_spatial_grids)
        self.assertTrue(settings.include_plots)
        self.assertEqual(settings.density_grid_shape, (3, 4))
        self.assertIs(settings.selected_ranges, selection)
        with self.assertRaises(FrozenInstanceError):
            settings.scope = "current_frame"
        with self.assertRaisesRegex(ValueError, "spatial grids require selected_ranges"):
            AnalysisExportSettings(
                scope="current_frame",
                destination=Path("analysis"),
                package_format="directory",
                include_tables=True,
                include_spatial_grids=True,
                include_plots=False,
                frame_count=2,
                active_frame_index=0,
                source_view="raw",
                use_segmentation_centroids=True,
                intensity_metric="mean",
                intensity_unit="a.u.",
                background_inner_radius_px=1,
                background_outer_radius_px=3,
                density_grid_shape=(2, 2),
            )

    def test_full_series_package_reports_frame_progress_and_record_counts(self) -> None:
        frame_count = 6
        detections = MolecularDetectionSet(frame_count=frame_count)
        for frame_index in range(frame_count):
            detections.set_detections(
                frame_index,
                [
                    MolecularDetection(
                        frame_index,
                        (1, 1, 3, 3),
                        0.8,
                        detection_id=f"molecule-{frame_index}",
                    )
                ],
                source_view="raw",
                frame_shape=(5, 5),
            )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.zeros((frame_count, 5, 5), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=5, pixels_y=5),
            active_frame_index=2,
            molecular_detections=detections,
        )
        progress_events = []

        with tempfile.TemporaryDirectory() as tmpdir:
            destination = Path(tmpdir) / "full-series-analysis"
            settings = AnalysisExportSettings(
                scope="full_working_series",
                destination=destination,
                package_format="directory",
                include_tables=True,
                include_spatial_grids=False,
                include_plots=False,
                frame_count=frame_count,
                active_frame_index=2,
                source_view="raw",
                use_segmentation_centroids=True,
                intensity_metric="mean",
                intensity_unit="a.u.",
                background_inner_radius_px=1,
                background_outer_radius_px=3,
                density_grid_shape=(4, 4),
            )

            result = export_analysis_package(
                series,
                settings,
                progress_callback=progress_events.append,
            )
            with (destination / "manifest.json").open("r", encoding="utf-8") as handle:
                manifest = json.load(handle)

        self.assertEqual(
            result.relative_files,
            (
                "domain_type_comparison.csv",
                "domain_type_ranges.csv",
                "domain_types.csv",
                "domains.csv",
                "frames.csv",
                "lattice_domains.csv",
                "manifest.json",
                "molecules.csv",
            ),
        )
        self.assertEqual(
            result.record_counts,
            (
                ("domain_type_comparison.csv", 0),
                ("domain_type_ranges.csv", 0),
                ("domain_types.csv", 0),
                ("domains.csv", 0),
                ("frames.csv", 6),
                ("lattice_domains.csv", 0),
                ("molecules.csv", 6),
            ),
        )
        self.assertEqual(manifest["scope"], "full_working_series")
        self.assertEqual(
            [
                (event.completed_count, event.total_count)
                for event in progress_events
                if event.phase == "analyzing_frames"
            ],
            [(index, frame_count) for index in range(1, frame_count + 1)],
        )
        self.assertTrue(
            all(isinstance(event, AnalysisExportProgress) for event in progress_events)
        )
        self.assertIn("writing_tables", [event.phase for event in progress_events])
        self.assertIn("publishing", [event.phase for event in progress_events])
        self.assertEqual(progress_events[-1].phase, "complete")

    def test_current_frame_package_exports_tables_and_available_plots(self) -> None:
        series, _selection = self._build_selected_ranges_fixture()
        series.active_frame_index = 1
        progress_events = []

        with tempfile.TemporaryDirectory() as tmpdir:
            destination = Path(tmpdir) / "current-frame-analysis"
            settings = AnalysisExportSettings(
                scope="current_frame",
                destination=destination,
                package_format="directory",
                include_tables=True,
                include_spatial_grids=False,
                include_plots=True,
                frame_count=2,
                active_frame_index=1,
                source_view="raw",
                use_segmentation_centroids=True,
                intensity_metric="mean",
                intensity_unit="a.u.",
                background_inner_radius_px=1,
                background_outer_radius_px=3,
                density_grid_shape=(4, 4),
            )

            result = export_analysis_package(
                series,
                settings,
                progress_callback=progress_events.append,
            )
            svg_text = (destination / "plots" / "current_frame_positions.svg").read_text(
                encoding="utf-8"
            )

        self.assertEqual(
            result.relative_files,
            (
                "domain_type_comparison.csv",
                "domain_type_ranges.csv",
                "domain_types.csv",
                "domains.csv",
                "frames.csv",
                "lattice_domains.csv",
                "manifest.json",
                "molecules.csv",
                "plots/current_frame_positions.png",
                "plots/current_frame_positions.svg",
            ),
        )
        self.assertEqual(
            result.record_counts,
            (
                ("domain_type_comparison.csv", 0),
                ("domain_type_ranges.csv", 0),
                ("domain_types.csv", 0),
                ("domains.csv", 0),
                ("frames.csv", 1),
                ("lattice_domains.csv", 0),
                ("molecules.csv", 4),
            ),
        )
        self.assertIn("Current frame positions - frame 2", svg_text)
        self.assertEqual(
            [
                (event.completed_count, event.total_count)
                for event in progress_events
                if event.phase == "analyzing_frames"
            ],
            [(1, 1)],
        )
        self.assertIn("writing_tables", [event.phase for event in progress_events])
        self.assertIn("rendering_plots", [event.phase for event in progress_events])
        self.assertEqual(progress_events[-1].phase, "complete")

    def test_selected_ranges_zip_contains_only_requested_spatial_grid(self) -> None:
        series, selection = self._build_selected_ranges_fixture()
        progress_events = []

        with tempfile.TemporaryDirectory() as tmpdir:
            destination = Path(tmpdir) / "selected-ranges.zip"
            settings = AnalysisExportSettings(
                scope="selected_ranges",
                destination=destination,
                package_format="zip",
                include_tables=False,
                include_spatial_grids=True,
                include_plots=False,
                frame_count=2,
                active_frame_index=0,
                source_view="raw",
                use_segmentation_centroids=True,
                intensity_metric="mean",
                intensity_unit="a.u.",
                background_inner_radius_px=1,
                background_outer_radius_px=3,
                density_grid_shape=(2, 2),
                selected_ranges=selection,
            )

            result = export_analysis_package(
                series,
                settings,
                progress_callback=progress_events.append,
            )
            with zipfile.ZipFile(destination, "r") as archive:
                archive_names = tuple(sorted(archive.namelist()))
                manifest = json.loads(archive.read("manifest.json"))

        self.assertEqual(
            archive_names,
            ("manifest.json", "spatial_bins.csv"),
        )
        self.assertEqual(result.relative_files, archive_names)
        self.assertEqual(result.record_counts, (("spatial_bins.csv", 8),))
        self.assertEqual(manifest["scope"], "selected_ranges")
        self.assertEqual(
            manifest["files"],
            [{"path": "spatial_bins.csv", "record_count": 8}],
        )
        self.assertEqual(
            [
                (event.completed_count, event.total_count)
                for event in progress_events
                if event.phase == "analyzing_frames"
            ],
            [(1, 2), (2, 2)],
        )
        phases = [event.phase for event in progress_events]
        self.assertLess(phases.index("packaging_zip"), phases.index("publishing"))
        self.assertEqual(phases[-1], "complete")

    def test_full_working_series_export_includes_every_frame_and_observation(self) -> None:
        detections = MolecularDetectionSet(frame_count=3)
        detections.set_detections(
            0,
            [MolecularDetection(0, (1, 1, 3, 3), 0.8, detection_id="frame-0-a")],
            source_view="raw",
            frame_shape=(8, 8),
        )
        detections.set_detections(
            2,
            [
                MolecularDetection(2, (1, 1, 3, 3), 0.7, detection_id="frame-2-a"),
                MolecularDetection(2, (4, 4, 6, 6), 0.9, detection_id="frame-2-b"),
            ],
            source_view="raw",
            frame_shape=(8, 8),
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.zeros((3, 8, 8), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=8, pixels_y=8),
            molecular_detections=detections,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            paths = export_full_working_series_analysis_csv(
                series,
                tmpdir,
                source_view="raw",
                intensity_metric="mean",
            )
            with paths["molecules_csv"].open("r", encoding="utf-8", newline="") as handle:
                molecule_rows = list(csv.DictReader(handle))
            with paths["frames_csv"].open("r", encoding="utf-8", newline="") as handle:
                frame_rows = list(csv.DictReader(handle))

        self.assertEqual(
            [row["working_frame_index"] for row in molecule_rows],
            ["0", "2", "2"],
        )
        self.assertEqual(
            [row["source_id"] for row in molecule_rows],
            ["frame-0-a", "frame-2-a", "frame-2-b"],
        )
        self.assertEqual(
            [row["working_frame_index"] for row in frame_rows],
            ["0", "1", "2"],
        )
        self.assertEqual(
            [row["molecule_count"] for row in frame_rows],
            ["1", "0", "2"],
        )

    def test_full_working_series_export_preserves_source_frames_after_reverse_and_removal(self) -> None:
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.zeros((5, 6, 6), dtype=np.float32),
            metadata=STMSequenceMetadata(
                pixels_x=6,
                pixels_y=6,
                frame_times_s=np.asarray([50.0, 40.0, 30.0, 20.0, 10.0]),
            ),
            reverse_frame_order=True,
        )
        series.remove_frame(1)
        series.remove_frame(2)
        detections = MolecularDetectionSet(frame_count=3)
        for frame_index in range(3):
            detections.set_detections(
                frame_index,
                [
                    MolecularDetection(
                        frame_index,
                        (1, 1, 3, 3),
                        0.8,
                        detection_id=f"bbox-{frame_index}",
                    )
                ],
                source_view="raw",
                frame_shape=(6, 6),
            )
        series.molecular_detections = detections

        with tempfile.TemporaryDirectory() as tmpdir:
            paths = export_full_working_series_analysis_csv(series, tmpdir)
            with paths["molecules_csv"].open("r", encoding="utf-8", newline="") as handle:
                molecule_rows = list(csv.DictReader(handle))
            with paths["frames_csv"].open("r", encoding="utf-8", newline="") as handle:
                frame_rows = list(csv.DictReader(handle))

        for rows in (molecule_rows, frame_rows):
            self.assertEqual(
                [row["working_frame_index"] for row in rows],
                ["0", "1", "2"],
            )
            self.assertEqual(
                [row["source_frame_index"] for row in rows],
                ["4", "2", "0"],
            )
            self.assertEqual(
                [row["source_frame_number"] for row in rows],
                ["5", "3", "1"],
            )
            self.assertEqual([row["time_s"] for row in rows], ["50.0", "30.0", "10.0"])

    def test_full_working_series_export_orders_observations_without_creating_tracks(self) -> None:
        detections = MolecularDetectionSet(frame_count=2)
        detections.set_detections(
            0,
            [
                MolecularDetection(0, (4, 1, 6, 3), 0.2, detection_id="z-id"),
                MolecularDetection(0, (1, 1, 3, 3), 0.1, detection_id="same-id"),
            ],
            source_view="raw",
            frame_shape=(8, 8),
        )
        detections.set_detections(
            1,
            [
                MolecularDetection(1, (4, 4, 6, 6), 0.9, detection_id="same-id"),
                MolecularDetection(1, (1, 4, 3, 6), 0.8, detection_id="a-id"),
            ],
            source_view="raw",
            frame_shape=(8, 8),
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.zeros((2, 8, 8), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=8, pixels_y=8),
            molecular_detections=detections,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            paths = export_full_working_series_analysis_csv(series, tmpdir)
            with paths["molecules_csv"].open("r", encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))

        self.assertEqual(
            [(row["working_frame_index"], row["source_id"]) for row in rows],
            [("0", "same-id"), ("0", "z-id"), ("1", "a-id"), ("1", "same-id")],
        )
        self.assertTrue(all("track_id" not in row for row in rows))
        repeated_rows = [row for row in rows if row["source_id"] == "same-id"]
        self.assertEqual(len(repeated_rows), 2)
        self.assertEqual(repeated_rows[0]["bbox_x1"], "1.0")
        self.assertEqual(repeated_rows[0]["confidence"], "0.1")
        self.assertEqual(repeated_rows[1]["bbox_x1"], "4.0")
        self.assertEqual(repeated_rows[1]["confidence"], "0.9")

    def test_full_frame_export_aligns_geometry_and_neighbor_metrics_by_source_id(self) -> None:
        detections = MolecularDetectionSet(frame_count=1)
        detections.set_detections(
            0,
            [
                MolecularDetection(0, (0.5, 0.5, 1.5, 1.5), 0.7, detection_id="bbox-a"),
                MolecularDetection(0, (3.5, 0.5, 4.5, 1.5), 0.8, detection_id="bbox-b"),
                MolecularDetection(0, (3.5, 4.5, 4.5, 5.5), 0.9, detection_id="bbox-c"),
            ],
            source_view="raw",
            frame_shape=(8, 8),
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.zeros((1, 8, 8), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=8, pixels_y=8),
            molecular_detections=detections,
        )
        frame_analysis = analyze_molecular_frame_range(
            series,
            MolecularFrameRange("current", 0, 0),
            source_view="raw",
            intensity_metric="mean",
        ).frame_results[0]

        with tempfile.TemporaryDirectory() as tmpdir:
            paths = export_current_frame_analysis_csv(series, frame_analysis, tmpdir)
            with paths["molecules_csv"].open("r", encoding="utf-8", newline="") as handle:
                rows = {row["source_id"]: row for row in csv.DictReader(handle)}
            with paths["frames_csv"].open("r", encoding="utf-8", newline="") as handle:
                frame_rows = list(csv.DictReader(handle))

        self.assertEqual(rows["bbox-a"]["detection_id"], "bbox-a")
        self.assertEqual(rows["bbox-a"]["segmentation_id"], "")
        self.assertEqual(rows["bbox-a"]["area_px"], "1.0")
        self.assertEqual(rows["bbox-a"]["bbox_x1"], "0.5")
        self.assertEqual(rows["bbox-a"]["bbox_y1"], "0.5")
        self.assertEqual(rows["bbox-a"]["bbox_x2"], "1.5")
        self.assertEqual(rows["bbox-a"]["bbox_y2"], "1.5")
        self.assertEqual(rows["bbox-a"]["confidence"], "0.7")
        self.assertEqual(rows["bbox-a"]["nearest_neighbor_distance"], "3.0")
        self.assertEqual(rows["bbox-a"]["nearest_neighbor_distance_unit"], "px")
        self.assertEqual(rows["bbox-a"]["nearest_neighbor_angle_deg"], "0.0")
        self.assertEqual(rows["bbox-c"]["nearest_neighbor_distance"], "4.0")
        self.assertEqual(rows["bbox-c"]["nearest_neighbor_angle_deg"], "90.0")
        self.assertEqual(len(frame_rows), 1)
        frame_row = frame_rows[0]
        self.assertEqual(frame_row["working_frame_index"], "0")
        self.assertEqual(frame_row["working_frame_number"], "1")
        self.assertEqual(frame_row["source_frame_index"], "0")
        self.assertEqual(frame_row["source_frame_number"], "1")
        self.assertEqual(frame_row["source_view"], "raw")
        self.assertEqual(frame_row["molecule_count"], "3")
        self.assertEqual(frame_row["nearest_neighbor_distance_unit"], "px")
        self.assertAlmostEqual(float(frame_row["mean_nearest_neighbor_distance"]), 10.0 / 3.0)
        self.assertEqual(frame_row["median_nearest_neighbor_distance"], "3.0")
        self.assertEqual(frame_row["min_nearest_neighbor_distance"], "3.0")
        self.assertEqual(frame_row["max_nearest_neighbor_distance"], "4.0")
        self.assertAlmostEqual(float(frame_row["line_order_score"]), 1.0 / 3.0)
        self.assertEqual(frame_row["intensity_metric"], "mean")
        self.assertEqual(frame_row["intensity_unit"], "a.u.")
        self.assertEqual(frame_row["mean_intensity"], "0.0")
        self.assertEqual(frame_row["median_intensity"], "0.0")

    def test_full_frame_export_uses_analysis_intensity_measurements_for_each_source(self) -> None:
        frame = np.ones((10, 10), dtype=np.float32)
        frame[3:5, 3:5] = 10.0
        frame[2, 3:5] = 3.0
        frame[5, 3:5] = 3.0
        frame[3:5, 2] = 3.0
        frame[3:5, 5] = 3.0
        frame[7:9, 7:9] = 5.0
        detections = MolecularDetectionSet(frame_count=1)
        detections.set_detections(
            0,
            [
                MolecularDetection(0, (2, 2, 6, 6), 0.8, detection_id="bbox-prompt"),
                MolecularDetection(0, (7, 7, 9, 9), 0.7, detection_id="bbox-fallback"),
            ],
            source_view="raw",
            frame_shape=frame.shape,
        )
        mask = np.zeros(frame.shape, dtype=bool)
        mask[3:5, 3:5] = True
        segmentations = MolecularSegmentationSet(frame_count=1)
        segmentations.add_segmentation(
            MolecularSegmentation(
                frame_index=0,
                source_view="raw",
                mask=mask,
                score=0.95,
                origin="sam2",
                prompt_detection_ids=("bbox-prompt",),
                segmentation_id="seg-a",
            )
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frame[np.newaxis, ...],
            metadata=STMSequenceMetadata(pixels_x=10, pixels_y=10),
            molecular_detections=detections,
            molecular_segmentations=segmentations,
        )
        frame_analysis = analyze_molecular_frame_range(
            series,
            MolecularFrameRange("current", 0, 0),
            source_view="raw",
            intensity_metric="background_corrected_median",
            background_inner_radius_px=0,
            background_outer_radius_px=1,
        ).frame_results[0]

        with tempfile.TemporaryDirectory() as tmpdir:
            paths = export_current_frame_analysis_csv(series, frame_analysis, tmpdir)
            with paths["molecules_csv"].open("r", encoding="utf-8", newline="") as handle:
                rows = {row["source_id"]: row for row in csv.DictReader(handle)}

        segmentation_row = rows["seg-a"]
        self.assertEqual(segmentation_row["detection_id"], "")
        self.assertEqual(segmentation_row["segmentation_id"], "seg-a")
        self.assertEqual(segmentation_row["area_px"], "4.0")
        self.assertEqual(segmentation_row["bbox_x1"], "3.0")
        self.assertEqual(segmentation_row["bbox_y1"], "3.0")
        self.assertEqual(segmentation_row["bbox_x2"], "5.0")
        self.assertEqual(segmentation_row["bbox_y2"], "5.0")
        self.assertEqual(segmentation_row["confidence"], "0.95")
        self.assertEqual(segmentation_row["intensity_pixel_count"], "4")
        self.assertEqual(segmentation_row["intensity_unit"], "a.u.")
        self.assertEqual(segmentation_row["intensity_sum"], "40.0")
        self.assertEqual(segmentation_row["intensity_mean"], "10.0")
        self.assertEqual(segmentation_row["intensity_median"], "10.0")
        self.assertEqual(segmentation_row["intensity_max"], "10.0")
        self.assertEqual(segmentation_row["local_background_median"], "3.0")
        self.assertEqual(segmentation_row["background_corrected_mean"], "7.0")
        self.assertEqual(segmentation_row["background_corrected_median"], "7.0")
        self.assertEqual(rows["bbox-fallback"]["intensity_mean"], "5.0")

    def test_full_frame_export_writes_missing_metrics_as_empty_fields_for_zero_or_one_point(self) -> None:
        for molecule_count in (0, 1):
            with self.subTest(molecule_count=molecule_count):
                detections = None
                if molecule_count == 1:
                    detections = MolecularDetectionSet(frame_count=1)
                    detections.set_detections(
                        0,
                        [MolecularDetection(0, (1, 1, 3, 3), 0.8, detection_id="bbox-a")],
                        source_view="raw",
                        frame_shape=(5, 5),
                    )
                series = MolTrackImageSeries(
                    source_path="movie.mpp",
                    raw_frames=np.full((1, 5, 5), np.nan, dtype=np.float32),
                    metadata=STMSequenceMetadata(pixels_x=5, pixels_y=5),
                    molecular_detections=detections,
                )
                frame_analysis = analyze_molecular_frame_range(
                    series,
                    MolecularFrameRange("current", 0, 0),
                    source_view="raw",
                    intensity_metric="mean",
                ).frame_results[0]

                with tempfile.TemporaryDirectory() as tmpdir:
                    paths = export_current_frame_analysis_csv(series, frame_analysis, tmpdir)
                    with paths["molecules_csv"].open(
                        "r", encoding="utf-8", newline=""
                    ) as handle:
                        molecule_rows = list(csv.DictReader(handle))
                    with paths["frames_csv"].open(
                        "r", encoding="utf-8", newline=""
                    ) as handle:
                        frame_row = next(csv.DictReader(handle))

                self.assertEqual(len(molecule_rows), molecule_count)
                self.assertEqual(frame_row["molecule_count"], str(molecule_count))
                self.assertEqual(frame_row["mean_nearest_neighbor_distance"], "")
                self.assertEqual(frame_row["median_nearest_neighbor_distance"], "")
                self.assertEqual(frame_row["min_nearest_neighbor_distance"], "")
                self.assertEqual(frame_row["max_nearest_neighbor_distance"], "")
                self.assertEqual(frame_row["line_order_score"], "")
                self.assertEqual(frame_row["mean_intensity"], "")
                self.assertEqual(frame_row["median_intensity"], "")
                if molecule_rows:
                    self.assertEqual(molecule_rows[0]["intensity_pixel_count"], "0")
                    self.assertEqual(molecule_rows[0]["intensity_sum"], "")

    def test_export_current_frame_creates_molecules_csv_with_one_row_per_plot_point(self) -> None:
        detections = MolecularDetectionSet(frame_count=2)
        detections.set_detections(
            1,
            [
                MolecularDetection(
                    frame_index=1,
                    bbox_xyxy=(2, 1, 6, 5),
                    confidence=0.9,
                    detection_id="bbox-a",
                )
            ],
            source_view="raw",
            frame_shape=(8, 10),
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.zeros((2, 8, 10), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=10, pixels_y=8),
            active_frame_index=1,
            molecular_detections=detections,
        )
        centroids = build_molecular_centroids(series, frame_index=1)
        plot_data = build_molecular_position_plot_data(
            centroids,
            frame_index=1,
            source_view="raw",
            frame_shape=series.frame_shape,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            export_path = export_current_frame_molecules_csv(series, plot_data, tmpdir)
            with export_path.open("r", encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))

            self.assertEqual(export_path, Path(tmpdir) / "molecules.csv")
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["source_id"], "bbox-a")
            self.assertEqual(rows[0]["source_kind"], "bbox")
            self.assertEqual(rows[0]["position_x"], "4.0")
            self.assertEqual(rows[0]["position_y"], "3.0")
            self.assertEqual(rows[0]["position_unit"], "px")
            self.assertEqual(rows[0]["time_s"], "")
            self.assertEqual(rows[0]["x_nm"], "")
            self.assertEqual(rows[0]["y_nm"], "")

    def test_export_preserves_working_source_time_origin_and_source_coordinates(self) -> None:
        detections = MolecularDetectionSet(frame_count=2)
        detections.set_detections(
            1,
            [
                MolecularDetection(
                    frame_index=1,
                    bbox_xyxy=(2, 2, 6, 4),
                    confidence=1.0,
                    model_name="manual",
                    detection_id="bbox-manual",
                    origin="manual",
                )
            ],
            source_view="raw",
            frame_shape=(8, 10),
        )
        mask = np.zeros((8, 10), dtype=bool)
        mask[5:7, 6:8] = True
        segmentations = MolecularSegmentationSet(frame_count=2)
        segmentations.add_segmentation(
            MolecularSegmentation(
                frame_index=1,
                source_view="raw",
                mask=mask,
                origin="sam2",
                segmentation_id="seg-sam2",
            )
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.zeros((2, 8, 10), dtype=np.float32),
            metadata=STMSequenceMetadata(
                pixels_x=10,
                pixels_y=8,
                size_nm_x=20.0,
                size_nm_y=8.0,
                frame_times_s=np.asarray([40.0, 30.0, 20.0, 10.0]),
            ),
            active_frame_index=1,
            reverse_frame_order=True,
            source_frame_indices=(3, 1),
            molecular_detections=detections,
            molecular_segmentations=segmentations,
            molecular_orientations=MolecularOrientationStore(
                frame_count=2,
                measurements=(
                    MolecularOrientationMeasurement(
                        measurement_id="orientation:segmentation:seg-sam2",
                        status="available",
                        angle_deg=25.0,
                        periodicity_deg=180.0,
                        confidence=0.8,
                        method="mask_principal_axis",
                        patch_shape_px=(8, 10),
                        provenance=MolecularOrientationProvenance(
                            source_file_name="movie.mpp",
                            source_file_sha256="a" * 64,
                            source_session_file_name=None,
                            source_session_sha256=None,
                            frame_index=1,
                            source_view="raw",
                            source_kind="segmentation",
                            source_id="seg-sam2",
                            patch_bbox_xyxy=(0.0, 0.0, 10.0, 8.0),
                            orientation_reference=(
                                "sample_x_axis_counterclockwise"
                            ),
                        ),
                    ).with_manual_correction(
                        status="available",
                        angle_deg=35.0,
                        confidence=1.0,
                        reviewer="MolTrack user",
                        note="Checked in viewer.",
                    ),
                ),
            ),
        )
        centroids = build_molecular_centroids(series, frame_index=1)
        plot_data = build_molecular_position_plot_data(
            centroids,
            frame_index=1,
            source_view="raw",
            frame_shape=series.frame_shape,
            scale_nm_per_px=(2.0, 1.0),
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            export_path = export_current_frame_molecules_csv(series, plot_data, tmpdir)
            with export_path.open("r", encoding="utf-8", newline="") as handle:
                rows = {
                    row["source_id"]: row
                    for row in csv.DictReader(handle)
                }

        expected_fields = {
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
        }
        m6_fields = {
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
        }
        expected_fields.update(m6_fields)
        self.assertEqual(set(rows["seg-sam2"]), expected_fields)
        self.assertTrue(all(rows["seg-sam2"][field] == "" for field in m6_fields))
        self.assertEqual(rows["seg-sam2"]["working_frame_index"], "1")
        self.assertEqual(rows["seg-sam2"]["working_frame_number"], "2")
        self.assertEqual(rows["seg-sam2"]["source_frame_index"], "1")
        self.assertEqual(rows["seg-sam2"]["source_frame_number"], "2")
        self.assertEqual(rows["seg-sam2"]["time_s"], "20.0")
        self.assertEqual(rows["seg-sam2"]["source_view"], "raw")
        self.assertEqual(rows["seg-sam2"]["source_kind"], "segmentation")
        self.assertEqual(rows["seg-sam2"]["origin"], "sam2")
        self.assertEqual(rows["seg-sam2"]["position_x"], "14.0")
        self.assertEqual(rows["seg-sam2"]["position_y"], "6.0")
        self.assertEqual(rows["seg-sam2"]["position_unit"], "nm")
        self.assertEqual(rows["seg-sam2"]["x_px"], "7.0")
        self.assertEqual(rows["seg-sam2"]["y_px"], "6.0")
        self.assertEqual(rows["seg-sam2"]["x_nm"], "14.0")
        self.assertEqual(rows["seg-sam2"]["y_nm"], "6.0")
        self.assertEqual(
            rows["seg-sam2"]["molecular_orientation_angle_deg"],
            "35.0",
        )
        self.assertEqual(
            rows["seg-sam2"]["molecular_orientation_method"],
            "manual_correction",
        )
        self.assertEqual(
            rows["seg-sam2"]["molecular_orientation_manual_corrected"],
            "True",
        )
        self.assertEqual(
            rows["seg-sam2"][
                "molecular_orientation_automatic_angle_deg"
            ],
            "25.0",
        )
        self.assertEqual(
            rows["seg-sam2"]["molecular_orientation_reviewer"],
            "MolTrack user",
        )
        self.assertEqual(
            rows["bbox-manual"]["molecular_orientation_angle_deg"],
            "",
        )
        self.assertEqual(rows["bbox-manual"]["source_kind"], "bbox")
        self.assertEqual(rows["bbox-manual"]["origin"], "manual")
        self.assertEqual(rows["bbox-manual"]["x_px"], "4.0")
        self.assertEqual(rows["bbox-manual"]["y_px"], "3.0")

    def test_export_rejects_empty_analysis_without_creating_molecules_csv(self) -> None:
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.zeros((1, 8, 10), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=10, pixels_y=8),
        )
        plot_data = build_molecular_position_plot_data(
            [],
            frame_index=0,
            source_view="raw",
            frame_shape=series.frame_shape,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            destination = Path(tmpdir) / "analysis"

            with self.assertRaisesRegex(RuntimeError, "No molecular positions"):
                export_current_frame_molecules_csv(series, plot_data, destination)

            self.assertFalse((destination / "molecules.csv").exists())


if __name__ == "__main__":
    unittest.main()
