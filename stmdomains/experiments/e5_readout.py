"""Postprocess completed E5 results, preserving contrasts and denominators."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import gzip
import json
from pathlib import Path
import sys
import time

import numpy as np

from .bundle import file_hash, write_json
from .e5_catalog import CONDITIONS


MODEL = ("regime", "family", "sampler", "case", "contrast", "condition", "context")
QUALITY = (*MODEL, "partition", "variant")
IDENTITY = ("run_id", "seed")
BASELINE = {c["id"]: c["baseline_id"] for c in CONDITIONS}
GEOMETRY = ("planned_elements", "scope_elements", "full_support_elements",
            "evaluated_elements", "positive_reference_elements", "known_zero_elements")
GRAPH_RATES = ("cut_precision", "cut_recall", "cut_f1", "assigned_only_cut_recall",
               "assigned_edge_fraction", "false_cut_rate_assigned_same", "merge_rate_assigned_different")


def ratio(a, b):
    return float(a / b) if b else None


def spread(values):
    finite = [float(v) for v in values if v is not None and np.isfinite(v)]
    return dict(n=len(finite), median=float(np.median(finite)) if finite else None,
                min=min(finite) if finite else None, max=max(finite) if finite else None)


def grouped(records, keys):
    groups = defaultdict(list)
    for row in records:
        groups[tuple(row[k] for k in keys)].append(row)
    return groups


def flattened(value, prefix=""):
    result = {}
    for key, item in value.items():
        name = f"{prefix}.{key}" if prefix else key
        if isinstance(item, dict):
            result.update(flattened(item, name))
        elif isinstance(item, (tuple, list)):
            result[name] = json.dumps(item, ensure_ascii=False, separators=(",", ":"))
        else:
            result[name] = item
    return result


def write_csv(path, records):
    rows = [flattened(row) for row in records]
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def seed_summary(rows, keys, metrics):
    result = []
    for group, records in grouped(rows, keys).items():
        seeds = [r["seed"] for r in records]
        if len(set(seeds)) != len(seeds):
            raise ValueError(f"Repeated seed in E5 summary: {group}")
        result.append(dict(zip(keys, group), seeds=seeds, n_runs=len(records),
            n_model_seeds=sum(seed is not None for seed in seeds),
            metrics={name: spread([r[name] for r in records]) for name in metrics}))
    return result


def domain_rows(source):
    """Rates already pool frame-local counts; do not average frame percentages."""
    rows = []
    for row in source:
        metrics = row["metrics"]
        item = {key: row[key] for key in (*QUALITY, *IDENTITY)}
        item.update(n_samples=metrics["sample_count"], **{k: metrics[k] for k in GEOMETRY},
                    unavailable_elements=metrics["unavailable_elements"])
        for stage in ("before", "after"):
            values = metrics[stage]
            for name in ("positive_reference_coverage", "assigned_full_support_elements",
                         "full_support_assignment_fraction", "false_known_zero_assignments",
                         "false_known_zero_fraction", "domain_count_sum", "assigned_without_support"):
                item[f"{stage}_{name}"] = values[name]
            for name in ("reference_elements", "assigned_elements", "same_reference_pairs",
                         "different_reference_pairs", "merged_pairs", "split_pairs", "merge_rate", "split_rate"):
                item[f"{stage}_{name}"] = values["pairs"][name]
            for name in ("f1", "precision", "recall", "predicted_points", "truth_points",
                         "matched_prediction_points", "matched_truth_points", "positive_contact_sample_count"):
                item[f"{stage}_raster_boundary_{name}"] = values["boundary"].get(name)
        rows.append(item)
    return rows


def paired_deltas(rows, keys, fields, denominator_fields):
    """Only common comparisons claim a paired effect, within the same seed."""
    index = {}
    for row in rows:
        key = tuple(row[k] for k in (*keys, *IDENTITY))
        if key in index:
            raise ValueError("Repeated per-seed E5 quality row")
        index[key] = row
    result = []
    for row in rows:
        baseline_id = BASELINE[row["condition"]]
        baseline_key = tuple(baseline_id if k == "condition" else row[k]
                             for k in (*keys, *IDENTITY))
        baseline = index.get(baseline_key)
        if baseline is None:
            raise ValueError(f"Missing same-contrast baseline: {baseline_key}")
        common = row["context"] == "common"
        if common and any(row[k] != baseline[k] for k in denominator_fields):
            raise ValueError("Common E5 comparison changed its reference/geometry denominator")
        item = {k: row[k] for k in (*keys, *IDENTITY)}
        item.update(baseline_id=baseline_id,
                    unavailable_reason=None if common else "own_support_is_not_a_paired_effect")
        for name in fields:
            a, b = row[name], baseline[name]
            item[f"delta_{name}"] = float(a - b) if common and a is not None and b is not None else None
        result.append(item)
    return result


def graph_rows(path):
    """Pool graph confusion counts within samples, never compare across frames."""
    groups = {}
    with gzip.open(path, "rt") as stream:
        for line in stream:
            row = json.loads(line)
            key = tuple(row[k] for k in (*QUALITY, *IDENTITY))
            item = groups.setdefault(key, dict(samples=set(), counts=Counter(),
                                               frames={k: [] for k in GRAPH_RATES}))
            if row["sample_id"] in item["samples"]:
                raise ValueError("Repeated sample in E5 graph summary")
            item["samples"].add(row["sample_id"])
            graph = row["locality"]["graph_cuts"]
            item["counts"].update(graph["counts"])
            for name in GRAPH_RATES:
                item["frames"][name].append(graph[name])
    rows = []
    for key, group in groups.items():
        c = group["counts"]
        rows.append(dict(zip((*QUALITY, *IDENTITY), key), n_samples=len(group["samples"]),
            **dict(c), cut_precision=ratio(c["correct_cut_edges"], c["predicted_cut_edges"]),
            cut_recall=ratio(c["correct_cut_edges"], c["different_reference_edges"]),
            cut_f1=ratio(2 * c["correct_cut_edges"], c["predicted_cut_edges"] + c["different_reference_edges"])
                if c["different_reference_edges"] else None,
            assigned_only_cut_recall=ratio(c["correct_cut_edges"], c["assigned_different_edges"]),
            assigned_edge_fraction=ratio(c["assigned_reference_edges"], c["reference_edges"]),
            false_cut_rate_assigned_same=ratio(c["false_cut_edges"], c["assigned_same_edges"]),
            merge_rate_assigned_different=ratio(c["merged_edges"], c["assigned_different_edges"]),
            frame_distributions={name: spread(values) for name, values in group["frames"].items()}))
    return rows


def support_rows(path):
    groups = {}
    with path.open() as stream:
        for line in stream:
            row = json.loads(line)
            key = tuple(row[k] for k in (*MODEL, *IDENTITY))
            item = groups.setdefault(key, dict(samples=set(), counts=Counter()))
            if row["sample_id"] in item["samples"]:
                raise ValueError("Repeated sample in E5 support summary")
            item["samples"].add(row["sample_id"])
            item["counts"].update(row["counts"])
    return [dict(zip((*MODEL, *IDENTITY), key), n_samples=len(value["samples"]), **dict(value["counts"]))
            for key, value in groups.items()]


def summarize(output_root):
    started = time.monotonic()
    output = Path(output_root).resolve()
    manifest = json.loads((output / "manifest.json").read_text())
    if manifest["status"] != "completed":
        raise ValueError("E5 must be completed before postprocessing")
    inputs = ("manifest.json", "prediction-freeze.json", "domain-summary.json.gz",
              "metrics.jsonl.gz", "support-summary.jsonl")
    hashes = {name: file_hash(output / name) for name in inputs}
    frozen = json.loads((output / "prediction-freeze.json").read_text())["files"]
    for name, value in hashes.items():
        if name in frozen and frozen[name] != value:
            raise ValueError(f"Frozen E5 input changed: {name}")
    with gzip.open(output / "domain-summary.json.gz", "rt") as stream:
        source = json.load(stream)["records"]
    domains = domain_rows(source)
    graphs = graph_rows(output / "metrics.jsonl.gz")
    supports = support_rows(output / "support-summary.jsonl")
    quality_fields = tuple(k for k in domains[0] if k not in (*QUALITY, *IDENTITY)) if domains else ()
    graph_fields = tuple(k for k in graphs[0] if k not in (*QUALITY, *IDENTITY, "frame_distributions")) if graphs else ()
    support_fields = tuple(k for k in supports[0] if k not in (*MODEL, *IDENTITY)) if supports else ()
    delta_fields = tuple(k for k in quality_fields if k.endswith(("coverage", "merge_rate", "split_rate", "fraction", "boundary_f1")))
    deltas = paired_deltas(domains, QUALITY, delta_fields, (*GEOMETRY, "n_samples"))
    graph_deltas = paired_deltas(graphs, QUALITY, GRAPH_RATES,
        ("n_samples", "reference_edges", "same_reference_edges", "different_reference_edges", "positive_reference_nodes"))
    exports = {
        "domain-seeds": domains, "domain-summary": seed_summary(domains, QUALITY, quality_fields),
        "delta-seeds": deltas, "delta-summary": seed_summary(deltas, QUALITY, tuple("delta_" + k for k in delta_fields)),
        "graph-seeds": graphs, "graph-summary": seed_summary(graphs, QUALITY, graph_fields),
        "graph-delta-seeds": graph_deltas,
        "graph-delta-summary": seed_summary(graph_deltas, QUALITY, tuple("delta_" + k for k in GRAPH_RATES)),
        "support-seeds": supports, "support-summary": seed_summary(supports, MODEL, support_fields),
    }
    for name, records in exports.items():
        write_csv(output / f"readout-{name}.csv", records)
    if any(file_hash(output / name) != digest for name, digest in hashes.items()):
        raise ValueError("E5 input changed during postprocessing")
    files = {f"readout-{name}.csv": file_hash(output / f"readout-{name}.csv") for name in exports}
    result = dict(schema="stmdomains-e5-readout-v1", output=str(output), run=manifest,
        rows={name: len(records) for name, records in exports.items()}, input_sha256=hashes,
        code_sha256={str(Path(__file__).resolve()): file_hash(Path(__file__)),
                     "e5_catalog.py": file_hash(Path(__file__).with_name("e5_catalog.py"))},
        files=files, aggregation=dict(
            quality="Within-sample counts summed per case/run; median and observed range across model seeds, never pooling seeds.",
            graph="After-stage graph cut counts pooled within frames. Recall retains refused different-instance edges. Frame distributions retain finite counts separately.",
            boundary="Raster boundary only from existing aggregate_samples; graph endpoint cuts are not physical pixel contours. Real partial-interior boundary stays null.",
            support="Geometry repeated per model is never summed across families/seeds. Feature validity remains separate from geometry denominators.",
            contrasts="Map, scale and centering remain separate, each with its own common support and baseline. Own support is descriptive and has no paired-effect delta.",
            deltas="Common differences paired within the same seed/contrast/context/partition/stage. Reference geometry counts must match baseline; assigned-pair denominators may differ.",
            missing="Null is unavailable, not zero or success; seed and frame ranges are descriptive, not confidence intervals. FFT seed null is one deterministic run."))
    write_json(output / "readout.json", result)
    write_json(output / "readout-manifest.json", dict(
        schema="stmdomains-e5-postprocessing-v1", status="completed",
        created_utc=datetime.now(timezone.utc).isoformat(), python=sys.executable,
        numpy=np.__version__, wall_seconds=time.monotonic() - started,
        input_sha256=hashes, code_sha256=result["code_sha256"],
        files=dict(files, **{"readout.json": file_hash(output / "readout.json")}),
        encoder_inference=False, encoder_training=False, adapter_refit=False,
        prediction_changes=False))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    result = summarize(parser.parse_args().output)
    print(json.dumps(dict(output=result["output"], rows=result["rows"])))
