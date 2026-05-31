import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    import pyqtgraph as pg
    from PyQt6.QtWidgets import QApplication
except ImportError:  # pragma: no cover - optional outside the target GUI env
    QApplication = None
    pg = None


@unittest.skipUnless(QApplication is not None, "PyQt6 is required for MolTrack app tests")
class MolTrackAppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_bootstrap_builds_workspace_without_showing_window(self) -> None:
        from moltrack.app import bootstrap_application

        app, window = bootstrap_application([], show=False)
        self.addCleanup(window.deleteLater)
        self.addCleanup(window.close)

        self.assertIs(app, QApplication.instance())
        self.assertEqual(app.organizationName(), "NaParA")
        self.assertEqual(app.applicationName(), "MolTrack")
        self.assertEqual(window.windowTitle(), "MolTrack Workspace")
        self.assertEqual(window.objectName(), "moltrack-workspace")
        self.assertFalse(window.isVisible())

    @unittest.skipUnless(pg is not None, "pyqtgraph is required for MolTrack rendering tests")
    def test_bootstrap_sets_row_major_image_axis_order(self) -> None:
        from moltrack.app import bootstrap_application

        pg.setConfigOptions(imageAxisOrder="col-major")

        _app, window = bootstrap_application([], show=False)
        self.addCleanup(window.deleteLater)
        self.addCleanup(window.close)

        self.assertEqual(pg.getConfigOption("imageAxisOrder"), "row-major")


if __name__ == "__main__":
    unittest.main()
