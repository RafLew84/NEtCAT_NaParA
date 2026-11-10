"""Post-freeze issue-24 evaluation on annotation nodes, never on a regular grid.

The existing pair, coverage and stability definitions are reused. Explicit
adaptations are all-edge centre boundary midpoints, missing-centre robustness
instead of grid invariance, and unavailable image-negative evidence when an
image has no annotation nodes. No model, threshold or prediction is changed.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import itertools
import json
from pathlib import Path
import time

import numpy as np
from scipy.spatial import cKDTree

from ...bundle import file_hash, write_json
from .. import evaluate as old
from .controls import SEEDS as CONTROL_SEEDS


MODEL_SEEDS = (20261101, 20261102, 20261103)
BOUNDARIES = old.BOUNDARY_CASES | {"phase_centers_jitter_072"}
ROBUST_SINGLE = old.ABLATION_CASES | {
    "centers_jitter_036", "centers_jitter_072", "centers_duplicates_10"}
EMPTY_GRAPH_CASES = {"noise", "stripes"}
NEGATIVES = old.ZERO_CASES - EMPTY_GRAPH_CASES
REQUIRED_CASES = NEGATIVES | old.TWO_CASES | BOUNDARIES | ROBUST_SINGLE | {
    "single", "insufficient_field"}
LEARNED_FAMILIES = {"graph_sce_scale", "graph_sce"}
FAMILY_KEYS = ("regime", "family", "latent", "partition")


def read(path):
    return json.loads(Path(path).read_text())


def key(meta, names):
    return tuple(meta.get(name) for name in names)


class Budget(old.PostprocessBudget):
    def __init__(self, root):
        self.cpu_started = time.process_time()
        self.wall_started = time.monotonic()
        self.prior_cpu_seconds = 0.
        self.prior_reports = {}
        for path in sorted(Path(root).glob("*resources.json")):
            value = read(path)
            seconds = float(value["cpu_seconds"])
            if not np.isfinite(seconds) or seconds < 0:
                raise ValueError("Invalid previous CPU resource record")
            self.prior_cpu_seconds += seconds
            self.prior_reports[str(path.resolve())] = file_hash(path)
        self.cpu_limit_seconds = 7200.
        self.rss_limit_bytes = 12 * 1024 ** 3


def verify_freeze(root, budget):
    """This must complete before either truth manifest is opened."""
    frozen = old.verify_prediction_freeze(root, check_budget=budget.check)
    repository = Path(__file__).resolve().parents[4]
    for field in ("external_files", "code_sha256"):
        for name, expected in budget.checked(frozen.get(field, {}).items()):
            path = Path(name)
            if field == "external_files" and not path.is_absolute():
                raise ValueError("External frozen paths must be absolute")
            if not path.is_absolute():
                path = repository / path
            if file_hash(path) != expected:
                raise ValueError(f"Frozen source/external artifact changed: {name}")
    return frozen


def boundary_scores(xy, prediction, edges, eligible, truth_raster, *, spacing=(1., 1.)):
    """Use every actual local centre edge, not the grid's axial-edge subset."""
    xy = np.asarray(xy, float)
    edge = old._edges(edges, len(xy))
    prediction = np.asarray(prediction)
    eligible = np.asarray(eligible, bool)
    u, v = edge.T
    chosen = (eligible[u] & eligible[v] & (prediction[u] > 0) &
              (prediction[v] > 0) & (prediction[u] != prediction[v]))
    predicted = (xy[u[chosen]] + xy[v[chosen]]) / 2 * np.asarray(spacing)
    truth = old.positive_boundary_points(truth_raster, spacing)
    matched_prediction = int((cKDTree(truth).query(predicted)[0] <= 8.).sum()) if len(truth) and len(predicted) else 0
    matched_truth = int((cKDTree(predicted).query(truth)[0] <= 8.).sum()) if len(truth) and len(predicted) else 0
    precision = old._ratio(matched_prediction, len(predicted))
    recall = old._ratio(matched_truth, len(truth))
    f1 = (2 * precision * recall / (precision + recall)
          if precision is not None and recall is not None and precision + recall else 0.) if len(truth) else None
    return dict(tolerance_reference_px=8., predicted_points=len(predicted),
                truth_points=len(truth), matched_prediction_points=matched_prediction,
                matched_truth_points=matched_truth,
                false_prediction_points=len(predicted) - matched_prediction,
                precision=precision, recall=recall, f1=f1,
                edge_policy="all actual local centre edges; no interpolation of missing annotations",
                unavailable_reason=None if len(truth) else "no_positive_domain_contact")


def control_criteria(metrics, case):
    stage = metrics["after"]
    if case in EMPTY_GRAPH_CASES and metrics["planned_elements"] == 0:
        return dict(old._check_result({}, applicable=False),
                    unavailable_reason="no_annotation_nodes; cannot assess the image as a negative")
    if case in ROBUST_SINGLE:
        return old._check_result(dict(
            no_assignment_without_support=stage["assigned_without_support"] == 0,
            one_domain=stage["domain_count_in_scope"] == 1,
            retained_node_coverage=old._at_least(stage["coverage"], .5),
            retained_node_split=old._at_most(stage["pairs"]["split_rate"], .1)))
    if case == "phase_centers_jitter_072":
        return old.control_criteria(metrics, "phase_boundary")
    return old.control_criteria(metrics, case)


def evaluate_sample(rows, prediction, truth, metadata, spacing):
    labels = truth.get("domain_labels" if metadata["kind"] == "synthetic" else "region_instances")
    result = old.evaluate_sample(
        rows, labels, prediction["before"], prediction["after"], prediction["edges"],
        evaluation_valid=truth.get("evaluation_valid"), orientation_labels=truth.get("orientation_groups"),
        truth_raster=None, pixel_spacing_xy=spacing, regime=metadata["regime"],
        kind=metadata["kind"], case=metadata.get("case"), states=prediction["states"])
    if metadata["kind"] == "synthetic":
        full = np.asarray([row["available"] for row in rows], bool)
        for stage in ("before", "after"):
            result[stage]["boundary"] = boundary_scores(old._positions(rows), prediction[stage],
                prediction["edges"], full, truth["domain_labels"], spacing=spacing)
        result["criteria"] = control_criteria(result, metadata.get("case"))
    result["sampling_note"] = "Observed annotation nodes with full 72px ego support; not molecule detection recall or material area"
    return result


def annotation_diagnostics(data, control_truth):
    """Keep original denominator and retained-ID pair changes separately."""
    lookup = {(meta["seed"], meta["case"]): sid for sid, (meta, _) in control_truth.items()}
    outputs = []
    for entry in data.values():
        meta = entry["record"]["metadata"]
        if meta["kind"] != "synthetic" or meta["case"] not in ROBUST_SINGLE | {"phase_centers_jitter_072"}:
            continue
        base_case = "phase_boundary" if meta["case"] == "phase_centers_jitter_072" else "single"
        base_sid = lookup[meta["control_seed"], base_case]
        base = data[meta["variant_id"], base_sid, meta["partition"]]
        b_ids = [row["element_id"] for row in base["rows"]]
        c_ids = [row["element_id"] for row in entry["rows"]]
        b_map, c_map = ({ident: i for i, ident in enumerate(ids)} for ids in (b_ids, c_ids))
        common = sorted(set(b_ids) & set(c_ids))
        bi, ci = (np.asarray([mapping[ident] for ident in common], dtype=int) for mapping in (b_map, c_map))
        common_available = np.asarray([base["rows"][i]["available"] for i in bi], bool) & np.asarray([entry["rows"][i]["available"] for i in ci], bool)
        stages = {}
        for stage in ("before", "after"):
            a, b = base["prediction"][stage][bi], entry["prediction"][stage][ci]
            both = common_available & (a > 0) & (b > 0)
            score = old.pair_scores(a[both], b[both])
            pair_count = int(both.sum()) * (int(both.sum()) - 1) // 2
            changed = score["split_pairs"] + score["merged_pairs"]
            original_evaluable = base["evaluated_mask"]
            original_ids = {b_ids[i] for i in np.flatnonzero(original_evaluable)}
            assigned_original = sum(ident in c_map and entry["evaluated_mask"][c_map[ident]] and
                                    entry["prediction"][stage][c_map[ident]] > 0 for ident in original_ids)
            stages[stage] = dict(common_available_elements=int(common_available.sum()),
                common_assigned_elements=int(both.sum()), compared_pairs=pair_count,
                changed_pairs=changed, changed_pair_fraction=old._ratio(changed, pair_count),
                original_evaluated_elements=len(original_ids), assigned_original_elements=int(assigned_original),
                original_denominator_coverage=old._ratio(assigned_original, len(original_ids)))
        truth_meta = control_truth[meta["sample_id"]][0]
        outputs.append(dict(metadata=meta, baseline_sample_id=base_sid, observed_nodes=len(c_ids),
            original_nodes=len(b_ids), retained_ids=len(common), extra_ids=len(set(c_ids) - set(b_ids)),
            absent_ids=len(set(b_ids) - set(c_ids)), duplicate_source_ids=truth_meta.get("duplicate_source_ids", {}),
            stages=stages, interpretation="Annotation perturbation diagnostic; no exact grid-invariance requirement"))
    return outputs


def compare_models(data):
    comparisons = []
    baseline_index = {}
    baseline_keys = ("regime", "sample_id", "partition", "family", "seed")
    for entry in data.values():
        meta = entry["record"]["metadata"]
        if meta["family"] in {"geometry", "graph_untrained"}:
            ident = key(meta, baseline_keys)
            if ident in baseline_index:
                raise ValueError("Repeated paired baseline")
            baseline_index[ident] = entry
    for entry in data.values():
        meta = entry["record"]["metadata"]
        if meta["family"] not in LEARNED_FAMILIES:
            continue
        for baseline_family in ("geometry", "graph_untrained"):
            baseline_meta = dict(meta, family=baseline_family,
                                 seed=None if baseline_family == "geometry" else meta["seed"])
            baseline = baseline_index.get(key(baseline_meta, baseline_keys))
            if baseline is None:
                raise ValueError(f"Expected one paired baseline for {meta}: {baseline_family}")
            for field in ("reference", "evaluated_mask"):
                if not np.array_equal(entry[field], baseline[field]):
                    raise ValueError("Paired model evaluation support differs")
            if not np.array_equal(entry["prediction"]["score"], baseline["prediction"]["score"], equal_nan=True):
                raise ValueError("Matched-coverage ranking must use the same geometric score")
            for stage in ("before", "after"):
                comparison = old.matched_coverage(entry["reference"], baseline["prediction"][stage],
                    entry["prediction"][stage], entry["prediction"]["score"],
                    [row["element_id"] for row in entry["rows"]], evaluated_mask=entry["evaluated_mask"])
                comparisons.append(dict(metadata=dict(meta, baseline_family=baseline_family, stage=stage), comparison=comparison))
    names = ("variant_id", "regime", "family", "latent", "seed", "scale_px", "sampler",
             "partition", "kind", "case", "baseline_family", "stage")
    groups = defaultdict(list)
    for row in comparisons:
        groups[key(row["metadata"], names)].append(row["comparison"])
        if row["metadata"]["kind"] == "synthetic":
            groups[key(dict(row["metadata"], case="__all__"), names)].append(row["comparison"])
    pooled = [dict(metadata=dict(zip(names, k)), comparison=old.aggregate_comparisons(v)) for k, v in groups.items()]
    benefit_names = tuple(name for name in names if name not in {"variant_id", "seed"})
    groups = defaultdict(dict)
    for row in pooled:
        groups[key(row["metadata"], benefit_names)][str(row["metadata"]["seed"])] = row["comparison"]
    benefits = [dict(metadata=dict(zip(benefit_names, k)), benefit=old.benefit_across_seeds(v)) for k, v in groups.items()]
    return comparisons, pooled, benefits


def continuation(records, stability, benefits):
    families = defaultdict(list)
    for row in records:
        families[key(row["metadata"], FAMILY_KEYS)].append(row)
    output = []
    for family, members in families.items():
        meta = dict(zip(FAMILY_KEYS, family))
        learned = meta["family"] in LEARNED_FAMILIES
        seeds = MODEL_SEEDS if meta["family"] not in {"geometry", "legacy15"} else (None,)
        by_case = {(r["metadata"]["seed"], r["metadata"]["case"], r["metadata"].get("control_seed")): r for r in members if r["metadata"]["kind"] == "synthetic"}
        checks = {}
        for model_seed, case, control_seed in itertools.product(seeds, sorted(REQUIRED_CASES), CONTROL_SEEDS):
            row = by_case.get((model_seed, case, control_seed))
            checks[f"model_seed={model_seed}/case={case}/control_seed={control_seed}"] = None if row is None else row["metrics"]["criteria"]["passed"]
        controls = old._check_result(checks)
        real = {}
        for seed in seeds:
            selected = [r["metrics"] for r in members if r["metadata"]["kind"] == "measurement" and r["metadata"]["seed"] == seed]
            real[str(seed)] = old.aggregate_samples(selected)["criteria"] if selected else old._check_result({"available": None})
        selected_stability = [r for r in stability if key(r["metadata"], FAMILY_KEYS) == family and r["stability"]["criteria"]["applicable"]]
        stable = True if seeds == (None,) else (all(r["stability"]["criteria"]["passed"] is True for r in selected_stability) if selected_stability else None)
        benefit = {}
        for baseline in ("geometry", "graph_untrained"):
            benefit[baseline] = {}
            for kind_name in ("synthetic", "measurement"):
                rows = [r for r in benefits if key(r["metadata"], FAMILY_KEYS) == family and
                        r["metadata"]["baseline_family"] == baseline and r["metadata"]["stage"] == "after" and
                        r["metadata"]["kind"] == kind_name and
                        (kind_name == "measurement" or r["metadata"]["case"] == "__all__")]
                benefit[baseline][kind_name] = rows[0]["benefit"]["benefit_condition"] if len(rows) == 1 else None
        qualification = old._check_result(dict(
            required_controls=controls["passed"], stability=stable,
            ttmapp_all_seeds=all(r.get("scope_conditions", r)["passed"] is True for r in real.values()),
            benefit_vs_geometry_on_controls=benefit["geometry"]["synthetic"],
            benefit_vs_geometry_on_ttmapp=benefit["geometry"]["measurement"],
            benefit_vs_initialization_on_controls=benefit["graph_untrained"]["synthetic"],
            benefit_vs_initialization_on_ttmapp=benefit["graph_untrained"]["measurement"]), applicable=learned)
        output.append(dict(metadata=meta, synthetic_controls=controls, ttmapp=real, stability=stable,
            benefit=benefit, continuation=qualification,
            primary=meta["family"] == "graph_sce_scale",
            claim_scope="observed annotation nodes in represented transfer regions" if meta["regime"] == "transfer" else "observed annotation nodes in the current series",
            limitations=["No image-negative proof on noise/stripes without nodes", "No inference of missing molecules or material area", "Missing-band and material-gap cases can have identical geometry"]))
    return output


def _evaluate(root, controls_dir, measurement_dir, out, budget):
    frozen = verify_freeze(root, budget)
    index = read(old._frozen_path(root, "predictions/index.json", frozen))
    if isinstance(index, dict):
        index = index["entries"]
    prepared = read(old._frozen_path(root, "prepared/manifest.json", frozen))
    samples = {}
    for sample in prepared["samples"]:
        rows_path = "prepared/" + sample["rows_file"]
        samples[sample["sample_id"]] = dict(record=sample["record"], rows=read(old._frozen_path(root, rows_path, frozen)))
    # Both truth reads occur only after the complete prediction/source audit above.
    control_manifest, control_truth = old._truth_bundle(controls_dir, "controls")
    _, measurement_truth = old._truth_bundle(measurement_dir, "references")
    records, data = [], {}
    for item in budget.checked(index):
        sample = samples[item["sample_id"]]
        rows = sample["rows"]
        heldout = item["kind"] == "measurement" and item["regime"] == "transfer"
        relative = item.get("heldout_file") if heldout else item["file"]
        if relative is None:
            raise ValueError("Transfer requires a separate test-only graph prediction")
        with np.load(old._frozen_path(root, relative, frozen), allow_pickle=False) as archive:
            prediction = {name: archive[name] for name in archive.files}
        if heldout:
            test = np.asarray([r.get("transfer_split") == "test" for r in rows], bool)
            if (prediction["before"][~test] > 0).any() or (prediction["after"][~test] > 0).any():
                raise ValueError("Transfer output assigns nodes outside the test graph")
            if len(prediction["edges"]) and not test[prediction["edges"]].all():
                raise ValueError("Transfer graph contains edges outside the test nodes")
        source = control_truth if item["kind"] == "synthetic" else measurement_truth
        if item["kind"] == "synthetic" and item["sample_id"] not in source:
            raise ValueError("Missing synthetic truth")
        truth_meta, truth = source.get(item["sample_id"], ({}, {}))
        meta = {k: v for k, v in item.items() if k not in {"file", "heldout_file"}}
        meta.update(case=truth_meta.get("case"), control_seed=truth_meta.get("seed"), assessment="primary_center_ego72")
        spacing = sample["record"]["pixel_spacing_xy"]
        metrics = evaluate_sample(rows, prediction, truth, meta, spacing)
        record = dict(metadata=meta, metrics=metrics)
        records.append(record)
        labels = truth.get("domain_labels" if meta["kind"] == "synthetic" else "region_instances")
        data_key = (meta["variant_id"], meta["sample_id"], meta["partition"])
        if data_key in data:
            raise ValueError("Repeated variant/sample/partition prediction")
        data[data_key] = dict(rows=rows, prediction=prediction, record=record,
            reference=old._comparison_reference(rows, labels, truth.get("evaluation_valid"), kind=meta["kind"], regime=meta["regime"]),
            evaluated_mask=old._evaluated_mask(rows, labels, truth.get("evaluation_valid"), kind=meta["kind"], regime=meta["regime"]))
    names = ("variant_id", "regime", "family", "latent", "seed", "scale_px", "sampler", "partition", "kind", "case")
    grouped, stable_groups = defaultdict(list), {}
    for row in records:
        meta = row["metadata"]
        grouped[key(meta, names)].append(row["metrics"])
        if meta["seed"] is None:
            continue
        stable_names = ("regime", "family", "latent", "scale_px", "sampler", "partition", "kind", "case", "sample_id")
        group = stable_groups.setdefault(key(meta, stable_names), dict(metadata={k: meta[k] for k in stable_names}, predictions={}, eligible=set()))
        entry = data[meta["variant_id"], meta["sample_id"], meta["partition"]]
        group["predictions"][str(meta["seed"])] = {r["element_id"]: int(v) for r, v in zip(entry["rows"], entry["prediction"]["after"])}
        group["eligible"].update(r["element_id"] for r, valid in zip(entry["rows"], entry["evaluated_mask"]) if valid)
    aggregates = [dict(metadata=dict(zip(names, k)), metrics=old.aggregate_samples(v)) for k, v in grouped.items()]
    stability = [dict(metadata=g["metadata"], stability=old.seed_stability(g["predictions"], eligible_ids=g["eligible"],
                 require_pair_evidence=g["metadata"]["case"] not in NEGATIVES | EMPTY_GRAPH_CASES | {"insufficient_field"})) for g in stable_groups.values()]
    comparisons, pooled, benefits = compare_models(data)
    ablations = annotation_diagnostics(data, control_truth)
    criteria = continuation(records, stability, benefits)
    budget.check()
    old.write_summary(records, out, extras=dict(aggregates=aggregates, comparisons=pooled,
                      stability=stability, ablations=ablations, benefits=benefits, criteria=criteria))
    for name, rows in (("aggregates", aggregates), ("comparisons", comparisons), ("pooled-comparisons", pooled),
                       ("stability", stability), ("ablations", ablations), ("benefits", benefits), ("continuation", criteria)):
        write_json(out / (name + ".json"), rows)
        old._flat_csv(out / (name + ".csv"), rows)
    evidence = dict(schema="stmdomains-post-freeze-evaluation-v1", frozen_manifest_sha256=file_hash(root / "frozen-predictions.json"),
        verified_prediction_files=len(frozen["files"]), verified_external_files=len(frozen.get("external_files", {})),
        prediction_entries=len(index), evaluated_records=len(records), controls_count=len(control_truth),
        controls_manifest_sha256=file_hash(Path(controls_dir) / "manifest.json"),
        measurement_manifest_sha256=file_hash(Path(measurement_dir) / "manifest.json"),
        code_sha256=file_hash(Path(__file__)), control_seeds=control_manifest["seeds"],
        boundary_policy="All actual centre edges, midpoint tolerance8 reference_px; no exact boundary on TTMAPP partial rectangles",
        criteria_policy="Predeclared graph24 adaptation of20; missing/jitter/duplicates require one domain,coverage>=.50,split<=.10; no grid-invariance claim",
        measurement_policy="Partial references; transfer test-only graph; no independent-acquisition generalization",
        postprocessing_budget=budget.measurements())
    write_json(out / "evaluation-evidence.json", evidence)
    return evidence


def evaluate_frozen(root, controls_dir=None, measurement_dir=None, out=None):
    root = Path(root).resolve()
    controls_dir = Path(controls_dir or root / "controls/evaluation")
    measurement_dir = Path(measurement_dir or ".scratch/unsupervised-input/evaluation")
    out = Path(out or root / "evaluation")
    if out.exists():
        raise FileExistsError(f"Use a fresh evaluation output: {out}")
    resource_path = root / (out.name + ".resources.json")
    if resource_path.exists():
        raise FileExistsError(f"An evaluation attempt is already recorded: {resource_path}")
    budget = Budget(root)
    status = "failed"
    try:
        result = _evaluate(root, controls_dir, measurement_dir, out, budget)
        status = "completed"
        return result
    finally:
        write_json(resource_path, dict(status=status, **budget.measurements()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--controls-evaluation", type=Path)
    parser.add_argument("--measurement-evaluation", type=Path)
    parser.add_argument("--evaluation-output", type=Path)
    args = parser.parse_args()
    result = evaluate_frozen(args.output, args.controls_evaluation, args.measurement_evaluation, args.evaluation_output)
    print(json.dumps({k: result[k] for k in ("prediction_entries", "evaluated_records", "controls_count")}))


if __name__ == "__main__":
    main()
