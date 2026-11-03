"""Public export contract: preserve identities and distinguish absent from zero results."""

import csv
import json

from stmdomains.core.project import ProjectAnalysis, ProjectSnapshot
from stmdomains.io.moltrack_import import prepare_import
from stmdomains.tools.analysis_demo import create_analysis_demo
from stmdomains.core.frame_presentation import FramePresenter
from stmdomains.analysis.series_analysis import analyze_series
from stmdomains.analysis.series_settings import SeriesAnalysisPlan


def test_csv_exports_one_run_and_missing_frame_without_computing(tmp_path):
    from stmdomains.io.export_results import export_results, ExportOptions
    series = prepare_import(create_analysis_demo(tmp_path / 'source')['series']).series
    events = analyze_series(FramePresenter(series).analysis_input, frame_count=series.frame_count,
        series_id=series.identity, plan=SeriesAnalysisPlan(k=4, current_frame=True), run_id='selected')
    catalogue, outcome = next(events), next(events)
    result = outcome.result
    analysis = ProjectAnalysis('selected', (0,), {0: result}, {0: {'status': result.status}}, (catalogue,))
    snapshot = ProjectSnapshot(series, analysis=analysis)
    target = tmp_path / 'export'
    export_results(target, snapshot, (0, 1), ExportOptions(csv=True, png=False))
    with (target / 'frames.csv').open() as stream:
        frames = list(csv.DictReader(stream))
    assert len(frames) == 2
    assert frames[0]['analysis_id'] == 'selected'
    assert int(frames[0]['assigned_count']) == result.assigned_count
    assert int(frames[0]['active_count']) == result.active_count
    assert frames[1]['analysis_status'] == 'not_in_analysis'
    assert frames[1]['domain_count'] == frames[1]['assigned_count'] == ''
    with (target / 'molecules.csv').open() as stream:
        molecules = list(csv.DictReader(stream))
    actual = {row['detection_id']: row for row in molecules if row['working_number'] == '1'}
    assert set(actual) == set(result.assignments)
    for identity, assignment in result.assignments.items():
        assert actual[identity]['class_id'] == assignment.class_id
        assert int(actual[identity]['domain_local_id']) == assignment.domain_local_id
        assert actual[identity]['rejection_reason'] == assignment.rejection_reason
    assert all(row['domain_local_id'] == '' for row in molecules if row['working_number'] == '2')
    manifest = json.loads((target / 'manifest.json').read_text())
    assert manifest['working_indices'] == [0, 1] and manifest['analysis_id'] == 'selected'
    frame_record = json.loads((target / 'frame-000001.json').read_text())
    assert frame_record['parameters'] == json.loads(json.dumps(dict(result.parameters)))
    assert frame_record['catalogue_id'] == catalogue.identifier
    assert (target / 'README.md').exists() and (target / 'domains.csv').exists()


def test_zero_domains_refusal_and_unanalysed_have_distinct_numeric_states(tmp_path):
    from dataclasses import replace
    from stmdomains.analysis.domain_settings import DomainSettings
    from stmdomains.io.export_results import export_results, ExportOptions
    from stmdomains.tools.auto_classes_demo import create_auto_demo
    series = prepare_import(create_auto_demo(tmp_path / 'source')).series
    events = list(analyze_series(FramePresenter(series).analysis_input, frame_count=series.frame_count,
        series_id=series.identity, plan=SeriesAnalysisPlan(start=0, end=4, k=1, fit_source='selected_range', fit_end=0,
            domain_settings=DomainSettings(minimum_domain_size=500)), run_id='zero'))
    frames = {outcome.index: outcome.result for outcome in events[1:]}
    analysis = ProjectAnalysis('zero', tuple(range(5)), frames,
        {i: {'status': frame.status} for i, frame in frames.items()}, (events[0],))
    target = tmp_path / 'results'
    export_results(target, ProjectSnapshot(series, analysis=analysis), (0, 4), ExportOptions(png=False))
    with (target / 'frames.csv').open() as stream:
        first, empty = list(csv.DictReader(stream))
    assert first['analysis_status'] == 'complete' and first['domain_count'] == '0'
    assert first['assigned_count'] == first['approx_area_px2'] == '0'
    assert first['counts_status'] == 'complete'
    assert first['coverage_area_px2'] == first['physical_area_nm2'] == ''
    assert empty['analysis_status'] == 'no_annotations' and empty['domain_count'] == ''
    assert empty['assigned_count'] == empty['approx_area_px2'] == ''
    target = tmp_path / 'no-analysis'
    export_results(target, ProjectSnapshot(series), (0,), ExportOptions(png=False))
    with (target / 'frames.csv').open() as stream:
        missing = next(csv.DictReader(stream))
    assert missing['analysis_status'] == 'unanalysed' and missing['domain_count'] == ''


def test_export_cancel_failure_and_existing_folder_never_destroy_outputs(tmp_path, monkeypatch):
    import os
    import pytest
    from stmdomains.io.export_results import export_results, ExportOptions
    from stmdomains.io.project_archive import ProjectCancelled
    series = prepare_import(create_analysis_demo(tmp_path / 'source')['series']).series
    snapshot = ProjectSnapshot(series)
    target = tmp_path / 'results'
    cancelled = False
    def cancel(message):
        nonlocal cancelled
        cancelled = True
    with pytest.raises(ProjectCancelled):
        export_results(target, snapshot, (0, 1), ExportOptions(png=False), cancelled=lambda: cancelled, progress=cancel)
    assert not target.exists() and not list(tmp_path.glob('.stmdomains-export-*'))
    def fail(*args):
        raise OSError('publication failed')
    with monkeypatch.context() as patch:
        patch.setattr(os, 'replace', fail)
        with pytest.raises(OSError):
            export_results(target, snapshot, (0,), ExportOptions(png=False))
    assert not target.exists()
    target.mkdir()
    marker = target / 'keep.txt'
    marker.write_text('previous export')
    with pytest.raises(ValueError, match='już istnieje'):
        export_results(target, snapshot, (0,), ExportOptions(png=False))
    assert marker.read_text() == 'previous export'
    assert not list(tmp_path.glob('.stmdomains-export-*'))
