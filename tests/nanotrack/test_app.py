import unittest

try:
    import pyqtgraph as pg
except ImportError:  # pragma: no cover - optional outside the target GUI env
    pg = None

if pg is not None:
    from nanotrack.app import configure_pyqtgraph
else:  # pragma: no cover - optional outside the target GUI env
    configure_pyqtgraph = None


@unittest.skipUnless(pg is not None, "pyqtgraph is required for NanoTrack app tests")
class NanoTrackAppTests(unittest.TestCase):
    def test_configure_pyqtgraph_sets_row_major_axis_order(self) -> None:
        pg.setConfigOptions(imageAxisOrder="col-major")

        configure_pyqtgraph()

        self.assertEqual(pg.getConfigOption("imageAxisOrder"), "row-major")


if __name__ == "__main__":
    unittest.main()
