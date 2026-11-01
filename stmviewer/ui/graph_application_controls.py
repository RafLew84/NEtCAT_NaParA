"""Explicit graph publication, with source and replacement details before action."""
from pathlib import Path

from PyQt6.QtCore import QSignalBlocker, Qt, pyqtSignal
from PyQt6.QtWidgets import QComboBox, QGroupBox, QLabel, QPlainTextEdit, QProgressBar, QPushButton, QToolButton, QVBoxLayout, QWidget

from stmviewer.frame import ImageFrame
from stmviewer.graph_types import GraphTrial
from stmviewer.registration import RegistrationResult


class GraphApplicationControls(QGroupBox):
    apply_requested = pyqtSignal(object, object)
    restore_requested = pyqtSignal()
    cancel_requested = pyqtSignal()
    variant_selected = pyqtSignal(str)

    def __init__(self, frames: tuple[ImageFrame, ...], parent: QWidget) -> None:
        super().__init__('Aktywny film', parent)
        self._frames = frames
        self._trial: GraphTrial | None = None
        self._registration: RegistrationResult | None = None
        self._available = True
        self._busy = False
        self._apply_reason: str | None = 'Brak kandydata grafu.'
        self._restore_reason: str | None = 'Brak zachowanego wyniku.'
        layout = QVBoxLayout(self)
        self._selection = QComboBox(self)
        self._selection.setObjectName('graphApplicationVariant')
        self._selection.setAccessibleName('Wynik grafu do zastosowania w filmie')
        layout.addWidget(self._selection)
        self._info = QLabel(self)
        self._info.setObjectName('graphApplicationInfo')
        self._info.setWordWrap(True)
        self._info.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self._info)
        self._sources_button = QToolButton(self)
        self._sources_button.setObjectName('graphApplicationSourcesToggle')
        self._sources_button.setText('Pełna kolejność źródeł…')
        self._sources_button.setCheckable(True)
        layout.addWidget(self._sources_button)
        self._sources = QPlainTextEdit(self)
        self._sources.setObjectName('graphApplicationSources')
        self._sources.setReadOnly(True)
        self._sources.setMaximumHeight(100)
        self._sources.hide()
        self._sources_button.toggled.connect(self._sources.setVisible)
        layout.addWidget(self._sources)
        self._apply = QPushButton('Zastosuj wynik do filmu', self)
        self._apply.setObjectName('applyGraphMovie')
        self._apply.clicked.connect(self._request_apply)
        layout.addWidget(self._apply)
        self._previous = QLabel(self)
        self._previous.setObjectName('graphPredecessorInfo')
        self._previous.setWordWrap(True)
        self._previous.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self._previous)
        self._restore = QPushButton('Przywróć zachowany wynik', self)
        self._restore.setObjectName('restoreGraphMovie')
        self._restore.clicked.connect(self.restore_requested)
        layout.addWidget(self._restore)
        self._progress = QProgressBar(self)
        self._progress.setObjectName('graphApplicationProgress')
        self._progress.hide()
        layout.addWidget(self._progress)
        self._cancel = QPushButton('Anuluj zmianę filmu', self)
        self._cancel.setObjectName('cancelGraphApplication')
        self._cancel.clicked.connect(self.cancel_requested)
        self._cancel.hide()
        layout.addWidget(self._cancel)
        self._message = QLabel(self)
        self._message.setObjectName('graphApplicationMessage')
        self._message.setWordWrap(True)
        self._message.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self._message)
        self._selection.currentIndexChanged.connect(self._selection_changed)

    @property
    def busy(self) -> bool:
        return self._busy

    def set_context(self, trial: GraphTrial | None, result: RegistrationResult | None) -> None:
        self._trial, self._registration = trial, result
        selected = self._selection.currentData()
        with QSignalBlocker(self._selection):
            self._selection.clear()
            if trial is not None:
                self._selection.addItem('LS — wspólne XY', 'graph')
                for number, robust in enumerate(trial.robust_trials, 1):
                    self._selection.addItem(f'Huber {number} — próg {robust.config.threshold_px:g} px',
                                            f'huber:{robust.revision}')
                index = self._selection.findData(selected)
                if index >= 0:
                    self._selection.setCurrentIndex(index)
        self._describe()

    def select_variant(self, key: str) -> None:
        index = self._selection.findData(key)
        if index >= 0:
            self._selection.setCurrentIndex(index)

    def set_available(self, available: bool) -> None:
        self._available = available
        self._sync()

    def _selection_changed(self) -> None:
        self._describe()
        self.variant_selected.emit(str(self._selection.currentData()))

    def _describe(self) -> None:
        trial, result = self._trial, self._registration
        self._apply_reason = ('Po usunięciu klatki oblicz nowy graf aktualnej serii. '
                              'Gotowy film nadal można oglądać i eksportować.'
                              if result is not None and not result.corrections_editable else 'Brak kandydata grafu.')
        text = ''
        if trial is not None:
            revision = self._selected_revision()
            robust = next((item for item in trial.robust_trials if item.revision == revision), None)
            solver = trial.solver if robust is None else robust.config.solver
            solver += '' if robust is None else f' · próg {robust.config.threshold_px:g} px'
            sources = '\n'.join(f'{index + 1}: {item.source}'
                                 + (f' · MPP {item.source_frame_index + 1}'
                                    if item.source_frame_index is not None else '')
                                 for index, item in enumerate(trial.sources))
            self._sources.setPlainText(sources)
            files = tuple(dict.fromkeys(item.source for item in trial.sources))
            source_summary = ', '.join(Path(path).name for path in files[:2])
            if len(files) > 2:
                source_summary += f' i {len(files) - 2} innych plików'
            source_indices = [item.source_frame_index + 1 for item in trial.sources
                              if item.source_frame_index is not None]
            if len(files) == 1 and source_indices:
                source_summary += f' · MPP {min(source_indices)}–{max(source_indices)}'
            count = len(result.corrections) if result is not None else 0
            text = (f'Metoda pary: Deep Matcher — translacja bez ECC.\n'
                    f'Model: {Path(trial.config.weights_path).name}\n'
                    f'SHA-256 wag: {trial.config.weights_sha256[:16]}…\n'
                    f'Okno: {trial.config.window} · solver: {solver}\n'
                    f'Źródła: {len(trial.sources)} klatek · {source_summary}\n'
                    f'Ręczne korekty do zastąpienia: {count}.\n'
                    'Dotychczasowy wynik i korekty zostaną zachowane.\n'
                    f'Mosty bez niezależnego obejścia: {len(trial.bridges)}. '
                    'Reszty dotyczą bazy G, nie oceniają dopasowania struktur ani ręcznych zmian.\n')
            if trial.positions is None:
                self._apply_reason = 'Graf rozłączny lub niepełny — brak pełnych wspólnych XY.'
            else:
                from stmviewer.graph_application import graph_application_reason
                self._apply_reason = graph_application_reason(self._frames, trial, robust_revision=revision, check_sources=False)
        self._sources_button.setEnabled(trial is not None)
        self._info.setToolTip('SHA-256 wag: ' + trial.config.weights_sha256 if trial is not None else '')
        self._info.setText(text + (self._apply_reason or 'Wybrany wynik jest kompletny. Zastosowanie odtworzy film z oryginałów.'))
        predecessor = result.predecessor if result is not None else None
        if predecessor is None or result is None:
            self._restore_reason = 'Brak zachowanego wyniku.'
            self._previous.setText(self._restore_reason)
        else:
            from stmviewer.graph_application import restore_movie_reason
            self._restore_reason = restore_movie_reason(self._frames, result, check_sources=False)
            self._previous.setText(f'Zachowany: {predecessor.method} · {predecessor.revision[:8]}\n'
                                   f'Ręczne korekty: {len(predecessor.corrections)}.\n'
                                   + (self._restore_reason or 'Przywrócenie odtworzy bazę, korekty i końcowe XY z oryginałów.'))
        self._sync()

    def _selected_revision(self) -> str | None:
        key = str(self._selection.currentData())
        return key.removeprefix('huber:') if key.startswith('huber:') else None

    def _request_apply(self) -> None:
        if self._apply.isEnabled() and self._trial is not None:
            self.apply_requested.emit(self._trial, self._selected_revision())

    def _sync(self) -> None:
        available = self._available and not self._busy
        self._selection.setEnabled(available and self._trial is not None)
        self._apply.setEnabled(available and self._apply_reason is None)
        self._restore.setEnabled(available and self._restore_reason is None)

    def show_progress(self, done: int, total: int, description: str) -> None:
        if not self._busy:
            self._cancel.setEnabled(True)
        self._busy = True
        self._progress.setRange(0, total)
        self._progress.setValue(done)
        self._progress.setFormat('%v / %m')
        self._progress.show()
        self._cancel.show()
        if self._cancel.isEnabled():
            self._message.setText(description)
        self._sync()

    def cancelling(self) -> None:
        self._cancel.setEnabled(False)
        self._message.setText('Anulowanie po bieżącym kroku… Poprzedni film i korekty pozostają.')

    def finish_progress(self, message: str) -> None:
        self._busy = False
        self._progress.hide()
        self._cancel.hide()
        self._message.setText(message)
        self._sync()
