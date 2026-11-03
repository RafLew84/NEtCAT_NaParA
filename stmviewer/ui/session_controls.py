"""Two session actions with transactional background IO and cancellation."""
from collections.abc import Callable
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction, QImage
from PyQt6.QtWidgets import (
    QFileDialog, QHBoxLayout, QLabel, QMenu, QMessageBox, QProgressBar,
    QPushButton, QVBoxLayout, QWidget,
)

from stmviewer.session_state import SessionState
from stmviewer.ui.session_job import SessionJob


class SessionControls(QWidget):
    busy_changed = pyqtSignal()

    def __init__(self, snapshot: Callable[[], SessionState],
                 restore: Callable[[SessionState, tuple[QImage, ...]], None], parent: QWidget) -> None:
        super().__init__(parent)
        self._snapshot, self._restore = snapshot, restore
        self._job: SessionJob | None = None
        self._available = True
        self._has_frames = False
        self._path: Path | None = None
        self._actions: tuple[QAction, QAction] | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        row = QHBoxLayout()
        self.open_button = QPushButton('Otwórz sesję…', self)
        self.open_button.setObjectName('openSession')
        self.open_button.setToolTip('Przywróć obrazy, aktywny aligned, zastosowane korekty i widok z jednego pliku.')
        self.open_button.clicked.connect(self.open_session)
        self.save_button = QPushButton('Zapisz sesję…', self)
        self.save_button.setObjectName('saveSession')
        self.save_button.setToolTip('Zapisz obrazy i bieżącą pracę. Niezastosowany szkic korekty pary pozostaje poza sesją.')
        self.save_button.clicked.connect(self.save_session)
        row.addWidget(self.open_button)
        row.addWidget(self.save_button)
        layout.addLayout(row)
        self.info = QLabel(self)
        self.info.setObjectName('sessionInfo')
        self.info.setTextFormat(Qt.TextFormat.PlainText)
        self.info.setWordWrap(True)
        self.info.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.info)
        self.progress = QProgressBar(self)
        self.progress.setObjectName('sessionProgress')
        self.progress.hide()
        layout.addWidget(self.progress)
        self.cancel_button = QPushButton('Anuluj zapis/odczyt sesji', self)
        self.cancel_button.setObjectName('cancelSession')
        self.cancel_button.clicked.connect(self.cancel)
        self.cancel_button.hide()
        layout.addWidget(self.cancel_button)
        self.sync(available=True, has_frames=False)

    @property
    def busy(self) -> bool:
        return self._job is not None

    def add_menu_actions(self, menu: QMenu) -> None:
        opening = QAction('Otwórz sesję…', self)
        opening.setShortcut('Ctrl+Shift+O')
        opening.triggered.connect(self.open_session)
        saving = QAction('Zapisz sesję…', self)
        saving.setShortcut('Ctrl+Shift+S')
        saving.triggered.connect(self.save_session)
        menu.addAction(opening)
        menu.addAction(saving)
        self._actions = opening, saving
        self.sync(available=self._available, has_frames=self._has_frames)

    def sync(self, *, available: bool, has_frames: bool) -> None:
        self._available, self._has_frames = available, has_frames
        enabled = available and not self.busy
        self.open_button.setEnabled(enabled)
        self.save_button.setEnabled(enabled and has_frames)
        if self._actions is not None:
            self._actions[0].setEnabled(enabled)
            self._actions[1].setEnabled(enabled and has_frames)

    def new_series(self) -> None:
        self._path = None
        self.info.clear()

    def save_session(self) -> None:
        if not self.save_button.isEnabled():
            return
        path, _ = QFileDialog.getSaveFileName(
            self, 'Zapisz sesję z obrazami', str(self._path or Path('sesja.stmsession')),
            'Sesja STM Viewer (*.stmsession)', options=QFileDialog.Option.DontConfirmOverwrite)
        if not path:
            return
        destination = Path(path)
        if destination.suffix.lower() != '.stmsession':
            destination = destination.with_name(destination.name + '.stmsession')
        if destination.exists() or destination.is_symlink():
            message = QMessageBox(self)
            message.setWindowTitle('Zastąpić sesję?')
            message.setTextFormat(Qt.TextFormat.PlainText)
            message.setText(f'Zastąpić istniejący plik sesji?\n{destination}')
            message.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            message.setDefaultButton(QMessageBox.StandardButton.No)
            if message.exec() != QMessageBox.StandardButton.Yes:
                return
        try:
            snapshot = self._snapshot()
            self._start(SessionJob(destination, self, state=snapshot))
        except (ValueError, MemoryError) as error:
            self.info.setText(f'Nie można zapisać sesji: {error}')

    def open_session(self) -> None:
        if not self.open_button.isEnabled():
            return
        path, _ = QFileDialog.getOpenFileName(self, 'Otwórz sesję z obrazami', str(self._path or ''),
                                             'Sesja STM Viewer (*.stmsession)')
        if path:
            self._start(SessionJob(Path(path), self))

    def _start(self, job: SessionJob) -> None:
        self._job = job
        self.progress.setRange(0, 0)
        self.progress.show()
        self.cancel_button.setEnabled(True)
        self.cancel_button.show()
        self.info.setText('Zapisywanie sesji…' if job.state is not None else 'Otwieranie sesji…')
        self.sync(available=self._available, has_frames=self._has_frames)
        self.busy_changed.emit()
        job.progress.connect(self._progress)
        job.finished.connect(self._finish)
        job.start()

    def _progress(self, done: int, total: int, text: str) -> None:
        self.progress.setRange(0, total)
        self.progress.setValue(done)
        if self.cancel_button.isEnabled():
            self.info.setText(text)

    def cancel(self) -> None:
        if self._job is not None:
            self._job.cancel()
            self.cancel_button.setEnabled(False)
            self.info.setText('Anulowanie po bieżącym kroku…')

    def _finish(self) -> None:
        job = self._job
        if job is None:
            return
        if job.error is not None:
            self.info.setText(f'Operacja sesji nie powiodła się: {job.error}\nDotychczasowa praca pozostaje.')
        elif job.saved is not None:
            self._path = job.saved
            self.info.setText(f'Zapisano sesję: {job.saved.name}')
        elif job.loaded is not None and not job.was_cancelled():
            try:
                self._restore(job.loaded, job.thumbnails)
            except (OSError, ValueError, MemoryError, OverflowError) as error:
                self.info.setText(f'Nie można pokazać sesji: {error}')
            else:
                self._path = job.path
                self.info.setText(f'Otwarto sesję: {job.path.name}')
        else:
            self.info.setText('Anulowano. Dotychczasowa praca i wcześniejszy plik pozostają.')
        self._job = None
        job.deleteLater()
        self.progress.hide()
        self.cancel_button.hide()
        self.busy_changed.emit()
        self.sync(available=self._available, has_frames=self._has_frames)
