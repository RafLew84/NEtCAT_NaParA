"""Existing pair methods feed the same graph and recorded LS/Huber measurements."""

from pathlib import Path

import numpy as np

from stmviewer.graph_registration import register_graph
from stmviewer.series import open_frame_series

FIXTURE = Path(__file__).parent / 'fixtures' / 'registration' / 'cpu.mpp'


def test_phase_graph_uses_known_original_translations_without_model_weights():
    frames = open_frame_series([FIXTURE])
    before = [frame.data.copy() for frame in frames]
    trial = register_graph(frames, method='phase_correlation')

    np.testing.assert_allclose(trial.positions, [(0, 0), (2, -1), (-1, 1)], atol=.3)
    assert [(edge.i, edge.j) for edge in trial.edges] == [(0, 1), (0, 2), (1, 2)]
    assert trial.config.method == 'phase_correlation'
    assert trial.config.weights_path is None and trial.config.weights_sha256 is None
    assert trial.config.device == 'CPU'
    assert trial.config.settings_version == 2
    assert trial.measured_pairs == 3 and trial.reused_pairs == 0
    for frame, original in zip(frames, before, strict=True):
        np.testing.assert_array_equal(frame.data, original)


def test_unnormalized_graph_keeps_unrated_measurements_for_huber():
    from stmviewer.robust_graph import solve_robust_graph
    from stmviewer.robust_graph_types import RobustConfig

    trial = register_graph(open_frame_series([FIXTURE]), method='phase_no_normalization')
    assert all(edge.status == 'manual_review' and edge.quality_score is None for edge in trial.edges)
    np.testing.assert_allclose(trial.positions, [(0, 0), (2, -1), (-1, 1)], atol=.3)
    robust = solve_robust_graph(trial, RobustConfig())
    np.testing.assert_allclose(robust.positions, trial.positions, atol=1e-7)
    assert all(edge.quality_score is None for edge in trial.edges)


def test_ecc_nonconvergence_is_missing_while_library_fault_is_fatal(monkeypatch):
    import cv2
    import pytest
    from stmviewer.registration import RegistrationError

    frames = open_frame_series([FIXTURE])
    failure = cv2.error('Iterations do not converge')
    failure.code = -7  # OpenCV StsNoConv, distinct from allocation and argument errors.

    def fail(*args, **kwargs):
        raise failure

    monkeypatch.setattr(cv2, 'findTransformECC', fail)
    trial = register_graph(frames, method='ecc_translation')
    assert trial.positions is None and len(trial.components) == 3
    assert all(edge.status == 'missing' and edge.shift_xy is None for edge in trial.edges)
    assert all('Iterations do not converge' in edge.reason for edge in trial.edges)

    failure = MemoryError('allocation failed')
    with pytest.raises(RegistrationError, match='allocation failed'):
        register_graph(frames, method='ecc_translation')
    assert all(edge.shift_xy is None for edge in trial.edges)


def test_huber_rejects_failed_measurement_even_when_saved_positions_are_consistent():
    from dataclasses import replace
    import pytest
    from stmviewer.robust_graph import solve_robust_graph

    trial = register_graph(open_frame_series([FIXTURE]), method='phase_correlation')
    malformed = replace(trial, edges=(replace(trial.edges[0], status='failed'),) + trial.edges[1:])
    with pytest.raises(ValueError, match='status'):
        solve_robust_graph(malformed)


def test_pair_progress_and_errors_include_current_and_source_frame_numbers(monkeypatch):
    from dataclasses import replace
    import cv2
    import pytest
    from stmviewer.registration import RegistrationError

    frames = tuple(replace(frame, source_frame_index=index + 2)
                   for index, frame in enumerate(open_frame_series([FIXTURE])))
    progress = []
    register_graph(frames, method='phase_correlation', progress=lambda *args: progress.append(args))
    text = next(text for _, _, text in progress if 'klatki 1–3' in text)
    assert 'cpu.mpp' in text and 'źródłowa 3' in text and 'źródłowa 5' in text

    def fail(*args, **kwargs):
        raise MemoryError('allocation failed')
    monkeypatch.setattr(cv2, 'findTransformECC', fail)
    with pytest.raises(RegistrationError, match='źródłowa 3.*źródłowa 4'):
        register_graph(frames, method='ecc_translation')
