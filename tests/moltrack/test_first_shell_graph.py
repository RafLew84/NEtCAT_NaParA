import math
import unittest
from dataclasses import FrozenInstanceError

from moltrack.analysis import FirstShellGraph


def _graph(**overrides: object) -> FirstShellGraph:
    payload: dict[str, object] = {
        "point_ids": ("point-a", "point-b", "point-c"),
        "point_count": 3,
        "edges_ij": ((0, 1), (1, 2)),
        "distances_nm": (1.25, 1.5),
        "angles_rad": (0.0, math.pi / 2.0),
        "degree": (1, 2, 1),
        "geometry_collision_epsilon_nm": 1e-12,
        "duplicate_max_distance_nm": 0.5,
        "first_shell_r_min_nm": 1.0,
        "first_shell_r_max_nm": 2.6,
        "coordinate_frame": "sample_nm",
        "orientation_reference": "+x_sample_axis",
        "spatial_calibration_fingerprint": "calibration-v1",
        "registration_fingerprint": "registration-v1",
        "construction_method": "delaunay_first_shell",
        "qc_status": "valid",
    }
    payload.update(overrides)
    return FirstShellGraph(**payload)


class FirstShellGraphTests(unittest.TestCase):
    def test_canonicalizes_valid_graph_and_exposes_directed_neighbors(self) -> None:
        graph = _graph(
            edges_ij=((1, 2), (0, 1)),
            distances_nm=(1.5, 1.25),
            angles_rad=(math.pi / 2.0, 0.0),
        )

        self.assertEqual(graph.edges_ij, ((0, 1), (1, 2)))
        self.assertEqual(graph.distances_nm, (1.25, 1.5))
        self.assertEqual(graph.angles_rad, (0.0, math.pi / 2.0))
        self.assertEqual(graph.neighbors_for_point(1), (0, 2))
        self.assertEqual(graph.neighbors_for_point("point-b"), (0, 2))
        self.assertEqual(graph.directed_angle_rad(0, 1), 0.0)
        self.assertEqual(graph.directed_angle_rad(1, 0), math.pi)

        with self.assertRaises(FrozenInstanceError):
            graph.point_count = 4

    def test_rejects_inconsistent_edge_and_degree_data(self) -> None:
        invalid_payloads = (
            {"point_count": 2},
            {"point_ids": ("point-a", "point-a", "point-c")},
            {"edges_ij": ((0, 1),), "degree": (1, 1, 0)},
            {"distances_nm": (1.25,)},
            {"angles_rad": (0.0,)},
            {"edges_ij": ((0, 1, 2), (1, 2))},
            {"edges_ij": ((1, 0), (1, 2))},
            {"edges_ij": ((0, 3), (1, 2))},
            {"edges_ij": ((0, 1), (0, 1)), "degree": (2, 2, 0)},
            {"distances_nm": (0.0, 1.5)},
            {"distances_nm": (math.inf, 1.5)},
            {"distances_nm": (0.9, 1.5)},
            {"distances_nm": (1.25, 2.7)},
            {"angles_rad": (math.nan, math.pi / 2.0)},
            {"degree": (1, 2)},
            {"degree": (1, -2, 1)},
            {"degree": (2, 1, 1)},
        )

        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                with self.assertRaises((TypeError, ValueError)):
                    _graph(**payload)

    def test_preserves_complete_duplicate_groups_and_rejects_inconsistent_metadata(self) -> None:
        graph = _graph(
            edges_ij=((0, 2),),
            distances_nm=(1.5,),
            angles_rad=(0.0,),
            degree=(1, 0, 1),
            representative_source_ids=("point-a", "point-a", "point-c"),
            duplicate_parent_component_ids=("parent-1", "parent-1", None),
            duplicate_parent_component_diameters_nm=(0.3, 0.3, None),
            duplicate_group_ids=("group-1", "group-1", None),
            duplicate_group_diameters_nm=(0.3, 0.3, None),
            duplicate_chain_qc=(False, False, False),
            physical_duplicate_qc=(False, True, False),
            geometry_duplicate_qc=(False, False, False),
        )

        self.assertEqual(graph.representative_source_ids[1], "point-a")
        self.assertEqual(graph.duplicate_group_ids[:2], ("group-1", "group-1"))
        self.assertEqual(graph.duplicate_group_diameters_nm[:2], (0.3, 0.3))
        self.assertEqual(graph.degree[1], 0)
        self.assertTrue(graph.physical_duplicate_qc[1])

        invalid_payloads = (
            {"representative_source_ids": ("point-a",)},
            {"physical_duplicate_qc": (False, True)},
            {"representative_source_ids": ("missing", "point-b", "point-c")},
            {
                "physical_duplicate_qc": (False, True, False),
                "geometry_duplicate_qc": (False, True, False),
            },
            {
                "physical_duplicate_qc": (True, False, False),
                "representative_source_ids": ("point-a", "point-b", "point-c"),
            },
            {
                "physical_duplicate_qc": (False, True, False),
                "representative_source_ids": ("point-a", "point-a", "point-c"),
                "duplicate_group_ids": (None, None, None),
            },
            {
                "duplicate_group_ids": ("group-1", "group-1", None),
                "duplicate_group_diameters_nm": (0.3, 0.4, None),
            },
            {
                "duplicate_group_ids": ("group-1", "group-1", None),
                "duplicate_group_diameters_nm": (0.3, 0.3, None),
                "representative_source_ids": ("point-a", "point-b", "point-c"),
            },
            {
                "edges_ij": ((0, 2),),
                "distances_nm": (1.5,),
                "angles_rad": (0.0,),
                "degree": (1, 0, 1),
                "duplicate_parent_component_ids": ("parent-1", "parent-2", None),
                "duplicate_parent_component_diameters_nm": (0.4, 0.4, None),
                "duplicate_group_ids": ("group-1", "group-1", None),
                "duplicate_group_diameters_nm": (0.3, 0.3, None),
                "representative_source_ids": ("point-a", "point-a", "point-c"),
                "physical_duplicate_qc": (False, True, False),
            },
            {
                "edges_ij": ((0, 2),),
                "distances_nm": (1.5,),
                "angles_rad": (0.0,),
                "degree": (1, 0, 1),
                "duplicate_parent_component_ids": ("parent-1", "parent-1", None),
                "duplicate_parent_component_diameters_nm": (0.2, 0.2, None),
                "duplicate_group_ids": ("group-1", "group-1", None),
                "duplicate_group_diameters_nm": (0.3, 0.3, None),
                "representative_source_ids": ("point-a", "point-a", "point-c"),
                "physical_duplicate_qc": (False, True, False),
            },
            {
                "duplicate_group_ids": ("group-1", None, None),
                "duplicate_group_diameters_nm": (None, None, None),
            },
            {
                "duplicate_parent_component_ids": ("parent-1", "parent-1", None),
                "duplicate_parent_component_diameters_nm": (0.6, 0.6, None),
                "duplicate_chain_qc": (False, False, False),
            },
            {"duplicate_chain_qc": (True, False, False)},
            {
                "physical_duplicate_qc": (False, True, False),
                "representative_source_ids": ("point-a", "point-a", "point-c"),
                "duplicate_group_ids": ("group-1", "group-1", None),
                "duplicate_group_diameters_nm": (0.3, 0.3, None),
            },
        )

        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                with self.assertRaises((TypeError, ValueError)):
                    _graph(**payload)

    def test_preserves_geometry_duplicates_and_split_chain_groups(self) -> None:
        geometry_duplicate = _graph(
            edges_ij=((0, 2),),
            distances_nm=(1.5,),
            angles_rad=(0.0,),
            degree=(1, 0, 1),
            representative_source_ids=("point-a", "point-a", "point-c"),
            duplicate_parent_component_ids=("parent-1", "parent-1", None),
            duplicate_parent_component_diameters_nm=(0.0, 0.0, None),
            duplicate_group_ids=("group-1", "group-1", None),
            duplicate_group_diameters_nm=(0.0, 0.0, None),
            geometry_duplicate_qc=(False, True, False),
        )
        self.assertTrue(geometry_duplicate.geometry_duplicate_qc[1])
        self.assertFalse(geometry_duplicate.physical_duplicate_qc[1])

        split_chain = _graph(
            edges_ij=((0, 2),),
            distances_nm=(1.5,),
            angles_rad=(0.0,),
            degree=(1, 0, 1),
            representative_source_ids=("point-a", "point-a", "point-c"),
            duplicate_parent_component_ids=("parent-1", "parent-1", "parent-1"),
            duplicate_parent_component_diameters_nm=(0.8, 0.8, 0.8),
            duplicate_group_ids=("group-1", "group-1", "group-2"),
            duplicate_group_diameters_nm=(0.4, 0.4, 0.0),
            duplicate_chain_qc=(True, True, True),
            physical_duplicate_qc=(False, True, False),
        )
        self.assertEqual(split_chain.duplicate_group_ids, ("group-1", "group-1", "group-2"))
        self.assertEqual(split_chain.duplicate_parent_component_ids, ("parent-1",) * 3)
        self.assertEqual(split_chain.representative_source_ids, ("point-a", "point-a", "point-c"))

    def test_rejects_invalid_physical_context_and_provenance(self) -> None:
        invalid_payloads = (
            {"geometry_collision_epsilon_nm": 0.0},
            {"geometry_collision_epsilon_nm": math.inf},
            {"duplicate_max_distance_nm": 0.0},
            {"first_shell_r_min_nm": 0.0},
            {"first_shell_r_max_nm": 0.0},
            {"first_shell_r_min_nm": 2.6, "first_shell_r_max_nm": 2.6},
            {"coordinate_frame": "image_px"},
            {"orientation_reference": ""},
            {"orientation_reference": "screen_x_axis"},
            {"spatial_calibration_fingerprint": ""},
            {"registration_fingerprint": ""},
            {"construction_method": ""},
            {"construction_method": "unknown_builder"},
            {"qc_status": ""},
        )

        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                with self.assertRaises((TypeError, ValueError)):
                    _graph(**payload)

        assumed_reference = _graph(
            orientation_reference="scan_x_axis_assumed_sample_x",
            construction_method="rank2_radius_fallback",
            qc_status="blocking_fallback_qc",
        )
        self.assertEqual(
            assumed_reference.orientation_reference,
            "scan_x_axis_assumed_sample_x",
        )

    def test_represents_empty_single_and_two_point_shell_cases(self) -> None:
        empty = _graph(
            point_ids=(),
            point_count=0,
            edges_ij=(),
            distances_nm=(),
            angles_rad=(),
            degree=(),
            construction_method="rank0_empty",
        )
        single = _graph(
            point_ids=("point-a",),
            point_count=1,
            edges_ij=(),
            distances_nm=(),
            angles_rad=(),
            degree=(0,),
            construction_method="rank0_empty",
        )

        self.assertEqual(empty.edges_ij, ())
        self.assertEqual(single.neighbors_for_point(0), ())
        self.assertEqual(single.representative_source_ids, ("point-a",))

        for distance, angle, expected_angle in (
            (1.0, 2.0 * math.pi, 0.0),
            (2.6, -math.pi / 2.0, 3.0 * math.pi / 2.0),
        ):
            with self.subTest(distance=distance):
                graph = _graph(
                    point_ids=("point-a", "point-b"),
                    point_count=2,
                    edges_ij=((0, 1),),
                    distances_nm=(distance,),
                    angles_rad=(angle,),
                    degree=(1, 1),
                    construction_method="rank1_adjacent_projection",
                )
                self.assertEqual(graph.edges_ij, ((0, 1),))
                self.assertAlmostEqual(graph.angles_rad[0], expected_angle)

        for distance in (0.99, 2.61):
            with self.subTest(excluded_distance=distance):
                with self.assertRaises(ValueError):
                    _graph(
                        point_ids=("point-a", "point-b"),
                        point_count=2,
                        edges_ij=((0, 1),),
                        distances_nm=(distance,),
                        angles_rad=(0.0,),
                        degree=(1, 1),
                    )
                no_shell_edge = _graph(
                    point_ids=("point-a", "point-b"),
                    point_count=2,
                    edges_ij=(),
                    distances_nm=(),
                    angles_rad=(),
                    degree=(0, 0),
                    construction_method="rank1_adjacent_projection",
                )
                self.assertEqual(no_shell_edge.edges_ij, ())


if __name__ == "__main__":
    unittest.main()
