import math
import time
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import numpy as np
from scipy.spatial import QhullError

from moltrack.analysis import (
    M6_ORIENTATION_ALGORITHM_VERSION,
    M6HeadlessValidationFrame,
    M6HeadlessValidationManifest,
    MolecularM6OrientationAnalysisSettings,
    load_m6_headless_validation_manifest,
    run_m6_headless_validation,
)


FIXTURE_PATH = (
    Path(__file__).parent
    / "fixtures"
    / "m6_headless_validation_ttmapp.json"
)


def _triangular_patch(
    angle_deg: float,
    shift_xy_nm: tuple[float, float],
    *,
    width: int = 8,
    height: int = 8,
    spacing_nm: float = 2.0,
) -> np.ndarray:
    points = np.asarray(
        [
            (
                spacing_nm * (x + 0.5 * (y % 2)),
                spacing_nm * math.sqrt(3.0) * y / 2.0,
            )
            for y in range(height)
            for x in range(width)
        ],
        dtype=np.float64,
    )
    angle_rad = math.radians(angle_deg)
    rotation = np.asarray(
        (
            (math.cos(angle_rad), -math.sin(angle_rad)),
            (math.sin(angle_rad), math.cos(angle_rad)),
        )
    )
    return points @ rotation.T + np.asarray(shift_xy_nm)


def _settings() -> MolecularM6OrientationAnalysisSettings:
    return MolecularM6OrientationAnalysisSettings(
        first_shell_r_min_nm=1.5,
        first_shell_r_max_nm=2.35,
        min_ordered_component_size=3,
        min_seed_size=6,
        min_domain_size=12,
        q_seed=0.65,
        q_grow=0.25,
        seed_angle_tolerance_deg=6.0,
        grow_angle_tolerance_deg=12.0,
        domain_merge_angle_tolerance_deg=6.0,
        footprint_support_radius_nm=1.2,
        gr_bin_width_nm=0.25,
        gr_max_nm=12.0,
        gr_min_expected_pair_exposure=0.1,
    )


def _frame(
    *,
    frame_id: str,
    physical_frame_id: str,
    condition: str,
    source_view: str,
    points: np.ndarray,
    point_ids: tuple[str, ...],
    origin: tuple[float, float] = (0.0, 0.0),
    reliable_fov: bool = True,
) -> M6HeadlessValidationFrame:
    return M6HeadlessValidationFrame(
        frame_id=frame_id,
        physical_frame_id=physical_frame_id,
        condition=condition,
        source_frame_index=0 if condition == "initial" else 1,
        source_view=source_view,
        points_xy_nm=tuple(tuple(float(value) for value in point) for point in points),
        point_ids=point_ids,
        window_size_nm=(28.0, 24.0),
        window_origin_nm=origin,
        valid_fov_reliable=reliable_fov,
        spatial_calibration_fingerprint="calibration-v1",
        registration_fingerprint=(
            "unregistered" if source_view == "raw" else "registration-v1"
        ),
    )


def _controlled_manifest() -> M6HeadlessValidationManifest:
    initial = _triangular_patch(0.0, (4.0, 4.0))
    readsorbed = _triangular_patch(18.0, (6.0, 3.0), width=7, height=7)
    initial_ids = tuple(f"initial-{index:03d}" for index in range(len(initial)))
    readsorbed_ids = tuple(
        f"readsorbed-{index:03d}" for index in range(len(readsorbed))
    )
    translation = np.asarray((3.0, 2.0))
    return M6HeadlessValidationManifest(
        manifest_version=1,
        manifest_id="controlled-two-condition-v1",
        algorithm_version=M6_ORIENTATION_ALGORITHM_VERSION,
        accepted_settings=_settings(),
        high_unassigned_fraction_warning_threshold=0.65,
        frames=(
            _frame(
                frame_id="initial-raw",
                physical_frame_id="initial-0",
                condition="initial",
                source_view="raw",
                points=initial,
                point_ids=initial_ids,
            ),
            _frame(
                frame_id="initial-aligned",
                physical_frame_id="initial-0",
                condition="initial",
                source_view="expanded_aligned",
                points=initial + translation,
                point_ids=initial_ids,
                origin=tuple(translation),
            ),
            _frame(
                frame_id="readsorbed-raw",
                physical_frame_id="readsorbed-1",
                condition="re_adsorbed",
                source_view="raw",
                points=readsorbed,
                point_ids=readsorbed_ids,
            ),
            _frame(
                frame_id="readsorbed-aligned",
                physical_frame_id="readsorbed-1",
                condition="re_adsorbed",
                source_view="expanded_aligned",
                points=readsorbed + translation,
                point_ids=readsorbed_ids,
                origin=tuple(translation),
            ),
        ),
    )


def _result_by_id(report, frame_id: str):
    return next(result for result in report.frame_results if result.frame.frame_id == frame_id)


def _assert_partition_sums(test_case: unittest.TestCase, summary) -> None:
    test_case.assertAlmostEqual(
        summary.full_domain_molecule_fraction
        + summary.small_island_molecule_fraction
        + summary.unassigned_molecule_fraction,
        1.0,
    )
    test_case.assertAlmostEqual(
        summary.full_domain_footprint_fraction
        + summary.small_island_footprint_fraction
        + summary.unassigned_supported_footprint_fraction
        + summary.unsupported_background_fraction,
        1.0,
    )


class M6HeadlessValidationTests(unittest.TestCase):
    def test_runs_complete_core_and_compares_conditions_without_fixed_conclusion(self) -> None:
        manifest = _controlled_manifest()

        report = run_m6_headless_validation(manifest)

        self.assertEqual(report.manifest_id, manifest.manifest_id)
        self.assertEqual(report.algorithm_version, M6_ORIENTATION_ALGORITHM_VERSION)
        self.assertEqual(report.accepted_settings, manifest.accepted_settings)
        self.assertEqual(len(report.frame_results), 4)
        self.assertEqual(
            tuple(summary.condition for summary in report.condition_orientation_summaries),
            ("initial", "re_adsorbed"),
        )
        for result in report.frame_results:
            self.assertEqual(result.status, "complete")
            self.assertIsNotNone(result.analysis)
            self.assertIsNotNone(result.pair_correlation)
            self.assertIsNotNone(result.summary)
            self.assertEqual(result.warnings, ())
            summary = result.summary
            assert summary is not None
            self.assertEqual(
                summary.original_observation_count,
                summary.valid_representative_count
                + summary.duplicate_excluded_count
                + summary.invalid_position_count,
            )
            _assert_partition_sums(self, summary)

        initial_raw = _result_by_id(report, "initial-raw").summary
        initial_aligned = _result_by_id(report, "initial-aligned").summary
        readsorbed_raw = _result_by_id(report, "readsorbed-raw").summary
        readsorbed_aligned = _result_by_id(report, "readsorbed-aligned").summary
        assert initial_raw is not None and initial_aligned is not None
        assert readsorbed_raw is not None and readsorbed_aligned is not None
        self.assertEqual(
            initial_raw.full_domain_orientations_deg,
            initial_aligned.full_domain_orientations_deg,
        )
        self.assertEqual(
            readsorbed_raw.full_domain_orientations_deg,
            readsorbed_aligned.full_domain_orientations_deg,
        )
        self.assertNotEqual(
            initial_raw.full_domain_orientations_deg,
            readsorbed_raw.full_domain_orientations_deg,
        )
        initial_result = _result_by_id(report, "initial-raw")
        readsorbed_result = _result_by_id(report, "readsorbed-raw")
        with self.assertRaisesRegex(ValueError, "Pair-correlation result"):
            replace(
                initial_result,
                pair_correlation=readsorbed_result.pair_correlation,
            )
        same_area_frame = replace(
            initial_result.frame,
            window_size_nm=(21.0, 32.0),
        )
        same_area_result = run_m6_headless_validation(
            replace(manifest, frames=(same_area_frame,))
        ).frame_results[0]
        with self.assertRaisesRegex(ValueError, "window context"):
            replace(
                initial_result,
                pair_correlation=same_area_result.pair_correlation,
            )
        single_point_frame = _frame(
            frame_id="single-point",
            physical_frame_id="single-point",
            condition="initial",
            source_view="raw",
            points=np.asarray(((4.0, 4.0),)),
            point_ids=("single-point",),
        )
        single_point_result = run_m6_headless_validation(
            replace(manifest, frames=(single_point_frame,))
        ).frame_results[0]
        single_point_other_shape = run_m6_headless_validation(
            replace(
                manifest,
                frames=(replace(single_point_frame, window_size_nm=(21.0, 32.0)),),
            )
        ).frame_results[0]
        with self.assertRaisesRegex(ValueError, "window context"):
            replace(
                single_point_result,
                pair_correlation=single_point_other_shape.pair_correlation,
            )
        alternate_gr_settings = replace(
            manifest.accepted_settings,
            gr_bin_width_nm=0.5,
        )
        alternate_gr_result = run_m6_headless_validation(
            replace(
                manifest,
                accepted_settings=alternate_gr_settings,
                frames=(initial_result.frame,),
            )
        ).frame_results[0]
        with self.assertRaisesRegex(ValueError, "accepted settings"):
            replace(
                initial_result,
                pair_correlation=alternate_gr_result.pair_correlation,
            )
        with self.assertRaisesRegex(ValueError, "Frame summary must be derived"):
            replace(
                initial_result,
                summary=replace(
                    initial_raw,
                    valid_fov_area_nm2=initial_raw.valid_fov_area_nm2 + 1.0,
                ),
            )
        with self.assertRaisesRegex(ValueError, "partition original observations"):
            replace(
                initial_raw,
                invalid_position_count=initial_raw.invalid_position_count + 1,
            )
        with self.assertRaisesRegex(ValueError, "one value per frame"):
            replace(report.condition_orientation_summaries[0], frame_ids=())
        with self.assertRaisesRegex(ValueError, "accepted_settings"):
            replace(
                report,
                accepted_settings=replace(
                    report.accepted_settings,
                    orientation_zero_tolerance=1e-6,
                ),
            )

    def test_manifest_roundtrip_preserves_settings_version_and_frames(self) -> None:
        manifest = _controlled_manifest()

        restored = M6HeadlessValidationManifest.from_dict(manifest.to_dict())

        self.assertEqual(restored, manifest)
        with self.assertRaisesRegex(ValueError, "algorithm_version"):
            replace(manifest, algorithm_version="unsupported-version")
        with self.assertRaisesRegex(ValueError, "frame_id"):
            replace(manifest, frames=(manifest.frames[0], manifest.frames[0]))

    def test_is_deterministic_and_invariant_to_observation_order(self) -> None:
        manifest = _controlled_manifest()
        baseline = run_m6_headless_validation(manifest)
        permutation = np.random.default_rng(71_200).permutation(
            len(manifest.frames[0].point_ids)
        )
        permuted_frames = []
        for frame in manifest.frames:
            if frame.physical_frame_id != "initial-0":
                permuted_frames.append(frame)
                continue
            points = np.asarray(frame.points_xy_nm)[permutation]
            permuted_frames.append(
                replace(
                    frame,
                    points_xy_nm=tuple(map(tuple, points)),
                    point_ids=tuple(frame.point_ids[index] for index in permutation),
                )
            )
        permuted = run_m6_headless_validation(
            replace(manifest, frames=tuple(permuted_frames))
        )
        repeated = run_m6_headless_validation(manifest)

        self.assertEqual(repeated.canonical_summary(), baseline.canonical_summary())
        self.assertEqual(permuted.canonical_summary(), baseline.canonical_summary())

    def test_reports_all_required_warning_classes(self) -> None:
        points = np.asarray(
            tuple((2.0 * x, 2.0 * y) for y in range(3) for x in range(3)),
            dtype=np.float64,
        )
        frame = M6HeadlessValidationFrame(
            frame_id="warning-frame",
            physical_frame_id="warning-frame",
            condition="control",
            source_frame_index=0,
            source_view="raw",
            points_xy_nm=tuple(map(tuple, points)),
            point_ids=tuple(f"square-{index}" for index in range(len(points))),
            window_size_nm=(8.0, 8.0),
            valid_fov_reliable=False,
            spatial_calibration_fingerprint="calibration-v1",
            registration_fingerprint="unregistered",
        )
        manifest = M6HeadlessValidationManifest(
            manifest_version=1,
            manifest_id="warnings-v1",
            algorithm_version=M6_ORIENTATION_ALGORITHM_VERSION,
            accepted_settings=_settings(),
            high_unassigned_fraction_warning_threshold=0.5,
            frames=(frame,),
        )

        result = run_m6_headless_validation(manifest).frame_results[0]

        self.assertEqual(
            {warning.code for warning in result.warnings},
            {
                "delaunay_degeneracy",
                "high_unassigned_fraction",
                "unreliable_valid_fov",
            },
        )

        random_points = np.random.default_rng(71_201).uniform(1.0, 7.0, size=(12, 2))
        fallback_frame = replace(
            frame,
            frame_id="fallback-frame",
            physical_frame_id="fallback-frame",
            points_xy_nm=tuple(map(tuple, random_points)),
            point_ids=tuple(f"fallback-{index}" for index in range(len(random_points))),
            valid_fov_reliable=True,
        )
        fallback_manifest = replace(manifest, frames=(fallback_frame,))
        with patch(
            "moltrack.analysis.first_shell_builder.Delaunay",
            side_effect=QhullError("forced fallback"),
        ):
            fallback_result = run_m6_headless_validation(
                fallback_manifest
            ).frame_results[0]

        self.assertEqual(fallback_result.status, "blocked_graph_fallback")
        self.assertIsNone(fallback_result.analysis)
        self.assertIsNone(fallback_result.summary)
        self.assertIn("graph_fallback", {item.code for item in fallback_result.warnings})
        with self.assertRaisesRegex(ValueError, "pair-correlation result"):
            replace(fallback_result, pair_correlation=None)
        with self.assertRaisesRegex(ValueError, "accepted_settings"):
            replace(
                fallback_result,
                accepted_settings=replace(
                    fallback_result.accepted_settings,
                    gr_bin_width_nm=0.5,
                ),
            )

    def test_reports_duplicate_and_invalid_observation_denominators(self) -> None:
        points = _triangular_patch(0.0, (4.0, 4.0), width=6, height=6)
        points_with_duplicate = tuple(map(tuple, points)) + (
            tuple(points[10]),
            tuple(points[10] + np.asarray((0.8, 0.6))),
        )
        point_ids = tuple(f"observed-{index:03d}" for index in range(len(points_with_duplicate)))
        frame = M6HeadlessValidationFrame(
            frame_id="rejections",
            physical_frame_id="rejections",
            condition="control",
            source_frame_index=0,
            source_view="raw",
            points_xy_nm=points_with_duplicate,
            point_ids=point_ids,
            window_size_nm=(28.0, 24.0),
            invalid_position_point_ids=(point_ids[-1],),
            valid_fov_reliable=True,
            spatial_calibration_fingerprint="calibration-v1",
            registration_fingerprint="unregistered",
        )
        manifest = M6HeadlessValidationManifest(
            manifest_version=1,
            manifest_id="rejections-v1",
            algorithm_version=M6_ORIENTATION_ALGORITHM_VERSION,
            accepted_settings=_settings(),
            high_unassigned_fraction_warning_threshold=1.0,
            frames=(frame,),
        )

        result = run_m6_headless_validation(manifest).frame_results[0]
        summary = result.summary
        assert summary is not None

        self.assertEqual(summary.original_observation_count, len(points_with_duplicate))
        self.assertEqual(summary.valid_representative_count, len(points))
        self.assertEqual(summary.duplicate_excluded_count, 1)
        self.assertEqual(summary.invalid_position_count, 1)
        self.assertAlmostEqual(
            summary.duplicate_excluded_fraction_of_original,
            1 / len(points_with_duplicate),
        )
        self.assertAlmostEqual(
            summary.invalid_position_fraction_of_original,
            1 / len(points_with_duplicate),
        )
        self.assertEqual(result.pair_correlation.point_count, len(points))

    def test_versioned_representative_fixture_runs_within_time_limit(self) -> None:
        manifest = load_m6_headless_validation_manifest(FIXTURE_PATH)

        started = time.perf_counter()
        report = run_m6_headless_validation(manifest)
        elapsed = time.perf_counter() - started

        self.assertLess(elapsed, 90.0)
        self.assertEqual(manifest.manifest_version, 1)
        self.assertEqual(manifest.algorithm_version, M6_ORIENTATION_ALGORITHM_VERSION)
        self.assertIsNotNone(manifest.provenance)
        self.assertEqual(
            M6HeadlessValidationManifest.from_dict(manifest.to_dict()),
            manifest,
        )
        self.assertEqual(
            {frame.source_view for frame in manifest.frames},
            {"raw", "expanded_aligned"},
        )
        self.assertEqual(
            {frame.condition for frame in manifest.frames},
            {"initial", "re_adsorbed"},
        )
        self.assertTrue(all(result.status == "complete" for result in report.frame_results))
        self.assertTrue(all(result.summary is not None for result in report.frame_results))
        self.assertTrue(
            all(len(result.frame.point_ids) >= 200 for result in report.frame_results)
        )
        self.assertEqual(
            {summary.condition for summary in report.condition_orientation_summaries},
            {"initial", "re_adsorbed"},
        )
        by_physical_frame = {}
        for result in report.frame_results:
            by_physical_frame.setdefault(result.frame.physical_frame_id, []).append(result)
        self.assertEqual({len(results) for results in by_physical_frame.values()}, {2})
        for results in by_physical_frame.values():
            summaries = [result.summary for result in results]
            assert summaries[0] is not None and summaries[1] is not None
            self.assertEqual(
                summaries[0].full_domain_orientations_deg,
                summaries[1].full_domain_orientations_deg,
            )


if __name__ == "__main__":
    unittest.main()
