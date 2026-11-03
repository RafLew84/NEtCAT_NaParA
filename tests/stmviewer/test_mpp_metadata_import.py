"""Metadata pairs through the public complete-series importer."""

from pathlib import Path
import numpy as np
import pytest

from stmviewer.series import open_frame_series

FIXTURES = Path(__file__).parent / 'fixtures' / 'mpp-metadata'


def test_pair_restores_individual_metadata_without_changing_movie_pixels():
    frames = open_frame_series([FIXTURES / 'mixed.MPP'])

    assert [frame.channel for frame in frames] == ['Topo', 'Current', None]
    assert [frame.signal_unit for frame in frames] == ['nm', 'nA', None]
    assert [(f.size_x_nm, f.size_y_nm) for f in frames] == [(8, 9), (16, 6), (None, 12)]
    assert [f.measurement_time_s for f in frames] == [10, None, 35]
    assert [f.measurement_time_raw for f in frames] == ['10000 ms', None, '35 s']
    assert [f.bias_v for f in frames] == [0, -0.2, None]
    assert all(f.setpoint_a == 0 and f.offset_x_nm == 0 and f.offset_y_nm == -1 for f in frames)
    assert frames[0].raw_header == {'General Info': {'Operator': 'Żaneta', 'Z Amplitude': '2 nm'}}
    assert frames[1].raw_header['Comment'] == 'frame eight'
    assert frames[2].raw_header == {'z_gain': '99', 'Swapped': '0'}
    assert frames[2].calibration_note == 'Nieznana kalibracja'
    assert [f.provenance.source for f in frames] == [
        '/pomiary/first.stp', r'C:\pomiary\movie.MPP', 'archive/third.s94']
    assert [f.provenance.source_frame_index for f in frames] == [None, 7, None]
    assert all(f.source == (FIXTURES / 'mixed.MPP').resolve() for f in frames)
    assert [f.source_frame_index for f in frames] == [0, 1, 2]
    np.testing.assert_array_equal(frames[0].data, [[8, 0, 0, 2], [8, 0, 4, 0], [8, 8, 8, 1]])
    np.testing.assert_array_equal(frames[1].data, [[11, 10, 9, 8], [7, 6, 5, 4], [3, 2, 1, 0]])
    np.testing.assert_array_equal(frames[2].data, [[1, 8, 8, 8], [0, 4, 0, 8], [2, 0, 0, 8]])
    assert all('wczytano' in f.metadata_note for f in frames)


def test_invalid_addon_is_rejected_as_a_whole_without_blocking_movie(tmp_path):
    import copy
    import json

    source = FIXTURES / 'mixed.MPP'
    base = json.loads(source.with_name(source.name + '.stmviewer.json').read_text())
    path = tmp_path / 'copied.MPP'
    path.write_bytes(source.read_bytes())
    sidecar = path.with_name(path.name + '.stmviewer.json')
    cases = []
    for section, field, value, reason in [
        (None, 'version', 999, 'wersj'), (None, 'format', 'foreign', 'format'),
        (None, 'image_kind', 'aligned', 'rodzaj'),
        ('movie', 'sha256', '0' * 64, 'SHA-256'),
        ('movie', 'shape_yx', [4, 3], 'wymiar'),
        ('movie', 'frame_count', 2, 'liczb'),
    ]:
        record = copy.deepcopy(base)
        (record if section is None else record[section])[field] = value
        cases.append((json.dumps(record), reason))
    record = copy.deepcopy(base)
    record['frames'][2]['size_x_nm'] = -2
    cases.append((json.dumps(record), 'size_x_nm'))
    cases.append(('{broken', 'JSON'))
    for content, reason in cases:
        sidecar.write_text(content, encoding='utf-8')
        frames = open_frame_series([path])
        assert len(frames) == 3
        assert all(f.channel == 'Current' and f.size_x_nm == 8 and f.provenance is None for f in frames)
        assert [f.measurement_time_s for f in frames] == [1.5, None, 4.25]
        assert frames[0].raw_header['General Info']['Z Amplitude'] == '99 nA'
        assert all('pominięto' in f.metadata_note and reason in f.metadata_note for f in frames)
        np.testing.assert_array_equal(frames[1].data, [[11, 10, 9, 8], [7, 6, 5, 4], [3, 2, 1, 0]])


def test_pair_can_move_and_be_renamed_without_resolving_historical_paths(tmp_path):
    import shutil

    source = FIXTURES / 'mixed.MPP'
    path = tmp_path / 'new folder' / 'renamed.mpp'
    path.parent.mkdir()
    shutil.copyfile(source, path)
    shutil.copyfile(source.with_name(source.name + '.stmviewer.json'),
                    path.with_name(path.name + '.stmviewer.json'))
    frames = open_frame_series([path])
    assert frames[0].source == path.resolve()
    assert [f.provenance.source for f in frames] == [
        '/pomiary/first.stp', r'C:\pomiary\movie.MPP', 'archive/third.s94']
    assert [f.provenance.source_frame_index for f in frames] == [None, 7, None]
    assert [f.measurement_time_s for f in frames] == [10, None, 35]
    assert all('wczytano renamed.mpp.stmviewer.json' in f.metadata_note for f in frames)


def test_missing_addon_uses_movie_header_and_explains_missing_provenance(tmp_path):
    path = tmp_path / 'single.MPP'
    path.write_bytes((FIXTURES / 'mixed.MPP').read_bytes())
    frames = open_frame_series([path])
    assert len(frames) == 3
    assert all(f.provenance is None and 'brak' in f.metadata_note for f in frames)
    assert [f.measurement_time_s for f in frames] == [1.5, None, 4.25]
    assert all(f.channel == 'Current' and f.size_x_nm == 8 for f in frames)


def test_content_hash_covers_header_payload_and_trailer_without_touching_inputs(tmp_path):
    import struct
    source = FIXTURES / 'mixed.MPP'
    original = source.read_bytes()
    metadata = source.with_name(source.name + '.stmviewer.json').read_bytes()
    path = tmp_path / 'modified.MPP'
    sidecar = path.with_name(path.name + '.stmviewer.json')
    sidecar.write_bytes(metadata)
    for payload in (original.replace(b'X Amplitude: 8 nm', b'X Amplitude: 7 nm'),
                    original[:-8] + struct.pack('<d', 999), original + b'trailer'):
        path.write_bytes(payload)
        frames = open_frame_series([path])
        assert len(frames) == 3 and all('SHA-256' in f.metadata_note for f in frames)
        assert all(f.provenance is None for f in frames)
        assert path.read_bytes() == payload and sidecar.read_bytes() == metadata
        if payload.endswith(struct.pack('<d', 999)):
            assert frames[2].data[0, 0] == 999


def test_invalid_record_types_and_incomplete_schema_never_apply_partial_metadata(tmp_path):
    import copy
    import json
    source = FIXTURES / 'mixed.MPP'
    original = json.loads(source.with_name(source.name + '.stmviewer.json').read_text())
    path = tmp_path / 'invalid.mpp'
    path.write_bytes(source.read_bytes())
    sidecar = path.with_name(path.name + '.stmviewer.json')
    for key, value in [('measurement_time_s', True), ('bias_v', float('nan')),
                       ('setpoint_a', float('inf')), ('size_x_nm', 0), ('size_y_nm', '8'),
                       ('channel', 99), ('raw_header', {'Control': {'Gain': 1}}),
                       ('provenance', {'source': '', 'source_frame_index': None}),
                       ('provenance', {'source': 'source.mpp', 'source_frame_index': -1}),
                       ('provenance', {'source': 'source.mpp', 'source_frame_index': True})]:
        metadata = copy.deepcopy(original)
        metadata['frames'][2][key] = value
        sidecar.write_text(json.dumps(metadata))
        frames = open_frame_series([path])
        assert all('pominięto' in f.metadata_note and f.provenance is None for f in frames)
        assert all(f.channel == 'Current' for f in frames)
    for change in ('missing', 'extra', 'short', 'wrong-root', 'duplicate'):
        metadata = copy.deepcopy(original)
        if change == 'missing':
            del metadata['frames'][2]['measurement_time_s']
        elif change == 'extra':
            metadata['frames'][2]['data'] = [[99]]
        elif change == 'short':
            metadata['frames'].pop()
        elif change == 'wrong-root':
            metadata = []
        content = json.dumps(metadata)
        if change == 'duplicate':
            content = content.replace('"version": 1', '"version": 2, "version": 1')
        sidecar.write_text(content)
        frames = open_frame_series([path])
        assert all('pominięto' in f.metadata_note and f.provenance is None for f in frames)
        assert all(f.data.shape == (3, 4) for f in frames)


def test_addon_read_error_falls_back_but_cancellation_propagates(tmp_path, monkeypatch):
    import pytest
    from stmviewer.series import ImportCancelled

    path = tmp_path / 'protected.MPP'
    path.write_bytes((FIXTURES / 'mixed.MPP').read_bytes())
    sidecar = path.with_name(path.name + '.stmviewer.json')
    sidecar.write_bytes((FIXTURES / 'mixed.MPP.stmviewer.json').read_bytes())
    real_open = Path.open
    def denied(p, *args, **kwargs):
        if p == sidecar:
            raise PermissionError('Brak dostępu do dodatku')
        return real_open(p, *args, **kwargs)
    monkeypatch.setattr(Path, 'open', denied)
    frames = open_frame_series([path])
    assert all('Brak dostępu' in f.metadata_note and f.provenance is None for f in frames)
    read = []
    class CancelDuringRead:
        def __init__(self, stream):
            self.stream = stream
        def __enter__(self):
            return self
        def __exit__(self, *args):
            self.stream.close()
        def read(self, size):
            read.append(True)
            return self.stream.read(size)
    def reading(p, *args, **kwargs):
        stream = real_open(p, *args, **kwargs)
        return CancelDuringRead(stream) if p == sidecar else stream
    monkeypatch.setattr(Path, 'open', reading)
    with pytest.raises(ImportCancelled):
        open_frame_series([path], cancelled=lambda: bool(read))


@pytest.mark.parametrize('name, reason', [
    ('without-addon', 'brak'), ('wrong-content', 'SHA-256'), ('wrong-shape', 'wymiary'),
    ('wrong-count', 'liczba'), ('unsupported', 'wersja'), ('broken', 'JSON'),
])
def test_manual_fixtures_open_with_the_documented_fallback(name, reason):
    frames = open_frame_series([FIXTURES / f'{name}.MPP'])
    assert len(frames) == 3 and all(f.provenance is None for f in frames)
    assert all(reason in f.metadata_note and f.channel == 'Current' for f in frames)
