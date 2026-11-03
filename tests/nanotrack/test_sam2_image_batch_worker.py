import sys
import textwrap
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from nanotrack.sam2 import (
    DEFAULT_SAM2_IMAGE_BATCH_WORKER_SCRIPT,
    Sam2ImageBatchBackendConfig,
    Sam2ImageBatchInput,
    Sam2ImageBatchSubprocessBackend,
)


def _write_fake_sam2_repo(repo_path: Path) -> None:
    package_path = repo_path / "sam2"
    package_path.mkdir(parents=True)
    (package_path / "__init__.py").write_text("", encoding="utf-8")
    (package_path / "build_sam.py").write_text(
        textwrap.dedent(
            """
            def build_sam2(config_identifier, checkpoint_path, **kwargs):
                assert config_identifier == "configs/fake.yaml"
                assert checkpoint_path == "selected-checkpoint.pt"
                assert kwargs["device"] == "cpu"
                return object()
            """
        ),
        encoding="utf-8",
    )
    (package_path / "sam2_image_predictor.py").write_text(
        textwrap.dedent(
            """
            import numpy as np

            class SAM2ImagePredictor:
                def __init__(self, model):
                    self.frame_shape = None

                def set_image(self, image):
                    import torch
                    assert torch.is_inference_mode_enabled()
                    self.frame_shape = image.shape[:2]

                def predict(self, *, box, multimask_output, return_logits):
                    import torch
                    assert torch.is_inference_mode_enabled()
                    assert multimask_output is False
                    assert return_logits is True
                    boxes = np.asarray(box, dtype=np.float32).reshape(-1, 4)
                    height, width = self.frame_shape
                    logits = np.full((len(boxes), 1, height, width), -10.0, dtype=np.float32)
                    for index, (x1, y1, x2, y2) in enumerate(boxes.astype(int)):
                        logits[index, 0, y1:y2, x1:x2] = 10.0
                    if len(boxes) == 1:
                        logits = logits[0]
                    return (
                        logits,
                        np.ones((len(boxes), 1), dtype=np.float32),
                        np.zeros((len(boxes), 1, 2, 2), dtype=np.float32),
                    )
            """
        ),
        encoding="utf-8",
    )


class Sam2ImageBatchWorkerTests(unittest.TestCase):
    def test_real_worker_cli_roundtrips_batch_contract_with_injected_sam2_repo(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            fake_repo = temp_path / "fake-sam2-repo"
            _write_fake_sam2_repo(fake_repo)
            backend = Sam2ImageBatchSubprocessBackend(
                Sam2ImageBatchBackendConfig(
                    python_executable=sys.executable,
                    worker_script=DEFAULT_SAM2_IMAGE_BATCH_WORKER_SCRIPT,
                    checkpoint_path="selected-checkpoint.pt",
                    repo_path=fake_repo,
                    config_path="configs/fake.yaml",
                    device="cpu",
                    timeout_sec=10.0,
                )
            )
            boxes = np.asarray(
                ((1.0, 1.0, 4.0, 4.0), (4.0, 2.0, 7.0, 5.0)),
                dtype=np.float32,
            )
            run_input = Sam2ImageBatchInput(
                frame=np.arange(48, dtype=np.float32).reshape(6, 8),
                frame_index=11,
                source_view="raw",
                boxes_xyxy=boxes,
                prompt_detection_ids=("bbox-one", "bbox-two"),
                mask_probability_threshold=0.7,
                chunk_size=16,
            )

            result = backend.run(run_input)

        self.assertEqual(result.frame_index, 11)
        self.assertEqual(result.prompt_detection_ids, ("bbox-one", "bbox-two"))
        np.testing.assert_array_equal(result.mask_bboxes_xyxy, boxes)
        np.testing.assert_array_equal(result.mask_component_counts, np.asarray((1, 1)))
        self.assertTrue(np.all(result.mask_scores > 0.99))

    def test_empty_batch_worker_does_not_require_sam2_repo_or_checkpoint(self) -> None:
        backend = Sam2ImageBatchSubprocessBackend(
            Sam2ImageBatchBackendConfig(
                python_executable=sys.executable,
                worker_script=DEFAULT_SAM2_IMAGE_BATCH_WORKER_SCRIPT,
                checkpoint_path="missing-checkpoint-is-not-opened.pt",
                repo_path=None,
                device="cpu",
                timeout_sec=10.0,
            )
        )
        run_input = Sam2ImageBatchInput(
            frame=np.zeros((4, 5), dtype=np.float32),
            frame_index=2,
            source_view="raw",
            boxes_xyxy=np.empty((0, 4), dtype=np.float32),
            prompt_detection_ids=(),
        )

        result = backend.run(run_input)

        self.assertEqual(result.frame_index, 2)
        self.assertEqual(result.result_count, 0)
        self.assertEqual(result.masks.shape, (0, 4, 5))


if __name__ == "__main__":
    unittest.main()
