import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest import mock

import numpy as np

from nanotrack.sam2 import (
    Sam2AdaptiveMemoryController,
    Sam2GpuMemoryBudget,
    Sam2ImageBatchInput,
    Sam2ImagePredictorKernel,
    Sam2MemoryBudget,
    Sam2MemoryBudgetError,
    build_sam2_image_predictor_kernel,
)


class _FakeImagePredictor:
    def __init__(self, mask_logits: np.ndarray) -> None:
        self.mask_logits = np.asarray(mask_logits, dtype=np.float32)
        self.set_image_calls: list[np.ndarray] = []
        self.predict_calls: list[dict[str, object]] = []

    def set_image(self, image: np.ndarray) -> None:
        self.set_image_calls.append(np.asarray(image).copy())

    def predict(self, **kwargs):
        self.predict_calls.append(dict(kwargs))
        return (
            self.mask_logits.copy(),
            np.asarray((0.75,), dtype=np.float32),
            np.zeros((1, 2, 2), dtype=np.float32),
        )


class _BatchImagePredictor:
    def __init__(self, frame_shape: tuple[int, int]) -> None:
        self.frame_shape = frame_shape
        self.set_image_calls: list[np.ndarray] = []
        self.predict_calls: list[np.ndarray] = []

    def set_image(self, image: np.ndarray) -> None:
        self.set_image_calls.append(np.asarray(image).copy())

    def predict(self, **kwargs):
        boxes = np.asarray(kwargs["box"], dtype=np.float32)
        if boxes.ndim == 1:
            boxes = boxes[None, ...]
        self.predict_calls.append(boxes.copy())
        count = int(boxes.shape[0])
        height, width = self.frame_shape
        logits = np.ones((count, 1, height, width), dtype=np.float32)
        if count == 1:
            logits = logits[0]
        return (
            logits,
            np.full((count, 1), 0.75, dtype=np.float32),
            np.zeros((count, 1, 2, 2), dtype=np.float32),
        )


class _BoxEncodedBatchPredictor(_BatchImagePredictor):
    def predict(self, **kwargs):
        boxes = np.asarray(kwargs["box"], dtype=np.float32)
        if boxes.ndim == 1:
            boxes = boxes[None, ...]
        self.predict_calls.append(boxes.copy())
        count = int(boxes.shape[0])
        height, width = self.frame_shape
        logits = np.full((count, 1, height, width), -10.0, dtype=np.float32)
        for index, box in enumerate(boxes):
            logits[index, 0, int(box[1]), int(box[0])] = 10.0
        if count == 1:
            logits = logits[0]
        return (
            logits,
            np.full((count, 1), 0.75, dtype=np.float32),
            np.zeros((count, 1, 2, 2), dtype=np.float32),
        )


class _RecordingChunkSizeLimiter:
    def __init__(self, limit: int) -> None:
        self.limit = int(limit)
        self.calls: list[dict[str, object]] = []

    def limit_chunk_size(self, **kwargs) -> int:
        self.calls.append(dict(kwargs))
        return self.limit


class _FakeCudaOutOfMemoryError(RuntimeError):
    pass


class _OomOnceBatchPredictor(_BatchImagePredictor):
    def __init__(self, frame_shape: tuple[int, int]) -> None:
        super().__init__(frame_shape)
        self._failed = False

    def predict(self, **kwargs):
        boxes = np.asarray(kwargs["box"], dtype=np.float32)
        if boxes.ndim == 1:
            boxes = boxes[None, ...]
        if not self._failed:
            self._failed = True
            self.predict_calls.append(boxes.copy())
            raise _FakeCudaOutOfMemoryError("CUDA out of memory")
        return super().predict(**kwargs)


class Sam2ImagePredictorKernelTests(unittest.TestCase):
    def test_single_bbox_runs_one_image_embedding_and_one_box_prompt(self) -> None:
        frame = np.arange(20, dtype=np.float32).reshape(4, 5)
        box = np.asarray(((1.0, 1.0, 4.0, 3.0),), dtype=np.float32)
        predictor = _FakeImagePredictor(np.ones((1, 4, 5), dtype=np.float32))
        kernel = Sam2ImagePredictorKernel(predictor)
        run_input = Sam2ImageBatchInput(
            frame=frame,
            frame_index=7,
            source_view="raw",
            boxes_xyxy=box,
            prompt_detection_ids=("bbox-7-1",),
        )

        result = kernel.run(run_input)

        self.assertEqual(len(predictor.set_image_calls), 1)
        self.assertEqual(predictor.set_image_calls[0].shape, (4, 5, 3))
        self.assertEqual(predictor.set_image_calls[0].dtype, np.uint8)
        self.assertEqual(len(predictor.predict_calls), 1)
        np.testing.assert_array_equal(predictor.predict_calls[0]["box"], box)
        self.assertFalse(predictor.predict_calls[0]["multimask_output"])
        self.assertTrue(predictor.predict_calls[0]["return_logits"])
        self.assertEqual(result.frame_index, 7)
        self.assertEqual(result.source_view, "raw")
        self.assertEqual(result.prompt_detection_ids, ("bbox-7-1",))

    def test_single_bbox_uses_legacy_sigmoid_threshold_and_original_frame_size(self) -> None:
        logits = np.asarray(
            (
                (-2.0, 0.0, 0.5, 2.0),
                (-1.0, 0.4, 1.0, -0.5),
                (-3.0, 0.8, 1.5, -2.0),
            ),
            dtype=np.float32,
        )
        predictor = _FakeImagePredictor(logits[None, ...])
        run_input = Sam2ImageBatchInput(
            frame=np.zeros((3, 4), dtype=np.float32),
            frame_index=2,
            source_view="expanded_aligned",
            boxes_xyxy=np.asarray(((0.0, 0.0, 4.0, 3.0),), dtype=np.float32),
            prompt_detection_ids=("bbox-2-1",),
            mask_probability_threshold=0.7,
        )

        result = Sam2ImagePredictorKernel(predictor).run(run_input)

        probabilities = 1.0 / (1.0 + np.exp(-logits))
        expected_mask = probabilities >= 0.7
        self.assertEqual(result.masks.shape, (1, 3, 4))
        np.testing.assert_array_equal(result.masks[0], expected_mask)
        self.assertAlmostEqual(result.mask_scores[0], float(probabilities[expected_mask].mean()))
        np.testing.assert_array_equal(
            result.mask_bboxes_xyxy[0],
            np.asarray((2.0, 0.0, 4.0, 3.0), dtype=np.float32),
        )

    def test_single_bbox_reports_eight_connected_component_count(self) -> None:
        logits = np.full((1, 5, 6), -10.0, dtype=np.float32)
        logits[0, 0:2, 0:2] = 10.0
        logits[0, 3:5, 4:6] = 10.0
        predictor = _FakeImagePredictor(logits)
        run_input = Sam2ImageBatchInput(
            frame=np.zeros((5, 6), dtype=np.float32),
            frame_index=0,
            source_view="raw",
            boxes_xyxy=np.asarray(((0.0, 0.0, 6.0, 5.0),), dtype=np.float32),
            prompt_detection_ids=("bbox-1",),
        )

        result = Sam2ImagePredictorKernel(predictor).run(run_input)

        np.testing.assert_array_equal(result.mask_component_counts, np.asarray((2,)))

    def test_factory_builds_sam2_image_predictor_without_eager_sam2_imports(self) -> None:
        build_calls: list[tuple[object, ...]] = []
        predictor_models: list[object] = []
        cuda_memory_info_calls: list[bool] = []
        model = object()

        build_module = ModuleType("sam2.build_sam")

        def fake_build_sam2(*args, **kwargs):
            build_calls.append((*args, kwargs))
            return model

        build_module.build_sam2 = fake_build_sam2  # type: ignore[attr-defined]
        predictor_module = ModuleType("sam2.sam2_image_predictor")

        class FakeSam2ImagePredictor:
            def __init__(self, supplied_model: object) -> None:
                predictor_models.append(supplied_model)

            def set_image(self, image: np.ndarray) -> None:
                pass

            def predict(self, **kwargs):
                return (
                    np.ones((1, 4, 5), dtype=np.float32),
                    np.asarray((0.75,), dtype=np.float32),
                    np.zeros((1, 2, 2), dtype=np.float32),
                )

        predictor_module.SAM2ImagePredictor = FakeSam2ImagePredictor  # type: ignore[attr-defined]
        sam2_package = ModuleType("sam2")
        sam2_package.__path__ = []  # type: ignore[attr-defined]
        torch_module = ModuleType("torch")

        class FakeTorchCudaOutOfMemoryError(RuntimeError):
            pass

        def fake_mem_get_info() -> tuple[int, int]:
            cuda_memory_info_calls.append(True)
            return 8 * 1024**3, 8 * 1024**3

        torch_module.cuda = SimpleNamespace(  # type: ignore[attr-defined]
            mem_get_info=fake_mem_get_info,
            empty_cache=lambda: None,
            OutOfMemoryError=FakeTorchCudaOutOfMemoryError,
        )

        with mock.patch.dict(
            "sys.modules",
            {
                "sam2": sam2_package,
                "sam2.build_sam": build_module,
                "sam2.sam2_image_predictor": predictor_module,
                "torch": torch_module,
            },
        ):
            kernel = build_sam2_image_predictor_kernel(
                config_identifier="configs/sam2.1/base_plus.yaml",
                checkpoint_path=Path("checkpoints/sam2.1_base_plus.pt"),
                device="cuda:0",
                apply_postprocessing=False,
            )
            kernel.run(
                Sam2ImageBatchInput(
                    frame=np.zeros((4, 5), dtype=np.float32),
                    frame_index=0,
                    source_view="raw",
                    boxes_xyxy=np.asarray(((1.0, 1.0, 4.0, 3.0),), dtype=np.float32),
                    prompt_detection_ids=("bbox-1",),
                )
            )

        self.assertIsInstance(kernel, Sam2ImagePredictorKernel)
        self.assertEqual(predictor_models, [model])
        self.assertEqual(cuda_memory_info_calls, [True])
        self.assertEqual(
            build_calls,
            [
                (
                    "configs/sam2.1/base_plus.yaml",
                    "checkpoints\\sam2.1_base_plus.pt",
                    {"device": "cuda:0", "apply_postprocessing": False},
                )
            ],
        )

    def test_seventy_bboxes_use_one_embedding_and_three_decoder_chunks(self) -> None:
        bbox_count = 70
        boxes = np.repeat(
            np.asarray(((1.0, 1.0, 4.0, 3.0),), dtype=np.float32),
            bbox_count,
            axis=0,
        )
        predictor = _BatchImagePredictor((4, 5))
        run_input = Sam2ImageBatchInput(
            frame=np.arange(20, dtype=np.float32).reshape(4, 5),
            frame_index=4,
            source_view="raw",
            boxes_xyxy=boxes,
            prompt_detection_ids=tuple(f"bbox-{index}" for index in range(bbox_count)),
        )

        result = Sam2ImagePredictorKernel(predictor).run(run_input)

        self.assertEqual(len(predictor.set_image_calls), 1)
        self.assertEqual([len(chunk) for chunk in predictor.predict_calls], [32, 32, 6])
        self.assertEqual(result.result_count, bbox_count)
        self.assertEqual(result.prompt_detection_ids, run_input.prompt_detection_ids)

    def test_results_keep_prompt_id_order_across_chunk_boundaries(self) -> None:
        boxes = np.asarray(
            (
                (0.0, 0.0, 2.0, 2.0),
                (1.0, 1.0, 3.0, 3.0),
                (2.0, 2.0, 4.0, 4.0),
                (3.0, 3.0, 5.0, 5.0),
                (4.0, 4.0, 6.0, 6.0),
            ),
            dtype=np.float32,
        )
        prompt_ids = ("alpha", "beta", "gamma", "delta", "epsilon")
        predictor = _BoxEncodedBatchPredictor((6, 6))
        run_input = Sam2ImageBatchInput(
            frame=np.zeros((6, 6), dtype=np.float32),
            frame_index=9,
            source_view="raw",
            boxes_xyxy=boxes,
            prompt_detection_ids=prompt_ids,
            chunk_size=2,
        )

        result = Sam2ImagePredictorKernel(predictor).run(run_input)

        expected_mask_boxes = np.asarray(
            tuple((box[0], box[1], box[0] + 1.0, box[1] + 1.0) for box in boxes),
            dtype=np.float32,
        )
        self.assertEqual([len(chunk) for chunk in predictor.predict_calls], [2, 2, 1])
        self.assertEqual(result.prompt_detection_ids, prompt_ids)
        np.testing.assert_array_equal(result.mask_bboxes_xyxy, expected_mask_boxes)

    def test_results_are_identical_for_chunk_sizes_one_sixteen_and_thirty_two(self) -> None:
        bbox_count = 35
        boxes = np.asarray(
            tuple(
                (
                    float(index % 8),
                    float((index // 8) % 8),
                    float(index % 8 + 2),
                    float((index // 8) % 8 + 2),
                )
                for index in range(bbox_count)
            ),
            dtype=np.float32,
        )
        prompt_ids = tuple(f"bbox-{index}" for index in range(bbox_count))
        results = []

        for chunk_size in (1, 16, 32):
            predictor = _BoxEncodedBatchPredictor((10, 10))
            run_input = Sam2ImageBatchInput(
                frame=np.zeros((10, 10), dtype=np.float32),
                frame_index=5,
                source_view="raw",
                boxes_xyxy=boxes,
                prompt_detection_ids=prompt_ids,
                chunk_size=chunk_size,
            )
            results.append(Sam2ImagePredictorKernel(predictor).run(run_input))

        reference = results[0]
        for result in results[1:]:
            self.assertEqual(result.prompt_detection_ids, reference.prompt_detection_ids)
            np.testing.assert_array_equal(result.masks, reference.masks)
            np.testing.assert_array_equal(result.mask_scores, reference.mask_scores)
            np.testing.assert_array_equal(result.mask_bboxes_xyxy, reference.mask_bboxes_xyxy)
            np.testing.assert_array_equal(
                result.mask_component_counts,
                reference.mask_component_counts,
            )

    def test_memory_limiter_can_reduce_each_decoder_chunk(self) -> None:
        bbox_count = 20
        boxes = np.repeat(
            np.asarray(((1.0, 1.0, 4.0, 3.0),), dtype=np.float32),
            bbox_count,
            axis=0,
        )
        predictor = _BatchImagePredictor((4, 5))
        limiter = _RecordingChunkSizeLimiter(limit=7)
        run_input = Sam2ImageBatchInput(
            frame=np.zeros((4, 5), dtype=np.float32),
            frame_index=0,
            source_view="raw",
            boxes_xyxy=boxes,
            prompt_detection_ids=tuple(f"bbox-{index}" for index in range(bbox_count)),
            chunk_size=32,
        )

        Sam2ImagePredictorKernel(predictor, chunk_size_limiter=limiter).run(run_input)

        self.assertEqual([len(chunk) for chunk in predictor.predict_calls], [7, 7, 6])
        self.assertEqual(
            [call["remaining_bbox_count"] for call in limiter.calls],
            [20, 13, 6],
        )
        self.assertTrue(
            all(call["requested_chunk_size"] == 32 for call in limiter.calls)
        )
        self.assertTrue(all(call["frame_shape"] == (4, 5) for call in limiter.calls))

    def test_empty_bbox_batch_returns_without_computing_an_embedding(self) -> None:
        predictor = _BatchImagePredictor((4, 5))
        run_input = Sam2ImageBatchInput(
            frame=np.zeros((4, 5), dtype=np.float32),
            frame_index=3,
            source_view="raw",
            boxes_xyxy=np.empty((0, 4), dtype=np.float32),
            prompt_detection_ids=(),
        )

        result = Sam2ImagePredictorKernel(predictor).run(run_input)

        self.assertEqual(predictor.set_image_calls, [])
        self.assertEqual(predictor.predict_calls, [])
        self.assertEqual(result.result_count, 0)
        self.assertEqual(result.masks.shape, (0, 4, 5))

    def test_host_configuration_over_budget_is_rejected_before_inference(self) -> None:
        gib = 1024**3
        predictor = _BatchImagePredictor((4, 5))
        controller = Sam2AdaptiveMemoryController(
            host_budget=Sam2MemoryBudget(
                limit_bytes=100,
                fixed_overhead_bytes=100,
                safety_reserve_bytes=100,
            ),
            gpu_budget=Sam2GpuMemoryBudget(),
            cuda_memory_info=lambda: (8 * gib, 8 * gib),
            host_rss_bytes=lambda: 0,
        )
        run_input = Sam2ImageBatchInput(
            frame=np.zeros((4, 5), dtype=np.float32),
            frame_index=0,
            source_view="raw",
            boxes_xyxy=np.asarray(((1.0, 1.0, 4.0, 3.0),), dtype=np.float32),
            prompt_detection_ids=("bbox-1",),
        )

        with self.assertRaisesRegex(Sam2MemoryBudgetError, "host RAM"):
            Sam2ImagePredictorKernel(
                predictor,
                chunk_size_limiter=controller,
            ).run(run_input)

        self.assertEqual(predictor.set_image_calls, [])
        self.assertEqual(predictor.predict_calls, [])

    def test_cuda_oom_clears_cache_and_retries_only_current_chunk_at_half_size(self) -> None:
        gib = 1024**3
        bbox_count = 8
        predictor = _OomOnceBatchPredictor((4, 5))
        empty_cache_calls = []
        controller = Sam2AdaptiveMemoryController(
            cuda_memory_info=lambda: (8 * gib, 8 * gib),
            host_rss_bytes=lambda: 0,
            cuda_empty_cache=lambda: empty_cache_calls.append(True),
            cuda_oom_error_types=(_FakeCudaOutOfMemoryError,),
        )
        run_input = Sam2ImageBatchInput(
            frame=np.zeros((4, 5), dtype=np.float32),
            frame_index=0,
            source_view="raw",
            boxes_xyxy=np.repeat(
                np.asarray(((1.0, 1.0, 4.0, 3.0),), dtype=np.float32),
                bbox_count,
                axis=0,
            ),
            prompt_detection_ids=tuple(f"bbox-{index}" for index in range(bbox_count)),
            chunk_size=8,
        )

        result = Sam2ImagePredictorKernel(
            predictor,
            chunk_size_limiter=controller,
        ).run(run_input)

        self.assertEqual(len(predictor.set_image_calls), 1)
        self.assertEqual([len(boxes) for boxes in predictor.predict_calls], [8, 4, 4])
        self.assertEqual(empty_cache_calls, [True])
        self.assertEqual(result.result_count, bbox_count)


if __name__ == "__main__":
    unittest.main()
