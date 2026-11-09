"""Immutable multi-frame class previews and preflighted, atomic application."""

from dataclasses import dataclass
from collections.abc import Callable, Mapping
from uuid import uuid4

from stmdomains.core.analysis_result import FrameAnalysis
from stmdomains.core.manual_classes import ManualClassList
from stmdomains.core.manual_class_lists import ManualClassLists
from stmdomains.core.manual_domains import ManualDomains


@dataclass(frozen=True)
class ClassChange:
    variant: ManualDomains
    before: FrameAnalysis
    after: FrameAnalysis


@dataclass(frozen=True)
class ClassTransaction:
    identifier: str
    before: ManualClassList
    after: ManualClassList
    changes: tuple[ClassChange, ...]

    @classmethod
    def prepare(cls, frames: tuple[ManualDomains, ...], labels: ManualClassList, operation: str, *,
                sources: tuple[str, ...], target: str = '', name: str = '', color: str = '',
                selections: Mapping[int, tuple[str, ...]] | None = None,
                check: Callable[[], None] = lambda: None,
                progress: Callable[[str], None] = lambda text: None) -> 'ClassTransaction':
        check()
        if not frames or len({v.data.frame.working_index for v in frames}) != len(frames):
            raise ValueError('Wybierz niepusty zakres z jednym wariantem na klatkę.')
        if any(ManualClassLists.source_key(v.data.series_id, v.original) != labels.source_key for v in frames):
            raise ValueError('Wybrane klatki korzystają z innego katalogu lub listy klas.')
        sources = tuple(dict.fromkeys(sources))
        if not sources or not set(sources) <= {c.class_id for c in labels.classes}:
            raise ValueError('Wybierz klasy z bieżącej listy.')
        if operation not in ('merge', 'split'):
            raise ValueError('Nieznana operacja klas.')
        if operation == 'merge' and len(sources) < 2:
            raise ValueError('Scalenie wymaga co najmniej dwóch klas z bieżącej listy.')
        if operation == 'split' and (len(sources) != 1 or target):
            raise ValueError('Podział wymaga jednej klasy źródłowej i nowej klasy docelowej.')
        if target and target not in sources:
            raise ValueError('Celem scalenia musi być jedna z klas źródłowych lub nowa klasa.')
        present = {a.class_id for v in frames for key, a in v.current.assignments.items() if key in v.eligible_ids}
        if not set(sources) <= present:
            raise ValueError('Każda klasa źródłowa musi mieć członków w wybranym zakresie.')
        selected_frames = {}
        for variant in frames:
            check()
            index = variant.data.frame.working_index
            members = {k for k, a in variant.current.assignments.items()
                       if k in variant.eligible_ids and a.class_id in sources}
            selected = set((selections or {}).get(index, ())) if operation == 'split' else members
            if operation == 'split' and ((members and not selected) or not selected <= members):
                raise ValueError(f'Klatka {index + 1}: wskaż jawnie członków jednej klasy źródłowej.')
            selected_frames[index] = selected
        if operation == 'split':
            total = sum(a.class_id == sources[0] for v in frames for k, a in v.current.assignments.items()
                        if k in v.eligible_ids)
            if sum(map(len, selected_frames.values())) >= total:
                raise ValueError('Wybrano całą klasę w zakresie. Podział wymaga właściwego podzbioru.')
        revised = labels if target else labels.edit('create', name=name, color=color)
        target = target or revised.classes[-1].class_id
        identity = uuid4().hex
        changes = []
        for variant in frames:
            check()
            progress(f'Podgląd: klatka {variant.data.frame.working_index + 1}')
            chosen = tuple(sorted(k for k in selected_frames[variant.data.frame.working_index]
                                  if variant.current.assignments[k].class_id != target))
            if not chosen:
                continue
            before = variant.current
            after = variant.preview_classes(revised, 'assign', target=target, selection=chosen,
                operation_details={'transaction_id': identity, 'class_operation': operation,
                    'class_sources': sources, 'class_list_before': labels.version,
                    'transaction_frames': tuple(v.data.frame.working_index for v in frames)})
            changes.append(ClassChange(variant, before, after))
        if not changes:
            raise ValueError('Operacja nie zmieni żadnego przypisania.')
        return cls(identity, labels, revised, tuple(changes))

    def validate(self) -> None:
        for change in self.changes:
            if change.variant.current is not change.before:
                raise ValueError('Wynik zmienił się od przygotowania podglądu. Odśwież podgląd.')
            change.variant.validate_preview(change.after)

    def apply(self) -> None:
        # All expected errors are checked before changing any frame's history.
        self.validate()
        for change in self.changes:
            change.variant.apply(change.after)
