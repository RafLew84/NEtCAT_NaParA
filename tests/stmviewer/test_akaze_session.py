"""Portable AKAZE work: active result, pending graph and no estimator on reopen."""
from dataclasses import replace
from pathlib import Path
import os
import subprocess
import sys
import numpy as np

from stmviewer.graph_application import apply_graph_to_movie, restore_movie_result
from stmviewer.graph_registration import register_graph
from stmviewer.manual_movie import apply_movie_correction, remove_movie_correction
from stmviewer.registration import register_series
from stmviewer.session_archive import load_session, save_session
from stmviewer.session_state import SessionState, SessionViewState
from test_akaze_integration import frames
from test_manual_movie import corrected_trial


def test_corrected_active_graph_and_pending_candidate_reopen_without_runtime(tmp_path):
    originals = frames()
    base = register_series(originals, method='akaze')
    graph = register_graph(originals, method='akaze')
    applied = apply_graph_to_movie(originals, graph, previous=base)
    corrected = apply_movie_correction(applied, corrected_trial(applied, 1, 1, 0))
    undone = remove_movie_correction(corrected, 1)
    np.testing.assert_allclose([f.shift_xy for f in undone.frames], [f.shift_xy for f in applied.frames])
    pending = replace(graph, revision='pending-akaze')
    display = SessionViewState(method='phase_correlation', deep_weights='/absent/unused.ckpt', deep_device='cuda')
    path = save_session(tmp_path/'akaze.stmsession', SessionState(originals, corrected, display, pending))
    restored = load_session(path)
    assert restored.display == display
    assert restored.graph.revision == 'pending-akaze'
    assert restored.registration.graph_application.graph.config == graph.config
    assert restored.registration.corrections == corrected.corrections
    previous = restore_movie_result(restored.frames, restored.registration)
    assert previous.correspondence_diagnostics == base.correspondence_diagnostics
    for expected, actual in zip(corrected.frames, restored.registration.frames, strict=True):
        np.testing.assert_array_equal(actual.image.data, expected.image.data)
    script = """
import sys
for name in ('cv2', 'torch', 'kornia', 'torchvision', 'lightglue'):
    sys.modules[name] = None
from stmviewer.session_archive import load_session
state = load_session(sys.argv[1])
assert state.graph.revision == 'pending-akaze'
assert state.registration.graph_application.graph.config.method == 'akaze'
assert state.registration.predecessor.correspondence_diagnostics[1].model_provenance
assert all(sys.modules[name] is None for name in ('cv2', 'torch', 'kornia', 'torchvision', 'lightglue'))
"""
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONPATH=str(Path(__file__).resolve().parents[2]))
    subprocess.run([sys.executable, '-c', script, str(path)], env=env, check=True, capture_output=True, text=True)
