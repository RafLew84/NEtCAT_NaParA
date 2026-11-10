"""Frozen E1 gate/oracle diagnosis. Uses existing pilots, never trains a model."""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import gzip
import itertools
import json
from pathlib import Path
import resource
import shutil
import sys
import time

import numpy as np
from PIL import Image
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

from .bundle import file_hash, load_sample, write_json
from .e1_inputs import Inputs, prepare_descriptors
from .e1_mechanics import apply_variant, gate_masks, oracle_proposals, truth_at_rows
from .training.evaluate import _truth_bundle, aggregate_samples, evaluate_sample
from .training.predict import label_numbers

REPO = Path(__file__).resolve().parents[2]
PROTOCOL = REPO / "docs/stmdomains/ml-ae-rvae-e1-protocol.md"
VARIANTS = list(itertools.product((False, True), repeat=3))


def clean(value):
    if isinstance(value, np.ndarray):
        return clean(value.tolist())
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    if isinstance(value, np.generic):
        return clean(value.item())
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def compact(value):
    return json.dumps(clean(value), ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def write_js(path, variable, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"window.{variable}=" + compact(value) + ";\n")


def budget():
    if time.process_time() > 45 * 60:
        raise RuntimeError("E1 CPU budget exceeded (45 minutes)")
    if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss > 8 * 1024**2:
        raise RuntimeError("E1 RSS budget exceeded (8 GiB)")


def context(inputs, entry):
    rows = inputs.rows(entry)
    ids = [row["element_id"] for row in rows]
    desc = inputs.descriptor(entry)
    scope = np.asarray([entry["kind"] != "measurement" or entry["regime"] != "transfer"
                        or row.get("transfer_split") == "test" for row in rows], bool)
    gates = gate_masks(desc["available"], desc["valid"], desc["acf_score"],
                       desc["second_direction_ratio"], desc["energy"], inputs.threshold)
    hard = gates["hard"] & scope
    minimum = 4 if entry["sampler"] == "grid" else 8
    return rows, ids, desc, scope, gates, hard, minimum


def generate(inputs, output):
    """No reference access here; reconstruct all eight ablations then freeze."""
    entries = sorted(inputs.entries, key=lambda e: (e["run_id"], e["sampler"], e["partition"], e["sample_id"]))
    index, files = [], {}
    for number, entry in enumerate(entries):
        rows, ids, desc, scope, gates, hard, minimum = context(inputs, entry)
        source = inputs.load_npz(f"{entry['directory']}/{entry['evaluation_input']}")
        heldout = entry["kind"] == "measurement" and entry["regime"] == "transfer"
        if heldout and entry["evaluation_input"] != "heldout-metrics-input.npz":
            raise ValueError("Transfer must use the original heldout graph")
        name = "heldout-result.json.gz" if heldout else "result.json.gz"
        payload = inputs.read_json(f"{entry['directory']}/{name}")
        extension = payload["extensions"]["training_v1"]
        if [p["element_id"] for p in extension["proposals"]] != ids:
            raise ValueError("Proposal/row order mismatch")
        proposals = [p["component_id"] for p in extension["proposals"]]
        if not np.array_equal(label_numbers(proposals), source["before"]):
            raise ValueError("Before partition did not reproduce")
        if not np.array_equal(desc["available"], source["available"]):
            raise ValueError("Support changed")
        arrays = {"before": source["before"], "edges": source["edges"]}
        for acf, spectral, size in VARIANTS:
            key = f"A{int(acf)}S{int(spectral)}M{int(size)}"
            mask = hard & (gates["acf"] if acf else True) & (gates["spectral"] if spectral else True)
            arrays[key] = apply_variant(ids, source["edges"], proposals, mask,
                                        minimum if size else 1)["after"]
        if not np.array_equal(arrays["A1S1M1"], source["after"]):
            raise ValueError(f"Baseline after partition did not reproduce: {entry}")
        ident = f"run-{number:05d}"
        path = output / "predictions" / f"{ident}.npz"
        path.parent.mkdir(exist_ok=True)
        np.savez_compressed(path, **arrays)
        relative = str(path.relative_to(output))
        files[relative] = file_hash(path)
        index.append(dict(entry, id=ident, prediction=relative))
        if number % 250 == 0:
            print(f"gate predictions {number + 1}/{len(entries)}", flush=True)
            budget()
    write_json(output / "prediction-index.json", index)
    files["prediction-index.json"] = file_hash(output / "prediction-index.json")
    write_json(output / "gate-freeze.json", dict(
        schema="stmdomains-e1-gate-freeze-v1", files=files, baseline_exact=len(index),
        protocol_sha256=file_hash(PROTOCOL), created_utc=datetime.now(timezone.utc).isoformat(),
        truth_opened_for_this_run=False, historical_data_already_known=True))
    inputs.save_audit()
    return index, files


def same_partition(a, b):
    """Compare assigned partitions independently of arbitrary numeric IDs."""
    if not np.array_equal(a > 0, b > 0):
        return False
    groups = lambda x: {tuple(np.flatnonzero(x == k)) for k in np.unique(x) if k > 0}
    return groups(a) == groups(b)


def readiness(truth, edges, hard, available, minimum, oracle_after):
    """Independent connected-component oracle ceiling on the unchanged graph."""
    n = len(truth)
    positive = hard & (truth > 0)
    u, v = edges.T if len(edges) else (np.array([], int), np.array([], int))
    inner = positive[u] & positive[v] & (truth[u] == truth[v])
    graph = coo_matrix((np.ones(int(inner.sum())), (u[inner], v[inner])), shape=(n, n))
    _, components = connected_components(graph, directed=False)
    expected = np.where(positive, components + 1, 0)
    if not same_partition(expected, oracle_after):
        raise ValueError("Ideal relations+mask disagree with induced truth graph")
    regions = []
    for ident in np.unique(truth[truth > 0]):
        selected = positive & (truth == ident)
        sizes = np.unique(components[selected], return_counts=True)[1]
        regions.append(dict(truth_id=int(ident), supported=int((available & (truth == ident)).sum()),
                            hard_valid=int(selected.sum()), components=len(sizes), sizes=sizes.tolist(),
                            lost_to_minimum=int(sizes[sizes < minimum].sum())))
    return dict(regions=regions, positive_edges=int(inner.sum()),
                between_positive_edges=int(((truth[u] > 0) & (truth[v] > 0) & (truth[u] != truth[v])).sum()),
                matches_induced_truth_graph=True)


def make_samples(inputs, control_truth, measurement_truth, output):
    groups = {g["group_id"]: g for g in inputs.groups.values()} if isinstance(inputs.groups, dict) else {
        g["group_id"]: g for g in inputs.groups}
    samples = {}
    for group in groups.values():
        sample = group["record"]["sample_id"]
        if sample in samples:
            continue
        record, arrays = inputs.sample(group)
        source = control_truth if record["kind"] == "synthetic" else measurement_truth
        meta, truth = source.get(sample, ({}, {}))
        lo, hi = np.percentile(arrays["image"][arrays["measured"]], [2, 98])
        gray = np.uint8(255 * np.clip((arrays["image"] - lo) / max(hi - lo, 1e-12), 0, 1))
        image_path = output / "images" / f"{sample}.png"
        image_path.parent.mkdir(exist_ok=True)
        Image.fromarray(gray).save(image_path)
        item = dict(id=sample, kind=record["kind"], case=meta.get("case"), frame=record.get("frame_number"),
                    control_seed=meta.get("seed"), image=str(image_path.relative_to(output)),
                    width=gray.shape[1], height=gray.shape[0], rows={}, display_limits=[float(lo), float(hi)])
        for sampler in ("grid", "centers"):
            rows = inputs.rows(dict(cache_group=f"{sample}/{sampler}/s48"))
            raster = truth.get("domain_labels", truth.get("region_instances"))
            labels = truth_at_rows(rows, raster) if raster is not None else np.zeros(len(rows), int)
            item["rows"][sampler] = [dict(xy=row["raw_edge_xy"], available=row["available"],
                                           element_id=row["element_id"], truth=int(label))
                                      for row, label in zip(rows, labels)]
        samples[sample] = item
    return list(sorted(samples.values(), key=lambda s: (s["kind"] != "measurement", s["id"])))


def evaluate(inputs, output, index, files):
    """Truth is first opened here, after all program ablations were frozen."""
    locations = {"controls": REPO / ".scratch/training-20/controls/evaluation",
                 "references": REPO / ".scratch/unsupervised-input/evaluation"}
    truths, truth_hashes = {}, {}
    for field, location in locations.items():
        manifest, truths[field] = _truth_bundle(location, field)
        truth_hashes[str(location / "manifest.json")] = file_hash(location / "manifest.json")
        for record in manifest[field]:
            truth_hashes[str(location / record["file"])] = record["sha256"]
    write_json(output / "truth-audit.json", dict(files=truth_hashes, oracle_is_privileged=True))
    samples = make_samples(inputs, truths["controls"], truths["references"], output)
    gallery_index, summaries, counts = [], [], defaultdict(int)
    batch, last_batch = defaultdict(list), None

    def flush():
        for (run_id, sampler, solver, case, variant), records in batch.items():
            summaries.append(dict(run_id=run_id, sampler=sampler, partition=solver,
                                  case=case, variant=variant, metrics=aggregate_samples(records)))
        batch.clear()

    with gzip.open(output / "sample-metrics.jsonl.gz", "wt") as stream, \
            gzip.open(output / "oracle-readiness.jsonl.gz", "wt") as ceilings:
        for number, entry in enumerate(index):
            budget()
            rows, ids, desc, scope, gates, hard, minimum = context(inputs, entry)
            path = output / entry["prediction"]
            if file_hash(path) != files[entry["prediction"]]:
                raise ValueError("Frozen gate predictions changed")
            with np.load(path, allow_pickle=False) as z:
                arrays = {k: z[k] for k in z.files}
            before, edges = arrays.pop("before"), arrays.pop("edges")
            source = truths["controls" if entry["kind"] == "synthetic" else "references"]
            meta, truth = source.get(entry["sample_id"], ({}, {}))
            label_raster = truth.get("domain_labels" if entry["kind"] == "synthetic" else "region_instances")
            case = meta.get("case") if entry["kind"] == "synthetic" else "measurement"
            entry_batch = (entry["run_id"], entry["sampler"], entry["partition"])
            if last_batch is not None and last_batch != entry_batch:
                flush()
            last_batch = entry_batch
            original = [str(int(v)) if v > 0 else None for v in before]
            predictions = dict(arrays)
            oracle_before = None
            if entry["kind"] == "synthetic":
                domain_truth = truth_at_rows(rows, truth["domain_labels"])
                ideal = oracle_proposals(ids, edges, domain_truth, before > 0, entry["partition"])
                oracle_before = label_numbers(ideal)
                for relation, proposals in (("P", original), ("I", ideal)):
                    for mask_kind in ("P", "I"):
                        mask = hard & ((gates["acf"] & gates["spectral"]) if mask_kind == "P" else domain_truth > 0)
                        for size in (False, True):
                            key = f"R{relation}_M{mask_kind}_M{int(size)}"
                            predictions[key] = apply_variant(ids, edges, proposals, mask,
                                                              minimum if size else 1)["after"]
                ceiling = readiness(domain_truth, edges, hard & (before > 0),
                                    desc["available"], minimum, predictions["RI_MI_M0"])
                ceilings.write(compact(dict(id=entry["id"], sample_id=entry["sample_id"],
                                            run_id=entry["run_id"], sampler=entry["sampler"],
                                            partition=entry["partition"], case=case, **ceiling)) + "\n")
                counts["oracle_graph_checks"] += 1
                if not same_partition(predictions["RP_MP_M1"], arrays["A1S1M1"]):
                    raise ValueError("Program/program oracle cell changed baseline")
                oracle_path = output / "oracle" / f"{entry['id']}.npz"
                oracle_path.parent.mkdir(exist_ok=True)
                np.savez_compressed(oracle_path, before=oracle_before,
                                    **{k: v for k, v in predictions.items() if k.startswith("R")})
            metrics_cache, variants = {}, {}
            for key, after in predictions.items():
                initial = oracle_before if key.startswith("RI") else before
                metric_key = (initial.tobytes(), after.tobytes())
                if metric_key not in metrics_cache:
                    states = np.where(~scope, "not_evaluated", np.where(~desc["available"], "insufficient_data",
                                      np.where(after > 0, "ordered_untyped", "ambiguous")))
                    metrics_cache[metric_key] = evaluate_sample(
                        rows, label_raster, initial, after, edges,
                        evaluation_valid=truth.get("evaluation_valid"), orientation_labels=truth.get("orientation_groups"),
                        truth_raster=truth.get("domain_labels") if entry["sampler"] == "grid" else None,
                        pixel_spacing_xy=entry["pixel_spacing_xy"], regime=entry["regime"],
                        kind=entry["kind"], case=case if entry["kind"] == "synthetic" else None, states=states)
                metrics = metrics_cache[metric_key]
                batch[(*entry_batch, case, key)].append(metrics)
                stream.write(compact(dict(id=entry["id"], sample_id=entry["sample_id"], variant=key,
                                          run_id=entry["run_id"], sampler=entry["sampler"], partition=entry["partition"],
                                          case=case, metrics=metrics)) + "\n")
                counts["evaluations"] += 1
                minimum_enabled = key.endswith("1")
                before_min = predictions[key[:-1] + "0"]
                stage = metrics["after"]
                variants[key] = dict(labels=after, coverage=stage["positive_reference_coverage"],
                                     merge_rate=stage["pairs"]["merge_rate"], split_rate=stage["pairs"]["split_rate"],
                                     assigned=stage["assigned_full_support_elements"], full_support=metrics["full_support_elements"],
                                     domain_count=stage["domain_count_in_scope"], minimum_enabled=minimum_enabled,
                                     minimum_failed=(before_min > 0) & (after == 0) if minimum_enabled else np.zeros(len(rows), bool),
                                     acf_enabled=key.startswith("A1") or "_MP_" in key,
                                     spectral_enabled=key.startswith(("A0S1", "A1S1")) or "_MP_" in key)
            failures = dict(gates["failures"], feature_unavailable=scope & desc["available"] & (before == 0))
            gallery = dict(id=entry["id"], before=before, oracle_before=oracle_before,
                           scope=scope, hard=hard, acf=desc["acf_score"], ratio=desc["second_direction_ratio"],
                           energy=desc["energy"], gate_failures=failures, min_size=minimum,
                           acf_threshold=inputs.threshold, variants=variants)
            relative = f"runs/{entry['id']}.js"
            write_js(output / relative, "E1_RUN_DATA", gallery)
            gallery_index.append({**{k: entry[k] for k in ("id", "sample_id", "sampler", "regime", "family", "seed", "partition")}, "path": relative})
            if number % 250 == 0:
                print(f"evaluate + oracle + viewer {number + 1}/{len(index)}", flush=True)
        flush()
    with gzip.open(output / "summary.json.gz", "wt") as stream:
        stream.write(compact(dict(records=summaries)))
    write_js(output / "gallery-data.js", "E1_DATA", dict(samples=samples, runs=gallery_index))
    from .e1_gallery import write_gallery
    write_gallery(output / "index.html")
    return dict(counts), len(summaries)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--source", type=Path, default=REPO / ".scratch/autoencoder-21")
    args = parser.parse_args()
    output = args.out.resolve()
    if output.exists():
        raise FileExistsError("Use a fresh output directory; preserve previous runs")
    if "/envs/netcat/" not in sys.executable:
        raise RuntimeError("Run E1 in the user's netcat environment")
    output.mkdir(parents=True)
    resource.setrlimit(resource.RLIMIT_CPU, (45 * 60, 45 * 60 + 10))
    started, cpu_start = time.monotonic(), time.process_time()
    shutil.copyfile(PROTOCOL, output / "protocol.md")
    modules = list(Path(__file__).parent.glob("e1_*.py"))
    modules += [Path(__file__).parent / "training" / f"{name}.py"
                for name in ("partition", "evaluate", "predict", "texture", "data")]
    for module in modules:
        snapshot = output / "code" / module.relative_to(REPO)
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(module, snapshot)
    manifest = dict(schema="stmdomains-e1-run-v1", status="running", source=str(args.source.resolve()),
                    output=str(output), python=sys.executable, protocol_sha256=file_hash(PROTOCOL),
                    started_utc=datetime.now(timezone.utc).isoformat(), source_commit="bbfa417",
                    scale_px=48, baseline_minimum=dict(grid=4, centers=8),
                    code_sha256={str(p.relative_to(REPO)): file_hash(p) for p in modules},
                    training=False, encoder_inference=False, adapter_fit=False)
    write_json(output / "manifest.json", manifest)
    try:
        prepare_descriptors(args.source, output, check_budget=budget)
        inputs = Inputs(args.source, output)
        index, files = generate(inputs, output)
        counts, summaries = evaluate(inputs, output, index, files)
        for relative in inputs.source_hashes:
            path = inputs.source_root / relative
            if file_hash(path) != inputs.source_hashes[relative]:
                raise ValueError(f"Source changed during E1: {relative}")
        for path, expected in inputs.external_hashes.items():
            if file_hash(Path(path)) != expected:
                raise ValueError(f"Input changed during E1: {path}")
        inputs.save_audit()
        total_bytes = sum(path.stat().st_size for path in output.rglob("*") if path.is_file())
        if total_bytes > 8 * 1024**3:
            raise RuntimeError("E1 artifact budget exceeded")
        budget()
        manifest.update(status="completed", baseline_exact=len(index), summary_records=summaries,
                        artifact_bytes=total_bytes, source_hashes_verified_after_run=True, **counts)
    finally:
        if manifest["status"] == "running":
            manifest["status"] = "failed"
        manifest.update(wall_seconds=time.monotonic() - started, cpu_seconds=time.process_time() - cpu_start,
                        peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        write_json(output / "manifest.json", manifest)
        print(compact(manifest), flush=True)


if __name__ == "__main__":
    main()
