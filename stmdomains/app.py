"""Application entry point for STM Domains."""

import sys

from PyQt6.QtWidgets import QApplication

from stmdomains.ui.main_window import STMDomainsMainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setOrganizationName("NEtCAT")
    app.setApplicationName("STMDomains")

    window = STMDomainsMainWindow()
    window.show()
    return app.exec()
