"""Issue-21a grid-only evaluation, using unchanged issue-20/21 metric functions."""
from __future__ import annotations

import argparse
import itertools
from pathlib import Path
import resource
import time

import numpy as np

from ...bundle import file_hash, write_json
from .. import evaluate as old
from ..evaluate import (ZERO_CASES, TWO_CASES, ABLATION_CASES, evaluate_sample,
    aggregate_samples, aggregate_comparisons, matched_coverage, seed_stability,
    benefit_across_seeds, ablation_invariance, write_summary, _check_result,
    _read_json, _truth_bundle, _frozen_path, _comparison_reference, _evaluated_mask,
    _group_key, _flat_csv)

CONTROL_SEEDS = (920011, 920012, 920013)


class PostprocessBudget(old.PostprocessBudget):
    """All issue-21a phases share ROOT/*.resources.json, including failures."""
    def __init__(self, root: Path):
        self.cpu_started=time.process_time()
        self.wall_started=time.monotonic()
        self.prior_cpu_seconds=0.
        self.prior_reports={}
        for path in sorted(Path(root).glob('*.resources.json')):
            seconds=float(_read_json(path)['cpu_seconds'])
            if not np.isfinite(seconds) or seconds<0: raise ValueError('Invalid CPU resource record')
            self.prior_cpu_seconds+=seconds
            self.prior_reports[path.name]=file_hash(path)
        self.cpu_limit_seconds=7200.
        self.rss_limit_bytes=12*1024**3


def verify_freeze(root: Path, *, check_budget=None) -> dict:
    """Verify local prediction tree, referenced immutable inputs/models, and code."""
    root=Path(root).resolve()
    frozen=old.verify_prediction_freeze(root,check_budget=check_budget)
    for key in ('external_files','code_sha256'):
        for index,(name,expected) in enumerate(frozen.get(key,{}).items()):
            if check_budget is not None and index%20==0: check_budget()
            path=Path(name)
            if not path.is_absolute() or not path.is_file() or file_hash(path)!=expected:
                raise ValueError('Frozen external artifact/code changed: '+name)
    return frozen


def compare_model_pairs(data: dict, budget: PostprocessBudget) -> list[dict]:
    """Matched-seed AE/original-rVAE comparisons at both refusal stages.

    Retains all scored nodes in the coverage denominator and positive-only
    endpoints in pair scores, exactly as the original matched_coverage helper.
    """
    pooled={}
    keys=('run_id','family','seed','partition','kind','case','stage','baseline_family')
    for value in budget.checked(data.values()):
        meta=value['record']['metadata']
        if not meta['family'].startswith('rvae_'): continue
        for family in ('ae','rvae'):
            base_id=f"transfer/{family}/z32/seed-{meta['seed']}"
            key=(base_id,meta['scale_px'],meta['sampler'],meta['sample_id'],meta['partition'])
            if key not in data: continue
            baseline=data[key]
            if not np.array_equal(value['reference'],baseline['reference']):
                raise ValueError('Paired baseline reference mismatch')
            for stage in ('before','after'):
                metadata=dict(meta,stage=stage,baseline_family=family)
                comparison=matched_coverage(value['reference'],baseline['prediction'][stage],
                    value['prediction'][stage],value['prediction']['acf_score'],
                    [row['element_id'] for row in value['rows']],evaluated_mask=value['evaluated_mask'])
                pooled.setdefault(_group_key(metadata,keys),[]).append(comparison)
    return [dict(metadata=dict(zip(keys,key)),comparison=aggregate_comparisons(values))
            for key,values in budget.checked(pooled.items())]

def continuation_summary(records, stability, benefits) -> list[dict]:
    """All fixed primary-grid cases/seeds, not a favorable average of checks."""
    family_keys = ("regime", "family", "latent", "partition")
    group_records = {}
    for record in records:
        meta = record["metadata"]
        if meta["sampler"] == "grid" and meta["scale_px"] == 48:
            group_records.setdefault(_group_key(meta, family_keys), []).append(record)
    required_cases = ZERO_CASES | TWO_CASES | ABLATION_CASES | {"single", "insufficient_field"}
    output = []
    for key, members in group_records.items():
        meta = dict(zip(family_keys, key))
        model_seeds = [None] if meta["family"] == "fft" else [20261101, 20261102, 20261103]
        by_case = {(record["metadata"]["seed"], record["metadata"]["case"], record["metadata"]["control_seed"]): record
                   for record in members if record["metadata"]["kind"] == "synthetic"}
        checks = {}
        for model_seed, case, control_seed in itertools.product(model_seeds, sorted(required_cases), CONTROL_SEEDS):
            record = by_case.get((model_seed, case, control_seed))
            checks[f"model_seed={model_seed}/case={case}/control_seed={control_seed}"] = None if record is None else record["metrics"]["criteria"]["passed"]
        controls = _check_result(checks)
        ttmapp = {}
        for seed in model_seeds:
            values = [record["metrics"] for record in members if record["metadata"]["kind"] == "measurement" and record["metadata"]["seed"] == seed]
            ttmapp[str(seed)] = aggregate_samples(values)["criteria"] if values else _check_result({"evaluation_available": None})
        stabilities = [entry for entry in stability if _group_key(entry["metadata"], family_keys) == key
                       and entry["metadata"]["sampler"] == "grid" and entry["metadata"]["scale_px"] == 48
                       and entry["stability"]["criteria"]["applicable"]]
        stable = True if meta["family"] == "fft" else (all(entry["stability"]["criteria"]["passed"] is True for entry in stabilities) if stabilities else None)
        benefit = {"synthetic": None, "measurement": None}
        for entry in benefits:
            item = entry["metadata"]
            if _group_key(item, family_keys) == key and item["sampler"] == "grid" and item["scale_px"] == 48:
                if item["kind"] == "synthetic" and item["case"] == "__all__":
                    benefit["synthetic"] = entry["benefit"]["benefit_condition"]
                if item["kind"] == "measurement":
                    benefit["measurement"] = entry["benefit"]["benefit_condition"]
        qualification = _check_result(dict(
            all_synthetic_control_conditions=controls["passed"], stability=stable,
            ttmapp_coverage_all_seeds=all(value.get("scope_conditions", value)["passed"] is True for value in ttmapp.values()),
            benefit_on_controls=benefit["synthetic"], benefit_on_ttmapp=benefit["measurement"],
        ), applicable=meta["family"] != "fft")
        output.append(dict(metadata=meta, synthetic_controls=controls, ttmapp=ttmapp,
                           stability=stable, benefit=benefit, continuation=qualification,
                           claim_scope="represented transfer-test regions only" if meta["regime"] == "transfer" else "all three partial-reference groups in transduction",
                           full_three_group_ttmapp_benefit=qualification["qualified"] and all(value["passed"] is True for value in ttmapp.values()),
                           note="Issue21a grid48 transferz32 only; TTMAPP is exploratory. Passing is research continuation, never application acceptance or independent-acquisition generalization."))
    return output


def _evaluate_frozen(predictions_root: Path, controls_evaluation: Path,
                     measurement_evaluation: Path, out: Path, budget: PostprocessBudget) -> dict:
    """Evaluate the predict.py index only after its complete freeze verifies."""
    started, cpu_started = time.monotonic(), time.process_time()
    root, out = Path(predictions_root).resolve(), Path(out)
    if out.exists():
        raise FileExistsError(f"Use a fresh evaluation output: {out}")
    budget.check()
    frozen = verify_freeze(root, check_budget=budget.check)
    budget.check()
    # No reference path has been opened above this line.
    _, control_truth = _truth_bundle(controls_evaluation, "controls")
    if {int(meta['seed']) for meta,_ in control_truth.values()} != set(CONTROL_SEEDS):
        raise ValueError('Unexpected fresh control seed set')
    _, measurement_truth = _truth_bundle(measurement_evaluation, "references")
    index = _read_json(_frozen_path(root, "predictions/index.json", frozen))
    cache_index = _read_json(_frozen_path(root, "cache/index.json", frozen))
    groups = {group["group_id"]: group for group in cache_index}
    rows_cache, data, records = {}, {}, []
    for item in index:
        key = _group_key(item, ("run_id", "scale_px", "sampler", "sample_id", "partition"))
        if key in data:
            raise ValueError("Duplicate prediction index entry")
        group = item["cache_group"]
        if group not in rows_cache:
            rows_cache[group] = _read_json(_frozen_path(root, f"cache/{group}/rows.json.gz", frozen))
        rows = rows_cache[group]
        path = _frozen_path(root, f"{item['directory']}/{item['evaluation_input']}", frozen)
        with np.load(path, allow_pickle=False) as archive:
            prediction = {name: archive[name] for name in archive.files}
        if not np.array_equal(prediction["available"], np.asarray([row["available"] for row in rows], dtype=bool)):
            raise ValueError("Prediction availability disagrees with frozen row geometry")
        heldout = item["kind"] == "measurement" and item["regime"] == "transfer"
        if heldout and item["evaluation_input"] != "heldout-metrics-input.npz":
            raise ValueError("Transfer must evaluate the graph containing test nodes only")
        payload_name = "heldout-result.json.gz" if heldout else "result.json.gz"
        payload = _read_json(_frozen_path(root, f"{item['directory']}/{payload_name}", frozen))
        if [assignment["element_id"] for assignment in payload["assignments"]] != [row["element_id"] for row in rows]:
            raise ValueError("Assignment/row order differs")
        assigned = np.asarray([assignment["domain_id"] is not None for assignment in payload["assignments"]], dtype=bool)
        if not np.array_equal(assigned, prediction["after"] > 0):
            raise ValueError("Result envelope and evaluation assignments disagree")
        states = np.asarray([assignment["state"] for assignment in payload["assignments"]], dtype="U64")
        source = control_truth if item["kind"] == "synthetic" else measurement_truth
        if item["kind"] == "synthetic" and item["sample_id"] not in source:
            raise ValueError("Missing truth for a synthetic evaluation sample")
        reference_meta, truth = source.get(item["sample_id"], ({}, {}))
        labels = truth.get("domain_labels" if item["kind"] == "synthetic" else "region_instances")
        case = reference_meta.get("case")
        metrics = evaluate_sample(
            rows, labels, prediction["before"], prediction["after"], prediction["edges"],
            evaluation_valid=truth.get("evaluation_valid"), orientation_labels=truth.get("orientation_groups"),
            truth_raster=truth.get("domain_labels"), pixel_spacing_xy=item["pixel_spacing_xy"],
            regime=item["regime"], kind=item["kind"], case=case, states=states,
        )
        metadata = {key: value for key, value in item.items() if key not in {"directory", "cache_group", "evaluation_input"}}
        metadata.update(case=case, control_seed=reference_meta.get("seed"),
                        assessment="primary_grid" if item["sampler"] == "grid" else "own_center_graph_diagnostic")
        record = dict(metadata=metadata, metrics=metrics)
        records.append(record)
        data[key] = dict(rows=rows, prediction=prediction, record=record,
                         reference=_comparison_reference(rows, labels, truth.get("evaluation_valid"), kind=item["kind"], regime=item["regime"]),
                         evaluated_mask=_evaluated_mask(rows, labels, truth.get("evaluation_valid"), kind=item["kind"], regime=item["regime"]),
                         truth=truth, states=states, source_entry=item)
        if len(records) % 500 == 0:
            print(f"evaluated {len(records)}/{len(index)} frozen predictions", flush=True)
        if len(records) % 100 == 0:
            budget.check()

    by_control = {(item[0]["seed"], item[0]["case"]): ident for ident, item in control_truth.items()}
    ablations = []
    for index_position, (key, value) in enumerate(data.items()):
        if index_position % 100 == 0:
            budget.check()
        metadata = value["record"]["metadata"]
        if metadata["sampler"] != "grid" or metadata["case"] not in ABLATION_CASES:
            continue
        baseline_id = by_control[metadata["control_seed"], "single"]
        baseline = data[(metadata["run_id"], metadata["scale_px"], "grid", baseline_id, metadata["partition"])]
        invariance = ablation_invariance(
            [row["element_id"] for row in baseline["rows"]], baseline["prediction"]["before"], baseline["prediction"]["after"],
            [row["element_id"] for row in value["rows"]], value["prediction"]["before"], value["prediction"]["after"],
        )
        checks = dict(value["record"]["metrics"]["criteria"]["checks"], paired_grid_partition_invariance=invariance["passed"])
        value["record"]["metrics"]["criteria"] = _check_result(checks)
        ablations.append(dict(metadata=metadata, baseline_sample_id=baseline_id, invariance=invariance))

    aggregates_by_key, comparisons, stability_groups = {}, [], {}
    aggregate_keys = ("run_id", "regime", "family", "latent", "seed", "scale_px", "sampler", "partition", "kind", "case", "assessment")
    for index_position, value in enumerate(data.values()):
        if index_position % 100 == 0:
            budget.check()
        metadata = value["record"]["metadata"]
        aggregates_by_key.setdefault(_group_key(metadata, aggregate_keys), []).append(value["record"]["metrics"])
        baseline_key = (metadata["regime"] + "/fft", metadata["scale_px"], metadata["sampler"], metadata["sample_id"], "fh4")
        if baseline_key in data and not (metadata["family"] == "fft" and metadata["partition"] == "fh4"):
            baseline = data[baseline_key]
            if not np.array_equal(value["reference"], baseline["reference"]):
                raise ValueError("Baseline and candidate evaluated on different reference positions")
            if not np.array_equal(value["prediction"]["acf_score"], baseline["prediction"]["acf_score"], equal_nan=True):
                raise ValueError("Matched-coverage ranking must use the same ACF scores")
            comparisons.append(dict(metadata=metadata, comparison=matched_coverage(
                value["reference"], baseline["prediction"]["after"], value["prediction"]["after"],
                value["prediction"]["acf_score"], [row["element_id"] for row in value["rows"]],
                evaluated_mask=value["evaluated_mask"],
            )))
        if metadata["seed"] is not None:
            keys = ("regime", "family", "latent", "scale_px", "sampler", "sample_id", "partition", "kind", "case")
            group = stability_groups.setdefault(_group_key(metadata, keys), dict(predictions={}, eligible=set(), metadata={key: metadata[key] for key in keys}))
            group["predictions"][str(metadata["seed"])] = {row["element_id"]: int(label) for row, label in zip(value["rows"], value["prediction"]["after"])}
            group["eligible"].update(row["element_id"] for row, eligible in zip(value["rows"], value["evaluated_mask"]) if eligible)
    aggregates = [dict(metadata=dict(zip(aggregate_keys, key)), metrics=aggregate_samples(values))
                  for key, values in budget.checked(aggregates_by_key.items())]
    stability = [dict(metadata=value["metadata"], stability=seed_stability(value["predictions"], eligible_ids=value["eligible"],
                    require_pair_evidence=value["metadata"]["case"] not in ZERO_CASES | {"insufficient_field"}))
                 for value in budget.checked(stability_groups.values())]
    comparison_keys = ("run_id", "regime", "family", "latent", "seed", "scale_px", "sampler", "partition", "kind", "case", "assessment")
    comparison_groups = {}
    for record in budget.checked(comparisons):
        comparison_groups.setdefault(_group_key(record["metadata"], comparison_keys), []).append(record["comparison"])
    pooled_comparisons = [dict(metadata=dict(zip(comparison_keys, key)), comparison=aggregate_comparisons(values))
                          for key, values in budget.checked(comparison_groups.items())]
    synthetic_all = {}
    all_keys = tuple(key for key in comparison_keys if key != "case")
    for record in budget.checked(comparisons):
        if record["metadata"]["kind"] == "synthetic":
            synthetic_all.setdefault(_group_key(record["metadata"], all_keys), []).append(record["comparison"])
    pooled_comparisons.extend(dict(metadata=dict(zip(all_keys, key), case="__all__"), comparison=aggregate_comparisons(values))
                              for key, values in budget.checked(synthetic_all.items()))
    benefit_keys = ("regime", "family", "latent", "scale_px", "sampler", "partition", "kind", "case", "assessment")
    benefit_groups = {}
    for record in budget.checked(pooled_comparisons):
        if record["metadata"]["seed"] is not None:
            benefit_groups.setdefault(_group_key(record["metadata"], benefit_keys), {})[str(record["metadata"]["seed"])] = record["comparison"]
    benefits = [dict(metadata=dict(zip(benefit_keys, key)), benefit=benefit_across_seeds(values))
                for key, values in budget.checked(benefit_groups.items())]
    continuation = continuation_summary(records, stability, benefits)
    paired = compare_model_pairs(data, budget)

    budget.check()
    write_summary(records, out, extras=dict(aggregates=aggregates, comparisons=pooled_comparisons,
                  stability=stability, ablations=ablations, benefits=benefits, criteria=continuation))
    for filename, values in (("aggregates", aggregates), ("comparisons", comparisons), ("pooled-comparisons", pooled_comparisons),
                             ("stability", stability), ("ablations", ablations), ("benefits", benefits), ("continuation", continuation), ("paired-model-comparisons", paired)):
        budget.check()
        write_json(out / f"{filename}.json", values)
        _flat_csv(out / f"{filename}.csv", values)
    evidence = dict(
        schema="stmdomains-post-freeze-evaluation-v1", frozen_manifest_sha256=file_hash(root / "frozen-predictions.json"),
        verified_prediction_files=len(frozen["files"]), verified_external_files=len(frozen.get("external_files",{})), prediction_entries=len(index), evaluated_records=len(records),
        controls_manifest_sha256=file_hash(Path(controls_evaluation) / "manifest.json"),
        measurement_manifest_sha256=file_hash(Path(measurement_evaluation) / "manifest.json"),
        evaluation_code_sha256=file_hash(Path(__file__)),
        elapsed_seconds=time.monotonic() - started, cpu_seconds=time.process_time() - cpu_started,
        peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        policy="Read-only frozen predictions; no model selection, parameter changes or exact TTMAPP boundary claims",
        postprocessing_budget=budget.measurements(),
    )
    budget.check()
    write_json(out / "evaluation-evidence.json", evidence)
    return evidence


def evaluate_frozen(predictions_root: Path, controls_evaluation: Path,
                    measurement_evaluation: Path, out: Path) -> dict:
    root,out=Path(predictions_root).resolve(),Path(out)
    resource_path=root/f'{out.name}.resources.json'
    if out.exists() or resource_path.exists(): raise FileExistsError(out)
    budget=PostprocessBudget(root)
    status='failed'
    try:
        result=_evaluate_frozen(root,controls_evaluation,measurement_evaluation,out,budget)
        status='completed'
        return result
    finally: write_json(resource_path,dict(status=status,**budget.measurements()))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--predictions',type=Path,required=True)
    parser.add_argument('--controls-evaluation',type=Path,required=True)
    parser.add_argument('--measurement-evaluation',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    print(evaluate_frozen(args.predictions,args.controls_evaluation,args.measurement_evaluation,args.out))


if __name__=='__main__': main()
