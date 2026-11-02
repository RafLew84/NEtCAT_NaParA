"""Graph methods reuse one native model and keep composite evidence."""

import numpy as np

from test_graph_measurement import native_model  # noqa: F401
from test_graph_methods import FIXTURE
from stmviewer.deep_matcher import DeepMatcherOptions
from stmviewer.graph_registration import register_graph
from stmviewer.series import open_frame_series


def test_deep_ecc_graph_refines_all_pairs_with_one_model_and_actual_pair_labels(native_model):  # noqa: F811 — pytest fixture injection
    weights, state = native_model
    state['responses'] = [(2, -1), (-1, 1), (-3, 2)]
    progress = []
    trial = register_graph(open_frame_series([FIXTURE]), method='deep_matcher_ecc',
                           deep_options=DeepMatcherOptions(weights, 'cpu'),
                           progress=lambda *args: progress.append(args))

    assert state['loads'] == 1 and state['calls'] == 3
    np.testing.assert_allclose(trial.positions, [(0, 0), (2, -1), (-1, 1)], atol=.3)
    assert trial.config.method == 'deep_matcher_ecc'
    assert all(edge.status == 'manual_review' and edge.quality_score is None for edge in trial.edges)
    assert all(edge.hybrid_diagnostics.final_shift_xy == edge.shift_xy for edge in trial.edges)
    assert any('Para 1 → 3' in text and 'ECC' in text for _, _, text in progress)
    assert dict(trial.config.backend_settings)['second_stage_device'] == 'CPU'


def test_local_refusal_remains_missing_with_evidence_and_no_deep_fallback(native_model):  # noqa: F811 — pytest fixture injection
    weights, state = native_model
    state['responses'] = [(100, 100), (-1, 1), (-3, 2)]
    trial = register_graph(open_frame_series([FIXTURE]), method='deep_local_consensus',
                           deep_options=DeepMatcherOptions(weights, 'cpu'))
    refused = trial.edges[0]
    assert refused.status == 'missing' and refused.shift_xy is None
    assert refused.local_diagnostics.final_shift_xy is None
    assert refused.local_diagnostics.deep_shift_xy == (100, 100)
    assert refused.reason and 'Para 1 → 2' in refused.reason
    assert state['loads'] == 1 and state['calls'] == 3
    assert trial.config.method == 'deep_local_consensus'


def test_deep_ecc_model_refusal_is_missing_without_losing_other_pairs(native_model):  # noqa: F811 — pytest fixture injection
    weights, state = native_model
    state['responses'] = [None, (-1, 1), (-3, 2)]
    trial = register_graph(open_frame_series([FIXTURE]), method='deep_matcher_ecc',
                           deep_options=DeepMatcherOptions(weights, 'cpu'))
    assert trial.edges[0].shift_xy is None
    assert 'Only 2 feature matches' in trial.edges[0].reason
    assert trial.positions is not None and trial.chain_positions is None
    np.testing.assert_allclose(trial.positions, [(0, 0), (2, -1), (-1, 1)], atol=.3)


def test_composite_code_change_invalidates_pair_cache_and_records_cpu_libraries(native_model, monkeypatch):  # noqa: F811 — pytest fixture injection
    from pathlib import Path
    weights, state = native_model
    frames = open_frame_series([FIXTURE])
    options = DeepMatcherOptions(weights, 'cpu')
    before = register_graph(frames, method='deep_matcher_ecc', deep_options=options)
    original_read = Path.read_bytes

    def updated_code(path):
        content = original_read(path)
        return content + b'\n# changed ECC code\n' if path.name == 'ecc_translation.py' else content

    monkeypatch.setattr(Path, 'read_bytes', updated_code)
    after = register_graph(frames, method='deep_matcher_ecc', deep_options=options, previous=before)
    assert after.measured_pairs == 3 and after.reused_pairs == 0
    assert after.config.code_version != before.config.code_version
    assert 'opencv-python' in dict(after.config.libraries)


def test_huber_rejects_composite_diagnostics_bound_to_another_measurement(native_model):  # noqa: F811 — pytest fixture injection
    from dataclasses import replace
    import pytest
    from stmviewer.robust_graph import solve_robust_graph
    weights, _ = native_model
    graph = register_graph(open_frame_series([FIXTURE]), method='deep_matcher_ecc',
                           deep_options=DeepMatcherOptions(weights, 'cpu'))
    diagnostics = replace(graph.edges[0].hybrid_diagnostics, final_shift_xy=(99, 99))
    malformed = replace(graph, edges=(replace(graph.edges[0], hybrid_diagnostics=diagnostics),)
                        + graph.edges[1:])
    with pytest.raises(ValueError, match='diagnoz'):
        solve_robust_graph(malformed)
