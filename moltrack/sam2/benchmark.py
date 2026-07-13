from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import json
from pathlib import Path
from time import perf_counter as default_perf_counter
from typing import Callable, Iterable

import numpy as np

from moltrack.core import (
    MolecularDetection,
    MolTrackImageSeries,
    RegisteredFrameTransform,
    build_moltrack_expanded_aligned_stack,
)


LEGACY_SAM2_BACKEND_NAME = "legacy_per_bbox_subprocess"
LEGACY_STAGE_TIMING_NOTE = (
    "The legacy subprocess exposes only combined subprocess startup, model load, "
    "image embedding and mask inference time."
)
DEFAULT_SAM2_BENCHMARK_HOST_RAM_LIMIT_BYTES = 16 * 1024**3
DEFAULT_SAM2_BENCHMARK_GPU_PHYSICAL_BYTES = 8 * 1024**3
DEFAULT_SAM2_BENCHMARK_GPU_RESERVE_BYTES = 1 * 1024**3
SAM2_OPTIMIZATION_REFERENCE_BACKEND_NAME = "one_frame_image_subprocess_per_bbox"


class Sam2OptimizationGateError(RuntimeError):
    """Raised when the persistent backend misses a quality or resource gate."""


@dataclass(frozen=True)
class Sam2OptimizationReport:
    checkpoint_path: str
    mask_probability_threshold: float
    frame_count: int
    bbox_count: int
    legacy_total_duration_seconds: float
    persistent_total_duration_seconds: float
    counts_match: bool
    prompt_assignments_match: bool
    max_relative_area_error: float
    max_bbox_error_px: float
    min_mask_iou: float
    peak_host_ram_bytes: int
    peak_vram_bytes: int
    host_ram_limit_bytes: int = DEFAULT_SAM2_BENCHMARK_HOST_RAM_LIMIT_BYTES
    gpu_physical_bytes: int = DEFAULT_SAM2_BENCHMARK_GPU_PHYSICAL_BYTES
    gpu_reserve_bytes: int = DEFAULT_SAM2_BENCHMARK_GPU_RESERVE_BYTES
    minimum_mask_iou: float = 0.95
    maximum_relative_area_error: float = 0.05
    maximum_bbox_error_px: float = 1.0
    reference_backend_name: str = SAM2_OPTIMIZATION_REFERENCE_BACKEND_NAME

    @property
    def legacy_bboxes_per_second(self) -> float:
        return self.bbox_count / self.legacy_total_duration_seconds

    @property
    def persistent_bboxes_per_second(self) -> float:
        return self.bbox_count / self.persistent_total_duration_seconds

    @property
    def speedup(self) -> float:
        return self.legacy_total_duration_seconds / self.persistent_total_duration_seconds

    @property
    def quality_gate_passed(self) -> bool:
        return (
            self.counts_match
            and self.prompt_assignments_match
            and self.min_mask_iou >= self.minimum_mask_iou
            and self.max_relative_area_error <= self.maximum_relative_area_error
            and self.max_bbox_error_px <= self.maximum_bbox_error_px
        )

    @property
    def usable_vram_limit_bytes(self) -> int:
        return self.gpu_physical_bytes - self.gpu_reserve_bytes

    @property
    def memory_gate_passed(self) -> bool:
        return (
            self.peak_host_ram_bytes <= self.host_ram_limit_bytes
            and self.peak_vram_bytes <= self.usable_vram_limit_bytes
        )

    @property
    def performance_gate_passed(self) -> bool:
        return self.speedup > 1.0

    @property
    def passed(self) -> bool:
        return (
            self.quality_gate_passed
            and self.memory_gate_passed
            and self.performance_gate_passed
        )

    def require_pass(self) -> None:
        if self.passed:
            return
        failed = []
        if not self.quality_gate_passed:
            failed.append("quality")
        if not self.memory_gate_passed:
            failed.append("memory")
        if not self.performance_gate_passed:
            failed.append("performance")
        raise Sam2OptimizationGateError(
            f"SAM2 optimization failed gate(s): {', '.join(failed)}."
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "checkpoint_path": self.checkpoint_path,
            "reference_backend_name": self.reference_backend_name,
            "mask_probability_threshold": self.mask_probability_threshold,
            "frame_count": self.frame_count,
            "bbox_count": self.bbox_count,
            "timing": {
                "legacy_total_duration_seconds": self.legacy_total_duration_seconds,
                "persistent_total_duration_seconds": self.persistent_total_duration_seconds,
                "legacy_bboxes_per_second": self.legacy_bboxes_per_second,
                "persistent_bboxes_per_second": self.persistent_bboxes_per_second,
                "speedup": self.speedup,
            },
            "quality": {
                "counts_match": self.counts_match,
                "prompt_assignments_match": self.prompt_assignments_match,
                "max_relative_area_error": self.max_relative_area_error,
                "max_bbox_error_px": self.max_bbox_error_px,
                "min_mask_iou": self.min_mask_iou,
                "minimum_mask_iou": self.minimum_mask_iou,
                "maximum_relative_area_error": self.maximum_relative_area_error,
                "maximum_bbox_error_px": self.maximum_bbox_error_px,
                "passed": self.quality_gate_passed,
            },
            "memory": {
                "peak_host_ram_bytes": self.peak_host_ram_bytes,
                "host_ram_limit_bytes": self.host_ram_limit_bytes,
                "peak_vram_bytes": self.peak_vram_bytes,
                "gpu_physical_bytes": self.gpu_physical_bytes,
                "gpu_reserve_bytes": self.gpu_reserve_bytes,
                "usable_vram_limit_bytes": self.usable_vram_limit_bytes,
                "passed": self.memory_gate_passed,
            },
            "performance_gate_passed": self.performance_gate_passed,
            "passed": self.passed,
        }

    def to_text(self) -> str:
        return "\n".join(
            (
                "SAM2 optimization benchmark",
                f"- Reference: {self.reference_backend_name}",
                f"- Frames: {self.frame_count}",
                f"- BBoxes: {self.bbox_count}",
                f"- Legacy: {self.legacy_total_duration_seconds:.3f} s",
                f"- Persistent: {self.persistent_total_duration_seconds:.3f} s",
                f"- Speedup: {self.speedup:.3f}x",
                f"- Minimum mask IoU: {self.min_mask_iou:.6f}",
                f"- Peak host RAM: {self.peak_host_ram_bytes} bytes",
                f"- Peak VRAM: {self.peak_vram_bytes} bytes",
                f"- Passed: {self.passed}",
            )
        )


def benchmark_sam2_optimization(
    tasks: Iterable[Sam2BaselineTask],
    *,
    legacy_segmenter,
    persistent_segmenter,
    checkpoint_path: str | Path,
    mask_probability_threshold: float = 0.5,
    perf_counter: Callable[[], float] = default_perf_counter,
    host_ram_limit_bytes: int = DEFAULT_SAM2_BENCHMARK_HOST_RAM_LIMIT_BYTES,
    gpu_physical_bytes: int = DEFAULT_SAM2_BENCHMARK_GPU_PHYSICAL_BYTES,
    gpu_reserve_bytes: int = DEFAULT_SAM2_BENCHMARK_GPU_RESERVE_BYTES,
) -> Sam2OptimizationReport:
    task_list = list(tasks)
    if not task_list:
        raise ValueError("SAM2 optimization benchmark requires at least one task.")
    if any(not isinstance(task, Sam2BaselineTask) for task in task_list):
        raise TypeError("tasks must contain Sam2BaselineTask instances.")

    legacy_started = float(perf_counter())
    legacy_results = [
        _run_reference_image_segmentation(
            legacy_segmenter,
            task,
            checkpoint_path=Path(checkpoint_path),
            mask_probability_threshold=float(mask_probability_threshold),
        )
        for task in task_list
    ]
    legacy_duration = float(perf_counter()) - legacy_started

    tasks_by_frame: dict[int, list[Sam2BaselineTask]] = {}
    for task in task_list:
        tasks_by_frame.setdefault(task.detection.frame_index, []).append(task)
    persistent_results = []
    peak_host_ram_bytes = 0
    peak_vram_bytes = 0
    persistent_started = float(perf_counter())
    with persistent_segmenter.open_persistent_image_session(
        checkpoint_path=Path(checkpoint_path)
    ) as session:
        for frame_tasks in tasks_by_frame.values():
            frame_results = list(
                session.segment_frame_detections(
                    frame_tasks[0].frame,
                    [task.detection for task in frame_tasks],
                    mask_probability_threshold=float(mask_probability_threshold),
                )
            )
            persistent_results.extend(frame_results)
            diagnostics = getattr(session, "last_diagnostics", None)
            if diagnostics is not None:
                peak_host_ram_bytes = max(
                    peak_host_ram_bytes,
                    int(
                        getattr(
                            diagnostics,
                            "peak_host_rss_bytes",
                            getattr(diagnostics, "host_rss_bytes", 0),
                        )
                    ),
                )
                peak_vram_bytes = max(
                    peak_vram_bytes,
                    int(getattr(diagnostics, "peak_vram_bytes", 0)),
                )
    persistent_duration = float(perf_counter()) - persistent_started

    quality = _compare_sam2_results(task_list, legacy_results, persistent_results)
    report = Sam2OptimizationReport(
        checkpoint_path=str(checkpoint_path),
        mask_probability_threshold=float(mask_probability_threshold),
        frame_count=len(tasks_by_frame),
        bbox_count=len(task_list),
        legacy_total_duration_seconds=legacy_duration,
        persistent_total_duration_seconds=persistent_duration,
        peak_host_ram_bytes=peak_host_ram_bytes,
        peak_vram_bytes=peak_vram_bytes,
        host_ram_limit_bytes=int(host_ram_limit_bytes),
        gpu_physical_bytes=int(gpu_physical_bytes),
        gpu_reserve_bytes=int(gpu_reserve_bytes),
        **quality,
    )
    return report


def _compare_sam2_results(tasks, legacy_results, persistent_results) -> dict[str, object]:
    counts_match = len(legacy_results) == len(persistent_results) == len(tasks)
    expected_ids = [task.detection.detection_id for task in tasks]
    legacy_ids = [_single_prompt_id(result) for result in legacy_results]
    persistent_ids = [_single_prompt_id(result) for result in persistent_results]
    prompt_assignments_match = legacy_ids == persistent_ids == expected_ids
    area_errors = []
    bbox_errors = []
    mask_ious = []
    for legacy, persistent in zip(legacy_results, persistent_results):
        legacy_mask = np.asarray(legacy.mask, dtype=bool)
        persistent_mask = np.asarray(persistent.mask, dtype=bool)
        if legacy_mask.shape != persistent_mask.shape:
            mask_ious.append(0.0)
        else:
            intersection = int(np.count_nonzero(legacy_mask & persistent_mask))
            union = int(np.count_nonzero(legacy_mask | persistent_mask))
            mask_ious.append(1.0 if union == 0 else intersection / union)
        legacy_area = int(np.count_nonzero(legacy_mask))
        persistent_area = int(np.count_nonzero(persistent_mask))
        area_errors.append(
            abs(persistent_area - legacy_area) / max(1, legacy_area)
        )
        legacy_bbox = np.asarray(legacy.bbox_xyxy, dtype=np.float64)
        persistent_bbox = np.asarray(persistent.bbox_xyxy, dtype=np.float64)
        bbox_errors.append(float(np.max(np.abs(legacy_bbox - persistent_bbox))))
    return {
        "counts_match": counts_match,
        "prompt_assignments_match": prompt_assignments_match,
        "max_relative_area_error": max(area_errors, default=float("inf")),
        "max_bbox_error_px": max(bbox_errors, default=float("inf")),
        "min_mask_iou": min(mask_ious, default=0.0),
    }


def _single_prompt_id(segmentation) -> str:
    prompt_ids = tuple(segmentation.prompt_detection_ids)
    return prompt_ids[0] if len(prompt_ids) == 1 else ""


def _run_reference_image_segmentation(
    segmenter,
    task: Sam2BaselineTask,
    *,
    checkpoint_path: Path,
    mask_probability_threshold: float,
):
    batch_method = getattr(segmenter, "segment_frame_detections", None)
    if callable(batch_method):
        results = list(
            batch_method(
                task.frame,
                [task.detection],
                checkpoint_path=checkpoint_path,
                mask_probability_threshold=mask_probability_threshold,
            )
        )
        if len(results) != 1:
            raise ValueError(
                "SAM2 reference image backend must return one result per BBox."
            )
        return results[0]
    return segmenter.segment_detection(
        task.frame,
        task.detection,
        checkpoint_path=checkpoint_path,
        mask_probability_threshold=mask_probability_threshold,
    )


def write_sam2_optimization_report(
    path: str | Path,
    report: Sam2OptimizationReport,
) -> Path:
    if not isinstance(report, Sam2OptimizationReport):
        raise TypeError("report must be Sam2OptimizationReport.")
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return output_path


@dataclass(frozen=True)
class Sam2BaselineTask:
    """One legacy SAM2 benchmark call for one frame and one prompt BBox."""

    frame: np.ndarray
    detection: MolecularDetection

    def __post_init__(self) -> None:
        frame = np.asarray(self.frame)
        if frame.ndim not in (2, 3):
            raise ValueError("SAM2 baseline frame must have shape [H, W] or [H, W, C].")
        if not isinstance(self.detection, MolecularDetection):
            raise TypeError("SAM2 baseline detection must be MolecularDetection.")
        self.detection.validate_within_frame(frame.shape[:2])
        object.__setattr__(self, "frame", frame)


@dataclass(frozen=True)
class Sam2BaselineReport:
    """Measured end-to-end performance of the legacy per-BBox SAM2 backend."""

    backend_name: str
    checkpoint_path: str
    mask_probability_threshold: float
    frame_bbox_counts: tuple[tuple[int, int], ...]
    detection_ids: tuple[str, ...]
    per_bbox_duration_seconds: tuple[float, ...]
    total_duration_seconds: float
    stage_timings_available: bool = False
    stage_timing_note: str = LEGACY_STAGE_TIMING_NOTE

    def __post_init__(self) -> None:
        if not self.detection_ids:
            raise ValueError("SAM2 baseline report requires at least one detection.")
        if len(self.per_bbox_duration_seconds) != len(self.detection_ids):
            raise ValueError("Per-BBox durations must match detection IDs.")
        if self.total_duration_seconds <= 0.0:
            raise ValueError("SAM2 baseline total duration must be positive.")

    @property
    def frame_count(self) -> int:
        return len(self.frame_bbox_counts)

    @property
    def bbox_count(self) -> int:
        return len(self.detection_ids)

    @property
    def mean_seconds_per_bbox(self) -> float:
        return self.total_duration_seconds / self.bbox_count

    @property
    def bboxes_per_second(self) -> float:
        return self.bbox_count / self.total_duration_seconds

    def to_dict(self) -> dict[str, object]:
        return {
            "backend_name": self.backend_name,
            "checkpoint_path": self.checkpoint_path,
            "mask_probability_threshold": self.mask_probability_threshold,
            "frame_count": self.frame_count,
            "bbox_count": self.bbox_count,
            "frame_bbox_counts": [
                {"frame_index": frame_index, "bbox_count": bbox_count}
                for frame_index, bbox_count in self.frame_bbox_counts
            ],
            "detection_ids": list(self.detection_ids),
            "per_bbox_duration_seconds": list(self.per_bbox_duration_seconds),
            "total_duration_seconds": self.total_duration_seconds,
            "mean_seconds_per_bbox": self.mean_seconds_per_bbox,
            "bboxes_per_second": self.bboxes_per_second,
            "stage_timings": {
                "available": self.stage_timings_available,
                "note": self.stage_timing_note,
            },
        }

    def to_text(self) -> str:
        return "\n".join(
            (
                "Legacy SAM2 baseline",
                f"- Frames: {self.frame_count}",
                f"- BBoxes: {self.bbox_count}",
                f"- Total: {self.total_duration_seconds:.3f} s",
                f"- Mean: {self.mean_seconds_per_bbox:.3f} s/BBox",
                f"- Throughput: {self.bboxes_per_second:.3f} BBox/s",
                f"- Stage timings: {self.stage_timing_note}",
            )
        )


def benchmark_legacy_sam2(
    tasks: Iterable[Sam2BaselineTask],
    *,
    segmenter,
    checkpoint_path: str | Path,
    mask_probability_threshold: float = 0.5,
    perf_counter: Callable[[], float] = default_perf_counter,
    progress_callback: Callable[[int, int, Sam2BaselineTask, float], None] | None = None,
) -> Sam2BaselineReport:
    """Run the current one-subprocess-per-BBox SAM2 path and measure wall time."""

    task_list = list(tasks)
    if not task_list:
        raise ValueError("SAM2 baseline benchmark requires at least one task.")
    started_at = float(perf_counter())
    durations = []
    for task in task_list:
        if not isinstance(task, Sam2BaselineTask):
            raise TypeError("tasks must contain Sam2BaselineTask instances.")
        bbox_started_at = float(perf_counter())
        segmenter.segment_detection(
            task.frame,
            task.detection,
            checkpoint_path=Path(checkpoint_path),
            mask_probability_threshold=float(mask_probability_threshold),
        )
        duration = float(perf_counter()) - bbox_started_at
        durations.append(duration)
        if progress_callback is not None:
            progress_callback(len(durations), len(task_list), task, duration)
    total_duration = float(perf_counter()) - started_at

    frame_counts = Counter(task.detection.frame_index for task in task_list)
    return Sam2BaselineReport(
        backend_name=LEGACY_SAM2_BACKEND_NAME,
        checkpoint_path=str(checkpoint_path),
        mask_probability_threshold=float(mask_probability_threshold),
        frame_bbox_counts=tuple(sorted(frame_counts.items())),
        detection_ids=tuple(task.detection.detection_id for task in task_list),
        per_bbox_duration_seconds=tuple(durations),
        total_duration_seconds=total_duration,
    )


def write_sam2_baseline_report(path: str | Path, report: Sam2BaselineReport) -> Path:
    if not isinstance(report, Sam2BaselineReport):
        raise TypeError("report must be Sam2BaselineReport.")
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return output_path


def build_sam2_baseline_tasks(
    series: MolTrackImageSeries,
    *,
    start_frame_index: int,
    end_frame_index: int,
    source_view: str,
    max_bbox_count: int | None = None,
) -> tuple[Sam2BaselineTask, ...]:
    """Build ordered per-BBox legacy benchmark tasks from one inclusive range."""

    if not isinstance(series, MolTrackImageSeries):
        raise TypeError("series must be MolTrackImageSeries.")
    start_frame_index = int(start_frame_index)
    end_frame_index = int(end_frame_index)
    if start_frame_index < 0 or end_frame_index >= series.frame_count:
        raise IndexError("SAM2 baseline frame range is outside the working series.")
    if start_frame_index > end_frame_index:
        raise ValueError("SAM2 baseline start frame must not exceed end frame.")
    source_view = str(source_view).strip()
    if source_view not in ("raw", "expanded_aligned"):
        raise ValueError("SAM2 baseline source_view must be 'raw' or 'expanded_aligned'.")
    if max_bbox_count is not None:
        max_bbox_count = int(max_bbox_count)
        if max_bbox_count <= 0:
            raise ValueError("max_bbox_count must be positive when provided.")

    if series.molecular_detections is None:
        return ()
    expanded_stack = None
    if source_view == "expanded_aligned":
        expanded_stack = series.expanded_aligned_stack
        if expanded_stack is None:
            expanded_stack = build_moltrack_expanded_aligned_stack(series)
    tasks = []
    for frame_index in range(start_frame_index, end_frame_index + 1):
        frame = series.raw_frames[frame_index]
        transform = None
        if expanded_stack is not None:
            transform = RegisteredFrameTransform(
                raw_shape=frame.shape[:2],
                expanded_shape=expanded_stack.frames[frame_index].shape[:2],
                frame_origin_xy=tuple(expanded_stack.frame_origins_xy[frame_index]),
            )
        for detection in series.molecular_detections.get_detections(
            frame_index,
            source_view=source_view,
        ):
            inference_detection = detection
            if transform is not None:
                inference_detection = transform.expanded_detection_to_raw_prompt(detection)
            tasks.append(Sam2BaselineTask(frame=frame, detection=inference_detection))
            if max_bbox_count is not None and len(tasks) >= max_bbox_count:
                return tuple(tasks)
    return tuple(tasks)
