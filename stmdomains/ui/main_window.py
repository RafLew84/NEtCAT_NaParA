"""Initial STM Domains window, ready for the application's first feature."""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence
from PyQt6.QtWidgets import QLabel, QMainWindow, QVBoxLayout, QWidget


class STMDomainsMainWindow(QMainWindow):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("STM Domains")
        self.resize(1100, 760)

        central = QWidget(self)
        layout = QVBoxLayout(central)
        layout.addStretch()
        title = QLabel("Analiza domen molekularnych w obrazach STM")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        empty_state = QLabel("Brak otwartego obrazu.")
        empty_state.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(empty_state)
        layout.addStretch()
        self.setCentralWidget(central)

        file_menu = self.menuBar().addMenu("&Plik")
        close_action = file_menu.addAction("&Zakończ")
        close_action.setShortcut(QKeySequence.StandardKey.Quit)
        close_action.triggered.connect(self.close)
