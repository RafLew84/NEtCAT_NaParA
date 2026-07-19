import os
import threading
import time
import unittest
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np

from moltrack.core import MolTrackImageSeries
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

    def clear(self) -> None:
        self.clear_count += 1

    def compute(self, source, *, classification_settings, progress_callback):
        del source, classification_settings
        progress_callback("extracting_observations")
        self.started.set()
        if not self.release.wait(timeout=2.0):
            raise RuntimeError("Test did not release the domain type worker.")
        progress_callback("complete_linkage")
        progress_callback("aggregating")
        return "stale computation"

    def publish(self, computation):
        self.publish_calls.append(computation)
        return computation


def _series(name: str) -> MolTrackImageSeries:
    return MolTrackImageSeries(
        source_path=name,
        raw_frames=np.zeros((2, 8, 8), dtype=np.float32),
        metadata=STMSequenceMetadata(pixels_x=8, pixels_y=8),
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


if __name__ == "__main__":
    unittest.main()
