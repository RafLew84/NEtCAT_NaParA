"""Frozen scope, explicit per-frame selections and background class previews."""

from collections.abc import Callable, Iterator
from dataclasses import replace
from threading import Event
from typing import TYPE_CHECKING

from PyQt6.QtCore import QCoreApplication, QObject, QThreadPool, QTimer, pyqtSlot

from stmdomains.core.analysis_result import FrameAnalysis
from stmdomains.core.class_operations import ClassTransaction
from stmdomains.core.manual_classes import ManualClassList
from stmdomains.core.manual_class_lists import ManualClassLists
from stmdomains.core.manual_domains import ManualDomains
from stmdomains.io.moltrack_import import ImportCancelled
from stmdomains.ui.tasks import Task

if TYPE_CHECKING:
    from stmdomains.ui.manual_controller import ManualController


class ManualClassOperations(QObject):
    def __init__(self, manual: 'ManualController') -> None:
        super().__init__(manual)
        self.manual = manual
        self.frames: dict[int, ManualDomains] = {}
        self.before: dict[int, FrameAnalysis] = {}
        self.skipped: dict[int, str] = {}
        self.selections: dict[int, tuple[str, ...]] = {}
        self.labels: ManualClassList | None = None
        self.transaction: ClassTransaction | None = None
        self._preview_frames: dict[int, FrameAnalysis] = {}
        self.message = ''
        self._pool = QThreadPool(QCoreApplication.instance())
        self._pool.setMaxThreadCount(1)
        self._tasks: dict[int, Task] = {}
        self._token: int | None = None
        self._counter = 0
        self._closed = False
        self._capture_work: Iterator[None] | None = None
        self._capture_serial = 0

    @property
    def running(self) -> bool:
        return bool(self._tasks) or self._capture_work is not None

    @property
    def pending_task_count(self) -> int:
        return len(self._tasks)

    def invalidate(self, message: str = '') -> None:
        self._capture_work = None
        self._capture_serial += 1
        for task in self._tasks.values():
            task.cancelled.set()
        self._token = None
        self.transaction = None
        self._preview_frames.clear()
        self.frames.clear()
        self.before.clear()
        self.skipped.clear()
        self.selections.clear()
        self.labels = None
        self.message = message

    def cancel_preview(self) -> None:
        if self._capture_work is not None:
            self.invalidate()
        for task in self._tasks.values():
            task.cancelled.set()
        self._token = None
        self.transaction = None
        self._preview_frames.clear()
        self.message = 'Podgląd anulowany; przypisania i historia bez zmian.'
        self.manual.controller._busy()
        self.manual._notify()

    def capture(self, scope: str, start: int = 0, end: int = 0, *, variant_id: str = '') -> None:
        m, c = self.manual, self.manual.controller
        if not m.can_edit:
            return
        self.invalidate()
        m.preview_result = None
        try:
            anchor = m.variants.get(variant_id) if variant_id else m.ensure_variant()
            if anchor is None or c.series is None or c.presenter is None:
                raise ValueError('Najpierw wybierz wynik i listę klas.')
            labels = m.class_lists.get(anchor)
            if not labels.classes:
                raise ValueError('Wybrana lista nie ma klas. Utwórz je w oknie Klasy ręczne.')
            indices: tuple[int, ...]
            if scope == 'current_frame':
                indices = (c.current_index,)
            elif scope == 'whole_series':
                indices = tuple(range(c.series.frame_count))
            elif scope == 'selected_range' and 0 <= start <= end < c.series.frame_count:
                indices = tuple(range(start, end + 1))
            else:
                raise ValueError('Niepoprawny zakres klatek.')
            method = c._method_name(anchor.original)
            version = c.result_version
            source_run = anchor.original.metadata.get('series_analysis', {}).get('run_id') if anchor.original else None
            self.labels = labels
            self._capture_work = self._capture_frames(indices, c.series.identity, labels, method, version, source_run, anchor)
            self.message = 'Sprawdzanie zakresu…'
            serial = self._capture_serial
            QTimer.singleShot(0, lambda: self._advance_capture(serial))
        except ValueError as error:
            self.message = str(error)
        c._busy()
        m._notify()

    def _capture_frames(self, indices: tuple[int, ...], series_id: str, labels: ManualClassList,
                        method: str, version: str, source_run: str | None, anchor: ManualDomains) -> Iterator[None]:
        m, c = self.manual, self.manual.controller
        for index in indices:
            selected = anchor if index == anchor.data.frame.working_index else m.variants.get(m.selected.get(index, ''))
            original = selected.original if selected else c.result_at(index, method, version)
            key = ManualClassLists.source_key(series_id, original)
            run = original.metadata.get('series_analysis', {}).get('run_id') if original else None
            if key != labels.source_key:
                self.skipped[index] = 'inny katalog / lista klas' if original else 'brak wyniku tej listy'
            elif source_run and run != source_run:
                self.skipped[index] = 'inny przebieg analizy'
            else:
                variant = selected or m.variant_for(index, original)
                if not any(a.class_id and k in variant.eligible_ids for k, a in variant.current.assignments.items()):
                    self.skipped[index] = 'brak przypisań klas'
                else:
                    self.frames[index] = variant
                    self.before[index] = variant.current
                    m.selected[index] = variant.identifier
            self.message = f'Sprawdzanie zakresu: klatka {index + 1}…'
            yield
        if not self.frames:
            raise ValueError('W zakresie nie ma przypisań wybranej listy.')
        self.message = 'Zakres ustalony. Wybierz klasy i przygotuj podgląd.'

    def _advance_capture(self, serial: int) -> None:
        if self._capture_work is None or serial != self._capture_serial or self._closed:
            return
        try:
            next(self._capture_work)
        except StopIteration:
            self._capture_work = None
        except Exception as error:
            self.invalidate(str(error))
        if self._capture_work is not None:
            QTimer.singleShot(0, lambda: self._advance_capture(serial))
        self.manual.controller._busy()
        self.manual._notify()

    def remember_selection(self, *, whole_domains: bool = False) -> None:
        m = self.manual
        index = m.controller.current_index
        self.transaction = None
        self._preview_frames.clear()
        try:
            self.validate_scope()
            variant = self.frames.get(index)
            if variant is None:
                raise ValueError('Bieżąca klatka nie należy do ustalonego zakresu.')
            selected = set(m.selection)
            if not selected or not selected <= variant.eligible_ids:
                raise ValueError('Zaznacz aktywne molekuły na tej klatce.')
            if whole_domains:
                domains = {variant.current.assignments[k].domain_local_id for k in selected} - {0}
                selected.update(k for k, a in variant.current.assignments.items() if a.domain_local_id in domains)
            self.selections[index] = tuple(sorted(selected))
            self.message = f'Zapamiętano {len(selected)} wskazań w klatce {index + 1}; pozostałe klatki mają własne wybory.'
        except ValueError as error:
            self.message = str(error)
        m._notify()

    def validate_scope(self) -> None:
        if self.labels is None or not self.frames:
            raise ValueError('Najpierw ustal zakres i wersję listy klas.')
        if self.manual.class_lists.current.get(self.labels.source_key) is not self.labels:
            raise ValueError('Lista klas zmieniła się. Ustal zakres i podgląd ponownie.')
        if any(v.current is not self.before[i] for i, v in self.frames.items()):
            raise ValueError('Przypisania zmieniły się. Ustal zakres i podgląd ponownie.')

    def preview(self, operation: str, *, sources: tuple[str, ...], target: str = '',
                name: str = '', color: str = '') -> None:
        if not self.manual.can_edit or self.running:
            return
        self.transaction = None
        self._preview_frames.clear()
        try:
            self.validate_scope()
            frames, labels = tuple(self.frames.values()), self.labels
            selections = dict(self.selections)
            self._counter += 1
            token = self._counter
            self._token = token
            def calculate(cancelled: Event, report: Callable[[str], None]) -> object:
                def check() -> None:
                    if cancelled.is_set():
                        raise ImportCancelled()
                assert labels is not None
                return ClassTransaction.prepare(frames, labels, operation, sources=sources, target=target,
                    name=name, color=color, selections=selections, check=check, progress=report)
            task = Task(token, calculate)
            task.signals.result.connect(self._received)
            task.signals.error.connect(self._failed)
            task.signals.progress.connect(self._progress)
            task.signals.finished.connect(self._finished)
            self._tasks[token] = task
            self.message = 'Przygotowanie podglądu klas…'
            self._pool.start(task)
        except ValueError as error:
            self.message = str(error)
        self.manual.controller._busy()
        self.manual._notify()

    @pyqtSlot(int, object)
    def _received(self, token: int, result: object) -> None:
        if token != self._token or self._closed or not isinstance(result, ClassTransaction):
            return
        try:
            self.validate_scope()
            result.validate()
            self.transaction = result
            changed = {change.after.working_index: change.after for change in result.changes}
            self._preview_frames = {i: changed[i] if i in changed else replace(before, class_list=result.after)
                                    for i, before in self.before.items()}
            self.message = 'Podgląd gotowy. Obejrzyj objęte klatki i zatwierdź całość jednym krokiem.'
        except ValueError as error:
            self.message = str(error)
        self.manual._notify()

    @pyqtSlot(int, str)
    def _failed(self, token: int, message: str) -> None:
        if token == self._token and not self._closed:
            self.message = message
            self.transaction = None
            self.manual._notify()

    @pyqtSlot(int, str)
    def _progress(self, token: int, message: str) -> None:
        if token == self._token and not self._closed:
            self.message = message
            self.manual.changed.emit()

    @pyqtSlot(int)
    def _finished(self, token: int) -> None:
        self._tasks.pop(token, None)
        if not self._closed:
            self.manual.controller._busy()
            self.manual._notify()

    def displayed(self, index: int) -> FrameAnalysis | None:
        return self._preview_frames.get(index) if self.transaction is not None else None

    def apply(self) -> None:
        if not self.manual.can_edit or self.transaction is None:
            return
        try:
            self.validate_scope()
            self.manual.apply_class_transaction(self.transaction)
            self.invalidate('Zastosowano całą operację. Cofnij/Ponów obejmuje wszystkie jej klatki.')
        except ValueError as error:
            self.transaction = None
            self.message = str(error)
        self.manual._notify()

    def shutdown(self) -> None:
        self._closed = True
        self.invalidate()

    def wait_for_workers(self) -> None:
        self._pool.waitForDone()
