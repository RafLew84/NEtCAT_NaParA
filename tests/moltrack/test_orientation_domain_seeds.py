import math
import unittest
from dataclasses import replace
from itertools import combinations

import numpy as np

from moltrack.analysis import (
    FirstShellGraph,
    LocalSixfoldBondOrderField,
    MolecularM6OrientationAnalysisSettings,
    build_first_shell_graph,
    compute_local_sixfold_bond_order,
    detect_m6_orientation_domain_seeds,
)
from moltrack.analysis._coordinate_fingerprint import point_coordinate_fingerprint


def _settings(**overrides: object) -> MolecularM6OrientationAnalysisSettings:
    payload: dict[str, object] = {
        "min_neighbors_for_local_order": 1,
        "min_neighbors_for_seed": 1,
        "min_ordered_component_size": 2,
        "min_seed_size": 3,
        "min_domain_size": 4,
        "q_seed": 0.65,
        "seed_angle_tolerance_deg": 8.0,
    }
    payload.update(overrides)
    return MolecularM6OrientationAnalysisSettings(**payload)


def _complete_graph_edges(indices: tuple[int, ...]) -> tuple[tuple[int, int], ...]:
    return tuple(combinations(indices, 2))


def _inputs(
    *,
    edges: tuple[tuple[int, int], ...],
    orientations_deg: tuple[float | None, ...],
    q6: tuple[float, ...] | None = None,
    edge_truncated: tuple[bool, ...] | None = None,
    source_ids: tuple[str, ...] | None = None,
    settings: MolecularM6OrientationAnalysisSettings | None = None,
) -> tuple[np.ndarray, FirstShellGraph, LocalSixfoldBondOrderField]:
    settings = settings or _settings()
    point_count = len(orientations_deg)
    source_ids = source_ids or tuple(f"point-{index}" for index in range(point_count))
    points = np.asarray(
        tuple((float(index), float(index % 3)) for index in range(point_count)),
        dtype=np.float64,
    )
    degree = [0] * point_count
    for left, right in edges:
        degree[left] += 1
        degree[right] += 1
    graph = FirstShellGraph(
        point_ids=source_ids,
        point_count=point_count,
        edges_ij=edges,
        distances_nm=(1.5,) * len(edges),
        angles_rad=(0.0,) * len(edges),
        degree=tuple(degree),
        geometry_collision_epsilon_nm=1e-12,
        duplicate_max_distance_nm=settings.duplicate_max_distance_nm,
        first_shell_r_min_nm=settings.first_shell_r_min_nm,
        first_shell_r_max_nm=settings.first_shell_r_max_nm,
        coordinate_frame="sample_nm",
        orientation_reference="+x_sample_axis",
        spatial_calibration_fingerprint="calibration-v1",
        registration_fingerprint="registration-v1",
        point_coordinate_fingerprint=point_coordinate_fingerprint(points, source_ids),
        construction_method="delaunay_first_shell",
        qc_status="valid",
    )
    q_values = q6 or tuple(0.9 if value is not None else 0.0 for value in orientations_deg)
    boundary_flags = edge_truncated or (False,) * point_count
    boundary_distances = tuple(
        1.0 if flag else 10.0 for flag in boundary_flags
    )
    psi6 = tuple(
        0j
        if orientation is None
        else magnitude * complex(
            math.cos(math.radians(6.0 * orientation)),
            math.sin(math.radians(6.0 * orientation)),
        )
        for orientation, magnitude in zip(orientations_deg, q_values)
    )
    field = LocalSixfoldBondOrderField(
        source_ids=source_ids,
        point_count=point_count,
        psi6=psi6,
        q6=q_values,
        lattice_orientation_deg=orientations_deg,
        orientation_status=tuple(
            "defined" if value is not None else "undefined_zero_magnitude"
            for value in orientations_deg
        ),
        neighbor_count=tuple(degree),
        computation_status=("valid_order",) * point_count,
        local_median_bond_length_nm=(1.5,) * point_count,
        local_bond_length_mad_nm=(0.0,) * point_count,
        local_bond_length_iqr_nm=(0.0,) * point_count,
        local_bond_length_robust_cv=(0.0,) * point_count,
        physical_duplicate_qc=(False,) * point_count,
        geometry_duplicate_qc=(False,) * point_count,
        edge_truncated_neighborhood=boundary_flags,
        distance_to_valid_fov_boundary_nm=boundary_distances,
        first_shell_r_max_nm=settings.first_shell_r_max_nm,
        coordinate_frame="sample_nm",
        orientation_reference="+x_sample_axis",
        spatial_calibration_fingerprint="calibration-v1",
        registration_fingerprint="registration-v1",
        min_neighbors_for_local_order=settings.min_neighbors_for_local_order,
    )
    return points, graph, field


class OrientationDomainSeedDetectionTests(unittest.TestCase):
    def test_connects_only_first_shell_neighbors_with_m6_compatible_orientation(self) -> None:
        settings = _settings(
            min_ordered_component_size=2,
            min_seed_size=2,
            min_domain_size=3,
            seed_angle_tolerance_deg=3.0,
        )
        points, graph, field = _inputs(
            edges=((0, 1), (2, 3), (4, 6), (5, 7)),
            orientations_deg=(59.0, 1.0, 0.0, 10.0, 25.0, 25.0, 25.0, 25.0),
            q6=(settings.q_seed, 0.9, 0.9, 0.9, 0.9, 0.9, 0.1, 0.1),
            settings=settings,
        )

        result = detect_m6_orientation_domain_seeds(
            points,
            first_shell_graph=graph,
            local_order=field,
            settings=settings,
        )

        self.assertEqual(result.ordered_component_count, 1)
        self.assertEqual(result.growth_seed_count, 1)
        self.assertEqual(result.components[0].source_ids, ("point-0", "point-1"))
        self.assertEqual(result.components[0].component_type, "growth_seed")
        self.assertTrue(result.components[0].can_initiate_growth)
        orientation = result.components[0].orientation_deg
        self.assertLess(min(orientation, 60.0 - orientation), 1.0)
        self.assertEqual(result.settings, settings)
        self.assertEqual(result.spatial_calibration_fingerprint, "calibration-v1")
        self.assertEqual(result.component_for_source_id("point-0"), result.components[0])
        self.assertIsNone(result.component_for_source_id("point-2"))
        self.assertEqual(result.ordered_component_id[0:2], (0, 0))
        self.assertEqual(result.ordered_component_id[2:], (-1,) * 6)

    def test_classifies_components_at_each_size_threshold_before_growth(self) -> None:
        settings = _settings()
        groups = ((0,), (1, 2), (3, 4, 5), (6, 7, 8, 9))
        edges = (
            (0, 10),
            (1, 2),
            (3, 4),
            (4, 5),
            (6, 7),
            (7, 8),
            (8, 9),
        )
        points, graph, field = _inputs(
            edges=edges,
            orientations_deg=(0.0,) * 11,
            q6=(0.9,) * 10 + (0.1,),
            settings=settings,
        )

        result = detect_m6_orientation_domain_seeds(
            points,
            first_shell_graph=graph,
            local_order=field,
            settings=settings,
        )

        self.assertEqual(
            tuple(component.molecule_count for component in result.components),
            (4, 3, 2),
        )
        self.assertEqual(
            tuple(component.component_type for component in result.components),
            ("growth_seed", "growth_seed", "small_ordered_island"),
        )
        self.assertEqual(result.ordered_component_id[groups[0][0]], -1)
        self.assertEqual(result.assignment_status[groups[0][0]], "boundary_or_disordered")
        self.assertEqual(tuple(result.ordered_component_id[index] for index in groups[1]), (2, 2))
        self.assertEqual(tuple(result.ordered_component_id[index] for index in groups[2]), (1, 1, 1))
        self.assertEqual(tuple(result.ordered_component_id[index] for index in groups[3]), (0, 0, 0, 0))
        self.assertEqual(result.growth_seed_count, 2)
        self.assertEqual(result.small_ordered_island_count, 1)
        self.assertEqual(result.components[0].component_type, "growth_seed")
        self.assertGreaterEqual(
            result.components[0].molecule_count,
            settings.min_domain_size,
        )

    def test_component_above_domain_size_is_still_a_growth_seed_before_final_sizing(self) -> None:
        settings = _settings()
        points, graph, field = _inputs(
            edges=((0, 1), (1, 2), (2, 3), (3, 4)),
            orientations_deg=(4.0,) * 5,
            settings=settings,
        )

        result = detect_m6_orientation_domain_seeds(
            points,
            first_shell_graph=graph,
            local_order=field,
            settings=settings,
        )

        self.assertGreater(result.components[0].molecule_count, settings.min_domain_size)
        self.assertEqual(result.components[0].component_type, "growth_seed")
        self.assertTrue(result.components[0].can_initiate_growth)

    def test_requires_five_neighbors_defined_orientation_and_interior_qc(self) -> None:
        settings = _settings(
            min_neighbors_for_seed=5,
            min_ordered_component_size=1,
            min_seed_size=1,
            min_domain_size=2,
        )
        k4 = (0, 1, 2, 3)
        k5 = (4, 5, 6, 7, 8)
        k6 = (9, 10, 11, 12, 13, 14)
        edges = (
            _complete_graph_edges(k4)
            + _complete_graph_edges(k5)
            + _complete_graph_edges(k6)
        )
        orientations = (0.0,) * 14 + (None,)
        edge_flags = (False,) * 9 + (True,) + (False,) * 5
        points, graph, field = _inputs(
            edges=edges,
            orientations_deg=orientations,
            edge_truncated=edge_flags,
            settings=settings,
        )

        result = detect_m6_orientation_domain_seeds(
            points,
            first_shell_graph=graph,
            local_order=field,
            settings=settings,
        )

        self.assertFalse(any(result.seed_eligible[index] for index in k4 + k5))
        self.assertTrue(all(result.seed_eligible[index] for index in (10, 11, 12, 13)))
        self.assertFalse(result.seed_eligible[9])
        self.assertFalse(result.seed_eligible[14])
        self.assertTrue(result.edge_truncated_neighborhood[9])
        self.assertEqual(result.assignment_status[9], "boundary_or_disordered")
        self.assertEqual(result.assignment_status[14], "boundary_or_disordered")
        self.assertEqual(result.components[0].point_indices, (10, 11, 12, 13))

    def test_keeps_rejected_physical_duplicate_out_of_seed_components(self) -> None:
        settings = _settings(
            min_ordered_component_size=1,
            min_seed_size=1,
            min_domain_size=1,
        )
        points = np.asarray(
            ((0.0, 0.0), (0.2, 0.0), (1.5, 0.0), (0.75, 1.3)),
            dtype=np.float64,
        )
        graph = build_first_shell_graph(
            points,
            point_ids=("representative", "duplicate", "east", "north"),
            settings=settings,
            detection_confidences=(1.0, 0.1, 1.0, 1.0),
            spatial_calibration_fingerprint="calibration-v1",
            registration_fingerprint="registration-v1",
        )
        field = compute_local_sixfold_bond_order(
            graph,
            distance_to_valid_fov_boundary_nm=(10.0,) * 4,
            settings=settings,
        )

        result = detect_m6_orientation_domain_seeds(
            points,
            first_shell_graph=graph,
            local_order=field,
            settings=settings,
        )
        duplicate_index = graph.physical_duplicate_qc.index(True)

        self.assertFalse(result.seed_eligible[duplicate_index])
        self.assertEqual(result.ordered_component_id[duplicate_index], -1)
        self.assertEqual(result.assignment_status[duplicate_index], "duplicate_excluded")
        self.assertTrue(result.physical_duplicate_qc[duplicate_index])

    def test_rejects_mismatched_graph_local_field_coordinates_and_settings(self) -> None:
        settings = _settings(min_ordered_component_size=1, min_seed_size=1, min_domain_size=1)
        points, graph, field = _inputs(
            edges=((0, 1),),
            orientations_deg=(0.0, 0.0),
            settings=settings,
        )

        with self.assertRaisesRegex(ValueError, "coordinate fingerprint"):
            detect_m6_orientation_domain_seeds(
                points + 1.0,
                first_shell_graph=graph,
                local_order=field,
                settings=settings,
            )
        with self.assertRaisesRegex(ValueError, "local_order"):
            detect_m6_orientation_domain_seeds(
                points,
                first_shell_graph=graph,
                local_order=field.__class__(
                    **{**field.__dict__, "source_ids": tuple(reversed(field.source_ids))}
                ),
                settings=settings,
            )
        with self.assertRaisesRegex(ValueError, "settings"):
            detect_m6_orientation_domain_seeds(
                points,
                first_shell_graph=graph,
                local_order=field,
                settings=_settings(
                    first_shell_r_max_nm=3.0,
                    min_ordered_component_size=1,
                    min_seed_size=1,
                    min_domain_size=1,
                ),
            )
        with self.assertRaisesRegex(ValueError, "blocking QC"):
            detect_m6_orientation_domain_seeds(
                points,
                first_shell_graph=replace(
                    graph,
                    construction_method="rank2_radius_fallback",
                    qc_status="blocking_rank2_radius_fallback",
                ),
                local_order=field,
                settings=settings,
            )


if __name__ == "__main__":
    unittest.main()
