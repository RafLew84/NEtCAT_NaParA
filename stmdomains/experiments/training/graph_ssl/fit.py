"""Bounded, label-free graph24 fits with complete local checkpoints.

The parent experiment freezes plan.json before any scientific fit. This worker
does not read evaluation data, choose graph parameters or retry failed runs.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import resource
import statistics
import sys
import tempfile
import time

import numpy as np
import torch

from ...bundle import arrays_hash, file_hash, write_json
from ..checkpoint import capture_rng, config_hash, load_checkpoint, read_checkpoint, save_checkpoint
from .models import ARCHITECTURE, GraphSSL, predict_features, reconstruction_loss, sample_mask


SEEDS = (20261101, 20261102, 20261103)
VALIDATION_SEED = 2401901
CAPS = {"steps_per_transfer_fit": 2000,
        "seconds_per_fit_including_validation_and_checkpoint": 900,
        "gpu_tensor_bytes": 8 * 1024**3, "process_rss_bytes": 12 * 1024**3,
        "all_checkpoint_bytes": 10 * 1024**3,
        "maximum_fit_count": 9, "max_total_fit_seconds": 8100}


def read_json(path):
    return json.loads(Path(path).read_text())


def preparation_root(root):
    root = Path(root).resolve()
    return root / "prepared" if (root / "prepared/manifest.json").exists() else root


def deny_evaluation_paths():
    def audit(event, args):
        if event == "open" and isinstance(args[0], (str, bytes, os.PathLike)):
            path = os.fsdecode(args[0]).replace("\\", "/")
            if "/evaluation/" in path or "/references/" in path or "manual_domain" in path:
                raise PermissionError(f"Reference data denied to graph training: {path}")
    sys.addaudithook(audit)


def graph_digest(graphs):
    digest = hashlib.sha256()
    for graph in graphs:
        digest.update(str(graph["graph_id"]).encode())
        for key in ("x", "adj", "valid"):
            value = np.ascontiguousarray(graph[key])
            digest.update(key.encode())
            digest.update(str((value.shape, str(value.dtype))).encode())
            digest.update(value.tobytes())
    return digest.hexdigest()


class GraphTrainingData:
    def __init__(self, root, regime):
        from .data import load_training_graphs
        if regime not in ("transfer", "transductive"):
            raise ValueError("Unknown graph training regime")
        self.root, self.regime = preparation_root(root), regime
        train = load_training_graphs(self.root, regime, "train")
        validation = load_training_graphs(self.root, regime, "validation") if regime == "transfer" else []
        self.train = sorted((g for g in train if np.count_nonzero(g["valid"]) >= 2), key=lambda g: g["graph_id"])
        self.validation = sorted((g for g in validation if np.count_nonzero(g["valid"]) >= 2), key=lambda g: g["graph_id"])
        self.excluded = {"train_fewer_than_two_nodes": len(train) - len(self.train),
                         "validation_fewer_than_two_nodes": len(validation) - len(self.validation)}
        if not self.train or (regime == "transfer" and not self.validation):
            raise ValueError("No eligible training or validation graph contexts")
        self.frames = sorted({g["frame_id"] for g in self.train})
        self.frame_indices = {frame: [i for i, g in enumerate(self.train) if g["frame_id"] == frame]
                              for frame in self.frames}

    def identity(self):
        return {"prepared": str(self.root), "regime": self.regime,
                "manifest_sha256": file_hash(self.root / "manifest.json"),
                "train_graphs": len(self.train), "validation_graphs": len(self.validation),
                "excluded": self.excluded,
                "train_per_frame": dict(sorted(Counter(str(g["frame_id"]) for g in self.train).items())),
                "validation_per_frame": dict(sorted(Counter(str(g["frame_id"]) for g in self.validation).items())),
                "train_content_sha256": graph_digest(self.train),
                "validation_content_sha256": graph_digest(self.validation)}

    def sample_indices(self, generator, batch_size=64):
        indices = []
        for _ in range(batch_size):
            frame = self.frames[int(torch.randint(len(self.frames), (), generator=generator))]
            available = self.frame_indices[frame]
            indices.append(available[int(torch.randint(len(available), (), generator=generator))])
        return indices

    def batch(self, indices, mask_rng, *, validation=False):
        rows = self.validation if validation else self.train
        graphs = [rows[i] for i in indices]
        result = {key: torch.from_numpy(np.stack([g[key] for g in graphs]))
                  for key in ("x", "adj", "valid")}
        if validation:
            masks = []
            for graph in graphs:
                seed = VALIDATION_SEED ^ int(hashlib.sha256(graph["graph_id"].encode()).hexdigest()[:16], 16)
                masks.append(sample_mask(np.asarray(graph["valid"])[None], np.random.default_rng(seed))[0])
            result["masked"] = torch.stack(masks)
        else:
            result["masked"] = sample_mask(result["valid"], mask_rng)
        return result

    def validation_batches(self):
        return [self.batch(list(range(start, min(start + 64, len(self.validation)))), None, validation=True)
                for start in range(0, len(self.validation), 64)]


def initialize(seed, device):
    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    torch.set_num_threads(1)
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if device == "cuda":
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA unavailable")
        torch.cuda.manual_seed_all(seed)
    torch.use_deterministic_algorithms(True)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    model = GraphSSL().to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=.001, weight_decay=.0001, foreach=False)
    scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, lambda _: 1.)
    sampler = torch.Generator(device="cpu").manual_seed(seed + 100)
    mask_rng = np.random.default_rng(seed + 200)
    return model, optimizer, scheduler, sampler, mask_rng


def batch_terms(model, batch, device, loss_name):
    b = {key: value.to(device) for key, value in batch.items()}
    x, valid = b["x"].float(), b["valid"].bool()
    output = model(x, b["adj"], valid, b["masked"].bool())
    return reconstruction_loss(output["reconstruction"], x, b["masked"].bool(), valid, loss_name)


def train_step(model, optimizer, scheduler, sampler, mask_rng, data, step, device, loss_name):
    indices = data.sample_indices(sampler)
    batch = data.batch(indices, mask_rng)
    digest = arrays_hash({key: value.numpy() for key, value in batch.items()})
    optimizer.zero_grad(set_to_none=True)
    terms = batch_terms(model, batch, device, loss_name)
    if not all(bool(torch.isfinite(value)) for value in terms.values()):
        raise FloatingPointError("nonfinite_graph_loss")
    record = {"step": step, "batch_indices": indices, "batch_content_sha256": digest,
              **{key: float(value.detach()) for key, value in terms.items()}}
    if not int(terms["masked_informative_nodes"]):
        return {**record, "optimizer_step": False, "skip_reason": "no_informative_masked_targets",
                "gradient_norm_before_clip": None}
    terms["loss"].backward()
    norm = torch.nn.utils.clip_grad_norm_(model.parameters(), 1., error_if_nonfinite=True, foreach=False)
    if any(p.grad is None or not bool(torch.isfinite(p.grad).all()) for p in model.parameters()):
        raise FloatingPointError("nonfinite_or_missing_graph_gradient")
    optimizer.step()
    scheduler.step()
    return {**record, "optimizer_step": True, "skip_reason": None,
            "gradient_norm_before_clip": float(norm)}


@torch.inference_mode()
def validate(model, batches, device, loss_name):
    was_training = model.training
    model.eval()
    sce_sum = scale_sum = masked = informative = distance_slots = 0.
    try:
        for batch in batches:
            terms = batch_terms(model, batch, device, loss_name)
            n, slots = float(terms["masked_nodes"]), float(terms["observed_distance_slots"])
            info = float(terms["masked_informative_nodes"])
            sce_sum += float(terms["sce"]) * info
            scale_sum += float(terms["scale_mse"]) * slots
            masked += n
            informative += info
            distance_slots += slots
    finally:
        model.train(was_training)
    if not informative:
        raise FloatingPointError("No informative masked validation targets")
    sce = sce_sum / informative
    scale = scale_sum / max(distance_slots, 1.)
    loss = sce + scale if loss_name == "sce_scale" else sce
    if not np.isfinite([sce, scale, loss]).all():
        raise FloatingPointError("Nonfinite graph validation")
    return {"loss": loss, "sce": sce, "scale_mse": scale,
            "masked_nodes": int(masked), "masked_informative_nodes": int(informative),
            "masked_zero_target_nodes": int(masked - informative),
            "observed_distance_slots": int(distance_slots)}


def source_hashes():
    own = Path(__file__).parent
    paths = [own / name for name in ("models.py", "fit.py", "data.py")]
    paths += [own.parent / "checkpoint.py", own.parent.parent / "bundle.py"]
    root = Path.cwd().resolve()
    return {str(path.resolve().relative_to(root)): file_hash(path) for path in paths}


def run_specs():
    return [dict(run_id=f"training/{regime}/{loss}/seed-{seed}", family="graph_ssl",
                 loss_name=loss, latent_dim=32, regime=regime, seed=seed)
            for regime in ("transfer", "transductive")
            for loss in (("sce", "sce_scale") if regime == "transfer" else ("sce_scale",))
            for seed in SEEDS]


def verified_plan(data_root, output):
    plan_path = Path(output) / "plan.json"
    plan = read_json(plan_path)
    own_hashes = source_hashes()
    if any(plan["code_sha256"].get(name) != digest for name, digest in own_hashes.items()):
        raise ValueError("Graph training code differs from frozen plan")
    for name, digest in plan["code_sha256"].items():
        if file_hash(Path(name)) != digest:
            raise ValueError(f"Frozen code changed: {name}")
    manifest = preparation_root(data_root) / "manifest.json"
    if file_hash(manifest) != plan["data_manifest_sha256"]:
        raise ValueError("Graph data manifest differs from frozen plan")
    if plan.get("training_caps", CAPS) != CAPS:
        raise ValueError("Graph training caps differ from implementation")
    return plan


def rss_bytes():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024


def checkpoint_bytes(output):
    return sum(p.stat().st_size for p in (Path(output) / "training").rglob("*.pt"))


def sync(device):
    if device == "cuda":
        torch.cuda.synchronize()


def fit_one(data_root, output, regime, loss_name, seed, steps, device="cuda"):
    output = Path(output).resolve()
    plan = verified_plan(data_root, output)
    spec = next((s for s in run_specs() if (s["regime"], s["loss_name"], s["seed"]) ==
                 (regime, loss_name, seed)), None)
    if spec is None:
        raise ValueError("Run is not in the frozen nine-fit graph matrix")
    if regime == "transfer":
        expected = CAPS["steps_per_transfer_fit"]
    else:
        transfer = [read_json(output / f"training/transfer/sce_scale/seed-{s}/run.json") for s in SEEDS]
        if any(r["status"] != "completed" for r in transfer):
            raise ValueError("Transduction requires three successful primary transfer fits")
        expected = int(statistics.median(r["selected_step"] for r in transfer))
    if steps != expected:
        raise ValueError(f"Expected exactly {expected} steps, received {steps}")
    previous = [read_json(p) for p in (output / "training").rglob("run.json")]
    if len(previous) >= 9 or sum(r["seconds"] for r in previous) + 900 > CAPS["max_total_fit_seconds"]:
        raise RuntimeError("Graph fit count or total time cap exceeded")
    target = output / spec["run_id"]
    if target.exists():
        raise FileExistsError("Graph run already attempted; no implicit retries")
    deny_evaluation_paths()
    started = time.perf_counter()
    target.mkdir(parents=True)
    data = GraphTrainingData(data_root, regime)
    identity = data.identity()
    config = {"schema": "stmdomains-graph24-run-config-v1", **spec, "architecture": ARCHITECTURE,
              "max_steps": steps, "device": device, "data": identity,
              "plan_sha256": file_hash(output / "plan.json"), "code_sha256": plan["code_sha256"],
              "batch_size": 64, "precision": "float32", "amp": False,
              "optimizer": {"name": "AdamW", "lr": .001, "weight_decay": .0001, "clip_norm": 1.},
              "scheduler": "constant", "checkpoint_interval": 100, "caps": CAPS,
              "validation_seed": VALIDATION_SEED,
              "selection": "minimum_fixed_unlabelled_validation_loss_earliest_tie" if regime == "transfer" else "fixed_last_step"}
    write_json(target / "config.json", config)
    model, optimizer, scheduler, sampler, mask_rng = initialize(seed, device)
    batches = data.validation_batches()
    validation_digest = arrays_hash({f"{i}-{key}": value.numpy() for i, b in enumerate(batches)
                                    for key, value in b.items()})
    write_json(target / "validation.json", {"seed": VALIDATION_SEED,
               "graph_ids": [g["graph_id"] for g in data.validation], "batch_content_sha256": validation_digest})
    initial_digest = arrays_hash({name: value.detach().cpu().numpy() for name, value in model.state_dict().items()})
    progress = {"step": 0, "history": [], "validation_history": [],
                "best_validation_loss": None, "selected_step": None}

    def save(path):
        save_checkpoint(path, model=model, optimizer=optimizer, scheduler=scheduler,
                        sampler=sampler, np_generator=mask_rng, progress=progress, config=config)

    initial_path = target / "step-0000.pt"
    save(initial_path)
    if device == "cuda":
        torch.cuda.reset_peak_memory_stats()
    checkpoints, first100 = [], None
    status, stop_reason = "completed", "fixed_step_budget"
    try:
        for step in range(1, steps + 1):
            if time.perf_counter() - started >= 900:
                status, stop_reason = "stopped", "time_cap"
                break
            record = train_step(model, optimizer, scheduler, sampler, mask_rng, data, step, device, loss_name)
            progress["history"].append(record)
            progress["step"] = step
            if rss_bytes() > CAPS["process_rss_bytes"] or (device == "cuda" and
                    torch.cuda.max_memory_allocated() > CAPS["gpu_tensor_bytes"]):
                status, stop_reason = "stopped", "memory_cap"
                break
            if step % 100 == 0 or step == steps:
                if batches:
                    value = validate(model, batches, device, loss_name)
                    progress["validation_history"].append({"step": step, **value})
                    if progress["best_validation_loss"] is None or value["loss"] < progress["best_validation_loss"]:
                        progress["best_validation_loss"], progress["selected_step"] = value["loss"], step
                else:
                    progress["selected_step"] = step
                path = target / f"step-{step:04d}.pt"
                save(path)
                checkpoints.append({"step": step, "file": path.name, "sha256": file_hash(path), "bytes": path.stat().st_size})
                sync(device)
                elapsed = time.perf_counter() - started
                if step == 100:
                    first100 = elapsed
                print(json.dumps({"run_id": spec["run_id"], "step": step, "seconds": elapsed,
                                  "train_loss": record["loss"],
                                  "validation_loss": progress["validation_history"][-1]["loss"] if batches else None}), flush=True)
                write_json(target / "progress.json", {"step": step, "selected_step": progress["selected_step"], "seconds": elapsed})
                if elapsed >= 900:
                    status, stop_reason = "stopped", "time_cap"
                    break
                if checkpoint_bytes(output) > CAPS["all_checkpoint_bytes"]:
                    status, stop_reason = "stopped", "checkpoint_storage_cap"
                    break
    except (RuntimeError, FloatingPointError) as exc:
        status, stop_reason = "failed", f"{type(exc).__name__}: {exc}"
    if status != "completed":
        save(target / "stopped.pt")
    sync(device)
    chosen = next((r for r in checkpoints if r["step"] == progress["selected_step"]), None)
    result = {"schema": "stmdomains-graph24-fit-v1", **spec, "status": status, "stop_reason": stop_reason,
              "config_hash": config_hash(config), "config_file_sha256": file_hash(target / "config.json"),
              "initial_checkpoint": initial_path.name, "initial_checkpoint_sha256": file_hash(initial_path),
              "initial_state_sha256": initial_digest,
              "selected_checkpoint": chosen["file"] if chosen and status == "completed" else None,
              "selected_checkpoint_sha256": chosen["sha256"] if chosen and status == "completed" else None,
              "selected_step": progress["selected_step"], "best_validation_loss": progress["best_validation_loss"],
              "completed_steps": progress["step"], "seconds": time.perf_counter() - started,
              "completed_optimizer_steps": sum(r["optimizer_step"] for r in progress["history"]),
              "skipped_uninformative_steps": sum(not r["optimizer_step"] for r in progress["history"]),
              "first100_seconds_including_setup": first100,
              "parameter_count": sum(p.numel() for p in model.parameters()),
              "training_graphs": len(data.train), "validation_graphs": len(data.validation),
              "data_exclusions": data.excluded, "validation_content_sha256": validation_digest,
              "checkpoints": checkpoints, "loss_history": progress["history"],
              "validation_history": progress["validation_history"], "peak_rss_bytes": rss_bytes(),
              "cuda_peak_allocated_bytes": torch.cuda.max_memory_allocated() if device == "cuda" else None,
              "cuda_peak_reserved_bytes": torch.cuda.max_memory_reserved() if device == "cuda" else None,
              "environment": {"python": platform.python_version(), "torch": torch.__version__,
                              "numpy": np.__version__, "cuda": torch.version.cuda,
                              "gpu": torch.cuda.get_device_name() if device == "cuda" else None},
              "reference_access": False}
    write_json(target / "run.json", result)
    return result


def load_encoder(checkpoint, device="cpu"):
    state = read_checkpoint(checkpoint)
    model = GraphSSL().to(device)
    model.load_state_dict(state["model"])
    model.eval()
    return model, state["config"]


def preflight(data_root, output, device="cpu", *, resume_check=False):
    """Technical audit; default does zero optimizer steps and never writes a fit."""
    deny_evaluation_paths()
    data = GraphTrainingData(data_root, "transfer")
    initialized = initialize(SEEDS[0], device)
    model, optimizer, scheduler, sampler, mask_rng = initialized
    batch = data.batch(data.sample_indices(sampler, 4), mask_rng)
    initial = arrays_hash({k: v.detach().cpu().numpy() for k, v in model.state_dict().items()})
    first = batch_terms(model, batch, device, "sce_scale")
    first["loss"].backward()
    gradients = {name: p.grad.detach().cpu().clone() for name, p in model.named_parameters()}
    optimizer.zero_grad(set_to_none=True)
    second = batch_terms(model, batch, device, "sce_scale")
    second["loss"].backward()
    deterministic = torch.equal(first["loss"], second["loss"]) and all(
        torch.equal(gradients[name], p.grad.detach().cpu()) for name, p in model.named_parameters())
    unchanged = initial == arrays_hash({k: v.detach().cpu().numpy() for k, v in model.state_dict().items()})
    rng = np.random.default_rng(24004)
    permutation = torch.from_numpy(rng.permutation(batch["x"].shape[1]))
    inverse = torch.argsort(permutation)
    with torch.inference_mode():
        b = {k: v.to(device) for k, v in batch.items()}
        reference = model.encode(b["x"], b["adj"], b["valid"])
        permuted = model.encode(b["x"][:, permutation], b["adj"][:, permutation][:, :, permutation], b["valid"][:, permutation])[:, inverse]
        delta = float((reference - permuted).abs().max())
        amplitude = reconstruction_loss(b["x"] * 2., b["x"], b["masked"], b["valid"], "sce_scale")
    result = {"schema": "stmdomains-graph24-preflight-v1", "data": data.identity(),
              "code_sha256": source_hashes(), "device": device,
              "deterministic_forward_backward": deterministic, "weights_unchanged": unchanged,
              "permutation_max_absolute_difference": delta, "permutation_tolerance": 1e-5,
              "amplitude_doubled_sce": float(amplitude["sce"]),
              "amplitude_doubled_distance_mse": float(amplitude["scale_mse"]),
              "optimizer_steps": 0, "parameter_count": sum(p.numel() for p in model.parameters()),
              "peak_rss_bytes": rss_bytes(), "reference_access": False}
    if resume_check:
        result["resume"] = audit_resume(data, device)
        result["optimizer_steps"] = result["resume"]["optimizer_steps"]
    result["passed"] = bool(deterministic and unchanged and delta <= 1e-5
                            and result["amplitude_doubled_sce"] < 1e-10
                            and result["amplitude_doubled_distance_mse"] > 0
                            and (not resume_check or result["resume"]["passed"]))
    write_json(output, result)
    if not result["passed"]:
        raise RuntimeError("Graph technical preflight failed")
    return result



def state_equal(first, second):
    if isinstance(first, torch.Tensor):
        return isinstance(second, torch.Tensor) and torch.equal(first, second)
    if isinstance(first, np.ndarray):
        return isinstance(second, np.ndarray) and np.array_equal(first, second)
    if isinstance(first, dict):
        return isinstance(second, dict) and first.keys() == second.keys() and all(
            state_equal(first[k], second[k]) for k in first)
    if isinstance(first, (list, tuple)):
        return type(first) is type(second) and len(first) == len(second) and all(
            state_equal(a, b) for a, b in zip(first, second))
    return first == second

def audit_resume(data, device):
    """6 continuous versus3+checkpoint+3 steps, using the same declared data."""
    def run(state, first, last):
        model, optimizer, scheduler, sampler, rng = state
        return [train_step(model, optimizer, scheduler, sampler, rng, data, step, device, "sce_scale")
                for step in range(first, last + 1)]
    continuous = initialize(SEEDS[0], device)
    continuous_records = run(continuous, 1, 6)
    continuous_rng = capture_rng(continuous[3], np_generator=continuous[4])
    split = initialize(SEEDS[0], device)
    split_records = run(split, 1, 3)
    config = {"purpose": "graph24_technical_resume", "seed": SEEDS[0], "architecture": ARCHITECTURE,
              "device": device, "data": data.identity()}
    with tempfile.TemporaryDirectory(prefix="stmdomains-graph24-resume-") as directory:
        path = Path(directory) / "step3.pt"
        save_checkpoint(path, model=split[0], optimizer=split[1], scheduler=split[2], sampler=split[3],
                        np_generator=split[4], progress={"step": 3}, config=config)
        restored = initialize(SEEDS[0], device)
        progress = load_checkpoint(path, model=restored[0], optimizer=restored[1], scheduler=restored[2],
                                   sampler=restored[3], np_generator=restored[4], config=config)
        split_records.extend(run(restored, 4, 6))
    weights_equal = all(torch.equal(v, restored[0].state_dict()[k]) for k, v in continuous[0].state_dict().items())
    optimizer_equal = state_equal(continuous[1].state_dict(), restored[1].state_dict())
    scheduler_equal = state_equal(continuous[2].state_dict(), restored[2].state_dict())
    all_rng_equal = state_equal(continuous_rng, capture_rng(restored[3], np_generator=restored[4]))
    records_equal = continuous_records == split_records
    sampler_equal = torch.equal(continuous[3].get_state(), restored[3].get_state())
    mask_rng_equal = continuous[4].bit_generator.state == restored[4].bit_generator.state
    return {"passed": bool(weights_equal and optimizer_equal and scheduler_equal and all_rng_equal and records_equal and sampler_equal and mask_rng_equal and progress["step"] == 3),
            "weights_equal": weights_equal, "optimizer_equal": optimizer_equal, "scheduler_equal": scheduler_equal,
            "all_rng_equal": all_rng_equal, "batch_loss_records_equal": records_equal,
            "sampler_equal": sampler_equal, "mask_rng_equal": mask_rng_equal,
            "attempted_steps": 12,
            "optimizer_steps": sum(r["optimizer_step"] for r in continuous_records + split_records)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    fit = sub.add_parser("run")
    check = sub.add_parser("preflight")
    for child in (fit, check):
        child.add_argument("--data", type=Path, required=True)
        child.add_argument("--output", type=Path, required=True)
        child.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    fit.add_argument("--regime", choices=("transfer", "transductive"), required=True)
    fit.add_argument("--loss", choices=("sce", "sce_scale"), required=True)
    fit.add_argument("--seed", type=int, choices=SEEDS, required=True)
    fit.add_argument("--steps", type=int, required=True)
    check.add_argument("--resume-check", action="store_true")
    args = parser.parse_args()
    if args.command == "run":
        result = fit_one(args.data, args.output, args.regime, args.loss, args.seed, args.steps, args.device)
        print(json.dumps({k: result[k] for k in ("run_id", "status", "selected_step", "completed_steps", "seconds")}), flush=True)
        if result["status"] != "completed":
            raise SystemExit(1)
    else:
        result = preflight(args.data, args.output, args.device, resume_check=args.resume_check)
        print(json.dumps({k: result[k] for k in ("passed", "optimizer_steps", "deterministic_forward_backward")}), flush=True)


if __name__ == "__main__":
    main()
