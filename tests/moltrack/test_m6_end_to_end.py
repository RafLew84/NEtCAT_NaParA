import csv
import json
import math
import tempfile
import time
import unittest
from functools import lru_cache
from pathlib import Path

import numpy as np

from moltrack.analysis import (
    MolecularFrameRange,
    MolecularFrameRangeSelection,
    MolecularM6SessionState,
    compare_molecular_frame_ranges,
    load_m6_headless_validation_manifest,
    run_m6_headless_validation,
)
from moltrack.core import (
    MolTrackImageSeries,
    MolTrackRegistrationFrameResult,
    MolTrackRegistrationResultSet,
    MolTrackRegistrationSettings,
    MolecularDetection,
    MolecularDetectionSet,
    RegisteredFrameTransform,
    build_moltrack_expanded_aligned_stack,
)
from moltrack.persistence import (
    export_selected_ranges_analysis_csv,
    load_moltrack_session,
    restore_moltrack_image_series_from_session,
    save_moltrack_session,
)
from nanotrack.core import STMSequenceMetadata


FIXTURE_PATH = (
    Path(__file__).parent
    / "fixtures"
    / "m6_headless_validation_ttmapp.json"
)

_FRAME_AGGREGATE_FIELDS = (
    "full_domain_count",
    "small_ordered_island_count",
    "ordered_component_count",
    "original_observation_count",
    "valid_representative_count",
    "duplicate_excluded_count",
    "invalid_position_count",
    "valid_fov_area_nm2",
    "supported_area_nm2",
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
    "mean_local_q6_interior",
    "global_q6_interior",
    "mean_local_q6_all_valid",
    "global_q6_all_valid",
    "edge_truncated_fraction_of_valid_representatives",
    "full_domain_molecule_weighted_coherent_q6",
    "full_domain_footprint_weighted_coherent_q6",
    "mean_full_domain_footprint_area_nm2",
    "median_full_domain_footprint_area_nm2",
    "domain_molecule_entropy",
    "domain_footprint_entropy",
)

_COMPONENT_METRIC_FIELDS = (
    "orientation_deg",
    "centroid_x_nm",
    "centroid_y_nm",
    "min_x_nm",
    "min_y_nm",
    "max_x_nm",
    "max_y_nm",
    "domain_mean_local_q6",
    "domain_coherent_q6",
    "domain_median_bond_length_nm",
    "domain_bond_length_mad_nm",
    "domain_bond_length_iqr_nm",
    "domain_bond_length_robust_cv",
)

_DOMAIN_EXPORT_FIELDS = (
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
)

_RELATIVE_TOLERANCE = 1e-10
_DIMENSIONLESS_ABSOLUTE_TOLERANCE = 1e-9
_ANGLE_ABSOLUTE_TOLERANCE_DEG = 1e-8
_LENGTH_ABSOLUTE_TOLERANCE_NM = 1e-7
_AREA_ABSOLUTE_TOLERANCE_NM2 = 1e-5
_REPRESENTATIVE_ANALYSIS_TIMEOUT_S = 90.0


def _fixture_frames(manifest, source_view: str):
    return tuple(
        sorted(
            (
                frame
                for frame in manifest.frames
                if frame.source_view == source_view
            ),
            key=lambda frame: frame.source_frame_index,
        )
    )


def _raw_fixture_frames(manifest):
    return _fixture_frames(manifest, "raw")


@lru_cache(maxsize=1)
def _representative_fixture():
    manifest = load_m6_headless_validation_manifest(FIXTURE_PATH)
    return manifest, run_m6_headless_validation(manifest)


def _representative_series(
    manifest,
    source_path: Path,
    *,
    include_detections: bool = True,
) -> MolTrackImageSeries:
    frames = _raw_fixture_frames(manifest)
    aligned_frames = _fixture_frames(manifest, "expanded_aligned")
    pixel_count = 256
    field_size_nm = float(frames[0].window_size_nm[0])
    pixel_size_nm = field_size_nm / pixel_count
    detections = None
    if include_detections:
        detections = MolecularDetectionSet(frame_count=len(frames))
        for working_frame_index, frame in enumerate(frames):
            frame_detections = []
            for point_id, (x_nm, y_nm) in zip(frame.point_ids, frame.points_xy_nm):
                x_px = x_nm / pixel_size_nm
                y_px = pixel_count - y_nm / pixel_size_nm
                frame_detections.append(
                    MolecularDetection(
                        frame_index=working_frame_index,
                        bbox_xyxy=(
                            x_px - 0.05,
                            y_px - 0.05,
                            x_px + 0.05,
                            y_px + 0.05,
                        ),
                        confidence=0.9,
                        detection_id=point_id,
                    )
                )
            detections.set_detections(
                working_frame_index,
                frame_detections,
                source_view="raw",
                frame_shape=(pixel_count, pixel_count),
            )
    reference_origin_nm = np.asarray(aligned_frames[0].window_origin_nm)
    registration_results = MolTrackRegistrationResultSet(
        settings=MolTrackRegistrationSettings(backend="optical_flow_median"),
        results_by_frame={
            frame_index: MolTrackRegistrationFrameResult(
                frame_index=frame_index,
                shift_xy=(
                    (
                        aligned_frame.window_origin_nm[0]
                        - reference_origin_nm[0]
                    )
                    / pixel_size_nm,
                    -(
                        aligned_frame.window_origin_nm[1]
                        - reference_origin_nm[1]
                    )
                    / pixel_size_nm,
                ),
                method="optical_flow_median",
                quality_score=1.0,
            )
            for frame_index, aligned_frame in enumerate(aligned_frames)
        },
    )
    series = MolTrackImageSeries(
        source_path=str(source_path),
        raw_frames=np.zeros(
            (len(frames), pixel_count, pixel_count),
            dtype=np.float32,
        ),
        metadata=STMSequenceMetadata(
            raw_header={"General Info": {"Angle": "0.0"}},
            pixels_x=pixel_count,
            pixels_y=pixel_count,
            size_nm_x=field_size_nm,
            size_nm_y=field_size_nm,
            scan_angle_deg=0.0,
        ),
        registration_results=registration_results,
        molecular_detections=detections,
        source_frame_indices=tuple(frame.source_frame_index for frame in frames),
    )
    expanded = build_moltrack_expanded_aligned_stack(
        series,
        interpolation_order=0,
    )
    if detections is not None:
        expanded_shape = tuple(int(value) for value in expanded.frames.shape[1:])
        for frame_index in range(series.frame_count):
            transform = RegisteredFrameTransform(
                raw_shape=series.frame_shape,
                expanded_shape=expanded_shape,
                frame_origin_xy=tuple(expanded.frame_origins_xy[frame_index]),
            )
            expanded_detections = tuple(
                transform.raw_detection_to_expanded(detection)
                for detection in detections.get_detections(
                    frame_index,
                    source_view="raw",
                )
            )
            detections.set_detections(
                frame_index,
                expanded_detections,
                source_view="expanded_aligned",
                frame_shape=expanded_shape,
            )
    return series


def _selection(source_view: str = "raw") -> MolecularFrameRangeSelection:
    return MolecularFrameRangeSelection(
        frame_count=2,
        source_view=source_view,
        first_range=MolecularFrameRange("initial", 0, 0),
        second_range=MolecularFrameRange("re-adsorbed", 1, 1),
    )


def _analysis_by_source_frame(comparison):
    results = (
        comparison.first_analysis.frame_results
        + comparison.second_analysis.frame_results
    )
    return {result.source_frame_index: result for result in results}


def _headless_for_view(report, source_view: str):
    return {
        result.frame.source_frame_index: result
        for result in report.frame_results
        if result.frame.source_view == source_view
    }


def _headless_translation(manifest, source_view: str) -> tuple[float, float]:
    if source_view == "raw":
        return 0.0, 0.0
    reference = _fixture_frames(manifest, source_view)[0]
    return -reference.window_origin_nm[0], -reference.window_origin_nm[1]


def _absolute_tolerance(field_name: str) -> float:
    if "nm2" in field_name or "area" in field_name:
        return _AREA_ABSOLUTE_TOLERANCE_NM2
    if "deg" in field_name or "orientation" in field_name:
        return _ANGLE_ABSOLUTE_TOLERANCE_DEG
    if field_name.endswith("_nm") or field_name in {
        "position_x",
        "position_y",
        "centroid_x_nm",
        "centroid_y_nm",
        "min_x_nm",
        "min_y_nm",
        "max_x_nm",
        "max_y_nm",
    }:
        return _LENGTH_ABSOLUTE_TOLERANCE_NM
    return _DIMENSIONLESS_ABSOLUTE_TOLERANCE


def _detection_snapshot(series: MolTrackImageSeries) -> tuple[tuple[object, ...], ...]:
    if series.molecular_detections is None:
        return ()
    return tuple(
        (
            source_view,
            frame_index,
            detection.detection_id,
            detection.bbox_xyxy,
            detection.confidence,
        )
        for source_view in ("raw", "expanded_aligned")
        for frame_index in range(series.frame_count)
        for detection in series.molecular_detections.get_detections(
            frame_index,
            source_view=source_view,
        )
    )


def _expected_molecule_values(
    headless_result,
    source_id: str,
    *,
    translation_xy: tuple[float, float] = (0.0, 0.0),
) -> dict[str, object]:
    analysis = headless_result.analysis
    assert analysis is not None
    point_index = headless_result.frame.point_ids.index(source_id)
    local = analysis.local_order
    segmentation = analysis.segmentation
    graph = analysis.first_shell_graph
    psi6 = local.psi6[point_index]
    ordered_component_id = segmentation.ordered_component_id[point_index]
    domain_id = segmentation.m6_orientation_domain_id[point_index]
    x_nm, y_nm = headless_result.frame.points_xy_nm[point_index]
    x_nm += translation_xy[0]
    y_nm += translation_xy[1]
    return {
        "position_x": x_nm,
        "position_y": y_nm,
        "position_unit": "nm",
        "neighbor_count": local.neighbor_count[point_index],
        "psi6_real": None if psi6 is None else psi6.real,
        "psi6_imag": None if psi6 is None else psi6.imag,
        "q6": local.q6[point_index],
        "lattice_orientation_deg": local.lattice_orientation_deg[point_index],
        "orientation_status": local.orientation_status[point_index],
        "ordered_component_id": (
            None if ordered_component_id < 0 else ordered_component_id
        ),
        "m6_orientation_domain_id": None if domain_id < 0 else domain_id,
        "component_type": segmentation.component_type[point_index],
        "order_qc": local.computation_status[point_index],
        "local_median_bond_length_nm": local.local_median_bond_length_nm[point_index],
        "local_bond_length_mad_nm": local.local_bond_length_mad_nm[point_index],
        "local_bond_length_iqr_nm": local.local_bond_length_iqr_nm[point_index],
        "local_bond_length_robust_cv": local.local_bond_length_robust_cv[point_index],
        "representative_source_id": graph.representative_source_ids[point_index],
        "duplicate_parent_component_id": graph.duplicate_parent_component_ids[point_index],
        "duplicate_parent_component_diameter_nm": (
            graph.duplicate_parent_component_diameters_nm[point_index]
        ),
        "duplicate_group_id": graph.duplicate_group_ids[point_index],
        "duplicate_group_diameter_nm": graph.duplicate_group_diameters_nm[point_index],
        "duplicate_chain_qc": graph.duplicate_chain_qc[point_index],
        "physical_duplicate_qc": graph.physical_duplicate_qc[point_index],
        "geometry_duplicate_qc": graph.geometry_duplicate_qc[point_index],
        "coordinate_frame": graph.coordinate_frame,
        "orientation_reference": graph.orientation_reference,
    }


class M6ScientificAssertionsMixin:
    def assert_optional_close(self, field_name: str, actual, expected) -> None:
        if expected is None:
            self.assertIsNone(actual)
        elif isinstance(expected, (float, np.floating)):
            self.assertTrue(
                math.isclose(
                    float(actual),
                    float(expected),
                    rel_tol=_RELATIVE_TOLERANCE,
                    abs_tol=_absolute_tolerance(field_name),
                ),
                f"{field_name}: {actual!r} != {expected!r}",
            )
        else:
            self.assertEqual(actual, expected)

    def assert_csv_value(self, field_name: str, actual: str, expected) -> None:
        if expected is None:
            self.assertEqual(actual, "")
        elif isinstance(expected, (int, bool)):
            self.assertEqual(actual, str(expected))
        elif isinstance(expected, str):
            self.assertEqual(actual, expected)
        else:
            self.assertTrue(
                math.isclose(
                    float(actual),
                    float(expected),
                    rel_tol=_RELATIVE_TOLERANCE,
                    abs_tol=_absolute_tolerance(field_name),
                ),
                f"{field_name}: {actual!r} != {expected!r}",
            )

    def assert_analysis_matches_headless(self, frame_result, headless_result) -> None:
        self.assert_analysis_matches_translated_headless(
            frame_result,
            headless_result,
            translation_xy=(0.0, 0.0),
        )

    def assert_analysis_matches_translated_headless(
        self,
        frame_result,
        headless_result,
        *,
        translation_xy: tuple[float, float],
    ) -> None:
        analysis = frame_result.m6_orientation_analysis
        self.assertIsNotNone(analysis)
        self.assertIsNotNone(headless_result.analysis)
        assert analysis is not None and headless_result.analysis is not None
        expected = headless_result.analysis
        expected_points = np.asarray(headless_result.frame.points_xy_nm) + np.asarray(
            translation_xy
        )
        np.testing.assert_allclose(
            analysis.points_xy_nm,
            expected_points,
            rtol=_RELATIVE_TOLERANCE,
            atol=_LENGTH_ABSOLUTE_TOLERANCE_NM,
        )
        self.assertEqual(analysis.point_source_ids, headless_result.frame.point_ids)
        expected_origin = np.asarray(headless_result.frame.window_origin_nm) + np.asarray(
            translation_xy
        )
        expected_width, expected_height = headless_result.frame.window_size_nm
        expected_valid_fov = (
            (expected_origin[0], expected_origin[1]),
            (expected_origin[0] + expected_width, expected_origin[1]),
            (
                expected_origin[0] + expected_width,
                expected_origin[1] + expected_height,
            ),
            (expected_origin[0], expected_origin[1] + expected_height),
        )
        np.testing.assert_allclose(
            analysis.sample_coordinates.valid_fov_polygon_xy_nm,
            expected_valid_fov,
            rtol=_RELATIVE_TOLERANCE,
            atol=_LENGTH_ABSOLUTE_TOLERANCE_NM,
        )
        self.assertEqual(analysis.coordinate_frame, "sample_nm")
        self.assertEqual(
            analysis.orientation_reference,
            headless_result.frame.orientation_reference,
        )
        self.assertEqual(
            analysis.first_shell_graph.construction_method,
            expected.first_shell_graph.construction_method,
        )
        self.assertEqual(
            analysis.frame_aggregates.footprint_partition.footprint_construction_method,
            expected.footprint_partition.footprint_construction_method,
        )
        for field_name in _FRAME_AGGREGATE_FIELDS:
            with self.subTest(
                source_frame=frame_result.source_frame_index,
                field=field_name,
            ):
                self.assert_optional_close(
                    field_name,
                    getattr(analysis.frame_aggregates, field_name),
                    getattr(expected.frame_aggregates, field_name),
                )
        actual_components = analysis.frame_aggregates.domain_metrics.components
        expected_components = expected.frame_aggregates.domain_metrics.components
        self.assertEqual(
            tuple(component.source_ids for component in actual_components),
            tuple(component.source_ids for component in expected_components),
        )
        for actual_component, expected_component in zip(
            actual_components, expected_components
        ):
            self.assertEqual(
                (
                    actual_component.ordered_component_id,
                    actual_component.m6_orientation_domain_id,
                    actual_component.component_type,
                    actual_component.molecule_count,
                ),
                (
                    expected_component.ordered_component_id,
                    expected_component.m6_orientation_domain_id,
                    expected_component.component_type,
                    expected_component.molecule_count,
                ),
            )
            for field_name in _COMPONENT_METRIC_FIELDS:
                expected_value = getattr(expected_component, field_name)
                if expected_value is not None:
                    if field_name in {"centroid_x_nm", "min_x_nm", "max_x_nm"}:
                        expected_value += translation_xy[0]
                    elif field_name in {"centroid_y_nm", "min_y_nm", "max_y_nm"}:
                        expected_value += translation_xy[1]
                self.assert_optional_close(
                    field_name,
                    getattr(actual_component, field_name),
                    expected_value,
                )
        np.testing.assert_allclose(
            analysis.pair_correlation.g_r,
            headless_result.pair_correlation.g_r,
            rtol=1e-10,
            atol=1e-10,
            equal_nan=True,
        )


class M6EndToEndRegressionTests(
    M6ScientificAssertionsMixin,
    unittest.TestCase,
):
    def test_representative_fixture_matches_after_session_and_csv_round_trip(self) -> None:
        manifest, headless_report = _representative_fixture()
        raw_frames = _raw_fixture_frames(manifest)
        raw_headless_results = _headless_for_view(headless_report, "raw")
        aligned_headless_results = _headless_for_view(
            headless_report,
            "expanded_aligned",
        )
        aligned_translation = _headless_translation(
            manifest,
            "expanded_aligned",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source_path = root / "representative.mpp"
            source_path.write_bytes(b"M6 representative fixture")
            series = _representative_series(manifest, source_path)
            settings = manifest.accepted_settings
            progress_events = []

            raw_comparison = compare_molecular_frame_ranges(
                series,
                _selection("raw"),
                m6_orientation_settings=settings,
            )
            for source_frame_index, result in _analysis_by_source_frame(
                raw_comparison
            ).items():
                self.assert_analysis_matches_headless(
                    result,
                    raw_headless_results[source_frame_index],
                )

            started = time.perf_counter()
            comparison = compare_molecular_frame_ranges(
                series,
                _selection("expanded_aligned"),
                progress_callback=lambda completed, total, frame: (
                    progress_events.append((completed, total, frame))
                ),
                m6_orientation_settings=settings,
            )
            elapsed = time.perf_counter() - started
            self.assertLess(elapsed, _REPRESENTATIVE_ANALYSIS_TIMEOUT_S)
            self.assertEqual(progress_events, [(1, 2, 0), (2, 2, 1)])
            for source_frame_index, result in _analysis_by_source_frame(
                comparison
            ).items():
                self.assert_analysis_matches_translated_headless(
                    result,
                    aligned_headless_results[source_frame_index],
                    translation_xy=aligned_translation,
                )

            series.m6_analysis_state = MolecularM6SessionState(
                enabled=True,
                source_view="expanded_aligned",
                use_segmentation_centroids=True,
                settings=settings,
            )
            session_path = root / "representative.moltrack.json"
            save_moltrack_session(session_path, series)
            loaded_session = load_moltrack_session(session_path)
            self.assertEqual(loaded_session.m6_analysis_state, series.m6_analysis_state)
            self.assertEqual(len(loaded_session.structural_analysis_cache_records), 4)

            source_only_series = None

            def source_only_loader(path, *, reverse_frame_order=False):
                nonlocal source_only_series
                self.assertFalse(reverse_frame_order)
                source_only_series = _representative_series(
                    manifest,
                    Path(path),
                    include_detections=False,
                )
                return source_only_series

            restored = restore_moltrack_image_series_from_session(
                loaded_session,
                series_loader=source_only_loader,
            )
            self.assertIsNotNone(source_only_series)
            self.assertEqual(_detection_snapshot(source_only_series), ())
            self.assertEqual(_detection_snapshot(restored), _detection_snapshot(series))
            self.assertEqual(restored.m6_analysis_state, series.m6_analysis_state)
            restored_cache = restored.structural_analysis_cache
            self.assertEqual(len(restored_cache.keys()), 4)
            self.assertEqual(restored_cache.stats().hit_count, 0)
            self.assertEqual(restored_cache.stats().miss_count, 0)
            self.assertIsNone(restored.expanded_aligned_stack)
            build_moltrack_expanded_aligned_stack(
                restored,
                interpolation_order=0,
            )

            restored_comparison = compare_molecular_frame_ranges(
                restored,
                _selection("expanded_aligned"),
                m6_orientation_settings=loaded_session.m6_analysis_state.settings,
            )
            self.assertEqual(restored_cache.stats().miss_count, 2)
            for source_frame_index, result in _analysis_by_source_frame(
                restored_comparison
            ).items():
                self.assert_analysis_matches_translated_headless(
                    result,
                    aligned_headless_results[source_frame_index],
                    translation_xy=aligned_translation,
                )

            restored_raw_comparison = compare_molecular_frame_ranges(
                restored,
                _selection("raw"),
                m6_orientation_settings=loaded_session.m6_analysis_state.settings,
            )
            self.assertEqual(restored_cache.stats().miss_count, 4)
            for source_frame_index, result in _analysis_by_source_frame(
                restored_raw_comparison
            ).items():
                self.assert_analysis_matches_headless(
                    result,
                    raw_headless_results[source_frame_index],
                )

            cache_hits_before_export = (
                restored.structural_analysis_cache.stats().hit_count
            )
            raw_export_paths = export_selected_ranges_analysis_csv(
                restored,
                _selection("raw"),
                root / "raw-export",
                m6_orientation_settings=settings,
            )
            export_paths = export_selected_ranges_analysis_csv(
                restored,
                _selection("expanded_aligned"),
                root / "export",
                m6_orientation_settings=settings,
            )
            self.assertGreater(
                restored.structural_analysis_cache.stats().hit_count,
                cache_hits_before_export,
            )
            with export_paths["frames_csv"].open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                frame_rows = list(csv.DictReader(handle))
            with export_paths["domains_csv"].open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                domain_rows = list(csv.DictReader(handle))
            with export_paths["molecules_csv"].open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                molecule_rows = list(csv.DictReader(handle))
            export_manifest = json.loads(
                export_paths["manifest_json"].read_text(encoding="utf-8")
            )
            with raw_export_paths["frames_csv"].open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                raw_frame_rows = list(csv.DictReader(handle))
            with raw_export_paths["molecules_csv"].open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                raw_molecule_rows = list(csv.DictReader(handle))

        self.assertEqual(
            [row["source_view"] for row in raw_frame_rows],
            ["raw", "raw"],
        )
        for row in raw_frame_rows:
            headless = raw_headless_results[int(row["source_frame_index"])]
            for field_name in _FRAME_AGGREGATE_FIELDS:
                self.assert_csv_value(
                    field_name,
                    row[field_name],
                    getattr(headless.analysis.frame_aggregates, field_name),
                )
        for row in raw_molecule_rows:
            self.assertEqual(row["source_view"], "raw")
            headless = raw_headless_results[int(row["source_frame_index"])]
            expected = _expected_molecule_values(headless, row["source_id"])
            self.assert_csv_value("position_x", row["position_x"], expected["position_x"])
            self.assert_csv_value("position_y", row["position_y"], expected["position_y"])

        self.assertTrue(frame_rows)
        self.assertTrue(
            {
                "condition_name",
                "source_frame_index",
                "source_view",
                "construction_method",
                "footprint_construction_method",
                "coordinate_frame",
                "orientation_reference",
                "spatial_calibration_fingerprint",
                "registration_fingerprint",
                "point_coordinate_fingerprint",
                *_FRAME_AGGREGATE_FIELDS,
            }.issubset(frame_rows[0])
        )
        self.assertEqual(
            [int(row["source_frame_index"]) for row in frame_rows],
            [0, 250],
        )
        self.assertTrue(molecule_rows)
        self.assertTrue(
            {
                "condition_name",
                "source_frame_index",
                "source_view",
                "source_kind",
                "source_id",
                "position_x",
                "position_y",
                "coordinate_frame",
                "orientation_reference",
            }.issubset(molecule_rows[0])
        )
        self.assertTrue(domain_rows)
        self.assertTrue(
            {
                "condition_name",
                "source_frame_index",
                "source_view",
                "ordered_component_id",
                "m6_orientation_domain_id",
                "component_type",
                "molecule_count",
                "coordinate_frame",
                "orientation_reference",
                *_DOMAIN_EXPORT_FIELDS,
            }.issubset(domain_rows[0])
        )
        self.assertEqual(export_manifest["export_schema_version"], 7)
        exported_m6 = export_manifest["analysis"]["m6_orientation"]
        self.assertEqual(exported_m6["settings"], settings.to_dict())
        self.assertEqual(exported_m6["coordinate_convention"]["coordinate_frame"], "sample_nm")
        self.assertEqual(
            exported_m6["pair_correlation"]["bin_width_nm"],
            settings.gr_bin_width_nm,
        )
        exported_methods = {
            int(row["source_frame_index"]): row["construction_method"]
            for row in frame_rows
        }
        for source_frame_index, headless_result in aligned_headless_results.items():
            self.assertEqual(
                exported_methods[source_frame_index],
                headless_result.first_shell_graph.construction_method,
            )
        for row in frame_rows:
            source_frame_index = int(row["source_frame_index"])
            headless = aligned_headless_results[source_frame_index]
            aggregates = headless.analysis.frame_aggregates
            self.assertEqual(row["source_view"], "expanded_aligned")
            self.assertEqual(row["coordinate_frame"], "sample_nm")
            self.assertEqual(
                row["orientation_reference"],
                headless.frame.orientation_reference,
            )
            self.assertTrue(row["spatial_calibration_fingerprint"])
            self.assertTrue(row["registration_fingerprint"])
            self.assertTrue(row["point_coordinate_fingerprint"])
            for field_name in _FRAME_AGGREGATE_FIELDS:
                with self.subTest(
                    source_frame=row["source_frame_index"],
                    csv_field=field_name,
                ):
                    self.assert_csv_value(
                        field_name,
                        row[field_name],
                        getattr(aggregates, field_name),
                    )

        molecule_keys = tuple(
            (int(row["source_frame_index"]), row["source_id"])
            for row in molecule_rows
        )
        expected_molecule_keys = {
            (frame.source_frame_index, source_id)
            for frame in raw_frames
            for source_id in frame.point_ids
        }
        self.assertEqual(len(molecule_keys), len(set(molecule_keys)))
        self.assertEqual(set(molecule_keys), expected_molecule_keys)
        self.assertEqual(len(molecule_rows), len(expected_molecule_keys))
        for row in molecule_rows:
            source_frame_index = int(row["source_frame_index"])
            headless = aligned_headless_results[source_frame_index]
            expected_values = _expected_molecule_values(
                headless,
                row["source_id"],
                translation_xy=aligned_translation,
            )
            self.assertEqual(row["source_kind"], "bbox")
            self.assertEqual(row["source_view"], "expanded_aligned")
            for field_name, expected_value in expected_values.items():
                with self.subTest(
                    source_frame=source_frame_index,
                    source_id=row["source_id"],
                    csv_field=field_name,
                ):
                    self.assert_csv_value(
                        field_name,
                        row[field_name],
                        expected_value,
                    )

        expected_domain_keys = {
            (source_frame_index, component.ordered_component_id)
            for source_frame_index, headless in aligned_headless_results.items()
            for component in headless.analysis.domain_metrics.components
        }
        domain_keys = tuple(
            (int(row["source_frame_index"]), int(row["ordered_component_id"]))
            for row in domain_rows
        )
        self.assertEqual(len(domain_keys), len(set(domain_keys)))
        self.assertEqual(set(domain_keys), expected_domain_keys)
        domain_rows_by_key = {
            (int(row["source_frame_index"]), int(row["ordered_component_id"])): row
            for row in domain_rows
        }
        for source_frame_index, headless in aligned_headless_results.items():
            footprints_by_id = {
                footprint.ordered_component_id: footprint
                for footprint in headless.analysis.footprint_partition.components
            }
            for component in headless.analysis.domain_metrics.components:
                row = domain_rows_by_key[
                    (source_frame_index, component.ordered_component_id)
                ]
                footprint = footprints_by_id[component.ordered_component_id]
                expected_values = {
                    field_name: getattr(component, field_name)
                    for field_name in _DOMAIN_EXPORT_FIELDS
                    if hasattr(component, field_name)
                }
                for field_name in ("centroid_x_nm", "min_x_nm", "max_x_nm"):
                    expected_values[field_name] += aligned_translation[0]
                for field_name in ("centroid_y_nm", "min_y_nm", "max_y_nm"):
                    expected_values[field_name] += aligned_translation[1]
                expected_values.update(
                    {
                        "footprint_area_nm2": footprint.footprint_area_nm2,
                        "footprint_fraction_of_valid_fov": (
                            footprint.footprint_fraction_of_valid_fov
                        ),
                        "edge_truncated": footprint.edge_truncated,
                        "footprint_disconnected_qc": (
                            footprint.footprint_disconnected_qc
                        ),
                        "insufficient_bonds_for_length_stats_qc": (
                            component.insufficient_bonds_for_length_stats_qc
                        ),
                        "bond_length_heterogeneity_qc": (
                            component.bond_length_heterogeneity_qc
                        ),
                    }
                )
                self.assertEqual(
                    row["m6_orientation_domain_id"],
                    ""
                    if component.m6_orientation_domain_id is None
                    else str(component.m6_orientation_domain_id),
                )
                self.assertEqual(row["component_type"], component.component_type)
                self.assertEqual(int(row["molecule_count"]), component.molecule_count)
                self.assertEqual(row["source_view"], "expanded_aligned")
                self.assertEqual(row["coordinate_frame"], "sample_nm")
                self.assertEqual(
                    row["orientation_reference"],
                    headless.frame.orientation_reference,
                )
                for field_name, expected in expected_values.items():
                    with self.subTest(
                        source_frame=source_frame_index,
                        component=component.ordered_component_id,
                        csv_field=field_name,
                    ):
                        self.assert_csv_value(field_name, row[field_name], expected)

if __name__ == "__main__":
    unittest.main()
