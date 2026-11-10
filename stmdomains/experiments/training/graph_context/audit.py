"""Technical audit of trial24a; no reference reads or detection-quality tests."""
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
import torch

from ...bundle import file_hash, write_json
from ..graph_ssl.data import descriptor, iter_prepared, prepare_sample
from ..graph_ssl.models import GraphSSL
from .representation import build_inputs, dependency_audit


MODES = ("closed72", "halfopen72", "root_only")
KEYS = ("x", "adj", "valid", "node_indices")
EPS = 1e-10
TOLERANCE = 1e-5


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def arrays(path):
    with np.load(path, allow_pickle=False) as archive:
        return {key: archive[key] for key in archive.files}


def deny_references():
    def hook(event, args):
        if event == "open" and isinstance(args[0], (str, bytes, os.PathLike)):
            name = os.fsdecode(args[0]).replace("\\", "/")
            if "/evaluation/" in name or "/references/" in name or "manual_domain" in name:
                raise PermissionError("Reference read forbidden to context audit: " + name)
    sys.addaudithook(hook)


def check_budget(root, started):
    used = sum(read(path)["cpu_seconds"] for path in root.glob("*resources.json"))
    require(used + time.process_time() - started <= 1800, "Trial24a CPU budget exhausted")
    require(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024 <= 4 * 1024**3, "Trial24a RSS cap exceeded")


def variant_matrix():
    neural = [f"transfer-graph_{state}-{seed}" for seed in (20261101, 20261102, 20261103)
              for state in ("sce_scale", "untrained")]
    return {**{f"{mode}--{base}": (mode, base) for mode in MODES for base in neural},
            "root57--transfer-geometry": ("root57", "transfer-geometry")}


def check_inputs(sample, value, mode):
    """Independent selection, padding and pinned-radius checks on each root."""
    n = len(sample["ids"])
    shapes = dict(x=(n, 128, 57), adj=(n, 128, 128), valid=(n, 128), node_indices=(n, 128))
    require(set(value) == set(KEYS), "Unexpected representation fields")
    for key in KEYS:
        require(value[key].shape == shapes[key], "Invalid representation shape: " + key)
    require(value["x"].dtype == np.float32 and value["adj"].dtype == bool and
            value["valid"].dtype == bool and value["node_indices"].dtype.kind in "iu", "Invalid representation dtype")
    require(np.isfinite(value["x"]).all(), "Non-finite representation")
    require(np.array_equal(value["valid"].any(axis=1), sample["eligible"]), "Fixed S24 changed")
    require(np.all(value["x"][~value["valid"]] == 0) and np.all(value["node_indices"][~value["valid"]] == -1),
            "Nonempty padding")
    require(np.array_equal(value["adj"], value["adj"].transpose(0, 2, 1)), "Asymmetric adjacency")
    require(np.all(~value["adj"] | (value["valid"][:, :, None] & value["valid"][:, None, :])), "Padding has edges")
    for root in np.flatnonzero(sample["eligible"]):
        original = sample["node_indices"][root, sample["valid"][root]]
        expected = original
        if mode == "halfopen72":
            expected = np.asarray([index for index in original
                                   if all(-36. - EPS <= delta < 36. - EPS
                                          for delta in sample["xyref"][index] - sample["xyref"][root])])
        elif mode == "root_only":
            expected = np.asarray([root])
        count = len(expected)
        require(0 < count <= 128 and expected[0] == root, "Invalid root/context cardinality")
        require(np.array_equal(value["node_indices"][root, value["valid"][root]], expected), "Context selection differs")
        require(np.array_equal(value["valid"][root], np.arange(128) < count), "Noncontiguous padding")
        require(np.array_equal(value["x"][root, 0], sample["x"][root, 0]), "Root57 changed")
        points = sample["xyref"][expected]
        distances = np.linalg.norm(points[:, None] - points[None, :], axis=-1)
        expected_adj = distances <= float(sample["adjacency_radius"][root]) + EPS
        require(np.array_equal(value["adj"][root, :count, :count], expected_adj), "Closed72 radius was not preserved")
        expected_x = sample["x"][root, :1] if mode == "root_only" else descriptor(points)
        require(np.array_equal(value["x"][root, :count], expected_x), "Descriptor differs from selected raw centers")
    if mode == "closed72":
        require(all(np.array_equal(value[key], sample[key]) for key in KEYS), "Closed72 cache changed")


def check_dependency(sample, value, dependency):
    """BFS plus geometric certificate, independent of implementation traversal."""
    n = len(sample["ids"])
    require(set(dependency) == {"two_hop_node_count", "required_box_ref", "complete_inside_ego72"},
            "Unexpected dependency audit fields")
    require(dependency["two_hop_node_count"].shape == (n,) and dependency["required_box_ref"].shape == (n, 4) and
            dependency["complete_inside_ego72"].shape == (n,), "Invalid dependency shapes")
    spacing = np.asarray(sample["record"]["pixel_spacing_xy"])
    measured = sample["arrays"]["measured"]
    height, width = measured.shape
    for root in range(n):
        if not sample["eligible"][root]:
            require(dependency["two_hop_node_count"][root] == 0 and
                    np.isnan(dependency["required_box_ref"][root]).all() and
                    not dependency["complete_inside_ego72"][root], "Unavailable root has dependency certificate")
            continue
        reachable = {0}
        for _ in range(2):
            reachable = {int(j) for i in reachable for j in np.flatnonzero(value["adj"][root, i])}
        points = sample["xyref"][value["node_indices"][root, sorted(reachable)]]
        box = np.r_[points.min(axis=0) - 24., points.max(axis=0) + 24.]
        require(dependency["two_hop_node_count"][root] == len(reachable) and
                np.array_equal(dependency["required_box_ref"][root], box), "Dependency extent differs")
        delta_low = box[:2] - sample["xyref"][root]
        delta_high = box[2:] - sample["xyref"][root]
        raw = box / np.tile(spacing, 2)
        complete = bool(np.all(delta_low >= -36. - EPS) and np.all(delta_high < 36. - EPS) and
                        np.all(box[:2] >= -EPS) and np.all(box[2:] < np.array([width, height]) * spacing - EPS))
        if complete:
            complete = bool(np.all(raw[:2] >= 0) and np.all(raw[2:] <= [width, height]))
            if complete:
                x0, y0 = np.floor(raw[:2]).astype(int)
                x1, y1 = np.ceil(raw[2:]).astype(int)
                complete = bool(measured[y0:y1, x0:x1].all())
        require(bool(dependency["complete_inside_ego72"][root]) == complete, "Dependency completeness differs")


def toy_sample(points, ids=None):
    points = np.asarray(points, float)
    ids = np.asarray(ids if ids is not None else [f"toy-{i:04d}" for i in range(len(points))])
    record = dict(sample_id="technical-toy", kind="synthetic", pixel_spacing_xy=[1., 1.], position_unit="px")
    raw = dict(image=np.zeros((256, 256), np.float32), measured=np.ones((256, 256), bool),
               centers_xy=points, object_ids=ids, boxes_xyxy=np.c_[points - 1, points + 1])
    packed, rows = prepare_sample(record, raw)
    return dict(packed, arrays=raw, record=record, rows=rows, ids=ids)


@torch.inference_mode()
def encode(model, value, selected, *, trim=True, batch_size=32):
    outputs = []
    for start in range(0, len(selected), batch_size):
        indices = selected[start:start + batch_size]
        width = int(value["valid"][indices].sum(axis=1).max()) if trim else 128
        x = torch.from_numpy(value["x"][indices, :width])
        adj = torch.from_numpy(value["adj"][indices, :width, :width])
        valid = torch.from_numpy(value["valid"][indices, :width])
        outputs.append(model.encode(x, adj, valid)[:, 0].numpy())
    return np.concatenate(outputs) if outputs else np.empty((0, 32), np.float32)


def load_frozen_model(path):
    # The existing checkpoint contains training state, but no optimizer object
    # is constructed/restored and only its frozen model tensors are used.
    state = torch.load(path, map_location="cpu", weights_only=False)
    model = GraphSSL()
    model.load_state_dict(state["model"])
    model.requires_grad_(False)
    model.eval()
    return model


def toy_audit(model):
    grid = np.asarray([[128. + x, 128. + y] for y in range(-36, 37, 12) for x in range(-36, 37, 12)])
    sample = toy_sample(grid)
    root = int(np.flatnonzero(np.all(grid == [128., 128.], axis=1))[0])
    permutation = np.random.default_rng(24001).permutation(len(grid))
    permuted = toy_sample(grid[permutation], sample["ids"][permutation])
    shifted = toy_sample(grid + [.5, -.25], sample["ids"])
    inverse = np.argsort(permutation)
    counts = {}
    for mode in MODES:
        value = build_inputs(sample, mode)
        check_inputs(sample, value, mode)
        dependency = dependency_audit(sample, value)
        check_dependency(sample, value, dependency)
        moved = build_inputs(shifted, mode)
        reordered = build_inputs(permuted, mode)
        for key in ("x", "adj", "valid"):
            require(np.array_equal(value[key], moved[key]), "Toy translation changed " + key)
            require(np.array_equal(value[key], reordered[key][inverse]), "Toy permutation changed " + key)
        counts[mode] = int(value["valid"][root].sum())
        one = encode(model, value, np.array([root]), trim=True)
        batch = encode(model, value, np.array([root, 0, len(grid) - 1]), trim=False)
        np.testing.assert_allclose(one[0], batch[0], rtol=TOLERANCE, atol=TOLERANCE)
        node_perm = np.r_[0, np.arange(127, 0, -1)]
        shuffled = dict(value, x=value["x"][:, node_perm], valid=value["valid"][:, node_perm],
                        adj=value["adj"][:, node_perm][:, :, node_perm])
        np.testing.assert_allclose(one, encode(model, shuffled, np.array([root]), trim=False),
                                   rtol=TOLERANCE, atol=TOLERANCE)
        extended = toy_sample(np.vstack([grid, [164. + 2 * EPS, 129.]]),
                              np.concatenate([sample["ids"], np.asarray(["outside"])]))
        outside = build_inputs(extended, mode)
        for key in ("x", "adj", "valid"):
            require(np.array_equal(value[key][root], outside[key][root]), "Out-of-window annotation entered root input")
    require(counts == dict(closed72=49, halfopen72=36, root_only=1), "Toy endpoint convention differs")
    # The positive endpoint contains a dense cluster. Removing it would change
    # median NN; halfopen must retain the smaller CLOSED radius nevertheless.
    dense = toy_sample(np.asarray([[128., 128.], [116., 128.], [140., 128.], [128., 116.], [128., 140.]] +
                                 [[164., 128. + j] for j in range(-5, 6)]))
    half = build_inputs(dense, "halfopen72")
    check_inputs(dense, half, "halfopen72")
    require(dense["adjacency_radius"][0] < 2 and half["adj"][0].sum() == half["valid"][0].sum(),
            "Pinned-radius toy did not retain self-only adjacency")
    overflow = toy_sample(np.c_[128 + np.linspace(-1, 1, 129), np.full(129, 128.)])
    require(not overflow["eligible"].any(), "Overflow toy was incorrectly eligible")
    for mode in MODES:
        check_inputs(overflow, build_inputs(overflow, mode), mode)
    return dict(passed=True, endpoint_root_node_counts=counts,
                checks=["independent_input_reconstruction", "two_hop_dependency_certificate", "annotation_permutation",
                        "binary_fraction_translation", "outside_window_annotation_isolation", "batch_composition_and_padding",
                        "model_node_permutation", "pinned_closed_radius_after_dense_edge_removal", "128_node_overflow_remains_unavailable"],
                inference_atol=TOLERANCE, inference_rtol=TOLERANCE)


def catalogue_groups(features, adapter):
    result = np.zeros(len(features), np.int32)
    finite = np.flatnonzero(np.isfinite(features).all(axis=1))
    groups = adapter.get("catalogue", {}).get("groups", [])
    if not adapter["available"] or not groups or not len(finite):
        return result
    projected = ((features[finite] - adapter["mean"]) / adapter["std"] - adapter["pca_mean"]) @ np.asarray(adapter["components"]).T
    distance = np.linalg.norm(projected[:, None] - np.asarray([group["centroid"] for group in groups]), axis=2)
    nearest = distance.argmin(axis=1)
    for index, group in enumerate(groups):
        accepted = (nearest == index) & (distance[:, index] <= group["radius"])
        result[finite[accepted]] = group["id"]
    return result


def check_export(root, sample, entry, old_entry, groups, gate):
    path = (root / entry["file"]).resolve()
    require(path.is_relative_to(root) and path.is_file(), "Prediction path escapes trial root or is missing")
    value = arrays(path)
    n = len(sample["ids"])
    expected_keys = {"before", "after", "edges", "states", "reasons", "score", "edge_distances",
                     "relation_kinds", "relation_strengths", "descriptor_group"}
    require(set(value) == expected_keys, "Unexpected prediction array fields")
    for key in ("before", "after", "states", "reasons", "score", "descriptor_group"):
        require(value[key].shape == (n,), "Prediction root count changed: " + key)
    require(np.array_equal(value["edges"], old_entry["edges"]), "Fixed partition graph changed")
    require(np.array_equal(value["score"], old_entry["score"], equal_nan=True), "Frozen geometry score changed")
    for key in ("edge_distances", "relation_kinds", "relation_strengths"):
        require(value[key].shape == (len(value["edges"]),), "Edge array shape differs")
    for key in ("before", "after"):
        require(value[key].dtype.kind in "iu" and np.all(value[key] >= 0) and
                np.all(value[key][~sample["eligible"]] == 0), "Prediction assigned outside S24")
    assigned = value["after"] > 0
    require(np.all(gate[assigned]), "Assignment bypassed the frozen geometry gate")
    expected_states = np.where(~sample["eligible"], "insufficient_data", np.where(assigned, "ordered_untyped", "ambiguous"))
    require(np.array_equal(value["states"], expected_states), "Prediction state/availability differs")
    require(np.all(value["reasons"][assigned] == "") and np.all(value["reasons"][~assigned] != ""), "Missing refusal reason")
    require(np.array_equal(value["descriptor_group"], groups), "Frozen catalogue assignment differs")
    for index in np.flatnonzero(~sample["eligible"]):
        require(value["reasons"][index] == sample["rows"][index]["unavailable_reason"], "Support refusal reason changed")
    with gzip.open(path.with_suffix(".json.gz"), "rt", encoding="utf-8") as stream:
        payload = json.load(stream)
    require(payload["sample_id"] == sample["sample_id"] and payload["input_content_sha256"] == sample["record"]["content_sha256"] and
            payload["run_id"] == entry["variant_id"] + "-" + entry["partition"] and payload["catalogue_id"] is None,
            "Export identity differs")
    ext = payload["extensions"]["graph24"]
    require(ext["elements"] == sample["rows"] and ext["material"] is None, "Source ID/support rows changed")
    for key in ("variant_id", "base_variant_id", "mode", "partition", "regime", "family", "sample_id"):
        require(ext["metadata"][key] == entry[key], "Export metadata differs: " + key)
    require(ext["descriptor_catalogue"] == "adapters/" + entry["variant_id"] + ".json", "Wrong frozen catalogue link")
    require(len(payload["assignments"]) == n, "Export dropped S24 rows")
    for i, (assignment, row) in enumerate(zip(payload["assignments"], sample["rows"])):
        expected = dict(element_id=row["element_id"], xy=row["raw_edge_xy"], support_xyxy=row["support_xyxy"],
                        state=str(value["states"][i]), reason=None if assigned[i] else str(value["reasons"][i]),
                        type_id=None, domain_id=int(value["after"][i]) or None, orientation_deg=None)
        require(assignment == expected, "JSON/NPZ assignment mismatch")
    return n


def audit(root, started):
    plan = read(root / "plan.json")
    source = Path(plan["source_root"]).resolve()
    require(plan["optimizer_steps"] == 0 and plan["calibration_fits"] == 0 and plan["device"] == "cpu",
            "Plan permits undeclared fitting or device")
    require(file_hash(Path(plan["protocol"])) == plan["protocol_sha256"], "Frozen protocol changed")
    require(file_hash(source / "frozen-predictions.json") == plan["initial_source_freeze_sha256"], "Source24 freeze changed")
    for name, digest in plan["code_sha256"].items():
        require(file_hash(Path(name)) == digest, "Frozen trial24a source changed: " + name)
    for name, digest in plan["source_files"].items():
        require(file_hash(Path(name)) == digest, "Pinned source24 artifact changed: " + name)
    require(not (root / "training").exists(), "Trial24a unexpectedly contains training outputs")
    execution = read(root / "execution.json")
    require(execution["optimizer_steps"] == 0 and execution["calibration_fits"] == 0 and
            execution["optimizer_steps_forbidden"] is True and execution["inference_mode"] is True and
            execution["weights_require_grad"] is False and execution["reference_access"] is False and
            execution["device"] == "cpu" and execution["prediction_entries"] == 3534,
            "Runtime evidence violates frozen inference-only scope")
    entries = read(root / "predictions/index.json")
    matrix = variant_matrix()
    require(len(entries) == 3534 and Counter(row["variant_id"] for row in entries) == Counter({key: 186 for key in matrix}),
            "Incomplete prediction matrix")
    require(len({entry["file"] for entry in entries}) == 3534 and all("heldout_file" not in entry for entry in entries),
            "Duplicate archive or unexpected TTMAPP/heldout result")
    by_sample = defaultdict(list)
    for entry in entries:
        require((entry["mode"], entry["base_variant_id"]) == matrix[entry["variant_id"]] and
                entry["kind"] == "synthetic", "Incorrect indexed variant identity")
        by_sample[entry["sample_id"]].append(entry)
    source_entries = {(row["sample_id"], row["variant_id"], row["partition"]): row
                      for row in read(source / "predictions/index.json")}
    runs = {row["variant_id"]: row for row in read(source / "features/runs.json")}
    bases = sorted({base for mode, base in matrix.values()} - {"transfer-geometry"})
    checkpoints = {base: Path(runs[base]["checkpoint"]) for base in bases}
    model = load_frozen_model(checkpoints[bases[0]])
    toys = toy_audit(model)
    del model
    adapters = {}
    for variant, (mode, base) in matrix.items():
        path = root / "adapters" / (variant + ".json")
        require(file_hash(path) == file_hash(source / "adapters" / (base + ".json")), "Adapter was refitted or modified")
        adapters[variant] = read(path)
        require(adapters[variant]["training_elements"] == 76 and len(adapters[variant]["training_ids"]) == 76,
                "Transfer adapter training IDs changed")
    counts = Counter()
    replay_samples = []
    for sample in iter_prepared(source, kind="synthetic"):
        check_budget(root, started)
        sid = sample["sample_id"]
        geometry_path = root / "geometry" / (sid + ".npz")
        require(file_hash(geometry_path) == file_hash(source / "geometry" / (sid + ".npz")),
                "Frozen geometry was modified")
        gate = arrays(geometry_path)["gate"]
        rows = by_sample.pop(sid, [])
        require(len(rows) == 38 and {(row["variant_id"], row["partition"]) for row in rows} ==
                {(variant, method) for variant in matrix for method in ("fh4", "mws")}, "Incomplete sample matrix")
        for mode in MODES:
            value = arrays(root / "representations" / mode / (sid + ".npz"))
            check_inputs(sample, value, mode)
            dep = arrays(root / "dependency" / mode / (sid + ".npz"))
            check_dependency(sample, value, dep)
            if mode == "root_only":
                require(np.array_equal(dep["complete_inside_ego72"], sample["eligible"]), "Root-only B24 unexpectedly incomplete")
            counts[mode + "_dependency_roots_checked"] += int(sample["eligible"].sum())
            if mode == "closed72" and len(replay_samples) < 3:
                replay_samples.append((sid, value, np.flatnonzero(sample["eligible"])))
        features, group_labels = {}, {}
        for variant, (mode, base) in matrix.items():
            path = root / "features" / variant / (sid + ".npz")
            cache = arrays(path)
            require(set(cache) == {"features"}, "Unexpected feature cache fields")
            features[variant] = cache["features"]
            require(features[variant].shape == (len(sample["ids"]), 57 if mode == "root57" else 32) and
                    np.isfinite(features[variant][sample["eligible"]]).all() and
                    np.isnan(features[variant][~sample["eligible"]]).all(), "Feature shape or S24 availability changed")
            group_labels[variant] = catalogue_groups(features[variant], adapters[variant])
            if mode in ("closed72", "root57"):
                require(file_hash(path) == file_hash(source / "features" / base / (sid + ".npz")), "Baseline features are not an exact copy")
                counts["baseline_feature_archives_bitwise"] += 1
        for entry in rows:
            mode, base = matrix[entry["variant_id"]]
            original = source_entries[(sid, base, entry["partition"])]
            old = arrays(source / original["file"])
            counts["assignment_rows_checked"] += check_export(root, sample, entry, old, group_labels[entry["variant_id"]], gate)
            if mode in ("closed72", "root57"):
                require(file_hash(root / entry["file"]) == file_hash(source / original["file"]), "Baseline NPZ is not a bitwise copy")
                counts["baseline_prediction_archives_bitwise"] += 1
            counts["prediction_archives"] += 1
        counts["samples"] += 1
        counts["source_anchors"] += len(sample["ids"])
        counts["fixed_S24"] += int(sample["eligible"].sum())
        if counts["samples"] % 12 == 0:
            print("audited", counts["samples"], "context samples", flush=True)
    require(not by_sample and counts["samples"] == 93 and counts["fixed_S24"] == 8350 and
            counts["baseline_prediction_archives_bitwise"] == 1302 and counts["baseline_feature_archives_bitwise"] == 651,
            "Final matrix or fixed S24 totals differ")
    cpu_replay = []
    for base in bases:
        check_budget(root, started)
        model = load_frozen_model(checkpoints[base])
        for sid, value, selected in replay_samples:
            actual = encode(model, value, selected)
            expected = arrays(source / "features" / base / (sid + ".npz"))["features"][selected]
            np.testing.assert_allclose(actual, expected, atol=TOLERANCE, rtol=TOLERANCE)
            cpu_replay.append(dict(base_variant_id=base, sample_id=sid, roots=len(selected),
                                   maximum_absolute_difference=float(np.max(np.abs(actual - expected))) if len(selected) else 0.))
        del model
    for name, digest in plan["source_files"].items():
        require(file_hash(Path(name)) == digest, "Source24 changed during audit: " + name)
    require(file_hash(source / "frozen-predictions.json") == plan["initial_source_freeze_sha256"], "Source24 freeze changed during audit")
    return dict(schema="stmdomains-graph-context-audit-v1", passed=True, counts=dict(counts), toy=toys,
                closed_cpu_replay=cpu_replay, closed_cpu_replay_atol=TOLERANCE, closed_cpu_replay_rtol=TOLERANCE,
                pinned_source_artifacts_verified=len(plan["source_files"]), adapters_bitwise_verified=len(adapters),
                auditor_sha256=file_hash(Path(__file__)), plan_sha256=file_hash(root / "plan.json"),
                index_sha256=file_hash(root / "predictions/index.json"), optimizer_objects_created=0, optimizer_steps_in_audit=0,
                execution_evidence=execution,
                historical_optimizer_activity="Audit verifies unchanged checkpoints and absent training outputs; trial runtime guard is separate evidence",
                opened_evaluation_or_reference_data=False, detection_quality_assessed=False,
                dependency_certificate_used_as_filter=False, source24_modified=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.output.resolve()
    report, resources = root / "audits/technical.json", root / "audit.resources.json"
    require(not report.exists() and not resources.exists(), "Audit evidence already exists; refusing overwrite")
    deny_references()
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    require((root / "predictions/index.json").is_file(), "Predictions incomplete: final index is missing")
    require(len(read(root / "predictions/index.json")) == 3534, "Predictions incomplete: expected3534 entries")
    started, wall = time.process_time(), time.perf_counter()
    status = "failed"
    try:
        check_budget(root, started)
        result = audit(root, started)
        check_budget(root, started)
        write_json(report, result)
        status = "completed"
        print(json.dumps(dict(passed=True, **result["counts"])), flush=True)
    except Exception as error:
        write_json(report, dict(schema="stmdomains-graph-context-audit-v1", passed=False,
                                error_type=type(error).__name__, error=str(error), auditor_sha256=file_hash(Path(__file__))))
        raise
    finally:
        write_json(resources, dict(status=status, cpu_seconds=time.process_time() - started,
                                   wall_seconds=time.perf_counter() - wall,
                                   max_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024))


if __name__ == "__main__":
    main()
