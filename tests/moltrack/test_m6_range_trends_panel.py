import os
import unittest
from dataclasses import replace

import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from moltrack.analysis import compare_molecular_frame_ranges
from test_m6_range_analysis import (
    _build_series,
    _m6_settings,
    _selection,
    _triangular_patch,
)

try:
    from PyQt6.QtWidgets import QApplication
except ImportError:  # pragma: no cover - optional outside target GUI env
    QApplication = None

if QApplication is not None:
    from moltrack.ui.dialogs import PositionAnalysisDialog


_REQUIRED_METRICS = (
    "mean_local_q6_interior",
    "mean_local_q6_all_valid",
    "global_q6_interior",
    "edge_truncated_fraction_of_valid_representatives",
    "full_domain_counts",
    "small_ordered_island_counts",
    "largest_domain_molecule_fraction",
    "largest_domain_footprint_fraction",
    "full_domain_molecule_fraction",
    "small_island_molecule_fraction",
    "unassigned_molecule_fraction",
    "full_domain_footprint_fraction",
    "small_island_footprint_fraction",
    "unassigned_supported_footprint_fraction",
    "unsupported_background_fraction",
    "full_domain_molecule_weighted_coherent_q6",
    "full_domain_footprint_weighted_coherent_q6",
    "domain_molecule_entropy",
    "domain_footprint_entropy",
)


def _series():
    one_domain = _triangular_patch(0.0, (6.0, 6.0))
    one_domain_small = _triangular_patch(0.0, (6.0, 6.0), width=6, height=6)
    two_domains = np.vstack(
        (
            _triangular_patch(0.0, (6.0, 6.0)),
            _triangular_patch(22.0, (38.0, 6.0)),
        )
    )
    series = _build_series(
        (one_domain, one_domain_small, two_domains, two_domains.copy())
    )
    series.source_frame_indices = (10, 20, 30, 40)
    return series


@unittest.skipUnless(QApplication is not None, "PyQt6 is required for MolTrack GUI tests")
class M6RangeTrendsPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])
        cls.series = _series()
        cls.comparison = compare_molecular_frame_ranges(
            cls.series,
            _selection(),
            m6_orientation_settings=_m6_settings(),
        )
        cls.changed_comparison = compare_molecular_frame_ranges(
            cls.series,
            _selection(),
            m6_orientation_settings=replace(_m6_settings(), q_seed=0.8),
        )

    def setUp(self) -> None:
        self.dialog = PositionAnalysisDialog()
        self.dialog.configure_frame_ranges(frame_count=4, source_view="raw")

    def tearDown(self) -> None:
        self.dialog.close()
        self.dialog.deleteLater()
        self.__class__._app.processEvents()

    def test_known_ranges_show_metrics_labels_names_and_both_frame_mappings(self) -> None:
        self.dialog.set_range_comparison(self.comparison)

        self.assertEqual(self.dialog.m6_trend_metric_options(), _REQUIRED_METRICS)
        first_m6 = self.dialog.m6_trend_data().first.m6_orientation
        second_m6 = self.dialog.m6_trend_data().second.m6_orientation
        for metric in _REQUIRED_METRICS:
            with self.subTest(metric=metric):
                self.dialog.set_m6_trend_metric(metric)
                self.assertEqual(
                    self.dialog.m6_trend_plot_values(),
                    (getattr(first_m6, metric), getattr(second_m6, metric)),
                )
        self.dialog.set_m6_trend_metric("full_domain_counts")
        self.assertEqual(self.dialog.m6_trend_legend_labels(), ("one domain", "two domains"))
        self.assertEqual(
            self.dialog.m6_trend_plot_values(),
            ((1, 1), (2, 2)),
        )
        self.assertEqual(
            self.dialog.m6_trend_frame_values(),
            ((1, 2), (3, 4)),
        )
        self.assertEqual(
            self.dialog.m6_trend_axis_labels(),
            ("Working frame number", "Full domains [count]"),
        )

        self.dialog.set_m6_trend_frame_axis("source")

        self.assertEqual(
            self.dialog.m6_trend_frame_values(),
            ((11, 21), (31, 41)),
        )
        self.assertEqual(
            self.dialog.m6_trend_axis_labels(),
            ("Source frame number", "Full domains [count]"),
        )
        self.assertIn("frame-local", self.dialog.m6_trend_status_text().lower())
        self.assertFalse(self.comparison.uses_tracking)

    def test_unavailable_value_is_a_gap_with_explicit_frame_and_reason(self) -> None:
        unavailable = replace(
            self.comparison.first_analysis.frame_results[1],
            m6_orientation_analysis=None,
            m6_orientation_availability_status="unavailable_blocking_graph_qc",
            m6_orientation_unavailability_reason="blocking_rank2_radius_fallback",
        )
        first_analysis = replace(
            self.comparison.first_analysis,
            frame_results=(
                self.comparison.first_analysis.frame_results[0],
                unavailable,
            ),
        )
        comparison = replace(self.comparison, first_analysis=first_analysis)

        self.dialog.set_range_comparison(comparison)
        self.dialog.set_m6_trend_metric("mean_local_q6_interior")

        values = self.dialog.m6_trend_plot_values()[0]
        self.assertIsNotNone(values[0])
        self.assertIsNone(values[1])
        curve_y = self.dialog.m6_settings_panel.range_trends_panel.first_curve.getData()[1]
        self.assertTrue(np.isnan(curve_y[1]))
        status = self.dialog.m6_trend_status_text()
        self.assertIn("one domain", status)
        self.assertIn("working 2", status)
        self.assertIn("source 21", status)
        self.assertIn("blocking_rank2_radius_fallback", status)

    def test_new_analysis_settings_refresh_values_and_preserve_metric_choice(self) -> None:
        self.dialog.set_range_comparison(self.comparison)
        self.dialog.set_m6_trend_metric("domain_molecule_entropy")
        previous_data = self.dialog.m6_trend_data()
        first_curve = self.dialog.m6_settings_panel.range_trends_panel.first_curve
        second_curve = self.dialog.m6_settings_panel.range_trends_panel.second_curve

        self.dialog.m6_settings_panel.q_seed.setValue(0.8)

        self.assertIsNone(self.dialog.m6_trend_data())
        self.assertIn("Run/Recalculate", self.dialog.m6_trend_status_text())

        self.dialog.set_range_comparison(self.changed_comparison)

        self.assertIsNot(self.dialog.m6_trend_data(), previous_data)
        self.assertEqual(
            self.dialog.m6_settings_panel.range_trends_panel.current_metric(),
            "domain_molecule_entropy",
        )
        self.assertIs(
            self.dialog.m6_settings_panel.range_trends_panel.first_curve,
            first_curve,
        )
        self.assertIs(
            self.dialog.m6_settings_panel.range_trends_panel.second_curve,
            second_curve,
        )
        expected = tuple(
            frame.m6_orientation_analysis.frame_aggregates.domain_molecule_entropy
            for frame in self.changed_comparison.first_analysis.frame_results
        )
        self.assertEqual(self.dialog.m6_trend_plot_values()[0], expected)


if __name__ == "__main__":
    unittest.main()
