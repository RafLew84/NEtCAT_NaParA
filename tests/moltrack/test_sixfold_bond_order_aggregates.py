import cmath
import math
import unittest
from dataclasses import FrozenInstanceError, replace

from moltrack.analysis import (
    LocalSixfoldBondOrderField,
    SixfoldBondOrderAggregates,
    aggregate_local_sixfold_bond_order,
)


def _valid_field(
    psi6: tuple[complex, ...],
    *,
    edge_truncated: tuple[bool, ...] | None = None,
) -> LocalSixfoldBondOrderField:
    point_count = len(psi6)
    edge_flags = edge_truncated or (False,) * point_count
    q6 = tuple(abs(value) for value in psi6)
    orientation_status = tuple(
        "undefined_zero_magnitude" if value == 0.0 else "defined"
        for value in q6
    )
    orientations = tuple(
        None if value == 0.0 else math.degrees(cmath.phase(order) / 6.0) % 60.0
        for order, value in zip(psi6, q6)
    )
    return LocalSixfoldBondOrderField(
        source_ids=tuple(f"molecule-{index}" for index in range(point_count)),
        point_count=point_count,
        psi6=psi6,
        q6=q6,
        lattice_orientation_deg=orientations,
        orientation_status=orientation_status,
        neighbor_count=(6,) * point_count,
        computation_status=("valid_order",) * point_count,
        local_median_bond_length_nm=(2.0,) * point_count,
        local_bond_length_mad_nm=(0.0,) * point_count,
        local_bond_length_iqr_nm=(0.0,) * point_count,
        local_bond_length_robust_cv=(0.0,) * point_count,
        physical_duplicate_qc=(False,) * point_count,
        geometry_duplicate_qc=(False,) * point_count,
        edge_truncated_neighborhood=edge_flags,
        distance_to_valid_fov_boundary_nm=tuple(
            1.0 if is_edge else 10.0 for is_edge in edge_flags
        ),
        first_shell_r_max_nm=2.6,
        coordinate_frame="sample_nm",
        orientation_reference="+x_sample_axis",
        spatial_calibration_fingerprint="calibration-v1",
        registration_fingerprint="registration-v1",
    )


def _mixed_field() -> LocalSixfoldBondOrderField:
    return LocalSixfoldBondOrderField(
        source_ids=("valid-a", "edge", "insufficient", "duplicate", "invalid", "valid-b"),
        point_count=6,
        psi6=(1.0 + 0.0j, 0.0 + 0.5j, None, None, None, -1.0 + 0.0j),
        q6=(1.0, 0.5, None, None, None, 1.0),
        lattice_orientation_deg=(0.0, 15.0, None, None, None, 30.0),
        orientation_status=(
            "defined",
            "defined",
            "not_available",
            "not_available",
            "not_available",
            "defined",
        ),
        neighbor_count=(3, 4, 2, 0, 0, 3),
        computation_status=(
            "valid_order",
            "valid_order",
            "insufficient_neighbors",
            "duplicate_excluded",
            "invalid_position",
            "valid_order",
        ),
        local_median_bond_length_nm=(2.0, 2.1, 2.2, None, None, 2.0),
        local_bond_length_mad_nm=(0.1, 0.1, 0.2, None, None, 0.1),
        local_bond_length_iqr_nm=(0.2, 0.2, 0.3, None, None, 0.2),
        local_bond_length_robust_cv=(0.07, 0.07, 0.13, None, None, 0.07),
        physical_duplicate_qc=(False, False, False, True, False, False),
        geometry_duplicate_qc=(False,) * 6,
        edge_truncated_neighborhood=(False, True, False, False, False, False),
        distance_to_valid_fov_boundary_nm=(10.0, 1.0, 10.0, 10.0, None, 10.0),
        first_shell_r_max_nm=2.6,
        coordinate_frame="sample_nm",
        orientation_reference="+x_sample_axis",
        spatial_calibration_fingerprint="calibration-v1",
        registration_fingerprint="registration-v1",
    )


class SixfoldBondOrderAggregateTests(unittest.TestCase):
    def test_separates_interior_and_all_valid_metrics_and_reports_counts(self) -> None:
        result = aggregate_local_sixfold_bond_order(_mixed_field())

        self.assertEqual(result.point_count, 6)
        self.assertEqual(result.valid_order_count, 3)
        self.assertEqual(result.valid_interior_count, 2)
        self.assertEqual(result.edge_truncated_valid_count, 1)
        self.assertEqual(result.insufficient_neighbors_count, 1)
        self.assertEqual(result.duplicate_excluded_count, 1)
        self.assertEqual(result.invalid_position_count, 1)
        self.assertEqual(result.rejected_point_count, 2)
        self.assertAlmostEqual(result.mean_local_q6_interior, 1.0)
        self.assertAlmostEqual(result.global_psi6_interior.real, 0.0)
        self.assertAlmostEqual(result.global_psi6_interior.imag, 0.0)
        self.assertAlmostEqual(result.global_q6_interior, 0.0)
        self.assertAlmostEqual(result.mean_local_q6_all_valid, 2.5 / 3.0)
        self.assertAlmostEqual(result.global_psi6_all_valid.real, 0.0)
        self.assertAlmostEqual(result.global_psi6_all_valid.imag, 1.0 / 6.0)
        self.assertAlmostEqual(result.global_q6_all_valid, 1.0 / 6.0)
        self.assertAlmostEqual(
            result.edge_truncated_fraction_of_valid_representatives,
            1.0 / 3.0,
        )

    def test_one_domain_has_high_local_and_global_order(self) -> None:
        phase = cmath.exp(6j * math.radians(11.0))

        result = aggregate_local_sixfold_bond_order(_valid_field((phase,) * 12))

        self.assertAlmostEqual(result.mean_local_q6_interior, 1.0)
        self.assertAlmostEqual(result.global_q6_interior, 1.0)

    def test_two_opposite_m6_domains_keep_local_order_but_cancel_global_order(self) -> None:
        result = aggregate_local_sixfold_bond_order(
            _valid_field((1.0 + 0.0j,) * 8 + (-1.0 + 0.0j,) * 8)
        )

        self.assertAlmostEqual(result.mean_local_q6_interior, 1.0)
        self.assertAlmostEqual(result.global_q6_interior, 0.0)
        self.assertAlmostEqual(result.global_psi6_interior.real, 0.0)

    def test_disordered_field_has_low_local_and_global_order(self) -> None:
        psi6 = tuple(
            magnitude * cmath.exp(1j * angle)
            for magnitude, angle in zip(
                (0.08, 0.12, 0.18, 0.10, 0.16, 0.14),
                (0.1, 1.3, 2.2, 3.4, 4.7, 5.8),
            )
        )

        result = aggregate_local_sixfold_bond_order(_valid_field(psi6))

        self.assertLess(result.mean_local_q6_interior, 0.2)
        self.assertLess(result.global_q6_interior, result.mean_local_q6_interior)

    def test_zero_magnitude_orientation_remains_in_valid_aggregate_population(self) -> None:
        result = aggregate_local_sixfold_bond_order(
            _valid_field((0.0 + 0.0j, 1.0 + 0.0j))
        )

        self.assertEqual(result.valid_order_count, 2)
        self.assertAlmostEqual(result.mean_local_q6_interior, 0.5)
        self.assertAlmostEqual(result.global_q6_interior, 0.5)

    def test_all_edge_points_keep_auxiliary_metrics_without_interior_metrics(self) -> None:
        field = _valid_field(
            (1.0 + 0.0j,) * 3,
            edge_truncated=(True, True, True),
        )

        result = aggregate_local_sixfold_bond_order(field)

        self.assertIsNone(result.mean_local_q6_interior)
        self.assertIsNone(result.global_psi6_interior)
        self.assertIsNone(result.global_q6_interior)
        self.assertAlmostEqual(result.mean_local_q6_all_valid, 1.0)
        self.assertAlmostEqual(result.global_q6_all_valid, 1.0)
        self.assertAlmostEqual(
            result.edge_truncated_fraction_of_valid_representatives,
            1.0,
        )

    def test_empty_valid_population_has_unavailable_metrics_and_fraction(self) -> None:
        field = LocalSixfoldBondOrderField(
            source_ids=("insufficient", "duplicate", "invalid"),
            point_count=3,
            psi6=(None, None, None),
            q6=(None, None, None),
            lattice_orientation_deg=(None, None, None),
            orientation_status=("not_available",) * 3,
            neighbor_count=(2, 0, 0),
            computation_status=(
                "insufficient_neighbors",
                "duplicate_excluded",
                "invalid_position",
            ),
            local_median_bond_length_nm=(2.0, None, None),
            local_bond_length_mad_nm=(0.0, None, None),
            local_bond_length_iqr_nm=(0.0, None, None),
            local_bond_length_robust_cv=(0.0, None, None),
            physical_duplicate_qc=(False, True, False),
            geometry_duplicate_qc=(False, False, False),
            edge_truncated_neighborhood=(False, False, False),
            distance_to_valid_fov_boundary_nm=(10.0, 10.0, None),
            first_shell_r_max_nm=2.6,
            coordinate_frame="sample_nm",
            orientation_reference="+x_sample_axis",
            spatial_calibration_fingerprint="calibration-v1",
            registration_fingerprint="registration-v1",
        )

        result = aggregate_local_sixfold_bond_order(field)

        self.assertEqual(result.valid_order_count, 0)
        self.assertIsNone(result.mean_local_q6_all_valid)
        self.assertIsNone(result.global_psi6_all_valid)
        self.assertIsNone(result.global_q6_all_valid)
        self.assertIsNone(result.edge_truncated_fraction_of_valid_representatives)

    def test_result_is_immutable_validated_and_preserves_provenance(self) -> None:
        result = aggregate_local_sixfold_bond_order(_mixed_field())

        self.assertIsInstance(result, SixfoldBondOrderAggregates)
        self.assertEqual(result.coordinate_frame, "sample_nm")
        self.assertEqual(result.orientation_reference, "+x_sample_axis")
        self.assertEqual(result.spatial_calibration_fingerprint, "calibration-v1")
        self.assertEqual(result.registration_fingerprint, "registration-v1")
        self.assertEqual(result.symmetry_m, 6)
        self.assertEqual(result.bond_weighting, "uniform")

        with self.assertRaises(FrozenInstanceError):
            result.valid_order_count = 4

        invalid_changes = (
            {"point_count": 5},
            {"valid_order_count": 4},
            {"rejected_point_count": 1},
            {"global_q6_interior": 0.5},
            {"mean_local_q6_interior": None},
            {"edge_truncated_fraction_of_valid_representatives": 0.5},
            {"coordinate_frame": "image_px"},
            {"symmetry_m": 4},
        )
        for changes in invalid_changes:
            with self.subTest(changes=changes):
                with self.assertRaises((TypeError, ValueError)):
                    replace(result, **changes)

    def test_rejects_non_field_input(self) -> None:
        with self.assertRaisesRegex(TypeError, "local_order_field"):
            aggregate_local_sixfold_bond_order(object())


if __name__ == "__main__":
    unittest.main()
