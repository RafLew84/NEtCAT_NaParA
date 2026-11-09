"""Session-only manual variants, independent of automatic workers and run tables."""

from typing import TYPE_CHECKING
from dataclasses import dataclass

from PyQt6.QtCore import QObject, pyqtSignal

from stmdomains.core.analysis_result import FrameAnalysis
from stmdomains.core.manual_domains import ManualDomains
from stmdomains.core.manual_classes import ManualClassList
from stmdomains.core.manual_class_lists import ManualClassLists
from stmdomains.core.result_names import class_name, domain_name, domain_names
from stmdomains.analysis.geometry_domain_settings import METHOD as GEOMETRY_METHOD
from stmdomains.analysis.freud_settings import METHOD as FREUD_METHOD

if TYPE_CHECKING:
    from stmdomains.ui.session_controller import SessionController

UNSAVED_MANUAL = ('Korekty ręczne są przechowywane tylko w tej sesji. '
                  'Zapis i eksport korekt nie są jeszcze dostępne.')


@dataclass(frozen=True)
class ManualStep:
    variant_id: str
    before: ManualClassList | None = None
    after: ManualClassList | None = None


class ManualController(QObject):
    changed = pyqtSignal()

    def __init__(self, controller: 'SessionController') -> None:
        super().__init__(controller)
        self.controller = controller
        self.variants: dict[str, ManualDomains] = {}
        self.selected: dict[int, str] = {}
        self.selection: tuple[str, ...] = ()
        self.preview_result: FrameAnalysis | None = None
        self.compare_original = False
        self.editing = False
        self.message = ''
        self.class_lists = ManualClassLists()
        self._undo: list[ManualStep] = []
        self._redo: list[ManualStep] = []
        self._frame_index = -1
        controller.series_changed.connect(self.reset)
        controller.frame_changed.connect(self._frame_changed)

    def reset(self, *_: object) -> None:
        self.variants.clear()
        self.class_lists = ManualClassLists()
        self._undo.clear()
        self._redo.clear()
        self.selected.clear()
        self.selection = ()
        self.preview_result = None
        self.editing = self.compare_original = False
        self._frame_index = -1
        self.message = ''
        self.changed.emit()

    @property
    def active(self) -> ManualDomains | None:
        return self.variants.get(self.selected.get(self.controller.current_index, ''))

    @property
    def has_changes(self) -> bool:
        return any(v.changed for v in self.variants.values())

    @property
    def class_list(self) -> ManualClassList | None:
        return self.class_lists.get(self.active) if self.active is not None else None

    @property
    def current_result(self) -> FrameAnalysis | None:
        """Applied memberships with current shared names, before any preview."""
        active = self.active
        if active is None:
            return self.controller.result
        return self.class_lists.display(active) or active.current

    def class_member_count(self, class_id: str) -> int:
        labels = self.class_list
        return sum(a.class_id == class_id for v in self.variants.values()
                   if labels is not None and self.class_lists.get(v).identifier == labels.identifier
                   for a in v.current.assignments.values())

    @property
    def original_class_list(self) -> ManualClassList | None:
        return self.class_lists.original(self.active) if self.active is not None else None

    @property
    def class_scope_frames(self) -> tuple[int, ...]:
        labels = self.class_list
        return tuple(sorted({v.data.frame.working_index for v in self.variants.values()
                             if labels is not None and self.class_lists.get(v).identifier == labels.identifier}))

    @property
    def blocks_persistence(self) -> bool:
        return (self.has_changes or self.preview_result is not None
                or self.displayed_result(self.controller.result) is not self.controller.result)

    @property
    def can_edit(self) -> bool:
        return self.editing and not self.compare_original and self.controller.can_analyze

    def displayed_result(self, automatic: FrameAnalysis | None) -> FrameAnalysis | None:
        active = self.active
        if active is None:
            return automatic
        if self.compare_original:
            return active.original
        return self.preview_result or self.class_lists.display(active)

    def _notify(self) -> None:
        self.controller._refresh_result()
        self.changed.emit()

    def _frame_changed(self, *_: object) -> None:
        self.changed.emit()

    def prepare_frame(self) -> None:
        """Resolve the frame's variant before the controller publishes its view."""
        if self._frame_index != self.controller.current_index:
            self._frame_index = self.controller.current_index
            self.selection = ()
            self.preview_result = None
            self.compare_original = False
            series = self.controller.series
            key = self.class_lists.source_key(series.identity, self.controller.result) if series else ''
            labels = self.class_lists.current.get(key)
            shared_labels = (labels is not None and labels.generation > 0
                             and self.controller.current_index not in self.selected)
            if (self.editing or shared_labels) and self.controller.can_analyze:
                try:
                    self.ensure_variant()
                except ValueError as error:
                    self.message = str(error)
                    self.editing = False

    def choices(self) -> list[tuple[str, str]]:
        entries = [('', 'Bieżący wynik automatyczny')]
        for key, variant in self.variants.items():
            if variant.data.frame.working_index == self.controller.current_index:
                method = variant.original.parameters.get('domain_method', '') if variant.original else ''
                source = ('bez analizy' if variant.original is None else
                          {GEOMETRY_METHOD: 'Geometria', FREUD_METHOD: 'freud'}.get(method, 'Bazowa'))
                entries.append((key, f'Korekta {len(entries)} · {source}'))
        return entries

    def select_variant(self, key: str) -> None:
        if self.controller.is_busy:
            return
        if key and (key not in self.variants or
                    self.variants[key].data.frame.working_index != self.controller.current_index):
            return
        self.controller.pause()
        self.selected[self.controller.current_index] = key
        self.compare_original = False
        self.preview_result = None
        self.selection = ()
        self.message = ''
        self._notify()

    def set_editing(self, enabled: bool) -> None:
        if enabled:
            self.controller.pause()
        self.editing = enabled
        self.preview_result = None
        if enabled:
            self.compare_original = False
            if self.controller.can_analyze:
                try:
                    self.ensure_variant()
                except ValueError as error:
                    self.message = str(error)
                    self.editing = False
        else:
            self.selection = ()
        self._notify()

    def set_comparison(self, enabled: bool) -> None:
        self.compare_original = enabled and self.active is not None
        self.preview_result = None
        self._notify()

    def ensure_variant(self) -> ManualDomains:
        active = self.active
        if active is not None:
            return active
        presenter = self.controller.presenter
        if presenter is None:
            raise ValueError('Najpierw otwórz serię.')
        original = self.controller.result
        # Re-entering the same source resumes its variant; a new analysis gets a new one.
        active = next((v for v in self.variants.values()
                       if v.data.frame.working_index == self.controller.current_index and v.original is original), None)
        if active is None:
            active = ManualDomains(presenter.analysis_input(self.controller.current_index), original)
            self.variants[active.identifier] = active
            self.class_lists.bind(active)
        self.selected[self.controller.current_index] = active.identifier
        return active

    def select_molecules(self, identifiers: tuple[str, ...], mode: str = 'replace') -> None:
        if not self.can_edit:
            return
        active = self.ensure_variant()
        selected = set(identifiers) & active.eligible_ids
        old = set(self.selection)
        choices = {'replace': selected, 'add': old | selected, 'subtract': old - selected,
                   'toggle': old ^ selected}
        self.selection = tuple(sorted(choices[mode]))
        self.preview_result = None
        self.message = ''
        self._notify()

    def preview(self, operation: str, target: int = 0) -> None:
        if not self.can_edit:
            return
        self.preview_result = None
        try:
            active = self.ensure_variant()
            labels = self.class_lists.get(active)
            result = active.preview(operation, self.selection, target,
                                    class_list=labels if labels.generation else None)
            self.preview_result = result
            current = self.current_result or active.current
            source_names, target_names = domain_names(current), domain_names(result)
            edit = result.metadata['manual_edit']
            destination = edit['target']
            before = sum(a.domain_local_id == destination for a in active.current.assignments.values()) if destination else 0
            after = sum(a.domain_local_id == destination for a in result.assignments.values()) if destination else 0
            sources = edit.get('source_domains', ())
            count = sum(len(source['member_ids']) for source in sources) if operation == 'merge' else len(self.selection)
            self.message = (f'Podgląd: {count} molekuł. '
                            + (f'Domena {target_names[destination]}: {before} → {after}. ' if destination else 'Usunięcie przypisania. ')
                            + f'Domeny: {active.current.domain_count} → {result.domain_count}.')
            if destination:
                member = next(a for a in result.assignments.values() if a.domain_local_id == destination)
                self.message += f' Klasa: {class_name(result, member.class_id) if member.class_id else "nieustalona"}.'
            if sources:
                source_text = ', '.join(f"{source_names[s['domain_id']]} ({len(s['member_ids'])})" for s in sources)
                target_text = ', '.join(f"{target_names[s['domain_id']]} ({len(s['member_ids'])})" for s in edit['target_domains'])
                self.message = f'{source_text} → {target_text}.\n' + self.message
                if operation == 'merge' and len({s['class_id'] for s in sources}) > 1:
                    self.message += '\nRóżne klasy źródłowe: wynik ma klasę nieustaloną.'
        except ValueError as error:
            self.message = str(error)
        self._notify()

    def cancel_preview(self) -> None:
        self.preview_result = None
        self.message = ''
        self._notify()

    def preview_classes(self, operation: str, *, target: str = '', name: str = '', color: str = '',
                        whole_domains: bool = False) -> None:
        if not self.can_edit:
            return
        self.preview_result = None
        try:
            active = self.ensure_variant()
            labels = self.class_lists.get(active)
            occupied = {a.class_id for v in self.variants.values()
                        if self.class_lists.get(v).identifier == labels.identifier
                        for a in v.current.assignments.values()}
            result = active.preview_classes(labels, operation, target=target, name=name, color=color,
                selection=self.selection, whole_domains=whole_domains, occupied=occupied)
            self.preview_result = result
            edit = result.metadata['manual_edit']
            splits = edit['splits']
            self.message = (f'Podgląd klas · {len(edit["selection"])} molekuł w klatce '
                            f'{self.controller.current_index + 1}. ')
            if splits:
                current = self.current_result or active.current
                self.message += 'Podział: ' + ', '.join(
                    f'{domain_name(current, s["source_domain"])} → '
                    f'{domain_name(result, s["source_domain"])} + {domain_name(result, s["target_domain"])}'
                    for s in splits) + '. '
            if result.class_list is not labels:
                self.message += 'Zmiana listy klas dotyczy wszystkich korzystających z niej klatek. '
            self.message += 'Model pozostaje bez zmian.'
        except ValueError as error:
            self.message = str(error)
        self._notify()

    def apply(self) -> None:
        if not self.can_edit or self.preview_result is None or self.active is None:
            return
        class_edit = self.preview_result.metadata['manual_edit']['operation'].startswith('class_')
        before = self.class_list if class_edit else None
        after = self.preview_result.class_list if class_edit else None
        self.active.apply(self.preview_result)
        if after is not None:
            self.class_lists.publish(after)
        self._undo.append(ManualStep(self.active.identifier, before, after))
        self._redo.clear()
        self.preview_result = None
        self.message = 'Zastosowano korektę. ' + UNSAVED_MANUAL
        self._notify()

    def undo(self) -> None:
        self._restore_history(self._undo, self._redo, redo=False)

    def redo(self) -> None:
        self._restore_history(self._redo, self._undo, redo=True)

    def history_target(self, *, redo: bool = False) -> ManualDomains | None:
        history = self._redo if redo else self._undo
        return self.variants[history[-1].variant_id] if history else None

    def history_label(self, *, redo: bool = False) -> str:
        history = self._redo if redo else self._undo
        if not history:
            return ''
        step = history[-1]
        frame = self.variants[step.variant_id].data.frame.working_index + 1
        prefix = 'lista klas · ' if step.before is not step.after else ''
        return f'{prefix}kl. {frame}'

    def _restore_history(self, source: list[ManualStep], destination: list[ManualStep], *, redo: bool) -> None:
        if not self.can_edit or not source:
            return
        step = source.pop()
        key = step.variant_id
        variant = self.variants[key]
        variant.redo() if redo else variant.undo()
        labels = step.after if redo else step.before
        if labels is not None:
            self.class_lists.publish(labels)
        destination.append(step)
        self.preview_result = None
        self.selection = ()
        index = variant.data.frame.working_index
        self.selected[index] = key
        self.message = f'{"Ponowiono" if redo else "Cofnięto"} operację w klatce {index + 1}.'
        if self.controller.current_index != index:
            self.controller.show_frame(index)
        self._notify()
