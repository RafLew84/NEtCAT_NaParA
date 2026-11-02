"""Compose the raw series browser; input parsing lives outside Qt."""

from PyQt6.QtCore import QSignalBlocker, Qt
from PyQt6.QtGui import QCloseEvent, QKeySequence
from PyQt6.QtWidgets import (
    QHBoxLayout, QLabel, QMainWindow, QProgressBar, QPushButton, QSlider, QSpinBox,
    QVBoxLayout, QWidget,
)

from stmdomains.core.series import Series
from stmdomains.ui.image_view import ImageView
from stmdomains.ui.import_prompts import ImportPrompts, QtImportPrompts
from stmdomains.ui.session_controller import PresentedFrame, SessionController


class STMDomainsMainWindow(QMainWindow):
    def __init__(
        self, parent: QWidget | None = None, *, prompts: ImportPrompts | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("STM Domains")
        self.resize(1100, 760)
        self.controller = SessionController(prompts or QtImportPrompts(self), self)
        central = QWidget(self)
        layout = QVBoxLayout(central)
        self.setCentralWidget(central)

        files = QHBoxLayout()
        self.open_button = QPushButton("Otwórz zapis MolTrack…")
        self.open_button.setObjectName("openButton")
        self.open_button.clicked.connect(lambda: self.controller.open_session())
        files.addWidget(self.open_button)
        self.source_label = QLabel("Brak otwartej serii")
        files.addWidget(self.source_label, 1)
        layout.addLayout(files)

        navigation = QHBoxLayout()
        self.previous_button = QPushButton("← Poprzednia")
        self.next_button = QPushButton("Następna →")
        self.frame_number = QSpinBox()
        self.frame_number.setPrefix("Klatka ")
        self.frame_number.setKeyboardTracking(False)
        self.previous_button.clicked.connect(lambda: self.controller.step_frame(-1))
        self.next_button.clicked.connect(lambda: self.controller.step_frame(1))
        self.frame_number.valueChanged.connect(self._select_frame)
        for control in (self.previous_button, self.frame_number, self.next_button):
            control.setEnabled(False)
            navigation.addWidget(control)
        navigation.addStretch()
        self.fit_button = QPushButton("Dopasuj")
        self.zoom_in_button = QPushButton("Powiększ +")
        self.zoom_out_button = QPushButton("Pomniejsz −")
        for button in (self.zoom_out_button, self.zoom_in_button, self.fit_button):
            button.setEnabled(False)
            navigation.addWidget(button)
        layout.addLayout(navigation)

        self.frame_label = QLabel("Wybierz zapis .moltrack.json; obrazy zostaną odczytane z MPP.")
        layout.addWidget(self.frame_label)
        self.image_view = ImageView(self)
        layout.addWidget(self.image_view, 1)
        self.frame_slider = QSlider(Qt.Orientation.Horizontal)
        self.frame_slider.setObjectName("frameSlider")
        self.frame_slider.setAccessibleName("Klatka serii")
        self.frame_slider.setToolTip("Przeciągnij, aby przeglądać klatki")
        self.frame_slider.setRange(1, 1)
        self.frame_slider.setEnabled(False)
        self.frame_slider.setTracking(True)
        self.frame_slider.valueChanged.connect(
            lambda number: self.controller.show_frame(number - 1)
        )
        layout.addWidget(self.frame_slider)
        self.fit_button.clicked.connect(self.image_view.fit_to_window)
        self.zoom_in_button.clicked.connect(lambda: self.image_view.zoom_by(1.25))
        self.zoom_out_button.clicked.connect(lambda: self.image_view.zoom_by(0.8))

        progress = QHBoxLayout()
        self.progress_label = QLabel("Gotowe")
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.hide()
        self.cancel_button = QPushButton("Anuluj")
        self.cancel_button.hide()
        self.cancel_button.clicked.connect(self.controller.cancel)
        progress.addWidget(self.progress_label, 1)
        progress.addWidget(self.progress_bar)
        progress.addWidget(self.cancel_button)
        layout.addLayout(progress)
        self.details_label = QLabel("Oryginał · auto kontrast osobno dla każdej klatki")
        self.details_label.setWordWrap(True)
        layout.addWidget(self.details_label)

        menu_bar = self.menuBar()
        menu = menu_bar.addMenu("&Plik") if menu_bar is not None else None
        if menu is not None:
            open_action = menu.addAction("&Otwórz zapis MolTrack…")
            if open_action is not None:
                open_action.setShortcut(QKeySequence.StandardKey.Open)
                open_action.triggered.connect(lambda: self.controller.open_session())
            close_action = menu.addAction("&Zakończ")
            if close_action is not None:
                close_action.setShortcut(QKeySequence.StandardKey.Quit)
                close_action.triggered.connect(self.close)
        self.controller.series_changed.connect(self._show_series)
        self.controller.frame_changed.connect(self._show_frame)
        self.controller.busy_changed.connect(self._show_progress)

    def _select_frame(self, number: int) -> None:
        # The displayed number changes together with the prepared image.
        with QSignalBlocker(self.frame_number):
            self.frame_number.setValue(self.controller.current_index + 1)
        self.controller.show_frame(number - 1)

    def _show_series(self, series: Series) -> None:
        self.setWindowTitle(f"STM Domains — {series.session_path.name}")
        self.source_label.setText(series.session_path.name)
        self.source_label.setToolTip(f"{series.session_path}\nMPP: {series.source_path}")
        with QSignalBlocker(self.frame_number):
            self.frame_number.setRange(1, series.frame_count)
        self.frame_number.setEnabled(series.frame_count > 1)
        with QSignalBlocker(self.frame_slider):
            self.frame_slider.setRange(1, series.frame_count)
        self.frame_slider.setEnabled(series.frame_count > 1)
        self.details_label.setText(
            "Oryginał · auto kontrast klatki · jednostki obrazu: px\n"
            + "\n".join(series.diagnostics)
        )
        for button in (self.fit_button, self.zoom_in_button, self.zoom_out_button):
            button.setEnabled(True)

    def _show_frame(self, view: PresentedFrame) -> None:
        series = self.controller.series
        if series is None:
            return
        frame = view.frame
        height, width = frame.image.shape
        self.image_view.set_image(view.rendered)
        self.frame_label.setText(
            f"Klatka {frame.working_index + 1} / {series.frame_count} · "
            f"źródłowa {frame.source_index + 1} · {width} × {height} px"
            + (f" · czas {frame.time_s:g} s" if frame.time_s is not None else " · czas nieznany")
        )
        with QSignalBlocker(self.frame_number):
            self.frame_number.setValue(frame.working_index + 1)
        self._sync_frame_slider()
        self.previous_button.setEnabled(frame.working_index > 0)
        self.next_button.setEnabled(frame.working_index < series.frame_count - 1)

    def _show_progress(self, busy: bool, text: str) -> None:
        self.progress_label.setText(text)
        self.progress_bar.setVisible(busy)
        self.cancel_button.setVisible(busy)
        if not busy:
            self._sync_frame_slider()

    def _sync_frame_slider(self) -> None:
        with QSignalBlocker(self.frame_slider):
            self.frame_slider.setValue(self.controller.current_index + 1)

    def closeEvent(self, event: QCloseEvent | None) -> None:
        self.controller.shutdown()
        super().closeEvent(event)
