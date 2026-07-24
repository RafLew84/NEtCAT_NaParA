import os
import threading
import time
import unittest
from dataclasses import replace
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from moltrack.analysis import (
    MolecularOrientationFrameData,
    MolecularFrameRange,
    MolecularFrameRangeAnalysisScope,
    MolecularOrderTypeClassificationSettings,
    MolecularOrderTypeSessionState,
    MolecularStackingDisplayResult,
    analyze_molecular_stacking,
    build_molecular_orientation_prototype_analysis,
)
from test_molecular_order_hierarchy import _inputs
from test_molecular_order_type_classifier import (
    _compare_scope,
    _domain_frame,
    _hierarchy,
)
from test_molecular_orientation_prototypes import _measurement

try:
    from PyQt6.QtWidgets import QApplication
except ImportError:  # pragma: no cover - optional outside target GUI env
    QApplication = None

if QApplication is not None:
    from moltrack.ui.molecular_order_type_worker import (
        MolecularOrderTypeAnalysisController,
        analyze_molecular_order_types,
        build_molecular_order_hierarchy_from_frame_results,
    )


def _analysis_inputs():
    return (
        _hierarchy(
            _domain_frame(0),
            _domain_frame(
                2,
                symmetry="sixfold",
                theta3_deg=None,
                theta6_deg=30.0,
                orientation_angles=(40.0,),
                stacking_pattern="uniform",
            ),
        ),
        _compare_scope(),
        MolecularOrderTypeClassificationSettings(),
    )


def _stacking_display_and_frame_results():
    frames = []
    frame_results = []
    for frame_index in (7, 8):
        lattice, rows, _stacking = _inputs(frame_index=frame_index)
        measurements = tuple(
            replace(
                _measurement(
                    frame_index=frame_index,
                    source_id=source_id,
                    angle_deg=(
                        20.0
                        if sum(
                            int(value)
                            for value in source_id.rsplit("-", 2)[1:]
                        )
                        % 2
                        == 0
                        else 80.0
                    ),
                    confidence=1.0,
                ),
                measurement_id=(
                    f"orientation-{frame_index}-{source_id}"
                ),
            )
            for source_id in rows.source_ids
        )
        frames.append(
            MolecularOrientationFrameData(
                frame_index=frame_index,
                row_assignment=rows,
                measurements=measurements,
            )
        )
        frame_results.append(
            SimpleNamespace(
                frame_index=frame_index,
                m6_orientation_analysis=SimpleNamespace(
                    lattice_domain_analysis=lattice,
                    lattice_row_assignment_analysis=rows,
                ),
            )
        )
    frame_tuple = tuple(frames)
    prototypes = build_molecular_orientation_prototype_analysis(frame_tuple)
    display = MolecularStackingDisplayResult(
        frames=frame_tuple,
        prototype_analysis=prototypes,
        stacking_analysis=analyze_molecular_stacking(
            frame_tuple,
            prototypes,
        ),
    )
    return display, tuple(frame_results)


@unittest.skipUnless(
    QApplication is not None,
    "PyQt6 is required for molecular-order worker tests",
)
class MolecularOrderTypeWorkerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def process_events_until(
        self,
        condition,
        *,
        timeout_s: float = 3.0,
    ) -> None:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            self.__class__._app.processEvents()
            if condition():
                return
            time.sleep(0.01)
        self.fail("Timed out waiting for Qt event-loop condition.")

    def test_analyzer_returns_consistent_classification_and_summary(self) -> None:
        hierarchy, scope, settings = _analysis_inputs()

        result = analyze_molecular_order_types(
            hierarchy,
            scope,
            settings,
        )

        self.assertIs(result.summary.classification, result.classification)
        self.assertEqual(
            result.classification.hierarchy_fingerprint,
            result.summary.classification.hierarchy_fingerprint,
        )
        self.assertEqual(
            tuple(value.range_name for value in result.summary.range_summaries),
            ("before", "after"),
        )

    def test_controller_binds_result_to_exact_stacking_context(self) -> None:
        hierarchy, scope, settings = _analysis_inputs()
        controller = MolecularOrderTypeAnalysisController()
        token = object()
        finished = []
        controller.finished.connect(finished.append)

        self.assertTrue(
            controller.start(
                hierarchy,
                scope,
                settings,
                context_token=token,
            )
        )
        self.process_events_until(lambda: not controller.is_running)

        self.assertEqual(len(finished), 1)
        self.assertIs(controller.current_result(token), finished[0])
        self.assertIsNone(controller.current_result(object()))

    def test_controller_restores_cache_only_for_matching_hierarchy(self) -> None:
        hierarchy, scope, settings = _analysis_inputs()
        result = analyze_molecular_order_types(hierarchy, scope, settings)
        state = MolecularOrderTypeSessionState.from_classification(
            result.classification
        )
        controller = MolecularOrderTypeAnalysisController()
        token = object()

        self.assertTrue(
            controller.restore(
                state,
                hierarchy,
                context_token=token,
            )
        )
        self.assertEqual(
            controller.current_result(token).classification,
            result.classification,
        )
        self.assertFalse(
            controller.restore(
                state,
                _hierarchy(_domain_frame(0)),
                context_token=token,
            )
        )

    def test_frame_result_adapter_runs_inside_worker_thread(self) -> None:
        display, frame_results = _stacking_display_and_frame_results()
        scope = MolecularFrameRangeAnalysisScope(
            analysis_mode="single_range",
            frame_count=9,
            source_view="expanded_aligned",
            ranges=(MolecularFrameRange("condition", 7, 8),),
        )
        caller_thread_id = threading.get_ident()
        builder_thread_ids = []

        def recording_builder(*args):
            builder_thread_ids.append(threading.get_ident())
            return build_molecular_order_hierarchy_from_frame_results(*args)

        controller = MolecularOrderTypeAnalysisController(
            hierarchy_builder=recording_builder
        )

        self.assertTrue(
            controller.start_from_frame_results(
                frame_results,
                scope,
                MolecularOrderTypeClassificationSettings(),
                context_token=display,
                display_result=display,
            )
        )
        self.process_events_until(lambda: not controller.is_running)

        self.assertEqual(len(builder_thread_ids), 1)
        self.assertNotEqual(builder_thread_ids[0], caller_thread_id)
        self.assertIsNotNone(controller.current_result(display))

    def test_async_restore_reuses_cache_without_reclassification(self) -> None:
        display, frame_results = _stacking_display_and_frame_results()
        hierarchy = build_molecular_order_hierarchy_from_frame_results(
            frame_results,
            display,
        )
        scope = MolecularFrameRangeAnalysisScope(
            analysis_mode="single_range",
            frame_count=9,
            source_view="expanded_aligned",
            ranges=(MolecularFrameRange("condition", 7, 8),),
        )
        settings = MolecularOrderTypeClassificationSettings()
        original = analyze_molecular_order_types(
            hierarchy,
            scope,
            settings,
            display,
        )
        state = MolecularOrderTypeSessionState.from_classification(
            original.classification
        )
        analyzer_calls = []

        def unexpected_analyzer(*args):
            analyzer_calls.append(args)
            raise AssertionError("cache restore must not reclassify")

        controller = MolecularOrderTypeAnalysisController(
            analyzer=unexpected_analyzer
        )

        self.assertTrue(
            controller.restore_from_frame_results(
                state,
                frame_results,
                context_token=display,
                display_result=display,
            )
        )
        self.process_events_until(lambda: not controller.is_running)

        restored = controller.current_result(display)
        self.assertIsNotNone(restored)
        self.assertEqual(
            restored.classification,
            original.classification,
        )
        self.assertEqual(analyzer_calls, [])

    def test_invalidated_running_result_is_not_published(self) -> None:
        hierarchy, scope, settings = _analysis_inputs()
        started = threading.Event()
        release = threading.Event()

        def blocking_analyzer(*args):
            started.set()
            release.wait(timeout=3.0)
            return analyze_molecular_order_types(*args)

        controller = MolecularOrderTypeAnalysisController(
            analyzer=blocking_analyzer
        )
        token = object()
        finished = []
        controller.finished.connect(finished.append)

        self.assertTrue(
            controller.start(
                hierarchy,
                scope,
                settings,
                context_token=token,
            )
        )
        self.process_events_until(started.is_set)
        controller.invalidate()
        release.set()
        self.process_events_until(lambda: not controller.is_running)

        self.assertEqual(finished, [])
        self.assertIsNone(controller.current_result(token))

    def test_adapter_joins_matching_m6_and_stacking_results(self) -> None:
        display, frame_results = _stacking_display_and_frame_results()

        hierarchy = build_molecular_order_hierarchy_from_frame_results(
            frame_results,
            display,
        )

        self.assertEqual(hierarchy.input_frame_indices, (7, 8))
        self.assertEqual(
            hierarchy.frames[0].lattice_domains[0].lattice_domain,
            frame_results[
                0
            ].m6_orientation_analysis.lattice_domain_analysis.domains[0],
        )

    def test_adapter_rejects_stacking_frame_without_m6_result(self) -> None:
        display, _frame_results = _stacking_display_and_frame_results()

        with self.assertRaisesRegex(
            ValueError,
            "without M6 analysis",
        ):
            build_molecular_order_hierarchy_from_frame_results((), display)

    def test_distribution_counts_reliable_molecular_measurements(self) -> None:
        display, frame_results = _stacking_display_and_frame_results()
        hierarchy = build_molecular_order_hierarchy_from_frame_results(
            frame_results,
            display,
        )
        scope = MolecularFrameRangeAnalysisScope(
            analysis_mode="single_range",
            frame_count=9,
            source_view="expanded_aligned",
            ranges=(MolecularFrameRange("condition", 7, 8),),
        )

        result = analyze_molecular_order_types(
            hierarchy,
            scope,
            MolecularOrderTypeClassificationSettings(),
            display,
        )

        distribution = result.orientation_distribution
        self.assertEqual(
            distribution.distribution_basis,
            "molecular_measurements",
        )
        self.assertEqual(
            sum(distribution.series[0].counts),
            sum(len(frame.measurements) for frame in display.frames),
        )


if __name__ == "__main__":
    unittest.main()
