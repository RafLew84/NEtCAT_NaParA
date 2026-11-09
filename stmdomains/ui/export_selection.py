"""Capture one family of applied corrections before a worker starts exporting."""

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from stmdomains.core.export_snapshot import ExportCorrection, ExportSnapshot
from stmdomains.core.analysis_result import analysis_identifier

if TYPE_CHECKING:
    from stmdomains.ui.session_controller import SessionController


def export_choices(controller: 'SessionController') -> list[tuple[str, str]]:
    m = controller.manual
    choices = []
    families = set()
    if m.active is not None or controller.result is not None:
        choices.append(('displayed', 'Po korektach — bieżący wariant'))
        if m.active is not None:
            families.add(m.class_lists.get(m.active).source_key)
        if (m.active.original if m.active else controller.result) is not None:
            choices.append(('base', 'Bazowy automat — przed korektami'))
    for v in m.variants.values():
        labels = m.class_lists.get(v)
        if labels.source_key in families or not (v.changed or labels.generation):
            continue
        families.add(labels.source_key)
        choices.append((f'manual:{v.identifier}', f'Po korektach — lista {labels.identifier[:8]}'))
        if v.original is not None:
            choices.append((f'base:{v.identifier}', f'Bazowy automat — lista {labels.identifier[:8]}'))
    run = controller.series_run
    if run is not None and analysis_identifier(controller.result) != run.identifier:
        choices.append(('latest', f'Ostatni przebieg automatyczny · {run.identifier[:8]}'))
    choices.append(('none', 'Tylko oznaczenia wejściowe — bez analizy'))
    return choices


def capture_export(controller: 'SessionController', selection: str,
                   view: Mapping[str, Any]) -> ExportSnapshot:
    m = controller.manual
    if m.preview_result is not None or m.class_operations.transaction is not None:
        raise ValueError('Zatwierdź lub anuluj podgląd korekt przed eksportem.')
    assert controller.series is not None
    automatic = selection == 'base' or selection.startswith('base:')
    source = 'manual:' + selection[5:] if selection.startswith('base:') else 'displayed' if automatic else selection
    anchor = m.variants.get(source[7:]) if source.startswith('manual:') else m.active
    analysis = controller.project_analysis(source)
    corrections = {}
    shared = {}
    if source == 'displayed' or source.startswith('manual:'):
        family = m.class_lists.get(anchor).source_key if anchor else None
        candidates = [v for v in m.variants.values() if (
            m.class_lists.get(v).source_key == family if family is not None else
            analysis is not None and analysis.frames.get(v.data.frame.working_index) is v.original)]
        # The selected variant wins if several independent edits refer to one frame.
        candidates.sort(key=lambda v: (m.selected.get(v.data.frame.working_index) == v.identifier, v is anchor))
        for variant in candidates:
            index = variant.data.frame.working_index
            labels = m.class_lists.get(variant)
            shared[labels.identifier] = labels
            corrections[index] = ExportCorrection(variant.original if automatic else m.class_lists.display(variant),
                variant.original, variant.identifier, () if automatic else variant.applied_history)
    # ProjectAnalysis already freezes in-memory frames; disk-backed frames belong
    # to an immutable opened document. Keep their bounded lazy cache intact.
    if automatic and not (analysis and analysis.frames) and not any(c.original for c in corrections.values()):
        raise ValueError('Brak bazowego wyniku automatycznego dla wybranego wariantu.')
    return ExportSnapshot(controller.series, view, analysis,
        'automatic' if automatic or source == 'latest' else 'input' if source == 'none' else 'after_corrections',
        corrections, tuple(shared.values()))
