import os
import time
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np

from moltrack.analysis import (
    TTMAPP_TEXTURE_DOMAIN_PRESET,
    TextureDomainPointInput,
    TextureDomainSessionState,
    analyze_texture_domain_descriptors,
    texture_domain_frame_fingerprint,
)
from moltrack.core import (
    MolecularDetection,
    MolecularDetectionSet,
    MolTrackImageSeries,
)
from nanotrack.core import STMSequenceMetadata

try:
    from PyQt6.QtWidgets import QApplication
except ImportError:  # pragma: no cover
    QApplication = None

if QApplication is not None:
    from moltrack.ui import MolTrackMainWindow


@unittest.skipUnless(QApplication is not None, "PyQt6 is required")
class TextureDomainMainWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.calls = []

        def analyzer(
            series,
            frame_range,
            *,
            source_view,
            settings,
            use_segmentation_centroids,
            progress_callback,
            cancel_requested,
        ):
            self.calls.append(
                (series, frame_range, source_view, use_segmentation_centroids)
            )
            frame_results = []
            for completed, frame_index in enumerate(
                frame_range.frame_indices,
                start=1,
            ):
                self.assertFalse(cancel_requested())
                points = tuple(
                    TextureDomainPointInput(
                        f"p-{frame_index}-{index}",
                        10.0 + index * 10.0,
                        20.0,
                    )
                    for index in range(5)
                )
                frame_results.append(
                    analyze_texture_domain_descriptors(
                        frame_index=frame_index,
                        source_view=source_view,
                        points=points,
                        descriptors=np.asarray(
                            (settings.prototype_histograms[0],) * 5,
                            dtype=np.float64,
                        ),
                        settings=settings,
                        frame_fingerprint=texture_domain_frame_fingerprint(
                            series.raw_frames[frame_index]
                        ),
                    )
                )
                progress_callback(
                    completed,
                    len(frame_range.frame_indices),
                    frame_index,
                )
            return TextureDomainSessionState(
                settings=settings,
                frame_results=tuple(frame_results),
                range_start_frame=frame_range.start_frame,
                range_end_frame=frame_range.end_frame,
            )

        self.window = MolTrackMainWindow(
            yolo_model_discovery=lambda: [],
            texture_domain_analyzer=analyzer,
        )
        detections = MolecularDetectionSet(frame_count=3)
        for frame_index in range(3):
            detections.set_detections(
                frame_index,
                [
                    MolecularDetection(
                        frame_index=frame_index,
                        bbox_xyxy=(
                            8.0 + index * 10.0,
                            18.0,
                            12.0 + index * 10.0,
                            22.0,
                        ),
                        confidence=0.9,
                        detection_id=f"p-{frame_index}-{index}",
                    )
                    for index in range(5)
                ],
                source_view="raw",
                frame_shape=(64, 64),
            )
        self.series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.zeros((3, 64, 64), dtype=np.float32),
            metadata=STMSequenceMetadata(
                pixels_x=64,
                pixels_y=64,
                size_nm_x=64.0,
                size_nm_y=64.0,
            ),
            molecular_detections=detections,
        )
        self.window.set_image_series(self.series)

    def tearDown(self):
        if self.window._texture_domain_controller.is_running:
            self.window._texture_domain_controller.cancel()
            self._process_until(
                lambda: not self.window._texture_domain_controller.is_running
            )
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()

    def _process_until(self, condition, timeout=3.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.app.processEvents()
            if condition():
                return
            time.sleep(0.005)
        self.fail("Timed out waiting for texture-domain main-window operation.")

    def test_menu_preset_opens_texture_tab_and_range_analysis_renders_result(self):
        self.window.action_texture_domain_preset_ttmapp.trigger()
        dialog = self.window.position_analysis_dialog()

        self.assertIsNotNone(dialog)
        self.assertEqual(
            dialog.tabs.tabText(dialog.tabs.currentIndex()),
            "Texture Domains",
        )
        self.assertEqual(
            dialog.texture_domains_panel.settings(),
            TTMAPP_TEXTURE_DOMAIN_PRESET,
        )
        self.assertEqual(
            self.window._current_ui_state()["position_analysis"]["active_tab"],
            "Texture Domains",
        )

        dialog.texture_domains_panel.start_frame.setValue(1)
        dialog.texture_domains_panel.end_frame.setValue(2)
        dialog.texture_domains_panel.run_button.click()
        self._process_until(
            lambda: not self.window._texture_domain_controller.is_running
        )

        self.assertEqual(len(self.calls), 1)
        self.assertIsInstance(
            self.series.texture_domain_state,
            TextureDomainSessionState,
        )
        self.assertEqual(len(self.series.texture_domain_state.frame_results), 2)
        self.assertEqual(
            self.window.viewer.visible_texture_domain_overlay_count(),
            5,
        )
        self.assertIn(
            "A: 5",
            dialog.texture_domains_panel.current_frame_label.text(),
        )

        dialog.chk_use_segmentation_centroids.setChecked(False)

        self.assertEqual(
            self.window.viewer.visible_texture_domain_overlay_count(),
            0,
        )
        self.assertEqual(dialog.texture_domains_panel.results_table.rowCount(), 0)
        self.assertIn(
            "another image view or centroid mode",
            dialog.texture_domains_panel.status_label.text().lower(),
        )
        dialog.chk_use_segmentation_centroids.setChecked(True)
        dialog.texture_domains_panel.opacity_slider.setValue(37)
        self.window.add_manual_bbox_from_pixel_drag((2.0, 2.0), (6.0, 6.0))

        self.assertIsInstance(
            self.series.texture_domain_state,
            TextureDomainSessionState,
        )
        self.assertFalse(self.series.texture_domain_state.computed)
        self.assertEqual(
            self.series.texture_domain_state.view_settings.opacity_percent,
            37,
        )
        self.assertEqual(dialog.texture_domains_panel.results_table.rowCount(), 0)
        self.assertIn(
            "invalidated",
            dialog.texture_domains_panel.status_label.text().lower(),
        )

    def test_bbox_change_outside_analyzed_range_preserves_result(self):
        self.window.action_texture_domain_preset_ttmapp.trigger()
        dialog = self.window.position_analysis_dialog()
        dialog.texture_domains_panel.end_frame.setValue(1)
        dialog.texture_domains_panel.opacity_slider.setValue(46)
        dialog.texture_domains_panel.run_button.click()
        self._process_until(
            lambda: not self.window._texture_domain_controller.is_running
        )
        self.assertTrue(self.series.texture_domain_state.computed)

        self.series.set_active_frame(2)
        self.window.add_manual_bbox_from_pixel_drag((2.0, 2.0), (6.0, 6.0))

        self.assertTrue(self.series.texture_domain_state.computed)
        self.assertEqual(
            self.series.texture_domain_state.view_settings.opacity_percent,
            46,
        )
        self.assertEqual(dialog.texture_domains_panel.results_table.rowCount(), 1)

    def test_view_settings_update_saved_state_without_recalculation(self):
        state = TextureDomainSessionState(
            settings=TTMAPP_TEXTURE_DOMAIN_PRESET,
            range_start_frame=0,
            range_end_frame=0,
        )
        self.series.texture_domain_state = state
        self.window._on_position_analysis_requested()
        dialog = self.window.position_analysis_dialog()

        dialog.texture_domains_panel.opacity_slider.setValue(42)

        self.assertEqual(
            self.series.texture_domain_state.view_settings.opacity_percent,
            42,
        )
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
