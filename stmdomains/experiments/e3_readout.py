"""Postprocess completed E3 artifacts without inference, refitting or selection.

Domain rates retain their original per-run reference denominators. Paired
image diagnostics give every frame equal weight within a model seed, then
summarize the seeds. Probe comparisons are paired within the nine renderer
realizations; their perturbation doses are deliberately not claimed equal.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import csv
from datetime import datetime, timezone
import gzip
import json
from pathlib import Path
import sys
import time

import numpy as np

from .bundle import file_hash, write_json


MODEL_KEYS = ("regime", "family", "sampler")
PAIRED_METRICS = (
    "feature_absolute_median", "feature_relative_median", "feature_norm_change_median",
    "distance_rmse", "distance_spearman", "relation_change_fraction",
    "outside_mean", "angle_median", "translation_median",
)
PROBE_METRICS = (
    "absolute_l2", "relative_l2", "base_norm", "changed_norm", "norm_change",
    "input_rmse", "baseline_saturation_fraction", "post_outside_fraction",
    "mean_delta", "std_delta", "angle_shift_radians", "translation_shift_normalized",
)
STRUCTURES = ("orientation8", "spacing16", "phase4")


def number(value):
    if value is None or value == "":
        return None
    parsed = float(value)
    return parsed if np.isfinite(parsed) else None


def spread(values):
    """Finite count, median and observed range; missing is never zero."""
    finite = np.asarray([v for v in values if v is not None and np.isfinite(v)], float)
    return dict(n=len(finite), median=float(np.median(finite)) if len(finite) else None,
                min=float(finite.min()) if len(finite) else None,
                max=float(finite.max()) if len(finite) else None)


def flatten(value, prefix=""):
    result = {}
    for key, item in value.items():
        name = f"{prefix}.{key}" if prefix else key
        if isinstance(item, dict):
            result.update(flatten(item, name))
        elif isinstance(item, (list, tuple)):
            result[name] = json.dumps(item, ensure_ascii=False, separators=(",", ":"))
        else:
            result[name] = item
    return result


def write_csv(path, records):
    rows = [flatten(row) for row in records]
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def grouped(records, keys):
    result = defaultdict(list)
    for row in records:
        result[tuple(row[k] for k in keys)].append(row)
    return result


def seed_summary(records, keys, metrics, *, nested=False):
    result = []
    for group, rows in grouped(records, keys).items():
        seeds = [r["seed"] for r in rows]
        if len(set(seeds)) != len(seeds):
            raise ValueError(f"Repeated seed in summary: {dict(zip(keys, group))}")
        values = {metric: spread([r["metrics"][metric]["median"] if nested else r[metric]
                                  for r in rows]) for metric in metrics}
        result.append(dict(zip(keys, group), seeds=seeds, n_runs=len(rows),
                           n_model_seeds=sum(seed is not None for seed in seeds), metrics=values,
                           within_run_finite_counts={metric: spread([r["metrics"][metric]["n"] for r in rows])
                                                     for metric in metrics} if nested else None,
                           n_frames=spread([r["n_frames"] for r in rows]) if "n_frames" in rows[0] else None))
    return result


def domain_readout(output):
    with gzip.open(output / "domain-summary.json.gz", "rt") as stream:
        source = json.load(stream)["records"]
    # Full per-seed export includes every case and every original denominator.
    write_csv(output / "readout-domain-all.csv", source)
    selected = []
    for row in source:
        if row["case"] != "measurement":
            continue
        metrics, after = row["metrics"], row["metrics"]["after"]
        pairs = after["pairs"]
        item = {key: row[key] for key in (*MODEL_KEYS, "seed", "run_id", "condition", "partition", "variant")}
        item.update(n_frames=metrics["sample_count"], coverage=after["positive_reference_coverage"],
                    merge_rate=pairs["merge_rate"], split_rate=pairs["split_rate"],
                    full_support_assignment_fraction=after["full_support_assignment_fraction"],
                    positive_reference_elements=metrics["positive_reference_elements"],
                    reference_elements=pairs["reference_elements"], assigned_reference_elements=pairs["assigned_elements"],
                    same_reference_pairs=pairs["same_reference_pairs"], different_reference_pairs=pairs["different_reference_pairs"],
                    split_pairs=pairs["split_pairs"], merged_pairs=pairs["merged_pairs"],
                    full_support_elements=metrics["full_support_elements"],
                    assigned_full_support_elements=after["assigned_full_support_elements"],
                    domain_count_sum=after["domain_count_sum"])
        selected.append(item)
    keys = (*MODEL_KEYS, "condition", "partition", "variant")
    fields = tuple(k for k in selected[0] if k not in (*keys, "seed", "run_id", "n_frames"))
    summary = seed_summary(selected, keys, fields)
    write_csv(output / "readout-domain-seeds.csv", selected)
    write_csv(output / "readout-domain-summary.csv", summary)
    return dict(source_records=len(source), measurement_seed_rows=selected, measurement_seed_summary=summary)


def paired_readout(output):
    with (output / "paired-metrics.csv").open() as stream:
        rows = [dict(row, seed=int(row["seed"]) if row["seed"] else None)
                for row in csv.DictReader(stream)
                if row["case"] == "measurement" and row["support"] == "common"]
    keys = ("run_id", *MODEL_KEYS, "seed", "condition", "space", "support")
    per_seed = []
    for group, frames in grouped(rows, keys).items():
        if len({r["sample_id"] for r in frames}) != len(frames):
            raise ValueError("Duplicate frame in equal-frame paired summary")
        counts = {key: [int(r[key]) for r in frames] for key in ("nodes", "edges")}
        changed = [number(r["relation_changed"]) for r in frames]
        per_seed.append(dict(zip(keys, group), n_frames=len(frames),
            n_frames_with_nodes=sum(v > 0 for v in counts["nodes"]),
            n_frames_with_edges=sum(v > 0 for v in counts["edges"]),
            sample_ids=[r["sample_id"] for r in frames], nodes_sum=sum(counts["nodes"]),
            edges_sum=sum(counts["edges"]),
            relation_changed_sum=sum(v for v in changed if v is not None) if any(v is not None for v in changed) else None,
            metrics={metric: spread([number(r[metric]) for r in frames]) for metric in PAIRED_METRICS}))
    summary = seed_summary(per_seed, (*MODEL_KEYS, "condition", "space", "support"), PAIRED_METRICS, nested=True)
    write_csv(output / "readout-paired-frame-medians.csv", per_seed)
    write_csv(output / "readout-paired-seed-summary.csv", summary)
    return dict(measurement_common_rows=len(rows), equal_frame_seed_rows=per_seed, seed_summary=summary)


def edge_quality_readout(output):
    """Reference-valid edges, paired to identity within the SAME condition mask."""
    records = []
    with gzip.open(output / "edge-summary.jsonl.gz", "rt") as stream:
        for line in stream:
            row = json.loads(line)
            if row["case"] != "measurement":
                continue
            current, baseline = row["summary"], row["paired_identity"]
            if current["counts"] != baseline["counts"]:
                raise ValueError("Current/identity edge scores have different paired denominators")
            item = {key: row[key] for key in (*MODEL_KEYS, "seed", "run_id", "condition", "space", "support")}
            for metric in ("roc_auc", "average_precision"):
                a, b = current[metric], baseline[metric]
                item[metric], item["paired_identity_" + metric] = a, b
                item["delta_" + metric] = a - b if a is not None and b is not None else None
            item.update(boundary_prevalence=current["boundary_prevalence"],
                        **current["counts"], unavailable_reason=current["unavailable_reason"])
            records.append(item)
    keys = (*MODEL_KEYS, "condition", "space", "support")
    metrics = ("roc_auc", "average_precision", "paired_identity_roc_auc", "paired_identity_average_precision",
               "delta_roc_auc", "delta_average_precision", "scored_pairs", "same_pairs", "different_pairs",
               "boundary_prevalence")
    summary = seed_summary(records, keys, metrics)
    write_csv(output / "readout-edge-quality-seeds.csv", records)
    write_csv(output / "readout-edge-quality-summary.csv", summary)
    return dict(seed_rows=records, seed_summary=summary)


def probe_readout(output):
    with (output / "probe-metrics.csv").open() as stream:
        rows = [dict(row, seed=int(row["seed"]) if row["seed"] else None) for row in csv.DictReader(stream)]
    keys = (*MODEL_KEYS, "seed", "space", "condition", "condition_kind")
    per_seed = []
    for group, realizations in grouped(rows, keys).items():
        if len({r["realization"] for r in realizations}) != len(realizations):
            raise ValueError("Repeated probe realization")
        per_seed.append(dict(zip(keys, group), n_realizations=len(realizations),
            n_paired_valid=sum(r["paired_valid"] == "True" for r in realizations),
            metrics={metric: spread([number(r[metric]) for r in realizations]) for metric in PROBE_METRICS}))
    summary = seed_summary(per_seed, (*MODEL_KEYS, "space", "condition", "condition_kind"), PROBE_METRICS, nested=True)
    comparisons = []
    for group, sample_rows in grouped(rows, (*MODEL_KEYS, "seed", "space")).items():
        conditions = grouped(sample_rows, ("condition",))
        for (photometric,), photo_rows in conditions.items():
            if photometric == "identity" or photo_rows[0]["condition_kind"] != "photometry":
                continue
            photo_by_id = {r["realization"]: r for r in photo_rows}
            for structure in STRUCTURES:
                paired = []
                for structural in conditions[(structure,)]:
                    photo = photo_by_id[structural["realization"]]
                    a, b = number(photo["absolute_l2"]), number(structural["absolute_l2"])
                    if photo["paired_valid"] == "True" and structural["paired_valid"] == "True" and a is not None and b is not None:
                        paired.append((a, b, number(photo["input_rmse"]), number(structural["input_rmse"])))
                ratios = [a / b for a, b, _, _ in paired if b > 0]
                comparisons.append(dict(zip((*MODEL_KEYS, "seed", "space"), group), photometric=photometric,
                    structural=structure, n_joint_realizations=len(paired), n_nonzero_structure=len(ratios),
                    photo_greater_or_equal_count=sum(a >= b for a, b, _, _ in paired),
                    photo_movement=spread([a for a, _, _, _ in paired]),
                    structure_movement=spread([b for _, b, _, _ in paired]),
                    photo_to_structure_ratio=spread(ratios),
                    photo_input_rmse=spread([a for _, _, a, _ in paired]),
                    structure_input_rmse=spread([b for _, _, _, b in paired])))
    comparison_summary = []
    compare_keys = (*MODEL_KEYS, "space", "photometric", "structural")
    compare_metrics = ("photo_movement", "structure_movement", "photo_to_structure_ratio", "photo_input_rmse", "structure_input_rmse")
    for group, seed_rows in grouped(comparisons, compare_keys).items():
        comparison_summary.append(dict(zip(compare_keys, group), seeds=[r["seed"] for r in seed_rows],
            n_runs=len(seed_rows), n_joint_realizations=spread([r["n_joint_realizations"] for r in seed_rows]),
            metrics={metric: spread([r[metric]["median"] for r in seed_rows]) for metric in compare_metrics}))
    write_csv(output / "readout-probe-seeds.csv", per_seed)
    write_csv(output / "readout-probe-summary.csv", summary)
    write_csv(output / "readout-probe-comparisons-seeds.csv", comparisons)
    write_csv(output / "readout-probe-comparisons-summary.csv", comparison_summary)
    return dict(source_rows=len(rows), seed_rows=per_seed, seed_summary=summary,
                comparison_seed_rows=comparisons, comparison_seed_summary=comparison_summary)


def backend_readout(output):
    records = json.loads((output / "backend-drift.json").read_text())["records"]
    def aggregate(rows):
        changes = {key: sum(r["partition_changed"][key] for r in rows) for key in rows[0]["partition_changed"]}
        return dict(entries=len(rows), max_abs_feature_error=max(r["max_abs_feature_error"] for r in rows),
                    exact_historical_partitions=sum(r["historical_exact_partitions"] for r in rows),
                    fresh_changed_partitions=sum(changes.values()), fresh_changed_by_stage=changes,
                    entries_with_fresh_changes=sum(any(r["partition_changed"].values()) for r in rows))
    runs = [dict(run_id=key[0], **aggregate(rows)) for key, rows in grouped(records, ("run_id",)).items()]
    return dict(**aggregate(records), per_run=runs)


def summarize(output_root) -> dict:
    started = time.monotonic()
    output = Path(output_root).resolve()
    manifest = json.loads((output / "manifest.json").read_text())
    if manifest["status"] != "completed":
        raise ValueError("E3 must be completed before postprocessing")
    names = ("manifest.json", "gradient-calibration.json", "backend-drift.json", "domain-summary.json.gz", "edge-summary.jsonl.gz",
             "paired-metrics.csv", "probe-metrics.csv", "probe-metadata.json", "prediction-freeze.json")
    source_hashes = {name: file_hash(output / name) for name in names}
    frozen = json.loads((output / "prediction-freeze.json").read_text())["files"]
    for name, expected in source_hashes.items():
        if name in frozen and frozen[name] != expected:
            raise ValueError(f"Frozen E3 input changed: {name}")
    calibration = json.loads((output / "gradient-calibration.json").read_text())
    calibration = {key: {field: value for field, value in record.items() if field != "fit_window_ids"}
                   for key, record in calibration.items()}
    result = dict(schema="stmdomains-e3-readout-v1", output=str(output), run=manifest,
        aggregation=dict(
            domains="Original per-run frame-local count aggregates; summary median/min/max across model seeds only. Coverage and merge/split denominators remain separate.",
            paired="Measurement, common support only. Equal-frame median within each run/condition/space; then median/min/max of model-seed medians. Each metric retains its finite-frame count; empty frames do not become zeros.",
            edge_quality="Measurement reference-valid edges only. AUC/AP differences use paired_identity in the SAME condition/support record, never the pooled identity-condition result. Current and identity counts must match. Seed summaries do not pool seeds.",
            edge_stability="Spearman and relation changes use all supported graph edges, without reference filtering; they have different denominators from ROC-AUC/AP.",
            probe="Nine paired phase-by-renderer-noise realizations per model. Photometry/structure ratios use the same realization and joint availability. No matching of input RMSE or physical effect sizes is assumed.",
            pixel_diagnostics="Pixel statistics describe64 encoder inputs, including rows for FFT/geometry, whose features instead use native48. Feature movement is never divided by64 input RMSE.",
            seeds="AE/rVAE: three model seeds. FFT/photometry/geometry: one deterministic run with seed null, not an extra trained seed.",
            missing="Null means unavailable; ranges are observed model-seed or frame/realization ranges, not confidence intervals.",
            adapted_units="Frozen PCA coordinates divided by original training-edge median; relative movement is invariant to this scalar."),
        calibration=calibration, backend=backend_readout(output), domains=domain_readout(output),
        paired=paired_readout(output), edge_quality=edge_quality_readout(output),
        probe=probe_readout(output), input_sha256=source_hashes,
        readout_code_sha256=file_hash(Path(__file__)))
    result["exports_sha256"] = {p.name: file_hash(p) for p in sorted(output.glob("readout-*.csv"))}
    # Detect an unexpected concurrent rewrite of any input used by the readout.
    if any(file_hash(output / name) != digest for name, digest in source_hashes.items()):
        raise ValueError("E3 source changed during postprocessing")
    write_json(output / "readout.json", result)
    write_json(output / "readout-manifest.json", dict(
        schema="stmdomains-e3-postprocessing-v1", status="completed",
        created_utc=datetime.now(timezone.utc).isoformat(), python=sys.executable,
        numpy=np.__version__, wall_seconds=time.monotonic() - started,
        code_sha256={str(Path(__file__).resolve()): result["readout_code_sha256"]},
        input_sha256=source_hashes,
        files=dict(result["exports_sha256"], **{"readout.json": file_hash(output / "readout.json")}),
        encoder_inference=False, encoder_training=False, adapter_refit=False,
        historical_artifacts_modified=False))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    result = summarize(parser.parse_args().output)
    print(json.dumps(dict(output=result["output"], backend={k: v for k, v in result["backend"].items() if k != "per_run"},
                          probe_rows=result["probe"]["source_rows"],
                          measurement_common_rows=result["paired"]["measurement_common_rows"])))
