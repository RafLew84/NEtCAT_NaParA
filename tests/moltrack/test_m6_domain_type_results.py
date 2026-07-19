from dataclasses import FrozenInstanceError, replace
import unittest

from moltrack.analysis import (
    M6DomainType,
    M6DomainTypeAssignment,
    M6DomainTypeClassificationResult,
    M6DomainTypeClassificationQcReport,
    M6DomainTypeClassificationSettings,
    M6DomainTypeObservation,
    MolecularFrameRange,
    MolecularFrameRangeAnalysisScope,
    MolecularM6OrientationAnalysisSettings,
)
from moltrack.analysis._m6_settings_fingerprint import m6_settings_fingerprint


def _m6_settings() -> MolecularM6OrientationAnalysisSettings:
    return MolecularM6OrientationAnalysisSettings()


def _observation(
    frame_index: int,
    ordered_component_id: int,
    *,
    qualification_status: str = "qualified",
    unclassified_reason: str | None = None,
) -> M6DomainTypeObservation:
    statistics_missing = unclassified_reason == "missing_bond_length_statistics"
    return M6DomainTypeObservation(
        range_name="condition",
        range_start_frame=0,
        range_end_frame=2,
        source_view="raw",
        m6_settings_fingerprint=m6_settings_fingerprint(_m6_settings()),
        m6_context_fingerprint="m6-context-v1",
        frame_index=frame_index,
        source_frame_index=frame_index + 10,
        ordered_component_id=ordered_component_id,
        m6_orientation_domain_id=ordered_component_id,
        component_type="full_domain",
        qualification_status=qualification_status,
        unclassified_reason=unclassified_reason,
        orientation_deg=5.0 + ordered_component_id,
        molecule_count=12,
        molecule_fraction_of_valid_representatives=0.5,
        footprint_area_nm2=20.0,
        footprint_fraction_of_valid_fov=0.2,
        molecular_mask_area_nm2=8.0,
        domain_mean_local_q6=0.8,
        domain_coherent_q6=0.7,
        centroid_x_nm=5.0,
        centroid_y_nm=6.0,
        min_x_nm=1.0,
        min_y_nm=2.0,
        max_x_nm=9.0,
        max_y_nm=10.0,
        internal_first_shell_bond_count=30,
        domain_median_bond_length_nm=None if statistics_missing else 2.0,
        domain_bond_length_mad_nm=None if statistics_missing else 0.1,
        domain_bond_length_iqr_nm=None if statistics_missing else 0.2,
        domain_bond_length_robust_cv=None if statistics_missing else 0.07413,
        insufficient_bonds_for_length_stats_qc=statistics_missing,
        bond_length_heterogeneity_qc=False,
        edge_truncated=False,
        footprint_disconnected_qc=False,
    )


def _scope() -> MolecularFrameRangeAnalysisScope:
    return MolecularFrameRangeAnalysisScope(
        analysis_mode="single_range",
        frame_count=3,
        source_view="raw",
        ranges=(MolecularFrameRange("condition", 0, 2),),
    )


def _domain_type(
    domain_type_id: int,
    observation_count: int,
) -> M6DomainType:
    return M6DomainType(
        domain_type_id=domain_type_id,
        prototype_orientation_deg=5.5,
        prototype_bond_length_nm=2.0,
        orientation_circular_spread_deg=0.5,
        bond_length_iqr_nm=0.2,
        observation_count=observation_count,
    )


def _qc_report(
    *,
    observation_count: int,
    classified_count: int,
    missing_count: int = 0,
    below_minimum_count: int = 0,
) -> M6DomainTypeClassificationQcReport:
    return M6DomainTypeClassificationQcReport(
        observation_count=observation_count,
        classified_observation_count=classified_count,
        unclassified_observation_count=observation_count - classified_count,
        unclassified_reason_counts=(
            ("small_ordered_island_excluded", 0),
            ("missing_bond_length_statistics", missing_count),
            ("bond_length_heterogeneity_qc", 0),
            ("below_minimum_observations_per_type", below_minimum_count),
        ),
    )


class M6DomainTypeResultModelsTests(unittest.TestCase):
    def test_result_is_a_complete_immutable_partition_of_observations(self) -> None:
        first = _observation(0, 0)
        second = _observation(1, 0)
        missing = _observation(
            2,
            0,
            qualification_status="unclassified",
            unclassified_reason="missing_bond_length_statistics",
        )
        domain_type = _domain_type(0, 2)
        assignments = (
            M6DomainTypeAssignment.classified(first.stable_key, domain_type_id=0),
            M6DomainTypeAssignment.classified(second.stable_key, domain_type_id=0),
            M6DomainTypeAssignment.unclassified(
                missing.stable_key,
                reason="missing_bond_length_statistics",
            ),
        )

        result = M6DomainTypeClassificationResult(
            analysis_scope=_scope(),
            classification_settings=M6DomainTypeClassificationSettings(
                minimum_observations_per_type=2
            ),
            m6_settings=_m6_settings(),
            m6_context_fingerprint="m6-context-v1",
            input_fingerprint="domain-type-input-v1",
            observations=(first, second, missing),
            domain_types=(domain_type,),
            assignments=assignments,
            qc_report=_qc_report(
                observation_count=3,
                classified_count=2,
                missing_count=1,
            ),
        )

        self.assertEqual(result.analysis_mode, "single_range")
        self.assertEqual(result.source_view, "raw")
        self.assertEqual(result.ranges, _scope().ranges)
        self.assertEqual(result.observations, (first, second, missing))
        self.assertEqual(result.assignments, assignments)
        self.assertEqual(result.domain_types[0].label, "A")
        self.assertFalse(hasattr(result, "tracks"))
        self.assertFalse(hasattr(result, "lifetimes"))
        with self.assertRaises(FrozenInstanceError):
            result.observation_count = 4

    def test_domain_type_labels_continue_deterministically_above_z(self) -> None:
        expected = {
            0: "A",
            25: "Z",
            26: "AA",
            27: "AB",
            51: "AZ",
            52: "BA",
            701: "ZZ",
            702: "AAA",
        }

        self.assertEqual(
            {type_id: _domain_type(type_id, 1).label for type_id in expected},
            expected,
        )

    def test_result_rejects_incomplete_duplicate_and_unknown_assignments(self) -> None:
        first = _observation(0, 0)
        second = _observation(1, 0)
        domain_type = _domain_type(0, 2)
        base = {
            "analysis_scope": _scope(),
            "classification_settings": M6DomainTypeClassificationSettings(
                minimum_observations_per_type=2
            ),
            "m6_settings": _m6_settings(),
            "m6_context_fingerprint": "m6-context-v1",
            "input_fingerprint": "domain-type-input-v1",
            "observations": (first, second),
            "domain_types": (domain_type,),
            "assignments": (
                M6DomainTypeAssignment.classified(first.stable_key, domain_type_id=0),
                M6DomainTypeAssignment.classified(second.stable_key, domain_type_id=0),
            ),
            "qc_report": _qc_report(observation_count=2, classified_count=2),
        }

        invalid_overrides = (
            {
                "observations": (first, first),
                "assignments": base["assignments"][:1],
                "qc_report": _qc_report(
                    observation_count=2,
                    classified_count=1,
                    below_minimum_count=1,
                ),
            },
            {"assignments": base["assignments"][:1]},
            {"assignments": (base["assignments"][0], base["assignments"][0])},
            {
                "assignments": (
                    M6DomainTypeAssignment.classified(
                        first.stable_key,
                        domain_type_id=99,
                    ),
                    base["assignments"][1],
                )
            },
            {"domain_types": (_domain_type(0, 1),)},
            {
                "qc_report": _qc_report(
                    observation_count=3,
                    classified_count=2,
                    below_minimum_count=1,
                )
            },
        )
        for overrides in invalid_overrides:
            with self.subTest(overrides=overrides):
                with self.assertRaises(ValueError):
                    M6DomainTypeClassificationResult(**{**base, **overrides})

    def test_result_rejects_scope_m6_context_and_unclassified_reason_mismatches(self) -> None:
        qualified = _observation(0, 0)
        missing = _observation(
            1,
            0,
            qualification_status="unclassified",
            unclassified_reason="missing_bond_length_statistics",
        )
        domain_type = _domain_type(0, 1)
        base = {
            "analysis_scope": _scope(),
            "classification_settings": M6DomainTypeClassificationSettings(
                minimum_observations_per_type=1
            ),
            "m6_settings": _m6_settings(),
            "m6_context_fingerprint": "m6-context-v1",
            "input_fingerprint": "domain-type-input-v1",
            "observations": (qualified, missing),
            "domain_types": (domain_type,),
            "assignments": (
                M6DomainTypeAssignment.classified(
                    qualified.stable_key,
                    domain_type_id=0,
                ),
                M6DomainTypeAssignment.unclassified(
                    missing.stable_key,
                    reason="missing_bond_length_statistics",
                ),
            ),
            "qc_report": _qc_report(
                observation_count=2,
                classified_count=1,
                missing_count=1,
            ),
        }

        mismatched_scope_observation = replace(qualified, source_view="expanded_aligned")
        mismatched_m6_observation = replace(
            qualified,
            m6_settings_fingerprint="other-m6-settings",
        )
        mismatched_m6_context_observation = replace(
            qualified,
            m6_context_fingerprint="other-m6-context",
        )
        wrong_reason_assignment = M6DomainTypeAssignment.unclassified(
            missing.stable_key,
            reason="below_minimum_observations_per_type",
        )
        invalid_overrides = (
            {
                "observations": (mismatched_scope_observation, missing),
                "assignments": (
                    M6DomainTypeAssignment.classified(
                        mismatched_scope_observation.stable_key,
                        domain_type_id=0,
                    ),
                    base["assignments"][1],
                ),
            },
            {
                "observations": (mismatched_m6_observation, missing),
                "assignments": (
                    M6DomainTypeAssignment.classified(
                        mismatched_m6_observation.stable_key,
                        domain_type_id=0,
                    ),
                    base["assignments"][1],
                ),
            },
            {
                "observations": (mismatched_m6_context_observation, missing),
                "assignments": (
                    M6DomainTypeAssignment.classified(
                        mismatched_m6_context_observation.stable_key,
                        domain_type_id=0,
                    ),
                    base["assignments"][1],
                ),
            },
            {"assignments": (base["assignments"][0], wrong_reason_assignment)},
        )
        for overrides in invalid_overrides:
            with self.subTest(overrides=overrides):
                with self.assertRaises(ValueError):
                    M6DomainTypeClassificationResult(**{**base, **overrides})


if __name__ == "__main__":
    unittest.main()
