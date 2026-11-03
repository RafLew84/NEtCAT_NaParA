"""Actual MPP decoding through the public complete-series import."""

from pathlib import Path

import numpy as np

from stmviewer.series import open_frame_series

FIXTURES = Path(__file__).parent / 'fixtures' / 'mpp'


def test_movie_preserves_values_orientation_order_and_measurement_metadata():
    frames = open_frame_series([FIXTURES / 'timed.MPP'])

    assert len(frames) == 3
    np.testing.assert_array_equal(frames[0].data, [
        [8, 0, 0, 2], [8, 0, 4, 0], [8, 8, 8, 1],
    ])
    np.testing.assert_array_equal(frames[1].data, [[11, 10, 9, 8], [7, 6, 5, 4], [3, 2, 1, 0]])
    np.testing.assert_array_equal(frames[2].data, [[1, 8, 8, 8], [0, 4, 0, 8], [2, 0, 0, 8]])
    assert all(frame.data.dtype == np.float64 for frame in frames)
    assert [frame.source_frame_index for frame in frames] == [0, 1, 2]
    frame = frames[0]
    assert frame.source == (FIXTURES / 'timed.MPP').resolve()
    assert frame.channel == 'Current' and frame.signal_unit == 'nA'
    assert (frame.size_x_nm, frame.size_y_nm) == (8, 9)
    assert (frame.offset_x_nm, frame.offset_y_nm) == (2, -1)
    assert frame.bias_v == -0.2 and frame.setpoint_a == 4e-10
    assert frame.scan_angle_deg == 37
    assert frame.raw_header['General Info']['Z Amplitude'] == '99 nA'


def test_partial_times_keep_units_gaps_and_original_description(tmp_path):
    from make_mpp_fixtures import movie_bytes

    times = {0: '1500 ms', 2: '4.25 s', 3: '0 sec', 4: '2 min', 5: '500 µs',
             6: '1e3 us', 7: '1 h', 8: '8', 9: '2 ticks', 10: 'NaN s',
             11: '1e999 s', 12: 'invalid', 40: '999 s'}
    path = tmp_path / 'times.mpp'
    path.write_bytes(movie_bytes([(i,) for i in range(13)], rows=1, columns=1, times=times,
                                extra='[Playback]\nFPS: 5\n'))

    frames = open_frame_series([path])

    assert [frame.measurement_time_s for frame in frames] == [
        1.5, None, 4.25, 0, 120, 0.0005, 0.001, 3600, None, None, None, None, None,
    ]
    assert [frame.measurement_time_raw for frame in frames] == [times.get(i) for i in range(13)]
    assert frames[-1].source_frame_index == 12
    assert open_frame_series([FIXTURES / 'no-times.mpp'])[0].measurement_time_s is None


def test_long_header_and_1000_frames_have_complete_order_and_progress():
    path = FIXTURES / 'long.mpp'
    assert path.read_bytes().split(b'[Header end]')[0].count(b'\n') > 1000
    progress = []

    frames = open_frame_series([path], progress=lambda done, total, source: progress.append((done, total, source)))

    assert len(frames) == 1000
    assert [frame.data.item() for frame in frames] == list(range(1000))
    assert [frame.source_frame_index for frame in frames] == list(range(1000))
    assert [frame.measurement_time_s for frame in frames] == list(range(1000))
    assert [done for done, _, _ in progress] == list(range(1001))
    assert all(total == 1000 and source == path.resolve() for _, total, source in progress)


def test_cancel_between_movie_frames_never_returns_a_partial_series():
    import pytest
    from stmviewer.series import ImportCancelled

    progress = []
    with pytest.raises(ImportCancelled):
        open_frame_series([FIXTURES / 'long.mpp'],
                          progress=lambda done, total, path: progress.append(done),
                          cancelled=lambda: len(progress) >= 3)
    assert progress == [0, 1, 2]


def test_unsupported_data_type_is_rejected_instead_of_decoded_as_double(tmp_path):
    import pytest

    path = tmp_path / 'integer.mpp'
    path.write_bytes((FIXTURES / 'timed.MPP').read_bytes().replace(b'Type: double', b'Type: short'))
    with pytest.raises(ValueError, match='integer.mpp.*typ danych.*short'):
        open_frame_series([path])


def test_truncated_movie_reports_which_frame_is_incomplete():
    import pytest

    with pytest.raises(ValueError, match='truncated.mpp.*[Nn]iepełn.*3/3'):
        open_frame_series([FIXTURES / 'truncated.mpp'])


def test_movie_selection_must_be_exactly_one_mpp():
    import pytest

    for paths in ([FIXTURES / 'timed.MPP', FIXTURES / 'no-times.mpp'],
                  [FIXTURES / 'timed.MPP', FIXTURES.parent / 'asymmetric.stp'],
                  [FIXTURES.parent / 's94/frame2.s94', FIXTURES / 'timed.MPP']):
        with pytest.raises(ValueError, match='[Ww]ybierz.*jeden.*MPP'):
            open_frame_series(paths)


def test_unknown_metadata_and_nan_are_preserved_without_defaults(tmp_path):
    from make_mpp_fixtures import movie_bytes

    path = tmp_path / 'unknown.mpp'
    payload = movie_bytes([(float('nan'), -2, 7, 0)], rows=2, columns=2,
                          times={0: '500 µs'}, encoding='latin1',
                          extra='[Custom]\nObservation: original\n')
    payload = payload.replace(b'X Amplitude: 8 nm', b'X Amplitude: 0.5 \xb5m')
    payload = payload.replace(b'Y Amplitude: 9 nm', b'Y Amplitude: 0 nm')
    payload = payload.replace(b'Z Amplitude: 99 nA', b'Z Amplitude: unknown')
    payload = payload.replace(b'Topography Bias: -200 mV', b'Topography Bias: 0 V')
    payload = payload.replace(b'Set Point: 400 pA', b'Set Point: 0 a.u.')
    path.write_bytes(payload)

    frame = open_frame_series([path])[0]

    np.testing.assert_array_equal(frame.data, [[0, 7], [-2, np.nan]])
    assert frame.size_x_nm == 500 and frame.size_y_nm is None
    assert frame.bias_v == 0 and frame.setpoint_a is None and frame.signal_unit is None
    assert frame.measurement_time_s == 0.0005
    assert frame.raw_header['Custom']['Observation'] == 'original'


def test_malformed_headers_and_missing_files_report_the_source(tmp_path):
    import pytest

    base = (FIXTURES / 'timed.MPP').read_bytes()
    for payload in (
        base.split(b'[Header end]')[0],
        base.replace(b'Number of Frames: 3', b'Number of Frames: 0'),
        base.replace(b'Number of rows: 3', b'Number of rows: -1'),
        base.replace(b'Number of columns: 4', b'Number of columns: invalid'),
        base.replace(b'Number of rows: 3', b'Number of rows: 999999999999999999'),
    ):
        path = tmp_path / 'bad.mpp'
        path.write_bytes(payload)
        with pytest.raises(ValueError, match='bad.mpp'):
            open_frame_series([path])
    with pytest.raises(ValueError, match='missing.mpp'):
        open_frame_series([tmp_path / 'missing.mpp'])


def test_cancellation_is_checked_during_header_and_after_last_frame():
    import pytest
    from stmviewer.series import ImportCancelled

    checks = []

    def cancel_header():
        checks.append(True)
        return len(checks) == 5

    progress = []
    with pytest.raises(ImportCancelled):
        open_frame_series([FIXTURES / 'long.mpp'], cancelled=cancel_header,
                          progress=lambda *args: progress.append(args))
    assert progress == []
    with pytest.raises(ImportCancelled):
        open_frame_series([FIXTURES / 'no-times.mpp'], cancelled=lambda: len(progress) == 2,
                          progress=lambda *args: progress.append(args))
