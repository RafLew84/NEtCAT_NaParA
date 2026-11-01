"""Explicit distant pairs preserve window measurements and expose their global effect."""
from stmviewer.graph_registration import graph_pairs, solve_graph
from stmviewer.graph_types import GraphEdge
from test_graph_registration import config, sources


def window_graph(count=8):
    return solve_graph(sources(count), tuple(
        GraphEdge(i, j, (float(j - i), 0.), 'ok')
        for i, j in graph_pairs(count, 3)), config())


def test_reference_plan_deduplicates_reverse_self_and_window_pairs():
    from stmviewer.long_references import plan_long_references
    base = window_graph()
    assert plan_long_references(base, (7, 0, 7), 0, 7) == (
        (0, 4), (0, 5), (0, 6), (0, 7), (1, 7), (2, 7), (3, 7))
    assert plan_long_references(base, (4,), 3, 5) == ()


def test_one_long_connection_reduces_chain_error_without_rewriting_old_measurements():
    import numpy as np
    from stmviewer.long_references import solve_extended_graph
    base = solve_graph(sources(8), tuple(
        GraphEdge(i, j, (1.5, 0.), 'ok') if j == i + 1
        else GraphEdge(i, j, None, 'missing', 'No common structure')
        for i, j in graph_pairs(8, 3)), config())
    result = solve_extended_graph(base, (GraphEdge(0, 7, (7., 0.), 'ok'),),
                                  references=(0,), target_start=7, target_end=7,
                                  measurement_config=base.config)
    # Eight equally weighted cycle equations share a 3.5-pixel discrepancy.
    np.testing.assert_allclose(result.positions, [(i * 17 / 16, 0) for i in range(8)], atol=1e-12)
    assert result.extension.base is base
    assert result.extension.references == (0,)
    assert result.extension.measurement_config == base.config
    old = {(e.i, e.j): (e.shift_xy, e.status, e.reason, e.quality_score) for e in base.edges}
    assert {(e.i, e.j): (e.shift_xy, e.status, e.reason, e.quality_score)
            for e in result.edges if (e.i, e.j) in old} == old
    np.testing.assert_allclose(base.positions[-1], (10.5, 0), atol=1e-12)


def test_selected_huber_settings_are_preserved_for_the_extended_measurements():
    from dataclasses import replace
    from stmviewer.long_references import solve_extended_graph
    from stmviewer.robust_graph import solve_robust_graph
    from stmviewer.robust_graph_types import RobustConfig
    from stmviewer.graph_validation import validate_graph_result
    base = window_graph()
    robust = solve_robust_graph(base, RobustConfig(threshold_px=1.75, max_iterations=40))
    base = replace(base, robust_trials=(robust,))
    result = solve_extended_graph(base, (GraphEdge(0, 7, (20., 0.), 'ok'),),
                                  references=(0,), target_start=7, target_end=7,
                                  measurement_config=base.config, robust_revision=robust.revision)
    assert result.extension.base_robust_revision == robust.revision
    assert result.robust_trials[0].config == robust.config
    assert result.robust_trials[0].revision != robust.revision
    assert result.robust_trials[0].measurement_id != robust.measurement_id
    validate_graph_result(result, lambda: None)


def test_false_long_match_can_worsen_the_known_scene_without_promoting_a_result():
    import numpy as np
    from stmviewer.long_references import solve_extended_graph
    base = window_graph()
    result = solve_extended_graph(base, (GraphEdge(0, 7, (40., -15.), 'ok'),),
                                  references=(0,), target_start=7, target_end=7,
                                  measurement_config=base.config)
    truth = np.asarray([(i, 0) for i in range(8)])
    assert np.linalg.norm(np.asarray(result.positions) - truth) > 1
    np.testing.assert_allclose(base.positions, truth, atol=1e-12)
    assert result.extension.base is base


def test_huber_nonconvergence_retains_the_failed_attempt_and_its_chosen_identity():
    from dataclasses import replace
    from stmviewer.long_references import solve_extended_graph
    from stmviewer.robust_graph import solve_robust_graph
    from stmviewer.robust_graph_types import RobustConfig
    base = window_graph()
    robust = solve_robust_graph(base, RobustConfig(threshold_px=.5, max_iterations=1))
    assert robust.status == 'converged'
    base = replace(base, robust_trials=(robust,))
    result = solve_extended_graph(base, (GraphEdge(0, 7, (40., -15.), 'ok'),),
                                  references=(0,), target_start=7, target_end=7,
                                  measurement_config=base.config, robust_revision=robust.revision)
    assert result.extension.base_robust_revision == robust.revision
    assert result.robust_trials[0].status == 'iteration_limit'
    assert result.robust_trials[0].positions is None
    assert result.robust_trials[0].config == robust.config


def test_plan_rejects_invalid_full_or_unbounded_selection_without_dense_allocation():
    import pytest
    from stmviewer.long_references import plan_reference_pairs, solve_extended_graph
    from stmviewer.registration import RegistrationError
    for references, start, end in [((True,), 0, 7), ((-1,), 0, 7), ((), 0, 7),
                                    ((0,), 5, 4), ((0,), 0, 8), (tuple(range(8)), 0, 7)]:
        with pytest.raises(RegistrationError):
            plan_reference_pairs(8, (), references, start, end)
    with pytest.raises(RegistrationError, match='limit 10000'):
        plan_reference_pairs(1_000_000, (), (0,), 1, 999_999)
    base = window_graph()
    with pytest.raises(RegistrationError, match='Brak nowych par'):
        solve_extended_graph(base, (), references=(0,), target_start=1, target_end=3,
                             measurement_config=base.config)


def test_solver_requires_exact_new_plan_and_validation_rejects_altered_baseline():
    from dataclasses import replace
    import pytest
    from stmviewer.graph_validation import validate_graph_result
    from stmviewer.long_references import solve_extended_graph
    from stmviewer.registration import RegistrationError
    base = window_graph()
    edge = GraphEdge(0, 7, (7., 0.), 'ok')
    with pytest.raises(RegistrationError, match='planowi'):
        solve_extended_graph(base, (edge, edge), references=(0,), target_start=7, target_end=7,
                             measurement_config=base.config)
    result = solve_extended_graph(base, (edge,), references=(0,), target_start=7, target_end=7,
                                  measurement_config=base.config)
    changed = replace(result.edges[0], quality_score=.5)
    with pytest.raises(ValueError, match='istniejący pomiar'):
        validate_graph_result(replace(result, edges=(changed, *result.edges[1:])), lambda: None)
