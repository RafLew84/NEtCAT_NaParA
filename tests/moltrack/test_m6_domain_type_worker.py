import os
import threading
import time
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt6.QtCore import QThread, QTimer
    from PyQt6.QtWidgets import QApplication
except ImportError:  # pragma: no cover - optional outside target GUI env
    QApplication = None

if QApplication is not None:
    from moltrack.ui.m6_domain_type_worker import (
        M6_DOMAIN_TYPE_ANALYSIS_PHASES,
        M6DomainTypeAnalysisController,
    )


class _BlockingStore:
    def __init__(self, *, failure: Exception | None = None) -> None:
        self.current = object()
        self.previous = self.current
        self.failure = failure
        self.started = threading.Event()
        self.release = threading.Event()
        self.worker_thread_ids = []
        self.publish_calls = []

    def compute(self, source, *, classification_settings, progress_callback):
        del source, classification_settings
        self.worker_thread_ids.append(int(QThread.currentThreadId()))
        progress_callback("extracting_observations")
        self.started.set()
        if not self.release.wait(timeout=2.0):
            raise RuntimeError("Test did not release the domain type worker.")
        progress_callback("complete_linkage")
        if self.failure is not None:
            raise self.failure
        progress_callback("aggregating")
        return "computed result"

    def publish(self, computation):
        self.publish_calls.append(computation)
        self.current = computation
        return computation


@unittest.skipUnless(QApplication is not None, "PyQt6 is required for worker tests")
class M6DomainTypeAnalysisControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def tearDown(self) -> None:
        if hasattr(self, "controller"):
            self.controller.shutdown()
            self.process_events_until(lambda: not self.controller.is_running)
            self.controller.deleteLater()
            self.__class__._app.processEvents()

    def process_events_until(self, condition, *, timeout_s: float = 3.0) -> None:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            self.__class__._app.processEvents()
            if condition():
                return
            time.sleep(0.005)
        self.fail("Timed out waiting for Qt event-loop condition.")

    def test_worker_keeps_event_loop_responsive_and_publishes_with_four_phase_progress(self) -> None:
        store = _BlockingStore()
        self.controller = M6DomainTypeAnalysisController(store)
        main_thread_id = int(QThread.currentThreadId())
        progress_events = []
        finished = []
        event_loop_ticks = []
        self.controller.progress.connect(progress_events.append)
        self.controller.finished.connect(finished.append)

        self.assertTrue(self.controller.start(object(), classification_settings=object()))
        self.process_events_until(store.started.is_set)
        self.assertFalse(
            self.controller.start(object(), classification_settings=object())
        )
        QTimer.singleShot(
            10,
            lambda: (event_loop_ticks.append("tick"), store.release.set()),
        )
        self.process_events_until(lambda: bool(finished))
        self.process_events_until(lambda: not self.controller.is_running)

        self.assertEqual(event_loop_ticks, ["tick"])
        self.assertNotEqual(store.worker_thread_ids, [main_thread_id])
        self.assertEqual(
            [value.phase for value in progress_events],
            list(M6_DOMAIN_TYPE_ANALYSIS_PHASES),
        )
        self.assertEqual(
            [value.phase_number for value in progress_events],
            [1, 2, 3, 4],
        )
        self.assertTrue(
            all(value.total_phase_count == 4 for value in progress_events)
        )
        self.assertEqual(finished, ["computed result"])
        self.assertEqual(store.publish_calls, ["computed result"])
        self.assertEqual(store.current, "computed result")

    def test_controlled_failure_keeps_previous_result_and_has_no_partial_success(self) -> None:
        store = _BlockingStore(failure=RuntimeError("synthetic worker failure"))
        self.controller = M6DomainTypeAnalysisController(store)
        failures = []
        finished = []
        self.controller.failed.connect(failures.append)
        self.controller.finished.connect(finished.append)

        self.assertTrue(self.controller.start(object(), classification_settings=object()))
        self.process_events_until(store.started.is_set)
        store.release.set()
        self.process_events_until(lambda: bool(failures))
        self.process_events_until(lambda: not self.controller.is_running)

        self.assertEqual(failures, ["synthetic worker failure"])
        self.assertEqual(finished, [])
        self.assertEqual(store.publish_calls, [])
        self.assertIs(store.current, store.previous)

    def test_series_change_discards_an_in_flight_result(self) -> None:
        store = _BlockingStore()
        self.controller = M6DomainTypeAnalysisController(store)
        canceled = []
        finished = []
        self.controller.canceled.connect(lambda: canceled.append(True))
        self.controller.finished.connect(finished.append)
        self.assertTrue(
            self.controller.start(object(), classification_settings=object())
        )
        self.process_events_until(store.started.is_set)

        self.assertTrue(self.controller.cancel_for_series_change())
        store.release.set()
        self.process_events_until(lambda: bool(canceled))
        self.process_events_until(lambda: not self.controller.is_running)

        self.assertEqual(finished, [])
        self.assertEqual(store.publish_calls, [])
        self.assertIs(store.current, store.previous)

    def test_active_worker_blocks_shutdown_until_it_finishes(self) -> None:
        store = _BlockingStore()
        self.controller = M6DomainTypeAnalysisController(store)
        finished = []
        self.controller.finished.connect(finished.append)
        self.assertTrue(
            self.controller.start(object(), classification_settings=object())
        )
        self.process_events_until(store.started.is_set)

        self.assertFalse(self.controller.shutdown())
        self.assertTrue(self.controller.is_running)
        store.release.set()
        self.process_events_until(lambda: bool(finished))
        self.process_events_until(lambda: not self.controller.is_running)

        self.assertTrue(self.controller.shutdown())

    def test_cancel_from_publishing_progress_slot_prevents_stale_publication(self) -> None:
        store = _BlockingStore()
        self.controller = M6DomainTypeAnalysisController(store)
        canceled = []
        finished = []
        self.controller.canceled.connect(lambda: canceled.append(True))
        self.controller.finished.connect(finished.append)
        self.controller.progress.connect(
            lambda progress: (
                self.controller.cancel_for_series_change()
                if progress.phase == "publishing"
                else None
            )
        )
        self.assertTrue(
            self.controller.start(object(), classification_settings=object())
        )
        self.process_events_until(store.started.is_set)

        store.release.set()
        self.process_events_until(lambda: bool(canceled))
        self.process_events_until(lambda: not self.controller.is_running)

        self.assertEqual(finished, [])
        self.assertEqual(store.publish_calls, [])
        self.assertIs(store.current, store.previous)


if __name__ == "__main__":
    unittest.main()
