"""Known measurements → anchored equal-weight graph, independent of matcher quality."""

import numpy as np

from stmviewer.graph_registration import solve_graph
from stmviewer.graph_types import GraphConfig, GraphEdge, GraphSource


def sources(count):
    return tuple(GraphSource('known.mpp', i, (80, 80), f'{i:064x}') for i in range(count))


def config(window=3):
    return GraphConfig(window, 'known.ckpt', 'a' * 64, 'cpu', 'CPU', (), (), 'fixture')


def test_graph_preserves_signed_turns_and_first_frame_anchor():
    edges = (GraphEdge(0, 1, (3., -2.), 'ok'),
             GraphEdge(1, 2, (-5., 3.), 'ok'),
             GraphEdge(0, 2, (-2., 1.), 'ok'))
    trial = solve_graph(sources(3), edges, config())
    np.testing.assert_allclose(trial.positions, ((0, 0), (3, -2), (-2, 1)), atol=1e-12)
    assert trial.chain_positions == ((0, 0), (3, -2), (-2, 1))
    assert trial.components == ((0, 1, 2),)
    assert trial.bridges == ()
    np.testing.assert_allclose([e.residual_xy for e in trial.edges], 0., atol=1e-12)


def test_missing_adjacent_pair_uses_redundant_route_without_inventing_chain():
    edges = (GraphEdge(0, 1, None, 'missing', 'Only 2 feature matches'),
             GraphEdge(0, 2, (2., 1.), 'ok'),
             GraphEdge(1, 2, (-1., 3.), 'ok'),
             GraphEdge(1, 3, (2., 4.), 'ok'),
             GraphEdge(2, 3, (3., 1.), 'ok'))
    trial = solve_graph(sources(4), edges, config())
    np.testing.assert_allclose(trial.positions, ((0, 0), (3, -2), (2, 1), (5, 2)), atol=1e-12)
    assert trial.chain_positions is None
    assert trial.bridges == ((0, 2),)
    assert trial.edges[0].shift_xy is None
    assert trial.edges[0].residual_xy is None
    assert trial.edges[0].reason == 'Only 2 feature matches'


def test_disconnected_components_do_not_reset_unconnected_frames_to_zero():
    edges = (GraphEdge(0, 1, (3., -2.), 'ok'),
             GraphEdge(1, 2, None, 'missing', 'Not enough matches'),
             GraphEdge(2, 3, (-5., 3.), 'ok'))
    trial = solve_graph(sources(5), edges, config())
    assert trial.positions is None
    assert trial.chain_positions is None
    assert trial.components == ((0, 1), (2, 3), (4,))
    assert trial.bridges == ((0, 1), (2, 3))
    assert all(edge.residual_xy is None for edge in trial.edges)


def test_equal_weight_ls_reports_disagreement_without_weighting_model_confidence():
    edges = (GraphEdge(0, 1, (1., 0.), 'ok', quality_score=1.),
             GraphEdge(1, 2, (1., 0.), 'low_confidence', quality_score=.01),
             GraphEdge(0, 2, (8., 0.), 'ok', quality_score=1.))
    trial = solve_graph(sources(3), edges, config())
    # Three inconsistent equations share the six-pixel discrepancy equally.
    np.testing.assert_allclose(trial.positions, ((0, 0), (3, 0), (6, 0)), atol=1e-12)
    assert trial.chain_positions == ((0, 0), (1, 0), (2, 0))
    np.testing.assert_allclose([e.residual_xy for e in trial.edges], ((2, 0), (2, 0), (-2, 0)), atol=1e-12)
    assert trial.edges[1].quality_score == .01


def test_periodic_alias_with_consistent_edges_is_not_relabelled_as_verified():
    # A periodic image can consistently align to another repeat at +16 px.
    trial = solve_graph(sources(3), (GraphEdge(0, 1, (16., 0.), 'low_confidence'),
                                    GraphEdge(0, 2, (32., 0.), 'low_confidence'),
                                    GraphEdge(1, 2, (16., 0.), 'low_confidence')), config())
    np.testing.assert_allclose(trial.positions, ((0, 0), (16, 0), (32, 0)), atol=1e-12)
    np.testing.assert_allclose([e.residual_xy for e in trial.edges], 0., atol=1e-12)
    assert all(e.status == 'low_confidence' for e in trial.edges)


def test_malformed_measurement_aborts_instead_of_publishing_invalid_positions():
    import pytest
    from stmviewer.registration import RegistrationError
    with pytest.raises(RegistrationError, match='pomiar'):
        solve_graph(sources(2), (GraphEdge(0, 1, (float('nan'), 1.), 'ok'),), config())


def test_long_chain_has_only_bridges_and_no_recursion_limit_or_smoothing():
    edges = tuple(GraphEdge(i, i + 1, (1., -1.), 'ok') for i in range(999))
    trial = solve_graph(sources(1000), edges, config())
    assert len(trial.bridges) == 999
    assert trial.bridges[0] == (0, 1) and trial.bridges[-1] == (998, 999)
    np.testing.assert_allclose(trial.positions[-1], (999., -999.), atol=1e-6)
    assert trial.chain_positions[-1] == (999., -999.)


def test_short_series_uses_only_existing_pairs_and_refuses_single_frame():
    import pytest
    from stmviewer.graph_registration import graph_pairs
    from stmviewer.registration import RegistrationError
    assert graph_pairs(2, 5) == ((0, 1),)
    assert len(graph_pairs(1000, 3)) == 2994
    assert len(graph_pairs(1000, 5)) == 4985
    trial = solve_graph(sources(2), (GraphEdge(0, 1, (-4.5, 8.25), 'ok'),), config())
    assert trial.positions == ((0., 0.), (-4.5, 8.25))
    assert trial.bridges == ((0, 1),)
    with pytest.raises(RegistrationError, match='dwóch'):
        solve_graph(sources(1), (), config())
