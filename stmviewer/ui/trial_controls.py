"""Lightweight trial library; navigation and exports stay with the main window."""
from collections.abc import Callable
from pathlib import Path

from PyQt6.QtCore import QSignalBlocker, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox, QDialog, QFileDialog, QGroupBox, QHBoxLayout, QLabel,
    QMessageBox, QPlainTextEdit, QProgressBar, QPushButton, QVBoxLayout, QWidget,
)

from stmviewer.frame import ImageFrame
from stmviewer.trial_comparison import FullTrialComparison, TrialSide
from stmviewer.trial_document import TrialDocument
from stmviewer.ui.trial_job import TrialJob


class TrialControls(QGroupBox):
    busy_changed = pyqtSignal()
    view_changed = pyqtSignal(bool)
    pairs_requested = pyqtSignal(object, object)

    def __init__(self, frames: Callable[[], tuple[ImageFrame, ...]],
                 current_index: Callable[[], int], parent: QWidget) -> None:
        super().__init__('Próby rejestracji', parent)
        self._frames, self._current_index = frames, current_index
        self._documents: list[TrialDocument] = []
        self._job: TrialJob | None = None
        self._available = True
        self._renderer: FullTrialComparison | None = None
        layout = QVBoxLayout(self)
        self.a, self.b = QComboBox(self), QComboBox(self)
        self.a.setObjectName('trialA')
        self.b.setObjectName('trialB')
        self._savers = []
        for side, combo in (('A', self.a), ('B', self.b)):
            row = QHBoxLayout()
            row.addWidget(QLabel(side, self))
            combo.setMinimumWidth(80)
            row.addWidget(combo, 1)
            save = QPushButton(f'Zapisz {side}…', self)
            save.setObjectName(f'saveTrial{side}')
            save.clicked.connect(lambda checked=False, side=side: self.save(side))
            row.addWidget(save)
            self._savers.append(save)
            layout.addLayout(row)
            combo.currentIndexChanged.connect(self._selection_changed)
        self.open_button = QPushButton('Otwórz próbę…', self)
        self.open_button.setObjectName('openTrial')
        self.open_button.setToolTip('Najpierw otwórz właściwe oryginały, także z nowej lokalizacji. Zachowaj tę samą kolejność i usunięcia klatek.')
        self.open_button.clicked.connect(self.open)
        layout.addWidget(self.open_button)
        self.view = QComboBox(self)
        self.view.setObjectName('trialView')
        self.view.addItems(['Aktualny film', 'Próba A', 'Próba B'])
        self.view.currentIndexChanged.connect(self._view_changed)
        layout.addWidget(self.view)
        self.pairs = QPushButton('Porównaj parę z prób A/B…', self)
        self.pairs.setObjectName('compareTrialPair')
        self.pairs.clicked.connect(self.compare_pair)
        layout.addWidget(self.pairs)
        self.details = QPushButton('Szczegóły prób A/B…', self)
        self.details.setObjectName('trialDetails')
        self.details.clicked.connect(self.show_details)
        layout.addWidget(self.details)
        self.info = QLabel(self)
        self.info.setObjectName('trialInfo')
        self.info.setTextFormat(Qt.TextFormat.PlainText)
        self.info.setWordWrap(True)
        layout.addWidget(self.info)
        self.progress = QProgressBar(self)
        self.progress.setObjectName('trialProgress')
        self.progress.hide()
        layout.addWidget(self.progress)
        self.cancel_button = QPushButton('Anuluj zapis/odczyt próby', self)
        self.cancel_button.setObjectName('cancelTrial')
        self.cancel_button.clicked.connect(self.cancel)
        self.cancel_button.hide()
        layout.addWidget(self.cancel_button)
        self.sync_available(True)

    @property
    def busy(self) -> bool:
        return self._job is not None

    @property
    def comparing(self) -> bool:
        return self.view.currentIndex() != 0 and self._renderer is not None

    def add(self, document: TrialDocument) -> None:
        """Accept only a finished attempt or an operator-approved manual trial."""
        self._documents.append(document)
        p = document.payload
        outcome = {'complete': 'gotowa', 'failed': 'przerwana', 'cancelled': 'anulowana'}.get(p['outcome'], p['outcome'])
        kind = 'film' if p['kind'] == 'series' else 'para'
        title = f"{len(self._documents)}. {p['label']} · {kind} · {outcome}"
        for combo in (self.a, self.b):
            with QSignalBlocker(combo):
                combo.addItem(title)
                combo.setItemData(combo.count() - 1, title, Qt.ItemDataRole.ToolTipRole)
        with QSignalBlocker(self.b):
            self.b.setCurrentIndex(len(self._documents) - 1)
        # Adding a document never changes the displayed movie or exported result.
        self.stop_comparison()
        self.sync_available(self._available)
        self.info.setText('Próba dostępna na liście B. Zapisz ją, aby zachować po zamknięciu programu.\nBrak niezależnej oceny jakości.')

    def clear(self) -> None:
        self._documents.clear()
        self._renderer = None
        for combo in (self.a, self.b):
            with QSignalBlocker(combo):
                combo.clear()
        with QSignalBlocker(self.view):
            self.view.setCurrentIndex(0)
        self.info.setText('Zmiana składu serii wyczyściła próby z pamięci. Pliki prób pozostają na dysku.')
        self.sync_available(self._available)

    def sync_available(self, available: bool) -> None:
        self._available = available
        enabled = available and not self.busy
        self.open_button.setEnabled(enabled and bool(self._frames()))
        for combo, save in zip((self.a, self.b), self._savers):
            combo.setEnabled(enabled and bool(self._documents))
            save.setEnabled(enabled and combo.currentIndex() >= 0)
        self.view.setEnabled(enabled and bool(self._documents))
        self.pairs.setEnabled(enabled and bool(self._documents))
        self.details.setEnabled(bool(self._documents))

    def selected(self, side: str) -> TrialDocument | None:
        index = (self.a if side == 'A' else self.b).currentIndex()
        return self._documents[index] if 0 <= index < len(self._documents) else None

    def save(self, side: str) -> None:
        document = self.selected(side)
        if document is None or not self._available or self.busy:
            return
        filename, _ = QFileDialog.getSaveFileName(self, f'Zapisz próbę {side}',
                                                 'proba.stmtrial.json', 'Próba STM Viewer (*.stmtrial.json)',
                                                 options=QFileDialog.Option.DontConfirmOverwrite)
        if filename:
            path = Path(filename)
            if not path.name.endswith('.stmtrial.json'):
                path = path.with_name(path.name + '.stmtrial.json')
            if path.exists() or path.is_symlink():
                message = QMessageBox(self)
                message.setWindowTitle('Zastąpić dokument próby?')
                message.setTextFormat(Qt.TextFormat.PlainText)
                message.setText(f'Zastąpić istniejący dokument?\n{path}')
                message.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                message.setDefaultButton(QMessageBox.StandardButton.No)
                if message.exec() != QMessageBox.StandardButton.Yes:
                    return
            self._start(TrialJob(path, self._frames(), self, document=document))

    def open(self) -> None:
        if not self._available or self.busy or not self._frames():
            return
        filename, _ = QFileDialog.getOpenFileName(self, 'Otwórz próbę przy bieżących oryginałach', '',
                                                 'Próba STM Viewer (*.stmtrial.json);;JSON (*.json)')
        if filename:
            self._start(TrialJob(Path(filename), self._frames(), self))

    def _start(self, job: TrialJob) -> None:
        self._job = job
        self.progress.setRange(0, 0)
        self.progress.show()
        self.cancel_button.setEnabled(True)
        self.cancel_button.show()
        self.info.setText('Sprawdzanie źródeł i dokumentu próby…')
        self.sync_available(self._available)
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
        if job.error:
            self.info.setText(f'Nie udało się otworzyć/zapisać próby: {job.error}\nPoprzednie próby pozostają.')
        elif job.result is None:
            self.info.setText('Anulowano. Wcześniejszy dokument i próby pozostają.')
        elif job.document is None:
            self.add(job.result)
            self.info.setText(f'Otwarto: {job.path.name}\nTylko porównanie; aktywny aligned i eksport pozostają bez zmian.')
        else:
            self.info.setText(f'Zapisano: {job.path}\nDokument wymaga tych samych oryginalnych źródeł.')
        self._job = None
        job.deleteLater()
        self.progress.hide()
        self.cancel_button.hide()
        self.sync_available(self._available)
        self.busy_changed.emit()

    def _selection_changed(self) -> None:
        self._renderer = None
        if self.view.currentIndex():
            self._view_changed(reset=True)

    def stop_comparison(self) -> None:
        with QSignalBlocker(self.view):
            self.view.setCurrentIndex(0)
        self._renderer = None
        self.view_changed.emit(False)

    def _view_changed(self, _index: int = 0, *, reset: bool = False) -> None:
        if not self.view.currentIndex():
            self.view_changed.emit(False)
            return
        try:
            if self._renderer is None:
                a, b = self.selected('A'), self.selected('B')
                if a is None or b is None:
                    raise ValueError('Wybierz dwie kompletne próby filmu.')
                shifts = []
                for doc in (a, b):
                    p = doc.payload
                    if p['kind'] != 'series' or p['outcome'] != 'complete':
                        raise ValueError('Pełny podgląd wymaga dwóch kompletnych prób filmu. Dla par i przerwanych prób użyj szczegółów lub porównania pary.')
                    shifts.append(tuple(tuple(r['cumulative_xy']) for r in p['records']))
                self._renderer = FullTrialComparison(self._frames(), shifts[0], shifts[1])
                reset = True
            self.info.setText('Porównanie A/B względem pierwszej bieżącej klatki. Suwak i Play zmieniają klatkę. Eksport nadal używa aktywnego aligned.')
            self.view_changed.emit(reset)
        except (ValueError, MemoryError, OverflowError) as error:
            self.stop_comparison()
            self.info.setText(str(error))

    def preview_frame(self, index: int) -> tuple[ImageFrame, tuple[float, float, int, int]] | None:
        if not self.comparing or self._renderer is None:
            return None
        side: TrialSide = 'A' if self.view.currentIndex() == 1 else 'B'
        try:
            return self._renderer.render(index, side=side), self._renderer.original_rect(index, side=side)
        except (ValueError, MemoryError, OverflowError) as error:
            self.stop_comparison()
            self.info.setText(f'Nie udało się odtworzyć klatki próby: {error}')
            return None

    def compare_pair(self) -> None:
        from stmviewer.trial_capture import pair_from_document, diagnostic_start_from_document
        a, b = self.selected('A'), self.selected('B')
        if a is None or b is None:
            return
        try:
            index = max(1, self._current_index())
            pair_docs = [d for d in (a, b) if d.payload['kind'] == 'pair']
            if pair_docs:
                index = pair_docs[0].payload['records'][-1]['index']
            trials = []
            for doc in (a, b):
                try:
                    trial = pair_from_document(doc, self._frames(), moving_index=index)
                except ValueError:
                    trial = diagnostic_start_from_document(doc, self._frames(), moving_index=index)
                trials.append(trial)
            self.pairs_requested.emit(*trials)
        except (ValueError, IndexError) as error:
            self.info.setText(f'Nie można porównać tej pary: {error}')

    def show_details(self) -> None:
        from stmviewer.ui.trial_details import trial_details_text
        dialog = QDialog(self)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dialog.setWindowTitle('Zapisane próby — ustawienia i dostępne wyniki')
        dialog.resize(900, 700)
        layout = QVBoxLayout(dialog)
        text = QPlainTextEdit(dialog)
        text.setObjectName('trialDetailsText')
        text.setReadOnly(True)
        text.setPlainText('\n\n'.join(f'PRÓBA {s}\n{trial_details_text(d)}' for s in ('A', 'B')
                                    if (d := self.selected(s)) is not None))
        layout.addWidget(text)
        close = QPushButton('Zamknij', dialog)
        close.clicked.connect(dialog.close)
        layout.addWidget(close)
        dialog.show()
