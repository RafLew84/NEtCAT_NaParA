from dataclasses import replace
from itertools import combinations
import unittest

from moltrack.analysis import (
    M6DomainTypeClassificationSettings,
    M6DomainTypeObservation,
    MolecularFrameRange,
    MolecularFrameRangeAnalysisScope,
    MolecularM6OrientationAnalysisSettings,
    classify_m6_domain_types,
    compute_m6_domain_type_distance,
)
from moltrack.analysis._m6_settings_fingerprint import m6_settings_fingerprint


M6_CONTEXT = "m6-context-v1"


def _m6_settings() -> MolecularM6OrientationAnalysisSettings:
    return MolecularM6OrientationAnalysisSettings()


def _observation(
    frame_index: int,
    component_id: int,
    orientation_deg: float,
    bond_length_nm: float | None,
    *,
    range_name: str = "condition",
    range_bounds: tuple[int, int] = (0, 9),
    centroid_xy_nm: tuple[float, float] = (5.0, 6.0),
    qualification_status: str = "qualified",
    unclassified_reason: str | None = None,
) -> M6DomainTypeObservation:
    statistics_missing = bond_length_nm is None
    centroid_x, centroid_y = centroid_xy_nm
    return M6DomainTypeObservation(
        range_name=range_name,
        range_start_frame=range_bounds[0],
        range_end_frame=range_bounds[1],
        source_view="raw",
        m6_settings_fingerprint=m6_settings_fingerprint(_m6_settings()),
        m6_context_fingerprint=M6_CONTEXT,
        frame_index=frame_index,
        source_frame_index=frame_index + 100,
        ordered_component_id=component_id,
        m6_orientation_domain_id=component_id,
        component_type="full_domain",
        qualification_status=qualification_status,
        unclassified_reason=unclassified_reason,
        orientation_deg=orientation_deg,
        molecule_count=12,
        molecule_fraction_of_valid_representatives=0.5,
        footprint_area_nm2=20.0,
        footprint_fraction_of_valid_fov=0.2,
        molecular_mask_area_nm2=8.0,
        domain_mean_local_q6=0.8,
        domain_coherent_q6=0.7,
        centroid_x_nm=centroid_x,
        centroid_y_nm=centroid_y,
        min_x_nm=centroid_x - 1.0,
        min_y_nm=centroid_y - 1.0,
        max_x_nm=centroid_x + 1.0,
        max_y_nm=centroid_y + 1.0,
        internal_first_shell_bond_count=30,
        domain_median_bond_length_nm=bond_length_nm,
        domain_bond_length_mad_nm=None if statistics_missing else 0.1,
        domain_bond_length_iqr_nm=None if statistics_missing else 0.2,
        domain_bond_length_robust_cv=None if statistics_missing else 0.07413,
        insufficient_bonds_for_length_stats_qc=statistics_missing,
        bond_length_heterogeneity_qc=False,
        edge_truncated=False,
        footprint_disconnected_qc=False,
    )


def _single_scope() -> MolecularFrameRangeAnalysisScope:
    return MolecularFrameRangeAnalysisScope(
        analysis_mode="single_range",
        frame_count=10,
        source_view="raw",
        ranges=(MolecularFrameRange("condition", 0, 9),),
    )


def _compare_scope() -> MolecularFrameRangeAnalysisScope:
    return MolecularFrameRangeAnalysisScope(
        analysis_mode="compare_ranges",
        frame_count=4,
        source_view="raw",
        ranges=(
            MolecularFrameRange("before", 0, 1),
            MolecularFrameRange("after", 2, 3),
        ),
    )


def _classify(observations, *, scope=None, settings=None):
    return classify_m6_domain_types(
        observations,
        analysis_scope=_single_scope() if scope is None else scope,
        classification_settings=(
            M6DomainTypeClassificationSettings(
                orientation_tolerance_deg=5.0,
                bond_length_tolerance_mode="absolute_nm",
                bond_length_tolerance_value=0.2,
                minimum_observations_per_type=2,
            )
            if settings is None
            else settings
        ),
        m6_settings=_m6_settings(),
        m6_context_fingerprint=M6_CONTEXT,
    )


def _assignment_signature(result):
    return {
        assignment.observation_key: (
            assignment.status,
            assignment.domain_type_id,
            assignment.unclassified_reason,
        )
        for assignment in result.assignments
    }


class M6DomainTypeClassifierTests(unittest.TestCase):
    def test_complete_linkage_prevents_chain_and_is_permutation_invariant(self) -> None:
        observations = (
            _observation(0, 0, 0.0, 2.0),
            _observation(1, 0, 4.0, 2.0),
            _observation(2, 0, 8.0, 2.0),
        )

        forward = _classify(observations)
        reverse = _classify(tuple(reversed(observations)))

        self.assertEqual(forward.domain_types, reverse.domain_types)
        self.assertEqual(_assignment_signature(forward), _assignment_signature(reverse))
        self.assertEqual(forward.input_fingerprint, reverse.input_fingerprint)
        self.assertEqual(tuple(item.observation_count for item in forward.domain_types), (2,))
        self.assertEqual(forward.classified_observation_count, 2)
        self.assertEqual(forward.unclassified_observation_count, 1)

        assigned_keys = {
            assignment.observation_key
            for assignment in forward.assignments
            if assignment.status == "classified"
        }
        assigned = tuple(
            observation
            for observation in forward.observations
            if observation.stable_key in assigned_keys
        )
        for first, second in combinations(assigned, 2):
            distance = compute_m6_domain_type_distance(
                first.orientation_deg,
                first.domain_median_bond_length_nm,
                second.orientation_deg,
                second.domain_median_bond_length_nm,
                settings=forward.classification_settings,
            )
            self.assertTrue(distance.is_compatible)

    def test_clusters_can_be_separated_independently_by_angle_and_length(self) -> None:
        observations = (
            _observation(0, 0, 1.0, 2.00),
            _observation(1, 0, 2.0, 2.05),
            _observation(2, 0, 20.0, 2.00),
            _observation(3, 0, 21.0, 2.05),
            _observation(4, 0, 1.0, 4.00),
            _observation(5, 0, 2.0, 4.05),
        )

        result = _classify(observations)

        self.assertEqual(len(result.domain_types), 3)
        self.assertEqual(
            tuple(domain_type.observation_count for domain_type in result.domain_types),
            (2, 2, 2),
        )
        self.assertEqual(result.classified_observation_count, 6)
        self.assertEqual(result.unclassified_observation_count, 0)

    def test_compare_ranges_are_classified_jointly_with_shared_type_id(self) -> None:
        before = _observation(
            0,
            0,
            3.0,
            2.0,
            range_name="before",
            range_bounds=(0, 1),
        )
        after = _observation(
            2,
            0,
            4.0,
            2.05,
            range_name="after",
            range_bounds=(2, 3),
        )

        result = _classify((after, before), scope=_compare_scope())

        self.assertEqual(result.analysis_mode, "compare_ranges")
        self.assertEqual(len(result.domain_types), 1)
        self.assertEqual(result.domain_types[0].observation_count, 2)
        self.assertEqual(
            {assignment.domain_type_id for assignment in result.assignments},
            {0},
        )

    def test_pre_unclassified_reasons_and_small_cluster_reason_are_preserved(self) -> None:
        qualified_pair = (
            _observation(0, 0, 2.0, 2.0),
            _observation(1, 0, 3.0, 2.05),
        )
        singleton = _observation(2, 0, 25.0, 4.0)
        missing = _observation(
            3,
            0,
            5.0,
            None,
            qualification_status="unclassified",
            unclassified_reason="missing_bond_length_statistics",
        )

        result = _classify((*qualified_pair, singleton, missing))
        assignments = _assignment_signature(result)

        self.assertEqual(
            assignments[singleton.stable_key],
            ("unclassified", None, "below_minimum_observations_per_type"),
        )
        self.assertEqual(
            assignments[missing.stable_key],
            ("unclassified", None, "missing_bond_length_statistics"),
        )
        self.assertEqual(result.classified_observation_count, 2)
        self.assertEqual(result.unclassified_observation_count, 2)

    def test_clustering_uses_structure_not_frame_adjacency_or_centroid_overlap(self) -> None:
        observations = (
            _observation(0, 0, 1.0, 2.0, centroid_xy_nm=(5.0, 5.0)),
            _observation(1, 0, 21.0, 4.0, centroid_xy_nm=(5.0, 5.0)),
            _observation(7, 0, 2.0, 2.05, centroid_xy_nm=(500.0, 500.0)),
            _observation(9, 0, 22.0, 4.05, centroid_xy_nm=(-500.0, -500.0)),
        )

        result = _classify(observations)
        assignments = _assignment_signature(result)

        self.assertEqual(len(result.domain_types), 2)
        self.assertEqual(
            assignments[observations[0].stable_key][1],
            assignments[observations[2].stable_key][1],
        )
        self.assertEqual(
            assignments[observations[1].stable_key][1],
            assignments[observations[3].stable_key][1],
        )
        self.assertNotEqual(
            assignments[observations[0].stable_key][1],
            assignments[observations[1].stable_key][1],
        )

    def test_rejects_observation_context_that_does_not_match_scope(self) -> None:
        observation = _observation(0, 0, 1.0, 2.0)
        mismatched = replace(
            observation,
            frame_index=1,
            source_frame_index=101,
            ordered_component_id=1,
            m6_orientation_domain_id=1,
            m6_context_fingerprint="other-context",
        )

        with self.assertRaisesRegex(ValueError, "context"):
            _classify((observation, mismatched))


if __name__ == "__main__":
    unittest.main()
