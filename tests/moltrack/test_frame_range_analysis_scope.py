from dataclasses import FrozenInstanceError
import json
import unittest

from moltrack.analysis import (
    MolecularFrameRange,
    MolecularFrameRangeAnalysisScope,
    MolecularFrameRangeSelection,
)


class MolecularFrameRangeAnalysisScopeTests(unittest.TestCase):
    def test_single_range_scope_exposes_one_inclusive_named_range(self) -> None:
        frame_range = MolecularFrameRange("stable condition", 2, 5)

        scope = MolecularFrameRangeAnalysisScope(
            analysis_mode="single_range",
            frame_count=8,
            source_view="raw",
            ranges=(frame_range,),
        )

        self.assertEqual(scope.analysis_mode, "single_range")
        self.assertEqual(scope.frame_count, 8)
        self.assertEqual(scope.source_view, "raw")
        self.assertEqual(scope.ranges, (frame_range,))
        self.assertIs(scope.single_range, frame_range)
        self.assertEqual(scope.single_range.frame_indices, (2, 3, 4, 5))
        with self.assertRaises(FrozenInstanceError):
            scope.frame_count = 9

    def test_existing_two_range_selection_converts_without_changing_its_contract(self) -> None:
        selection = MolecularFrameRangeSelection(
            frame_count=12,
            source_view="expanded_aligned",
            first_range=MolecularFrameRange("condition one", 1, 4),
            second_range=MolecularFrameRange("condition two", 7, 10),
        )

        scope = selection.to_analysis_scope()

        self.assertEqual(scope.analysis_mode, "compare_ranges")
        self.assertEqual(
            scope.comparison_ranges,
            (selection.first_range, selection.second_range),
        )
        self.assertEqual(scope.to_frame_range_selection(), selection)
        self.assertEqual(
            MolecularFrameRangeAnalysisScope.from_frame_range_selection(selection),
            scope,
        )
        with self.assertRaisesRegex(ValueError, "single_range"):
            _ = scope.single_range

    def test_scope_round_trips_through_a_strict_json_compatible_dictionary(self) -> None:
        scope = MolecularFrameRangeAnalysisScope(
            analysis_mode="compare_ranges",
            frame_count=20,
            source_view="raw",
            ranges=(
                MolecularFrameRange("first condition", 0, 5),
                MolecularFrameRange("second condition", 12, 19),
            ),
        )

        payload = scope.to_dict()

        self.assertEqual(
            payload,
            {
                "analysis_mode": "compare_ranges",
                "frame_count": 20,
                "source_view": "raw",
                "ranges": [
                    {"name": "first condition", "start_frame": 0, "end_frame": 5},
                    {"name": "second condition", "start_frame": 12, "end_frame": 19},
                ],
            },
        )
        self.assertEqual(
            MolecularFrameRangeAnalysisScope.from_dict(
                json.loads(json.dumps(payload))
            ),
            scope,
        )

    def test_scope_dictionary_rejects_missing_and_unknown_fields(self) -> None:
        payload = {
            "analysis_mode": "single_range",
            "frame_count": 4,
            "source_view": "raw",
            "ranges": [{"name": "one", "start_frame": 0, "end_frame": 3}],
        }

        with self.assertRaisesRegex(ValueError, "Unknown.*unexpected"):
            MolecularFrameRangeAnalysisScope.from_dict(
                {**payload, "unexpected": True}
            )
        incomplete = dict(payload)
        del incomplete["source_view"]
        with self.assertRaisesRegex(ValueError, "Missing.*source_view"):
            MolecularFrameRangeAnalysisScope.from_dict(incomplete)
        with self.assertRaisesRegex(ValueError, "Unknown.*extra"):
            MolecularFrameRangeAnalysisScope.from_dict(
                {
                    **payload,
                    "ranges": [
                        {
                            "name": "one",
                            "start_frame": 0,
                            "end_frame": 3,
                            "extra": "not allowed",
                        }
                    ],
                }
            )

    def test_scope_dictionary_rejects_coercible_range_scalar_types(self) -> None:
        base_range = {"name": "one", "start_frame": 0, "end_frame": 3}
        base_payload = {
            "analysis_mode": "single_range",
            "frame_count": 4,
            "source_view": "raw",
            "ranges": [base_range],
        }
        invalid_fields = (
            ("name", 123, "name.*string"),
            ("start_frame", True, "start_frame.*integer"),
            ("start_frame", "0", "start_frame.*integer"),
            ("end_frame", 3.5, "end_frame.*integer"),
        )

        for field_name, value, message in invalid_fields:
            with self.subTest(field_name=field_name, value=value):
                with self.assertRaisesRegex(ValueError, message):
                    MolecularFrameRangeAnalysisScope.from_dict(
                        {
                            **base_payload,
                            "ranges": [{**base_range, field_name: value}],
                        }
                    )

    def test_scope_rejects_non_domain_scalar_types_instead_of_stringifying_them(self) -> None:
        frame_range = MolecularFrameRange("one", 0, 0)

        for invalid_frame_count in (True, 1.5, "1"):
            with self.subTest(frame_count=invalid_frame_count):
                with self.assertRaisesRegex(ValueError, "frame_count.*integer"):
                    MolecularFrameRangeAnalysisScope(
                        analysis_mode="single_range",
                        frame_count=invalid_frame_count,
                        source_view="raw",
                        ranges=(frame_range,),
                    )
        with self.assertRaisesRegex(ValueError, "source_view.*string"):
            MolecularFrameRangeAnalysisScope(
                analysis_mode="single_range",
                frame_count=1,
                source_view=None,
                ranges=(frame_range,),
            )
        with self.assertRaisesRegex(ValueError, "analysis_mode.*string"):
            MolecularFrameRangeAnalysisScope(
                analysis_mode=None,
                frame_count=1,
                source_view="raw",
                ranges=(frame_range,),
            )

    def test_scope_enforces_mode_cardinality_and_working_frame_bounds(self) -> None:
        first = MolecularFrameRange("first", 0, 1)
        second = MolecularFrameRange("second", 2, 3)

        invalid_cases = (
            ("unsupported", 4, (first,), "analysis_mode"),
            ("single_range", 4, (first, second), "exactly 1"),
            ("compare_ranges", 4, (first,), "exactly 2"),
            (
                "compare_ranges",
                4,
                (first, MolecularFrameRange("duplicate", 0, 1)),
                "distinct",
            ),
            ("single_range", 1, (first,), "fit within frame_count"),
            (
                "single_range",
                4,
                (MolecularFrameRange("negative", -1, 0),),
                "fit within frame_count",
            ),
        )
        for mode, frame_count, ranges, message in invalid_cases:
            with self.subTest(mode=mode, frame_count=frame_count, ranges=ranges):
                with self.assertRaisesRegex(ValueError, message):
                    MolecularFrameRangeAnalysisScope(
                        analysis_mode=mode,
                        frame_count=frame_count,
                        source_view="raw",
                        ranges=ranges,
                    )

        single_scope = MolecularFrameRangeAnalysisScope(
            analysis_mode="single_range",
            frame_count=4,
            source_view="raw",
            ranges=(first,),
        )
        with self.assertRaisesRegex(ValueError, "compare_ranges"):
            _ = single_scope.comparison_ranges
        with self.assertRaisesRegex(ValueError, "compare_ranges"):
            single_scope.to_frame_range_selection()


if __name__ == "__main__":
    unittest.main()
