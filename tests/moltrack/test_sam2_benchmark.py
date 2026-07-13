import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from moltrack.core import (
    MolecularDetection,
    MolecularDetectionSet,
    MolecularSegmentation,
    MolTrackImageSeries,
)
from moltrack.sam2 import (
    Sam2BaselineReport,
    Sam2BaselineTask,
    Sam2OptimizationGateError,
    Sam2OptimizationReport,
    benchmark_legacy_sam2,
    benchmark_sam2_optimization,
    build_sam2_baseline_tasks,
    write_sam2_baseline_report,
)
from nanotrack.core import STMSequenceMetadata


class Sam2BaselineBenchmarkTests(unittest.TestCase):
    def test_optimization_report_compares_quality_speed_and_persistent_memory(self) -> None:
        frames = (
            np.zeros((5, 6), dtype=np.float32),
            np.ones((5, 6), dtype=np.float32),
        )
        detections = (
            MolecularDetection(0, (1, 1, 3, 3), 0.9, detection_id="bbox-a"),
            MolecularDetection(1, (2, 1, 5, 4), 0.8, detection_id="bbox-b"),
        )
        tasks = tuple(
            Sam2BaselineTask(frame=frame, detection=detection)
            for frame, detection in zip(frames, detections)
        )

        def make_segmentation(frame, detection):
            mask = np.zeros(frame.shape[:2], dtype=bool)
            x0, y0, x1, y1 = (int(value) for value in detection.bbox_xyxy)
            mask[y0:y1, x0:x1] = True
            return MolecularSegmentation(
                frame_index=detection.frame_index,
                source_view=detection.source_view,
                bbox_xyxy=detection.bbox_xyxy,
                mask=mask,
                origin="sam2",
                prompt_detection_ids=(detection.detection_id,),
            )

        class LegacySegmenter:
            def segment_detection(self, frame, detection, **_kwargs):
                return make_segmentation(frame, detection)

        class PersistentSession:
            def __init__(self) -> None:
                self.last_diagnostics = None

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_value, traceback) -> None:
                pass

            def segment_frame_detections(self, frame, frame_detections, **_kwargs):
                self.last_diagnostics = SimpleNamespace(
                    host_rss_bytes=2 * 1024**3,
                    peak_host_rss_bytes=3 * 1024**3,
                    peak_vram_bytes=3 * 1024**3,
                )
                return [
                    make_segmentation(frame, detection)
                    for detection in frame_detections
                ]

        class PersistentSegmenter:
            def open_persistent_image_session(self, *, checkpoint_path=None):
                return PersistentSession()

        clock_values = iter((0.0, 4.0, 4.0, 5.0))

        report = benchmark_sam2_optimization(
            tasks,
            legacy_segmenter=LegacySegmenter(),
            persistent_segmenter=PersistentSegmenter(),
            checkpoint_path=Path(r"C:\models\sam2.pt"),
            perf_counter=lambda: next(clock_values),
        )

        self.assertEqual(report.bbox_count, 2)
        self.assertEqual(report.frame_count, 2)
        self.assertEqual(report.legacy_total_duration_seconds, 4.0)
        self.assertEqual(report.persistent_total_duration_seconds, 1.0)
        self.assertEqual(report.speedup, 4.0)
        self.assertEqual(report.persistent_bboxes_per_second, 2.0)
        self.assertTrue(report.counts_match)
        self.assertTrue(report.prompt_assignments_match)
        self.assertEqual(report.max_relative_area_error, 0.0)
        self.assertEqual(report.max_bbox_error_px, 0.0)
        self.assertEqual(report.min_mask_iou, 1.0)
        self.assertEqual(report.peak_host_ram_bytes, 3 * 1024**3)
        self.assertEqual(report.peak_vram_bytes, 3 * 1024**3)
        self.assertTrue(report.quality_gate_passed)
        self.assertTrue(report.memory_gate_passed)
        self.assertTrue(report.passed)

    def test_optimization_gate_rejects_peak_host_ram_above_sixteen_gib(self) -> None:
        report = Sam2OptimizationReport(
            checkpoint_path="sam2.pt",
            mask_probability_threshold=0.5,
            frame_count=1,
            bbox_count=1,
            legacy_total_duration_seconds=2.0,
            persistent_total_duration_seconds=1.0,
            counts_match=True,
            prompt_assignments_match=True,
            max_relative_area_error=0.0,
            max_bbox_error_px=0.0,
            min_mask_iou=1.0,
            peak_host_ram_bytes=16 * 1024**3 + 1,
            peak_vram_bytes=1 * 1024**3,
        )

        self.assertFalse(report.memory_gate_passed)
        self.assertFalse(report.passed)
        with self.assertRaisesRegex(Sam2OptimizationGateError, "memory"):
            report.require_pass()

    def test_optimization_gate_preserves_one_gib_vram_reserve_on_eight_gib_gpu(self) -> None:
        report = Sam2OptimizationReport(
            checkpoint_path="sam2.pt",
            mask_probability_threshold=0.5,
            frame_count=1,
            bbox_count=1,
            legacy_total_duration_seconds=2.0,
            persistent_total_duration_seconds=1.0,
            counts_match=True,
            prompt_assignments_match=True,
            max_relative_area_error=0.0,
            max_bbox_error_px=0.0,
            min_mask_iou=1.0,
            peak_host_ram_bytes=2 * 1024**3,
            peak_vram_bytes=7 * 1024**3 + 1,
        )

        self.assertEqual(report.usable_vram_limit_bytes, 7 * 1024**3)
        self.assertFalse(report.memory_gate_passed)
        with self.assertRaisesRegex(Sam2OptimizationGateError, "memory"):
            report.require_pass()

    def test_optimization_gate_rejects_changed_prompt_assignment_or_mask(self) -> None:
        report = Sam2OptimizationReport(
            checkpoint_path="sam2.pt",
            mask_probability_threshold=0.5,
            frame_count=1,
            bbox_count=1,
            legacy_total_duration_seconds=2.0,
            persistent_total_duration_seconds=1.0,
            counts_match=True,
            prompt_assignments_match=False,
            max_relative_area_error=0.25,
            max_bbox_error_px=2.0,
            min_mask_iou=0.7,
            peak_host_ram_bytes=2 * 1024**3,
            peak_vram_bytes=2 * 1024**3,
        )

        self.assertFalse(report.quality_gate_passed)
        with self.assertRaisesRegex(Sam2OptimizationGateError, "quality"):
            report.require_pass()

    def test_report_measures_end_to_end_legacy_time_and_throughput_per_bbox(self) -> None:
        frame = np.zeros((4, 4), dtype=np.float32)
        detections = (
            MolecularDetection(1, (0, 0, 2, 2), 0.9, detection_id="bbox-a"),
            MolecularDetection(2, (1, 1, 3, 3), 0.8, detection_id="bbox-b"),
        )
        tasks = tuple(Sam2BaselineTask(frame=frame, detection=detection) for detection in detections)

        class FakeSegmenter:
            def __init__(self) -> None:
                self.calls = []

            def segment_detection(self, call_frame, detection, **kwargs):
                self.calls.append((call_frame, detection, kwargs))
                return object()

        clock_values = iter((0.0, 0.0, 1.0, 1.0, 3.0, 3.0))
        segmenter = FakeSegmenter()

        report = benchmark_legacy_sam2(
            tasks,
            segmenter=segmenter,
            checkpoint_path=Path(r"C:\models\sam2.pt"),
            mask_probability_threshold=0.6,
            perf_counter=lambda: next(clock_values),
        )

        self.assertEqual(report.backend_name, "legacy_per_bbox_subprocess")
        self.assertEqual(report.frame_count, 2)
        self.assertEqual(report.bbox_count, 2)
        self.assertEqual(report.frame_bbox_counts, ((1, 1), (2, 1)))
        self.assertEqual(report.detection_ids, ("bbox-a", "bbox-b"))
        self.assertEqual(report.per_bbox_duration_seconds, (1.0, 2.0))
        self.assertEqual(report.total_duration_seconds, 3.0)
        self.assertEqual(report.mean_seconds_per_bbox, 1.5)
        self.assertAlmostEqual(report.bboxes_per_second, 2.0 / 3.0)
        self.assertFalse(report.stage_timings_available)
        self.assertIn("combined", report.stage_timing_note)
        self.assertEqual(len(segmenter.calls), 2)
        self.assertTrue(all(call[0] is frame for call in segmenter.calls))
        self.assertTrue(all(call[2]["checkpoint_path"] == Path(r"C:\models\sam2.pt") for call in segmenter.calls))
        self.assertTrue(all(call[2]["mask_probability_threshold"] == 0.6 for call in segmenter.calls))

    def test_empty_benchmark_is_rejected_without_calling_backend(self) -> None:
        class UnexpectedSegmenter:
            def segment_detection(self, *_args, **_kwargs):
                raise AssertionError("backend must not be called")

        with self.assertRaisesRegex(ValueError, "at least one"):
            benchmark_legacy_sam2(
                (),
                segmenter=UnexpectedSegmenter(),
                checkpoint_path=Path(r"C:\models\sam2.pt"),
            )

    def test_report_writes_machine_json_and_readable_text_summary(self) -> None:
        report = Sam2BaselineReport(
            backend_name="legacy_per_bbox_subprocess",
            checkpoint_path=r"C:\models\sam2.pt",
            mask_probability_threshold=0.5,
            frame_bbox_counts=((8, 2),),
            detection_ids=("bbox-a", "bbox-b"),
            per_bbox_duration_seconds=(1.0, 3.0),
            total_duration_seconds=4.0,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = Path(tmpdir) / "baseline.json"
            write_sam2_baseline_report(report_path, report)
            payload = json.loads(report_path.read_text(encoding="utf-8"))

        self.assertEqual(payload["backend_name"], "legacy_per_bbox_subprocess")
        self.assertEqual(payload["frame_count"], 1)
        self.assertEqual(payload["bbox_count"], 2)
        self.assertEqual(payload["frame_bbox_counts"], [{"frame_index": 8, "bbox_count": 2}])
        self.assertEqual(payload["per_bbox_duration_seconds"], [1.0, 3.0])
        self.assertEqual(payload["total_duration_seconds"], 4.0)
        self.assertEqual(payload["mean_seconds_per_bbox"], 2.0)
        self.assertEqual(payload["bboxes_per_second"], 0.5)
        self.assertFalse(payload["stage_timings"]["available"])
        summary = report.to_text()
        self.assertIn("Legacy SAM2 baseline", summary)
        self.assertIn("BBoxes: 2", summary)
        self.assertIn("2.000 s/BBox", summary)
        self.assertIn("0.500 BBox/s", summary)

    def test_build_tasks_uses_every_raw_bbox_in_inclusive_frame_range(self) -> None:
        frames = np.stack(
            [np.full((4, 4), frame_index, dtype=np.float32) for frame_index in range(3)]
        )
        detections = MolecularDetectionSet(frame_count=3)
        detections.set_detections(
            0,
            [MolecularDetection(0, (0, 0, 2, 2), 0.9, detection_id="outside")],
            source_view="raw",
            frame_shape=(4, 4),
        )
        detections.set_detections(
            1,
            [
                MolecularDetection(1, (0, 0, 2, 2), 0.8, detection_id="frame-2-a"),
                MolecularDetection(1, (2, 2, 4, 4), 0.7, detection_id="frame-2-b"),
            ],
            source_view="raw",
            frame_shape=(4, 4),
        )
        detections.set_detections(
            2,
            [MolecularDetection(2, (1, 1, 3, 3), 0.6, detection_id="frame-3")],
            source_view="raw",
            frame_shape=(4, 4),
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=frames,
            metadata=STMSequenceMetadata(pixels_x=4, pixels_y=4),
            molecular_detections=detections,
        )

        tasks = build_sam2_baseline_tasks(
            series,
            start_frame_index=1,
            end_frame_index=2,
            source_view="raw",
        )

        self.assertEqual(
            [task.detection.detection_id for task in tasks],
            ["frame-2-a", "frame-2-b", "frame-3"],
        )
        self.assertEqual([float(task.frame[0, 0]) for task in tasks], [1.0, 1.0, 2.0])

    def test_build_tasks_maps_expanded_prompts_to_raw_inference_coordinates(self) -> None:
        raw_frame = np.arange(20, dtype=np.float32).reshape(4, 5)
        detections = MolecularDetectionSet(frame_count=1)
        detections.set_detections(
            0,
            [
                MolecularDetection(
                    0,
                    (3, 2, 5, 4),
                    0.9,
                    source_view="expanded_aligned",
                    detection_id="expanded-bbox",
                )
            ],
            source_view="expanded_aligned",
            frame_shape=(7, 8),
        )
        series = MolTrackImageSeries(
            source_path="movie.mpp",
            raw_frames=raw_frame[np.newaxis, ...],
            metadata=STMSequenceMetadata(pixels_x=5, pixels_y=4),
            molecular_detections=detections,
            expanded_aligned_stack=SimpleNamespace(
                frames=np.zeros((1, 7, 8), dtype=np.float32),
                frame_origins_xy=np.asarray(((2.0, 1.0),)),
            ),
        )

        tasks = build_sam2_baseline_tasks(
            series,
            start_frame_index=0,
            end_frame_index=0,
            source_view="expanded_aligned",
        )

        self.assertEqual(len(tasks), 1)
        np.testing.assert_array_equal(tasks[0].frame, raw_frame)
        self.assertEqual(tasks[0].detection.source_view, "raw")
        self.assertEqual(tasks[0].detection.detection_id, "expanded-bbox")
        self.assertEqual(tasks[0].detection.bbox_xyxy, (1.0, 1.0, 3.0, 3.0))


if __name__ == "__main__":
    unittest.main()
