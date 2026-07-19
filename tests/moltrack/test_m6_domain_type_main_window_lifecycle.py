import os
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np

from moltrack.analysis import (
    MolecularFrameRange,
    MolecularFrameRangeSelection,
    compare_molecular_frame_ranges,
)
from moltrack.core import (
    MolTrackImageSeries,
    MolTrackRegistrationFrameResult,
    MolTrackRegistrationResultSet,
    MolTrackRegistrationSettings,
)
from nanotrack.core import STMSequenceMetadata

try:
    from PyQt6.QtWidgets import QApplication
except ImportError:  # pragma: no cover - optional outside target GUI env
    QApplication = None

if QApplication is not None:
    from moltrack.ui import MolTrackMainWindow


class _BlockingDomainTypeStore:
    def __init__(self) -> None:
        self.started = threading.Event()
        self.release = threading.Event()
        self.clear_count = 0
        self.publish_calls = []
        self.invalidation_reasons = []
        self.compute_count = 0
        self.state = "empty"

    def clear(self) -> None:
        self.clear_count += 1
        self.state = "empty"

    def invalidate(self, reason) -> bool:
        self.invalidation_reasons.append(str(reason))
        self.state = f"out_of_date:{reason}"
        return True

    def compute(self, source, *, classification_settings, progress_callback):
        del source, classification_settings
        self.compute_count += 1
        progress_callback("extracting_observations")
        self.started.set()
        if not self.release.wait(timeout=2.0):
            raise RuntimeError("Test did not release the domain type worker.")
        progress_callback("complete_linkage")
        progress_callback("aggregating")
        return "stale computation"

    def publish(self, computation):
        self.publish_calls.append(computation)
        self.state = "current"
        return computation


def _series(name: str) -> MolTrackImageSeries:
    return MolTrackImageSeries(
        source_path=name,
        raw_frames=np.zeros((2, 8, 8), dtype=np.float32),
        metadata=STMSequenceMetadata(
            pixels_x=8,
            pixels_y=8,
            size_nm_x=8.0,
            size_nm_y=8.0,
        ),
    )


@unittest.skipUnless(QApplication is not None, "PyQt6 is required for GUI tests")
class M6DomainTypeMainWindowLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def tearDown(self) -> None:
        if hasattr(self, "window"):
            self.window.close()
            self.window.deleteLater()
            self.__class__._app.processEvents()

    def process_events_until(self, condition, *, timeout_s: float = 3.0) -> None:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            self.__class__._app.processEvents()
            if condition():
                return
            time.sleep(0.005)
        self.fail("Timed out waiting for Qt event-loop condition.")

    def test_window_keeps_navigation_live_and_discards_result_on_series_change(self) -> None:
        store = _BlockingDomainTypeStore()
        self.window = MolTrackMainWindow(
            yolo_model_discovery=lambda: [],
            m6_domain_type_store=store,
        )
        self.window.set_image_series(_series("first.mpp"))
        controller = self.window._m6_domain_type_controller
        canceled = []
        controller.canceled.connect(lambda: canceled.append(True))

        self.assertTrue(controller.start(object(), classification_settings=object()))
        self.process_events_until(store.started.is_set)

        self.assertFalse(self.window._is_processing())
        self.assertTrue(self.window.slider_frame.isEnabled())
        close_event = Mock()
        self.window.closeEvent(close_event)
        close_event.ignore.assert_called_once_with()

        self.window.set_image_series(_series("second.mpp"))
        store.release.set()
        self.process_events_until(lambda: bool(canceled))
        self.process_events_until(lambda: not controller.is_running)

        self.assertEqual(store.clear_count, 2)
        self.assertEqual(store.publish_calls, [])

    def test_scientific_context_controls_invalidate_without_automatic_classification(self) -> None:
        store = _BlockingDomainTypeStore()
        self.window = MolTrackMainWindow(
            yolo_model_discovery=lambda: [],
            m6_domain_type_store=store,
        )
        self.window.set_image_series(_series("movie.mpp"))
        self.window.btn_position_analysis.click()
        dialog = self.window.position_analysis_dialog()
        store.invalidation_reasons.clear()

        dialog.sp_first_range_end.setValue(
            min(dialog.sp_first_range_end.maximum(), dialog.sp_first_range_end.value() + 1)
        )
        dialog.chk_use_segmentation_centroids.setChecked(False)
        dialog.m6_settings_panel.q_seed.setValue(0.81)
        dialog.analysis_mode_changed.emit("single_range")
        self.window._on_m6_domain_type_settings_changed(object())

        self.assertEqual(
            set(store.invalidation_reasons),
            {
                "analysis_mode",
                "frame_ranges",
                "m6_settings",
                "classification_settings",
                "centroid_source",
            },
        )
        self.assertEqual(store.compute_count, 0)

    def test_registration_view_control_invalidates_source_view(self) -> None:
        store = _BlockingDomainTypeStore()
        expanded_stack = SimpleNamespace(
            frames=np.zeros((2, 10, 10), dtype=np.float32),
            metadata=STMSequenceMetadata(
                pixels_x=10,
                pixels_y=10,
                size_nm_x=10.0,
                size_nm_y=10.0,
            ),
            padding_ltrb=(1, 1, 1, 1),
            frame_origins_xy=np.zeros((2, 2), dtype=np.float64),
        )

        def expanded_builder(series):
            series.expanded_aligned_stack = expanded_stack
            return expanded_stack

        self.window = MolTrackMainWindow(
            yolo_model_discovery=lambda: [],
            m6_domain_type_store=store,
            expanded_aligned_builder=expanded_builder,
        )
        series = _series("movie.mpp")
        series.registration_results = MolTrackRegistrationResultSet(
            settings=MolTrackRegistrationSettings(),
            results_by_frame={
                frame_index: MolTrackRegistrationFrameResult(
                    frame_index=frame_index,
                    shift_xy=(0.0, 0.0),
                    method="identity",
                    quality_score=1.0,
                )
                for frame_index in range(series.frame_count)
            },
        )
        self.window.set_image_series(series)
        self.window.btn_position_analysis.click()
        store.invalidation_reasons.clear()

        self.window.cmb_registration_view_mode.setCurrentText(
            "Show expanded aligned"
        )
        self.__class__._app.processEvents()

        self.assertEqual(store.invalidation_reasons, ["source_view"])

    def test_programmatic_range_restore_can_suppress_one_context_notification(self) -> None:
        store = _BlockingDomainTypeStore()
        self.window = MolTrackMainWindow(
            yolo_model_discovery=lambda: [],
            m6_domain_type_store=store,
        )
        self.window.set_image_series(_series("movie.mpp"))
        self.window.btn_position_analysis.click()
        dialog = self.window.position_analysis_dialog()
        changed = MolecularFrameRangeSelection(
            frame_count=2,
            source_view="raw",
            first_range=MolecularFrameRange("first", 0, 0),
            second_range=MolecularFrameRange("second", 1, 1),
        )
        store.invalidation_reasons.clear()

        dialog.apply_frame_range_selection(changed, notify=False)

        self.assertEqual(store.invalidation_reasons, [])

        dialog.apply_frame_range_selection(
            MolecularFrameRangeSelection(
                frame_count=2,
                source_view="raw",
                first_range=MolecularFrameRange("renamed", 0, 0),
                second_range=MolecularFrameRange("second", 1, 1),
            )
        )

        self.assertEqual(store.invalidation_reasons, ["frame_ranges"])

    def test_ttmapp_preset_invalidates_m6_settings_without_classification(self) -> None:
        store = _BlockingDomainTypeStore()
        self.window = MolTrackMainWindow(
            yolo_model_discovery=lambda: [],
            m6_domain_type_store=store,
        )
        self.window.set_image_series(_series("movie.mpp"))
        store.invalidation_reasons.clear()

        self.window.action_m6_preset_ttmapp.trigger()

        self.assertEqual(store.invalidation_reasons, ["m6_settings"])
        self.assertEqual(store.compute_count, 0)

    def test_m6_view_and_opacity_changes_do_not_invalidate_domain_types(self) -> None:
        store = _BlockingDomainTypeStore()
        self.window = MolTrackMainWindow(
            yolo_model_discovery=lambda: [],
            m6_domain_type_store=store,
        )
        self.window.set_image_series(_series("movie.mpp"))
        self.window.btn_position_analysis.click()
        dialog = self.window.position_analysis_dialog()
        store.invalidation_reasons.clear()

        dialog.m6_settings_panel.overlay_opacity.setValue(37)
        dialog.set_m6_overlay_mode("orientation")
        dialog.m6_settings_panel.show_unassigned_points.setChecked(False)

        self.assertEqual(store.invalidation_reasons, [])
        self.assertEqual(store.compute_count, 0)

    def test_recalculate_m6_invalidates_types_before_m6_backend_starts(self) -> None:
        store = _BlockingDomainTypeStore()
        backend_started = threading.Event()
        release_backend = threading.Event()
        reason_seen_by_backend = []

        def comparator(series, selection, **kwargs):
            reason_seen_by_backend.append(store.invalidation_reasons[-1])
            backend_started.set()
            if not release_backend.wait(timeout=2.0):
                raise RuntimeError("Test did not release the M6 backend.")
            return compare_molecular_frame_ranges(series, selection, **kwargs)

        self.window = MolTrackMainWindow(
            yolo_model_discovery=lambda: [],
            m6_domain_type_store=store,
            position_range_comparator=comparator,
        )
        self.window.set_image_series(_series("movie.mpp"))
        self.window.btn_position_analysis.click()
        dialog = self.window.position_analysis_dialog()
        store.invalidation_reasons.clear()

        with patch("moltrack.ui.main_window.QMessageBox.critical") as critical:
            dialog.m6_run_button.click()
            self.process_events_until(backend_started.is_set)

            self.assertEqual(reason_seen_by_backend, ["m6_recalculation"])
            release_backend.set()
            self.process_events_until(lambda: not self.window._m6_analysis_running)

        critical.assert_not_called()


if __name__ == "__main__":
    unittest.main()
