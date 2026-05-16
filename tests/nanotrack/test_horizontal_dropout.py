import unittest
from unittest.mock import patch

import numpy as np

from nanotrack.processing.horizontal_dropout import (
    run_horizontal_dropout_batch,
    run_horizontal_dropout_preview,
)


class HorizontalDropoutTests(unittest.TestCase):
    def test_preview_repairs_local_horizontal_segment(self) -> None:
        y = np.linspace(0.0, 1.0, 16, dtype=np.float32)[:, None]
        x = np.linspace(0.0, 0.2, 32, dtype=np.float32)[None, :]
        frame = (y + x).astype(np.float32)
        damaged = frame.copy()
        damaged[8, 8:14] += 3.0

        repaired, mask = run_horizontal_dropout_preview(
            damaged,
            threshold_sigma=2.5,
            min_width_frac=0.05,
            max_width_frac=0.3,
            max_thickness_px=2,
            gap_closing_px=2,
            repair_mode="vertical_interp",
        )

        self.assertEqual(repaired.dtype, np.float32)
        self.assertTrue(mask.any())
        self.assertTrue(mask[8, 10])
        expected = float((damaged[7, 10] + damaged[9, 10]) / 2.0)
        self.assertAlmostEqual(float(repaired[8, 10]), expected, places=4)
        self.assertLess(abs(float(repaired[8, 10] - expected)), abs(float(damaged[8, 10] - expected)))

    @patch("nanotrack.processing.horizontal_dropout.run_horizontal_dropout_preview")
    def test_batch_runs_preview_for_all_frames_and_reports_progress(self, run_preview_mock) -> None:
        frames = np.arange(12, dtype=np.float32).reshape(3, 2, 2)
        run_preview_mock.side_effect = lambda frame, **_: (frame + 2.0, np.zeros_like(frame, dtype=bool))
        progress = []

        output = run_horizontal_dropout_batch(
            frames,
            threshold_sigma=3.0,
            min_width_frac=0.02,
            max_width_frac=0.2,
            max_thickness_px=3,
            gap_closing_px=3,
            repair_mode="vertical_interp",
            progress_callback=lambda done, total: progress.append((done, total)),
        )

        self.assertEqual(run_preview_mock.call_count, 3)
        np.testing.assert_allclose(output, frames + 2.0)
        self.assertEqual(progress, [(1, 3), (2, 3), (3, 3)])

    def test_preview_rejects_invalid_width_range(self) -> None:
        with self.assertRaises(ValueError):
            run_horizontal_dropout_preview(
                np.zeros((8, 8), dtype=np.float32),
                min_width_frac=0.3,
                max_width_frac=0.2,
            )
