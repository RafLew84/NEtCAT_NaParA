"""Portable lightweight trial documents bind estimates to original image content."""

from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import numpy as np

from stmviewer.series import open_frame_series

FIXTURES = Path(__file__).parent / 'fixtures'


def example_payload():
    return {
        'kind': 'series', 'outcome': 'complete', 'frame_count': 3, 'reference_index': 0,
        'method': 'phase_correlation', 'label': 'Phase', 'device': 'CPU',
        'settings_text': 'normalization=phase', 'settings': {'normalization': 'phase'},
        'error': None, 'manual_movie': None, 'code_revision': 'test-revision',
        'records': [
            {'index': 0, 'cumulative_xy': [0., 0.], 'shift_xy': None,
             'status': 'ok', 'quality_score': 1., 'inherited_uncertainty': False,
             'hybrid': None, 'local': None, 'manual': None},
            {'index': 1, 'cumulative_xy': [2.5, -1.], 'shift_xy': [2.5, -1.],
             'status': 'ok', 'quality_score': .9, 'inherited_uncertainty': False,
             'hybrid': None, 'local': None, 'manual': None},
            {'index': 2, 'cumulative_xy': [-1., 2.], 'shift_xy': [-3.5, 3.],
             'status': 'manual_review', 'quality_score': None, 'inherited_uncertainty': False,
             'hybrid': None, 'local': None, 'manual': None},
        ],
    }


def test_saved_trial_reopens_with_exact_estimates_and_settings_without_images(tmp_path):
    from stmviewer.trial_document import TrialDocument, load_trial, save_trial

    frames = open_frame_series([FIXTURES / 'mpp/known-times.mpp'])
    path = tmp_path / 'phase.stmtrial.json'
    saved = save_trial(path, TrialDocument(example_payload()), frames)
    loaded = load_trial(path, frames)
    assert loaded.payload['records'][1]['cumulative_xy'] == [2.5, -1.]
    assert loaded.payload['records'][2]['shift_xy'] == [-3.5, 3.]
    assert loaded.payload['settings'] == {'normalization': 'phase'}
    assert loaded.payload['code_revision'] == 'test-revision'
    assert loaded == saved
    assert len(loaded.sources) == 3
    assert 'array' not in path.read_text() and 'pixels' not in path.read_text()


def test_relocated_identical_source_is_accepted_but_content_order_and_geometry_are_not(tmp_path):
    import shutil
    import pytest
    from stmviewer.trial_document import TrialDocument, TrialDocumentError, load_trial, save_trial

    source = FIXTURES / 'mpp/known-times.mpp'
    frames = open_frame_series([source])
    path = tmp_path / 'phase.stmtrial.json'
    save_trial(path, TrialDocument(example_payload()), frames)
    moved = tmp_path / 'renamed.mpp'
    shutil.copyfile(source, moved)
    relocated = open_frame_series([moved])
    loaded = load_trial(path, relocated)
    assert loaded.sources[0].source == str(moved.resolve())
    assert loaded.payload['records'][1]['cumulative_xy'] == [2.5, -1.]
    for wrong in (tuple(reversed(relocated)), relocated[:2],
                  (replace(relocated[0], size_x_nm=17.), *relocated[1:]),
                  (replace(relocated[0], source_frame_index=12), *relocated[1:]),
                  (replace(relocated[0], data=np.ones((3, 4))), *relocated[1:])):
        with pytest.raises(TrialDocumentError, match='źród|klatek|kolejno|geometri'):
            load_trial(path, wrong)


def test_corrupt_documents_unknown_versions_and_impossible_results_are_rejected(tmp_path):
    import json
    import pytest
    from stmviewer.trial_document import TrialDocument, TrialDocumentError, load_trial, save_trial

    frames = open_frame_series([FIXTURES / 'mpp/known-times.mpp'])
    path = tmp_path / 'phase.stmtrial.json'
    save_trial(path, TrialDocument(example_payload()), frames)
    valid = json.loads(path.read_text())
    variants = []
    for key, value in (('version', 23), ('format', 'some-other-format'), ('sources', [])):
        broken = deepcopy(valid)
        broken[key] = value
        variants.append(broken)
    for mutate in (
        lambda p: p.update(frame_count=2),
        lambda p: p.update(outcome='invented'),
        lambda p: p['records'][1].update(cumulative_xy=[float('nan'), 0]),
        lambda p: p['records'][1].update(cumulative_xy=None),
        lambda p: p['records'][1].update(index=0),
        lambda p: p['records'][1].update(quality_score=5),
        lambda p: p['records'][1].update(status='manual', quality_score=.9),
    ):
        broken = deepcopy(valid)
        mutate(broken['trial'])
        variants.append(broken)
    for broken in variants:
        path.write_text(json.dumps(broken))
        with pytest.raises(TrialDocumentError):
            load_trial(path, frames)
    for text in ('{', 'null', '[]', '{"format": 3}', '{"version": 1, "version": 2}'):
        path.write_text(text)
        with pytest.raises(TrialDocumentError):
            load_trial(path, frames)


def test_cancelling_publish_keeps_existing_document_and_does_not_leave_temporary_files(tmp_path):
    import pytest
    from stmviewer.trial_document import TrialCancelled, TrialDocument, load_trial, save_trial

    frames = open_frame_series([FIXTURES / 'mpp/known-times.mpp'])
    path = tmp_path / 'phase.stmtrial.json'
    save_trial(path, TrialDocument(example_payload()), frames)
    before = path.read_bytes()
    cancelled = False
    messages = []

    def progress(done, total, description):
        nonlocal cancelled
        messages.append(description)
        if description.startswith('Zapisywanie'):
            cancelled = True

    changed = example_payload()
    changed['label'] = 'Anulowana próba'
    with pytest.raises(TrialCancelled):
        save_trial(path, TrialDocument(changed), frames, progress=progress,
                   cancelled=lambda: cancelled)
    assert path.read_bytes() == before
    assert list(tmp_path.iterdir()) == [path]
    assert any(message.startswith('Sprawdzanie') for message in messages)
    assert load_trial(path, frames).payload['label'] == 'Phase'


def test_manual_pair_retains_fractional_start_and_no_confidence_and_rejects_invented_correction(tmp_path):
    import json
    import pytest
    from test_manual_pair import automatic_trial, pair_frames
    from stmviewer.manual_pair import ManualPairDraft
    from stmviewer.trial_capture import from_pair, pair_from_document
    from stmviewer.trial_document import TrialDocumentError, load_trial, save_trial

    frames = pair_frames()
    draft = ManualPairDraft(*frames, start=automatic_trial(*frames))
    draft.nudge(1, 0)
    draft.nudge(0, -1)
    approved = draft.apply()
    path = tmp_path / 'manual.stmtrial.json'
    save_trial(path, from_pair(approved, frames), frames)
    loaded = load_trial(path, frames)
    restored = pair_from_document(loaded, frames)
    assert restored.shift_xy == (3.4, -2.25)
    assert restored.manual.start_xy == (2.4, -1.25)
    assert restored.manual.correction_xy == (1, -1)
    assert 'Phase' in restored.manual.source_label
    assert restored.status == 'manual' and restored.quality_score is None
    broken = json.loads(path.read_text())
    broken['trial']['records'][0]['manual']['correction_xy'] = [5, 5]
    path.write_text(json.dumps(broken))
    with pytest.raises(TrialDocumentError, match='ręcz|korekt|Korekt'):
        load_trial(path, frames)


def test_manual_movie_retains_two_overrides_baseline_and_rejects_changed_history(tmp_path):
    import json
    import pytest
    from test_manual_movie import corrected_trial, cpu_result
    from stmviewer.manual_movie import apply_movie_correction
    from stmviewer.trial_capture import from_registration
    from stmviewer.trial_document import TrialDocumentError, load_trial, save_trial

    baseline = cpu_result()
    first = apply_movie_correction(baseline, corrected_trial(baseline, 1, 1, 0))
    both = apply_movie_correction(first, corrected_trial(first, 2, 0, 1))
    frames = tuple(frame.original for frame in both.frames)
    path = tmp_path / 'corrected.stmtrial.json'
    save_trial(path, from_registration(both), frames)
    loaded = load_trial(path, frames)
    assert [r['cumulative_xy'] for r in loaded.payload['records']] == [[0, 0], [3, -1], [0, 2]]
    history = loaded.payload['manual_movie']
    assert [b['shift_xy'] for b in history['baseline']] == [[0, 0], [2, -1], [-1, 1]]
    assert [r['shift_xy'] for r in history['corrections']] == [[3, -1], [-3, 3]]
    assert [r['quality_score'] for r in loaded.payload['records']] == [1, None, None]
    for mutate in (
        lambda p: p['manual_movie']['baseline'][1].update(shift_xy=[100, 100]),
        lambda p: p['records'][2].update(cumulative_xy=[100, 100]),
    ):
        broken = json.loads(path.read_text())
        mutate(broken['trial'])
        target = tmp_path / 'invalid.stmtrial.json'
        target.write_text(json.dumps(broken))
        with pytest.raises(TrialDocumentError):
            load_trial(target, frames)


def test_save_cannot_rebind_loaded_estimates_or_overwrite_source_files(tmp_path):
    import shutil
    import pytest
    from stmviewer.trial_document import TrialDocument, TrialDocumentError, load_trial, save_trial

    source = tmp_path / 'input.mpp'
    shutil.copyfile(FIXTURES / 'mpp/known-times.mpp', source)
    frames = open_frame_series([source])
    destination = tmp_path / 'phase.stmtrial.json'
    bound = save_trial(destination, TrialDocument(example_payload()), frames)
    wrong = (replace(frames[0], data=np.zeros((3, 4))), *frames[1:])
    with pytest.raises(TrialDocumentError):
        save_trial(destination, bound, wrong)
    assert load_trial(destination, frames).payload['label'] == 'Phase'
    before = source.read_bytes()
    for target in (source, source.with_name(source.name + '.stmviewer.json')):
        with pytest.raises(TrialDocumentError, match='źródł|metadan'):
            save_trial(target, bound, frames)
    assert source.read_bytes() == before


def test_stage_diagnostics_roundtrip_and_malformed_evidence_is_rejected(tmp_path):
    from dataclasses import asdict
    import json
    import pytest
    from stmviewer.deep_ecc import HybridDiagnostics, HybridFailure
    from stmviewer.local_consensus import LocalDiagnostics, LocalPatchEvidence
    from stmviewer.trial_document import TrialDocument, TrialDocumentError, load_trial, save_trial

    frames = open_frame_series([FIXTURES / 'mpp/known-times.mpp'])
    hybrid = HybridDiagnostics((2, -1), (2.5, -1), (.5, 0), 'ok', .8, 'ok', .95,
                               'deep+ECC', '/weights.ckpt', 'CPU', 'CPU')
    local = LocalDiagnostics((2, -1), (2.5, -1), (
        LocalPatchEvidence((0, 0, 16, 16), (2., 1., 16., 16.), (2.5, -1), .8, .2,
                           'inlier', 'zgodny fragment', 5.),
    ), 'manual_review', 'konsensus', 'local settings')
    payload = example_payload()
    payload['records'][1].update(hybrid=asdict(hybrid), local=asdict(local))
    path = tmp_path / 'diagnostics.stmtrial.json'
    save_trial(path, TrialDocument(payload), frames)
    loaded = load_trial(path, frames)
    assert loaded.payload['records'][1]['hybrid']['deep_shift_xy'] == [2, -1]
    assert loaded.payload['records'][1]['local']['patches'][0]['reference_rect'] == [0, 0, 16, 16]
    original = json.loads(path.read_text())
    for mutate in (
        lambda r: r['hybrid'].update(unexpected=4),
        lambda r: r['hybrid'].pop('deep_shift_xy'),
        lambda r: r['hybrid'].update(correction_xy=[50, 50]),
        lambda r: r['local']['patches'][0].update(reference_rect=[0, 0, -1, 16]),
        lambda r: r['local']['patches'][0].update(status='made-up'),
        lambda r: r['local'].update(patches='corrupt'),
    ):
        broken = deepcopy(original)
        mutate(broken['trial']['records'][1])
        path.write_text(json.dumps(broken))
        with pytest.raises(TrialDocumentError):
            load_trial(path, frames)
    partial = example_payload()
    partial.update(outcome='failed', error='ECC refused')
    partial['records'] = partial['records'][:2]
    partial['records'][1].update(shift_xy=None, cumulative_xy=None, quality_score=None,
                                 status='failed', hybrid=asdict(HybridFailure(
                                     'ECC', 'ECC refused', (2, -1), 'ok', .8,
                                     'deep+ECC', '/weights.ckpt', 'CPU', 'CPU')))
    save_trial(path, TrialDocument(partial), frames)
    loaded = load_trial(path, frames)
    assert loaded.payload['outcome'] == 'failed'
    assert loaded.payload['records'][1]['hybrid']['deep_shift_xy'] == [2, -1]
    assert loaded.payload['records'][1]['shift_xy'] is None


def test_manual_history_after_deletion_stays_bound_through_relocation_and_resave(tmp_path):
    import json
    import shutil
    import pytest
    from test_manual_movie import corrected_trial, cpu_result
    from stmviewer.manual_movie import apply_movie_correction
    from stmviewer.trial_capture import from_registration
    from stmviewer.trial_document import TrialDocumentError, load_trial, save_trial

    baseline = cpu_result()
    first = apply_movie_correction(baseline, corrected_trial(baseline, 1, 1, 0))
    both = apply_movie_correction(first, corrected_trial(first, 2, 0, 1))
    remaining = both.without_frame(0)
    frames = tuple(frame.original for frame in remaining.frames)
    path = tmp_path / 'remaining.stmtrial.json'
    save_trial(path, from_registration(remaining), frames)
    moved = tmp_path / 'moved.mpp'
    shutil.copyfile(frames[0].source, moved)
    relocated = open_frame_series([moved])[1:]
    loaded = load_trial(path, relocated)
    saved_again = tmp_path / 'resaved.stmtrial.json'
    save_trial(saved_again, loaded, relocated)
    restored = load_trial(saved_again, relocated)
    assert [r['cumulative_xy'] for r in restored.payload['records']] == [[3, -1], [0, 2]]
    broken = json.loads(saved_again.read_text())
    for item in broken['trial']['manual_movie']['baseline']:
        item['shift_xy'][0] += 1
    saved_again.write_text(json.dumps(broken))
    with pytest.raises(TrialDocumentError, match='histor|Korekt|korekt'):
        load_trial(saved_again, relocated)


def test_source_schema_payload_bounds_and_pair_quality_are_checked_before_open(tmp_path):
    import json
    import pytest
    from stmviewer.trial_document import TrialDocument, TrialDocumentError, load_trial, save_trial

    frames = open_frame_series([FIXTURES / 'mpp/known-times.mpp'])
    path = tmp_path / 'trial.stmtrial.json'
    save_trial(path, TrialDocument(example_payload()), frames)
    valid = json.loads(path.read_text())
    for key, value in (('source_group', False), ('shape', [3., 4.]), ('source', {})):
        broken = deepcopy(valid)
        broken['sources'][0][key] = value
        path.write_text(json.dumps(broken))
        with pytest.raises(TrialDocumentError):
            load_trial(path, frames)
    broken = deepcopy(valid)
    broken['trial']['records'][1].update(pair_status='ok', pair_quality_score=5)
    path.write_text(json.dumps(broken))
    with pytest.raises(TrialDocumentError):
        load_trial(path, frames)
    with path.open('wb') as stream:
        stream.truncate(64 * 1024 * 1024 + 1)
    with pytest.raises(TrialDocumentError, match='rozmiar|duży'):
        load_trial(path, frames)
