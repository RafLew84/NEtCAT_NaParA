"""Explicit file, result and unsaved-work choices on the GUI thread."""

from pathlib import Path
from typing import Protocol

from PyQt6.QtWidgets import QFileDialog, QInputDialog, QMessageBox, QWidget


class ProjectPrompts(Protocol):
    def choose_path(self, suggested: Path) -> Path | None: ...
    def choose_analysis(self, options: list[tuple[str, str]]) -> str | None: ...
    def confirm_unsaved(self) -> str: ...


class ProjectFileDialog(QFileDialog):
    def accept(self) -> None:
        selected = self.selectedFiles()
        if selected and Path(selected[0]).suffix.lower() != '.stmdomains':
            self.selectFile(selected[0] + '.stmdomains')
        # Confirmation refers to the final name, including an appended extension.
        super().accept()


class QtProjectPrompts:
    def __init__(self, parent: QWidget) -> None:
        self.parent = parent

    def choose_path(self, suggested: Path) -> Path | None:
        dialog = ProjectFileDialog(self.parent, 'Zapisz projekt STM Domains', str(suggested))
        dialog.setOption(QFileDialog.Option.DontUseNativeDialog)
        dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
        dialog.setNameFilter('Projekt STM Domains (*.stmdomains)')
        dialog.setDefaultSuffix('stmdomains')
        # QFileDialog confirms replacement of an existing file, including the suffix.
        return Path(dialog.selectedFiles()[0]) if dialog.exec() else None

    def choose_analysis(self, options: list[tuple[str, str]]) -> str | None:
        choice, accepted = QInputDialog.getItem(
            self.parent, 'Wynik w projekcie',
            'Zapisz jeden przebieg analizy wraz ze stanami jego klatek.\n'
            'Projekt zawiera cały oryginalny MPP, oznaczenia, widok i szkic parametrów.\n'
            'Inne przebiegi zachowasz osobno przez „Zapisz jako…”.',
            [label for _, label in options], 0, False,
        )
        return next(key for key, label in options if label == choice) if accepted else None

    def confirm_unsaved(self) -> str:
        box = QMessageBox(QMessageBox.Icon.Question, 'Niezapisana praca',
                          'Zapisać projekt przed zamknięciem bieżącej pracy?\n'
                          'Trwające obliczenia zostaną zatrzymane; można zapisać wynik częściowy.',
                          QMessageBox.StandardButton.NoButton, self.parent)
        save = box.addButton('Zapisz…', QMessageBox.ButtonRole.AcceptRole)
        discard = box.addButton('Odrzuć zmiany', QMessageBox.ButtonRole.DestructiveRole)
        cancel = box.addButton('Anuluj', QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(cancel)
        box.setEscapeButton(cancel)
        box.exec()
        return 'save' if box.clickedButton() is save else 'discard' if box.clickedButton() is discard else 'cancel'
