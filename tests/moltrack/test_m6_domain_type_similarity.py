import math
import unittest

from moltrack.analysis import (
    M6DomainTypeClassificationSettings,
    M6DomainTypeDistance,
    compute_m6_domain_type_distance,
    mean_m6_orientation_deg,
    m6_bond_length_difference,
    m6_orientation_distance_deg,
)


class M6DomainTypeSimilarityTests(unittest.TestCase):
    def test_orientation_distance_is_cyclic_modulo_sixty_and_symmetric(self) -> None:
        self.assertAlmostEqual(m6_orientation_distance_deg(59.0, 1.0), 2.0)
        self.assertAlmostEqual(m6_orientation_distance_deg(1.0, 59.0), 2.0)
        self.assertAlmostEqual(m6_orientation_distance_deg(-1.0, 61.0), 2.0)
        self.assertAlmostEqual(m6_orientation_distance_deg(0.0, 30.0), 30.0)

    def test_mean_orientation_uses_the_sixfold_circular_representation(self) -> None:
        self.assertAlmostEqual(mean_m6_orientation_deg((59.0, 1.0)), 0.0)
        self.assertAlmostEqual(mean_m6_orientation_deg((1.0, 59.0)), 0.0)
        self.assertAlmostEqual(mean_m6_orientation_deg((5.0, 5.0, 5.0)), 5.0)

        with self.assertRaisesRegex(ValueError, "undefined"):
            mean_m6_orientation_deg((0.0, 30.0))
        with self.assertRaisesRegex(ValueError, "at least one"):
            mean_m6_orientation_deg(())

    def test_bond_length_difference_supports_relative_and_absolute_modes(self) -> None:
        expected_percent = 200.0 * 2.0 / 22.0
        self.assertAlmostEqual(
            m6_bond_length_difference(10.0, 12.0, mode="relative_percent"),
            expected_percent,
        )
        self.assertAlmostEqual(
            m6_bond_length_difference(12.0, 10.0, mode="relative_percent"),
            expected_percent,
        )
        self.assertAlmostEqual(
            m6_bond_length_difference(10.0, 12.0, mode="absolute_nm"),
            2.0,
        )
        self.assertAlmostEqual(
            m6_bond_length_difference(12.0, 10.0, mode="absolute_nm"),
            2.0,
        )

    def test_normalized_distance_uses_maximum_and_includes_exact_boundary(self) -> None:
        settings = M6DomainTypeClassificationSettings(
            orientation_tolerance_deg=2.0,
            bond_length_tolerance_mode="absolute_nm",
            bond_length_tolerance_value=2.0,
        )

        distance = compute_m6_domain_type_distance(
            59.0,
            10.0,
            1.0,
            12.0,
            settings=settings,
        )

        self.assertIsInstance(distance, M6DomainTypeDistance)
        self.assertEqual(distance.bond_length_difference_unit, "nm")
        self.assertAlmostEqual(distance.orientation_difference_deg, 2.0)
        self.assertAlmostEqual(distance.bond_length_difference, 2.0)
        self.assertAlmostEqual(distance.normalized_orientation_distance, 1.0)
        self.assertAlmostEqual(distance.normalized_bond_length_distance, 1.0)
        self.assertAlmostEqual(distance.normalized_distance, 1.0)
        self.assertTrue(distance.is_compatible)

        outside = compute_m6_domain_type_distance(
            59.0,
            10.0,
            1.0001,
            12.0,
            settings=settings,
        )
        self.assertGreater(outside.normalized_distance, 1.0)
        self.assertFalse(outside.is_compatible)

    def test_relative_distance_reports_percent_and_is_symmetric(self) -> None:
        settings = M6DomainTypeClassificationSettings(
            orientation_tolerance_deg=5.0,
            bond_length_tolerance_mode="relative_percent",
            bond_length_tolerance_value=10.0,
        )

        forward = compute_m6_domain_type_distance(
            4.0,
            10.0,
            8.0,
            12.0,
            settings=settings,
        )
        reverse = compute_m6_domain_type_distance(
            8.0,
            12.0,
            4.0,
            10.0,
            settings=settings,
        )

        self.assertEqual(forward, reverse)
        self.assertEqual(forward.bond_length_difference_unit, "percent")
        self.assertAlmostEqual(forward.normalized_orientation_distance, 0.8)
        self.assertAlmostEqual(
            forward.normalized_bond_length_distance,
            (200.0 * 2.0 / 22.0) / 10.0,
        )
        self.assertAlmostEqual(
            forward.normalized_distance,
            max(
                forward.normalized_orientation_distance,
                forward.normalized_bond_length_distance,
            ),
        )

    def test_nonfinite_and_nonphysical_inputs_are_rejected(self) -> None:
        for value in (math.nan, math.inf, -math.inf):
            with self.subTest(function="orientation", value=value):
                with self.assertRaises(ValueError):
                    m6_orientation_distance_deg(value, 0.0)
            with self.subTest(function="mean", value=value):
                with self.assertRaises(ValueError):
                    mean_m6_orientation_deg((0.0, value))
            with self.subTest(function="bond", value=value):
                with self.assertRaises(ValueError):
                    m6_bond_length_difference(
                        value,
                        1.0,
                        mode="relative_percent",
                    )

        for value in (0.0, -1.0):
            with self.subTest(nonpositive_bond_length=value):
                with self.assertRaises(ValueError):
                    m6_bond_length_difference(
                        value,
                        1.0,
                        mode="absolute_nm",
                    )

        with self.assertRaises(ValueError):
            m6_bond_length_difference(1.0, 2.0, mode="unsupported")
        with self.assertRaises(TypeError):
            compute_m6_domain_type_distance(
                0.0,
                1.0,
                1.0,
                2.0,
                settings=object(),
            )


if __name__ == "__main__":
    unittest.main()
