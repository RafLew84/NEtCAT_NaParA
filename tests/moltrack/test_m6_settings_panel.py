import os
import unittest
from dataclasses import replace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from moltrack.analysis import (
    FirstShellSuggestionResult,
    MolecularM6OrientationAnalysisSettings,
)

try:
    from PyQt6.QtWidgets import QApplication, QAbstractButton, QLabel
except ImportError:  # pragma: no cover - optional outside target GUI env
    QApplication = None

if QApplication is not None:
    from moltrack.ui.dialogs import PositionAnalysisDialog


def _suggestion(radius_nm: float) -> FirstShellSuggestionResult:
    return FirstShellSuggestionResult(
        bin_centers_nm=(1.0, 2.0, radius_nm),
        raw_g_r=(0.8, 2.0, 0.7),
        smoothed_g_r=(0.9, 1.8, 0.8),
        valid_bin_mask=(True, True, True),
        smoothing_support=(1.0, 1.0, 1.0),
        search_min_radius_nm=1.0,
        peak_bin_index=1,
        peak_radius_nm=2.0,
        peak_value=1.8,
        peak_prominence=0.6,
        minimum_bin_index=2,
        minimum_radius_nm=radius_nm,
        minimum_value=0.8,
        suggested_first_shell_r_max_nm=radius_nm,
        quality_status="valid_suggestion",
        smoothing_method="gaussian_bins",
        smoothing_width_bins=2.0,
        minimum_expected_pair_exposure=5.0,
        minimum_contributing_frames=1,
        required_peak_prominence=0.1,
    )


@unittest.skipUnless(QApplication is not None, "PyQt6 is required for MolTrack GUI tests")
class MolecularM6SettingsPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.dialog = PositionAnalysisDialog()
        self.dialog.configure_frame_ranges(frame_count=4, source_view="raw")

    def tearDown(self) -> None:
        self.dialog.close()
        self.dialog.deleteLater()
        self.__class__._app.processEvents()

    def test_sixfold_tab_round_trips_complete_settings_and_uses_domain_terms(self) -> None:
        settings = replace(
            MolecularM6OrientationAnalysisSettings(),
            duplicate_max_distance_nm=0.4,
            first_shell_r_min_nm=0.9,
            first_shell_r_max_nm=2.8,
            q_seed=0.72,
            q_grow=0.31,
            min_neighbors_for_local_order=4,
            min_neighbors_for_seed=6,
            min_ordered_component_size=4,
            min_seed_size=7,
            min_domain_size=10,
            seed_angle_tolerance_deg=7.0,
            grow_angle_tolerance_deg=13.0,
            domain_merge_angle_tolerance_deg=6.0,
            min_bonds_for_domain_length_stats=7,
            domain_bond_length_robust_cv_qc_threshold=0.18,
            footprint_support_radius_nm=1.4,
            domain_conflict_margin=0.08,
        )

        self.dialog.set_m6_analysis_settings(settings)

        self.assertIn("Sixfold Bond Order", self.dialog.analysis_tab_labels())
        self.assertEqual(self.dialog.m6_analysis_settings(), settings)
        visible_text = "\n".join(
            [widget.text() for widget in self.dialog.findChildren(QLabel)]
            + [widget.text() for widget in self.dialog.findChildren(QAbstractButton)]
            + list(self.dialog.analysis_tab_labels())
        )
        self.assertIn("Local q6", visible_text)
        self.assertIn("Global q6 coherence", visible_text)
        self.assertIn("M6 orientation domains", visible_text)
        self.assertNotIn("Row order", visible_text)
        self.assertNotIn("Line order", visible_text)
        self.assertNotIn("Molecular row direction", visible_text)
        self.assertTrue(self.dialog.m6_advanced_group.isCheckable())

    def test_validation_blocks_run_and_explains_default_seed_neighbor_threshold(self) -> None:
        self.assertEqual(self.dialog.m6_min_neighbors_for_seed_spin.value(), 5)
        self.assertIn("3-4 neighbors", self.dialog.m6_validation_message())
        self.assertIn("do not initiate domains", self.dialog.m6_validation_message())
        self.assertTrue(self.dialog.m6_run_button.isEnabled())

        self.dialog.m6_first_shell_r_min_spin.setValue(3.0)
        self.dialog.m6_first_shell_r_max_spin.setValue(2.0)

        self.assertIn("first_shell_r_min_nm", self.dialog.m6_validation_message())
        self.assertFalse(self.dialog.m6_run_button.isEnabled())
        with self.assertRaises(ValueError):
            self.dialog.m6_analysis_settings()

        self.dialog.m6_first_shell_r_min_spin.setValue(1.0)
        self.dialog.m6_first_shell_r_max_spin.setValue(2.6)
        self.dialog.m6_min_neighbors_for_seed_spin.setValue(4)
        self.assertIn("at least 4 neighbors", self.dialog.m6_validation_message())
        self.assertNotIn("3-4 neighbors", self.dialog.m6_validation_message())

    def test_invalid_settings_disable_both_run_and_suggestion_requests(self) -> None:
        requests = []
        self.dialog.m6_first_shell_suggestion_requested.connect(requests.append)
        self.dialog.m6_first_shell_r_min_spin.setValue(3.0)
        self.dialog.m6_first_shell_r_max_spin.setValue(2.0)

        self.assertFalse(self.dialog.m6_run_button.isEnabled())
        self.assertFalse(self.dialog.m6_settings_panel.suggest_button.isEnabled())
        self.dialog.m6_settings_panel._request_suggestion()
        self.assertEqual(requests, [])

    def test_suggestion_is_displayed_without_mutating_r_max_until_applied(self) -> None:
        original = self.dialog.m6_analysis_settings().first_shell_r_max_nm
        requests = []
        self.dialog.m6_first_shell_suggestion_requested.connect(requests.append)

        self.dialog.m6_settings_panel.suggest_button.click()

        self.assertEqual(requests, [self.dialog.m6_analysis_settings()])
        self.assertEqual(self.dialog.m6_analysis_settings().first_shell_r_max_nm, original)

        self.dialog.set_m6_first_shell_suggestion(_suggestion(3.15))

        self.assertEqual(self.dialog.m6_analysis_settings().first_shell_r_max_nm, original)
        self.assertIn("3.150 nm", self.dialog.m6_suggestion_status_text())
        self.assertTrue(self.dialog.m6_apply_suggestion_button.isEnabled())

        self.dialog.apply_m6_first_shell_suggestion()

        self.assertEqual(self.dialog.m6_analysis_settings().first_shell_r_max_nm, 3.15)

    def test_editing_settings_invalidates_a_pending_first_shell_suggestion(self) -> None:
        self.dialog.set_m6_first_shell_suggestion(_suggestion(3.15))
        self.assertTrue(self.dialog.m6_apply_suggestion_button.isEnabled())

        self.dialog.m6_settings_panel.q_seed.setValue(0.7)

        self.assertFalse(self.dialog.m6_apply_suggestion_button.isEnabled())
        self.assertIn("out of date", self.dialog.m6_suggestion_status_text().lower())

        self.dialog.set_m6_first_shell_suggestion(_suggestion(3.15))
        self.dialog.edit_first_range_name.setText("changed condition")
        self.assertFalse(self.dialog.m6_apply_suggestion_button.isEnabled())
        self.assertIn("out of date", self.dialog.m6_suggestion_status_text().lower())

    def test_advanced_settings_round_trip_values_above_one_and_small_tolerances(self) -> None:
        settings = replace(
            MolecularM6OrientationAnalysisSettings(),
            geometry_absolute_tolerance_nm=1e-11,
            geometry_relative_tolerance=2.0,
            domain_conflict_margin=1.25,
        )

        self.dialog.set_m6_analysis_settings(settings)

        self.assertEqual(self.dialog.m6_analysis_settings(), settings)

    def test_run_signal_emits_one_validated_settings_model(self) -> None:
        received = []
        self.dialog.m6_analysis_requested.connect(received.append)

        self.dialog.m6_run_button.click()

        self.assertEqual(received, [self.dialog.m6_analysis_settings()])


if __name__ == "__main__":
    unittest.main()
