"""Small paired fixtures exercise E2 shuffles, distance spaces and graph replay."""

import json
from types import SimpleNamespace

import numpy as np
import pytest

from stmdomains.experiments import e1_run, e2_pipeline
from stmdomains.experiments.training import evaluate
from stmdomains.experiments.training.partition import fit_feature_adapter, partition_graph
from stmdomains.experiments.training.predict import label_numbers


SCOPE = dict(regime="transfer", scale_px=48, sampler="grid", feature_id="fixture")


def adapter_fixture():
    train = np.array([[1., 0.], [1., .1], [.5, 1.], [0., 1.], [-1., 0.], [0., -1.]])
    edges = np.array([[i, i + 1] for i in range(len(train) - 1)])
    return fit_feature_adapter(train, edges, list("abcdef"), scope=SCOPE)


def test_shared_shuffles_preserve_all15_availability_patterns_and_outside_scope():
    valid = np.ones((15, 24), bool)
    valid[3, 8:16] = False
    valid[[0, 8], 16:] = False
    eligible = np.ones(24, bool)
    eligible[[0, 8, 16, 23]] = False
    original = valid.copy()
    key = "transfer/grid/sample-without-truth"
    first = e2_pipeline.permutations(valid, eligible, key)
    again = e2_pipeline.permutations(valid, eligible, key)
    np.testing.assert_array_equal(first, again)
    np.testing.assert_array_equal(valid, original)
    assert first.shape == (5, 24)
    assert not np.array_equal(first, e2_pipeline.permutations(valid, eligible, key + "/other"))
    for order in first:
        np.testing.assert_array_equal(np.sort(order), np.arange(24))
        np.testing.assert_array_equal(order[~eligible], np.flatnonzero(~eligible))
        np.testing.assert_array_equal(valid[:, order], valid)
        assert np.count_nonzero(order != np.arange(24)) > 0
        # Unique whole-vector tags retain their within-vector relation. Every
        # readout uses the same donor node, including linked content/angle.
        for feature in range(15):
            values = np.column_stack((np.arange(24) + feature * 100,
                                      -3 * np.arange(24) - feature * 300)).astype(float)
            values[~valid[feature]] = np.nan
            shuffled = values[order]
            np.testing.assert_array_equal(np.isfinite(shuffled), np.isfinite(values))
            keep = valid[feature]
            np.testing.assert_array_equal(shuffled[keep, 0] - feature * 100, order[keep])
            np.testing.assert_array_equal(shuffled[keep, 1], -3 * shuffled[keep, 0])


def test_empty_and_singleton_shuffle_strata_are_explicit_identity_controls():
    valid = np.array([[True, True, False], [True, False, False]])
    for eligible in (np.zeros(3, bool), np.ones(3, bool)):
        actual = e2_pipeline.permutations(valid, eligible, "singleton")
        np.testing.assert_array_equal(actual, np.tile(np.arange(3), (5, 1)))
    assert e2_pipeline.permutations(np.empty((15, 0), bool), np.empty(0, bool), "empty").shape == (5, 0)
    with pytest.raises(ValueError, match="feature-by-node"):
        e2_pipeline.permutations(np.ones((3, 5), bool), np.ones(3, bool), "wrong")


def test_angle_chord_wraps_at_two_pi_without_identifying_opposite_directions():
    epsilon = 1e-4
    angles = np.array([-np.pi + epsilon, np.pi - epsilon, epsilon])
    vectors = np.column_stack((np.cos(angles), np.sin(angles)))
    edges = np.array([[0, 1], [0, 2]])
    actual = e2_pipeline.distances(vectors, edges, np.ones(3, bool))
    assert actual[0] == pytest.approx(2 * np.sin(epsilon), abs=1e-14)
    assert actual[1] == pytest.approx(2.)
    assert abs(angles[0] - angles[1]) > 6  # Raw angle subtraction would fail here.


def test_native_and_unit_distance_are_distinct_and_scope_does_not_mutate_inputs():
    features = np.array([[1., 0.], [2., 0.], [0., 1.], [np.nan, 1.], [0., 0.], [1., 1.]])
    original = features.copy()
    scope = np.array([True, True, True, True, True, False])
    adapter = adapter_fixture()
    frozen = json.dumps(adapter, sort_keys=True, allow_nan=False)
    coordinates, valid = e2_pipeline.spaces(features, adapter, scope)
    assert valid.tolist() == [True, True, True, False, False, False]
    edges = np.array([[0, 1], [0, 2], [1, 3], [0, 4], [1, 5]])
    native = e2_pipeline.distances(coordinates[0], edges, valid)
    unit = e2_pipeline.distances(coordinates[1], edges, valid)
    np.testing.assert_allclose(native[:2], [1., np.sqrt(2)])
    np.testing.assert_allclose(unit[:2], [0., np.sqrt(2)])
    assert np.isnan(native[2:]).all() and np.isnan(unit[2:]).all()
    assert np.isnan(coordinates[0][-1]).all()
    np.testing.assert_array_equal(features, original)
    assert json.dumps(adapter, sort_keys=True, allow_nan=False) == frozen


def test_actual_graph_replay_matches_original_partition_for_every_refusal_stage():
    adapter = adapter_fixture()
    features = np.array([[1., 0.], [2., 0.], [1., .05], [0., 1.], [0., 2.], [np.nan, 1.], [0., 0.], [.1, 1.]])
    ids = ["z", "a", "y", "b", "x", "c", "w", "d"]
    edges = np.array([[i, i + 1] for i in range(len(ids) - 1)])
    scope = np.ones(len(ids), bool)
    hard = np.ones(len(ids), bool)
    hard[2] = False
    full = hard.copy()
    full[4] = False
    coordinates, valid = e2_pipeline.spaces(features, adapter, scope)
    distance = e2_pipeline.distances(coordinates[2], edges, valid, scale=adapter["edge_median"])
    actual = e2_pipeline.predictions(ids, edges, distance, valid, adapter, hard, full, 2)
    for method in ("fh4", "mws"):
        for stage, mask, minimum in (("H_M0", hard, 1), ("H_M1", hard, 2),
                                     ("A1S1M0", full, 1), ("A1S1M1", full, 2)):
            original = partition_graph(ids, edges, features, adapter, method=method,
                                       order_pass=mask, min_size=minimum)
            np.testing.assert_array_equal(distance, original["edge_distances"])
            np.testing.assert_array_equal(actual[f"{method}_before"], label_numbers(original["proposal_component_ids"]))
            np.testing.assert_array_equal(actual[f"{method}_{stage}"], label_numbers(original["final_component_ids"]))
        # Hard refusal happens after proposals, and zero/NaN features never propose.
        assert actual[f"{method}_before"][2] > 0 and actual[f"{method}_H_M0"][2] == 0
        assert not actual[f"{method}_before"][[5, 6]].any()


def test_unavailable_adapter_does_not_turn_finite_features_into_one_domain():
    features = np.ones((4, 2))
    edges = np.array([[0, 1], [1, 2], [2, 3]])
    adapter = fit_feature_adapter(features, edges, list("abcd"), scope=SCOPE)
    assert not adapter["available"]
    coordinates, valid = e2_pipeline.spaces(features, adapter, np.ones(4, bool))
    assert not valid.any()
    distance = e2_pipeline.distances(coordinates[2], edges, valid)
    assert np.isnan(distance).all()
    actual = e2_pipeline.predictions(list("abcd"), edges, distance, valid, adapter,
                                    np.ones(4, bool), np.ones(4, bool), 2)
    assert not any(value.any() for value in actual.values())


@pytest.mark.parametrize("tamper_baseline", [False, True])
def test_miniature_generation_keeps_common_pairs_before_h_and_refuses_incomplete_freeze(tmp_path, monkeypatch, tamper_baseline):
    def forbidden(*args, **kwargs):
        raise AssertionError("Phase one opened evaluation truth")

    monkeypatch.setattr(e1_run, "_truth_bundle", forbidden)
    monkeypatch.setattr(evaluate, "_truth_bundle", forbidden)
    adapter = adapter_fixture()
    features = np.array([[1., 0.], [1., .2], [.2, 1.], [0., 1.]])
    ids = list("abcd")
    rows = [dict(element_id=ident, raw_edge_xy=[i + .5, .5], available=True)
            for i, ident in enumerate(ids)]
    edges = np.array([[0, 1], [1, 2], [2, 3]])
    # Available features with invalid ACF measurement must still enter pair
    # comparisons and permutation strata; H affects domain refusals only.
    description = dict(available=np.ones(4, bool), valid=np.zeros(4, bool),
                       acf_score=np.ones(4), second_direction_ratio=np.ones(4), energy=np.ones(4))
    runs, entries, sources = [], [], {}
    for regime in ("transfer", "transductive"):
        runs.append(dict(run_id=f"{regime}/fft", regime=regime, family="fft",
                         source_run_id=f"{regime}/fft", baseline=True))
        for sampler in ("grid", "centers"):
            for method in ("fh4", "mws"):
                directory = f"{regime}/{sampler}/{method}"
                entries.append(dict(run_id=f"{regime}/fft", regime=regime, sampler=sampler,
                                    family="fft", partition=method, sample_id="fixture", kind="synthetic",
                                    directory=directory, evaluation_input="metrics-input.npz", pixel_spacing_xy=[1., 1.]))
                original = partition_graph(ids, edges, features, adapter, method=method,
                                           order_pass=np.zeros(4, bool), min_size=4 if sampler == "grid" else 8)
                sources[f"{directory}/metrics-input.npz"] = dict(edges=edges,
                    before=label_numbers(original["proposal_component_ids"]), after=label_numbers(original["final_component_ids"]))
    if tamper_baseline:
        sources["transfer/grid/fh4/metrics-input.npz"]["before"][-1] = 0
    groups = {sampler: dict(group_id=sampler, sampler=sampler, record=dict(sample_id="fixture"))
              for sampler in ("grid", "centers")}
    inputs = SimpleNamespace(entries=entries, groups=groups, threshold=.5, rows=lambda _: rows,
                             descriptor=lambda _: description, load_npz=sources.__getitem__)
    bank = SimpleNamespace(inputs=inputs, runs=runs, features=lambda *_: features,
                           adapter=lambda *_: adapter, audit=lambda: {})
    output = tmp_path / "miniature"
    output.mkdir()
    with pytest.raises(ValueError, match="Baseline replay differs" if tamper_baseline else "Incomplete E2 matrix"):
        e2_pipeline.generate(bank, output)
    assert not (output / "prediction-freeze.json").exists()
    if tamper_baseline:
        return
    files = sorted((output / "predictions").glob("*.npz"))
    assert len(files) == 4
    for path in files:
        with np.load(path, allow_pickle=False) as saved:
            np.testing.assert_array_equal(saved["common"], np.ones(4, bool))
            assert not saved["hard"].any()
            assert np.any(saved["permutations"] != np.arange(4))
            np.testing.assert_array_equal(saved["edges"], edges)
            for index, order in enumerate(np.vstack((np.arange(4), saved["permutations"]))):
                expected = np.linalg.norm(features[order[edges[:, 0]]] - features[order[edges[:, 1]]], axis=1)
                np.testing.assert_allclose(saved["distances"][index, 0], expected)
            assert saved["actual_fh4_before"].all()
            assert not saved["actual_fh4_H_M0"].any()
