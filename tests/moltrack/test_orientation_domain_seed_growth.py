import cmath
import math
import unittest
from dataclasses import replace
from unittest.mock import patch

import numpy as np

from moltrack.analysis import (
    FirstShellGraph,
    LocalSixfoldBondOrderField,
    MolecularM6OrientationAnalysisSettings,
    detect_m6_orientation_domain_seeds,
    grow_m6_orientation_domains,
)
from moltrack.analysis._coordinate_fingerprint import point_coordinate_fingerprint


def _settings(**overrides: object) -> MolecularM6OrientationAnalysisSettings:
    payload: dict[str, object] = {
        "min_neighbors_for_local_order": 1,
        "min_neighbors_for_seed": 1,
        "min_ordered_component_size": 1,
        "min_seed_size": 2,
        "min_domain_size": 4,
        "q_seed": 0.7,
        "q_grow": 0.3,
        "seed_angle_tolerance_deg": 4.0,
        "grow_angle_tolerance_deg": 8.0,
        "domain_conflict_margin": 0.05,
    }
    payload.update(overrides)
    return MolecularM6OrientationAnalysisSettings(**payload)


def _analysis_inputs(
    *,
    orientations_deg: tuple[float, ...],
    edges_ij: tuple[tuple[int, int], ...],
    settings: MolecularM6OrientationAnalysisSettings,
    q6: tuple[float, ...] | None = None,
    point_ids: tuple[str, ...] | None = None,
    points_xy_nm: np.ndarray | None = None,
    edge_truncated: tuple[bool, ...] | None = None,
    undefined_orientation: tuple[bool, ...] | None = None,
) -> tuple[np.ndarray, FirstShellGraph, LocalSixfoldBondOrderField]:
    point_count = len(orientations_deg)
    ids = point_ids or tuple(f"p{index:02d}" for index in range(point_count))
    points = np.asarray(
        points_xy_nm
        if points_xy_nm is not None
        else tuple((float(index), float(index % 3)) for index in range(point_count)),
        dtype=np.float64,
    )
    magnitudes = q6 or (0.9,) * point_count
    edge_flags = edge_truncated or (False,) * point_count
    undefined = undefined_orientation or (False,) * point_count
    degree = [0] * point_count
    for left, right in edges_ij:
        degree[left] += 1
        degree[right] += 1
    if any(value == 0 for value in degree):
        raise ValueError("Test fixture points must have at least one graph neighbor.")

    graph = FirstShellGraph(
        point_ids=ids,
        point_count=point_count,
        edges_ij=edges_ij,
        distances_nm=(1.5,) * len(edges_ij),
        angles_rad=(0.0,) * len(edges_ij),
        degree=tuple(degree),
        geometry_collision_epsilon_nm=1e-12,
        duplicate_max_distance_nm=settings.duplicate_max_distance_nm,
        first_shell_r_min_nm=settings.first_shell_r_min_nm,
        first_shell_r_max_nm=settings.first_shell_r_max_nm,
        coordinate_frame="sample_nm",
        orientation_reference="+x_sample_axis",
        spatial_calibration_fingerprint="calibration-v1",
        registration_fingerprint="registration-v1",
        point_coordinate_fingerprint=point_coordinate_fingerprint(points, ids),
        construction_method="delaunay_first_shell",
        qc_status="valid",
        duplicate_detection_enabled=settings.duplicate_detection_enabled,
    )

    psi6: list[complex] = []
    orientations: list[float | None] = []
    orientation_status: list[str] = []
    normalized_q6: list[float] = []
    for angle, magnitude, is_undefined in zip(orientations_deg, magnitudes, undefined):
        if is_undefined:
            psi6.append(0j)
            normalized_q6.append(0.0)
            orientations.append(None)
            orientation_status.append("undefined_zero_magnitude")
        else:
            psi6.append(magnitude * cmath.exp(6j * math.radians(angle)))
            normalized_q6.append(magnitude)
            orientations.append(angle)
            orientation_status.append("defined")
    boundary_distances = tuple(1.0 if flag else 10.0 for flag in edge_flags)
    local_order = LocalSixfoldBondOrderField(
        source_ids=ids,
        point_count=point_count,
        psi6=tuple(psi6),
        q6=tuple(normalized_q6),
        lattice_orientation_deg=tuple(orientations),
        orientation_status=tuple(orientation_status),
        neighbor_count=tuple(degree),
        computation_status=("valid_order",) * point_count,
        local_median_bond_length_nm=(1.5,) * point_count,
        local_bond_length_mad_nm=(0.0,) * point_count,
        local_bond_length_iqr_nm=(0.0,) * point_count,
        local_bond_length_robust_cv=(0.0,) * point_count,
        physical_duplicate_qc=(False,) * point_count,
        geometry_duplicate_qc=(False,) * point_count,
        edge_truncated_neighborhood=edge_flags,
        distance_to_valid_fov_boundary_nm=boundary_distances,
        first_shell_r_max_nm=settings.first_shell_r_max_nm,
        coordinate_frame="sample_nm",
        orientation_reference="+x_sample_axis",
        spatial_calibration_fingerprint="calibration-v1",
        registration_fingerprint="registration-v1",
        min_neighbors_for_local_order=settings.min_neighbors_for_local_order,
    )
    return points, graph, local_order


def _detect(
    inputs: tuple[np.ndarray, FirstShellGraph, LocalSixfoldBondOrderField],
    settings: MolecularM6OrientationAnalysisSettings,
):
    points, graph, local_order = inputs
    return detect_m6_orientation_domain_seeds(
        points,
        first_shell_graph=graph,
        local_order=local_order,
        settings=settings,
    )


def _clique_edges(start: int, size: int) -> tuple[tuple[int, int], ...]:
    return tuple(
        (left, right)
        for left in range(start, start + size)
        for right in range(left + 1, start + size)
    )


class OrientationDomainSeedDetectionTests(unittest.TestCase):
    def test_connects_wraparound_orientations_but_splits_angles_outside_tolerance(self) -> None:
        settings = _settings(min_seed_size=1)
        inputs = _analysis_inputs(
            orientations_deg=(59.0, 1.0, 10.0, 11.0),
            edges_ij=((0, 1), (1, 2), (2, 3)),
            settings=settings,
        )

        result = _detect(inputs, settings)

        self.assertEqual(result.ordered_component_id, (0, 0, 1, 1))
        self.assertEqual(result.component_type, ("growth_seed",) * 4)
        self.assertAlmostEqual(result.components[0].orientation_deg, 0.0)
        self.assertAlmostEqual(result.components[1].orientation_deg, 10.5)

    def test_same_orientation_without_first_shell_edge_stays_spatially_separate(self) -> None:
        settings = _settings(min_seed_size=1)
        result = _detect(
            _analysis_inputs(
                orientations_deg=(3.0, 3.0, 3.0, 3.0),
                edges_ij=((0, 1), (2, 3)),
                settings=settings,
            ),
            settings,
        )

        self.assertEqual(result.ordered_component_count, 2)
        self.assertNotEqual(result.ordered_component_id[0], result.ordered_component_id[2])

    def test_classifies_components_around_all_three_size_thresholds(self) -> None:
        settings = _settings(
            min_ordered_component_size=2,
            min_seed_size=3,
            min_domain_size=4,
        )
        edges = (
            ((0, 1),)
            + _clique_edges(1, 2)
            + _clique_edges(3, 3)
            + _clique_edges(6, 4)
        )
        result = _detect(
            _analysis_inputs(
                orientations_deg=(30.0,) + (0.0,) * 9,
                edges_ij=edges,
                settings=settings,
                points_xy_nm=np.asarray(
                    ((-10.0, 0.0), (0.0, 0.0), (1.0, 0.0))
                    + tuple((10.0 + index, 0.0) for index in range(3))
                    + tuple((20.0 + index, 0.0) for index in range(4))
                ),
            ),
            settings,
        )

        self.assertEqual(result.ordered_component_id[0], -1)
        self.assertEqual(result.assignment_status[0], "boundary_or_disordered")
        self.assertEqual(result.ordered_component_id[1:3], (2, 2))
        self.assertEqual(result.component_type[1:3], ("small_ordered_island",) * 2)
        self.assertFalse(result.components[2].can_initiate_growth)
        self.assertEqual(result.ordered_component_id[3:6], (1, 1, 1))
        self.assertEqual(result.ordered_component_id[6:10], (0, 0, 0, 0))
        self.assertTrue(result.components[0].can_initiate_growth)
        self.assertTrue(result.components[1].can_initiate_growth)
        self.assertEqual(result.components[0].component_type, "growth_seed")

    def test_requires_five_neighbors_defined_orientation_and_non_edge_qc(self) -> None:
        settings = _settings(
            min_neighbors_for_seed=5,
            min_ordered_component_size=1,
            min_seed_size=1,
            min_domain_size=1,
        )
        edges = _clique_edges(0, 5) + _clique_edges(5, 6)
        result = _detect(
            _analysis_inputs(
                orientations_deg=(0.0,) * 11,
                edges_ij=edges,
                settings=settings,
                edge_truncated=(False,) * 10 + (True,),
                undefined_orientation=(False,) * 9 + (True, False),
            ),
            settings,
        )

        self.assertEqual(result.seed_eligible[:5], (False,) * 5)
        self.assertEqual(result.seed_eligible[5:9], (True,) * 4)
        self.assertFalse(result.seed_eligible[9])
        self.assertFalse(result.seed_eligible[10])
        self.assertEqual(result.ordered_component_id[:5], (-1,) * 5)
        self.assertEqual(result.ordered_component_id[5:9], (0,) * 4)

    def test_seed_detection_rejects_mismatched_analysis_inputs(self) -> None:
        settings = _settings(min_seed_size=1)
        points, graph, local_order = _analysis_inputs(
            orientations_deg=(0.0, 0.0),
            edges_ij=((0, 1),),
            settings=settings,
        )

        with self.assertRaisesRegex(ValueError, "coordinate fingerprint"):
            detect_m6_orientation_domain_seeds(
                points + 1.0,
                first_shell_graph=graph,
                local_order=local_order,
                settings=settings,
            )


class OrientationDomainGrowthTests(unittest.TestCase):
    def test_grows_in_synchronous_layers_and_accepts_edge_truncated_candidate(self) -> None:
        settings = _settings()
        inputs = _analysis_inputs(
            orientations_deg=(0.0, 0.0, 1.0, 1.0),
            q6=(0.9, 0.9, 0.5, 0.5),
            edges_ij=((0, 1), (1, 2), (2, 3)),
            settings=settings,
            edge_truncated=(False, False, False, True),
        )
        seeds = _detect(inputs, settings)

        result = grow_m6_orientation_domains(
            inputs[0],
            first_shell_graph=inputs[1],
            local_order=inputs[2],
            seeds=seeds,
            settings=settings,
        )

        self.assertEqual(seeds.ordered_component_id, (0, 0, -1, -1))
        self.assertEqual(result.ordered_component_id, (0, 0, 0, 0))
        self.assertEqual(result.growth_iteration_count, 2)
        self.assertTrue(result.edge_truncated_neighborhood[3])
        self.assertEqual(result.assignment_status[3], "assigned")

    def test_conflict_margin_keeps_ambiguous_boundary_unassigned(self) -> None:
        settings = _settings(seed_angle_tolerance_deg=2.0, grow_angle_tolerance_deg=8.0)
        inputs = _analysis_inputs(
            orientations_deg=(0.0, 0.0, 10.0, 10.0, 5.0, 3.0),
            q6=(0.9, 0.9, 0.9, 0.9, 0.5, 0.5),
            edges_ij=((0, 1), (2, 3), (1, 4), (2, 4), (1, 5), (2, 5)),
            settings=settings,
        )
        seeds = _detect(inputs, settings)

        result = grow_m6_orientation_domains(
            inputs[0],
            first_shell_graph=inputs[1],
            local_order=inputs[2],
            seeds=seeds,
            settings=settings,
        )

        self.assertEqual(result.assignment_status[4], "boundary_or_disordered")
        self.assertEqual(result.ordered_component_id[4], -1)
        self.assertEqual(result.ordered_component_id[5], 0)

    def test_three_domain_conflict_does_not_use_domain_iteration_order(self) -> None:
        settings = _settings(
            seed_angle_tolerance_deg=2.0,
            grow_angle_tolerance_deg=30.0,
        )
        inputs = _analysis_inputs(
            orientations_deg=(0.0, 0.0, 20.0, 20.0, 40.0, 40.0, 10.0),
            q6=(0.9, 0.9, 0.9, 0.9, 0.9, 0.9, 0.5),
            edges_ij=(
                (0, 1),
                (2, 3),
                (4, 5),
                (1, 6),
                (3, 6),
                (5, 6),
            ),
            settings=settings,
        )
        seeds = _detect(inputs, settings)

        result = grow_m6_orientation_domains(
            inputs[0],
            first_shell_graph=inputs[1],
            local_order=inputs[2],
            seeds=seeds,
            settings=settings,
        )
        with patch(
            "moltrack.analysis.orientation_domain_seed_growth._growth_seed_components",
            return_value=tuple(
                component
                for component in reversed(seeds.components)
                if component.can_initiate_growth
            ),
        ):
            reversed_domain_order = grow_m6_orientation_domains(
                inputs[0],
                first_shell_graph=inputs[1],
                local_order=inputs[2],
                seeds=seeds,
                settings=settings,
            )

        self.assertEqual(seeds.growth_seed_count, 3)
        self.assertEqual(result.ordered_component_id[6], -1)
        self.assertEqual(result.assignment_status[6], "boundary_or_disordered")
        self.assertEqual(reversed_domain_order, result)

    def test_conflict_margin_uses_second_neighbor_even_below_growth_tolerance(self) -> None:
        settings = _settings(
            seed_angle_tolerance_deg=2.0,
            grow_angle_tolerance_deg=8.0,
            domain_conflict_margin=0.45,
        )
        inputs = _analysis_inputs(
            orientations_deg=(0.0, 0.0, 9.0, 9.0, 0.0),
            q6=(0.9, 0.9, 0.9, 0.9, 0.5),
            edges_ij=((0, 1), (2, 3), (1, 4), (3, 4)),
            settings=settings,
        )
        seeds = _detect(inputs, settings)

        result = grow_m6_orientation_domains(
            inputs[0],
            first_shell_graph=inputs[1],
            local_order=inputs[2],
            seeds=seeds,
            settings=settings,
        )

        self.assertEqual(result.ordered_component_id[4], -1)
        self.assertEqual(result.assignment_status[4], "boundary_or_disordered")

    def test_exactly_cancelling_seed_orientation_uses_deterministic_medoid(self) -> None:
        settings = _settings(
            seed_angle_tolerance_deg=30.0,
            grow_angle_tolerance_deg=30.0,
        )
        inputs = _analysis_inputs(
            orientations_deg=(0.0, 30.0, 0.0),
            q6=(0.9, 0.9, 0.5),
            edges_ij=((0, 1), (0, 2)),
            settings=settings,
        )
        seeds = _detect(inputs, settings)

        result = grow_m6_orientation_domains(
            inputs[0],
            first_shell_graph=inputs[1],
            local_order=inputs[2],
            seeds=seeds,
            settings=settings,
        )

        self.assertAlmostEqual(seeds.components[0].orientation_deg, 0.0)
        self.assertEqual(result.ordered_component_id, (0, 0, 0))

    def test_growth_result_rejects_inconsistent_parallel_labels(self) -> None:
        settings = _settings()
        inputs = _analysis_inputs(
            orientations_deg=(0.0, 0.0, 1.0),
            q6=(0.9, 0.9, 0.5),
            edges_ij=((0, 1), (1, 2)),
            settings=settings,
        )
        result = grow_m6_orientation_domains(
            inputs[0],
            first_shell_graph=inputs[1],
            local_order=inputs[2],
            seeds=_detect(inputs, settings),
            settings=settings,
        )

        with self.assertRaisesRegex(ValueError, "ordered_component_id"):
            replace(result, ordered_component_id=())
        with self.assertRaisesRegex(ValueError, "retain every seed"):
            replace(result.components[0], point_indices=(1, 2), source_ids=("p01", "p02"))

    def test_growth_is_invariant_to_point_and_edge_order(self) -> None:
        settings = _settings()
        ids = ("a", "b", "c", "d")
        points = np.asarray(((0.0, 0.0), (1.0, 0.0), (2.0, 0.0), (3.0, 0.0)))
        original = _analysis_inputs(
            orientations_deg=(0.0, 0.0, 1.0, 1.0),
            q6=(0.9, 0.9, 0.5, 0.5),
            edges_ij=((0, 1), (1, 2), (2, 3)),
            settings=settings,
            point_ids=ids,
            points_xy_nm=points,
        )
        permutation = (3, 2, 1, 0)
        old_to_new = {old: new for new, old in enumerate(permutation)}
        permuted = _analysis_inputs(
            orientations_deg=tuple((0.0, 0.0, 1.0, 1.0)[index] for index in permutation),
            q6=tuple((0.9, 0.9, 0.5, 0.5)[index] for index in permutation),
            edges_ij=tuple(
                sorted((old_to_new[left], old_to_new[right]))
                for left, right in reversed(((0, 1), (1, 2), (2, 3)))
            ),
            settings=settings,
            point_ids=tuple(ids[index] for index in permutation),
            points_xy_nm=points[np.asarray(permutation)],
        )

        def assignments(inputs):
            seeds = _detect(inputs, settings)
            grown = grow_m6_orientation_domains(
                inputs[0],
                first_shell_graph=inputs[1],
                local_order=inputs[2],
                seeds=seeds,
                settings=settings,
            )
            return dict(zip(grown.source_ids, grown.ordered_component_id))

        self.assertEqual(assignments(original), assignments(permuted))


if __name__ == "__main__":
    unittest.main()
