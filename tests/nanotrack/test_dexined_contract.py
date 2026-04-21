import unittest

import numpy as np

from nanotrack.edges import DEXINED_CONTRACT_VERSION, DexiNedRunInput, DexiNedRunOutput


class DexiNedRunInputTests(unittest.TestCase):
    def test_input_roundtrip_preserves_frames_mask_and_options(self) -> None:
        frames = np.zeros((3, 8, 10), dtype=np.float32)
        polygon_mask = np.zeros((8, 10), dtype=bool)
        polygon_mask[2:6, 3:8] = True
        contract = DexiNedRunInput(
            frames=frames,
            polygon_mask=polygon_mask,
            frame_indices=np.asarray([10, 11, 12], dtype=np.int32),
            inference_resolution_hw=np.asarray([256, 256], dtype=np.int32),
            device="cuda",
            threshold=0.35,
            source_view="bm3d",
        )

        payload = contract.to_npz_payload()
        restored = DexiNedRunInput.from_npz_payload(payload)

        self.assertEqual(int(payload["contract_version"]), DEXINED_CONTRACT_VERSION)
        self.assertEqual(restored.device, "cuda")
        self.assertEqual(restored.source_view, "bm3d")
        self.assertAlmostEqual(restored.threshold, 0.35)
        np.testing.assert_array_equal(restored.frames, frames)
        np.testing.assert_array_equal(restored.polygon_mask, polygon_mask)
        np.testing.assert_array_equal(restored.frame_indices, np.asarray([10, 11, 12], dtype=np.int32))
        np.testing.assert_array_equal(restored.inference_resolution_hw, np.asarray([256, 256], dtype=np.int32))

    def test_input_requires_non_empty_polygon_mask(self) -> None:
        with self.assertRaises(ValueError):
            DexiNedRunInput(
                frames=np.zeros((2, 5, 6), dtype=np.float32),
                polygon_mask=np.zeros((5, 6), dtype=bool),
            )

    def test_input_validates_spatial_shape_and_threshold(self) -> None:
        with self.assertRaises(ValueError):
            DexiNedRunInput(
                frames=np.zeros((2, 5, 6), dtype=np.float32),
                polygon_mask=np.ones((4, 6), dtype=bool),
            )

        with self.assertRaises(ValueError):
            DexiNedRunInput(
                frames=np.zeros((2, 5, 6), dtype=np.float32),
                polygon_mask=np.ones((5, 6), dtype=bool),
                threshold=1.5,
            )


class DexiNedRunOutputTests(unittest.TestCase):
    def test_output_roundtrip_preserves_probabilities_and_binary_map(self) -> None:
        edge_prob = np.zeros((3, 5, 6), dtype=np.float32)
        edge_prob[:, 1:3, 2:4] = 0.9
        edge_binary = edge_prob > 0.5
        contract = DexiNedRunOutput(
            edge_prob=edge_prob,
            edge_binary=edge_binary,
            model_name="dexined",
            checkpoint_name="DexiNed_BIPED_10.pth",
        )

        payload = contract.to_npz_payload()
        restored = DexiNedRunOutput.from_npz_payload(payload)

        np.testing.assert_array_equal(restored.edge_prob, edge_prob)
        np.testing.assert_array_equal(restored.edge_binary, edge_binary)
        self.assertEqual(restored.model_name, "dexined")
        self.assertEqual(restored.checkpoint_name, "DexiNed_BIPED_10.pth")

    def test_output_validates_binary_shape_against_probability_map(self) -> None:
        with self.assertRaises(ValueError):
            DexiNedRunOutput(
                edge_prob=np.zeros((2, 4, 4), dtype=np.float32),
                edge_binary=np.zeros((4, 4), dtype=bool),
            )


if __name__ == "__main__":
    unittest.main()
