from __future__ import annotations

import sys
from typing import Any, Sequence


def configure_pyqtgraph(pg_module: Any | None = None) -> None:
    """Configure pyqtgraph image rendering for STM frame arrays."""

    if pg_module is None:
        import pyqtgraph as pg_module

    pg_module.setConfigOptions(imageAxisOrder="row-major")


def main(argv: Sequence[str] | None = None) -> int:
    configure_pyqtgraph()

    from PyQt6.QtWidgets import QApplication

    from moltrack.ui import MolTrackMainWindow

    app = QApplication(list(sys.argv if argv is None else argv))
    app.setOrganizationName("NaParA")
    app.setApplicationName("MolTrack")

    window = MolTrackMainWindow()
    window.show()

    return int(app.exec())

