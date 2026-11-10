"""Issue25 evaluation after prediction freeze; primary claims use grid48 only."""
from __future__ import annotations

import argparse
from collections import defaultdict
import itertools
import json
from pathlib import Path
import shutil
import tempfile

import numpy as np

from ...bundle import file_hash, load_sample, write_json
from .. import evaluate as old
from .common import reporting_stage


MODEL_SEEDS = (20261101, 20261102, 20261103)
CONTROL_SEEDS = (920031, 920032, 920033)
CANDIDATES = ("mask25", "mask50")
BASELINES = ("ae", "local_ssl", "ae_untrained", "fft")
ANNOTATION_PAIRS = {case: "single" for case in old.ABLATION_CASES | {
    "centers_jitter_036", "centers_jitter_072", "centers_duplicates_10"}}
ANNOTATION_PAIRS["phase_centers_jitter_072"] = "phase_boundary"
REQUIRED_CASES = old.ZERO_CASES | old.TWO_CASES | set(ANNOTATION_PAIRS) | {"single", "insufficient_field"}
IDENTITY = ("run_id", "scale_px", "sampler", "sample_id", "partition")
AGGREGATE_KEYS = ("run_id", "regime", "family", "latent", "seed", "scale_px", "sampler", "partition", "kind", "case", "assessment")
FAMILY_KEYS = ("regime", "family", "latent", "partition")


def read(path):
    return old._read_json(Path(path))


def key(meta, fields=IDENTITY):
    return tuple(meta.get(name) for name in fields)


def primary(meta):
    return meta["sampler"] == "grid" and meta["scale_px"] == 48


def verify_freeze(root, *, check_budget=None):
    root = Path(root).resolve()
    frozen = old.verify_prediction_freeze(root, check_budget=check_budget)
    repository = Path(__file__).resolve().parents[4]
    for field in ("external_files", "code_sha256"):
        for i, (name, expected) in enumerate(frozen.get(field, {}).items()):
            if check_budget and i % 100 == 0:
                check_budget()
            path = Path(name)
            if field == "external_files" and not path.is_absolute():
                raise ValueError("External frozen sources must have absolute paths")
            if not path.is_absolute():
                path = repository / path
            if file_hash(path) != expected:
                raise ValueError("Frozen source/checkpoint/input changed: " + name)
    return frozen


def sample_metrics(rows, prediction, truth, metadata, states):
    synthetic = metadata["kind"] == "synthetic"
    result = old.evaluate_sample(rows, truth.get("domain_labels" if synthetic else "region_instances"),
        prediction["before"], prediction["after"], prediction["edges"],
        evaluation_valid=truth.get("evaluation_valid"), orientation_labels=truth.get("orientation_groups"),
        truth_raster=truth.get("domain_labels") if metadata["sampler"] == "grid" else None,
        pixel_spacing_xy=metadata.get("pixel_spacing_xy", (1., 1.)), regime=metadata["regime"],
        kind=metadata["kind"], case=metadata.get("case"), states=states)
    if metadata["sampler"] != "grid":
        result["criteria"] = dict(old._check_result({}, applicable=False),
                                  reason="Center results are diagnostic; formal criteria use grid48")
        for stage in ("before", "after"):
            if synthetic:
                result[stage]["boundary"]["unavailable_reason"] = "center_graph_has_no_grid_axial_boundary_metric"
    return result


def cross_boundary_endpoints(rows, prediction, reference, evaluated):
    edges = old._edges(prediction["edges"], len(rows))
    u, v = edges.T
    cross = evaluated[u] & evaluated[v] & (reference[u] > 0) & (reference[v] > 0) & (reference[u] != reference[v])
    u, v = u[cross], v[cross]
    result = {}
    for stage in ("before", "after"):
        labels = prediction[stage]
        count = (labels[u] > 0).astype(np.int8) + (labels[v] > 0).astype(np.int8)
        result[stage] = dict(reference_cross_boundary_edges=len(u),
            zero_assigned_endpoints=int((count == 0).sum()), one_assigned_endpoint=int((count == 1).sum()),
            two_assigned_endpoints=int((count == 2).sum()),
            merged_with_two_assigned=int(((count == 2) & (labels[u] == labels[v])).sum()),
            separated_with_two_assigned=int(((count == 2) & (labels[u] != labels[v])).sum()))
    return result


def compare_models(data, path, budget):
    """Stream primary per-sample curves; retain only pooled within-sample counts."""
    names = (*AGGREGATE_KEYS, "baseline_family", "stage")
    pooled = {}
    count = 0
    with path.open("w", encoding="utf-8") as stream:
        for value in budget.checked(data.values()):
            meta = value["record"]["metadata"]
            if not primary(meta) or meta["family"] not in CANDIDATES:
                continue
            for family in BASELINES:
                run = meta["regime"] + "/fft" if family == "fft" else f"{meta['regime']}/{family}/z32/seed-{meta['seed']}"
                baseline = data.get((run, 48, "grid", meta["sample_id"], meta["partition"]))
                if baseline is None:
                    raise ValueError(f"Missing paired baseline: {run}")
                if value["rows"] != baseline["rows"] or not np.array_equal(value["reference"], baseline["reference"]) or not np.array_equal(value["evaluated"], baseline["evaluated"]):
                    raise ValueError("Candidate and baseline evaluation scope/IDs differ")
                if not np.array_equal(value["prediction"]["acf_score"], baseline["prediction"]["acf_score"], equal_nan=True):
                    raise ValueError("Matched coverage requires the same original ACF ranking")
                if not np.array_equal(value["prediction"]["edges"], baseline["prediction"]["edges"]):
                    raise ValueError("Paired representations must use the same partition graph")
                for stage in ("before", "after"):
                    metadata = dict(meta, baseline_family=family, stage=stage)
                    comparison = old.matched_coverage(value["reference"], baseline["prediction"][stage],
                        value["prediction"][stage], value["prediction"]["acf_score"],
                        [r["element_id"] for r in value["rows"]], evaluated_mask=value["evaluated"])
                    stream.write(json.dumps(dict(metadata=metadata, baseline_run_id=run, comparison=comparison), allow_nan=False) + "\n")
                    count += 1
                    for group_meta in [metadata] + ([dict(metadata, case="__all__")] if meta["kind"] == "synthetic" else []):
                        ident = key(group_meta, names)
                        prior = pooled.get(ident)
                        pooled[ident] = old.aggregate_comparisons(([prior] if prior else []) + [comparison])
    records = [dict(metadata=dict(zip(names, ident)), comparison=value) for ident, value in pooled.items()]
    benefit_names = tuple(name for name in names if name not in {"run_id", "seed"})
    grouped = defaultdict(dict)
    for row in records:
        grouped[key(row["metadata"], benefit_names)][str(row["metadata"]["seed"])] = row["comparison"]
    benefits = [dict(metadata=dict(zip(benefit_names, ident)), benefit=old.benefit_across_seeds(values)) for ident, values in grouped.items()]
    return records, benefits, count


def continuation(records, stability, benefits):
    groups = defaultdict(list)
    for record in records:
        if primary(record["metadata"]):
            groups[key(record["metadata"], FAMILY_KEYS)].append(record)
    output = []
    for ident, members in groups.items():
        meta = dict(zip(FAMILY_KEYS, ident))
        seeds = (None,) if meta["family"] == "fft" else MODEL_SEEDS
        by_case = {(r["metadata"]["seed"], r["metadata"].get("control_seed"), r["metadata"].get("case")): r for r in members if r["metadata"]["kind"] == "synthetic"}
        checks = {}
        for seed, control_seed, case in itertools.product(seeds, CONTROL_SEEDS, sorted(REQUIRED_CASES)):
            row = by_case.get((seed, control_seed, case))
            checks[f"model_seed={seed}/control_seed={control_seed}/case={case}"] = None if row is None else row["metrics"]["criteria"]["passed"]
        controls = old._check_result(checks)
        measurement = {}
        for seed in seeds:
            values = [r["metrics"] for r in members if r["metadata"]["kind"] == "measurement" and r["metadata"]["seed"] == seed]
            measurement[str(seed)] = old.aggregate_samples(values)["criteria"] if values else old._check_result({"measurement_available": None})
        stable_rows = [r for r in stability if key(r["metadata"], FAMILY_KEYS) == ident and r["stability"]["criteria"]["applicable"]]
        stable = True if meta["family"] == "fft" else (all(r["stability"]["criteria"]["passed"] is True for r in stable_rows) if stable_rows else None)
        gains = {}
        for family in BASELINES:
            gains[family] = {}
            for stage, kind in itertools.product(("before", "after"), ("synthetic", "measurement")):
                rows = [r for r in benefits if key(r["metadata"], FAMILY_KEYS) == ident and
                        r["metadata"]["baseline_family"] == family and r["metadata"]["stage"] == stage and
                        r["metadata"]["kind"] == kind and (kind == "measurement" or r["metadata"]["case"] == "__all__")]
                gains[family][stage + "/" + kind] = rows[0]["benefit"]["benefit_condition"] if len(rows) == 1 else None
        conditions = dict(all_synthetic_control_conditions=controls["passed"], stability=stable,
                          ttmapp_coverage_all_seeds=all(v.get("scope_conditions", v)["passed"] is True for v in measurement.values()))
        conditions.update({f"benefit_after_vs_{family}_on_{kind}": gains[family]["after/" + kind]
                           for family, kind in itertools.product(BASELINES, ("synthetic", "measurement"))})
        qualified = old._check_result(conditions, applicable=meta["family"] in CANDIDATES)
        output.append(dict(metadata=meta, synthetic_controls=controls, ttmapp=measurement, stability=stable,
            benefit=gains, continuation=qualified, primary=meta["family"] == "mask50",
            primary_claim_qualified=bool(meta["family"] == "mask50" and qualified["qualified"]),
            claim_scope="represented regions of the existing transfer test only" if meta["regime"] == "transfer" else "three partial-reference groups of the current acquisition",
            full_three_group_ttmapp_benefit=qualified["qualified"] and all(v["passed"] is True for v in measurement.values()),
            note="mask50 fixed primary; mask25 diagnostic; new control seeds of known families; no independent STM acquisition"))
    return output


def map_centers(root, frozen, groups, data, records, budget):
    arrays_by_sample = {}
    for value in list(data.values()):
        meta = value["record"]["metadata"]
        if not primary(meta) or meta["kind"] != "measurement":
            continue
        budget.check()
        center = data[meta["run_id"], 48, "centers", meta["sample_id"], meta["partition"]]
        group = groups[value["source_entry"]["cache_group"]]
        if meta["sample_id"] not in arrays_by_sample:
            loaded, arrays = load_sample(Path(group["analysis"]), meta["sample_id"])
            if loaded["content_sha256"] != group["record"]["content_sha256"]:
                raise ValueError("Source centers changed after freeze")
            arrays_by_sample[meta["sample_id"]] = arrays
        arrays = arrays_by_sample[meta["sample_id"]]
        if [r["element_id"] for r in center["rows"]] != arrays["object_ids"].tolist() or not np.array_equal(old._positions(center["rows"]), arrays["centers_xy"]):
            raise ValueError("Center identity differs from the original input")
        eligible = np.asarray([meta["regime"] != "transfer" or r.get("transfer_split") == "test" for r in value["rows"]], bool)
        mapped = old.map_current_centers(arrays["centers_xy"], value["rows"], value["prediction"]["before"], value["prediction"]["after"],
                                        pixel_spacing_xy=meta.get("pixel_spacing_xy", (1., 1.)), eligible_grid=eligible)
        available = np.asarray([r["available"] for r in center["rows"]], bool)
        mapped["before"][~available] = mapped["after"][~available] = 0
        states = np.full(len(available), "insufficient_data", dtype="U64")
        effective = mapped["mapped"] & available
        states[effective] = value["states"][mapped["nearest_grid_index"][effective]]
        mapped["edges"] = center["prediction"]["edges"]
        metadata = dict(meta, sampler="centers_from_grid", assessment="nearest_grid_center_diagnostic")
        metrics = sample_metrics(center["rows"], mapped, value["truth"], metadata, states)
        metrics["grid_mapping"] = dict(radius_px=16 * np.sqrt(2) / 2, centers=len(available),
            matched_available_grid=int(mapped["mapped"].sum()), unmatched_count=int((~mapped["mapped"]).sum()),
            denominator_policy="Unmapped centers with complete support remain unassigned")
        records.append(dict(metadata=metadata, metrics=metrics))


def _evaluate(root, controls_dir, measurement_dir, out, budget):
    frozen = verify_freeze(root, check_budget=budget.check)
    index = read(old._frozen_path(root, "predictions/index.json", frozen))
    groups = {r["group_id"]: r for r in read(old._frozen_path(root, "cache/index.json", frozen))}
    # No reference is opened until every frozen source and prediction verifies.
    plan = read(old._frozen_path(root, "plan.json", frozen))
    for directory, field in ((controls_dir, "controls_evaluation_manifest_sha256"),
                             (measurement_dir, "measurement_evaluation_manifest_sha256")):
        if file_hash(directory / "manifest.json") != plan[field]:
            raise ValueError("Evaluation manifest differs from the frozen plan: " + field)
    control_manifest, controls = old._truth_bundle(controls_dir, "controls")
    _, measurements = old._truth_bundle(measurement_dir, "references")
    if len(controls) != 93 or tuple(control_manifest["seeds"]) != CONTROL_SEEDS:
        raise ValueError("Unexpected held-out synthetic realization matrix")
    records, data, row_cache, identities = [], {}, {}, set()
    for item in budget.checked(index):
        ident = key(item)
        if ident in identities:
            raise ValueError("Repeated prediction identity")
        identities.add(ident)
        group_id = item["cache_group"]
        if group_id not in row_cache:
            row_cache[group_id] = read(old._frozen_path(root, f"cache/{group_id}/rows.json.gz", frozen))
        rows = row_cache[group_id]
        filename = f"{item['directory']}/{item['evaluation_input']}"
        with np.load(old._frozen_path(root, filename, frozen), allow_pickle=False) as archive:
            prediction = {k: archive[k] for k in archive.files}
        if not np.array_equal(prediction["available"], np.asarray([r["available"] for r in rows], bool)):
            raise ValueError("Prediction availability differs from frozen support")
        heldout = item["kind"] == "measurement" and item["regime"] == "transfer"
        if heldout:
            if item["evaluation_input"] != "heldout-metrics-input.npz":
                raise ValueError("Transfer must use the separate test-only prediction")
            test = np.asarray([r.get("transfer_split") == "test" for r in rows], bool)
            if (prediction["before"][~test] > 0).any() or (prediction["after"][~test] > 0).any() or (len(prediction["edges"]) and not test[prediction["edges"]].all()):
                raise ValueError("Held-out graph contains non-test assignments or edges")
        payload = read(old._frozen_path(root, f"{item['directory']}/" + ("heldout-result.json.gz" if heldout else "result.json.gz"), frozen))
        if [a["element_id"] for a in payload["assignments"]] != [r["element_id"] for r in rows]:
            raise ValueError("Result envelope element order differs")
        if not np.array_equal(np.asarray([a["domain_id"] is not None for a in payload["assignments"]]), prediction["after"] > 0):
            raise ValueError("Result envelope and prediction assignments disagree")
        states = np.asarray([a["state"] for a in payload["assignments"]], dtype="U64")
        source = controls if item["kind"] == "synthetic" else measurements
        if item["kind"] == "synthetic" and item["sample_id"] not in source:
            raise ValueError("Synthetic truth is missing")
        truth_meta, truth = source.get(item["sample_id"], ({}, {}))
        meta = {k: v for k, v in item.items() if k not in {"directory", "cache_group", "evaluation_input"}}
        meta.update(case=truth_meta.get("case"), control_seed=truth_meta.get("seed"),
                    assessment="primary_grid" if primary(item) else "other_grid_scale_diagnostic" if item["sampler"] == "grid" else "own_center_graph_diagnostic")
        metrics = sample_metrics(rows, prediction, truth, meta, states)
        record = dict(metadata=meta, metrics=metrics)
        records.append(record)
        # Keep grid arrays for primary comparisons and exact annotation ablations;
        # only real center48 predictions are needed for the separate mapped-center output.
        if item["sampler"] == "grid" or (item["scale_px"] == 48 and item["kind"] == "measurement"):
            labels = truth.get("domain_labels" if item["kind"] == "synthetic" else "region_instances")
            ref = old._comparison_reference(rows, labels, truth.get("evaluation_valid"), kind=item["kind"], regime=item["regime"])
            evaluated = old._evaluated_mask(rows, labels, truth.get("evaluation_valid"), kind=item["kind"], regime=item["regime"])
            data[ident] = dict(rows=rows, prediction=prediction, states=states, record=record, reference=ref,
                               evaluated=evaluated, truth=truth, source_entry=item)
            if primary(item):
                record["cross_boundary_endpoints"] = cross_boundary_endpoints(rows, prediction, ref, evaluated)
        if len(records) % 1000 == 0:
            print(f"evaluated {len(records)}/{len(index)}", flush=True)
    map_centers(root, frozen, groups, data, records, budget)
    by_control = {(meta["seed"], meta["case"]): sid for sid, (meta, _) in controls.items()}
    ablations = []
    for entry in budget.checked(data.values()):
        meta = entry["record"]["metadata"]
        if meta["sampler"] != "grid" or meta["case"] not in ANNOTATION_PAIRS:
            continue
        base_sid = by_control[meta["control_seed"], ANNOTATION_PAIRS[meta["case"]]]
        baseline = data[meta["run_id"], meta["scale_px"], "grid", base_sid, meta["partition"]]
        invariant = old.ablation_invariance([r["element_id"] for r in baseline["rows"]], baseline["prediction"]["before"], baseline["prediction"]["after"],
            [r["element_id"] for r in entry["rows"]], entry["prediction"]["before"], entry["prediction"]["after"])
        base_criteria = old.control_criteria(entry["record"]["metrics"], ANNOTATION_PAIRS[meta["case"]])
        entry["record"]["metrics"]["criteria"] = old._check_result(dict(base_criteria["checks"],
            paired_grid_partition_invariance=invariant["passed"]))
        ablations.append(dict(metadata=meta, baseline_sample_id=base_sid, invariance=invariant,
                              interpretation="Annotation-only change; not robustness to perturbed image pixels"))
    grouped = defaultdict(list)
    for record in records:
        grouped[key(record["metadata"], AGGREGATE_KEYS)].append(record["metrics"])
    aggregates = [dict(metadata=dict(zip(AGGREGATE_KEYS, ident)), metrics=old.aggregate_samples(values)) for ident, values in budget.checked(grouped.items())]
    for aggregate in aggregates:
        if aggregate["metadata"]["sampler"] != "grid":
            aggregate["metrics"]["criteria"] = dict(old._check_result({}, applicable=False),
                reason="Center results are diagnostic; formal criteria use grid48")
    stable_groups = {}
    stable_keys = ("regime", "family", "latent", "scale_px", "sampler", "sample_id", "partition", "kind", "case")
    for entry in data.values():
        meta = entry["record"]["metadata"]
        if not primary(meta) or meta["seed"] is None:
            continue
        group = stable_groups.setdefault(key(meta, stable_keys), dict(metadata={k: meta[k] for k in stable_keys}, predictions={}, eligible=set()))
        group["predictions"][str(meta["seed"])] = {r["element_id"]: int(p) for r, p in zip(entry["rows"], entry["prediction"]["after"])}
        group["eligible"].update(r["element_id"] for r, valid in zip(entry["rows"], entry["evaluated"]) if valid)
    stability = [dict(metadata=g["metadata"], stability=old.seed_stability(g["predictions"], eligible_ids=g["eligible"],
        require_pair_evidence=g["metadata"]["case"] not in old.ZERO_CASES | {"insufficient_field"})) for g in budget.checked(stable_groups.values())]
    with tempfile.TemporaryDirectory(prefix=".masked25-comparisons-", dir=root) as temporary:
        path = Path(temporary) / "comparisons.jsonl"
        comparisons, benefits, comparison_count = compare_models(data, path, budget)
        criteria = continuation(records, stability, benefits)
        budget.check()
        old.write_summary(records, out, extras=dict(aggregates=aggregates, comparisons=comparisons, stability=stability,
            ablations=ablations, benefits=benefits, criteria=criteria,
            comparisons_scope="grid48 only; four paired baselines, same solver, both stages; sample curves in comparisons.jsonl"))
        shutil.copyfile(path, out / "comparisons.jsonl")
    for name, values in (("aggregates", aggregates), ("pooled-comparisons", comparisons), ("stability", stability),
                         ("ablations", ablations), ("benefits", benefits), ("continuation", criteria)):
        budget.check()
        write_json(out / (name + ".json"), values)
        old._flat_csv(out / (name + ".csv"), values)
    evidence = dict(schema="stmdomains-masked-ae25-evaluation-evidence-v1",
        frozen_manifest_sha256=file_hash(root / "frozen-predictions.json"), verified_prediction_files=len(frozen["files"]),
        verified_external_files=len(frozen.get("external_files", {})), prediction_entries=len(index), evaluated_records=len(records),
        primary_sample_comparisons=comparison_count, controls_count=len(controls), control_seeds=list(CONTROL_SEEDS),
        controls_manifest_sha256=file_hash(Path(controls_dir) / "manifest.json"), measurement_manifest_sha256=file_hash(Path(measurement_dir) / "manifest.json"),
        code_sha256=file_hash(Path(__file__)), primary="mask50/grid48; transfer and transduction separately",
        centers_boundary_metric=False, fresh_controls="New realizations of known synthetic families; no new STM acquisition",
        partial_reference_policy="Known positive interiors only; no exact TTMAPP boundary or complete detection recall",
        postprocessing_budget=budget.measurements())
    write_json(out / "evaluation-evidence.json", evidence)
    budget.check()
    return evidence


def evaluate_frozen(root, controls_dir=None, measurement_dir=None, out=None):
    root = Path(root).resolve()
    out = Path(out or root / "evaluation")
    if out.exists():
        raise FileExistsError(out)
    with reporting_stage(root, out.name) as budget:
        return _evaluate(root, Path(controls_dir or root / "controls/evaluation"),
                         Path(measurement_dir or ".scratch/unsupervised-input/evaluation"), out, budget)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--controls-evaluation", type=Path)
    parser.add_argument("--measurement-evaluation", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    result = evaluate_frozen(args.output, args.controls_evaluation, args.measurement_evaluation, args.out)
    print(json.dumps({k: result[k] for k in ("prediction_entries", "evaluated_records", "primary_sample_comparisons")}))


if __name__ == "__main__":
    main()
