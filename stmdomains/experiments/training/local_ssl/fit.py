"""Nine bounded issue22 fits with label-free local correspondence supervision.

All architectural and numerical choices are frozen before optimization. This
module reads analysis pixels only, never evaluation labels or synthetic truth.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform
import random
import statistics
import subprocess
import sys
import time

import numpy as np
import scipy
import torch

from ...bundle import arrays_hash, file_hash, write_json
from .. import fit as original
from ..checkpoint import config_hash, read_checkpoint, save_checkpoint
from ..data import augmented_pair
from .models import ARCHITECTURE, LocalSSL, aligned_tokens

SEEDS = original.SEEDS
VALIDATION_SEED = original.VALIDATION_SEED
PLAN_PATH = original.PLAN_PATH
MODULE = "stmdomains.experiments.training.local_ssl.fit"


def read_json(path):
    return json.loads(Path(path).read_text())


class SSLTrainingData(original.TrainingData):
    def batch(self, indices, rng, *, validation=False):
        rows = self.validation if validation else self.train
        views, shifts, scales = [], [], []
        for index in indices:
            row = rows[index]
            pair, metadata = augmented_pair(self.arrays[row["sample_id"]], row, self.normalizer, rng)
            views.append(pair)
            shifts.append([item["translation_raw_xy"] for item in metadata["transforms"]])
            scales.append(row["scale_raw_px"])
        return {"views": torch.from_numpy(np.stack(views)),
                "shifts": torch.tensor(shifts, dtype=torch.float32),
                "scales": torch.tensor(scales, dtype=torch.float32)}

    def validation_batches(self, batch_size=64):
        rng = np.random.default_rng(VALIDATION_SEED)
        return [self.batch(list(range(start, min(start + batch_size, len(self.validation)))),
                           rng, validation=True)
                for start in range(0, len(self.validation), batch_size)]

    def identity(self):
        return {**super().identity(),
                "positive_pairs": "Two independently translated/photometrically perturbed views of each same measured patch",
                "augmentation": read_json(PLAN_PATH)["augmentations"],
                "correspondence": ARCHITECTURE["correspondence"]}


def initialize(latent_dim, seed, device):
    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    torch.set_num_threads(1)
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if device == "cuda":
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA unavailable for requested fit")
        torch.cuda.manual_seed_all(seed)
    torch.use_deterministic_algorithms(True)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    model = LocalSSL(latent_dim).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=.001, weight_decay=.0001, foreach=False)
    scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, lr_lambda=lambda _: 1.)
    sampler = torch.Generator(device="cpu").manual_seed(seed + 100)
    augmentation = np.random.default_rng(seed + 200)
    return model, optimizer, scheduler, sampler, augmentation


def losses(map1, map2, shifts, scales):
    aligned = [aligned_tokens(value, shifts[:, i], scales).flatten(0, 1)
               for i, value in enumerate((map1, map2))]
    invariance = (aligned[0] - aligned[1]).square().mean()
    variance, covariance, stds = [], [], []
    for value in aligned:
        std = torch.sqrt(value.var(dim=0, unbiased=False) + 1e-4)
        stds.append(torch.sqrt(value.var(dim=0, unbiased=False)))
        variance.append(torch.relu(1 - std).mean())
        centered = value - value.mean(0)
        cov = centered.T @ centered / (len(value) - 1)
        offdiag = cov - torch.diag_embed(cov.diagonal())
        covariance.append(offdiag.square().sum() / value.shape[1])
    var, cov = torch.stack(variance).mean(), torch.stack(covariance).mean()
    std = torch.stack(stds)
    return {"loss": 25 * invariance + 25 * var + cov,
            "invariance": invariance, "variance": var, "covariance": cov,
            "std_mean": std.mean(), "std_min": std.min(), "std_max": std.max(),
            "descriptor_std_max": torch.stack([value.flatten(1).std(dim=0, unbiased=False).max()
                                                 for value in (map1, map2)]).max()}


def batch_terms(model, batch, device):
    views = batch["views"].to(device)
    maps = model(views.flatten(0, 1))["local_map"].reshape(len(views), 2, model.latent_dim, 7, 7)
    return losses(maps[:, 0], maps[:, 1], batch["shifts"].to(device), batch["scales"].to(device))


def train_step(model, optimizer, scheduler, sampler, augmentation, data, step, device):
    indices = data.sample_indices(sampler, 64)
    batch = data.batch(indices, augmentation)
    digest = arrays_hash({key: value.numpy() for key, value in batch.items()})
    optimizer.zero_grad(set_to_none=True)
    terms = batch_terms(model, batch, device)
    if not all(bool(torch.isfinite(value)) for value in terms.values()):
        raise FloatingPointError("nonfinite_loss_or_statistics")
    if min(float(terms["std_max"].detach()), float(terms["descriptor_std_max"].detach())) <= 1e-6:
        raise FloatingPointError("collapsed_SSL_representation")
    terms["loss"].backward()
    norm = torch.nn.utils.clip_grad_norm_(model.parameters(), 1., error_if_nonfinite=True, foreach=False)
    if any(p.grad is None or not bool(torch.isfinite(p.grad).all()) for p in model.parameters()):
        raise FloatingPointError("nonfinite_or_missing_gradient")
    optimizer.step()
    scheduler.step()
    return {"step": step, "batch_indices": indices, "batch_content_sha256": digest,
            **{key: float(value.detach()) for key, value in terms.items()},
            "gradient_norm_before_clip": float(norm)}


@torch.inference_mode()
def validate(model, batches, device):
    was_training = model.training
    model.eval()
    total, count = {}, 0
    try:
        for batch in batches:
            terms = batch_terms(model, batch, device)
            n = len(batch["views"])
            for key, value in terms.items():
                total[key] = total.get(key, 0.) + float(value) * n
            count += n
    finally:
        model.train(was_training)
    if not count or not np.isfinite(list(total.values())).all():
        raise FloatingPointError("missing_or_nonfinite_validation")
    return {key: value / count for key, value in total.items()} | {"elements": count}


def source_hashes():
    own = Path(__file__).parent
    paths = [own / name for name in ("models.py", "fit.py")]
    paths += [own.parent / name for name in ("fit.py", "models.py", "checkpoint.py", "data.py", "predict.py", "experiment-plan.json")]
    paths += [own.parent.parent / "bundle.py"]
    root = Path.cwd().resolve()
    return {str(path.resolve().relative_to(root)): file_hash(path) for path in paths}


def run_specs():
    return [dict(run_id=f"training/{regime}/local_ssl/z{latent}/seed-{seed}",
                 family="local_ssl", latent_dim=latent, seed=seed, regime=regime,
                 steps=2000 if regime == "transfer" else "median_selected_transfer_z32")
            for regime in ("transfer", "transductive")
            for latent in ((16, 32) if regime == "transfer" else (32,)) for seed in SEEDS]


def prepare_plan(prepared, baseline, output):
    output, baseline = Path(output), Path(baseline).resolve()
    if (output / "plan.json").exists() or any((output / spec["run_id"]).exists() for spec in run_specs()):
        raise FileExistsError("Issue22 plan or training already exists")
    registry = read_json(baseline / "training/registry.json")
    if registry["completed"] != 18 or len(registry["runs"]) != 18:
        raise ValueError("Expected the frozen18 original issue21 fits")
    prior = {"fit_count": 18,
             "fit_seconds": sum(row["seconds"] for row in registry["runs"]),
             "checkpoint_bytes": original._checkpoint_bytes(baseline / "training"),
             "registry_sha256": file_hash(baseline / "training/registry.json")}
    plan = {"schema": "stmdomains-local-ssl-plan-v1", "issue": 22,
            "architecture": ARCHITECTURE, "code_sha256": source_hashes(),
            "original_plan_sha256": file_hash(PLAN_PATH),
            "prepared": str(Path(prepared).resolve()), "baseline": str(baseline),
            "data": {regime: SSLTrainingData(prepared, regime).identity()
                     for regime in ("transfer", "transductive")},
            "runs": run_specs(), "prior21": prior,
            "caps": read_json(PLAN_PATH)["administrative_caps"],
            "maximum_new_fit_count": 9, "maximum_total_original_plan_fits": 27,
            "untrained_controls": "Step0 weights of same seed,z32 encoder; both regimes share identical initial tensors; no extra fit",
            "selection": "Fixed validation augmentation/order, minimum mean unlabelled batch loss, earliest tie; transductive fixed median of3 selected transfer z32 steps",
            "evaluation_scope": "Frozen original81 controls and TTMAPP are already viewed development data; no parameter selection from their labels",
            "additional21a_budget": "Separate; excluded from original27-fit accounting",
            "purpose": "Freeze before first issue22 optimization step"}
    write_json(output / "plan.json", plan)
    write_json(output / "training/architecture.json", {
        "architecture": ARCHITECTURE, "code_sha256": plan["code_sha256"],
        "plan_sha256": file_hash(output / "plan.json"), "expected_fit_count": 9})
    return plan


def verified_plan(prepared, baseline, output):
    output = Path(output)
    plan = read_json(output / "plan.json")
    if plan["code_sha256"] != source_hashes() or plan["original_plan_sha256"] != file_hash(PLAN_PATH):
        raise ValueError("Training implementation changed after plan freeze")
    if plan["prepared"] != str(Path(prepared).resolve()) or plan["baseline"] != str(Path(baseline).resolve()):
        raise ValueError("Input roots differ from frozen plan")
    if plan["runs"] != run_specs():
        raise ValueError("Run specifications changed")
    if file_hash(Path(baseline) / "training/registry.json") != plan["prior21"]["registry_sha256"]:
        raise ValueError("Original21 registry changed")
    return plan


def make_config(data, spec, device, steps, plan, output):
    identity = data.identity()
    if identity != plan["data"][spec["regime"]]:
        raise ValueError("Training inputs changed after plan freeze")
    return {"schema": "stmdomains-local-ssl-run-v1", "purpose": "issue22_fit",
            **spec, "architecture": ARCHITECTURE, "max_steps": steps, "device": device,
            "plan_sha256": file_hash(Path(output) / "plan.json"),
            "code_sha256": plan["code_sha256"], "data": identity,
            "batch_size": 64, "precision": "float32", "amp": False,
            "optimizer": {"name": "AdamW", "lr": .001, "weight_decay": .0001, "clip_norm": 1.},
            "scheduler": "constant", "checkpoint_interval": 100,
            "validation_seed": VALIDATION_SEED,
            "selected_on": "unlabelled_validation_loss" if data.regime == "transfer" else "fixed_last_step",
            "limits": plan["caps"]}


def fit_one(prepared, baseline, output, spec, steps, device):
    output = Path(output)
    plan = verified_plan(prepared, baseline, output)
    if spec["regime"] == "transfer":
        expected_steps = 2000
    else:
        base = [read_json(output / f"training/transfer/local_ssl/z32/seed-{seed}/run.json") for seed in SEEDS]
        if any(row["status"] != "completed" for row in base):
            raise ValueError("Transductive fit requires three completed transfer z32 runs")
        expected_steps = int(statistics.median(row["selected_step"] for row in base))
    if steps != expected_steps:
        raise ValueError("Worker step count differs from the frozen protocol")
    target = output / spec["run_id"]
    if target.exists():
        raise FileExistsError(f"Run already attempted; no replacement: {target}")
    from ..predict import deny_evaluation_paths
    deny_evaluation_paths()
    started = time.perf_counter()
    target.mkdir(parents=True)
    data = SSLTrainingData(prepared, spec["regime"])
    config = make_config(data, spec, device, steps, plan, output)
    write_json(target / "config.json", config)
    model, optimizer, scheduler, sampler, augmentation = initialize(spec["latent_dim"], spec["seed"], device)
    batches = data.validation_batches() if spec["regime"] == "transfer" else []
    validation_digest = arrays_hash({f"{i}-{key}": value.numpy() for i, batch in enumerate(batches)
                                    for key, value in batch.items()})
    write_json(target / "validation.json", {"seed": VALIDATION_SEED,
               "batch_content_sha256": validation_digest,
               "window_ids": [row["window_id"] for row in data.validation]})
    initial_state_digest = arrays_hash({name: value.detach().cpu().numpy()
                                        for name, value in model.state_dict().items()})
    progress = {"step": 0, "history": [], "validation_history": [],
                "best_validation_loss": None, "selected_step": None}
    initial_path = target / "step-0000.pt"
    save_checkpoint(initial_path, model=model, optimizer=optimizer, scheduler=scheduler,
                    sampler=sampler, np_generator=augmentation, progress=progress, config=config)
    initial_digest = file_hash(initial_path)
    if device == "cuda":
        torch.cuda.reset_peak_memory_stats()
    status, stop_reason, first100, checkpoints = "completed", "fixed_step_budget", None, []
    limits = plan["caps"]
    try:
        for step in range(1, steps + 1):
            if time.perf_counter() - started >= limits["seconds_per_fit_including_validation_and_checkpoint"]:
                status, stop_reason = "stopped", "time_cap"
                break
            record = train_step(model, optimizer, scheduler, sampler, augmentation, data, step, device)
            progress["history"].append(record)
            progress["step"] = step
            if original._rss_bytes() > limits["process_rss_bytes"] or (
                    device == "cuda" and torch.cuda.max_memory_allocated() > limits["gpu_tensor_bytes"]):
                status, stop_reason = "stopped", "memory_cap"
                break
            if step % 100 == 0 or step == steps:
                if batches:
                    value = validate(model, batches, device)
                    if min(value["std_max"], value["descriptor_std_max"]) <= 1e-6:
                        raise FloatingPointError("collapsed_SSL_validation_representation")
                    progress["validation_history"].append({"step": step, **value})
                    if progress["best_validation_loss"] is None or value["loss"] < progress["best_validation_loss"]:
                        progress["best_validation_loss"], progress["selected_step"] = value["loss"], step
                else:
                    progress["selected_step"] = step
                path = target / f"step-{step:04}.pt"
                save_checkpoint(path, model=model, optimizer=optimizer, scheduler=scheduler,
                                sampler=sampler, np_generator=augmentation, progress=progress, config=config)
                checkpoints.append({"step": step, "file": path.name, "sha256": file_hash(path),
                                    "bytes": path.stat().st_size})
                original._sync(device)
                elapsed = time.perf_counter() - started
                if step == 100:
                    first100 = elapsed
                print(json.dumps({"run_id": spec["run_id"], "step": step, "seconds": elapsed,
                                  "train_loss": record["loss"],
                                  "validation_loss": progress["validation_history"][-1]["loss"] if batches else None}), flush=True)
                write_json(target / "progress.json", {"step": step,
                           "selected_step": progress["selected_step"], "seconds": elapsed})
                if elapsed >= limits["seconds_per_fit_including_validation_and_checkpoint"]:
                    status, stop_reason = "stopped", "time_cap"
                    break
                if original._checkpoint_bytes(output / "training") + plan["prior21"]["checkpoint_bytes"] > limits["all_checkpoint_bytes"]:
                    status, stop_reason = "stopped", "checkpoint_storage_cap"
                    break
    except (RuntimeError, FloatingPointError) as exc:
        status, stop_reason = "failed", f"{type(exc).__name__}: {exc}"
    if status != "completed":
        save_checkpoint(target / "stopped.pt", model=model, optimizer=optimizer, scheduler=scheduler,
                        sampler=sampler, np_generator=augmentation, progress=progress, config=config)
    original._sync(device)
    selected = next((row for row in checkpoints if row["step"] == progress["selected_step"]), None)
    result = {"schema": "stmdomains-local-ssl-fit-v1", **spec,
              "status": status, "stop_reason": stop_reason,
              "config_hash": config_hash(config), "config_file_sha256": file_hash(target / "config.json"),
              "initial_checkpoint": initial_path.name, "initial_checkpoint_sha256": initial_digest,
              "initial_state_sha256": initial_state_digest,
              "selected_checkpoint": selected["file"] if selected and status == "completed" else None,
              "selected_checkpoint_sha256": selected["sha256"] if selected and status == "completed" else None,
              "selected_step": progress["selected_step"], "best_validation_loss": progress["best_validation_loss"],
              "completed_steps": progress["step"], "seconds": time.perf_counter() - started,
              "first100_seconds_including_setup": first100,
              "parameter_count": sum(p.numel() for p in model.parameters()),
              "training_windows": len(data.train), "validation_windows": len(data.validation),
              "validation_content_sha256": validation_digest, "checkpoints": checkpoints,
              "loss_history": progress["history"], "validation_history": progress["validation_history"],
              "peak_rss_bytes": original._rss_bytes(),
              "cuda_peak_allocated_bytes": torch.cuda.max_memory_allocated() if device == "cuda" else None,
              "cuda_peak_reserved_bytes": torch.cuda.max_memory_reserved() if device == "cuda" else None,
              "environment": {"python": platform.python_version(), "torch": torch.__version__,
                              "numpy": np.__version__, "scipy": scipy.__version__, "cuda": torch.version.cuda,
                              "gpu": torch.cuda.get_device_name() if device == "cuda" else None},
              "reference_access": False}
    write_json(target / "run.json", result)
    return result


def run_all(prepared, baseline, output, device):
    output = Path(output)
    plan = verified_plan(prepared, baseline, output)
    registry = {"schema": "stmdomains-local-ssl-suite-v1", "runs": [], "skipped": [],
                "plan_sha256": file_hash(output / "plan.json")}
    for spec in plan["runs"]:
        target = output / spec["run_id"]
        if target.exists():
            raise FileExistsError(f"A run already exists; no suite retry: {target}")
    for spec in plan["runs"]:
        if spec["regime"] == "transductive":
            base = [row for row in registry["runs"] if row["regime"] == "transfer"
                    and row["latent_dim"] == 32 and row["status"] == "completed"]
            if len(base) != 3:
                registry["skipped"].append({**spec, "reason": "fewer_than_three_successful_z32_transfer_runs"})
                continue
            steps = int(statistics.median(row["selected_step"] for row in base))
        else:
            steps = 2000
        if plan["prior21"]["fit_seconds"] + sum(row["seconds"] for row in registry["runs"]) + 900 > plan["caps"]["max_total_fit_seconds"]:
            registry["skipped"].append({**spec, "reason": "total_training_time_cap"})
            continue
        target = output / spec["run_id"]
        log = output / "logs" / (spec["run_id"].replace("/", "--") + ".log")
        log.parent.mkdir(exist_ok=True)
        print("start " + spec["run_id"], flush=True)
        started = time.perf_counter()
        command = [sys.executable, "-m", MODULE, "worker", "--prepared", str(Path(prepared).resolve()),
                   "--baseline", str(Path(baseline).resolve()), "--output", str(output.resolve()),
                   "--device", device, "--run-id", spec["run_id"], "--steps", str(steps)]
        with log.open("x") as stream:
            completed = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, check=False)
        if not (target / "run.json").exists():
            write_json(target / "run.json", {**spec, "status": "failed",
                       "stop_reason": "worker_failed_without_result", "exit_code": completed.returncode,
                       "seconds": time.perf_counter() - started, "completed_steps": None,
                       "reserved_steps_consumed": steps, "selected_step": None,
                       "selected_checkpoint": None, "selected_checkpoint_sha256": None,
                       "checkpoints": []})
        result = read_json(target / "run.json")
        row = {key: result[key] for key in ("status", "family", "latent_dim", "seed", "regime",
               "selected_step", "selected_checkpoint_sha256", "seconds", "completed_steps", "stop_reason")}
        row.update(directory=str(target.resolve()), run_json_sha256=file_hash(target / "run.json"))
        registry["runs"].append(row)
        print(json.dumps(row), flush=True)
        write_json(output / "training/registry.json", registry)
    registry.update(completed=sum(row["status"] == "completed" for row in registry["runs"]),
                    total_fit_seconds=sum(row["seconds"] for row in registry["runs"]),
                    checkpoint_bytes=original._checkpoint_bytes(output / "training"))
    registry["original21_22_total_fit_seconds"] = plan["prior21"]["fit_seconds"] + registry["total_fit_seconds"]
    registry["original21_22_total_checkpoint_bytes"] = plan["prior21"]["checkpoint_bytes"] + registry["checkpoint_bytes"]
    write_json(output / "training/registry.json", registry)
    return registry


def audit(prepared, baseline, output):
    output = Path(output)
    plan = verified_plan(prepared, baseline, output)
    registry = read_json(output / "training/registry.json")
    rows, initial_digests, validation_digests = [], {}, set()
    checkpoint_count = 0
    for entry in registry["runs"]:
        target = Path(entry["directory"])
        result = read_json(target / "run.json")
        if file_hash(target / "run.json") != entry["run_json_sha256"]:
            raise ValueError("Run metadata changed")
        if result["status"] != "completed":
            rows.append({"run_id": result["run_id"], "status": result["status"], "reason": result["stop_reason"]})
            continue
        config = read_json(target / "config.json")
        if config_hash(config) != result["config_hash"] or file_hash(target / "config.json") != result["config_file_sha256"]:
            raise ValueError("Run configuration changed")
        checkpoints = [{"file": result["initial_checkpoint"], "sha256": result["initial_checkpoint_sha256"]}] + result["checkpoints"]
        for checkpoint in checkpoints:
            if file_hash(target / checkpoint["file"]) != checkpoint["sha256"]:
                raise ValueError("Checkpoint changed")
            checkpoint_count += 1
        initial = read_checkpoint(target / result["initial_checkpoint"])
        initial_digest = arrays_hash({name: value.numpy() for name, value in initial["model"].items()})
        if initial_digest != result["initial_state_sha256"] or initial["progress"]["step"] != 0:
            raise ValueError("Initial control is not untrained")
        key = (result["latent_dim"], result["seed"])
        if key in initial_digests and initial_digests[key] != initial_digest:
            raise ValueError("Initial weights differ between regimes")
        initial_digests[key] = initial_digest
        if result["regime"] == "transfer":
            best = min(result["validation_history"], key=lambda item: (item["loss"], item["step"]))
            if best["step"] != result["selected_step"]:
                raise ValueError("Wrong validation-selected checkpoint")
            validation_digests.add(result["validation_content_sha256"])
        else:
            base = [row["selected_step"] for row in registry["runs"] if row["regime"] == "transfer"
                    and row["latent_dim"] == 32 and row["status"] == "completed"]
            if result["selected_step"] != int(statistics.median(base)) or result["selected_step"] != result["completed_steps"]:
                raise ValueError("Transductive step budget differs from predetermined transfer median")
        if result["reference_access"] is not False:
            raise ValueError("Training reference-access audit failed")
        rows.append({key: result[key] for key in ("run_id", "status", "selected_step", "completed_steps", "seconds",
                     "parameter_count", "peak_rss_bytes", "cuda_peak_allocated_bytes")})
    if len(validation_digests) != 1:
        raise ValueError("Validation inputs differ across SSL configurations")
    combined_seconds = plan["prior21"]["fit_seconds"] + sum(row["seconds"] for row in registry["runs"])
    checkpoint_bytes = original._checkpoint_bytes(output / "training")
    combined_bytes = plan["prior21"]["checkpoint_bytes"] + checkpoint_bytes
    if combined_seconds > plan["caps"]["max_total_fit_seconds"] or combined_bytes > plan["caps"]["all_checkpoint_bytes"]:
        raise ValueError("Shared original21/22 budget exceeded")
    result = {"schema": "stmdomains-local-ssl-training-audit-v1", "runs": rows,
              "completed": sum(row["status"] == "completed" for row in rows),
              "skipped": registry["skipped"], "checkpoints_verified": checkpoint_count,
              "initial_weights_identical_between_regimes": True,
              "validation_inputs_identical": True, "source_hashes_unchanged": True,
              "original21_metadata_unchanged": True, "reference_access": False,
              "steps": sum(row.get("completed_steps") or 0 for row in registry["runs"]),
              "seconds": sum(row["seconds"] for row in registry["runs"]),
              "checkpoint_bytes": checkpoint_bytes,
              "original21_22_total_seconds": combined_seconds,
              "original21_22_total_checkpoint_bytes": combined_bytes,
              "within_shared_training_caps": True}
    write_json(output / "training/training-audit.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("plan", "train", "audit", "worker"))
    parser.add_argument("--prepared", "--data", type=Path, default=Path(".scratch/training-20"))
    parser.add_argument("--baseline", type=Path, default=Path(".scratch/autoencoder-21"))
    parser.add_argument("--output", type=Path, default=Path(".scratch/local-ssl-22"))
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    parser.add_argument("--run-id")
    parser.add_argument("--steps", type=int)
    args = parser.parse_args()
    if args.stage == "plan":
        result = prepare_plan(args.prepared, args.baseline, args.output)
        print(json.dumps({"plan": str(args.output / "plan.json"), "sha256": file_hash(args.output / "plan.json"), "runs": len(result["runs"])}))
    elif args.stage == "worker":
        plan = verified_plan(args.prepared, args.baseline, args.output)
        spec = next(spec for spec in plan["runs"] if spec["run_id"] == args.run_id)
        result = fit_one(args.prepared, args.baseline, args.output, spec, args.steps, args.device)
        if result["status"] != "completed":
            raise SystemExit(1)
    elif args.stage == "train":
        run_all(args.prepared, args.baseline, args.output, args.device)
    else:
        result = audit(args.prepared, args.baseline, args.output)
        print(json.dumps({key: value for key, value in result.items() if key != "runs"}))


if __name__ == "__main__":
    main()
