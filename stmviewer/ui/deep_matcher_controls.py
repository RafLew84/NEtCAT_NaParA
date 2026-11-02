"""Local model paths and device inputs shared by pair, film and graph windows."""

import os
from pathlib import Path

from PyQt6.QtCore import QSignalBlocker, Qt, pyqtSignal
from PyQt6.QtWidgets import QComboBox, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget

from stmviewer.deep_matcher import DeepMatcherOptions
from stmviewer.efficient_matcher import EFFICIENT_METHOD, default_efficient_options
from stmviewer.roma_matcher import ROMA_METHOD, default_roma_options
from stmviewer.ui.roma_controls import RomaControls


class DeepMatcherControls(QWidget):
    changed = pyqtSignal()
    check_requested = pyqtSignal()

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self._method = 'deep_matcher_translation'
        self._remembered: dict[str, DeepMatcherOptions] = {
            EFFICIENT_METHOD: default_efficient_options(), ROMA_METHOD: default_roma_options(),
        }
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._weights_label = QLabel('Lokalne wagi LoFTR outdoor', self)
        layout.addWidget(self._weights_label)
        self._weights = QLineEdit(os.environ.get('STMVIEWER_LOFTR_WEIGHTS', ''), self)
        self._weights.setObjectName('deepWeights')
        self._weights.setPlaceholderText('Ścieżka do pliku .ckpt')
        self._weights.setAccessibleName('Lokalne wagi LoFTR outdoor')
        layout.addWidget(self._weights)
        browse = QPushButton('Wybierz wagi…', self)
        browse.setObjectName('chooseDeepWeights')
        browse.clicked.connect(self._browse)
        layout.addWidget(browse)
        self._source_panel = QWidget(self)
        source_layout = QVBoxLayout(self._source_panel)
        source_layout.setContentsMargins(0, 0, 0, 0)
        self._source_label = QLabel('Lokalny katalog kodu EfficientLoFTR', self)
        source_layout.addWidget(self._source_label)
        self._source = QLineEdit(self)
        self._source.setObjectName('efficientSource')
        self._source.setAccessibleName('Lokalny katalog kodu EfficientLoFTR')
        self._source.setPlaceholderText('Katalog zawierający src/loftr')
        source_layout.addWidget(self._source)
        source_browse = QPushButton('Wybierz katalog kodu…', self)
        source_browse.setObjectName('chooseEfficientSource')
        source_browse.clicked.connect(self._browse_source)
        source_layout.addWidget(source_browse)
        layout.addWidget(self._source_panel)
        self._source_panel.hide()
        self._roma = RomaControls(self)
        layout.addWidget(self._roma)
        self._roma.hide()
        self._roma.changed.connect(self._changed)
        row = QHBoxLayout()
        row.addWidget(QLabel('Urządzenie', self))
        self._device = QComboBox(self)
        self._device.setObjectName('deepDevice')
        self._device.addItems(['Auto', 'CPU', 'CUDA'])
        self._device.setToolTip('Auto wybiera CUDA, gdy jest dostępna w Torch. Jawny wybór CUDA nie przełącza na CPU.')
        row.addWidget(self._device)
        layout.addLayout(row)
        self.check = QPushButton('Sprawdź model', self)
        self.check.setObjectName('checkDeepModel')
        self.check.clicked.connect(self.check_requested)
        layout.addWidget(self.check)
        self._status = QLabel(self)
        self._status.setObjectName('deepModelStatus')
        self._status.setWordWrap(True)
        self._status.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self._status)
        self._weights.textChanged.connect(self._changed)
        self._source.textChanged.connect(self._changed)
        self._device.currentIndexChanged.connect(self._changed)
        self._changed()

    def options(self) -> DeepMatcherOptions:
        value = self._weights.text().strip()
        source = self._source.text().strip() if self._method in (EFFICIENT_METHOD, ROMA_METHOD) else ''
        roma = self._method == ROMA_METHOD
        return DeepMatcherOptions(Path(value).expanduser() if value else None,
                                  self._device.currentText().lower(),
                                  Path(source).expanduser() if source else None,
                                  interpreter=self._roma.interpreter if roma else None,
                                  preset=self._roma.preset if roma else 'turbo',
                                  samples=self._roma.samples if roma else 1000,
                                  seed=self._roma.seed if roma else 20261102)

    def set_method(self, method: str) -> None:
        """Remember each model's local files when switching the next calculation."""
        family = method if method in (EFFICIENT_METHOD, ROMA_METHOD) else 'deep'
        previous = self._method if self._method in (EFFICIENT_METHOD, ROMA_METHOD) else 'deep'
        if family != previous:
            self._remembered[previous] = self.options()
            self._method = method
            with QSignalBlocker(self):
                self.set_options(self._remembered.get(family, DeepMatcherOptions()))
        else:
            self._method = method
        efficient, roma = method == EFFICIENT_METHOD, method == ROMA_METHOD
        text = ('Lokalne wagi RoMa v2' if roma else 'Lokalne wagi EfficientLoFTR outdoor'
                if efficient else 'Lokalne wagi LoFTR outdoor')
        self._weights_label.setText(text)
        self._weights.setAccessibleName(text)
        source_text = 'Lokalny katalog kodu DINOv3' if roma else 'Lokalny katalog kodu EfficientLoFTR'
        self._source_label.setText(source_text)
        self._source.setAccessibleName(source_text)
        self._source.setPlaceholderText('Katalog zawierający hubconf.py i dinov3' if roma
                                        else 'Katalog zawierający src/loftr')
        self._source_panel.setVisible(efficient or roma)
        self._roma.setVisible(roma)

    def set_options(self, options: DeepMatcherOptions) -> None:
        with QSignalBlocker(self):
            self._weights.setText(str(options.weights) if options.weights is not None else '')
            self._source.setText(str(options.source) if options.source is not None else '')
            self._device.setCurrentText(options.device.upper() if options.device != 'auto' else 'Auto')
            self._roma.set_options(options)
        self._changed()

    def set_status(self, text: str) -> None:
        self._status.setText(text)

    def _changed(self) -> None:
        self.set_status('Model niesprawdzony. Sprawdź model lub uruchom Rejestruj.')
        self.changed.emit()

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, self._weights_label.text(), self._weights.text(),
                                            'Wagi (*.ckpt *.pth *.pt);;Wszystkie pliki (*)')
        if path:
            self._weights.setText(path)

    def _browse_source(self) -> None:
        path = QFileDialog.getExistingDirectory(self, self._source_label.text(), self._source.text())
        if path:
            self._source.setText(path)
