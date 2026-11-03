import unittest
from threading import Event, Thread

from nanotrack.sam2 import (
    Sam2AdaptiveMemoryController,
    Sam2GpuMemoryBudget,
    Sam2FrameResultQueue,
    Sam2MemoryBudget,
    Sam2MemoryBudgetError,
)


class Sam2MemoryBudgetTests(unittest.TestCase):
    def test_host_budget_selects_largest_chunk_that_fits_synthetic_frame(self) -> None:
        budget = Sam2MemoryBudget(
            limit_bytes=752,
            fixed_overhead_bytes=100,
            safety_reserve_bytes=100,
        )

        plan = budget.plan_frame(
            frame_shape=(2, 2),
            frame_channels=1,
            bbox_count=10,
            requested_chunk_size=10,
        )

        self.assertEqual(plan.chunk_size, 3)
        self.assertEqual(plan.chunk_count, 4)
        self.assertEqual(plan.frame_bytes, 28)
        self.assertEqual(plan.retained_result_bytes, 320)
        self.assertEqual(plan.per_chunk_bbox_bytes, 68)
        self.assertEqual(plan.predicted_peak_bytes, 752)
        self.assertLessEqual(plan.predicted_peak_bytes, budget.limit_bytes)

    def test_more_streamed_frames_increase_chunks_but_not_peak_host_ram(self) -> None:
        budget = Sam2MemoryBudget()

        one_frame = budget.plan_sequence(
            frame_shape=(256, 256),
            frame_channels=1,
            frame_bbox_counts=(300,),
            requested_chunk_size=32,
        )
        one_hundred_frames = budget.plan_sequence(
            frame_shape=(256, 256),
            frame_channels=1,
            frame_bbox_counts=(300,) * 100,
            requested_chunk_size=32,
        )

        self.assertEqual(
            one_hundred_frames.total_chunk_count,
            one_frame.total_chunk_count * 100,
        )
        self.assertEqual(one_hundred_frames.total_bbox_count, 30_000)
        self.assertEqual(
            one_hundred_frames.predicted_peak_bytes,
            one_frame.predicted_peak_bytes,
        )
        self.assertLessEqual(
            one_hundred_frames.predicted_peak_bytes,
            budget.limit_bytes,
        )

    def test_host_configuration_above_sixteen_gib_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "16 GiB"):
            Sam2MemoryBudget(limit_bytes=16 * 1024**3 + 1)


class Sam2GpuMemoryBudgetTests(unittest.TestCase):
    def test_eight_gib_gpu_never_plans_more_than_seven_gib(self) -> None:
        gib = 1024**3
        budget = Sam2GpuMemoryBudget()

        plan = budget.plan_chunk(
            frame_shape=(256, 256),
            requested_chunk_size=100,
            remaining_bbox_count=100,
            free_vram_bytes=8 * gib,
            total_vram_bytes=8 * gib,
        )

        self.assertEqual(plan.physical_vram_bytes, 8 * gib)
        self.assertEqual(plan.effective_limit_bytes, 7 * gib)
        self.assertEqual(plan.reserve_bytes, 1 * gib)
        self.assertLessEqual(plan.predicted_usage_bytes, 7 * gib)
        self.assertGreaterEqual(plan.chunk_size, 1)

    def test_lower_currently_free_vram_reduces_the_chunk_automatically(self) -> None:
        gib = 1024**3
        budget = Sam2GpuMemoryBudget()

        full = budget.plan_chunk(
            frame_shape=(256, 256),
            requested_chunk_size=100,
            remaining_bbox_count=100,
            free_vram_bytes=8 * gib,
            total_vram_bytes=8 * gib,
        )
        constrained = budget.plan_chunk(
            frame_shape=(256, 256),
            requested_chunk_size=100,
            remaining_bbox_count=100,
            free_vram_bytes=4 * gib,
            total_vram_bytes=8 * gib,
        )

        self.assertEqual(full.chunk_size, 39)
        self.assertEqual(constrained.chunk_size, 7)
        self.assertEqual(constrained.effective_limit_bytes, 3 * gib)
        self.assertLess(constrained.chunk_size, full.chunk_size)
        self.assertLessEqual(
            constrained.predicted_usage_bytes,
            constrained.effective_limit_bytes,
        )


class Sam2AdaptiveMemoryControllerTests(unittest.TestCase):
    def test_effective_chunk_is_minimum_of_host_and_current_gpu_limits(self) -> None:
        gib = 1024**3
        diagnostics = []
        memory_info_calls = []
        host_budget = Sam2MemoryBudget(
            limit_bytes=1_208,
            fixed_overhead_bytes=100,
            safety_reserve_bytes=100,
        )

        def cuda_memory_info() -> tuple[int, int]:
            memory_info_calls.append(True)
            return 4 * gib, 8 * gib

        controller = Sam2AdaptiveMemoryController(
            host_budget=host_budget,
            gpu_budget=Sam2GpuMemoryBudget(),
            cuda_memory_info=cuda_memory_info,
            host_rss_bytes=lambda: 50,
            diagnostic_callback=diagnostics.append,
        )

        chunk_size = controller.limit_chunk_size(
            requested_chunk_size=32,
            remaining_bbox_count=20,
            total_bbox_count=20,
            frame_shape=(2, 2),
            frame_channels=1,
        )

        self.assertEqual(chunk_size, 5)
        self.assertEqual(len(memory_info_calls), 1)
        self.assertEqual(len(diagnostics), 1)
        self.assertEqual(diagnostics[0].effective_chunk_size, 5)
        self.assertEqual(diagnostics[0].predicted_peak_host_ram_bytes, 1_208)
        self.assertEqual(diagnostics[0].measured_peak_host_ram_bytes, 50)
        self.assertEqual(diagnostics[0].effective_vram_limit_bytes, 3 * gib)

    def test_measured_peak_host_ram_does_not_decrease_between_chunks(self) -> None:
        gib = 1024**3
        measured_values = iter((800, 600))
        diagnostics = []
        controller = Sam2AdaptiveMemoryController(
            cuda_memory_info=lambda: (8 * gib, 8 * gib),
            host_rss_bytes=lambda: next(measured_values),
            diagnostic_callback=diagnostics.append,
        )

        for remaining in (20, 10):
            controller.limit_chunk_size(
                requested_chunk_size=8,
                remaining_bbox_count=remaining,
                total_bbox_count=20,
                frame_shape=(4, 5),
                frame_channels=1,
            )

        self.assertEqual(
            [item.measured_host_ram_bytes for item in diagnostics],
            [800, 600],
        )
        self.assertEqual(
            [item.measured_peak_host_ram_bytes for item in diagnostics],
            [800, 800],
        )

    def test_cuda_oom_for_single_bbox_clears_cache_and_stops(self) -> None:
        class FakeCudaOutOfMemoryError(RuntimeError):
            pass

        empty_cache_calls = []
        controller = Sam2AdaptiveMemoryController(
            cuda_memory_info=lambda: (8 * 1024**3, 8 * 1024**3),
            cuda_empty_cache=lambda: empty_cache_calls.append(True),
            cuda_oom_error_types=(FakeCudaOutOfMemoryError,),
        )

        with self.assertRaisesRegex(Sam2MemoryBudgetError, "single-BBox"):
            controller.recover_from_cuda_oom(
                error=FakeCudaOutOfMemoryError("CUDA out of memory"),
                failed_chunk_size=1,
            )

        self.assertEqual(empty_cache_calls, [True])


class Sam2FrameResultQueueTests(unittest.TestCase):
    def test_second_frame_blocks_until_first_frame_is_consumed(self) -> None:
        result_queue = Sam2FrameResultQueue()
        producer_started = Event()
        producer_finished = Event()
        result_queue.put("frame-one")

        def produce_second_frame() -> None:
            producer_started.set()
            result_queue.put("frame-two")
            producer_finished.set()

        producer = Thread(target=produce_second_frame, daemon=True)
        producer.start()
        self.assertTrue(producer_started.wait(timeout=1.0))
        self.assertFalse(producer_finished.wait(timeout=0.05))

        self.assertEqual(result_queue.get(timeout=1.0), "frame-one")
        self.assertTrue(producer_finished.wait(timeout=1.0))
        self.assertEqual(result_queue.get(timeout=1.0), "frame-two")
        producer.join(timeout=1.0)
        self.assertFalse(producer.is_alive())


if __name__ == "__main__":
    unittest.main()
