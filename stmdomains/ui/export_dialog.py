"""Choose one available run, a frame range and the current view's export scope."""

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QSpinBox, QVBoxLayout, QWidget,
)

from stmdomains.core.export import ExportOptions
from stmdomains.ui.export_selection import capture_export, export_choices
from stmdomains.ui.project_view import capture_view

if TYPE_CHECKING:
    from stmdomains.ui.main_window import STMDomainsMainWindow


class ExportDialog(QDialog):
    def __init__(self, window: 'STMDomainsMainWindow') -> None:
        super().__init__(window)
        self.main_window, self.controller = window, window.controller
        self.setWindowTitle('Eksport PNG / CSV')
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.resize(640, 520)
        layout = QVBoxLayout(self)
        self.fields = QWidget()
        form = QFormLayout(self.fields)
        self.selection = QComboBox()
        form.addRow('Wynik', self.selection)
        self.scope = QComboBox()
        for label, key in (('Bieżąca klatka', 'current'), ('Wybrany zakres', 'range')):
            self.scope.addItem(label, key)
        form.addRow('Klatki', self.scope)
        self.first, self.last = QSpinBox(), QSpinBox()
        for control in (self.first, self.last):
            control.setMinimum(1)
            control.setKeyboardTracking(False)
        form.addRow('Pierwsza klatka', self.first)
        form.addRow('Ostatnia klatka', self.last)
        formats = QHBoxLayout()
        self.csv, self.png = QCheckBox('Tabele CSV'), QCheckBox('Obrazy PNG')
        self.csv.setChecked(True)
        self.png.setChecked(True)
        formats.addWidget(self.csv)
        formats.addWidget(self.png)
        form.addRow('Formaty', formats)
        self.image_scope = QComboBox()
        self.image_scope.addItem('Pełny obraz bieżącego widoku', 'full')
        self.image_scope.addItem('Aktualnie widoczny wycinek', 'crop')
        form.addRow('Zakres PNG', self.image_scope)
        self.image_width = QSpinBox()
        self.image_width.setRange(320, 4096)
        self.image_width.setValue(1200)
        self.image_width.setSuffix(' px')
        form.addRow('Szerokość obrazu PNG', self.image_width)
        path_row = QHBoxLayout()
        self.folder = QLineEdit(str(Path.cwd()))
        browse = QPushButton('Wybierz…')
        browse.clicked.connect(self._browse)
        path_row.addWidget(self.folder, 1)
        path_row.addWidget(browse)
        form.addRow('Katalog docelowy', path_row)
        self.name = QLineEdit()
        form.addRow('Nowy podkatalog', self.name)
        layout.addWidget(self.fields)
        self.note = QLabel('PNG zachowuje bieżący widok, gammę, tryb Klasy/Domeny i warstwy. '
                           'Wycinek jest ten sam dla wybranych klatek w tym układzie współrzędnych. '
                           'Liczniki CSV dotyczą całych klatek. Braki pozostają brakami; eksport nie uruchamia analizy. '
                           'Korekty ręczne nie są oceną trafności modelu. '
                           'Plik .stmdomains służy do zapisania całej pracy z historią.')
        self.note.setWordWrap(True)
        layout.addWidget(self.note)
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setMinimumHeight(self.status.fontMetrics().lineSpacing() * 3)
        layout.addWidget(self.status)
        buttons = QHBoxLayout()
        self.export_button = QPushButton('Eksportuj')
        self.cancel_button = QPushButton('Anuluj eksport')
        self.close_button = QPushButton('Zamknij')
        self.export_button.clicked.connect(self._export)
        self.cancel_button.clicked.connect(self.controller.cancel)
        self.close_button.clicked.connect(self.close)
        for button in (self.export_button, self.cancel_button, self.close_button):
            button.setAutoDefault(False)
            buttons.addWidget(button)
        layout.addLayout(buttons)
        for combo in (self.scope, self.image_scope):
            combo.currentIndexChanged.connect(self._refresh)
        for checkbox in (self.png, self.csv):
            checkbox.toggled.connect(self._refresh)
        self.controller.busy_changed.connect(lambda *_: self._refresh())
        self.controller.export_changed.connect(self._progress)
        self.controller.manual.changed.connect(self._refresh)
        self.selection.currentIndexChanged.connect(self._choose_analysis_scope)

    def prepare(self) -> None:
        controller = self.controller
        controller.pause()
        self.selection.clear()
        self.selection.blockSignals(True)
        for key, label in export_choices(controller):
            self.selection.addItem(label, key)
        self.selection.blockSignals(False)
        count = controller.series.frame_count if controller.series else 1
        for control in (self.first, self.last):
            control.setMaximum(count)
        self._choose_analysis_scope()
        self.name.setText(datetime.now().strftime('eksport-%Y%m%d-%H%M%S'))
        self._refresh()

    def _choose_analysis_scope(self) -> None:
        if self.controller.manual.blocks_export or self.selection.currentData() is None:
            return
        choice = self.selection.currentData()
        snapshot = capture_export(self.controller, choice, {})
        indices = tuple(sorted(set(snapshot.analysis.indices if snapshot.analysis else ()) | set(snapshot.corrections)))
        indices = indices or (self.controller.current_index,)
        self.first.setValue(min(indices) + 1)
        self.last.setValue(max(indices) + 1)
        self.scope.setCurrentIndex(0 if indices == (self.controller.current_index,) else 1)
        self.status.setText(f'{self.selection.currentText()}. Bieżąca klatka: {self.controller.current_index + 1}. '
                           + ('Brak bazowego automatu; dostępne wyłącznie wskazania ręczne.'
                              if snapshot.corrections and snapshot.analysis is None else
                              'Zostanie utworzony nowy podkatalog eksportu.'))

    def _browse(self) -> None:
        path = QFileDialog.getExistingDirectory(self, 'Wybierz katalog na eksport', self.folder.text())
        if path:
            self.folder.setText(path)

    def _refresh(self) -> None:
        ready = self.controller.can_analyze and not self.controller.manual.blocks_export
        if self.controller.manual.blocks_export:
            self.status.setText('Zatwierdź lub anuluj podgląd korekt przed eksportem.')
        self.fields.setEnabled(ready)
        self.first.setEnabled(self.scope.currentData() == 'range')
        self.last.setEnabled(self.scope.currentData() == 'range')
        self.image_scope.setEnabled(self.png.isChecked())
        self.image_width.setEnabled(self.png.isChecked())
        self.export_button.setEnabled(ready and (self.csv.isChecked() or self.png.isChecked()))
        self.cancel_button.setEnabled(self.controller.export_running)

    def _progress(self) -> None:
        self.status.setText(self.controller.export_message)
        self._refresh()

    def _export(self) -> None:
        try:
            name = self.name.text().strip()
            if not name or Path(name).name != name or name in ('.', '..'):
                raise ValueError('Podaj nazwę nowego podkatalogu bez separatorów ścieżki.')
            indices: tuple[int, ...]
            if self.scope.currentData() == 'current':
                indices = (self.controller.current_index,)
            else:
                if self.first.value() > self.last.value():
                    raise ValueError('Pierwsza klatka nie może być późniejsza od ostatniej.')
                indices = tuple(range(self.first.value() - 1, self.last.value()))
            crop = None
            if self.png.isChecked() and self.image_scope.currentData() == 'crop':
                crop = self.main_window.image_view.visible_image_rect()
            options = ExportOptions(self.csv.isChecked(), self.png.isChecked(), crop, self.image_width.value())
            self.controller.start_export(Path(self.folder.text()).expanduser() / name, indices, options,
                                         view=capture_view(self.main_window), selection=self.selection.currentData())
        except ValueError as error:
            self.status.setText(str(error))
