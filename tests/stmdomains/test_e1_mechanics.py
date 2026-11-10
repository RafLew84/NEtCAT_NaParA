"""Small known graphs exercise E1 oracle semantics and mask interventions."""

from itertools import product

import numpy as np
import pytest

from stmdomains.experiments.e1_mechanics import (
    apply_variant, gate_masks, oracle_proposals, truth_at_rows,
)
from stmdomains.experiments.training.evaluate import evaluate_sample
from stmdomains.experiments.training.partition import fh_partition
from stmdomains.experiments.training.predict import label_numbers


@pytest.mark.parametrize("method", ["fh4", "mws"])
def test_oracle_separates_small_domains_and_naive_fh_zero_one_does_not(method):
    ids, edges = list("abcd"), np.array([[0, 1], [1, 2], [2, 3]])
    truth = np.array([1, 1, 2, 2])
    proposals = oracle_proposals(ids, edges, truth, np.ones(4, bool), method)
    assert proposals == ["a", "a", "c", "c"]
    assert fh_partition(ids, edges, [0., 1., 0.], k=4.) == ["a"] * 4
    assert apply_variant(ids, edges, proposals, np.ones(4, bool), 1)["after"].tolist() == [1, 1, 2, 2]


@pytest.mark.parametrize("method", ["fh4", "mws"])
def test_background_is_not_one_oracle_domain_and_presence_is_a_separate_mask(method):
    ids = list("abcdefg")
    edges = np.array([[i, i + 1] for i in range(6)])
    truth = np.array([0, 0, 1, 1, 0, 2, 2])
    feature_valid = np.ones(7, bool)
    feature_valid[6] = False
    proposals = oracle_proposals(ids, edges, truth, feature_valid, method)
    assert proposals == ["a", "b", "c", "c", "e", "f", None]
    program_mask = apply_variant(ids, edges, proposals, np.ones(7, bool), 1)
    assert np.count_nonzero(program_mask["after"][truth == 0]) == 3
    presence_mask = apply_variant(ids, edges, proposals, truth > 0, 1)
    assert presence_mask["after"].tolist() == [0, 0, 1, 1, 0, 2, 0]
    # Hard validity is a later refusal, never used to construct these proposals.
    hard = np.ones(7, bool)
    hard[2] = False
    assert proposals[2] == proposals[3]
    assert apply_variant(ids, edges, proposals, hard & (truth > 0), 1)["components"][2] is None
    zeros = oracle_proposals(ids, edges, np.zeros(7, int), feature_valid, method)
    assert len(set(value for value in zeros if value is not None)) == 6
    assert not apply_variant(ids, edges, zeros, np.zeros(7, bool), 1)["after"].any()


@pytest.mark.parametrize("method", ["fh4", "mws"])
def test_oracle_cannot_bridge_a_disconnected_true_domain(method):
    ids, edges = list("abcd"), np.array([[0, 1], [2, 3]])
    original_edges = edges.copy()
    proposals = oracle_proposals(ids, edges, np.ones(4, int), np.ones(4, bool), method)
    assert proposals == ["a", "a", "c", "c"]
    np.testing.assert_array_equal(edges, original_edges)
    result = apply_variant(ids, edges, proposals, np.ones(4, bool), 1)
    assert len(set(result["after"])) == 2


def test_refusal_splits_components_before_minimum_even_when_minimum_is_disabled():
    ids = list("abcdefghi")
    edges = np.array([[i, i + 1] for i in range(8)])
    proposals = ["a"] * 9
    passed = np.ones(9, bool)
    passed[4] = False
    before_minimum = apply_variant(ids, edges, proposals, passed, 1)
    minimum_four = apply_variant(ids, edges, proposals, passed, 4)
    assert before_minimum["components"] == ["a"] * 4 + [None] + ["f"] * 4
    np.testing.assert_array_equal(before_minimum["after"], minimum_four["after"])
    minimum_five = apply_variant(ids, edges, proposals, passed, 5)
    assert not minimum_five["after"].any()
    assert minimum_five["reasons"][0] == minimum_five["reasons"][-1] == "component_below_minimum_size"
    assert minimum_five["reasons"][4] == "order_evidence_below_threshold"
    assert proposals == ["a"] * 9


def test_eight_gate_variants_keep_hard_failures_and_record_independent_causes():
    available, valid = np.ones(10, bool), np.ones(10, bool)
    available[4], valid[5] = False, False
    acf, ratio, energy = np.ones(10), np.ones(10), np.ones(10)
    acf[[1, 3]], ratio[[2, 3]] = .5, .2
    acf[6], ratio[7], energy[8], energy[9] = np.nan, np.inf, 0., np.nan
    masks = gate_masks(available, valid, acf, ratio, energy, .5)
    assert np.flatnonzero(masks["hard"]).tolist() == [0, 1, 2, 3]
    assert np.flatnonzero(masks["failures"]["acf_below_threshold"]).tolist() == [1, 3]
    assert np.flatnonzero(masks["failures"]["spectral_below_threshold"]).tolist() == [2, 3]
    assert masks["failures"]["nonfinite_acf"][6]
    assert masks["failures"]["nonpositive_energy"][8]
    boundary = gate_masks([True], [True], [.5], [.25], [1.], .5)
    assert not boundary["acf"][0] and boundary["spectral"][0]
    ids = [str(i) for i in range(10)]
    edges = np.array([(i, j) for i in range(10) for j in range(i + 1, 10)])
    for acf_on, spectral_on, minimum_on in product((False, True), repeat=3):
        passed = masks["hard"] & (masks["acf"] if acf_on else True) & (masks["spectral"] if spectral_on else True)
        expected = [0] + ([] if acf_on else [1]) + ([] if spectral_on else [2])
        expected += [3] if not acf_on and not spectral_on else []
        assert np.flatnonzero(passed).tolist() == expected
        result = apply_variant(ids, edges, ["0"] * 10, passed, 4 if minimum_on else 1)
        if minimum_on and len(expected) < 4:
            expected = []
        assert np.flatnonzero(result["after"]).tolist() == expected
    with pytest.raises(ValueError, match="vectors"):
        gate_masks([True], [True], [], [1.], [1.], .5)


@pytest.mark.parametrize("method", ["fh4", "mws"])
def test_two_by_two_keeps_graph_and_evaluation_denominators_and_samples_truth_by_floor(method):
    ids = list("abcde")
    rows = [dict(element_id=ident, raw_edge_xy=[i + .99, .99], available=True)
            for i, ident in enumerate(ids)]
    raster = np.array([[1, 1, 0, 2, 2]])
    truth = truth_at_rows(rows, raster)
    assert truth.tolist() == [1, 1, 0, 2, 2]
    edges = np.array([[i, i + 1] for i in range(4)])
    original_edges = edges.copy()
    proposals = {"program": ["a"] * 5, "oracle": oracle_proposals(ids, edges, truth, np.ones(5, bool), method)}
    masks = {"program": np.ones(5, bool), "oracle": truth > 0}
    expected = {("program", "program"): [1, 1, 1, 1, 1],
                ("program", "oracle"): [1, 1, 0, 2, 2],
                ("oracle", "program"): [1, 1, 2, 3, 3],
                ("oracle", "oracle"): [1, 1, 0, 2, 2]}
    for relation_source, mask_source in product(proposals, masks):
        before = label_numbers(proposals[relation_source])
        result = apply_variant(ids, edges, proposals[relation_source], masks[mask_source], 1)
        assert result["after"].tolist() == expected[relation_source, mask_source]
        metrics = evaluate_sample(rows, truth, before, result["after"], edges)
        assert metrics["full_support_elements"] == metrics["evaluated_elements"] == 5
        assert metrics["known_zero_elements"] == 1
        assert metrics["after"]["false_known_zero_assignments"] == (mask_source == "program")
        np.testing.assert_array_equal(edges, original_edges)
    with pytest.raises(ValueError, match="outside"):
        truth_at_rows([dict(raw_edge_xy=[5., .5])], raster)
    with pytest.raises(ValueError, match="N-by-2"):
        truth_at_rows([dict(raw_edge_xy=[0., 0., 1., 0.])], raster)
    assert truth_at_rows([], raster).shape == (0,)
