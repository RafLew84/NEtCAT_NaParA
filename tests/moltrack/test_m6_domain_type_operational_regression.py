import os
import time
import tracemalloc
from dataclasses import replace
from types import SimpleNamespace
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from moltrack.analysis import (
    M6DomainTypeAnalysisStore,
    M6DomainTypeSessionState,
    MolecularFrameRange,
    MolecularFrameRangeAnalysis,
    adapt_m6_domain_type_analysis_source,
)
from test_m6_domain_type_lifecycle import (
    _component,
    _m6_analysis,
    _m6_settings,
    _type_settings,
)
from test_m6_domain_type_range_comparison import (
    BEFORE,
    _classification,
    _observation,
)

try:
    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QApplication
except ImportError:  # pragma: no cover - optional outside target GUI env
    QApplication = None

if QApplication is not None:
    from moltrack.ui.m6_domain_type_worker import (
        M6DomainTypeAnalysisController,
    )


def _large_observation_set(
    *,
    type_count: int,
    observations_per_type: int,
):
    return tuple(
        _observation(
            frame_index=member % 3,
            local_domain_id=type_index * observations_per_type + member,
            orientation_deg=float(type_index % 6) * 8.0,
            bond_length_nm=2.0 + type_index,
            frame_range=BEFORE,
            molecule_count=10,
            molecule_fraction=0.1,
            footprint_area_nm2=10.0,
            footprint_fraction=0.1,
            coherent_q6=0.7,
        )
        for type_index in range(type_count)
        for member in range(observations_per_type)
    )


def _large_analysis_source(
    *,
    type_count: int,
    observations_per_type: int,
    components_per_frame: int,
):
    settings = _m6_settings()
    components = tuple(
        _component(
            type_index * observations_per_type + member,
            orientation_deg=float(type_index % 6) * 8.0,
            bond_length_nm=2.0 + type_index,
        )
        for type_index in range(type_count)
        for member in range(observations_per_type)
    )
    frame_count = len(components) // components_per_frame
    frame_results = []
    for frame_index in range(frame_count):
        start = frame_index * components_per_frame
        analysis = _m6_analysis(
            components[start:start + components_per_frame],
            source_view="raw",
            settings=settings,
        )
        frame_results.append(SimpleNamespace(
            frame_index=frame_index,
            source_frame_index=frame_index + 100,
            source_view="raw",
            m6_orientation_availability_status="available",
            m6_orientation_unavailability_reason=None,
            m6_orientation_analysis=analysis,
        ))
    range_analysis = MolecularFrameRangeAnalysis(
        frame_range=MolecularFrameRange("performance range", 0, frame_count - 1),
        source_view="raw",
        frame_results=tuple(frame_results),
        aggregates=None,
        intensity_metric="background_corrected_median",
        intensity_unit="a.u.",
        use_segmentation_centroids=True,
        m6_orientation_settings=settings,
    )
    return adapt_m6_domain_type_analysis_source(
        range_analysis,
        frame_count=frame_count,
    )


class M6DomainTypeOperationalRegressionTests(unittest.TestCase):
    def test_representative_classification_is_fast_and_order_independent(self) -> None:
        observations = _large_observation_set(
            type_count=20,
            observations_per_type=5,
        )

        started = time.perf_counter()
        forward = _classification(observations)
        elapsed = time.perf_counter() - started
        reverse = _classification(tuple(reversed(observations)))

        self.assertLess(elapsed, 1.5)
        self.assertEqual(len(forward.observations), 100)
        self.assertEqual(len(forward.domain_types), 20)
        self.assertEqual(forward.domain_types, reverse.domain_types)
        self.assertEqual(forward.assignments, reverse.assignments)


@unittest.skipUnless(QApplication is not None, "PyQt6 is required for worker tests")
class M6DomainTypeOperationalWorkerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def tearDown(self) -> None:
        if hasattr(self, "controller"):
            self.controller.shutdown()
            self._process_events_until(lambda: not self.controller.is_running)
            self.controller.deleteLater()
            self.__class__._app.processEvents()

    def _process_events_until(self, condition, *, timeout_s: float = 15.0) -> None:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            self.__class__._app.processEvents()
            if condition():
                return
            time.sleep(0.001)
        self.fail("Timed out waiting for domain type worker.")

    def test_large_worker_is_responsive_memory_bounded_and_keeps_one_cache(self) -> None:
        source = _large_analysis_source(
            type_count=1,
            observations_per_type=200,
            components_per_frame=5,
        )
        settings = _type_settings(minimum_observations_per_type=5)
        store = M6DomainTypeAnalysisStore()
        self.controller = M6DomainTypeAnalysisController(store)
        finished = []
        event_loop_ticks = []
        self.controller.finished.connect(finished.append)
        timer = QTimer()
        timer.setInterval(1)
        timer.timeout.connect(lambda: event_loop_ticks.append(time.monotonic()))

        tracemalloc.start()
        started = time.perf_counter()
        timer.start()
        self.assertTrue(
            self.controller.start(source, classification_settings=settings)
        )
        self._process_events_until(lambda: bool(finished))
        self._process_events_until(lambda: not self.controller.is_running)
        timer.stop()
        elapsed = time.perf_counter() - started
        _current_bytes, peak_bytes = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        outcome = finished[0]
        self.assertLess(elapsed, 10.0)
        self.assertLess(peak_bytes, 128 * 1024 * 1024)
        self.assertGreater(len(event_loop_ticks), 1)
        self.assertEqual(len(outcome.classification.observations), 200)
        self.assertEqual(len(outcome.classification.domain_types), 1)
        self.assertIs(store.current, outcome)

        reused = store.analyze(source, classification_settings=settings)
        session_state = M6DomainTypeSessionState.from_outcome(outcome)
        payload = session_state.to_dict()

        self.assertIs(reused, outcome)
        self.assertIsInstance(payload["reproducible_cache"], dict)
        self.assertNotIsInstance(payload["reproducible_cache"], list)
        self.assertEqual(store.state.status, "current")

        replacement = store.analyze(
            source,
            classification_settings=replace(
                settings,
                orientation_tolerance_deg=(
                    settings.orientation_tolerance_deg * 0.9
                ),
            ),
        )

        self.assertIsNot(replacement, outcome)
        self.assertIs(store.current, replacement)
        self.assertEqual(store.state.status, "current")


if __name__ == "__main__":
    unittest.main()
