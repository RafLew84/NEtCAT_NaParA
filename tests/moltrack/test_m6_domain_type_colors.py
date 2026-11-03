import unittest

from moltrack.visualization.m6_domain_type_colors import (
    m6_domain_type_color,
)


class M6DomainTypeColorTests(unittest.TestCase):
    def test_first_eight_curated_colors_remain_stable(self) -> None:
        self.assertEqual(
            tuple(m6_domain_type_color(type_id) for type_id in range(8)),
            (
                (0, 114, 178, 220),
                (213, 94, 0, 220),
                (0, 158, 115, 220),
                (204, 121, 167, 220),
                (230, 159, 0, 220),
                (86, 180, 233, 220),
                (122, 90, 170, 220),
                (60, 60, 60, 220),
            ),
        )

    def test_palette_does_not_repeat_for_many_domain_types(self) -> None:
        colors = tuple(
            m6_domain_type_color(type_id) for type_id in range(64)
        )

        self.assertEqual(len(set(colors)), len(colors))
        self.assertTrue(all(color[3] == 220 for color in colors))

    def test_type_id_validation_is_preserved(self) -> None:
        for invalid in (-1, True, 1.5):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                m6_domain_type_color(invalid)


if __name__ == "__main__":
    unittest.main()
