"""A project opens from its own bytes, with images, annotations and view intact."""

import numpy as np

from stmdomains.core.frame_presentation import FramePresenter
from stmdomains.core.project import ProjectSnapshot
from stmdomains.io.moltrack_import import prepare_import
from stmdomains.io.project import open_project, save_project
from stmdomains.tools.analysis_demo import create_analysis_demo


def test_unanalysed_project_is_self_contained_and_keeps_view_and_source_mapping(tmp_path):
    source = create_analysis_demo(tmp_path / 'input')['series']
    series = prepare_import(source).series
    view = {'current_index': 1, 'mode': 'expanded_aligned', 'gamma': 1.3}
    draft = {'class_count_mode': 'auto', 'auto_max_k': 4}
    saved = ProjectSnapshot(series, view=view, draft=draft)
    target = tmp_path / 'work.stmdomains'
    original = series.source_path.read_bytes()
    save_project(target, saved)
    series.source_path.unlink()
    source.unlink()
    opened = open_project(target)
    assert opened.analysis is None and opened.view == view and opened.draft == draft
    assert opened.series.source_path.read_bytes() == original
    assert opened.series.source_frame_indices == series.source_frame_indices
    assert opened.series.source_sha256 == series.source_sha256
    assert opened.series.identity != series.identity
    np.testing.assert_array_equal(opened.series.raw_frames, series.raw_frames)
    expected = FramePresenter(series).present(1, view['mode'], view['gamma'])
    actual = FramePresenter(opened.series).present(1, view['mode'], view['gamma'])
    np.testing.assert_array_equal(actual.rendered.rgba, expected.rendered.rgba)
    assert actual.annotations.detections == expected.annotations.detections
    assert opened.series.provenance['input_session_sha256']


def test_partial_analysis_round_trip_keeps_catalogue_memberships_and_exact_preview(tmp_path, monkeypatch):
    from dataclasses import replace
    from stmdomains.analysis.series_analysis import analyze_series
    from stmdomains.analysis.series_settings import SeriesAnalysisPlan
    from stmdomains.core.project import ProjectAnalysis
    from stmdomains.tools.auto_classes_demo import create_auto_demo
    from sklearn.cluster import KMeans
    from sklearn.decomposition import PCA
    series = prepare_import(create_auto_demo(tmp_path / 'input')).series
    presenter = FramePresenter(series)
    events = analyze_series(presenter.analysis_input, frame_count=5, series_id=series.identity,
                            plan=SeriesAnalysisPlan(end=1, class_count_mode='auto'), run_id='selected-run')
    catalogue, frame = next(events), next(events)
    result = frame.result
    analysis = ProjectAnalysis('selected-run', (0, 1), {0: result},
                               {0: {'status': 'complete'}, 1: {'status': 'not_run', 'message': 'Anulowano'}},
                               (catalogue,), {'phase': 'cancelled', 'selection': catalogue.state['class_selection']})
    snapshot = ProjectSnapshot(series, {'current_index': 0, 'mode': 'raw', 'gamma': 1.2},
                               {'class_count_mode': 'manual', 'k': 5}, analysis)
    path = tmp_path / 'partial.stmdomains'
    save_project(path, snapshot)
    def no_fit(*args, **kwargs):
        raise AssertionError('Opening a project must not train PCA/KMeans')
    monkeypatch.setattr(PCA, 'fit', no_fit)
    monkeypatch.setattr(KMeans, 'fit', no_fit)
    series.source_path.unlink()
    series.session_path.unlink()
    opened = open_project(path)
    restored = opened.analysis.frames[0]
    assert opened.analysis.identifier == 'selected-run' and opened.analysis.indices == (0, 1)
    assert 1 not in opened.analysis.frames and opened.analysis.statuses[1]['status'] == 'not_run'
    assert restored.catalogue.identifier == catalogue.identifier
    assert restored.catalogue.series_id == opened.series.identity != series.identity
    assert restored.assignments == result.assignments and restored.metadata == result.metadata
    assert restored.parameters == result.parameters and opened.draft['k'] == 5
    np.testing.assert_array_equal(restored.domain_labels, result.domain_labels)
    actual = FramePresenter(opened.series).present(0, 'raw', 1.2, result=restored)
    expected = presenter.present(0, 'raw', 1.2, result=result)
    np.testing.assert_array_equal(actual.rendered.rgba, expected.rendered.rgba)
    second = tmp_path / 'copy.stmdomains'
    save_project(second, opened)
    assert open_project(second).analysis.identifier == 'selected-run'
    # Preview remains available even when no reusable fitting state exists.
    without_model = replace(result, catalogue=None)
    analysis = replace(analysis, frames={0: without_model}, catalogues=())
    save_project(tmp_path / 'preview.stmdomains', replace(snapshot, series=opened.series,
                  analysis=replace(analysis, frames={0: replace(without_model, series_id=opened.series.identity)})))
    preview = open_project(tmp_path / 'preview.stmdomains').analysis.frames[0]
    assert preview.catalogue is None and preview.assignments == result.assignments
    assert preview.metadata['model_id'] == result.metadata['model_id']


def test_atomic_save_cancel_failure_and_changed_mpp_preserve_previous_file(tmp_path, monkeypatch):
    import os
    import pytest
    from stmdomains.io.project import ProjectCancelled, ProjectError
    series = prepare_import(create_analysis_demo(tmp_path / 'input')['single']).series
    snapshot = ProjectSnapshot(series)
    path = tmp_path / 'work.stmdomains'
    save_project(path, snapshot)
    before = path.read_bytes()
    cancelled = False
    def report(message):
        nonlocal cancelled
        cancelled = True
    with pytest.raises(ProjectCancelled):
        save_project(path, snapshot, cancelled=lambda: cancelled, progress=report)
    assert path.read_bytes() == before
    def fail_replace(*args):
        raise OSError('disk publication failed')
    with monkeypatch.context() as patch:
        patch.setattr(os, 'replace', fail_replace)
        with pytest.raises(OSError):
            save_project(path, snapshot)
    assert path.read_bytes() == before
    with series.source_path.open('r+b') as stream:
        stream.seek(-1, 2)
        stream.write(b'X')
    with pytest.raises(ProjectError, match='MPP zmienił'):
        save_project(path, snapshot)
    assert path.read_bytes() == before and not list(tmp_path.glob('.*.tmp'))
    assert open_project(path).analysis is None


def rewrite_part(path, name, replacement, *, refresh_hash=False):
    import hashlib
    import json
    import zipfile
    with zipfile.ZipFile(path) as archive:
        parts = {n: archive.read(n) for n in archive.namelist()}
    parts[name] = replacement
    if refresh_hash:
        manifest = json.loads(parts['manifest.json'])
        manifest['entries'][name] = {'size': len(replacement), 'sha256': hashlib.sha256(replacement).hexdigest()}
        parts['manifest.json'] = json.dumps(manifest).encode()
    with zipfile.ZipFile(path, 'w') as archive:
        for key, data in parts.items():
            archive.writestr(key, data)


def test_integrity_unknown_version_bad_mapping_and_invalid_view_are_refused(tmp_path):
    import json
    import pytest
    import zipfile
    from stmdomains.io.project import ProjectError
    series = prepare_import(create_analysis_demo(tmp_path / 'input')['single']).series
    path = tmp_path / 'work.stmdomains'
    save_project(path, ProjectSnapshot(series))
    before = path.read_bytes()
    with zipfile.ZipFile(path) as archive:
        manifest, record = json.loads(archive.read('manifest.json')), json.loads(archive.read('project.json'))
    cases = [('input.json', b'{}', False),
             ('manifest.json', json.dumps({**manifest, 'version': 99}).encode(), False),
             ('project.json', json.dumps({**record, 'source_frame_indices': [99]}).encode(), True),
             ('project.json', json.dumps({**record, 'view': {'gamma': -1}}).encode(), True)]
    for name, content, checksums in cases:
        path.write_bytes(before)
        rewrite_part(path, name, content, refresh_hash=checksums)
        with pytest.raises(ProjectError):
            open_project(path)


def test_invalid_result_references_and_execution_never_publish_a_project(tmp_path):
    import json
    import zipfile
    from dataclasses import replace
    import pytest
    from stmdomains.analysis.series_analysis import analyze_series
    from stmdomains.analysis.series_settings import SeriesAnalysisPlan
    from stmdomains.core.project import ProjectAnalysis
    from stmdomains.io.project import ProjectError
    series = prepare_import(create_analysis_demo(tmp_path / 'input')['single']).series
    presenter = FramePresenter(series)
    events = analyze_series(presenter.analysis_input, frame_count=1, series_id=series.identity,
                            plan=SeriesAnalysisPlan(k=4), run_id='run')
    catalogue, outcome = next(events), next(events)
    result = outcome.result
    analysis = ProjectAnalysis('run', (0,), {0: result}, {0: {'status': result.status}}, (catalogue,))
    path = tmp_path / 'work.stmdomains'
    save_project(path, ProjectSnapshot(series, analysis=analysis))
    before = path.read_bytes()
    broken = replace(result, assignments={})
    with pytest.raises(ProjectError, match='Przypisania'):
        save_project(path, ProjectSnapshot(series, analysis=replace(analysis, frames={0: broken})))
    assert path.read_bytes() == before
    with zipfile.ZipFile(path) as archive:
        frame = json.loads(archive.read('frames/0.json'))
        record = json.loads(archive.read('project.json'))
    frame['assignments'].pop(next(iter(frame['assignments'])))
    rewrite_part(path, 'frames/0.json', json.dumps(frame).encode(), refresh_hash=True)
    with pytest.raises(ProjectError, match='Przypisania'):
        open_project(path)
    path.write_bytes(before)
    record['analysis']['execution'] = {'phase': 'analysing'}
    rewrite_part(path, 'project.json', json.dumps(record).encode(), refresh_hash=True)
    with pytest.raises(ProjectError, match='stan wykonania'):
        open_project(path)
    path.write_bytes(before)
    with zipfile.ZipFile(path) as archive:
        manifest = json.loads(archive.read('manifest.json'))
    manifest['entries']['../outside.json'] = {'size': 0, 'sha256': '0' * 64}
    rewrite_part(path, 'manifest.json', json.dumps(manifest).encode())
    with pytest.raises(ProjectError):
        open_project(path)
    assert not (tmp_path / 'outside.json').exists()
