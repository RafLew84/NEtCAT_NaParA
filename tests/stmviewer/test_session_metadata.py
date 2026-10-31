"""A saved session restores its images, metadata, and active edit state."""
import json
from dataclasses import replace
from pathlib import Path

import numpy as np

from stmviewer.mpp import open_mpp_series

CPU = Path(__file__).parent / 'fixtures/registration/cpu.mpp'


def frames():
    return open_mpp_series(CPU, check_cancelled=lambda: None)


def test_original_session_keeps_values_metadata_and_display_without_source_access():
    from stmviewer.session_state import SessionState, SessionViewState, ViewTransform
    from stmviewer.session_metadata import encode_session, decode_session
    original = frames()
    display = SessionViewState(index=2, gamma=1.7, fps=10, loop=True,
                               navigation={'original': ViewTransform(2.4, (15.0, -12.0))})
    state = SessionState(original, display=display)
    manifest, arrays = encode_session(state)
    assert arrays['original/000000.npy'] is original[0].data
    restored = decode_session(json.loads(json.dumps(manifest)), arrays)
    assert restored.display == display
    assert restored.registration is None
    for before, after in zip(original, restored.frames):
        assert before.source == after.source
        assert before.raw_header == after.raw_header
        assert before.provenance == after.provenance
        assert before.metadata_note == after.metadata_note
        assert before.measurement_time_s == after.measurement_time_s
        np.testing.assert_array_equal(before.data, after.data)


def test_aligned_session_restores_pixels_two_overrides_and_allows_further_correction():
    from test_manual_movie import cpu_result, corrected_trial
    from stmviewer.manual_movie import apply_movie_correction, remove_movie_correction
    from stmviewer.session_state import SessionState, SessionViewState
    from stmviewer.session_metadata import encode_session, decode_session
    base = cpu_result()
    first = apply_movie_correction(base, corrected_trial(base, 1, 1, 0))
    both = apply_movie_correction(first, corrected_trial(first, 2, 0, 1))
    originals = tuple(frame.original for frame in both.frames)
    manifest, arrays = encode_session(SessionState(originals, both, SessionViewState(view='aligned')))
    assert arrays['aligned/000001.npy'] is both.frames[1].image.data
    loaded = decode_session(json.loads(json.dumps(manifest)), arrays)
    result = loaded.registration
    assert result is not None
    assert result.revision == both.revision
    assert result.baseline == both.baseline
    assert result.corrections == both.corrections
    assert result.canvas_shape == both.canvas_shape
    assert result.padding_ltrb == both.padding_ltrb
    assert result.pixel_size_nm == both.pixel_size_nm
    for index, (before, after) in enumerate(zip(both.frames, result.frames)):
        assert after.original is loaded.frames[index]
        assert after.shift_xy == before.shift_xy
        assert after.origin_xy == before.origin_xy
        assert after.image.alignment == before.image.alignment
        assert after.status == before.status
        assert after.quality_score == before.quality_score
        assert after.inherited_uncertainty == before.inherited_uncertainty
        np.testing.assert_array_equal(after.image.data, before.image.data)
        np.testing.assert_array_equal(after.valid_mask, before.valid_mask)
        assert not after.image.data.flags.writeable
    changed = apply_movie_correction(result, corrected_trial(result, 1, 1, 0))
    assert [f.shift_xy for f in changed.frames] == [(0, 0), (4, -1), (1, 2)]
    undone = remove_movie_correction(result, 1)
    assert [f.shift_xy for f in undone.frames] == [(0, 0), (2, -1), (-1, 2)]


def test_deleted_reference_keeps_historical_geometry_and_disabled_manual_editing():
    from test_manual_movie import cpu_result, corrected_trial
    from stmviewer.manual_movie import apply_movie_correction
    from stmviewer.session_state import SessionState
    from stmviewer.session_metadata import encode_session, decode_session
    base = cpu_result()
    corrected = apply_movie_correction(base, corrected_trial(base, 1, 1, 0))
    result = corrected.without_frame(0)
    assert result is not None
    loaded = decode_session(*encode_session(SessionState(tuple(f.original for f in result.frames), result)))
    restored = loaded.registration
    assert restored is not None
    assert not restored.corrections_editable
    assert restored.reference == corrected.reference
    assert restored.canvas_shape == corrected.canvas_shape
    assert restored.padding_ltrb == corrected.padding_ltrb
    assert restored.baseline == corrected.baseline
    assert restored.corrections == corrected.corrections
    for before, after in zip(result.frames, restored.frames):
        assert after.origin_xy == before.origin_xy
        assert after.shift_xy == before.shift_xy
        np.testing.assert_array_equal(after.image.data, before.image.data)


def test_imported_aligned_metadata_raw_headers_and_missing_pixels_survive():
    from test_manual_movie import cpu_result, corrected_trial
    from stmviewer.manual_movie import apply_movie_correction
    from stmviewer.alignment_metadata import aligned_export_frames
    from stmviewer.frame import FrameProvenance
    from stmviewer.session_state import SessionState
    from stmviewer.session_metadata import encode_session, decode_session
    base = cpu_result()
    corrected = apply_movie_correction(base, corrected_trial(base, 1, 1, 0))
    imported = aligned_export_frames(corrected, lambda: None)
    first = replace(imported[0], source=Path('/missing/computer/imported.mpp'),
                    raw_header={'source': 'scan', 'custom': {'unknown': '  a:2\nline\n'}},
                    bias_v=-0.2, setpoint_a=1.3e-12, scan_angle_deg=37.5,
                    provenance=FrameProvenance(r'C:\experiment\source.stp', None),
                    measurement_time_s=12.25, measurement_time_raw='00:12.25',
                    metadata_note='Metadata note', calibration_note='Calibration note')
    loaded = decode_session(*encode_session(SessionState((first, *imported[1:]))))
    restored = loaded.frames[0]
    for key in ('source', 'raw_header', 'bias_v', 'setpoint_a', 'scan_angle_deg', 'provenance',
                'measurement_time_s', 'measurement_time_raw', 'metadata_note', 'calibration_note', 'alignment'):
        assert getattr(restored, key) == getattr(first, key)
    assert loaded.frames[1].alignment.manual_movie.corrections == corrected.corrections
    assert any(np.isnan(frame.data).any() for frame in loaded.frames)
    for before, after in zip((first, *imported[1:]), loaded.frames):
        np.testing.assert_array_equal(after.data, before.data)


def test_pair_and_local_diagnostics_roundtrip_without_recomputing():
    from test_manual_movie import cpu_result
    from stmviewer.deep_ecc import HybridDiagnostics
    from stmviewer.local_consensus import LocalDiagnostics, LocalPatchEvidence
    from stmviewer.session_state import SessionState
    from stmviewer.session_metadata import encode_session, decode_session
    base = cpu_result()
    pair = HybridDiagnostics((2.2, -1.1), (2, -1), (-0.2, 0.1), 'ok', 0.91,
                             'ok', 0.82, 'Recorded settings', '/missing/outdoor.ckpt', 'cuda', 'CUDA')
    local = LocalDiagnostics((2.2, -1.1), (2, -1), (
        LocalPatchEvidence((4, 7, 16, 16), (2.0, 8.0, 16.0, 16.0), (2, -1),
                           0.8, 0.09, 'inlier', 'Measured support', 4.1),
        LocalPatchEvidence((24, 7, 16, 16), None, None, None, None, 'unmatched', 'No texture'),
    ), 'manual_review', 'Visual review', 'Recorded settings', '/missing/outdoor.ckpt', 'cuda', 'CUDA', 'ok', 0.91)
    result = replace(base, pair_diagnostics=(None, pair, None), local_diagnostics=(None, local, None))
    loaded = decode_session(*encode_session(SessionState(tuple(f.original for f in result.frames), result)))
    assert loaded.registration.pair_diagnostics == result.pair_diagnostics
    assert loaded.registration.local_diagnostics == result.local_diagnostics


def test_inconsistent_session_metadata_cannot_publish_a_partial_state():
    import copy
    import pytest
    from test_manual_movie import cpu_result, corrected_trial
    from stmviewer.manual_movie import apply_movie_correction
    from stmviewer.session_state import SessionState
    from stmviewer.session_metadata import encode_session, decode_session, session_array_shapes
    result = cpu_result()
    result = apply_movie_correction(result, corrected_trial(result, 1, 1, 0))
    state = SessionState(tuple(f.original for f in result.frames), result)
    valid, arrays = encode_session(state)
    mutations = [
        lambda record: record.update(schema='future-session'),
        lambda record: record['display'].update(index=10),
        lambda record: record['display'].update(gamma=float('nan')),
        lambda record: record['display'].update(fps=True),
        lambda record: record['display'].update(navigation={'original': {'zoom': 2, 'pan_xy': [float('inf'), 0]}}),
        lambda record: record['frames'][0].update(size_x_nm=-1),
        lambda record: record['frames'][0].update(source='/wrong/source.mpp'),
        lambda record: record['frames'][0].update(raw_header={'section': {'nontext': 1}}),
        lambda record: record['registration'].update(canvas_shape=[100, 200]),
        lambda record: record['registration'].update(revision='another-result'),
        lambda record: record['registration'].update(corrections_editable=1),
        lambda record: record['registration'].update(pixel_size_nm=[1, 2]),
        lambda record: record['registration']['frames'][1]['alignment'].update(origin_xy=[999, 999]),
        lambda record: record['registration']['frames'][1]['alignment'].pop('previous'),
        lambda record: record['manual_histories'][0]['corrections'][0].update(correction_xy=[500, 0]),
    ]
    for mutation in mutations:
        damaged = copy.deepcopy(valid)
        mutation(damaged)
        with pytest.raises(ValueError):
            decode_session(damaged, arrays)
    with pytest.raises(ValueError):
        decode_session(valid, {key: value for key, value in arrays.items() if key != 'aligned/000001.npy'})
    with pytest.raises(ValueError):
        decode_session(valid, arrays | {'original/000000.npy': arrays['original/000000.npy'].astype(np.float32)})
    shapes = session_array_shapes(valid)
    assert shapes['original/000000.npy'] == state.frames[0].data.shape
    assert shapes['aligned/000000.npy'] == result.canvas_shape
    # The valid state and buffers remain usable after every rejected candidate.
    loaded = decode_session(valid, arrays)
    assert loaded.registration.revision == result.revision


def test_nested_imported_history_survives_without_inventing_originals():
    from test_manual_movie import cpu_result, corrected_trial
    from stmviewer.manual_movie import apply_movie_correction
    from stmviewer.alignment_metadata import aligned_export_frames
    from stmviewer.frame import AlignmentHistory
    from stmviewer.session_state import SessionState
    from stmviewer.session_metadata import encode_session, decode_session
    base = cpu_result()
    result = apply_movie_correction(base, corrected_trial(base, 1, 1, 0))
    exported = aligned_export_frames(result, lambda: None)[1]
    previous = exported.alignment
    history = AlignmentHistory(
        previous.canvas_shape, (0, 0, 0, 0), previous.pixel_size_nm,
        previous.reference, 'Second historical registration', 'CPU', previous.canvas_shape,
        (exported.size_x_nm, exported.size_y_nm), (None, None), (0, 0), (0, 0),
        'ok', 1.0, False, previous,
    )
    historical = replace(exported, alignment=history)
    restored = decode_session(*encode_session(SessionState((historical,))))
    assert restored.registration is None
    assert restored.frames[0].alignment == history
    np.testing.assert_array_equal(restored.frames[0].data, historical.data)


def test_linux_windows_session_continues_manual_edits_exports_and_returns_to_linux(tmp_path, monkeypatch):
    from pathlib import PureWindowsPath
    from test_manual_movie import cpu_result, corrected_trial
    from stmviewer import session_paths
    from stmviewer.frame import FrameProvenance
    from stmviewer.manual_movie import apply_movie_correction
    from stmviewer.mpp_export import save_aligned_mpp
    from stmviewer.mpp import open_mpp_series
    from stmviewer.session_state import SessionState
    from stmviewer.session_metadata import encode_session, decode_session

    class WindowsSessionPath(PureWindowsPath):
        # Only the lexical path boundary is emulated. Output files stay in pytest's Linux directory.
        def resolve(self):
            return Path(self.as_posix()).resolve()

    from stmviewer.registration import register_series
    base = cpu_result()
    prior_provenance = FrameProvenance('historical/source.stp', 73)
    originals = tuple(replace(frame.original, provenance=prior_provenance if i == 2 else None)
                      for i, frame in enumerate(base.frames))
    result = register_series(originals)
    result = apply_movie_correction(result, corrected_trial(result, 1, 1, 0))
    manifest, arrays = encode_session(SessionState(originals, result))
    with monkeypatch.context() as windows:
        windows.setattr(session_paths, 'Path', WindowsSessionPath)
        loaded = decode_session(manifest, arrays)
        assert str(loaded.frames[0].source).startswith('\\home\\')
        assert loaded.frames[0].raw_header == originals[0].raw_header
        assert loaded.frames[0].provenance == (originals[0].provenance or FrameProvenance(
            str(originals[0].source), originals[0].source_frame_index))
        assert loaded.frames[2].provenance == prior_provenance
        assert loaded.registration.corrections[0].moving.source.startswith('\\home\\')
        changed = apply_movie_correction(loaded.registration, corrected_trial(loaded.registration, 1, 1, 0))
        assert [f.shift_xy for f in changed.frames] == [(0, 0), (4, -1), (1, 1)]
        export = save_aligned_mpp(tmp_path / 'on-windows.mpp', changed)
        exported = open_mpp_series(export, check_cancelled=lambda: None)
        for before, after in zip(changed.frames, exported):
            np.testing.assert_array_equal(before.image.data, after.data)
        saved_manifest, saved_arrays = encode_session(SessionState(loaded.frames, changed))
    returned = decode_session(saved_manifest, saved_arrays)
    assert returned.frames[0].provenance == loaded.frames[0].provenance
    assert returned.frames[0].raw_header == originals[0].raw_header
    continued = apply_movie_correction(returned.registration, corrected_trial(returned.registration, 2, 0, 1))
    assert [f.shift_xy for f in continued.frames] == [(0, 0), (4, -1), (1, 2)]
