"""A portable session restores measurement pixels without external source files."""
from dataclasses import replace

import numpy as np

from make_registration_fixtures import frames_with_data


def test_session_is_self_contained_and_preserves_exact_float_samples(tmp_path):
    from stmviewer.session_archive import load_session, save_session
    from stmviewer.session_state import SessionState

    samples = np.array([[np.nextafter(1., 2.), -0., np.nan], [np.inf, -np.inf, np.nextafter(0., 1.)]])
    frame = replace(frames_with_data(samples)[0], source=tmp_path / 'missing-source.stp')
    destination = tmp_path / 'portable.stmsession'
    assert save_session(destination, SessionState((frame,))) == destination
    relocated = tmp_path / 'elsewhere' / 'renamed.stmsession'
    relocated.parent.mkdir()
    destination.replace(relocated)
    restored = load_session(relocated)
    assert restored.frames[0].data.tobytes() == samples.tobytes()
    assert not restored.frames[0].data.flags.writeable
    assert restored.frames[0].source == frame.source
    assert restored.frames[0].raw_header == frame.raw_header
    assert restored.registration is None


def test_cancel_and_failed_publish_keep_previous_session_readable(tmp_path, monkeypatch):
    import os
    from threading import Event
    import pytest
    from stmviewer.session_archive import load_session, save_session, SessionCancelled, SessionError
    from stmviewer.session_state import SessionState

    first = SessionState(frames_with_data(np.arange(12.).reshape(3, 4)))
    second = SessionState(frames_with_data(np.full((3, 4), 100.)))
    destination = tmp_path / 'work.stmsession'
    save_session(destination, first)
    previous_bytes = destination.read_bytes()
    stop = Event()
    with pytest.raises(SessionCancelled):
        save_session(destination, second, cancelled=stop.is_set,
                     progress=lambda done, total, text: stop.set() if done == total else None)
    assert destination.read_bytes() == previous_bytes
    assert list(tmp_path.glob('.*.tmp')) == []
    def deny_publish(*args, **kwargs):
        raise OSError('controlled publish failure')
    monkeypatch.setattr(os, 'replace', deny_publish)
    with pytest.raises(SessionError, match='controlled publish failure'):
        save_session(destination, second)
    assert destination.read_bytes() == previous_bytes
    np.testing.assert_array_equal(load_session(destination).frames[0].data, first.frames[0].data)
    assert list(tmp_path.glob('.*.tmp')) == []


def test_saved_aligned_session_keeps_two_manual_edits_and_export_values(tmp_path):
    from test_manual_movie import cpu_result, corrected_trial
    from stmviewer.manual_movie import apply_movie_correction
    from stmviewer.mpp import open_mpp_series
    from stmviewer.mpp_export import save_aligned_mpp
    from stmviewer.session_archive import save_session, load_session
    from stmviewer.session_state import SessionState, SessionViewState, ViewTransform

    result = cpu_result()
    result = apply_movie_correction(result, corrected_trial(result, 1, 1, 0))
    result = apply_movie_correction(result, corrected_trial(result, 2, 0, 1))
    display = SessionViewState(index=1, view='aligned', gamma=1.8, fps=7, loop=True,
                               navigation={'aligned': ViewTransform(2., (-13., 21.))})
    state = SessionState(tuple(f.original for f in result.frames), result, display)
    destination = tmp_path / 'edited.stmsession'
    save_session(destination, state)
    loaded = load_session(destination)
    assert loaded.display == display
    assert loaded.registration is not None
    assert loaded.registration.baseline == result.baseline
    assert loaded.registration.corrections == result.corrections
    assert loaded.registration.revision == result.revision
    for expected, actual in zip(result.frames, loaded.registration.frames):
        assert actual.image.data.tobytes() == expected.image.data.tobytes()
        assert actual.original.data.tobytes() == expected.original.data.tobytes()
        np.testing.assert_array_equal(actual.valid_mask, expected.valid_mask)
    continued = apply_movie_correction(loaded.registration, corrected_trial(loaded.registration, 1, 1, 0))
    assert [f.shift_xy for f in continued.frames] == [(0, 0), (4, -1), (1, 2)]
    exported = save_aligned_mpp(tmp_path / 'restored.mpp', loaded.registration)
    reopened = open_mpp_series(exported, check_cancelled=lambda: None)
    for before, after in zip(result.frames, reopened):
        np.testing.assert_array_equal(after.data, before.image.data)
        assert after.source_frame_index == before.image.source_frame_index
        assert after.measurement_time_s == before.image.measurement_time_s


def test_untrusted_archive_rejected_before_allocating_declared_image(tmp_path, monkeypatch):
    import io
    import json
    import zipfile
    import pytest
    from stmviewer.session_archive import load_session, save_session, SessionError
    from stmviewer.session_state import SessionState

    destination = tmp_path / 'valid.stmsession'
    save_session(destination, SessionState(frames_with_data(np.arange(12.).reshape(3, 4))))
    with zipfile.ZipFile(destination) as archive:
        contents = {name: archive.read(name) for name in archive.namelist()}
    source_manifest = json.loads(contents['manifest.json'])
    array_name = 'original/000000.npy'
    wrong_shape = io.BytesIO()
    np.save(wrong_shape, np.arange(12.).reshape(4, 3), allow_pickle=False)
    object_array = io.BytesIO()
    np.save(object_array, np.full((3, 4), 'pickle payload', dtype=object), allow_pickle=True)
    oversized = json.loads(contents['manifest.json'])
    oversized['state']['frames'][0]['shape'] = [65536, 65536]
    unknown = dict(source_manifest, version=2)
    variants = [
        ('unknown-version', {'manifest.json': json.dumps(unknown).encode()}),
        ('wrong-dimensions', {array_name: wrong_shape.getvalue()}),
        ('object-dtype', {array_name: object_array.getvalue()}),
        ('extra-samples', {array_name: contents[array_name] + b'\x00'}),
        ('truncated-samples', {array_name: contents[array_name][:-1]}),
        ('oversized-declaration', {'manifest.json': json.dumps(oversized).encode()}),
        ('oversized-npy-header', {array_name: b'\x93NUMPY\x02\x00' + (2**30).to_bytes(4, 'little')
                                  + contents[array_name][12:]}),
        ('foreign-path', {'../original/extra.npy': contents[array_name]}),
        ('duplicate-json-key', {'manifest.json': contents['manifest.json'].replace(
            b'"version":1', b'"version":1,"version":1')}),
    ]
    for label, replacements in variants:
        damaged = tmp_path / f'{label}.stmsession'
        with zipfile.ZipFile(damaged, 'w') as archive:
            for name, payload in (contents | replacements).items():
                archive.writestr(name, payload)

    def no_allocation(*args, **kwargs):
        raise AssertionError('Malformed headers must be rejected before pixel allocation.')
    monkeypatch.setattr(np, 'empty', no_allocation)
    for label, _ in variants:
        with pytest.raises(SessionError):
            load_session(tmp_path / f'{label}.stmsession')


def test_zip_integrity_duplicates_missing_members_and_load_cancel(tmp_path):
    import zipfile
    from threading import Event
    import pytest
    from stmviewer.session_archive import load_session, save_session, SessionError, SessionCancelled
    from stmviewer.session_state import SessionState

    destination = tmp_path / 'valid.stmsession'
    save_session(destination, SessionState(frames_with_data(np.arange(12.).reshape(3, 4))))
    with zipfile.ZipFile(destination) as archive:
        contents = {name: archive.read(name) for name in archive.namelist()}
    duplicate = tmp_path / 'duplicate.stmsession'
    with zipfile.ZipFile(duplicate, 'w') as archive:
        for name, payload in contents.items():
            archive.writestr(name, payload)
        with pytest.warns(UserWarning, match='Duplicate name'):
            archive.writestr('manifest.json', contents['manifest.json'])
    missing = tmp_path / 'missing.stmsession'
    with zipfile.ZipFile(missing, 'w') as archive:
        archive.writestr('manifest.json', contents['manifest.json'])
    damaged = tmp_path / 'damaged.stmsession'
    with zipfile.ZipFile(damaged, 'w') as archive:
        for name, payload in contents.items():
            archive.writestr(name, payload)
    encoded = bytearray(damaged.read_bytes())
    index = encoded.index(b'\x93NUMPY')
    encoded[index + 128] ^= 1
    damaged.write_bytes(encoded)
    truncated = tmp_path / 'truncated.stmsession'
    truncated.write_bytes(destination.read_bytes()[:-100])
    for bad in (duplicate, missing, damaged, truncated):
        with pytest.raises(SessionError):
            load_session(bad)
    stop = Event()
    with pytest.raises(SessionCancelled):
        load_session(destination, cancelled=stop.is_set,
                     progress=lambda done, total, text: stop.set() if done else None)
    assert load_session(destination).frames[0].data.shape == (3, 4)


def test_session_save_cannot_overwrite_image_or_metadata_source(tmp_path):
    import pytest
    from stmviewer.session_archive import save_session, SessionError
    from stmviewer.session_state import SessionState

    source = tmp_path / 'source.mpp'
    sidecar = tmp_path / 'source.mpp.stmviewer.json'
    source.write_bytes(b'original data')
    sidecar.write_text('original metadata')
    state = SessionState(tuple(replace(f, source=source) for f in frames_with_data(np.ones((3, 4)))))
    for protected in (source, sidecar):
        before = protected.read_bytes()
        with pytest.raises(SessionError, match='źródłowego'):
            save_session(protected, state)
        assert protected.read_bytes() == before


def test_corrupt_compressed_payload_is_reported_as_session_error(tmp_path):
    import struct
    import zipfile
    import pytest
    from stmviewer.session_archive import save_session, load_session, SessionError
    from stmviewer.session_state import SessionState

    path = tmp_path / 'compression-corrupt.stmsession'
    save_session(path, SessionState(frames_with_data(np.arange(1200.).reshape(30, 40))))
    with zipfile.ZipFile(path) as archive:
        info = archive.getinfo('original/000000.npy')
    content = bytearray(path.read_bytes())
    name_length, extra_length = struct.unpack_from('<HH', content, info.header_offset + 26)
    payload = info.header_offset + 30 + name_length + extra_length
    content[payload:payload + 16] = b'\xff' * 16
    path.write_bytes(content)
    with pytest.raises(SessionError):
        load_session(path)
