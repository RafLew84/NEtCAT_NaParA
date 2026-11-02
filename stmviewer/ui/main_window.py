"""Series browsing through the application's public file action."""

from pathlib import Path
from time import perf_counter

from PyQt6.QtCore import QSignalBlocker, Qt, QTimer
from PyQt6.QtGui import QAction, QCloseEvent, QKeySequence, QImage
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QFrame, QHBoxLayout, QLabel, QMainWindow, QMenu, QMenuBar,
    QMessageBox, QProgressBar, QPushButton, QScrollArea, QSlider, QSpinBox, QStatusBar, QVBoxLayout, QWidget,
)

from stmviewer.frame import ImageFrame
from stmviewer.session_state import SessionState, SessionViewState
from stmviewer.ui.session_controls import SessionControls
from stmviewer.ui.graph_controls import GraphControls
from stmviewer.deep_matcher import DeepMatcherOptions
from stmviewer.avi_raster import MoviePresentation
from stmviewer.ui.avi_export_controls import AviExportControls
from stmviewer.mpp_metadata import mpp_sidecar_path
from stmviewer.registration import (
    CPU_METHODS, DEEP_METHODS, REGISTRATION_METHODS, RegistrationResult, ShiftBackend, registration_unavailable_reason,
)
from stmviewer.ui.registration_options import method_unavailable_reason
from stmviewer.ui.registration_info import registration_info, registration_warnings
from stmviewer.ui.deep_matcher_controls import DeepMatcherControls
from stmviewer.ui.registration_job import RegistrationJob
from stmviewer.ui.manual_movie_job import ManualMovieJob
from stmviewer.ui.graph_application_job import GraphApplicationJob
from stmviewer.graph_types import GraphTrial
from stmviewer.pair_comparison import PairTrial
from stmviewer.ui.pair_dialog import PairComparisonDialog
from stmviewer.ui.filmstrip import Filmstrip
from stmviewer.ui.frame_source import frame_source_text, alignment_history_text
from stmviewer.ui.import_job import ImportJob
from stmviewer.ui.mpp_export_job import MppExportJob
from stmviewer.ui.image_preview import ImagePreview


MovieJob = RegistrationJob | ManualMovieJob | GraphApplicationJob


def _value(value: float | None, unit: str) -> str:
    return "nieznane" if value is None else f"{value:g} {unit}"


class STMViewerMainWindow(QMainWindow):
    def __init__(self, parent: QWidget | None = None, *,
                 registration_backend: ShiftBackend | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("STM Viewer")
        self.resize(1100, 760)
        self._frames: tuple[ImageFrame, ...] = ()
        self._index = 0
        self._job: ImportJob | None = None
        self._export_job: MppExportJob | None = None
        self._registration: RegistrationResult | None = None
        self._registration_job: MovieJob | None = None
        self._registration_backend = registration_backend
        self._pair_dialog: PairComparisonDialog | None = None
        self._method_errors = {key: registration_unavailable_reason(key) for key in CPU_METHODS}
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
        self._session = SessionControls(self._session_snapshot, self._restore_session, panel)
        self._session.busy_changed.connect(self._pair_busy_changed)
        controls.addWidget(self._session)
        self._save_button = QPushButton("Zapisz MPP…", panel)
        self._save_button.setObjectName("saveOriginalMpp")
        self._save_button.setToolTip("Zapisz wszystkie pozostałe klatki oraz metadane. W oknie zapisu wybierz original lub aligned.")
        self._save_button.clicked.connect(self.save_mpp)
        controls.addWidget(self._save_button)
        self._export_info = QLabel(panel)
        self._export_info.setObjectName("mppExportInfo")
        self._export_info.setTextFormat(Qt.TextFormat.PlainText)
        self._export_info.setWordWrap(True)
        self._export_info.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        controls.addWidget(self._export_info)
        self._export_progress = QProgressBar(panel)
        self._export_progress.setObjectName("mppExportProgress")
        self._export_progress.hide()
        controls.addWidget(self._export_progress)
        self._export_cancel = QPushButton("Anuluj zapis MPP", panel)
        self._export_cancel.setObjectName("cancelMppExport")
        self._export_cancel.clicked.connect(self._cancel_export)
        self._export_cancel.hide()
        controls.addWidget(self._export_cancel)
        self._avi = AviExportControls(panel)
        self._avi.requested.connect(self.save_avi)
        self._avi.busy_changed.connect(self._avi_busy_changed)
        controls.addWidget(self._avi)
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
        self._view = QComboBox(panel)
        self._view.setObjectName("frameView")
        self._view.addItems(["original", "aligned"])
        self._view.currentTextChanged.connect(self._change_view)
        controls.addWidget(self._view)
        self._method = QComboBox(panel)
        self._method.setObjectName("registrationMethod")
        for key, label in REGISTRATION_METHODS.items():
            self._method.addItem(label, key)
            self._method.setItemData(self._method.count() - 1, self._method_errors.get(key) or
                                     ("Surowe dane; korelacja bez normalizacji fazowej. Pewność niezweryfikowana."
                                      if key == "phase_no_normalization" else "Domyślne ustawienia NanoTrack"),
                                     Qt.ItemDataRole.ToolTipRole)
        self._method.setToolTip("Metoda rejestracji sąsiednich oryginalnych klatek.")
        controls.addWidget(self._method)
        self._method_availability = QLabel(panel)
        self._method_availability.setObjectName("registrationAvailability")
        self._method_availability.setWordWrap(True)
        self._method_availability.setTextFormat(Qt.TextFormat.PlainText)
        controls.addWidget(self._method_availability)
        self._deep_controls = DeepMatcherControls(panel)
        controls.addWidget(self._deep_controls)
        self._deep_controls.changed.connect(self._change_registration_method)
        self._deep_controls.check_requested.connect(lambda: self._start_registration(check_only=True))
        self._method.currentIndexChanged.connect(self._change_registration_method)
        self._register = QPushButton("Rejestruj", panel)
        self._register.setObjectName("registerFrames")
        self._register.clicked.connect(self._start_registration)
        controls.addWidget(self._register)
        self._compare_pair = QPushButton('Porównaj parę…', panel)
        self._compare_pair.setObjectName('comparePair')
        self._compare_pair.clicked.connect(self._open_pair_comparison)
        controls.addWidget(self._compare_pair)
        self._graph = GraphControls(self)
        self._graph.open_button.clicked.connect(lambda: self._graph.open_graph(
            self._frames, self._registration, self._deep_controls.options(),
            method=str(self._method.currentData())
            if self._method.currentData() in ('roma_v2', 'matchanything_eloftr', 'lightglue_superpoint') else None))
        self._graph.busy_changed.connect(self._pair_busy_changed)
        self._graph.movie_apply_requested.connect(self._apply_graph_movie)
        self._graph.movie_restore_requested.connect(self._restore_graph_movie)
        self._graph.movie_cancel_requested.connect(self._cancel_registration)
        controls.addWidget(self._graph.open_button)
        self._registration_text = QLabel("", panel)
        self._registration_text.setObjectName("registrationInfo")
        self._registration_text.setWordWrap(True)
        self._registration_text.setTextFormat(Qt.TextFormat.PlainText)
        controls.addWidget(self._registration_text)
        self._registration_progress = QProgressBar(panel)
        self._registration_progress.setObjectName("registrationProgress")
        self._registration_progress.hide()
        controls.addWidget(self._registration_progress)
        self._registration_cancel = QPushButton("Anuluj rejestrację", panel)
        self._registration_cancel.setObjectName("cancelRegistration")
        self._registration_cancel.clicked.connect(self._cancel_registration)
        self._registration_cancel.hide()
        controls.addWidget(self._registration_cancel)
        controls.addWidget(QLabel("Źródło", panel))
        self._source = QLabel("—", panel)
        self._source.setWordWrap(True)
        self._source.setTextFormat(Qt.TextFormat.PlainText)
        self._source.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        controls.addWidget(self._source)
        self._metadata_note = QLabel(panel)
        self._metadata_note.setObjectName('metadataImportInfo')
        self._metadata_note.setWordWrap(True)
        self._metadata_note.setTextFormat(Qt.TextFormat.PlainText)
        self._metadata_note.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        controls.addWidget(self._metadata_note)
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
        self._delete = QPushButton("Usuń klatkę", central)
        self._delete.setObjectName("deleteFrame")
        self._delete.setToolTip("Usuń bieżącą klatkę z serii. Plik źródłowy pozostaje bez zmian.")
        self._delete.clicked.connect(self._delete_frame)
        playback.addWidget(self._delete)
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
        self._pixel_proportions.toggled.connect(self._show_registration_info)
        self.setCentralWidget(central)
        self._change_registration_method()

        menu_bar = QMenuBar(self)
        self.setMenuBar(menu_bar)
        file_menu = QMenu("&Plik", menu_bar)
        menu_bar.addMenu(file_menu)
        open_action = QAction("&Otwórz STP/S94/MPP…", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self.open_file)
        file_menu.addAction(open_action)
        self._open_action = open_action
        self._session.add_menu_actions(file_menu)
        self._save_action = QAction("Zapisz &MPP…", self)
        self._save_action.setShortcut(QKeySequence.StandardKey.Save)
        self._save_action.triggered.connect(self.save_mpp)
        self._save_action.setEnabled(False)
        file_menu.addAction(self._save_action)
        self._avi_action = QAction('Zapisz AVI…', self)
        self._avi_action.triggered.connect(self.save_avi)
        self._avi_action.setEnabled(False)
        file_menu.addAction(self._avi_action)
        file_menu.addSeparator()
        close_action = QAction("&Zakończ", self)
        close_action.setShortcut(QKeySequence.StandardKey.Quit)
        close_action.triggered.connect(self.close)
        file_menu.addAction(close_action)
        self._status = QStatusBar(self)
        self.setStatusBar(self._status)
        self._status.showMessage("Brak otwartego obrazu")

    @property
    def _processing_series(self) -> bool:
        """Operations that lock series edits and playback, but allow browsing."""
        return (self._registration_job is not None or self._export_job is not None or self._avi.busy
                or self._session.busy or self._graph.busy
                or (self._pair_dialog is not None and self._pair_dialog.busy))

    @property
    def _operation_in_progress(self) -> bool:
        """Import also excludes launching another operation."""
        return self._job is not None or self._processing_series

    def open_file(self) -> None:
        """Choose a complete series; a worker keeps the existing view responsive."""
        if self._operation_in_progress:
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
        self._sync_navigation()

    def _session_snapshot(self) -> SessionState:
        options = self._deep_controls.options()
        return SessionState(self._frames, self._registration, SessionViewState(
            index=self._index, view=self._view.currentText(), gamma=self._gamma.value(),
            pixel_proportions=self._pixel_proportions.isChecked(), fps=int(self._fps.currentText()),
            loop=self._loop.isChecked(), method=str(self._method.currentData()),
            deep_weights=str(options.weights) if options.weights is not None else None,
            deep_device=options.device, deep_source=str(options.source) if options.source else None,
            deep_interpreter=str(options.interpreter) if options.interpreter else None,
            deep_preset=options.preset, deep_samples=options.samples, deep_seed=options.seed,
            navigation=self._preview.navigation_states(),
            roma_options=self._deep_controls.remembered_roma_options(),
            matchanything_options=self._deep_controls.remembered_matchanything_options(),
            deep_extractor_weights=str(options.extractor_weights) if options.extractor_weights else None,
            lightglue_options=self._deep_controls.remembered_lightglue_options()), graph=self._graph.trial)

    def _restore_session(self, state: SessionState, thumbnails: tuple[QImage, ...]) -> None:
        if self._closing:
            return
        display = state.display
        frame = state.frames[display.index]
        aligned = state.registration.frames[display.index] if state.registration is not None and display.view == 'aligned' else None
        self._preview.set_frame(aligned.image if aligned else frame, view=display.view, reset_settings=True,
                                gamma=display.gamma,
                                original_rect=aligned.original_rect if aligned else frame.alignment.original_rect if frame.alignment else None)
        self._pause()
        self._discard_pair_comparison()
        self._frames, self._registration, self._index = state.frames, state.registration, display.index
        self._graph.restore(state.graph)
        self._strip.set_series(state.frames, thumbnails)
        self._show_registration_warnings()
        selection = self._strip.selectionModel()
        assert selection is not None
        selection.currentChanged.connect(lambda current, previous: self._thumbnail_changed(current.row()))
        with QSignalBlocker(self._view), QSignalBlocker(self._method), QSignalBlocker(self._deep_controls):
            self._view.setCurrentText(display.view)
            self._method.setCurrentIndex(self._method.findData(display.method))
            self._deep_controls.set_method(display.method)
            self._deep_controls.set_options(DeepMatcherOptions(Path(display.deep_weights) if display.deep_weights else None,
                                                               display.deep_device,
                                                               Path(display.deep_source) if display.deep_source else None,
                                                               interpreter=Path(display.deep_interpreter) if display.deep_interpreter else None,
                                                               preset=display.deep_preset, samples=display.deep_samples,
                                                               seed=display.deep_seed,
                                                               extractor_weights=Path(display.deep_extractor_weights)
                                                               if display.deep_extractor_weights else None))
            self._deep_controls.restore_roma_options(display.roma_options)
            self._deep_controls.restore_matchanything_options(display.matchanything_options)
            self._deep_controls.restore_lightglue_options(display.lightglue_options)
        with QSignalBlocker(self._gamma):
            self._gamma.setValue(display.gamma)
        self._pixel_proportions.setChecked(display.pixel_proportions)
        self._preview.set_pixel_proportions(display.pixel_proportions)
        self._strip.set_pixel_proportions(display.pixel_proportions)
        if self._fps.findText(str(display.fps)) < 0:
            self._fps.addItem(str(display.fps), display.fps)
        self._fps.setCurrentText(str(display.fps))
        self._loop.setChecked(display.loop)
        self._preview.restore_navigation(display.navigation)
        self._export_info.clear()
        self._avi.clear_message()
        self._change_registration_method()
        self._show_current_frame()

    def save_avi(self) -> None:
        if not self._frames or self._operation_in_progress:
            return
        self._pause()
        self._avi.open_export(self._frames, MoviePresentation(
            gamma=self._gamma.value(), pixel_proportions=self._pixel_proportions.isChecked()),
            int(self._fps.currentText()), self._frames[self._index].source,
            registration=self._registration, current_view=self._view.currentText())

    def _avi_busy_changed(self) -> None:
        self._open_button.setEnabled(not self._avi.busy)
        self._open_action.setEnabled(not self._avi.busy)
        self._sync_navigation()
        if self._closing and not self._avi.busy:
            self.close()

    def save_mpp(self) -> None:
        """Choose input or ready aligned samples, independent of preview settings."""
        if not self._frames or self._operation_in_progress:
            return
        self._pause()
        source = self._frames[self._index].source
        kinds = ['original', 'aligned'] if self._registration is not None else ['original']
        formats = {f"MPP {kind} (*.mpp *.MPP)": kind for kind in kinds}
        kind = 'aligned' if self._view.currentText() == 'aligned' else 'original'
        default = f"MPP {kind} (*.mpp *.MPP)"
        filename, chosen = QFileDialog.getSaveFileName(
            self, "Zapisz całą serię MPP — wybierz original/aligned w typie pliku",
            str(source.with_name(source.stem + f'-{kind}.mpp')), ';;'.join(formats), initialFilter=default,
            options=QFileDialog.Option.DontConfirmOverwrite,
        )
        if not filename:
            return
        kind = formats[chosen or default]
        registration = self._registration if kind == 'aligned' else None
        path = Path(filename)
        if path.suffix.lower() != '.mpp':
            path = path.with_name(path.name + '.mpp')
        sidecar = mpp_sidecar_path(path)
        existing = [p for p in (path, sidecar) if p.exists() or p.is_symlink()]
        if existing:
            confirmation = QMessageBox(self)
            confirmation.setWindowTitle("Zastąpić zapis MPP?")
            confirmation.setIcon(QMessageBox.Icon.Question)
            confirmation.setTextFormat(Qt.TextFormat.PlainText)
            confirmation.setText("Zastąpić istniejące pliki?\n" + "\n".join(map(str, existing)))
            confirmation.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            confirmation.setDefaultButton(QMessageBox.StandardButton.No)
            if confirmation.exec() != QMessageBox.StandardButton.Yes:
                return
        job = MppExportJob(path, self._frames, self, overwrite=bool(existing), registration=registration,
                           wsxm_compatible=True)
        self._export_job = job
        self._export_info.setText(f"Zapis całej serii {kind}…")
        self._export_progress.setRange(0, len(self._frames) + 3)
        self._export_progress.setValue(0)
        self._export_progress.show()
        self._export_cancel.setEnabled(True)
        self._export_cancel.show()
        self._open_button.setEnabled(False)
        self._open_action.setEnabled(False)
        self._sync_navigation()
        job.progress.connect(self._show_export_progress)
        job.finished.connect(self._finish_export)
        job.start()

    def _show_export_progress(self, done: int, total: int, description: str) -> None:
        self._export_progress.setRange(0, total)
        self._export_progress.setValue(done)
        if self._export_cancel.isEnabled():
            self._export_info.setText(description)

    def _cancel_export(self) -> None:
        if self._export_job is not None:
            self._export_job.cancel()
            self._export_cancel.setEnabled(False)
            self._export_info.setText("Anulowanie zapisu po bieżącym kroku…")

    def _finish_export(self) -> None:
        job = self._export_job
        if job is None:
            return
        if job.result is not None:
            self._export_info.setText(f"Zapisano: {job.result.name} i {mpp_sidecar_path(job.result).name}")
        elif job.error is not None:
            self._export_info.setText(f"Nie udało się zapisać MPP. {job.error}")
        else:
            self._export_info.setText("Anulowano zapis MPP; wcześniejsze pliki zachowane.")
        self._export_job = None
        job.deleteLater()
        self._export_progress.hide()
        self._export_cancel.hide()
        self._open_button.setEnabled(True)
        self._open_action.setEnabled(True)
        self._sync_navigation()
        if self._closing:
            self.close()

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
                    first = result.frames[0]
                    self._preview.set_frame(first, reset_settings=True,
                                            original_rect=first.alignment.original_rect if first.alignment else None)
                    self._pause()
                    with QSignalBlocker(self._gamma):
                        self._gamma.setValue(1.0)
                    with QSignalBlocker(self._pixel_proportions):
                        self._pixel_proportions.setChecked(False)
                    self._registration = None
                    self._session.new_series()
                    self._graph.clear()
                    with QSignalBlocker(self._view):
                        self._view.setCurrentText("original")
                    self._export_info.clear()
                    self._avi.clear_message()
                    self._discard_pair_comparison()
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
            self._sync_navigation()
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
        if event is not None and self._operation_in_progress:
            self._closing = True
            self._cancel_import()
            self._cancel_registration()
            self._cancel_export()
            self._avi.cancel()
            self._session.cancel()
            self._graph.cancel()
            self._discard_pair_comparison()
            event.ignore()
            return
        self._discard_pair_comparison()
        self._graph.close_dialog()
        super().closeEvent(event)

    def _sync_navigation(self) -> None:
        count = len(self._frames)
        busy = self._processing_series
        self._session.sync(available=not self._operation_in_progress, has_frames=bool(count))
        self._graph.sync(available=not self._operation_in_progress, has_frames=count > 1)
        self._compare_pair.setEnabled(count > 1 and not self._operation_in_progress)
        if self._pair_dialog is not None:
            self._pair_dialog.set_available(not (self._job is not None or self._registration_job is not None
                                                 or self._export_job is not None or self._avi.busy
                                                 or self._session.busy or self._graph.busy))
        can_save = bool(count) and not self._operation_in_progress
        self._save_button.setEnabled(can_save)
        self._avi.set_available(can_save)
        if hasattr(self, "_avi_action"):
            self._avi_action.setEnabled(can_save)
        if hasattr(self, '_save_action'):
            self._save_action.setEnabled(can_save)
        self._play.setEnabled(count > 1 and not busy)
        self._delete.setEnabled(bool(count) and not busy)
        self._register.setEnabled(bool(count) and not self._operation_in_progress
                                  and not self._selected_method_error())
        self._method.setEnabled(not self._operation_in_progress)
        self._deep_controls.setEnabled(not self._operation_in_progress)
        self._deep_controls.check.setEnabled(not self._operation_in_progress
                                             and not self._selected_method_error())
        self._view.setEnabled(self._registration is not None)
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

    def _delete_frame(self) -> None:
        if not self._frames or self._processing_series:
            return
        self._pause()
        self._discard_pair_comparison()
        removed = self._index
        frames = self._frames[:removed] + self._frames[removed + 1:]
        index = min(removed, len(frames) - 1) if frames else 0
        registration = self._registration.without_frame(removed) if self._registration is not None else None
        if frames:
            if registration is not None and self._view.currentText() == "aligned":
                current = registration.frames[index]
                self._preview.set_frame(current.image, view="aligned", reset_view=False,
                                        original_rect=current.original_rect)
            else:
                frame = frames[index]
                self._preview.set_frame(frame, reset_view=False,
                                        original_rect=frame.alignment.original_rect if frame.alignment else None)
        else:
            self._preview.clear_frame()
            with QSignalBlocker(self._view):
                self._view.setCurrentText("original")
        self._registration = registration
        self._graph.clear()
        self._frames = frames
        self._index = index
        self._strip.remove_frame(removed)
        self._show_current_frame()

    def _pause(self) -> None:
        self._playing = False
        self._play_timer.stop()
        self._play.setText("Play")

    def _toggle_playback(self) -> None:
        if self._playing:
            self._pause()
        elif len(self._frames) > 1 and not self._processing_series:
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
        self._show_preview(index)
        self._index = index
        self._show_current_frame()

    def _show_current_frame(self) -> None:
        self._sync_navigation()
        if not self._frames:
            self._source.setText("—")
            self._metadata_note.clear()
            self._metadata.setText("Brak danych.")
            self._registration_text.setText("")
            self.setWindowTitle("STM Viewer")
            self._status.showMessage("Brak otwartego obrazu")
            return
        frame = self._frames[self._index]
        self._fit_button.setEnabled(True)
        self._source.setText(frame_source_text(frame))
        self._metadata_note.setText(frame.metadata_note or "")
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
        self._status.showMessage(f"Klatka {self._index + 1} z {len(self._frames)} · {self._view.currentText()}")
        self._show_registration_info()


    def _show_preview(self, index: int, *, reset_view: bool = False) -> None:
        if self._view.currentText() == "aligned" and self._registration is not None:
            frame = self._registration.frames[index]
            self._preview.set_frame(frame.image, view="aligned", original_rect=frame.original_rect,
                                    reset_view=reset_view)
        else:
            original = self._frames[index]
            self._preview.set_frame(original, reset_view=reset_view,
                                    original_rect=original.alignment.original_rect if original.alignment else None)

    def _change_view(self) -> None:
        self._pause()
        if self._frames:
            self._show_preview(self._index)
            self._show_current_frame()

    def _open_pair_comparison(self) -> None:
        if len(self._frames) < 2 or self._operation_in_progress:
            return
        self._pause()
        if self._pair_dialog is None:
            dialog = PairComparisonDialog(self._frames, max(1, self._index), self,
                                          method=str(self._method.currentData()),
                                          deep_options=self._deep_controls.options(),
                                          backend=self._registration_backend)
            self._pair_dialog = dialog
            dialog.set_registration(self._registration)
            dialog.movie_apply_requested.connect(self._apply_movie_correction)
            dialog.movie_remove_requested.connect(self._remove_movie_correction)
            dialog.movie_cancel_requested.connect(self._cancel_registration)
            dialog.busy_changed.connect(self._pair_busy_changed)
            dialog.finished.connect(self._pair_closed)
        self._pair_dialog.show()
        self._pair_dialog.raise_()
        self._pair_dialog.activateWindow()

    def _pair_closed(self) -> None:
        self._pair_dialog = None
        self._sync_navigation()

    def _pair_busy_changed(self) -> None:
        self._pause()
        self._open_button.setEnabled(not self._operation_in_progress)
        self._open_action.setEnabled(not self._operation_in_progress)
        self._sync_navigation()
        if self._closing and not self._operation_in_progress:
            self.close()

    def _discard_pair_comparison(self) -> None:
        if self._pair_dialog is not None:
            self._pair_dialog.close()

    def _selected_method_error(self) -> str | None:
        key = str(self._method.currentData())
        return method_unavailable_reason(key, self._deep_controls.options(), self._method_errors)

    def _change_registration_method(self) -> None:
        self._deep_controls.set_method(str(self._method.currentData()))
        self._deep_controls.setVisible(self._method.currentData() in DEEP_METHODS)
        reason = self._selected_method_error()
        self._method_availability.setText(reason or "")
        self._method_availability.setVisible(reason is not None)
        self._sync_navigation()

    def _start_registration(self, *, check_only: bool = False) -> None:
        if ((not self._frames and not check_only) or self._operation_in_progress or self._selected_method_error()):
            return
        job = RegistrationJob(self._frames, self, self._registration_backend,
                              method=str(self._method.currentData()),
                              deep_options=self._deep_controls.options(), check_only=check_only)
        self._start_registration_job(job)

    def _apply_movie_correction(self, trial: PairTrial) -> None:
        if self._registration is not None and not self._operation_in_progress:
            self._start_registration_job(ManualMovieJob(self._registration, self, trial=trial))

    def _remove_movie_correction(self, index: int) -> None:
        if self._registration is not None and not self._operation_in_progress:
            self._start_registration_job(ManualMovieJob(self._registration, self, remove_index=index))

    def _apply_graph_movie(self, graph: GraphTrial, robust_revision: str | None) -> None:
        if not self._operation_in_progress:
            self._start_registration_job(GraphApplicationJob(
                self._frames, self, previous=self._registration, graph=graph, robust_revision=robust_revision))

    def _restore_graph_movie(self) -> None:
        if self._registration is not None and not self._operation_in_progress:
            self._start_registration_job(GraphApplicationJob(self._frames, self, previous=self._registration))

    def _start_registration_job(self, job: MovieJob) -> None:
        self._pause()
        self._registration_job = job
        manual = isinstance(job, ManualMovieJob)
        graph = isinstance(job, GraphApplicationJob)
        self._registration_progress.setRange(0, len(self._frames) * (1 if manual or graph else 2))
        self._registration_progress.setValue(0)
        self._registration_progress.setFormat('Przeliczanie ręcznej korekty filmu…' if manual else 'Przygotowanie…')
        if manual and self._pair_dialog is not None:
            self._pair_dialog.show_movie_progress(0, len(self._frames), 'Przeliczanie filmu…')
        if graph:
            self._graph.show_movie_progress(0, len(self._frames), 'Odtwarzanie filmu z oryginałów…')
        self._registration_progress.show()
        self._registration_cancel.setText('Anuluj zmianę filmu' if graph else 'Anuluj korektę filmu' if manual else 'Anuluj rejestrację')
        self._registration_cancel.setEnabled(True)
        self._registration_cancel.show()
        self._open_button.setEnabled(False)
        self._open_action.setEnabled(False)
        self._sync_navigation()
        job.progress.connect(self._show_registration_progress)
        job.finished.connect(self._finish_registration)
        job.start()

    def _show_registration_progress(self, done: int, total: int, description: str) -> None:
        if isinstance(self._registration_job, ManualMovieJob) and self._pair_dialog is not None:
            self._pair_dialog.show_movie_progress(done, total, description)
        if isinstance(self._registration_job, GraphApplicationJob):
            self._graph.show_movie_progress(done, total, description)
        self._registration_progress.setRange(0, total)
        self._registration_progress.setValue(done)
        if self._registration_cancel.isEnabled():
            self._registration_progress.setFormat(description)

    def _cancel_registration(self) -> None:
        if self._registration_job is not None:
            self._registration_job.cancel()
            if isinstance(self._registration_job, GraphApplicationJob):
                self._graph.movie_cancelling()
            if isinstance(self._registration_job, ManualMovieJob) and self._pair_dialog is not None:
                self._pair_dialog.movie_cancelling()
            self._registration_cancel.setEnabled(False)
            self._registration_progress.setFormat("Anulowanie po bieżącym kroku…")

    def _finish_registration(self) -> None:
        job = self._registration_job
        if job is None:
            return
        try:
            if not job.was_cancelled() and not self._closing:
                if job.error is not None:
                    self._show_registration_error(job.error)
                    if isinstance(job, RegistrationJob) and self._method.currentData() in DEEP_METHODS:
                        self._deep_controls.set_status(f'Niepowodzenie próby: {job.error}')
                elif job.checked_device is not None:
                    self._deep_controls.set_status(f'Sprawdzono model. Urządzenie: {job.checked_device}')
                elif job.result is not None:
                    # Prepare the visible raster before publishing the new complete result.
                    current = job.result.frames[self._index]
                    self._preview.set_frame(current.image, view="aligned", reset_view=True,
                                            original_rect=current.original_rect)
                    self._registration = job.result
                    self._graph.set_registration(job.result)
                    if self._pair_dialog is not None:
                        self._pair_dialog.set_registration(
                            job.result, applied_trial=job.trial if isinstance(job, ManualMovieJob) else None)
                    if job.result.method in (REGISTRATION_METHODS[key] for key in DEEP_METHODS):
                        self._deep_controls.set_status(f'Sprawdzono model. Urządzenie: {job.result.device}')
                    self._show_registration_warnings()
                    with QSignalBlocker(self._view):
                        self._view.setCurrentText("aligned")
        except (OSError, ValueError, OverflowError, MemoryError) as error:
            self._show_registration_error(str(error) or type(error).__name__)
        finally:
            if isinstance(job, (ManualMovieJob, GraphApplicationJob)):
                message = ('Anulowano. Poprzedni film i korekty pozostają.' if job.was_cancelled()
                           else f'Niepowodzenie: {job.error}. Poprzedni film i korekty pozostają.' if job.error
                           else 'Film został przeliczony. Podgląd aligned oraz eksport używają nowego wyniku.'
                           if self._registration is job.result else 'Nie podmieniono wyniku filmu.')
                if isinstance(job, GraphApplicationJob):
                    self._graph.finish_movie_progress(message)
                elif self._pair_dialog is not None:
                    self._pair_dialog.finish_movie_progress(message)
            self._registration_job = None
            job.deleteLater()
            self._registration_progress.hide()
            self._registration_cancel.hide()
            self._registration_cancel.setText('Anuluj rejestrację')
            self._open_button.setEnabled(True)
            self._open_action.setEnabled(True)
            self._show_current_frame()
            if self._closing:
                self.close()

    def _show_registration_error(self, error: str) -> None:
        message = QMessageBox(self)
        message.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        message.setIcon(QMessageBox.Icon.Critical)
        message.setWindowTitle("Nie można zarejestrować serii")
        message.setTextFormat(Qt.TextFormat.PlainText)
        message.setText(error)
        message.open()

    def _show_registration_warnings(self) -> None:
        if self._registration is not None:
            self._strip.set_warnings(registration_warnings(self._registration))

    def _show_registration_info(self) -> None:
        text = (alignment_history_text(self._frames[self._index]) if self._registration is None else
                registration_info(self._registration, self._index, self._pixel_proportions.isChecked()))
        self._registration_text.setText(text)
