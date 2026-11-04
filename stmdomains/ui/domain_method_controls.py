"""Stable comparison strip above the image; selecting never recalculates."""

from PyQt6.QtCore import QSignalBlocker, Qt
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSizePolicy, QWidget

from stmdomains.ui.session_controller import SessionController


class DomainMethodControls(QWidget):
    def __init__(self, controller: SessionController, parent=None):
        super().__init__(parent)
        self.controller = controller
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(QLabel('Wynik:'))
        self.baseline = QPushButton('Bazowa')
        self.geometric = QPushButton('Geometria')
        for button, method in ((self.baseline, 'baseline'), (self.geometric, 'geometry')):
            button.setCheckable(True)
            button.setAutoDefault(False)
            button.clicked.connect(lambda checked, value=method: controller.select_domain_method(value))
            row.addWidget(button)
        self.note = QLabel()
        self.note.setTextFormat(Qt.TextFormat.PlainText)
        self.note.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        row.addWidget(self.note, 1)
        controller.frame_changed.connect(lambda _: self.refresh())
        controller.busy_changed.connect(lambda *_: self.refresh())
        self.refresh()

    def refresh(self):
        controller = self.controller
        for button, method, result in ((self.baseline, 'baseline', controller.baseline_result),
                                        (self.geometric, 'geometry', controller.geometric_result)):
            with QSignalBlocker(button):
                button.setChecked(controller.domain_method == method and result is not None)
            button.setEnabled(controller.can_analyze and result is not None)
            button.setToolTip('Pokaż zachowane przypisania bez przeliczania.' if result else
                              'Brak wyniku tej metody na klatce. Oblicz w oknie Analiza.')
        geometric = controller.domain_method == 'geometry'
        text = 'Eksperymentalna · bez testu fazy · typ nieznany' if geometric else 'Analiza → wybierz metodę i oblicz wynik'
        self.note.setText(text)
        self.note.setToolTip(text)
