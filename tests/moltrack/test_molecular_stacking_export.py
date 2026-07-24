import csv
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

import numpy as np

from moltrack.analysis import (
    MolecularFrameRange,
    MolecularFrameRangeSelection,
    MolecularOrientationStore,
    MolecularStackingSessionState,
    analyze_molecular_stacking,
    build_molecular_orientation_prototype_analysis,
)
from moltrack.core import MolTrackImageSeries
from moltrack.persistence import (
    AnalysisExportSettings,
    build_molecular_stacking_export_data,
    export_analysis_package,
    export_selected_ranges_analysis_csv,
    write_molecular_stacking_tables,
)
from nanotrack.core import STMSequenceMetadata
from test_molecular_stacking_persistence import _display_result


def _series_with_stacking() -> tuple[
    MolTrackImageSeries,
    MolecularStackingSessionState,
]:
    display = _display_result()
    state = MolecularStackingSessionState.from_display_result(display)
    return (
        MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.zeros((2, 20, 20), dtype=np.float32),
            metadata=STMSequenceMetadata(
                pixels_x=20,
                pixels_y=20,
                size_nm_x=40.0,
                size_nm_y=40.0,
            ),
            source_frame_indices=(10, 11),
            molecular_orientations=MolecularOrientationStore(
                frame_count=2,
                measurements=tuple(
                    measurement
                    for frame in display.frames
                    for measurement in frame.measurements
                ),
            ),
            molecular_stacking_state=state,
        ),
        state,
    )


def _display_with_unassigned_and_corrected_orientation():
    display = _display_result()
    first = display.frames[0]
    corrected = first.measurements[0].with_manual_correction(
        status="available",
        angle_deg=25.0,
        confidence=0.8,
        reviewer="analyst",
        note="manual review",
    )
    orphan = replace(
        first.measurements[-1],
        measurement_id="orientation-zz-orphan",
        provenance=replace(
            first.measurements[-1].provenance,
            source_id="zz-orphan",
        ),
    )
    row_assignment = replace(
        first.row_assignment,
        source_ids=first.row_assignment.source_ids + ("zz-orphan",),
        point_count=first.row_assignment.point_count + 1,
        point_coordinate_fingerprint="coordinates-with-orphan",
    )
    frames = (
        replace(
            first,
            row_assignment=row_assignment,
            measurements=(corrected, *first.measurements[1:], orphan),
        ),
        display.frames[1],
    )
    prototypes = build_molecular_orientation_prototype_analysis(frames)
    return replace(
        display,
        frames=frames,
        prototype_analysis=prototypes,
        stacking_analysis=analyze_molecular_stacking(frames, prototypes),
    )


def _raw_display_result():
    display = _display_result()
    raw_frames = tuple(
        replace(
            frame,
            measurements=tuple(
                replace(
                    measurement,
                    provenance=replace(
                        measurement.provenance,
                        source_view="raw",
                    ),
                )
                for measurement in frame.measurements
            ),
        )
        for frame in display.frames
    )
    raw_prototypes = build_molecular_orientation_prototype_analysis(raw_frames)
    return replace(
        display,
        frames=raw_frames,
        prototype_analysis=raw_prototypes,
        stacking_analysis=analyze_molecular_stacking(
            raw_frames,
            raw_prototypes,
        ),
    )


class MolecularStackingExportTests(unittest.TestCase):
    def test_builds_filtered_molecule_domain_subdomain_tables_with_provenance(
        self,
    ) -> None:
        series, state = _series_with_stacking()

        export = build_molecular_stacking_export_data(
            series,
            state,
            frame_indices=(0,),
        )

        self.assertTrue(export.available)
        self.assertEqual(len(export.molecule_rows), 48)
        self.assertEqual(len(export.domain_rows), 1)
        self.assertEqual(len(export.subdomain_rows), 1)
        molecule = export.molecule_rows[0]
        self.assertEqual(molecule["source_frame_index"], 10)
        self.assertIn(molecule["ab_state"], ("A", "B"))
        self.assertIsNotNone(molecule["row_index"])
        self.assertEqual(molecule["stacking_pattern"], "ABAB")
        self.assertEqual(
            len(molecule["stacking_analysis_fingerprint"]),
            64,
        )
        domain = export.domain_rows[0]
        self.assertEqual(domain["pattern"], "ABAB")
        self.assertEqual(domain["qc"], "")
        self.assertEqual(export.manifest["record_counts"]["molecules"], 48)
        self.assertFalse(export.manifest["uses_tracking"])
        self.assertEqual(
            export.manifest["row_assignment_settings"][0][
                "settings_fingerprint"
            ],
            display_settings_fingerprint := (
                state.row_assignments[0].settings_fingerprint
            ),
        )
        self.assertEqual(len(display_settings_fingerprint), 64)

    def test_exports_unassigned_molecules_and_manual_correction_provenance(
        self,
    ) -> None:
        display = _display_with_unassigned_and_corrected_orientation()
        state = MolecularStackingSessionState.from_display_result(display)
        series, _original_state = _series_with_stacking()
        series.molecular_orientations = MolecularOrientationStore(
            frame_count=2,
            measurements=tuple(
                measurement
                for frame in display.frames
                for measurement in frame.measurements
            ),
        )

        export = build_molecular_stacking_export_data(
            series,
            state,
            frame_indices=(0,),
        )

        rows = {row["source_id"]: row for row in export.molecule_rows}
        orphan = rows["zz-orphan"]
        self.assertEqual(orphan["row_assignment_status"], "unavailable")
        self.assertEqual(
            orphan["row_assignment_reason"],
            "not_in_lattice_domain",
        )
        corrected = rows[display.frames[0].measurements[0].provenance.source_id]
        self.assertTrue(corrected["orientation_manual_corrected"])
        self.assertEqual(corrected["orientation_reviewer"], "analyst")
        self.assertEqual(corrected["orientation_note"], "manual review")
        self.assertEqual(corrected["orientation_original_angle_deg"], 20.0)
        self.assertEqual(
            len(corrected["orientation_source_file_sha256"]),
            64,
        )

    def test_range_manifest_exports_before_after_shares_without_tracking(
        self,
    ) -> None:
        series, state = _series_with_stacking()

        export = build_molecular_stacking_export_data(
            series,
            state,
            frame_indices=(0, 1),
            comparison_ranges=(
                MolecularFrameRange("Before desorption", 0, 0),
                MolecularFrameRange("After adsorption", 1, 1),
            ),
        )

        comparison = export.manifest["range_comparison"]
        self.assertFalse(comparison["uses_tracking"])
        self.assertEqual(
            comparison["denominator"],
            "classified_domain_instances",
        )
        self.assertEqual(
            [row["pattern"] for row in comparison["rows"]],
            ["ABAB", "uniform", "mixed"],
        )

    def test_writes_three_stable_csv_tables(self) -> None:
        series, state = _series_with_stacking()
        export = build_molecular_stacking_export_data(
            series,
            state,
            frame_indices=(0,),
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            paths = write_molecular_stacking_tables(tmpdir, export)
            with paths["stacking_molecules_csv"].open(
                "r",
                encoding="utf-8",
                newline="",
            ) as handle:
                rows = list(csv.DictReader(handle))

            self.assertEqual(len(paths), 3)
            self.assertEqual(len(rows), 48)
            self.assertIn("orientation_manual_corrected", rows[0])
            self.assertIn("row_assignment_fingerprint", rows[0])

    def test_missing_or_stale_result_is_explicitly_unavailable(self) -> None:
        series, state = _series_with_stacking()
        series.molecular_orientations = MolecularOrientationStore(frame_count=2)

        missing = build_molecular_stacking_export_data(
            series,
            None,
            frame_indices=(0,),
        )
        stale = build_molecular_stacking_export_data(
            series,
            state,
            frame_indices=(0,),
        )

        self.assertFalse(missing.available)
        self.assertEqual(missing.reason, "stacking_analysis_not_computed")
        self.assertFalse(stale.available)
        self.assertEqual(stale.reason, "stacking_dependencies_changed")

    def test_analysis_package_includes_stacking_tables_and_manifest(self) -> None:
        raw_display = _raw_display_result()
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source_path = root / "movie.mpp"
            source_path.write_bytes(b"stacking export source")
            destination = root / "analysis"
            state = MolecularStackingSessionState.from_display_result(
                raw_display
            )
            series = MolTrackImageSeries(
                source_path=source_path,
                raw_frames=np.zeros((2, 20, 20), dtype=np.float32),
                metadata=STMSequenceMetadata(
                    pixels_x=20,
                    pixels_y=20,
                    size_nm_x=40.0,
                    size_nm_y=40.0,
                ),
                molecular_orientations=MolecularOrientationStore(
                    frame_count=2,
                    measurements=tuple(
                        measurement
                        for frame in raw_display.frames
                        for measurement in frame.measurements
                    ),
                ),
                molecular_stacking_state=state,
            )
            result = export_analysis_package(
                series,
                AnalysisExportSettings(
                    scope="current_frame",
                    destination=destination,
                    package_format="directory",
                    include_tables=True,
                    include_spatial_grids=False,
                    include_plots=False,
                    frame_count=2,
                    active_frame_index=0,
                    source_view="raw",
                    use_segmentation_centroids=True,
                    intensity_metric="background_corrected_median",
                    intensity_unit="a.u.",
                    background_inner_radius_px=1,
                    background_outer_radius_px=3,
                    density_grid_shape=(8, 8),
                    molecular_stacking_state=state,
                ),
            )
            manifest = json.loads(
                (destination / "manifest.json").read_text(encoding="utf-8")
            )

            self.assertIn("stacking_molecules.csv", result.relative_files)
            self.assertIn("stacking_domains.csv", result.relative_files)
            self.assertIn("stacking_subdomains.csv", result.relative_files)
            self.assertTrue(
                manifest["analysis"]["molecular_stacking"]["available"]
            )
            self.assertEqual(manifest["export_schema_version"], 8)
            self.assertEqual(
                manifest["source"]["integrity"]["algorithm"],
                "sha256",
            )

    def test_direct_selected_ranges_export_includes_stacking_contract(
        self,
    ) -> None:
        display = _raw_display_result()
        state = MolecularStackingSessionState.from_display_result(display)
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            series = MolTrackImageSeries(
                source_path=root / "movie.mpp",
                raw_frames=np.zeros((2, 20, 20), dtype=np.float32),
                metadata=STMSequenceMetadata(
                    pixels_x=20,
                    pixels_y=20,
                    size_nm_x=40.0,
                    size_nm_y=40.0,
                ),
                molecular_orientations=MolecularOrientationStore(
                    frame_count=2,
                    measurements=tuple(
                        measurement
                        for frame in display.frames
                        for measurement in frame.measurements
                    ),
                ),
            )
            paths = export_selected_ranges_analysis_csv(
                series,
                MolecularFrameRangeSelection(
                    frame_count=2,
                    source_view="raw",
                    first_range=MolecularFrameRange("Before", 0, 0),
                    second_range=MolecularFrameRange("After", 1, 1),
                ),
                root / "export",
                molecular_stacking_state=state,
            )
            manifest = json.loads(
                paths["manifest_json"].read_text(encoding="utf-8")
            )

        self.assertIn("stacking_molecules_csv", paths)
        self.assertIn("stacking_domains_csv", paths)
        self.assertIn("stacking_subdomains_csv", paths)
        stacking_manifest = manifest["analysis"]["molecular_stacking"]
        self.assertTrue(stacking_manifest["available"])
        self.assertFalse(
            stacking_manifest["range_comparison"]["uses_tracking"]
        )


if __name__ == "__main__":
    unittest.main()
