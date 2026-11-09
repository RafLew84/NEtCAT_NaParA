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
from stmdomains.ui.project_selection import analysis_identifier
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
                           'Plik .stmdomains służy do zapisania całej pracy.')
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
        result, run = controller.result, controller.series_run
        if result is not None:
            self.selection.addItem(f'Wyświetlany wynik · {analysis_identifier(result)[:8]}', 'displayed')
        if run and (result is None or analysis_identifier(result) != run.identifier):
            self.selection.addItem(f'Ostatni przebieg · {run.identifier[:8]}', 'latest')
        self.selection.addItem('Tylko oznaczenia wejściowe — bez analizy', 'none')
        count = controller.series.frame_count if controller.series else 1
        for control in (self.first, self.last):
            control.setMaximum(count)
        self._choose_analysis_scope()
        self.name.setText(datetime.now().strftime('eksport-%Y%m%d-%H%M%S'))
        self.status.setText(f'Bieżąca klatka: {controller.current_index + 1}. Zostanie utworzony nowy podkatalog eksportu.')
        self._refresh()

    def _choose_analysis_scope(self) -> None:
        if self.controller.manual.blocks_persistence:
            return
        choice = self.selection.currentData()
        if choice not in ('displayed', 'latest', 'none'):
            return
        analysis = self.controller.project_analysis(choice)
        indices = analysis.indices if analysis else (self.controller.current_index,)
        self.first.setValue(min(indices) + 1)
        self.last.setValue(max(indices) + 1)
        self.scope.setCurrentIndex(0 if indices == (self.controller.current_index,) else 1)

    def _browse(self) -> None:
        path = QFileDialog.getExistingDirectory(self, 'Wybierz katalog na eksport', self.folder.text())
        if path:
            self.folder.setText(path)

    def _refresh(self) -> None:
        ready = self.controller.can_analyze and not self.controller.manual.blocks_persistence
        if self.controller.manual.blocks_persistence:
            self.status.setText('Korekty można zapisać w projekcie. Eksport korekt nie jest jeszcze dostępny.')
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
