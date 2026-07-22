import unittest
from dataclasses import replace
from math import cos, radians, sin

from moltrack.analysis import (
    LATTICE_DOMAIN_EDGE_COMPATIBILITY_SCHEMA_VERSION,
    LatticeDomainEdgeCompatibilitySettings,
    LocalMultiSymmetryBondOrderField,
    LocalMultiSymmetryBondOrderProvenance,
    LocalSymmetryEvidenceField,
    build_first_shell_graph,
    build_lattice_domain_edge_compatibility,
    lattice_domain_edge_settings_fingerprint,
)
from moltrack.analysis._first_shell_graph_fingerprint import (
    first_shell_graph_fingerprint,
)


_PROFILE_BY_MODEL = {
    "trifold": (0.90, 0.25, 0.35, 0.10),
    "sixfold": (0.25, 0.90, 0.35, 0.10),
    "mixed": (0.72, 0.74, 0.90, 0.10),
    "disordered": (0.10, 0.10, 0.10, 0.90),
    "ambiguous": (0.61, 0.59, 0.58, 0.20),
}


def _harmonic(order: int, angle_deg: float, amplitude: float = 0.8) -> complex:
    phase = radians(order * angle_deg)
    return amplitude * complex(cos(phase), sin(phase))


def _pair_inputs(
    models: tuple[str, str],
    *,
    theta3: tuple[float, float] = (10.0, 12.0),
    theta6: tuple[float, float] = (10.0, 12.0),
    profiles: tuple[tuple[float, float, float, float], ...] | None = None,
    classification_confidence: tuple[float, float] = (0.8, 0.8),
    m3_orientation_confidence: tuple[float, float] = (0.8, 0.8),
    m6_orientation_confidence: tuple[float, float] = (0.8, 0.8),
):
    graph = build_first_shell_graph(
        ((0.0, 0.0), (1.5, 0.0)),
        point_ids=("molecule-a", "molecule-b"),
    )
    graph_fingerprint = first_shell_graph_fingerprint(graph)
    available = tuple(model != "unavailable" for model in models)
    qualified = tuple(model == "trifold" for model in models)
    local_order = LocalMultiSymmetryBondOrderField(
        source_ids=graph.point_ids,
        point_count=2,
        psi3=tuple(
            _harmonic(3, angle) if is_available else None
            for angle, is_available in zip(theta3, available)
        ),
        q3=tuple(0.8 if is_available else None for is_available in available),
        theta3_polar_deg=tuple(
            angle % 120.0 if is_available else None
            for angle, is_available in zip(theta3, available)
        ),
        theta3_lattice_deg=tuple(
            angle % 60.0 if is_available else None
            for angle, is_available in zip(theta3, available)
        ),
        m3_orientation_status=tuple(
            "defined" if is_available else "insufficient_neighbors"
            for is_available in available
        ),
        m3_orientation_confidence=tuple(
            confidence if is_available else None
            for confidence, is_available in zip(m3_orientation_confidence, available)
        ),
        psi6=tuple(
            _harmonic(6, angle) if is_available else None
            for angle, is_available in zip(theta6, available)
        ),
        q6=tuple(0.8 if is_available else None for is_available in available),
        theta6_deg=tuple(
            angle % 60.0 if is_available else None
            for angle, is_available in zip(theta6, available)
        ),
        m6_orientation_status=tuple(
            "defined" if is_available else "insufficient_neighbors"
            for is_available in available
        ),
        m6_orientation_confidence=tuple(
            confidence if is_available else None
            for confidence, is_available in zip(m6_orientation_confidence, available)
        ),
        neighbor_count=tuple(3 if is_available else 0 for is_available in available),
        computation_status=tuple(
            "valid_order" if is_available else "insufficient_neighbors"
            for is_available in available
        ),
        m3_sublattice_phase=tuple(0 if is_qualified else None for is_qualified in qualified),
        m3_sublattice_phase_status=tuple(
            "defined"
            if is_qualified
            else ("not_applicable" if is_available else "unavailable")
            for is_qualified, is_available in zip(qualified, available)
        ),
        m3_phase_gauge_anchor=tuple(
            source_id if is_qualified else None
            for source_id, is_qualified in zip(graph.point_ids, qualified)
        ),
        m3_qualified_trifold=qualified,
        m3_sublattice_assignment_ambiguous=(False, False),
        m3_gauge_inconsistent_cycle=(False, False),
        m3_gauge_frustration_qc=(False, False),
        symmetry_resolvability_status=tuple(
            "resolvable" if is_available else "unavailable"
            for is_available in available
        ),
        physical_duplicate_qc=(False, False),
        geometry_duplicate_qc=(False, False),
        edge_truncated_neighborhood=(False, False),
        distance_to_valid_fov_boundary_nm=(100.0, 100.0),
        first_shell_r_max_nm=graph.first_shell_r_max_nm,
        provenance=LocalMultiSymmetryBondOrderProvenance(
            coordinate_frame="sample_nm",
            orientation_reference=graph.orientation_reference,
            spatial_calibration_fingerprint=graph.spatial_calibration_fingerprint,
            registration_fingerprint=graph.registration_fingerprint,
            point_coordinate_fingerprint=graph.point_coordinate_fingerprint,
            first_shell_graph_fingerprint=graph_fingerprint,
            qualified_trifold_subgraph_fingerprint="qualified-trifold-v1",
            m3_phase_assignment_fingerprint="m3-phase-v1",
            analysis_settings_fingerprint="local-order-v1",
        ),
    )

    active_profiles = profiles or tuple(
        _PROFILE_BY_MODEL[model] if model != "unavailable" else (0.0, 0.0, 0.0, 0.0)
        for model in models
    )
    evidence = LocalSymmetryEvidenceField(
        source_ids=graph.point_ids,
        point_count=2,
        trifold_model_score=tuple(
            profile[0] if is_available else None
            for profile, is_available in zip(active_profiles, available)
        ),
        sixfold_model_score=tuple(
            profile[1] if is_available else None
            for profile, is_available in zip(active_profiles, available)
        ),
        mixed_model_score=tuple(
            profile[2] if is_available else None
            for profile, is_available in zip(active_profiles, available)
        ),
        disordered_model_score=tuple(
            profile[3] if is_available else None
            for profile, is_available in zip(active_profiles, available)
        ),
        best_model=models,
        second_best_margin=tuple(
            (0.01 if model == "ambiguous" else 0.30) if is_available else None
            for model, is_available in zip(models, available)
        ),
        observed_direction_count=tuple(3 if is_available else 0 for is_available in available),
        expected_direction_coverage=tuple(
            0.8 if is_available else None for is_available in available
        ),
        classification_confidence=tuple(
            (0.0 if model == "ambiguous" else confidence)
            if is_available
            else None
            for model, confidence, is_available in zip(
                models,
                classification_confidence,
                available,
            )
        ),
        classification_reason=tuple(
            {
                "trifold": "classified_trifold",
                "sixfold": "classified_sixfold",
                "mixed": "classified_mixed",
                "disordered": "classified_disordered",
                "ambiguous": "below_minimum_margin",
                "unavailable": "local_order_unavailable",
            }[model]
            for model in models
        ),
        winning_model_orientation_deg=tuple(
            theta3[index]
            if model == "trifold"
            else theta6[index]
            if model == "sixfold"
            else None
            for index, model in enumerate(models)
        ),
        edge_truncated_neighborhood=(False, False),
        first_shell_graph_fingerprint=graph_fingerprint,
        local_order_analysis_fingerprint="local-order-v1",
        settings_fingerprint="local-evidence-settings-v1",
        bond_evidence_fingerprint="bond-evidence-v1",
    )
    return graph, local_order, evidence


class LatticeDomainEdgeCompatibilityTests(unittest.TestCase):
    def test_accepts_trifold_orientation_modulo_sixty_and_rejects_above_tolerance(self) -> None:
        graph, local_order, evidence = _pair_inputs(
            ("trifold", "trifold"),
            theta3=(59.0, 1.0),
        )

        accepted = build_lattice_domain_edge_compatibility(
            graph,
            local_order,
            evidence,
            settings=LatticeDomainEdgeCompatibilitySettings(
                trifold_orientation_tolerance_deg=2.0,
            ),
        )
        rejected = build_lattice_domain_edge_compatibility(
            graph,
            local_order,
            evidence,
            settings=LatticeDomainEdgeCompatibilitySettings(
                trifold_orientation_tolerance_deg=1.99,
            ),
        )

        self.assertEqual(accepted.decision, ("compatible_trifold",))
        self.assertEqual(accepted.compatible_channels, (("m3",),))
        self.assertEqual(accepted.theta3_delta_deg, (2.0,))
        self.assertEqual(accepted.retained_edges_ij, ((0, 1),))
        self.assertEqual(accepted.rejection_reason, (None,))
        self.assertEqual(
            accepted.minimum_endpoint_classification_confidence,
            (0.8,),
        )
        self.assertEqual(accepted.minimum_endpoint_m3_orientation_confidence, (0.8,))
        self.assertEqual(accepted.minimum_endpoint_m6_orientation_confidence, (0.8,))
        self.assertEqual(rejected.decision, ("conflict_boundary",))
        self.assertEqual(rejected.compatible_channels, ((),))
        self.assertEqual(
            rejected.rejection_reason,
            ("trifold_orientation_mismatch",),
        )
        self.assertEqual(rejected.boundary_edges_ij, ((0, 1),))

    def test_accepts_sixfold_orientation_with_its_configured_tolerance(self) -> None:
        graph, local_order, evidence = _pair_inputs(
            ("sixfold", "sixfold"),
            theta6=(4.0, 10.0),
        )
        result = build_lattice_domain_edge_compatibility(
            graph,
            local_order,
            evidence,
            settings=LatticeDomainEdgeCompatibilitySettings(
                sixfold_orientation_tolerance_deg=6.0,
            ),
        )

        self.assertEqual(result.decision, ("compatible_sixfold",))
        self.assertEqual(result.theta6_delta_deg, (6.0,))

    def test_mixed_pair_requires_both_orientations_and_compatible_model_profiles(self) -> None:
        graph, local_order, evidence = _pair_inputs(
            ("mixed", "mixed"),
            theta3=(10.0, 13.0),
            theta6=(20.0, 24.0),
        )
        compatible = build_lattice_domain_edge_compatibility(
            graph,
            local_order,
            evidence,
        )
        _, profile_order, profile_evidence = _pair_inputs(
            ("mixed", "mixed"),
            theta3=(10.0, 13.0),
            theta6=(20.0, 24.0),
            profiles=((0.90, 0.20, 0.88, 0.10), (0.20, 0.90, 0.88, 0.10)),
        )
        incompatible_profile = build_lattice_domain_edge_compatibility(
            graph,
            profile_order,
            profile_evidence,
            settings=LatticeDomainEdgeCompatibilitySettings(
                mixed_model_profile_tolerance=0.25,
            ),
        )

        self.assertEqual(compatible.decision, ("compatible_mixed",))
        self.assertEqual(incompatible_profile.decision, ("conflict_boundary",))
        self.assertEqual(
            incompatible_profile.rejection_reason,
            ("mixed_model_profile_mismatch",),
        )

    def test_asymmetric_matrix_rows_are_invariant_to_endpoint_order(self) -> None:
        cases = (
            (("trifold", "sixfold"), "conflict_boundary", "incompatible_symmetry_models"),
            (("trifold", "mixed"), "conditional_halo_edge", None),
            (("sixfold", "mixed"), "conditional_halo_edge", None),
            (("trifold", "ambiguous"), "conditional_halo_edge", None),
            (("sixfold", "ambiguous"), "conditional_halo_edge", None),
            (("mixed", "ambiguous"), "conditional_halo_edge", None),
            (("trifold", "unavailable"), "no_domain_edge", "endpoint_unavailable"),
        )
        for models, expected_decision, expected_reason in cases:
            outcomes = []
            for ordered_models in (models, tuple(reversed(models))):
                graph, local_order, evidence = _pair_inputs(ordered_models)
                result = build_lattice_domain_edge_compatibility(
                    graph,
                    local_order,
                    evidence,
                )
                outcomes.append((result.decision[0], result.rejection_reason[0]))
            with self.subTest(models=models):
                self.assertEqual(
                    outcomes,
                    [(expected_decision, expected_reason)] * 2,
                )

    def test_mixed_endpoint_is_a_conditional_halo_edge_for_a_strong_matching_channel(self) -> None:
        decisions = []
        for models, theta3 in (
            (("trifold", "mixed"), (10.0, 12.0)),
            (("mixed", "trifold"), (12.0, 10.0)),
        ):
            graph, local_order, evidence = _pair_inputs(models, theta3=theta3)
            result = build_lattice_domain_edge_compatibility(
                graph,
                local_order,
                evidence,
            )
            decisions.append(result.decision)
            self.assertEqual(result.compatible_channels, (("m3",),))
            self.assertFalse(result.core_connectivity_eligible[0])

        self.assertEqual(decisions, [("conditional_halo_edge",)] * 2)

    def test_mixed_endpoint_rejects_a_weak_relevant_channel(self) -> None:
        graph, local_order, evidence = _pair_inputs(
            ("trifold", "mixed"),
            profiles=((0.90, 0.20, 0.30, 0.10), (0.30, 0.80, 0.90, 0.10)),
        )
        result = build_lattice_domain_edge_compatibility(
            graph,
            local_order,
            evidence,
            settings=LatticeDomainEdgeCompatibilitySettings(
                conditional_channel_minimum_score=0.5,
            ),
        )

        self.assertEqual(result.decision, ("conflict_boundary",))
        self.assertEqual(
            result.rejection_reason,
            ("conditional_channel_too_weak",),
        )

    def test_ambiguous_endpoint_can_only_form_a_conditional_compatible_edge(self) -> None:
        graph, local_order, evidence = _pair_inputs(
            ("sixfold", "ambiguous"),
            theta6=(58.0, 2.0),
            profiles=((0.20, 0.90, 0.30, 0.10), (0.20, 0.30, 0.25, 0.20)),
        )
        result = build_lattice_domain_edge_compatibility(
            graph,
            local_order,
            evidence,
            settings=LatticeDomainEdgeCompatibilitySettings(
                sixfold_orientation_tolerance_deg=4.0,
                conditional_channel_minimum_score=0.5,
            ),
        )

        self.assertEqual(result.decision, ("conditional_halo_edge",))
        self.assertEqual(result.retained_edges_ij, ((0, 1),))
        self.assertEqual(result.core_connectivity_eligible, (False,))

    def test_relative_m3_sublattice_phase_is_qc_not_an_edge_boundary(self) -> None:
        graph, local_order, evidence = _pair_inputs(("trifold", "trifold"))
        phase_qc_order = replace(
            local_order,
            m3_sublattice_phase=(None, None),
            m3_sublattice_phase_status=("ambiguous", "ambiguous"),
            m3_phase_gauge_anchor=("molecule-a", "molecule-a"),
            m3_sublattice_assignment_ambiguous=(True, True),
        )

        result = build_lattice_domain_edge_compatibility(
            graph,
            phase_qc_order,
            evidence,
        )

        self.assertEqual(result.decision, ("compatible_trifold",))

    def test_low_confidence_edge_is_retained_for_halo_but_not_core_connectivity(self) -> None:
        graph, local_order, evidence = _pair_inputs(
            ("trifold", "trifold"),
            classification_confidence=(0.2, 0.8),
            m3_orientation_confidence=(0.3, 0.8),
        )
        result = build_lattice_domain_edge_compatibility(
            graph,
            local_order,
            evidence,
            settings=LatticeDomainEdgeCompatibilitySettings(
                minimum_classification_confidence=0.5,
                minimum_orientation_confidence=0.5,
            ),
        )

        self.assertEqual(result.decision, ("compatible_trifold",))
        self.assertEqual(result.retained_for_domain_growth, (True,))
        self.assertEqual(result.core_connectivity_eligible, (False,))

    def test_unavailable_or_disordered_endpoint_cannot_connect_a_domain(self) -> None:
        for right_model, expected_reason in (
            ("unavailable", "endpoint_unavailable"),
            ("disordered", "endpoint_disordered"),
        ):
            with self.subTest(right_model=right_model):
                graph, local_order, evidence = _pair_inputs(("trifold", right_model))
                result = build_lattice_domain_edge_compatibility(
                    graph,
                    local_order,
                    evidence,
                )

                self.assertEqual(result.decision, ("no_domain_edge",))
                self.assertEqual(result.rejection_reason, (expected_reason,))
                self.assertEqual(result.retained_edges_ij, ())

    def test_near_equal_domain_claim_overrides_local_compatibility(self) -> None:
        graph, local_order, evidence = _pair_inputs(("trifold", "trifold"))
        result = build_lattice_domain_edge_compatibility(
            graph,
            local_order,
            evidence,
            near_equal_domain_claim_edges=((1, 0),),
        )

        self.assertEqual(result.decision, ("boundary_unassigned",))
        self.assertEqual(result.rejection_reason, ("near_equal_domain_claim",))
        self.assertEqual(result.boundary_edges_ij, ((0, 1),))

    def test_unavailable_endpoint_precedes_near_equal_domain_claim(self) -> None:
        graph, local_order, evidence = _pair_inputs(("trifold", "unavailable"))
        result = build_lattice_domain_edge_compatibility(
            graph,
            local_order,
            evidence,
            near_equal_domain_claim_edges=((0, 1),),
        )

        self.assertEqual(result.decision, ("no_domain_edge",))
        self.assertEqual(result.rejection_reason, ("endpoint_unavailable",))

    def test_settings_are_versioned_fingerprinted_and_validate_explicit_thresholds(self) -> None:
        settings = LatticeDomainEdgeCompatibilitySettings(
            trifold_orientation_tolerance_deg=7.0,
            sixfold_orientation_tolerance_deg=9.0,
            mixed_model_profile_tolerance=0.15,
            conditional_channel_minimum_score=0.6,
            minimum_classification_confidence=0.7,
            minimum_orientation_confidence=0.65,
        )

        self.assertEqual(
            LatticeDomainEdgeCompatibilitySettings.from_dict(settings.to_dict()),
            settings,
        )
        self.assertEqual(len(lattice_domain_edge_settings_fingerprint(settings)), 64)
        self.assertEqual(LATTICE_DOMAIN_EDGE_COMPATIBILITY_SCHEMA_VERSION, 2)
        with self.assertRaises(ValueError):
            LatticeDomainEdgeCompatibilitySettings(
                trifold_orientation_tolerance_deg=30.01,
            )

    def test_rejects_local_results_from_a_different_graph(self) -> None:
        graph, local_order, evidence = _pair_inputs(("trifold", "trifold"))
        other_graph = build_first_shell_graph(
            ((0.0, 0.0), (1.6, 0.0)),
            point_ids=("molecule-a", "molecule-b"),
        )

        with self.assertRaisesRegex(ValueError, "first-shell graph"):
            build_lattice_domain_edge_compatibility(
                other_graph,
                local_order,
                evidence,
            )


if __name__ == "__main__":
    unittest.main()
