import importlib
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

    def test_moltrack_main_imports_without_starting_gui(self) -> None:
        module = importlib.import_module("moltrack.main")

        self.assertTrue(callable(module.main))


if __name__ == "__main__":
    unittest.main()
