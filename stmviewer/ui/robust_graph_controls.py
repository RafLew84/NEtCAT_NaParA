"""Choose a Huber threshold and retain separate results on the same measurements."""
from PyQt6.QtCore import QSignalBlocker, Qt, pyqtSignal
from PyQt6.QtWidgets import QComboBox, QDoubleSpinBox, QLabel, QProgressBar, QPushButton, QSpinBox, QVBoxLayout, QWidget

from stmviewer.graph_types import GraphTrial
from stmviewer.robust_graph_types import RobustConfig, RobustTrial
from stmviewer.ui.robust_graph_job import RobustGraphJob


def robust_label(index: int, result: RobustTrial) -> str:
    suffix = '' if result.positions is not None else ' — brak pełnego wyniku'
    return f'Huber {index + 1} · próg {result.config.threshold_px:g} px{suffix}'


class RobustGraphControls(QWidget):
    result_ready = pyqtSignal(object)
    selected_changed = pyqtSignal()
    busy_changed = pyqtSignal()

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self._graph: GraphTrial | None = None
        self._job: RobustGraphJob | None = None
        self._available = True
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 0)
        title = QLabel('Huber — te same zapisane pomiary', self)
        title.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(QLabel('Próg Hubera', self))
        self._threshold = QDoubleSpinBox(self)
        self._threshold.setObjectName('robustThreshold')
        self._threshold.setAccessibleName('Próg Hubera w pikselach')
        self._threshold.setRange(.01, 10000.)
        self._threshold.setDecimals(2)
        self._threshold.setSingleStep(.5)
        self._threshold.setSuffix(' px')
        self._threshold.setValue(RobustConfig().threshold_px)
        self._threshold.setToolTip('Próg długości reszty XY. Zmiana ustawienia nie zmienia zapisanych wyników; oblicz nowy wariant.')
        layout.addWidget(self._threshold)
        layout.addWidget(QLabel('Limit iteracji', self))
        self._iterations = QSpinBox(self)
        self._iterations.setObjectName('robustMaxIterations')
        self._iterations.setAccessibleName('Maksymalna liczba iteracji Hubera')
        self._iterations.setRange(1, 10000)
        self._iterations.setValue(RobustConfig().max_iterations)
        self._iterations.setToolTip('Jeśli próba osiąga limit, można jawnie wybrać większy i obliczyć kolejny wariant. Tolerancje pozostają takie same.')
        layout.addWidget(self._iterations)
        self._run = QPushButton('Oblicz nowy wariant Hubera', self)
        self._run.setObjectName('runRobustGraph')
        self._run.clicked.connect(self._start)
        layout.addWidget(self._run)
        self._progress = QProgressBar(self)
        self._progress.setObjectName('robustProgress')
        layout.addWidget(self._progress)
        self._cancel = QPushButton('Anuluj Hubera', self)
        self._cancel.setObjectName('cancelRobustGraph')
        self._cancel.clicked.connect(self.cancel)
        layout.addWidget(self._cancel)
        self._message = QLabel(self)
        self._message.setObjectName('robustMessage')
        self._message.setTextFormat(Qt.TextFormat.PlainText)
        self._message.setWordWrap(True)
        layout.addWidget(self._message)
        layout.addWidget(QLabel('Zapisane wyniki Hubera', self))
        self._variant = QComboBox(self)
        self._variant.setObjectName('robustVariant')
        self._variant.setAccessibleName('Zapisany wariant Hubera i jego diagnostyka')
        self._variant.currentIndexChanged.connect(self._selection_changed)
        layout.addWidget(self._variant)
        self._summary = QLabel(self)
        self._summary.setObjectName('robustSummary')
        self._summary.setTextFormat(Qt.TextFormat.PlainText)
        self._summary.setWordWrap(True)
        self._summary.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self._summary)
        self.set_graph(None)

    @property
    def busy(self) -> bool:
        return self._job is not None

    @property
    def selected(self) -> RobustTrial | None:
        if self._graph is None:
            return None
        key = self._variant.currentData()
        return next((trial for trial in self._graph.robust_trials if trial.revision == key), None)

    def set_graph(self, graph: GraphTrial | None, *, select_new: bool = False) -> None:
        previous = self._variant.currentData()
        self._graph = graph
        with QSignalBlocker(self._variant):
            self._variant.clear()
            if graph is not None:
                for index, trial in enumerate(graph.robust_trials):
                    self._variant.addItem(robust_label(index, trial), trial.revision)
            found = self._variant.findData(previous)
            self._variant.setCurrentIndex(found if found >= 0 and not select_new else self._variant.count() - 1)
        self._show_summary()
        self._sync()

    def select(self, revision: str) -> None:
        index = self._variant.findData(revision)
        if index >= 0:
            self._variant.setCurrentIndex(index)

    def set_available(self, available: bool) -> None:
        self._available = available
        self._sync()

    def cancel(self) -> None:
        if self._job is not None:
            self._job.cancel()
            self._cancel.setEnabled(False)
            self._message.setText('Anulowanie po bieżącej iteracji… Wcześniejsze warianty pozostają.')

    def _sync(self) -> None:
        available = self._available and not self.busy
        self._threshold.setEnabled(available)
        self._iterations.setEnabled(available)
        self._run.setEnabled(available and self._graph is not None)
        self._variant.setEnabled(available and self._variant.count() > 0)
        self._progress.setVisible(self.busy)
        self._cancel.setVisible(self.busy)

    def _selection_changed(self) -> None:
        self._show_summary()
        self.selected_changed.emit()

    def _show_summary(self) -> None:
        result = self.selected
        if result is None:
            self._summary.setText('Obliczenie korzysta z relacji LS bez ponownego uruchamiania Deep. Każdy próg tworzy osobny wariant.')
            return
        config = result.config
        status = 'Zbieżny — pozycje dostępne do porównania.' if result.positions is not None else 'Brak pełnego wyniku — tylko diagnostyka.'
        objective = f'{result.objective:.6g}' if result.objective is not None else '—'
        condition = f'{result.condition_estimate:.3g}' if result.condition_estimate is not None else '—'
        def diagnostic(value: float | None) -> str:
            return '—' if value is None else f'{value:.6g}'
        limit_note = ('\nMożna zwiększyć limit iteracji i obliczyć nowy wariant.'
                      if result.status == 'iteration_limit' else '')
        self._summary.setText(
            f'{status}\n{result.reason}\n'
            f'Próg: {config.threshold_px:g} px · iteracje: {result.iterations}/{config.max_iterations}\n'
            f'Koszt Hubera: {objective}; koszt dla LS: {diagnostic(result.ls_objective)}\n'
            f'Zmiana XY: {diagnostic(result.max_step_px)} px; zmiana kosztu: {diagnostic(result.relative_cost_change)}; '
            f'gradient: {diagnostic(result.gradient_inf)}\n'
            f'Uwarunkowanie: {condition} ({config.condition_method})\n'
            f'Koniec: {result.status} · czas: {result.solver_s:.3f} s\n'
            f'Pomiar: {result.measurement_id[:16]}…\n'
            f'{config.solver}\n'
            f'Tolerancje: XY {config.position_tolerance_px:g} px; koszt {config.objective_relative_tolerance:g}; '
            f'gradient {config.gradient_tolerance:g}. Limit uwarunkowania: {config.max_condition:g}.\n'
            f'Jedna waga dla całej reszty XY. Mała waga oznacza konflikt relacji, nie dowód jej fizycznego błędu.{limit_note}')

    def _start(self) -> None:
        if not self._run.isEnabled() or self._graph is None:
            return
        config = RobustConfig(threshold_px=self._threshold.value(), max_iterations=self._iterations.value())
        job = RobustGraphJob(self._graph, config, self)
        self._job = job
        self._cancel.setEnabled(True)
        self._progress.setRange(0, 0)
        self._message.setText('Wyznaczanie Hubera na zapisanych relacjach…')
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
            self._message.setText('Anulowano. Wcześniejsze warianty i aktywny aligned pozostają.')
        elif job.error is not None:
            self._message.setText(f'Niepowodzenie nowej próby: {job.error}\nWcześniejsze warianty pozostają.')
        elif job.result is not None:
            self.result_ready.emit(job.result)
            self._message.setText('Zapisano nowy wariant Hubera.' if job.result.positions is not None
                                  else 'Zapisano diagnozę odmowy; nie utworzono pełnego filmu Hubera.')
        job.deleteLater()
        self._sync()
        self.busy_changed.emit()
