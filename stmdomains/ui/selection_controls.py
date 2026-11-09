"""Synchronized selection tools for the sidebar and modeless class editors."""

from PyQt6.QtCore import QSignalBlocker
from PyQt6.QtWidgets import QComboBox, QFormLayout, QLabel, QPushButton, QSizePolicy, QWidget

from stmdomains.ui.manual_controller import ManualController


class SelectionControls(QWidget):
    def __init__(self, manual: ManualController) -> None:
        super().__init__()
        self.manual = manual
        form = QFormLayout(self)
        form.setContentsMargins(0, 0, 0, 0)
        self.tool, self.mode = QComboBox(), QComboBox()
        for text, key in (('Kliknięcia', 'click'), ('Lasso', 'lasso'), ('Przesuwanie', 'pan')):
            self.tool.addItem(text, key)
        for text, key in (('Dodaj do wyboru', 'add'), ('Odejmij z wyboru', 'subtract'), ('Zastąp wybór', 'replace')):
            self.mode.addItem(text, key)
        self.clear = QPushButton('Wyczyść wybór')
        self.clear.clicked.connect(lambda: manual.select_molecules((), 'replace'))
        self.hint = QLabel('Dodaj do wyboru: zbieraj kliknięcia i obrysy. '
                           'Shift: dodaj · Alt: odejmij · Ctrl: przełącz.')
        self.hint.setWordWrap(True)
        self.hint.setMinimumHeight(self.hint.fontMetrics().lineSpacing() * 3)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        form.addRow('Narzędzie', self.tool)
        form.addRow('Zaznaczanie', self.mode)
        form.addRow(self.clear)
        form.addRow(self.hint)
        self.tool.currentIndexChanged.connect(lambda: manual.set_selection_options(tool=self.tool.currentData()))
        self.mode.currentIndexChanged.connect(lambda: manual.set_selection_options(mode=self.mode.currentData()))
        manual.changed.connect(self.refresh)
        manual.controller.busy_changed.connect(self.refresh)
        self.refresh()

    def refresh(self, *_: object) -> None:
        with QSignalBlocker(self.tool), QSignalBlocker(self.mode):
            self.tool.setCurrentIndex(self.tool.findData(self.manual.selection_tool))
            self.mode.setCurrentIndex(self.mode.findData(self.manual.selection_mode))
        self.setEnabled(self.manual.can_edit)
