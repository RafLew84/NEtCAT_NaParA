import tempfile
import unittest
from pathlib import Path

import numpy as np

from nanotrack.mask_trackers import (
    MASK_TRACKER_CONTRACT_VERSION,
    MaskTrackerKind,
    MaskTrackerRunInput,
    MaskTrackerRunOutput,
)


def _roundtrip_npz_payload(payload: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    with tempfile.TemporaryDirectory() as temp_dir:
        path = Path(temp_dir) / "contract.npz"
        np.savez_compressed(path, **payload)
        with np.load(path, allow_pickle=False) as loaded:
            return {key: loaded[key] for key in loaded.files}


class MaskTrackerRunInputTests(unittest.TestCase):
    def test_input_roundtrip_preserves_tracker_prompts_and_source_view(self) -> None:
        frames = np.arange(3 * 5 * 6, dtype=np.float32).reshape(3, 5, 6)
        initial_mask = np.zeros((5, 6), dtype=bool)
        initial_mask[1:4, 2:5] = True
        run_input = MaskTrackerRunInput(
            tracker_kind="dam4sam",
            track_id=7,
            frame_index_offset=12,
            frames=frames,
            query_box_xyxy=np.asarray([1.0, 2.0, 5.0, 4.0], dtype=np.float64),
            query_point_tyx=np.asarray([0.0, 3.0, 4.0], dtype=np.float64),
            initial_mask=initial_mask,
            source_view="bm3d",
            mask_probability_threshold=0.7,
        )

        payload = run_input.to_npz_payload()
        payload = _roundtrip_npz_payload(payload)
        restored = MaskTrackerRunInput.from_npz_payload(payload)

        self.assertEqual(int(payload["contract_version"].item()), MASK_TRACKER_CONTRACT_VERSION)
        self.assertEqual(str(payload["tracker_kind"].item()), "dam4sam")
        self.assertEqual(restored.tracker_kind, MaskTrackerKind.DAM4SAM)
        self.assertEqual(restored.track_id, 7)
        self.assertEqual(restored.frame_index_offset, 12)
        self.assertEqual(restored.source_view, "bm3d")
        self.assertAlmostEqual(restored.mask_probability_threshold, 0.7)
        self.assertEqual(restored.frames.dtype, np.float32)
        self.assertEqual(restored.query_box_xyxy.dtype, np.float32)
        self.assertEqual(restored.query_point_tyx.dtype, np.float32)
        np.testing.assert_array_equal(restored.frames, frames)
        np.testing.assert_array_equal(restored.initial_mask, initial_mask)

    def test_input_accepts_initial_mask_as_only_prompt(self) -> None:
        run_input = MaskTrackerRunInput(
            tracker_kind=MaskTrackerKind.SAMURAI,
            track_id=2,
            frame_index_offset=3,
            frames=np.zeros((2, 4, 5), dtype=np.float32),
            initial_mask=np.ones((4, 5), dtype=np.uint8),
        )

        restored = MaskTrackerRunInput.from_npz_payload(_roundtrip_npz_payload(run_input.to_npz_payload()))

        self.assertEqual(restored.tracker_kind, MaskTrackerKind.SAMURAI)
        np.testing.assert_array_equal(restored.initial_mask, np.ones((4, 5), dtype=bool))

    def test_input_rejects_missing_prompt(self) -> None:
        with self.assertRaises(ValueError):
            MaskTrackerRunInput(
                tracker_kind="sam2",
                track_id=1,
                frame_index_offset=0,
                frames=np.zeros((2, 4, 4), dtype=np.float32),
            )

    def test_input_rejects_shape_and_time_mismatches(self) -> None:
        with self.assertRaises(ValueError):
            MaskTrackerRunInput(
                tracker_kind="sam2",
                track_id=1,
                frame_index_offset=0,
                frames=np.zeros((2, 4, 4), dtype=np.float32),
                query_box_xyxy=np.zeros((1, 4), dtype=np.float32),
            )
        with self.assertRaises(ValueError):
            MaskTrackerRunInput(
                tracker_kind="sam2",
                track_id=1,
                frame_index_offset=0,
                frames=np.zeros((2, 4, 4), dtype=np.float32),
                query_point_tyx=np.asarray([2.0, 1.0, 1.0], dtype=np.float32),
            )
        with self.assertRaises(ValueError):
            MaskTrackerRunInput(
                tracker_kind="sam2",
                track_id=1,
                frame_index_offset=0,
                frames=np.zeros((2, 4, 4), dtype=np.float32),
                initial_mask=np.zeros((3, 4), dtype=bool),
            )
        with self.assertRaises(ValueError):
            MaskTrackerRunInput(
                tracker_kind="sam2",
                track_id=1,
                frame_index_offset=0,
                frames=np.zeros((2, 4, 4), dtype=np.float32),
                query_box_xyxy=np.asarray([0.0, 0.0, 3.0, 3.0], dtype=np.float32),
                mask_probability_threshold=1.0,
            )

    def test_input_rejects_unsupported_contract_version(self) -> None:
        payload = MaskTrackerRunInput(
            tracker_kind="sam2",
            track_id=1,
            frame_index_offset=0,
            frames=np.zeros((2, 4, 4), dtype=np.float32),
            query_box_xyxy=np.asarray([0.0, 0.0, 3.0, 3.0], dtype=np.float32),
        ).to_npz_payload()
        payload["contract_version"] = np.asarray(999, dtype=np.int64)

        with self.assertRaises(ValueError):
            MaskTrackerRunInput.from_npz_payload(payload)


class MaskTrackerRunOutputTests(unittest.TestCase):
    def test_output_roundtrip_preserves_masks_summaries_and_backend_metadata(self) -> None:
        masks = np.zeros((3, 5, 6), dtype=bool)
        masks[:, 1:3, 2:5] = True
        run_output = MaskTrackerRunOutput(
            tracker_kind="samurai",
            track_id=11,
            frame_index_offset=9,
            masks=masks,
            visible_mask=np.asarray([True, True, False]),
            mask_areas=np.asarray([6.0, 6.0, 0.0], dtype=np.float64),
            mask_bboxes_xyxy=np.asarray(
                [
                    [2.0, 1.0, 5.0, 3.0],
                    [2.0, 1.0, 5.0, 3.0],
                    [0.0, 0.0, 0.0, 0.0],
                ],
                dtype=np.float64,
            ),
            mask_scores=np.asarray([0.9, 0.8, 0.1], dtype=np.float64),
            mask_component_counts=np.asarray([1, 1, 0], dtype=np.int64),
            model_name="samurai",
            model_variant="sam2.1_hiera_base_plus",
            checkpoint_name="sam2.1_hiera_base_plus.pt",
        )

        payload = run_output.to_npz_payload()
        payload = _roundtrip_npz_payload(payload)
        restored = MaskTrackerRunOutput.from_npz_payload(payload)

        self.assertEqual(restored.tracker_kind, MaskTrackerKind.SAMURAI)
        self.assertEqual(restored.track_id, 11)
        self.assertEqual(restored.frame_index_offset, 9)
        self.assertEqual(restored.model_name, "samurai")
        self.assertEqual(restored.model_variant, "sam2.1_hiera_base_plus")
        self.assertEqual(restored.checkpoint_name, "sam2.1_hiera_base_plus.pt")
        self.assertEqual(restored.mask_areas.dtype, np.float32)
        self.assertEqual(restored.mask_bboxes_xyxy.dtype, np.float32)
        self.assertEqual(restored.mask_scores.dtype, np.float32)
        self.assertEqual(restored.mask_component_counts.dtype, np.int32)
        np.testing.assert_array_equal(restored.masks, masks)
        np.testing.assert_array_equal(restored.visible_mask, np.asarray([True, True, False]))

    def test_output_rejects_summary_shape_mismatches(self) -> None:
        with self.assertRaises(ValueError):
            MaskTrackerRunOutput(
                tracker_kind="sam2",
                track_id=1,
                frame_index_offset=0,
                masks=np.zeros((2, 4, 4), dtype=bool),
                visible_mask=np.asarray([True]),
            )
        with self.assertRaises(ValueError):
            MaskTrackerRunOutput(
                tracker_kind="sam2",
                track_id=1,
                frame_index_offset=0,
                masks=np.zeros((2, 4, 4), dtype=bool),
                visible_mask=np.asarray([True, False]),
                mask_bboxes_xyxy=np.zeros((2, 5), dtype=np.float32),
            )
        with self.assertRaises(ValueError):
            MaskTrackerRunOutput(
                tracker_kind="sam2",
                track_id=1,
                frame_index_offset=0,
                masks=np.zeros((2, 4, 4), dtype=bool),
                visible_mask=np.asarray([True, False]),
                mask_scores=np.asarray([0.5], dtype=np.float32),
            )


if __name__ == "__main__":
    unittest.main()
