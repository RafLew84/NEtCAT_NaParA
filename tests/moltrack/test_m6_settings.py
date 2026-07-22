import json
import unittest
from dataclasses import FrozenInstanceError

from moltrack.analysis import (
    MolecularM6OrientationAnalysisSettings,
    MolecularM6ViewSettings,
)


class MolecularM6OrientationAnalysisSettingsTests(unittest.TestCase):
    def test_defaults_are_public_and_immutable(self) -> None:
        settings = MolecularM6OrientationAnalysisSettings()

        self.assertTrue(settings.duplicate_detection_enabled)
        self.assertEqual(settings.duplicate_max_distance_nm, 0.5)
        self.assertEqual(settings.first_shell_r_min_nm, 1.0)
        self.assertEqual(settings.first_shell_r_max_nm, 2.6)
        self.assertEqual(settings.symmetry_m, 6)
        self.assertEqual(settings.bond_weighting, "uniform")
        self.assertEqual(settings.duplicate_policy, "best_quality_representative")
        self.assertEqual(settings.duplicate_chain_policy, "deterministic_complete_linkage")
        self.assertEqual(settings.geometry_collision_policy, "always_deduplicate_with_tolerance")
        self.assertEqual(settings.geometry_absolute_tolerance_nm, 1e-12)
        self.assertEqual(settings.geometry_relative_tolerance, 1e-10)
        self.assertEqual(settings.min_neighbors_for_local_order, 3)
        self.assertEqual(settings.min_neighbors_for_seed, 5)
        self.assertEqual(settings.min_ordered_component_size, 3)
        self.assertEqual(settings.min_seed_size, 5)
        self.assertEqual(settings.min_domain_size, 8)
        self.assertEqual(settings.domain_conflict_margin, 0.05)
        self.assertEqual(settings.domain_merge_angle_tolerance_deg, 8.0)
        self.assertEqual(settings.footprint_support_radius_nm, 1.3)
        self.assertEqual(settings.q_seed, 0.65)
        self.assertEqual(settings.q_grow, 0.25)
        self.assertEqual(settings.seed_angle_tolerance_deg, 8.0)
        self.assertEqual(settings.grow_angle_tolerance_deg, 12.0)
        self.assertEqual(settings.delaunay_degeneracy_policy, "exclude_ambiguous_edges")
        self.assertEqual(settings.gr_bin_width_nm, 0.1)
        self.assertEqual(settings.gr_max_nm, 10.0)
        self.assertEqual(settings.gr_min_expected_pair_exposure, 5.0)
        self.assertEqual(settings.gr_min_contributing_frames, 1)
        self.assertEqual(settings.gr_smoothing_method, "gaussian_bins")
        self.assertEqual(settings.gr_smoothing_width, 2.0)
        self.assertEqual(settings.gr_peak_prominence, 0.1)
        self.assertEqual(settings.min_bonds_for_domain_length_stats, 5)
        self.assertEqual(settings.domain_bond_length_robust_cv_qc_threshold, 0.2)
        self.assertEqual(settings.orientation_zero_tolerance, 1e-12)

        with self.assertRaises(FrozenInstanceError):
            settings.q_seed = 0.7

    def test_normalizes_supported_scalar_inputs(self) -> None:
        settings = MolecularM6OrientationAnalysisSettings(
            duplicate_detection_enabled=0,
            duplicate_max_distance_nm="0.4",
            first_shell_r_min_nm="1.1",
            first_shell_r_max_nm="2.8",
            symmetry_m="6",
            bond_weighting=" UNIFORM ",
            duplicate_policy=" BEST_QUALITY_REPRESENTATIVE ",
            duplicate_chain_policy=" DETERMINISTIC_COMPLETE_LINKAGE ",
            geometry_collision_policy=" ALWAYS_DEDUPLICATE_WITH_TOLERANCE ",
            min_neighbors_for_local_order="4",
            min_neighbors_for_seed="6",
            min_ordered_component_size="2",
            min_seed_size="4",
            min_domain_size="9",
            delaunay_degeneracy_policy=" EXCLUDE_AMBIGUOUS_EDGES ",
            gr_min_contributing_frames="2",
            gr_smoothing_method=" SAVITZKY_GOLAY ",
            min_bonds_for_domain_length_stats="7",
        )

        self.assertIs(settings.duplicate_detection_enabled, False)
        self.assertEqual(settings.duplicate_max_distance_nm, 0.4)
        self.assertIsInstance(settings.duplicate_max_distance_nm, float)
        self.assertEqual(settings.symmetry_m, 6)
        self.assertEqual(settings.bond_weighting, "uniform")
        self.assertEqual(settings.duplicate_policy, "best_quality_representative")
        self.assertEqual(settings.duplicate_chain_policy, "deterministic_complete_linkage")
        self.assertEqual(settings.geometry_collision_policy, "always_deduplicate_with_tolerance")
        self.assertEqual(settings.min_neighbors_for_local_order, 4)
        self.assertEqual(settings.min_neighbors_for_seed, 6)
        self.assertEqual(settings.min_ordered_component_size, 2)
        self.assertEqual(settings.min_seed_size, 4)
        self.assertEqual(settings.min_domain_size, 9)
        self.assertEqual(settings.delaunay_degeneracy_policy, "exclude_ambiguous_edges")
        self.assertEqual(settings.gr_min_contributing_frames, 2)
        self.assertEqual(settings.gr_smoothing_method, "savitzky_golay")
        self.assertEqual(settings.min_bonds_for_domain_length_stats, 7)

    def test_rejects_unsupported_algorithm_constants(self) -> None:
        invalid_values = (
            ("symmetry_m", 4),
            ("bond_weighting", "distance"),
            ("duplicate_policy", "first"),
            ("duplicate_chain_policy", "single_linkage"),
            ("geometry_collision_policy", "ignore"),
            ("delaunay_degeneracy_policy", "keep_ambiguous_edges"),
        )

        for field_name, value in invalid_values:
            with self.subTest(field_name=field_name):
                with self.assertRaisesRegex(ValueError, field_name):
                    MolecularM6OrientationAnalysisSettings(**{field_name: value})

    def test_rejects_non_finite_numeric_settings(self) -> None:
        float_fields = (
            "duplicate_max_distance_nm",
            "first_shell_r_min_nm",
            "first_shell_r_max_nm",
            "geometry_absolute_tolerance_nm",
            "geometry_relative_tolerance",
            "domain_conflict_margin",
            "domain_merge_angle_tolerance_deg",
            "footprint_support_radius_nm",
            "q_seed",
            "q_grow",
            "seed_angle_tolerance_deg",
            "grow_angle_tolerance_deg",
            "gr_bin_width_nm",
            "gr_max_nm",
            "gr_min_expected_pair_exposure",
            "gr_smoothing_width",
            "gr_peak_prominence",
            "domain_bond_length_robust_cv_qc_threshold",
            "orientation_zero_tolerance",
        )

        for field_name in float_fields:
            for value in (float("nan"), float("inf"), float("-inf")):
                with self.subTest(field_name=field_name, value=value):
                    with self.assertRaisesRegex(ValueError, field_name):
                        MolecularM6OrientationAnalysisSettings(**{field_name: value})

    def test_validates_distance_scales_and_optional_physical_duplicate_threshold(self) -> None:
        invalid_payloads = (
            {"geometry_absolute_tolerance_nm": 0.0},
            {"geometry_relative_tolerance": 0.0},
            {"duplicate_max_distance_nm": 0.0},
            {"first_shell_r_min_nm": 0.0},
            {"first_shell_r_max_nm": 0.0},
            {"footprint_support_radius_nm": 0.0},
            {"geometry_absolute_tolerance_nm": 0.5, "duplicate_max_distance_nm": 0.5},
            {"duplicate_max_distance_nm": 1.0, "first_shell_r_min_nm": 1.0},
            {"first_shell_r_min_nm": 2.6, "first_shell_r_max_nm": 2.6},
        )

        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    MolecularM6OrientationAnalysisSettings(**payload)

        settings = MolecularM6OrientationAnalysisSettings(
            duplicate_detection_enabled=False,
            duplicate_max_distance_nm=5.0,
            first_shell_r_min_nm=1.0,
            first_shell_r_max_nm=2.0,
        )
        self.assertFalse(settings.duplicate_detection_enabled)
        self.assertEqual(settings.duplicate_max_distance_nm, 5.0)

    def test_validates_quality_thresholds_and_m6_angle_tolerances(self) -> None:
        invalid_payloads = (
            {"q_grow": -0.01},
            {"q_seed": 1.01},
            {"q_grow": 0.7, "q_seed": 0.6},
            {"seed_angle_tolerance_deg": -0.01},
            {"grow_angle_tolerance_deg": 30.01},
            {"domain_merge_angle_tolerance_deg": -0.01},
            {"domain_merge_angle_tolerance_deg": 30.01},
            {"domain_conflict_margin": -0.01},
            {"orientation_zero_tolerance": -1e-12},
        )

        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    MolecularM6OrientationAnalysisSettings(**payload)

        settings = MolecularM6OrientationAnalysisSettings(
            q_grow=0.0,
            q_seed=1.0,
            seed_angle_tolerance_deg=20.0,
            grow_angle_tolerance_deg=10.0,
            domain_merge_angle_tolerance_deg=30.0,
            domain_conflict_margin=2.5,
            orientation_zero_tolerance=0.0,
        )
        self.assertEqual(settings.q_grow, 0.0)
        self.assertEqual(settings.seed_angle_tolerance_deg, 20.0)
        self.assertEqual(settings.grow_angle_tolerance_deg, 10.0)

    def test_validates_integer_counts_and_component_size_order(self) -> None:
        positive_integer_fields = (
            "min_neighbors_for_local_order",
            "min_neighbors_for_seed",
            "min_ordered_component_size",
            "min_seed_size",
            "min_domain_size",
            "gr_min_contributing_frames",
            "min_bonds_for_domain_length_stats",
        )
        for field_name in positive_integer_fields:
            with self.subTest(field_name=field_name, value=0):
                with self.assertRaisesRegex(ValueError, field_name):
                    MolecularM6OrientationAnalysisSettings(**{field_name: 0})
            with self.subTest(field_name=field_name, value=1.5):
                with self.assertRaisesRegex(ValueError, field_name):
                    MolecularM6OrientationAnalysisSettings(**{field_name: 1.5})

        invalid_orders = (
            {"min_ordered_component_size": 6, "min_seed_size": 5},
            {"min_seed_size": 9, "min_domain_size": 8},
        )
        for payload in invalid_orders:
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    MolecularM6OrientationAnalysisSettings(**payload)

        settings = MolecularM6OrientationAnalysisSettings(
            min_ordered_component_size=4,
            min_seed_size=4,
            min_domain_size=4,
        )
        self.assertEqual(settings.min_ordered_component_size, 4)
        self.assertEqual(settings.min_seed_size, 4)
        self.assertEqual(settings.min_domain_size, 4)

    def test_validates_pair_correlation_and_bond_length_settings(self) -> None:
        invalid_payloads = (
            {"gr_bin_width_nm": 0.0},
            {"gr_max_nm": 0.0},
            {"gr_min_expected_pair_exposure": 0.0},
            {"gr_smoothing_width": 0.0},
            {"gr_peak_prominence": -0.01},
            {"domain_bond_length_robust_cv_qc_threshold": -0.01},
        )

        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    MolecularM6OrientationAnalysisSettings(**payload)

        settings = MolecularM6OrientationAnalysisSettings(
            gr_bin_width_nm=2.0,
            gr_max_nm=1.0,
            gr_peak_prominence=0.0,
            domain_bond_length_robust_cv_qc_threshold=0.0,
        )
        self.assertEqual(settings.gr_bin_width_nm, 2.0)
        self.assertEqual(settings.gr_max_nm, 1.0)
        self.assertEqual(settings.gr_peak_prominence, 0.0)

        with self.assertRaisesRegex(ValueError, "bin count"):
            MolecularM6OrientationAnalysisSettings(
                gr_bin_width_nm=1e-6,
                gr_max_nm=100.0,
            )

    def test_round_trips_through_a_stable_json_compatible_dictionary(self) -> None:
        settings = MolecularM6OrientationAnalysisSettings(
            duplicate_detection_enabled=False,
            first_shell_r_min_nm=1.2,
            first_shell_r_max_nm=3.4,
            q_seed=0.8,
            q_grow=0.4,
            min_ordered_component_size=4,
            min_seed_size=6,
            min_domain_size=10,
        )

        payload = settings.to_dict()
        serialized = json.dumps(payload, sort_keys=False)
        restored = MolecularM6OrientationAnalysisSettings.from_dict(json.loads(serialized))

        self.assertEqual(restored, settings)
        self.assertEqual(restored.to_dict(), payload)
        self.assertEqual(
            tuple(payload),
            tuple(MolecularM6OrientationAnalysisSettings().to_dict()),
        )

        truncated = dict(payload)
        truncated.pop("q_seed")
        with self.assertRaisesRegex(ValueError, "q_seed"):
            MolecularM6OrientationAnalysisSettings.from_dict(truncated)

        with self.assertRaisesRegex(ValueError, "unknown_setting"):
            MolecularM6OrientationAnalysisSettings.from_dict({"unknown_setting": 1})


class MolecularM6ViewSettingsTests(unittest.TestCase):
    def test_overlay_mode_and_opacity_are_validated_and_immutable(self) -> None:
        settings = MolecularM6ViewSettings(
            overlay_mode="Orientation",
            overlay_opacity_percent=47,
        )

        self.assertEqual(settings.overlay_mode, "orientation")
        self.assertEqual(settings.overlay_opacity_percent, 47)
        with self.assertRaisesRegex(ValueError, "overlay_mode"):
            MolecularM6ViewSettings(overlay_mode="rows")
        with self.assertRaisesRegex(ValueError, "between 0 and 100"):
            MolecularM6ViewSettings(overlay_opacity_percent=101)

    def test_multisymmetry_overlay_modes_are_supported(self) -> None:
        for mode in ("q3", "m3_orientation", "symmetry_evidence"):
            with self.subTest(mode=mode):
                self.assertEqual(
                    MolecularM6ViewSettings(overlay_mode=mode).overlay_mode,
                    mode,
                )


if __name__ == "__main__":
    unittest.main()
