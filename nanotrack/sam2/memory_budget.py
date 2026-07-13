"""Memory planning primitives for single-image SAM2 batches."""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from queue import Queue
from typing import Callable


GIB = 1024**3
DEFAULT_SAM2_HOST_RAM_LIMIT_BYTES = 16 * GIB
DEFAULT_SAM2_HOST_FIXED_OVERHEAD_BYTES = 2 * GIB
DEFAULT_SAM2_HOST_SAFETY_RESERVE_BYTES = 1 * GIB
DEFAULT_SAM2_GPU_PHYSICAL_BYTES = 8 * GIB
DEFAULT_SAM2_GPU_WORKING_LIMIT_BYTES = 7 * GIB
DEFAULT_SAM2_GPU_RESERVE_BYTES = 1 * GIB
DEFAULT_SAM2_GPU_FIXED_OVERHEAD_BYTES = 2 * GIB
DEFAULT_SAM2_GPU_DECODER_BYTES_PER_BBOX = 128 * 1024**2


class Sam2MemoryBudgetError(RuntimeError):
    """Raised before inference when a SAM2 batch cannot fit its memory budget."""


@dataclass(frozen=True)
class Sam2HostMemoryPlan:
    limit_bytes: int
    frame_bytes: int
    retained_result_bytes: int
    per_chunk_bbox_bytes: int
    chunk_size: int
    chunk_count: int
    predicted_peak_bytes: int


@dataclass(frozen=True)
class Sam2SequenceMemoryPlan:
    frame_count: int
    total_bbox_count: int
    total_chunk_count: int
    predicted_peak_bytes: int


@dataclass(frozen=True)
class Sam2GpuMemoryPlan:
    physical_vram_bytes: int
    free_vram_bytes: int
    effective_limit_bytes: int
    reserve_bytes: int
    per_chunk_bbox_bytes: int
    chunk_size: int
    predicted_usage_bytes: int


@dataclass(frozen=True)
class Sam2MemoryDiagnostics:
    requested_chunk_size: int
    effective_chunk_size: int
    predicted_peak_host_ram_bytes: int
    measured_host_ram_bytes: int
    measured_peak_host_ram_bytes: int
    free_vram_bytes: int
    effective_vram_limit_bytes: int
    predicted_vram_usage_bytes: int


@dataclass(frozen=True)
class Sam2MemoryBudget:
    limit_bytes: int = DEFAULT_SAM2_HOST_RAM_LIMIT_BYTES
    fixed_overhead_bytes: int = DEFAULT_SAM2_HOST_FIXED_OVERHEAD_BYTES
    safety_reserve_bytes: int = DEFAULT_SAM2_HOST_SAFETY_RESERVE_BYTES

    def __post_init__(self) -> None:
        values = {
            "limit_bytes": int(self.limit_bytes),
            "fixed_overhead_bytes": int(self.fixed_overhead_bytes),
            "safety_reserve_bytes": int(self.safety_reserve_bytes),
        }
        if values["limit_bytes"] <= 0:
            raise ValueError("SAM2 host RAM limit_bytes must be positive.")
        if values["limit_bytes"] > DEFAULT_SAM2_HOST_RAM_LIMIT_BYTES:
            raise ValueError("SAM2 host RAM limit cannot exceed 16 GiB.")
        if values["fixed_overhead_bytes"] < 0 or values["safety_reserve_bytes"] < 0:
            raise ValueError("SAM2 host RAM overhead and reserve must be non-negative.")
        for name, value in values.items():
            object.__setattr__(self, name, value)

    def plan_frame(
        self,
        *,
        frame_shape: tuple[int, int],
        frame_channels: int,
        bbox_count: int,
        requested_chunk_size: int,
        current_host_ram_bytes: int = 0,
    ) -> Sam2HostMemoryPlan:
        height, width = _validate_frame_shape(frame_shape)
        channels = int(frame_channels)
        count = int(bbox_count)
        requested = int(requested_chunk_size)
        current_host_ram = max(0, int(current_host_ram_bytes))
        if channels <= 0:
            raise ValueError("frame_channels must be positive.")
        if count < 0:
            raise ValueError("bbox_count must be non-negative.")
        if requested <= 0:
            raise ValueError("requested_chunk_size must be positive.")

        pixel_count = height * width
        frame_bytes = pixel_count * (channels * 4 + 3)
        result_bytes_per_bbox = pixel_count + 4 + 4 * 4 + 8
        retained_result_bytes = count * result_bytes_per_bbox
        per_chunk_bbox_bytes = (
            4 * 4
            + pixel_count * 4
            + pixel_count
            + result_bytes_per_bbox
        )
        base_bytes = (
            max(self.fixed_overhead_bytes, current_host_ram)
            + self.safety_reserve_bytes
            + frame_bytes
            + retained_result_bytes
        )

        if count == 0:
            return Sam2HostMemoryPlan(
                limit_bytes=self.limit_bytes,
                frame_bytes=frame_bytes,
                retained_result_bytes=0,
                per_chunk_bbox_bytes=per_chunk_bbox_bytes,
                chunk_size=0,
                chunk_count=0,
                predicted_peak_bytes=base_bytes,
            )

        available_for_chunk = self.limit_bytes - base_bytes
        max_chunk_size = available_for_chunk // per_chunk_bbox_bytes
        if max_chunk_size < 1:
            raise Sam2MemoryBudgetError(
                "SAM2 frame cannot fit one BBox within the configured host RAM budget."
            )
        chunk_size = min(requested, count, int(max_chunk_size))
        return Sam2HostMemoryPlan(
            limit_bytes=self.limit_bytes,
            frame_bytes=frame_bytes,
            retained_result_bytes=retained_result_bytes,
            per_chunk_bbox_bytes=per_chunk_bbox_bytes,
            chunk_size=chunk_size,
            chunk_count=ceil(count / chunk_size),
            predicted_peak_bytes=base_bytes + chunk_size * per_chunk_bbox_bytes,
        )

    def plan_sequence(
        self,
        *,
        frame_shape: tuple[int, int],
        frame_channels: int,
        frame_bbox_counts: tuple[int, ...],
        requested_chunk_size: int,
    ) -> Sam2SequenceMemoryPlan:
        total_bbox_count = 0
        total_chunk_count = 0
        predicted_peak_bytes = self.fixed_overhead_bytes + self.safety_reserve_bytes
        for bbox_count in frame_bbox_counts:
            frame_plan = self.plan_frame(
                frame_shape=frame_shape,
                frame_channels=frame_channels,
                bbox_count=int(bbox_count),
                requested_chunk_size=requested_chunk_size,
            )
            total_bbox_count += int(bbox_count)
            total_chunk_count += frame_plan.chunk_count
            predicted_peak_bytes = max(predicted_peak_bytes, frame_plan.predicted_peak_bytes)
        return Sam2SequenceMemoryPlan(
            frame_count=len(frame_bbox_counts),
            total_bbox_count=total_bbox_count,
            total_chunk_count=total_chunk_count,
            predicted_peak_bytes=predicted_peak_bytes,
        )


@dataclass(frozen=True)
class Sam2GpuMemoryBudget:
    physical_vram_bytes: int = DEFAULT_SAM2_GPU_PHYSICAL_BYTES
    working_limit_bytes: int = DEFAULT_SAM2_GPU_WORKING_LIMIT_BYTES
    reserve_bytes: int = DEFAULT_SAM2_GPU_RESERVE_BYTES
    fixed_overhead_bytes: int = DEFAULT_SAM2_GPU_FIXED_OVERHEAD_BYTES
    decoder_bytes_per_bbox: int = DEFAULT_SAM2_GPU_DECODER_BYTES_PER_BBOX

    def __post_init__(self) -> None:
        values = {
            "physical_vram_bytes": int(self.physical_vram_bytes),
            "working_limit_bytes": int(self.working_limit_bytes),
            "reserve_bytes": int(self.reserve_bytes),
            "fixed_overhead_bytes": int(self.fixed_overhead_bytes),
            "decoder_bytes_per_bbox": int(self.decoder_bytes_per_bbox),
        }
        if any(value <= 0 for value in values.values()):
            raise ValueError("SAM2 GPU memory budget values must be positive.")
        if (
            values["working_limit_bytes"] + values["reserve_bytes"]
            > values["physical_vram_bytes"]
        ):
            raise ValueError("SAM2 GPU working limit and reserve exceed physical VRAM.")
        for name, value in values.items():
            object.__setattr__(self, name, value)

    def plan_chunk(
        self,
        *,
        frame_shape: tuple[int, int],
        requested_chunk_size: int,
        remaining_bbox_count: int,
        free_vram_bytes: int,
        total_vram_bytes: int,
    ) -> Sam2GpuMemoryPlan:
        height, width = _validate_frame_shape(frame_shape)
        requested = int(requested_chunk_size)
        remaining = int(remaining_bbox_count)
        free_vram = int(free_vram_bytes)
        reported_total = int(total_vram_bytes)
        if requested <= 0 or remaining <= 0:
            raise ValueError("SAM2 GPU chunk sizes and remaining BBox count must be positive.")
        if free_vram < 0 or reported_total <= 0:
            raise ValueError(
                "CUDA memory information must be non-negative with positive total VRAM."
            )

        physical_vram = min(self.physical_vram_bytes, reported_total)
        usable_free_vram = min(free_vram, physical_vram)
        effective_limit = min(
            self.working_limit_bytes,
            max(0, usable_free_vram - self.reserve_bytes),
        )
        embedding_bytes = height * width * 16
        per_chunk_bbox_bytes = self.decoder_bytes_per_bbox + height * width * 4
        available_for_chunk = effective_limit - self.fixed_overhead_bytes - embedding_bytes
        max_chunk_size = available_for_chunk // per_chunk_bbox_bytes
        if max_chunk_size < 1:
            raise Sam2MemoryBudgetError(
                "SAM2 cannot fit one BBox within the currently available GPU memory."
            )
        chunk_size = min(requested, remaining, int(max_chunk_size))
        predicted_usage = (
            self.fixed_overhead_bytes
            + embedding_bytes
            + chunk_size * per_chunk_bbox_bytes
        )
        return Sam2GpuMemoryPlan(
            physical_vram_bytes=physical_vram,
            free_vram_bytes=usable_free_vram,
            effective_limit_bytes=effective_limit,
            reserve_bytes=self.reserve_bytes,
            per_chunk_bbox_bytes=per_chunk_bbox_bytes,
            chunk_size=chunk_size,
            predicted_usage_bytes=predicted_usage,
        )


class Sam2AdaptiveMemoryController:
    """Select a chunk from host and current GPU limits and report diagnostics."""

    def __init__(
        self,
        *,
        host_budget: Sam2MemoryBudget | None = None,
        gpu_budget: Sam2GpuMemoryBudget | None = None,
        cuda_memory_info: Callable[[], tuple[int, int]],
        host_rss_bytes: Callable[[], int] | None = None,
        diagnostic_callback: Callable[[Sam2MemoryDiagnostics], None] | None = None,
        cuda_empty_cache: Callable[[], None] | None = None,
        cuda_oom_error_types: tuple[type[BaseException], ...] = (),
    ) -> None:
        self.host_budget = host_budget or Sam2MemoryBudget()
        self.gpu_budget = gpu_budget or Sam2GpuMemoryBudget()
        self._cuda_memory_info = cuda_memory_info
        self._host_rss_bytes = host_rss_bytes or current_process_rss_bytes
        self._diagnostic_callback = diagnostic_callback
        self._cuda_empty_cache = cuda_empty_cache
        self._cuda_oom_error_types = tuple(cuda_oom_error_types)
        self._oom_chunk_cap: int | None = None
        self._measured_peak_host_ram_bytes = 0
        self.last_diagnostics: Sam2MemoryDiagnostics | None = None

    def limit_chunk_size(
        self,
        *,
        requested_chunk_size: int,
        remaining_bbox_count: int,
        total_bbox_count: int,
        frame_shape: tuple[int, int],
        frame_channels: int,
    ) -> int:
        measured_host_ram_bytes = max(0, int(self._host_rss_bytes()))
        host_plan = self.host_budget.plan_frame(
            frame_shape=frame_shape,
            frame_channels=frame_channels,
            bbox_count=total_bbox_count,
            requested_chunk_size=requested_chunk_size,
            current_host_ram_bytes=measured_host_ram_bytes,
        )
        free_vram_bytes, total_vram_bytes = self._cuda_memory_info()
        gpu_plan = self.gpu_budget.plan_chunk(
            frame_shape=frame_shape,
            requested_chunk_size=requested_chunk_size,
            remaining_bbox_count=remaining_bbox_count,
            free_vram_bytes=free_vram_bytes,
            total_vram_bytes=total_vram_bytes,
        )
        effective_chunk_size = min(
            host_plan.chunk_size,
            gpu_plan.chunk_size,
            remaining_bbox_count,
        )
        if self._oom_chunk_cap is not None:
            effective_chunk_size = min(effective_chunk_size, self._oom_chunk_cap)
        self._measured_peak_host_ram_bytes = max(
            self._measured_peak_host_ram_bytes,
            measured_host_ram_bytes,
        )
        diagnostics = Sam2MemoryDiagnostics(
            requested_chunk_size=int(requested_chunk_size),
            effective_chunk_size=effective_chunk_size,
            predicted_peak_host_ram_bytes=host_plan.predicted_peak_bytes,
            measured_host_ram_bytes=measured_host_ram_bytes,
            measured_peak_host_ram_bytes=self._measured_peak_host_ram_bytes,
            free_vram_bytes=gpu_plan.free_vram_bytes,
            effective_vram_limit_bytes=gpu_plan.effective_limit_bytes,
            predicted_vram_usage_bytes=gpu_plan.predicted_usage_bytes,
        )
        self.last_diagnostics = diagnostics
        if self._diagnostic_callback is not None:
            self._diagnostic_callback(diagnostics)
        return effective_chunk_size

    def recover_from_cuda_oom(
        self,
        *,
        error: BaseException,
        failed_chunk_size: int,
    ) -> bool:
        if not self._is_cuda_oom(error):
            return False
        if self._cuda_empty_cache is not None:
            self._cuda_empty_cache()
        failed_size = int(failed_chunk_size)
        if failed_size <= 1:
            raise Sam2MemoryBudgetError(
                "SAM2 CUDA out of memory occurred for a single-BBox chunk."
            ) from error
        reduced_size = max(1, failed_size // 2)
        if self._oom_chunk_cap is None:
            self._oom_chunk_cap = reduced_size
        else:
            self._oom_chunk_cap = min(self._oom_chunk_cap, reduced_size)
        return True

    def _is_cuda_oom(self, error: BaseException) -> bool:
        if self._cuda_oom_error_types and isinstance(error, self._cuda_oom_error_types):
            return True
        error_name = type(error).__name__.lower()
        error_module = type(error).__module__.lower()
        error_message = str(error).lower()
        return (
            "cuda out of memory" in error_message
            or ("torch" in error_module and "outofmemory" in error_name)
        )


class Sam2FrameResultQueue:
    """One-slot result queue enforcing frame-level backpressure."""

    def __init__(self) -> None:
        self._queue: Queue[object] = Queue(maxsize=1)

    def put(self, result: object, *, timeout: float | None = None) -> None:
        self._queue.put(result, block=True, timeout=timeout)

    def get(self, *, timeout: float | None = None) -> object:
        return self._queue.get(block=True, timeout=timeout)

    @property
    def capacity(self) -> int:
        return 1


def current_process_rss_bytes() -> int:
    try:
        import psutil  # type: ignore

        return max(0, int(psutil.Process().memory_info().rss))
    except Exception:
        return 0


def current_process_peak_rss_bytes() -> int:
    try:
        import psutil  # type: ignore

        memory_info = psutil.Process().memory_info()
        peak_wset = getattr(memory_info, "peak_wset", None)
        if peak_wset is not None:
            return max(0, int(peak_wset))
    except Exception:
        pass
    try:
        import resource
        import sys

        peak_rss = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        return max(0, peak_rss if sys.platform == "darwin" else peak_rss * 1024)
    except Exception:
        return current_process_rss_bytes()


def _validate_frame_shape(frame_shape: tuple[int, int]) -> tuple[int, int]:
    if len(frame_shape) != 2:
        raise ValueError("frame_shape must contain height and width.")
    height, width = (int(value) for value in frame_shape)
    if height <= 0 or width <= 0:
        raise ValueError("frame_shape dimensions must be positive.")
    return height, width
