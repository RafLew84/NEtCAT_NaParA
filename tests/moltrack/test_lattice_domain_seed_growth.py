import unittest
from dataclasses import replace
from math import cos, radians, sin

from moltrack.analysis import (
    LatticeDomainEdgeCompatibilitySettings,
    LatticeDomainSeedGrowthSettings,
    LocalMultiSymmetryBondOrderField,
    LocalMultiSymmetryBondOrderProvenance,
    LocalSymmetryEvidenceField,
    build_first_shell_graph,
    build_lattice_domain_edge_compatibility,
    build_lattice_domain_seed_growth,
)
from moltrack.analysis._first_shell_graph_fingerprint import (
    first_shell_graph_fingerprint,
)


_PROFILE_BY_MODEL = {
    "trifold": (0.90, 0.25, 0.35, 0.10),
    "sixfold": (0.25, 0.90, 0.35, 0.10),
    "mixed": (0.72, 0.74, 0.90, 0.10),
    "ambiguous": (0.61, 0.59, 0.58, 0.20),
}


def _harmonic(order: int, angle_deg: float, amplitude: float) -> complex:
    phase = radians(order * angle_deg)
    return amplitude * complex(cos(phase), sin(phase))


def _inputs(
    records: tuple[tuple[str, float, float, str, float, float], ...],
    *,
    positions: dict[str, tuple[float, float]] | None = None,
    profiles: tuple[tuple[float, float, float, float], ...] | None = None,
    edge_settings: LatticeDomainEdgeCompatibilitySettings | None = None,
):
    """Build aligned graph/order/evidence from id, q3, q6, model, theta3, theta6."""

    source_ids = tuple(record[0] for record in records)
    if positions is None:
        positions = {
            source_id: (1.5 * index, 0.0)
            for index, source_id in enumerate(sorted(source_ids))
        }
    graph = build_first_shell_graph(
        tuple(positions[source_id] for source_id in source_ids),
        point_ids=source_ids,
    )
    graph_fingerprint = first_shell_graph_fingerprint(graph)
    q3 = tuple(record[1] for record in records)
    q6 = tuple(record[2] for record in records)
    models = tuple(record[3] for record in records)
    theta3 = tuple(record[4] for record in records)
    theta6 = tuple(record[5] for record in records)
    qualified = tuple(model == "trifold" for model in models)
    local_order = LocalMultiSymmetryBondOrderField(
        source_ids=source_ids,
        point_count=len(records),
        psi3=tuple(_harmonic(3, angle, amplitude) for angle, amplitude in zip(theta3, q3)),
        q3=q3,
        theta3_polar_deg=tuple(angle % 120.0 for angle in theta3),
        theta3_lattice_deg=tuple(angle % 60.0 for angle in theta3),
        m3_orientation_status=("defined",) * len(records),
        m3_orientation_confidence=(0.9,) * len(records),
        psi6=tuple(_harmonic(6, angle, amplitude) for angle, amplitude in zip(theta6, q6)),
        q6=q6,
        theta6_deg=tuple(angle % 60.0 for angle in theta6),
        m6_orientation_status=("defined",) * len(records),
        m6_orientation_confidence=(0.9,) * len(records),
        neighbor_count=(6,) * len(records),
        computation_status=("valid_order",) * len(records),
        m3_sublattice_phase=tuple(0 if value else None for value in qualified),
        m3_sublattice_phase_status=tuple(
            "defined" if value else "not_applicable" for value in qualified
        ),
        m3_phase_gauge_anchor=tuple(
            source_id if value else None
            for source_id, value in zip(source_ids, qualified)
        ),
        m3_qualified_trifold=qualified,
        m3_sublattice_assignment_ambiguous=(False,) * len(records),
        m3_gauge_inconsistent_cycle=(False,) * len(records),
        m3_gauge_frustration_qc=(False,) * len(records),
        symmetry_resolvability_status=("resolvable",) * len(records),
        physical_duplicate_qc=(False,) * len(records),
        geometry_duplicate_qc=(False,) * len(records),
        edge_truncated_neighborhood=(False,) * len(records),
        distance_to_valid_fov_boundary_nm=(100.0,) * len(records),
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
    profiles = profiles or tuple(_PROFILE_BY_MODEL[model] for model in models)
    evidence = LocalSymmetryEvidenceField(
        source_ids=source_ids,
        point_count=len(records),
        trifold_model_score=tuple(profile[0] for profile in profiles),
        sixfold_model_score=tuple(profile[1] for profile in profiles),
        mixed_model_score=tuple(profile[2] for profile in profiles),
        disordered_model_score=tuple(profile[3] for profile in profiles),
        best_model=models,
        second_best_margin=tuple(0.01 if model == "ambiguous" else 0.3 for model in models),
        observed_direction_count=(6,) * len(records),
        expected_direction_coverage=(0.9,) * len(records),
        classification_confidence=tuple(0.0 if model == "ambiguous" else 0.9 for model in models),
        classification_reason=tuple(
            "below_minimum_margin" if model == "ambiguous" else f"classified_{model}"
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
        edge_truncated_neighborhood=(False,) * len(records),
        first_shell_graph_fingerprint=graph_fingerprint,
        local_order_analysis_fingerprint="local-order-v1",
        settings_fingerprint="local-evidence-settings-v1",
        bond_evidence_fingerprint="bond-evidence-v1",
    )
    edges = build_lattice_domain_edge_compatibility(
        graph,
        local_order,
        evidence,
        settings=edge_settings,
    )
    return graph, local_order, evidence, edges


def _run(records, *, settings=None, positions=None, profiles=None, edge_settings=None):
    graph, local_order, evidence, edges = _inputs(
        records,
        positions=positions,
        profiles=profiles,
        edge_settings=edge_settings,
    )
    return build_lattice_domain_seed_growth(
        graph,
        local_order,
        evidence,
        edges,
        settings=settings,
    )


class LatticeDomainSeedGrowthTests(unittest.TestCase):
    def test_builds_validated_seeds_separately_for_each_symmetry(self) -> None:
        result = _run(
            (
                ("t-a", 0.9, 0.4, "trifold", 4.0, 4.0),
                ("t-b", 0.9, 0.4, "trifold", 6.0, 6.0),
                ("s-a", 0.4, 0.9, "sixfold", 20.0, 20.0),
                ("s-b", 0.4, 0.9, "sixfold", 22.0, 22.0),
            ),
            settings=LatticeDomainSeedGrowthSettings(
                min_ordered_component_size=2,
                min_seed_size=2,
            ),
        )

        self.assertEqual(
            tuple(
                (component.symmetry_model, component.seed_state)
                for component in result.components
            ),
            (("sixfold", "validated_seed"), ("trifold", "validated_seed")),
        )
        self.assertEqual(
            tuple(component.seed_support_count for component in result.components),
            (2, 2),
        )
        self.assertEqual(result.point_role, ("core", "core", "core", "core"))

    def test_complete_linkage_prevents_an_orientation_bridge(self) -> None:
        result = _run(
            (
                ("a", 0.4, 0.9, "sixfold", 0.0, 0.0),
                ("b", 0.4, 0.9, "sixfold", 7.0, 7.0),
                ("c", 0.4, 0.9, "sixfold", 14.0, 14.0),
            ),
            settings=LatticeDomainSeedGrowthSettings(
                seed_max_orientation_spread_deg=8.0,
                min_ordered_component_size=2,
                min_seed_size=2,
            ),
        )

        self.assertEqual(tuple(component.core_size for component in result.components), (2, 1))
        self.assertEqual(
            tuple(component.seed_state for component in result.components),
            ("validated_seed", "proto_seed"),
        )

    def test_periodic_spread_requires_one_common_orientation_window(self) -> None:
        result = _run(
            (
                ("a", 0.4, 0.9, "sixfold", 0.0, 0.0),
                ("b", 0.4, 0.9, "sixfold", 20.0, 20.0),
                ("c", 0.4, 0.9, "sixfold", 40.0, 40.0),
            ),
            edge_settings=LatticeDomainEdgeCompatibilitySettings(
                sixfold_orientation_tolerance_deg=20.0,
            ),
            settings=LatticeDomainSeedGrowthSettings(
                seed_max_orientation_spread_deg=20.0,
                grow_max_orientation_spread_deg=20.0,
                min_ordered_component_size=2,
                min_seed_size=2,
            ),
        )

        self.assertEqual(tuple(component.core_size for component in result.components), (2, 1))

    def test_conflict_edge_blocks_merge_even_when_another_cross_edge_is_compatible(self) -> None:
        positions = {"a": (0.0, 0.0), "b": (1.3, 0.0), "c": (0.65, 1.1)}
        result = _run(
            (
                ("a", 0.9, 0.9, "mixed", 0.0, 0.0),
                ("b", 0.9, 0.9, "mixed", 0.0, 0.0),
                ("c", 0.9, 0.9, "mixed", 0.0, 0.0),
            ),
            positions=positions,
            profiles=(
                (0.30, 0.30, 0.90, 0.10),
                (0.45, 0.45, 0.90, 0.10),
                (0.60, 0.60, 0.90, 0.10),
            ),
            settings=LatticeDomainSeedGrowthSettings(
                min_ordered_component_size=2,
                min_seed_size=2,
            ),
        )

        self.assertEqual(tuple(component.core_size for component in result.components), (2, 1))

    def test_adding_one_compatible_seed_does_not_reassign_existing_core(self) -> None:
        settings = LatticeDomainSeedGrowthSettings(
            min_ordered_component_size=2,
            min_seed_size=2,
        )
        without_added = _run(
            (
                ("a", 0.4, 0.9, "sixfold", 0.0, 0.0),
                ("b", 0.4, 0.9, "sixfold", 6.0, 6.0),
                ("d", 0.4, 0.9, "sixfold", 12.0, 12.0),
            ),
            positions={"a": (0.0, 0.0), "b": (1.5, 0.0), "d": (0.0, 1.5)},
            settings=settings,
        )
        with_added = _run(
            (
                ("a", 0.4, 0.9, "sixfold", 0.0, 0.0),
                ("b", 0.4, 0.9, "sixfold", 6.0, 6.0),
                ("c", 0.4, 0.9, "sixfold", 7.0, 7.0),
                ("d", 0.4, 0.9, "sixfold", 12.0, 12.0),
            ),
            positions={
                "a": (0.0, 0.0),
                "b": (1.5, 0.0),
                "c": (1.5, 1.5),
                "d": (0.0, 1.5),
            },
            settings=settings,
        )

        def same_component(result, first, second):
            first_index = result.source_ids.index(first)
            second_index = result.source_ids.index(second)
            return result.component_id[first_index] == result.component_id[second_index]

        for pair in (("a", "b"), ("a", "d"), ("b", "d")):
            self.assertEqual(
                same_component(without_added, *pair),
                same_component(with_added, *pair),
            )

    def test_near_equal_domain_claim_is_left_as_boundary(self) -> None:
        positions = {"left": (0.0, 0.0), "candidate": (1.3, 0.0), "right": (0.65, 1.1)}
        result = _run(
            (
                ("left", 0.4, 0.9, "sixfold", 0.0, 0.0),
                ("candidate", 0.4, 0.5, "sixfold", 5.0, 5.0),
                ("right", 0.4, 0.9, "sixfold", 10.0, 10.0),
            ),
            positions=positions,
            settings=LatticeDomainSeedGrowthSettings(
                seed_max_orientation_spread_deg=4.0,
                grow_max_orientation_spread_deg=8.0,
                min_ordered_component_size=1,
                min_seed_size=1,
                conflict_margin=0.05,
            ),
        )

        candidate = result.source_ids.index("candidate")
        self.assertEqual(result.point_role[candidate], "boundary")
        self.assertEqual(result.boundary_reason[candidate], "competing_domain_claim")
        self.assertEqual(sum(component.halo_size for component in result.components), 0)

    def test_joint_growth_batch_must_obey_complete_linkage(self) -> None:
        positions = {
            "core": (0.0, 0.0),
            "minus": (-1.5, 0.0),
            "plus": (1.5, 0.0),
        }
        result = _run(
            (
                ("core", 0.4, 0.9, "sixfold", 0.0, 0.0),
                ("minus", 0.4, 0.5, "sixfold", 54.0, 54.0),
                ("plus", 0.4, 0.5, "sixfold", 6.0, 6.0),
            ),
            positions=positions,
            settings=LatticeDomainSeedGrowthSettings(
                seed_max_orientation_spread_deg=4.0,
                grow_max_orientation_spread_deg=8.0,
                min_ordered_component_size=1,
                min_seed_size=1,
            ),
        )

        self.assertEqual(result.point_role[0], "core")
        self.assertEqual(result.point_role[1:], ("boundary", "boundary"))
        self.assertEqual(
            result.boundary_reason[1:],
            ("batch_orientation_spread", "batch_orientation_spread"),
        )
        self.assertEqual(result.components[0].halo_size, 0)

    def test_conflicting_candidates_cannot_enter_the_same_halo_batch(self) -> None:
        positions = {"core": (0.0, 0.0), "left": (1.3, 0.0), "right": (0.65, 1.1)}
        result = _run(
            (
                ("core", 0.9, 0.9, "mixed", 0.0, 0.0),
                ("left", 0.5, 0.5, "mixed", 0.0, 0.0),
                ("right", 0.5, 0.5, "mixed", 0.0, 0.0),
            ),
            positions=positions,
            profiles=(
                (0.45, 0.45, 0.90, 0.10),
                (0.30, 0.30, 0.90, 0.10),
                (0.60, 0.60, 0.90, 0.10),
            ),
            settings=LatticeDomainSeedGrowthSettings(
                min_ordered_component_size=1,
                min_seed_size=1,
            ),
        )

        self.assertEqual(result.point_role, ("core", "boundary", "boundary"))
        self.assertEqual(
            result.boundary_reason[1:],
            ("incompatible_domain_edge", "incompatible_domain_edge"),
        )

    def test_halo_grows_without_increasing_seed_support(self) -> None:
        result = _run(
            (
                ("a", 0.4, 0.9, "sixfold", 0.0, 0.0),
                ("b", 0.4, 0.9, "sixfold", 2.0, 2.0),
                ("c", 0.4, 0.5, "sixfold", 3.0, 3.0),
            ),
            settings=LatticeDomainSeedGrowthSettings(
                min_ordered_component_size=2,
                min_seed_size=2,
            ),
        )

        component = result.components[0]
        self.assertEqual(component.seed_state, "validated_seed")
        self.assertEqual(component.seed_support_count, 2)
        self.assertEqual(component.core_size, 2)
        self.assertEqual(component.halo_size, 1)
        self.assertEqual(result.point_role, ("core", "core", "halo"))
        stability = {
            item.threshold_offset: item for item in result.seed_support_stability
        }
        self.assertEqual(stability[0].halo_source_ids, ("c",))
        self.assertEqual(stability[1].halo_source_ids, ())

    def test_mixed_seed_must_fit_both_periodic_orientation_channels(self) -> None:
        result = _run(
            (
                ("a", 0.9, 0.9, "mixed", 0.0, 0.0),
                ("b", 0.9, 0.9, "mixed", 2.0, 7.0),
            ),
            settings=LatticeDomainSeedGrowthSettings(
                seed_max_orientation_spread_deg=6.0,
                min_ordered_component_size=2,
                min_seed_size=2,
            ),
        )

        self.assertEqual(tuple(component.core_size for component in result.components), (1, 1))
        self.assertEqual(
            tuple(component.seed_state for component in result.components),
            ("proto_seed", "proto_seed"),
        )

    def test_conditional_halo_edges_cannot_create_a_seed(self) -> None:
        result = _run(
            (
                ("left", 0.9, 0.4, "trifold", 3.0, 3.0),
                ("middle", 0.6, 0.6, "ambiguous", 4.0, 4.0),
                ("right", 0.9, 0.4, "trifold", 5.0, 5.0),
            ),
            settings=LatticeDomainSeedGrowthSettings(
                min_ordered_component_size=2,
                min_seed_size=2,
            ),
        )

        self.assertEqual(tuple(component.core_size for component in result.components), (1, 1))
        self.assertEqual(
            tuple(component.seed_state for component in result.components),
            ("proto_seed", "proto_seed"),
        )
        self.assertNotIn("halo", result.point_role)

    def test_conditional_halo_edge_must_match_the_domain_channel(self) -> None:
        result = _run(
            (
                ("sixfold-core", 0.4, 0.9, "sixfold", 0.0, 0.0),
                ("mixed-halo", 0.5, 0.5, "mixed", 0.0, 0.0),
                ("ambiguous-tail", 0.5, 0.5, "ambiguous", 0.0, 10.0),
            ),
            positions={
                "sixfold-core": (0.0, 0.0),
                "mixed-halo": (1.5, 0.0),
                "ambiguous-tail": (3.0, 0.0),
            },
            settings=LatticeDomainSeedGrowthSettings(
                min_ordered_component_size=1,
                min_seed_size=1,
            ),
        )

        mixed_index = result.source_ids.index("mixed-halo")
        ambiguous_index = result.source_ids.index("ambiguous-tail")
        self.assertEqual(result.point_role[mixed_index], "halo")
        self.assertEqual(result.point_role[ambiguous_index], "unassigned")

    def test_conditional_edge_cannot_be_reused_for_a_different_symmetry(self) -> None:
        result = _run(
            (
                ("sixfold-core", 0.4, 0.9, "sixfold", 0.0, 0.0),
                ("mixed-halo", 0.5, 0.5, "mixed", 0.0, 0.0),
                ("trifold-tail", 0.5, 0.5, "trifold", 0.0, 0.0),
            ),
            positions={
                "sixfold-core": (0.0, 0.0),
                "mixed-halo": (1.5, 0.0),
                "trifold-tail": (3.0, 0.0),
            },
            settings=LatticeDomainSeedGrowthSettings(
                min_ordered_component_size=1,
                min_seed_size=1,
            ),
        )

        mixed_index = result.source_ids.index("mixed-halo")
        trifold_index = result.source_ids.index("trifold-tail")
        self.assertEqual(result.point_role[mixed_index], "halo")
        self.assertEqual(result.point_role[trifold_index], "unassigned")

    def test_edge_truncated_point_cannot_initiate_a_seed(self) -> None:
        graph, local_order, evidence, _edges = _inputs(
            (("edge", 0.4, 0.9, "sixfold", 0.0, 0.0),)
        )
        local_order = replace(
            local_order,
            edge_truncated_neighborhood=(True,),
            distance_to_valid_fov_boundary_nm=(1.0,),
        )
        evidence = replace(evidence, edge_truncated_neighborhood=(True,))
        edges = build_lattice_domain_edge_compatibility(
            graph,
            local_order,
            evidence,
        )

        result = build_lattice_domain_seed_growth(
            graph,
            local_order,
            evidence,
            edges,
            settings=LatticeDomainSeedGrowthSettings(
                min_ordered_component_size=1,
                min_seed_size=1,
            ),
        )

        self.assertEqual(result.components, ())
        self.assertEqual(result.point_role, ("unassigned",))

    def test_reports_small_ordered_island_below_seed_support(self) -> None:
        result = _run(
            (
                ("a", 0.4, 0.9, "sixfold", 0.0, 0.0),
                ("b", 0.4, 0.9, "sixfold", 2.0, 2.0),
                ("c", 0.4, 0.9, "sixfold", 4.0, 4.0),
            ),
            settings=LatticeDomainSeedGrowthSettings(
                min_ordered_component_size=3,
                min_seed_size=4,
            ),
        )

        self.assertEqual(len(result.components), 1)
        self.assertEqual(result.components[0].seed_state, "small_ordered_island")
        self.assertEqual(result.components[0].seed_support_count, 3)

    def test_result_is_invariant_to_input_order_by_source_id(self) -> None:
        records = (
            ("a", 0.4, 0.9, "sixfold", 0.0, 0.0),
            ("b", 0.4, 0.9, "sixfold", 7.0, 7.0),
            ("c", 0.4, 0.9, "sixfold", 14.0, 14.0),
            ("d", 0.4, 0.5, "sixfold", 20.0, 20.0),
        )
        settings = LatticeDomainSeedGrowthSettings(
            seed_max_orientation_spread_deg=8.0,
            min_ordered_component_size=2,
            min_seed_size=2,
        )
        first = _run(records, settings=settings)
        second = _run(tuple(reversed(records)), settings=settings)

        def assignments(result):
            return {
                source_id: (result.point_role[index], result.component_id[index])
                for index, source_id in enumerate(result.source_ids)
            }

        self.assertEqual(assignments(first), assignments(second))
        self.assertEqual(
            tuple(
                (item.threshold_offset, item.min_seed_size)
                for item in first.seed_support_stability
            ),
            ((-1, 1), (0, 2), (1, 3)),
        )


if __name__ == "__main__":
    unittest.main()
