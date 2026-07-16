import math
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from moltrack.analysis import (
    MolecularM6OrientationAnalysisSettings,
    PairCorrelationResult,
    suggest_first_shell_r_max,
)

try:
    from PyQt6.QtWidgets import QApplication
except ImportError:  # pragma: no cover - optional outside target GUI env
    QApplication = None

if QApplication is not None:
    from moltrack.ui.dialogs.m6_pair_correlation_plot import M6PairCorrelationPlot


def _settings() -> MolecularM6OrientationAnalysisSettings:
    return MolecularM6OrientationAnalysisSettings(
        first_shell_r_min_nm=1.0,
        first_shell_r_max_nm=2.6,
        gr_bin_width_nm=0.5,
        gr_max_nm=6.0,
        gr_min_expected_pair_exposure=50.0,
        gr_min_contributing_frames=1,
        gr_smoothing_method="gaussian_bins",
        gr_smoothing_width=0.2,
        gr_peak_prominence=0.3,
    )


def _pair_correlation(g_values: tuple[float, ...]) -> PairCorrelationResult:
    width = 0.5
    edges = tuple(index * width for index in range(len(g_values) + 1))
    centers = tuple((left + right) / 2.0 for left, right in zip(edges, edges[1:]))
    exposure = tuple(100.0 if math.isfinite(value) else float("nan") for value in g_values)
    observed = tuple(
        int(round(value * expected))
        if math.isfinite(value) and math.isfinite(expected)
        else 0
        for value, expected in zip(g_values, exposure)
    )
    status = tuple(
        "valid" if math.isfinite(value) else "insufficient_exposure"
        for value in g_values
    )
    point_count = 100
    return PairCorrelationResult(
        bin_edges_nm=edges,
        bin_centers_nm=centers,
        g_r=g_values,
        observed_unordered_pair_count=observed,
        expected_pair_exposure=exposure,
        bin_status=status,
        contributing_frame_count=tuple(int(math.isfinite(value)) for value in g_values),
        point_count=point_count,
        total_unordered_pair_count=point_count * (point_count - 1) // 2,
        min_expected_pair_exposure=1.0,
        window_area_nm2=100.0,
        window_geometry_status="rectangular_translation_correction",
        frame_index=0,
        representative_point_ids=tuple(f"point-{index}" for index in range(point_count)),
        coordinate_frame="sample_nm",
        spatial_calibration_fingerprint="calibration-v1",
        registration_fingerprint="registration-v1",
        point_coordinate_fingerprint="coordinates-v1",
        window_origin_nm=(0.0, 0.0),
    )


@unittest.skipUnless(QApplication is not None, "PyQt6 is required for MolTrack GUI tests")
class M6PairCorrelationPlotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.plot = M6PairCorrelationPlot()

    def tearDown(self) -> None:
        self.plot.close()
        self.plot.deleteLater()
        self.__class__._app.processEvents()

    def test_known_pair_correlation_shows_curves_axes_and_physical_markers(self) -> None:
        pair_correlation = _pair_correlation(
            (0.2, 1.8, 0.4, 0.7, 1.7, 0.8, 0.0, 0.6, 0.9, 0.7, 0.8, 0.7)
        )
        suggestion = suggest_first_shell_r_max(pair_correlation, settings=_settings())

        self.plot.set_shell_bounds(1.0, 2.6, gr_max_nm=6.0)
        self.plot.set_suggestion_result(suggestion)

        self.assertEqual(self.plot.axis_labels(), ("Radius [nm]", "g(r)"))
        self.assertEqual(
            self.plot.raw_curve_data(),
            (pair_correlation.bin_centers_nm, pair_correlation.g_r),
        )
        self.assertEqual(
            self.plot.smoothed_curve_data(),
            (suggestion.bin_centers_nm, suggestion.smoothed_g_r),
        )
        self.assertEqual(
            self.plot.marker_positions_nm(),
            {
                "first_shell_r_min": 1.0,
                "current_first_shell_r_max": 2.6,
                "first_peak": 2.25,
                "suggested_minimum": 3.25,
            },
        )
        self.assertEqual(
            self.plot.marker_visibility(),
            {
                "first_shell_r_min": True,
                "current_first_shell_r_max": True,
                "first_peak": True,
                "suggested_minimum": True,
            },
        )
        self.assertIn("reliable", self.plot.status_text().lower())

    def test_insufficient_data_keeps_curves_but_hides_arbitrary_peak_and_minimum(self) -> None:
        pair_correlation = _pair_correlation((0.0,) * 12)
        suggestion = suggest_first_shell_r_max(pair_correlation, settings=_settings())

        self.plot.set_shell_bounds(1.0, 2.6, gr_max_nm=6.0)
        self.plot.set_suggestion_result(suggestion)

        self.assertEqual(suggestion.quality_status, "no_reliable_peak")
        self.assertTrue(self.plot.has_result())
        self.assertFalse(self.plot.marker_visibility()["first_peak"])
        self.assertFalse(self.plot.marker_visibility()["suggested_minimum"])
        self.assertIsNone(self.plot.marker_positions_nm()["first_peak"])
        self.assertIsNone(self.plot.marker_positions_nm()["suggested_minimum"])
        self.assertIn("no reliable peak", self.plot.status_text().lower())

    def test_dragged_current_r_max_emits_the_same_physical_radius(self) -> None:
        received = []
        self.plot.current_r_max_changed.connect(received.append)
        self.plot.set_shell_bounds(1.0, 2.6, gr_max_nm=6.0)

        self.plot.current_r_max_line.setValue(3.4)

        self.assertEqual(received[-1], 3.4)
        self.assertEqual(
            self.plot.marker_positions_nm()["current_first_shell_r_max"],
            3.4,
        )


if __name__ == "__main__":
    unittest.main()
