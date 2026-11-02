"""CPU graph measurements stay independent of models and of other methods' caches."""
import builtins
from pathlib import Path

import numpy as np
import pytest

from stmviewer.deep_matcher import DeepMatcherOptions
from stmviewer.graph_registration import register_graph
from stmviewer.robust_graph import solve_robust_graph
from stmviewer.series import open_frame_series

FIXTURE = Path(__file__).parent / 'fixtures/registration/cpu.mpp'
CPU_METHODS = (
    'phase_correlation', 'phase_no_normalization', 'tile_correlation_ransac',
    'ecc_translation', 'optical_flow_median',
)


@pytest.mark.parametrize('method', CPU_METHODS)
def test_cpu_graph_and_huber_need_no_deep_runtime_even_when_options_request_cuda(monkeypatch, tmp_path, method):
    frames = open_frame_series([FIXTURE])
    native_import = builtins.__import__
    model_imports = []

    def without_models(name, *args, **kwargs):
        if name.split('.')[0] in ('torch', 'kornia'):
            model_imports.append(name)
            raise ImportError(f'Model runtime unavailable: {name}')
        return native_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, '__import__', without_models)
    trial = register_graph(frames, method=method,
                           deep_options=DeepMatcherOptions(tmp_path / 'absent.ckpt', 'cuda'))
    np.testing.assert_allclose(trial.positions, [(0, 0), (2, -1), (-1, 1)], atol=.35)
    robust = solve_robust_graph(trial)
    np.testing.assert_allclose(robust.positions, [(0, 0), (2, -1), (-1, 1)], atol=.35)
    assert trial.config.method == method and trial.config.device == 'CPU'
    assert trial.config.weights_path is None and trial.config.weights_sha256 is None
    assert model_imports == []


def six_frames():
    from dataclasses import replace
    originals = open_frame_series([FIXTURE])
    return tuple(replace(originals[index % 3], source_frame_index=index) for index in range(6))


def test_window_growth_reuses_same_cpu_measurements_but_changing_method_remeasures_every_pair():
    frames = six_frames()
    phase = register_graph(frames, method='phase_correlation', window=3)
    assert phase.measured_pairs == 12 and phase.reused_pairs == 0
    wider = register_graph(frames, method='phase_correlation', window=5, previous=phase)
    assert wider.measured_pairs == 3 and wider.reused_pairs == 12
    assert len(wider.edges) == 15
    old_xy = {(edge.i, edge.j): edge.shift_xy for edge in phase.edges}
    assert {(edge.i, edge.j): edge.shift_xy for edge in wider.edges if (edge.i, edge.j) in old_xy} == old_xy
    flow = register_graph(frames, method='optical_flow_median', window=5, previous=wider)
    assert flow.config.method == 'optical_flow_median'
    assert flow.measured_pairs == 15 and flow.reused_pairs == 0
    repeated = register_graph(frames, method='optical_flow_median', window=3, previous=flow)
    assert repeated.measured_pairs == 0 and repeated.reused_pairs == 12
    np.testing.assert_allclose(repeated.positions, [(0, 0), (2, -1), (-1, 1), (0, 0), (2, -1), (-1, 1)], atol=.35)


def test_cancelling_new_cpu_method_keeps_previous_trial_and_originals_unchanged():
    from copy import deepcopy
    from threading import Event
    from stmviewer.registration import RegistrationCancelled
    frames = six_frames()
    previous = register_graph(frames, method='phase_correlation', window=3)
    saved = deepcopy(previous)
    original_pixels = [frame.data.copy() for frame in frames]
    cancel = Event()
    completed = []

    def progress(done, total, text):
        if done:
            completed.append((done, total, text))
            cancel.set()

    with pytest.raises(RegistrationCancelled):
        register_graph(frames, method='optical_flow_median', window=5, previous=previous,
                       progress=progress, cancelled=cancel.is_set)
    assert completed and completed[0][0:2] == (1, 15)
    assert 'Optical Flow' in completed[0][2]
    assert previous == saved
    for frame, pixels in zip(frames, original_pixels, strict=True):
        np.testing.assert_array_equal(frame.data, pixels)
