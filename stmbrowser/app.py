import sys

import pyqtgraph as pg
from PyQt6.QtWidgets import QApplication

from stmbrowser.ui.main_window import STMBrowserMainWindow


def main() -> None:
    pg.setConfigOptions(imageAxisOrder="row-major")

    app = QApplication(sys.argv)
    app.setOrganizationName("NaParA")
    app.setApplicationName("STM Browser")

    window = STMBrowserMainWindow()
    window.show()

    sys.exit(app.exec())
