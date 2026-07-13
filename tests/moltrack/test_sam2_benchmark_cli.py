import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from moltrack.core import MolecularDetection, MolecularDetectionSet, MolTrackImageSeries
from nanotrack.core import STMSequenceMetadata
from scripts.benchmark_moltrack_sam2 import main


class Sam2BaselineBenchmarkCliTests(unittest.TestCase):
    def test_cli_benchmarks_requested_inclusive_range_and_writes_json(self) -> None:
        frames = np.zeros((3, 4, 4), dtype=np.float32)
        detections = MolecularDetectionSet(frame_count=3)
        for frame_index in range(3):
            detections.set_detections(
                frame_index,
                [
                    MolecularDetection(
                        frame_index,
                        (1, 1, 3, 3),
                        0.9,
                        detection_id=f"bbox-{frame_index + 1}",
                    )
                ],
                source_view="raw",
                frame_shape=(4, 4),
            )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames,
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=4),
            molecular_detections=detections,
        )

        class FakeSegmenter:
            def segment_detection(self, _frame, _detection, **_kwargs):
                return object()

        clock_values = iter((0.0, 0.0, 1.0, 1.0, 3.0, 3.0))
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "baseline.json"
            with redirect_stdout(StringIO()):
                exit_code = main(
                    [
                        "state.moltrack.json",
                        "--start-frame",
                        "2",
                        "--end-frame",
                        "3",
                        "--source-view",
                        "raw",
                        "--output",
                        str(output_path),
                    ],
                    session_loader=lambda _path: SimpleNamespace(
                        registration_view_mode="Show raw",
                        active_frame_index=0,
                    ),
                    series_restorer=lambda _session: series,
                    checkpoint_discovery=lambda: [Path(r"C:\models\sam2.pt")],
                    segmenter_factory=FakeSegmenter,
                    perf_counter=lambda: next(clock_values),
                )
            payload = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["bbox_count"], 2)
        self.assertEqual(payload["detection_ids"], ["bbox-2", "bbox-3"])
        self.assertEqual(payload["frame_bbox_counts"], [
            {"frame_index": 1, "bbox_count": 1},
            {"frame_index": 2, "bbox_count": 1},
        ])
        self.assertEqual(payload["checkpoint_path"], r"C:\models\sam2.pt")

    def test_cli_does_not_write_success_report_for_range_without_bboxes(self) -> None:
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=np.zeros((1, 4, 4), dtype=np.float32),
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=4),
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "must-not-exist.json"
            error_output = StringIO()
            with redirect_stdout(StringIO()), redirect_stderr(error_output):
                exit_code = main(
                    ["state.moltrack.json", "--output", str(output_path)],
                    session_loader=lambda _path: SimpleNamespace(
                        registration_view_mode="Show raw",
                        active_frame_index=0,
                    ),
                    series_restorer=lambda _session: series,
                    checkpoint_discovery=lambda: [Path(r"C:\models\sam2.pt")],
                )

            self.assertEqual(exit_code, 1)
            self.assertFalse(output_path.exists())
            self.assertIn("at least one task", error_output.getvalue())


if __name__ == "__main__":
    unittest.main()
