"""Lifecycle of the current graph candidate, independent of active aligned."""
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QPushButton, QWidget

from stmviewer.ui.method_parameters import MethodParameterControls
from stmviewer.deep_matcher import DeepMatcherOptions
from stmviewer.frame import ImageFrame
from stmviewer.graph_types import GraphTrial
from stmviewer.registration import RegistrationResult
from stmviewer.ui.graph_dialog import GraphComparisonDialog


class GraphControls(QObject):
    changed = pyqtSignal()
    busy_changed = pyqtSignal()
    movie_apply_requested = pyqtSignal(object, object)
    movie_restore_requested = pyqtSignal()
    movie_cancel_requested = pyqtSignal()

    def __init__(self, parent: QWidget, *, parameters: MethodParameterControls | None = None) -> None:
        super().__init__(parent)
        self._parent = parent
        self._parameters = parameters or MethodParameterControls(parent)
        self._trial: GraphTrial | None = None
        self._dialog: GraphComparisonDialog | None = None
        self._available = True
        self.open_button = QPushButton('Dopasowanie wieloklatkowe…', parent)
        self.open_button.setObjectName('openGraph')
        self.open_button.setToolTip('Oblicz i obejrzyj osobny kandydat grafu. Aktywny aligned pozostaje bez zmian.')
        self.open_button.setEnabled(False)

    @property
    def trial(self) -> GraphTrial | None:
        return self._trial

    @property
    def busy(self) -> bool:
        return self._dialog is not None and self._dialog.busy

    def sync(self, available: bool, has_frames: bool) -> None:
        self._available = available
        self.open_button.setEnabled(available and has_frames and not self.busy)
        if self._dialog is not None:
            self._dialog.set_available(available)

    def open_graph(self, frames: tuple[ImageFrame, ...], registration: RegistrationResult | None,
                   deep_options: DeepMatcherOptions, *, method: str | None = None) -> None:
        if not self._available or len(frames) < 2:
            return
        if self._dialog is not None:
            self._dialog.show()
            self._dialog.raise_()
            self._dialog.activateWindow()
            return
        dialog = GraphComparisonDialog(frames, self._parent, registration=registration,
                                        deep_options=deep_options, trial=self._trial, method=method, parameters=self._parameters)
        self._dialog = dialog
        dialog.changed.connect(self._changed)
        dialog.movie_apply_requested.connect(self.movie_apply_requested)
        dialog.movie_restore_requested.connect(self.movie_restore_requested)
        dialog.movie_cancel_requested.connect(self.movie_cancel_requested)
        dialog.busy_changed.connect(self.busy_changed)
        dialog.finished.connect(lambda: self._closed(dialog))
        dialog.destroyed.connect(lambda: self._closed(dialog))
        dialog.show()

    def restore(self, trial: GraphTrial | None) -> None:
        self.close_dialog()
        self._trial = trial

    def clear(self) -> None:
        self.restore(None)

    def set_registration(self, registration: RegistrationResult | None) -> None:
        if self._dialog is not None:
            self._dialog.set_registration(registration)

    def show_movie_progress(self, done: int, total: int, description: str) -> None:
        if self._dialog is not None:
            self._dialog.show_movie_progress(done, total, description)

    def finish_movie_progress(self, message: str) -> None:
        if self._dialog is not None:
            self._dialog.finish_movie_progress(message)

    def movie_cancelling(self) -> None:
        if self._dialog is not None:
            self._dialog.movie_cancelling()

    def cancel(self) -> None:
        if self._dialog is not None:
            self._dialog.cancel()

    def close_dialog(self) -> None:
        if self._dialog is not None:
            dialog = self._dialog
            dialog.close()
            if not dialog.busy:
                self._dialog = None

    def _changed(self) -> None:
        if self._dialog is not None:
            self._trial = self._dialog.trial
            self.changed.emit()

    def _closed(self, dialog: GraphComparisonDialog) -> None:
        if self._dialog is dialog:
            self._dialog = None
