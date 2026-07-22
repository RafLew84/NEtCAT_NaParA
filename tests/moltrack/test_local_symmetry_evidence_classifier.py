import math
import unittest
from dataclasses import replace

from moltrack.analysis import (
    FirstShellGraph,
    LocalSymmetryEvidenceSettings,
    build_local_symmetry_confusion_report,
    classify_local_symmetry_evidence,
    compute_local_multisymmetry_bond_order,
)


def _star_graph(angles_deg: tuple[float, ...]) -> FirstShellGraph:
    angles_rad = tuple(math.radians(value) for value in angles_deg)
    point_count = len(angles_deg) + 1
    edges = tuple((0, index) for index in range(1, point_count))
    return FirstShellGraph(
        point_ids=tuple(f"point-{index}" for index in range(point_count)),
        point_count=point_count,
        edges_ij=edges,
        distances_nm=(1.5,) * len(edges),
        angles_rad=angles_rad,
        degree=(len(edges),) + (1,) * len(edges),
        geometry_collision_epsilon_nm=1e-12,
        duplicate_max_distance_nm=0.5,
        first_shell_r_min_nm=1.0,
        first_shell_r_max_nm=2.6,
        coordinate_frame="sample_nm",
        orientation_reference="+x_sample_axis",
        spatial_calibration_fingerprint="calibration-v1",
        registration_fingerprint="registration-v1",
        point_coordinate_fingerprint="coordinates-v1",
        construction_method="delaunay_first_shell",
        qc_status="valid",
    )


def _classification(
    angles_deg: tuple[float, ...],
    *,
    boundary_distance_nm: float = 10.0,
    bond_weights: tuple[float, ...] | None = None,
    angular_uncertainty_deg: tuple[float, ...] | None = None,
    settings: LocalSymmetryEvidenceSettings | None = None,
):
    graph = _star_graph(angles_deg)
    boundary_distances = (boundary_distance_nm,) + (10.0,) * len(angles_deg)
    local_order = compute_local_multisymmetry_bond_order(
        graph,
        distance_to_valid_fov_boundary_nm=boundary_distances,
    )
    result = classify_local_symmetry_evidence(
        graph,
        local_order,
        settings=settings,
        bond_weights=bond_weights,
        bond_angular_uncertainty_deg=angular_uncertainty_deg,
    )
    return local_order, result


class LocalSymmetryEvidenceClassifierTests(unittest.TestCase):
    def test_ideal_trifold_wins_despite_its_high_q6_harmonic(self) -> None:
        local_order, result = _classification((0.0, 120.0, 240.0))

        self.assertAlmostEqual(local_order.q3[0], 1.0)
        self.assertAlmostEqual(local_order.q6[0], 1.0)
        self.assertEqual(result.best_model[0], "trifold")
        self.assertGreater(result.trifold_model_score[0], result.sixfold_model_score[0])
        self.assertEqual(result.observed_direction_count[0], 3)
        self.assertAlmostEqual(result.expected_direction_coverage[0], 1.0)
        self.assertGreater(result.classification_confidence[0], 0.5)
        self.assertEqual(result.classification_reason[0], "classified_trifold")

    def test_ideal_sixfold_is_not_reduced_to_raw_q6(self) -> None:
        local_order, result = _classification(
            (15.0, 75.0, 135.0, 195.0, 255.0, 315.0)
        )

        self.assertAlmostEqual(local_order.q6[0], 1.0)
        self.assertEqual(result.best_model[0], "sixfold")
        self.assertGreater(result.sixfold_model_score[0], result.trifold_model_score[0])
        self.assertEqual(result.observed_direction_count[0], 6)
        self.assertAlmostEqual(result.expected_direction_coverage[0], 1.0)
        self.assertEqual(result.classification_reason[0], "classified_sixfold")

    def test_mixed_requires_a_significant_gain_over_both_single_models(self) -> None:
        directions = (
            0.0,
            120.0,
            240.0,
            30.0,
            90.0,
            150.0,
            210.0,
            270.0,
            330.0,
        )

        _local_order, result = _classification(directions)

        self.assertEqual(result.best_model[0], "mixed")
        self.assertGreater(result.mixed_model_score[0], result.trifold_model_score[0])
        self.assertGreater(result.mixed_model_score[0], result.sixfold_model_score[0])
        self.assertGreater(result.second_best_margin[0], 0.0)
        self.assertEqual(result.classification_reason[0], "classified_mixed")

    def test_disordered_model_wins_for_nonperiodic_directions(self) -> None:
        _local_order, result = _classification(
            (7.0, 43.0, 101.0, 167.0, 214.0, 278.0, 329.0)
        )

        self.assertEqual(result.best_model[0], "disordered")
        self.assertGreater(result.disordered_model_score[0], 0.0)
        self.assertEqual(result.classification_reason[0], "classified_disordered")

    def test_missing_direction_at_the_edge_reduces_coverage_but_keeps_sixfold(self) -> None:
        _local_order, result = _classification(
            (0.0, 60.0, 120.0, 180.0, 240.0),
            boundary_distance_nm=1.0,
        )

        self.assertTrue(result.edge_truncated_neighborhood[0])
        self.assertEqual(result.best_model[0], "sixfold")
        self.assertEqual(result.observed_direction_count[0], 5)
        self.assertAlmostEqual(result.expected_direction_coverage[0], 5.0 / 6.0)
        self.assertLess(result.classification_confidence[0], 1.0)

    def test_low_weight_extra_edge_and_position_uncertainty_do_not_flip_trifold(self) -> None:
        _local_order, result = _classification(
            (2.0, 118.0, 244.0, 53.0),
            bond_weights=(1.0, 1.0, 1.0, 0.02),
            angular_uncertainty_deg=(4.0, 4.0, 6.0, 2.0),
        )

        self.assertEqual(result.best_model[0], "trifold")
        self.assertEqual(result.observed_direction_count[0], 3)
        self.assertGreater(result.classification_confidence[0], 0.3)

    def test_angular_uncertainty_merges_indistinguishable_directions(self) -> None:
        _local_order, result = _classification(
            (0.0, 20.0, 120.0, 240.0),
            angular_uncertainty_deg=(10.0, 10.0, 0.0, 0.0),
        )

        self.assertEqual(result.observed_direction_count[0], 3)
        self.assertEqual(result.best_model[0], "trifold")

    def test_returns_controlled_ambiguous_and_unavailable_states(self) -> None:
        strict_settings = LocalSymmetryEvidenceSettings(
            minimum_second_best_margin=0.95,
        )
        _local_order, ambiguous = _classification(
            (0.0, 120.0, 240.0),
            settings=strict_settings,
        )
        _local_order, unavailable = _classification((0.0, 120.0))

        self.assertEqual(ambiguous.best_model[0], "ambiguous")
        self.assertEqual(ambiguous.classification_reason[0], "below_minimum_margin")
        self.assertEqual(ambiguous.classification_confidence[0], 0.0)
        self.assertEqual(unavailable.best_model[0], "unavailable")
        self.assertIsNone(unavailable.trifold_model_score[0])
        self.assertIsNone(unavailable.classification_confidence[0])

    def test_low_m3_and_m6_amplitudes_return_a_controlled_state(self) -> None:
        local_order, result = _classification((0.0, 90.0, 180.0, 270.0))

        self.assertEqual(local_order.m3_orientation_status[0], "undefined_low_amplitude")
        self.assertEqual(local_order.m6_orientation_status[0], "undefined_low_amplitude")
        self.assertEqual(result.best_model[0], "ambiguous")
        self.assertEqual(
            result.classification_reason[0],
            "order_amplitudes_below_threshold",
        )

    def test_large_uncertainty_does_not_create_periodic_evidence(self) -> None:
        directions = (7.0, 43.0, 101.0, 167.0, 214.0, 278.0, 329.0)
        _local_order, baseline = _classification(directions)
        _local_order, uncertain = _classification(
            directions,
            angular_uncertainty_deg=(30.0,) * len(directions),
        )

        self.assertNotIn(uncertain.best_model[0], {"trifold", "sixfold", "mixed"})
        if uncertain.classification_confidence[0] is not None:
            self.assertLessEqual(
                uncertain.classification_confidence[0],
                baseline.classification_confidence[0],
            )

    def test_ineligible_mixed_model_still_constrains_the_margin(self) -> None:
        strict_mixed_gate = LocalSymmetryEvidenceSettings(
            mixed_minimum_improvement=0.3,
        )
        _local_order, result = _classification(
            (
                0.0,
                120.0,
                240.0,
                30.0,
                90.0,
                150.0,
                210.0,
                270.0,
                330.0,
            ),
            settings=strict_mixed_gate,
        )

        self.assertEqual(result.best_model[0], "ambiguous")
        self.assertEqual(result.classification_reason[0], "below_minimum_margin")

    def test_synthetic_validation_matrix_reports_classification_errors(self) -> None:
        cases = (
            ("ideal-trifold", "trifold", (0.0, 120.0, 240.0)),
            ("ideal-sixfold", "sixfold", (0.0, 60.0, 120.0, 180.0, 240.0, 300.0)),
            (
                "mixed",
                "mixed",
                (0.0, 120.0, 240.0, 30.0, 90.0, 150.0, 210.0, 270.0, 330.0),
            ),
            ("disordered", "disordered", (7.0, 43.0, 101.0, 167.0, 214.0, 278.0, 329.0)),
        )
        predicted = tuple(_classification(angles)[1].best_model[0] for _, _, angles in cases)
        report = build_local_symmetry_confusion_report(
            case_ids=tuple(case_id for case_id, _, _ in cases),
            expected=tuple(expected for _, expected, _ in cases),
            predicted=predicted,
        )

        self.assertEqual(report.case_count, 4)
        self.assertEqual(report.correct_count, 4)
        self.assertEqual(report.errors, ())
        self.assertAlmostEqual(report.accuracy, 1.0)
        self.assertEqual(sum(sum(row) for row in report.confusion_matrix), 4)

    def test_rotation_preserves_class_and_rotates_periodic_orientation(self) -> None:
        _base_order, base = _classification((0.0, 120.0, 240.0))
        _rotated_order, rotated = _classification((27.0, 147.0, 267.0))

        self.assertEqual(base.best_model[0], rotated.best_model[0])
        self.assertAlmostEqual(base.trifold_model_score[0], rotated.trifold_model_score[0])
        self.assertAlmostEqual(rotated.winning_model_orientation_deg[0], 27.0)

    def test_settings_are_versionable_and_validate_thresholds(self) -> None:
        settings = LocalSymmetryEvidenceSettings(
            base_angular_tolerance_deg=6.0,
            mixed_complexity_penalty=0.2,
        )

        self.assertEqual(
            LocalSymmetryEvidenceSettings.from_dict(settings.to_dict()),
            settings,
        )
        with self.assertRaises(ValueError):
            LocalSymmetryEvidenceSettings(minimum_model_score=1.1)
        with self.assertRaises(ValueError):
            LocalSymmetryEvidenceSettings.from_dict(
                {**settings.to_dict(), "unknown": 1}
            )

    def test_settings_and_graph_context_are_fingerprinted(self) -> None:
        _local_order, baseline = _classification((0.0, 120.0, 240.0))
        _local_order, repeated = _classification((0.0, 120.0, 240.0))
        _local_order, changed = _classification(
            (0.0, 120.0, 240.0),
            settings=LocalSymmetryEvidenceSettings(
                base_angular_tolerance_deg=9.0,
            ),
        )

        self.assertEqual(baseline.settings_fingerprint, repeated.settings_fingerprint)
        self.assertNotEqual(baseline.settings_fingerprint, changed.settings_fingerprint)
        self.assertEqual(
            baseline.first_shell_graph_fingerprint,
            repeated.first_shell_graph_fingerprint,
        )

    def test_bond_evidence_is_part_of_result_provenance(self) -> None:
        _local_order, baseline = _classification((0.0, 120.0, 240.0))
        _local_order, weighted = _classification(
            (0.0, 120.0, 240.0),
            bond_weights=(1.0, 0.8, 1.0),
        )
        _local_order, uncertain = _classification(
            (0.0, 120.0, 240.0),
            angular_uncertainty_deg=(1.0, 0.0, 0.0),
        )

        self.assertNotEqual(
            baseline.bond_evidence_fingerprint,
            weighted.bond_evidence_fingerprint,
        )
        self.assertNotEqual(
            baseline.bond_evidence_fingerprint,
            uncertain.bond_evidence_fingerprint,
        )

    def test_rejects_invalid_per_edge_evidence(self) -> None:
        graph = _star_graph((0.0, 120.0, 240.0))
        local_order = compute_local_multisymmetry_bond_order(
            graph,
            distance_to_valid_fov_boundary_nm=(10.0,) * graph.point_count,
        )

        with self.assertRaisesRegex(ValueError, "one value per graph edge"):
            classify_local_symmetry_evidence(
                graph,
                local_order,
                bond_weights=(1.0,),
            )
        with self.assertRaisesRegex(ValueError, "at least one positive"):
            classify_local_symmetry_evidence(
                graph,
                local_order,
                bond_weights=(0.0, 0.0, 0.0),
            )
        with self.assertRaisesRegex(ValueError, "at most 60"):
            classify_local_symmetry_evidence(
                graph,
                local_order,
                bond_angular_uncertainty_deg=(0.0, 0.0, 61.0),
            )

    def test_extreme_finite_weights_are_normalized_before_fitting(self) -> None:
        _local_order, result = _classification(
            (0.0, 120.0, 240.0),
            bond_weights=(1e308, 1e308, 1e308),
        )

        self.assertEqual(result.best_model[0], "trifold")
        self.assertTrue(math.isfinite(result.trifold_model_score[0]))

    def test_rejects_local_order_from_another_graph(self) -> None:
        graph = _star_graph((0.0, 120.0, 240.0))
        local_order = compute_local_multisymmetry_bond_order(
            graph,
            distance_to_valid_fov_boundary_nm=(10.0,) * graph.point_count,
        )
        changed_graph = replace(graph, registration_fingerprint="registration-v2")

        with self.assertRaisesRegex(ValueError, "originate"):
            classify_local_symmetry_evidence(changed_graph, local_order)

    def test_confusion_report_preserves_auditable_errors(self) -> None:
        report = build_local_symmetry_confusion_report(
            case_ids=("case-a", "case-b"),
            expected=("trifold", "sixfold"),
            predicted=("trifold", "ambiguous"),
        )

        self.assertEqual(report.case_count, 2)
        self.assertEqual(report.correct_count, 1)
        self.assertEqual(report.errors[0].case_id, "case-b")
        self.assertEqual(report.errors[0].predicted, "ambiguous")


if __name__ == "__main__":
    unittest.main()
