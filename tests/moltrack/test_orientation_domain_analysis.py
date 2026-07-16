import math
import unittest
from dataclasses import replace

import numpy as np

from moltrack.analysis import (
    M6OrientationDomainAnalysis,
    MolecularM6OrientationAnalysisSettings,
    analyze_m6_orientation_domains,
)


def _triangular_patch(
    angle_deg: float,
    shift_xy_nm: tuple[float, float],
    *,
    width: int = 8,
    height: int = 8,
    spacing_nm: float = 2.0,
) -> np.ndarray:
    points = np.asarray(
        [
            (
                spacing_nm * (x + 0.5 * (y % 2)),
                spacing_nm * math.sqrt(3.0) * y / 2.0,
            )
            for y in range(height)
            for x in range(width)
        ],
        dtype=np.float64,
    )
    angle_rad = math.radians(angle_deg)
    rotation = np.asarray(
        (
            (math.cos(angle_rad), -math.sin(angle_rad)),
            (math.sin(angle_rad), math.cos(angle_rad)),
        )
    )
    return points @ rotation.T + np.asarray(shift_xy_nm)


def _settings() -> MolecularM6OrientationAnalysisSettings:
    return MolecularM6OrientationAnalysisSettings(
        first_shell_r_min_nm=1.5,
        first_shell_r_max_nm=2.3,
        min_ordered_component_size=3,
        min_seed_size=8,
        min_domain_size=15,
        q_seed=0.65,
        q_grow=0.25,
        seed_angle_tolerance_deg=6.0,
        grow_angle_tolerance_deg=12.0,
        domain_merge_angle_tolerance_deg=6.0,
    )


def _canonical_float(value: float | None) -> float | None:
    return None if value is None else round(value, 12)


def _canonical_orientation(value: float | None) -> float | None:
    if value is None:
        return None
    normalized = round(value % 60.0, 10)
    return 0.0 if normalized == 60.0 else normalized


def _canonical_result(result: M6OrientationDomainAnalysis) -> tuple[object, ...]:
    graph_edges = frozenset(
        frozenset(
            (
                result.first_shell_graph.point_ids[left],
                result.first_shell_graph.point_ids[right],
            )
        )
        for left, right in result.first_shell_graph.edges_ij
    )
    point_state = {
        source_id: (
            result.local_order.computation_status[index],
            result.local_order.orientation_status[index],
            _canonical_float(result.local_order.q6[index]),
            _canonical_orientation(result.local_order.lattice_orientation_deg[index]),
            result.segmentation.assignment_status[index],
            result.segmentation.component_type[index],
            (
                None
                if result.segmentation.component_for_source_id(source_id) is None
                else frozenset(
                    result.segmentation.component_for_source_id(source_id).source_ids
                )
            ),
        )
        for index, source_id in enumerate(result.first_shell_graph.point_ids)
    }
    components = {
        frozenset(component.source_ids): (
            component.ordered_component_id,
            component.m6_orientation_domain_id,
            component.component_type,
            component.molecule_count,
            _canonical_float(component.centroid_x_nm),
            _canonical_float(component.centroid_y_nm),
            _canonical_orientation(component.orientation_deg),
        )
        for component in result.segmentation.components
    }
    return graph_edges, point_state, components


class OrientationDomainAnalysisTests(unittest.TestCase):
    def test_two_rotated_triangular_domains_end_to_end_and_permuted(self) -> None:
        left = _triangular_patch(0.0, (0.0, 0.0))
        right = _triangular_patch(22.0, (22.0, 0.0))
        points = np.vstack((left, right))
        point_ids = tuple(
            [f"left-{index:03d}" for index in range(len(left))]
            + [f"right-{index:03d}" for index in range(len(right))]
        )
        settings = _settings()

        result = analyze_m6_orientation_domains(
            points,
            point_ids=point_ids,
            distance_to_valid_fov_boundary_nm=(100.0,) * len(points),
            settings=settings,
            spatial_calibration_fingerprint="calibration-v1",
            registration_fingerprint="registration-v1",
        )

        self.assertEqual(result.point_count, 128)
        self.assertEqual(result.settings, settings)
        self.assertEqual(result.segmentation.full_domain_count, 2)
        self.assertEqual(result.segmentation.small_ordered_island_count, 0)
        self.assertEqual(
            tuple(component.molecule_count for component in result.segmentation.domains),
            (62, 62),
        )
        self.assertAlmostEqual(result.segmentation.domains[0].orientation_deg, 0.0)
        self.assertAlmostEqual(result.segmentation.domains[1].orientation_deg, 22.0)
        self.assertTrue(
            all(
                all(source_id.startswith("left-") for source_id in component.source_ids)
                or all(source_id.startswith("right-") for source_id in component.source_ids)
                for component in result.segmentation.domains
            )
        )

        interior_indices = tuple(
            index
            for index, degree in enumerate(result.first_shell_graph.degree)
            if degree == 6
        )
        self.assertGreater(len(interior_indices), len(points) // 2)
        self.assertGreater(
            sum(result.local_order.q6[index] > 0.95 for index in interior_indices),
            0.95 * len(interior_indices),
        )
        unassigned_indices = tuple(
            index
            for index, status in enumerate(result.segmentation.assignment_status)
            if status != "assigned"
        )
        self.assertEqual(
            {point_ids[index] for index in unassigned_indices},
            {"left-000", "left-063", "right-000", "right-063"},
        )
        self.assertTrue(
            all(result.first_shell_graph.degree[index] < 3 for index in unassigned_indices)
        )
        self.assertTrue(
            all(
                result.segmentation.assignment_status[index] == "insufficient_neighbors"
                for index in unassigned_indices
            )
        )

        permutation = np.random.default_rng(69_006).permutation(len(points))
        permuted = analyze_m6_orientation_domains(
            points[permutation],
            point_ids=tuple(point_ids[index] for index in permutation),
            distance_to_valid_fov_boundary_nm=(100.0,) * len(points),
            settings=settings,
            spatial_calibration_fingerprint="calibration-v1",
            registration_fingerprint="registration-v1",
        )

        self.assertEqual(_canonical_result(result), _canonical_result(permuted))

        with self.assertRaisesRegex(ValueError, "coordinate provenance"):
            replace(
                result,
                segmentation=replace(
                    result.segmentation,
                    registration_fingerprint="different-registration",
                ),
            )
        with self.assertRaisesRegex(ValueError, "analysis settings"):
            replace(
                result,
                segmentation=replace(
                    result.segmentation,
                    settings=replace(settings, orientation_zero_tolerance=1e-6),
                ),
            )
        changed_settings = replace(settings, orientation_zero_tolerance=1e-6)
        with self.assertRaisesRegex(ValueError, "settings fingerprint"):
            replace(
                result,
                settings=changed_settings,
                segmentation=replace(
                    result.segmentation,
                    settings=changed_settings,
                ),
            )
        altered_statuses = list(result.segmentation.assignment_status)
        altered_statuses[0] = "boundary_or_disordered"
        with self.assertRaisesRegex(ValueError, "statuses"):
            replace(
                result,
                segmentation=replace(
                    result.segmentation,
                    assignment_status=tuple(altered_statuses),
                ),
            )
        assigned_index = 1
        psi6 = list(result.local_order.psi6)
        q6 = list(result.local_order.q6)
        orientations = list(result.local_order.lattice_orientation_deg)
        orientation_statuses = list(result.local_order.orientation_status)
        psi6[assigned_index] = 0j
        q6[assigned_index] = 0.0
        orientations[assigned_index] = None
        orientation_statuses[assigned_index] = "undefined_zero_magnitude"
        with self.assertRaisesRegex(ValueError, "Assigned domain points"):
            replace(
                result,
                local_order=replace(
                    result.local_order,
                    psi6=tuple(psi6),
                    q6=tuple(q6),
                    lattice_orientation_deg=tuple(orientations),
                    orientation_status=tuple(orientation_statuses),
                ),
            )

    def test_rejects_mismatched_boundary_distance_count(self) -> None:
        points = _triangular_patch(0.0, (0.0, 0.0), width=3, height=3)

        with self.assertRaisesRegex(ValueError, "distance_to_valid_fov_boundary_nm"):
            analyze_m6_orientation_domains(
                points,
                distance_to_valid_fov_boundary_nm=(100.0,),
                settings=_settings(),
            )

        generated = analyze_m6_orientation_domains(
            (tuple(point) for point in points),
            distance_to_valid_fov_boundary_nm=(100.0,) * len(points),
            settings=_settings(),
        )
        self.assertEqual(generated.point_count, len(points))


if __name__ == "__main__":
    unittest.main()
