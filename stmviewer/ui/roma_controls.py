"""Explicit process and sampling settings for the separate RoMa environment."""
from pathlib import Path

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox, QFileDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QSpinBox, QVBoxLayout, QWidget,
)

from stmviewer.deep_matcher import DeepMatcherOptions


class RomaControls(QWidget):
    changed = pyqtSignal()

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel('Python środowiska RoMa', self))
        row = QHBoxLayout()
        self._interpreter = QLineEdit(self)
        self._interpreter.setObjectName('romaInterpreter')
        self._interpreter.setAccessibleName('Python środowiska RoMa')
        self._interpreter.setPlaceholderText('netcat-romav2/bin/python lub python.exe')
        row.addWidget(self._interpreter)
        browse = QPushButton('Wybierz…', self)
        browse.setObjectName('chooseRomaInterpreter')
        browse.clicked.connect(self._browse)
        row.addWidget(browse)
        layout.addLayout(row)
        form = QFormLayout()
        self._preset = QComboBox(self)
        self._preset.setObjectName('romaPreset')
        for text, value in (
            ('Turbo — 320 px', 'turbo'), ('Fast — 512 px', 'fast'),
            ('Base — 640 px', 'base'), ('Precise — 1280 px', 'precise'),
        ):
            self._preset.addItem(text, value)
        self._preset.setToolTip('Rozmiar wejścia modelu. Większy wariant wymaga więcej pamięci i czasu.')
        form.addRow('Wariant', self._preset)
        self._samples = QSpinBox(self)
        self._samples.setObjectName('romaSamples')
        self._samples.setRange(8, 10000)
        self._samples.setValue(1000)
        self._samples.setToolTip('Maksymalna liczba próbkowanych korespondencji jednej pary.')
        form.addRow('Limit punktów', self._samples)
        self._seed = QSpinBox(self)
        self._seed.setObjectName('romaSeed')
        self._seed.setRange(0, 2**31 - 1)
        self._seed.setValue(20261102)
        self._seed.setToolTip('Stałe ziarno pozwala powtórzyć losowe próbkowanie przy tej samej konfiguracji.')
        form.addRow('Ziarno losowania', self._seed)
        layout.addLayout(form)
        self._interpreter.textChanged.connect(self.changed)
        self._preset.currentIndexChanged.connect(self.changed)
        self._samples.valueChanged.connect(self.changed)
        self._seed.valueChanged.connect(self.changed)

    @property
    def interpreter(self) -> Path | None:
        value = self._interpreter.text().strip()
        return Path(value).expanduser() if value else None

    @property
    def preset(self) -> str:
        return str(self._preset.currentData())

    @property
    def samples(self) -> int:
        return self._samples.value()

    @property
    def seed(self) -> int:
        return self._seed.value()

    def set_options(self, options: DeepMatcherOptions) -> None:
        self._interpreter.setText(str(options.interpreter) if options.interpreter else '')
        self._preset.setCurrentIndex(self._preset.findData(options.preset))
        self._samples.setValue(options.samples)
        self._seed.setValue(options.seed)

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, 'Python środowiska RoMa', self._interpreter.text(),
                                             'Wszystkie pliki (*)')
        if path:
            self._interpreter.setText(path)
