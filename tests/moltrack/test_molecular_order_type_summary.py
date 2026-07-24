import unittest

from moltrack.analysis import (
    MolecularFrameRange,
    MolecularFrameRangeAnalysisScope,
    MolecularOrderTypeClassificationSettings,
    build_molecular_order_type_summary,
    classify_molecular_order_types,
)
from test_molecular_order_type_classifier import _domain_frame, _hierarchy


def _comparison_classification():
    hierarchy = _hierarchy(
        _domain_frame(0),
        _domain_frame(1, theta3_deg=11.0),
        _domain_frame(
            2,
            symmetry="sixfold",
            theta3_deg=None,
            theta6_deg=30.0,
            orientation_angles=(40.0,),
            stacking_pattern="uniform",
        ),
        _domain_frame(
            3,
            symmetry="sixfold",
            theta3_deg=None,
            theta6_deg=31.0,
            stacking_pattern="unavailable",
        ),
    )
    scope = MolecularFrameRangeAnalysisScope(
        analysis_mode="compare_ranges",
        frame_count=4,
        source_view="expanded_aligned",
        ranges=(
            MolecularFrameRange("before", 0, 1),
            MolecularFrameRange("after", 2, 3),
        ),
    )
    return classify_molecular_order_types(
        hierarchy,
        analysis_scope=scope,
        settings=MolecularOrderTypeClassificationSettings(),
    )


class MolecularOrderTypeSummaryTests(unittest.TestCase):
    def test_each_layer_uses_only_its_reliable_observations(self) -> None:
        summary = build_molecular_order_type_summary(
            _comparison_classification()
        )

        before, after = summary.range_summaries
        self.assertEqual(before.range_name, "before")
        self.assertEqual(before.total_observation_count, 2)
        self.assertEqual(before.denominator_for_layer("geometry"), 2)
        self.assertEqual(before.denominator_for_layer("orientation"), 2)
        self.assertEqual(before.denominator_for_layer("stacking"), 2)
        self.assertEqual(before.denominator_for_layer("combination"), 2)

        self.assertEqual(after.total_observation_count, 2)
        self.assertEqual(after.denominator_for_layer("geometry"), 2)
        self.assertEqual(after.denominator_for_layer("orientation"), 1)
        self.assertEqual(after.denominator_for_layer("stacking"), 1)
        self.assertEqual(after.denominator_for_layer("combination"), 1)
        self.assertEqual(after.excluded_for_layer("geometry"), 0)
        self.assertEqual(after.excluded_for_layer("orientation"), 1)
        self.assertEqual(after.excluded_for_layer("stacking"), 1)
        self.assertEqual(after.excluded_for_layer("combination"), 1)

    def test_rows_keep_zero_shares_and_second_minus_first_deltas(self) -> None:
        summary = build_molecular_order_type_summary(
            _comparison_classification()
        )
        geometry_rows = summary.rows_for_layer("geometry")

        self.assertEqual(
            tuple(row.label for row in geometry_rows),
            ("G:A", "G:B"),
        )
        first_type = geometry_rows[0]
        second_type = geometry_rows[1]
        self.assertEqual(first_type.side_for_range("before").count, 2)
        self.assertEqual(first_type.side_for_range("before").share_percent, 100.0)
        self.assertEqual(first_type.side_for_range("after").count, 0)
        self.assertEqual(first_type.side_for_range("after").share_percent, 0.0)
        self.assertEqual(first_type.share_delta_percentage_points, -100.0)
        self.assertEqual(second_type.share_delta_percentage_points, 100.0)

        orientation_rows = summary.rows_for_layer("orientation")
        self.assertEqual(
            orientation_rows[0].side_for_range("after").share_percent,
            100.0,
        )
        self.assertEqual(
            orientation_rows[1].side_for_range("after").share_percent,
            0.0,
        )

    def test_combination_rows_use_joint_assignments_without_tracking(self) -> None:
        summary = build_molecular_order_type_summary(
            _comparison_classification()
        )
        rows = summary.rows_for_layer("combination")

        self.assertFalse(summary.uses_tracking)
        self.assertEqual(
            tuple(row.label for row in rows),
            ("G:A / O:B / S:A", "G:B / O:A / S:B"),
        )
        self.assertEqual(rows[0].side_for_range("before").count, 2)
        self.assertEqual(rows[0].side_for_range("after").count, 0)
        self.assertEqual(rows[1].side_for_range("before").count, 0)
        self.assertEqual(rows[1].side_for_range("after").count, 1)

    def test_representatives_are_deterministic_and_range_specific(self) -> None:
        classification = _comparison_classification()
        first = build_molecular_order_type_summary(classification)
        second = build_molecular_order_type_summary(classification)
        rows = first.rows_for_layer("combination")

        self.assertEqual(first, second)
        self.assertEqual(
            rows[0].representative_for_range("before")[3],
            0,
        )
        self.assertIsNone(rows[0].representative_for_range("after"))
        self.assertEqual(
            rows[1].representative_for_range("after")[3],
            2,
        )

    def test_zero_reliable_denominator_is_undefined_not_zero(self) -> None:
        single_hierarchy = _hierarchy(
            _domain_frame(0, stacking_pattern="unavailable"),
        )
        single_scope = MolecularFrameRangeAnalysisScope(
            analysis_mode="single_range",
            frame_count=1,
            source_view="expanded_aligned",
            ranges=(MolecularFrameRange("condition", 0, 0),),
        )
        single = classify_molecular_order_types(
            single_hierarchy,
            analysis_scope=single_scope,
            settings=MolecularOrderTypeClassificationSettings(),
        )
        summary = build_molecular_order_type_summary(single)

        self.assertEqual(
            summary.range_summaries[0].denominator_for_layer("stacking"),
            0,
        )
        self.assertEqual(summary.rows_for_layer("stacking"), ())
        self.assertIsNone(summary.share_delta_direction)


if __name__ == "__main__":
    unittest.main()
