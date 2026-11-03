"""Small checks of the opt-in fixture through import and real Phase contracts."""

import hashlib

from make_large_series import generate
from stmviewer.registration import register_series
from stmviewer.series import open_frame_series


def test_streamed_fixture_is_reproducible_with_known_times_and_drift(tmp_path):
    first = generate(tmp_path / 'first', count=8, size=128, drift=20)
    second = generate(tmp_path / 'second', count=8, size=128, drift=20)
    assert first == second
    path = tmp_path / 'first/large.mpp'
    with path.open('rb') as source:
        assert hashlib.file_digest(source, 'sha256').hexdigest() == first['sha256']
    frames = open_frame_series([path])
    assert len(frames) == 8 and frames[-1].data.shape == (128, 128)
    assert frames[-1].measurement_time_s == 10.5
    assert frames[0].size_x_nm == frames[0].size_y_nm == 128
    result = register_series(frames)
    assert result.canvas_shape == (131, 135)
    assert result.frames[-1].shift_xy == (-7, -3)
