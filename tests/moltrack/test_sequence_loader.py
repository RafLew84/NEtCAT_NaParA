import unittest
from pathlib import Path

import numpy as np

from moltrack.io import load_moltrack_image_series
from nanotrack.core import STMSequence, STMSequenceMetadata


class MolTrackSequenceLoaderTests(unittest.TestCase):
    def test_loader_accepts_single_mpp_series_and_returns_first_frame_active(self) -> None:
        frames = np.arange(24, dtype=np.float32).reshape(3, 2, 4)
        metadata = STMSequenceMetadata(pixels_x=4, pixels_y=2)
        calls = []

        def fake_sequence_loader(source_path, *, reverse_frame_order=False):
            calls.append((source_path, reverse_frame_order))
            return STMSequence(
                source_path=str(source_path),
                raw_frames=frames,
                metadata=metadata,
                active_frame_index=1,
                reverse_frame_order=reverse_frame_order,
            )

        series = load_moltrack_image_series(
            Path("movie.MPP"),
            reverse_frame_order=True,
            sequence_loader=fake_sequence_loader,
        )

        self.assertEqual(calls, [(Path("movie.MPP"), True)])
        self.assertEqual(series.source_path, "movie.MPP")
        self.assertTrue(series.reverse_frame_order)
        self.assertEqual(series.active_frame_index, 0)
        np.testing.assert_array_equal(series.active_frame, frames[0])

    def test_loader_rejects_non_mpp_sources(self) -> None:
        def fail_if_called(*args, **kwargs):
            raise AssertionError("sequence loader should not be called for non-MPP sources")

        with self.assertRaises(ValueError):
            load_moltrack_image_series(
                "frame.stp",
                sequence_loader=fail_if_called,
            )

    def test_loader_rejects_multiple_source_paths(self) -> None:
        def fail_if_called(*args, **kwargs):
            raise AssertionError("sequence loader should not be called for multiple sources")

        with self.assertRaises(ValueError):
            load_moltrack_image_series(
                ["first.mpp", "second.mpp"],
                sequence_loader=fail_if_called,
            )

    def test_loader_reports_source_when_underlying_loader_fails(self) -> None:
        def failing_sequence_loader(source_path, *, reverse_frame_order=False):
            raise RuntimeError("low-level parse failed")

        with self.assertRaisesRegex(ValueError, "Cannot load MolTrack STM source: broken.mpp"):
            load_moltrack_image_series(
                "broken.mpp",
                sequence_loader=failing_sequence_loader,
            )


if __name__ == "__main__":
    unittest.main()
