"""Independent E1 ceilings and phase-one freeze checks on miniature fixtures."""

import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from stmdomains.experiments import e1_run
from stmdomains.experiments.bundle import file_hash


def test_runner_paths_are_anchored_to_the_repository():
    root = Path(__file__).resolve().parents[2]
    assert e1_run.REPO == root
    assert e1_run.PROTOCOL == root / "docs/stmdomains/ml-ae-rvae-e1-protocol.md"


def test_partition_comparison_ignores_label_numbers_but_preserves_membership_and_refusals():
    original = np.array([1, 1, 0, 2, 2, 3])
    assert e1_run.same_partition(original, np.array([91, 91, 0, 7, 7, 15]))
    assert not e1_run.same_partition(original, np.array([91, 91, 4, 7, 7, 15]))
    assert not e1_run.same_partition(original, np.array([91, 91, 0, 7, 15, 15]))
    assert not e1_run.same_partition(original, np.array([91, 91, 0, 7, 7, 7]))
    assert e1_run.same_partition(np.empty(0, int), np.empty(0, int))


def test_readiness_measures_hard_valid_components_and_predicts_minimum_losses():
    truth = np.array([1, 1, 1, 1, 2, 2, 0])
    edges = np.array([[i, i + 1] for i in range(6)])
    available = np.ones(7, bool)
    hard = np.array([True, True, False, True, True, True, True])
    oracle = np.array([10, 10, 0, 20, 30, 30, 0])
    result = e1_run.readiness(truth, edges, hard, available, 2, oracle)
    assert result["regions"] == [
        dict(truth_id=1, supported=4, hard_valid=3, components=2, sizes=[2, 1], lost_to_minimum=1),
        dict(truth_id=2, supported=2, hard_valid=2, components=1, sizes=[2], lost_to_minimum=0),
    ]
    assert result["positive_edges"] == 2
    assert result["between_positive_edges"] == 1
    assert result["matches_induced_truth_graph"] is True
    with pytest.raises(ValueError, match="induced truth graph"):
        e1_run.readiness(truth, edges, hard, available, 2, np.array([10, 10, 0, 10, 30, 30, 0]))
    # Passing the post-minimum partition is a stage error: the singleton is lost.
    with pytest.raises(ValueError, match="induced truth graph"):
        e1_run.readiness(truth, edges, hard, available, 2, np.array([10, 10, 0, 0, 30, 30, 0]))


def test_readiness_keeps_unobservable_positive_truth_distinct_from_background():
    edges = np.empty((0, 2), int)
    positive = e1_run.readiness(np.array([1]), edges, np.array([False]), np.array([False]), 4, np.array([0]))
    background = e1_run.readiness(np.array([0]), edges, np.array([True]), np.array([True]), 4, np.array([0]))
    assert positive["regions"] == [dict(truth_id=1, supported=0, hard_valid=0, components=0, sizes=[], lost_to_minimum=0)]
    assert background["regions"] == []
    assert positive["positive_edges"] == background["positive_edges"] == 0


def test_generate_freezes_all_gate_predictions_without_opening_truth(tmp_path, monkeypatch):
    protocol = tmp_path / "protocol.md"
    protocol.write_text("Frozen miniature E1 protocol\n")
    monkeypatch.setattr(e1_run, "PROTOCOL", protocol)

    def forbidden(*args, **kwargs):
        raise AssertionError("Phase one attempted to open evaluation truth")

    monkeypatch.setattr(e1_run, "_truth_bundle", forbidden)
    ids = ["node-z", "node-a", "node-c", "node-b"]
    rows = [dict(element_id=ident, available=True, raw_edge_xy=[i + .5, .5])
            for i, ident in enumerate(ids)]
    edges = np.array([[0, 1], [1, 2], [2, 3]])
    desc = dict(available=np.ones(4, bool), valid=np.ones(4, bool),
                acf_score=np.array([1., .1, 1., 1.]), second_direction_ratio=np.ones(4), energy=np.ones(4))
    source = dict(before=np.ones(4, int), after=np.zeros(4, int), edges=edges, available=np.ones(4, bool))
    entry = dict(run_id="transfer/fft", sampler="grid", partition="fh4", sample_id="synthetic-fixture",
                 kind="synthetic", regime="transfer", directory="fixture", evaluation_input="metrics-input.npz")
    proposals = [dict(element_id=ident, component_id="node-a") for ident in ids]
    inputs = SimpleNamespace(entries=[entry], threshold=.5, rows=lambda item: rows,
        descriptor=lambda item: desc, load_npz=lambda path: source,
        read_json=lambda path: {"extensions": {"training_v1": {"proposals": proposals}}}, save_audit=lambda: None)
    output = tmp_path / "run"
    output.mkdir()
    index, hashes = e1_run.generate(inputs, output)
    freeze = json.loads((output / "gate-freeze.json").read_text())
    assert freeze["truth_opened_for_this_run"] is False
    assert freeze["baseline_exact"] == 1
    assert freeze["protocol_sha256"] == file_hash(protocol)
    assert freeze["files"] == hashes
    assert all(file_hash(output / relative) == digest for relative, digest in hashes.items())
    with np.load(output / index[0]["prediction"], allow_pickle=False) as predictions:
        assert len(predictions.files) == 10  # Eight ablations plus before and edges.
        np.testing.assert_array_equal(predictions["before"], source["before"])
        np.testing.assert_array_equal(predictions["edges"], edges)
        assert not predictions["A1S1M1"].any()
        assert np.count_nonzero(predictions["A1S1M0"]) == 3
        assert np.count_nonzero(predictions["A0S1M1"]) == 4
