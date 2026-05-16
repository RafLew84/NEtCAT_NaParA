import sys
import textwrap
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from nanotrack.mask_trackers import (
    MaskTrackerBackendConfig,
    MaskTrackerKind,
    MaskTrackerRunInput,
    MaskTrackerSubprocessBackend,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
DAM4SAM_WORKER = REPO_ROOT / "nanotrack" / "mask_trackers" / "run_dam4sam_subprocess.py"


class Dam4SamStubWorkerTests(unittest.TestCase):
    def test_stub_worker_runs_through_common_subprocess_backend(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            models_dir = temp_path / "models"
            models_dir.mkdir()
            checkpoint = models_dir / "sam2.1_hiera_base_plus.pt"
            checkpoint.write_bytes(b"stub checkpoint")
            repo_path = temp_path / "dam4sam_repo"
            repo_path.mkdir()

            backend = MaskTrackerSubprocessBackend(
                MaskTrackerBackendConfig(
                    kind=MaskTrackerKind.DAM4SAM,
                    python_executable=sys.executable,
                    worker_script=DAM4SAM_WORKER,
                    models_dir=models_dir,
                    checkpoint_path=checkpoint,
                    repo_path=repo_path,
                    variant="stub",
                    config_identifier=None,
                    device="cpu",
                    timeout_sec=10.0,
                    working_directory=REPO_ROOT,
                )
            )
            frames = np.zeros((3, 6, 8), dtype=np.float32)
            run_input = MaskTrackerRunInput(
                tracker_kind=MaskTrackerKind.DAM4SAM,
                track_id=7,
                frame_index_offset=4,
                frames=frames,
                query_box_xyxy=np.asarray([2.0, 1.0, 5.0, 4.0], dtype=np.float32),
                source_view="raw",
            )

            result = backend.run(run_input)

        expected_mask = np.zeros((6, 8), dtype=bool)
        expected_mask[1:4, 2:5] = True
        self.assertEqual(result.tracker_kind, MaskTrackerKind.DAM4SAM)
        self.assertEqual(result.track_id, 7)
        self.assertEqual(result.frame_index_offset, 4)
        self.assertEqual(result.model_name, "dam4sam_stub")
        self.assertEqual(result.model_variant, "stub")
        self.assertEqual(result.checkpoint_name, "sam2.1_hiera_base_plus.pt")
        np.testing.assert_array_equal(result.masks, np.repeat(expected_mask[None, :, :], 3, axis=0))
        np.testing.assert_array_equal(result.visible_mask, np.asarray([True, True, True]))
        np.testing.assert_array_equal(result.mask_areas, np.asarray([9.0, 9.0, 9.0], dtype=np.float32))
        np.testing.assert_array_equal(
            result.mask_bboxes_xyxy,
            np.asarray(
                [
                    [2.0, 1.0, 5.0, 4.0],
                    [2.0, 1.0, 5.0, 4.0],
                    [2.0, 1.0, 5.0, 4.0],
                ],
                dtype=np.float32,
            ),
        )
        np.testing.assert_array_equal(result.mask_scores, np.asarray([1.0, 1.0, 1.0], dtype=np.float32))
        np.testing.assert_array_equal(result.mask_component_counts, np.asarray([1, 1, 1], dtype=np.int32))

    def test_real_worker_imports_repo_and_runs_tracker_api(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            models_dir = temp_path / "models"
            models_dir.mkdir()
            checkpoint = models_dir / "sam2.1_hiera_base_plus.pt"
            checkpoint.write_bytes(b"fake checkpoint")
            repo_path = temp_path / "dam4sam_repo"
            repo_path.mkdir()
            (repo_path / "dam4sam_tracker.py").write_text(
                textwrap.dedent(
                    """
                    import numpy as np


                    class DAM4SAMTracker:
                        def __init__(self, tracker_name="sam21pp-B"):
                            self.tracker_name = tracker_name
                            self.frame_index = 0

                        def initialize(self, image, init_mask, bbox=None):
                            self.frame_index = 0
                            mask = np.zeros((image.height, image.width), dtype=np.uint8)
                            if init_mask is not None:
                                mask = np.asarray(init_mask, dtype=np.uint8)
                            else:
                                x, y, w, h = [int(round(value)) for value in bbox]
                                mask[y:y + h, x:x + w] = 1
                            return {"pred_mask": mask}

                        def track(self, image):
                            self.frame_index += 1
                            mask = np.zeros((image.height, image.width), dtype=np.uint8)
                            row0 = min(image.height, self.frame_index)
                            row1 = min(image.height, self.frame_index + 2)
                            mask[row0:row1, 1:4] = 1
                            return {"pred_mask": mask}
                    """
                ),
                encoding="utf-8",
            )

            backend = MaskTrackerSubprocessBackend(
                MaskTrackerBackendConfig(
                    kind=MaskTrackerKind.DAM4SAM,
                    python_executable=sys.executable,
                    worker_script=DAM4SAM_WORKER,
                    models_dir=models_dir,
                    checkpoint_path=checkpoint,
                    repo_path=repo_path,
                    variant="sam21pp-B",
                    config_identifier="sam21pp_hiera_b+.yaml",
                    device="cpu",
                    timeout_sec=10.0,
                    working_directory=REPO_ROOT,
                )
            )
            frames = np.zeros((2, 6, 8), dtype=np.float32)
            run_input = MaskTrackerRunInput(
                tracker_kind=MaskTrackerKind.DAM4SAM,
                track_id=11,
                frame_index_offset=2,
                frames=frames,
                query_box_xyxy=np.asarray([2.0, 1.0, 5.0, 4.0], dtype=np.float32),
            )

            result = backend.run(run_input)

        expected_first_mask = np.zeros((6, 8), dtype=bool)
        expected_first_mask[1:4, 2:5] = True
        expected_second_mask = np.zeros((6, 8), dtype=bool)
        expected_second_mask[1:3, 1:4] = True
        self.assertEqual(result.tracker_kind, MaskTrackerKind.DAM4SAM)
        self.assertEqual(result.track_id, 11)
        self.assertEqual(result.frame_index_offset, 2)
        self.assertEqual(result.model_name, "dam4sam")
        self.assertEqual(result.model_variant, "sam21pp-B")
        self.assertEqual(result.checkpoint_name, "sam2.1_hiera_base_plus.pt")
        np.testing.assert_array_equal(result.masks[0], expected_first_mask)
        np.testing.assert_array_equal(result.masks[1], expected_second_mask)
        np.testing.assert_array_equal(result.visible_mask, np.asarray([True, True]))
        np.testing.assert_array_equal(result.mask_areas, np.asarray([9.0, 6.0], dtype=np.float32))
        np.testing.assert_array_equal(
            result.mask_bboxes_xyxy,
            np.asarray(
                [
                    [2.0, 1.0, 5.0, 4.0],
                    [1.0, 1.0, 4.0, 3.0],
                ],
                dtype=np.float32,
            ),
        )


if __name__ == "__main__":
    unittest.main()
