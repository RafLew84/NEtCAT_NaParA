import unittest
from dataclasses import replace

from moltrack.analysis import (
    LOCAL_MULTI_SYMMETRY_BOND_ORDER_SCHEMA_VERSION,
    LocalMultiSymmetryBondOrderField,
    LocalMultiSymmetryBondOrderProvenance,
    M3SublatticeGaugeAssignment,
    build_first_shell_graph,
    build_m3_sublattice_gauge_assignment,
    m3_lattice_orientation_distance_deg,
)


def _provenance() -> LocalMultiSymmetryBondOrderProvenance:
    return LocalMultiSymmetryBondOrderProvenance(
        coordinate_frame="sample_nm",
        orientation_reference="+x_sample_axis",
        spatial_calibration_fingerprint="calibration-v1",
        registration_fingerprint="registration-v1",
        point_coordinate_fingerprint="coordinates-v1",
        first_shell_graph_fingerprint="first-shell-v1",
        qualified_trifold_subgraph_fingerprint="trifold-subgraph-v1",
        m3_phase_assignment_fingerprint="m3-phase-assignment-v1",
        analysis_settings_fingerprint="settings-v1",
    )


def _valid_field(**overrides: object) -> LocalMultiSymmetryBondOrderField:
    values: dict[str, object] = {
        "source_ids": ("molecule-0",),
        "point_count": 1,
        "psi3": (1j,),
        "q3": (1.0,),
        "theta3_polar_deg": (150.0,),
        "theta3_lattice_deg": (90.0,),
        "m3_orientation_status": ("defined",),
        "m3_orientation_confidence": (1.0,),
        "psi6": (-1.0 + 0.0j,),
        "q6": (1.0,),
        "theta6_deg": (90.0,),
        "m6_orientation_status": ("defined",),
        "m6_orientation_confidence": (1.0,),
        "neighbor_count": (3,),
        "computation_status": ("valid_order",),
        "m3_sublattice_phase": (0,),
        "m3_sublattice_phase_status": ("defined",),
        "m3_phase_gauge_anchor": ("molecule-0",),
        "m3_qualified_trifold": (True,),
        "m3_sublattice_assignment_ambiguous": (False,),
        "m3_gauge_inconsistent_cycle": (False,),
        "m3_gauge_frustration_qc": (False,),
        "symmetry_resolvability_status": ("resolvable",),
        "physical_duplicate_qc": (False,),
        "geometry_duplicate_qc": (False,),
        "edge_truncated_neighborhood": (False,),
        "distance_to_valid_fov_boundary_nm": (100.0,),
        "first_shell_r_max_nm": 70.0,
        "provenance": _provenance(),
    }
    values.update(overrides)
    return LocalMultiSymmetryBondOrderField(**values)


class LocalMultiSymmetryBondOrderFieldTests(unittest.TestCase):
    def test_builds_component_relative_phase_from_trifold_edge_parity(self) -> None:
        graph = build_first_shell_graph(
            ((2.5, 0.0), (1.25, 0.0), (0.0, 0.0)),
            point_ids=("molecule-b", "molecule-a", "molecule-c"),
        )
        assignment = build_m3_sublattice_gauge_assignment(
            first_shell_graph=graph,
            m3_orientation_status=("defined", "defined", "defined"),
            qualified_trifold_point_indices=(0, 1, 2),
        )

        self.assertEqual(assignment.m3_sublattice_phase, (1, 0, 1))
        self.assertEqual(
            assignment.m3_phase_gauge_anchor,
            ("molecule-a", "molecule-a", "molecule-a"),
        )
        self.assertEqual(
            assignment.m3_sublattice_phase_status,
            ("defined", "defined", "defined"),
        )

    def test_reports_an_inconsistent_cycle_in_the_qualified_trifold_graph(self) -> None:
        graph = build_first_shell_graph(
            ((0.0, 0.0), (1.25, 0.0), (0.625, 1.0825317547)),
            point_ids=("molecule-a", "molecule-b", "molecule-c"),
        )
        assignment = build_m3_sublattice_gauge_assignment(
            first_shell_graph=graph,
            m3_orientation_status=("defined", "defined", "defined"),
            qualified_trifold_point_indices=(0, 1, 2),
        )

        self.assertEqual(assignment.m3_sublattice_phase, (None, None, None))
        self.assertEqual(
            assignment.m3_sublattice_phase_status,
            ("inconsistent", "inconsistent", "inconsistent"),
        )
        self.assertEqual(
            assignment.m3_gauge_inconsistent_cycle,
            (True, True, True),
        )
        self.assertEqual(assignment.m3_gauge_frustration_qc, (True, True, True))

    def test_filters_first_shell_edges_with_an_explicit_trifold_qualification(self) -> None:
        graph = build_first_shell_graph(
            ((0.0, 0.0), (1.25, 0.0), (0.625, 1.0825317547)),
            point_ids=("molecule-a", "molecule-b", "molecule-c"),
        )
        assignment = build_m3_sublattice_gauge_assignment(
            first_shell_graph=graph,
            m3_orientation_status=("defined", "defined", "defined"),
            qualified_trifold_point_indices=(0, 1, 2),
            trifold_edge_qualified=(True, True, False),
        )
        unfiltered_assignment = build_m3_sublattice_gauge_assignment(
            first_shell_graph=graph,
            m3_orientation_status=("defined", "defined", "defined"),
            qualified_trifold_point_indices=(0, 1, 2),
        )

        self.assertEqual(
            assignment.m3_sublattice_phase_status,
            ("defined", "defined", "defined"),
        )
        self.assertEqual(assignment.m3_gauge_inconsistent_cycle, (False, False, False))
        self.assertNotEqual(
            assignment.qualified_trifold_subgraph_fingerprint,
            unfiltered_assignment.qualified_trifold_subgraph_fingerprint,
        )

    def test_reports_ambiguity_and_an_inconsistent_cycle_independently(self) -> None:
        graph = build_first_shell_graph(
            ((0.0, 0.0), (1.25, 0.0), (0.625, 1.0825317547)),
            point_ids=("molecule-a", "molecule-b", "molecule-c"),
        )
        assignment = build_m3_sublattice_gauge_assignment(
            first_shell_graph=graph,
            m3_orientation_status=("defined", "defined", "defined"),
            qualified_trifold_point_indices=(0, 1, 2),
            ambiguous_trifold_point_indices=(1,),
        )

        self.assertEqual(
            assignment.m3_sublattice_assignment_ambiguous,
            (True, True, True),
        )
        self.assertEqual(
            assignment.m3_gauge_inconsistent_cycle,
            (True, True, True),
        )

    def test_does_not_color_points_outside_the_qualified_trifold_graph(self) -> None:
        graph = build_first_shell_graph(
            ((0.0, 0.0), (1.25, 0.0), (2.5, 0.0)),
            point_ids=("qualified", "sixfold", "unavailable"),
        )
        assignment = build_m3_sublattice_gauge_assignment(
            first_shell_graph=graph,
            m3_orientation_status=(
                "defined",
                "defined",
                "insufficient_neighbors",
            ),
            qualified_trifold_point_indices=(0,),
        )

        self.assertEqual(assignment.m3_sublattice_phase, (0, None, None))
        self.assertEqual(
            assignment.m3_sublattice_phase_status,
            ("defined", "not_applicable", "unavailable"),
        )
        self.assertEqual(assignment.m3_qualified_trifold, (True, False, False))

    def test_marks_a_whole_qualified_component_when_phase_is_ambiguous(self) -> None:
        graph = build_first_shell_graph(
            ((0.0, 0.0), (1.25, 0.0), (2.5, 0.0)),
            point_ids=("molecule-a", "molecule-b", "molecule-c"),
        )
        assignment = build_m3_sublattice_gauge_assignment(
            first_shell_graph=graph,
            m3_orientation_status=("defined", "defined", "defined"),
            qualified_trifold_point_indices=(0, 1, 2),
            ambiguous_trifold_point_indices=(1,),
        )

        self.assertEqual(assignment.m3_sublattice_phase, (None, None, None))
        self.assertEqual(
            assignment.m3_sublattice_phase_status,
            ("ambiguous", "ambiguous", "ambiguous"),
        )
        self.assertEqual(
            assignment.m3_sublattice_assignment_ambiguous,
            (True, True, True),
        )

    def test_canonicalizes_a_directly_constructed_gauge_assignment(self) -> None:
        assignment = M3SublatticeGaugeAssignment(
            source_ids=("molecule-b", "molecule-a"),
            m3_sublattice_phase=(0, 1),
            m3_sublattice_phase_status=("defined", "defined"),
            m3_phase_gauge_anchor=("molecule-a", "molecule-a"),
            m3_qualified_trifold=(True, True),
            m3_sublattice_assignment_ambiguous=(False, False),
            m3_gauge_inconsistent_cycle=(False, False),
            m3_gauge_frustration_qc=(False, False),
            qualified_trifold_edges_ij=((0, 1),),
        )

        self.assertEqual(assignment.m3_sublattice_phase, (1, 0))

    def test_rejects_mixed_phase_statuses_within_one_gauge_component(self) -> None:
        with self.assertRaisesRegex(ValueError, "one phase status"):
            M3SublatticeGaugeAssignment(
                source_ids=("molecule-a", "molecule-b"),
                m3_sublattice_phase=(0, None),
                m3_sublattice_phase_status=("defined", "ambiguous"),
                m3_phase_gauge_anchor=("molecule-a", "molecule-a"),
                m3_qualified_trifold=(True, True),
                m3_sublattice_assignment_ambiguous=(False, True),
                m3_gauge_inconsistent_cycle=(False, False),
                m3_gauge_frustration_qc=(False, False),
                qualified_trifold_edges_ij=((0, 1),),
            )

    def test_rejects_mixed_ambiguity_flags_within_one_gauge_component(self) -> None:
        with self.assertRaisesRegex(ValueError, "ambiguity flag"):
            M3SublatticeGaugeAssignment(
                source_ids=("molecule-a", "molecule-b"),
                m3_sublattice_phase=(None, None),
                m3_sublattice_phase_status=("inconsistent", "inconsistent"),
                m3_phase_gauge_anchor=("molecule-a", "molecule-a"),
                m3_qualified_trifold=(True, True),
                m3_sublattice_assignment_ambiguous=(False, True),
                m3_gauge_inconsistent_cycle=(True, True),
                m3_gauge_frustration_qc=(True, True),
                qualified_trifold_edges_ij=((0, 1),),
            )

    def test_rejects_an_unknown_orientation_status_outside_the_subgraph(self) -> None:
        graph = build_first_shell_graph(
            ((0.0, 0.0), (1.25, 0.0)),
            point_ids=("molecule-a", "molecule-b"),
        )
        with self.assertRaisesRegex(ValueError, "orientation status"):
            build_m3_sublattice_gauge_assignment(
                first_shell_graph=graph,
                m3_orientation_status=("defined", "unknown"),
                qualified_trifold_point_indices=(0,),
            )

    def test_compares_m3_lattice_orientation_modulo_sixty_degrees(self) -> None:
        self.assertAlmostEqual(m3_lattice_orientation_distance_deg(59.0, 1.0), 2.0)
        self.assertAlmostEqual(m3_lattice_orientation_distance_deg(1.0, 61.0), 0.0)

    def test_preserves_both_channels_and_normalizes_periodic_angles(self) -> None:
        field = _valid_field()

        self.assertEqual(field.schema_version, LOCAL_MULTI_SYMMETRY_BOND_ORDER_SCHEMA_VERSION)
        self.assertEqual(field.symmetry_channels, (3, 6))
        self.assertEqual(field.theta3_polar_deg, (30.0,))
        self.assertEqual(field.theta3_lattice_deg, (30.0,))
        self.assertEqual(field.theta6_deg, (30.0,))
        self.assertEqual(field.m3_sublattice_phase, (0,))
        self.assertEqual(field.m3_phase_gauge_anchor, ("molecule-0",))
        self.assertEqual(field.m3_orientation_confidence, (1.0,))
        self.assertEqual(field.m6_orientation_confidence, (1.0,))
        self.assertEqual(field.provenance.first_shell_graph_fingerprint, "first-shell-v1")
        with self.assertRaisesRegex(ValueError, "confidence between 0 and 1"):
            _valid_field(m3_orientation_confidence=(1.1,))

    def test_low_amplitude_has_no_angle_while_edge_qc_is_independent(self) -> None:
        field = _valid_field(
            psi3=(0j,),
            q3=(0.0,),
            theta3_polar_deg=(None,),
            theta3_lattice_deg=(None,),
            m3_orientation_status=("undefined_low_amplitude",),
            m3_orientation_confidence=(None,),
            m3_sublattice_phase=(None,),
            m3_sublattice_phase_status=("unavailable",),
            m3_phase_gauge_anchor=(None,),
            m3_qualified_trifold=(False,),
            edge_truncated_neighborhood=(True,),
            distance_to_valid_fov_boundary_nm=(10.0,),
        )

        self.assertIsNone(field.theta3_polar_deg[0])
        self.assertEqual(field.m6_orientation_status[0], "defined")
        self.assertEqual(field.theta6_deg[0], 30.0)
        self.assertTrue(field.edge_truncated_neighborhood[0])

        with self.assertRaisesRegex(ValueError, "undefined_low_amplitude"):
            _valid_field(
                psi3=(0j,),
                q3=(0.0,),
                theta3_polar_deg=(0.0,),
                theta3_lattice_deg=(None,),
                m3_orientation_status=("undefined_low_amplitude",),
                m3_orientation_confidence=(None,),
                m3_sublattice_phase=(None,),
                m3_sublattice_phase_status=("unavailable",),
                m3_phase_gauge_anchor=(None,),
                m3_qualified_trifold=(False,),
            )

    def test_canonical_anchor_makes_global_phase_swap_equivalent(self) -> None:
        field = _valid_field(
            source_ids=("molecule-b", "molecule-a"),
            point_count=2,
            psi3=(1j, -1j),
            q3=(1.0, 1.0),
            theta3_polar_deg=(30.0, 90.0),
            theta3_lattice_deg=(30.0, 30.0),
            m3_orientation_status=("defined", "defined"),
            m3_orientation_confidence=(1.0, 1.0),
            psi6=(-1.0 + 0.0j, -1.0 + 0.0j),
            q6=(1.0, 1.0),
            theta6_deg=(30.0, 30.0),
            m6_orientation_status=("defined", "defined"),
            m6_orientation_confidence=(1.0, 1.0),
            neighbor_count=(3, 3),
            computation_status=("valid_order", "valid_order"),
            m3_sublattice_phase=(0, 1),
            m3_sublattice_phase_status=("defined", "defined"),
            m3_phase_gauge_anchor=("molecule-a", "molecule-a"),
            m3_qualified_trifold=(True, True),
            m3_sublattice_assignment_ambiguous=(False, False),
            m3_gauge_inconsistent_cycle=(False, False),
            m3_gauge_frustration_qc=(False, False),
            symmetry_resolvability_status=("resolvable", "resolvable"),
            physical_duplicate_qc=(False, False),
            geometry_duplicate_qc=(False, False),
            edge_truncated_neighborhood=(False, False),
            distance_to_valid_fov_boundary_nm=(100.0, 100.0),
        )

        self.assertEqual(field.m3_phase_gauge_anchor, ("molecule-a", "molecule-a"))
        self.assertEqual(field.m3_sublattice_phase, (1, 0))

    def test_defined_angles_must_match_the_complex_order_parameters(self) -> None:
        with self.assertRaisesRegex(ValueError, "theta3_lattice_deg"):
            _valid_field(theta3_lattice_deg=(10.0,))
        with self.assertRaisesRegex(ValueError, "theta6_deg"):
            _valid_field(theta6_deg=(10.0,))

    def test_common_computation_status_controls_both_channels(self) -> None:
        with self.assertRaisesRegex(ValueError, "insufficient_neighbors"):
            _valid_field(computation_status=("insufficient_neighbors",))

    def test_sublattice_phase_requires_a_defined_m3_orientation(self) -> None:
        with self.assertRaisesRegex(ValueError, "sublattice phase"):
            _valid_field(
                psi3=(0j,),
                q3=(0.0,),
                theta3_polar_deg=(None,),
                theta3_lattice_deg=(None,),
                m3_orientation_status=("undefined_low_amplitude",),
                m3_orientation_confidence=(None,),
            )

    def test_one_channel_can_be_numerically_invalid_on_a_valid_graph(self) -> None:
        field = _valid_field(
            psi3=(None,),
            q3=(None,),
            theta3_polar_deg=(None,),
            theta3_lattice_deg=(None,),
            m3_orientation_status=("invalid_geometry",),
            m3_orientation_confidence=(None,),
            m3_sublattice_phase=(None,),
            m3_sublattice_phase_status=("unavailable",),
            m3_phase_gauge_anchor=(None,),
            m3_qualified_trifold=(False,),
        )

        self.assertEqual(field.m3_orientation_status, ("invalid_geometry",))
        self.assertEqual(field.m6_orientation_status, ("defined",))

    def test_numerically_unstable_orientation_can_retain_psi_and_q(self) -> None:
        field = _valid_field(
            psi3=(0.5 + 0.0j,),
            q3=(0.5,),
            theta3_polar_deg=(None,),
            theta3_lattice_deg=(None,),
            m3_orientation_status=("invalid_geometry",),
            m3_orientation_confidence=(None,),
            m3_sublattice_phase=(None,),
            m3_sublattice_phase_status=("unavailable",),
            m3_phase_gauge_anchor=(None,),
            m3_qualified_trifold=(False,),
        )

        self.assertEqual(field.psi3, (0.5 + 0.0j,))
        self.assertEqual(field.q3, (0.5,))

        with self.assertRaisesRegex(ValueError, "invalid_geometry.*above"):
            _valid_field(
                psi3=(0j,),
                q3=(0.0,),
                theta3_polar_deg=(None,),
                theta3_lattice_deg=(None,),
                m3_orientation_status=("invalid_geometry",),
                m3_orientation_confidence=(None,),
                m3_sublattice_phase=(None,),
                m3_sublattice_phase_status=("unavailable",),
                m3_phase_gauge_anchor=(None,),
                m3_qualified_trifold=(False,),
            )

    def test_uses_the_explicit_centroid_symmetry_alias_status(self) -> None:
        field = _valid_field(
            symmetry_resolvability_status=(
                "symmetry_alias_unresolvable_from_centroids",
            )
        )

        self.assertEqual(
            field.symmetry_resolvability_status,
            ("symmetry_alias_unresolvable_from_centroids",),
        )
        with self.assertRaisesRegex(ValueError, "unsupported status"):
            _valid_field(
                symmetry_resolvability_status=(
                    "orientation_alias_unresolvable_from_centroids",
                )
            )

    def test_rejects_an_unknown_model_schema_version(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unsupported schema_version"):
            _valid_field(schema_version=999)
        with self.assertRaisesRegex(ValueError, "Unsupported schema_version"):
            _valid_field(schema_version=True)

    def test_requires_complete_shared_graph_provenance(self) -> None:
        with self.assertRaisesRegex(TypeError, "first_shell_graph_fingerprint"):
            _valid_field(
                provenance=replace(_provenance(), first_shell_graph_fingerprint="")
            )

    def test_edge_qc_must_match_the_shared_first_shell_context(self) -> None:
        with self.assertRaisesRegex(ValueError, "edge_truncated_neighborhood"):
            _valid_field(edge_truncated_neighborhood=(True,))

    def test_represents_points_without_a_valid_local_order(self) -> None:
        field = _valid_field(
            source_ids=("insufficient", "duplicate", "invalid"),
            point_count=3,
            psi3=(None, None, None),
            q3=(None, None, None),
            theta3_polar_deg=(None, None, None),
            theta3_lattice_deg=(None, None, None),
            m3_orientation_status=(
                "insufficient_neighbors",
                "invalid_geometry",
                "invalid_geometry",
            ),
            m3_orientation_confidence=(None, None, None),
            psi6=(None, None, None),
            q6=(None, None, None),
            theta6_deg=(None, None, None),
            m6_orientation_status=(
                "insufficient_neighbors",
                "invalid_geometry",
                "invalid_geometry",
            ),
            m6_orientation_confidence=(None, None, None),
            neighbor_count=(2, 0, 0),
            computation_status=(
                "insufficient_neighbors",
                "duplicate_excluded",
                "invalid_position",
            ),
            m3_sublattice_phase=(None, None, None),
            m3_sublattice_phase_status=(
                "unavailable",
                "unavailable",
                "unavailable",
            ),
            m3_phase_gauge_anchor=(None, None, None),
            m3_qualified_trifold=(False, False, False),
            m3_sublattice_assignment_ambiguous=(False, False, False),
            m3_gauge_inconsistent_cycle=(False, False, False),
            m3_gauge_frustration_qc=(False, False, False),
            symmetry_resolvability_status=(
                "unavailable",
                "unavailable",
                "unavailable",
            ),
            physical_duplicate_qc=(False, True, False),
            geometry_duplicate_qc=(False, False, False),
            edge_truncated_neighborhood=(False, False, False),
            distance_to_valid_fov_boundary_nm=(100.0, 100.0, None),
        )

        self.assertEqual(field.psi3, (None, None, None))
        self.assertEqual(field.psi6, (None, None, None))
        self.assertEqual(
            field.computation_status,
            ("insufficient_neighbors", "duplicate_excluded", "invalid_position"),
        )

        with self.assertRaisesRegex(ValueError, "Non-valid order cannot retain"):
            _valid_field(
                psi3=(0.5 + 0.0j,),
                q3=(0.5,),
                theta3_polar_deg=(None,),
                theta3_lattice_deg=(None,),
                m3_orientation_status=("invalid_geometry",),
                m3_orientation_confidence=(None,),
                psi6=(None,),
                q6=(None,),
                theta6_deg=(None,),
                m6_orientation_status=("invalid_geometry",),
                m6_orientation_confidence=(None,),
                neighbor_count=(0,),
                computation_status=("duplicate_excluded",),
                m3_sublattice_phase=(None,),
                m3_sublattice_phase_status=("unavailable",),
                m3_phase_gauge_anchor=(None,),
                m3_qualified_trifold=(False,),
                symmetry_resolvability_status=("unavailable",),
                physical_duplicate_qc=(True,),
            )

    def test_resolves_input_indices_by_stable_source_id(self) -> None:
        field = _valid_field()

        self.assertEqual(field.index_for_source_id("molecule-0"), 0)
        with self.assertRaisesRegex(KeyError, "missing"):
            field.index_for_source_id("missing")

    def test_orientation_status_uses_explicit_per_channel_q_tolerances(self) -> None:
        field = _valid_field(
            psi3=(0.05 + 0.0j,),
            q3=(0.05,),
            theta3_polar_deg=(None,),
            theta3_lattice_deg=(None,),
            m3_orientation_status=("undefined_low_amplitude",),
            m3_orientation_confidence=(None,),
            m3_sublattice_phase=(None,),
            m3_sublattice_phase_status=("unavailable",),
            m3_phase_gauge_anchor=(None,),
            m3_qualified_trifold=(False,),
            m3_orientation_zero_tolerance=0.1,
        )

        self.assertEqual(field.m3_orientation_zero_tolerance, 0.1)
        with self.assertRaisesRegex(ValueError, "M3 defined"):
            _valid_field(
                psi3=(0.05 + 0.0j,),
                q3=(0.05,),
                theta3_polar_deg=(0.0,),
                theta3_lattice_deg=(0.0,),
                m3_orientation_zero_tolerance=0.1,
            )
        with self.assertRaisesRegex(ValueError, "M6 defined"):
            _valid_field(
                psi6=(0.05 + 0.0j,),
                q6=(0.05,),
                theta6_deg=(0.0,),
                m6_orientation_zero_tolerance=0.1,
            )

    def test_rejects_m3_gauge_status_that_disagrees_with_qc_flags(self) -> None:
        with self.assertRaisesRegex(ValueError, "ambiguous.*QC"):
            _valid_field(
                m3_sublattice_phase=(None,),
                m3_sublattice_phase_status=("ambiguous",),
            )

    def test_represents_an_ambiguous_m3_sublattice_assignment(self) -> None:
        field = _valid_field(
            m3_sublattice_phase=(None,),
            m3_sublattice_phase_status=("ambiguous",),
            m3_sublattice_assignment_ambiguous=(True,),
        )

        self.assertEqual(field.m3_sublattice_phase_status, ("ambiguous",))
        self.assertEqual(field.m3_sublattice_assignment_ambiguous, (True,))


if __name__ == "__main__":
    unittest.main()
