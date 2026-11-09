"""Select a coherent manual document and track which variants were actually saved."""

from collections import Counter
from typing import TYPE_CHECKING

from stmdomains.core.manual_class_lists import ManualClassLists
from stmdomains.core.manual_domains import ManualDomains
from stmdomains.core.manual_project import ManualProjectState, validate_history
from stmdomains.core.project import ProjectAnalysis
from stmdomains.ui.project_selection import analysis_identifier

if TYPE_CHECKING:
    from stmdomains.ui.manual_controller import ManualController


class ManualPersistence:
    def __init__(self, manual: 'ManualController') -> None:
        self.manual = manual
        self.saved: dict[str, tuple] = {}

    def reset(self) -> None:
        self.saved.clear()

    def _token(self, state: ManualProjectState, source_key: str) -> tuple:
        list_ids = {r.identifier for r in state.revisions if r.source_key == source_key}
        variants = tuple((v.identifier, v.cursor, tuple(id(f) for f in v.frames))
                         for v in state.variants if v.class_list_id in list_ids and len(v.frames) > 1)
        keys = {v[0] for v in variants}
        def steps(values):
            return tuple((s.variant_ids or (s.variant_id,), s.before.version if s.before else None,
                          s.after.version if s.after else None) for s in values if s.variant_id in keys)
        return variants, tuple(x for x in state.current if x[0] in list_ids), steps(state.undo), steps(state.redo)

    def tokens(self) -> dict[str, tuple]:
        state = self.snapshot(all_variants=True)
        if state is None:
            return {}
        used = {v.class_list_id for v in state.variants if len(v.frames) > 1}
        return {r.source_key: self._token(state, r.source_key) for r in state.revisions if r.identifier in used}

    @property
    def dirty(self) -> bool:
        current = self.tokens()
        return any(current.get(key) != self.saved.get(key) for key in set(current) | set(self.saved))

    def mark_saved(self, state: ManualProjectState | None) -> None:
        if state is not None:
            used = {v.class_list_id for v in state.variants if len(v.frames) > 1}
            for labels in state.revisions:
                if labels.identifier in used:
                    self.saved[labels.source_key] = self._token(state, labels.source_key)

    def options(self) -> list[tuple[str, str]]:
        m = self.manual
        sources = {}
        for variant in m.variants.values():
            labels = m.class_lists.get(variant)
            sources[labels.source_key] = variant
        if m.active is not None:
            sources[m.class_lists.get(m.active).source_key] = m.active
        used = self.tokens()
        ordered = sorted(sources.values(), key=lambda v: v is not m.active)
        return [(f'manual:{v.identifier}', f'Po korektach — lista {m.class_lists.get(v).identifier[:8]} · '
                 + ('bez analizy' if v.original is None else 'z wynikiem bazowym') + ' · wraz z historią')
                for v in ordered if m.class_lists.get(v).source_key in used]

    def snapshot(self, analysis: ProjectAnalysis | None = None, anchor: ManualDomains | None = None,
                 *, all_variants: bool = False) -> ManualProjectState | None:
        m = self.manual
        candidates = set(m.variants) if all_variants else set()
        if anchor is not None:
            source = m.class_lists.get(anchor).source_key
            candidates.update(k for k, v in m.variants.items() if m.class_lists.get(v).source_key == source)
        if analysis is not None:
            sources = {m.class_lists.get(v).source_key for v in m.variants.values()
                       if v.original is not None and analysis_identifier(v.original) == analysis.identifier}
            candidates.update(k for k, v in m.variants.items() if m.class_lists.get(v).source_key in sources)
        if not candidates:
            return None
        undo = tuple(s for s in m._undo if s.variant_id in candidates)
        redo = tuple(s for s in m._redo if s.variant_id in candidates)
        counts: Counter[str] = Counter()
        for step in (*undo, *redo):
            keys = step.variant_ids or (step.variant_id,)
            if not set(keys) <= candidates:
                raise ValueError('Wybrany zapis rozdziela atomową operację. Wybierz powiązany wariant ręczny.')
            counts.update(keys)
        states = tuple(v.snapshot(m.class_lists.get(v).identifier, counts[k])
                       for k, v in m.variants.items() if k in candidates)
        list_ids = {v.class_list_id for v in states}
        revisions = tuple(r for r in m.class_lists.revisions.values() if r.identifier in list_ids)
        current = tuple((r.identifier, r.version) for r in m.class_lists.current.values() if r.identifier in list_ids)
        selected = {i: k for i, k in m.selected.items() if k in candidates}
        for v in states:
            selected.setdefault(v.frames[0].working_index, v.identifier)
        if anchor is not None:
            selected[anchor.data.frame.working_index] = anchor.identifier
        state = ManualProjectState(states, revisions, current, undo, redo, tuple(sorted(selected.items())),
                                   m.editing, m.compare_original)
        validate_history(state)
        return state

    def base_analysis(self, state: ManualProjectState | None, base: ProjectAnalysis | None) -> ProjectAnalysis | None:
        if state is None:
            return base
        variants = {v.identifier: v for v in state.variants}
        frames = dict(base.frames) if base else {}
        for index, key in state.selected:
            original = variants[key].original
            if original is not None:
                frames[index] = original
        if not frames:
            return None
        statuses = dict(base.statuses) if base else {}
        statuses.update({i: {'status': f.status, 'message': f.message} for i, f in frames.items()})
        indices = tuple(sorted(set(statuses)))
        execution = base.execution if base and indices == base.indices else {'phase': 'restored'}
        return ProjectAnalysis(base.identifier if base else 'manual-base-' + state.variants[0].identifier,
                               indices, frames, statuses, base.catalogues if base else (), execution)

    def restore(self, state: ManualProjectState | None) -> None:
        m = self.manual
        if state is None:
            return
        validate_history(state)
        presenter = m.controller.presenter
        if presenter is None:
            raise ValueError('Brak danych projektu dla korekt.')
        registry = ManualClassLists()
        registry.revisions = {(r.identifier, r.version): r for r in state.revisions}
        for key in state.current:
            registry.publish(registry.revisions[key])
        m.variants = {v.identifier: ManualDomains.restore(presenter.analysis_input(v.frames[0].working_index), v)
                      for v in state.variants}
        for v in state.variants:
            source = registry.revisions[(v.class_list_id, dict(state.current)[v.class_list_id])].source_key
            registry.bindings[v.identifier] = source
        m.class_lists = registry
        m._undo, m._redo = list(state.undo), list(state.redo)
        m.selected = dict(state.selected)
        m.editing, m.compare_original = state.editing, state.comparison
        m._frame_index = m.controller.current_index
        self.mark_saved(state)
