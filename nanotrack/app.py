import sys

import pyqtgraph as pg
from PyQt6.QtWidgets import QApplication

from nanotrack.ui import NanoTrackMainWindow


def configure_pyqtgraph() -> None:
    """Align NanoTrack image rendering with the rest of the repo."""
    pg.setConfigOptions(imageAxisOrder="row-major")


def main() -> None:
    configure_pyqtgraph()
    app = QApplication(sys.argv)
    app.setOrganizationName("NaParA")
    app.setApplicationName("NanoTrack")

    window = NanoTrackMainWindow()
    window.show()

    sys.exit(app.exec())
