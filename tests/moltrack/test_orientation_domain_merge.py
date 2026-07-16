import cmath
import math
import unittest
from dataclasses import replace

import numpy as np

from moltrack.analysis import (
    FirstShellGraph,
    M6OrientationDomainSegmentation,
    LocalSixfoldBondOrderField,
    MolecularM6OrientationAnalysisSettings,
    M6OrientationDomainMergeState,
    detect_m6_orientation_domain_seeds,
    grow_m6_orientation_domains,
    finalize_m6_orientation_domains,
    merge_and_grow_m6_orientation_domains,
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
        "seed_angle_tolerance_deg": 1.0,
        "grow_angle_tolerance_deg": 8.0,
        "domain_merge_angle_tolerance_deg": 8.0,
        "domain_conflict_margin": 0.05,
    }
    payload.update(overrides)
    return MolecularM6OrientationAnalysisSettings(**payload)


def _inputs(
    *,
    orientations_deg: tuple[float, ...],
    edges_ij: tuple[tuple[int, int], ...],
    settings: MolecularM6OrientationAnalysisSettings,
    q6: tuple[float, ...] | None = None,
    point_ids: tuple[str, ...] | None = None,
    points_xy_nm: np.ndarray | None = None,
) -> tuple[np.ndarray, FirstShellGraph, LocalSixfoldBondOrderField]:
    point_count = len(orientations_deg)
    ids = point_ids or tuple(f"p{index:02d}" for index in range(point_count))
    points = np.asarray(
        points_xy_nm
        if points_xy_nm is not None
        else tuple((float(index), float(index % 2)) for index in range(point_count)),
        dtype=np.float64,
    )
    magnitudes = q6 or (0.9,) * point_count
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
    psi6 = tuple(
        magnitude * cmath.exp(6j * math.radians(angle))
        for angle, magnitude in zip(orientations_deg, magnitudes)
    )
    local_order = LocalSixfoldBondOrderField(
        source_ids=ids,
        point_count=point_count,
        psi6=psi6,
        q6=magnitudes,
        lattice_orientation_deg=orientations_deg,
        orientation_status=("defined",) * point_count,
        neighbor_count=tuple(degree),
        computation_status=("valid_order",) * point_count,
        local_median_bond_length_nm=(1.5,) * point_count,
        local_bond_length_mad_nm=(0.0,) * point_count,
        local_bond_length_iqr_nm=(0.0,) * point_count,
        local_bond_length_robust_cv=(0.0,) * point_count,
        physical_duplicate_qc=(False,) * point_count,
        geometry_duplicate_qc=(False,) * point_count,
        edge_truncated_neighborhood=(False,) * point_count,
        distance_to_valid_fov_boundary_nm=(10.0,) * point_count,
        first_shell_r_max_nm=settings.first_shell_r_max_nm,
        coordinate_frame="sample_nm",
        orientation_reference="+x_sample_axis",
        spatial_calibration_fingerprint="calibration-v1",
        registration_fingerprint="registration-v1",
        min_neighbors_for_local_order=settings.min_neighbors_for_local_order,
    )
    return points, graph, local_order


def _merge(
    inputs: tuple[np.ndarray, FirstShellGraph, LocalSixfoldBondOrderField],
    settings: MolecularM6OrientationAnalysisSettings,
):
    points, graph, local_order = inputs
    seeds = detect_m6_orientation_domain_seeds(
        points,
        first_shell_graph=graph,
        local_order=local_order,
        settings=settings,
    )
    growth = grow_m6_orientation_domains(
        points,
        first_shell_graph=graph,
        local_order=local_order,
        seeds=seeds,
        settings=settings,
    )
    return merge_and_grow_m6_orientation_domains(
        points,
        first_shell_graph=graph,
        local_order=local_order,
        growth=growth,
        settings=settings,
    )


def _partition_by_source_id(
    result: M6OrientationDomainMergeState,
) -> set[frozenset[str]]:
    return {
        frozenset(component.source_ids)
        for component in result.components
    }


def _canonical_result(result: M6OrientationDomainMergeState) -> tuple[object, ...]:
    point_state = {
        source_id: (
            result.seed_eligible[index],
            result.component_type[index],
            result.assignment_status[index],
            result.edge_truncated_neighborhood[index],
            result.physical_duplicate_qc[index],
            result.geometry_duplicate_qc[index],
            (
                None
                if result.component_for_source_id(source_id) is None
                else frozenset(result.component_for_source_id(source_id).source_ids)
            ),
        )
        for index, source_id in enumerate(result.source_ids)
    }
    components = {
        frozenset(component.source_ids): (
            component.component_type,
            component.molecule_count,
            component.centroid_x_nm,
            component.centroid_y_nm,
            component.orientation_deg,
            tuple(
                frozenset(constituent.seed_component.source_ids)
                for constituent in component.constituents
            ),
            component.constituent_orientation_deg,
        )
        for component in result.components
    }
    return (
        point_state,
        components,
        result.ordered_component_count,
        result.growth_seed_count,
        result.small_ordered_island_count,
        result.growth_iteration_count,
        result.merge_iteration_count,
        result.post_merge_growth_iteration_count,
        result.settings,
        result.coordinate_frame,
        result.orientation_reference,
        result.spatial_calibration_fingerprint,
        result.registration_fingerprint,
    )


def _canonical_segmentation(
    result: M6OrientationDomainSegmentation,
) -> tuple[object, ...]:
    point_state = {
        source_id: (
            result.ordered_component_id[index],
            result.m6_orientation_domain_id[index],
            result.component_type[index],
            result.assignment_status[index],
            result.edge_truncated_neighborhood[index],
            result.physical_duplicate_qc[index],
            result.geometry_duplicate_qc[index],
            (
                None
                if result.component_for_source_id(source_id) is None
                else frozenset(result.component_for_source_id(source_id).source_ids)
            ),
        )
        for index, source_id in enumerate(result.source_ids)
    }
    components = {
        frozenset(component.source_ids): (
            component.ordered_component_id,
            component.m6_orientation_domain_id,
            component.component_type,
            component.molecule_count,
            component.centroid_x_nm,
            component.centroid_y_nm,
            component.orientation_deg,
        )
        for component in result.components
    }
    return (
        point_state,
        components,
        result.ordered_component_count,
        result.full_domain_count,
        result.small_ordered_island_count,
        result.settings,
        result.coordinate_frame,
        result.orientation_reference,
        result.spatial_calibration_fingerprint,
        result.registration_fingerprint,
    )


class OrientationDomainMergeTests(unittest.TestCase):
    def test_merges_two_cores_across_compatible_boundary_then_regrows_it(self) -> None:
        settings = _settings(domain_merge_angle_tolerance_deg=5.0)
        result = _merge(
            _inputs(
                orientations_deg=(0.0, 0.0, 4.0, 4.0, 2.0),
                q6=(0.9, 0.9, 0.9, 0.9, 0.5),
                edges_ij=((0, 1), (2, 3), (1, 4), (2, 4)),
                settings=settings,
            ),
            settings,
        )

        self.assertEqual(result.ordered_component_count, 1)
        self.assertEqual(result.components[0].molecule_count, 5)
        self.assertEqual(result.components[0].seed_component_count, 2)
        self.assertEqual(result.ordered_component_id, (0, 0, 0, 0, 0))
        self.assertEqual(result.merge_iteration_count, 1)
        self.assertEqual(result.post_merge_growth_iteration_count, 1)

    def test_direct_contact_merges_but_distant_same_orientation_islands_do_not(self) -> None:
        settings = _settings(domain_merge_angle_tolerance_deg=5.0)
        connected = _merge(
            _inputs(
                orientations_deg=(59.0, 59.0, 1.0, 1.0),
                edges_ij=((0, 1), (1, 2), (2, 3)),
                settings=settings,
            ),
            settings,
        )
        distant = _merge(
            _inputs(
                orientations_deg=(0.0, 0.0, 0.0, 0.0),
                edges_ij=((0, 1), (2, 3)),
                settings=settings,
            ),
            settings,
        )

        self.assertEqual(connected.ordered_component_count, 1)
        self.assertEqual(distant.ordered_component_count, 2)
        self.assertEqual(distant.merge_iteration_count, 0)

    def test_adjacent_but_angularly_incompatible_domains_do_not_merge(self) -> None:
        settings = _settings(domain_merge_angle_tolerance_deg=5.0)
        result = _merge(
            _inputs(
                orientations_deg=(0.0, 0.0, 10.0, 10.0),
                edges_ij=((0, 1), (1, 2), (2, 3)),
                settings=settings,
            ),
            settings,
        )

        self.assertEqual(result.ordered_component_count, 2)
        self.assertEqual(result.merge_iteration_count, 0)

    def test_orientation_incompatible_boundary_candidate_is_not_a_bridge(self) -> None:
        settings = _settings(
            grow_angle_tolerance_deg=8.0,
            domain_merge_angle_tolerance_deg=5.0,
        )
        result = _merge(
            _inputs(
                orientations_deg=(0.0, 0.0, 0.0, 0.0, 30.0),
                q6=(0.9, 0.9, 0.9, 0.9, 0.5),
                edges_ij=((0, 1), (2, 3), (1, 4), (2, 4)),
                settings=settings,
            ),
            settings,
        )

        self.assertEqual(result.ordered_component_count, 2)
        self.assertEqual(result.ordered_component_id[4], -1)
        self.assertEqual(result.merge_iteration_count, 0)

    def test_merge_result_rejects_inconsistent_parallel_labels(self) -> None:
        settings = _settings(domain_merge_angle_tolerance_deg=5.0)
        result = _merge(
            _inputs(
                orientations_deg=(0.0, 0.0, 4.0, 4.0),
                edges_ij=((0, 1), (1, 2), (2, 3)),
                settings=settings,
            ),
            settings,
        )

        with self.assertRaisesRegex(ValueError, "ordered_component_id"):
            replace(result, ordered_component_id=())
        with self.assertRaisesRegex(ValueError, "assignment_status"):
            replace(
                result,
                assignment_status=("unknown",) + result.assignment_status[1:],
            )

        boundary_result = _merge(
            _inputs(
                orientations_deg=(0.0, 0.0, 10.0, 10.0, 5.0),
                q6=(0.9, 0.9, 0.9, 0.9, 0.1),
                edges_ij=((0, 1), (2, 3), (1, 4), (2, 4)),
                settings=settings,
            ),
            settings,
        )
        with self.assertRaisesRegex(ValueError, "Unassigned points"):
            replace(
                boundary_result,
                ordered_component_id=(
                    *boundary_result.ordered_component_id[:4],
                    0,
                ),
            )

    def test_complete_linkage_prevents_gradual_orientation_chain_merge(self) -> None:
        settings = _settings(domain_merge_angle_tolerance_deg=8.0)
        result = _merge(
            _inputs(
                orientations_deg=(0.0, 0.0, 6.0, 6.0, 12.0, 12.0),
                edges_ij=((0, 1), (1, 2), (2, 3), (3, 4), (4, 5)),
                settings=settings,
            ),
            settings,
        )

        self.assertEqual(result.ordered_component_count, 2)
        for component in result.components:
            seed_angles = tuple(
                seed.orientation_deg for seed in component.seed_components
            )
            for left in seed_angles:
                for right in seed_angles:
                    delta = abs(left - right) % 60.0
                    self.assertLessEqual(min(delta, 60.0 - delta), 8.0)
        self.assertFalse(
            any(
                {"p00", "p05"}.issubset(component.source_ids)
                for component in result.components
            )
        )

    def test_merge_and_regrow_repeats_until_a_fixed_point(self) -> None:
        settings = _settings(
            grow_angle_tolerance_deg=2.0,
            domain_merge_angle_tolerance_deg=8.0,
        )
        result = _merge(
            _inputs(
                orientations_deg=(0.0, 0.0, 4.0, 4.0, 8.0, 8.0, 2.0, 2.0),
                q6=(0.9, 0.9, 0.9, 0.9, 0.9, 0.9, 0.5, 0.5),
                edges_ij=(
                    (0, 1),
                    (2, 3),
                    (4, 5),
                    (1, 6),
                    (2, 6),
                    (6, 7),
                    (4, 7),
                ),
                settings=settings,
            ),
            settings,
        )

        self.assertEqual(result.ordered_component_count, 1)
        self.assertEqual(result.components[0].molecule_count, 8)
        self.assertEqual(result.components[0].seed_component_count, 3)
        self.assertEqual(result.merge_iteration_count, 2)
        self.assertEqual(result.post_merge_growth_iteration_count, 2)

    def test_regrown_orientation_can_block_a_subsequent_merge(self) -> None:
        settings = _settings(
            grow_angle_tolerance_deg=20.0,
            domain_merge_angle_tolerance_deg=5.0,
        )
        result = _merge(
            _inputs(
                orientations_deg=(0.0,) * 6 + (20.0,) * 20 + (25.0,),
                q6=(0.9,) * 6 + (0.5,) * 21,
                edges_ij=(
                    ((0, 1), (2, 3), (4, 5))
                    + tuple((1, index) for index in range(6, 26))
                    + tuple((2, index) for index in range(6, 26))
                    + ((6, 26), (4, 26))
                ),
                settings=settings,
            ),
            settings,
        )

        self.assertEqual(result.ordered_component_count, 2)
        self.assertEqual(result.merge_iteration_count, 1)
        grown_component = result.component_for_source_id("p00")
        self.assertIsNotNone(grown_component)
        assert grown_component is not None
        self.assertGreater(grown_component.orientation_deg, 15.0)
        self.assertNotEqual(
            result.ordered_component_id[0],
            result.ordered_component_id[4],
        )

    def test_result_is_invariant_to_point_domain_and_edge_order(self) -> None:
        settings = _settings(domain_merge_angle_tolerance_deg=5.0)
        ids = ("a", "b", "c", "d", "bridge", "x", "y")
        points = np.asarray(
            (
                (0.0, 0.0),
                (1.0, 0.0),
                (3.0, 0.0),
                (4.0, 0.0),
                (2.0, 0.0),
                (10.0, 0.0),
                (11.0, 0.0),
            )
        )
        orientations = (0.0, 0.0, 4.0, 4.0, 2.0, 20.0, 20.0)
        q6 = (0.9, 0.9, 0.9, 0.9, 0.5, 0.9, 0.9)
        edges = ((0, 1), (2, 3), (1, 4), (2, 4), (5, 6))
        original = _merge(
            _inputs(
                orientations_deg=orientations,
                q6=q6,
                edges_ij=edges,
                settings=settings,
                point_ids=ids,
                points_xy_nm=points,
            ),
            settings,
        )
        permutation = (6, 4, 3, 5, 2, 1, 0)
        old_to_new = {old: new for new, old in enumerate(permutation)}
        permuted_edges = tuple(
            sorted((old_to_new[left], old_to_new[right]))
            for left, right in reversed(edges)
        )
        permuted = _merge(
            _inputs(
                orientations_deg=tuple(orientations[index] for index in permutation),
                q6=tuple(q6[index] for index in permutation),
                edges_ij=permuted_edges,
                settings=settings,
                point_ids=tuple(ids[index] for index in permutation),
                points_xy_nm=points[np.asarray(permutation)],
            ),
            settings,
        )

        self.assertEqual(_partition_by_source_id(original), _partition_by_source_id(permuted))
        self.assertEqual(_canonical_result(original), _canonical_result(permuted))
        self.assertEqual(
            _canonical_segmentation(finalize_m6_orientation_domains(original)),
            _canonical_segmentation(finalize_m6_orientation_domains(permuted)),
        )

    def test_source_id_changes_preserve_physical_partition_and_metrics(self) -> None:
        settings = _settings(domain_merge_angle_tolerance_deg=8.0)
        geometry = dict(
            orientations_deg=(0.0, 0.0, 5.0, 5.0, 13.0, 13.0),
            edges_ij=((0, 1), (1, 2), (2, 3), (3, 4), (4, 5)),
            settings=settings,
        )
        original = _merge(_inputs(**geometry), settings)
        renamed = _merge(
            _inputs(point_ids=("z", "x", "w", "y", "v", "u"), **geometry),
            settings,
        )

        self.assertEqual(
            {component.point_indices for component in original.components},
            {component.point_indices for component in renamed.components},
        )
        self.assertEqual(
            {
                component.point_indices: (
                    component.molecule_count,
                    component.centroid_x_nm,
                    component.centroid_y_nm,
                    component.orientation_deg,
                )
                for component in original.components
            },
            {
                component.point_indices: (
                    component.molecule_count,
                    component.centroid_x_nm,
                    component.centroid_y_nm,
                    component.orientation_deg,
                )
                for component in renamed.components
            },
        )


class OrientationDomainFinalizationTests(unittest.TestCase):
    def test_classifies_all_size_intervals_independently_of_seed_rights(self) -> None:
        settings = _settings(
            min_ordered_component_size=2,
            min_seed_size=3,
            min_domain_size=5,
        )
        orientations = (
            (0.0,) * 2
            + (10.0,) * 3
            + (20.0,) * 5
            + (30.0, 45.0)
        )
        edges = (
            (0, 1),
            (2, 3),
            (3, 4),
            (5, 6),
            (6, 7),
            (7, 8),
            (8, 9),
            (10, 11),
        )
        inputs = _inputs(
            orientations_deg=orientations,
            edges_ij=edges,
            settings=settings,
        )
        merged = _merge(inputs, settings)
        result = finalize_m6_orientation_domains(merged)

        self.assertEqual(
            result.point_coordinate_fingerprint,
            merged.point_coordinate_fingerprint,
        )
        self.assertFalse(merged.component_for_source_id("p00").can_initiate_growth)
        self.assertTrue(merged.component_for_source_id("p02").can_initiate_growth)
        self.assertTrue(merged.component_for_source_id("p05").can_initiate_growth)
        self.assertEqual(result.ordered_component_count, 3)
        self.assertEqual(result.full_domain_count, 1)
        self.assertEqual(result.small_ordered_island_count, 2)
        self.assertEqual(result.component_type[:2], ("small_ordered_island",) * 2)
        self.assertEqual(result.component_type[2:5], ("small_ordered_island",) * 3)
        self.assertEqual(result.component_type[5:10], ("full_domain",) * 5)
        self.assertEqual(result.assignment_status[10:], ("boundary_or_disordered",) * 2)
        self.assertEqual(result.assignment_status[:10], ("assigned",) * 10)
        self.assertEqual(result.ordered_component_id[10:], (-1, -1))
        self.assertEqual(result.m6_orientation_domain_id[10:], (-1, -1))
        self.assertEqual(result.m6_orientation_domain_id[5:10], (0,) * 5)
        self.assertEqual(result.m6_orientation_domain_id[:5], (-1,) * 5)
        self.assertEqual(
            tuple(component.molecule_count for component in result.components),
            (5, 3, 2),
        )
        self.assertEqual(
            tuple(component.ordered_component_id for component in result.components),
            (0, 1, 2),
        )

        permutation = tuple(reversed(range(len(orientations))))
        old_to_new = {old: new for new, old in enumerate(permutation)}
        permuted_inputs = _inputs(
            orientations_deg=tuple(orientations[index] for index in permutation),
            edges_ij=tuple(
                sorted((old_to_new[left], old_to_new[right]))
                for left, right in reversed(edges)
            ),
            settings=settings,
            point_ids=tuple(inputs[1].point_ids[index] for index in permutation),
            points_xy_nm=inputs[0][np.asarray(permutation)],
        )
        permuted_result = finalize_m6_orientation_domains(
            _merge(permuted_inputs, settings)
        )
        self.assertEqual(
            _canonical_segmentation(result),
            _canonical_segmentation(permuted_result),
        )

        stricter_seed_settings = replace(settings, min_seed_size=4)
        stricter_inputs = _inputs(
            orientations_deg=(
                (0.0,) * 2
                + (10.0,) * 3
                + (20.0,) * 5
                + (30.0, 45.0)
            ),
            edges_ij=inputs[1].edges_ij,
            settings=stricter_seed_settings,
        )
        stricter_merged = _merge(stricter_inputs, stricter_seed_settings)
        stricter_result = finalize_m6_orientation_domains(stricter_merged)

        self.assertFalse(
            stricter_merged.component_for_source_id("p02").can_initiate_growth
        )
        self.assertEqual(result.component_type, stricter_result.component_type)
        self.assertEqual(
            result.m6_orientation_domain_id,
            stricter_result.m6_orientation_domain_id,
        )

    def test_distant_same_orientation_components_remain_distinct_full_domains(self) -> None:
        settings = _settings(
            min_ordered_component_size=2,
            min_seed_size=2,
            min_domain_size=2,
        )
        result = finalize_m6_orientation_domains(
            _merge(
                _inputs(
                    orientations_deg=(0.0, 0.0, 0.0, 0.0),
                    edges_ij=((0, 1), (2, 3)),
                    settings=settings,
                ),
                settings,
            )
        )

        self.assertEqual(result.full_domain_count, 2)
        self.assertEqual(
            tuple(component.m6_orientation_domain_id for component in result.domains),
            (0, 1),
        )
        self.assertNotEqual(result.ordered_component_id[0], result.ordered_component_id[2])
        self.assertEqual(result.ordered_component_id, (0, 0, 1, 1))

    def test_preserves_non_assignment_statuses_and_duplicate_qc(self) -> None:
        settings = _settings(
            min_ordered_component_size=2,
            min_seed_size=2,
            min_domain_size=2,
        )
        merged = _merge(
            _inputs(
                orientations_deg=(0.0, 0.0, 10.0, 30.0, 15.0, 35.0),
                edges_ij=((0, 1), (2, 3), (4, 5)),
                settings=settings,
            ),
            settings,
        )
        altered = replace(
            merged,
            assignment_status=(
                "assigned",
                "assigned",
                "insufficient_neighbors",
                "duplicate_excluded",
                "invalid_position",
                "boundary_or_disordered",
            ),
            physical_duplicate_qc=(False, False, False, True, False, False),
        )

        result = finalize_m6_orientation_domains(altered)

        self.assertEqual(result.assignment_status, altered.assignment_status)
        self.assertEqual(result.physical_duplicate_qc, altered.physical_duplicate_qc)
        self.assertEqual(result.geometry_duplicate_qc, altered.geometry_duplicate_qc)


if __name__ == "__main__":
    unittest.main()
