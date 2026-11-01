"""Issue26 frozen/teacher inference, shared graph exports and hash-only freeze."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import time

import numpy as np

from ...bundle import file_hash, write_json
from .. import predict as old
from ..data import SCALES, STRIDE
from ..export_contract import normalize_element
from ..partition import fit_feature_adapter, neighbor_edges, partition_graph
from .common import CAPS, reporting_stage
from .prepare import DINO_SHA256, verify_plan


def trial_runs(output):
    """Require completed suite accounting, not successful replacement fits."""
    output = Path(output).resolve()
    plan = old.read_json(output / "plan.json")
    registry = old.read_json(output / "training/registry.json")
    expected = {row["run_id"]: row for row in plan["run_specs"]}
    if not registry.get("suite_finished") or set(registry["planned_run_ids"]) != set(expected):
        raise ValueError("Adaptation suite must record every planned outcome before inference")
    outcomes = registry["outcomes"]
    if len(outcomes) != 6 or {row["run_id"] for row in outcomes} != set(expected):
        raise ValueError("Missing or repeated adaptation outcome")
    runs, omitted = list(plan["baseline_runs"]), []
    for outcome in outcomes:
        ident = outcome["run_id"]
        if outcome["status"] != "completed":
            if not outcome.get("reason"):
                raise ValueError("Failed/skipped adaptation requires an explicit reason")
            omitted.append(dict(run_id=ident, status=outcome["status"], reason=outcome["reason"]))
            continue
        spec = expected[ident]
        directory = output / "training" / ident
        if Path(outcome["directory"]).resolve() != directory.resolve():
            raise ValueError("Registry run directory differs from the plan")
        metadata = old.read_json(directory / "run.json")
        if metadata["status"] != "completed" or metadata["completed_steps"] != 1000 or not metadata.get("selected_checkpoint_sha256"):
            raise ValueError("Completed teacher run lacks its declared1000-step checkpoint")
        if metadata["run_id"] != ident:
            raise ValueError("Adaptation run identity changed")
        if outcome.get("run_sha256") and outcome["run_sha256"] != file_hash(directory / "run.json"):
            raise ValueError("Adaptation report changed after suite accounting")
        # The full training history stays in its authenticated run.json, rather
        # than being duplicated into every feature/matrix bookkeeping file.
        summary_fields = ("status", "run_id", "completed_steps", "selected_step", "selected_checkpoint",
                          "selected_checkpoint_sha256", "initial_checkpoint", "initial_checkpoint_sha256",
                          "base_checkpoint_sha256", "base_state_sha256", "initial_state_sha256", "config_hash", "config_file_sha256",
                          "family", "regime", "seed", "latent_dim")
        run_metadata = {name: metadata[name] for name in summary_fields if name in metadata}
        runs.append(dict(run_id=ident, regime=spec["regime"], family="dino_adapted", latent=384,
                         seed=spec["seed"], directory=str(directory.resolve()), run_metadata=run_metadata,
                         run_report_sha256=file_hash(directory / "run.json"),
                         selected_role="teacher", baseline=False))
    if len(runs) != 10 - len(omitted) or len({run["run_id"] for run in runs}) != len(runs):
        raise ValueError("Incorrect actual representation matrix")
    runs = sorted(runs, key=lambda row: row["run_id"])
    transfer_count = sum(run["regime"] == "transfer" for run in runs)
    matrix = dict(schema="stmdomains-pretrained26-actual-matrix-v1", runs=runs, omitted_adaptations=omitted,
                  completed_adaptations=len(runs) - 4, all_planned_adaptations_completed=not omitted,
                  models=len(runs), full_predictions=len(runs) * 1404,
                  heldout_archives=transfer_count * 288, test_frame_heldout_archives=transfer_count * 228,
                  empty_non_test_heldout_archives=transfer_count * 60,
                  adapter_count=len(runs) * 6, maximum_models=10, maximum_full_predictions=14040,
                  maximum_heldout_archives=1440, source_labels_used=False,
                  qualification_policy="Missing adaptation seeds prevent three-seed qualification; no replacement fit")
    return runs, matrix


def encode_models(output, device, budget):
    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    os.environ.setdefault("XFORMERS_DISABLED", "1")
    import torch
    from .models import load_frozen, load_model
    output = Path(output).resolve()
    plan = verify_plan(output, budget)
    runs, matrix = trial_runs(output)
    target = output / "features"
    if target.exists():
        raise FileExistsError(target)
    target.mkdir()
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    groups = old.read_json(output / "cache/index.json")
    completed = []
    for run in budget.checked(runs):
        if run["family"] == "fft":
            continue
        model = load_frozen(Path(plan["assets_root"]), device=device) if run["family"] == "dino_frozen" else \
            load_model(Path(run["directory"]), device=device, role="teacher")
        model.eval().requires_grad_(False)
        started = time.monotonic()
        if device == "cuda":
            torch.cuda.reset_peak_memory_stats()
        for group in budget.checked(groups):
            path = (target / run["run_id"] / group["group_id"]).with_suffix(".npz")
            path.parent.mkdir(parents=True, exist_ok=True)
            folder = output / "cache" / group["group_id"]
            rows = old.read_json(folder / "rows.json.gz")
            with np.load(folder / (run["regime"] + ".npz"), allow_pickle=False) as cache:
                indices, patches = cache["available_indices"], cache["patches"]
            features = np.full((len(rows), 384), np.nan, np.float32)
            with torch.inference_mode():
                for begin in range(0, len(indices), 64):
                    tensor = torch.from_numpy(patches[begin:begin + 64, None]).to(device)
                    encoded = model.encode(tensor)["content"]
                    if encoded.shape != (len(tensor), 384) or not bool(torch.isfinite(encoded).all()):
                        raise ValueError("Non-finite or wrongly shaped DINO representation")
                    features[indices[begin:begin + 64]] = encoded.cpu().numpy()
            if device == "cuda" and torch.cuda.max_memory_allocated() > CAPS["gpu_tensor_bytes"]:
                raise MemoryError("Issue26 inference GPU tensor cap exceeded")
            np.savez_compressed(path, features=features)
        if device == "cuda":
            torch.cuda.synchronize()
        summary = dict(run, descriptor_dimension=384, inference_seconds=time.monotonic() - started,
                       input_transform=plan["input_transform"], inference_batch_size=64,
                       fresh_inference=True, source_labels_used=False,
                       peak_gpu_bytes=int(torch.cuda.max_memory_allocated()) if device == "cuda" else 0)
        write_json(target / run["run_id"] / "complete.json", summary)
        completed.append(summary)
        print("encoded", run["run_id"], flush=True)
        del model
    write_json(target / "index.json", completed)
    write_json(target / "actual-matrix.json", matrix)
    return dict(model_runs=len(completed), omitted_adaptations=matrix["omitted_adaptations"])


def fit_adapter(output, run, groups, scale, sampler, rows_cache, budget):
    values, edges, ids, offset = [], [], [], 0
    for group in budget.checked(groups):
        if group["record"]["kind"] != "measurement":
            continue
        rows = rows_cache[group["group_id"]]
        chosen = [i for i, row in enumerate(rows) if row["available"] and
                  (run["regime"] == "transductive" or row["transfer_split"] == "train")]
        if not chosen:
            continue
        values.append(old.load_features(output, run, group)[chosen])
        current_ids = [rows[i]["window_id"] for i in chosen]
        xy = np.asarray([rows[i]["raw_edge_xy"] for i in chosen])
        edges.extend((neighbor_edges(xy, current_ids, mode=sampler, stride=STRIDE) + offset).tolist())
        ids.extend(current_ids)
        offset += len(chosen)
    if not values:
        raise ValueError("No eligible measured training features")
    adapter = fit_feature_adapter(np.concatenate(values), np.asarray(edges, int).reshape(-1, 2), ids,
        scope=dict(regime=run["regime"], scale_px=scale, sampler=sampler, feature_id=run["run_id"]))
    adapter["fit_window_ids"] = ids
    return adapter


def graph_for(rows, sampler, heldout=False):
    ids = [row["element_id"] for row in rows]
    xy = np.asarray([np.asarray(row["raw_edge_xy"]) * row["pixel_spacing_xy"] for row in rows]).reshape(-1, 2)
    scope = np.asarray([row["transfer_split"] == "test" for row in rows], bool) if heldout else np.ones(len(rows), bool)
    indices = np.flatnonzero(scope)
    edges = indices[neighbor_edges(xy[scope], [ids[i] for i in indices], mode=sampler, stride=STRIDE)]
    return scope, edges


def export_partition(output, group, rows, run, method, features, adapter, order_pass, acf,
                     threshold, folder, hashes, *, heldout=False, graph=None):
    """Normalize/validate once at write; retain states in NPZ for evaluation."""
    scope, edges = graph_for(rows, group["sampler"], heldout) if graph is None else graph
    scoped_features = features.copy()
    scoped_features[~scope] = np.nan
    result = partition_graph([row["element_id"] for row in rows], edges, scoped_features, adapter,
                             method=method, order_pass=order_pass & scope, min_size=4 if group["sampler"] == "grid" else 8)
    for index in np.flatnonzero(~scope):
        result["reasons"][index] = "outside_transfer_test"
    prefix = "heldout-" if heldout else ""
    relations = folder / (prefix + "relations.json.gz")
    old.write_gzip(relations, old.relation_records(rows, edges, result), compresslevel=1)
    normalized_rows = [normalize_element(row, kind=group["record"]["kind"]) for row in rows]
    payload = old.result_envelope(group, normalized_rows, run, method, result, acf, threshold, hashes,
                                  dict(path=relations.name, sha256=file_hash(relations)))
    extension = payload["extensions"]["training_v1"]
    extension["protocol_id"] = "stmdomains-pretrained-ssl26-plan-v1"
    extension["selected_model_role"] = run.get("selected_role")
    extension["graph_context"] = "eligible_transfer_test_only" if heldout else "full_field_context"
    old.write_gzip(folder / (prefix + "result.json.gz"), payload, compresslevel=1)
    np.savez_compressed(folder / (prefix + "metrics-input.npz"),
        before=old.label_numbers(result["proposal_component_ids"]), after=old.label_numbers(result["final_component_ids"]),
        edges=edges, acf_score=acf, available=np.asarray([row["available"] for row in rows], bool),
        states=np.asarray([row["state"] for row in payload["assignments"]], dtype="U32"))


def partition_all(output, budget):
    output = Path(output).resolve()
    plan = verify_plan(output, budget)
    runs, matrix = trial_runs(output)
    if old.read_json(output / "features/actual-matrix.json") != matrix:
        raise ValueError("Adaptation outcomes changed after feature extraction")
    target = output / "predictions"
    if target.exists():
        raise FileExistsError(target)
    target.mkdir()
    groups = old.read_json(output / "cache/index.json")
    thresholds = old.read_json(output / "cache/order-thresholds.json")
    rows_cache, graph_cache, gate_cache = {}, {}, {}
    for group in budget.checked(groups):
        gid = group["group_id"]
        rows = old.read_json(output / "cache" / gid / "rows.json.gz")
        rows_cache[gid] = rows
        for heldout in (False, True) if group["record"]["kind"] == "measurement" else (False,):
            graph_cache[gid, heldout] = graph_for(rows, group["sampler"], heldout)
        for regime in ("transfer", "transductive"):
            with np.load(output / "cache" / gid / (regime + ".npz"), allow_pickle=False) as archive:
                gate_cache[gid, regime] = (archive["order_pass"], archive["acf_score"])
    hashes = dict(plan_sha256=file_hash(output / "plan.json"), split_sha256=file_hash(Path(plan["data_root"]) / "split.json"))
    index, copied = [], []
    for run in budget.checked(runs):
        for scale in SCALES:
            for sampler in ("grid", "centers"):
                selected = [group for group in groups if group["scale_px"] == scale and group["sampler"] == sampler]
                adapter_path = target / run["run_id"] / sampler / f"s{scale}" / "adapter.json"
                adapter_path.parent.mkdir(parents=True, exist_ok=True)
                if run["family"] == "fft":
                    shutil.copyfile(Path(plan["baseline_fft_root"]) / adapter_path.relative_to(output), adapter_path)
                    adapter = old.read_json(adapter_path)
                else:
                    adapter = fit_adapter(output, run, selected, scale, sampler, rows_cache, budget)
                    write_json(adapter_path, adapter)
                if adapter["scope"] != dict(regime=run["regime"], scale_px=scale, sampler=sampler, feature_id=run["run_id"]):
                    raise ValueError("Feature adapter scope differs")
                checkpoint_sha = DINO_SHA256 if run["family"] == "dino_frozen" else run.get("run_metadata", {}).get("selected_checkpoint_sha256")
                current_hashes = dict(hashes, adapter_sha256=file_hash(adapter_path), checkpoint_sha256=checkpoint_sha)
                for group in budget.checked(selected):
                    gid = group["group_id"]
                    rows = rows_cache[gid]
                    heldout = run["regime"] == "transfer" and group["record"]["kind"] == "measurement"
                    reused = run["family"] == "fft" and group["record"]["kind"] == "measurement"
                    if not reused:
                        feature = old.load_features(output, run, group)
                        order_pass, acf = gate_cache[gid, run["regime"]]
                    for method in ("fh4", "mws"):
                        folder = target / run["run_id"] / sampler / f"s{scale}" / group["record"]["sample_id"] / method
                        if reused:
                            source = Path(plan["baseline_fft_root"]) / folder.relative_to(output)
                            folder.mkdir(parents=True)
                            for prefix in ("", "heldout-") if heldout else ("",):
                                for name in ("result.json.gz", "relations.json.gz", "metrics-input.npz"):
                                    filename = prefix + name
                                    shutil.copyfile(source / filename, folder / filename)
                                    copied.append(dict(source=str(source / filename), target=str((folder / filename).relative_to(output)), sha256=file_hash(source / filename)))
                        else:
                            for is_heldout in (False, True) if heldout else (False,):
                                export_partition(output, group, rows, run, method, feature, adapter, order_pass, acf,
                                    thresholds["scales"][str(scale)]["threshold"], folder, current_hashes,
                                    heldout=is_heldout, graph=graph_cache[gid, is_heldout])
                        index.append(dict(run_id=run["run_id"], regime=run["regime"], family=run["family"],
                            latent=run["latent"], seed=run["seed"], scale_px=scale, sampler=sampler,
                            sample_id=group["record"]["sample_id"], kind=group["record"]["kind"],
                            pixel_spacing_xy=group["record"]["pixel_spacing_xy"], partition=method,
                            directory=str(folder.relative_to(output)), evaluation_input="heldout-metrics-input.npz" if heldout else "metrics-input.npz",
                            cache_group=gid, baseline_reused_measurement=bool(reused), selected_model_role=run.get("selected_role")))
                print("partitioned", run["run_id"], sampler, scale, flush=True)
    if len(index) != matrix["full_predictions"] or sum(row["evaluation_input"].startswith("heldout-") for row in index) != matrix["heldout_archives"]:
        raise ValueError("Incomplete actual prediction matrix")
    write_json(target / "index.json", index)
    write_json(target / "actual-matrix.json", matrix)
    write_json(output / "baseline-prediction-copies.json", dict(schema="stmdomains-pretrained26-baseline-copies-v1", files=copied))
    return dict(full_predictions=len(index), heldout_archives=matrix["heldout_archives"],
                copied_baseline_files=len(copied), omitted_adaptations=matrix["omitted_adaptations"])


def freeze(output, budget):
    output = Path(output).resolve()
    plan = verify_plan(output, budget)
    _, matrix = trial_runs(output)
    if (output / "frozen-predictions.json").exists():
        raise FileExistsError("Predictions already frozen")
    if old.read_json(output / "predictions/actual-matrix.json") != matrix:
        raise ValueError("Prediction matrix differs from completed adaptation outcomes")
    audit = old.read_json(output / "prediction-audit.json")
    if not audit["passed"] or audit["index_sha256"] != file_hash(output / "predictions/index.json") or audit["plan_sha256"] != file_hash(output / "plan.json"):
        raise ValueError("Completed independent export audit required before freeze")
    files = {}
    for path in budget.checked(sorted(output.rglob("*"))):
        relative = path.relative_to(output)
        if path.is_file() and "evaluation" not in relative.parts and not any(part.startswith(".") for part in relative.parts):
            files[str(relative)] = file_hash(path)
    external = {name: value for name, value in plan["source_files"].items() if not Path(name).is_relative_to(output)}
    result = dict(schema="stmdomains-frozen-predictions-v1", evaluation_opened=False, files=files,
        external_files=external, code_sha256=plan["code_sha256"], prediction_count=matrix["full_predictions"],
        actual_matrix_sha256=file_hash(output / "predictions/actual-matrix.json"), plan_sha256=file_hash(output / "plan.json"),
        export_policy="Normalized and validated at write; independent audit parses every JSON once; freeze hashes bytes only",
        policy="Fresh known-family controls and known measurements; no reference opened until complete actual prediction freeze")
    write_json(output / "frozen-predictions.json", result)
    return dict(local_files=len(files), external_files=len(external), prediction_count=matrix["full_predictions"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("encode", "partition", "freeze"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    args = parser.parse_args()
    old.deny_evaluation_paths()
    with reporting_stage(args.output, args.stage) as budget:
        result = encode_models(args.output, args.device, budget) if args.stage == "encode" else \
            partition_all(args.output, budget) if args.stage == "partition" else freeze(args.output, budget)
        print(result, flush=True)


if __name__ == "__main__":
    main()
