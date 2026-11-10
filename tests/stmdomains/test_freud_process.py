"""Real optional-library boundary: rotation, cancellation and resource cleanup."""

import time

import numpy as np
import pytest

from stmdomains.analysis.freud_adapter import compare_environments
from stmdomains.analysis.freud_neighbors import Environments
from stmdomains.analysis.freud_settings import FreudSettings
from stmdomains.core.analysis_result import AnalysisCancelled


def two_environments():
    motif = np.array([(0., 0.), (1., 0.), (0., 1.4), (-1., 0.), (0., -1.4)])
    theta = np.deg2rad(30)
    rotated = motif @ np.array([[np.cos(theta), -np.sin(theta)], [np.sin(theta), np.cos(theta)]]).T
    return Environments(np.vstack((motif, rotated+(10, 0))), np.array([0]*4+[5]*4, np.uint32),
        np.array([1, 2, 3, 4, 6, 7, 8, 9], np.uint32), np.array([0, 5]), [])


def test_actual_library_matches_rotation_only_when_requested():
    fixed, version = compare_environments(two_environments(), FreudSettings(), lambda: False)
    rotated, _ = compare_environments(two_environments(), FreudSettings(registration=True), lambda: False)
    assert version
    assert fixed[0] != fixed[5] and rotated[0] == rotated[5] > 0
    assert not any(rotated[i] for i in (1, 2, 3, 4, 6, 7, 8, 9))


def test_registration_explicitly_includes_mirror_images_in_the_plane():
    from dataclasses import replace
    motif = np.array([(0., 0.), (1., 0.), (.3, 1.3), (-1., .2), (-.2, -.9)])
    mirrored = motif * (-1, 1) + (10, 0)
    environments = replace(two_environments(), points=np.vstack((motif, mirrored)))
    fixed, _ = compare_environments(environments, FreudSettings(tolerance=.01), lambda: False)
    settings = FreudSettings(tolerance=.01, registration=True)
    registered, _ = compare_environments(environments, settings, lambda: False)
    assert fixed[0] != fixed[5] and registered[0] == registered[5] > 0
    assert settings.registration_transform == 'proper_3d_rotation_including_planar_reflection'


@pytest.mark.parametrize('cancel', [True, False])
def test_cancel_or_timeout_reaps_native_process(monkeypatch, cancel):
    from stmdomains.analysis import freud_adapter
    processes = []
    original = freud_adapter.subprocess.Popen
    def track(*args, **kwargs):
        process = original(*args, **kwargs)
        processes.append(process)
        return process
    monkeypatch.setattr(freud_adapter.subprocess, 'Popen', track)
    started = time.monotonic()
    with pytest.raises(AnalysisCancelled if cancel else ValueError):
        compare_environments(two_environments(), FreudSettings(registration=True),
            lambda: cancel and time.monotonic()-started > .1, time_limit=90 if cancel else .01)
    assert processes and processes[0].poll() is not None
    assert time.monotonic()-started < 5


def test_absent_optional_dependency_reports_actionable_error(monkeypatch):
    from stmdomains.analysis import freud_adapter
    monkeypatch.setattr(freud_adapter.importlib.util, 'find_spec', lambda name: None)
    with pytest.raises(ValueError, match='netcat'):
        compare_environments(two_environments(), FreudSettings(), lambda: False)
