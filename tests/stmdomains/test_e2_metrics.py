"""Known rankings and partial references protect the E2 diagnostic contract."""

import json

import numpy as np
import pytest

from stmdomains.experiments.e2_metrics import edge_reference, pair_summary


def rows(n):
    return [dict(element_id=str(i), raw_edge_xy=[i + .5, .5], available=True,
                 transfer_split="test") for i in range(n)]


def test_boundary_is_positive_and_ties_are_grouped_without_order_bias():
    result = pair_summary([0., 1., 1., 2.], [True, True, False, False], [True] * 4)
    assert result["roc_auc"] == pytest.approx(.875)
    assert result["average_precision"] == pytest.approx(5 / 6)
    assert result["boundary_prevalence"] == .5
    assert result["roc"]["thresholds"] == [None, 2., 1., 0.]
    assert result["pr"]["precision"] == pytest.approx([1., 1., 2 / 3, .5])
    assert result["pr"]["recall"] == [0., .5, 1., 1.]
    assert result["quantiles"]["same"]["median"] == .5
    assert result["quantiles"]["different"]["median"] == 1.5
    tied = pair_summary([7.] * 4, [True, False, True, False], [True] * 4)
    assert tied["roc_auc"] == tied["average_precision"] == .5
    permuted = pair_summary([2., 1., 0., 1.], [False, False, True, True], [True] * 4)
    assert result == permuted


@pytest.mark.parametrize(("distances", "same", "eligible", "reason", "prevalence"), [
    ([1., 2.], [True, True], [True, True], "no_different_pairs", 0.),
    ([1., 2.], [False, False], [True, True], "no_same_pairs", 1.),
    ([1., 2.], [False, True], [False, False], "no_eligible_pairs", None),
    ([np.nan, np.inf], [False, True], [True, True], "no_finite_distances", None),
    ([], [], [], "no_eligible_pairs", None),
])
def test_missing_comparison_class_never_becomes_a_performance_claim(distances, same, eligible, reason, prevalence):
    result = pair_summary(distances, same, eligible)
    assert result["unavailable_reason"] == reason
    assert result["boundary_prevalence"] == prevalence
    assert result["roc_auc"] is result["average_precision"] is result["roc"] is result["pr"] is None
    json.dumps(result, allow_nan=False)


def test_common_mask_finite_denominators_and_curve_decimation_leave_exact_metrics():
    own = np.array([True, True, True, False, True])
    common = own & [True, True, False, True, True]
    result = pair_summary([1., 2., 100., 100., np.nan], [True, False, True, True, False], common)
    assert result["counts"] == dict(planned_pairs=5, eligible_pairs=3, excluded_ineligible_pairs=2,
                                    excluded_nonfinite_pairs=1, scored_pairs=2, same_pairs=1, different_pairs=1)
    assert result["roc_auc"] == result["average_precision"] == 1.
    assert pair_summary([1., 2., 100., 100., np.nan], [True, False, True, True, False], own)["roc_auc"] == .5
    values, same = np.arange(20.), np.arange(20) % 3 == 0
    full = pair_summary(values, same, np.ones(20, bool), max_curve_points=None)
    compact = pair_summary(values, same, np.ones(20, bool), max_curve_points=4)
    assert compact["roc_auc"] == full["roc_auc"]
    assert compact["average_precision"] == full["average_precision"]
    for name in ("roc", "pr"):
        assert compact[name]["full_points"] == 21
        assert compact[name]["stored_points"] == 4
        assert compact[name]["decimated"]
        assert compact[name]["thresholds"][0] is None and compact[name]["thresholds"][-1] == 0.


@pytest.mark.parametrize("kind", ["synthetic", "measurement"])
def test_zero_is_never_a_domain_and_domain_instance_not_orientation_defines_pairs(kind):
    key = "domain_labels" if kind == "synthetic" else "region_instances"
    truth = {key: np.array([0, 0, 1, 1, 2]), "evaluation_valid": np.ones(5, bool),
             "orientation_groups": np.ones(5, int)}
    result = edge_reference(rows(5), [[0, 1], [1, 2], [2, 3], [3, 4]], truth, kind, "transductive")
    assert result["valid"].tolist() == [False, False, True, True]
    assert result["same"].tolist() == [False, False, True, False]
    assert result["different"].tolist() == [False, False, False, True]
    assert result["counts"]["known_zero_nodes"] == (2 if kind == "synthetic" else 0)
    assert result["counts"]["excluded_nonpositive_pairs"] == 2


def test_transfer_scope_support_and_boundary_uncertainty_are_separate_exclusions():
    nodes = rows(7)
    nodes[0]["transfer_split"] = "train"
    nodes[2]["available"] = False
    truth = dict(region_instances=np.array([[1, 1, 1, 1, 2, 2, 2]]),
                 evaluation_valid=np.array([[True, True, True, False, True, True, True]]),
                 boundary_unscored=np.array([[False, False, False, False, True, False, False]]))
    edges = [[0, 1], [1, 2], [1, 3], [1, 4], [1, 5], [5, 6]]
    result = edge_reference(nodes, edges, truth, "measurement", "transfer")
    assert result["valid"].tolist() == [False, False, False, False, True, True]
    assert result["same"].tolist() == [False, False, False, False, False, True]
    assert result["counts"]["excluded_out_of_scope_pairs"] == 1
    assert result["counts"]["excluded_support_pairs"] == 1
    assert result["counts"]["excluded_reference_pairs"] == 2
    assert result["counts"]["uncertain_full_support_nodes"] == 1
    assert edge_reference(nodes, edges, truth, "measurement", "transductive")["valid"][0]
    synthetic = dict(domain_labels=truth["region_instances"], evaluation_valid=truth["evaluation_valid"],
                     boundary_uncertain=truth["boundary_unscored"])
    assert edge_reference(nodes, edges, synthetic, "synthetic", "transfer")["valid"][0]


def test_conservative_interiors_do_not_invent_graph_boundary_edges():
    truth = dict(region_instances=np.array([1, 1, 0, 2, 2]),
                 evaluation_valid=np.array([True, True, False, True, True]))
    local = edge_reference(rows(5), [[0, 1], [1, 2], [2, 3], [3, 4]], truth, "measurement", "transfer")
    summary = pair_summary([1., 5., 6., 2.], local["same"], local["valid"])
    assert summary["unavailable_reason"] == "no_different_pairs"
    assert summary["counts"]["same_pairs"] == 2
    assert local["counts"]["different_pairs"] == 0
    # The separate all-pairs diagnostic can compare interiors, not locate their boundary.
    core = edge_reference(rows(5), [[0, 1], [0, 3], [0, 4], [1, 3], [1, 4], [3, 4]],
                          truth, "measurement", "transfer")
    assert core["counts"]["different_pairs"] == 4
    assert core["reference_scope"] == "conservative_interiors"
    missing = edge_reference(rows(5), [[0, 1]], {}, "measurement", "transfer")
    assert not missing["valid"].any() and missing["unavailable_reason"] == "missing_reference"


def test_invalid_shapes_duplicate_pairs_and_escaped_coordinates_fail_loudly():
    truth = dict(domain_labels=np.ones((1, 2), int))
    with pytest.raises(ValueError, match="Repeated undirected"):
        edge_reference(rows(2), [[0, 1], [1, 0]], truth, "synthetic", "transfer")
    with pytest.raises(ValueError, match="escape"):
        edge_reference(rows(3), [[0, 1]], truth, "synthetic", "transfer")
    with pytest.raises(ValueError, match="equally sized"):
        pair_summary([1., 2.], [True], [True, True])
    with pytest.raises(ValueError, match="nonnegative"):
        pair_summary([-1., 2.], [True, False], [True, True])
