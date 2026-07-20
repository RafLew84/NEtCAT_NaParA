import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from moltrack.analysis import (
    M6DomainTypeAnalysisOutcome,
    build_m6_domain_type_range_comparison,
    build_m6_single_range_domain_type_summary,
)
from test_m6_domain_type_range_comparison import (
    _classification as _comparison_classification,
    _range_analysis as _comparison_range_analysis,
)
from test_m6_single_range_domain_type_summary import (
    _classification as _single_classification,
    _observation as _single_observation,
    _range_analysis as _single_range_analysis,
)

try:
    from PyQt6.QtWidgets import QApplication
except ImportError:  # pragma: no cover - optional outside target GUI env
    QApplication = None

if QApplication is not None:
    from moltrack.ui.dialogs.m6_domain_type_plot_data import (
        M6_DOMAIN_TYPE_UNCLASSIFIED_COLOR,
        build_m6_domain_type_scatter_data,
        build_m6_domain_type_share_plot_data,
    )
    from moltrack.ui.dialogs.m6_domain_type_plots_panel import M6DomainTypePlotsPanel


def _single_outcome() -> M6DomainTypeAnalysisOutcome:
    observations = (
        _single_observation(
            0,
            0,
            1.0,
            2.0,
            range_end=2,
            molecule_fraction=0.2,
            footprint_fraction=0.1,
        ),
        _single_observation(
            1,
            0,
            2.0,
            2.1,
            range_end=2,
            molecule_fraction=0.3,
            footprint_fraction=0.2,
        ),
        _single_observation(
            2,
            1,
            30.0,
            None,
            range_end=2,
            molecule_fraction=0.1,
            footprint_fraction=0.1,
            qualification_status="unclassified",
            unclassified_reason="missing_bond_length_statistics",
        ),
    )
    classification = _single_classification(observations, frame_count=3)
    table_result = build_m6_single_range_domain_type_summary(
        classification,
        _single_range_analysis(
            ((1, 0.2, 0.1), (1, 0.3, 0.2), (1, 0.1, 0.1))
        ),
    )
    return M6DomainTypeAnalysisOutcome(
        status="ready",
        status_message="Domain type classification is ready.",
        context_fingerprint="single-plot-context",
        analysis_scope=classification.analysis_scope,
        available_m6_frame_count=3,
        classification=classification,
        table_result=table_result,
    )


def _comparison_outcome() -> M6DomainTypeAnalysisOutcome:
    classification = _comparison_classification()
    first_range, second_range = classification.analysis_scope.comparison_ranges
    table_result = build_m6_domain_type_range_comparison(
        classification,
        _comparison_range_analysis(first_range),
        _comparison_range_analysis(second_range),
    )
    return M6DomainTypeAnalysisOutcome(
        status="ready",
        status_message="Domain type classification is ready.",
        context_fingerprint="comparison-plot-context",
        analysis_scope=classification.analysis_scope,
        available_m6_frame_count=6,
        classification=classification,
        table_result=table_result,
    )


def _classification_with_visible_unclassified():
    observations = (
        _single_observation(
            0,
            0,
            1.0,
            2.0,
            range_end=2,
            molecule_fraction=0.2,
            footprint_fraction=0.1,
        ),
        _single_observation(
            1,
            0,
            2.0,
            2.1,
            range_end=2,
            molecule_fraction=0.3,
            footprint_fraction=0.2,
        ),
        _single_observation(
            2,
            1,
            30.0,
            5.0,
            range_end=2,
            molecule_fraction=0.1,
            footprint_fraction=0.1,
        ),
    )
    return _single_classification(observations, frame_count=3)


@unittest.skipUnless(QApplication is not None, "PyQt6 is required for GUI tests")
class M6DomainTypePlotDataTests(unittest.TestCase):
    def test_scatter_uses_type_colors_range_markers_and_skips_missing_lengths(self) -> None:
        outcome = _comparison_outcome()
        data = build_m6_domain_type_scatter_data(outcome.classification)

        self.assertEqual(data.axis_labels, (
            "M6 orientation [deg]",
            "Median bond length [nm]",
        ))
        self.assertTrue(all(0.0 <= point.orientation_deg < 60.0 for point in data.points))
        self.assertEqual(data.omitted_missing_bond_length_count, 0)
        self.assertEqual(
            tuple(item.label for item in data.type_legend),
            ("A", "B", "C"),
        )
        self.assertEqual(
            tuple(item.label for item in data.range_legend),
            ("before desorption", "after adsorption"),
        )
        common_points = tuple(point for point in data.points if point.type_label == "B")
        self.assertEqual({point.symbol for point in common_points}, {"o", "s"})
        self.assertEqual(len({point.color for point in common_points}), 1)

        single = build_m6_domain_type_scatter_data(_single_outcome().classification)
        self.assertEqual(single.omitted_missing_bond_length_count, 1)
        self.assertEqual(len(single.points), 2)
        self.assertEqual(single.range_legend, ())

        visible_unclassified = build_m6_domain_type_scatter_data(
            _classification_with_visible_unclassified()
        )
        unclassified = tuple(
            point for point in visible_unclassified.points
            if point.type_label == "Unclassified"
        )
        self.assertEqual(len(unclassified), 1)
        self.assertEqual(unclassified[0].color, M6_DOMAIN_TYPE_UNCLASSIFIED_COLOR)

    def test_share_data_adapts_one_or_two_series_and_preserves_zeros(self) -> None:
        single = _single_outcome()
        single_data = build_m6_domain_type_share_plot_data(
            single.table_result,
            "instances_per_frame",
        )
        self.assertEqual(single_data.type_labels, ("A", "Unclassified"))
        self.assertEqual(tuple(item.name for item in single_data.series), ("condition",))
        self.assertEqual(single_data.axis_label, "Instances/frame")
        self.assertAlmostEqual(single_data.series[0].values[0], 2.0 / 3.0)
        self.assertAlmostEqual(single_data.series[0].values[1], 1.0 / 3.0)
        self.assertEqual(
            single_data.type_colors[-1],
            M6_DOMAIN_TYPE_UNCLASSIFIED_COLOR,
        )
        single_molecules = build_m6_domain_type_share_plot_data(
            single.table_result,
            "molecule_fraction",
        )
        self.assertAlmostEqual(single_molecules.series[0].values[0], 50.0 / 3.0)
        self.assertAlmostEqual(single_molecules.series[0].values[1], 10.0 / 3.0)
        single_footprints = build_m6_domain_type_share_plot_data(
            single.table_result,
            "footprint_fraction",
        )
        self.assertAlmostEqual(single_footprints.series[0].values[0], 10.0)
        self.assertAlmostEqual(single_footprints.series[0].values[1], 10.0 / 3.0)

        comparison = _comparison_outcome()
        comparison_data = build_m6_domain_type_share_plot_data(
            comparison.table_result,
            "molecule_fraction",
        )
        self.assertEqual(
            comparison_data.type_labels,
            ("A", "B", "C", "Unclassified"),
        )
        self.assertEqual(
            tuple(item.name for item in comparison_data.series),
            ("before desorption", "after adsorption"),
        )
        self.assertEqual(comparison_data.axis_label, "Molecule fraction [%]")
        self.assertEqual(comparison_data.series[0].values[2], 0.0)
        self.assertEqual(comparison_data.series[1].values[0], 0.0)
        self.assertEqual(comparison_data.series[0].values[-1], 0.0)
        self.assertEqual(comparison_data.series[1].values[-1], 0.0)
        self.assertGreater(comparison_data.series[0].values[0], 0.0)
        self.assertAlmostEqual(comparison_data.series[0].values[0], 40.0 / 3.0)
        self.assertAlmostEqual(comparison_data.series[1].values[1], 40.0 / 3.0)
        comparison_footprints = build_m6_domain_type_share_plot_data(
            comparison.table_result,
            "footprint_fraction",
        )
        self.assertAlmostEqual(comparison_footprints.series[0].values[0], 20.0 / 3.0)
        self.assertAlmostEqual(comparison_footprints.series[1].values[1], 10.0)


@unittest.skipUnless(QApplication is not None, "PyQt6 is required for GUI tests")
class M6DomainTypePlotsPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.panel = M6DomainTypePlotsPanel()

    def tearDown(self) -> None:
        self.panel.close()
        self.panel.deleteLater()
        self.__class__._app.processEvents()

    def test_plots_axes_legends_and_metric_update_reuse_result_and_items(self) -> None:
        outcome = _comparison_outcome()
        observations_before = outcome.classification.observations
        table_before = outcome.table_result
        first_bars_id = id(self.panel.first_bars)
        second_bars_id = id(self.panel.second_bars)

        self.panel.set_outcome(outcome)

        self.assertIs(self.panel.outcome(), outcome)
        scatter_data = self.panel.scatter_data()
        self.assertEqual(self.panel.scatter_axis_labels(), scatter_data.axis_labels)
        self.assertEqual(self.panel.scatter_point_count(), 8)
        x_range = self.panel.scatter_plot.getViewBox().viewRange()[0]
        self.assertAlmostEqual(x_range[0], 0.0)
        self.assertAlmostEqual(x_range[1], 60.0)
        self.assertEqual(
            self.panel.scatter_legend_labels(),
            ("A", "B", "C", "before desorption", "after adsorption"),
        )
        self.assertEqual(
            self.panel.share_legend_labels(),
            ("before desorption", "after adsorption"),
        )
        self.assertEqual(
            self.panel.metric_labels(),
            ("Instances/frame", "Molecule fraction", "Footprint fraction"),
        )
        instances = self.panel.share_values()

        self.panel.set_metric("footprint_fraction")

        self.assertIs(self.panel.outcome(), outcome)
        self.assertIs(self.panel.scatter_data(), scatter_data)
        self.assertEqual(id(self.panel.first_bars), first_bars_id)
        self.assertEqual(id(self.panel.second_bars), second_bars_id)
        self.assertNotEqual(self.panel.share_values(), instances)
        self.assertEqual(self.panel.share_axis_label(), "Footprint fraction [%]")
        self.assertIs(outcome.classification.observations, observations_before)
        self.assertIs(outcome.table_result, table_before)

        self.panel.set_outcome(None, empty_message="No current classification.")
        self.assertEqual(self.panel.scatter_point_count(), 0)
        self.assertEqual(self.panel.status_text(), "No current classification.")


if __name__ == "__main__":
    unittest.main()
