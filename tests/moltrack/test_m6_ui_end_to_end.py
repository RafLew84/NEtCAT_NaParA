import os
import tempfile
import time
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt6.QtWidgets import QApplication
except ImportError:  # pragma: no cover - optional outside target GUI env
    QApplication = None

if QApplication is not None:
    from moltrack.ui import MolTrackMainWindow

from test_m6_end_to_end import (
    M6ScientificAssertionsMixin,
    _REPRESENTATIVE_ANALYSIS_TIMEOUT_S,
    _analysis_by_source_frame,
    _headless_for_view,
    _headless_translation,
    _representative_fixture,
    _representative_series,
)


@unittest.skipUnless(
    QApplication is not None,
    "PyQt6 is required for MolTrack GUI tests",
)
class M6RepresentativePositionAnalysisUiTests(
    M6ScientificAssertionsMixin,
    unittest.TestCase,
):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def tearDown(self) -> None:
        if hasattr(self, "window"):
            self.window.close()
            self.window.deleteLater()
            self.__class__._app.processEvents()

    def process_events_until(self, condition, *, timeout_s: float) -> None:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            self.__class__._app.processEvents()
            if condition():
                return
            time.sleep(0.01)
        self.fail("Timed out waiting for representative Position Analysis.")

    def test_representative_fixture_runs_through_ui_worker_and_reuses_cache(self) -> None:
        manifest, headless_report = _representative_fixture()
        headless_results = _headless_for_view(
            headless_report,
            "expanded_aligned",
        )
        translation_xy = _headless_translation(manifest, "expanded_aligned")

        class ProgressRecordingWindow(MolTrackMainWindow):
            def __init__(self) -> None:
                self.m6_progress_events = []
                super().__init__(yolo_model_discovery=lambda: [])

            def _on_m6_analysis_progress(self, progress) -> None:
                self.m6_progress_events.append(
                    (
                        progress.completed_count,
                        progress.total_count,
                        progress.frame_index,
                    )
                )
                super()._on_m6_analysis_progress(progress)

        with tempfile.TemporaryDirectory() as tmpdir:
            source_path = Path(tmpdir) / "representative-ui.mpp"
            source_path.write_bytes(b"M6 representative UI fixture")
            series = _representative_series(manifest, source_path)
            self.window = ProgressRecordingWindow()
            self.window.set_image_series(series)
            self.window.cmb_registration_view_mode.setCurrentText(
                "Show expanded aligned"
            )
            self.window.btn_position_analysis.click()
            dialog = self.window.position_analysis_dialog()
            dialog.activate_analysis_tab("Sixfold Bond Order")
            dialog.set_m6_analysis_settings(manifest.accepted_settings)

            dialog.m6_run_button.click()
            self.assertTrue(self.window._m6_analysis_running)
            self.assertIsNotNone(self.window._m6_analysis_thread)
            self.assertTrue(self.window._m6_analysis_thread.isRunning())
            self.process_events_until(
                lambda: not self.window._m6_analysis_running,
                timeout_s=_REPRESENTATIVE_ANALYSIS_TIMEOUT_S,
            )
            comparison = dialog.range_comparison()
            self.assertIsNotNone(comparison)
            self.assertEqual(
                self.window.m6_progress_events,
                [(1, 2, 0), (2, 2, 1)],
            )
            for source_frame_index, result in _analysis_by_source_frame(
                comparison
            ).items():
                self.assert_analysis_matches_translated_headless(
                    result,
                    headless_results[source_frame_index],
                    translation_xy=translation_xy,
                )

            cache = series.structural_analysis_cache
            stats_after_first_run = cache.stats()
            first_comparison = comparison
            for frame_index in (1, 0, 1, 0):
                self.window.slider_frame.setValue(frame_index)
                self.__class__._app.processEvents()
            # Navigation retains the comparison without cache lookup or rebuild.
            self.assertIs(dialog.range_comparison(), first_comparison)
            self.assertEqual(
                cache.stats().entry_count,
                stats_after_first_run.entry_count,
            )
            self.assertEqual(
                cache.stats().estimated_bytes,
                stats_after_first_run.estimated_bytes,
            )

            self.window.m6_progress_events.clear()
            dialog.m6_run_button.click()
            self.process_events_until(
                lambda: not self.window._m6_analysis_running,
                timeout_s=_REPRESENTATIVE_ANALYSIS_TIMEOUT_S,
            )
            stats_after_repeat = cache.stats()
            self.assertEqual(
                stats_after_repeat.hit_count,
                stats_after_first_run.hit_count + 2,
            )
            self.assertEqual(
                stats_after_repeat.entry_count,
                stats_after_first_run.entry_count,
            )
            self.assertEqual(
                stats_after_repeat.estimated_bytes,
                stats_after_first_run.estimated_bytes,
            )


if __name__ == "__main__":
    unittest.main()
