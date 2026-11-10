"""Truth-free E2 distances, fixed availability permutations and graph replay."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from .bundle import file_hash, write_json
from .e1_mechanics import apply_variant
from .e1_run import context
from .training.partition import (_unit_features, transform_features, fh_partition,
                                 mws_partition, relation_weights)
from .training.predict import label_numbers

SHUFFLE_SEEDS = tuple(range(20261110, 20261115))
SPACES = ("native", "l2", "adapted")
STAGES = ("H_M0", "H_M1", "A1S1M0", "A1S1M1")


def permutations(valid_matrix, eligible, key):
    """Shared whole-row shuffles within availability strata, never using truth."""
    valid = np.asarray(valid_matrix, bool)
    eligible = np.asarray(eligible, bool)
    if valid.ndim != 2 or valid.shape[1:] != eligible.shape:
        raise ValueError("Expected feature-by-node validity and node scope")
    patterns = np.packbits(valid.T, axis=1)
    _, strata = np.unique(patterns, axis=0, return_inverse=True)
    results = []
    for seed in SHUFFLE_SEEDS:
        entropy = int.from_bytes(hashlib.sha256(f"{key}/{seed}".encode()).digest()[:16], "little")
        rng = np.random.default_rng(entropy)
        permutation = np.arange(len(eligible))
        for group in np.unique(strata[eligible]):
            indices = np.flatnonzero(eligible & (strata == group))
            permutation[indices] = rng.permutation(indices)
        if not np.array_equal(valid[:, permutation], valid):
            raise AssertionError("Permutation moved missingness")
        results.append(permutation)
    return np.asarray(results, dtype=np.int64)


def distances(values, edges, valid, scale=1.):
    result = np.full(len(edges), np.nan)
    usable = valid[edges].all(axis=1)
    result[usable] = np.linalg.norm(values[edges[usable, 0]] - values[edges[usable, 1]], axis=1) / scale
    return result


def spaces(features, adapter, scope):
    native = np.asarray(features, dtype=float).copy()
    native[~scope] = np.nan
    unit, unit_valid = _unit_features(native)
    projected, adapted_valid = transform_features(native, adapter)
    # Availability of the downstream adapter remains explicit even in native/L2.
    valid = unit_valid & adapted_valid
    return (native, unit, projected), valid


def predictions(ids, edges, distance, valid, adapter, hard, full_gate, minimum):
    outputs = {}
    if adapter["available"]:
        kinds, strengths = relation_weights(distance, adapter["q25"], adapter["q75"])
    else:
        kinds = np.full(len(edges), "unavailable", dtype="U11")
        strengths = np.full(len(edges), np.nan)
    for method in ("fh4", "mws"):
        proposals = (fh_partition(ids, edges, distance, valid=valid, k=4.) if method == "fh4" else
                     mws_partition(ids, edges, kinds, strengths, valid=valid)["component_ids"])
        outputs[f"{method}_before"] = label_numbers(proposals)
        for stage in STAGES:
            mask = hard if stage.startswith("H_") else full_gate
            size = minimum if stage.endswith("1") else 1
            outputs[f"{method}_{stage}"] = apply_variant(ids, edges, proposals, mask & valid, size)["after"]
    return outputs


def generate(bank, output, check_budget=lambda: None):
    """Fit only old training windows, freeze all predictions BEFORE truth access."""
    inputs = bank.inputs
    templates = {(e["regime"], e["sampler"], e["sample_id"], e["partition"]): e
                 for e in inputs.entries if e["family"] == "fft"}
    originals = {(e["run_id"], e["sampler"], e["sample_id"], e["partition"]): e for e in inputs.entries}
    index, frozen_files, adapters = [], {}, {}
    baseline_exact = 0
    for run in bank.runs:
        for sampler in ("grid", "centers"):
            adapter = bank.adapter(run, sampler)
            relative = f"adapters/{run['run_id']}/{sampler}.json"
            write_json(output / relative, adapter)
            frozen_files[relative] = file_hash(output / relative)
            adapters[(run["run_id"], sampler)] = adapter
    print(f"E2 adapters frozen: {len(adapters)}", flush=True)
    for regime in ("transfer", "transductive"):
        runs = [r for r in bank.runs if r["regime"] == regime]
        for sampler in ("grid", "centers"):
            groups = [g for g in inputs.groups.values() if g["sampler"] == sampler]
            for group in sorted(groups, key=lambda g: g["group_id"]):
                check_budget()
                sample = group["record"]["sample_id"]
                template = templates[(regime, sampler, sample, "fh4")]
                rows, ids, desc, scope, gates, hard, minimum = context(inputs, template)
                source = inputs.load_npz(f"{template['directory']}/{template['evaluation_input']}")
                edges = source["edges"]
                prepared = [spaces(bank.features(run, group), adapters[(run["run_id"], sampler)], scope) for run in runs]
                matrix = np.array([valid for _, valid in prepared])
                full_scope = scope & desc["available"]
                common = full_scope & matrix.all(axis=0)
                perm = permutations(matrix, full_scope, f"{regime}/{group['group_id']}")
                full_gate = hard & gates["acf"] & gates["spectral"]
                for run, (coordinates, valid) in zip(runs, prepared):
                    adapter = adapters[(run["run_id"], sampler)]
                    # Condition zero is unpermuted, followed by the five fixed shuffles.
                    conditions = np.vstack((np.arange(len(rows)), perm))
                    edge_distances = np.stack([
                        np.stack([distances(values[order], edges, valid,
                                            adapter["edge_median"] if space == 2 and adapter["available"] else 1.)
                                  for space, values in enumerate(coordinates)])
                        for order in conditions])
                    arrays = dict(edges=edges, distances=edge_distances, valid=valid,
                                  common=common, hard=hard, scope=scope, permutations=perm)
                    for name, which in (("actual", 0), ("shuffle", 1)):
                        result = predictions(ids, edges, edge_distances[which, 2], valid, adapter,
                                             hard, full_gate, minimum)
                        arrays.update({f"{name}_{k}": v for k, v in result.items()})
                    if run["baseline"]:
                        for method in ("fh4", "mws"):
                            old = originals[(run["source_run_id"], sampler, sample, method)]
                            saved = inputs.load_npz(f"{old['directory']}/{old['evaluation_input']}")
                            if not np.array_equal(edges, saved["edges"]):
                                raise ValueError("Baseline graph changed")
                            for key, old_key in ((f"actual_{method}_before", "before"),
                                                 (f"actual_{method}_A1S1M1", "after")):
                                if not np.array_equal(arrays[key], saved[old_key]):
                                    raise ValueError(f"Baseline replay differs: {run['run_id']} {sample} {key}")
                            baseline_exact += 1
                    ident = f"group-{len(index):05d}"
                    relative = f"predictions/{ident}.npz"
                    path = output / relative
                    path.parent.mkdir(exist_ok=True)
                    np.savez_compressed(path, **arrays)
                    frozen_files[relative] = file_hash(path)
                    index.append(dict(run, id=ident, sample_id=sample, sampler=sampler,
                                      kind=template["kind"], cache_group=group["group_id"],
                                      pixel_spacing_xy=template["pixel_spacing_xy"], prediction=relative))
                if len(index) % 300 == 0:
                    print(f"E2 predictions/distances {len(index)}/6300", flush=True)
    if len(index) != 6300 or baseline_exact != 5880:
        raise ValueError("Incomplete E2 matrix")
    write_json(output / "prediction-index.json", index)
    frozen_files["prediction-index.json"] = file_hash(output / "prediction-index.json")
    write_json(output / "input-audit.json", bank.audit())
    frozen_files["input-audit.json"] = file_hash(output / "input-audit.json")
    write_json(output / "prediction-freeze.json", dict(
        schema="stmdomains-e2-freeze-v1", files=frozen_files, baseline_exact=baseline_exact,
        groups=len(index), adapter_count=len(adapters), truth_opened_for_this_run=False,
        historical_data_known=True, shuffle_seeds=list(SHUFFLE_SEEDS)))
    return index, frozen_files
