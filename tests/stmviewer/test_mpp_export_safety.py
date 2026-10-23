"""Failure injection only at filesystem boundaries of the public exporter."""
from pathlib import Path
import os

import pytest

from stmviewer.series import open_frame_series
from stmviewer.mpp_export import save_original_mpp, ExportCancelled

FIXTURES = Path(__file__).parent / 'fixtures'


def old_pair(tmp_path):
    path = tmp_path / 'movie.mpp'
    sidecar = path.with_name(path.name + '.stmviewer.json')
    path.write_bytes(b'previous movie')
    sidecar.write_bytes(b'previous metadata')
    return path, sidecar


def assert_old_pair(path, sidecar):
    assert path.read_bytes() == b'previous movie'
    assert sidecar.read_bytes() == b'previous metadata'
    assert sorted(p.name for p in path.parent.iterdir()) == [path.name, sidecar.name]


def test_requires_overwrite_consent_for_either_existing_member(tmp_path):
    frames = open_frame_series([FIXTURES / 'asymmetric.stp'])
    path, sidecar = old_pair(tmp_path)
    with pytest.raises(FileExistsError):
        save_original_mpp(path, frames)
    assert_old_pair(path, sidecar)
    path.unlink()
    with pytest.raises(FileExistsError):
        save_original_mpp(path, frames)
    assert not path.exists() and sidecar.read_bytes() == b'previous metadata'


def test_cancel_after_first_frame_keeps_old_pair(tmp_path):
    path, sidecar = old_pair(tmp_path)
    frames = open_frame_series([FIXTURES / 'mpp/known-times.mpp'])
    stopped = False
    events = []

    def progress(done, total, description):
        nonlocal stopped
        events.append((done, total, description))
        stopped = done >= 1

    with pytest.raises(ExportCancelled):
        save_original_mpp(path, frames, overwrite=True, progress=progress, cancelled=lambda: stopped)
    assert events and events[-1][0] < events[-1][1]
    assert_old_pair(path, sidecar)


@pytest.mark.parametrize('existing', [False, True])
@pytest.mark.parametrize('cancel', [False, True])
def test_failure_or_cancel_between_publications_rolls_back_both_files(tmp_path, monkeypatch, existing, cancel):
    path = tmp_path / 'movie.mpp'
    sidecar = path.with_name(path.name + '.stmviewer.json')
    if existing:
        old_pair(tmp_path)
    frames = open_frame_series([FIXTURES / 'asymmetric.stp'])
    real_replace = os.replace
    stopped = False

    def replace(source, destination):
        nonlocal stopped
        if Path(destination) == sidecar and not str(source).endswith('.backup'):
            raise OSError('disk failure')
        result = real_replace(source, destination)
        if Path(destination) == path:
            stopped = cancel
        return result

    monkeypatch.setattr(os, 'replace', replace)
    with pytest.raises(ExportCancelled if cancel else OSError):
        save_original_mpp(path, frames, overwrite=existing, cancelled=lambda: stopped)
    if existing:
        assert_old_pair(path, sidecar)
    else:
        assert list(tmp_path.iterdir()) == []


def test_short_write_does_not_replace_old_output(tmp_path, monkeypatch):
    path, sidecar = old_pair(tmp_path)
    frames = open_frame_series([FIXTURES / 'asymmetric.stp'])
    real_open = Path.open

    class ShortWriter:
        def __init__(self, stream):
            self.stream = stream
        def __getattr__(self, key):
            return getattr(self.stream, key)
        def __enter__(self):
            return self
        def __exit__(self, *args):
            self.stream.close()
        def write(self, data):
            return self.stream.write(data[:3])

    def open_file(source, mode='r', *args, **kwargs):
        stream = real_open(source, mode, *args, **kwargs)
        return ShortWriter(stream) if mode == 'xb' else stream

    monkeypatch.setattr(Path, 'open', open_file)
    with pytest.raises(OSError):
        save_original_mpp(path, frames, overwrite=True)
    assert_old_pair(path, sidecar)


def test_invalid_metadata_and_empty_series_leave_output_untouched(tmp_path):
    from dataclasses import replace
    path, sidecar = old_pair(tmp_path)
    frame = open_frame_series([FIXTURES / 'asymmetric.stp'])[0]
    for frames in ((), (replace(frame, size_x_nm=float('nan')),),
                   (frame, replace(frame, data=frame.data[:1]))):
        with pytest.raises(ValueError):
            save_original_mpp(path, frames, overwrite=True)
        assert_old_pair(path, sidecar)


def test_real_process_exit_between_publications_is_detected_on_reopen(tmp_path):
    import subprocess
    import sys

    frames = open_frame_series([FIXTURES / 'mpp/known-times.mpp'])
    path = tmp_path / 'movie.mpp'
    save_original_mpp(path, frames)
    old_metadata = path.with_name(path.name + '.stmviewer.json').read_bytes()
    script = '''
import os, sys
from pathlib import Path
from stmviewer.mpp_export import save_original_mpp
from stmviewer.series import open_frame_series
path = Path(sys.argv[1])
frames = open_frame_series([path])
real_replace = os.replace
def replace(source, destination):
    real_replace(source, destination)
    if Path(destination) == path:
        os._exit(42)
os.replace = replace
save_original_mpp(path, frames[:1], overwrite=True)
'''
    result = subprocess.run([sys.executable, '-c', script, str(path)], timeout=15)
    assert result.returncode == 42
    assert path.with_name(path.name + '.stmviewer.json').read_bytes() == old_metadata
    restored = open_frame_series([path])
    assert len(restored) == 1 and 'SHA-256' in restored[0].metadata_note
    assert restored[0].provenance is None
