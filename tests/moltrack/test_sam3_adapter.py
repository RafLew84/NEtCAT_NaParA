import unittest

import numpy as np

from moltrack.core import MolecularDetection
from moltrack.sam3 import (
    MolTrackSam3BoxPrompt,
    MolTrackSam3ConceptAdapter,
    MolTrackSam3BackendConfig,
    MolTrackSam3Error,
    MolTrackSam3OutputProposal,
    MolTrackSam3RunOutput,
    MolTrackSam3SubprocessBackend,
)


class MolTrackSam3AdapterTests(unittest.TestCase):
    def test_adapter_maps_worker_proposals_from_roi_upscale_to_full_frame_coordinates(self) -> None:
        class FakeSam3Backend:
            def __init__(self) -> None:
                self.inputs = []

            def run(self, run_input):
                self.inputs.append(run_input)
                worker_mask = np.zeros((6, 8), dtype=bool)
                worker_mask[0:4, 2:6] = True
                return MolTrackSam3RunOutput(
                    proposals=(
                        MolTrackSam3OutputProposal(
                            bbox_xyxy=(2, 0, 6, 4),
                            score=0.92,
                            mask=worker_mask,
                            polygon_xy=((2, 0), (6, 0), (6, 4), (2, 4)),
                            metadata={"backend": "official_sam31"},
                        ),
                    )
                )

        backend = FakeSam3Backend()
        adapter = MolTrackSam3ConceptAdapter(backend=backend)
        frame = np.arange(5 * 6, dtype=np.float32).reshape(5, 6)
        detection = MolecularDetection(
            frame_index=7,
            bbox_xyxy=(2, 1, 4, 3),
            confidence=0.9,
            source_view="raw",
            detection_id="bbox-1",
        )

        proposals = adapter.segment_detections(
            frame,
            [detection],
            frame_index=7,
            source_view="raw",
            model_id="facebook/sam3.1",
            backend="official_sam31",
            roi_xyxy=(1, 1, 5, 4),
            upscale=2,
            score_threshold=0.4,
            mask_threshold=0.6,
        )

        self.assertEqual(len(backend.inputs), 1)
        run_input = backend.inputs[0]
        self.assertEqual(run_input.frame_index, 7)
        self.assertEqual(run_input.source_view, "raw")
        self.assertEqual(run_input.model_id, "facebook/sam3.1")
        self.assertEqual(run_input.backend, "official_sam31")
        self.assertEqual(run_input.roi_xyxy, (1.0, 1.0, 5.0, 4.0))
        self.assertEqual(run_input.upscale, 2)
        self.assertEqual(run_input.score_threshold, 0.4)
        self.assertEqual(run_input.mask_threshold, 0.6)
        self.assertEqual(run_input.prompts[0].bbox_xyxy, (2.0, 1.0, 4.0, 3.0))
        self.assertEqual(run_input.prompts[0].detection_id, "bbox-1")

        self.assertEqual(len(proposals), 1)
        proposal = proposals[0]
        self.assertEqual(proposal.frame_index, 7)
        self.assertEqual(proposal.source_view, "raw")
        self.assertEqual(proposal.bbox_xyxy, (2.0, 1.0, 4.0, 3.0))
        self.assertEqual(
            proposal.polygon_xy,
            ((2.0, 1.0), (4.0, 1.0), (4.0, 3.0), (2.0, 3.0)),
        )
        expected_mask = np.zeros((5, 6), dtype=bool)
        expected_mask[1:3, 2:4] = True
        np.testing.assert_array_equal(proposal.mask, expected_mask)
        self.assertAlmostEqual(proposal.score, 0.92)
        self.assertEqual(proposal.prompt_detection_ids, ("bbox-1",))
        self.assertEqual(proposal.model_name, "facebook/sam3.1")
        self.assertEqual(proposal.metadata["backend"], "official_sam31")

    def test_adapter_runs_explicit_prompt_batch_and_reports_positive_prompt_ids(self) -> None:
        class FakeSam3Backend:
            def __init__(self) -> None:
                self.inputs = []

            def run(self, run_input):
                self.inputs.append(run_input)
                return MolTrackSam3RunOutput(
                    proposals=(
                        MolTrackSam3OutputProposal(
                            bbox_xyxy=(1, 1, 4, 4),
                            score=0.8,
                        ),
                    )
                )

        backend = FakeSam3Backend()
        adapter = MolTrackSam3ConceptAdapter(backend=backend)
        frame = np.arange(5 * 6, dtype=np.float32).reshape(5, 6)
        prompts = (
            MolTrackSam3BoxPrompt(bbox_xyxy=(1, 1, 3, 3), label=1, detection_id="positive-1"),
            MolTrackSam3BoxPrompt(bbox_xyxy=(4, 1, 5, 3), label=0, detection_id="negative-1"),
        )

        proposals = adapter.segment_prompts(
            frame,
            prompts,
            frame_index=0,
            source_view="raw",
            model_id="facebook/sam3",
            score_threshold=0.4,
            mask_threshold=0.7,
            max_results=12,
        )

        self.assertEqual(len(backend.inputs), 1)
        run_input = backend.inputs[0]
        self.assertEqual([prompt.label for prompt in run_input.prompts], [1, 0])
        self.assertEqual([prompt.detection_id for prompt in run_input.prompts], ["positive-1", "negative-1"])
        self.assertEqual(run_input.score_threshold, 0.4)
        self.assertEqual(run_input.mask_threshold, 0.7)
        self.assertEqual(run_input.max_results, 12)
        self.assertEqual(len(proposals), 1)
        self.assertEqual(proposals[0].prompt_detection_ids, ("positive-1",))

    def test_subprocess_backend_reports_missing_sam3_environment_as_domain_error(self) -> None:
        def fake_subprocess_run(*_args, **_kwargs):
            raise FileNotFoundError("missing sam3 python")

        backend = MolTrackSam3SubprocessBackend(
            config=MolTrackSam3BackendConfig(
                python_executable="missing-python.exe",
                transformers_worker_script="missing-worker.py",
            ),
            subprocess_run=fake_subprocess_run,
        )
        frame = np.arange(4 * 5, dtype=np.float32).reshape(4, 5)
        detection = MolecularDetection(
            frame_index=0,
            bbox_xyxy=(1, 1, 4, 3),
            confidence=0.9,
            source_view="raw",
            detection_id="bbox-1",
        )
        adapter = MolTrackSam3ConceptAdapter(backend=backend)

        with self.assertRaisesRegex(MolTrackSam3Error, "SAM3 executable or worker not found"):
            adapter.segment_detections(
                frame,
                [detection],
                frame_index=0,
                source_view="raw",
                model_id="facebook/sam3",
            )


if __name__ == "__main__":
    unittest.main()
