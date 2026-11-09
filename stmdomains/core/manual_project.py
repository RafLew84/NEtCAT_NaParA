"""Immutable persisted manual histories, independent of the Qt controller."""

from dataclasses import dataclass

from stmdomains.core.analysis_result import FrameAnalysis
from stmdomains.core.manual_classes import ManualClassList


@dataclass(frozen=True)
class ManualStep:
    variant_id: str
    before: ManualClassList | None = None
    after: ManualClassList | None = None
    variant_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class ManualVariantState:
    identifier: str
    class_list_id: str
    original: FrameAnalysis | None
    frames: tuple[FrameAnalysis, ...]
    cursor: int
    revision: int


@dataclass(frozen=True)
class ManualProjectState:
    variants: tuple[ManualVariantState, ...]
    revisions: tuple[ManualClassList, ...]
    current: tuple[tuple[str, str], ...]
    undo: tuple[ManualStep, ...]
    redo: tuple[ManualStep, ...]
    selected: tuple[tuple[int, str], ...]
    editing: bool = False
    comparison: bool = False


def validate_history(state: ManualProjectState) -> None:
    """Check the full undo/redo timeline and shared class-list revisions."""
    variants = {v.identifier: v for v in state.variants}
    if not variants or len(variants) != len(state.variants):
        raise ValueError('Niejednoznaczne warianty historii korekt.')
    revisions = {(r.identifier, r.version): r for r in state.revisions}
    if len(revisions) != len(state.revisions):
        raise ValueError('Powtórzone rewizje listy klas.')
    current = dict(state.current)
    starts = {r.identifier: r.version for r in state.revisions if r.generation == 0}
    if set(starts) != set(current) or len(starts) != sum(r.generation == 0 for r in state.revisions):
        raise ValueError('Brak jednoznacznych początków list klas.')
    if len(current) != len(state.current) or any((key, value) not in revisions for key, value in state.current):
        raise ValueError('Nieznana bieżąca wersja listy klas.')
    if any(v.class_list_id not in current or type(v.cursor) is not int or not 0 <= v.cursor < len(v.frames)
           or type(v.revision) is not int or v.revision < 0 for v in state.variants):
        raise ValueError('Niepoprawna pozycja historii wariantu.')
    positions = dict.fromkeys(variants, 0)
    versions = dict(starts)
    timeline = state.undo + tuple(reversed(state.redo))
    for position in range(len(timeline) + 1):
        if position == len(state.undo):
            if versions != current or any(positions[v.identifier] != v.cursor for v in state.variants):
                raise ValueError('Bieżący stan nie odpowiada pozycji Cofnij/Ponów.')
        if position == len(timeline):
            break
        step = timeline[position]
        keys = step.variant_ids or (step.variant_id,)
        if not keys or step.variant_id != keys[0] or len(set(keys)) != len(keys) or not set(keys) <= variants.keys():
            raise ValueError('Historia odwołuje się do nieznanego wariantu.')
        if (step.before is None) != (step.after is None):
            raise ValueError('Niepełna zmiana rewizji klas w historii.')
        transactions = set()
        transaction_scopes = set()
        for key in keys:
            variant = variants[key]
            positions[key] += 1
            if positions[key] >= len(variant.frames):
                raise ValueError('Brak stanu operacji Cofnij/Ponów.')
            frame = variant.frames[positions[key]]
            edit = frame.metadata.get('manual_edit', {})
            if edit.get('variant_id') != key:
                raise ValueError('Operacja należy do innego wariantu.')
            if bool(str(edit.get('operation', '')).startswith('class_')) != (step.before is not None):
                raise ValueError('Rodzaj operacji nie odpowiada historii klas.')
            if step.after is not None:
                assert step.before is not None
                if frame.class_list is not step.after or step.after.identifier != variant.class_list_id:
                    raise ValueError('Stan klatki nie odpowiada rewizji listy klas.')
                if edit.get('class_list_before') != step.before.version:
                    raise ValueError('Niepoprawna poprzednia rewizja operacji klas.')
                if edit.get('class_list_after') != step.after.version or edit.get('class_list_id') != step.after.identifier:
                    raise ValueError('Niepoprawna docelowa rewizja operacji klas.')
                target = edit.get('class_target')
                if target and target not in {c.class_id for c in step.after.classes} and edit.get('operation') != 'class_delete':
                    raise ValueError('Nieznana klasa docelowa operacji.')
                if edit.get('transaction_id') is not None:
                    sources = edit.get('class_sources', ())
                    scope = tuple(edit.get('transaction_frames', ()))
                    if (edit.get('class_operation') not in ('merge', 'split') or not sources
                            or not set(sources) <= {c.class_id for c in step.before.classes}
                            or len(scope) != len(set(scope)) or frame.working_index not in scope):
                        raise ValueError('Niepoprawne źródła lub zakres operacji klas.')
                    previous = variant.frames[positions[key] - 1]
                    if any(previous.assignments[k].class_id not in sources
                           or frame.assignments[k].class_id != target for k in edit.get('selection', ())):
                        raise ValueError('Przypisania nie odpowiadają operacji scalania/podziału klas.')
                    transaction_scopes.add(scope)
            transactions.add(edit.get('transaction_id'))
        if len(keys) > 1 and (len(transactions) != 1 or None in transactions or len(transaction_scopes) != 1):
            raise ValueError('Niespójna wieloklatkowa operacja historii.')
        if step.before is not None and step.after is not None:
            if (step.before.identifier != step.after.identifier or versions.get(step.before.identifier) != step.before.version
                    or revisions.get((step.before.identifier, step.before.version)) is not step.before
                    or revisions.get((step.after.identifier, step.after.version)) is not step.after):
                raise ValueError('Niespójna kolejność zmian wspólnej listy klas.')
            versions[step.after.identifier] = step.after.version
    if any(positions[v.identifier] != len(v.frames) - 1 for v in state.variants):
        raise ValueError('Stan korekt nie ma operacji w historii.')
    selected = dict(state.selected)
    if len(selected) != len(state.selected) or any(type(i) is not int or key not in variants
            or variants[key].frames[0].working_index != i for i, key in state.selected):
        raise ValueError('Niepoprawny wybrany wariant klatki.')
    if type(state.editing) is not bool or type(state.comparison) is not bool:
        raise ValueError('Niepoprawny widok korekt.')
