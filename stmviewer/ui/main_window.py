"""Single-frame browsing through the application's public file action."""

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import (
    QFileDialog, QHBoxLayout, QLabel, QMainWindow, QMenu, QMenuBar,
    QMessageBox, QPushButton, QStatusBar, QVBoxLayout, QWidget,
)

from stmviewer.frame import ImageFrame
from stmviewer.io import open_stp
from stmviewer.ui.image_preview import ImagePreview


def _value(value: float | None, unit: str) -> str:
    return "nieznane" if value is None else f"{value:g} {unit}"


class STMViewerMainWindow(QMainWindow):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("STM Viewer")
        self.resize(1100, 760)
        self._frame: ImageFrame | None = None

        central = QWidget(self)
        layout = QHBoxLayout(central)
        self._preview = ImagePreview(central)
        layout.addWidget(self._preview, 1)
        panel = QWidget(central)
        panel.setFixedWidth(280)
        controls = QVBoxLayout(panel)
        open_button = QPushButton("Otwórz STP…", panel)
        open_button.setObjectName("openStp")
        open_button.clicked.connect(self.open_file)
        controls.addWidget(open_button)
        controls.addWidget(QLabel("Źródło", panel))
        self._source = QLabel("—", panel)
        self._source.setWordWrap(True)
        self._source.setTextFormat(Qt.TextFormat.PlainText)
        self._source.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        controls.addWidget(self._source)
        controls.addWidget(QLabel("Parametry klatki", panel))
        self._metadata = QLabel("Brak danych.", panel)
        self._metadata.setWordWrap(True)
        self._metadata.setTextFormat(Qt.TextFormat.PlainText)
        self._metadata.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        controls.addWidget(self._metadata)
        controls.addStretch()
        layout.addWidget(panel)
        self.setCentralWidget(central)

        menu_bar = QMenuBar(self)
        self.setMenuBar(menu_bar)
        file_menu = QMenu("&Plik", menu_bar)
        menu_bar.addMenu(file_menu)
        open_action = QAction("&Otwórz STP…", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self.open_file)
        file_menu.addAction(open_action)
        file_menu.addSeparator()
        close_action = QAction("&Zakończ", self)
        close_action.setShortcut(QKeySequence.StandardKey.Quit)
        close_action.triggered.connect(self.close)
        file_menu.addAction(close_action)
        self._status = QStatusBar(self)
        self.setStatusBar(self._status)
        self._status.showMessage("Brak otwartego obrazu")

    def open_file(self) -> None:
        """Choose one file; replace the visible frame only after a successful read."""
        initial = str(self._frame.source.parent) if self._frame else ""
        filename, _ = QFileDialog.getOpenFileName(
            self, "Otwórz obraz STP", initial, "STP (*.stp *.STP)"
        )
        if not filename:
            return
        try:
            frame = open_stp(filename)
            self._preview.set_frame(frame)
        except (OSError, ValueError, OverflowError, MemoryError) as error:
            message = QMessageBox(self)
            message.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
            message.setIcon(QMessageBox.Icon.Critical)
            message.setWindowTitle("Nie można otworzyć STP")
            message.setTextFormat(Qt.TextFormat.PlainText)
            message.setText(f"Nie można otworzyć pliku:\n{Path(filename)}\n\n{error}")
            message.open()
            return
        self._frame = frame
        self._source.setText(str(frame.source))
        height, width = frame.data.shape
        current = frame.setpoint_a * 1e9 if frame.setpoint_a is not None else None
        self._metadata.setText(
            f"Rozmiar: {width} × {height} px\n"
            f"Kanał: {frame.channel or 'nieznany'}\n"
            f"Jednostka sygnału: {frame.signal_unit or 'nieznana'}\n\n"
            f"Pole X: {_value(frame.size_x_nm, 'nm')}\n"
            f"Pole Y: {_value(frame.size_y_nm, 'nm')}\n"
            f"Offset X: {_value(frame.offset_x_nm, 'nm')}\n"
            f"Offset Y: {_value(frame.offset_y_nm, 'nm')}\n\n"
            f"Napięcie: {_value(frame.bias_v, 'V')}\n"
            f"Prąd: {_value(current, 'nA')}\n"
            f"Kąt skanowania: {_value(frame.scan_angle_deg, '°')}"
        )
        self.setWindowTitle(f"{frame.source.name} — STM Viewer")
        self._status.showMessage("Klatka 1 z 1 · original")
