"""Bounded technical training/resume probe; never a domain-quality experiment."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import resource
import subprocess
import sys
import time
from typing import Any

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

from .checkpoint import config_hash, load_checkpoint, read_checkpoint, save_checkpoint


SEEDS = (20261101, 20261102, 20261103)
TOLERANCE = 1e-6


class ProbeAE(nn.Module):
    """Small convolutional proxy, not a selected architecture for issue 21."""

    def __init__(self) -> None:
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Conv2d(1, 8, 4, 2, 1), nn.ELU(),
            nn.Conv2d(8, 16, 4, 2, 1), nn.ELU(),
            nn.Conv2d(16, 24, 4, 2, 1), nn.ELU(),
        )
        self.decoder = nn.Sequential(
            nn.ConvTranspose2d(24, 16, 4, 2, 1), nn.ELU(),
            nn.ConvTranspose2d(16, 8, 4, 2, 1), nn.ELU(),
            nn.ConvTranspose2d(8, 1, 4, 2, 1),
        )

    def forward(self, images: torch.Tensor) -> torch.Tensor:
        return self.decoder(self.encoder(images))


def initialize(seed: int, device: str) -> tuple[Any, Any, Any, Any]:
    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    torch.set_num_threads(1)
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.use_deterministic_algorithms(True)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    if device == "cuda":
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA is unavailable; CPU output cannot satisfy the GPU preparation")
        torch.cuda.manual_seed_all(seed)
    model = ProbeAE().to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3, foreach=False)
    scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size=2, gamma=0.9)
    sampler = torch.Generator(device="cpu").manual_seed(seed + 100)
    return model, optimizer, scheduler, sampler


def read_batch(path: Path) -> torch.Tensor:
    with np.load(path, allow_pickle=False) as archive:
        patches = archive["patches"]
    if patches.dtype != np.float32 or patches.ndim != 4 or patches.shape[1:] != (1, 64, 64):
        raise ValueError("patches must be float32 [N,1,64,64]")
    if len(patches) < 2 or not np.isfinite(patches).all():
        raise ValueError("At least two finite patches are required")
    return torch.from_numpy(np.ascontiguousarray(patches))


def train_step(model: nn.Module, optimizer: Any, scheduler: Any,
               sampler: torch.Generator, patches: torch.Tensor,
               batch_size: int, device: str,
               np_generator: np.random.Generator | None = None) -> dict[str, Any]:
    ids = torch.randint(len(patches), (batch_size,), generator=sampler)
    source = patches[ids]
    # Exercise every saved random stream, including CPU RNG in a CUDA run.
    gain = 1.0 + 0.005 * (random.random() + float(np.random.uniform(-1, 1)))
    if np_generator is not None:
        gain += 0.003 * float(np_generator.uniform(-1, 1))
    image = (source + 0.003 * torch.randn_like(source)).to(device) * gain
    image = image + 0.002 * torch.randn_like(image)
    optimizer.zero_grad(set_to_none=True)
    loss = F.mse_loss(model(image), source.to(device))
    if not torch.isfinite(loss):
        raise RuntimeError("Nonfinite proxy loss")
    loss.backward()
    if any(p.grad is None or not torch.isfinite(p.grad).all() for p in model.parameters()):
        raise RuntimeError("Missing or nonfinite convolution gradient")
    optimizer.step()
    scheduler.step()
    return {"batch_ids": ids.tolist(), "loss": float(loss.detach()),
            "learning_rate": scheduler.get_last_lr()[0]}


def _sync(device: str) -> None:
    if device == "cuda":
        torch.cuda.synchronize()


def _memory(device: str) -> dict[str, int | None]:
    return {
        "rss_peak_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
        "cuda_peak_allocated_bytes": torch.cuda.max_memory_allocated() if device == "cuda" else None,
        "cuda_peak_reserved_bytes": torch.cuda.max_memory_reserved() if device == "cuda" else None,
    }


def _config(batch: Path, seed: int, device: str, batch_size: int) -> dict[str, Any]:
    return {
        "purpose": "issue20_technical_probe", "seed": seed, "device": device,
        "input_sha256": hashlib.sha256(batch.read_bytes()).hexdigest(),
        "code_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                        for p in (Path(__file__), Path(__file__).with_name("checkpoint.py"))},
        "model": "ProbeAE_conv_8_16_24_v1", "batch_size": batch_size,
        "sampler": "uniform_with_replacement_cpu_generator", "precision": "float32",
        "augmentation_generator": "numpy.default_rng.PCG64",
        "optimizer": {"name": "Adam", "lr": 1e-3, "foreach": False},
        "scheduler": {"name": "StepLR", "step_size": 2, "gamma": 0.9},
        "total_steps": 6,
    }


def _worker(batch: Path, out: Path, device: str, seed: int, phase: str) -> None:
    patches = read_batch(batch)
    model, optimizer, scheduler, sampler = initialize(seed, device)
    augmentation_rng = np.random.default_rng(seed + 200)
    config = _config(batch, seed, device, 8)
    progress: dict[str, Any] = {"step": 0, "history": []}
    if phase == "resume":
        progress = load_checkpoint(out / "first.pt", model=model, optimizer=optimizer,
                                   scheduler=scheduler, sampler=sampler, config=config,
                                   np_generator=augmentation_rng)
    if device == "cuda":
        torch.cuda.reset_peak_memory_stats()
    _sync(device)
    started = time.perf_counter()
    stop = 3 if phase == "first" else 6
    for step in range(progress["step"], stop):
        progress["history"].append(train_step(model, optimizer, scheduler, sampler,
                                               patches, 8, device, augmentation_rng))
        progress["step"] = step + 1
    _sync(device)
    elapsed = time.perf_counter() - started
    save_checkpoint(out / f"{phase}.pt", model=model, optimizer=optimizer,
                    scheduler=scheduler, sampler=sampler, progress=progress, config=config,
                    np_generator=augmentation_rng)
    _write_json(out / f"{phase}.json", {
        "phase": phase, "pid": os.getpid(), "seconds": elapsed,
        "completed_step": progress["step"], "config_hash": config_hash(config),
        **_memory(device),
    })


def compare_states(left: Any, right: Any, tolerance: float = TOLERANCE) -> dict[str, Any]:
    """Compare nested model/optimizer/RNG/history values, not archive bytes."""
    failures: list[str] = []
    maximum = 0.0
    exact = True

    def compare(a: Any, b: Any, path: str) -> None:
        nonlocal maximum, exact
        if isinstance(a, torch.Tensor):
            if not isinstance(b, torch.Tensor) or a.shape != b.shape or a.dtype != b.dtype:
                failures.append(path)
                exact = False
                return
            a, b = a.cpu(), b.cpu()
            same = torch.equal(a, b)
            exact = exact and same
            if a.is_floating_point():
                delta = float((a.to(torch.float64) - b.to(torch.float64)).abs().max()) if a.numel() else 0.0
                maximum = max(maximum, delta)
                if not torch.isfinite(a).all() or not torch.isfinite(b).all() or delta > tolerance:
                    failures.append(path)
            elif not same:
                failures.append(path)
        elif isinstance(a, np.ndarray):
            same = isinstance(b, np.ndarray) and a.dtype == b.dtype and np.array_equal(a, b)
            exact = exact and same
            if not same:
                failures.append(path)
        elif isinstance(a, dict):
            if not isinstance(b, dict) or a.keys() != b.keys():
                failures.append(path)
                exact = False
            else:
                for key in a:
                    compare(a[key], b[key], f"{path}.{key}")
        elif isinstance(a, (tuple, list)):
            if type(a) is not type(b) or len(a) != len(b):
                failures.append(path)
                exact = False
            else:
                for index, (aa, bb) in enumerate(zip(a, b)):
                    compare(aa, bb, f"{path}[{index}]")
        elif isinstance(a, float) and isinstance(b, float):
            delta = abs(a - b)
            maximum = max(maximum, delta)
            exact = exact and a == b
            if not np.isfinite([a, b]).all() or delta > tolerance:
                failures.append(path)
        elif a != b:
            failures.append(path)
            exact = False

    compare(left, right, "state")
    return {"passed": not failures, "exact": exact, "max_absolute_difference": maximum,
            "absolute_tolerance": tolerance, "failures": failures}


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def operation_probe(patches: torch.Tensor, device: str) -> dict[str, Any]:
    model, _, _, _ = initialize(SEEDS[0], device)
    _sync(device)
    if device == "cuda":
        torch.cuda.reset_peak_memory_stats()
    started = time.perf_counter()
    image = patches[:4].to(device).detach().requires_grad_(True)
    # grid_sample CUDA backward is documented as nondeterministic. Test both
    # strict support and executable gradients; do not claim deterministic rVAE.
    grid_result: dict[str, Any] = {}
    for strict in (True, False):
        torch.use_deterministic_algorithms(strict)
        inp = image.detach().clone().requires_grad_(True)
        theta = torch.tensor([[[0.99, -0.05, 0.01], [0.05, 0.99, -0.01]]],
                             device=device).expand(len(inp), -1, -1).clone().requires_grad_(True)
        try:
            grid = F.affine_grid(theta, inp.shape, align_corners=False)
            transformed = F.grid_sample(inp, grid, padding_mode="border", align_corners=False)
            transformed.square().mean().backward()
            passed = all(t.grad is not None and bool(torch.isfinite(t.grad).all())
                         for t in (inp, theta))
            grid_result["strict" if strict else "permissive"] = {
                "passed": passed,
                "input_gradient_norm": float(inp.grad.norm()),
                "transform_gradient_norm": float(theta.grad.norm()),
            }
        except RuntimeError as exc:
            grid_result["strict" if strict else "permissive"] = {
                "passed": False, "error": str(exc)}
    torch.use_deterministic_algorithms(True)
    # A coordinate decoder is a distinct rVAE implementation candidate: rotate
    # coordinates analytically, then predict intensity, without grid resampling.
    angles = torch.full((len(image),), 0.05, device=device, requires_grad=True)
    translations = torch.zeros(len(image), 1, 2, device=device, requires_grad=True)
    code = torch.randn(len(image), 4, device=device, requires_grad=True)
    axis = (torch.arange(64, device=device, dtype=torch.float32) + 0.5) / 32 - 1
    yy, xx = torch.meshgrid(axis, axis, indexing="ij")
    coordinates = torch.stack((xx, yy), dim=-1).reshape(1, -1, 2)
    c, s = angles.cos(), angles.sin()
    rotation = torch.stack((c, -s, s, c), dim=-1).reshape(-1, 2, 2)
    transformed_coordinates = coordinates @ rotation + translations
    decoder = nn.Sequential(nn.Linear(6, 32), nn.Tanh(), nn.Linear(32, 1)).to(device)
    decoder_input = torch.cat((transformed_coordinates, code[:, None].expand(-1, 4096, -1)), dim=-1)
    coordinate_loss = F.mse_loss(decoder(decoder_input).reshape_as(image), image.detach())
    coordinate_loss.backward()
    coordinate_passed = all(t.grad is not None and bool(torch.isfinite(t.grad).all())
                            for t in (angles, translations, code, *decoder.parameters()))
    features = model.encoder(image).permute(0, 2, 3, 1).reshape(-1, 24)
    centered = features - features.mean(0)
    covariance = centered.T @ centered / (len(features) - 1)
    off_diagonal = covariance - torch.diag_embed(covariance.diagonal())
    ssl_loss = F.relu(1 - torch.sqrt(features.var(0, unbiased=False) + 1e-4)).mean()
    ssl_loss = ssl_loss + off_diagonal.square().sum() / features.shape[1]
    ssl_loss.backward()
    ssl_passed = all(p.grad is not None and bool(torch.isfinite(p.grad).all())
                     for p in model.encoder.parameters())
    mean = torch.zeros(8, 4, device=device, requires_grad=True)
    log_variance = torch.zeros_like(mean, requires_grad=True)
    latent = mean + torch.exp(0.5 * log_variance) * torch.randn_like(mean)
    latent.square().mean().backward()
    vae_passed = all(v.grad is not None and bool(torch.isfinite(v.grad).all())
                     for v in (mean, log_variance))
    _sync(device)
    return {"grid_sample_backward": grid_result,
            "coordinate_decoder_backward": {"passed": coordinate_passed, "strict_determinism": True,
                "loss": float(coordinate_loss.detach()), "angle_gradient_norm": float(angles.grad.norm())},
            "local_variance_covariance_backward": {"passed": ssl_passed, "loss": float(ssl_loss.detach())},
            "reparameterization_backward": {"passed": vae_passed},
            "seconds": time.perf_counter() - started, **_memory(device)}


def run_probe(batch: Path, out: Path, device: str) -> dict[str, Any]:
    run_started = time.perf_counter()
    out.mkdir(parents=True, exist_ok=True)
    patches = read_batch(batch)
    initialize(SEEDS[0], device)
    report: dict[str, Any] = {
        "schema": "stmdomains.training-gpu-probe.v1", "purpose": "technical_preparation_only",
        "input": str(batch.resolve()), "input_sha256": hashlib.sha256(batch.read_bytes()).hexdigest(),
        "patch_count": len(patches), "torch": torch.__version__, "numpy": np.__version__,
        "python": sys.version, "device": device, "cuda_runtime": torch.version.cuda,
        "gpu": torch.cuda.get_device_name() if device == "cuda" else None,
        "gpu_total_memory_bytes": torch.cuda.get_device_properties(0).total_memory if device == "cuda" else None,
        "gpu_compute_capability": list(torch.cuda.get_device_capability(0)) if device == "cuda" else None,
        "cudnn": torch.backends.cudnn.version(), "seeds": list(SEEDS),
        "precision": "float32", "cpu_threads": 1, "resume": [], "measurements": [],
        "proxy_parameter_count": sum(p.numel() for p in ProbeAE().parameters()),
        "training_steps": {"resume_comparisons": 36, "benchmark_warmup": 18,
                           "benchmark_measured": 45, "total": 99},
        "limitations": ["Only the proxy AE has a continuation equivalence test.",
                        "No quality assessment or training of issue 21/22 models.",
                        "RSS is per-process high-water mark, not isolated allocation.",
                        "CUDA tensor allocator peaks exclude driver/context memory.",
                        "Timing covers sampling, copies, forward/backward/Adam and validation.",
                        "No mixed precision, accumulation, workers or prefetch queues."],
    }
    for seed in SEEDS:
        seed_out = out / f"seed-{seed}"
        seed_out.mkdir(exist_ok=True)
        phases = []
        for phase in ("full", "first", "resume"):
            command = [sys.executable, "-m", __spec__.name, "--batch", str(batch.resolve()),
                       "--out", str(seed_out.resolve()), "--device", device,
                       "--worker", phase, "--seed", str(seed)]
            completed = subprocess.run(command, capture_output=True, text=True, check=False)
            if completed.returncode:
                raise RuntimeError(f"{phase} worker failed: {completed.stderr[-4000:]}")
            phases.append(json.loads((seed_out / f"{phase}.json").read_text()))
        full, resumed = (read_checkpoint(seed_out / f"{name}.pt") for name in ("full", "resume"))
        compared = {key: compare_states(full[key], resumed[key]) for key in
                    ("model", "optimizer", "scheduler", "rng", "progress", "config", "runtime")}
        report["resume"].append({"seed": seed, "phases": phases, "comparison": compared,
                                 "passed": all(item["passed"] for item in compared.values())})
        _write_json(out / "gpu-probe.json", report)
    report["operations"] = operation_probe(patches, device)
    for batch_size in (32, 64, 128):
        for seed in SEEDS:
            model, optimizer, scheduler, sampler = initialize(seed, device)
            augmentation_rng = np.random.default_rng(seed + 200)
            for _ in range(2):
                train_step(model, optimizer, scheduler, sampler, patches, batch_size, device, augmentation_rng)
            _sync(device)
            if device == "cuda":
                torch.cuda.reset_peak_memory_stats()
            started = time.perf_counter()
            history = [train_step(model, optimizer, scheduler, sampler, patches, batch_size, device, augmentation_rng)
                       for _ in range(5)]
            _sync(device)
            elapsed = time.perf_counter() - started
            report["measurements"].append({"seed": seed, "batch_size": batch_size,
                "warmup_steps": 2, "measured_steps": 5, "seconds": elapsed,
                "seconds_per_step": elapsed / 5, "patches_per_second": batch_size * 5 / elapsed,
                "losses": [row["loss"] for row in history], **_memory(device)})
            del model, optimizer, scheduler
            if device == "cuda":
                torch.cuda.empty_cache()
    ops = report["operations"]
    report["passed"] = (all(row["passed"] for row in report["resume"])
                        and ops["grid_sample_backward"]["permissive"]["passed"]
                        and ops["coordinate_decoder_backward"]["passed"]
                        and ops["local_variance_covariance_backward"]["passed"]
                        and ops["reparameterization_backward"]["passed"])
    report["gpu_requirement_met"] = device == "cuda" and report["passed"]
    report["rvae_determinism_condition"] = (
        "CUDA grid_sample backward is not a validated deterministic rVAE path. "
        "Use an analytically transformed-coordinate decoder candidate or explicitly "
        "measure and document relaxed reproducibility. Full rVAE continuation remains "
        "a requirement of issue 21; the coordinate-operation check is not that test.")
    report["total_wall_seconds_including_workers"] = time.perf_counter() - run_started
    _write_json(out / "gpu-probe.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    parser.add_argument("--worker", choices=("full", "first", "resume"), help=argparse.SUPPRESS)
    parser.add_argument("--seed", type=int, default=SEEDS[0], help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        _worker(args.batch, args.out, args.device, args.seed, args.worker)
    else:
        report = run_probe(args.batch, args.out, args.device)
        print(json.dumps({"passed": report["passed"], "gpu_requirement_met": report["gpu_requirement_met"],
                          "report": str(args.out / "gpu-probe.json")}))
        if not report["passed"]:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
