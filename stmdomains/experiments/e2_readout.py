"""Export completed E2 domains, permutation audit and compact provenance."""
from __future__ import annotations

import argparse
from collections import defaultdict
import csv
import gzip
import json
from pathlib import Path

import numpy as np

from .bundle import file_hash, write_json
from .e1_readout import flatten
from .e2_pipeline import SHUFFLE_SEEDS


def readout(output):
    manifest = json.loads((output / "manifest.json").read_text())
    if manifest["status"] != "completed":
        raise ValueError("E2 must complete before readout")
    with gzip.open(output / "domain-summary.json.gz", "rt") as stream:
        records = json.load(stream)["records"]
    with (output / "domain-metrics.csv").open("w", newline="") as stream:
        writer = None
        for record in records:
            row = dict(flatten(record), **{key: record[key] for key in ("regime", "family", "seed", "condition")})
            if writer is None:
                writer = csv.DictWriter(stream, fieldnames=list(row))
                writer.writeheader()
            writer.writerow(row)
    index = json.loads((output / "prediction-index.json").read_text())
    # Shared permutations: audit exactly one representative per image/sampler/regime.
    selected = [entry for entry in index if entry["family"] == "ae" and entry["seed"] == 20261101]
    if len(selected) != 420:
        raise ValueError("Permutation audit needs 420 unique scopes")
    entries_by_group = defaultdict(list)
    for entry in index:
        entries_by_group[(entry["regime"], entry["cache_group"])].append(entry)
    permutations = []
    for entry in selected:
        with np.load(output / entry["prediction"], allow_pickle=False) as z:
            orders, scope = z["permutations"], z["scope"]
        related = entries_by_group[(entry["regime"], entry["cache_group"])]
        masks = []
        for sibling in related:
            with np.load(output / sibling["prediction"], allow_pickle=False) as z:
                if not np.array_equal(orders, z["permutations"]):
                    raise ValueError("Readouts did not share permutations")
                masks.append(z["valid"])
        rows_path = Path(manifest["source"]) / "cache" / entry["cache_group"] / "rows.json.gz"
        with gzip.open(rows_path, "rt") as stream:
            available = np.array([r["available"] for r in json.load(stream)], bool)
        eligible = scope & available
        matrix = np.asarray(masks, bool)
        _, group_sizes = np.unique(np.packbits(matrix[:, eligible].T, axis=1), axis=0, return_counts=True)
        moved = [(orders[i] != np.arange(len(scope))) for i in range(len(SHUFFLE_SEEDS))]
        if any(np.any(m & ~eligible) for m in moved):
            raise ValueError("Moved a node outside the eligible scope")
        permutations.append(dict(sample_id=entry["sample_id"], regime=entry["regime"], sampler=entry["sampler"],
            eligible_nodes=int(eligible.sum()), stratum_sizes=group_sizes.tolist(),
            moved_by_seed={str(seed): int(m.sum()) for seed, m in zip(SHUFFLE_SEEDS, moved)},
            shared_by_15_readouts=len(related) == 15))
    write_json(output / "permutation-audit.json", dict(records=permutations))
    audit = json.loads((output / "final-input-audit.json").read_text())
    adapters = audit["adapters"]
    result = dict(schema="stmdomains-e2-readout-v1", run=manifest,
        adapter_audit=adapters, checkpoint_lineage=audit["checkpoint_lineage"],
        verified_source_files=len(audit["source_hashes"]), e1_descriptors=len(audit["e1_descriptor_hashes"]),
        permutation_scopes=len(permutations), permutation_identity_scopes=sum(
            r["eligible_nodes"] > 1 and not any(r["moved_by_seed"].values()) for r in permutations),
        permutation_moved_totals={str(seed): sum(r["moved_by_seed"][str(seed)] for r in permutations) for seed in SHUFFLE_SEEDS},
        files={name: file_hash(output / name) for name in (
            "manifest.json", "protocol.md", "input-audit.json", "final-input-audit.json", "truth-audit.json",
            "prediction-freeze.json", "edge-summary.jsonl.gz", "edge-sample-metrics.jsonl.gz",
            "domain-summary.json.gz", "domain-sample-metrics.jsonl.gz", "edge-metrics.csv",
            "domain-metrics.csv", "permutation-audit.json", "gallery-data.js", "index.html")})
    write_json(output / "readout.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    result = readout(parser.parse_args().output)
    print(json.dumps({key: result[key] for key in ("verified_source_files", "permutation_scopes", "permutation_moved_totals")}))
