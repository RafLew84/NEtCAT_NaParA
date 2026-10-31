"""Explicit publication controls, separate from diagnostic pair editing."""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QGroupBox, QLabel, QProgressBar, QPushButton, QVBoxLayout, QWidget, QSizePolicy

from stmviewer.frame import ImageFrame
from stmviewer.manual_movie import movie_pair_trial
from stmviewer.pair_comparison import PairTrial
from stmviewer.registration import RegistrationResult


class ManualMovieControls(QGroupBox):
    start_requested = pyqtSignal()
    apply_requested = pyqtSignal()
    remove_requested = pyqtSignal()
    cancel_requested = pyqtSignal()

    def __init__(self, parent: QWidget) -> None:
        super().__init__('Korekta całego filmu', parent)
        layout = QVBoxLayout(self)
        self.start = QPushButton('Popraw dopasowanie z filmu', self)
        self.start.setObjectName('manualMovieStart')
        self.apply = QPushButton('Zastosuj do filmu', self)
        self.apply.setObjectName('manualMovieApply')
        self.remove = QPushButton('Usuń korektę tej pary z filmu', self)
        self.remove.setObjectName('manualMovieRemove')
        self.info = QLabel(self)
        self.info.setObjectName('manualMovieInfo')
        self.info.setWordWrap(True)
        self.info.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.info.setTextFormat(Qt.TextFormat.PlainText)
        self.start.clicked.connect(self.start_requested.emit)
        self.apply.clicked.connect(self.apply_requested.emit)
        self.remove.clicked.connect(self.remove_requested.emit)
        for control in (self.start, self.info, self.apply, self.remove):
            layout.addWidget(control)
        self.progress = QProgressBar(self)
        self.progress.setObjectName('manualMovieProgress')
        self.progress.hide()
        layout.addWidget(self.progress)
        self.cancel = QPushButton('Anuluj korektę filmu', self)
        self.cancel.setObjectName('cancelManualMovie')
        self.cancel.clicked.connect(self.cancel_requested.emit)
        self.cancel.hide()
        layout.addWidget(self.cancel)

    def show_progress(self, done: int, total: int, description: str) -> None:
        starting = not self.progress.isVisible()
        self.progress.setRange(0, total)
        self.progress.setValue(done)
        self.progress.setFormat('%v / %m')
        self.progress.setToolTip(description)
        self.progress.show()
        self.cancel.show()
        if starting:
            self.cancel.setEnabled(True)

    def finish_progress(self) -> None:
        self.progress.hide()
        self.cancel.hide()

    def cancelling(self) -> None:
        self.cancel.setEnabled(False)
        self.progress.setFormat('Anulowanie…')

    def sync(self, result: RegistrationResult | None, frames: tuple[ImageFrame, ...],
             index: int, trial: PairTrial | None, *, available: bool, editing: bool,
             already_applied: bool = False) -> None:
        for control in (self.start, self.apply, self.remove):
            control.setEnabled(False)
        if result is None:
            self.info.setText('Najpierw wykonaj pełną rejestrację filmu w głównym oknie.')
            return
        if not result.corrections_editable:
            self.info.setText('Po usunięciu klatki wykonaj nową pełną rejestrację przed dalszą korektą filmu. '
                              'Gotowy aligned można nadal oglądać i eksportować.')
            return
        if len(result.frames) != len(frames) or any(a.original is not f for a, f in zip(result.frames, frames)):
            self.info.setText('Film pochodzi z innej serii. Wykonaj nową pełną rejestrację.')
            return
        try:
            current = movie_pair_trial(result, index)
        except ValueError as error:
            self.info.setText(str(error))
            return
        enabled = available and not editing
        self.start.setEnabled(enabled)
        override = any(c.reference.source == str(current.reference.source)
                       and c.reference.source_frame_index == current.reference.source_frame_index
                       and c.moving.source == str(current.moving.source)
                       and c.moving.source_frame_index == current.moving.source_frame_index
                       for c in result.corrections)
        self.remove.setEnabled(enabled and override)
        def source(frame: ImageFrame) -> str:
            index_text = f' · MPP {frame.source_frame_index + 1}' if frame.source_frame_index is not None else ''
            return frame.source.name + index_text
        text = (f'{source(frames[index - 1])} → {source(frames[index])}\n'
                f'W filmie: XY ({current.shift_xy[0]:g}, {current.shift_xy[1]:g}) px.\n'
                f'Zmiana obejmie klatki {index + 1}–{len(frames)}.\n')
        if trial is None or trial.manual is None:
            text += 'Rozpocznij i zakończ ręczną korektę, aby zastosować ją do filmu.'
        elif already_applied:
            text += 'Ta korekta została zastosowana do filmu.'
        elif (trial.movie_revision != result.revision
              or (trial.reference, trial.moving) != (current.reference, current.moving)):
            text += 'Ta próba nie dotyczy aktualnego wyniku filmu. Rozpocznij nową korektę.'
        elif trial.shift_xy == current.shift_xy:
            text += 'Film ma już to przesunięcie; nie ma zmiany do zastosowania.'
        else:
            text += f'Po korekcie: XY ({trial.shift_xy[0]:g}, {trial.shift_xy[1]:g}) px.'
            self.apply.setEnabled(enabled)
        self.info.setText(text)
