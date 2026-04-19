import unittest
from unittest.mock import patch

import numpy as np

from nanotrack.processing.bm3d_preview import run_bm3d_preview


class _FakeBM3DModule:
    def __init__(self) -> None:
        self.last_image = None
        self.last_sigma_psd = None

    def bm3d(self, image, sigma_psd):
        self.last_image = np.array(image, copy=True)
        self.last_sigma_psd = float(sigma_psd)
        return image + 0.25


class BM3DPreviewTests(unittest.TestCase):
    @patch("nanotrack.processing.bm3d_preview._import_bm3d_module")
    def test_runs_bm3d_with_clamped_input_and_sigma_factor(self, import_bm3d_mock) -> None:
        fake_bm3d = _FakeBM3DModule()
        import_bm3d_mock.return_value = fake_bm3d
        frame = np.array([[-1.0, 1.0], [3.0, 5.0]], dtype=np.float32)

        output = run_bm3d_preview(frame, sigma_factor=2.0)

        self.assertEqual(output.dtype, np.float32)
        self.assertAlmostEqual(float(fake_bm3d.last_image.min()), 0.0, places=6)
        self.assertAlmostEqual(float(fake_bm3d.last_image.max()), 1.0, places=6)

        mad = np.median(np.abs(fake_bm3d.last_image - np.median(fake_bm3d.last_image)))
        expected_sigma = float(mad * 1.4826 * 2.0)
        self.assertAlmostEqual(fake_bm3d.last_sigma_psd, expected_sigma, places=6)
        np.testing.assert_allclose(output, fake_bm3d.last_image + 0.25)

    def test_rejects_non_positive_sigma_factor(self) -> None:
        with self.assertRaises(ValueError):
            run_bm3d_preview(np.zeros((2, 2), dtype=np.float32), sigma_factor=0.0)
