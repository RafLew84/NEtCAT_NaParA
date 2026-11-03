from dataclasses import FrozenInstanceError
import json
import unittest

from moltrack.analysis import M6DomainTypeClassificationSettings


class M6DomainTypeClassificationSettingsTests(unittest.TestCase):
    def test_defaults_are_public_immutable_starting_analytical_settings(self) -> None:
        settings = M6DomainTypeClassificationSettings()

        self.assertEqual(settings.orientation_tolerance_deg, 5.0)
        self.assertEqual(settings.bond_length_tolerance_mode, "relative_percent")
        self.assertEqual(settings.bond_length_tolerance_value, 10.0)
        self.assertEqual(settings.minimum_observations_per_type, 3)
        self.assertFalse(settings.include_small_ordered_islands)
        self.assertTrue(settings.exclude_bond_length_heterogeneity_qc)
        self.assertIn("not a validated TTMAPP preset", type(settings).__doc__)
        with self.assertRaises(FrozenInstanceError):
            settings.orientation_tolerance_deg = 8.0

    def test_accepts_relative_and_absolute_bond_length_tolerances(self) -> None:
        relative = M6DomainTypeClassificationSettings(
            orientation_tolerance_deg=8,
            bond_length_tolerance_mode="relative_percent",
            bond_length_tolerance_value=7,
            minimum_observations_per_type=2,
            include_small_ordered_islands=True,
            exclude_bond_length_heterogeneity_qc=False,
        )
        absolute = M6DomainTypeClassificationSettings(
            bond_length_tolerance_mode="absolute_nm",
            bond_length_tolerance_value=0.25,
        )

        self.assertEqual(relative.orientation_tolerance_deg, 8.0)
        self.assertEqual(relative.bond_length_tolerance_value, 7.0)
        self.assertEqual(absolute.bond_length_tolerance_mode, "absolute_nm")
        self.assertEqual(absolute.bond_length_tolerance_value, 0.25)

    def test_rejects_invalid_orientation_tolerances(self) -> None:
        for value in (0.0, -1.0, 30.0001, float("nan"), float("inf")):
            with self.subTest(value=value):
                with self.assertRaisesRegex(
                    ValueError,
                    "orientation_tolerance_deg",
                ):
                    M6DomainTypeClassificationSettings(
                        orientation_tolerance_deg=value
                    )
        for value in (True, "5"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(TypeError, "orientation_tolerance_deg"):
                    M6DomainTypeClassificationSettings(
                        orientation_tolerance_deg=value
                    )

    def test_rejects_invalid_bond_length_tolerance(self) -> None:
        for mode in ("relative", "percent", "ABSOLUTE_NM", 1):
            with self.subTest(mode=mode):
                with self.assertRaisesRegex(
                    (TypeError, ValueError),
                    "bond_length_tolerance_mode",
                ):
                    M6DomainTypeClassificationSettings(
                        bond_length_tolerance_mode=mode
                    )
        for value in (0.0, -0.1, float("nan"), float("inf")):
            with self.subTest(value=value):
                with self.assertRaisesRegex(
                    ValueError,
                    "bond_length_tolerance_value",
                ):
                    M6DomainTypeClassificationSettings(
                        bond_length_tolerance_value=value
                    )
        for value in (False, "10"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(
                    TypeError,
                    "bond_length_tolerance_value",
                ):
                    M6DomainTypeClassificationSettings(
                        bond_length_tolerance_value=value
                    )

    def test_rejects_invalid_count_and_boolean_flags(self) -> None:
        for value in (0, -1, True, 1.5, "3"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(
                    (TypeError, ValueError),
                    "minimum_observations_per_type",
                ):
                    M6DomainTypeClassificationSettings(
                        minimum_observations_per_type=value
                    )
        for field_name in (
            "include_small_ordered_islands",
            "exclude_bond_length_heterogeneity_qc",
        ):
            with self.subTest(field_name=field_name):
                with self.assertRaisesRegex(TypeError, field_name):
                    M6DomainTypeClassificationSettings(**{field_name: 1})

    def test_round_trips_through_strict_ordered_json_dictionary(self) -> None:
        settings = M6DomainTypeClassificationSettings(
            orientation_tolerance_deg=7.5,
            bond_length_tolerance_mode="absolute_nm",
            bond_length_tolerance_value=0.2,
            minimum_observations_per_type=4,
            include_small_ordered_islands=True,
            exclude_bond_length_heterogeneity_qc=False,
        )

        payload = settings.to_dict()

        self.assertEqual(
            tuple(payload),
            (
                "orientation_tolerance_deg",
                "bond_length_tolerance_mode",
                "bond_length_tolerance_value",
                "minimum_observations_per_type",
                "include_small_ordered_islands",
                "exclude_bond_length_heterogeneity_qc",
            ),
        )
        restored = M6DomainTypeClassificationSettings.from_dict(
            json.loads(json.dumps(payload))
        )
        self.assertEqual(restored, settings)
        self.assertEqual(restored.to_dict(), payload)

    def test_from_dict_rejects_schema_and_scalar_type_errors(self) -> None:
        payload = M6DomainTypeClassificationSettings().to_dict()
        missing = dict(payload)
        del missing["orientation_tolerance_deg"]

        with self.assertRaisesRegex(ValueError, "Missing.*orientation_tolerance_deg"):
            M6DomainTypeClassificationSettings.from_dict(missing)
        with self.assertRaisesRegex(ValueError, "Unknown.*extra"):
            M6DomainTypeClassificationSettings.from_dict({**payload, "extra": 1})
        with self.assertRaisesRegex(ValueError, "field names must be strings"):
            M6DomainTypeClassificationSettings.from_dict({**payload, 1: "extra"})
        with self.assertRaisesRegex(TypeError, "payload must be a mapping"):
            M6DomainTypeClassificationSettings.from_dict([])

        invalid_values = (
            ("orientation_tolerance_deg", "5"),
            ("bond_length_tolerance_mode", 1),
            ("bond_length_tolerance_value", "10"),
            ("minimum_observations_per_type", 2.5),
            ("include_small_ordered_islands", 1),
            ("exclude_bond_length_heterogeneity_qc", 0),
        )
        for field_name, value in invalid_values:
            with self.subTest(field_name=field_name, value=value):
                with self.assertRaises((TypeError, ValueError)):
                    M6DomainTypeClassificationSettings.from_dict(
                        {**payload, field_name: value}
                    )


if __name__ == "__main__":
    unittest.main()
