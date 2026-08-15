from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from moltrack import __version__ as moltrack_version
from moltrack.ui import MolTrackMainWindow


def test_help_menu_opens_version_compatible_domain_analysis_guide() -> None:
    app = QApplication.instance() or QApplication([])
    opened: list[Path] = []
    window = MolTrackMainWindow(
        yolo_model_discovery=lambda: [],
        documentation_opener=lambda path: opened.append(path) or True,
    )
    try:
        assert window.help_menu.title() == "Help"
        assert window.action_domain_analysis_guide.text() == "Domain Analysis Guide"
        assert moltrack_version in window.action_domain_analysis_guide.toolTip()

        window.action_domain_analysis_guide.trigger()
        app.processEvents()

        assert opened == [
            (
                Path(__file__).resolve().parents[2]
                / "docs/moltrack/DOMAIN_ANALYSIS_USER_GUIDE.md"
            ).resolve()
        ]
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()
