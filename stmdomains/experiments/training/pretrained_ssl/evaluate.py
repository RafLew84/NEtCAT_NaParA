"""Issue26 adapter for the unchanged issue20 metrics and frozen input contract.

Two predeclared conclusions: representation before refusals on positive
controls/partial STM, and complete detector after refusals. Neither chooses a
checkpoint, seed, readout or threshold. A deterministic baseline is stored
once per regime and paired with each adaptation seed without duplicating it.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import itertools
import json
from pathlib import Path
import shutil
import tempfile

import numpy as np

from ...bundle import file_hash, write_json
from .. import evaluate as metrics20
from ..masked_ae.evaluate import (ANNOTATION_PAIRS, AGGREGATE_KEYS, FAMILY_KEYS, read, key, primary,
    verify_freeze, sample_metrics, cross_boundary_endpoints, map_centers)
from .common import reporting_stage


MODEL_SEEDS = (20261101, 20261102, 20261103)
CONTROL_SEEDS = (930031, 930032, 930033)
BASELINES = ("dino_frozen", "fft")
POSITIVE_CASES = metrics20.TWO_CASES | {"single"}
REQUIRED_CASES = metrics20.ZERO_CASES | metrics20.TWO_CASES | set(ANNOTATION_PAIRS) | {"single", "insufficient_field"}


def stage_criteria(record, stage, invariant=None):
    meta, metrics = record["metadata"], record["metrics"]
    if meta["sampler"] != "grid":
        return metrics20._check_result({}, applicable=False)
    view = dict(metrics, after=metrics[stage])
    if meta["kind"] == "measurement":
        return metrics20.ttmapp_criteria(view)
    result = metrics20.control_criteria(view, ANNOTATION_PAIRS.get(meta["case"], meta["case"]))
    if meta["case"] in ANNOTATION_PAIRS:
        result = metrics20._check_result(dict(result["checks"], paired_grid_partition_invariance=invariant))
    return result


def paired_comparisons(data, path, budget):
    """Use one seedless baseline for each candidate seed; stream sample curves."""
    names = (*AGGREGATE_KEYS, "baseline_family", "stage")
    pooled, sample_count = {}, 0
    with path.open("w", encoding="utf-8") as stream:
        for value in budget.checked(data.values()):
            meta = value["record"]["metadata"]
            if not primary(meta) or meta["family"] != "dino_adapted":
                continue
            for family in BASELINES:
                run_id = meta["regime"] + "/" + family
                base = data[run_id, 48, "grid", meta["sample_id"], meta["partition"]]
                if base["record"]["metadata"]["seed"] is not None:
                    raise ValueError("The frozen baseline must not be duplicated as training seeds")
                if value["rows"] != base["rows"] or not np.array_equal(value["reference"], base["reference"]) or not np.array_equal(value["evaluated"], base["evaluated"]):
                    raise ValueError("Paired methods differ in element identity or evaluation scope")
                for name in ("edges", "acf_score", "available"):
                    if not np.array_equal(value["prediction"][name], base["prediction"][name], equal_nan=True):
                        raise ValueError("Paired methods differ in graph, support or shared ACF ranking")
                for stage in ("before", "after"):
                    metadata = dict(meta, baseline_family=family, stage=stage)
                    result = metrics20.matched_coverage(value["reference"], base["prediction"][stage], value["prediction"][stage],
                        value["prediction"]["acf_score"], [r["element_id"] for r in value["rows"]], evaluated_mask=value["evaluated"])
                    stream.write(json.dumps(dict(metadata=metadata, baseline_run_id=run_id, comparison=result), allow_nan=False) + "\n")
                    sample_count += 1
                    groups = [metadata]
                    if meta["kind"] == "synthetic":
                        groups.append(dict(metadata, case="__all__"))
                        if meta["case"] in POSITIVE_CASES:
                            groups.append(dict(metadata, case="__positive__"))
                    for group_meta in groups:
                        ident = key(group_meta, names)
                        previous = pooled.get(ident)
                        pooled[ident] = metrics20.aggregate_comparisons(([previous] if previous else []) + [result])
    records = [dict(metadata=dict(zip(names, ident)), comparison=value) for ident, value in pooled.items()]
    benefit_names = tuple(n for n in names if n not in {"run_id", "seed"})
    grouped = defaultdict(dict)
    for record in records:
        grouped[key(record["metadata"], benefit_names)][str(record["metadata"]["seed"])] = record["comparison"]
    benefits = [dict(metadata=dict(zip(benefit_names, ident)), benefit=metrics20.benefit_across_seeds(values)) for ident, values in grouped.items()]
    return records, benefits, sample_count


def stability_records(data, budget):
    groups = {}
    names = ("regime", "family", "latent", "scale_px", "sampler", "sample_id", "partition", "kind", "case", "stage")
    for entry in data.values():
        meta = entry["record"]["metadata"]
        if not primary(meta) or meta["family"] != "dino_adapted":
            continue
        for stage in ("before", "after"):
            if stage == "before" and meta["kind"] == "synthetic" and meta["case"] not in POSITIVE_CASES:
                continue
            metadata = dict(meta, stage=stage)
            group = groups.setdefault(key(metadata, names), dict(metadata={n: metadata[n] for n in names}, predictions={}, eligible=set()))
            group["predictions"][str(meta["seed"])] = {r["element_id"]: int(p) for r, p in zip(entry["rows"], entry["prediction"][stage])}
            group["eligible"].update(r["element_id"] for r, valid in zip(entry["rows"], entry["evaluated"]) if valid)
    return [dict(metadata=g["metadata"], stability=metrics20.seed_stability(g["predictions"], eligible_ids=g["eligible"],
        require_pair_evidence=g["metadata"]["case"] not in metrics20.ZERO_CASES | {"insufficient_field"})) for g in budget.checked(groups.values())]


def verdicts(records, stability, benefits):
    """Emit all four planned candidate decisions, even when no fit succeeded."""
    output = []
    for regime, partition in itertools.product(("transfer", "transductive"), ("fh4", "mws")):
        members = [r for r in records if primary(r["metadata"]) and r["metadata"]["family"] == "dino_adapted"
                   and r["metadata"]["regime"] == regime and r["metadata"]["partition"] == partition]
        lookup = {(r["metadata"]["seed"], r["metadata"].get("control_seed"), r["metadata"].get("case")): r
                  for r in members if r["metadata"]["kind"] == "synthetic"}
        available_seeds = sorted({r["metadata"]["seed"] for r in members})
        complete = available_seeds == list(MODEL_SEEDS)
        stage_results, ttmapp, gains = {}, {}, {}
        for stage, cases, cohort in (("before", POSITIVE_CASES, "__positive__"), ("after", REQUIRED_CASES, "__all__")):
            checks = {}
            for seed, control_seed, case in itertools.product(MODEL_SEEDS, CONTROL_SEEDS, sorted(cases)):
                row = lookup.get((seed, control_seed, case))
                checks[f"model_seed={seed}/control_seed={control_seed}/case={case}"] = None if row is None else row["stage_criteria"][stage]["passed"]
            controls = metrics20._check_result(checks)
            ttmapp[stage] = {}
            for seed in MODEL_SEEDS:
                values = [r["metrics"] for r in members if r["metadata"]["kind"] == "measurement" and r["metadata"]["seed"] == seed]
                if values:
                    aggregate = metrics20.aggregate_samples(values)
                    ttmapp[stage][str(seed)] = metrics20.ttmapp_criteria(dict(aggregate, after=aggregate[stage]))
                else:
                    ttmapp[stage][str(seed)] = metrics20._check_result({"measurement_available": None})
            matched_stability = [r for r in stability if r["metadata"]["regime"] == regime and r["metadata"]["partition"] == partition
                                 and r["metadata"]["stage"] == stage and r["stability"]["criteria"]["applicable"]]
            stable = all(r["stability"]["criteria"]["passed"] is True for r in matched_stability) if matched_stability else None
            conditions = dict(all_planned_adaptation_seeds_available=complete, positive_controls=controls["passed"] if stage == "before" else None,
                              all_required_controls=controls["passed"] if stage == "after" else None, stability=stable)
            conditions.pop("all_required_controls" if stage == "before" else "positive_controls")
            if stage == "after":
                conditions["ttmapp_scope_coverage_all_seeds"] = all(v.get("scope_conditions", v)["passed"] is True for v in ttmapp[stage].values())
            gains[stage] = {}
            for baseline, kind in itertools.product(BASELINES, ("synthetic", "measurement")):
                entries = [r for r in benefits if r["metadata"]["regime"] == regime and r["metadata"]["partition"] == partition
                           and r["metadata"]["baseline_family"] == baseline and r["metadata"]["stage"] == stage
                           and r["metadata"]["kind"] == kind and (kind == "measurement" or r["metadata"]["case"] == cohort)]
                value = entries[0]["benefit"]["benefit_condition"] if len(entries) == 1 else None
                gains[stage][baseline + "/" + kind] = value
                conditions[f"benefit_vs_{baseline}_on_{kind}"] = value
            stage_results[stage] = dict(criteria=metrics20._check_result(conditions), controls=controls, stability=stable,
                control_criteria_cases=sorted(cases), synthetic_benefit_cohort=cohort,
                baseline_seed_policy="One unchanged baseline per regime, paired with each adaptation seed")
        output.append(dict(metadata=dict(regime=regime, family="dino_adapted", latent=384, partition=partition),
            available_adaptation_seeds=available_seeds, missing_adaptation_seeds=sorted(set(MODEL_SEEDS) - set(available_seeds)),
            evidence_status="complete" if complete else "insufficient_adaptation_runs", before=stage_results["before"], after=stage_results["after"],
            representation_improved_before=stage_results["before"]["criteria"]["qualified"],
            complete_detector_after=stage_results["after"]["criteria"]["qualified"], ttmapp=ttmapp, paired_benefits=gains,
            fixed_gate_ceiling=dict(reference_assignments=0 if regime == "transfer" else 4, reference_denominator=174 if regime == "transfer" else 782,
                source="issue22 gate-and-connectivity audit; same cached order mask and graph", limitation="Changing descriptors cannot remove this fixed final-assignment ceiling"),
            claim_scope="Existing transfer test and new realizations of known positive controls; no application acceptance" if regime == "transfer"
                        else "Transductive representation on the current acquisition; not held-out STM generalization"))
    return output


def load_records(root, controls_dir, measurement_dir, budget):
    frozen = verify_freeze(root, check_budget=budget.check)
    plan = read(metrics20._frozen_path(root, "plan.json", frozen))
    for directory, name in ((controls_dir, "controls_evaluation_manifest_sha256"), (measurement_dir, "measurement_evaluation_manifest_sha256")):
        if file_hash(directory / "manifest.json") != plan[name]:
            raise ValueError("Reference manifest differs from the frozen plan")
    control_manifest, controls = metrics20._truth_bundle(controls_dir, "controls")
    _, measurements = metrics20._truth_bundle(measurement_dir, "references")
    if len(controls) != 93 or tuple(control_manifest["seeds"]) != CONTROL_SEEDS:
        raise ValueError("Unexpected reserved control realizations")
    index = read(metrics20._frozen_path(root, "predictions/index.json", frozen))
    groups = {r["group_id"]: r for r in read(metrics20._frozen_path(root, "cache/index.json", frozen))}
    records, data, row_cache, identities = [], {}, {}, set()
    for item in budget.checked(index):
        identity = key(item)
        if identity in identities:
            raise ValueError("Duplicate prediction identity")
        identities.add(identity)
        group = item["cache_group"]
        if group not in row_cache:
            row_cache[group] = read(metrics20._frozen_path(root, f"cache/{group}/rows.json.gz", frozen))
        rows = row_cache[group]
        with np.load(metrics20._frozen_path(root, f"{item['directory']}/{item['evaluation_input']}", frozen), allow_pickle=False) as archive:
            prediction = {name: archive[name] for name in archive.files}
        if not np.array_equal(prediction["available"], np.asarray([r["available"] for r in rows], bool)):
            raise ValueError("Prediction support differs from frozen geometry")
        heldout = item["kind"] == "measurement" and item["regime"] == "transfer"
        if heldout:
            test = np.asarray([r.get("transfer_split") == "test" for r in rows], bool)
            if item["evaluation_input"] != "heldout-metrics-input.npz" or (prediction["before"][~test] > 0).any() or (prediction["after"][~test] > 0).any() or (len(prediction["edges"]) and not test[prediction["edges"]].all()):
                raise ValueError("Transfer evaluation requires the separate test-only graph")
        states = prediction.get("states")
        if states is None:
            payload = read(metrics20._frozen_path(root, f"{item['directory']}/" + ("heldout-result.json.gz" if heldout else "result.json.gz"), frozen))
            if [a["element_id"] for a in payload["assignments"]] != [r["element_id"] for r in rows]:
                raise ValueError("Legacy FFT envelope row identity differs")
            if not np.array_equal(np.asarray([a["domain_id"] is not None for a in payload["assignments"]]), prediction["after"] > 0):
                raise ValueError("Legacy FFT assignments differ from metrics arrays")
            states = np.asarray([a["state"] for a in payload["assignments"]], dtype="U64")
        source = controls if item["kind"] == "synthetic" else measurements
        if item["kind"] == "synthetic" and item["sample_id"] not in source:
            raise ValueError("Missing synthetic reference")
        truth_meta, truth = source.get(item["sample_id"], ({}, {}))
        meta = {k: v for k, v in item.items() if k not in {"directory", "cache_group", "evaluation_input"}}
        meta.update(case=truth_meta.get("case"), control_seed=truth_meta.get("seed"),
                    assessment="primary_grid" if primary(meta) else "other_grid_scale_diagnostic" if meta["sampler"] == "grid" else "own_center_graph_diagnostic")
        record = dict(metadata=meta, metrics=sample_metrics(rows, prediction, truth, meta, states))
        records.append(record)
        if item["sampler"] == "grid" or (item["scale_px"] == 48 and item["kind"] == "measurement"):
            labels = truth.get("domain_labels" if item["kind"] == "synthetic" else "region_instances")
            reference = metrics20._comparison_reference(rows, labels, truth.get("evaluation_valid"), kind=item["kind"], regime=item["regime"])
            evaluated = metrics20._evaluated_mask(rows, labels, truth.get("evaluation_valid"), kind=item["kind"], regime=item["regime"])
            data[identity] = dict(rows=rows, prediction=prediction, record=record, states=states, reference=reference, evaluated=evaluated, truth=truth, source_entry=item)
            if primary(meta):
                record["cross_boundary_endpoints"] = cross_boundary_endpoints(rows, prediction, reference, evaluated)
        if len(records) % 1000 == 0:
            print(f"evaluated {len(records)}/{len(index)}", flush=True)
    map_centers(root, frozen, groups, data, records, budget)
    by_case = {(meta["seed"], meta["case"]): sid for sid, (meta, _) in controls.items()}
    ablations, invariances = [], {}
    for entry in budget.checked(data.values()):
        meta = entry["record"]["metadata"]
        if meta["sampler"] != "grid" or meta["case"] not in ANNOTATION_PAIRS:
            continue
        base_sid = by_case[meta["control_seed"], ANNOTATION_PAIRS[meta["case"]]]
        base = data[meta["run_id"], meta["scale_px"], "grid", base_sid, meta["partition"]]
        result = metrics20.ablation_invariance([r["element_id"] for r in base["rows"]], base["prediction"]["before"], base["prediction"]["after"],
            [r["element_id"] for r in entry["rows"]], entry["prediction"]["before"], entry["prediction"]["after"])
        invariances[key(meta)] = result["passed"]
        ablations.append(dict(metadata=meta, baseline_sample_id=base_sid, invariance=result,
                              interpretation="Only annotation positions/availability changed; grid invariance is not image-jitter robustness"))
    for record in records:
        record["stage_criteria"] = {stage: stage_criteria(record, stage, invariances.get(key(record["metadata"]))) for stage in ("before", "after")}
        record["metrics"]["criteria"] = record["stage_criteria"]["after"]
    return frozen, index, records, data, ablations


def evaluate(root, controls_dir=None, measurement_dir=None, out=None):
    root = Path(root).resolve()
    controls_dir = Path(controls_dir or root / "controls/evaluation")
    measurement_dir = Path(measurement_dir or ".scratch/unsupervised-input/evaluation")
    out = Path(out or root / "evaluation")
    if out.exists():
        raise FileExistsError(out)
    with reporting_stage(root, "evaluation") as budget:
        frozen, index, records, data, ablations = load_records(root, controls_dir, measurement_dir, budget)
        grouped = defaultdict(list)
        for record in records:
            grouped[key(record["metadata"], AGGREGATE_KEYS)].append(record)
        aggregates = []
        for identity, values in budget.checked(grouped.items()):
            meta = dict(zip(AGGREGATE_KEYS, identity))
            result = metrics20.aggregate_samples([r["metrics"] for r in values])
            if meta["sampler"] != "grid":
                result["criteria"] = metrics20._check_result({}, applicable=False)
            stages = {}
            for stage in ("before", "after"):
                if meta["sampler"] != "grid":
                    stages[stage] = metrics20._check_result({}, applicable=False)
                elif meta["kind"] == "measurement":
                    stages[stage] = metrics20.ttmapp_criteria(dict(result, after=result[stage]))
                else:
                    applicable = [r["stage_criteria"][stage] for r in values if r["stage_criteria"][stage]["applicable"]]
                    stages[stage] = metrics20._check_result({f"sample_{i}": r["passed"] for i, r in enumerate(applicable)}, applicable=bool(applicable))
            aggregates.append(dict(metadata=meta, metrics=result, stage_criteria=stages))
        stability = stability_records(data, budget)
        with tempfile.TemporaryDirectory(prefix=".adapted26-comparisons-", dir=root) as tmp:
            path = Path(tmp) / "comparisons.jsonl"
            comparisons, benefits, comparison_count = paired_comparisons(data, path, budget)
            decisions = verdicts(records, stability, benefits)
            metrics20.write_summary(records, out, extras=dict(aggregates=aggregates, stability=stability, ablations=ablations,
                comparisons=comparisons, benefits=benefits, verdicts=decisions,
                formal_scope="grid48; before positive7cases+TTMAPP; after full20; deterministic frozen baseline paired with each available seed"))
            shutil.copyfile(path, out / "comparisons.jsonl")
        for name, values in (("aggregates", aggregates), ("stability", stability), ("ablations", ablations),
                             ("pooled-comparisons", comparisons), ("benefits", benefits), ("verdicts", decisions)):
            write_json(out / (name + ".json"), values)
            metrics20._flat_csv(out / (name + ".csv"), values)
            budget.check()
        evidence = dict(schema="stmdomains-pretrained-ssl26-evaluation-v1", frozen_manifest_sha256=file_hash(root / "frozen-predictions.json"),
            controls_manifest_sha256=file_hash(controls_dir / "manifest.json"), measurement_manifest_sha256=file_hash(measurement_dir / "manifest.json"),
            prediction_entries=len(index), evaluated_records=len(records), primary_sample_comparisons=comparison_count,
            control_seeds=list(CONTROL_SEEDS), controls_count=93, before_positive_cases=sorted(POSITIVE_CASES), after_required_cases=sorted(REQUIRED_CASES),
            verified_prediction_files=len(frozen["files"]), verified_external_files=len(frozen.get("external_files", {})),
            primary="Adapted EMA teacher at fixed step1000; mean384; grid48; no winning seed/readout selection",
            complete_detector_limitation="Frozen20 gate/connectivity caps TTMAPP at0/174 transfer and4/782 transduction regardless of representation",
            partial_reference_policy="Known positive interiors only; missing regions/null pairs are not negative evidence or zero errors",
            code_sha256=file_hash(Path(__file__)), resources=budget.measurements())
        write_json(out / "evaluation-evidence.json", evidence)
        return evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--controls-evaluation", type=Path)
    parser.add_argument("--measurement-evaluation", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    result = evaluate(args.output, args.controls_evaluation, args.measurement_evaluation, args.out)
    print(json.dumps({name: result[name] for name in ("prediction_entries", "evaluated_records", "primary_sample_comparisons")}))


if __name__ == "__main__":
    main()
