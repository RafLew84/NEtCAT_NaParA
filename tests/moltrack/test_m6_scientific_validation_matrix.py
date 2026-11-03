import math
import unittest

import numpy as np

from moltrack.analysis import (
    MolecularM6OrientationAnalysisSettings,
    aggregate_local_sixfold_bond_order,
    analyze_m6_orientation_domains,
    build_first_shell_graph,
    compute_local_sixfold_bond_order,
    detect_m6_orientation_domain_seeds,
)


def _triangular_patch(
    *,
    width: int = 10,
    height: int = 10,
    spacing_nm: float = 2.0,
    angle_deg: float = 0.0,
    shift_xy_nm: tuple[float, float] = (4.0, 4.0),
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
        first_shell_r_max_nm=2.35,
        min_ordered_component_size=3,
        min_seed_size=6,
        min_domain_size=12,
        q_seed=0.65,
        q_grow=0.25,
        seed_angle_tolerance_deg=6.0,
        grow_angle_tolerance_deg=12.0,
        domain_merge_angle_tolerance_deg=6.0,
        footprint_support_radius_nm=1.2,
    )


def _analyze(
    points: np.ndarray,
    *,
    point_ids: tuple[str, ...] | None = None,
    boundary_distances_nm: tuple[float, ...] | None = None,
    settings: MolecularM6OrientationAnalysisSettings | None = None,
    with_rectangular_fov: bool = False,
    registration_fingerprint: str = "registration-v1",
):
    normalized_points = np.asarray(points, dtype=np.float64)
    count = len(normalized_points)
    if point_ids is None:
        point_ids = tuple(f"point-{index:04d}" for index in range(count))
    if boundary_distances_nm is None:
        boundary_distances_nm = (100.0,) * count
    kwargs = {}
    if with_rectangular_fov:
        kwargs = {
            "window_geometry": "rectangular",
            "window_size_nm": (40.0, 32.0),
        }
    return analyze_m6_orientation_domains(
        normalized_points,
        point_ids=point_ids,
        distance_to_valid_fov_boundary_nm=boundary_distances_nm,
        settings=settings or _settings(),
        spatial_calibration_fingerprint="calibration-v1",
        registration_fingerprint=registration_fingerprint,
        **kwargs,
    )


def _component_summary(result) -> tuple[tuple[object, ...], ...]:
    return tuple(
        sorted(
            (
                component.component_type,
                component.molecule_count,
                round(component.orientation_deg, 9),
                round(component.domain_mean_local_q6, 9),
                round(component.domain_coherent_q6, 9),
                round(component.domain_median_bond_length_nm, 9)
                if component.domain_median_bond_length_nm is not None
                else None,
            )
            for component in result.domain_metrics.components
        )
    )


def _fraction_sum(values: tuple[float | None, ...]) -> float:
    if any(value is None for value in values):
        raise AssertionError("Expected every partition fraction to be available.")
    return math.fsum(float(value) for value in values if value is not None)


def _edge_source_pairs(result) -> frozenset[frozenset[str]]:
    source_ids = result.first_shell_graph.point_ids
    return frozenset(
        frozenset((source_ids[left], source_ids[right]))
        for left, right in result.first_shell_graph.edges_ij
    )


def _component_source_partition(result) -> frozenset[frozenset[str]]:
    return frozenset(
        frozenset(component.source_ids)
        for component in result.segmentation.components
    )


def _point_state_by_source(result) -> dict[str, tuple[object, ...]]:
    return {
        source_id: (
            result.first_shell_graph.degree[index],
            None
            if result.local_order.q6[index] is None
            else round(result.local_order.q6[index], 12),
            result.local_order.orientation_status[index],
            result.segmentation.assignment_status[index],
            result.segmentation.component_type[index],
        )
        for index, source_id in enumerate(result.first_shell_graph.point_ids)
    }


class M6ScientificValidationMatrixTests(unittest.TestCase):
    """Cross-stage scientific regressions complementing the exact unit contracts."""

    def test_low_population_geometry_and_global_partition_matrix(self) -> None:
        cases = (
            (
                np.empty((0, 2), dtype=np.float64),
                "rank0_empty",
                "empty_partition",
            ),
            (np.asarray(((2.0, 2.0),)), "rank0_empty", "single_point_cell"),
            (
                np.asarray(((2.0, 2.0), (4.0, 2.0))),
                "rank1_adjacent_projection",
                "two_point_bisector",
            ),
            (
                np.asarray(((2.0, 2.0), (4.0, 2.0), (6.0, 2.0))),
                "rank1_adjacent_projection",
                "rank1_projection_strips",
            ),
            (
                np.asarray(((2.0, 2.0), (4.0, 2.0), (3.0, 3.8))),
                "delaunay_first_shell",
                "rank2_bounded_voronoi",
            ),
        )

        for points, graph_method, footprint_method in cases:
            with self.subTest(point_count=len(points), graph_method=graph_method):
                result = _analyze(points, with_rectangular_fov=True)
                footprint = result.footprint_partition
                aggregates = result.frame_aggregates
                assert footprint is not None
                assert aggregates is not None

                self.assertEqual(result.first_shell_graph.construction_method, graph_method)
                self.assertEqual(footprint.footprint_construction_method, footprint_method)
                self.assertAlmostEqual(footprint.footprint_overlap_error_nm2, 0.0)
                self.assertAlmostEqual(
                    _fraction_sum(
                        (
                            aggregates.full_domain_footprint_fraction,
                            aggregates.small_island_footprint_fraction,
                            aggregates.unassigned_supported_footprint_fraction,
                            aggregates.unsupported_background_fraction,
                        )
                    ),
                    1.0,
                )
                if len(points) == 0:
                    self.assertIsNone(aggregates.unassigned_molecule_fraction)
                else:
                    self.assertAlmostEqual(
                        _fraction_sum(
                            (
                                aggregates.full_domain_molecule_fraction,
                                aggregates.small_island_molecule_fraction,
                                aggregates.unassigned_molecule_fraction,
                            )
                        ),
                        1.0,
                    )
                    self.assertTrue(
                        all(value is None for value in result.local_order.psi6)
                    )

    def test_single_missing_interior_centroid_does_not_split_a_lattice(self) -> None:
        points = _triangular_patch()
        point_ids = tuple(f"lattice-{index:03d}" for index in range(len(points)))
        baseline = _analyze(points, point_ids=point_ids)
        missing_index = 5 * 10 + 5
        retained = np.arange(len(points)) != missing_index
        with_hole = _analyze(
            points[retained],
            point_ids=tuple(
                point_id for index, point_id in enumerate(point_ids) if retained[index]
            ),
        )

        self.assertEqual(baseline.segmentation.full_domain_count, 1)
        self.assertEqual(with_hole.segmentation.full_domain_count, 1)
        baseline_domain = baseline.segmentation.domains[0]
        hole_domain = with_hole.segmentation.domains[0]
        self.assertGreaterEqual(hole_domain.molecule_count, baseline_domain.molecule_count - 7)
        self.assertGreater(hole_domain.molecule_count, 0.85 * len(with_hole.local_order.source_ids))
        self.assertAlmostEqual(
            hole_domain.orientation_deg,
            baseline_domain.orientation_deg,
            places=8,
        )

    def test_random_false_negatives_report_population_degradation(self) -> None:
        points = _triangular_patch(width=12, height=10)
        baseline = _analyze(points)
        self.assertEqual(baseline.segmentation.full_domain_count, 1)
        baseline_assigned = sum(
            status == "assigned" for status in baseline.segmentation.assignment_status
        )
        for removal_fraction, seed in ((0.05, 71_005), (0.30, 71_030)):
            with self.subTest(removal_fraction=removal_fraction):
                rng = np.random.default_rng(seed)
                removed_count = round(removal_fraction * len(points))
                retained = np.ones(len(points), dtype=bool)
                retained[rng.choice(len(points), size=removed_count, replace=False)] = False
                reduced_points = points[retained]
                reduced = _analyze(
                    reduced_points,
                    point_ids=tuple(
                        f"retained-{index:03d}"
                        for index, is_retained in enumerate(retained)
                        if is_retained
                    ),
                )

                self.assertEqual(
                    reduced.domain_metrics.valid_representative_count,
                    len(points) - removed_count,
                )
                self.assertLess(
                    sum(
                        status == "assigned"
                        for status in reduced.segmentation.assignment_status
                    ),
                    baseline_assigned,
                )
                self.assertLessEqual(reduced.segmentation.full_domain_count, 1)
                self.assertNotEqual(
                    _component_summary(reduced),
                    _component_summary(baseline),
                )

    def test_false_positive_centroids_have_explicit_short_pair_qc(self) -> None:
        points = _triangular_patch(width=12, height=10)
        false_positives = points[[16, 31, 64, 87]] + np.asarray((0.72, 0.66))
        augmented_points = np.vstack((points, false_positives))
        baseline = _analyze(points)
        augmented = _analyze(
            augmented_points,
            point_ids=tuple(f"augmented-{index:03d}" for index in range(len(augmented_points))),
        )
        baseline_order = aggregate_local_sixfold_bond_order(baseline.local_order)
        augmented_order = aggregate_local_sixfold_bond_order(augmented.local_order)
        assert baseline_order.mean_local_q6_interior is not None
        assert augmented_order.mean_local_q6_interior is not None

        self.assertEqual(
            augmented.domain_metrics.valid_representative_count,
            len(augmented_points),
        )
        self.assertGreater(sum(augmented.first_shell_graph.short_non_shell_pair_qc), 0)
        self.assertLess(
            augmented_order.mean_local_q6_interior,
            baseline_order.mean_local_q6_interior,
        )
        self.assertLessEqual(augmented.segmentation.full_domain_count, 1)

    def test_position_noise_degrades_order_without_destroying_main_domain(self) -> None:
        points = _triangular_patch(width=12, height=10)
        rng = np.random.default_rng(71_101)
        noisy_points = points + rng.normal(0.0, 0.10, size=points.shape)
        baseline = _analyze(points)
        noisy = _analyze(noisy_points)
        baseline_order = aggregate_local_sixfold_bond_order(baseline.local_order)
        noisy_order = aggregate_local_sixfold_bond_order(noisy.local_order)
        assert baseline_order.mean_local_q6_interior is not None
        assert noisy_order.mean_local_q6_interior is not None

        self.assertEqual(noisy.segmentation.full_domain_count, 1)
        self.assertLess(
            noisy_order.mean_local_q6_interior,
            baseline_order.mean_local_q6_interior,
        )
        self.assertGreater(noisy_order.mean_local_q6_interior, 0.90)

    def test_one_or_two_period_empty_strip_splits_the_physical_graph(self) -> None:
        points = _triangular_patch(width=12, height=8)
        baseline = _analyze(points)
        self.assertEqual(baseline.segmentation.full_domain_count, 1)

        for removed_columns in ((5,), (5, 6)):
            with self.subTest(removed_columns=removed_columns):
                retained = np.asarray(
                    [index % 12 not in removed_columns for index in range(len(points))]
                )
                retained_ids = tuple(
                    f"gap-{index // 12:02d}-{index % 12:02d}"
                    for index, is_retained in enumerate(retained)
                    if is_retained
                )
                split = _analyze(points[retained], point_ids=retained_ids)

                self.assertEqual(split.settings.first_shell_r_max_nm, 2.35)
                self.assertEqual(split.segmentation.full_domain_count, 2)
                for left, right in split.first_shell_graph.edges_ij:
                    left_column = int(retained_ids[left].rsplit("-", 1)[1])
                    right_column = int(retained_ids[right].rsplit("-", 1)[1])
                    self.assertFalse(
                        min(left_column, right_column) < min(removed_columns)
                        and max(left_column, right_column) > max(removed_columns)
                    )

    def test_touching_same_orientation_phases_report_bond_heterogeneity(self) -> None:
        left = _triangular_patch(
            width=6,
            height=5,
            spacing_nm=2.0,
            shift_xy_nm=(4.0, 4.0),
        )
        right = _triangular_patch(
            width=6,
            height=5,
            spacing_nm=2.3,
            shift_xy_nm=(16.0, 4.0),
        )
        points = np.vstack((left, right))
        settings = MolecularM6OrientationAnalysisSettings(
            first_shell_r_min_nm=1.5,
            first_shell_r_max_nm=2.35,
            min_ordered_component_size=3,
            min_seed_size=5,
            min_domain_size=10,
            q_seed=0.55,
            q_grow=0.20,
            seed_angle_tolerance_deg=8.0,
            grow_angle_tolerance_deg=15.0,
            domain_merge_angle_tolerance_deg=8.0,
            min_bonds_for_domain_length_stats=5,
            domain_bond_length_robust_cv_qc_threshold=0.025,
        )
        result = _analyze(points, settings=settings)

        self.assertEqual(result.segmentation.full_domain_count, 1)
        component = result.domain_metrics.components[0]
        self.assertTrue(component.bond_length_heterogeneity_qc)
        self.assertIsNotNone(component.domain_bond_length_mad_nm)
        self.assertIsNotNone(component.domain_bond_length_iqr_nm)
        self.assertIsNotNone(component.domain_bond_length_robust_cv)
        assert component.domain_bond_length_mad_nm is not None
        assert component.domain_bond_length_iqr_nm is not None
        assert component.domain_bond_length_robust_cv is not None
        self.assertGreater(component.domain_bond_length_mad_nm, 0.0)
        self.assertGreater(component.domain_bond_length_iqr_nm, 0.0)
        self.assertGreaterEqual(component.domain_bond_length_robust_cv, 0.025)

    def test_cocircular_ambiguity_does_not_create_a_domain(self) -> None:
        points = np.asarray(
            tuple((2.0 * x, 2.0 * y) for y in range(3) for x in range(3)),
            dtype=np.float64,
        )
        source_ids = tuple(f"square-{index:02d}" for index in range(len(points)))
        baseline = _analyze(points, point_ids=source_ids)
        permutation = np.random.default_rng(71_202).permutation(len(points))
        permuted = _analyze(
            points[permutation],
            point_ids=tuple(source_ids[index] for index in permutation),
        )

        self.assertTrue(baseline.first_shell_graph.delaunay_degeneracy_qc)
        self.assertGreater(len(baseline.first_shell_graph.ambiguous_edges_ij), 0)
        self.assertEqual(baseline.segmentation.full_domain_count, 0)
        self.assertEqual(baseline.segmentation.ordered_component_count, 0)
        self.assertEqual(
            _component_source_partition(permuted),
            _component_source_partition(baseline),
        )
        self.assertEqual(_point_state_by_source(permuted), _point_state_by_source(baseline))
        center_index = source_ids.index("square-04")
        self.assertEqual(baseline.first_shell_graph.degree[center_index], 4)
        self.assertLessEqual(
            baseline.local_order.q6[center_index] or 0.0,
            baseline.settings.orientation_zero_tolerance,
        )

    def test_physical_result_is_stable_for_ids_permutation_and_translation(self) -> None:
        points = _triangular_patch(angle_deg=9.0, shift_xy_nm=(7.0, 6.0))
        source_ids = tuple(f"source-{index:03d}" for index in range(len(points)))
        baseline = _analyze(points, point_ids=source_ids)
        renamed = _analyze(
            points,
            point_ids=tuple(f"renamed-{index:03d}" for index in range(len(points))),
        )
        permutation = np.random.default_rng(71_002).permutation(len(points))
        permuted = _analyze(
            points[permutation],
            point_ids=tuple(source_ids[index] for index in permutation),
        )
        translated = _analyze(
            points + np.asarray((8.5, 3.25)),
            point_ids=source_ids,
            registration_fingerprint="registration-translated",
        )

        expected = _component_summary(baseline)
        self.assertEqual(_component_summary(renamed), expected)
        self.assertEqual(_component_summary(permuted), expected)
        self.assertEqual(_component_summary(translated), expected)
        self.assertEqual(_edge_source_pairs(permuted), _edge_source_pairs(baseline))
        self.assertEqual(_edge_source_pairs(translated), _edge_source_pairs(baseline))
        self.assertEqual(
            _component_source_partition(permuted),
            _component_source_partition(baseline),
        )
        self.assertEqual(
            _component_source_partition(translated),
            _component_source_partition(baseline),
        )
        self.assertTrue(
            all(0.0 <= angle < 2.0 * math.pi for angle in baseline.first_shell_graph.angles_rad)
        )
        self.assertTrue(
            all(
                orientation is None or 0.0 <= orientation < 60.0
                for orientation in baseline.local_order.lattice_orientation_deg
            )
        )

    def test_end_to_end_orientation_is_covariant_to_sample_rotation(self) -> None:
        points = _triangular_patch(angle_deg=4.0, shift_xy_nm=(0.0, 0.0))
        rotation_deg = 13.0
        angle_rad = math.radians(rotation_deg)
        rotation = np.asarray(
            (
                (math.cos(angle_rad), -math.sin(angle_rad)),
                (math.sin(angle_rad), math.cos(angle_rad)),
            )
        )
        baseline = _analyze(points)
        rotated = _analyze(points @ rotation.T)

        self.assertEqual(baseline.segmentation.full_domain_count, 1)
        self.assertEqual(rotated.segmentation.full_domain_count, 1)
        expected = (baseline.segmentation.domains[0].orientation_deg + rotation_deg) % 60.0
        self.assertAlmostEqual(
            rotated.segmentation.domains[0].orientation_deg,
            expected,
            places=8,
        )
        self.assertEqual(baseline.first_shell_graph.coordinate_frame, "sample_nm")
        self.assertEqual(baseline.first_shell_graph.orientation_reference, "+x_sample_axis")

    def test_edge_truncated_point_can_join_growth_but_cannot_seed(self) -> None:
        points = _triangular_patch(width=8, height=8)
        point_ids = tuple(f"edge-policy-{index:03d}" for index in range(len(points)))
        settings = _settings()
        graph = build_first_shell_graph(points, point_ids=point_ids, settings=settings)
        center_index = next(
            index
            for index, degree in enumerate(graph.degree)
            if degree == 6 and 2 < index // 8 < 6 and 2 < index % 8 < 6
        )
        boundary_distances = [100.0] * len(points)
        boundary_distances[center_index] = settings.first_shell_r_max_nm / 2.0
        local_order = compute_local_sixfold_bond_order(
            graph,
            distance_to_valid_fov_boundary_nm=boundary_distances,
            settings=settings,
        )
        seeds = detect_m6_orientation_domain_seeds(
            points,
            first_shell_graph=graph,
            local_order=local_order,
            settings=settings,
        )
        final = _analyze(
            points,
            point_ids=point_ids,
            boundary_distances_nm=tuple(boundary_distances),
            settings=settings,
        )

        self.assertEqual(local_order.computation_status[center_index], "valid_order")
        self.assertTrue(local_order.edge_truncated_neighborhood[center_index])
        self.assertFalse(seeds.seed_eligible[center_index])
        self.assertEqual(final.segmentation.assignment_status[center_index], "assigned")

    def test_affine_distortion_and_irregular_fov_keep_explicit_qc_and_partitions(self) -> None:
        points = _triangular_patch(width=8, height=7, shift_xy_nm=(3.0, 3.0))
        baseline = _analyze(points)
        affine = np.asarray(((1.08, 0.10), (0.0, 0.93)))
        distorted_points = points @ affine.T
        valid_fov_mask = np.ones((48, 64), dtype=bool)
        valid_fov_mask[18:19, 19:20] = False
        distorted = analyze_m6_orientation_domains(
            distorted_points,
            point_ids=tuple(f"distorted-{index:03d}" for index in range(len(points))),
            distance_to_valid_fov_boundary_nm=(100.0,) * len(points),
            settings=_settings(),
            spatial_calibration_fingerprint="affine-calibration-v1",
            registration_fingerprint="registration-v1",
            window_geometry="irregular",
            valid_fov_mask=valid_fov_mask,
            valid_fov_pixel_size_nm=(0.5, 0.5),
        )
        baseline_order = aggregate_local_sixfold_bond_order(baseline.local_order)
        distorted_order = aggregate_local_sixfold_bond_order(distorted.local_order)
        footprint = distorted.footprint_partition
        aggregates = distorted.frame_aggregates
        assert footprint is not None
        assert aggregates is not None
        assert baseline_order.mean_local_q6_interior is not None
        assert distorted_order.mean_local_q6_interior is not None

        self.assertLess(
            distorted_order.mean_local_q6_interior,
            baseline_order.mean_local_q6_interior,
        )
        self.assertEqual(footprint.footprint_construction_method, "rank2_bounded_voronoi")
        self.assertAlmostEqual(
            footprint.valid_fov_area_nm2,
            float(np.count_nonzero(valid_fov_mask)) * 0.25,
        )
        self.assertTrue(footprint.footprint_clipped_by_fov_qc)
        self.assertFalse(footprint.fewer_than_3_noncollinear_points_qc)
        self.assertFalse(footprint.voronoi_degenerate_qc)
        self.assertTrue(footprint.footprint_disconnected_qc)
        self.assertFalse(footprint.footprint_overlap_error_qc)
        self.assertAlmostEqual(footprint.footprint_overlap_error_nm2, 0.0, places=8)
        self.assertAlmostEqual(
            _fraction_sum(
                (
                    aggregates.full_domain_footprint_fraction,
                    aggregates.small_island_footprint_fraction,
                    aggregates.unassigned_supported_footprint_fraction,
                    aggregates.unsupported_background_fraction,
                )
            ),
            1.0,
        )


if __name__ == "__main__":
    unittest.main()
