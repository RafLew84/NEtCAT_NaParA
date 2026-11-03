import tempfile
import unittest
from pathlib import Path

import numpy as np

from moltrack.sam3 import (
    MolTrackSam3BoxPrompt,
    MolTrackSam3RunInput,
    parse_moltrack_sam3_output_npz,
    write_moltrack_sam3_input_npz,
)


class MolTrackSam3ContractTests(unittest.TestCase):
    def test_npz_contract_writes_prompt_input_and_parses_mask_proposals(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            input_path = tmp_path / "input.npz"
            output_path = tmp_path / "output.npz"
            frame = np.arange(4 * 5, dtype=np.float32).reshape(4, 5)
            run_input = MolTrackSam3RunInput(
                frame_index=3,
                source_view="expanded_aligned",
                frame=frame,
                prompts=(
                    MolTrackSam3BoxPrompt(
                        bbox_xyxy=(1, 1, 4, 3),
                        label=1,
                        detection_id="bbox-1",
                    ),
                ),
                model_id="facebook/sam3",
                backend="transformers_sam3",
                score_threshold=0.35,
                mask_threshold=0.55,
            )

            write_moltrack_sam3_input_npz(run_input, input_path)

            with np.load(input_path, allow_pickle=False) as payload:
                self.assertEqual(int(payload["contract_version"]), 1)
                self.assertEqual(int(payload["frame_index"]), 3)
                self.assertEqual(str(payload["source_view"].item()), "expanded_aligned")
                self.assertEqual(str(payload["model_id"].item()), "facebook/sam3")
                self.assertEqual(str(payload["backend"].item()), "transformers_sam3")
                self.assertEqual(payload["image_rgb"].shape, (4, 5, 3))
                self.assertEqual(payload["image_rgb"].dtype, np.uint8)
                np.testing.assert_array_equal(
                    payload["prompt_bboxes_xyxy"],
                    np.asarray([[1, 1, 4, 3]], dtype=np.float32),
                )
                np.testing.assert_array_equal(payload["prompt_labels"], np.asarray([1], dtype=np.int64))
                self.assertEqual(str(payload["prompt_detection_ids"][0]), "bbox-1")
                self.assertAlmostEqual(float(payload["score_threshold"]), 0.35, places=6)
                self.assertAlmostEqual(float(payload["mask_threshold"]), 0.55, places=6)

            mask = np.zeros((1, 4, 5), dtype=bool)
            mask[0, 1:3, 2:4] = True
            np.savez_compressed(
                output_path,
                bboxes_xyxy=np.asarray([[2, 1, 4, 3]], dtype=np.float32),
                scores=np.asarray([0.91], dtype=np.float32),
                masks=mask,
                backend=np.asarray("transformers_sam3"),
                model_id=np.asarray("facebook/sam3"),
                device=np.asarray("cuda"),
            )

            output = parse_moltrack_sam3_output_npz(output_path, score_threshold=0.5)

            self.assertEqual(output.proposal_count, 1)
            proposal = output.proposals[0]
            self.assertEqual(proposal.bbox_xyxy, (2.0, 1.0, 4.0, 3.0))
            self.assertAlmostEqual(proposal.score, 0.91, places=6)
            np.testing.assert_array_equal(proposal.mask, mask[0])
            self.assertEqual(proposal.metadata["backend"], "transformers_sam3")
            self.assertEqual(proposal.metadata["model_id"], "facebook/sam3")
            self.assertEqual(proposal.metadata["device"], "cuda")

    def test_npz_input_crops_roi_and_writes_local_upscaled_prompt_boxes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "input.npz"
            frame = np.arange(4 * 5, dtype=np.float32).reshape(4, 5)
            run_input = MolTrackSam3RunInput(
                frame_index=0,
                source_view="raw",
                frame=frame,
                prompts=(
                    MolTrackSam3BoxPrompt(
                        bbox_xyxy=(2, 1, 4, 3),
                        label=1,
                        detection_id="bbox-1",
                    ),
                ),
                roi_xyxy=(1, 1, 5, 4),
                upscale=2,
            )

            write_moltrack_sam3_input_npz(run_input, input_path)

            with np.load(input_path, allow_pickle=False) as payload:
                self.assertEqual(payload["image_rgb"].shape, (6, 8, 3))
                np.testing.assert_array_equal(
                    payload["prompt_bboxes_xyxy"],
                    np.asarray([[2, 0, 6, 4]], dtype=np.float32),
                )
                np.testing.assert_array_equal(
                    payload["roi_xyxy"],
                    np.asarray([1, 1, 5, 4], dtype=np.float32),
                )
                self.assertEqual(int(payload["upscale"]), 2)


if __name__ == "__main__":
    unittest.main()
