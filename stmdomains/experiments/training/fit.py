"""Bounded label-free AE/rVAE fits from the frozen issue-20 preparation.

Only the analysis/data tree is accepted. Domain references and synthetic truth
are neither arguments nor inputs. Validation chooses checkpoints by the fixed
unlabelled loss; transductive fits have a predetermined last-step checkpoint.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import resource
import statistics
import subprocess
import sys
import time

import numpy as np
import scipy
import torch

from ..bundle import arrays_hash, file_hash, load_sample, write_json
from .checkpoint import capture_rng, config_hash, load_checkpoint, restore_rng, save_checkpoint
from .data import extract_patch, read_windows
from .models import ARCHITECTURE, make_model, load_model

PLAN_PATH = Path(__file__).with_name("experiment-plan.json")
SEEDS = (20261101, 20261102, 20261103)
VALIDATION_SEED = 740021


def preparation_root(path: str | Path) -> Path:
    path = Path(path).resolve()
    if not (path / "manifest.json").exists() and (path / "data/manifest.json").exists():
        path = path / "data"
    return path


class TrainingData:
    """Use only declared grid windows, with one frozen scalar normalizer."""

    def __init__(self, root: str | Path, regime: str):
        if regime not in ("transfer", "transductive"):
            raise ValueError("Unknown training regime")
        self.root, self.regime = preparation_root(root), regime
        self.manifest = json.loads((self.root / "manifest.json").read_text())
        if self.manifest["schema"] != "stmdomains-training-preparation-v1":
            raise ValueError("Wrong preparation schema")
        for name in ("windows", "split", "normalization"):
            if file_hash(self.root / self.manifest[f"{name}_file"]) != self.manifest[f"{name}_sha256"]:
                raise ValueError(f"Changed preparation {name}")
        if file_hash(self.root / "analysis/manifest.json") != self.manifest["analysis_manifest_sha256"]:
            raise ValueError("Changed analysis manifest")
        self.normalizer = json.loads((self.root / "normalization.json").read_text())[regime]
        rows = read_windows(self.root / "windows.jsonl")
        self.train = sorted((r for r in rows if r["sampler"] == "grid" and r["available"]
                             and (regime == "transductive" or r["transfer_split"] == "train")),
                            key=lambda r: r["window_id"])
        self.validation = sorted((r for r in rows if r["sampler"] == "grid" and r["available"]
                                  and regime == "transfer" and r["transfer_split"] == "validation"),
                                 key=lambda r: r["window_id"])
        if not self.train or (regime == "transfer" and not self.validation):
            raise ValueError("Missing training or validation windows")
        self.arrays = {}
        for sample_id in sorted({r["sample_id"] for r in self.train + self.validation}):
            _, arrays = load_sample(self.root / "analysis", sample_id)
            self.arrays[sample_id] = arrays
        groups = defaultdict(lambda: defaultdict(list))
        for index, row in enumerate(self.train):
            groups[row["scale_raw_px"]][row["sample_id"]].append(index)
        self.groups = {scale: {frame: indices for frame, indices in sorted(by_frame.items())}
                       for scale, by_frame in sorted(groups.items())}
        if tuple(self.groups) != (32, 48, 64):
            raise ValueError("All three frozen scales must be represented")
        self.scales = tuple(self.groups)
        self.frames = {scale: tuple(group) for scale, group in self.groups.items()}

    def sample_indices(self, generator: torch.Generator, batch_size: int) -> list[int]:
        result = []
        for _ in range(batch_size):
            scale = self.scales[int(torch.randint(len(self.scales), (), generator=generator))]
            frames = self.frames[scale]
            frame = frames[int(torch.randint(len(frames), (), generator=generator))]
            indices = self.groups[scale][frame]
            result.append(indices[int(torch.randint(len(indices), (), generator=generator))])
        return result

    def batch(self, indices: list[int], rng: np.random.Generator,
              *, validation: bool = False) -> tuple[torch.Tensor, torch.Tensor]:
        rows = self.validation if validation else self.train
        inputs, targets = [], []
        for index in indices:
            row = rows[index]
            shift = rng.uniform(-2., 2., size=2)
            gain, offset, sigma = rng.uniform(.9, 1.1), rng.uniform(-.1, .1), rng.uniform(0., .03)
            clean = extract_patch(self.arrays[row["sample_id"]], row, self.normalizer, shift_xy=shift)
            noisy = gain * clean + offset + rng.normal(0., sigma, clean.shape)
            # Target has the same spatial translation; only photometric noise is removed.
            inputs.append(noisy.astype(np.float32))
            targets.append(clean)
        return (torch.from_numpy(np.stack(inputs)[:, None]),
                torch.from_numpy(np.stack(targets)[:, None]))

    def validation_batches(self, batch_size: int = 64):
        rng = np.random.default_rng(VALIDATION_SEED)
        result = []
        for offset in range(0, len(self.validation), batch_size):
            indices = list(range(offset, min(offset + batch_size, len(self.validation))))
            result.append(self.batch(indices, rng, validation=True))
        return result

    def identity(self) -> dict:
        return {
            "preparation_manifest_sha256": file_hash(self.root / "manifest.json"),
            "analysis_manifest_sha256": self.manifest["analysis_manifest_sha256"],
            "windows_sha256": self.manifest["windows_sha256"],
            "split_sha256": self.manifest["split_sha256"],
            "normalization_sha256": self.manifest["normalization_sha256"],
            "normalizer": self.normalizer,
            "train_window_ids": [r["window_id"] for r in self.train],
            "validation_window_ids": [r["window_id"] for r in self.validation],
            "loaded_sample_ids": sorted(self.arrays),
            "sampling": "uniform scale, then uniform eligible frame, then uniform window; with replacement",
            "validation": "All eligible validation grid windows in sorted ID order; fixed augmentation seed740021; mean over elements",
            "source_labels_used": False,
        }


def initialize(family: str, latent_dim: int, seed: int, device: str):
    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    torch.set_num_threads(1)
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if device == "cuda":
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA unavailable for the requested fit")
        torch.cuda.manual_seed_all(seed)
    torch.use_deterministic_algorithms(True)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    model = make_model(family, latent_dim).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4, foreach=False)
    scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, lr_lambda=lambda _: 1.)
    sampler = torch.Generator(device="cpu").manual_seed(seed + 100)
    augmentation = np.random.default_rng(seed + 200)
    return model, optimizer, scheduler, sampler, augmentation


def losses(output: dict, target: torch.Tensor, step: int, *, validation: bool = False) -> dict:
    mse = (output["reconstruction"] - target).square().flatten(1).mean(1)
    kl = output["kl_per_sample"]
    beta = .001 if validation else .001 * min(1., step / 200.)
    return {"loss": (mse + beta * kl).mean(), "mse": mse.mean(), "kl": kl.mean(), "beta": beta}


def train_step(model, optimizer, scheduler, sampler, augmentation, data: TrainingData,
               step: int, device: str, batch_size: int = 64) -> dict:
    indices = data.sample_indices(sampler, batch_size)
    inputs, targets = data.batch(indices, augmentation)
    batch_digest = arrays_hash({"inputs": inputs.numpy(), "targets": targets.numpy()})
    optimizer.zero_grad(set_to_none=True)
    output = model(inputs.to(device), sample=True)
    terms = losses(output, targets.to(device), step)
    if not torch.isfinite(terms["loss"]):
        raise FloatingPointError("nonfinite_loss")
    terms["loss"].backward()
    norm = torch.nn.utils.clip_grad_norm_(model.parameters(), 1., error_if_nonfinite=True, foreach=False)
    if any(p.grad is None or not torch.isfinite(p.grad).all() for p in model.parameters()):
        raise FloatingPointError("nonfinite_or_missing_gradient")
    optimizer.step()
    scheduler.step()
    return {"step": step, "batch_indices": indices, "batch_content_sha256": batch_digest,
            "loss": float(terms["loss"].detach()), "mse": float(terms["mse"].detach()),
            "kl": float(terms["kl"].detach()), "beta": terms["beta"], "gradient_norm_before_clip": float(norm)}


@torch.inference_mode()
def validate(model, batches: list, device: str) -> dict:
    was_training = model.training
    model.eval()
    total = {"loss": 0., "mse": 0., "kl": 0.}
    count = 0
    try:
        for inputs, targets in batches:
            terms = losses(model(inputs.to(device), sample=False), targets.to(device), 0, validation=True)
            for name in total:
                total[name] += float(terms[name]) * len(inputs)
            count += len(inputs)
    finally:
        model.train(was_training)
    if not count or not all(np.isfinite(list(total.values()))):
        raise FloatingPointError("missing_or_nonfinite_validation")
    return {name: value / count for name, value in total.items()} | {"elements": count, "beta": .001}


def source_hashes() -> dict:
    names = ("models.py", "fit.py", "checkpoint.py", "data.py")
    return {name: file_hash(Path(__file__).with_name(name)) for name in names}


def make_config(data: TrainingData, family: str, latent_dim: int, seed: int,
                device: str, steps: int, *, purpose: str = "issue21_fit") -> dict:
    return {
        "schema": "stmdomains-autoencoder-run-v1", "purpose": purpose,
        "family": family, "latent_dim": latent_dim, "regime": data.regime, "seed": seed,
        "architecture": ARCHITECTURE, "plan_sha256": file_hash(PLAN_PATH),
        "code_sha256": source_hashes(), "data": data.identity(),
        "device": device, "precision": "float32", "batch_size": 64,
        "optimizer": {"name": "AdamW", "lr": .001, "weight_decay": .0001, "clip_norm": 1.},
        "scheduler": "constant", "max_steps": steps,
        "checkpoint_interval": 100, "validation_seed": VALIDATION_SEED,
        "validation_beta": .001, "selected_on": "unlabelled_validation_loss" if data.regime == "transfer" else "fixed_last_step",
        "limits": json.loads(PLAN_PATH.read_text())["administrative_caps"],
    }


def _rss_bytes() -> int:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024


def _checkpoint_bytes(root: Path) -> int:
    return sum(p.stat().st_size for p in root.rglob("*.pt"))


def _sync(device: str) -> None:
    if device == "cuda":
        torch.cuda.synchronize()


def fit_one(data_root: Path, out: Path, family: str, latent_dim: int, seed: int,
            regime: str, steps: int, device: str, budget_root: Path | None = None) -> dict:
    if out.exists():
        raise FileExistsError(f"A fit may not silently replace previous results: {out}")
    started = time.perf_counter()
    out.mkdir(parents=True)
    data = TrainingData(data_root, regime)
    config = make_config(data, family, latent_dim, seed, device, steps)
    write_json(out / "config.json", config)  # frozen before initialization/training
    model, optimizer, scheduler, sampler, augmentation = initialize(family, latent_dim, seed, device)
    validation_batches = data.validation_batches() if regime == "transfer" else []
    validation_digest = arrays_hash({f"{i}-{part}": tensor.numpy() for i, batch in enumerate(validation_batches)
                                    for part, tensor in zip(("input", "target"), batch)})
    write_json(out / "validation.json", {"seed": VALIDATION_SEED, "batch_content_sha256": validation_digest,
                                        "window_ids": [r["window_id"] for r in data.validation]})
    progress = {"step": 0, "history": [], "validation_history": [],
                "best_validation_loss": None, "selected_step": None}
    status, stop_reason = "completed", "fixed_step_budget"
    limits = config["limits"]
    budget_root = out if budget_root is None else budget_root
    if device == "cuda":
        torch.cuda.reset_peak_memory_stats()
    first100 = None
    checkpoints = []
    try:
        for step in range(1, steps + 1):
            if time.perf_counter() - started >= limits["seconds_per_fit_including_validation_and_checkpoint"]:
                status, stop_reason = "stopped", "time_cap"
                break
            record = train_step(model, optimizer, scheduler, sampler, augmentation, data, step, device)
            progress["history"].append(record)
            progress["step"] = step
            if step == 100:
                _sync(device)
                first100 = time.perf_counter() - started
            if _rss_bytes() > limits["process_rss_bytes"] or (
                device == "cuda" and torch.cuda.max_memory_allocated() > limits["gpu_tensor_bytes"]):
                status, stop_reason = "stopped", "memory_cap"
                break
            if step % 100 == 0 or step == steps:
                if regime == "transfer":
                    value = validate(model, validation_batches, device)
                    progress["validation_history"].append({"step": step, **value})
                    if progress["best_validation_loss"] is None or value["loss"] < progress["best_validation_loss"]:
                        progress["best_validation_loss"] = value["loss"]
                        progress["selected_step"] = step
                else:
                    progress["selected_step"] = step
                path = out / f"step-{step:04}.pt"
                save_checkpoint(path, model=model, optimizer=optimizer, scheduler=scheduler,
                                sampler=sampler, np_generator=augmentation, progress=progress, config=config)
                checkpoints.append({"step": step, "file": path.name, "sha256": file_hash(path),
                                    "bytes": path.stat().st_size})
                elapsed = time.perf_counter() - started
                print(json.dumps({"run": str(out), "step": step, "train_loss": record["loss"],
                                  "validation_loss": progress["validation_history"][-1]["loss"] if validation_batches else None,
                                  "seconds": elapsed}), flush=True)
                write_json(out / "progress.json", {"step": step, "selected_step": progress["selected_step"],
                                                    "seconds": elapsed, "checkpoints": checkpoints})
                if elapsed > limits["seconds_per_fit_including_validation_and_checkpoint"]:
                    status, stop_reason = "stopped", "time_cap"
                    break
                if _checkpoint_bytes(budget_root) > limits["all_checkpoint_bytes"]:
                    status, stop_reason = "stopped", "checkpoint_storage_cap"
                    break
    except (RuntimeError, FloatingPointError) as exc:
        status, stop_reason = "failed", f"{type(exc).__name__}: {exc}"
    if status != "completed":
        # Preserve the last state to diagnose/resume explicitly, never silently restart.
        path = out / "stopped.pt"
        try:
            save_checkpoint(path, model=model, optimizer=optimizer, scheduler=scheduler,
                            sampler=sampler, np_generator=augmentation, progress=progress, config=config)
        except RuntimeError:
            pass
    _sync(device)
    elapsed = time.perf_counter() - started
    selected = next((row for row in checkpoints if row["step"] == progress["selected_step"]), None)
    result = {
        "schema": "stmdomains-autoencoder-fit-v1", "status": status, "stop_reason": stop_reason,
        "family": family, "latent_dim": latent_dim, "seed": seed, "regime": regime,
        "config_hash": config_hash(config), "config_file_sha256": file_hash(out / "config.json"),
        "selected_checkpoint": selected["file"] if selected and status == "completed" else None,
        "selected_checkpoint_sha256": selected["sha256"] if selected and status == "completed" else None,
        "selected_step": progress["selected_step"], "best_validation_loss": progress["best_validation_loss"],
        "completed_steps": progress["step"], "seconds": elapsed, "first100_seconds_including_setup": first100,
        "parameter_count": sum(p.numel() for p in model.parameters()),
        "training_windows": len(data.train), "validation_windows": len(data.validation),
        "validation_content_sha256": validation_digest,
        "checkpoints": checkpoints, "loss_history": progress["history"],
        "validation_history": progress["validation_history"],
        "peak_rss_bytes": _rss_bytes(),
        "cuda_peak_allocated_bytes": torch.cuda.max_memory_allocated() if device == "cuda" else None,
        "cuda_peak_reserved_bytes": torch.cuda.max_memory_reserved() if device == "cuda" else None,
        "environment": {"python": platform.python_version(), "torch": torch.__version__,
                        "numpy": np.__version__, "scipy": scipy.__version__, "cuda": torch.version.cuda,
                        "gpu": torch.cuda.get_device_name() if device == "cuda" else None},
        "reference_access": False,
    }
    write_json(out / "run.json", result)
    return result


def run_all(data_root: Path, out: Path, device: str) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    freeze_path = out / "architecture.json"
    freeze = {"architecture": ARCHITECTURE, "code_sha256": source_hashes(),
              "plan_sha256": file_hash(PLAN_PATH), "purpose": "Frozen before issue21 fits",
              "expected_fit_count": 18}
    if freeze_path.exists() and json.loads(freeze_path.read_text()) != freeze:
        raise ValueError("Existing architecture freeze differs; do not reinterpret old fits")
    write_json(freeze_path, freeze)
    registry = {"schema": "stmdomains-autoencoder-suite-v1", "runs": [], "skipped": [],
                "architecture_sha256": file_hash(freeze_path), "plan_sha256": file_hash(PLAN_PATH)}
    plan = json.loads(PLAN_PATH.read_text())
    max_suite_seconds = plan["administrative_caps"]["seconds_per_fit_including_validation_and_checkpoint"] * 18
    for regime in ("transfer", "transductive"):
        for family in ("ae", "rvae"):
            if regime == "transductive":
                base_runs = [row for row in registry["runs"] if row["regime"] == "transfer"
                             and row["family"] == family and row["latent_dim"] == 32 and row["status"] == "completed"]
                if len(base_runs) != 3:
                    registry["skipped"].append({"family": family, "regime": regime,
                                                "reason": "fewer_than_three_successful_z32_transfer_runs"})
                    continue
                steps = int(statistics.median(row["selected_step"] for row in base_runs))
                latents = (32,)
            else:
                steps, latents = 2000, (16, 32)
            for latent_dim in latents:
                for seed in SEEDS:
                    target = out / regime / family / f"z{latent_dim}" / f"seed-{seed}"
                    if sum(row["seconds"] for row in registry["runs"]) >= max_suite_seconds:
                        registry["skipped"].append({"path": str(target), "reason": "total_time_cap"})
                        continue
                    if (target / "run.json").exists():
                        result = json.loads((target / "run.json").read_text())
                        old_config = json.loads((target / "config.json").read_text())
                        if old_config["code_sha256"] != freeze["code_sha256"] or old_config["plan_sha256"] != freeze["plan_sha256"]:
                            raise ValueError("Existing run belongs to different code/plan")
                    else:
                        command = [sys.executable, "-m", "stmdomains.experiments.training.fit",
                                   "--data", str(data_root.resolve()), "--out", str(target.resolve()),
                                   "--device", device, "--worker", "--family", family,
                                   "--latent", str(latent_dim), "--seed", str(seed),
                                   "--regime", regime, "--steps", str(steps), "--budget-root", str(out.resolve())]
                        completed = subprocess.run(command, check=False)
                        if not (target / "run.json").exists():
                            raise RuntimeError(f"Fit worker exited {completed.returncode} without a result: {target}")
                        result = json.loads((target / "run.json").read_text())
                    registry["runs"].append({key: result[key] for key in (
                        "status", "family", "latent_dim", "seed", "regime", "selected_step",
                        "selected_checkpoint_sha256", "seconds", "completed_steps", "stop_reason")}
                        | {"directory": str(target.resolve()), "run_json_sha256": file_hash(target / "run.json")})
                    write_json(out / "registry.json", registry)
    registry["completed"] = sum(row["status"] == "completed" for row in registry["runs"])
    registry["total_fit_seconds"] = sum(row["seconds"] for row in registry["runs"])
    registry["checkpoint_bytes"] = _checkpoint_bytes(out)
    write_json(out / "registry.json", registry)
    return registry


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--family", choices=("ae", "rvae"))
    parser.add_argument("--latent", type=int, choices=(16, 32))
    parser.add_argument("--seed", type=int)
    parser.add_argument("--regime", choices=("transfer", "transductive"))
    parser.add_argument("--steps", type=int)
    parser.add_argument("--budget-root", type=Path)
    args = parser.parse_args()
    if args.worker:
        result = fit_one(args.data, args.out, args.family, args.latent, args.seed,
                         args.regime, args.steps, args.device, args.budget_root)
        if result["status"] != "completed":
            raise SystemExit(1)
    else:
        result = run_all(args.data, args.out, args.device)
        print(json.dumps({"completed": result["completed"], "seconds": result["total_fit_seconds"]}))


if __name__ == "__main__":
    main()
