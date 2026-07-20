import os
import time
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from moltrack.analysis import (
    M6DomainTypeAnalysisStore,
    M6DomainTypeClassificationSettings,
    MolecularFrameRange,
    adapt_m6_domain_type_analysis_source,
    analyze_molecular_frame_range,
    compare_molecular_frame_ranges,
)
from moltrack.ui.m6_domain_type_worker import M6DomainTypeAnalysisProgress
from test_m6_range_analysis import _m6_settings, _selection
from test_m6_range_trends_panel import _series

try:
    from PyQt6.QtWidgets import QApplication, QScrollArea
except ImportError:  # pragma: no cover - optional outside target GUI env
    QApplication = None

if QApplication is not None:
    from moltrack.ui import MolTrackMainWindow
    from moltrack.ui.dialogs import M6DomainTypesPanel, PositionAnalysisDialog


class _RecordingDomainTypeStore(M6DomainTypeAnalysisStore):
    def __init__(self) -> None:
        super().__init__()
        self.received_settings = []

    def compute(self, source, *, classification_settings, progress_callback=None):
        self.received_settings.append(classification_settings)
        return super().compute(
            source,
            classification_settings=classification_settings,
            progress_callback=progress_callback,
        )


@unittest.skipUnless(QApplication is not None, "PyQt6 is required for MolTrack GUI tests")
class M6DomainTypesPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])
        cls.series = _series()
        cls.single_analysis = analyze_molecular_frame_range(
            cls.series,
            MolecularFrameRange("stable phase", 0, 1),
            source_view="raw",
            m6_orientation_settings=_m6_settings(),
        )
        cls.single_source = adapt_m6_domain_type_analysis_source(
            cls.single_analysis,
            frame_count=cls.series.frame_count,
        )
        cls.comparison = compare_molecular_frame_ranges(
            cls.series,
            _selection(),
            m6_orientation_settings=_m6_settings(),
        )
        cls.compare_source = adapt_m6_domain_type_analysis_source(
            cls.comparison,
            frame_count=cls.series.frame_count,
        )

    def setUp(self) -> None:
        self.panel = M6DomainTypesPanel()

    def tearDown(self) -> None:
        self.panel.close()
        self.panel.deleteLater()
        self.__class__._app.processEvents()

    def test_position_dialog_places_scrollable_domain_types_after_m6(self) -> None:
        dialog = PositionAnalysisDialog()
        try:
            self.assertEqual(dialog.analysis_tab_labels()[-2:], (
                "Sixfold Bond Order",
                "Domain Types",
            ))
            self.assertIsInstance(dialog.domain_types_panel, QScrollArea)
            self.assertTrue(dialog.domain_types_panel.widgetResizable())
        finally:
            dialog.close()
            dialog.deleteLater()

    def test_controls_cover_settings_units_validation_and_non_tracking_tooltips(self) -> None:
        defaults = M6DomainTypeClassificationSettings()

        self.assertEqual(self.panel.settings(), defaults)
        self.assertEqual(self.panel.orientation_tolerance_deg.suffix(), " deg")
        self.assertEqual(self.panel.bond_length_tolerance_value.suffix(), " %")
        self.assertEqual(self.panel.minimum_observations_per_type.suffix(), " observations")
        for widget in self.panel.settings_widgets():
            self.assertIn("does not track", widget.toolTip().lower())

        self.panel.bond_length_tolerance_mode.setCurrentText("Absolute distance")
        self.panel.bond_length_tolerance_value.setValue(0.45)
        self.assertEqual(self.panel.bond_length_tolerance_value.suffix(), " nm")
        self.assertEqual(self.panel.settings().bond_length_tolerance_mode, "absolute_nm")
        self.assertEqual(self.panel.settings().bond_length_tolerance_value, 0.45)

        self.panel.set_analysis_source(self.single_source)
        self.assertTrue(self.panel.classify_button.isEnabled())
        self.panel.orientation_tolerance_deg.setValue(0.0)

        self.assertFalse(self.panel.classify_button.isEnabled())
        self.assertIn("greater than 0", self.panel.validation_message())

    def test_states_report_progress_result_frames_out_of_date_and_error(self) -> None:
        settings = M6DomainTypeClassificationSettings(
            minimum_observations_per_type=1,
        )
        self.panel.set_settings(settings)
        self.panel.set_analysis_source(self.compare_source)
        self.assertTrue(self.panel.classify_button.isEnabled())
        self.assertEqual(self.panel.classify_button.text(), "Classify Types")

        self.panel.set_running(True)
        self.panel.set_progress(M6DomainTypeAnalysisProgress(
            phase="extracting_observations",
            phase_number=1,
        ))
        self.assertFalse(self.panel.classify_button.isEnabled())
        self.assertIn("1/4", self.panel.status_text())
        self.assertIn("Extracting", self.panel.status_text())

        store = M6DomainTypeAnalysisStore()
        outcome = store.analyze(
            self.compare_source,
            classification_settings=settings,
        )
        self.panel.set_store_state(store.state)
        self.panel.set_running(False)

        status = self.panel.status_text()
        self.assertIn("Classified observations:", status)
        self.assertIn("Unclassified:", status)
        self.assertIn("one domain: 2/2", status)
        self.assertIn("two domains: 2/2", status)
        self.assertEqual(self.panel.classify_button.text(), "Recalculate Types")
        self.assertIs(self.panel.outcome(), outcome)

        store.invalidate("classification_settings")
        self.panel.set_store_state(store.state)
        self.assertIn("out of date", self.panel.status_text().lower())
        self.assertTrue(self.panel.classify_button.isEnabled())

        self.panel.set_error("synthetic classification failure")
        self.assertIn("synthetic classification failure", self.panel.status_text())


@unittest.skipUnless(QApplication is not None, "PyQt6 is required for MolTrack GUI tests")
class M6DomainTypesPanelMainWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def tearDown(self) -> None:
        if hasattr(self, "window"):
            self.window.close()
            self.window.deleteLater()
            self.__class__._app.processEvents()

    def process_events_until(self, condition, *, timeout_s: float = 5.0) -> None:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            self.__class__._app.processEvents()
            if condition():
                return
            time.sleep(0.005)
        self.fail("Timed out waiting for Qt event-loop condition.")

    def test_classify_uses_current_m6_source_and_one_settings_model(self) -> None:
        store = _RecordingDomainTypeStore()
        self.window = MolTrackMainWindow(
            yolo_model_discovery=lambda: [],
            m6_domain_type_store=store,
        )
        self.window.set_image_series(_series())
        self.window.btn_position_analysis.click()
        dialog = self.window.position_analysis_dialog()
        panel = dialog.domain_types_panel
        self.assertFalse(panel.classify_button.isEnabled())

        dialog.set_analysis_mode("single_range")
        dialog.edit_first_range_name.setText("stable phase")
        dialog.sp_first_range_start.setValue(1)
        dialog.sp_first_range_end.setValue(2)
        dialog.set_m6_analysis_settings(_m6_settings())
        dialog.m6_run_button.click()
        self.process_events_until(lambda: not self.window._m6_analysis_running)
        self.assertTrue(panel.classify_button.isEnabled())

        self.window._m6_analysis_running = True
        self.window._sync_m6_domain_type_panel()
        self.assertFalse(panel.classify_button.isEnabled())
        self.assertIn("Run/Recalculate M6", panel.status_text())
        self.window._m6_analysis_running = False
        self.window._sync_m6_domain_type_panel()
        self.assertTrue(panel.classify_button.isEnabled())

        panel.orientation_tolerance_deg.setValue(7.0)
        panel.bond_length_tolerance_mode.setCurrentText("Absolute distance")
        panel.bond_length_tolerance_value.setValue(0.4)
        panel.minimum_observations_per_type.setValue(2)
        panel.include_small_ordered_islands.setChecked(True)
        panel.exclude_bond_length_heterogeneity_qc.setChecked(False)
        requested_settings = []
        panel.classification_requested.connect(requested_settings.append)

        panel.classify_button.click()
        self.process_events_until(
            lambda: not self.window._m6_domain_type_controller.is_running
        )

        self.assertEqual(len(requested_settings), 1)
        self.assertEqual(len(store.received_settings), 1)
        self.assertIs(store.received_settings[0], requested_settings[0])
        self.assertEqual(requested_settings[0], panel.settings())
        self.assertIn("Classified observations:", panel.status_text())
        self.assertIn("stable phase", panel.status_text())

        panel.orientation_tolerance_deg.setValue(8.0)
        self.__class__._app.processEvents()
        self.assertIn("out of date", panel.status_text().lower())
        self.assertTrue(panel.classify_button.isEnabled())


if __name__ == "__main__":
    unittest.main()
