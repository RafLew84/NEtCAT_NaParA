import math
import unittest
from dataclasses import replace

import numpy as np

from moltrack.analysis import (
    FirstShellGraph,
    MolecularM6OrientationAnalysisSettings,
    build_first_shell_graph,
    compute_local_multisymmetry_bond_order,
    compute_local_sixfold_bond_order,
    m3_lattice_orientation_distance_deg,
)


def _star_graph(angles_rad: tuple[float, ...]) -> FirstShellGraph:
    point_count = len(angles_rad) + 1
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


def _ring_settings() -> MolecularM6OrientationAnalysisSettings:
    return MolecularM6OrientationAnalysisSettings(
        first_shell_r_min_nm=0.9,
        first_shell_r_max_nm=1.1,
        min_neighbors_for_local_order=2,
    )


def _hexagonal_ring(
    *,
    rotation_deg: float = 0.0,
    permutation: tuple[int, ...] | None = None,
) -> tuple[FirstShellGraph, MolecularM6OrientationAnalysisSettings]:
    angles = np.radians(rotation_deg + np.arange(6, dtype=np.float64) * 60.0)
    points = np.column_stack((np.cos(angles), np.sin(angles)))
    point_ids = tuple(f"molecule-{index}" for index in range(6))
    if permutation is not None:
        indices = np.asarray(permutation, dtype=np.int64)
        points = points[indices]
        point_ids = tuple(point_ids[index] for index in permutation)
    settings = _ring_settings()
    return (
        build_first_shell_graph(points, point_ids=point_ids, settings=settings),
        settings,
    )


def _compute(
    graph: FirstShellGraph,
    *,
    settings: MolecularM6OrientationAnalysisSettings | None = None,
    qualified_trifold_point_indices: tuple[int, ...] = (),
):
    return compute_local_multisymmetry_bond_order(
        graph,
        distance_to_valid_fov_boundary_nm=(10.0,) * graph.point_count,
        settings=settings,
        qualified_trifold_point_indices=qualified_trifold_point_indices,
    )


class LocalMultiSymmetryBondOrderComputationTests(unittest.TestCase):
    def test_computes_ideal_three_direction_trifold_order(self) -> None:
        result = _compute(
            _star_graph((0.0, 2.0 * math.pi / 3.0, 4.0 * math.pi / 3.0))
        )

        self.assertAlmostEqual(result.q3[0], 1.0)
        self.assertAlmostEqual(result.theta3_polar_deg[0], 0.0)
        self.assertAlmostEqual(
            m3_lattice_orientation_distance_deg(result.theta3_lattice_deg[0], 0.0),
            0.0,
        )
        self.assertEqual(result.m3_orientation_status[0], "defined")

    def test_computes_two_component_relative_trifold_sublattices(self) -> None:
        graph, settings = _hexagonal_ring()

        result = _compute(
            graph,
            settings=settings,
            qualified_trifold_point_indices=tuple(range(graph.point_count)),
        )

        self.assertEqual(result.neighbor_count, graph.degree)
        self.assertEqual(result.computation_status, ("valid_order",) * 6)
        for index in range(graph.point_count):
            self.assertAlmostEqual(result.q3[index], 1.0)
            self.assertAlmostEqual(result.q6[index], 1.0)
            self.assertEqual(result.m3_sublattice_phase_status[index], "defined")
            for neighbor in graph.neighbors_for_point(index):
                self.assertNotEqual(
                    result.m3_sublattice_phase[index],
                    result.m3_sublattice_phase[neighbor],
                )
                polar_delta = abs(
                    (result.theta3_polar_deg[index] - result.theta3_polar_deg[neighbor])
                    % 120.0
                )
                self.assertAlmostEqual(polar_delta, 60.0)

    def test_phase_assignment_provenance_includes_ambiguity(self) -> None:
        graph, settings = _hexagonal_ring()
        qualified = tuple(range(graph.point_count))
        defined = _compute(
            graph,
            settings=settings,
            qualified_trifold_point_indices=qualified,
        )
        ambiguous = compute_local_multisymmetry_bond_order(
            graph,
            distance_to_valid_fov_boundary_nm=(10.0,) * graph.point_count,
            settings=settings,
            qualified_trifold_point_indices=qualified,
            ambiguous_trifold_point_indices=(0,),
        )

        self.assertEqual(
            defined.provenance.qualified_trifold_subgraph_fingerprint,
            ambiguous.provenance.qualified_trifold_subgraph_fingerprint,
        )
        self.assertNotEqual(
            defined.provenance.m3_phase_assignment_fingerprint,
            ambiguous.provenance.m3_phase_assignment_fingerprint,
        )
        self.assertEqual(
            ambiguous.m3_sublattice_phase_status,
            ("ambiguous",) * graph.point_count,
        )

    def test_computes_sixfold_order_without_inventing_an_m3_angle(self) -> None:
        rotation_deg = 17.0
        angles = tuple(
            math.radians(rotation_deg + 60.0 * index) for index in range(6)
        )

        result = _compute(_star_graph(angles))

        self.assertAlmostEqual(result.q6[0], 1.0)
        self.assertAlmostEqual(result.theta6_deg[0], rotation_deg)
        self.assertAlmostEqual(result.q3[0], 0.0, places=12)
        self.assertEqual(result.m3_orientation_status[0], "undefined_low_amplitude")
        self.assertIsNone(result.theta3_polar_deg[0])
        self.assertIsNone(result.theta3_lattice_deg[0])

    def test_computes_both_channels_for_a_mixed_direction_set(self) -> None:
        graph = _star_graph((0.0, math.pi / 3.0, 2.0 * math.pi / 3.0))
        result = _compute(graph)

        m3_suppressed = compute_local_multisymmetry_bond_order(
            graph,
            distance_to_valid_fov_boundary_nm=(10.0,) * graph.point_count,
            m3_orientation_zero_tolerance=0.4,
            m6_orientation_zero_tolerance=0.1,
        )

        self.assertAlmostEqual(result.q3[0], 1.0 / 3.0)
        self.assertAlmostEqual(result.q6[0], 1.0)
        self.assertEqual(result.m3_orientation_status[0], "defined")
        self.assertEqual(result.m6_orientation_status[0], "defined")
        self.assertEqual(
            m3_suppressed.m3_orientation_status[0],
            "undefined_low_amplitude",
        )
        self.assertEqual(m3_suppressed.m6_orientation_status[0], "defined")
        self.assertIsNone(m3_suppressed.theta3_lattice_deg[0])

    def test_preserves_the_existing_m6_result_for_the_same_context(self) -> None:
        graph = _star_graph((0.13, 0.41, 1.72, 2.05, 4.33, 5.71))
        boundary_distances = (10.0,) * graph.point_count

        existing = compute_local_sixfold_bond_order(
            graph,
            distance_to_valid_fov_boundary_nm=boundary_distances,
        )
        multisymmetry = compute_local_multisymmetry_bond_order(
            graph,
            distance_to_valid_fov_boundary_nm=boundary_distances,
        )

        self.assertEqual(multisymmetry.psi6, existing.psi6)
        self.assertEqual(multisymmetry.q6, existing.q6)
        self.assertEqual(multisymmetry.theta6_deg, existing.lattice_orientation_deg)
        self.assertEqual(multisymmetry.neighbor_count, existing.neighbor_count)
        self.assertEqual(multisymmetry.computation_status, existing.computation_status)
        self.assertEqual(
            multisymmetry.edge_truncated_neighborhood,
            existing.edge_truncated_neighborhood,
        )

    def test_is_covariant_to_rotation_and_invariant_to_input_permutation(self) -> None:
        graph, settings = _hexagonal_ring()
        rotated_graph, _ = _hexagonal_ring(rotation_deg=19.0)
        permutation = (4, 1, 5, 0, 3, 2)
        permuted_graph, _ = _hexagonal_ring(permutation=permutation)

        reference = _compute(
            graph,
            settings=settings,
            qualified_trifold_point_indices=tuple(range(6)),
        )
        rotated = _compute(
            rotated_graph,
            settings=settings,
            qualified_trifold_point_indices=tuple(range(6)),
        )
        permuted = _compute(
            permuted_graph,
            settings=settings,
            qualified_trifold_point_indices=tuple(range(6)),
        )

        for source_id in graph.point_ids:
            ref_index = reference.index_for_source_id(source_id)
            rotated_index = rotated.index_for_source_id(source_id)
            permuted_index = permuted.index_for_source_id(source_id)
            self.assertAlmostEqual(reference.q3[ref_index], rotated.q3[rotated_index])
            self.assertAlmostEqual(reference.q6[ref_index], rotated.q6[rotated_index])
            self.assertAlmostEqual(
                m3_lattice_orientation_distance_deg(
                    rotated.theta3_lattice_deg[rotated_index],
                    reference.theta3_lattice_deg[ref_index] + 19.0,
                ),
                0.0,
            )
            self.assertAlmostEqual(
                m3_lattice_orientation_distance_deg(
                    permuted.theta3_lattice_deg[permuted_index],
                    reference.theta3_lattice_deg[ref_index],
                ),
                0.0,
            )
        self._assert_phase_equivalent_up_to_global_swap(
            reference,
            rotated,
            graph.point_ids,
        )
        self._assert_phase_equivalent_up_to_global_swap(
            reference,
            permuted,
            graph.point_ids,
        )

    def test_reversing_every_bond_direction_preserves_m3_lattice_orientation(self) -> None:
        graph, settings = _hexagonal_ring()
        reversed_directions = replace(
            graph,
            angles_rad=tuple(angle + math.pi for angle in graph.angles_rad),
            candidate_angles_rad=tuple(
                angle + math.pi for angle in graph.candidate_angles_rad
            ),
        )

        reference = _compute(
            graph,
            settings=settings,
            qualified_trifold_point_indices=tuple(range(6)),
        )
        reversed_result = _compute(
            reversed_directions,
            settings=settings,
            qualified_trifold_point_indices=tuple(range(6)),
        )

        for index in range(graph.point_count):
            self.assertAlmostEqual(reference.q3[index], reversed_result.q3[index])
            self.assertAlmostEqual(
                m3_lattice_orientation_distance_deg(
                    reference.theta3_lattice_deg[index],
                    reversed_result.theta3_lattice_deg[index],
                ),
                0.0,
            )
            self.assertAlmostEqual(reversed_result.psi3[index], -reference.psi3[index])
            self.assertEqual(
                reversed_result.m3_sublattice_phase[index],
                reference.m3_sublattice_phase[index],
            )

    def _assert_phase_equivalent_up_to_global_swap(
        self,
        reference,
        transformed,
        source_ids: tuple[str, ...],
    ) -> None:
        swaps: set[int] = set()
        for source_id in source_ids:
            reference_phase = reference.m3_sublattice_phase[
                reference.index_for_source_id(source_id)
            ]
            transformed_phase = transformed.m3_sublattice_phase[
                transformed.index_for_source_id(source_id)
            ]
            self.assertIsNotNone(reference_phase)
            self.assertIsNotNone(transformed_phase)
            swaps.add(reference_phase ^ transformed_phase)
        self.assertEqual(len(swaps), 1)


if __name__ == "__main__":
    unittest.main()
