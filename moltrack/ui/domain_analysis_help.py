from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QAction, QDesktopServices
from PyQt6.QtWidgets import QMainWindow, QMenu

from moltrack import __version__ as moltrack_version


DOMAIN_ANALYSIS_GUIDE_NAME = "DOMAIN_ANALYSIS_USER_GUIDE.md"


def domain_analysis_guide_path() -> Path:
    """Return the version-controlled guide shipped with this application."""

    return (
        Path(__file__).resolve().parents[2]
        / "docs"
        / "moltrack"
        / DOMAIN_ANALYSIS_GUIDE_NAME
    ).resolve()


def install_domain_analysis_help(
    window: QMainWindow,
    *,
    documentation_opener: Callable[[Path], object] | None = None,
) -> tuple[QMenu, QAction]:
    """Install the version-compatible Domain Analysis Help entry."""

    opener = documentation_opener or _open_local_document
    menu_bar = window.menuBar()
    if menu_bar is None:
        raise RuntimeError("The main window has no menu bar for Domain Analysis Help.")
    help_menu = menu_bar.addMenu("Help")
    if help_menu is None:
        raise RuntimeError("Unable to create the Domain Analysis Help menu.")
    action = QAction("Domain Analysis Guide", window)
    action.setToolTip(f"Open the MolTrack {moltrack_version} Domain Analysis guide")
    action.triggered.connect(
        lambda _checked=False: opener(domain_analysis_guide_path())
    )
    help_menu.addAction(action)
    return help_menu, action


def _open_local_document(path: Path) -> bool:
    return QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))


__all__ = [
    "DOMAIN_ANALYSIS_GUIDE_NAME",
    "domain_analysis_guide_path",
    "install_domain_analysis_help",
]
