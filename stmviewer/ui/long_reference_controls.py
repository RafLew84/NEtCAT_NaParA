"""Explicit far-frame relation plans over a fixed window graph."""
from pathlib import Path

from PyQt6.QtCore import QSignalBlocker, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView, QComboBox, QFormLayout, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QMessageBox, QProgressBar, QPushButton, QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from stmviewer.deep_matcher import DeepMatcherOptions, deep_unavailable_reason
from stmviewer.frame import ImageFrame
from stmviewer.graph_types import GraphTrial
from stmviewer.registration import RegistrationError
from stmviewer.ui.long_reference_job import LongReferenceJob


class LongReferenceControls(QWidget):
    result_ready = pyqtSignal(object)
    busy_changed = pyqtSignal()

    def __init__(self, frames: tuple[ImageFrame, ...], parent: QWidget) -> None:
        super().__init__(parent)
        self._frames = frames
        self._job: LongReferenceJob | None = None
        self._base: GraphTrial | None = None
        self._options = DeepMatcherOptions()
        self._available = True
        self._pairs: tuple[tuple[int, int], ...] = ()
        self._reason: str | None = 'Najpierw oblicz albo otwórz kompletny graf okna.'
        layout = QVBoxLayout(self)
        help_text = QLabel('Wskaż klatki odniesienia i zakres porównania. Powstanie osobny wynik '
                           'okno + dalsze odniesienia. Dotychczasowe pomiary, model i ustawienia '
                           'wybranego solvera pozostają. Żadna klatka nie jest wybierana automatycznie.', self)
        help_text.setWordWrap(True)
        layout.addWidget(help_text)
        form = QFormLayout()
        self._solver = QComboBox(self)
        self._solver.setObjectName('longBaseSolver')
        self._solver.setAccessibleName('Bazowy wynik okna do rozszerzenia')
        form.addRow('Bazowy wynik okna:', self._solver)
        self._references = QLineEdit(self)
        self._references.setObjectName('longReferences')
        self._references.setPlaceholderText('Numery w bieżącej serii, np. 1, 30, 80')
        form.addRow('Klatki odniesienia:', self._references)
        bounds = QHBoxLayout()
        self._start = QSpinBox(self)
        self._start.setObjectName('longTargetStart')
        self._start.setRange(1, max(1, len(frames)))
        self._end = QSpinBox(self)
        self._end.setObjectName('longTargetEnd')
        self._end.setRange(1, max(1, len(frames)))
        self._end.setValue(max(1, len(frames)))
        bounds.addWidget(self._start)
        bounds.addWidget(QLabel('do', self))
        bounds.addWidget(self._end)
        form.addRow('Zakres klatek od:', bounds)
        layout.addLayout(form)
        self._base_info = QLabel(self)
        self._base_info.setObjectName('longBaseInfo')
        self._base_info.setWordWrap(True)
        self._base_info.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self._base_info)
        self._summary = QLabel(self)
        self._summary.setObjectName('longPlanSummary')
        self._summary.setWordWrap(True)
        layout.addWidget(self._summary)
        self._table = QTableWidget(self)
        self._table.setObjectName('longPairs')
        self._table.setColumnCount(3)
        self._table.setHorizontalHeaderLabels(['Para w serii', 'Źródło klatki i', 'Źródło klatki j'])
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        header = self._table.horizontalHeader()
        assert header is not None
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self._table, 1)
        self._reason_text = QLabel(self)
        self._reason_text.setObjectName('longPlanReason')
        self._reason_text.setWordWrap(True)
        self._reason_text.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self._reason_text)
        self._run = QPushButton('Oblicz okno + dalsze odniesienia', self)
        self._run.setObjectName('runLongReferences')
        layout.addWidget(self._run)
        self._run.clicked.connect(self._start_job)
        self._progress = QProgressBar(self)
        self._progress.setObjectName('longReferenceProgress')
        layout.addWidget(self._progress)
        self._cancel = QPushButton('Anuluj dalsze odniesienia', self)
        self._cancel.setObjectName('cancelLongReferences')
        self._cancel.clicked.connect(self.cancel)
        layout.addWidget(self._cancel)
        self._message = QLabel(self)
        self._message.setObjectName('longReferenceMessage')
        self._message.setWordWrap(True)
        self._message.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self._message)
        self._references.textChanged.connect(self._present_plan)
        self._start.valueChanged.connect(self._present_plan)
        self._end.valueChanged.connect(self._present_plan)
        self._solver.currentIndexChanged.connect(self._present_plan)
        self._present_plan()

    def set_graph(self, trial: GraphTrial | None) -> None:
        extension = trial.extension if trial is not None else None
        base = extension.base if extension is not None else trial
        same_base = base is not None and self._base is not None and base.revision == self._base.revision
        selected = self._solver.currentData()
        self._base = base
        with QSignalBlocker(self._solver):
            self._solver.clear()
            if base is not None and base.positions is not None:
                self._solver.addItem('Samo okno — LS', 'graph')
                for index, robust in enumerate(base.robust_trials, 1):
                    if robust.positions is not None:
                        self._solver.addItem(f'Samo okno — Huber {index}, próg {robust.config.threshold_px:g} px',
                                             f'huber:{robust.revision}')
                if extension is not None and not same_base:
                    selected = ('graph' if extension.base_robust_revision is None
                                else f'huber:{extension.base_robust_revision}')
                found = self._solver.findData(selected)
                if found >= 0:
                    self._solver.setCurrentIndex(found)
        if extension is not None and not same_base:
            with QSignalBlocker(self._references), QSignalBlocker(self._start), QSignalBlocker(self._end):
                self._references.setText(', '.join(str(i + 1) for i in extension.references))
                self._start.setValue(extension.target_start + 1)
                self._end.setValue(extension.target_end + 1)
        self._present_plan()

    def set_options(self, options: DeepMatcherOptions) -> None:
        if options != self._options:
            self._options = options
            self._present_plan()

    def set_available(self, available: bool) -> None:
        self._available = available
        self._sync()

    def _reference_indices(self) -> tuple[int, ...]:
        text = self._references.text().strip()
        if not text:
            raise RegistrationError('Wpisz numery klatek odniesienia, oddzielone przecinkami.')
        try:
            values = tuple(int(part.strip()) - 1 for part in text.split(','))
        except ValueError as error:
            raise RegistrationError('Podaj całkowite numery klatek, oddzielone przecinkami.') from error
        if any(i < 0 or i >= len(self._frames) for i in values):
            raise RegistrationError(f'Numery klatek muszą należeć do zakresu 1–{len(self._frames)}.')
        return tuple(sorted(set(values)))

    def _selected_revision(self) -> str | None:
        key = str(self._solver.currentData())
        return key.removeprefix('huber:') if key.startswith('huber:') else None

    def _present_plan(self) -> None:
        from stmviewer.long_references import plan_long_references
        self._pairs = ()
        self._reason = None
        base = self._base
        self._base_info.setText('Brak bazowego wyniku okna.')
        try:
            if base is None or base.positions is None:
                raise RegistrationError('Najpierw oblicz albo otwórz kompletny graf okna.')
            solver = base.solver
            revision = self._selected_revision()
            robust = next((item for item in base.robust_trials if item.revision == revision), None)
            if robust is not None:
                solver = (f'{robust.config.solver} · próg {robust.config.threshold_px:g} px '
                          f'· limit {robust.config.max_iterations}')
            self._base_info.setText(
                f'Baza: okno {base.config.window} · {solver} · kotwica: klatka 1.\n'
                f'Model: {Path(base.config.weights_path).name} · SHA-256 {base.config.weights_sha256[:16]}…\n'
                'Wagi i urządzenie wybierasz w lewym panelu; zgodność z bazą zostanie sprawdzona przed pomiarami. '
                'Zmiana okna po lewej dotyczy nowego grafu; rozszerzenie zachowuje okno bazy.')
            self._pairs = plan_long_references(base, self._reference_indices(),
                                               self._start.value() - 1, self._end.value() - 1)
            if not self._pairs:
                raise RegistrationError('Brak nowych par. Wskazane relacje są już w oknie lub łączą klatkę z nią samą.')
            self._reason = deep_unavailable_reason(self._options)
        except RegistrationError as error:
            self._reason = str(error)
        self._summary.setText(f'{len(self._pairs)} nowych par. Pary okna i powtórzenia są pomijane. '
                               'Pomiar przesuwa klatkę j na i; kierunek pary jest zawsze i < j.')
        self._table.setRowCount(len(self._pairs))
        for row, (i, j) in enumerate(self._pairs):
            cells = [f'{i + 1} → {j + 1}', self._source_label(i), self._source_label(j)]
            for column, text in enumerate(cells):
                item = QTableWidgetItem(text)
                if column > 0:
                    item.setToolTip(str(self._frames[i if column == 1 else j].source))
                self._table.setItem(row, column, item)
        self._reason_text.setText(self._reason or 'Plan gotowy. Zostaną zmierzone tylko wymienione nowe pary.')
        self._sync()

    def _source_label(self, index: int) -> str:
        frame = self._frames[index]
        text = frame.source.name
        if frame.source_frame_index is not None:
            text += f' · MPP {frame.source_frame_index + 1}'
        return text

    def _sync(self) -> None:
        for widget in (self._solver, self._references, self._start, self._end):
            widget.setEnabled(self._available and not self.busy)
        self._run.setEnabled(self._available and not self.busy and self._reason is None and bool(self._pairs))
        self._cancel.setVisible(self.busy)
        self._progress.setVisible(self.busy)

    @property
    def busy(self) -> bool:
        return self._job is not None

    def cancel(self) -> None:
        if self._job is not None:
            self._job.cancel()
            self._cancel.setEnabled(False)
            self._message.setText('Anulowanie po bieżącym pomiarze… Poprzedni kandydat i film pozostają.')

    def _start_job(self) -> None:
        if not self._run.isEnabled() or self._base is None:
            return
        job = LongReferenceJob(self._frames, self._base, self, references=self._reference_indices(),
                               target_start=self._start.value() - 1, target_end=self._end.value() - 1,
                               robust_revision=self._selected_revision(), deep_options=self._options)
        self._job = job
        self._cancel.setEnabled(True)
        self._progress.setRange(0, 0)
        self._message.setText('Sprawdzanie zgodności bazy i przygotowanie jawnego planu par…')
        job.progress.connect(self._show_progress)
        job.finished.connect(self._finish)
        self._sync()
        self.busy_changed.emit()
        job.start()

    def _show_progress(self, done: int, total: int, description: str) -> None:
        self._progress.setRange(0, total)
        self._progress.setValue(done)
        if self._cancel.isEnabled():
            self._message.setText(description)

    def _finish(self) -> None:
        job = self._job
        if job is None:
            return
        self._job = None
        if job.was_cancelled():
            self._message.setText('Anulowano. Poprzedni kandydat i aktywny aligned pozostają.')
        elif job.error is not None:
            self._message.setText(f'Niepowodzenie: {job.error}\nPoprzedni kandydat i aktywny aligned pozostają.')
        elif job.result is not None:
            self.result_ready.emit(job.result)
            self._message.setText('Gotowy kandydat. W zakładce Film porównaj go z samym oknem. '
                                  'Aktywny aligned zmieni się dopiero po „Zastosuj wynik do filmu”.')
            extension = job.result.extension
            if extension is not None and extension.base_robust_revision is not None:
                robust = job.result.robust_trials[0]
                if robust.positions is None:
                    message = QMessageBox(self)
                    message.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
                    message.setIcon(QMessageBox.Icon.Information)
                    message.setWindowTitle('Niekompletny wynik Hubera')
                    message.setText('Nie uzyskano kompletnego wyniku Hubera dla rozszerzonego grafu.')
                    message.setInformativeText(robust.reason + '\nWybrany Huber pozostaje niedostępny do zastosowania. '
                                               'Podgląd może pokazywać LS; nie został zastosowany do filmu. '
                                               'Możesz jawnie wybrać LS albo obliczyć nowy wariant Hubera.')
                    message.setStandardButtons(QMessageBox.StandardButton.Ok)
                    message.open()
        job.deleteLater()
        self._sync()
        self.busy_changed.emit()
