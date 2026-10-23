"""Public pair export, independent byte expectations, and public reader round-trips."""

from pathlib import Path
import hashlib
import json
import struct

import numpy as np
import pytest

from stmviewer.series import open_frame_series

FIXTURES = Path(__file__).parent / 'fixtures'


def test_original_export_preserves_removed_frame_gaps_provenance_and_file_orientation(tmp_path):
    from stmviewer.mpp_export import save_original_mpp

    first, _, third = open_frame_series([FIXTURES / 'mpp/known-times.mpp'])
    destination = tmp_path / 'result.MPP'
    save_original_mpp(destination, (first, third))
    raw = destination.read_bytes()
    header, payload = raw.split(b'[Header end]\n', 1)
    assert b'Image Data Type: double' in header
    assert b'Number of Frames: 2' in header
    assert b'Frame 0000: 10.0 s' in header and b'Frame 0001: 35.0 s' in header
    # Known file order: independently specified rotated L then the inverse marker.
    assert struct.unpack('<24d', payload) == (
        1, 8, 8, 8, 0, 4, 0, 8, 2, 0, 0, 8,
        8, 0, 0, 2, 8, 0, 4, 0, 8, 8, 8, 1,
    )
    metadata = json.loads(destination.with_name(destination.name + '.stmviewer.json').read_text())
    assert metadata['version'] == 1 and metadata['image_kind'] == 'original'
    assert metadata['movie'] == dict(sha256=hashlib.sha256(raw).hexdigest(), frame_count=2, shape_yx=[3, 4])
    restored = open_frame_series([destination])
    assert [f.measurement_time_s for f in restored] == [10, 35]
    assert [f.provenance.source_frame_index for f in restored] == [0, 2]
    assert all(f.provenance.source == str(first.source) for f in restored)
    for source, output in zip((first, third), restored):
        np.testing.assert_array_equal(output.data, source.data)
        assert output.raw_header == source.raw_header
        assert output.signal_unit == 'nA' and output.size_x_nm == 8
        assert 'wczytano' in output.metadata_note


def test_stp_s94_and_missing_pixels_roundtrip_without_precision_loss(tmp_path):
    from dataclasses import replace
    from stmviewer.mpp_export import save_original_mpp

    for relative in ('asymmetric.stp', 's94/frame2.s94', 'preview/missing.stp', 'mpp/timed.MPP'):
        frames = open_frame_series([FIXTURES / relative])
        path = tmp_path / (Path(relative).name + '.mpp')
        save_original_mpp(path, frames)
        for source, output in zip(frames, open_frame_series([path]), strict=True):
            np.testing.assert_array_equal(output.data, source.data)
            for field in ('raw_header', 'channel', 'signal_unit', 'size_x_nm', 'size_y_nm',
                          'offset_x_nm', 'offset_y_nm', 'bias_v', 'setpoint_a', 'scan_angle_deg',
                          'calibration_note', 'measurement_time_s', 'measurement_time_raw'):
                assert getattr(output, field) == getattr(source, field), field
    values = np.array([[np.nextafter(1., 2.), -0., np.finfo(float).max],
                       [np.nextafter(0., 1.), -np.finfo(float).max, np.nan]])
    path = tmp_path / 'precise.mpp'
    save_original_mpp(path, (replace(frames[0], data=values),))
    saved = open_frame_series([path])[0].data
    np.testing.assert_array_equal(saved, values)
    assert np.signbit(saved[0, 1])
    payload = path.read_bytes().split(b'[Header end]\n', 1)[1]
    assert payload == struct.pack('<6d', np.nan, -np.finfo(float).max,
                                 np.nextafter(0., 1.), np.finfo(float).max, -0., np.nextafter(1., 2.))


def test_mixed_metadata_uses_conventional_header_and_keeps_historical_provenance(tmp_path):
    from stmviewer.mpp_export import save_original_mpp

    frames = open_frame_series([FIXTURES / 'mpp-metadata/mixed.MPP'])
    path = tmp_path / 'mixed.mpp'
    save_original_mpp(path, frames)
    header = path.read_bytes().split(b'[Header end]', 1)[0]
    assert b'Acquisition channel: Unknown' in header
    assert b'Z Amplitude: 1 a.u.' in header
    assert b'X Amplitude: 4 a.u.' in header and b'Y Amplitude: 3 a.u.' in header
    assert b'Gap Voltage:' not in header
    assert b'Frame 0001:' not in header
    restored = open_frame_series([path])
    for source, output in zip(frames, restored, strict=True):
        assert output.provenance == source.provenance
        for field in ('raw_header', 'signal_unit', 'channel', 'size_x_nm', 'size_y_nm',
                      'measurement_time_s', 'measurement_time_raw', 'bias_v', 'calibration_note'):
            assert getattr(output, field) == getattr(source, field)
    assert restored[1].provenance.source == r'C:\pomiary\movie.MPP'
    assert restored[0].raw_header['General Info']['Operator'] == 'Żaneta'
    moved = tmp_path / 'moved'
    moved.mkdir()
    path.rename(moved / path.name)
    path.with_name(path.name + '.stmviewer.json').rename(moved / (path.name + '.stmviewer.json'))
    assert open_frame_series([moved / path.name])[1].provenance == frames[1].provenance


def test_long_utf8_header_has_exact_byte_offset_and_reopens(tmp_path):
    from dataclasses import replace
    from stmviewer.mpp_export import save_original_mpp

    source = open_frame_series([FIXTURES / 'asymmetric.stp'])[0]
    frames = tuple(replace(source, channel='Kanał µ', measurement_time_s=float(i)) for i in range(1100))
    path = tmp_path / 'long.mpp'
    save_original_mpp(path, frames)
    raw = path.read_bytes()
    offset = int(raw.splitlines()[2].split(b': ')[1])
    assert raw[:offset].endswith(b'[Header end]\n')
    assert len(raw[:offset].splitlines()) > 1000
    assert raw[offset:offset+8] == struct.pack('<d', source.data[-1, -1])
    restored = open_frame_series([path])
    assert len(restored) == 1100
    assert restored[-1].measurement_time_s == 1099 and restored[-1].channel == 'Kanał µ'


def test_existing_readers_receive_values_and_common_calibration(tmp_path):
    from stmviewer.mpp_export import save_original_mpp
    from napara.io.mpp_reader import read_mpp_file
    from nanotrack.io.mpp_loader import load_mpp_sequence
    from moltrack.io.sequence_loader import load_moltrack_image_series

    frames = open_frame_series([FIXTURES / 'mpp/known-times.mpp'])
    path = tmp_path / 'readers.mpp'
    save_original_mpp(path, frames)
    legacy = read_mpp_file(str(path))
    for source, output in zip(frames, legacy, strict=True):
        np.testing.assert_array_equal(output.data, np.rot90(source.data, 2))
        assert output.size_nm_x == source.size_x_nm
        assert output.size_nm_y == pytest.approx(source.size_y_nm, rel=1e-14)
        assert output.setpoint_a == pytest.approx(source.setpoint_a, rel=1e-14, abs=0)
    sequence = load_mpp_sequence(str(path))
    np.testing.assert_array_equal(sequence.raw_frames, np.stack([f.data for f in frames]))
    np.testing.assert_array_equal(sequence.metadata.frame_times_s, [10, 20, 35])
    series = load_moltrack_image_series(path)
    np.testing.assert_array_equal(series.raw_frames, sequence.raw_frames)
