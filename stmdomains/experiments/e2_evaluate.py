"""Post-freeze E2 evaluation and offline viewer payloads, with fixed denominators."""
from __future__ import annotations

from collections import defaultdict
import csv
import gzip
import json
from pathlib import Path

import numpy as np

from .bundle import file_hash, write_json
from .e1_run import compact, context, make_samples, write_js
from .e2_metrics import edge_reference, pair_summary
from .e2_pipeline import SHUFFLE_SEEDS, SPACES, STAGES
from .training.evaluate import _truth_bundle, aggregate_samples, evaluate_sample

REPO = Path(__file__).resolve().parents[2]
CONDITIONS = ("actual",) + tuple(f"shuffle-{s}" for s in SHUFFLE_SEEDS)


def small_metric(metric):
    return {k: v for k, v in metric.items() if k not in ("roc", "pr")}


def metric_csv(metadata, metric):
    result = dict(metadata, **metric["counts"], boundary_prevalence=metric["boundary_prevalence"],
                  roc_auc=metric["roc_auc"], average_precision=metric["average_precision"],
                  unavailable_reason=metric["unavailable_reason"])
    for label in ("same", "different"):
        for key in ("min", "q05", "q25", "median", "q75", "q95", "max"):
            result[f"{label}_{key}"] = (metric["quantiles"][label] or {}).get(key)
    return result


def evaluate(bank, output, index, frozen_files, check_budget=lambda: None):
    for name, expected in frozen_files.items():
        if file_hash(output / name) != expected:
            raise ValueError(f"Frozen E2 input changed: {name}")
    # No references were accessed by generate/FeatureBank. Oracle is not part of E2.
    truths, truth_hashes = {}, {}
    for field, location in (("controls", REPO / ".scratch/training-20/controls/evaluation"),
                            ("references", REPO / ".scratch/unsupervised-input/evaluation")):
        manifest, truths[field] = _truth_bundle(location, field)
        truth_hashes[str(location / "manifest.json")] = file_hash(location / "manifest.json")
        truth_hashes.update({str(location / record["file"]): record["sha256"] for record in manifest[field]})
    write_json(output / "truth-audit.json", dict(files=truth_hashes))
    samples = make_samples(bank.inputs, truths["controls"], truths["references"], output)
    gallery_index, domain_summaries = [], []
    pair_batch, domain_batch = defaultdict(list), defaultdict(list)
    final_counts = defaultdict(int)
    last_batch = None
    current_meta = None
    with gzip.open(output / "edge-summary.jsonl.gz", "wt") as edge_summary, \
            gzip.open(output / "edge-sample-metrics.jsonl.gz", "wt") as edge_sample, \
            gzip.open(output / "domain-sample-metrics.jsonl.gz", "wt") as domain_stream, \
            (output / "edge-metrics.csv").open("w", newline="") as csv_stream:
        writer = None

        def flush():
            nonlocal writer
            if not pair_batch:
                return
            for (case, condition, space, support), pieces in pair_batch.items():
                distance = np.concatenate([p[0] for p in pieces])
                same = np.concatenate([p[1] for p in pieces])
                eligible = np.concatenate([p[2] for p in pieces])
                metric = pair_summary(distance, same, eligible,
                                      max_curve_points=512 if condition == "actual" else 2)
                if condition != "actual":
                    metric["roc"] = metric["pr"] = None
                metadata = dict(current_meta, case=case, condition=condition, space=space,
                                support=support, sample_count=len(pieces))
                edge_summary.write(compact(dict(metadata, summary=metric)) + "\n")
                row = metric_csv(metadata, metric)
                if writer is None:
                    writer = csv.DictWriter(csv_stream, fieldnames=list(row))
                    writer.writeheader()
                writer.writerow(row)
                final_counts["edge_aggregates"] += 1
            for (case, condition, method, stage), pieces in domain_batch.items():
                domain_summaries.append(dict(current_meta, case=case, condition=condition,
                                             partition=method, variant=stage,
                                             metrics=aggregate_samples(pieces)))
            pair_batch.clear()
            domain_batch.clear()

        ordered = sorted(index, key=lambda e: (e["run_id"], e["sampler"], e["sample_id"]))
        for number, entry in enumerate(ordered):
            check_budget()
            group_key = (entry["run_id"], entry["sampler"])
            if last_batch is not None and group_key != last_batch:
                flush()
            current_meta = {key: entry[key] for key in ("run_id", "regime", "family", "seed", "sampler")}
            last_batch = group_key
            rows, ids, desc, scope, gates, hard, minimum = context(bank.inputs, entry)
            with np.load(output / entry["prediction"], allow_pickle=False) as archive:
                data = {key: archive[key] for key in archive.files}
            edges = data["edges"]
            meta, truth = truths["controls" if entry["kind"] == "synthetic" else "references"].get(entry["sample_id"], ({}, {}))
            case = meta.get("case") if entry["kind"] == "synthetic" else "measurement"
            ref = edge_reference(rows, edges, truth, entry["kind"], entry["regime"])
            own = data["valid"][edges].all(axis=1)
            common = data["common"][edges].all(axis=1)
            summaries_for_viewer = {}
            for condition_index, condition in enumerate(CONDITIONS):
                for space_index, space in enumerate(SPACES):
                    distance = data["distances"][condition_index, space_index]
                    for support, feature_mask in (("own", own), ("common", common)):
                        eligible = ref["valid"] & feature_mask
                        metric = pair_summary(distance, ref["same"], eligible, max_curve_points=2)
                        pair_batch[(case, condition, space, support)].append((distance, ref["same"], eligible))
                        edge_sample.write(compact(dict(current_meta, sample_id=entry["sample_id"],
                            case=case, condition=condition, space=space, support=support,
                            reference_counts=ref["counts"], summary=small_metric(metric))) + "\n")
                        final_counts["edge_sample_evaluations"] += 1
                        if condition_index < 2 and support == "common":
                            summaries_for_viewer[(condition_index, space)] = dict(
                                space=space, n_same=metric["counts"]["same_pairs"],
                                n_different=metric["counts"]["different_pairs"], roc_auc=metric["roc_auc"],
                                average_precision=metric["average_precision"],
                                boundary_prevalence=metric["boundary_prevalence"],
                                unavailable_reason=metric["unavailable_reason"], support="common")
            labels = truth.get("domain_labels" if entry["kind"] == "synthetic" else "region_instances")
            for which, prefix in enumerate(("actual", "shuffle")):
                condition = CONDITIONS[which]
                for method in ("fh4", "mws"):
                    before = data[f"{prefix}_{method}_before"]
                    variants = {}
                    for stage in STAGES:
                        after = data[f"{prefix}_{method}_{stage}"]
                        states = np.where(~scope, "not_evaluated", np.where(~desc["available"], "insufficient_data",
                                          np.where(after > 0, "ordered_untyped", "ambiguous")))
                        metric = evaluate_sample(rows, labels, before, after, edges,
                            evaluation_valid=truth.get("evaluation_valid"), orientation_labels=truth.get("orientation_groups"),
                            truth_raster=truth.get("domain_labels") if entry["sampler"] == "grid" else None,
                            pixel_spacing_xy=entry["pixel_spacing_xy"], regime=entry["regime"], kind=entry["kind"],
                            case=case if entry["kind"] == "synthetic" else None, states=states)
                        domain_batch[(case, condition, method, stage)].append(metric)
                        domain_stream.write(compact(dict(current_meta, sample_id=entry["sample_id"], case=case,
                            condition=condition, partition=method, variant=stage, metrics=metric)) + "\n")
                        final_counts["domain_sample_evaluations"] += 1
                        value = metric["after"]
                        before_min = data[f"{prefix}_{method}_{stage[:-1]}0"]
                        variants[stage] = dict(labels=after, coverage=value["positive_reference_coverage"],
                            merge_rate=value["pairs"]["merge_rate"], split_rate=value["pairs"]["split_rate"],
                            assigned=value["assigned_full_support_elements"], full_support=metric["full_support_elements"],
                            domain_count=value["domain_count_in_scope"], minimum_enabled=stage.endswith("1"),
                            minimum_failed=(before_min > 0) & (after == 0),
                            acf_enabled=stage.startswith("A"), spectral_enabled=stage.startswith("A"))
                    ident = f"{entry['id']}-{prefix}-{method}"
                    relative = f"runs/{ident}.js"
                    failures = dict(gates["failures"], feature_unavailable=scope & desc["available"] & ~data["valid"])
                    payload = dict(id=ident, before=before, scope=scope, hard=hard, acf=desc["acf_score"],
                        ratio=desc["second_direction_ratio"], energy=desc["energy"],
                        acf_threshold=bank.inputs.threshold, gate_failures=failures, min_size=minimum,
                        variants=variants, edge_summary=[summaries_for_viewer[(which, space)] for space in SPACES],
                        condition=condition, common_nodes=int(data["common"].sum()),
                        own_nodes=int((scope & desc["available"] & data["valid"]).sum()))
                    write_js(output / relative, "E1_RUN_DATA", payload)
                    gallery_index.append(dict(current_meta, id=ident, sample_id=entry["sample_id"],
                                              condition=condition, partition=method, path=relative))
            if number % 150 == 0:
                print(f"E2 evaluate + gallery {number + 1}/{len(index)}", flush=True)
        flush()
    with gzip.open(output / "domain-summary.json.gz", "wt") as stream:
        stream.write(compact(dict(records=domain_summaries)))
    write_js(output / "gallery-data.js", "E1_DATA", dict(samples=samples, runs=gallery_index))
    from .e2_gallery import write_gallery
    write_gallery(output / "index.html")
    write_json(output / "final-input-audit.json", bank.audit())
    return dict(final_counts, gallery_runs=len(gallery_index), samples=len(samples), domain_aggregates=len(domain_summaries))
