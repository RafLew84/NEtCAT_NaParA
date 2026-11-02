"""File choices and source confirmation stay on the GUI thread."""

from pathlib import Path
from typing import Protocol

from PyQt6.QtWidgets import QFileDialog, QMessageBox, QWidget


class ImportPrompts(Protocol):
    def choose_session(self) -> Path | None: ...
    def choose_source(self, message: str, suggested: Path | None) -> Path | None: ...
    def confirm_source(self, path: Path, reasons: tuple[str, ...]) -> bool: ...
    def show_error(self, message: str) -> None: ...


class QtImportPrompts:
    def __init__(self, parent: QWidget) -> None:
        self.parent = parent

    def choose_session(self) -> Path | None:
        filename, _ = QFileDialog.getOpenFileName(
            self.parent, "Otwórz zapis MolTrack", "",
            "Zapis MolTrack (*.moltrack.json *.json);;Wszystkie pliki (*)",
        )
        return Path(filename) if filename else None

    def choose_source(self, message: str, suggested: Path | None) -> Path | None:
        QMessageBox.information(self.parent, "Źródło obrazów MPP", message)
        filename, _ = QFileDialog.getOpenFileName(
            self.parent, "Wskaż plik MPP powiązany z zapisem", str(suggested or ""),
            "Obrazy MPP (*.mpp *.MPP);;Wszystkie pliki (*)",
        )
        return Path(filename) if filename else None

    def confirm_source(self, path: Path, reasons: tuple[str, ...]) -> bool:
        dialog = QMessageBox(
            QMessageBox.Icon.Question, "Potwierdź źródło obrazów",
            f"{path}\n\n" + "\n".join(reasons),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            self.parent,
        )
        for choice, label in ((QMessageBox.StandardButton.Yes, "Użyj tego pliku"),
                              (QMessageBox.StandardButton.Cancel, "Anuluj")):
            button = dialog.button(choice)
            if button is not None:
                button.setText(label)
        dialog.setDefaultButton(QMessageBox.StandardButton.Cancel)
        return dialog.exec() == QMessageBox.StandardButton.Yes

    def show_error(self, message: str) -> None:
        QMessageBox.warning(self.parent, "Nie można otworzyć obrazu", message)
