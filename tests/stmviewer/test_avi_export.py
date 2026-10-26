"""AVI contract verified by actually decoding complete movies."""
import cv2
import numpy as np
import pytest

from stmviewer.avi_export import prepare_avi, save_avi
from stmviewer.avi_raster import MoviePresentation
from test_avi_raster import frame


def decode(path):
    reader = cv2.VideoCapture(str(path))
    assert reader.isOpened()
    fps = reader.get(cv2.CAP_PROP_FPS)
    rasters = []
    try:
        while True:
            ok, raster = reader.read()
            if not ok:
                break
            rasters.append(raster)
    finally:
        reader.release()
    return fps, rasters


@pytest.mark.parametrize('codec', ['MJPG', 'FFV1'])
def test_range_odd_edges_order_and_fps_are_real_decoded_movie(tmp_path, codec):
    images = []
    expected = []
    for index in range(4):
        data = np.zeros((49, 65))
        data[4:24, index * 12:index * 12 + 10] = 4
        data[-1] = 1
        data[:, -1] = 4
        images.append(frame(data))
        raster = np.zeros((50, 66, 3), dtype=np.uint8)
        raster[:49, :65] = np.where(data[:, :, None] == 4, 255,
                                    np.where(data[:, :, None] == 1, 127, 0))
        expected.append(raster)
    plan = prepare_avi(tuple(images), start=2, end=3, fps=7, codec=codec,
                       presentation=MoviePresentation(gamma=2))
    assert plan.frame_count == 2 and plan.duration_s == pytest.approx(2/7)
    assert plan.geometry.output_size == (66, 50)
    path = tmp_path / f'film żółty {codec}.avi'
    assert save_avi(path, plan) == path
    fps, decoded = decode(path)
    assert fps == pytest.approx(7) and len(decoded) == 2
    for actual, wanted in zip(decoded, expected[1:3], strict=True):
        assert actual.shape == (50, 66, 3)
        if codec == 'FFV1':
            np.testing.assert_array_equal(actual, wanted)
        else:
            assert np.abs(actual.astype(float) - wanted).mean() < 5
    assert len(list(tmp_path.iterdir())) == 1


@pytest.mark.parametrize('outcome', ['cancel_write', 'cancel_check', 'disk_error', 'unavailable', 'silent_drop'])
def test_failure_or_cancel_preserves_existing_movie_and_removes_temporary_files(tmp_path, monkeypatch, outcome):
    from threading import Event
    from stmviewer.avi_export import AviCancelled
    path = tmp_path / 'old.avi'
    source = frame(np.arange(64 * 48).reshape(48, 64))
    plan = prepare_avi((source,) * 3, codec='FFV1')
    save_avi(path, plan)
    previous = path.read_bytes()
    cancelled = Event()
    progress_seen = []

    def progress(done, total, description):
        progress_seen.append((done, total))
        if outcome == 'cancel_write' and done == 2:
            cancelled.set()
        if outcome == 'cancel_check' and done == 5:
            cancelled.set()

    real_writer = cv2.VideoWriter

    class BrokenWriter:
        def __init__(self, *args):
            self.writer = real_writer(*args)
        def isOpened(self):
            return outcome != 'unavailable' and self.writer.isOpened()
        def write(self, raster):
            if outcome == 'disk_error':
                raise OSError('dysk pełny')
            if outcome != 'silent_drop':
                self.writer.write(raster)
        def release(self):
            self.writer.release()

    monkeypatch.setattr(cv2, 'VideoWriter', BrokenWriter)
    expected = AviCancelled if outcome.startswith('cancel') else (OSError, ValueError)
    with pytest.raises(expected):
        save_avi(path, plan, overwrite=True, progress=progress, cancelled=cancelled.is_set)
    assert path.read_bytes() == previous
    assert list(tmp_path.iterdir()) == [path]
    assert len(decode(path)[1]) == 3


def test_single_empty_frame_and_input_validation(tmp_path):
    source = frame(np.full((48, 64), np.nan))
    path = tmp_path / 'empty.avi'
    save_avi(path, prepare_avi((source,), codec='FFV1', fps=30))
    fps, frames = decode(path)
    assert fps == 30 and len(frames) == 1 and not frames[0].any()
    for kwargs in ({'start': 0}, {'start': 2}, {'end': 0}, {'fps': 0}, {'fps': 31}, {'codec': 'bad'}):
        with pytest.raises(ValueError):
            prepare_avi((source,), **kwargs)
    with pytest.raises(ValueError):
        prepare_avi(())
    with pytest.raises(FileExistsError):
        save_avi(path, prepare_avi((source,)))


def test_native_mjpg_failure_is_reported_without_crashing_application(tmp_path):
    """Run the public API in a child too: a regression must not kill pytest."""
    import os
    import subprocess
    import sys
    script = '''
from pathlib import Path
from test_avi_raster import frame
from stmviewer.avi_export import prepare_avi, save_avi
path = Path(__import__('sys').argv[1])
path.write_bytes(b'previous movie')
try:
    save_avi(path, prepare_avi((frame([[0, 1, 2, 3]] * 4),)), overwrite=True)
except ValueError as error:
    assert 'MJPG' in str(error)
    assert path.read_bytes() == b'previous movie'
# Builds which can encode 4x4 successfully are also acceptable.
'''
    result = subprocess.run([sys.executable, '-c', script, str(tmp_path / 'tiny.avi')],
                            env=os.environ, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr


def test_relative_destination_outside_repository(tmp_path, monkeypatch):
    from pathlib import Path
    monkeypatch.chdir(tmp_path)
    plan = prepare_avi((frame(np.arange(48 * 64).reshape(48, 64)),), codec='FFV1')
    path = Path('relative.avi')
    save_avi(path, plan)
    assert len(decode(path)[1]) == 1
