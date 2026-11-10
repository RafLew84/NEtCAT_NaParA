"""Compact, reproducible readout of completed E1 results; no new predictions."""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import gzip
import json
from pathlib import Path

from .bundle import file_hash, write_json
from .e1_inputs import Inputs
from .e1_run import context


def flatten(record):
    metric = record["metrics"]
    result = {k: record[k] for k in ("run_id", "sampler", "partition", "case", "variant")}
    for key in ("sample_count", "full_support_elements", "evaluated_elements",
                "positive_reference_elements", "known_zero_elements"):
        result[key] = metric[key]
    for stage in ("before", "after"):
        value = metric[stage]
        for key in ("positive_reference_coverage", "assigned_full_support_elements",
                    "false_known_zero_fraction", "domain_count_sum"):
            result[f"{stage}_{key}"] = value[key]
        for key in ("merge_rate", "split_rate", "same_reference_pairs", "different_reference_pairs"):
            result[f"{stage}_{key}"] = value["pairs"][key]
        result[f"{stage}_boundary_f1"] = value["boundary"]["f1"]
    return result


def readout(output):
    manifest = json.loads((output / "manifest.json").read_text())
    if manifest["status"] != "completed":
        raise ValueError("E1 must complete before readout")
    inputs = Inputs(manifest["source"], output)
    counters = {}
    for regime in ("transfer", "transductive"):
        for sampler in ("grid", "centers"):
            count = Counter()
            for entry in inputs.entries:
                if not (entry["kind"] == "measurement" and entry["family"] == "fft"
                        and entry["partition"] == "fh4" and entry["regime"] == regime
                        and entry["sampler"] == sampler):
                    continue
                _, _, desc, scope, gates, hard, _ = context(inputs, entry)
                count.update(dict(full=int((scope & desc["available"]).sum()), hard=int(hard.sum()),
                    acf=int((hard & gates["acf"]).sum()), spectral=int((hard & gates["spectral"]).sum()),
                    both=int((hard & gates["acf"] & gates["spectral"]).sum()),
                    acf_only_failure=int((hard & ~gates["acf"] & gates["spectral"]).sum()),
                    spectral_only_failure=int((hard & gates["acf"] & ~gates["spectral"]).sum()),
                    joint_failure=int((hard & ~gates["acf"] & ~gates["spectral"]).sum())))
            counters[f"{regime}/{sampler}"] = dict(count)
    with gzip.open(output / "summary.json.gz", "rt") as stream:
        records = json.load(stream)["records"]
    flat = [flatten(r) for r in records]
    for filename, rows in (("summary.csv", flat),
                           ("measurement.csv", [r for r in flat if r["case"] == "measurement"])):
        with (output / filename).open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    audit = json.loads((output / "input-audit.json").read_text())
    checkpoints = audit["provenance"]["runs"]
    result = dict(schema="stmdomains-e1-readout-v1", run=manifest,
                  real_gate_counts_without_model_duplication=counters,
                  provenance=checkpoints, descriptors_exact=len(audit["descriptors"]),
                  max_acf_difference=max(d["acf_max_abs_difference"] for d in audit["descriptors"].values()),
                  max_fft_difference=max(d["fft_max_abs_difference"] for d in audit["descriptors"].values()),
                  verified_source_files=len(audit["source_hashes"]),
                  verified_external_files=len(audit["external_hashes"]),
                  files={name: file_hash(output / name) for name in (
                      "manifest.json", "protocol.md", "input-audit.json", "truth-audit.json",
                      "gate-freeze.json", "summary.json.gz", "sample-metrics.jsonl.gz",
                      "oracle-readiness.jsonl.gz", "summary.csv", "measurement.csv")})
    write_json(output / "readout.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    print(json.dumps(readout(parser.parse_args().output), ensure_ascii=False, indent=2))
