import os
import unittest

import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from moltrack.analysis import (
    MolecularFrameRange,
    MolecularRangeComparisonTrendData,
    MolecularRangeTrendSeries,
    analyze_molecular_frame_range,
    compare_molecular_frame_ranges,
)
from test_m6_range_analysis import _m6_settings, _selection
from test_m6_range_trends_panel import _series

try:
    from PyQt6.QtWidgets import QApplication
except ImportError:  # pragma: no cover - optional outside target GUI env
    QApplication = None

if QApplication is not None:
    from moltrack.ui import MolTrackMainWindow
    from moltrack.ui.dialogs import PositionAnalysisDialog


@unittest.skipUnless(QApplication is not None, "PyQt6 is required for MolTrack GUI tests")
class PositionAnalysisSingleRangePresentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])
        cls.series = _series()
        cls.analysis = analyze_molecular_frame_range(
            cls.series,
            MolecularFrameRange("stable phase", 0, 1),
            source_view="raw",
            m6_orientation_settings=_m6_settings(),
        )
        cls.comparison = compare_molecular_frame_ranges(
            cls.series,
            _selection(),
            m6_orientation_settings=_m6_settings(),
        )

    def setUp(self) -> None:
        self.dialog = PositionAnalysisDialog()
        self.dialog.configure_frame_ranges(frame_count=4, source_view="raw")
        self.dialog.set_analysis_mode("single_range")

    def tearDown(self) -> None:
        self.dialog.close()
        self.dialog.deleteLater()
        self.__class__._app.processEvents()

    def test_single_range_shows_one_standard_and_m6_trend_series(self) -> None:
        self.dialog.set_range_analysis_result(self.analysis)

        trend_data = self.dialog.range_trend_data()
        self.assertIsInstance(trend_data, MolecularRangeTrendSeries)
        self.assertEqual(trend_data.condition_name, "stable phase")
        self.assertEqual(
            trend_data.molecule_counts,
            tuple(result.point_count for result in self.analysis.frame_results),
        )
        self.assertEqual(self.dialog.trend_legend_labels(), ("stable phase",))
        for plot in (
            self.dialog.molecule_count_trend_plot,
            self.dialog.nearest_neighbor_trend_plot,
            self.dialog.line_order_trend_plot,
            self.dialog.intensity_trend_plot,
        ):
            self.assertEqual(len(plot.listDataItems()), 1)

        self.dialog.set_m6_trend_metric("full_domain_counts")
        self.assertIs(self.dialog.m6_trend_data(), trend_data)
        self.assertEqual(self.dialog.m6_trend_legend_labels(), ("stable phase",))
        self.assertEqual(self.dialog.m6_trend_plot_values(), ((1, 1),))
        self.assertEqual(self.dialog.m6_trend_frame_values(), ((1, 2),))
        second_x, second_y = (
            self.dialog.m6_settings_panel.range_trends_panel.second_curve.getData()
        )
        self.assertTrue(second_x is None or len(second_x) == 0)
        self.assertTrue(second_y is None or len(second_y) == 0)

    def test_single_range_uses_analysis_aggregates_without_deltas_or_spatial_comparison(self) -> None:
        self.dialog.set_range_analysis_result(self.analysis)

        aggregates = self.analysis.aggregates
        summary = self.dialog.range_summary_text()
        self.assertIn("stable phase", summary)
        self.assertIn(f"Frames: {aggregates.analyzed_frame_count}", summary)
        self.assertIn(
            f"Mean molecules: {aggregates.mean_molecule_count:.3f}",
            summary,
        )
        self.assertIsNone(self.dialog.range_differences())
        self.assertIsNone(self.dialog.range_spatial_data())
        self.assertFalse(self.dialog.analysis_tab_enabled("Spatial comparison"))
        status = self.dialog.spatial_status_text().lower()
        self.assertIn("spatial comparison", status)
        self.assertIn("range deltas", status)
        self.assertIn("require two ranges", status)

    def test_comparison_after_single_restores_two_series_deltas_and_spatial_tab(self) -> None:
        self.dialog.set_range_analysis_result(self.analysis)
        self.dialog.set_analysis_mode("compare_ranges")
        self.dialog.set_range_analysis_result(self.comparison)

        self.assertIsInstance(
            self.dialog.range_trend_data(),
            MolecularRangeComparisonTrendData,
        )
        self.assertEqual(
            self.dialog.trend_legend_labels(),
            ("one domain", "two domains"),
        )
        self.assertEqual(
            self.dialog.m6_trend_legend_labels(),
            ("one domain", "two domains"),
        )
        self.assertIs(self.dialog.range_differences(), self.comparison.differences)
        self.assertTrue(self.dialog.analysis_tab_enabled("Spatial comparison"))
        self.assertIsNotNone(self.dialog.range_spatial_data())
        for plot in (
            self.dialog.molecule_count_trend_plot,
            self.dialog.nearest_neighbor_trend_plot,
            self.dialog.line_order_trend_plot,
            self.dialog.intensity_trend_plot,
        ):
            self.assertEqual(len(plot.listDataItems()), 2)

    def test_mode_change_invalidates_range_result_but_preserves_current_frame_data(self) -> None:
        current_plot_data = self.analysis.frame_results[0].plot_data
        self.dialog.set_plot_data(current_plot_data)
        self.dialog.set_analysis_mode("compare_ranges")
        self.dialog.set_range_analysis_result(self.comparison)
        self.dialog.activate_analysis_tab("Spatial comparison")
        displayed_points = self.dialog.displayed_points_xy()

        self.dialog.set_analysis_mode("single_range")

        self.assertIsNone(self.dialog.range_analysis_result())
        self.assertIsNone(self.dialog.range_trend_data())
        self.assertIsNone(self.dialog.range_spatial_data())
        self.assertEqual(self.dialog.active_analysis_tab(), "Range trends")
        self.assertEqual(self.dialog.displayed_points_xy(), displayed_points)
        self.assertTrue(np.array_equal(
            np.asarray(self.dialog.displayed_points_xy()),
            np.asarray(current_plot_data.points_xy),
        ))


@unittest.skipUnless(QApplication is not None, "PyQt6 is required for MolTrack GUI tests")
class PositionAnalysisSingleRangeContextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def tearDown(self) -> None:
        if hasattr(self, "window"):
            self.window.close()
            self.window.deleteLater()
            self.__class__._app.processEvents()

    def test_context_controls_invalidate_single_result_without_changing_source_data(self) -> None:
        calls = []

        def analyzer(series, frame_range, **kwargs):
            calls.append((frame_range, dict(kwargs)))
            return analyze_molecular_frame_range(series, frame_range, **kwargs)

        self.window = MolTrackMainWindow(
            yolo_model_discovery=lambda: [],
            position_range_analyzer=analyzer,
        )
        series = _series()
        detections = series.molecular_detections
        self.window.set_image_series(series)
        self.window.btn_position_analysis.click()
        dialog = self.window.position_analysis_dialog()
        dialog.set_analysis_mode("single_range")
        dialog.sp_first_range_start.setValue(1)
        dialog.sp_first_range_end.setValue(2)
        dialog.btn_run_range_analysis.click()

        self.assertEqual(len(calls), 1)
        dialog.cmb_intensity_metric.setCurrentText("Maximum")
        self.__class__._app.processEvents()

        self.assertEqual(len(calls), 1)
        self.assertIsNone(dialog.range_analysis_result())
        self.assertIsNone(dialog.range_trend_data())
        self.assertIn("Analyze range", dialog.range_summary_text())

        dialog.sp_background_outer_radius.setValue(4)
        self.__class__._app.processEvents()
        self.assertEqual(len(calls), 1)

        dialog.chk_use_segmentation_centroids.setChecked(False)
        self.__class__._app.processEvents()
        self.assertEqual(len(calls), 1)

        registration = object()
        segmentations = object()
        series.registration_results = registration
        series.molecular_segmentations = segmentations
        dialog.set_analysis_mode("compare_ranges")

        self.assertIs(series.molecular_detections, detections)
        self.assertIs(series.molecular_segmentations, segmentations)
        self.assertIs(series.registration_results, registration)

    def test_editing_completed_single_range_invalidates_stale_presentation(self) -> None:
        self.window = MolTrackMainWindow(yolo_model_discovery=lambda: [])
        self.window.set_image_series(_series())
        self.window.btn_position_analysis.click()
        dialog = self.window.position_analysis_dialog()
        dialog.set_analysis_mode("single_range")
        dialog.sp_first_range_start.setValue(1)
        dialog.sp_first_range_end.setValue(2)
        dialog.btn_run_range_analysis.click()
        self.assertIsNotNone(dialog.range_analysis_result())

        dialog.sp_first_range_end.setValue(3)
        self.__class__._app.processEvents()

        self.assertIsNone(dialog.range_analysis_result())
        self.assertIsNone(dialog.range_trend_data())
        self.assertIn("Analyze range", dialog.range_summary_text())


if __name__ == "__main__":
    unittest.main()
