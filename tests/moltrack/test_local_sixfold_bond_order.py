import math
import unittest
from dataclasses import FrozenInstanceError

from moltrack.analysis import LocalSixfoldBondOrderField


def _field(**overrides: object) -> LocalSixfoldBondOrderField:
    payload: dict[str, object] = {
        "source_ids": ("molecule-a", "molecule-b", "molecule-c", "molecule-d"),
        "point_count": 4,
        "psi6": (0.5 + 0.5j, 0.0j, None, None),
        "q6": (math.sqrt(0.5), 0.0, None, None),
        "lattice_orientation_deg": (61.0, None, None, None),
        "orientation_status": (
            "defined",
            "undefined_zero_magnitude",
            "not_available",
            "not_available",
        ),
        "neighbor_count": (4, 3, 2, 0),
        "computation_status": (
            "valid_order",
            "valid_order",
            "insufficient_neighbors",
            "duplicate_excluded",
        ),
        "local_median_bond_length_nm": (1.5, 1.6, 1.7, None),
        "local_bond_length_mad_nm": (0.1, 0.2, 0.0, None),
        "local_bond_length_iqr_nm": (0.2, 0.3, 0.0, None),
        "local_bond_length_robust_cv": (0.1, 0.2, 0.0, None),
        "physical_duplicate_qc": (False, False, False, True),
        "geometry_duplicate_qc": (False, False, False, False),
        "edge_truncated_neighborhood": (True, False, False, False),
        "distance_to_valid_fov_boundary_nm": (1.0, 4.0, 4.0, 4.0),
        "first_shell_r_max_nm": 2.6,
        "coordinate_frame": "sample_nm",
        "orientation_reference": "+x_sample_axis",
        "spatial_calibration_fingerprint": "calibration-v1",
        "registration_fingerprint": "registration-v1",
    }
    payload.update(overrides)
    return LocalSixfoldBondOrderField(**payload)


class LocalSixfoldBondOrderFieldTests(unittest.TestCase):
    def test_preserves_source_order_constants_provenance_and_is_immutable(self) -> None:
        field = _field()

        self.assertEqual(field.source_ids, ("molecule-a", "molecule-b", "molecule-c", "molecule-d"))
        self.assertEqual(field.index_for_source_id("molecule-c"), 2)
        self.assertEqual(field.min_neighbors_for_local_order, 3)
        self.assertEqual(field.symmetry_m, 6)
        self.assertEqual(field.bond_weighting, "uniform")
        self.assertEqual(field.coordinate_frame, "sample_nm")
        self.assertEqual(field.orientation_reference, "+x_sample_axis")
        self.assertEqual(field.spatial_calibration_fingerprint, "calibration-v1")
        self.assertEqual(field.registration_fingerprint, "registration-v1")

        with self.assertRaises(KeyError):
            field.index_for_source_id("missing")
        with self.assertRaises(FrozenInstanceError):
            field.point_count = 5

    def test_normalizes_defined_m6_orientation_to_one_period(self) -> None:
        field = _field(
            psi6=(1.0 + 0.0j, 1.0 + 0.0j, 1.0 + 0.0j, 1.0 + 0.0j),
            q6=(1.0, 1.0, 1.0, 1.0),
            lattice_orientation_deg=(-1.0, 0.0, 60.0, 121.0),
            orientation_status=("defined",) * 4,
            neighbor_count=(3, 3, 3, 3),
            computation_status=("valid_order",) * 4,
            local_median_bond_length_nm=(1.5,) * 4,
            local_bond_length_mad_nm=(0.0,) * 4,
            local_bond_length_iqr_nm=(0.0,) * 4,
            local_bond_length_robust_cv=(0.0,) * 4,
            physical_duplicate_qc=(False,) * 4,
        )

        self.assertEqual(field.lattice_orientation_deg, (59.0, 0.0, 0.0, 1.0))

    def test_points_with_zero_one_or_two_neighbors_have_no_order_value(self) -> None:
        field = _field(
            psi6=(None, None, None, None),
            q6=(None, None, None, None),
            lattice_orientation_deg=(None, None, None, None),
            orientation_status=("not_available",) * 4,
            neighbor_count=(0, 1, 2, 0),
            computation_status=("insufficient_neighbors",) * 4,
            local_median_bond_length_nm=(None, 1.5, 1.6, None),
            local_bond_length_mad_nm=(None, 0.0, 0.1, None),
            local_bond_length_iqr_nm=(None, 0.0, 0.2, None),
            local_bond_length_robust_cv=(None, 0.0, 0.1, None),
            physical_duplicate_qc=(False,) * 4,
        )

        self.assertEqual(field.neighbor_count, (0, 1, 2, 0))
        self.assertEqual(field.q6, (None, None, None, None))

        for neighbor_count in (0, 1, 2):
            with self.subTest(neighbor_count=neighbor_count):
                with self.assertRaises(ValueError):
                    _field(neighbor_count=(neighbor_count, 3, 2, 0))

    def test_edge_qc_is_independent_from_a_valid_order_result(self) -> None:
        field = _field()

        self.assertEqual(field.computation_status[0], "valid_order")
        self.assertTrue(field.edge_truncated_neighborhood[0])
        self.assertIsNotNone(field.psi6[0])
        self.assertIsNotNone(field.q6[0])

    def test_classifies_edge_neighborhood_with_strict_first_shell_distance(self) -> None:
        field = _field(
            distance_to_valid_fov_boundary_nm=(2.599, 2.6, 2.601, 2.0),
            edge_truncated_neighborhood=(True, False, False, True),
        )

        self.assertEqual(field.first_shell_r_max_nm, 2.6)
        self.assertEqual(field.edge_truncated_neighborhood, (True, False, False, True))

        with self.assertRaisesRegex(ValueError, "edge_truncated_neighborhood"):
            _field(edge_truncated_neighborhood=(False, False, False, False))

    def test_represents_geometry_duplicates_and_invalid_positions_separately(self) -> None:
        field = _field(
            computation_status=(
                "valid_order",
                "valid_order",
                "invalid_position",
                "duplicate_excluded",
            ),
            neighbor_count=(4, 3, 0, 0),
            local_median_bond_length_nm=(1.5, 1.6, None, None),
            local_bond_length_mad_nm=(0.1, 0.2, None, None),
            local_bond_length_iqr_nm=(0.2, 0.3, None, None),
            local_bond_length_robust_cv=(0.1, 0.2, None, None),
            physical_duplicate_qc=(False, False, False, False),
            geometry_duplicate_qc=(False, False, False, True),
            distance_to_valid_fov_boundary_nm=(1.0, 4.0, None, 4.0),
            edge_truncated_neighborhood=(True, False, False, False),
        )

        self.assertEqual(field.computation_status[2], "invalid_position")
        self.assertFalse(field.physical_duplicate_qc[2])
        self.assertFalse(field.geometry_duplicate_qc[2])
        self.assertEqual(field.computation_status[3], "duplicate_excluded")
        self.assertTrue(field.geometry_duplicate_qc[3])

    def test_validates_every_per_point_shape(self) -> None:
        per_point_fields = (
            "psi6",
            "q6",
            "lattice_orientation_deg",
            "orientation_status",
            "neighbor_count",
            "computation_status",
            "local_median_bond_length_nm",
            "local_bond_length_mad_nm",
            "local_bond_length_iqr_nm",
            "local_bond_length_robust_cv",
            "physical_duplicate_qc",
            "geometry_duplicate_qc",
            "edge_truncated_neighborhood",
            "distance_to_valid_fov_boundary_nm",
        )
        for field_name in per_point_fields:
            with self.subTest(field_name=field_name):
                with self.assertRaisesRegex(ValueError, field_name):
                    _field(**{field_name: ()})

        with self.assertRaisesRegex(ValueError, "point_count"):
            _field(point_count=3)
        with self.assertRaisesRegex(ValueError, "unique"):
            _field(source_ids=("same", "same", "c", "d"))

    def test_rejects_inconsistent_status_values_and_qc_flags(self) -> None:
        invalid_payloads = (
            {"computation_status": ("unknown", "valid_order", "insufficient_neighbors", "duplicate_excluded")},
            {"orientation_status": ("unknown", "undefined_zero_magnitude", "not_available", "not_available")},
            {"q6": (0.2, 0.0, None, None)},
            {"q6": (1.1, 0.0, None, None)},
            {"lattice_orientation_deg": (None, None, None, None)},
            {"lattice_orientation_deg": (61.0, 4.0, None, None)},
            {"psi6": (0.5 + 0.5j, None, None, None)},
            {"computation_status": ("insufficient_neighbors", "valid_order", "insufficient_neighbors", "duplicate_excluded")},
            {"physical_duplicate_qc": (False, False, False, False)},
            {"geometry_duplicate_qc": (False, False, False, True)},
            {"geometry_duplicate_qc": (False, False, False, True), "physical_duplicate_qc": (False, False, False, True)},
        )
        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                with self.assertRaises((TypeError, ValueError)):
                    _field(**payload)

    def test_rejects_invalid_bond_statistics_and_physical_context(self) -> None:
        invalid_payloads = (
            {"local_median_bond_length_nm": (0.0, 1.6, 1.7, None)},
            {"local_bond_length_mad_nm": (-0.1, 0.2, 0.0, None)},
            {"local_bond_length_iqr_nm": (0.2, math.inf, 0.0, None)},
            {"local_bond_length_robust_cv": (0.1, None, 0.0, None)},
            {"distance_to_valid_fov_boundary_nm": (-1.0, 4.0, 4.0, 4.0)},
            {"distance_to_valid_fov_boundary_nm": (1.0, math.inf, 4.0, 4.0)},
            {"first_shell_r_max_nm": 0.0},
            {"coordinate_frame": "image_px"},
            {"orientation_reference": "screen_x_axis"},
            {"spatial_calibration_fingerprint": ""},
            {"registration_fingerprint": ""},
            {"min_neighbors_for_local_order": 0},
            {"symmetry_m": 4},
            {"bond_weighting": "distance"},
        )
        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                with self.assertRaises((TypeError, ValueError)):
                    _field(**payload)


if __name__ == "__main__":
    unittest.main()
