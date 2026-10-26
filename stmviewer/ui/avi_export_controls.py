"""AVI file choice and worker lifecycle; the main window owns series locking."""
from pathlib import Path
from threading import Event

from PyQt6.QtCore import QObject, QThread, Qt, pyqtSignal
from PyQt6.QtWidgets import QFileDialog, QLabel, QMessageBox, QProgressBar, QPushButton, QVBoxLayout, QWidget

from stmviewer.avi_export import AviCancelled, AviPlan, save_avi
from stmviewer.avi_raster import MoviePresentation
from stmviewer.frame import ImageFrame
from stmviewer.registration import RegistrationResult
from stmviewer.ui.avi_dialog import AviDialog


class AviExportJob(QThread):
    progress = pyqtSignal(int, int, str)

    def __init__(self, path: Path, plan: AviPlan, overwrite: bool, parent: QObject) -> None:
        super().__init__(parent)
        self._path, self._plan, self._overwrite = path, plan, overwrite
        self._cancelled = Event()
        self.result: Path | None = None
        self.error: str | None = None

    def cancel(self) -> None:
        self._cancelled.set()

    def run(self) -> None:
        try:
            self.result = save_avi(self._path, self._plan, overwrite=self._overwrite,
                                   progress=self.progress.emit, cancelled=self._cancelled.is_set)
        except AviCancelled:
            pass
        except Exception as error:
            # Thread boundary: report filesystem, codec and allocation failures.
            self.error = str(error) or type(error).__name__


class AviExportControls(QWidget):
    requested = pyqtSignal()
    busy_changed = pyqtSignal()

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self._job: AviExportJob | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._save = QPushButton('Zapisz AVI…', self)
        self._save.setObjectName('saveAvi')
        self._save.clicked.connect(self.requested)
        layout.addWidget(self._save)
        self._info = QLabel(self)
        self._info.setObjectName('aviExportInfo')
        self._info.setTextFormat(Qt.TextFormat.PlainText)
        self._info.setWordWrap(True)
        self._info.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self._info)
        self._progress = QProgressBar(self)
        self._progress.setObjectName('aviExportProgress')
        self._progress.hide()
        layout.addWidget(self._progress)
        self._cancel = QPushButton('Anuluj zapis AVI', self)
        self._cancel.setObjectName('cancelAviExport')
        self._cancel.clicked.connect(self.cancel)
        self._cancel.hide()
        layout.addWidget(self._cancel)

    @property
    def busy(self) -> bool:
        return self._job is not None

    def set_available(self, available: bool) -> None:
        self._save.setEnabled(available)

    def clear_message(self) -> None:
        self._info.clear()

    def open_export(self, frames: tuple[ImageFrame, ...], presentation: MoviePresentation,
                    fps: int, source: Path, *, registration: RegistrationResult | None = None,
                    current_view: str = 'original') -> None:
        dialog = AviDialog(frames, presentation, fps, self,
                           registration=registration, current_view=current_view)
        accepted = dialog.exec()
        plan, version = dialog.plan, dialog.version
        dialog.deleteLater()
        if not accepted or plan is None:
            return
        filename, _ = QFileDialog.getSaveFileName(
            self, f'Zapisz AVI {version}', str(source.with_name(f'{source.stem}-{version}.avi')),
            'AVI (*.avi *.AVI)', options=QFileDialog.Option.DontConfirmOverwrite)
        if not filename:
            return
        path = Path(filename)
        if path.suffix.lower() != '.avi':
            path = path.with_name(path.name + '.avi')
        existing = path.exists() or path.is_symlink()
        if existing:
            message = QMessageBox(self)
            message.setWindowTitle('Zastąpić film AVI?')
            message.setTextFormat(Qt.TextFormat.PlainText)
            message.setText(f'Zastąpić istniejący plik?\n{path}')
            message.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            message.setDefaultButton(QMessageBox.StandardButton.No)
            if message.exec() != QMessageBox.StandardButton.Yes:
                return
        job = AviExportJob(path, plan, existing, self)
        self._job = job
        self._progress.setRange(0, 2 * plan.frame_count + 2)
        self._progress.setValue(0)
        self._progress.show()
        self._cancel.setEnabled(True)
        self._cancel.show()
        self._info.setText(f'Sprawdzanie kodeka {plan.codec}…')
        job.progress.connect(self._show_progress)
        job.finished.connect(self._finish)
        self.busy_changed.emit()
        job.start()

    def cancel(self) -> None:
        if self._job is not None:
            self._job.cancel()
            self._cancel.setEnabled(False)
            self._info.setText('Anulowanie zapisu po bieżącym kroku…')

    def _show_progress(self, done: int, total: int, description: str) -> None:
        self._progress.setRange(0, total)
        self._progress.setValue(done)
        if self._cancel.isEnabled():
            self._info.setText(description)

    def _finish(self) -> None:
        job = self._job
        if job is None:
            return
        if job.result is not None:
            self._info.setText(f'Zapisano: {job.result}')
        elif job.error is not None:
            self._info.setText(f'Nie udało się zapisać AVI. {job.error}')
        else:
            self._info.setText('Anulowano zapis AVI; wcześniejszy plik zachowany.')
        self._job = None
        job.deleteLater()
        self._progress.hide()
        self._cancel.hide()
        self.busy_changed.emit()
