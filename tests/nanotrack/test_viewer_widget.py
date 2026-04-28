import unittest

import numpy as np

try:
    from napara.gui.widgets.viewer_widget import _image_for_pyqtgraph_display
except ImportError:  # pragma: no cover - optional outside GUI env
    _image_for_pyqtgraph_display = None


@unittest.skipUnless(_image_for_pyqtgraph_display is not None, "ViewerWidget dependencies are required")
class ViewerWidgetDisplayImageTests(unittest.TestCase):
    def test_display_image_replaces_nan_and_inf_without_mutating_source(self) -> None:
        source = np.asarray(
            [
                [1.0, np.nan],
                [np.inf, -np.inf],
            ],
            dtype=np.float64,
        )

        display = _image_for_pyqtgraph_display(source)

        self.assertEqual(display.dtype, np.float32)
        self.assertTrue(np.all(np.isfinite(display)))
        np.testing.assert_array_equal(
            source,
            np.asarray(
                [
                    [1.0, np.nan],
                    [np.inf, -np.inf],
                ],
                dtype=np.float64,
            ),
        )
        self.assertEqual(float(display[0, 0]), 1.0)
        self.assertEqual(float(display[0, 1]), 1.0)
        self.assertEqual(float(display[1, 0]), 1.0)
        self.assertEqual(float(display[1, 1]), 1.0)

    def test_display_image_uses_zero_when_all_pixels_are_non_finite(self) -> None:
        source = np.asarray([[np.nan, np.inf]], dtype=np.float32)

        display = _image_for_pyqtgraph_display(source)

        np.testing.assert_array_equal(display, np.zeros_like(source))

    def test_display_image_returns_finite_numeric_input_without_copying(self) -> None:
        source = np.asarray([[1, 2], [3, 4]], dtype=np.int16)

        display = _image_for_pyqtgraph_display(source)

        self.assertIs(display, source)


if __name__ == "__main__":
    unittest.main()
