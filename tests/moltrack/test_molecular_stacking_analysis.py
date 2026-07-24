import random
import unittest
from dataclasses import replace

from moltrack.analysis import (
    MolecularStackingSettings,
    analyze_molecular_stacking,
    molecular_stacking_analysis_fingerprint,
    molecular_stacking_settings_fingerprint,
)
from test_molecular_orientation_prototypes import _frame_data


def _prototype_analysis(
    *,
    state_for_site,
    row_count: int = 6,
    column_count: int = 8,
    angles: tuple[float, ...] = (20.0, 80.0),
    measurements_transform=None,
    first_axis_only: bool = True,
    missing_sites: frozenset[tuple[int, int]] = frozenset(),
):
    from moltrack.analysis import (
        build_molecular_orientation_prototype_analysis,
    )

    frames = [
        _frame_data(
            frame_index,
            state_for_site=state_for_site,
            prototype_angles=angles,
            row_count=row_count,
            column_count=column_count,
            missing_sites=missing_sites,
        )
        for frame_index in (0, 1)
    ]
    if measurements_transform is not None:
        frames = [
            replace(
                frame,
                measurements=_transform_measurements(
                    frame,
                    measurements_transform,
                ),
            )
            for frame in frames
        ]
    frame_tuple = tuple(frames)
    prototypes = build_molecular_orientation_prototype_analysis(
        frame_tuple
    )
    if first_axis_only and prototypes.axis_evidence:
        axis_evidence = tuple(
            value
            for value in prototypes.axis_evidence
            if value.candidate_index == 0
        )
        range_evidence = tuple(
            replace(value, axis_family_index=index)
            for index, value in enumerate(
                value
                for value in prototypes.range_axis_evidence
                if all(key[2] == 0 for key in value.candidate_keys)
            )
        )
        prototypes = replace(
            prototypes,
            axis_evidence=axis_evidence,
            range_axis_evidence=range_evidence,
        )
    return frame_tuple, prototypes


def _transform_measurements(frame, transform):
    transformed = []
    for measurement in frame.measurements:
        value = transform(frame.frame_index, measurement)
        if value is not None:
            transformed.append(value)
    return tuple(transformed)


class MolecularStackingAnalysisTests(unittest.TestCase):
    def test_clean_checkerboard_is_measurable_abab(self) -> None:
        frames, prototypes = _prototype_analysis(
            state_for_site=lambda row, column: (row + column) % 2,
        )

        result = analyze_molecular_stacking(frames, prototypes)

        self.assertEqual(len(result.orders), 2)
        self.assertEqual(
            tuple(value.pattern for value in result.orders),
            ("ABAB", "ABAB"),
        )
        for order in result.orders:
            self.assertEqual(order.mode, "checkerboard")
            self.assertEqual(order.phase, "ABAB")
            self.assertEqual(order.axis_candidate_index, 0)
            self.assertAlmostEqual(order.coverage_fraction, 1.0)
            self.assertAlmostEqual(order.ordered_fraction, 1.0)
            self.assertGreater(order.score, 0.95)
            self.assertGreater(order.confidence, 0.9)
            self.assertAlmostEqual(order.prototype_a_angle_deg, 20.0)
            self.assertAlmostEqual(order.prototype_b_angle_deg, 80.0)
            self.assertEqual(len(order.subdomain_ids), 1)

    def test_one_orientation_state_is_uniform_not_forced_to_abab(self) -> None:
        frames, prototypes = _prototype_analysis(
            state_for_site=lambda _row, _column: 0,
            angles=(35.0,),
        )

        result = analyze_molecular_stacking(frames, prototypes)

        self.assertTrue(
            all(value.pattern == "uniform" for value in result.orders)
        )
        self.assertTrue(
            all(value.mode is None for value in result.orders)
        )
        self.assertTrue(
            all(value.phase is None for value in result.orders)
        )
        self.assertTrue(
            all(value.pattern == "uniform" for value in result.subdomains)
        )

    def test_phase_boundary_creates_two_sibling_subdomains(self) -> None:
        frames, prototypes = _prototype_analysis(
            state_for_site=lambda row, column: (
                (row + column) % 2
                if column < 4
                else 1 - (row + column) % 2
            ),
        )

        result = analyze_molecular_stacking(frames, prototypes)

        for order in result.orders:
            self.assertEqual(order.pattern, "mixed")
            self.assertEqual(order.mode, "checkerboard")
            self.assertIsNone(order.phase)
            self.assertIn("phase_boundary", order.qc_reasons)
            children = tuple(
                value
                for value in result.subdomains
                if value.parent_lattice_domain_id
                == order.lattice_domain_id
                and value.frame_index == order.frame_index
            )
            self.assertEqual(len(children), 2)
            self.assertEqual(
                {value.phase for value in children},
                {"ABAB", "BABA"},
            )
            self.assertTrue(
                all(
                    value.parent_lattice_domain_id
                    == order.lattice_domain_id
                    for value in children
                )
            )

    def test_pattern_boundary_preserves_distinct_local_modes(self) -> None:
        frames, prototypes = _prototype_analysis(
            state_for_site=lambda row, column: (
                (row + column) % 2 if row < 3 else column % 2
            ),
        )

        result = analyze_molecular_stacking(frames, prototypes)

        for order in result.orders:
            self.assertEqual(order.pattern, "mixed")
            self.assertIsNone(order.mode)
            self.assertIn("pattern_boundary", order.qc_reasons)
            modes = {
                value.mode
                for value in result.subdomains
                if value.frame_index == order.frame_index
            }
            self.assertEqual(modes, {"checkerboard", "along_rows"})

    def test_orientation_error_and_vacancies_reduce_certainty_not_order(
        self,
    ) -> None:
        def transform(frame_index, measurement):
            source_id = measurement.provenance.source_id
            if source_id.endswith("-r00-c00"):
                return None
            if frame_index == 0 and source_id.endswith("-r03-c03"):
                replacement = 80.0 if measurement.angle_deg == 20.0 else 20.0
                return replace(measurement, angle_deg=replacement)
            return measurement

        frames, prototypes = _prototype_analysis(
            state_for_site=lambda row, column: (row + column) % 2,
            measurements_transform=transform,
            missing_sites=frozenset({(2, 3)}),
        )

        result = analyze_molecular_stacking(frames, prototypes)

        first = result.order_for_domain(0, "domain-0")
        self.assertEqual(first.pattern, "ABAB")
        self.assertLess(first.coverage_fraction, 1.0)
        self.assertLess(first.ordered_fraction, 1.0)
        self.assertIn("incomplete_coverage", first.qc_reasons)
        self.assertIn("orientation_outliers", first.qc_reasons)
        self.assertGreater(first.confidence, 0.6)
        self.assertEqual(len(first.subdomain_ids), 1)

    def test_axis_tie_is_ambiguous(self) -> None:
        frames, prototypes = _prototype_analysis(
            state_for_site=lambda row, column: (row + column) % 2,
            first_axis_only=False,
        )

        result = analyze_molecular_stacking(frames, prototypes)

        self.assertTrue(
            all(value.pattern == "ambiguous" for value in result.orders)
        )
        self.assertTrue(
            all(value.ordered_fraction == 1.0 for value in result.orders)
        )
        self.assertTrue(
            all(
                "axis_selection_ambiguous" in value.qc_reasons
                for value in result.orders
            )
        )

    def test_random_control_is_ambiguous(self) -> None:
        generator = random.Random(20260724)
        states = {
            (row, column): generator.randrange(2)
            for row in range(8)
            for column in range(10)
        }
        frames, prototypes = _prototype_analysis(
            state_for_site=lambda row, column: states[(row, column)],
            row_count=8,
            column_count=10,
        )
        result = analyze_molecular_stacking(frames, prototypes)

        self.assertTrue(
            all(value.pattern == "ambiguous" for value in result.orders)
        )
        self.assertTrue(
            all(
                "pattern_score_below_threshold" in value.qc_reasons
                for value in result.orders
            )
        )

    def test_unavailable_order_preserves_measured_coverage(self) -> None:
        def keep_half(_frame_index, measurement):
            column = int(measurement.provenance.source_id.rsplit("c", 1)[1])
            return measurement if column < 4 else None

        frames, prototypes = _prototype_analysis(
            state_for_site=lambda _row, _column: 0,
            angles=(35.0,),
            measurements_transform=keep_half,
        )

        result = analyze_molecular_stacking(frames, prototypes)

        for order in result.orders:
            self.assertEqual(order.pattern, "unavailable")
            self.assertEqual(order.usable_molecule_count, 24)
            self.assertAlmostEqual(order.coverage_fraction, 0.5)
            self.assertIn(
                "insufficient_domain_coverage",
                order.qc_reasons,
            )

    def test_more_than_two_orientation_states_are_unavailable(self) -> None:
        frames, prototypes = _prototype_analysis(
            state_for_site=lambda row, column: (row + column) % 3,
            angles=(10.0, 70.0, 130.0),
        )

        result = analyze_molecular_stacking(frames, prototypes)

        self.assertTrue(
            all(value.pattern == "unavailable" for value in result.orders)
        )
        self.assertTrue(
            all(
                "prototype_states_unavailable" in value.qc_reasons
                for value in result.orders
            )
        )

    def test_settings_and_analysis_have_deterministic_fingerprints(self) -> None:
        frames, prototypes = _prototype_analysis(
            state_for_site=lambda row, column: (row + column) % 2,
        )
        settings = MolecularStackingSettings(
            minimum_subdomain_size=4,
        )

        result = analyze_molecular_stacking(
            frames,
            prototypes,
            settings=settings,
        )
        equivalent = analyze_molecular_stacking(
            frames,
            prototypes,
            settings=settings,
        )
        changed = analyze_molecular_stacking(
            frames,
            prototypes,
            settings=MolecularStackingSettings(
                minimum_subdomain_size=5,
            ),
        )

        self.assertEqual(
            MolecularStackingSettings.from_dict(settings.to_dict()),
            settings,
        )
        self.assertEqual(
            result.settings_fingerprint,
            molecular_stacking_settings_fingerprint(settings),
        )
        self.assertEqual(
            molecular_stacking_analysis_fingerprint(result),
            molecular_stacking_analysis_fingerprint(equivalent),
        )
        self.assertNotEqual(
            molecular_stacking_analysis_fingerprint(result),
            molecular_stacking_analysis_fingerprint(changed),
        )
        with self.assertRaisesRegex(ValueError, "minimum_subdomain_size"):
            MolecularStackingSettings(minimum_subdomain_size=0)


if __name__ == "__main__":
    unittest.main()
