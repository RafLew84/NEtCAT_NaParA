"""Compact popup for display-only region choices; the image keeps its height."""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox, QLabel, QMenu, QSlider, QToolButton, QVBoxLayout, QWidget, QWidgetAction,
)

from stmdomains.core.analysis_result import FrameAnalysis


class DomainControls(QToolButton):
    layers_changed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setText("Obszary…")
        self.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(self)
        self.setMenu(menu)
        panel = QWidget(menu)
        layout = QVBoxLayout(panel)
        self.fill = QCheckBox("Wypełnienie domen")
        self.outlines = QCheckBox("Obrysy domen")
        self.numbers = QCheckBox("Podpisy klas / domen")
        for checkbox in (self.fill, self.outlines, self.numbers):
            checkbox.setChecked(True)
            checkbox.toggled.connect(self.layers_changed)
            layout.addWidget(checkbox)
        self.opacity_label = QLabel("Krycie wypełnienia: 35%")
        self.opacity = QSlider(Qt.Orientation.Horizontal)
        self.opacity.setRange(0, 100)
        self.opacity.setValue(35)
        self.opacity.setAccessibleName("Krycie wypełnienia domen")
        self.opacity.valueChanged.connect(self._opacity_changed)
        layout.addWidget(self.opacity_label)
        layout.addWidget(self.opacity)
        note = QLabel("Klasy: A, B… · Domeny klasy A: A1, A2…\n"
                      "? — klasa nieustalona. Numery lokalne dla klatki.\n"
                      "Obrys przybliża obszar wsparty molekułami.")
        layout.addWidget(note)
        action = QWidgetAction(menu)
        action.setDefaultWidget(panel)
        menu.addAction(action)
        self.set_available(None, "domains")

    def _opacity_changed(self, value: int) -> None:
        self.opacity_label.setText(f"Krycie wypełnienia: {value}%")
        self.layers_changed.emit()

    def set_available(self, result: FrameAnalysis | None, mode: str) -> None:
        available = (result is not None and result.status == "complete"
                     and result.domain_labels is not None and result.domain_count > 0 and mode != "input")
        self.setEnabled(available)
        self.setToolTip("Wypełnienie, obrysy i podpisy obliczonych domen"
                        if available else "Dostępne dla wyniku z domenami w trybie Domeny lub Klasy")
        menu = self.menu()
        if not available and menu is not None:
            menu.hide()
