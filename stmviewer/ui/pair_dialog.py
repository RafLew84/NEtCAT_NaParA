"""Modeless, isolated comparison of adjacent original frames."""

from PyQt6.QtCore import Qt, QSignalBlocker, pyqtSignal
from PyQt6.QtGui import QCloseEvent, QImage
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QSpinBox, QVBoxLayout, QWidget,
)

from stmviewer.deep_matcher import DeepMatcherOptions, deep_unavailable_reason
from stmviewer.frame import ImageFrame
from stmviewer.manual_pair import ManualPairDraft
from stmviewer.ui.manual_pair_controls import ManualPairControls
from stmviewer.pair_comparison import PairImages, PairTrial
from stmviewer.registration import CPU_METHODS, REGISTRATION_METHODS, ShiftBackend, registration_unavailable_reason
from stmviewer.ui.deep_matcher_controls import DeepMatcherControls
from stmviewer.ui.pair_job import PairJob
from stmviewer.ui.image_preview import ImagePreview
from stmviewer.ui.raster import frame_aspect


class PairComparisonDialog(QDialog):
    busy_changed = pyqtSignal()

    def __init__(self, frames: tuple[ImageFrame, ...], moving_index: int, parent: QWidget,
                 *, method: str = 'phase_correlation', deep_options: DeepMatcherOptions | None = None,
                 backend: ShiftBackend | None = None) -> None:
        super().__init__(parent)
        self.setObjectName('pairComparison')
        self.setWindowTitle('Porównanie pary — próba rejestracji')
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.resize(1080, 760)
        self._frames = frames
        self._backend = backend
        self._job: PairJob | None = None
        self._closing = False
        self._available = True
        self._trial: PairTrial | None = None
        self._pinned: PairTrial | None = None
        self._draft: ManualPairDraft | None = None
        self._manual_before_alignment = 0
        self._images: PairImages | None = None
        self._errors = {key: registration_unavailable_reason(key) for key in CPU_METHODS}
        outer = QHBoxLayout(self)
        self._preview = ImagePreview(self)
        self._preview.setObjectName('pairPreview')
        outer.addWidget(self._preview, 1)
        panel = QWidget(self)
        layout = QVBoxLayout(panel)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFixedWidth(340)
        scroll.setWidget(panel)
        outer.addWidget(scroll)
        row = QHBoxLayout()
        row.addWidget(QLabel('Klatka do poprzedniej:', self))
        self._number = QSpinBox(self)
        self._number.setObjectName('pairNumber')
        self._number.setRange(2, len(frames))
        self._number.setValue(moving_index + 1)
        row.addWidget(self._number)
        layout.addLayout(row)
        self._source = QLabel(self)
        self._source.setObjectName('pairSource')
        self._source.setTextFormat(Qt.TextFormat.PlainText)
        self._source.setWordWrap(True)
        layout.addWidget(self._source)
        self._method = QComboBox(self)
        self._method.setObjectName('pairMethod')
        for key, name in REGISTRATION_METHODS.items():
            self._method.addItem(name, key)
        self._method.setCurrentIndex(self._method.findData(method))
        layout.addWidget(self._method)
        self._deep = DeepMatcherControls(self)
        self._deep.check.hide()
        if deep_options is not None:
            self._deep.set_options(deep_options)
        layout.addWidget(self._deep)
        self._availability = QLabel(self)
        self._availability.setObjectName('pairAvailability')
        self._availability.setWordWrap(True)
        self._availability.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self._availability)
        row = QHBoxLayout()
        self._run = QPushButton('Oblicz parę', self)
        self._run.setObjectName('runPair')
        self._run.clicked.connect(self._start)
        row.addWidget(self._run)
        self._cancel = QPushButton('Anuluj próbę', self)
        self._cancel.setObjectName('cancelPair')
        self._cancel.clicked.connect(self._cancel_job)
        row.addWidget(self._cancel)
        layout.addLayout(row)
        self._message = QLabel(self)
        self._message.setObjectName('pairMessage')
        self._message.setWordWrap(True)
        self._message.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self._message)
        self._result = QLabel(self)
        self._result.setObjectName('pairResult')
        self._result.setWordWrap(True)
        self._result.setTextFormat(Qt.TextFormat.PlainText)
        self._result.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self._result)
        row = QHBoxLayout()
        self._trial_choice = QComboBox(self)
        self._trial_choice.setObjectName('pairTrial')
        self._trial_choice.addItem('B — ostatnia', 'B')
        row.addWidget(self._trial_choice)
        self._pin = QPushButton('Przypnij B jako A', self)
        self._pin.setObjectName('pinPair')
        self._pin.clicked.connect(self._pin_trial)
        row.addWidget(self._pin)
        layout.addLayout(row)
        self._alignment = QComboBox(self)
        self._alignment.setObjectName('pairAlignment')
        self._alignment.addItem('Przed dopasowaniem', False)
        self._alignment.addItem('Po dopasowaniu', True)
        layout.addWidget(self._alignment)
        self._layer = QComboBox(self)
        self._layer.setObjectName('pairLayer')
        self._layer.addItem('Odniesienie', 'reference')
        self._layer.addItem('Dopasowywana', 'moving')
        self._layer.addItem('Nakładka 50/50', 'overlay')
        self._layer.setCurrentIndex(2)
        layout.addWidget(self._layer)
        blink = QPushButton('Przełącz obrazy', self)
        blink.setToolTip('Przełącz między odniesieniem a dopasowywaną klatką.')
        blink.setObjectName('pairToggleImage')
        blink.clicked.connect(self._toggle_layer)
        layout.addWidget(blink)
        self._manual = ManualPairControls(self)
        self._manual.start_zero.connect(self._start_manual)
        self._manual.start_copy.connect(lambda: self._start_manual(copy_trial=True))
        self._manual.reset_requested.connect(self._reset_manual)
        self._manual.discarded.connect(self._discard_manual)
        self._manual.nudged.connect(self._nudge_manual)
        self._manual.applied.connect(self._apply_manual)
        layout.addWidget(self._manual)
        row = QHBoxLayout()
        for title, name, callback in (('−', 'pairZoomOut', self._preview.zoom_out),
                                      ('+', 'pairZoomIn', self._preview.zoom_in),
                                      ('Dopasuj', 'pairFit', self._preview.fit_image)):
            button = QPushButton(title, self)
            button.setObjectName(name)
            button.clicked.connect(callback)
            row.addWidget(button)
        layout.addLayout(row)
        row = QHBoxLayout()
        row.addWidget(QLabel('Gamma A/B', self))
        self._gamma = QDoubleSpinBox(self)
        self._gamma.setObjectName('pairGamma')
        self._gamma.setRange(0.1, 4)
        self._gamma.setSingleStep(0.1)
        self._gamma.setValue(1)
        row.addWidget(self._gamma)
        layout.addLayout(row)
        self._pixels = QCheckBox('Proporcje pikselowe A/B', self)
        self._pixels.setObjectName('pairPixelProportions')
        self._pixels.setChecked(True)
        layout.addWidget(self._pixels)
        self._contrast = QLabel(self)
        self._contrast.setObjectName('pairContrast')
        self._contrast.setWordWrap(True)
        layout.addWidget(self._contrast)
        self._overlap = QLabel(self)
        self._overlap.setObjectName('pairOverlap')
        self._overlap.setWordWrap(True)
        layout.addWidget(self._overlap)
        note = QLabel('Kadr: pole źródłowej klatki odniesienia. Część dopasowywanej poza tym polem '
                      'nie jest tu wyświetlana. Białe tło: brak próbek; nakładka obejmuje tylko '
                      'wspólne ważne piksele. Podgląd pary nie zmienia pełnego aligned.', self)
        note.setWordWrap(True)
        layout.addWidget(note)
        layout.addStretch()
        self._number.valueChanged.connect(self._change_pair)
        self._method.currentIndexChanged.connect(self._sync)
        self._deep.changed.connect(self._sync)
        self._trial_choice.currentIndexChanged.connect(self._show_trial)
        self._alignment.currentIndexChanged.connect(self._render)
        self._layer.currentIndexChanged.connect(self._render)
        self._gamma.valueChanged.connect(self._render)
        self._pixels.toggled.connect(self._render)
        self._change_pair()

    @property
    def busy(self) -> bool:
        return self._job is not None

    def set_available(self, available: bool) -> None:
        self._available = available
        self._sync()

    def _change_pair(self) -> None:
        index = self._number.value() - 1
        reference, moving = self._frames[index - 1:index + 1]
        def name(frame: ImageFrame) -> str:
            suffix = f' · MPP {frame.source_frame_index + 1}' if frame.source_frame_index is not None else ''
            return frame.source.name + suffix
        self._source.setText(f'Odniesienie: {name(reference)}\nDopasowywana: {name(moving)}')
        self._trial = None
        self._pinned = None
        self._draft = None
        self._manual.info.setText('Krok: 1 px oryginału · +X w prawo, +Y w dół.')
        with QSignalBlocker(self._trial_choice):
            self._trial_choice.clear()
            self._trial_choice.addItem('B — ostatnia', 'B')
        with QSignalBlocker(self._alignment):
            self._alignment.setCurrentIndex(0)
        self._images = PairImages(reference, moving)
        low, high = self._images.contrast
        self._contrast.setText(f'Stały kontrast A/B z oryginalnej pary:\n{low:g} … {high:g}')
        self._result.setText('Brak wyniku tej pary.')
        self._message.clear()
        self._sync()
        self._render(reset_view=True)

    def _sync(self) -> None:
        method = str(self._method.currentData())
        self._deep.setVisible(method == 'deep_matcher_translation')
        reason = (deep_unavailable_reason(self._deep.options()) if method == 'deep_matcher_translation'
                  else self._errors[method])
        self._availability.setText(reason or '')
        available = self._available and not self.busy
        editing = self._draft is not None
        self._run.setEnabled(available and not editing and reason is None)
        self._cancel.setVisible(self.busy)
        self._pin.setEnabled(available and not editing and self._trial is not None)
        self._trial_choice.setEnabled(available and not editing)
        self._manual.sync(available=available, editing=editing,
                          can_copy=self._selected_trial() is not None)
        for control in (self._method, self._number, self._deep):
            control.setEnabled(self._available and not self.busy)

    def _start_manual(self, *, copy_trial: bool = False) -> None:
        control = self._manual.correct if copy_trial else self._manual.zero
        if not control.isEnabled():
            return
        index = self._number.value() - 1
        self._draft = ManualPairDraft(self._frames[index - 1], self._frames[index],
                                      start=self._selected_trial() if copy_trial else None)
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
        self._manual.info.setText('Krok: 1 px oryginału · +X w prawo, +Y w dół.')
        self._message.setText('Odrzucono edycję. Zapisane próby A/B pozostają bez zmian.')
        self._show_trial()
        self._sync()

    def _show_manual(self) -> None:
        if self._draft is None:
            return
        x, y = self._draft.shift_xy
        sx, sy = self._draft.start_xy
        dx, dy = self._draft.correction_xy
        self._manual.info.setText(f'Szkic: ΔX: {x:g} px · ΔY: {y:g} px\n'
                                 f'Start: ({sx:g}, {sy:g}) px; korekta: ({dx:+d}, {dy:+d}) px\n'
                                 'Krok: 1 px oryginału · +X w prawo, +Y w dół.')
        with QSignalBlocker(self._alignment):
            self._alignment.setCurrentIndex(1)
        self._render()

    def _apply_manual(self) -> None:
        if self._draft is None or not self._manual.apply.isEnabled():
            return
        self._trial = self._draft.apply()
        self._draft = None
        with QSignalBlocker(self._trial_choice):
            self._trial_choice.setCurrentIndex(0)
        self._manual.info.setText('Krok: 1 px oryginału · +X w prawo, +Y w dół.')
        self._message.setText('Zachowano ręczną próbę B. Pełny aligned pozostaje bez zmian.')
        self._show_trial()
        self._sync()

    def _start(self) -> None:
        if not self._run.isEnabled():
            return
        index = self._number.value() - 1
        job = PairJob(self._frames[index - 1], self._frames[index], self,
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
            self._message.setText(f'Niepowodzenie nowej próby: {job.error}\nPoprzedni wynik zachowany.')
        elif job.result is not None:
            self._trial = job.result
            with QSignalBlocker(self._trial_choice):
                self._trial_choice.setCurrentIndex(0)
            with QSignalBlocker(self._alignment):
                self._alignment.setCurrentIndex(1)
            self._show_trial()
            self._message.setText('Próba pary zakończona. Pełny aligned pozostaje bez zmian.')
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
        if self._trial_choice.count() == 1:
            self._trial_choice.addItem('A — przypięta', 'A')
        self._show_trial()

    def _selected_trial(self) -> PairTrial | None:
        return self._pinned if self._trial_choice.currentData() == 'A' else self._trial

    def _show_trial(self) -> None:
        trial = self._selected_trial()
        if trial is None:
            self._result.setText('Brak wyniku tej pary.')
        else:
            quality = ('ustawione ręcznie — jakość nieoceniona' if trial.manual is not None
                       else 'OK backendu (bez niezależnej oceny)' if trial.status == 'ok'
                       else 'Do sprawdzenia')
            self._result.setText(f'{trial.label} · {quality} [{trial.status}]\n'
                                 f'ΔX: {trial.shift_xy[0]:g} px · ΔY: {trial.shift_xy[1]:g} px\n'
                                 'Przesunięcie nakładane na następną klatkę względem poprzedniej.\n'
                                 f'{trial.device}\n{trial.settings_text}')
        self._render()
        self._sync()

    def _toggle_layer(self) -> None:
        self._layer.setCurrentIndex(1 if self._layer.currentIndex() == 0 else 0)

    def _render(self, *, reset_view: bool = False) -> None:
        if self._images is None:
            return
        trial = self._selected_trial()
        shift = (0.0, 0.0)
        if bool(self._alignment.currentData()):
            if self._draft is not None:
                shift = self._draft.shift_xy
            elif trial is not None:
                shift = trial.shift_xy
        try:
            raster = self._images.render(shift, gamma=self._gamma.value(), layer=self._layer.currentData())
            pixels = raster.rgba
            height, width, _ = pixels.shape
            image = QImage(pixels.tobytes(), width, height, pixels.strides[0],
                           QImage.Format.Format_RGBA8888).copy()
            reference = self._frames[self._number.value() - 2]
            aspect = frame_aspect(reference, pixel_proportions=self._pixels.isChecked())
            self._preview.set_image(image, aspect=aspect, reset_view=reset_view)
            text = (f'Wspólne ważne piksele: {raster.overlap_pixels} '
                    f'({raster.overlap_fraction:.1%} pola odniesienia).')
            if not raster.overlap_pixels:
                text += '\nBrak wspólnego ważnego obszaru.'
            if bool(self._alignment.currentData()) and trial is None and self._draft is None:
                text += '\nBrak wyniku — wyświetlane przed dopasowaniem.'
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
