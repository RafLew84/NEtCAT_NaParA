"""One lightweight graph candidate, its evidence and a whole-movie preview."""
from dataclasses import replace
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QCloseEvent
from PyQt6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QHBoxLayout, QHeaderView, QLabel,
    QProgressBar, QPushButton, QScrollArea, QTabWidget, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from stmviewer.deep_matcher import DeepMatcherOptions, deep_unavailable_reason
from stmviewer.frame import ImageFrame
from stmviewer.graph_registration import graph_pairs
from stmviewer.graph_types import GraphTrial
from stmviewer.robust_graph_types import RobustTrial
from stmviewer.pair_comparison import PairTrial
from stmviewer.registration import FrameOrigin, RegistrationResult
from stmviewer.ui.deep_matcher_controls import DeepMatcherControls
from stmviewer.ui.graph_job import GraphJob
from stmviewer.ui.graph_application_controls import GraphApplicationControls
from stmviewer.ui.graph_movie import GraphMovieWidget
from stmviewer.ui.long_reference_controls import LongReferenceControls
from stmviewer.ui.robust_graph_controls import RobustGraphControls
from stmviewer.ui.pair_dialog import PairComparisonDialog


def _number_ranges(indices: tuple[int, ...]) -> str:
    """Compact consecutive series positions without hiding isolated frames."""
    groups: list[str] = []
    if not indices:
        return 'brak'
    start = end = indices[0] + 1
    for index in indices[1:]:
        value = index + 1
        if value == end + 1:
            end = value
        else:
            groups.append(str(start) if start == end else f'{start}–{end}')
            start = end = value
    groups.append(str(start) if start == end else f'{start}–{end}')
    return ', '.join(groups)


class GraphComparisonDialog(QDialog):
    changed = pyqtSignal()
    busy_changed = pyqtSignal()
    movie_apply_requested = pyqtSignal(object, object)
    movie_restore_requested = pyqtSignal()
    movie_cancel_requested = pyqtSignal()

    def __init__(self, frames: tuple[ImageFrame, ...], parent: QWidget, *,
                 registration: RegistrationResult | None = None,
                 deep_options: DeepMatcherOptions | None = None, trial: GraphTrial | None = None) -> None:
        super().__init__(parent)
        self.setObjectName('graphComparison')
        self.setWindowTitle('Dopasowanie wieloklatkowe — kandydat grafu')
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.resize(1260, 850)
        self._frames, self._registration, self._trial = frames, registration, trial
        self._job: GraphJob | None = None
        self._pair: PairComparisonDialog | None = None
        self._available, self._closing = True, False
        layout = QVBoxLayout(self)
        scope = QLabel('Przeglądanie i obliczanie kandydata zachowuje aktywny film i korekty. '
                       'Jawne zastosowanie lub przywrócenie podmienia aligned oraz wynik eksportu.', self)
        scope.setObjectName('graphScope')
        scope.setWordWrap(True)
        layout.addWidget(scope)
        body = QHBoxLayout()
        layout.addLayout(body, 1)
        panel = QWidget(self)
        sidebar = QVBoxLayout(panel)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFixedWidth(310)
        scroll.setWidget(panel)
        body.addWidget(scroll)
        self._application = GraphApplicationControls(frames, self)
        self._application.apply_requested.connect(self.movie_apply_requested)
        self._application.restore_requested.connect(self.movie_restore_requested)
        self._application.cancel_requested.connect(self.movie_cancel_requested)
        self._application.variant_selected.connect(self._application_variant_changed)
        sidebar.addWidget(self._application)
        sidebar.addWidget(QLabel('Deep Matcher — wspólne XY bez ECC', self))
        self._window = QComboBox(self)
        self._window.setObjectName('graphWindow')
        self._window.setAccessibleName('Liczba poprzednich klatek grafu')
        self._window.addItem('Do 3 poprzednich klatek', 3)
        self._window.addItem('Do 5 poprzednich klatek', 5)
        if trial is not None:
            self._window.setCurrentIndex(self._window.findData(trial.config.window))
        sidebar.addWidget(self._window)
        self._count = QLabel(self)
        self._count.setObjectName('graphPairCount')
        self._count.setWordWrap(True)
        sidebar.addWidget(self._count)
        self._deep = DeepMatcherControls(self)
        self._deep.check.hide()
        self._deep.set_options(DeepMatcherOptions(Path(trial.config.weights_path), trial.config.requested_device)
                               if trial is not None else deep_options or DeepMatcherOptions())
        sidebar.addWidget(self._deep)
        self._run = QPushButton('Oblicz kandydata grafu', self)
        self._run.setObjectName('runGraph')
        self._run.clicked.connect(self._start)
        sidebar.addWidget(self._run)
        self._progress = QProgressBar(self)
        self._progress.setObjectName('graphProgress')
        sidebar.addWidget(self._progress)
        self._cancel = QPushButton('Anuluj obliczenia', self)
        self._cancel.setObjectName('cancelGraph')
        self._cancel.clicked.connect(self.cancel)
        sidebar.addWidget(self._cancel)
        self._message = QLabel(self)
        self._message.setObjectName('graphMessage')
        self._message.setWordWrap(True)
        self._message.setTextFormat(Qt.TextFormat.PlainText)
        sidebar.addWidget(self._message)
        self._summary = QLabel(self)
        self._summary.setObjectName('graphSummary')
        self._summary.setWordWrap(True)
        self._summary.setTextFormat(Qt.TextFormat.PlainText)
        self._summary.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        sidebar.addWidget(self._summary)
        self._robust = RobustGraphControls(self)
        sidebar.addWidget(self._robust)
        sidebar.addStretch()
        tabs = QTabWidget(self)
        body.addWidget(tabs, 1)
        self._movie = GraphMovieWidget(frames, self)
        self._movie.variant_changed.connect(self._movie_variant_changed)
        tabs.addTab(self._movie, 'Film')
        relations = QWidget(self)
        relations_layout = QVBoxLayout(relations)
        info = QLabel('Pomiar przesuwa klatkę j na i. LS i Huber pokazują różnicę wspólnych pozycji; '
                      'reszta = rozwiązanie − pomiar. Mała reszta oznacza spójność relacji, '
                      'nie potwierdza poprawnego dopasowania struktur.', self)
        info.setWordWrap(True)
        relations_layout.addWidget(info)
        self._edges = QTableWidget(self)
        self._edges.setObjectName('graphEdges')
        self._edges.setColumnCount(10)
        self._edges.setHorizontalHeaderLabels(['Para i → j', 'Pomiar X', 'Pomiar Y', 'LS X', 'LS Y',
                                               'Reszta X', 'Reszta Y', 'Stan', 'Wynik modelu', 'Uwagi'])
        self._edges.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._edges.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._edges.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        header = self._edges.horizontalHeader()
        assert header is not None
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(True)
        relations_layout.addWidget(self._edges, 1)
        self._inspect = QPushButton('Obejrzyj wybraną parę', self)
        self._inspect.setObjectName('inspectGraphPair')
        self._inspect.clicked.connect(self._inspect_pair)
        relations_layout.addWidget(self._inspect)
        self._edges.itemSelectionChanged.connect(self._sync)
        tabs.addTab(relations, 'Relacje i rozbieżności')
        self._long = LongReferenceControls(frames, self)
        tabs.addTab(self._long, 'Dalsze odniesienia')
        self._long.result_ready.connect(self._finish_long)
        self._long.busy_changed.connect(self._long_busy_changed)
        self._robust.result_ready.connect(self._finish_robust)
        self._robust.selected_changed.connect(self._selected_robust)
        self._robust.busy_changed.connect(self._robust_busy_changed)
        self._deep.changed.connect(self._sync)
        self._window.currentIndexChanged.connect(self._sync)
        self._present_trial()
        if trial is not None and trial.extension is not None:
            self._select_extension_result(trial)
        self._sync()

    @property
    def trial(self) -> GraphTrial | None:
        return self._trial

    @property
    def busy(self) -> bool:
        return (self._job is not None or self._robust.busy or self._long.busy
                or self._application.busy or (self._pair is not None and self._pair.busy))

    def set_available(self, available: bool) -> None:
        self._available = available
        self._sync()

    def set_registration(self, registration: RegistrationResult | None) -> None:
        self._registration = registration
        self._movie.set_graph(self._trial, registration)
        self._application.set_context(self._trial, registration)

    def show_movie_progress(self, done: int, total: int, description: str) -> None:
        self._movie.pause()
        self._application.show_progress(done, total, description)
        self._sync()

    def finish_movie_progress(self, message: str) -> None:
        self._application.finish_progress(message)
        self._sync()
        if self._closing and not self.busy:
            self.close()

    def movie_cancelling(self) -> None:
        self._application.cancelling()

    def cancel(self) -> None:
        if self._application.busy:
            self.movie_cancel_requested.emit()
        self._robust.cancel()
        self._long.cancel()
        if self._job is not None:
            self._job.cancel()
            self._cancel.setEnabled(False)
            self._message.setText('Anulowanie po bieżącym dopasowaniu… Poprzedni kandydat pozostaje.')
        if self._pair is not None and self._pair.busy:
            self._pair.close()

    def _sync(self) -> None:
        count = len(graph_pairs(len(self._frames), int(self._window.currentData())))
        self._count.setText(f'{len(self._frames)} klatek · {count} par do rozpatrzenia.\n'
                            'Każda para liczona raz; zachowane pomiary tej samej konfiguracji są używane ponownie.')
        reason = deep_unavailable_reason(self._deep.options())
        self._deep.set_status(reason or 'Model zostanie sprawdzony podczas obliczania; bez pobierania wag.')
        available = self._available and not self.busy
        self._run.setEnabled(available and len(self._frames) > 1 and reason is None)
        self._window.setEnabled(available)
        self._deep.setEnabled(available)
        self._cancel.setVisible(self._job is not None)
        self._progress.setVisible(self._job is not None)
        self._robust.set_available(available)
        self._application.set_available(available)
        self._long.set_options(self._deep.options())
        self._long.set_available(available)
        self._inspect.setEnabled(available and self._trial is not None and self._edges.currentRow() >= 0)
        if self._pair is not None:
            self._pair.set_available(self._available and self._job is None and not self._robust.busy and not self._long.busy)

    def _present_trial(self, *, select_new_robust: bool = False) -> None:
        trial = self._trial
        if trial is None:
            self._summary.setText('Brak kandydata. Wybierz lokalne wagi i oblicz graf.')
        else:
            state = ('Graf spójny — pełne wspólne XY.' if trial.positions is not None else
                     f'Graf rozłączny — {len(trial.components)} komponenty. Brak pełnych XY.')
            groups = '; '.join(_number_ranges(group) for group in trial.components)
            bridge = ', '.join(f'{i + 1}–{j + 1}' for i, j in trial.bridges) or 'brak'
            bridge_note = ' Brak niezależnego obejścia tych relacji.' if trial.bridges else ''
            self._summary.setText(
                f'{state}\nKotwica: klatka {trial.anchor + 1}. Okno: {trial.config.window}.\n'
                f'Nowe pomiary: {trial.measured_pairs}; użyte ponownie: {trial.reused_pairs}.\n'
                f'Pomiary: {trial.measurement_s:.2f} s; solver: {trial.solver_s:.3f} s.\n'
                f'Komponenty: {groups}\nMosty: {bridge}.{bridge_note}\n'
                f'{trial.config.device} · wagi: {Path(trial.config.weights_path).name}\n'
                f'SHA-256 wag: {trial.config.weights_sha256[:16]}…\n'
                'Równe wagi LS. Wynik modelu i małe reszty nie stanowią oceny jakości obrazu.')
        self._application.set_context(trial, self._registration)
        self._long.set_graph(trial)
        self._robust.set_graph(trial, select_new=select_new_robust)
        self._present_edges()
        self._movie.set_graph(trial, self._registration)
        if select_new_robust:
            self._selected_robust()

    def _present_edges(self) -> None:
        trial, robust = self._trial, self._robust.selected
        previous = self._edges.currentRow()
        headers = ['Para i → j', 'Pomiar X', 'Pomiar Y', 'LS X', 'LS Y', 'Reszta LS X', 'Reszta LS Y']
        if robust is not None:
            headers += ['Huber X', 'Huber Y', 'Reszta Hubera X', 'Reszta Hubera Y', 'Waga Hubera']
        headers += ['Stan', 'Wynik modelu']
        if trial is not None and trial.extension is not None:
            headers += ['Pochodzenie']
        headers += ['Uwagi']
        self._edges.setColumnCount(len(headers))
        self._edges.setHorizontalHeaderLabels(headers)
        self._edges.setRowCount(len(trial.edges) if trial else 0)
        if trial is None:
            return

        def xy(value: tuple[float, ...] | None) -> list[str]:
            return [f'{v:.3f}' for v in value] if value is not None else ['—', '—']

        original_pairs = ({(item.i, item.j) for item in trial.extension.base.edges}
                          if trial.extension is not None else set())
        for row, edge in enumerate(trial.edges):
            solved = (tuple(trial.positions[edge.j][d] - trial.positions[edge.i][d] for d in (0, 1))
                      if trial.positions is not None else None)
            notes = edge.reason or ''
            if (edge.i, edge.j) in trial.bridges:
                notes = f'Most — brak obejścia. {notes}'
            cells = [f'{edge.i + 1} → {edge.j + 1}', *xy(edge.shift_xy), *xy(solved), *xy(edge.residual_xy)]
            if robust is not None:
                huber = (tuple(robust.positions[edge.j][d] - robust.positions[edge.i][d] for d in (0, 1))
                         if robust.positions is not None else None)
                weight = robust.weights[row]
                cells += [*xy(huber), *xy(robust.residuals[row]), '—' if weight is None else f'{weight:.6g}']
                if robust.positions is None:
                    notes += ' Huber: diagnostyka bez pełnego wyniku.'
            cells += [edge.status, '—' if edge.quality_score is None else f'{edge.quality_score:.3f}']
            if trial.extension is not None:
                cells += ['Okno' if (edge.i, edge.j) in original_pairs else 'Dalsze odniesienie']
            cells += [notes]
            for column, text in enumerate(cells):
                self._edges.setItem(row, column, QTableWidgetItem(text))
        if trial.edges:
            self._edges.selectRow(max(0, min(previous, len(trial.edges) - 1)))

    def _finish_robust(self, result: RobustTrial) -> None:
        if self._trial is None:
            return
        self._trial = replace(self._trial, robust_trials=(*self._trial.robust_trials, result))
        self._present_trial(select_new_robust=True)
        self.changed.emit()

    def _selected_robust(self) -> None:
        self._present_edges()
        result = self._robust.selected
        if result is not None:
            self._application.select_variant(f'huber:{result.revision}')
        if result is not None and result.positions is not None:
            self._movie.select_variant(f'huber:{result.revision}')

    def _application_variant_changed(self, key: str) -> None:
        if key.startswith('huber:'):
            self._robust.select(key.removeprefix('huber:'))
        self._movie.select_variant(key)

    def _movie_variant_changed(self, key: str) -> None:
        self._application.select_variant(key)
        if key.startswith('huber:'):
            self._robust.select(key.removeprefix('huber:'))

    def _robust_busy_changed(self) -> None:
        if self._robust.busy:
            self._movie.pause()
        self._sync()
        self.busy_changed.emit()
        if self._closing and not self.busy:
            self.close()

    def _finish_long(self, trial: GraphTrial) -> None:
        self._trial = trial
        self._present_trial()
        self._select_extension_result(trial)
        self.changed.emit()

    def _select_extension_result(self, trial: GraphTrial) -> None:
        extension = trial.extension
        key = 'graph'
        if extension is not None and extension.base_robust_revision is not None:
            key = f'huber:{trial.robust_trials[0].revision}'
            self._robust.select(trial.robust_trials[0].revision)
        self._application.select_variant(key)
        self._movie.select_variant(key)

    def _long_busy_changed(self) -> None:
        if self._long.busy:
            self._movie.pause()
        self._sync()
        self.busy_changed.emit()
        if self._closing and not self.busy:
            self.close()

    def _start(self) -> None:
        if not self._run.isEnabled():
            return
        self._movie.pause()
        job = GraphJob(self._frames, self, window=int(self._window.currentData()),
                        deep_options=self._deep.options(), previous=self._trial)
        self._job = job
        self._cancel.setEnabled(True)
        self._progress.setRange(0, 0)
        self._message.setText('Przygotowanie pomiarów grafu…')
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
            self._message.setText(f'Niepowodzenie nowej próby: {job.error}\nPoprzedni kandydat pozostaje.')
        elif job.result is not None:
            self._trial = job.result
            self._present_trial()
            self._message.setText('Obliczenia zakończone. Kandydat jest dostępny do oceny i zapisu w sesji.')
            self.changed.emit()
        job.deleteLater()
        self._sync()
        self.busy_changed.emit()
        if self._closing:
            self.close()

    def _inspect_pair(self) -> None:
        trial, row = self._trial, self._edges.currentRow()
        if trial is None or not self._inspect.isEnabled() or row < 0:
            return
        if self._pair is not None:
            self._pair.close()
        edge = trial.edges[row]
        initial = None
        if edge.shift_xy is not None:
            reference, moving = self._frames[edge.i], self._frames[edge.j]
            details = (f'Zapisany pomiar grafu: {edge.i + 1} → {edge.j + 1}. '
                       f'Wagi: {trial.config.weights_path}; okno {trial.config.window}.')
            if edge.residual_xy is not None:
                details += f'\nReszta LS − pomiar: {edge.residual_xy[0]:.3f}, {edge.residual_xy[1]:.3f} px.'
            initial = PairTrial(FrameOrigin(reference.source, reference.source_frame_index),
                                FrameOrigin(moving.source, moving.source_frame_index), 'deep_matcher_translation',
                                'Pomiar grafu — Deep Matcher', details, trial.config.device,
                                edge.shift_xy, edge.status, edge.quality_score)
        pair = PairComparisonDialog(self._frames, edge.j, self, reference_index=edge.i,
                                     initial_trial=initial, method='deep_matcher_translation',
                                     deep_options=DeepMatcherOptions(Path(trial.config.weights_path),
                                                                      trial.config.requested_device))
        self._pair = pair
        pair.busy_changed.connect(self._pair_busy_changed)
        pair.finished.connect(lambda: self._pair_closed(pair))
        pair.destroyed.connect(lambda: self._pair_closed(pair))
        pair.show()
        self._sync()

    def _pair_busy_changed(self) -> None:
        self._sync()
        self.busy_changed.emit()
        if self._closing and not self.busy:
            self.close()

    def _pair_closed(self, pair: PairComparisonDialog) -> None:
        # The destroyed signal can arrive while Qt is deleting the parent and
        # its controls. Finished/busy transitions already synchronized the UI.
        if self._pair is pair:
            self._pair = None

    def reject(self) -> None:
        if self.busy:
            self._closing = True
            self.cancel()
            return
        self._movie.pause()
        super().reject()

    def closeEvent(self, event: QCloseEvent | None) -> None:
        if event is not None and self.busy:
            self._closing = True
            self.cancel()
            event.ignore()
            return
        self._movie.pause()
        super().closeEvent(event)
