"""Frozen issue25 inference and exact measurement-baseline reuse."""
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
from .prepare import verify_plan


def trial_runs(output):
    output = Path(output).resolve()
    plan = old.read_json(output / "plan.json")
    trained = old.model_runs(output / "training")
    if {run["run_id"] for run in trained} != {row["run_id"] for row in plan["run_specs"]}:
        raise ValueError("All12 planned fits must have completed outcomes; no replacement fit is allowed")
    runs = [dict(run, initial=False, baseline=False) for run in trained]
    for run in trained:
        if run["family"] != "mask50":
            continue
        other = next(value for value in trained if value["run_id"] == run["run_id"].replace("/mask50/", "/mask25/"))
        metadata = dict(run["run_metadata"])
        if metadata["initial_state_sha256"] != other["run_metadata"]["initial_state_sha256"]:
            raise ValueError("Masked ratios do not share identical initial model tensors")
        metadata.update(selected_checkpoint=metadata["initial_checkpoint"],
                        selected_checkpoint_sha256=metadata["initial_checkpoint_sha256"], selected_step=0)
        runs.append(dict(run, run_id=run["run_id"].replace("/mask50/", "/ae_untrained/"), family="ae_untrained",
                         initial=True, baseline=False, run_metadata=metadata))
    runs.extend(plan["baseline_runs"])
    if len(runs) != 32 or len({run["run_id"] for run in runs}) != 32:
        raise ValueError("Incorrect issue25 run matrix")
    return sorted(runs, key=lambda row: row["run_id"])


def encode_models(output, device, budget):
    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    import torch
    from ..models import load_model as load_ae
    from ..local_ssl.models import load_model as load_ssl
    from .models import load_model as load_masked
    output = Path(output).resolve()
    verify_plan(output, budget)
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
    for run in budget.checked(trial_runs(output)):
        if run["family"] == "fft":
            continue
        loader = load_ssl if run["family"] == "local_ssl" else load_ae if run["family"] == "ae" else load_masked
        kwargs = dict(initial=run.get("initial", False)) if loader is load_masked else {}
        model = loader(Path(run["directory"]), device=device, **kwargs)
        model.eval().requires_grad_(False)
        started = time.monotonic()
        if device == "cuda":
            torch.cuda.reset_peak_memory_stats()
        dimension = 32 * 49 if run["family"] == "local_ssl" else 32
        copied = 0
        for group in budget.checked(groups):
            path = (target / run["run_id"] / group["group_id"]).with_suffix(".npz")
            path.parent.mkdir(parents=True, exist_ok=True)
            if run["baseline"] and group["record"]["kind"] == "measurement":
                source = (Path(run["source_root"]) / "features" / run["run_id"] / group["group_id"]).with_suffix(".npz")
                shutil.copyfile(source, path)
                copied += 1
                continue
            folder = output / "cache" / group["group_id"]
            rows = old.read_json(folder / "rows.json.gz")
            with np.load(folder / (run["regime"] + ".npz"), allow_pickle=False) as data:
                indices, patches = data["available_indices"], data["patches"]
            features = np.full((len(rows), dimension), np.nan, np.float32)
            mse = np.full(len(rows), np.nan, np.float32)
            with torch.inference_mode():
                for begin in range(0, len(indices), 128):
                    chosen = indices[begin:begin + 128]
                    tensor = torch.from_numpy(patches[begin:begin + 128, None]).to(device)
                    features[chosen] = model.encode(tensor)["content"].cpu().numpy()
                    if run["family"] != "local_ssl":
                        reconstruction = model.predict(tensor)
                        mse[chosen] = (reconstruction - tensor).square().mean((1, 2, 3)).cpu().numpy()
            if device == "cuda" and torch.cuda.max_memory_allocated() > CAPS["gpu_tensor_bytes"]:
                raise MemoryError("Issue25 inference GPU tensor cap exceeded")
            np.savez_compressed(path, features=features, angle_radians=np.full(len(rows), np.nan, np.float32),
                                reconstruction_mse=mse)
        if device == "cuda":
            torch.cuda.synchronize()
        summary = dict(run, descriptor_dimension=dimension, inference_seconds=time.monotonic() - started,
                       unmasked_inference=True, reused_measurement_feature_archives=copied,
                       peak_gpu_bytes=int(torch.cuda.max_memory_allocated()) if device == "cuda" else 0)
        write_json(target / run["run_id"] / "complete.json", summary)
        completed.append(summary)
        print("encoded", run["run_id"], flush=True)
        del model
    write_json(target / "index.json", completed)
    return dict(model_runs=len(completed))


def fit_adapter(output, run, groups, scale, sampler, budget):
    values, edges, ids, offset = [], [], [], 0
    for group in budget.checked(groups):
        if group["record"]["kind"] != "measurement":
            continue
        rows = old.read_json(output / "cache" / group["group_id"] / "rows.json.gz")
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
        raise ValueError("No eligible measurement training descriptors")
    adapter = fit_feature_adapter(np.concatenate(values), np.asarray(edges, int).reshape(-1, 2), ids,
                                  scope=dict(regime=run["regime"], scale_px=scale, sampler=sampler, feature_id=run["run_id"]))
    adapter["fit_window_ids"] = ids
    return adapter


def export_partition(output, group, rows, run, method, features, adapter, order_pass, acf,
                     threshold, folder, hashes, *, heldout=False):
    """Shared full/test-only export; unavailable and out-of-test IDs remain explicit."""
    ids = [row["element_id"] for row in rows]
    xy = np.asarray([np.asarray(row["raw_edge_xy"]) * row["pixel_spacing_xy"] for row in rows]).reshape(-1, 2)
    scope = np.asarray([row["transfer_split"] == "test" for row in rows], bool) if heldout else np.ones(len(rows), bool)
    indices = np.flatnonzero(scope)
    edges = indices[neighbor_edges(xy[scope], [ids[i] for i in indices], mode=group["sampler"], stride=STRIDE)]
    scoped_features = features.copy()
    scoped_features[~scope] = np.nan
    result = partition_graph(ids, edges, scoped_features, adapter, method=method, order_pass=order_pass & scope,
                             min_size=4 if group["sampler"] == "grid" else 8)
    for index in np.flatnonzero(~scope):
        result["reasons"][index] = "outside_transfer_test"
    prefix = "heldout-" if heldout else ""
    relations = folder / (prefix + "relations.json.gz")
    old.write_gzip(relations, old.relation_records(rows, edges, result), compresslevel=1)
    payload = old.result_envelope(group, rows, run, method, result, acf, threshold, hashes,
                                  dict(path=relations.name, sha256=file_hash(relations)))
    extension = payload["extensions"]["training_v1"]
    extension["protocol_id"] = "stmdomains-masked-ae25-plan-v1"
    extension["elements"] = [normalize_element(row, kind=group["record"]["kind"]) for row in rows]
    if heldout:
        extension["graph_context"] = "eligible_transfer_test_only"
    old.write_gzip(folder / (prefix + "result.json.gz"), payload, compresslevel=1)
    np.savez_compressed(folder / (prefix + "metrics-input.npz"),
                        before=old.label_numbers(result["proposal_component_ids"]),
                        after=old.label_numbers(result["final_component_ids"]), edges=edges, acf_score=acf,
                        available=np.asarray([row["available"] for row in rows], bool))


def partition_all(output, budget):
    output = Path(output).resolve()
    plan = verify_plan(output, budget)
    target = output / "predictions"
    if target.exists():
        raise FileExistsError(target)
    target.mkdir()
    groups = old.read_json(output / "cache/index.json")
    thresholds = old.read_json(output / "cache/order-thresholds.json")
    hashes = dict(plan_sha256=file_hash(output / "plan.json"), split_sha256=file_hash(Path(plan["data_root"]) / "split.json"))
    index, copied = [], []
    for run in trial_runs(output):
        for scale in SCALES:
            for sampler in ("grid", "centers"):
                budget.check()
                selected = [group for group in groups if group["scale_px"] == scale and group["sampler"] == sampler]
                adapter_path = target / run["run_id"] / sampler / f"s{scale}" / "adapter.json"
                adapter_path.parent.mkdir(parents=True, exist_ok=True)
                if run["baseline"]:
                    source = Path(run["source_root"]) / adapter_path.relative_to(output)
                    shutil.copyfile(source, adapter_path)
                    adapter = old.read_json(adapter_path)
                else:
                    adapter = fit_adapter(output, run, selected, scale, sampler, budget)
                    write_json(adapter_path, adapter)
                if adapter["scope"] != dict(regime=run["regime"], scale_px=scale, sampler=sampler, feature_id=run["run_id"]):
                    raise ValueError("Adapter scope mismatch")
                current_hashes = dict(hashes, adapter_sha256=file_hash(adapter_path),
                                      checkpoint_sha256=run.get("run_metadata", {}).get("selected_checkpoint_sha256"))
                for group in budget.checked(selected):
                    rows = old.read_json(output / "cache" / group["group_id"] / "rows.json.gz")
                    heldout = run["regime"] == "transfer" and group["record"]["kind"] == "measurement"
                    reused = run["baseline"] and group["record"]["kind"] == "measurement"
                    if not reused:
                        feature = old.load_features(output, run, group)
                        with np.load(output / "cache" / group["group_id"] / (run["regime"] + ".npz"), allow_pickle=False) as cache:
                            order_pass, acf = cache["order_pass"], cache["acf_score"]
                    for method in ("fh4", "mws"):
                        folder = target / run["run_id"] / sampler / f"s{scale}" / group["record"]["sample_id"] / method
                        if reused:
                            source = Path(run["source_root"]) / folder.relative_to(output)
                            folder.mkdir(parents=True)
                            names = [prefix + name for prefix in (("", "heldout-") if heldout else ("",))
                                     for name in ("result.json.gz", "relations.json.gz", "metrics-input.npz")]
                            for name in names:
                                shutil.copyfile(source / name, folder / name)
                                copied.append(dict(source=str(source / name), target=str((folder / name).relative_to(output)),
                                                   sha256=file_hash(source / name)))
                        else:
                            for is_heldout in (False, True) if heldout else (False,):
                                export_partition(output, group, rows, run, method, feature, adapter, order_pass, acf,
                                                 thresholds["scales"][str(scale)]["threshold"], folder, current_hashes, heldout=is_heldout)
                        index.append(dict(run_id=run["run_id"], regime=run["regime"], family=run["family"],
                                          latent=run["latent"], seed=run["seed"], scale_px=scale, sampler=sampler,
                                          sample_id=group["record"]["sample_id"], kind=group["record"]["kind"],
                                          pixel_spacing_xy=group["record"]["pixel_spacing_xy"], partition=method,
                                          directory=str(folder.relative_to(output)),
                                          evaluation_input="heldout-metrics-input.npz" if heldout else "metrics-input.npz",
                                          cache_group=group["group_id"], baseline_reused_measurement=bool(reused)))
                print("partitioned", run["run_id"], sampler, scale, flush=True)
    if len(index) != 44928:
        raise ValueError("Incomplete planned prediction matrix")
    write_json(target / "index.json", index)
    write_json(output / "baseline-prediction-copies.json", dict(schema="stmdomains-masked25-baseline-copies-v1", files=copied))
    return dict(full_predictions=len(index), copied_baseline_files=len(copied),
                heldout_archives=sum(row["evaluation_input"] == "heldout-metrics-input.npz" for row in index))


def freeze(output, budget):
    from ..export_contract import finalize
    output = Path(output).resolve()
    plan = verify_plan(output, budget)
    if (output / "frozen-predictions.json").exists():
        raise FileExistsError("Predictions already frozen")
    if len(old.read_json(output / "predictions/index.json")) != 44928:
        raise ValueError("Complete prediction index required")
    finalize(output)
    files = {}
    for path in budget.checked(sorted(output.rglob("*"))):
        if path.is_file() and "evaluation" not in path.relative_to(output).parts and not any(part.startswith(".") for part in path.relative_to(output).parts):
            files[str(path.relative_to(output))] = file_hash(path)
    external = {name: digest for name, digest in plan["source_files"].items() if not Path(name).is_relative_to(output)}
    value = dict(schema="stmdomains-frozen-predictions-v1", evaluation_opened=False, files=files,
                 external_files=external, code_sha256=plan["code_sha256"], prediction_count=44928,
                 plan_sha256=file_hash(output / "plan.json"),
                 policy="Fresh controls and known measurements; truth opened only after full prediction freeze")
    write_json(output / "frozen-predictions.json", value)
    return dict(local_files=len(files), external_files=len(external))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("encode", "partition", "freeze"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", default="cuda")
    args = parser.parse_args()
    old.deny_evaluation_paths()
    with reporting_stage(args.output, args.stage) as budget:
        result = encode_models(args.output, args.device, budget) if args.stage == "encode" else \
            partition_all(args.output, budget) if args.stage == "partition" else freeze(args.output, budget)
        print(result, flush=True)


if __name__ == "__main__":
    main()
