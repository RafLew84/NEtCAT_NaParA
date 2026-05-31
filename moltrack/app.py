from __future__ import annotations

import sys
from collections.abc import Sequence

import pyqtgraph as pg
from PyQt6.QtWidgets import QApplication

from moltrack.ui import MolTrackWorkspace


def configure_pyqtgraph() -> None:
    """Align MolTrack image rendering with NanoTrack and NaParA viewers."""
    pg.setConfigOptions(imageAxisOrder="row-major")


def bootstrap_application(
    argv: Sequence[str] | None = None,
    *,
    show: bool = True,
) -> tuple[QApplication, MolTrackWorkspace]:
    """Create the MolTrack Qt application and main workspace."""
    configure_pyqtgraph()
    app = QApplication.instance()
    if app is None:
        app = QApplication(list(sys.argv if argv is None else argv))

    app.setOrganizationName("NaParA")
    app.setApplicationName("MolTrack")

    window = MolTrackWorkspace()
    if show:
        window.show()

    return app, window


def main(argv: Sequence[str] | None = None) -> int:
    app, _window = bootstrap_application(argv, show=True)
    return int(app.exec())
