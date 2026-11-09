"""Select one analysis, including unfinished frames, without mixing unrelated runs."""

from collections.abc import Mapping
from dataclasses import asdict
from typing import Any

from stmdomains.core.analysis_result import FrameAnalysis, analysis_identifier
from stmdomains.core.project import ProjectAnalysis
from stmdomains.ui.series_runner import FrameRunStatus, SeriesRun
from stmdomains.io.project_validation import analysis_plan


def select_analysis(identifier: str, results: Mapping[int, FrameAnalysis], previous: Mapping[int, FrameAnalysis],
                    run: SeriesRun | None, run_results: Mapping[int, FrameAnalysis]) -> ProjectAnalysis:
    current_run = run if run and run.identifier == identifier else None
    frames = dict(run_results) if current_run else {
        index: result for collection in (previous, results) for index, result in collection.items()
        if analysis_identifier(result) == identifier}
    if current_run:
        indices = current_run.indices
        statuses = {index: asdict(item) for index, item in current_run.frames.items()}
        execution: dict[str, Any] = {'phase': current_run.phase, 'message': current_run.message,
                                   'selection': current_run.selection, 'plan': asdict(current_run.plan)}
        catalogues = (current_run.catalogue,) if current_run.catalogue else ()
    else:
        if not frames:
            raise ValueError('Wybrany wynik nie jest już dostępny w pamięci.')
        first = next(iter(frames.values()))
        indices = tuple(first.metadata.get('series_analysis', {}).get('working_indices', (first.working_index,)))
        statuses = {index: {'status': frames[index].status, 'message': frames[index].message} if index in frames else
                    {'status': 'unavailable', 'message': 'Brak tej części wybranego przebiegu w pamięci.'} for index in indices}
        execution = {'phase': 'restored', 'message': 'Wybrany wynik; brakujące części pozostają niedostępne.'}
        catalogues = ()
    return ProjectAnalysis(identifier, indices, frames, statuses, catalogues, execution)


def restored_run(analysis: ProjectAnalysis, series_id: str) -> SeriesRun:
    record = analysis.execution
    plan = analysis_plan(record['plan']) if 'plan' in record else analysis_plan({
        'start': min(analysis.indices), 'end': max(analysis.indices)})
    frames = {}
    for index, status in analysis.statuses.items():
        frames[index] = FrameRunStatus(status['status'], status.get('message', ''), status.get('assigned', 0),
                                       status.get('active', 0), status.get('domains', 0))
    return SeriesRun(series_id, plan, analysis.indices, phase=str(record.get('phase', 'restored')),
                     message=str(record.get('message', 'Otworzono zapisany wynik.')),
                     catalogue=analysis.catalogues[0] if analysis.catalogues else None,
                     frames=frames, selection=record.get('selection'), identifier=analysis.identifier)
