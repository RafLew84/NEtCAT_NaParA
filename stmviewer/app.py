"""Application entry point for STM Viewer."""

import sys

from PyQt6.QtWidgets import QApplication

from stmviewer.ui.main_window import STMViewerMainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setOrganizationName("NEtCAT")
    app.setApplicationName("STMViewer")

    window = STMViewerMainWindow()
    window.show()
    return app.exec()
