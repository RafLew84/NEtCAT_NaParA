import os
import time
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np

from moltrack.analysis import (
    TTMAPP_TEXTURE_DOMAIN_PRESET,
    MolecularFrameRange,
    TextureDomainSessionState,
)
from moltrack.core import MolTrackImageSeries
from nanotrack.core import STMSequenceMetadata

try:
    from PyQt6.QtWidgets import QApplication
except ImportError:  # pragma: no cover
    QApplication = None

if QApplication is not None:
    from moltrack.ui.texture_domain_worker import (
        TextureDomainAnalysisController,
        TextureDomainAnalysisProgress,
    )


@unittest.skipUnless(QApplication is not None, "PyQt6 is required")
class TextureDomainWorkerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _process_until(self, condition, timeout=2.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.app.processEvents()
            if condition():
                return
            time.sleep(0.005)
        self.fail("Timed out waiting for texture-domain worker.")

    def test_controller_runs_analyzer_off_main_thread_and_reports_progress(self):
        calls = []

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
            calls.append(
                (
                    series,
                    frame_range,
                    source_view,
                    settings,
                    use_segmentation_centroids,
                )
            )
            progress_callback(1, 1, frame_range.start_frame)
            return TextureDomainSessionState(
                settings=settings,
                frame_results=(),
                range_start_frame=frame_range.start_frame,
                range_end_frame=frame_range.end_frame,
            )

        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.zeros((1, 8, 8), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=8, pixels_y=8),
        )
        controller = TextureDomainAnalysisController(analyzer=analyzer)
        progress = []
        results = []
        running = []
        controller.progress.connect(progress.append)
        controller.finished.connect(results.append)
        controller.running_changed.connect(running.append)

        started = controller.start(
            series,
            MolecularFrameRange("test", 0, 0),
            source_view="raw",
            settings=TTMAPP_TEXTURE_DOMAIN_PRESET,
            use_segmentation_centroids=True,
        )
        self._process_until(lambda: not controller.is_running)

        self.assertTrue(started)
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(results), 1)
        self.assertIsInstance(progress[0], TextureDomainAnalysisProgress)
        self.assertEqual(progress[0].completed_count, 1)
        self.assertEqual(running, [True, False])

    def test_controller_rejects_parallel_start(self):
        def analyzer(*args, **kwargs):
            time.sleep(0.05)
            frame_range = args[1]
            return TextureDomainSessionState(
                settings=kwargs["settings"],
                frame_results=(),
                range_start_frame=frame_range.start_frame,
                range_end_frame=frame_range.end_frame,
            )

        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.zeros((1, 8, 8), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=8, pixels_y=8),
        )
        controller = TextureDomainAnalysisController(analyzer=analyzer)

        self.assertTrue(
            controller.start(
                series,
                MolecularFrameRange("test", 0, 0),
                source_view="raw",
                settings=TTMAPP_TEXTURE_DOMAIN_PRESET,
                use_segmentation_centroids=True,
            )
        )
        self.assertFalse(
            controller.start(
                series,
                MolecularFrameRange("test", 0, 0),
                source_view="raw",
                settings=TTMAPP_TEXTURE_DOMAIN_PRESET,
                use_segmentation_centroids=True,
            )
        )
        self._process_until(lambda: not controller.is_running)

    def test_shutdown_cancels_and_waits_for_worker_thread(self):
        def analyzer(*args, **kwargs):
            while not kwargs["cancel_requested"]():
                time.sleep(0.005)
            raise RuntimeError("canceled")

        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.zeros((1, 8, 8), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=8, pixels_y=8),
        )
        controller = TextureDomainAnalysisController(analyzer=analyzer)
        canceled = []
        controller.canceled.connect(lambda: canceled.append(True))
        controller.start(
            series,
            MolecularFrameRange("test", 0, 0),
            source_view="raw",
            settings=TTMAPP_TEXTURE_DOMAIN_PRESET,
            use_segmentation_centroids=True,
        )
        self._process_until(lambda: controller.is_running)

        self.assertTrue(controller.shutdown(wait_ms=1000))
        self._process_until(lambda: not controller.is_running)
        self.assertEqual(canceled, [True])


if __name__ == "__main__":
    unittest.main()
