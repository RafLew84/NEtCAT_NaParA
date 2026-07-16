import math
import unittest

import numpy as np

from moltrack.analysis import (
    FirstShellGraph,
    MolecularM6OrientationAnalysisSettings,
    build_first_shell_graph,
    compute_local_sixfold_bond_order,
)


def _star_graph(
    angles_rad: tuple[float, ...],
    *,
    distances_nm: tuple[float, ...] | None = None,
    ambiguous_edges_ij: tuple[tuple[int, int], ...] = (),
) -> FirstShellGraph:
    point_count = len(angles_rad) + 1
    edges = tuple((0, index) for index in range(1, point_count))
    distances = distances_nm or (1.5,) * len(edges)
    degree = (len(edges),) + (1,) * len(edges)
    return FirstShellGraph(
        point_ids=tuple(f"point-{index}" for index in range(point_count)),
        point_count=point_count,
        edges_ij=edges,
        distances_nm=distances,
        angles_rad=angles_rad,
        degree=degree,
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
        ambiguous_edges_ij=ambiguous_edges_ij,
        delaunay_degeneracy_qc=bool(ambiguous_edges_ij),
    )


def _triangular_lattice(width: int, height: int) -> np.ndarray:
    return np.asarray(
        [
            (2.0 * (x + 0.5 * (y % 2)), math.sqrt(3.0) * y)
            for y in range(height)
            for x in range(width)
        ],
        dtype=np.float64,
    )


def _compute_local_sixfold_order(
    graph: FirstShellGraph,
    *,
    settings: MolecularM6OrientationAnalysisSettings | None = None,
    boundary_distances: tuple[float | None, ...] | None = None,
):
    return compute_local_sixfold_bond_order(
        graph,
        distance_to_valid_fov_boundary_nm=(
            boundary_distances
            if boundary_distances is not None
            else (10.0,) * graph.point_count
        ),
        settings=settings,
    )


class LocalSixfoldBondOrderComputationTests(unittest.TestCase):
    def test_computes_perfect_rotated_sixfold_order_and_local_bond_statistics(self) -> None:
        rotation_deg = 17.0
        angles = tuple(
            math.radians(rotation_deg + 60.0 * index)
            for index in range(6)
        )
        distances = (1.2, 1.4, 1.5, 1.7, 1.8, 2.0)

        result = _compute_local_sixfold_order(_star_graph(angles, distances_nm=distances))

        self.assertEqual(result.computation_status[0], "valid_order")
        self.assertAlmostEqual(result.psi6[0].real, math.cos(math.radians(6.0 * rotation_deg)))
        self.assertAlmostEqual(result.psi6[0].imag, math.sin(math.radians(6.0 * rotation_deg)))
        self.assertAlmostEqual(result.q6[0], 1.0)
        self.assertAlmostEqual(result.lattice_orientation_deg[0], rotation_deg)
        self.assertEqual(result.orientation_status[0], "defined")
        self.assertAlmostEqual(result.local_median_bond_length_nm[0], 1.6)
        self.assertAlmostEqual(result.local_bond_length_mad_nm[0], 0.2)
        self.assertAlmostEqual(result.local_bond_length_iqr_nm[0], 0.35)
        self.assertAlmostEqual(
            result.local_bond_length_robust_cv[0],
            1.4826 * 0.2 / 1.6,
        )

    def test_uses_both_directions_of_each_physical_edge(self) -> None:
        graph = FirstShellGraph(
            point_ids=("a", "b", "c"),
            point_count=3,
            edges_ij=((0, 1), (0, 2), (1, 2)),
            distances_nm=(1.2, 1.3, 1.4),
            angles_rad=(0.1, 1.1, 2.1),
            degree=(2, 2, 2),
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
        settings = MolecularM6OrientationAnalysisSettings(min_neighbors_for_local_order=2)

        result = _compute_local_sixfold_order(graph, settings=settings)

        for point_index in range(3):
            directed_angles = tuple(
                graph.directed_angle_rad(point_index, neighbor)
                for neighbor in graph.neighbors_for_point(point_index)
            )
            expected = sum(
                np.exp(6j * angle) for angle in directed_angles
            ) / len(directed_angles)
            self.assertAlmostEqual(result.psi6[point_index].real, expected.real)
            self.assertAlmostEqual(result.psi6[point_index].imag, expected.imag)

    def test_excludes_builder_identified_ambiguous_edge_from_order(self) -> None:
        points = np.asarray(((0.0, 0.0), (1.5, 0.0), (1.5, 1.5), (0.0, 1.5)))
        graph = build_first_shell_graph(
            points,
            point_ids=("south-west", "south-east", "north-east", "north-west"),
        )

        result = _compute_local_sixfold_order(graph)

        self.assertEqual(len(graph.ambiguous_edges_ij), 1)
        self.assertEqual(graph.degree, (2, 2, 2, 2))
        self.assertEqual(result.neighbor_count, (2, 2, 2, 2))
        self.assertEqual(result.computation_status, ("insufficient_neighbors",) * 4)
        self.assertEqual(result.psi6, (None,) * 4)

    def test_keeps_valid_order_for_edge_truncated_point(self) -> None:
        graph = _star_graph((0.0, math.pi / 3.0, 2.0 * math.pi / 3.0))

        result = _compute_local_sixfold_order(
            graph,
            boundary_distances=(1.0, 10.0, 10.0, 10.0),
        )

        self.assertEqual(result.neighbor_count[0], 3)
        self.assertAlmostEqual(result.q6[0], 1.0)
        self.assertTrue(result.edge_truncated_neighborhood[0])
        self.assertEqual(result.computation_status[0], "valid_order")

    def test_leaves_points_with_too_few_neighbors_without_order(self) -> None:
        result = _compute_local_sixfold_order(_star_graph((0.0,)))

        self.assertEqual(result.neighbor_count, (1, 1))
        self.assertEqual(result.computation_status, ("insufficient_neighbors",) * 2)
        self.assertEqual(result.psi6, (None, None))
        self.assertEqual(result.q6, (None, None))
        self.assertEqual(result.local_median_bond_length_nm, (1.5, 1.5))
        self.assertEqual(result.local_bond_length_mad_nm, (0.0, 0.0))

    def test_preserves_duplicate_and_invalid_position_statuses(self) -> None:
        points = np.asarray(
            ((0.0, 0.0), (0.2, 0.0), (1.5, 0.0), (-0.75, 1.3), (-0.75, -1.3))
        )
        graph = build_first_shell_graph(
            points,
            point_ids=("representative", "duplicate", "east", "north-west", "south-west"),
            detection_confidences=(1.0, 0.1, 1.0, 1.0, 1.0),
        )

        result = _compute_local_sixfold_order(graph)
        duplicate_index = graph.physical_duplicate_qc.index(True)

        self.assertEqual(result.computation_status[duplicate_index], "duplicate_excluded")
        self.assertIsNone(result.psi6[duplicate_index])
        self.assertTrue(result.physical_duplicate_qc[duplicate_index])

        invalid = _compute_local_sixfold_order(
            _star_graph(()),
            boundary_distances=(None,),
        )
        self.assertEqual(invalid.computation_status, ("invalid_position",))
        self.assertEqual(invalid.orientation_status, ("not_available",))
        self.assertEqual(invalid.edge_truncated_neighborhood, (False,))

    def test_applies_orientation_zero_tolerance_below_on_and_above_threshold(self) -> None:
        graph = _star_graph((0.0, 0.0, 0.0, math.pi / 6.0))
        raw = _compute_local_sixfold_order(
            graph,
            settings=MolecularM6OrientationAnalysisSettings(orientation_zero_tolerance=0.0),
        )
        q6 = raw.q6[0]
        self.assertGreater(q6, 0.0)

        below = _compute_local_sixfold_order(
            graph,
            settings=MolecularM6OrientationAnalysisSettings(
                orientation_zero_tolerance=np.nextafter(q6, 0.0),
            ),
        )
        on = _compute_local_sixfold_order(
            graph,
            settings=MolecularM6OrientationAnalysisSettings(
                orientation_zero_tolerance=q6,
            ),
        )
        above = _compute_local_sixfold_order(
            graph,
            settings=MolecularM6OrientationAnalysisSettings(
                orientation_zero_tolerance=np.nextafter(q6, math.inf),
            ),
        )

        self.assertEqual(below.orientation_status[0], "defined")
        for result in (on, above):
            self.assertEqual(result.orientation_status[0], "undefined_zero_magnitude")
            self.assertIsNone(result.lattice_orientation_deg[0])
            self.assertEqual(result.q6[0], q6)

    def test_exactly_cancelling_phases_have_zero_order_and_undefined_orientation(self) -> None:
        result = _compute_local_sixfold_order(
            _star_graph((0.0, math.pi / 6.0, 0.0, math.pi / 6.0))
        )

        self.assertAlmostEqual(result.q6[0], 0.0)
        self.assertEqual(result.orientation_status[0], "undefined_zero_magnitude")
        self.assertIsNone(result.lattice_orientation_deg[0])

    def test_tiny_opposite_signed_residuals_do_not_create_orientation(self) -> None:
        tolerance = 1e-8
        settings = MolecularM6OrientationAnalysisSettings(
            orientation_zero_tolerance=tolerance,
        )
        positive = _compute_local_sixfold_order(
            _star_graph((0.0, math.pi / 6.0 + 1e-10, 0.0, math.pi / 6.0)),
            settings=settings,
        )
        negative = _compute_local_sixfold_order(
            _star_graph((0.0, math.pi / 6.0 - 1e-10, 0.0, math.pi / 6.0)),
            settings=settings,
        )

        for result in (positive, negative):
            self.assertLessEqual(result.q6[0], tolerance)
            self.assertEqual(result.orientation_status[0], "undefined_zero_magnitude")
            self.assertIsNone(result.lattice_orientation_deg[0])

    def test_perturbed_and_random_bonds_have_lower_order_than_a_perfect_shell(self) -> None:
        perfect = _compute_local_sixfold_order(
            _star_graph(tuple(index * math.pi / 3.0 for index in range(6)))
        )
        perturbed = _compute_local_sixfold_order(
            _star_graph((0.0, 0.9, 2.2, 3.0, 4.4, 5.0))
        )
        random = _compute_local_sixfold_order(
            _star_graph((0.13, 0.41, 1.72, 2.05, 4.33, 5.71))
        )

        self.assertAlmostEqual(perfect.q6[0], 1.0)
        self.assertLess(perturbed.q6[0], perfect.q6[0])
        self.assertLess(random.q6[0], perfect.q6[0])

    def test_triangular_lattice_degrades_for_perturbations_and_random_points(self) -> None:
        lattice = _triangular_lattice(10, 10)
        point_ids = tuple(f"molecule-{index}" for index in range(len(lattice)))
        settings = MolecularM6OrientationAnalysisSettings(
            first_shell_r_min_nm=1.2,
            first_shell_r_max_nm=2.5,
        )
        generator = np.random.default_rng(123)
        point_sets = (
            lattice,
            lattice + generator.normal(0.0, 0.18, lattice.shape),
            generator.uniform((0.0, 0.0), (19.0, 16.0), lattice.shape),
        )

        median_q6: list[float] = []
        for points in point_sets:
            graph = build_first_shell_graph(
                points,
                point_ids=point_ids,
                settings=settings,
            )
            result = _compute_local_sixfold_order(graph, settings=settings)
            median_q6.append(float(np.median([value for value in result.q6 if value is not None])))

        self.assertGreater(median_q6[0], median_q6[1])
        self.assertGreater(median_q6[1], median_q6[2])

    def test_is_invariant_to_translation_and_permutation_and_covariant_to_rotation(self) -> None:
        points = _triangular_lattice(5, 4)
        point_ids = tuple(f"molecule-{index}" for index in range(len(points)))
        settings = MolecularM6OrientationAnalysisSettings(
            first_shell_r_min_nm=1.5,
            first_shell_r_max_nm=2.2,
        )

        def result_for(values: np.ndarray, ids: tuple[str, ...]):
            graph = build_first_shell_graph(
                values,
                point_ids=ids,
                settings=settings,
            )
            return _compute_local_sixfold_order(graph, settings=settings)

        reference = result_for(points, point_ids)
        translated = result_for(points + np.asarray((13.0, -7.0)), point_ids)
        permutation = np.asarray(tuple(reversed(range(len(points)))), dtype=np.int64)
        permuted = result_for(points[permutation], tuple(point_ids[index] for index in permutation))
        rotation_deg = 13.0
        rotation_rad = math.radians(rotation_deg)
        rotation = np.asarray(
            (
                (math.cos(rotation_rad), -math.sin(rotation_rad)),
                (math.sin(rotation_rad), math.cos(rotation_rad)),
            )
        )
        rotated = result_for(points @ rotation.T, point_ids)

        for source_id in point_ids:
            reference_index = reference.index_for_source_id(source_id)
            translated_index = translated.index_for_source_id(source_id)
            permuted_index = permuted.index_for_source_id(source_id)
            rotated_index = rotated.index_for_source_id(source_id)
            self.assertEqual(
                translated.computation_status[translated_index],
                reference.computation_status[reference_index],
            )
            self.assertEqual(
                permuted.computation_status[permuted_index],
                reference.computation_status[reference_index],
            )
            reference_psi6 = reference.psi6[reference_index]
            if reference_psi6 is None:
                continue
            self.assertAlmostEqual(
                translated.psi6[translated_index].real,
                reference_psi6.real,
            )
            self.assertAlmostEqual(
                translated.psi6[translated_index].imag,
                reference_psi6.imag,
            )
            self.assertAlmostEqual(
                permuted.psi6[permuted_index].real,
                reference_psi6.real,
            )
            self.assertAlmostEqual(
                permuted.psi6[permuted_index].imag,
                reference_psi6.imag,
            )
            self.assertAlmostEqual(
                translated.q6[translated_index],
                reference.q6[reference_index],
            )
            self.assertAlmostEqual(
                permuted.q6[permuted_index],
                reference.q6[reference_index],
            )
            self.assertAlmostEqual(
                rotated.q6[rotated_index],
                reference.q6[reference_index],
            )
            rotation_phase = np.exp(6j * rotation_rad)
            expected_rotated_psi6 = reference_psi6 * rotation_phase
            self.assertAlmostEqual(
                rotated.psi6[rotated_index].real,
                expected_rotated_psi6.real,
            )
            self.assertAlmostEqual(
                rotated.psi6[rotated_index].imag,
                expected_rotated_psi6.imag,
            )
            if reference.lattice_orientation_deg[reference_index] is not None:
                self.assertAlmostEqual(
                    (
                        translated.lattice_orientation_deg[translated_index]
                        - reference.lattice_orientation_deg[reference_index]
                        + 30.0
                    )
                    % 60.0
                    - 30.0,
                    0.0,
                )
                self.assertAlmostEqual(
                    (
                        permuted.lattice_orientation_deg[permuted_index]
                        - reference.lattice_orientation_deg[reference_index]
                        + 30.0
                    )
                    % 60.0
                    - 30.0,
                    0.0,
                )
                expected_orientation = (
                    reference.lattice_orientation_deg[reference_index] + rotation_deg
                ) % 60.0
                self.assertAlmostEqual(
                    (
                        rotated.lattice_orientation_deg[rotated_index]
                        - expected_orientation
                        + 30.0
                    )
                    % 60.0
                    - 30.0,
                    0.0,
                )

        rotated_valid_q6 = [value for value in rotated.q6 if value is not None]
        self.assertGreater(float(np.median(rotated_valid_q6)), 0.99)

    def test_validates_graph_settings_and_boundary_distance_contract(self) -> None:
        graph = _star_graph((0.0, math.pi / 3.0, 2.0 * math.pi / 3.0))

        with self.assertRaisesRegex(TypeError, "first_shell_graph"):
            compute_local_sixfold_bond_order(
                object(),
                distance_to_valid_fov_boundary_nm=(),
            )
        with self.assertRaisesRegex(ValueError, "distance_to_valid_fov_boundary_nm"):
            compute_local_sixfold_bond_order(
                graph,
                distance_to_valid_fov_boundary_nm=(10.0,),
            )
        with self.assertRaisesRegex(ValueError, "settings"):
            _compute_local_sixfold_order(
                graph,
                settings=MolecularM6OrientationAnalysisSettings(first_shell_r_max_nm=2.7),
            )


if __name__ == "__main__":
    unittest.main()
