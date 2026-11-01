"""Read-only structural audit of completed graph24 prediction exports.

This adds evidence after numerical code was frozen. It never fits models,
opens reference data, computes detection quality, or modifies predictions.
Run with ``python -m ...graph_ssl.audit_predictions --output TRIAL_ROOT``.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import gzip
import json
import os
from pathlib import Path
import resource
import sys
import time

import numpy as np

from ...bundle import arrays_hash, file_hash, write_json
from .data import iter_prepared
from .legacy_geometry import legacy_join


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def deny_references():
    def audit(event, args):
        if event == "open" and isinstance(args[0], (str, bytes, os.PathLike)):
            path = os.fsdecode(args[0]).replace("\\", "/")
            if "/evaluation/" in path or "/references/" in path or "manual_domain" in path:
                raise PermissionError("Reference data forbidden to export audit: " + path)
    sys.addaudithook(audit)


def artifact(root, relative):
    path = (root / relative).resolve()
    require(path.is_relative_to(root), "Artifact escapes trial root: " + str(relative))
    require(path.is_file(), "Missing artifact: " + str(relative))
    return path


def load_arrays(path):
    with np.load(path, allow_pickle=False) as archive:
        return {key: archive[key] for key in archive.files}


def expected_variants():
    result = {}
    for regime in ("transfer", "transductive"):
        result[regime + "-geometry"] = (regime, "geometry", None)
        losses = ("sce_scale", "sce", "untrained") if regime == "transfer" else ("sce_scale", "untrained")
        for seed in (20261101, 20261102, 20261103):
            for loss in losses:
                result[f"{regime}-graph_{loss}-{seed}"] = (regime, "graph_" + loss, seed)
    return result


def complete_index(root):
    """Gate all audit work on the final index written after partition export."""
    path = root / "predictions/index.json"
    require(path.is_file(), "Predictions are incomplete: final index.json is absent")
    entries = read(path)
    require(isinstance(entries, list) and len(entries) == 4212, "Expected 4212 completed index entries")
    require(sum("heldout_file" in row for row in entries) == 504, "Expected 504 heldout archives")
    paths = []
    for row in entries:
        for key in ("file", "heldout_file"):
            if key in row:
                value = row[key]
                require(isinstance(value, str) and value.startswith("predictions/") and value.endswith(".npz"),
                        "Unexpected prediction path")
                artifact(root, value)
                artifact(root, str(Path(value).with_suffix(".json.gz")))
                paths.append(value)
    require(len(set(paths)) == 4716, "Duplicated prediction archive path")
    return entries


def expected_edges(xy, ids, scope):
    """Independently reconstruct the declared center graph and canonical ties."""
    selected = np.flatnonzero(scope)
    points = xy[selected]
    if len(points) < 2:
        return np.empty((0, 2), np.int64)
    distance = np.linalg.norm(points[:, None] - points[None, :], axis=2)
    nearest = np.where(distance > 1e-10, distance, np.inf).min(axis=1)
    finite = nearest[np.isfinite(nearest)]
    radius = min(24., 1.65 * float(np.median(finite))) if len(finite) else 24.
    pairs = []
    for a, b in zip(*np.where(np.triu(distance <= radius + 1e-10, 1))):
        i, j = int(selected[a]), int(selected[b])
        pairs.append((i, j) if str(ids[i]) < str(ids[j]) else (j, i))
    return np.asarray(sorted(pairs, key=lambda pair: (str(ids[pair[0]]), str(ids[pair[1]]))), np.int64).reshape(-1, 2)


def project_groups(features, adapter):
    result = np.zeros(len(features), np.int32)
    if not adapter["available"]:
        return result
    finite = np.flatnonzero(np.isfinite(features).all(axis=1))
    groups = adapter["catalogue"]["groups"]
    if not len(finite) or not groups:
        return result
    projected = ((features[finite] - adapter["mean"]) / adapter["std"] - adapter["pca_mean"]) @ np.asarray(adapter["components"]).T
    distances = np.linalg.norm(projected[:, None] - np.asarray([group["centroid"] for group in groups]), axis=2)
    nearest = distances.argmin(axis=1)
    for index, group in enumerate(groups):
        accepted = (nearest == index) & (distances[:, index] <= group["radius"])
        result[finite[accepted]] = group["id"]
    return result


def check_export(path, sample, entry, heldout, edges, groups, legacy, geom):
    values = load_arrays(path)
    n = len(sample["ids"])
    base = {"before", "after", "edges", "states", "reasons", "score"}
    extra = {"edge_distances", "relation_kinds", "relation_strengths", "descriptor_group"}
    require(set(values) == base | (set() if legacy is not None else extra), f"Unexpected fields: {path}")
    for key in base - {"edges"}:
        require(values[key].shape == (n,), f"Invalid {key} shape: {path}")
    for key in ("before", "after"):
        require(values[key].dtype.kind in "iu" and np.all(values[key] >= 0), f"Invalid {key} labels: {path}")
    scope = sample["split"] == "test" if heldout else np.ones(n, bool)
    available = scope & sample["eligible"]
    require(np.array_equal(values["edges"], edges), f"Incorrect scoped center graph: {path}")
    require(values["edges"].dtype.kind in "iu", f"Noninteger edge indices: {path}")
    require(np.all(values["before"][~available] == 0) and np.all(values["after"][~available] == 0),
            f"Assignment outside eligible scope: {path}")
    require(np.array_equal(values["score"], geom["score"], equal_nan=True), f"Changed geometry score: {path}")
    assigned = values["after"] > 0
    require(np.all(geom["gate"][assigned]), f"Assigned node failed geometry gate: {path}")
    states = np.where(~scope, "not_evaluated", np.where(~sample["eligible"], "insufficient_data",
                      np.where(assigned, "ordered_untyped", "ambiguous")))
    require(np.array_equal(values["states"], states), f"State/assignment mismatch: {path}")
    require(np.all(values["reasons"][assigned] == "") and np.all(values["reasons"][~assigned] != ""),
            f"Missing or contradictory refusal reason: {path}")
    require(np.all(values["reasons"][~scope] == "not_test_scope"), f"Incorrect excluded-scope reason: {path}")
    for index in np.flatnonzero(scope & ~sample["eligible"]):
        require(values["reasons"][index] == sample["rows"][index]["unavailable_reason"],
                f"Lost support refusal reason: {path}")
    if legacy is not None:
        require(np.array_equal(values["before"], legacy) and np.array_equal(values["after"], legacy),
                f"Canonical legacy replay differs: {path}")
    else:
        for key in ("edge_distances", "relation_kinds", "relation_strengths"):
            require(values[key].shape == (len(edges),), f"Invalid edge attribute shape: {path}")
        expected_groups = np.where(scope, groups, 0)
        require(values["descriptor_group"].dtype.kind in "iu" and
                np.array_equal(values["descriptor_group"], expected_groups), f"Catalogue assignment differs: {path}")
    with gzip.open(path.with_suffix(".json.gz"), "rt", encoding="utf-8") as stream:
        payload = json.load(stream)
    require(payload["schema"] == "stmdomains-result-v1" and payload["sample_id"] == sample["sample_id"] and
            payload["input_content_sha256"] == sample["record"]["content_sha256"], f"Incorrect result identity: {path}")
    require(payload["run_id"] == entry["variant_id"] + "-" + entry["partition"] and payload["catalogue_id"] is None,
            f"Incorrect run or physical catalogue: {path}")
    extension = payload["extensions"]["graph24"]
    require(extension["elements"] == sample["rows"] and extension["material"] is None, f"Changed input rows: {path}")
    for key in ("sample_id", "variant_id", "family", "regime", "partition", "seed", "latent", "scale_px", "sampler"):
        require(extension["metadata"][key] == entry[key], f"Metadata mismatch ({key}): {path}")
    require(extension["metadata"].get("case") is None and extension["metadata"].get("control_seed") is None,
            f"Evaluation identity leaked into frozen result: {path}")
    expected_catalogue = None if legacy is not None else "adapters/" + entry["variant_id"] + ".json"
    require(extension["descriptor_catalogue"] == expected_catalogue, f"Incorrect descriptor catalogue: {path}")
    assignments = payload["assignments"]
    require(len(assignments) == n, f"Missing assignments: {path}")
    for index, (assignment, row) in enumerate(zip(assignments, sample["rows"])):
        expected = dict(element_id=row["element_id"], xy=row["raw_edge_xy"], support_xyxy=row["support_xyxy"],
                        state=str(states[index]), reason=None if assigned[index] else str(values["reasons"][index]),
                        type_id=None, domain_id=int(values["after"][index]) or None, orientation_deg=None)
        require(assignment == expected, f"JSON/NPZ identity or assignment differs at {index}: {path}")
    return arrays_hash(values), n


def audit(root, entries):
    plan = read(root / "plan.json")
    require(file_hash(root / "prepared/manifest.json") == plan["data_manifest_sha256"], "Prepared manifest changed")
    for path, digest in plan["code_sha256"].items():
        require(file_hash(Path(path)) == digest, "Frozen numerical source changed: " + path)
    variants = expected_variants()
    runs = read(root / "features/runs.json")
    require(len(runs) == 17 and {run["variant_id"] for run in runs} == set(variants), "Incorrect feature variant matrix")
    adapters = {variant: read(artifact(root, "adapters/" + variant + ".json")) for variant in variants}
    by_sample = defaultdict(list)
    for entry in entries:
        by_sample[entry["sample_id"]].append(entry)
        require(entry.get("case") is None and entry.get("control_seed") is None, "Index contains evaluation labels")
    expected_ids = defaultdict(list)
    training_features = defaultdict(list)
    pairs = defaultdict(dict)
    # The factory ordering is public analysis provenance, not evaluation labels.
    from .controls import CASES, SEEDS
    pair_ids = {f"graph-heldout-{seed_index * len(CASES) + CASES.index(case) + 1:04d}": (seed, case)
                for seed_index, seed in enumerate(SEEDS) for case in ("empty_gap", "missing_band")}
    counts = Counter()
    for sample in iter_prepared(root):
        sid, n = sample["sample_id"], len(sample["ids"])
        sample_entries = by_sample.pop(sid, [])
        expected_keys = {(variant, method) for variant in variants for method in ("fh4", "mws")}
        expected_keys |= {(regime + "-legacy15", "legacy15") for regime in ("transfer", "transductive")}
        require(len(sample_entries) == 36 and {(row["variant_id"], row["partition"]) for row in sample_entries} == expected_keys,
                "Incomplete or duplicate sample matrix: " + sid)
        geom = load_arrays(artifact(root, "geometry/" + sid + ".npz"))
        edges = {False: expected_edges(sample["xyref"], sample["ids"], np.ones(n, bool)),
                 True: expected_edges(sample["xyref"], sample["ids"], sample["split"] == "test")}
        canonical = np.argsort(sample["ids"], kind="stable")
        legacy = {}
        for heldout in (False, True) if sample["kind"] == "measurement" else (False,):
            scope = sample["split"] == "test" if heldout else np.ones(n, bool)
            value = np.zeros(n, np.int64)
            value[canonical] = legacy_join(sample["xyref"][canonical], {key: val[canonical] for key, val in geom.items()},
                                            (scope & sample["eligible"])[canonical])
            legacy[heldout] = value
        features, groups = {}, {}
        for variant, (regime, family, seed) in variants.items():
            values = load_arrays(artifact(root, "features/" + variant + "/" + sid + ".npz"))
            require(set(values) == {"features"}, "Unexpected feature archive fields")
            value = values["features"]
            require(value.shape == (n, 57 if family == "geometry" else 32), "Incorrect feature shape: " + sid)
            require(np.all(np.isfinite(value[sample["eligible"]])) and np.all(np.isnan(value[~sample["eligible"]])),
                    "Feature availability differs from prepared input: " + sid)
            features[variant], groups[variant] = value, project_groups(value, adapters[variant])
            if sample["kind"] == "measurement":
                selected = sample["eligible"] & ((sample["split"] == "train") if regime == "transfer" else True)
                expected_ids[variant].extend(sid + "/" + str(ident) for ident in sample["ids"][selected])
                training_features[variant].append(value[selected])
        pair_proof = None
        if sid in pair_ids:
            pair_proof = {"input": arrays_hash({key: sample[key] for key in ("x", "adj", "valid", "eligible", "ids", "xyref")}),
                          "geometry": arrays_hash(geom), "features": {key: arrays_hash({"features": val}) for key, val in features.items()},
                          "predictions": {}}
        for entry in sample_entries:
            variant, method = entry["variant_id"], entry["partition"]
            is_legacy = entry["family"] == "legacy15"
            expected_regime, expected_family, expected_seed = ((variant.split("-")[0], "legacy15", None)
                                                               if is_legacy else variants[variant])
            require((entry["regime"], entry["family"], entry["seed"]) == (expected_regime, expected_family, expected_seed) and
                    entry["kind"] == sample["kind"] and entry["scale_px"] == 72 and entry["sampler"] == "centers",
                    "Incorrect indexed metadata: " + sid)
            has_heldout = sample["kind"] == "measurement" and entry["regime"] == "transfer"
            require(("heldout_file" in entry) == has_heldout, "Incorrect heldout presence: " + sid)
            for heldout in (False, True) if has_heldout else (False,):
                path = artifact(root, entry["heldout_file" if heldout else "file"])
                digest, checked = check_export(path, sample, entry, heldout, edges[heldout],
                                               None if is_legacy else groups[variant], legacy[heldout] if is_legacy else None, geom)
                counts["heldout_archives" if heldout else "full_archives"] += 1
                counts["assignment_rows_checked"] += checked
                counts["canonical_legacy_replays"] += int(is_legacy)
                if pair_proof is not None:
                    pair_proof["predictions"][variant + "/" + method] = digest
        if pair_proof is not None:
            seed, case = pair_ids[sid]
            pairs[seed][case] = pair_proof
        counts["samples"] += 1
        counts["measurement_samples" if sample["kind"] == "measurement" else "synthetic_samples"] += 1
        if counts["samples"] % 12 == 0:
            print("audited", counts["samples"], "samples", flush=True)
    require(not by_sample and counts["samples"] == 117 and counts["measurement_samples"] == 24, "Unexpected sample matrix")
    adapter_proof = []
    for variant, adapter in adapters.items():
        regime, family, seed = variants[variant]
        required_count = 76 if regime == "transfer" else 3795
        require(adapter["training_ids"] == expected_ids[variant] and adapter["training_elements"] == required_count and
                len(set(expected_ids[variant])) == required_count, "Adapter training IDs differ: " + variant)
        require(adapter["regime"] == regime and adapter["feature_id"] == variant, "Adapter identity differs: " + variant)
        values = np.concatenate(training_features[variant])
        require(adapter["input_dimension"] == values.shape[1], "Adapter input dimension differs")
        if adapter["available"]:
            np.testing.assert_allclose(adapter["mean"], values.mean(axis=0), rtol=0, atol=1e-10)
            np.testing.assert_allclose(adapter["std"], np.maximum(values.std(axis=0), 1e-6), rtol=0, atol=1e-10)
            components = np.asarray(adapter["components"])
            require(components.shape == (24, values.shape[1]) and np.isfinite(components).all(), "Invalid PCA projection")
            np.testing.assert_allclose(components @ components.T, np.eye(24), rtol=0, atol=1e-6)
            catalogue = adapter["catalogue"]
            require(catalogue["meaning"] == "descriptor_similarity_only_not_structural_type", "Catalogue claimed physical type")
            ids = [group["id"] for group in catalogue["groups"]]
            require(len(set(ids)) == len(ids) and all(isinstance(ident, int) and ident > 0 for ident in ids), "Invalid catalogue IDs")
            require(sum(group["training_members"] for group in catalogue["groups"]) <= required_count, "Catalogue training count overflow")
            for group in catalogue["groups"]:
                require(np.asarray(group["centroid"]).shape == (24,) and np.isfinite(group["centroid"]).all() and
                        np.isfinite(group["radius"]) and group["radius"] >= 0 and 8 <= group["training_members"] <= required_count,
                        "Invalid catalogue group")
        else:
            require(bool(adapter["reason"]), "Unavailable adapter has no reason")
        adapter_proof.append(dict(variant_id=variant, training_elements=required_count,
                                  training_ids_verified=True, training_mean_std_verified=bool(adapter["available"])))
    require(set(pairs) == set(SEEDS), "Missing geometry-equivalent control pairs")
    for seed, pair in pairs.items():
        require(pair["empty_gap"] == pair["missing_band"], f"Geometry-equivalent outputs differ: seed {seed}")
    require(counts["full_archives"] == 4212 and counts["heldout_archives"] == 504, "Archive totals differ")
    return dict(schema="stmdomains-graph24-prediction-audit-v1", passed=True,
                plan_sha256=file_hash(root / "plan.json"), index_sha256=file_hash(root / "predictions/index.json"),
                auditor_sha256=file_hash(Path(__file__)), counts=dict(counts), adapters=adapter_proof,
                geometry_equivalent_pairs=[dict(seed=seed, identical_inputs_features_geometry_and_predictions=True) for seed in sorted(pairs)],
                frozen_source_hashes_checked=len(plan["code_sha256"]), opened_evaluation_or_reference_data=False,
                detection_quality_assessed=False, prediction_or_training_artifacts_modified=False,
                scope="Export contracts, input identity, support and split isolation, catalogue assignment, canonical legacy replay only")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.output.resolve()
    report = root / "audits/prediction-technical.json"
    resources = root / "prediction-audit.resources.json"
    require(not report.exists() and not resources.exists(), "Audit evidence already exists; refusing overwrite")
    deny_references()
    started, wall = time.process_time(), time.perf_counter()
    entries = complete_index(root)
    status = "failed"
    try:
        result = audit(root, entries)
        write_json(report, result)
        status = "completed"
        print(json.dumps(dict(passed=True, **result["counts"])), flush=True)
    except Exception as error:
        write_json(report, dict(schema="stmdomains-graph24-prediction-audit-v1", passed=False,
                                error_type=type(error).__name__, error=str(error), auditor_sha256=file_hash(Path(__file__))))
        raise
    finally:
        write_json(resources, dict(status=status, cpu_seconds=time.process_time() - started,
                                   wall_seconds=time.perf_counter() - wall,
                                   max_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024))


if __name__ == "__main__":
    main()
