import unittest
from unittest.mock import patch
from types import SimpleNamespace

import numpy as np

from nanotrack.processing.bm3d_preview import run_bm3d_batch, run_bm3d_preview


class _FakeBM3DModule:
    def __init__(self) -> None:
        self.last_image = None
        self.last_sigma_psd = None

    def bm3d(self, image, sigma_psd):
        self.last_image = np.array(image, copy=True)
        self.last_sigma_psd = float(sigma_psd)
        return image + 0.25


class BM3DPreviewTests(unittest.TestCase):
    def test_batch_restores_each_frames_offset_and_scale(self) -> None:
        frames = np.array([[[-1., 1.], [3., 5.]], [[100., 104.], [108., 112.]]])
        original = frames.copy()
        backend = SimpleNamespace(bm3d=lambda image, sigma_psd: image + 0.25)
        with patch.dict("sys.modules", {"bm3d": backend}):
            output = run_bm3d_batch(frames)
        np.testing.assert_allclose(output, [[[0.5, 2.5], [4.5, 6.5]], [[103., 107.], [111., 115.]]])
        np.testing.assert_array_equal(frames, original)

    def test_constant_and_missing_samples_keep_their_meaning(self) -> None:
        frames = np.full((3, 4, 4), 17.123456789, dtype=np.float64)
        frames[0, 0, 0] = np.nan
        frames[1] = np.nan
        frames[2] = [[100., 102., 104., 106.]] * 4
        frames[2, 1, 0] = np.inf
        original = frames.copy()
        backend = SimpleNamespace(bm3d=lambda image, sigma_psd: image)
        with patch.dict("sys.modules", {"bm3d": backend}):
            output = run_bm3d_batch(frames)
        self.assertEqual(float(output[0, 1, 1]), 17.123456789)
        np.testing.assert_array_equal(np.isfinite(output), np.isfinite(original))
        self.assertTrue(np.isnan(output[2, 1, 0]))
        np.testing.assert_allclose(output[2, 0], [100., 102., 104., 106.])
        np.testing.assert_array_equal(frames, original)

    def test_rejects_invalid_backend_output_without_mutating_input(self) -> None:
        frame = np.array([[100., 102.], [104., 106.]])
        original = frame.copy()
        for bad_output in (np.zeros((1, 2)), np.full((2, 2), np.nan), np.full((2, 2), 1 + 3j)):
            with self.subTest(shape=bad_output.shape, dtype=bad_output.dtype):
                def broken_backend(image, sigma_psd):
                    image[:] = -999
                    return bad_output
                with patch.dict("sys.modules", {"bm3d": SimpleNamespace(bm3d=broken_backend)}):
                    with self.assertRaises(ValueError):
                        run_bm3d_preview(frame)
                np.testing.assert_array_equal(frame, original)

    @patch("nanotrack.processing.bm3d_preview._import_bm3d_module")
    def test_runs_bm3d_with_clamped_input_and_sigma_factor(self, import_bm3d_mock) -> None:
        fake_bm3d = _FakeBM3DModule()
        import_bm3d_mock.return_value = fake_bm3d
        frame = np.array([[-1.0, 1.0], [3.0, 5.0]], dtype=np.float32)

        output = run_bm3d_preview(frame, sigma_factor=2.0)

        self.assertEqual(output.dtype, np.float64)
        self.assertAlmostEqual(float(fake_bm3d.last_image.min()), 0.0, places=6)
        self.assertAlmostEqual(float(fake_bm3d.last_image.max()), 1.0, places=6)

        mad = np.median(np.abs(fake_bm3d.last_image - np.median(fake_bm3d.last_image)))
        expected_sigma = float(mad * 1.4826 * 2.0)
        self.assertAlmostEqual(fake_bm3d.last_sigma_psd, expected_sigma, places=6)
        np.testing.assert_allclose(output, [[0.5, 2.5], [4.5, 6.5]])

    def test_rejects_non_positive_sigma_factor(self) -> None:
        with self.assertRaises(ValueError):
            run_bm3d_preview(np.zeros((2, 2), dtype=np.float32), sigma_factor=0.0)

    @patch("nanotrack.processing.bm3d_preview.run_bm3d_preview")
    def test_batch_runs_preview_for_all_frames_and_reports_progress(self, run_preview_mock) -> None:
        frames = np.arange(12, dtype=np.float32).reshape(3, 2, 2)
        run_preview_mock.side_effect = lambda frame, sigma_factor: frame + sigma_factor
        progress = []

        output = run_bm3d_batch(
            frames,
            sigma_factor=1.5,
            progress_callback=lambda done, total: progress.append((done, total)),
        )

        self.assertEqual(run_preview_mock.call_count, 3)
        np.testing.assert_allclose(output, frames + 1.5)
        self.assertEqual(progress, [(1, 3), (2, 3), (3, 3)])

    def test_batch_rejects_non_3d_frames(self) -> None:
        with self.assertRaises(ValueError):
            run_bm3d_batch(np.zeros((4, 4), dtype=np.float32), sigma_factor=1.0)
