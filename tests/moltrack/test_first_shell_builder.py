import unittest
from unittest.mock import patch

import numpy as np
from scipy.spatial import QhullError

from moltrack.analysis import (
    MolecularM6OrientationAnalysisSettings,
    build_first_shell_graph,
)


class FirstShellGraphBuilderTests(unittest.TestCase):
    def test_filters_first_shell_boundaries_and_marks_short_candidate_pairs(self) -> None:
        settings = MolecularM6OrientationAnalysisSettings(
            duplicate_max_distance_nm=0.5,
            first_shell_r_min_nm=1.0,
            first_shell_r_max_nm=2.0,
            geometry_absolute_tolerance_nm=0.01,
            geometry_relative_tolerance=1e-12,
        )
        cases = (
            (np.nextafter(0.5, np.inf), False, True),
            (np.nextafter(1.0, 0.0), False, True),
            (1.0, True, False),
            (np.nextafter(1.0, np.inf), True, False),
            (np.nextafter(2.0, 0.0), True, False),
            (2.0, True, False),
            (np.nextafter(2.0, np.inf), False, False),
        )

        for distance, expected_edge, expected_short_qc in cases:
            with self.subTest(distance=distance):
                graph = build_first_shell_graph(
                    np.asarray(((0.0, 0.0), (distance, 0.0))),
                    point_ids=("point-a", "point-b"),
                    settings=settings,
                )
                self.assertEqual(graph.edges_ij == ((0, 1),), expected_edge)
                self.assertEqual(
                    graph.short_non_shell_pair_qc,
                    (expected_short_qc, expected_short_qc),
                )
                self.assertEqual(
                    graph.degree,
                    (1, 1) if expected_edge else (0, 0),
                )
                self.assertEqual(graph.candidate_edges_ij, ((0, 1),))

    def test_disabled_physical_duplicate_threshold_does_not_classify_pair_as_duplicate(self) -> None:
        graph = build_first_shell_graph(
            np.asarray(((0.0, 0.0), (0.5, 0.0), (1.5, 0.0))),
            point_ids=("point-a", "point-b", "point-c"),
            settings=MolecularM6OrientationAnalysisSettings(
                duplicate_detection_enabled=False,
                duplicate_max_distance_nm=0.5,
                first_shell_r_min_nm=1.0,
                first_shell_r_max_nm=2.0,
                geometry_absolute_tolerance_nm=0.01,
                geometry_relative_tolerance=1e-12,
            ),
        )

        self.assertFalse(graph.duplicate_detection_enabled)
        self.assertEqual(graph.physical_duplicate_qc, (False, False, False))
        self.assertEqual(graph.geometry_duplicate_qc, (False, False, False))
        self.assertEqual(graph.short_non_shell_pair_qc, (True, True, False))
        self.assertEqual(graph.candidate_edges_ij, ((0, 1), (1, 2)))
        self.assertEqual(graph.edges_ij, ((1, 2),))
        self.assertEqual(graph.degree, (0, 1, 1))

    def test_builds_rank_zero_and_two_point_graph_without_mutating_input(self) -> None:
        settings = MolecularM6OrientationAnalysisSettings(
            geometry_absolute_tolerance_nm=1e-6,
            geometry_relative_tolerance=1e-3,
            duplicate_max_distance_nm=0.5,
            first_shell_r_min_nm=1.0,
            first_shell_r_max_nm=2.6,
        )
        points = np.asarray(((0.0, 0.0), (1.5, 0.0)), dtype=np.float64)
        original = points.copy()

        graph = build_first_shell_graph(points, settings=settings)

        np.testing.assert_array_equal(points, original)
        self.assertEqual(graph.point_ids, ("point-0", "point-1"))
        self.assertEqual(graph.point_count, 2)
        self.assertEqual(graph.edges_ij, ((0, 1),))
        self.assertEqual(graph.distances_nm, (1.5,))
        self.assertEqual(graph.degree, (1, 1))
        self.assertEqual(graph.construction_method, "rank1_adjacent_projection")
        self.assertAlmostEqual(graph.geometry_collision_epsilon_nm, 0.0026)

        for small_points, expected_ids in (
            (np.empty((0, 2), dtype=np.float64), ()),
            (np.asarray(((4.0, 5.0),), dtype=np.float64), ("point-0",)),
        ):
            with self.subTest(point_count=len(small_points)):
                small_graph = build_first_shell_graph(small_points, settings=settings)
                self.assertEqual(small_graph.point_ids, expected_ids)
                self.assertEqual(small_graph.edges_ij, ())
                self.assertEqual(small_graph.degree, (0,) * len(small_points))
                self.assertEqual(small_graph.construction_method, "rank0_empty")

        for invalid_points in (
            np.asarray((0.0, 1.0)),
            np.zeros((2, 3), dtype=np.float64),
            np.asarray(((0.0, np.nan),), dtype=np.float64),
        ):
            with self.subTest(shape=invalid_points.shape):
                with self.assertRaises(ValueError):
                    build_first_shell_graph(invalid_points, settings=settings)

    def test_rank_one_connects_only_adjacent_projections(self) -> None:
        settings = MolecularM6OrientationAnalysisSettings(
            duplicate_detection_enabled=False,
            first_shell_r_min_nm=1.0,
            first_shell_r_max_nm=3.0,
            geometry_relative_tolerance=1e-9,
        )
        points = np.asarray(((2.4, 1e-12), (0.0, 0.0), (1.2, -1e-12)))
        point_ids = ("point-c", "point-a", "point-b")

        graph = build_first_shell_graph(points, point_ids=point_ids, settings=settings)

        edge_ids = {
            frozenset((graph.point_ids[i], graph.point_ids[j]))
            for i, j in graph.edges_ij
        }
        self.assertEqual(
            edge_ids,
            {frozenset(("point-a", "point-b")), frozenset(("point-b", "point-c"))},
        )
        self.assertNotIn(frozenset(("point-a", "point-c")), edge_ids)
        self.assertEqual(graph.construction_method, "rank1_adjacent_projection")

        rank_two_graph = build_first_shell_graph(
            np.asarray(((0.0, 0.0), (1.0, 1e-5), (2.0, 0.0))),
            point_ids=("point-a", "point-b", "point-c"),
            settings=settings,
        )
        self.assertEqual(rank_two_graph.construction_method, "delaunay_first_shell")
        self.assertEqual(len(rank_two_graph.edges_ij), 3)

    def test_geometry_collisions_are_deduplicated_when_physical_detection_is_disabled(self) -> None:
        settings = MolecularM6OrientationAnalysisSettings(
            duplicate_detection_enabled=False,
            geometry_absolute_tolerance_nm=0.01,
            geometry_relative_tolerance=1e-12,
            duplicate_max_distance_nm=0.5,
            first_shell_r_min_nm=1.0,
            first_shell_r_max_nm=2.6,
        )
        points = np.asarray(((0.0, 0.0), (0.005, 0.0), (1.5, 0.0)))

        graph = build_first_shell_graph(
            points,
            point_ids=("point-b", "point-a", "point-c"),
            settings=settings,
        )

        self.assertEqual(graph.geometry_duplicate_qc, (True, False, False))
        self.assertEqual(graph.physical_duplicate_qc, (False, False, False))
        self.assertEqual(
            graph.representative_source_ids,
            ("point-a", "point-a", "point-c"),
        )
        self.assertEqual(graph.degree, (0, 1, 1))
        self.assertEqual(graph.edges_ij, ((1, 2),))
        self.assertEqual(graph.duplicate_group_diameters_nm[:2], (0.005, 0.005))

        wide_geometry_settings = MolecularM6OrientationAnalysisSettings(
            duplicate_detection_enabled=False,
            geometry_absolute_tolerance_nm=0.6,
            geometry_relative_tolerance=1e-12,
            duplicate_max_distance_nm=0.5,
            first_shell_r_min_nm=1.0,
            first_shell_r_max_nm=2.6,
        )
        wide_geometry_graph = build_first_shell_graph(
            np.asarray(((0.0, 0.0), (0.55, 0.0), (1.8, 0.0))),
            point_ids=("point-a", "point-b", "point-c"),
            settings=wide_geometry_settings,
        )
        self.assertEqual(wide_geometry_graph.geometry_duplicate_qc, (False, True, False))
        self.assertEqual(wide_geometry_graph.duplicate_chain_qc, (False, False, False))
        self.assertEqual(wide_geometry_graph.duplicate_group_diameters_nm[:2], (0.55, 0.55))

    def test_geometry_collision_epsilon_is_inclusive_and_scale_validated(self) -> None:
        epsilon = 0.01
        settings = MolecularM6OrientationAnalysisSettings(
            duplicate_detection_enabled=False,
            geometry_absolute_tolerance_nm=epsilon,
            geometry_relative_tolerance=1e-12,
            first_shell_r_min_nm=1.0,
            first_shell_r_max_nm=2.6,
        )
        for distance, expected_duplicate in (
            (0.0, True),
            (np.nextafter(epsilon, 0.0), True),
            (epsilon, True),
            (np.nextafter(epsilon, np.inf), False),
        ):
            with self.subTest(distance=distance):
                graph = build_first_shell_graph(
                    np.asarray(((0.0, 0.0), (distance, 0.0), (1.5, 0.0))),
                    point_ids=("point-a", "point-b", "point-c"),
                    settings=settings,
                )
                self.assertEqual(graph.geometry_duplicate_qc[1], expected_duplicate)
                self.assertEqual(
                    graph.short_non_shell_pair_qc[1],
                    not expected_duplicate,
                )

        invalid_scale_settings = MolecularM6OrientationAnalysisSettings(
            geometry_absolute_tolerance_nm=1e-6,
            geometry_relative_tolerance=0.1,
            duplicate_max_distance_nm=0.2,
            first_shell_r_min_nm=1.0,
            first_shell_r_max_nm=2.6,
        )
        with self.assertRaisesRegex(ValueError, "geometry_collision_epsilon_nm"):
            build_first_shell_graph(
                np.asarray(((0.0, 0.0), (1.5, 0.0))),
                settings=invalid_scale_settings,
            )

        disabled_overlap_settings = MolecularM6OrientationAnalysisSettings(
            duplicate_detection_enabled=False,
            geometry_absolute_tolerance_nm=1.0,
            geometry_relative_tolerance=1e-12,
            first_shell_r_min_nm=1.0,
            first_shell_r_max_nm=2.6,
        )
        with self.assertRaisesRegex(ValueError, "geometry_collision_epsilon_nm"):
            build_first_shell_graph(
                np.asarray(((0.0, 0.0), (1.5, 0.0))),
                settings=disabled_overlap_settings,
            )

    def test_geometry_collision_chain_leaves_no_colliding_representatives(self) -> None:
        settings = MolecularM6OrientationAnalysisSettings(
            duplicate_detection_enabled=False,
            geometry_absolute_tolerance_nm=0.1,
            geometry_relative_tolerance=1e-12,
            first_shell_r_min_nm=1.0,
            first_shell_r_max_nm=2.6,
        )
        graph = build_first_shell_graph(
            np.asarray(((0.0, 0.0), (0.09, 0.0), (0.18, 0.0), (1.5, 0.0))),
            point_ids=("point-a", "point-b", "point-c", "point-d"),
            settings=settings,
            segmentation_quality_scores=(0.1, 0.9, 0.2, None),
        )

        self.assertEqual(
            graph.representative_source_ids[:3],
            ("point-b", "point-b", "point-b"),
        )
        self.assertEqual(graph.geometry_duplicate_qc[:3], (True, False, True))
        self.assertEqual(graph.degree, (0, 1, 0, 1))

    def test_physical_duplicate_threshold_is_inclusive(self) -> None:
        threshold = 0.5
        settings = MolecularM6OrientationAnalysisSettings(
            duplicate_max_distance_nm=threshold,
            first_shell_r_min_nm=1.0,
            first_shell_r_max_nm=2.6,
        )
        for distance, expected_duplicate in (
            (np.nextafter(threshold, 0.0), True),
            (threshold, True),
            (np.nextafter(threshold, np.inf), False),
        ):
            with self.subTest(distance=distance):
                graph = build_first_shell_graph(
                    np.asarray(((0.0, 0.0), (distance, 0.0), (1.5, 0.0))),
                    point_ids=("point-a", "point-b", "point-c"),
                    settings=settings,
                )
                self.assertEqual(graph.physical_duplicate_qc[1], expected_duplicate)
                self.assertEqual(
                    graph.short_non_shell_pair_qc[1],
                    not expected_duplicate,
                )

    def test_physical_duplicate_chain_uses_complete_linkage_and_quality_representative(self) -> None:
        settings = MolecularM6OrientationAnalysisSettings(
            duplicate_max_distance_nm=0.3,
            first_shell_r_min_nm=1.0,
            first_shell_r_max_nm=2.6,
        )
        points = np.asarray(((0.0, 0.0), (0.25, 0.0), (0.5, 0.0), (1.5, 0.0)))

        graph = build_first_shell_graph(
            points,
            point_ids=("point-a", "point-b", "point-c", "point-d"),
            settings=settings,
            mask_blocking_qc=(False, False, False, False),
            segmentation_quality_scores=(0.2, 0.9, None, None),
            topography_peak_matches=(None, None, None, None),
            detection_confidences=(0.8, 0.7, 0.6, 0.5),
        )

        self.assertEqual(
            graph.representative_source_ids,
            ("point-b", "point-b", "point-c", "point-d"),
        )
        self.assertEqual(graph.physical_duplicate_qc, (True, False, False, False))
        self.assertEqual(graph.geometry_duplicate_qc, (False, False, False, False))
        self.assertEqual(graph.duplicate_chain_qc, (True, True, True, False))
        self.assertEqual(graph.duplicate_parent_component_diameters_nm[:3], (0.5,) * 3)
        self.assertEqual(graph.duplicate_group_diameters_nm[:3], (0.25, 0.25, 0.0))
        self.assertEqual(graph.duplicate_group_ids[0], graph.duplicate_group_ids[1])
        self.assertNotEqual(graph.duplicate_group_ids[1], graph.duplicate_group_ids[2])
        self.assertEqual(graph.edges_ij, ((2, 3),))
        self.assertEqual(graph.degree, (0, 0, 1, 1))

    def test_representative_quality_order_is_deterministic(self) -> None:
        settings = MolecularM6OrientationAnalysisSettings(
            duplicate_max_distance_nm=0.2,
            first_shell_r_min_nm=1.0,
            first_shell_r_max_nm=2.6,
        )
        cases = (
            ({}, "point-a"),
            ({"mask_blocking_qc": (False, True, False)}, "point-z"),
            ({"segmentation_quality_scores": (0.2, 0.9, None)}, "point-a"),
            (
                {
                    "segmentation_quality_scores": (0.5, 0.5, None),
                    "topography_peak_matches": (True, None, None),
                },
                "point-z",
            ),
            (
                {
                    "segmentation_quality_scores": (0.5, 0.5, None),
                    "topography_peak_matches": (True, True, None),
                    "detection_confidences": (0.1, 0.9, None),
                },
                "point-a",
            ),
        )
        for quality, expected_representative in cases:
            with self.subTest(quality=quality):
                graph = build_first_shell_graph(
                    np.asarray(((0.0, 0.0), (0.1, 0.0), (1.5, 0.0))),
                    point_ids=("point-z", "point-a", "point-c"),
                    settings=settings,
                    **quality,
                )
                self.assertEqual(graph.representative_source_ids[0], expected_representative)
                self.assertEqual(graph.representative_source_ids[1], expected_representative)

    def test_duplicate_result_is_invariant_to_permutation_and_translation(self) -> None:
        settings = MolecularM6OrientationAnalysisSettings(
            duplicate_max_distance_nm=0.3,
            first_shell_r_min_nm=1.0,
            first_shell_r_max_nm=2.6,
        )
        points = np.asarray(((0.0, 0.0), (0.25, 0.0), (0.5, 0.0), (1.5, 0.0)))
        point_ids = np.asarray(("point-a", "point-b", "point-c", "point-d"), dtype=object)
        quality = np.asarray((0.2, 0.9, np.nan, np.nan))

        def snapshot(order: np.ndarray, translated: bool) -> tuple[object, ...]:
            ordered_points = points[order].copy()
            if translated:
                ordered_points += np.asarray((1000.0, -2000.0))
            ordered_quality = tuple(
                None if np.isnan(quality[index]) else float(quality[index])
                for index in order
            )
            graph = build_first_shell_graph(
                ordered_points,
                point_ids=tuple(str(point_ids[index]) for index in order),
                settings=settings,
                segmentation_quality_scores=ordered_quality,
            )
            per_point = {
                point_id: (
                    graph.representative_source_ids[index],
                    graph.duplicate_parent_component_ids[index],
                    graph.duplicate_parent_component_diameters_nm[index],
                    graph.duplicate_group_ids[index],
                    graph.duplicate_group_diameters_nm[index],
                    graph.duplicate_chain_qc[index],
                    graph.physical_duplicate_qc[index],
                    graph.geometry_duplicate_qc[index],
                )
                for index, point_id in enumerate(graph.point_ids)
            }
            edges = {
                frozenset((graph.point_ids[i], graph.point_ids[j]))
                for i, j in graph.edges_ij
            }
            return per_point, edges, graph.geometry_collision_epsilon_nm

        baseline = snapshot(np.arange(4), False)
        permuted = snapshot(np.asarray((2, 0, 3, 1)), True)
        self.assertEqual(permuted[0], baseline[0])
        self.assertEqual(permuted[1], baseline[1])
        self.assertAlmostEqual(permuted[2], baseline[2])

    def test_generated_point_ids_keep_duplicate_partition_permutation_invariant(self) -> None:
        settings = MolecularM6OrientationAnalysisSettings(
            duplicate_max_distance_nm=0.3,
            first_shell_r_min_nm=1.0,
            first_shell_r_max_nm=2.6,
        )
        points = np.asarray(((0.0, 0.0), (0.25, 0.0), (0.5, 0.0), (1.5, 0.0)))

        def grouped_coordinates(order: np.ndarray) -> set[frozenset[tuple[float, float]]]:
            ordered = points[order]
            graph = build_first_shell_graph(ordered, settings=settings)
            groups: dict[str, set[tuple[float, float]]] = {}
            for index, group_id in enumerate(graph.duplicate_group_ids):
                if group_id is not None:
                    groups.setdefault(group_id, set()).add(tuple(ordered[index]))
            return {frozenset(group) for group in groups.values()}

        self.assertEqual(
            grouped_coordinates(np.arange(4)),
            grouped_coordinates(np.asarray((3, 2, 1, 0))),
        )

    def test_component_ids_encode_source_ids_without_delimiter_collisions(self) -> None:
        graph = build_first_shell_graph(
            np.asarray(((0.0, 0.0), (0.1, 0.0), (2.0, 0.0), (2.1, 0.0))),
            point_ids=("a|b", "c", "a", "b|c"),
            settings=MolecularM6OrientationAnalysisSettings(
                duplicate_max_distance_nm=0.2,
                first_shell_r_min_nm=1.0,
                first_shell_r_max_nm=2.6,
            ),
        )
        self.assertNotEqual(graph.duplicate_group_ids[0], graph.duplicate_group_ids[2])

    def test_rank_two_uses_delaunay_natural_neighbors_and_is_permutation_invariant(self) -> None:
        settings = MolecularM6OrientationAnalysisSettings(
            duplicate_max_distance_nm=0.2,
            first_shell_r_min_nm=0.3,
            first_shell_r_max_nm=3.0,
        )
        points = np.asarray(
            ((0.0, 0.0), (2.0, 0.0), (2.0, 2.0), (0.0, 2.0), (1.0, 1.0))
        )
        point_ids = ("bottom-left", "bottom-right", "top-right", "top-left", "center")
        expected_edges = {
            frozenset(pair)
            for pair in (
                ("bottom-left", "bottom-right"),
                ("bottom-right", "top-right"),
                ("top-right", "top-left"),
                ("top-left", "bottom-left"),
                ("center", "bottom-left"),
                ("center", "bottom-right"),
                ("center", "top-right"),
                ("center", "top-left"),
            )
        }

        for order in (
            np.arange(5),
            np.asarray((4, 2, 0, 3, 1)),
            np.asarray((1, 3, 2, 4, 0)),
        ):
            with self.subTest(order=tuple(order)):
                graph = build_first_shell_graph(
                    points[order],
                    point_ids=tuple(point_ids[index] for index in order),
                    settings=settings,
                )
                edge_ids = {
                    frozenset((graph.point_ids[i], graph.point_ids[j]))
                    for i, j in graph.edges_ij
                }
                self.assertEqual(edge_ids, expected_edges)
                self.assertEqual(len(graph.edges_ij), 8)
                self.assertEqual(graph.construction_method, "delaunay_first_shell")

        long_edge_graph = build_first_shell_graph(
            np.asarray(((0.0, 0.0), (1.5, 0.0), (0.0, 1.5), (5.0, 5.0))),
            point_ids=("a", "b", "c", "far"),
            settings=MolecularM6OrientationAnalysisSettings(
                duplicate_max_distance_nm=0.2,
                first_shell_r_min_nm=0.3,
                first_shell_r_max_nm=2.6,
            ),
        )
        self.assertGreater(len(long_edge_graph.candidate_edges_ij), len(long_edge_graph.edges_ij))
        self.assertTrue(
            any(distance > 2.6 for distance in long_edge_graph.candidate_distances_nm)
        )

    def test_cocircular_delaunay_diagonal_is_marked_ambiguous_and_excluded(self) -> None:
        settings = MolecularM6OrientationAnalysisSettings(
            duplicate_max_distance_nm=0.1,
            first_shell_r_min_nm=0.2,
            first_shell_r_max_nm=2.0,
        )
        points = np.asarray(((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)))
        point_ids = ("bottom-left", "bottom-right", "top-right", "top-left")

        baseline_ambiguous_ids: set[frozenset[str]] | None = None
        for order in (np.arange(4), np.asarray((2, 0, 3, 1))):
            graph = build_first_shell_graph(
                points[order],
                point_ids=tuple(point_ids[index] for index in order),
                settings=settings,
            )

            edge_ids = {
                frozenset((graph.point_ids[i], graph.point_ids[j]))
                for i, j in graph.edges_ij
            }
            ambiguous_ids = {
                frozenset((graph.point_ids[i], graph.point_ids[j]))
                for i, j in graph.ambiguous_edges_ij
            }
            self.assertEqual(
                edge_ids,
                {
                    frozenset(("bottom-left", "bottom-right")),
                    frozenset(("bottom-right", "top-right")),
                    frozenset(("top-right", "top-left")),
                    frozenset(("top-left", "bottom-left")),
                },
            )
            self.assertEqual(len(ambiguous_ids), 1)
            self.assertTrue(graph.delaunay_degeneracy_qc)
            self.assertEqual(graph.degree, (2, 2, 2, 2))
            if baseline_ambiguous_ids is None:
                baseline_ambiguous_ids = ambiguous_ids
            else:
                self.assertEqual(ambiguous_ids, baseline_ambiguous_ids)

    def test_rank_two_qhull_error_uses_explicit_blocking_radius_fallback(self) -> None:
        settings = MolecularM6OrientationAnalysisSettings(
            duplicate_max_distance_nm=0.1,
            first_shell_r_min_nm=0.2,
            first_shell_r_max_nm=3.0,
        )
        points = np.asarray(
            ((0.0, 0.0), (2.0, 0.0), (2.0, 2.0), (0.0, 2.0), (1.0, 1.0))
        )

        with patch(
            "moltrack.analysis.first_shell_builder.Delaunay",
            side_effect=QhullError("forced rank-2 failure"),
        ):
            graph = build_first_shell_graph(points, settings=settings)

        self.assertEqual(graph.construction_method, "rank2_radius_fallback")
        self.assertEqual(graph.qc_status, "blocking_rank2_radius_fallback")
        self.assertEqual(len(graph.edges_ij), 10)
        self.assertFalse(graph.delaunay_degeneracy_qc)
        self.assertEqual(graph.ambiguous_edges_ij, ())

    def test_invalid_positions_remain_in_graph_without_edges_or_duplicate_qc(self) -> None:
        graph = build_first_shell_graph(
            np.asarray(((0.0, 0.0), (0.05, 0.0), (1.0, 0.0))),
            point_ids=("valid-a", "invalid-padding", "valid-b"),
            invalid_position_qc=(False, True, False),
            settings=MolecularM6OrientationAnalysisSettings(
                duplicate_max_distance_nm=0.2,
                first_shell_r_min_nm=0.5,
                first_shell_r_max_nm=1.5,
            ),
        )

        self.assertEqual(
            graph.point_ids,
            ("valid-a", "invalid-padding", "valid-b"),
        )
        self.assertEqual(graph.edges_ij, ((0, 2),))
        self.assertEqual(graph.degree, (1, 0, 1))
        self.assertEqual(
            graph.representative_source_ids,
            graph.point_ids,
        )
        self.assertEqual(graph.physical_duplicate_qc, (False, False, False))
        self.assertEqual(graph.geometry_duplicate_qc, (False, False, False))


if __name__ == "__main__":
    unittest.main()
