"""Modeless pair comparison, with fixed nonadjacent inspection for graph edges."""

from dataclasses import replace

from PyQt6.QtCore import Qt, QSignalBlocker, pyqtSignal
from PyQt6.QtGui import QCloseEvent, QImage
from PyQt6.QtWidgets import (
    QButtonGroup, QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QGroupBox, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QSizePolicy, QSpinBox, QToolButton, QVBoxLayout, QWidget,
)

from stmviewer.ui.registration_options import method_unavailable_reason
from stmviewer.ui.hybrid_details import deep_start_trial, hybrid_details_text
from stmviewer.ui.local_details import LocalDetails, local_overlays, local_start_trial
from stmviewer.local_consensus import LocalDiagnostics
from stmviewer.deep_matcher import DeepMatcherOptions
from stmviewer.frame import ImageFrame
from stmviewer.manual_pair import ManualPairDraft
from stmviewer.manual_movie import movie_pair_trial
from stmviewer.ui.manual_movie_controls import ManualMovieControls
from stmviewer.ui.manual_pair_controls import ManualPairControls
from stmviewer.pair_comparison import PairImages, PairTrial
from stmviewer.registration import CPU_METHODS, DEEP_METHODS, REGISTRATION_METHODS, RegistrationResult, ShiftBackend, registration_unavailable_reason
from stmviewer.ui.deep_matcher_controls import DeepMatcherControls
from stmviewer.ui.pair_job import PairJob
from stmviewer.ui.image_preview import ImagePreview
from stmviewer.ui.raster import frame_aspect


class PairComparisonDialog(QDialog):
    busy_changed = pyqtSignal()
    movie_apply_requested = pyqtSignal(object)
    movie_remove_requested = pyqtSignal(int)
    movie_cancel_requested = pyqtSignal()

    def __init__(self, frames: tuple[ImageFrame, ...], moving_index: int, parent: QWidget,
                 *, method: str = 'phase_correlation', deep_options: DeepMatcherOptions | None = None,
                 backend: ShiftBackend | None = None, reference_index: int | None = None,
                 initial_trial: PairTrial | None = None) -> None:
        if not 1 <= moving_index < len(frames):
            raise ValueError("Nieprawidłowa klatka przesuwana.")
        if reference_index is not None and not 0 <= reference_index < moving_index:
            raise ValueError("Nieprawidłowa klatka bazowa.")
        super().__init__(parent)
        self._fixed_reference = reference_index
        self.setObjectName('pairComparison')
        self.setWindowTitle('Dopasowanie pary klatek')
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.resize(1180, 820)
        self._frames = frames
        self._backend = backend
        self._job: PairJob | None = None
        self._closing = False
        self._available = True
        self._trial: PairTrial | None = None
        self._pinned: PairTrial | None = None
        self._local_failure: LocalDiagnostics | None = None
        self._draft: ManualPairDraft | None = None
        self._manual_before_alignment = 0
        self._registration: RegistrationResult | None = None
        self._published_trial: PairTrial | None = None
        self._draft_movie_revision: str | None = None
        self._images: PairImages | None = None
        self._errors = {key: registration_unavailable_reason(key) for key in CPU_METHODS}
        outer = QVBoxLayout(self)
        header = QHBoxLayout()
        self._source = QLabel(self)
        self._source.setObjectName('pairSource')
        self._source.setTextFormat(Qt.TextFormat.PlainText)
        self._source.setWordWrap(True)
        self._source.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        header.addWidget(self._source, 1)
        header.addWidget(QLabel('Klatka przesuwana:', self))
        self._number = QSpinBox(self)
        self._number.setObjectName('pairNumber')
        self._number.setRange(2, len(frames))
        self._number.setValue(moving_index + 1)
        header.addWidget(self._number)
        outer.addLayout(header)
        body = QHBoxLayout()
        outer.addLayout(body, 1)
        panel = QWidget(self)
        sidebar = QVBoxLayout(panel)
        scroll = QScrollArea(self)
        scroll.setObjectName('pairSidebar')
        scroll.setWidgetResizable(True)
        scroll.setFixedWidth(330)
        scroll.setWidget(panel)
        body.addWidget(scroll)

        comparisons = QGroupBox('Porównaj dopasowania', self)
        choices = QVBoxLayout(comparisons)
        hint = QLabel('Opcjonalnie — zachowaj wynik, aby porównać go z następnym.', self)
        hint.setWordWrap(True)
        choices.addWidget(hint)
        self._choice_group = QButtonGroup(self)
        self._current_choice = QPushButton(self)
        self._current_choice.setObjectName('pairCurrentResult')
        self._saved_choice = QPushButton(self)
        self._saved_choice.setObjectName('pairSavedResult')
        for choice in (self._current_choice, self._saved_choice):
            choice.setCheckable(True)
            choice.setAutoDefault(False)
            choice.setMinimumHeight(76)
            self._choice_group.addButton(choice)
            choice.clicked.connect(self._choose_result)
        self._current_choice.setChecked(True)
        choices.addWidget(self._current_choice)
        self._pin = QPushButton('Zachowaj do porównania', self)
        self._pin.setObjectName('pinPair')
        self._pin.setToolTip('Kopiuje wynik bieżący do zachowanego. Kolejne obliczenie lub korekta go nie zmieni.')
        self._pin.clicked.connect(self._pin_trial)
        choices.addWidget(self._pin)
        choices.addWidget(self._saved_choice)
        self._hybrid_stage = QComboBox(self)
        self._hybrid_stage.setObjectName('pairHybridStage')
        self._hybrid_stage.setAccessibleName('Etap wybranej próby Deep Matcher + ECC')
        self._hybrid_stage.addItems(['Wynik po ECC', 'Start Deep tej próby'])
        self._hybrid_stage.setToolTip('Oba przesunięcia pochodzą z jednego obliczenia. Zachowana próba pozostaje osobno.')
        self._hybrid_stage.currentIndexChanged.connect(self._show_trial)
        choices.addWidget(self._hybrid_stage)
        self._hybrid_details = QLabel(self)
        self._hybrid_details.setObjectName('pairHybridDetails')
        self._hybrid_details.setWordWrap(True)
        self._hybrid_details.setTextFormat(Qt.TextFormat.PlainText)
        self._hybrid_details.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self._hybrid_details.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        choices.addWidget(self._hybrid_details)
        self._failure_view = QCheckBox('Pokaż fragmenty odrzuconej próby', self)
        self._failure_view.setObjectName('pairLocalFailure')
        self._failure_view.toggled.connect(self._show_trial)
        choices.addWidget(self._failure_view)
        self._local_details = LocalDetails(self)
        self._local_details.changed.connect(self._show_trial)
        choices.addWidget(self._local_details)
        self._details_toggle = QToolButton(self)
        self._details_toggle.setObjectName('pairResultDetails')
        self._details_toggle.setText('Szczegóły wybranego wyniku')
        self._details_toggle.setCheckable(True)
        self._details_toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._details_toggle.setArrowType(Qt.ArrowType.RightArrow)
        choices.addWidget(self._details_toggle)
        self._result = QLabel(self)
        self._result.setObjectName('pairResult')
        self._result.setWordWrap(True)
        self._result.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self._result.setTextFormat(Qt.TextFormat.PlainText)
        self._result.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._result.hide()
        self._details_toggle.toggled.connect(self._result.setVisible)
        self._details_toggle.toggled.connect(lambda opened: self._details_toggle.setArrowType(
            Qt.ArrowType.DownArrow if opened else Qt.ArrowType.RightArrow))
        choices.addWidget(self._result)
        sidebar.addWidget(comparisons)

        automatic = QGroupBox('Dopasowanie automatyczne', self)
        auto_layout = QVBoxLayout(automatic)
        self._method = QComboBox(self)
        self._method.setObjectName('pairMethod')
        for key, name in REGISTRATION_METHODS.items():
            self._method.addItem(name, key)
        self._method.setCurrentIndex(self._method.findData(method))
        auto_layout.addWidget(QLabel('Metoda', self))
        auto_layout.addWidget(self._method)
        self._deep = DeepMatcherControls(self)
        self._deep.check.hide()
        if deep_options is not None:
            self._deep.set_options(deep_options)
        auto_layout.addWidget(self._deep)
        self._availability = QLabel(self)
        self._availability.setObjectName('pairAvailability')
        self._availability.setWordWrap(True)
        self._availability.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self._availability.setTextFormat(Qt.TextFormat.PlainText)
        auto_layout.addWidget(self._availability)
        self._run = QPushButton('Dopasuj automatycznie', self)
        self._run.setObjectName('runPair')
        self._run.clicked.connect(self._start)
        auto_layout.addWidget(self._run)
        self._cancel = QPushButton('Przerwij obliczanie', self)
        self._cancel.setObjectName('cancelPair')
        self._cancel.clicked.connect(self._cancel_job)
        auto_layout.addWidget(self._cancel)
        sidebar.addWidget(automatic)
        self._movie = ManualMovieControls(self)
        self._movie.start_requested.connect(self._start_movie_manual)
        self._movie.cancel_requested.connect(self.movie_cancel_requested.emit)
        self._movie.apply_requested.connect(self._apply_to_movie)
        self._movie.remove_requested.connect(
            lambda: self.movie_remove_requested.emit(self._number.value() - 1))
        sidebar.addWidget(self._movie)
        sidebar.addStretch()

        viewer = QVBoxLayout()
        body.addLayout(viewer, 1)
        row = QHBoxLayout()
        self._alignment = QComboBox(self)
        self._alignment.setObjectName('pairAlignment')
        self._alignment.addItem('Bez przesunięcia', False)
        self._alignment.addItem('Z dopasowaniem', True)
        row.addWidget(self._alignment)
        self._layer = QComboBox(self)
        self._layer.setObjectName('pairLayer')
        self._layer.addItem('Klatka bazowa', 'reference')
        self._layer.addItem('Klatka przesuwana', 'moving')
        self._layer.addItem('Nakładka 50/50', 'overlay')
        self._layer.setCurrentIndex(2)
        row.addWidget(self._layer)
        self._blink = QPushButton(self)
        self._blink.setObjectName('pairToggleImage')
        self._blink.clicked.connect(self._toggle_layer)
        row.addWidget(self._blink)
        row.addStretch()
        viewer.addLayout(row)
        self._preview_status = QLabel(self)
        self._preview_status.setObjectName('pairPreviewStatus')
        self._preview_status.setTextFormat(Qt.TextFormat.PlainText)
        viewer.addWidget(self._preview_status)
        self._preview = ImagePreview(self)
        self._preview.setObjectName('pairPreview')
        viewer.addWidget(self._preview, 1)
        row = QHBoxLayout()
        for title, name, callback in (('−', 'pairZoomOut', self._preview.zoom_out),
                                      ('+', 'pairZoomIn', self._preview.zoom_in),
                                      ('Pokaż cały obraz', 'pairFit', self._preview.fit_image)):
            button = QPushButton(title, self)
            button.setObjectName(name)
            if name != 'pairFit':
                button.setFixedWidth(32)
            button.clicked.connect(callback)
            row.addWidget(button)
        row.addStretch()
        row.addWidget(QLabel('Gamma podglądu', self))
        self._gamma = QDoubleSpinBox(self)
        self._gamma.setObjectName('pairGamma')
        self._gamma.setRange(0.1, 4)
        self._gamma.setSingleStep(0.1)
        self._gamma.setValue(1)
        row.addWidget(self._gamma)
        self._pixels = QCheckBox('Proporcje pikselowe', self)
        self._pixels.setObjectName('pairPixelProportions')
        self._pixels.setChecked(True)
        row.addWidget(self._pixels)
        viewer.addLayout(row)
        self._overlap = QLabel(self)
        self._overlap.setObjectName('pairOverlap')
        self._overlap.setWordWrap(True)
        self._overlap.setMinimumHeight(self._overlap.fontMetrics().lineSpacing() * 2)
        self._overlap.setToolTip('Pole klatki bazowej; część przesuwanej poza tym polem nie jest wyświetlana. '
                                 'Białe tło oznacza brak próbek. Pokrycie nie jest oceną jakości dopasowania.')
        viewer.addWidget(self._overlap)
        self._contrast = QLabel(self)
        self._contrast.setObjectName('pairContrast')
        self._contrast.setWordWrap(True)
        viewer.addWidget(self._contrast)
        self._manual = ManualPairControls(self)
        self._manual.start_zero.connect(self._start_manual)
        self._manual.start_copy.connect(lambda: self._start_manual(copy_trial=True))
        self._manual.reset_requested.connect(self._reset_manual)
        self._manual.discarded.connect(self._discard_manual)
        self._manual.nudged.connect(self._nudge_manual)
        self._manual.applied.connect(self._apply_manual)
        viewer.addWidget(self._manual)

        self._message = QLabel(self)
        self._message.setObjectName('pairMessage')
        self._message.setWordWrap(True)
        self._message.setTextFormat(Qt.TextFormat.PlainText)
        self._message.setMinimumHeight(self._message.fontMetrics().lineSpacing() * 2)
        outer.addWidget(self._message)
        note = QLabel('Zakończ korektę tworzy próbę pary. Dopiero Zastosuj do filmu zmienia aligned i eksport. '
                      'Zmiana pary lub zamknięcie okna usuwa próby; zastosowane korekty filmu pozostają.', self)
        note.setObjectName('pairScope')
        note.setWordWrap(True)
        outer.addWidget(note)
        self._number.valueChanged.connect(self._change_pair)
        self._method.currentIndexChanged.connect(self._sync)
        self._deep.changed.connect(self._sync)
        self._alignment.currentIndexChanged.connect(self._render)
        self._layer.currentIndexChanged.connect(self._render)
        self._gamma.valueChanged.connect(self._render)
        self._pixels.toggled.connect(self._render)
        self._change_pair()
        if reference_index is not None:
            note.setText('Podgląd relacji grafu. Korekta tworzy tylko próbę tej pary; '
                         'nie zmienia grafu ani filmu. Zamknięcie okna usuwa lokalne próby pary.')
        if initial_trial is not None:
            reference, moving = frames[self._reference_index], frames[moving_index]
            if ((initial_trial.reference.source, initial_trial.reference.source_frame_index)
                    != (reference.source, reference.source_frame_index)
                    or (initial_trial.moving.source, initial_trial.moving.source_frame_index)
                    != (moving.source, moving.source_frame_index)):
                raise ValueError('Zapisana próba pochodzi z innej pary.')
            self._trial = initial_trial
            with QSignalBlocker(self._alignment):
                self._alignment.setCurrentIndex(1)
            self._show_trial()

    @property
    def _reference_index(self) -> int:
        return self._fixed_reference if self._fixed_reference is not None else self._number.value() - 2

    @property
    def busy(self) -> bool:
        return self._job is not None

    def set_available(self, available: bool) -> None:
        self._available = available
        self._sync()

    def set_registration(self, result: RegistrationResult | None, *,
                         applied_trial: PairTrial | None = None) -> None:
        self._registration = result if self._fixed_reference is None else None
        self._published_trial = applied_trial if self._fixed_reference is None else None
        self._sync()

    def show_movie_progress(self, done: int, total: int, description: str) -> None:
        self._movie.show_progress(done, total, description)

    def finish_movie_progress(self, message: str) -> None:
        self._movie.finish_progress()
        self._message.setText(message)

    def movie_cancelling(self) -> None:
        self._movie.cancelling()

    def _start_movie_manual(self) -> None:
        if not self._movie.start.isEnabled() or self._registration is None:
            return
        index = self._number.value() - 1
        start = movie_pair_trial(self._registration, index)
        with QSignalBlocker(self._failure_view):
            self._failure_view.setChecked(False)
        self._draft = ManualPairDraft(self._frames[self._reference_index], self._frames[index], start=start)
        self._draft_movie_revision = start.movie_revision
        self._manual_before_alignment = self._alignment.currentIndex()
        self._message.clear()
        self._show_manual()
        self._sync()

    def _apply_to_movie(self) -> None:
        trial = self._selected_trial()
        if self._movie.apply.isEnabled() and trial is not None:
            self.movie_apply_requested.emit(trial)

    def _change_pair(self) -> None:
        index = self._number.value() - 1
        reference, moving = self._frames[self._reference_index], self._frames[index]
        def name(frame: ImageFrame) -> str:
            suffix = f' · MPP {frame.source_frame_index + 1}' if frame.source_frame_index is not None else ''
            return frame.source.name + suffix
        self._source.setText(f'Klatka bazowa {self._reference_index + 1}: {name(reference)}\n'
                             f'Klatka przesuwana {index + 1}: {name(moving)}')
        self._trial = None
        self._pinned = None
        self._local_failure = None
        with QSignalBlocker(self._failure_view):
            self._failure_view.setChecked(False)
        self._draft = None
        self._draft_movie_revision = None
        self._manual.show_draft(None)
        self._current_choice.setChecked(True)
        with QSignalBlocker(self._alignment):
            self._alignment.setCurrentIndex(0)
        self._images = PairImages(reference, moving)
        low, high = self._images.contrast
        self._contrast.setText(f'Stały kontrast oryginalnej pary: {low:g} … {high:g}')
        self._result.setText('Brak wyniku tej pary.')
        self._message.clear()
        self._sync()
        self._render(reset_view=True)

    def _sync(self) -> None:
        method = str(self._method.currentData())
        self._deep.setVisible(method in DEEP_METHODS)
        reason = method_unavailable_reason(method, self._deep.options(), self._errors)
        self._availability.setText(reason or '')
        available = self._available and not self.busy
        editing = self._draft is not None
        selected = self._selected_result()
        hybrid = selected.hybrid if selected is not None and not self._failure_view.isChecked() else None
        self._hybrid_stage.setVisible(hybrid is not None)
        self._hybrid_stage.setEnabled(available and not editing)
        self._hybrid_details.setVisible(hybrid is not None)
        self._hybrid_details.setText(hybrid_details_text(hybrid) if hybrid else '')
        self._failure_view.setVisible(self._local_failure is not None)
        self._failure_view.setEnabled(available and not editing)
        details = self._selected_local_details()
        self._local_details.set_details(details)
        self._local_details.stage.setVisible(details is not None and details.final_shift_xy is not None)
        self._local_details.stage.setEnabled(available and not editing)
        self._run.setEnabled(available and not editing and reason is None)
        self._cancel.setVisible(self.busy)
        self._pin.setEnabled(available and not editing and self._trial is not None
                             and not self._failure_view.isChecked())
        for button, title, trial in ((self._current_choice, 'Wynik bieżący', self._trial),
                                     (self._saved_choice, 'Wynik zachowany', self._pinned)):
            description = ('Brak wyniku' if trial is None else
                           f'{trial.label}\nΔX: {trial.shift_xy[0]:g} px · ΔY: {trial.shift_xy[1]:g} px')
            button.setText(f'{title}\n{description}')
            button.setEnabled(available and not editing and trial is not None)
        self._manual.sync(available=available, editing=editing,
                          can_copy=self._selected_trial() is not None)
        self._movie.sync(self._registration, self._frames, self._number.value() - 1,
                         self._selected_trial(), available=available, editing=editing,
                         already_applied=self._selected_trial() is not None
                         and self._selected_trial() is self._published_trial)
        for control in (self._method, self._number, self._deep):
            control.setEnabled(self._available and not self.busy)
        self._number.setEnabled(available and self._fixed_reference is None)
        if self._fixed_reference is not None:
            self._movie.info.setText('Relacja grafu służy do porównania. Jej korekta nie zmienia grafu ani filmu.')

    def _start_manual(self, *, copy_trial: bool = False) -> None:
        control = self._manual.correct if copy_trial else self._manual.zero
        if not control.isEnabled():
            return
        index = self._number.value() - 1
        start = self._selected_trial() if copy_trial else None
        with QSignalBlocker(self._failure_view):
            self._failure_view.setChecked(False)
        self._draft = ManualPairDraft(self._frames[self._reference_index], self._frames[index], start=start)
        # Bind when editing begins, never when an old trial is later published.
        self._draft_movie_revision = start.movie_revision if start is not None else None
        if self._draft_movie_revision is None and self._registration is not None:
            self._draft_movie_revision = self._registration.revision
        self._manual_before_alignment = self._alignment.currentIndex()
        self._message.clear()
        self._show_manual()
        self._sync()

    def _nudge_manual(self, dx: int, dy: int) -> None:
        if self._draft is not None and self._available and not self.busy:
            self._draft.nudge(dx, dy)
            self._show_manual()

    def _reset_manual(self) -> None:
        if self._draft is not None and self._manual.reset.isEnabled():
            self._draft.reset()
            self._show_manual()

    def _discard_manual(self) -> None:
        if self._draft is None or not self._manual.discard.isEnabled():
            return
        self._draft = None
        with QSignalBlocker(self._alignment):
            self._alignment.setCurrentIndex(self._manual_before_alignment)
        self._manual.show_draft(None)
        self._message.setText('Anulowano korektę. Wynik bieżący i zachowany pozostają bez zmian.')
        self._show_trial()
        self._sync()

    def _show_manual(self) -> None:
        if self._draft is None:
            return
        self._manual.show_draft(self._draft)
        with QSignalBlocker(self._alignment):
            self._alignment.setCurrentIndex(1)
        self._render()

    def _apply_manual(self) -> None:
        if self._draft is None or not self._manual.apply.isEnabled():
            return
        self._trial = replace(self._draft.apply(), movie_revision=self._draft_movie_revision)
        self._draft = None
        self._current_choice.setChecked(True)
        self._manual.show_draft(None)
        self._message.setText('Korekta zakończona. Wynik bieżący jest gotowy do porównania; film pozostaje bez zmian.')
        self._show_trial()
        self._sync()

    def _start(self) -> None:
        if not self._run.isEnabled():
            return
        index = self._number.value() - 1
        job = PairJob(self._frames[self._reference_index], self._frames[index], self,
                      method=str(self._method.currentData()), deep_options=self._deep.options(),
                      backend=self._backend)
        self._job = job
        self._message.setText('Obliczanie wyłącznie tej pary…')
        self._cancel.setEnabled(True)
        self._sync()
        self.busy_changed.emit()
        job.progress.connect(self._show_progress)
        job.finished.connect(self._finish)
        job.start()

    def _show_progress(self, text: str) -> None:
        if self._cancel.isEnabled():
            self._message.setText(text)

    def _cancel_job(self) -> None:
        if self._job is not None:
            self._job.cancel()
            self._cancel.setEnabled(False)
            self._message.setText('Anulowanie po bieżącym obliczeniu pary…')

    def _finish(self) -> None:
        job = self._job
        if job is None:
            return
        if job.was_cancelled():
            self._message.setText('Anulowano próbę. Poprzedni wynik zachowany.')
        elif job.error is not None:
            if job.local_failure is not None:
                self._local_failure = job.local_failure
                with QSignalBlocker(self._failure_view):
                    self._failure_view.setChecked(True)
                with QSignalBlocker(self._alignment):
                    self._alignment.setCurrentIndex(1)
                self._show_trial()
            self._message.setText(f'Niepowodzenie nowej próby: {job.error}\nPoprzedni wynik zachowany.')
        elif job.result is not None:
            self._local_failure = None
            with QSignalBlocker(self._failure_view):
                self._failure_view.setChecked(False)
            self._trial = job.result
            with QSignalBlocker(self._local_details.stage):
                self._local_details.stage.setCurrentIndex(0)
            with QSignalBlocker(self._hybrid_stage):
                self._hybrid_stage.setCurrentIndex(0)
            self._current_choice.setChecked(True)
            with QSignalBlocker(self._alignment):
                self._alignment.setCurrentIndex(1)
            self._show_trial()
            self._message.setText('Dopasowanie pary zakończone. Możesz poprawić wynik ręcznie lub zachować go do porównania.')
        self._job = None
        job.deleteLater()
        self._sync()
        self.busy_changed.emit()
        if self._closing:
            self.close()

    def _pin_trial(self) -> None:
        if self._trial is None:
            return
        self._pinned = self._trial
        self._message.setText('Wynik bieżący zachowano do porównania. Kolejne obliczenie lub korekta go nie zmieni.')
        self._show_trial()

    def _choose_result(self) -> None:
        with QSignalBlocker(self._failure_view):
            self._failure_view.setChecked(False)
        self._show_trial()

    def _selected_local_details(self) -> LocalDiagnostics | None:
        if self._failure_view.isChecked():
            return self._local_failure
        trial = self._selected_result()
        return trial.local if trial is not None else None

    def _selected_result(self) -> PairTrial | None:
        return self._pinned if self._saved_choice.isChecked() else self._trial

    def _selected_trial(self) -> PairTrial | None:
        if self._failure_view.isChecked():
            return None
        trial = self._selected_result()
        if trial is not None and trial.hybrid is not None and self._hybrid_stage.currentIndex() == 1:
            return deep_start_trial(trial)
        if trial is not None and trial.local is not None and self._local_details.stage.currentIndex() == 1:
            return local_start_trial(trial)
        return trial

    def _show_trial(self) -> None:
        trial = self._selected_trial()
        if self._failure_view.isChecked():
            self._result.setText('Odmowa lokalnego dopasowania. To diagnostyka, nie nowy wynik pary.')
        elif trial is None:
            self._result.setText('Brak wyniku tej pary.')
        else:
            quality = ('ustawione ręcznie — jakość nieoceniona' if trial.manual is not None
                       else 'Do sprawdzenia — pewność niezweryfikowana' if trial.quality_score is None
                       else 'OK backendu (bez niezależnej oceny)' if trial.status == 'ok'
                       else 'Do sprawdzenia')
            relation = ('Przesunięcie klatki przesuwanej względem wybranej bazowej.'
                        if self._fixed_reference is not None else
                        'Przesunięcie nakładane na następną klatkę względem poprzedniej.')
            self._result.setText(f'{trial.label} · {quality} [{trial.status}]\n'
                                 f'ΔX: {trial.shift_xy[0]:g} px · ΔY: {trial.shift_xy[1]:g} px\n'
                                 f'{relation}\n'
                                 f'{trial.device}\n{trial.settings_text}')
        self._render()
        self._sync()

    def _toggle_layer(self) -> None:
        self._layer.setCurrentIndex(1 if self._layer.currentIndex() == 0 else 0)

    def _render(self, *, reset_view: bool = False) -> None:
        if self._images is None:
            return
        trial = self._selected_trial()
        self._blink.setText('Pokaż klatkę przesuwaną' if self._layer.currentData() == 'reference'
                            else 'Pokaż klatkę bazową')
        if not self._alignment.currentData():
            caption = 'Obrazy bez przesunięcia'
        elif self._draft is not None:
            caption = 'Podgląd ręcznej korekty'
        elif self._failure_view.isChecked():
            caption = 'Diagnostyka odmowy — start Deep, brak nowego wyniku lokalnego'
        elif trial is None:
            caption = 'Brak wyniku — obrazy bez przesunięcia'
        else:
            name = 'Wynik zachowany' if self._saved_choice.isChecked() else 'Wynik bieżący'
            caption = f'{name}: {trial.label}'
        self._preview_status.setText(caption)
        shift = (0.0, 0.0)
        if bool(self._alignment.currentData()):
            if self._draft is not None:
                shift = self._draft.shift_xy
            elif self._failure_view.isChecked() and self._local_failure is not None:
                shift = self._local_failure.deep_shift_xy
            elif trial is not None:
                shift = trial.shift_xy
        try:
            raster = self._images.render(shift, gamma=self._gamma.value(), layer=self._layer.currentData())
            pixels = raster.rgba
            height, width, _ = pixels.shape
            image = QImage(pixels.tobytes(), width, height, pixels.strides[0],
                           QImage.Format.Format_RGBA8888).copy()
            reference = self._frames[self._reference_index]
            aspect = frame_aspect(reference, pixel_proportions=self._pixels.isChecked())
            self._preview.set_image(image, aspect=aspect, reset_view=reset_view)
            details = self._selected_local_details()
            overlays = (local_overlays(details, shift)
                        if details is not None and self._local_details.overlay.isChecked() and self._draft is None
                        else ())
            self._preview.set_overlays(overlays)
            text = (f'Wspólne ważne piksele: {raster.overlap_pixels} '
                    f'({raster.overlap_fraction:.1%} pola klatki bazowej). Pokrycie nie jest oceną jakości.')
            if not raster.overlap_pixels:
                text += '\nBrak wspólnego ważnego obszaru.'
            if (bool(self._alignment.currentData()) and trial is None and self._draft is None
                    and not self._failure_view.isChecked()):
                text += '\nBrak wyniku — obrazy bez przesunięcia.'
            self._overlap.setText(text)
        except (ValueError, MemoryError, OverflowError) as error:
            self._overlap.setText(f'Nie udało się wyświetlić próby: {error}')

    def reject(self) -> None:
        # Escape bypasses closeEvent in QDialog; never destroy a running worker.
        if self.busy:
            self._closing = True
            self._cancel_job()
            return
        super().reject()

    def closeEvent(self, event: QCloseEvent | None) -> None:
        if event is not None and self.busy:
            self._closing = True
            self._cancel_job()
            event.ignore()
            return
        super().closeEvent(event)
