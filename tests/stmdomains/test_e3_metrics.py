"""Independent paired examples test E3 denominators and unidentifiable cases."""

import numpy as np
import pytest

from stmdomains.experiments.e3_metrics import assignment_stability, distance_change, feature_change


def test_feature_changes_keep_zero_norm_and_nonfinite_cases_explicit():
    result = feature_change([[3., 4.], [0., 0.], [1., np.nan], [1., 0.]],
                            [[6., 8.], [2., 0.], [1., 2.], [100., 0.]], [True, True, True, False])
    np.testing.assert_allclose(result["absolute_l2"], [5., 2., np.nan, np.nan])
    np.testing.assert_allclose(result["relative_l2"], [1., np.nan, np.nan, np.nan])
    np.testing.assert_allclose(result["norm_change"], [5., 2., np.nan, np.nan])
    assert result["counts"] == dict(planned_nodes=4, eligible_nodes=3, compared_nodes=2,
        excluded_scope_nodes=1, excluded_nonfinite_nodes=1, relative_nodes=1, zero_base_norm_nodes=1)


def test_distance_rank_ties_and_frozen_relations_use_full_paired_denominators():
    edges = np.array([[i, i + 1] for i in range(5)])
    result = distance_change([0., 1., 1., 3., np.nan], [0., 1., 2., 2., 4.],
                             edges, np.ones(5, bool), 1., 2.)
    assert result["counts"]["compared_pairs"] == 4
    assert result["counts"]["excluded_nonfinite_pairs"] == 1
    assert result["rmse"] == pytest.approx(np.sqrt(.5))
    assert result["median_absolute_change"] == .5
    # Mean ranks [1,2.5,2.5,4] versus [1,2,3.5,3.5] give 5/6.
    assert result["spearman"] == pytest.approx(5 / 6)
    assert result["relation_transitions"] == [[1, 0, 0], [0, 2, 0], [0, 1, 0]]
    assert result["relation_change_fraction"] == .25
    assert result["relation_order"] == ["attractive", "neutral", "repulsive"]
    no_calibration = distance_change([0., 1.], [0., 2.], [[0, 1], [1, 2]], [True, True])
    assert no_calibration["relation_change_fraction"] is None
    assert no_calibration["relation_unavailable_reason"] == "no_calibrated_thresholds"


@pytest.mark.parametrize(("base", "changed", "eligible", "reason"), [
    ([1., 1.], [1., 2.], [True, True], "constant_base_distances"),
    ([1., 2.], [1., 1.], [True, True], "constant_changed_distances"),
    ([1., 2.], [1., 2.], [True, False], "fewer_than_two_pairs"),
    ([1., 2.], [1., 2.], [False, False], "fewer_than_two_pairs"),
])
def test_distance_spearman_is_unavailable_for_flat_or_insufficient_pairs(base, changed, eligible, reason):
    result = distance_change(base, changed, [[0, 1], [1, 2]], eligible, 1., 1.)
    assert result["spearman"] is None and result["spearman_unavailable_reason"] == reason
    if not any(eligible):
        assert result["rmse"] is result["median_absolute_change"] is result["relation_change_fraction"] is None


def test_assignment_stability_ignores_label_permutation_and_preserves_refusal_counts():
    result = assignment_stability([1, 1, 2, 2, 0, 3], [91, 91, 7, 7, 0, 0],
                                  [[0, 1], [1, 2], [2, 3], [3, 4], [4, 5]], [True] * 5 + [False])
    assert result["assignment_jaccard"] == result["boundary_edge_jaccard"] == 1.
    assert result["assignment_status_change_fraction"] == result["pairwise_partition_disagreement"] == 0.
    assert result["counts"]["compared_pairs"] == 6
    assert result["counts"]["compared_boundary_edges"] == 3
    assert result["counts"]["boundary_union_edges"] == 1
    assert result["counts"]["scope_nodes"] == 5
    assert result["counts"]["lost_assignment_nodes"] == 0


def test_assignment_change_partition_change_and_boundary_change_have_distinct_scopes():
    result = assignment_stability([1, 1, 2, 2, 0, 0], [7, 8, 8, 0, 9, 0],
                                  [[0, 1], [1, 2], [2, 3], [3, 4], [4, 5]], [True] * 6)
    counts = result["counts"]
    assert (counts["assigned_intersection_nodes"], counts["assigned_union_nodes"]) == (3, 5)
    assert result["assignment_jaccard"] == .6
    assert result["assignment_status_change_fraction"] == pytest.approx(2 / 6)
    assert counts["lost_assignment_nodes"] == counts["gained_assignment_nodes"] == 1
    assert counts["compared_pairs"] == 3 and counts["partition_disagreed_pairs"] == 2
    assert result["pairwise_partition_disagreement"] == pytest.approx(2 / 3)
    assert counts["boundary_union_edges"] == 2 and counts["boundary_intersection_edges"] == 0
    assert result["boundary_edge_jaccard"] == 0.
    assert counts["compared_boundary_edges"] == 2


def test_empty_assignments_or_boundary_unions_are_not_perfect_stability():
    empty = assignment_stability([0, 0], [0, 0], [[0, 1]], [True, True])
    assert empty["assignment_jaccard"] is empty["pairwise_partition_disagreement"] is empty["boundary_edge_jaccard"] is None
    assert empty["assignment_status_change_fraction"] == 0.
    assert empty["counts"]["assignment_status_changed_nodes"] == 0
    one_domain = assignment_stability([1, 1], [8, 8], [[0, 1]], [True, True])
    assert one_domain["assignment_jaccard"] == 1.
    assert one_domain["boundary_edge_jaccard"] is None
    assert one_domain["boundary_unavailable_reason"] == "empty_boundary_union"
    no_scope = assignment_stability([1], [2], [], [False])
    assert no_scope["assignment_status_change_fraction"] is None


def test_invalid_metric_shapes_and_duplicate_edges_fail_loudly():
    with pytest.raises(ValueError, match="align"):
        feature_change([[1., 2.]], [[1.]], [True])
    with pytest.raises(ValueError, match="Repeated undirected"):
        distance_change([1., 2.], [1., 2.], [[0, 1], [1, 0]], [True, True])
    with pytest.raises(ValueError, match="both frozen"):
        distance_change([1.], [2.], [[0, 1]], [True], q25=1.)
    with pytest.raises(ValueError, match="Integer assignment"):
        assignment_stability([1.], [2.], [], [True])
