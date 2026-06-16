import unittest

from moltrack.app import configure_pyqtgraph


class _PyqtgraphAdapter:
    def __init__(self):
        self.options = {"imageAxisOrder": "col-major"}

    def setConfigOptions(self, **options):
        self.options.update(options)


class MolTrackAppTests(unittest.TestCase):
    def test_configure_pyqtgraph_sets_row_major_axis_order(self) -> None:
        pg = _PyqtgraphAdapter()

        configure_pyqtgraph(pg)

        self.assertEqual(pg.options["imageAxisOrder"], "row-major")


if __name__ == "__main__":
    unittest.main()
