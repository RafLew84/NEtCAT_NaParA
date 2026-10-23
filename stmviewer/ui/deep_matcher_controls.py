"""File and device inputs; model validation itself runs in the registration worker."""

import os
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QComboBox, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget

from stmviewer.deep_matcher import DeepMatcherOptions


class DeepMatcherControls(QWidget):
    changed = pyqtSignal()
    check_requested = pyqtSignal()

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel('Lokalne wagi LoFTR outdoor', self))
        self._weights = QLineEdit(os.environ.get('STMVIEWER_LOFTR_WEIGHTS', ''), self)
        self._weights.setObjectName('deepWeights')
        self._weights.setPlaceholderText('Ścieżka do pliku .ckpt')
        self._weights.setAccessibleName('Lokalne wagi LoFTR outdoor')
        layout.addWidget(self._weights)
        browse = QPushButton('Wybierz wagi…', self)
        browse.setObjectName('chooseDeepWeights')
        browse.clicked.connect(self._browse)
        layout.addWidget(browse)
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
        self._device.currentIndexChanged.connect(self._changed)
        self._changed()

    def options(self) -> DeepMatcherOptions:
        value = self._weights.text().strip()
        return DeepMatcherOptions(Path(value).expanduser() if value else None, self._device.currentText().lower())

    def set_status(self, text: str) -> None:
        self._status.setText(text)

    def _changed(self) -> None:
        self.set_status('Model niesprawdzony. Sprawdź model lub uruchom Rejestruj.')
        self.changed.emit()

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, 'Lokalne wagi LoFTR outdoor', self._weights.text(),
                                            'Wagi (*.ckpt *.pth *.pt);;Wszystkie pliki (*)')
        if path:
            self._weights.setText(path)
