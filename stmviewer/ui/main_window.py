"""Series browsing through the application's public file action."""

from time import perf_counter

from PyQt6.QtCore import QSignalBlocker, Qt, QTimer
from PyQt6.QtGui import QAction, QCloseEvent, QKeySequence
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QFrame, QHBoxLayout, QLabel, QMainWindow, QMenu, QMenuBar,
    QMessageBox, QProgressBar, QPushButton, QScrollArea, QSlider, QSpinBox, QStatusBar, QVBoxLayout, QWidget,
)

from stmviewer.frame import ImageFrame
from stmviewer.ui.filmstrip import Filmstrip
from stmviewer.ui.import_job import ImportJob
from stmviewer.ui.image_preview import ImagePreview


def _value(value: float | None, unit: str) -> str:
    return "nieznane" if value is None else f"{value:g} {unit}"


class STMViewerMainWindow(QMainWindow):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("STM Viewer")
        self.resize(1100, 760)
        self._frames: tuple[ImageFrame, ...] = ()
        self._index = 0
        self._job: ImportJob | None = None
        self._closing = False
        self._playing = False
        self._play_timer = QTimer(self)
        self._play_timer.setSingleShot(True)
        self._play_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._play_timer.timeout.connect(self._advance_playback)

        central = QWidget(self)
        outer = QVBoxLayout(central)
        layout = QHBoxLayout()
        outer.addLayout(layout, 1)
        self._preview = ImagePreview(central)
        layout.addWidget(self._preview, 1)
        panel = QWidget(central)
        panel.setFixedWidth(280)
        controls = QVBoxLayout(panel)
        open_button = QPushButton("Otwórz STP/S94/MPP…", panel)
        open_button.setObjectName("openFrames")
        open_button.clicked.connect(self.open_file)
        controls.addWidget(open_button)
        self._open_button = open_button
        self._fit_button = QPushButton("Dopasuj", panel)
        self._fit_button.setObjectName("fitImage")
        self._fit_button.setToolTip("Pokaż cały obraz i wyzeruj przesunięcie.")
        self._fit_button.setEnabled(False)
        self._fit_button.clicked.connect(self._preview.fit_image)
        zoom_layout = QHBoxLayout()
        self._zoom_in = QPushButton("+", panel)
        self._zoom_in.setObjectName("zoomIn")
        self._zoom_in.setToolTip("Przybliż wokół środka podglądu.")
        self._zoom_in.setAccessibleName("Przybliż")
        self._zoom_in.clicked.connect(self._preview.zoom_in)
        self._zoom_out = QPushButton("−", panel)
        self._zoom_out.setObjectName("zoomOut")
        self._zoom_out.setToolTip("Oddal wokół środka podglądu.")
        self._zoom_out.setAccessibleName("Oddal")
        self._zoom_out.clicked.connect(self._preview.zoom_out)
        zoom_layout.addWidget(self._zoom_out)
        zoom_layout.addWidget(self._zoom_in)
        zoom_layout.addWidget(self._fit_button)
        controls.addLayout(zoom_layout)
        gamma_layout = QHBoxLayout()
        gamma_layout.addWidget(QLabel("Gamma", panel))
        self._gamma = QDoubleSpinBox(panel)
        self._gamma.setObjectName("previewGamma")
        self._gamma.setAccessibleName("Gamma podglądu")
        self._gamma.setRange(0.1, 4.0)
        self._gamma.setSingleStep(0.1)
        self._gamma.setValue(1.0)
        self._gamma.valueChanged.connect(self._preview.set_gamma)
        gamma_layout.addWidget(self._gamma)
        self._gamma_reset = QPushButton("Reset gamma", panel)
        self._gamma_reset.setObjectName("resetGamma")
        self._gamma_reset.clicked.connect(lambda: self._gamma.setValue(1.0))
        gamma_layout.addWidget(self._gamma_reset)
        controls.addLayout(gamma_layout)
        self._pixel_proportions = QCheckBox("Proporcje pikselowe", panel)
        self._pixel_proportions.setObjectName("pixelProportions")
        self._pixel_proportions.setToolTip(
            "Pomiń skalę z nagłówka przy wyświetlaniu, np. gdy zawiera wartości zastępcze. "
            "Metadane źródłowe pozostają zachowane."
        )
        self._pixel_proportions.toggled.connect(self._preview.set_pixel_proportions)
        controls.addWidget(self._pixel_proportions)
        controls.addWidget(QLabel("Źródło", panel))
        self._source = QLabel("—", panel)
        self._source.setWordWrap(True)
        self._source.setTextFormat(Qt.TextFormat.PlainText)
        self._source.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        controls.addWidget(self._source)
        controls.addWidget(QLabel("Parametry z pliku", panel))
        self._metadata = QLabel("Brak danych.", panel)
        self._metadata.setWordWrap(True)
        self._metadata.setTextFormat(Qt.TextFormat.PlainText)
        self._metadata.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        controls.addWidget(self._metadata)
        self._import_panel = QWidget(panel)
        import_layout = QVBoxLayout(self._import_panel)
        import_layout.setContentsMargins(0, 0, 0, 0)
        self._progress_text = QLabel(self._import_panel)
        self._progress_text.setWordWrap(True)
        self._progress_text.setTextFormat(Qt.TextFormat.PlainText)
        self._progress = QProgressBar(self._import_panel)
        self._progress.setObjectName("importProgress")
        self._cancel = QPushButton("Anuluj import", self._import_panel)
        self._cancel.setObjectName("cancelImport")
        self._cancel.clicked.connect(self._cancel_import)
        import_layout.addWidget(self._progress_text)
        import_layout.addWidget(self._progress)
        import_layout.addWidget(self._cancel)
        controls.addWidget(self._import_panel)
        self._import_panel.hide()
        controls.addStretch()
        sidebar = QScrollArea(central)
        sidebar.setWidgetResizable(True)
        sidebar.setFrameShape(QFrame.Shape.NoFrame)
        sidebar.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        sidebar.setFixedWidth(300)
        sidebar.setWidget(panel)
        layout.addWidget(sidebar)
        playback = QHBoxLayout()
        self._play = QPushButton("Play", central)
        self._play.setObjectName("playPause")
        self._play.clicked.connect(self._toggle_playback)
        self._fps = QComboBox(central)
        self._fps.setObjectName("playbackFps")
        self._fps.setAccessibleName("Tempo odtwarzania w klatkach na sekundę")
        self._fps.addItems(["1", "2", "5", "10", "20", "30"])
        self._fps.setCurrentText("5")
        self._fps.currentTextChanged.connect(self._change_tempo)
        playback.addWidget(self._play)
        playback.addWidget(QLabel("kl./s", central))
        playback.addWidget(self._fps)
        self._loop = QCheckBox("Pętla", central)
        self._loop.setObjectName("playbackLoop")
        playback.addWidget(self._loop)
        playback.addStretch()
        outer.addLayout(playback)
        navigation = QHBoxLayout()
        self._previous = QPushButton("← Poprzednia", central)
        self._previous.setObjectName("previousFrame")
        self._previous.clicked.connect(lambda: self._select_frame(self._index - 1))
        self._next = QPushButton("Następna →", central)
        self._next.setObjectName("nextFrame")
        self._next.clicked.connect(lambda: self._select_frame(self._index + 1))
        self._slider = QSlider(Qt.Orientation.Horizontal, central)
        self._slider.setObjectName("frameSlider")
        self._slider.setAccessibleName("Wybór klatki")
        self._slider.sliderPressed.connect(self._pause)
        self._slider.valueChanged.connect(lambda value: self._select_frame(value - 1))
        self._number = QSpinBox(central)
        self._number.setObjectName("frameNumber")
        self._number.setAccessibleName("Numer klatki")
        self._number.setKeyboardTracking(False)
        editor = self._number.lineEdit()
        assert editor is not None
        editor.textEdited.connect(self._pause)
        self._number.valueChanged.connect(lambda value: self._select_frame(value - 1))
        self._total = QLabel("z 0", central)
        for control in (self._previous, self._slider, self._number, self._total, self._next):
            navigation.addWidget(control)
        outer.addLayout(navigation)
        self._strip = Filmstrip(central)
        self._strip.pressed.connect(self._pause)
        outer.addWidget(self._strip)
        self._pixel_proportions.toggled.connect(self._strip.set_pixel_proportions)
        self.setCentralWidget(central)
        self._sync_navigation()

        menu_bar = QMenuBar(self)
        self.setMenuBar(menu_bar)
        file_menu = QMenu("&Plik", menu_bar)
        menu_bar.addMenu(file_menu)
        open_action = QAction("&Otwórz STP/S94/MPP…", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self.open_file)
        file_menu.addAction(open_action)
        self._open_action = open_action
        file_menu.addSeparator()
        close_action = QAction("&Zakończ", self)
        close_action.setShortcut(QKeySequence.StandardKey.Quit)
        close_action.triggered.connect(self.close)
        file_menu.addAction(close_action)
        self._status = QStatusBar(self)
        self.setStatusBar(self._status)
        self._status.showMessage("Brak otwartego obrazu")

    def open_file(self) -> None:
        """Choose a complete series; a worker keeps the existing view responsive."""
        if self._job is not None:
            return
        initial = str(self._frames[self._index].source.parent) if self._frames else ""
        filenames, _ = QFileDialog.getOpenFileNames(
            self, "Otwórz serię STP/S94 lub jeden film MPP", initial,
            "STP/S94/MPP (*.stp *.STP *.s94 *.S94 *.mpp *.MPP);;"
            "STP/S94 (*.stp *.STP *.s94 *.S94);;MPP (*.mpp *.MPP);;"
            "STP (*.stp *.STP);;S94 (*.s94 *.S94)"
        )
        if not filenames:
            return
        self._open_button.setEnabled(False)
        self._open_action.setEnabled(False)
        self._cancel.setEnabled(True)
        self._progress.setRange(0, len(filenames) * 2)
        self._progress.setValue(0)
        self._progress_text.setText("Wczytywanie serii…")
        self._import_panel.show()
        self._job = ImportJob(filenames, self)
        self._job.progress.connect(self._show_progress)
        self._job.finished.connect(self._finish_import)
        self._job.start()

    def _show_progress(self, done: int, total: int, description: str) -> None:
        self._progress.setRange(0, total)
        self._progress.setValue(done)
        if self._cancel.isEnabled():
            self._progress_text.setText(description)

    def _cancel_import(self) -> None:
        if self._job is not None:
            self._job.cancel()
            self._cancel.setEnabled(False)
            self._progress_text.setText("Anulowanie po zakończeniu bieżącego odczytu…")

    def _finish_import(self) -> None:
        job = self._job
        if job is None:
            return
        try:
            if not job.was_cancelled() and not self._closing:
                if job.error is not None:
                    self._show_import_error(job.error)
                elif job.result is not None:
                    result = job.result
                    self._preview.set_frame(result.frames[0], reset_settings=True)
                    self._pause()
                    with QSignalBlocker(self._gamma):
                        self._gamma.setValue(1.0)
                    with QSignalBlocker(self._pixel_proportions):
                        self._pixel_proportions.setChecked(False)
                    self._frames = result.frames
                    self._strip.set_series(result.frames, result.thumbnails)
                    selection = self._strip.selectionModel()
                    assert selection is not None
                    selection.currentChanged.connect(
                        lambda current, previous: self._thumbnail_changed(current.row())
                    )
                    self._index = 0
                    self._show_current_frame()
        except (OSError, ValueError, OverflowError, MemoryError) as error:
            self._show_import_error(str(error) or type(error).__name__)
        finally:
            self._job = None
            job.deleteLater()
            self._import_panel.hide()
            self._open_button.setEnabled(True)
            self._open_action.setEnabled(True)
            if self._closing:
                self.close()

    def _show_import_error(self, error: str) -> None:
        message = QMessageBox(self)
        message.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        message.setIcon(QMessageBox.Icon.Critical)
        message.setWindowTitle("Nie można otworzyć serii STP/S94/MPP")
        message.setTextFormat(Qt.TextFormat.PlainText)
        message.setText(error)
        message.open()

    def closeEvent(self, event: QCloseEvent | None) -> None:
        self._pause()
        if event is not None and self._job is not None:
            self._closing = True
            self._cancel_import()
            event.ignore()
            return
        super().closeEvent(event)

    def _sync_navigation(self) -> None:
        count = len(self._frames)
        self._play.setEnabled(count > 1)
        for preview_control in (self._zoom_in, self._zoom_out, self._fit_button, self._gamma,
                                self._gamma_reset, self._pixel_proportions):
            preview_control.setEnabled(bool(count))
        for control in (self._slider, self._number):
            with QSignalBlocker(control):
                control.setRange(1 if count else 0, count)
                control.setValue(self._index + 1 if count else 0)
                control.setEnabled(count > 1)
        self._previous.setEnabled(self._index > 0)
        self._next.setEnabled(self._index < count - 1)
        self._total.setText(f"z {count}")
        self._strip.setEnabled(bool(count))
        if count:
            model = self._strip.model()
            assert model is not None
            index = model.index(self._index, 0)
            # The view needs selectionChanged to repaint the previous highlight.
            self._strip.setCurrentIndex(index)
            self._strip.scrollTo(index)

    def _pause(self) -> None:
        self._playing = False
        self._play_timer.stop()
        self._play.setText("Play")

    def _toggle_playback(self) -> None:
        if self._playing:
            self._pause()
        elif len(self._frames) > 1:
            if self._index == len(self._frames) - 1:
                self._display_frame(0)
                self._preview.repaint()
            self._playing = True
            self._play.setText("Pause")
            self._play_timer.start(round(1000 / int(self._fps.currentText())))

    def _change_tempo(self) -> None:
        if self._playing:
            self._play_timer.start(round(1000 / int(self._fps.currentText())))

    def _advance_playback(self) -> None:
        if not self._playing:
            return
        started = perf_counter()
        next_index = self._index + 1
        if next_index == len(self._frames):
            if not self._loop.isChecked():
                self._pause()
                return
            next_index = 0
        self._display_frame(next_index)
        # Complete this paint before scheduling another frame, even under load.
        self._preview.repaint()
        if self._index == len(self._frames) - 1 and not self._loop.isChecked():
            self._pause()
        else:
            interval = 1000 / int(self._fps.currentText())
            elapsed = (perf_counter() - started) * 1000
            self._play_timer.start(max(1, round(interval - elapsed)))

    def _thumbnail_changed(self, index: int) -> None:
        # Synchronizing the current thumbnail during Play is not a manual choice.
        if index != self._index:
            self._select_frame(index)

    def _select_frame(self, index: int) -> None:
        self._pause()
        self._display_frame(index)

    def _display_frame(self, index: int) -> None:
        if index == self._index or not 0 <= index < len(self._frames):
            return
        frame = self._frames[index]
        self._preview.set_frame(frame, reset_view=False)
        self._index = index
        self._show_current_frame()

    def _show_current_frame(self) -> None:
        frame = self._frames[self._index]
        self._sync_navigation()
        self._fit_button.setEnabled(True)
        source = str(frame.source)
        if frame.source_frame_index is not None:
            source += f"\nKlatka źródłowa MPP: {frame.source_frame_index + 1}"
        self._source.setText(source)
        height, width = frame.data.shape
        current = frame.setpoint_a * 1e9 if frame.setpoint_a is not None else None
        self._metadata.setText(
            f"Rozmiar: {width} × {height} px\n"
            f"Czas pomiaru: {_value(frame.measurement_time_s, 's')}\n"
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
        if frame.measurement_time_raw:
            self._metadata.setText(self._metadata.text() + f"\nZapis czasu: {frame.measurement_time_raw}")
        if frame.calibration_note:
            self._metadata.setText(self._metadata.text() + "\n\n" + frame.calibration_note)
        self.setWindowTitle(f"{frame.source.name} — STM Viewer")
        self._status.showMessage(f"Klatka {self._index + 1} z {len(self._frames)} · original")
