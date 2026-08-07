import json
import math
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

import numpy as np

from moltrack.analysis import (
    LATTICE_DOMAIN_CALIBRATION_PARAMETER_SPECS,
    LATTICE_DOMAIN_CALIBRATION_PARAMETER_NAMES,
    LATTICE_DOMAIN_CALIBRATION_QUALITY_TAGS,
    LatticeDomainCalibrationCanceled,
    LatticeDomainCalibrationPrediction,
    LatticeDomainCalibrationReferenceDataset,
    LatticeDomainCalibrationReferenceFrame,
    LatticeDomainCalibrationSweepSettings,
    LatticeDomainPartitionLabels,
    MolecularFrameRange,
    MolecularM6OrientationAnalysisSettings,
    adapt_m6_domain_type_analysis_source,
    analyze_molecular_frame_range,
    analyze_molecular_m6_orientation,
    build_lattice_domain_calibration_initial_variants,
    lattice_domain_calibration_source_fingerprint,
    load_lattice_domain_calibration_reference,
    run_lattice_domain_calibration,
    run_lattice_domain_calibration_for_source,
    save_lattice_domain_calibration_reference,
    write_lattice_domain_calibration_report,
    lattice_domain_partition_labels_from_analysis,
)
from moltrack.core import (
    MolecularDetection,
    MolecularDetectionSet,
    MolTrackImageSeries,
)
from nanotrack.core import STMSequenceMetadata


def _triangular_patch(
    angle_deg: float,
    shift_xy_nm: tuple[float, float],
    *,
    width: int = 8,
    height: int = 8,
) -> np.ndarray:
    points = np.asarray([
        (2.0 * (column + 0.5 * (row % 2)), math.sqrt(3.0) * row)
        for row in range(height)
        for column in range(width)
    ])
    angle = math.radians(angle_deg)
    rotation = np.asarray(
        ((math.cos(angle), -math.sin(angle)), (math.sin(angle), math.cos(angle)))
    )
    return points @ rotation.T + np.asarray(shift_xy_nm)


def _m6_settings() -> MolecularM6OrientationAnalysisSettings:
    return MolecularM6OrientationAnalysisSettings(
        first_shell_r_min_nm=1.5,
        first_shell_r_max_nm=2.3,
        min_ordered_component_size=3,
        min_seed_size=8,
        min_domain_size=15,
        q_seed=0.65,
        q_grow=0.25,
        seed_angle_tolerance_deg=6.0,
        grow_angle_tolerance_deg=12.0,
        domain_merge_angle_tolerance_deg=6.0,
    )


def _build_series(frame_points: tuple[np.ndarray, ...]) -> MolTrackImageSeries:
    frame_size = 72
    detections = MolecularDetectionSet(frame_count=len(frame_points))
    for frame_index, points in enumerate(frame_points):
        detections.set_detections(
            frame_index,
            [MolecularDetection(
                frame_index=frame_index,
                bbox_xyxy=(x - 0.2, frame_size - y - 0.2, x + 0.2, frame_size - y + 0.2),
                confidence=0.9,
                detection_id=f"frame-{frame_index}-molecule-{point_index}",
            ) for point_index, (x, y) in enumerate(points)],
            source_view="raw",
            frame_shape=(frame_size, frame_size),
        )
    return MolTrackImageSeries(
        source_path="movie.mpp",
        raw_frames=np.zeros((len(frame_points), frame_size, frame_size), dtype=np.float32),
        metadata=STMSequenceMetadata(
            pixels_x=frame_size,
            pixels_y=frame_size,
            size_nm_x=float(frame_size),
            size_nm_y=float(frame_size),
        ),
        molecular_detections=detections,
    )


def _series():
    one_domain = _triangular_patch(0.0, (6.0, 6.0))
    one_domain_small = _triangular_patch(0.0, (6.0, 6.0), width=6, height=6)
    two_domains = np.vstack(
        (
            _triangular_patch(0.0, (6.0, 6.0)),
            _triangular_patch(22.0, (38.0, 6.0)),
        )
    )
    series = _build_series(
        (one_domain, one_domain_small, two_domains, two_domains.copy())
    )
    series.source_frame_indices = (10, 20, 30, 40)
    return series


def _labels(prefix: str = "manual") -> LatticeDomainPartitionLabels:
    return LatticeDomainPartitionLabels(
        source_ids=("a", "b", "c", "d"),
        domain_labels=(
            f"{prefix}-left",
            f"{prefix}-left",
            f"{prefix}-right",
            f"{prefix}-right",
        ),
        boundary=(False, False, False, True),
        confidence=(None, None, None, None),
    )


def _reference() -> LatticeDomainCalibrationReferenceDataset:
    return LatticeDomainCalibrationReferenceDataset(
        dataset_id="manual-ttmapp-v1",
        source_file_name="movie.mpp",
        source_frame_count=4,
        source_sample_fingerprint="0" * 64,
        source_view="raw",
        use_segmentation_centroids=True,
        reviewed=True,
        frames=(
            LatticeDomainCalibrationReferenceFrame(
                frame_index=0,
                split="calibration",
                symmetry_class="trifold",
                quality_tags=(
                    "incomplete_neighborhood",
                    "edge",
                    "jitter",
                    "missing_molecules",
                ),
                labels=_labels("frame-0"),
            ),
            LatticeDomainCalibrationReferenceFrame(
                frame_index=1,
                split="calibration",
                symmetry_class="sixfold",
                quality_tags=(),
                labels=_labels("frame-1"),
            ),
            LatticeDomainCalibrationReferenceFrame(
                frame_index=2,
                split="holdout",
                symmetry_class="trifold",
                quality_tags=(
                    "incomplete_neighborhood",
                    "edge",
                    "jitter",
                    "missing_molecules",
                ),
                labels=_labels("frame-2"),
            ),
            LatticeDomainCalibrationReferenceFrame(
                frame_index=3,
                split="holdout",
                symmetry_class="sixfold",
                quality_tags=(),
                labels=_labels("frame-3"),
            ),
        ),
    )


class LatticeDomainCalibrationTests(unittest.TestCase):
    def test_reference_json_round_trip_preserves_explicit_split_and_provenance(self) -> None:
        reference = _reference()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "reference.json"
            save_lattice_domain_calibration_reference(reference, path)
            payload = json.loads(path.read_text(encoding="utf-8"))
            restored = load_lattice_domain_calibration_reference(path)

        self.assertEqual(restored, reference)
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["uses_tracking"], False)
        self.assertEqual(
            [frame["split"] for frame in payload["frames"]],
            ["calibration", "calibration", "holdout", "holdout"],
        )
        self.assertEqual(len(reference.fingerprint), 64)

    def test_reference_rejects_unknown_quality_tag(self) -> None:
        with self.assertRaisesRegex(ValueError, "quality tag"):
            LatticeDomainCalibrationReferenceFrame(
                frame_index=0,
                split="calibration",
                symmetry_class="trifold",
                quality_tags=("egde",),
                labels=_labels(),
            )

    def test_reference_json_rejects_implicit_string_coercion(self) -> None:
        payload = _reference().to_dict()
        payload["source_file_name"] = 123
        with self.assertRaisesRegex(TypeError, "source_file_name"):
            LatticeDomainCalibrationReferenceDataset.from_dict(payload)

        payload = _reference().to_dict()
        payload["frames"][0]["labels"]["domain_labels"][0] = 123
        with self.assertRaisesRegex(TypeError, "domain label"):
            LatticeDomainCalibrationReferenceDataset.from_dict(payload)

    def test_run_requires_tagged_and_control_quality_examples_by_default(self) -> None:
        reference = _reference()
        reference = replace(
            reference,
            frames=tuple(
                replace(
                    frame,
                    quality_tags=tuple(
                        value
                        for value in frame.quality_tags
                        if value != "jitter"
                    ),
                )
                if frame.split == "calibration"
                else frame
                for frame in reference.frames
            ),
        )

        with self.assertRaisesRegex(ValueError, "calibration:jitter:tagged"):
            run_lattice_domain_calibration(
                reference,
                LatticeDomainCalibrationSweepSettings(
                    baseline_settings=MolecularM6OrientationAnalysisSettings(),
                    parameter_names=(),
                ),
                evaluator=lambda frame, _settings: frame.labels,
            )

    def test_initial_sweep_changes_one_parameter_and_locks_first_shell(self) -> None:
        baseline = MolecularM6OrientationAnalysisSettings()
        selected = (
            "local_symmetry_trifold_minimum_model_score",
            "seed_angle_tolerance_deg",
            "min_seed_size",
        )

        variants = build_lattice_domain_calibration_initial_variants(
            LatticeDomainCalibrationSweepSettings(
                baseline_settings=baseline,
                parameter_names=selected,
                max_multivariate_variants=0,
            )
        )

        self.assertEqual(variants[0].variant_id, "baseline")
        self.assertEqual(len(variants), 1 + 2 * len(selected))
        self.assertEqual(
            {variant.phase for variant in variants[1:]},
            {"one_at_a_time"},
        )
        for variant in variants:
            self.assertEqual(
                variant.settings.first_shell_r_min_nm,
                baseline.first_shell_r_min_nm,
            )
            self.assertEqual(
                variant.settings.first_shell_r_max_nm,
                baseline.first_shell_r_max_nm,
            )
            self.assertLessEqual(len(variant.changed_parameters), 1)
        self.assertNotIn(
            "first_shell_r_max_nm",
            LATTICE_DOMAIN_CALIBRATION_PARAMETER_NAMES,
        )
        self.assertIn("q_seed", LATTICE_DOMAIN_CALIBRATION_PARAMETER_NAMES)
        self.assertIn("q_grow", LATTICE_DOMAIN_CALIBRATION_PARAMETER_NAMES)
        self.assertTrue(
            {
                "lattice_edge_trifold_orientation_tolerance_deg",
                "lattice_edge_sixfold_orientation_tolerance_deg",
                "lattice_edge_mixed_model_profile_tolerance",
                "lattice_edge_conditional_channel_minimum_score",
                "lattice_edge_minimum_classification_confidence",
                "lattice_edge_minimum_orientation_confidence",
            }.issubset(LATTICE_DOMAIN_CALIBRATION_PARAMETER_NAMES)
        )
        self.assertEqual(
            len(LATTICE_DOMAIN_CALIBRATION_PARAMETER_NAMES),
            len(LATTICE_DOMAIN_CALIBRATION_PARAMETER_SPECS),
        )

    def test_initial_sweep_skips_size_perturbations_that_break_invariants(self) -> None:
        baseline = replace(
            MolecularM6OrientationAnalysisSettings(),
            min_ordered_component_size=5,
            min_seed_size=5,
            min_domain_size=5,
        )

        variants = build_lattice_domain_calibration_initial_variants(
            LatticeDomainCalibrationSweepSettings(
                baseline_settings=baseline,
                parameter_names=("min_seed_size", "min_domain_size"),
                max_multivariate_variants=0,
            )
        )

        self.assertEqual(
            tuple(value.variant_id for value in variants),
            ("baseline", "min_domain_size:high"),
        )

    def test_selects_on_calibration_only_then_evaluates_one_setting_on_holdout(self) -> None:
        reference = _reference()
        baseline = MolecularM6OrientationAnalysisSettings()
        calls: list[tuple[int, int]] = []

        def evaluator(frame, settings):
            calls.append((frame.frame_index, settings.min_seed_size))
            if settings.min_seed_size in {4, 5, 6}:
                return replace(
                    frame.labels,
                    domain_labels=("x", "x", "y", "y"),
                    confidence=(0.95, 0.95, 0.9, 0.9),
                )
            return replace(
                frame.labels,
                domain_labels=("merged", "merged", "merged", "merged"),
                confidence=(0.8, 0.8, 0.8, 0.8),
            )

        report = run_lattice_domain_calibration(
            reference,
            LatticeDomainCalibrationSweepSettings(
                baseline_settings=baseline,
                parameter_names=("min_seed_size",),
                max_multivariate_variants=0,
                minimum_stability_ari=0.5,
            ),
            evaluator=evaluator,
        )

        self.assertEqual(report.status, "stable_geometry_unverified")
        self.assertFalse(report.first_shell_validation_passed)
        self.assertEqual(report.selected_settings.min_seed_size, 5)
        self.assertEqual(report.best_variant_id, "baseline")
        self.assertAlmostEqual(report.holdout_metrics.mean_adjusted_rand_index, 1.0)
        holdout_calls = [
            setting_value for frame_index, setting_value in calls
            if frame_index in {2, 3}
        ]
        self.assertEqual(holdout_calls, [5, 5])
        self.assertEqual(
            {value.symmetry_class for value in report.first_shell_validation},
            {"trifold", "sixfold"},
        )
        self.assertTrue(
            {"edge", "jitter", "missing_molecules"}.issubset(
                {value.quality_tag for value in report.quality_impacts}
            )
        )
        self.assertFalse(report.preset_modified)
        self.assertFalse(report.uses_tracking)
        self.assertEqual(
            (
                report.stable_ranges[0].minimum_value,
                report.stable_ranges[0].maximum_value,
            ),
            (4, 6),
        )
        self.assertIsNotNone(
            next(
                value
                for value in report.variant_results
                if value.variant.phase == "stability"
                and value.variant.changed_parameters == ("min_seed_size",)
            ).metrics.mean_partition_stability_ari
        )

    def test_isolated_optimum_does_not_open_holdout(self) -> None:
        reference = _reference()
        holdout_calls = []
        progress = []

        def evaluator(frame, settings):
            if frame.split == "holdout":
                holdout_calls.append(frame.frame_index)
            labels = (
                ("x", "x", "y", "y")
                if settings.min_seed_size == 4
                else ("merged", "merged", "merged", "merged")
            )
            return replace(frame.labels, domain_labels=labels)

        report = run_lattice_domain_calibration(
            reference,
            LatticeDomainCalibrationSweepSettings(
                baseline_settings=MolecularM6OrientationAnalysisSettings(),
                parameter_names=("min_seed_size",),
                max_multivariate_variants=0,
                minimum_stability_ari=0.5,
            ),
            evaluator=evaluator,
            progress_callback=progress.append,
        )

        self.assertEqual(report.status, "no_stable_solution")
        self.assertEqual(report.stable_ranges, ())
        self.assertEqual(report.indeterminate_parameters, ("min_seed_size",))
        self.assertEqual(holdout_calls, [])
        self.assertEqual(progress[-1].phase, "stability")
        self.assertEqual(
            progress[-1].completed_evaluations,
            progress[-1].total_evaluations,
        )

    def test_holdout_failure_is_reported_without_reselecting_parameters(self) -> None:
        reference = _reference()

        def evaluator(frame, _settings):
            return replace(
                frame.labels,
                domain_labels=(
                    ("x", "x", "y", "y")
                    if frame.split == "calibration"
                    else ("merged", "merged", "merged", "merged")
                ),
            )

        report = run_lattice_domain_calibration(
            reference,
            LatticeDomainCalibrationSweepSettings(
                baseline_settings=MolecularM6OrientationAnalysisSettings(),
                parameter_names=(),
                max_multivariate_variants=0,
                minimum_stability_ari=0.5,
                minimum_holdout_ari=0.8,
            ),
            evaluator=evaluator,
        )

        self.assertEqual(report.status, "stable_geometry_unverified")
        self.assertEqual(report.selected_settings, report.baseline_settings)
        self.assertEqual(report.best_variant_id, "baseline")
        self.assertFalse(report.holdout_passed)
        self.assertLess(report.holdout_metrics.mean_adjusted_rand_index, 0.8)

    def test_no_stable_solution_is_a_visible_valid_result(self) -> None:
        reference = _reference()

        def evaluator(frame, _settings):
            return replace(
                frame.labels,
                domain_labels=("merged", "merged", "merged", "merged"),
                confidence=(0.99, 0.99, 0.99, 0.99),
            )

        report = run_lattice_domain_calibration(
            reference,
            LatticeDomainCalibrationSweepSettings(
                baseline_settings=MolecularM6OrientationAnalysisSettings(),
                parameter_names=("min_seed_size",),
                max_multivariate_variants=0,
                minimum_stability_ari=0.95,
            ),
            evaluator=evaluator,
        )

        self.assertEqual(report.status, "no_stable_solution")
        self.assertIsNone(report.selected_settings)
        self.assertIsNone(report.best_variant_id)
        self.assertIsNone(report.holdout_metrics)

    def test_limited_multivariate_sweep_and_cooperative_cancel(self) -> None:
        reference = _reference()

        def evaluator(frame, _settings):
            return replace(
                frame.labels,
                domain_labels=("x", "x", "y", "y"),
            )

        report = run_lattice_domain_calibration(
            reference,
            LatticeDomainCalibrationSweepSettings(
                baseline_settings=MolecularM6OrientationAnalysisSettings(),
                parameter_names=(
                    "local_symmetry_trifold_minimum_model_score",
                    "min_seed_size",
                ),
                max_multivariate_variants=1,
                minimum_stability_ari=0.5,
            ),
            evaluator=evaluator,
        )

        multivariate = tuple(
            value
            for value in report.variant_results
            if value.variant.phase == "multivariate"
        )
        self.assertEqual(len(multivariate), 1)
        self.assertEqual(len(multivariate[0].variant.changed_parameters), 2)

        progress = []
        with self.assertRaises(LatticeDomainCalibrationCanceled):
            run_lattice_domain_calibration(
                reference,
                LatticeDomainCalibrationSweepSettings(
                    baseline_settings=MolecularM6OrientationAnalysisSettings(),
                    parameter_names=("min_seed_size",),
                    max_multivariate_variants=0,
                ),
                evaluator=evaluator,
                progress_callback=progress.append,
                cancel_callback=lambda: bool(progress),
            )
        self.assertEqual(len(progress), 1)

    def test_multivariate_sweep_keeps_individually_worse_interactions(self) -> None:
        reference = _reference()
        baseline = MolecularM6OrientationAnalysisSettings()

        def evaluator(frame, settings):
            jointly_low = (
                settings.q_seed < baseline.q_seed
                and settings.q_grow < baseline.q_grow
            )
            return replace(
                frame.labels,
                domain_labels=(
                    ("x", "x", "y", "y")
                    if jointly_low
                    else ("merged", "merged", "merged", "merged")
                ),
            )

        report = run_lattice_domain_calibration(
            reference,
            LatticeDomainCalibrationSweepSettings(
                baseline_settings=baseline,
                parameter_names=(
                    "local_symmetry_trifold_minimum_model_score",
                    "lattice_edge_trifold_orientation_tolerance_deg",
                    "local_symmetry_sixfold_minimum_model_score",
                    "lattice_edge_sixfold_orientation_tolerance_deg",
                    "local_symmetry_mixed_minimum_model_score",
                    "lattice_edge_mixed_model_profile_tolerance",
                    "local_symmetry_minimum_second_best_margin",
                    "lattice_edge_minimum_classification_confidence",
                    "local_symmetry_minimum_expected_direction_coverage",
                    "lattice_edge_minimum_orientation_confidence",
                    "lattice_edge_conditional_channel_minimum_score",
                    "domain_conflict_margin",
                    "lattice_seed_min_model_score",
                    "lattice_halo_min_model_score",
                    "q_seed",
                    "q_grow",
                ),
                max_multivariate_variants=23,
                max_stability_candidates=1,
                minimum_stability_ari=0.5,
            ),
            evaluator=evaluator,
        )

        self.assertTrue(
            any(
                value.variant.phase == "multivariate"
                and value.variant.settings.q_seed < baseline.q_seed
                and value.variant.settings.q_grow < baseline.q_grow
                for value in report.variant_results
            )
        )

    def test_multivariate_refinement_is_centered_on_stable_candidate(self) -> None:
        reference = _reference()
        baseline = MolecularM6OrientationAnalysisSettings()

        def evaluator(frame, settings):
            if settings.q_seed >= baseline.q_seed + 0.05:
                labels = ("x", "x", "y", "y")
            elif settings.q_seed >= baseline.q_seed:
                labels = ("x", "x", "y", None)
            else:
                labels = ("merged", "merged", "merged", "merged")
            return replace(frame.labels, domain_labels=labels)

        report = run_lattice_domain_calibration(
            reference,
            LatticeDomainCalibrationSweepSettings(
                baseline_settings=baseline,
                parameter_names=("q_seed", "q_grow"),
                max_multivariate_variants=8,
                max_stability_candidates=4,
                minimum_stability_ari=0.5,
            ),
            evaluator=evaluator,
        )

        refinement = tuple(
            value
            for value in report.variant_results
            if value.variant.variant_id.startswith("refine:")
        )
        multivariate = tuple(
            value
            for value in report.variant_results
            if value.variant.phase == "multivariate"
        )
        self.assertTrue(refinement)
        self.assertLessEqual(len(multivariate), 8)
        self.assertEqual(
            len({value.variant.variant_id for value in multivariate}),
            len(multivariate),
        )
        self.assertTrue(
            any(
                value.variant.settings.q_seed
                >= baseline.q_seed + 0.10 - 1e-12
                for value in refinement
            )
        )

    def test_selects_weaker_stable_region_after_isolated_best_candidate(self) -> None:
        reference = _reference()
        baseline = MolecularM6OrientationAnalysisSettings()

        def evaluator(frame, settings):
            q_seed_state = round((settings.q_seed - baseline.q_seed) / 0.05)
            q_grow_state = round((settings.q_grow - baseline.q_grow) / 0.05)
            if q_seed_state == -1 and q_grow_state == -1:
                labels = ("x", "x", "y", "y")
            elif q_seed_state >= 0 and q_grow_state >= 0:
                labels = ("x", "x", "y", None)
            else:
                labels = ("merged", "merged", "merged", "merged")
            return replace(frame.labels, domain_labels=labels)

        report = run_lattice_domain_calibration(
            reference,
            LatticeDomainCalibrationSweepSettings(
                baseline_settings=baseline,
                parameter_names=("q_seed", "q_grow"),
                max_multivariate_variants=8,
                max_stability_candidates=8,
                minimum_stability_ari=0.5,
            ),
            evaluator=evaluator,
        )

        self.assertEqual(report.status, "stable_geometry_unverified")
        self.assertGreaterEqual(report.selected_settings.q_seed, baseline.q_seed)
        self.assertGreaterEqual(report.selected_settings.q_grow, baseline.q_grow)
        self.assertNotEqual(
            (report.selected_settings.q_seed, report.selected_settings.q_grow),
            (baseline.q_seed - 0.05, baseline.q_grow - 0.05),
        )

    def test_first_shell_validation_uses_manual_neighbor_edges(self) -> None:
        reference = _reference()
        reference = replace(
            reference,
            frames=tuple(
                replace(
                    frame,
                    first_shell_neighbor_pairs=(("a", "b"), ("b", "c")),
                )
                for frame in reference.frames
            ),
        )

        def evaluator(frame, _settings):
            return LatticeDomainCalibrationPrediction(
                labels=replace(
                    frame.labels,
                    domain_labels=("x", "x", "y", "y"),
                ),
                first_shell_neighbor_pairs=(("a", "b"), ("c", "d")),
            )

        report = run_lattice_domain_calibration(
            reference,
            LatticeDomainCalibrationSweepSettings(
                baseline_settings=MolecularM6OrientationAnalysisSettings(),
                parameter_names=(),
                max_multivariate_variants=0,
                minimum_stability_ari=0.5,
            ),
            evaluator=evaluator,
        )

        self.assertEqual(
            {value.status for value in report.first_shell_validation},
            {"available"},
        )
        for value in report.first_shell_validation:
            self.assertEqual(value.reference_edge_count, 4)
            self.assertEqual(value.predicted_edge_count, 4)
            self.assertAlmostEqual(value.precision, 0.5)
            self.assertAlmostEqual(value.recall, 0.5)

    def test_full_stable_status_requires_ttmapp_shell_range_and_manual_edges(self) -> None:
        reference = replace(
            _reference(),
            frames=tuple(
                replace(
                    frame,
                    first_shell_neighbor_pairs=(("a", "b"), ("b", "c")),
                )
                for frame in _reference().frames
            ),
        )
        baseline = replace(
            MolecularM6OrientationAnalysisSettings(),
            first_shell_r_min_nm=30.0,
            first_shell_r_max_nm=70.0,
        )

        def evaluator(frame, _settings):
            return LatticeDomainCalibrationPrediction(
                labels=replace(
                    frame.labels,
                    domain_labels=("x", "x", "y", "y"),
                ),
                first_shell_neighbor_pairs=frame.first_shell_neighbor_pairs,
            )

        report = run_lattice_domain_calibration(
            reference,
            LatticeDomainCalibrationSweepSettings(
                baseline_settings=baseline,
                parameter_names=(),
                max_multivariate_variants=0,
                minimum_stability_ari=0.5,
            ),
            evaluator=evaluator,
        )

        self.assertEqual(report.status, "stable")
        self.assertTrue(report.first_shell_validation_passed)

    def test_report_contains_metrics_settings_split_and_no_preset_side_effect(self) -> None:
        reference = _reference()

        def evaluator(frame, _settings):
            return replace(
                frame.labels,
                domain_labels=("x", "x", "y", "y"),
                confidence=(0.9, 0.9, 0.9, 0.9),
            )

        report = run_lattice_domain_calibration(
            reference,
            LatticeDomainCalibrationSweepSettings(
                baseline_settings=MolecularM6OrientationAnalysisSettings(),
                parameter_names=("min_seed_size",),
                max_multivariate_variants=0,
                minimum_stability_ari=0.5,
            ),
            evaluator=evaluator,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            paths = write_lattice_domain_calibration_report(report, tmpdir)
            second_paths = write_lattice_domain_calibration_report(report, tmpdir)
            payload = json.loads(paths["json"].read_text(encoding="utf-8"))
            markdown = paths["markdown"].read_text(encoding="utf-8")
            csv_text = paths["variants_csv"].read_text(encoding="utf-8")
            self.assertNotEqual(paths["json"].parent, second_paths["json"].parent)
            self.assertTrue(paths["json"].exists())
            self.assertTrue(second_paths["json"].exists())

        self.assertEqual(payload["reference_dataset_fingerprint"], reference.fingerprint)
        self.assertEqual(payload["calibration_frame_indices"], [0, 1])
        self.assertEqual(payload["holdout_frame_indices"], [2, 3])
        self.assertEqual(payload["source_frame_count"], 4)
        self.assertEqual(payload["source_sample_fingerprint"], "0" * 64)
        self.assertFalse(payload["preset_modified"])
        self.assertTrue(payload["holdout_passed"])
        self.assertFalse(payload["first_shell_validation_passed"])
        self.assertIn("mean_adjusted_rand_index", csv_text)
        self.assertIn("Holdout", markdown)
        self.assertIn("Preset modified: `false`", markdown)
        self.assertIn("Brier", markdown)
        self.assertIn("Boundary P/R", markdown)
        self.assertIn("over_segmentation_count", csv_text)
        self.assertEqual(len(payload["quality_impacts"]), 8)
        self.assertIn("algorithm_versions", payload)

    def test_completed_position_analysis_source_can_drive_real_calibration(self) -> None:
        series = _series()
        baseline = _m6_settings()
        analysis = analyze_molecular_frame_range(
            series,
            MolecularFrameRange("calibration", 0, 3),
            source_view="raw",
            m6_orientation_settings=baseline,
        )
        source = adapt_m6_domain_type_analysis_source(
            analysis,
            frame_count=series.frame_count,
        )
        reference_frames = []
        for frame_result, split, symmetry, quality_tags in zip(
            analysis.frame_results,
            ("calibration", "calibration", "holdout", "holdout"),
            ("trifold", "sixfold", "trifold", "sixfold"),
            (
                LATTICE_DOMAIN_CALIBRATION_QUALITY_TAGS,
                (),
                LATTICE_DOMAIN_CALIBRATION_QUALITY_TAGS,
                (),
            ),
        ):
            m6 = frame_result.m6_orientation_analysis
            assert m6 is not None and m6.lattice_domain_analysis is not None
            point_ids = m6.first_shell_graph.point_ids
            reference_frames.append(
                LatticeDomainCalibrationReferenceFrame(
                    frame_index=frame_result.frame_index,
                    split=split,
                    symmetry_class=symmetry,
                    quality_tags=quality_tags,
                    labels=lattice_domain_partition_labels_from_analysis(
                        m6.lattice_domain_analysis
                    ),
                    first_shell_neighbor_pairs=tuple(
                        tuple(sorted((point_ids[left], point_ids[right])))
                        for left, right in m6.first_shell_graph.edges_ij
                    ),
                )
            )
            repeated = analyze_molecular_m6_orientation(
                m6.sample_coordinates,
                settings=baseline,
            )
            assert repeated.lattice_domain_analysis is not None
            self.assertEqual(
                lattice_domain_partition_labels_from_analysis(
                    repeated.lattice_domain_analysis
                ),
                reference_frames[-1].labels,
            )
        reference = LatticeDomainCalibrationReferenceDataset(
            dataset_id="real-source-smoke",
            source_file_name="movie.mpp",
            source_frame_count=source.frame_count,
            source_sample_fingerprint=(
                lattice_domain_calibration_source_fingerprint(source)
            ),
            source_view="raw",
            use_segmentation_centroids=True,
            reviewed=True,
            frames=tuple(reference_frames),
        )

        report = run_lattice_domain_calibration_for_source(
            reference,
            LatticeDomainCalibrationSweepSettings(
                baseline_settings=baseline,
                parameter_names=(),
                max_multivariate_variants=0,
                minimum_stability_ari=0.9,
            ),
            source,
            source_file_name="movie.mpp",
        )

        self.assertEqual(
            report.status,
            "stable_geometry_unverified",
            (
                report.variant_results[0].metrics,
                report.holdout_metrics,
            ),
        )
        self.assertEqual(report.selected_settings, baseline)
        self.assertEqual(report.best_variant_id, "baseline")
        self.assertEqual(
            {value.status for value in report.first_shell_validation},
            {"available"},
        )

        mismatched_reference = replace(
            reference,
            source_sample_fingerprint="f" * 64,
        )
        with self.assertRaisesRegex(ValueError, "different analyzed samples"):
            run_lattice_domain_calibration_for_source(
                mismatched_reference,
                LatticeDomainCalibrationSweepSettings(
                    baseline_settings=baseline,
                    parameter_names=(),
                    max_multivariate_variants=0,
                ),
                source,
                source_file_name="movie.mpp",
            )


if __name__ == "__main__":
    unittest.main()
