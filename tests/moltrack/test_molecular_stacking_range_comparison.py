import unittest
from dataclasses import replace

from moltrack.analysis import (
    MolecularFrameRange,
    MolecularStackingRangeComparison,
    MolecularStackingRangeComparisonRow,
    build_molecular_stacking_range_comparison,
)
from test_molecular_stacking_analysis import _prototype_analysis


def _stacking_with_patterns(patterns: tuple[str, ...]):
    from moltrack.analysis import analyze_molecular_stacking

    def analyzed(**kwargs):
        frame_data, prototype_data = _prototype_analysis(**kwargs)
        return analyze_molecular_stacking(frame_data, prototype_data)

    analyses = {
        "ABAB": analyzed(
            state_for_site=lambda row, column: (row + column) % 2,
        ),
        "uniform": analyzed(
            state_for_site=lambda _row, _column: 0,
            angles=(35.0,),
        ),
        "mixed": analyzed(
            state_for_site=lambda row, column: (
                (row + column) % 2
                if column < 4
                else 1 - (row + column) % 2
            ),
        ),
        "ambiguous": analyzed(
            state_for_site=lambda row, column: (row + column) % 2,
            first_axis_only=False,
        ),
        "unavailable": analyzed(
            state_for_site=lambda row, column: (row + column) % 3,
            angles=(10.0, 70.0, 130.0),
        ),
    }
    base = analyses["ABAB"]
    orders = []
    subdomains = []
    for index, pattern in enumerate(patterns):
        source = analyses[pattern]
        template = source.orders[0]
        id_map = {
            subdomain.subdomain_id: f"{subdomain.subdomain_id}-frame-{index}"
            for subdomain in source.subdomains
            if (
                subdomain.frame_index == template.frame_index
                and subdomain.parent_lattice_domain_id
                == template.lattice_domain_id
            )
        }
        orders.append(
            replace(
                template,
                frame_index=index,
                subdomain_ids=tuple(
                    sorted(
                        id_map[subdomain_id]
                        for subdomain_id in template.subdomain_ids
                    )
                ),
            )
        )
        subdomains.extend(
            replace(
                subdomain,
                subdomain_id=id_map[subdomain.subdomain_id],
                frame_index=index,
            )
            for subdomain in source.subdomains
            if subdomain.subdomain_id in id_map
        )
    return replace(
        base,
        orders=tuple(orders),
        subdomains=tuple(
            sorted(
                subdomains,
                key=lambda value: (
                    value.frame_index,
                    value.parent_lattice_domain_id,
                    value.subdomain_id,
                ),
            )
        ),
        input_frame_indices=tuple(range(len(patterns))),
        row_assignment_fingerprints=tuple(
            (index, f"row-{index}") for index in range(len(patterns))
        ),
    )


class MolecularStackingRangeComparisonTests(unittest.TestCase):
    def test_compares_classified_domain_instance_shares_without_tracking(self) -> None:
        analysis = _stacking_with_patterns(
            ("ABAB", "uniform", "ambiguous", "mixed", "mixed", "unavailable")
        )

        result = build_molecular_stacking_range_comparison(
            analysis,
            MolecularFrameRange("Before desorption", 0, 2),
            MolecularFrameRange("After adsorption", 3, 5),
        )

        self.assertFalse(result.uses_tracking)
        self.assertEqual(result.denominator, "classified_domain_instances")
        self.assertEqual(result.first.classified_domain_count, 2)
        self.assertEqual(result.first.excluded_domain_count, 1)
        self.assertEqual(result.second.classified_domain_count, 2)
        self.assertEqual(result.second.excluded_domain_count, 1)
        rows = {row.pattern: row for row in result.rows}
        self.assertAlmostEqual(rows["ABAB"].first_share_percent, 50.0)
        self.assertAlmostEqual(rows["uniform"].first_share_percent, 50.0)
        self.assertAlmostEqual(rows["mixed"].second_share_percent, 100.0)
        self.assertAlmostEqual(rows["mixed"].share_delta_percentage_points, 100.0)

    def test_empty_classified_side_has_undefined_shares(self) -> None:
        analysis = _stacking_with_patterns(("ambiguous", "unavailable", "ABAB"))

        result = build_molecular_stacking_range_comparison(
            analysis,
            MolecularFrameRange("Before", 0, 1),
            MolecularFrameRange("After", 2, 2),
        )

        self.assertTrue(all(row.first_share_percent is None for row in result.rows))
        self.assertTrue(
            all(row.share_delta_percentage_points is None for row in result.rows)
        )

    def test_rejects_comparison_row_inconsistent_with_range_summaries(self) -> None:
        analysis = _stacking_with_patterns(("ABAB", "mixed"))
        valid = build_molecular_stacking_range_comparison(
            analysis,
            MolecularFrameRange("Before", 0, 0),
            MolecularFrameRange("After", 1, 1),
        )
        invalid_row = MolecularStackingRangeComparisonRow(
            pattern="ABAB",
            first_count=0,
            first_share_percent=0.0,
            second_count=0,
            second_share_percent=0.0,
            count_delta=0,
            share_delta_percentage_points=0.0,
        )

        with self.assertRaisesRegex(
            ValueError,
            "does not match its range summaries",
        ):
            MolecularStackingRangeComparison(
                first=valid.first,
                second=valid.second,
                rows=(invalid_row, *valid.rows[1:]),
            )


if __name__ == "__main__":
    unittest.main()
