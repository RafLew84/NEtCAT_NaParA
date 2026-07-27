import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np

from moltrack.analysis import (
    TTMAPP_TEXTURE_DOMAIN_PRESET,
    TextureDomainPointInput,
    TextureDomainSessionState,
    TextureDomainViewSettings,
    analyze_texture_domain_descriptors,
)

try:
    from PyQt6.QtWidgets import QApplication
except ImportError:  # pragma: no cover
    QApplication = None

if QApplication is not None:
    from moltrack.ui.dialogs.position_analysis_dialog import (
        PositionAnalysisDialog,
    )
    from moltrack.ui.dialogs.texture_domains_panel import (
        TextureDomainAnalysisRequest,
        TextureDomainsPanel,
    )


@unittest.skipUnless(QApplication is not None, "PyQt6 is required")
class TextureDomainsPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.panel = TextureDomainsPanel()

    def tearDown(self):
        self.panel.deleteLater()
        self.app.processEvents()

    def test_panel_exposes_experimental_preset_and_configures_inclusive_range(self):
        self.panel.configure(
            frame_count=20,
            source_view="expanded_aligned",
            active_frame_index=8,
        )

        self.assertEqual(self.panel.preset_combo.count(), 1)
        self.assertIn("TTMAPP", self.panel.preset_combo.currentText())
        self.assertIn("experimental", self.panel.preset_combo.currentText().lower())
        self.assertEqual(self.panel.start_frame.value(), 9)
        self.assertEqual(self.panel.end_frame.value(), 14)
        self.assertEqual(self.panel.source_view_label.text(), "expanded aligned")
        self.assertTrue(self.panel.run_button.isEnabled())

    def test_run_emits_zero_based_request(self):
        requests = []
        self.panel.configure(
            frame_count=20,
            source_view="raw",
            active_frame_index=8,
        )
        self.panel.start_frame.setValue(9)
        self.panel.end_frame.setValue(12)
        self.panel.analysis_requested.connect(requests.append)

        self.panel.run_button.click()

        self.assertEqual(len(requests), 1)
        request = requests[0]
        self.assertIsInstance(request, TextureDomainAnalysisRequest)
        self.assertEqual(request.frame_range.start_frame, 8)
        self.assertEqual(request.frame_range.end_frame, 11)
        self.assertEqual(request.source_view, "raw")
        self.assertEqual(request.settings, TTMAPP_TEXTURE_DOMAIN_PRESET)

    def test_view_controls_emit_settings(self):
        settings = []
        self.panel.view_settings_changed.connect(settings.append)

        self.panel.opacity_slider.setValue(55)
        self.panel.show_unknown_checkbox.setChecked(True)

        self.assertEqual(settings[-1].opacity_percent, 55)
        self.assertTrue(settings[-1].show_unknown)

    def test_empty_state_restores_view_settings_without_claiming_result(self):
        state = TextureDomainSessionState(
            settings=TTMAPP_TEXTURE_DOMAIN_PRESET,
            view_settings=TextureDomainViewSettings(
                opacity_percent=63,
                show_unknown=True,
            ),
        )

        self.panel.set_session_state(state)

        self.assertEqual(self.panel.status_label.text(), "Not computed")
        self.assertEqual(self.panel.results_table.rowCount(), 0)
        self.assertEqual(self.panel.opacity_slider.value(), 63)
        self.assertTrue(self.panel.show_unknown_checkbox.isChecked())

    def test_reconfigure_updates_source_view_without_resetting_range(self):
        self.panel.configure(
            frame_count=20,
            source_view="raw",
            active_frame_index=8,
        )
        self.panel.start_frame.setValue(5)
        self.panel.end_frame.setValue(10)

        self.panel.configure(
            frame_count=20,
            source_view="expanded_aligned",
            active_frame_index=12,
        )

        self.assertEqual(self.panel.start_frame.value(), 5)
        self.assertEqual(self.panel.end_frame.value(), 10)
        self.assertEqual(
            self.panel.analysis_request().source_view,
            "expanded_aligned",
        )

    def test_current_frame_summary_reports_class_and_component_counts(self):
        custom = TTMAPP_TEXTURE_DOMAIN_PRESET
        descriptors = np.asarray(
            (
                custom.prototype_histograms[0],
                custom.prototype_histograms[0],
                custom.prototype_histograms[0],
                custom.prototype_histograms[0],
                custom.prototype_histograms[0],
            ),
            dtype=np.float64,
        )
        frame = analyze_texture_domain_descriptors(
            frame_index=3,
            source_view="raw",
            points=tuple(
                TextureDomainPointInput(f"p{index}", 10.0 + index * 10.0, 10.0)
                for index in range(5)
            ),
            descriptors=descriptors,
            settings=custom,
        )
        state = TextureDomainSessionState(
            settings=custom,
            frame_results=(frame,),
            range_start_frame=3,
            range_end_frame=3,
        )

        self.panel.set_session_state(state)
        self.panel.set_current_frame(3)

        self.assertIn("Frame 4", self.panel.current_frame_label.text())
        self.assertIn("A: 5", self.panel.current_frame_label.text())
        self.assertIn("domains: 1", self.panel.current_frame_label.text())
        self.assertEqual(self.panel.results_table.rowCount(), 1)
        self.assertEqual(self.panel.results_table.item(0, 0).text(), "4")

    def test_position_analysis_dialog_embeds_and_forwards_texture_panel(self):
        dialog = PositionAnalysisDialog()
        requests = []
        dialog.texture_domain_analysis_requested.connect(requests.append)
        dialog.configure_frame_ranges(
            frame_count=20,
            source_view="raw",
            active_frame_index=8,
        )
        dialog.set_texture_domain_current_frame(8)

        labels = tuple(
            dialog.tabs.tabText(index)
            for index in range(dialog.tabs.count())
        )
        self.assertIn("Texture Domains", labels)
        self.assertEqual(dialog.texture_domains_panel.start_frame.value(), 9)

        dialog.texture_domains_panel.end_frame.setValue(12)
        dialog.texture_domains_panel.run_button.click()

        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0].frame_range.start_frame, 8)
        self.assertEqual(requests[0].frame_range.end_frame, 11)
        dialog.deleteLater()


if __name__ == "__main__":
    unittest.main()
