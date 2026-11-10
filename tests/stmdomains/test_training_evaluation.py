"""Ground-truth fixtures for evaluation semantics; no held-out data is opened."""

import csv
import gzip
import json
from types import SimpleNamespace

import numpy as np
import pytest

from stmdomains.experiments.training.evaluate import (
    ABLATION_CASES, TWO_CASES, ZERO_CASES, PostprocessBudget,
    ablation_invariance, aggregate_comparisons, aggregate_samples, benefit_across_seeds,
    boundary_scores, continuation_summary, evaluate_frozen, evaluate_sample,
    local_pair_scores, matched_coverage, positive_boundary_points, seed_stability,
    map_current_centers, write_summary,
)
from stmdomains.experiments.training import evaluate as evaluation
from stmdomains.experiments.bundle import file_hash, write_arrays, write_json


def rows(n=4, *, available=True, split="test"):
    return [dict(element_id=f"p{i}", raw_edge_xy=[i + .5, .5],
                 available=available, transfer_split=split) for i in range(n)]


def test_all_pairs_and_actual_edges_have_separate_denominators():
    reference = np.array([1, 1, 2, 2])
    prediction = np.array([1, 2, 2, 2])
    edges = np.array([[0, 1], [1, 2], [2, 3]])
    metrics = evaluate_sample(rows(), reference, prediction, prediction, edges)
    assert metrics["after"]["pairs"]["split_rate"] == .5
    assert metrics["after"]["pairs"]["merge_rate"] == .5
    assert metrics["after"]["local_pairs"]["split_rate"] == .5
    assert metrics["after"]["local_pairs"]["merge_rate"] == 1
    assert metrics["after"]["local_pairs"]["different_reference_pairs"] == 1
    with pytest.raises(ValueError, match="Repeated"):
        local_pair_scores(reference, prediction, np.array([[0, 1], [1, 0]]))


def test_refusing_everything_never_becomes_zero_error_or_passes_single_domain():
    prediction = np.zeros(4, dtype=int)
    metrics = evaluate_sample(rows(), np.ones(4, dtype=int), prediction, prediction,
                              np.array([[0, 1], [1, 2], [2, 3]]), case="single")
    assert metrics["after"]["coverage"] == 0
    assert metrics["after"]["pairs"]["merge_rate"] is None
    assert metrics["after"]["pairs"]["split_rate"] is None
    assert not metrics["criteria"]["qualified"]


def test_known_negative_zero_is_distinct_from_unannotated_real_image():
    reference = np.array([1, 1, 0, 0])
    prediction = np.ones(4, dtype=int)
    synthetic = evaluate_sample(rows(), reference, prediction, prediction, [])
    measured = evaluate_sample(rows(), reference, prediction, prediction, [], kind="measurement")
    assert synthetic["known_zero_elements"] == 2
    assert synthetic["after"]["false_known_zero_assignments"] == 2
    assert measured["known_zero_elements"] == 0
    assert measured["evaluated_elements"] == 2
    assert measured["after"]["false_known_zero_assignments"] == 0
    assert measured["after"]["false_known_zero_fraction"] is None


def test_gap_continuation_uses_all_evaluable_places_not_only_positive_domains():
    reference = np.repeat([1, 2, 0], 10)
    prediction = np.zeros(30, int)
    prediction[:6] = 1
    prediction[10:16] = 2
    metrics = evaluate_sample(rows(30), reference, prediction, prediction, [], case="empty_gap")
    assert metrics["after"]["positive_reference_coverage"] == .6
    assert metrics["after"]["coverage"] == metrics["after"]["evaluated_coverage"] == .4
    assert metrics["criteria"]["checks"]["coverage"] is False
    assert not metrics["criteria"]["qualified"]
    pooled = aggregate_samples([metrics, metrics])
    assert pooled["after"]["coverage"] == .4
    assert pooled["after"]["positive_reference_coverage"] == .6
    comparison = matched_coverage(reference, np.zeros(30, int), prediction, np.ones(30), list(map(str, range(30))),
                                  evaluated_mask=np.ones(30, bool))
    assert comparison["coverage_gain"] == .4


def test_partial_transfer_ignores_non_test_positions_even_with_same_domain_id():
    points = rows()
    points[0]["transfer_split"] = "train"
    points[1]["transfer_split"] = "validation"
    prediction = np.array([1, 1, 2, 3])
    truth = np.array([[1, 1, 2, 2]])
    metrics = evaluate_sample(points, truth, prediction, prediction, [[0, 1], [1, 2], [2, 3]],
                              kind="measurement", regime="transfer", orientation_labels=np.array([[1, 1, 2, 2]]),
                              truth_raster=truth)
    assert metrics["scope_elements"] == 2
    assert metrics["after"]["pairs"]["split_pairs"] == 1
    assert metrics["after"]["pairs"]["different_reference_pairs"] == 0
    assert metrics["after"]["per_orientation_group"]["1"]["coverage"] is None
    assert not metrics["criteria"]["qualified"]
    assert metrics["after"]["boundary"]["f1"] is None
    assert metrics["after"]["boundary"]["unavailable_reason"] == "partial_reference_has_no_exact_boundary"


def boundary_fixture():
    truth = np.ones((64, 64), dtype=int)
    truth[:, 32:] = 2
    xy = np.array([[x, y] for y in (8, 24, 40, 56) for x in (24, 40)], dtype=float)
    prediction = np.tile([1, 2], 4)
    edges = np.array([[0, 1], [2, 3], [4, 5], [6, 7], [0, 3], [2, 5]])
    return truth, xy, prediction, edges


def test_boundary_uses_only_axial_contacts_and_scales_in_reference_pixels():
    truth, xy, prediction, edges = boundary_fixture()
    result = boundary_scores(xy, prediction, edges, np.ones(8, bool), truth)
    assert result["predicted_points"] == 4  # Two extra diagonal graph edges are ignored.
    assert result["truth_points"] == 64
    assert result["precision"] == result["recall"] == result["f1"] == 1
    double_truth = np.repeat(np.repeat(truth, 2, axis=0), 2, axis=1)
    doubled = boundary_scores(2 * xy, prediction, edges, np.ones(8, bool), double_truth, pixel_spacing_xy=(.5, .5))
    assert doubled == result
    shifted = boundary_scores(xy + [9, 0], prediction, edges, np.ones(8, bool), truth)
    assert shifted["f1"] == 0


def test_boundary_does_not_score_outer_edges_or_empty_gaps_as_exact_material_contours():
    truth, xy, prediction, edges = boundary_fixture()
    truth[:, 28:36] = 0
    assert positive_boundary_points(truth).shape == (0, 2)
    result = boundary_scores(xy, prediction, edges, np.ones(8, bool), truth)
    assert result["truth_points"] == 0
    assert result["false_prediction_points"] == 4
    assert result["recall"] is result["f1"] is None
    original, _, _, _ = boundary_fixture()
    refusal = boundary_scores(xy, np.zeros(8, int), edges, np.ones(8, bool), original)
    assert refusal["precision"] is None
    assert refusal["recall"] == refusal["f1"] == 0


def test_boundary_crossing_windows_remain_evaluable_despite_interior_exclusion():
    truth, xy, prediction, edges = boundary_fixture()
    points = [dict(element_id=str(i), raw_edge_xy=point.tolist(), available=True) for i, point in enumerate(xy)]
    validity = np.ones_like(truth, bool)
    validity[:, 28:36] = False
    metrics = evaluate_sample(points, truth, prediction, prediction, edges,
                              evaluation_valid=validity, truth_raster=truth, case="two_orientations")
    assert metrics["after"]["boundary"]["f1"] == 1
    assert metrics["criteria"]["qualified"]


def test_insufficient_support_requires_state_evidence_and_cannot_claim_disorder():
    points = rows(2, available=False)
    zero = np.zeros(2, int)
    metrics = evaluate_sample(points, np.ones(2, int), zero, zero, [],
                              evaluation_valid=np.zeros(2, bool), case="insufficient_field")
    assert metrics["after"]["coverage"] is None
    assert not metrics["criteria"]["qualified"]
    metrics = evaluate_sample(points, np.ones(2, int), zero, zero, [], evaluation_valid=np.zeros(2, bool),
                              case="insufficient_field", states=np.array(["insufficient_data"] * 2))
    assert metrics["criteria"]["qualified"]
    wrong = evaluate_sample(points, np.ones(2, int), zero, zero, [], evaluation_valid=np.zeros(2, bool),
                            case="insufficient_field", states=np.array(["disordered"] * 2))
    assert not wrong["criteria"]["qualified"]


def test_matched_coverage_uses_existing_assignments_and_common_acf_ranking():
    truth = np.array([1, 1, 2, 2])
    a, b = np.array([1, 1, 2, 0]), np.array([0, 3, 4, 4])
    result = matched_coverage(truth, a, b, np.array([.1, .9, .8, .7]), ["a", "b", "c", "d"])
    assert result["common_assigned_elements"] == 2
    assert result["common_coverage"] == .5
    assert result["comparable_errors"] is False  # Common subset has no same-reference pair.
    assert [point["requested_coverage"] for point in result["curves"]] == [.2, .4, .6]
    half = result["curves"][1]
    assert half["selected_elements"] == 2
    assert half["baseline"]["different_reference_pairs"] == half["candidate"]["different_reference_pairs"] == 1
    empty = matched_coverage(truth, np.zeros(4, int), np.zeros(4, int), np.ones(4), list("abcd"))
    assert empty["curves"] == []
    assert empty["common_error_improvement"] is None


def test_common_coverage_cannot_hide_known_negative_refusals_in_sample_or_pool():
    # A perfect correction on four positive positions is only 4% coverage of
    # this evaluated field, despite covering every positive reference position.
    reference = np.r_[1, 1, 2, 2, np.zeros(96, int)]
    baseline = np.r_[np.ones(4, int), np.zeros(96, int)]
    candidate = reference.copy()
    comparison = matched_coverage(reference, baseline, candidate, np.ones(100),
                                  [str(i) for i in range(100)], evaluated_mask=np.ones(100, bool))
    assert comparison["common_assigned_elements"] == comparison["common_positive_reference_elements"] == 4
    assert comparison["reference_elements"] == 4
    assert comparison["evaluated_elements"] == 100
    assert comparison["common_coverage"] == .04
    assert comparison["common_baseline"]["merge_rate"] == 1
    assert comparison["common_candidate"]["merge_rate"] == 0
    assert comparison["common_error_improvement"] is None
    assert not comparison["comparable_errors"]
    assert comparison["curves"] == []
    small_full_field = matched_coverage(reference[:4], baseline[:4], candidate[:4], np.ones(4), list("abcd"))
    pooled = aggregate_comparisons([comparison, small_full_field])
    assert pooled["common_coverage"] == 8 / 104
    assert pooled["common_positive_reference_elements"] == 8
    assert not pooled["comparable_errors"]
    assert pooled["common_error_improvement"] is None
    assert pooled["common_candidate"]["same_reference_pairs"] == 4  # No cross-field pairs.


def test_equal_coverage_acf_ranking_includes_assigned_known_zero_positions():
    reference = np.array([1, 1, 2, 2, 0, 0, 0, 0, 0, 0])
    baseline = np.ones(10, int)
    candidate = np.array([1, 1, 2, 2, 3, 3, 3, 3, 3, 3])
    scores = np.array([1, 1, 1, 1, 10, 10, 10, 10, 10, 10])
    result = matched_coverage(reference, baseline, candidate, scores, list("abcdefghij"),
                              evaluated_mask=np.ones(10, bool))
    assert result["common_coverage"] == 1
    assert result["common_assigned_elements"] == 10
    assert result["common_positive_reference_elements"] == 4
    assert [point["selected_elements"] for point in result["curves"]] == [2, 4, 6, 8, 10]
    # Highest ACF values happen to be false assignments in the empty region.
    # Those consume the coverage budget but never manufacture reference pairs.
    assert result["curves"][0]["candidate"]["reference_elements"] == 0
    assert result["curves"][0]["candidate"]["merge_rate"] is None
    assert result["curves"][3]["candidate"]["same_reference_pairs"] == 1
    assert result["curves"][3]["candidate"]["different_reference_pairs"] == 0


@pytest.mark.parametrize("regime,scope_pass", [("transfer", True), ("transductive", False)])
def test_missing_ttmapp_color_allows_only_represented_transfer_scope(regime, scope_pass):
    reference = np.array([1, 1, 2, 2])
    metric = evaluate_sample(rows(), reference, reference, reference, [],
                             kind="measurement", regime=regime, orientation_labels=reference)
    # Test through the pooled path used by continuation, including an unlabelled frame.
    unlabelled = evaluate_sample(rows(), None, np.zeros(4, int), np.zeros(4, int), [],
                                 kind="measurement", regime=regime)
    pooled = aggregate_samples([metric, unlabelled])
    criteria = pooled["criteria"]
    assert criteria["represented_groups"] == ["1", "2"]
    assert pooled["after"]["per_orientation_group"]["3"]["coverage"] is None
    assert criteria["represented_group_conditions"]["qualified"]
    assert criteria["scope_conditions"]["qualified"] is scope_pass
    assert not criteria["full_three_group_conditions"]["qualified"]
    three_groups = np.repeat([1, 2, 3], 2)
    full = evaluate_sample(rows(6), three_groups, three_groups, three_groups, [],
                           kind="measurement", regime=regime, orientation_labels=three_groups)
    assert aggregate_samples([full])["criteria"]["full_three_group_conditions"]["qualified"]
    missing_groups = evaluate_sample(rows(), reference, reference, reference, [], kind="measurement", regime=regime)
    assert not missing_groups["criteria"]["scope_conditions"]["qualified"]

    # Every other continuation gate passes. A missing color must not be hidden
    # by synthetic success or by the availability of both positive pair kinds.
    records, stability, benefits = [], [], []
    base = dict(regime=regime, family="ae", latent=32, partition="fh4", sampler="grid", scale_px=48)
    cases = ZERO_CASES | TWO_CASES | ABLATION_CASES | {"single", "insufficient_field"}
    for seed in (20261101, 20261102, 20261103):
        for case in cases:
            for control_seed in (920001, 920002, 920003):
                records.append(dict(metadata=dict(base, seed=seed, kind="synthetic", case=case, control_seed=control_seed),
                                    metrics=dict(criteria=dict(passed=True))))
        records.append(dict(metadata=dict(base, seed=seed, kind="measurement"), metrics=metric))
    stability.append(dict(metadata=base, stability=seed_stability({str(seed): dict(zip("abcd", reference)) for seed in range(3)})))
    for kind, case in (("synthetic", "__all__"), ("measurement", None)):
        benefits.append(dict(metadata=dict(base, kind=kind, case=case), benefit=dict(benefit_condition=True)))
    result, = continuation_summary(records, stability, benefits)
    assert result["continuation"]["qualified"] is scope_pass
    assert not result["full_three_group_ttmapp_benefit"]


def test_postprocess_budget_sums_prior_attempts_and_checks_current_cpu_and_rss(tmp_path, monkeypatch):
    write_json(tmp_path / "cache-resources.json", dict(cpu_seconds=6000))
    write_json(tmp_path / "partition-resources.json", dict(cpu_seconds=1190))
    write_json(tmp_path / "ignored.json", dict(cpu_seconds=50000))
    clock = dict(cpu=100., rss=1024)
    monkeypatch.setattr(evaluation.time, "process_time", lambda: clock["cpu"])
    monkeypatch.setattr(evaluation.resource, "getrusage", lambda _: SimpleNamespace(ru_maxrss=clock["rss"]))
    budget = PostprocessBudget(tmp_path)
    clock["cpu"] = 109.
    budget.check()
    assert budget.measurements()["cumulative_postprocess_cpu_seconds"] == 7199
    assert len(budget.measurements()["prior_reports_sha256"]) == 2
    clock["cpu"] = 110.
    with pytest.raises(RuntimeError, match="CPU budget"):
        budget.check()
    clock["cpu"] = 100.
    clock["rss"] = 12 * 1024 ** 2 + 1
    with pytest.raises(RuntimeError, match="RSS budget"):
        budget.check()


def test_postprocess_budget_rechecks_every_hundred_aggregation_entries(tmp_path, monkeypatch):
    budget = PostprocessBudget(tmp_path)
    seen = []
    monkeypatch.setattr(budget, "check", lambda: seen.append("check"))
    assert list(budget.checked(range(201))) == list(range(201))
    assert len(seen) == 3


def test_exhausted_budget_stops_before_truth_and_records_failed_attempt(tmp_path, monkeypatch):
    root, controls, references = frozen_fixture(tmp_path)
    write_json(root / "partition-resources.json", dict(cpu_seconds=7200))
    monkeypatch.setattr(evaluation, "_truth_bundle", lambda *_: pytest.fail("Truth read after exhausted budget"))
    with pytest.raises(RuntimeError, match="CPU budget"):
        evaluate_frozen(root, controls, references, tmp_path / "evaluation")
    assert not (tmp_path / "evaluation").exists()
    resource_record = json.loads((root / "evaluation-resources.json").read_text())
    assert resource_record["status"] == "failed"
    assert resource_record["cpu_seconds"] >= 0
    assert resource_record["cumulative_postprocess_cpu_seconds"] >= 7200


def test_seed_stability_compares_identity_and_partition_relations_not_label_numbers():
    predictions = {
        "1": {"a": 1, "b": 1, "c": 2, "d": 2},
        "2": {"d": 5, "c": 5, "b": 7, "a": 7},
        "3": {"a": 8, "b": 8, "c": 9, "d": 9},
    }
    stable = seed_stability(predictions)
    assert stable["criteria"]["qualified"]
    assert all(pair["changed_pairs"] == 0 and pair["compared_pairs"] == 6 for pair in stable["pairs"])
    for prediction in predictions.values():
        for ident in prediction:
            prediction[ident] = 0
    refused = seed_stability(predictions)
    assert not refused["criteria"]["qualified"]
    assert all(pair["changed_pair_fraction"] is None for pair in refused["pairs"])
    negative = seed_stability(predictions, require_pair_evidence=False)
    assert negative["criteria"]["qualified"]
    assert negative["pair_comparison_applicable"] is False


def test_ablation_invariance_accepts_renumbering_but_not_changed_refusals_or_element_sets():
    before = np.array([1, 1, 2, 0])
    after = np.array([1, 1, 0, 0])
    result = ablation_invariance(list("abcd"), before, after, list("dcba"), np.array([0, 7, 9, 9]), np.array([0, 0, 6, 6]))
    assert result["passed"]
    result = ablation_invariance(list("abcd"), before, after, list("abcd"), before, np.array([1, 0, 0, 0]))
    assert not result["passed"]
    result = ablation_invariance(list("abcd"), before, after, list("abc"), before[:3], after[:3])
    assert not result["same_element_set"]


def test_benefit_needs_three_seeds_and_measurable_errors():
    truth = np.array([1, 1, 2, 2])
    bad = np.ones(4, int)
    good = np.array([10, 10, 20, 20])
    comparison = matched_coverage(truth, bad, good, np.ones(4), list("abcd"))
    assert comparison["common_error_improvement"] == .5
    assert not benefit_across_seeds({"1": comparison})["benefit_condition"]
    result = benefit_across_seeds({str(seed): comparison for seed in range(3)})
    assert result["error_path"]
    assert result["requires_all_control_and_stability_gates"]


def test_json_and_csv_keep_null_denominators_empty_and_never_write_nan(tmp_path):
    prediction = np.zeros(4, int)
    metrics = evaluate_sample(rows(), None, prediction, prediction, [], kind="measurement")
    records = [{"metadata": {"sample_id": "fixture", "run_id": "test"}, "metrics": metrics}]
    write_summary(records, tmp_path / "evaluation")
    payload = json.loads((tmp_path / "evaluation/summary.json").read_text())
    assert payload["records"][0]["metrics"]["after"]["coverage"] is None
    with (tmp_path / "evaluation/metrics.csv").open() as stream:
        csv_rows = list(csv.DictReader(stream))
    assert len(csv_rows) == 2
    assert csv_rows[0]["coverage"] == ""
    assert csv_rows[0]["pairs_merge_rate"] == ""
    with pytest.raises(FileExistsError):
        write_summary(records, tmp_path / "evaluation")


def test_nearest_grid_mapping_keeps_unmatched_and_unavailable_as_refusals():
    grid = [dict(element_id="b", raw_edge_xy=[8., 8.], available=True),
            dict(element_id="a", raw_edge_xy=[24., 8.], available=False)]
    centers = np.array([[8., 8.], [16., 8.], [24., 8.], [60., 60.]])
    result = map_current_centers(centers, grid, np.array([1, 2]), np.array([1, 2]))
    assert result["nearest_grid_index"].tolist()[:3] == [0, 1, 1]  # Tie uses canonical ID a.
    assert result["mapped"].tolist() == [True, False, False, False]
    assert result["after"].tolist() == [1, 0, 0, 0]
    doubled_grid = [dict(row, raw_edge_xy=(2 * np.array(row["raw_edge_xy"])).tolist()) for row in grid]
    doubled = map_current_centers(2 * centers, doubled_grid, np.array([1, 2]), np.array([1, 2]), pixel_spacing_xy=(.5, .5))
    np.testing.assert_array_equal(doubled["mapped"], result["mapped"])
    np.testing.assert_allclose(doubled["distance_reference_px"], result["distance_reference_px"])


def frozen_fixture(tmp_path):
    root = tmp_path / "predictions"
    controls, references = tmp_path / "controls", tmp_path / "references"
    source = tmp_path / "analysis"
    centers = np.array([[24.1, 24.], [40.1, 40.], [3., 3.]])
    arrays = dict(image=np.zeros((64, 64)), measured=np.ones((64, 64), bool), centers_xy=centers,
                  boxes_xyxy=np.column_stack((centers - .25, centers + .25)), object_ids=np.array(["c0", "c1", "c2"]))
    source_record = dict(sample_id="ttmapp-250", kind="measurement", file="samples/ttmapp-250.npz",
                         **write_arrays(source / "samples/ttmapp-250.npz", arrays))
    write_json(source / "manifest.json", dict(schema="stmdomains-input-v1", samples=[source_record]))
    truth = np.ones((64, 64), int)
    truth[:, 32:] = 2
    reference_record = dict(sample_id="ttmapp-250", file="references/frame.npz",
                            **write_arrays(references / "references/frame.npz", dict(region_instances=truth, orientation_groups=truth,
                                           evaluation_valid=np.ones((64, 64), bool))))
    write_json(references / "manifest.json", dict(schema="stmdomains-evaluation-v1", references=[reference_record], controls=[]))
    control_records = []
    for ident, case in (("fixture-a", "single"), ("fixture-b", "missing_10")):
        relative = f"controls/{ident}.npz"
        control_records.append(dict(sample_id=ident, file=relative, case=case, seed=7,
                                    **write_arrays(controls / relative, dict(domain_labels=np.ones((64, 64), int), evaluation_valid=np.ones((64, 64), bool)))))
    write_json(controls / "manifest.json", dict(schema="stmdomains-evaluation-v1", controls=control_records, references=[]))
    grid = [dict(element_id=f"g{i}", raw_edge_xy=[float(x), float(y)], available=True, transfer_split="test")
            for i, (x, y) in enumerate(((24, 24), (40, 24), (24, 40), (40, 40)))]
    center_rows = [dict(element_id=ident, raw_edge_xy=xy.tolist(), available=True, transfer_split="test")
                   for ident, xy in zip(arrays["object_ids"].tolist(), centers)]
    groups, index = [], []

    def gzip_json(path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(path, "wt") as stream:
            json.dump(value, stream)

    for ident in ("fixture-a", "fixture-b", "ttmapp-250"):
        kind = "measurement" if ident == "ttmapp-250" else "synthetic"
        for sampler in (("grid", "centers") if kind == "measurement" else ("grid",)):
            selected = grid if sampler == "grid" else center_rows
            group_id = f"{ident}/{sampler}/s48"
            gzip_json(root / "cache" / group_id / "rows.json.gz", selected)
            groups.append(dict(group_id=group_id, analysis=str(source.resolve()), record=source_record if kind == "measurement" else dict(sample_id=ident)))
            for family, seed in (("fft", None), ("ae", 20261101)):
                run_id = f"transfer/{family}" if seed is None else f"transfer/{family}/z32/seed-{seed}"
                for partition in ("fh4", "mws"):
                    relative = f"predictions/{run_id}/{sampler}/s48/{ident}/{partition}"
                    folder = root / relative
                    folder.mkdir(parents=True)
                    input_name = "heldout-metrics-input.npz" if kind == "measurement" else "metrics-input.npz"
                    labels = np.ones(len(selected), dtype=int)
                    if kind == "measurement":
                        labels = np.array([1 if row["raw_edge_xy"][0] < 32 else 2 for row in selected])
                    edges = np.column_stack((np.arange(len(selected) - 1), np.arange(1, len(selected))))
                    np.savez_compressed(folder / input_name, before=labels, after=labels, edges=edges,
                                        acf_score=np.ones(len(selected)), available=np.ones(len(selected), bool))
                    result_name = "heldout-result.json.gz" if kind == "measurement" else "result.json.gz"
                    gzip_json(folder / result_name, dict(assignments=[dict(element_id=row["element_id"], domain_id=str(label), state="ordered_untyped")
                                                                     for row, label in zip(selected, labels)]))
                    index.append(dict(run_id=run_id, family=family, seed=seed, latent=None if family == "fft" else 32,
                                      regime="transfer", scale_px=48, sampler=sampler, sample_id=ident, kind=kind,
                                      pixel_spacing_xy=[1., 1.], partition=partition, directory=relative, evaluation_input=input_name, cache_group=group_id))
    write_json(root / "cache/index.json", groups)
    write_json(root / "predictions/index.json", index)
    write_json(root / "frozen-predictions.json", dict(schema="stmdomains-frozen-predictions-v1", evaluation_opened=False,
               files={str(path.relative_to(root)): file_hash(path) for path in root.rglob("*") if path.is_file()}))
    return root, controls, references


def test_frozen_pipeline_evaluation_preserves_all_variants_mapping_and_denominators(tmp_path):
    root, controls, references = frozen_fixture(tmp_path)
    evidence = evaluate_frozen(root, controls, references, tmp_path / "evaluation")
    assert evidence["prediction_entries"] == 16
    assert evidence["evaluated_records"] == 20  # Four separate nearest-grid center assessments.
    summary = json.loads((tmp_path / "evaluation/summary.json").read_text())
    assert {"records", "aggregates", "criteria", "comparisons", "stability", "ablations"} <= summary.keys()
    assert all(item["invariance"]["passed"] for item in summary["ablations"])
    mapped = [record for record in summary["records"] if record["metadata"]["sampler"] == "centers_from_grid"]
    assert all(record["metrics"]["after"]["coverage"] == 2 / 3 for record in mapped)
    assert all(record["metrics"]["evaluated_elements"] == 3 for record in mapped)
    assert all(record["metrics"]["grid_mapping"]["unmatched_count"] == 1 for record in mapped)
    assert all(not item["continuation"]["qualified"] for item in summary["criteria"])


def test_freeze_is_verified_before_any_reference_is_opened(tmp_path):
    root, _, _ = frozen_fixture(tmp_path)
    (root / "predictions/index.json").write_text("[]\n")
    with pytest.raises(ValueError, match="Frozen artifact changed"):
        evaluate_frozen(root, tmp_path / "nonexistent-controls", tmp_path / "nonexistent-reference", tmp_path / "evaluation")
    assert not (tmp_path / "evaluation").exists()
