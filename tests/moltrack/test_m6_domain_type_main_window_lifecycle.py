import os
import threading
import time
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np

from moltrack.analysis import (
    M6DomainTypeAnalysisStore,
    M6DomainTypeSessionState,
    MolecularFrameRange,
    MolecularFrameRangeSelection,
    MolecularM6SessionState,
    adapt_m6_domain_type_analysis_source,
    build_m6_domain_type_analysis_context,
    compare_molecular_frame_ranges,
)
from moltrack.core import (
    MolTrackImageSeries,
    MolTrackRegistrationFrameResult,
    MolTrackRegistrationResultSet,
    MolTrackRegistrationSettings,
    MolTrackPositionAnalysisRange,
    MolTrackPositionAnalysisState,
)
from nanotrack.core import STMSequenceMetadata

try:
    from PyQt6.QtWidgets import QApplication, QMessageBox
except ImportError:  # pragma: no cover - optional outside target GUI env
    QApplication = None

if QApplication is not None:
    from moltrack.ui import MolTrackMainWindow
    from moltrack.ui.dialogs import PositionAnalysisDialog

from test_m6_domain_type_lifecycle import (
    _comparison,
    _m6_settings,
    _range_analysis,
    _type_settings,
)


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

    def _restorable_domain_type_state(self):
        before = MolecularFrameRange("before desorption", 0, 0)
        after = MolecularFrameRange("after adsorption", 1, 1)
        result = _comparison(
            _range_analysis(before),
            _range_analysis(after),
        )
        source = adapt_m6_domain_type_analysis_source(result, frame_count=2)
        settings = _type_settings()
        outcome = M6DomainTypeAnalysisStore().analyze(
            source,
            classification_settings=settings,
        )
        return result, M6DomainTypeSessionState.from_outcome(outcome)

    def _saved_position_state(self) -> MolTrackPositionAnalysisState:
        return MolTrackPositionAnalysisState(
            source_view="raw",
            first_range=MolTrackPositionAnalysisRange(
                "before desorption",
                0,
                0,
            ),
            second_range=MolTrackPositionAnalysisRange(
                "after adsorption",
                1,
                1,
            ),
            comparison_completed=True,
            active_tab="Domain Types",
            use_segmentation_centroids=True,
        )

    def _saved_single_range_position_state(self) -> MolTrackPositionAnalysisState:
        return MolTrackPositionAnalysisState(
            source_view="raw",
            first_range=MolTrackPositionAnalysisRange("condition", 0, 1),
            second_range=MolTrackPositionAnalysisRange("unused", 0, 0),
            comparison_completed=True,
            active_tab="Domain Types",
            use_segmentation_centroids=True,
        )

    @staticmethod
    def _set_range_result_without_plot_rendering(
        dialog,
        result,
        *,
        density_grid_shape=(32, 32),
    ) -> None:
        del density_grid_shape
        dialog._range_analysis_result = result
        dialog._range_comparison = result

    def test_open_state_restores_exact_domain_types_after_async_m6(self) -> None:
        result, saved_domain_state = self._restorable_domain_type_state()
        restored_store = M6DomainTypeAnalysisStore()
        self.window = MolTrackMainWindow(
            yolo_model_discovery=lambda: [],
            m6_domain_type_store=restored_store,
            position_range_comparator=lambda *_args, **_kwargs: result,
        )
        series = _series("movie.mpp")
        series.m6_analysis_state = MolecularM6SessionState(
            enabled=True,
            source_view="raw",
            use_segmentation_centroids=True,
            settings=_m6_settings(),
        )
        session = SimpleNamespace(
            registration_view_mode="Show raw",
            position_analysis=self._saved_position_state(),
            m6_domain_type_analysis_state=saved_domain_state,
        )
        context_thread_ids = []

        def build_context_off_ui_thread(*args, **kwargs):
            context_thread_ids.append(threading.get_ident())
            return build_m6_domain_type_analysis_context(*args, **kwargs)

        started_at = time.monotonic()
        render_overlay = Mock()
        with patch.object(
            PositionAnalysisDialog,
            "set_range_analysis_result",
            new=self._set_range_result_without_plot_rendering,
        ), patch.object(
            MolTrackMainWindow,
            "_set_m6_first_shell_suggestion_from_result",
            new=lambda *_args, **_kwargs: None,
        ), patch.object(
            MolTrackMainWindow,
            "_render_current_m6_overlay",
            new=render_overlay,
        ), patch(
            "moltrack.ui.main_window.build_m6_domain_type_analysis_context",
            side_effect=build_context_off_ui_thread,
        ):
            self.window._apply_loaded_state("state.moltrack.json", session, series)
            elapsed = time.monotonic() - started_at

            self.assertLess(elapsed, 0.2)
            self.assertTrue(self.window._m6_analysis_running)
            self.process_events_until(lambda: not self.window._m6_analysis_running)

        dialog = self.window.position_analysis_dialog()
        self.assertEqual(restored_store.state.status, "current")
        self.assertEqual(
            restored_store.current,
            saved_domain_state.cache_record.outcome,
        )
        self.assertEqual(
            dialog.domain_types_panel.settings(),
            saved_domain_state.classification_settings,
        )
        self.assertEqual(
            dialog.frame_range_analysis_scope(),
            saved_domain_state.analysis_scope,
        )
        self.assertEqual(dialog.active_analysis_tab(), "Domain Types")
        self.assertIs(
            dialog.domain_types_panel.outcome(),
            restored_store.current,
        )
        self.assertIs(
            dialog.domain_types_panel.results_table.table_result(),
            restored_store.current.table_result,
        )
        self.assertIs(
            dialog.domain_types_panel.plots_panel.outcome(),
            restored_store.current,
        )
        self.assertEqual(
            tuple(value.name for value in restored_store.current.analysis_scope.ranges),
            ("before desorption", "after adsorption"),
        )
        self.assertGreater(render_overlay.call_count, 0)
        self.assertEqual(len(context_thread_ids), 1)
        self.assertNotEqual(context_thread_ids[0], threading.get_ident())

    def test_save_open_json_restores_domain_type_result(self) -> None:
        result, saved_domain_state = self._restorable_domain_type_state()
        with tempfile.TemporaryDirectory() as tmpdir:
            source_path = Path(tmpdir) / "movie.mpp"
            state_path = Path(tmpdir) / "state.moltrack.json"
            source_path.write_bytes(b"synthetic mpp source")
            source_store = M6DomainTypeAnalysisStore()
            source_series = _series(str(source_path))
            source_series.m6_analysis_state = MolecularM6SessionState(
                enabled=True,
                source_view="raw",
                use_segmentation_centroids=True,
                settings=_m6_settings(),
            )
            self.window = MolTrackMainWindow(
                yolo_model_discovery=lambda: [],
                m6_domain_type_store=source_store,
            )
            self.window.set_image_series(source_series)
            self.window._on_position_analysis_requested()
            source_dialog = self.window.position_analysis_dialog()
            self.window._restore_m6_domain_type_configuration(
                source_dialog,
                saved_domain_state,
            )
            source_dialog.set_m6_analysis_settings(_m6_settings())
            source_dialog._range_analysis_result = result
            source_dialog.activate_analysis_tab("Domain Types")
            source_store.restore(
                build_m6_domain_type_analysis_context(
                    adapt_m6_domain_type_analysis_source(result, frame_count=2),
                    classification_settings=(
                        saved_domain_state.classification_settings
                    ),
                ),
                saved_domain_state.cache_record.outcome,
            )

            self.window.save_state(state_path)
            self.assertTrue(state_path.is_file())
            self.window.close()
            self.window.deleteLater()
            self.__class__._app.processEvents()

            restored_store = M6DomainTypeAnalysisStore()

            def restore_series(session):
                restored = _series(session.source_path)
                restored.m6_analysis_state = session.m6_analysis_state
                return restored

            self.window = MolTrackMainWindow(
                yolo_model_discovery=lambda: [],
                m6_domain_type_store=restored_store,
                session_restorer=restore_series,
                position_range_comparator=lambda *_args, **_kwargs: result,
            )
            with patch.object(
                PositionAnalysisDialog,
                "set_range_analysis_result",
                new=self._set_range_result_without_plot_rendering,
            ), patch.object(
                MolTrackMainWindow,
                "_set_m6_first_shell_suggestion_from_result",
                new=lambda *_args, **_kwargs: None,
            ), patch.object(
                MolTrackMainWindow,
                "_render_current_m6_overlay",
                new=lambda *_args, **_kwargs: None,
            ):
                self.window.open_state(state_path)
                self.process_events_until(
                    lambda: not self.window._m6_analysis_running
                )

            restored_dialog = self.window.position_analysis_dialog()
            self.assertEqual(restored_store.state.status, "current")
            self.assertEqual(
                restored_store.current,
                saved_domain_state.cache_record.outcome,
            )
            self.assertEqual(restored_dialog.active_analysis_tab(), "Domain Types")

    def test_open_state_restores_single_range_domain_types(self) -> None:
        frame_range = MolecularFrameRange("condition", 0, 1)
        result = _range_analysis(frame_range)
        source = adapt_m6_domain_type_analysis_source(result, frame_count=2)
        saved_domain_state = M6DomainTypeSessionState.from_outcome(
            M6DomainTypeAnalysisStore().analyze(
                source,
                classification_settings=_type_settings(),
            )
        )
        restored_store = M6DomainTypeAnalysisStore()
        self.window = MolTrackMainWindow(
            yolo_model_discovery=lambda: [],
            m6_domain_type_store=restored_store,
            position_range_analyzer=lambda *_args, **_kwargs: result,
        )
        series = _series("movie.mpp")
        series.m6_analysis_state = MolecularM6SessionState(
            enabled=True,
            source_view="raw",
            use_segmentation_centroids=True,
            settings=_m6_settings(),
        )
        session = SimpleNamespace(
            registration_view_mode="Show raw",
            position_analysis=self._saved_single_range_position_state(),
            m6_domain_type_analysis_state=saved_domain_state,
        )

        with patch.object(
            PositionAnalysisDialog,
            "set_range_analysis_result",
            new=self._set_range_result_without_plot_rendering,
        ), patch.object(
            MolTrackMainWindow,
            "_set_m6_first_shell_suggestion_from_result",
            new=lambda *_args, **_kwargs: None,
        ), patch.object(
            MolTrackMainWindow,
            "_render_current_m6_overlay",
            new=lambda *_args, **_kwargs: None,
        ):
            self.window._apply_loaded_state("state.moltrack.json", session, series)
            self.process_events_until(lambda: not self.window._m6_analysis_running)

        dialog = self.window.position_analysis_dialog()
        self.assertEqual(dialog.analysis_mode(), "single_range")
        self.assertEqual(dialog.frame_range_analysis_scope(), saved_domain_state.analysis_scope)
        self.assertEqual(restored_store.state.status, "current")

    def test_save_marks_completed_single_range_analysis_for_restore(self) -> None:
        self.window = MolTrackMainWindow(yolo_model_discovery=lambda: [])
        self.window.set_image_series(_series("movie.mpp"))
        self.window._on_position_analysis_requested()
        dialog = self.window.position_analysis_dialog()
        frame_range = MolecularFrameRange("condition", 0, 1)
        dialog.set_analysis_mode("single_range", notify=False)
        dialog.apply_frame_range_selection(
            MolecularFrameRangeSelection(
                frame_count=2,
                source_view="raw",
                first_range=frame_range,
                second_range=MolecularFrameRange("unused", 0, 0),
            ),
            notify=False,
        )
        dialog._range_analysis_result = _range_analysis(frame_range)

        ui_state = self.window._current_ui_state()

        self.assertTrue(ui_state["position_analysis"]["comparison_completed"])

    def test_open_single_range_without_enabled_m6_uses_range_analyzer(self) -> None:
        frame_range = MolecularFrameRange("condition", 0, 1)
        result = _range_analysis(frame_range)
        analyzer = Mock(return_value=result)
        comparator = Mock(side_effect=AssertionError("comparison must not run"))
        self.window = MolTrackMainWindow(
            yolo_model_discovery=lambda: [],
            position_range_analyzer=analyzer,
            position_range_comparator=comparator,
        )
        series = _series("movie.mpp")
        series.m6_analysis_state = MolecularM6SessionState(
            enabled=False,
            source_view="raw",
            use_segmentation_centroids=True,
            settings=_m6_settings(),
        )
        scope = adapt_m6_domain_type_analysis_source(
            result,
            frame_count=2,
        ).analysis_scope
        domain_state = M6DomainTypeSessionState(
            analysis_scope=scope,
            classification_settings=_type_settings(),
        )
        session = SimpleNamespace(
            registration_view_mode="Show raw",
            position_analysis=self._saved_single_range_position_state(),
            m6_domain_type_analysis_state=domain_state,
        )

        with patch.object(
            PositionAnalysisDialog,
            "set_range_analysis_result",
            new=self._set_range_result_without_plot_rendering,
        ):
            self.window._apply_loaded_state("state.moltrack.json", session, series)

        dialog = self.window.position_analysis_dialog()
        analyzer.assert_called_once()
        comparator.assert_not_called()
        self.assertEqual(dialog.analysis_mode(), "single_range")
        self.assertIs(dialog.range_analysis_result(), result)

    def test_open_state_keeps_mismatched_cache_stale_until_explicit_worker_run(self) -> None:
        _saved_result, saved_domain_state = self._restorable_domain_type_state()
        before = MolecularFrameRange("before desorption", 0, 0)
        after = MolecularFrameRange("after adsorption", 1, 1)
        changed_result = _comparison(
            _range_analysis(before, component=False),
            _range_analysis(after, component=False),
        )
        restored_store = M6DomainTypeAnalysisStore()
        self.window = MolTrackMainWindow(
            yolo_model_discovery=lambda: [],
            m6_domain_type_store=restored_store,
            position_range_comparator=lambda *_args, **_kwargs: changed_result,
        )
        series = _series("movie.mpp")
        series.m6_analysis_state = MolecularM6SessionState(
            enabled=True,
            source_view="raw",
            use_segmentation_centroids=True,
            settings=_m6_settings(),
        )
        session = SimpleNamespace(
            registration_view_mode="Show raw",
            position_analysis=self._saved_position_state(),
            m6_domain_type_analysis_state=saved_domain_state,
        )

        with patch.object(
            PositionAnalysisDialog,
            "set_range_analysis_result",
            new=self._set_range_result_without_plot_rendering,
        ), patch.object(
            MolTrackMainWindow,
            "_set_m6_first_shell_suggestion_from_result",
            new=lambda *_args, **_kwargs: None,
        ), patch.object(
            MolTrackMainWindow,
            "_render_current_m6_overlay",
            new=lambda *_args, **_kwargs: None,
        ):
            self.window._apply_loaded_state("state.moltrack.json", session, series)
            self.process_events_until(lambda: not self.window._m6_analysis_running)

            dialog = self.window.position_analysis_dialog()
            self.assertEqual(restored_store.state.status, "out_of_date")
            self.assertIsNone(restored_store.state.outcome)
            self.assertIn("out of date", dialog.domain_types_panel.status_text())
            self.assertTrue(dialog.domain_types_panel.classify_button.isEnabled())

            dialog.domain_types_panel.classify_button.click()
            self.process_events_until(
                lambda: self.window._m6_domain_type_controller.is_running
            )
            self.process_events_until(
                lambda: not self.window._m6_domain_type_controller.is_running
            )

            self.assertEqual(restored_store.state.status, "current")
            self.assertIsNotNone(restored_store.current)
            self.assertNotEqual(
                restored_store.current.context_fingerprint,
                saved_domain_state.cache_record.context_fingerprint,
            )

    def test_domain_cache_validation_failure_does_not_discard_restored_m6(self) -> None:
        result, saved_domain_state = self._restorable_domain_type_state()
        restored_store = M6DomainTypeAnalysisStore()
        self.window = MolTrackMainWindow(
            yolo_model_discovery=lambda: [],
            m6_domain_type_store=restored_store,
            position_range_comparator=lambda *_args, **_kwargs: result,
        )
        series = _series("movie.mpp")
        series.m6_analysis_state = MolecularM6SessionState(
            enabled=True,
            source_view="raw",
            use_segmentation_centroids=True,
            settings=_m6_settings(),
        )
        session = SimpleNamespace(
            registration_view_mode="Show raw",
            position_analysis=self._saved_position_state(),
            m6_domain_type_analysis_state=saved_domain_state,
        )

        with patch.object(
            PositionAnalysisDialog,
            "set_range_analysis_result",
            new=self._set_range_result_without_plot_rendering,
        ), patch.object(
            MolTrackMainWindow,
            "_set_m6_first_shell_suggestion_from_result",
            new=lambda *_args, **_kwargs: None,
        ), patch.object(
            MolTrackMainWindow,
            "_render_current_m6_overlay",
            new=lambda *_args, **_kwargs: None,
        ), patch(
            "moltrack.ui.main_window.build_m6_domain_type_analysis_context",
            side_effect=ValueError("incompatible domain cache"),
        ), patch.object(QMessageBox, "critical") as critical:
            self.window._apply_loaded_state("state.moltrack.json", session, series)
            self.process_events_until(lambda: not self.window._m6_analysis_running)

        self.assertTrue(series.m6_analysis_state.enabled)
        self.assertIsNotNone(
            self.window.position_analysis_dialog().range_analysis_result()
        )
        self.assertEqual(restored_store.state.status, "out_of_date")
        critical.assert_not_called()

    def test_active_domain_type_worker_blocks_save_state_only(self) -> None:
        store = _BlockingDomainTypeStore()
        saved = []
        self.window = MolTrackMainWindow(
            yolo_model_discovery=lambda: [],
            m6_domain_type_store=store,
            session_saver=lambda *args: saved.append(args),
        )
        self.window.set_image_series(_series("movie.mpp"))

        self.assertTrue(
            self.window._m6_domain_type_controller.start(
                object(),
                classification_settings=object(),
            )
        )
        self.process_events_until(store.started.is_set)

        try:
            self.assertFalse(self.window.action_save_state.isEnabled())
            self.assertFalse(self.window.action_save_state_as.isEnabled())
            self.assertTrue(self.window.slider_frame.isEnabled())
            self.window.save_state("blocked.moltrack.json")
            self.assertEqual(saved, [])
        finally:
            store.release.set()
        self.process_events_until(
            lambda: not self.window._m6_domain_type_controller.is_running
        )
        self.assertTrue(self.window.action_save_state.isEnabled())

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
