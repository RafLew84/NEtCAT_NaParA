import csv
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

import numpy as np

from moltrack.analysis import (
    MolecularFrameRange,
    MolecularFrameRangeAnalysisScope,
    MolecularFrameRangeSelection,
    MolecularOrderTypeClassificationSettings,
    classify_molecular_order_types,
)
from moltrack.core import MolTrackImageSeries
from moltrack.persistence import (
    AnalysisExportSettings,
    build_molecular_order_type_export_data,
    export_analysis_package,
    write_molecular_order_type_tables,
)
from nanotrack.core import STMSequenceMetadata
from test_molecular_order_type_classifier import _domain_frame, _hierarchy


def _raw_hierarchy_and_classification():
    hierarchy = replace(
        _hierarchy(
            _domain_frame(0),
            _domain_frame(
                2,
                symmetry="sixfold",
                theta3_deg=None,
                theta6_deg=30.0,
                orientation_angles=(40.0,),
                stacking_pattern="uniform",
            ),
        ),
        source_view="raw",
    )
    scope = MolecularFrameRangeAnalysisScope(
        analysis_mode="compare_ranges",
        frame_count=3,
        source_view="raw",
        ranges=(
            MolecularFrameRange("before", 0, 0),
            MolecularFrameRange("after", 2, 2),
        ),
    )
    classification = classify_molecular_order_types(
        hierarchy,
        analysis_scope=scope,
        settings=MolecularOrderTypeClassificationSettings(),
    )
    return hierarchy, classification


class MolecularOrderTypeExportTests(unittest.TestCase):
    def test_builds_auditable_hierarchy_type_assignment_and_share_rows(
        self,
    ) -> None:
        hierarchy, classification = _raw_hierarchy_and_classification()

        export = build_molecular_order_type_export_data(
            hierarchy,
            classification,
            frame_indices=(0, 2),
            tables_included=True,
        )

        self.assertTrue(export.available)
        self.assertEqual(len(export.hierarchy_rows), 2)
        self.assertEqual(len(export.assignment_rows), 2)
        self.assertEqual(
            {row["layer"] for row in export.type_rows},
            {"geometry", "orientation", "stacking"},
        )
        self.assertTrue(export.range_share_rows)
        assignment = export.assignment_rows[0]
        self.assertIn("geometry_status", assignment)
        self.assertIn("orientation_unclassified_reason", assignment)
        self.assertIn("representative_source_ids_json", assignment)
        self.assertEqual(
            assignment["hierarchy_fingerprint"],
            classification.hierarchy_fingerprint,
        )
        self.assertFalse(export.manifest["uses_tracking"])
        self.assertEqual(
            export.manifest["type_catalog_scope"],
            "classification_analysis_scope",
        )
        self.assertEqual(
            export.manifest["range_share_scope"],
            "classification_analysis_scope",
        )
        self.assertEqual(
            export.manifest["classification_fingerprint"],
            export.classification_fingerprint,
        )

    def test_unavailable_or_out_of_scope_result_does_not_claim_tables(
        self,
    ) -> None:
        unavailable = build_molecular_order_type_export_data(
            None,
            None,
            frame_indices=(0,),
            tables_included=True,
        )
        hierarchy, classification = _raw_hierarchy_and_classification()
        outside_scope = build_molecular_order_type_export_data(
            hierarchy,
            classification,
            frame_indices=(),
            tables_included=True,
        )

        self.assertFalse(unavailable.available)
        self.assertFalse(unavailable.manifest["tables_included"])
        self.assertFalse(outside_scope.available)
        self.assertEqual(
            outside_scope.manifest["reason"],
            "no_hierarchical_results_for_exported_frames",
        )
        self.assertFalse(outside_scope.manifest["tables_included"])

    def test_writes_four_stable_csv_tables(self) -> None:
        hierarchy, classification = _raw_hierarchy_and_classification()
        export = build_molecular_order_type_export_data(
            hierarchy,
            classification,
            frame_indices=(0, 2),
            tables_included=True,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            paths = write_molecular_order_type_tables(tmpdir, export)
            with paths["molecular_order_assignments_csv"].open(
                "r",
                encoding="utf-8",
                newline="",
            ) as handle:
                assignments = list(csv.DictReader(handle))

        self.assertEqual(len(paths), 4)
        self.assertEqual(len(assignments), 2)
        self.assertEqual(assignments[0]["uses_tracking"], "False")

    def test_analysis_package_includes_tables_and_manifest(self) -> None:
        hierarchy, classification = _raw_hierarchy_and_classification()
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "movie.mpp"
            source.write_bytes(b"molecular order export source")
            destination = root / "analysis"
            series = MolTrackImageSeries(
                source_path=source,
                raw_frames=np.zeros((3, 8, 8), dtype=np.float32),
                metadata=STMSequenceMetadata(
                    pixels_x=8,
                    pixels_y=8,
                    size_nm_x=80.0,
                    size_nm_y=80.0,
                ),
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
                    frame_count=3,
                    active_frame_index=0,
                    source_view="raw",
                    use_segmentation_centroids=True,
                    intensity_metric="background_corrected_median",
                    intensity_unit="a.u.",
                    background_inner_radius_px=1,
                    background_outer_radius_px=3,
                    density_grid_shape=(8, 8),
                    molecular_order_hierarchy=hierarchy,
                    molecular_order_type_classification=classification,
                ),
            )
            manifest = json.loads(
                (destination / "manifest.json").read_text(encoding="utf-8")
            )

        self.assertIn(
            "molecular_order_assignments.csv",
            result.relative_files,
        )
        order_manifest = manifest["analysis"]["molecular_order_types"]
        self.assertTrue(order_manifest["available"])
        self.assertFalse(order_manifest["uses_tracking"])
        self.assertEqual(order_manifest["exported_frame_indices"], [0])

    def test_selected_ranges_package_exports_both_conditions(self) -> None:
        hierarchy, classification = _raw_hierarchy_and_classification()
        selection = MolecularFrameRangeSelection(
            frame_count=3,
            source_view="raw",
            first_range=MolecularFrameRange("before", 0, 0),
            second_range=MolecularFrameRange("after", 2, 2),
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "movie.mpp"
            source.write_bytes(b"molecular order range export source")
            destination = root / "analysis"
            series = MolTrackImageSeries(
                source_path=source,
                raw_frames=np.zeros((3, 8, 8), dtype=np.float32),
                metadata=STMSequenceMetadata(
                    pixels_x=8,
                    pixels_y=8,
                    size_nm_x=80.0,
                    size_nm_y=80.0,
                ),
            )

            result = export_analysis_package(
                series,
                AnalysisExportSettings(
                    scope="selected_ranges",
                    destination=destination,
                    package_format="directory",
                    include_tables=True,
                    include_spatial_grids=False,
                    include_plots=False,
                    frame_count=3,
                    active_frame_index=0,
                    source_view="raw",
                    use_segmentation_centroids=True,
                    intensity_metric="background_corrected_median",
                    intensity_unit="a.u.",
                    background_inner_radius_px=1,
                    background_outer_radius_px=3,
                    density_grid_shape=(8, 8),
                    selected_ranges=selection,
                    molecular_order_hierarchy=hierarchy,
                    molecular_order_type_classification=classification,
                ),
            )
            with (
                (destination / "molecular_order_assignments.csv").open(
                    "r",
                    encoding="utf-8",
                    newline="",
                ) as handle
            ):
                assignments = list(csv.DictReader(handle))
            manifest = json.loads(
                (destination / "manifest.json").read_text(encoding="utf-8")
            )

        self.assertIn(
            "molecular_order_range_shares.csv",
            result.relative_files,
        )
        self.assertEqual(
            {int(row["working_frame_index"]) for row in assignments},
            {0, 2},
        )
        self.assertEqual(
            manifest["analysis"]["molecular_order_types"][
                "exported_frame_indices"
            ],
            [0, 2],
        )


if __name__ == "__main__":
    unittest.main()
