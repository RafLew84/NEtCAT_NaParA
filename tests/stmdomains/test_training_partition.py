"""Independent graph examples, frozen fitting and permutation invariants."""

import copy
import json

import numpy as np
import pytest

from stmdomains.experiments.training.partition import (
    apply_refusals, fh_partition, fit_feature_adapter, mws_partition,
    neighbor_edges, partition_graph, relation_weights, transform_features,
)


SCOPE = dict(regime="transfer", scale_px=48, sampler="grid", feature_id="technical")


def test_graph_is_frame_local_canonical_and_uses_diagonals_without_distance_two_edges():
    xy = np.array([[0, 0], [16, 0], [16, 16], [32, 0], [100, 100]], float)
    ids = ["z", "a", "c", "b", "isolated"]
    edges = neighbor_edges(xy, ids)
    pairs = [(ids[a], ids[b]) for a, b in edges]
    assert pairs == [("a", "b"), ("a", "c"), ("a", "z"), ("b", "c"), ("c", "z")]
    perm = np.array([3, 0, 4, 2, 1])
    changed = neighbor_edges(xy[perm], [ids[i] for i in perm])
    assert [(ids[perm[a]], ids[perm[b]]) for a, b in changed] == pairs
    assert neighbor_edges(np.empty((0, 2)), []).shape == (0, 2)


def test_center_graph_has_median_neighbor_radius_and24px_cap():
    assert neighbor_edges(np.array([[0, 0], [30, 0]]), ["a", "b"], mode="centers").size == 0
    edges = neighbor_edges(np.array([[0, 0], [5, 0], [10, 0]]), ["a", "b", "c"], mode="centers")
    assert edges.tolist() == [[0, 1], [1, 2]]


def slow_fh(ids, edges, distances, k=4):
    """Explicit component sets and internal maxima, independent of union-find."""
    components = [{i} for i in range(len(ids))]
    internal = [0.] * len(ids)
    ordering = sorted(range(len(edges)), key=lambda j: (distances[j], *sorted(ids[i] for i in edges[j])))
    for edge in ordering:
        u, v = edges[edge]
        left = next(i for i, members in enumerate(components) if u in members)
        right = next(i for i, members in enumerate(components) if v in members)
        if left == right:
            continue
        threshold = min(internal[left] + k / len(components[left]), internal[right] + k / len(components[right]))
        if distances[edge] <= threshold:
            components[left] |= components[right]
            components[right] = set()
            internal[left] = max(internal[left], internal[right], distances[edge])
    return [min(ids[j] for j in next(c for c in components if i in c)) for i in range(len(ids))]


def test_fh_matches_explicit_component_oracle_for_ties_and_permutations():
    rng = np.random.default_rng(553)
    for _ in range(15):
        ids = [f"n{i:02}" for i in range(12)]
        edges = np.array([(a, b) for a in range(12) for b in range(a + 1, 12) if rng.random() < .4], int)
        distances = rng.integers(0, 8, len(edges)).astype(float) / 2
        result = fh_partition(ids, edges, distances)
        assert result == slow_fh(ids, edges, distances)
        perm = rng.permutation(len(ids))
        inverse = np.argsort(perm)
        order = rng.permutation(len(edges))
        permuted = fh_partition([ids[i] for i in perm], inverse[edges[order]][:, ::-1], distances[order])
        assert [permuted[inverse[i]] for i in range(len(ids))] == result


def test_mws_ideal_relations_form_two_domains_and_carry_mutex_through_merges():
    ids = ["a", "b", "c", "d"]
    edges = np.array([[0, 2], [0, 1], [2, 3], [1, 3]])
    kinds = ["repulsive", "attractive", "attractive", "attractive"]
    strength = [1., .9, .8, .7]
    result = mws_partition(ids, edges, kinds, strength)
    assert result["component_ids"] == ["a", "a", "c", "c"]
    assert result["stats"] == dict(merges=2, mutex_constraints=1, blocked_attractions=1, late_repulsive_conflicts=0)
    for perm in ([3, 2, 1, 0], [1, 3, 0, 2]):
        inverse = np.argsort(perm)
        changed = mws_partition([ids[i] for i in perm], inverse[edges[::-1]][:, ::-1], kinds[::-1], strength[::-1])
        assert [changed["component_ids"][inverse[i]] for i in range(4)] == result["component_ids"]
        assert changed["stats"] == result["stats"]


def test_mws_repulsion_precedes_attraction_at_equal_strength_and_counts_late_conflict():
    ids = ["a", "b", "c"]
    edges = np.array([[0, 1], [1, 2], [0, 2]])
    kinds = ["attractive", "attractive", "repulsive"]
    tied = mws_partition(ids, edges, kinds, [1., 1., 1.])
    assert tied["component_ids"] == ["a", "a", "c"]
    assert tied["stats"]["blocked_attractions"] == 1
    late = mws_partition(ids, edges, kinds, [1., 1., .5])
    assert late["component_ids"] == ["a", "a", "a"]
    assert late["stats"]["late_repulsive_conflicts"] == 1


def test_mws_neutral_edges_do_not_join_and_missing_nodes_stay_unavailable():
    result = mws_partition(["a", "b", "c"], [[0, 1], [1, 2]],
                           ["none", "unavailable"], [0., np.nan], valid=[True, True, False])
    assert result["component_ids"] == ["a", "b", None]


def test_relation_quantile_ties_are_neutral_and_missing_is_not_attractive():
    kinds, strength = relation_weights([0., 1., 2., np.nan], 1., 1.)
    assert kinds.tolist() == ["attractive", "none", "repulsive", "unavailable"]
    np.testing.assert_equal(strength, [1., 0., 1., np.nan])
    kinds, _ = relation_weights([0., .1], 0., 0.)
    assert kinds.tolist() == ["none", "repulsive"]


def test_gate_removal_recomputes_connectivity_and_keeps_small_proposals_visible():
    ids = list("abcdefghi")
    edges = np.array([[i, i + 1] for i in range(8)])
    passed = np.ones(9, bool)
    passed[4] = False
    final, reasons = apply_refusals(ids, edges, ["a"] * 9, passed, min_size=4)
    assert final == ["a"] * 4 + [None] + ["f"] * 4
    assert reasons[4] == "order_evidence_below_threshold"
    final, reasons = apply_refusals(ids, edges, ["a"] * 9, passed, min_size=8)
    assert final == [None] * 9
    assert reasons[0] == reasons[-1] == "component_below_minimum_size"


def test_adapter_fits_only_explicit_train_and_has_no_inference_mutation():
    rng = np.random.default_rng(813)
    train = rng.normal(size=(30, 37))
    ids = [f"train{i:03}" for i in range(len(train))]
    edges = np.array([[i, i + 1] for i in range(len(train) - 1)])
    adapter = fit_feature_adapter(train, edges, ids, scope=SCOPE)
    assert adapter["available"]
    assert np.asarray(adapter["components"]).shape == (24, 37)
    frozen = json.dumps(adapter, sort_keys=True, allow_nan=False)
    for heldout in [rng.normal(size=(8, 37)), rng.normal(size=(8, 37)) * 1000]:
        transformed, valid = transform_features(heldout, adapter)
        normalized = heldout / np.linalg.norm(heldout, axis=1, keepdims=True)
        expected = (normalized - adapter["mean"]) @ np.array(adapter["components"]).T
        np.testing.assert_allclose(transformed, expected, atol=1e-14)
        assert valid.all()
    assert json.dumps(adapter, sort_keys=True, allow_nan=False) == frozen
    perm = rng.permutation(len(train))
    inverse = np.argsort(perm)
    shuffled = fit_feature_adapter(train[perm], inverse[edges[::-1]], [ids[i] for i in perm], scope=SCOPE)
    assert shuffled == adapter


def test_constant_or_empty_training_edges_are_unavailable_not_one_domain():
    ids = ["a", "b", "c", "d"]
    edges = np.array([[0, 1], [1, 2], [2, 3]])
    adapter = fit_feature_adapter(np.ones((4, 3)), edges, ids, scope=SCOPE)
    assert not adapter["available"]
    assert adapter["reason"] == "degenerate_training_edge_distances"
    for method in ["fh4", "mws"]:
        prediction = partition_graph(ids, edges, np.ones((4, 3)), adapter, method=method)
        assert prediction["proposal_component_ids"] == [None] * 4
        assert prediction["final_component_ids"] == [None] * 4
        assert np.isnan(prediction["edge_distances"]).all()
    adapter = fit_feature_adapter(np.eye(4), np.empty((0, 2), int), ids, scope=SCOPE)
    assert adapter["reason"] == "no_valid_training_edges"


def test_zero_and_nonfinite_vectors_refuse_but_zero_PCA_coordinate_is_valid():
    train = np.array([[1., 0.], [0., 1.], [-1., 0.], [0., -1.]])
    adapter = fit_feature_adapter(train, [[0, 1], [1, 2], [2, 3]], list("abcd"), scope=SCOPE)
    output, valid = transform_features([[0., 0.], [np.nan, 1.], [1., 0.]], adapter)
    assert valid.tolist() == [False, False, True]
    assert np.isnan(output[:2]).all()
    # A centered projected descriptor is not itself a zero input vector.
    centered = copy.deepcopy(adapter)
    centered["mean"] = [1., 0.]
    output, valid = transform_features([[1., 0.]], centered)
    assert valid.tolist() == [True]
    assert np.all(output == 0)


def test_graph_rejects_accidental_duplicate_ids_edges_and_scope_omission():
    with pytest.raises(ValueError, match="unique"):
        neighbor_edges([[0, 0], [16, 0]], ["same", "same"])
    with pytest.raises(ValueError, match="Duplicate"):
        fh_partition(["a", "b"], [[0, 1], [1, 0]], [1., 1.])
    with pytest.raises(ValueError, match="scope"):
        fit_feature_adapter(np.eye(2), [[0, 1]], ["a", "b"], scope={})


@pytest.mark.parametrize("method", ["fh4", "mws"])
def test_empty_sample_graph_works_with_a_valid_nonempty_frozen_training_adapter(method):
    adapter = fit_feature_adapter(np.eye(3), [[0, 1], [1, 2]], list("abc"), scope=SCOPE)
    result = partition_graph([], np.empty((0, 2), int), np.empty((0, 3)), adapter,
                             method=method, order_pass=np.empty(0, bool))
    assert result["proposal_component_ids"] == result["final_component_ids"] == result["reasons"] == []
    assert result["edge_distances"].shape == result["available"].shape == (0,)
