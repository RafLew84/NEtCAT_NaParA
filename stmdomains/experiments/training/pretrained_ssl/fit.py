"""Six fixed-step local DINO fits; validation never selects a checkpoint."""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
import math
import os
from pathlib import Path
import platform
import random
import resource
import tempfile
import time

import numpy as np
import torch
import torch.nn.functional as F

from ...bundle import arrays_hash, file_hash, write_json
from ..checkpoint import config_hash, load_checkpoint, read_checkpoint, save_checkpoint
from ..data import read_windows
from ..fit import TrainingData, preparation_root, VALIDATION_SEED
from ..local_ssl.fit import SSLTrainingData
from .common import CAPS, PROTOCOL_PATH, reporting_stage
from .models import (ARCHITECTURE, DEFAULT_ASSETS, LocalDINO, aligned_tokens, asset_identity,
                     batch_terms, entropy_statistics, state_digest, transform)


SEEDS = (20261101, 20261102, 20261103)
STEPS = 1000
BATCH_SIZE = 64
REPOSITORY = Path(__file__).resolve().parents[4]


def read(path):
    return json.loads(Path(path).read_text())


def deny_references():
    import sys
    def hook(event, args):
        if event == "open" and isinstance(args[0], (str, bytes, os.PathLike)):
            name = os.fsdecode(args[0]).replace("\\", "/")
            if "/evaluation/" in name or "/references/" in name or "manual_domain" in name:
                raise PermissionError("References denied to adaptation training: " + name)
    sys.addaudithook(hook)


class AdaptationData(SSLTrainingData):
    def __init__(self, root, regime):
        super().__init__(root, regime)
        if regime == "transductive":
            self.validation = sorted((r for r in read_windows(self.root / "windows.jsonl")
                if r["available"] and r["sampler"] == "grid" and r["transfer_split"] == "validation"),
                key=lambda r: r["window_id"])

    def identity(self):
        return dict(TrainingData.identity(self),
            augmentation="Unchanged issue20 augmented_pair: two independent known translations and photometric perturbations",
            correspondence=ARCHITECTURE["correspondence"],
            validation_role="Diagnostic only, no selection; transduction validation windows also belong to its training pool")

    def train_probe_batches(self):
        # Fixed canonical order, unrelated to reference labels or feature values.
        indices = [i for scale in (32, 48, 64) for i in
                   [i for i, row in enumerate(self.train) if row["scale_raw_px"] == scale][:32]]
        rng = np.random.default_rng(740026)
        return [self.batch(indices[start:start+64], rng) for start in range(0, len(indices), 64)]


def source_hashes():
    own = Path(__file__).parent
    paths = [own / name for name in ("models.py", "fit.py", "common.py")]
    paths += [own.parent / name for name in ("models.py", "fit.py", "data.py", "checkpoint.py", "experiment-plan.json")]
    paths += [own.parent / "local_ssl" / name for name in ("fit.py", "models.py")]
    paths += [own.parent.parent / "bundle.py", own.parent.parent / "frozen/models.py"]
    return {str(p.resolve().relative_to(REPOSITORY)): file_hash(p) for p in paths}


def run_specs():
    return [dict(run_id=f"{regime}/dino_adapted/seed-{seed}", regime=regime,
                 family="dino_adapted", seed=seed, latent_dim=384)
            for regime in ("transfer", "transductive") for seed in SEEDS]


def verified_plan(data_root, output):
    plan = read(Path(output) / "plan.json")
    if plan["schema"] != "pretrained-ssl26-plan-v1" or plan["training_caps"] != CAPS:
        raise ValueError("Wrong adaptation plan or budget")
    pinned = {}
    for name, digest in plan["code_sha256"].items():
        path = Path(name) if Path(name).is_absolute() else REPOSITORY / name
        if file_hash(path) != digest:
            raise ValueError("Changed frozen source: " + name)
        pinned[str(path.resolve())] = digest
    for name, digest in source_hashes().items():
        if pinned.get(str((REPOSITORY / name).resolve())) != digest:
            raise ValueError("Incomplete numerical source freeze: " + name)
    for name, digest in plan["source_files"].items():
        if file_hash(Path(name)) != digest:
            raise ValueError("Changed source data or pretrained asset: " + name)
    protocol = Path(plan["protocol_file"])
    protocol = protocol if protocol.is_absolute() else REPOSITORY / protocol
    if file_hash(protocol) != plan["protocol_sha256"] or file_hash(PROTOCOL_PATH) != plan["protocol_sha256"]:
        raise ValueError("Changed protocol")
    root = preparation_root(data_root)
    if root != preparation_root(plan["data_root"]) or file_hash(root / "manifest.json") != plan["data_manifest_sha256"]:
        raise ValueError("Training data differ from frozen plan")
    expected = {(r["run_id"], r["regime"], r["family"], r["seed"]) for r in run_specs()}
    actual = {(r["run_id"], r["regime"], r["family"], r["seed"]) for r in plan["run_specs"]}
    if actual != expected or len(plan["run_specs"]) != 6:
        raise ValueError("Changed six-fit matrix")
    identity = asset_identity(plan["assets_root"])
    for name, digest in identity["source_sha256"].items():
        path = str((Path(identity["source_root"]) / name).resolve())
        if plan["source_files"].get(path) != digest and pinned.get(path) != digest:
            raise ValueError("Unpinned official DINO source: " + name)
    if plan["source_files"].get(identity["weights_file"]) != identity["weights_sha256"]:
        raise ValueError("Unpinned pretrained weights")
    return plan


def configure(seed, device):
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


def learning_rate_multiplier(step):
    if step < 50:
        return (step+1) / 50
    return .1 + .9 * (1 + math.cos(math.pi * (step-50)/(STEPS-50))) / 2


def initialize(seed, device, assets=DEFAULT_ASSETS):
    configure(seed, device)
    model = LocalDINO(assets).to(device)
    groups = {}
    for name, parameter in model.delta["student"].named_parameters():
        if not parameter.requires_grad:
            continue
        lr = 2e-4 if name.startswith("head.") else 2e-5
        decay = .04 if parameter.ndim >= 2 else 0.
        groups.setdefault((lr, decay), []).append(parameter)
    optimizer = torch.optim.AdamW([dict(params=values, lr=lr, weight_decay=decay)
        for (lr, decay), values in groups.items()], foreach=False)
    scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, learning_rate_multiplier)
    return model, optimizer, scheduler, torch.Generator(device="cpu").manual_seed(seed+100), np.random.default_rng(seed+200)


def train_step(model, optimizer, scheduler, sampler, augmentation, data, step, device, batch_size=BATCH_SIZE):
    indices = data.sample_indices(sampler, batch_size)
    batch = data.batch(indices, augmentation)
    digest = arrays_hash({name: value.numpy() for name, value in batch.items()})
    optimizer.zero_grad(set_to_none=True)
    terms, extra = batch_terms(model, batch, device)
    if not all(bool(torch.isfinite(value)) for value in terms.values()):
        raise FloatingPointError("Nonfinite SSL loss or diagnostics")
    if min(float(terms[k]) for k in ("token_std_max", "descriptor_std_max")) <= 1e-6:
        raise FloatingPointError("Collapsed tokens or mean384 descriptors")
    terms["loss"].backward()
    parameters = [p for p in model.parameters() if p.requires_grad]
    norm = torch.nn.utils.clip_grad_norm_(parameters, 1., error_if_nonfinite=True, foreach=False)
    if any(p.grad is None or not bool(torch.isfinite(p.grad).all()) for p in parameters):
        raise FloatingPointError("Missing or nonfinite trainable gradient")
    optimizer.step()
    momentum = model.update_teacher(step, STEPS, extra["teacher_logits"])
    scheduler.step()
    return dict(step=step, batch_indices=indices, batch_content_sha256=digest,
                gradient_norm_before_clip=float(norm), teacher_momentum=momentum,
                **{key: float(value.detach()) for key, value in terms.items()})


def representation_statistics(values):
    array = np.asarray(values, dtype=np.float64)
    std = array.std(0)
    singular = np.linalg.svd(array-array.mean(0), compute_uv=False)
    eigen = singular**2
    weights = eigen[eigen > 1e-20]
    weights = weights/weights.sum() if len(weights) else weights
    rank = float(np.exp(-np.sum(weights*np.log(weights)))) if len(weights) else 0.
    return dict(elements=len(array), std_min=float(std.min()), std_max=float(std.max()),
                std_mean=float(std.mean()), effective_rank=rank)


@torch.no_grad()
def validate(model, batches, device):
    before_center = model.delta.center.clone()
    was_training = model.training
    model.eval()
    totals, count, probabilities, scales, brightness = {}, 0, [], [], []
    descriptors = {role: [] for role in ("student", "teacher", "base")}
    aligned_mse = []
    try:
        for batch in batches:
            terms, extra = batch_terms(model, batch, device, details=True)
            n = len(batch["views"])
            for key, value in terms.items():
                totals[key] = totals.get(key, 0.) + float(value)*n
            count += n
            probabilities.append(extra["probabilities"].cpu())
            scales.append(batch["scales"].numpy())
            brightness.append(batch["views"].mean((2, 3, 4)).numpy())
            for role in descriptors:
                descriptors[role].append(extra[role+"_descriptor"].cpu().numpy())
            aligned_mse.append(float((extra["aligned_teacher"][:, 0]-extra["aligned_teacher"][:, 1]).square().mean())*n)
    finally:
        model.train(was_training)
    if not count or not np.isfinite(list(totals.values())).all() or not torch.equal(before_center, model.delta.center):
        raise FloatingPointError("Invalid diagnostic validation or mutated center")
    result = {key: value/count for key, value in totals.items()}
    result.update({key: float(value) for key, value in entropy_statistics(torch.cat(probabilities)).items()})
    result.update(elements=count, aligned_teacher_view_mse=sum(aligned_mse)/count,
                  loss_role="Moving EMA/head/center CE; diagnostic only, never checkpoint selection")
    values = {role: np.concatenate(chunks) for role, chunks in descriptors.items()}
    scale_values = np.repeat(np.concatenate(scales), 2)
    brightness_values = np.concatenate(brightness).reshape(-1)

    def stats_with_brightness(array, brightness_array):
        stats = representation_statistics(array)
        centered = array.astype(np.float64)-array.mean(0)
        target = brightness_array.astype(np.float64)-brightness_array.mean()
        denominator = np.sqrt((centered**2).sum(0)*(target**2).sum())
        corr = np.divide((centered*target[:, None]).sum(0), denominator,
                         out=np.zeros(array.shape[1]), where=denominator > 0)
        valid = denominator > 0
        stats["max_absolute_brightness_correlation"] = float(np.abs(corr[valid]).max()) if valid.any() else None
        stats["brightness_correlation_unavailable_reason"] = None if valid.any() else "No varying brightness/descriptor coordinate pair"
        return stats

    for role, array in values.items():
        per_window = array.reshape(-1, 384)
        stats = stats_with_brightness(per_window, brightness_values)
        stats["observation_unit"] = "One emitted mean384 descriptor per augmented view; two views per window"
        stats["per_scale"] = {str(int(scale)): stats_with_brightness(per_window[scale_values == scale], brightness_values[scale_values == scale])
                              for scale in sorted(set(scale_values))}
        if role != "base":
            reference = values["base"].reshape(-1, 384)
            norms = np.linalg.norm(per_window, axis=1)*np.linalg.norm(reference, axis=1)
            stats["mean_cosine_to_frozen"] = float(np.mean(np.sum(per_window*reference, axis=1)/np.maximum(norms, 1e-12)))
            stats["mse_to_frozen"] = float(np.mean((per_window-reference)**2))
            normalized = per_window/np.maximum(np.linalg.norm(per_window, axis=1, keepdims=True), 1e-12)
            reference_normalized = reference/np.maximum(np.linalg.norm(reference, axis=1, keepdims=True), 1e-12)
            stats["l2_mse_to_frozen"] = float(np.mean((normalized-reference_normalized)**2))
        result[role+"_descriptor"] = stats
    return result


def save_state(path, initialized, progress, config):
    model, optimizer, scheduler, sampler, augmentation = initialized
    if model.asset != config["asset"] or model.base_digest != config["base_state_sha256"]:
        raise ValueError("Delta checkpoint base differs from configuration")
    save_checkpoint(path, model=model.delta, optimizer=optimizer, scheduler=scheduler,
                    sampler=sampler, np_generator=augmentation, progress=progress, config=config)


def restore_state(path, initialized, config):
    model, optimizer, scheduler, sampler, augmentation = initialized
    if model.asset != config["asset"] or state_digest(model.backbone) != config["base_state_sha256"]:
        raise ValueError("Cannot restore delta over a different base")
    progress = load_checkpoint(path, model=model.delta, optimizer=optimizer, scheduler=scheduler,
                              sampler=sampler, np_generator=augmentation, config=config)
    model.train()
    return progress


def sync(device):
    if device == "cuda":
        torch.cuda.synchronize()


def resource_check(root, started, device):
    if time.perf_counter()-started > CAPS["seconds_per_fit_including_validation_and_checkpoint"]:
        raise TimeoutError("Per-fit time cap including setup/diagnostics/checkpoints reached")
    if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024 > CAPS["process_rss_bytes"]:
        raise MemoryError("Process RSS cap reached")
    if device == "cuda" and torch.cuda.max_memory_allocated() > CAPS["gpu_tensor_bytes"]:
        raise MemoryError("GPU tensor cap reached")
    if sum(p.stat().st_size for p in (root / "training").rglob("*.pt")) > CAPS["all_checkpoint_bytes"]:
        raise MemoryError("Checkpoint storage cap reached")


def external_failures(root):
    """Authenticate terminal process accounting without inventing step counts."""
    root = Path(root).resolve()
    path = root / "training/registry.json"
    if not path.exists():
        return {}
    registry = read(path)
    if registry["plan_sha256"] != file_hash(root / "plan.json"):
        raise ValueError("Registry belongs to another frozen plan")
    expected = {row["run_id"] for row in run_specs()}
    records = {}
    for row in registry["outcomes"]:
        if not row.get("external_termination"):
            continue
        ident = row["run_id"]
        if ident not in expected or ident in records or row["status"] != "failed" or row["returncode"] == 0:
            raise ValueError("Invalid terminal external-failure record")
        if Path(row["directory"]).resolve() != root / "training" / ident or row["completed_optimizer_steps"] is not None:
            raise ValueError("External failure has mismatched path or a fabricated step count")
        if (root / "training" / ident / "run.json").exists():
            raise ValueError("External-failure record conflicts with terminal run.json")
        for key in ("wall_seconds", "cpu_seconds", "peak_rss_bytes"):
            if not math.isfinite(row[key]) or row[key] < 0:
                raise ValueError("Invalid measured external-failure resource usage")
        log = (root / row["log_file"]).resolve()
        if not log.is_relative_to(root) or file_hash(log) != row["log_sha256"]:
            raise ValueError("Missing or changed external-failure process log")
        records[ident] = row
    return records


def fit_one(data_root, output, regime, seed, steps=STEPS, device="cuda"):
    root = Path(output).resolve()
    started = time.perf_counter()
    plan = verified_plan(data_root, root)
    spec = next((r for r in run_specs() if r["regime"] == regime and r["seed"] == seed), None)
    if spec is None or steps != STEPS:
        raise ValueError("Only the six declared fixed1000-step runs are allowed")
    prior = [read(p) for p in (root / "training").rglob("run.json")]
    configs = list((root / "training").rglob("config.json"))
    external = external_failures(root)
    if any(not p.with_name("run.json").exists() and str(p.parent.relative_to(root / "training")) not in external for p in configs):
        raise RuntimeError("Earlier attempt has no terminal accounting; no automatic restart")
    registry_path = root / "training/registry.json"
    prior_seconds = read(registry_path)["worker_wall_seconds"] if registry_path.exists() else sum(r["seconds"] for r in prior)
    if len(prior)+len(external) >= CAPS["max_total_fits"] or prior_seconds+900 > CAPS["max_total_fit_seconds"]:
        raise RuntimeError("Fit-count/total-time budget exhausted")
    directory = root / "training" / spec["run_id"]
    if directory.exists():
        raise FileExistsError("Run already attempted; no implicit retry")
    directory.mkdir(parents=True)
    deny_references()
    initialized = None
    result = dict(schema="stmdomains-pretrained-ssl26-fit-v1", **spec, status="failed",
                  completed_steps=0, completed_optimizer_steps=0, selected_step=None,
                  selected_checkpoint=None, selected_checkpoint_sha256=None, checkpoints=[],
                  loss_history=[], validation_history=[], train_probe_history=[], reference_access=False)
    progress = dict(step=0, history=[], validation_history=[], train_probe_history=[], degeneracy_streak=0)
    try:
        data = AdaptationData(data_root, regime)
        initialized = initialize(seed, device, plan["assets_root"])
        model = initialized[0]
        if device == "cuda":
            torch.cuda.reset_peak_memory_stats()
        config = dict(schema="stmdomains-pretrained-ssl26-run-v1", **spec, architecture=ARCHITECTURE,
            assets_root=plan["assets_root"], asset=model.asset, base_state_sha256=model.base_digest,
            data_root=str(preparation_root(data_root)), data=data.identity(), device=device,
            plan_sha256=file_hash(root / "plan.json"), protocol_sha256=file_hash(PROTOCOL_PATH),
            code_sha256=plan["code_sha256"], training_caps=CAPS, max_steps=STEPS, batch_size=BATCH_SIZE,
            selected_on="fixed_last_step", selected_role="teacher", checkpoint_interval=100,
            optimizer=dict(name="AdamW", backbone_lr=2e-5, head_lr=2e-4, matrix_weight_decay=.04,
                           other_weight_decay=0., clip_norm=1., foreach=False),
            scheduler="50-step linear warmup, cosine to0.1; fixed1000 schedule",
            teacher=dict(momentum_start=.996, momentum_end=1., center_momentum=.9),
            augmentation_rng_seed=seed+200, sampler_seed=seed+100, validation_seed=VALIDATION_SEED,
            train_probe_seed=740026, precision="float32", amp=False)
        write_json(directory / "config.json", config)
        result.update(config_file_sha256=file_hash(directory / "config.json"), config_hash=config_hash(config),
            base_checkpoint_sha256=model.asset["weights_sha256"], base_state_sha256=model.base_digest,
            initial_state_sha256=state_digest(model.delta), parameter_count=ARCHITECTURE["backbone_parameters"],
            trainable_parameter_count=ARCHITECTURE["trainable_parameters"], train_windows=len(data.train),
            validation_windows=len(data.validation), run_directory="training/"+spec["run_id"])
        validation = data.validation_batches()
        probe = data.train_probe_batches()
        validation_identity = dict(window_ids=[r["window_id"] for r in data.validation],
            batch_sha256=arrays_hash({f"{i}-{k}": v.numpy() for i, b in enumerate(validation) for k, v in b.items()}),
            selected_on="none; diagnostics only", seed=VALIDATION_SEED)
        write_json(directory / "validation.json", validation_identity)
        result["validation"] = validation_identity
        progress["validation_history"].append(dict(step=0, **validate(model, validation, device)))
        progress["train_probe_history"].append(dict(step=0, **validate(model, probe, device)))
        initial = directory / "step-0000.pt"
        save_state(initial, initialized, progress, config)
        result.update(initial_checkpoint=initial.name, initial_checkpoint_sha256=file_hash(initial))
        for step in range(1, STEPS+1):
            resource_check(root, started, device)
            record = train_step(*initialized, data, step, device)
            progress["step"] = step
            progress["history"].append(record)
            if step > 50:
                progress["degeneracy_streak"] = (progress["degeneracy_streak"]+1
                    if record["head_mutual_information"] <= 1e-6 else 0)
                if progress["degeneracy_streak"] >= 2:
                    raise FloatingPointError("Head mutual information<=1e-6 twice after warmup; task degeneration")
            if step % 100 == 0:
                progress["validation_history"].append(dict(step=step, **validate(model, validation, device)))
                progress["train_probe_history"].append(dict(step=step, **validate(model, probe, device)))
                model.frozen_proof()
                checkpoint = directory / f"step-{step:04}.pt"
                save_state(checkpoint, initialized, progress, config)
                result["checkpoints"].append(dict(step=step, file=checkpoint.name, sha256=file_hash(checkpoint)))
                sync(device)
                if step == 100:
                    result["first100_seconds_including_setup"] = time.perf_counter()-started
                resource_check(root, started, device)
                print(json.dumps(dict(run_id=spec["run_id"], step=step, seconds=time.perf_counter()-started)), flush=True)
        selected = result["checkpoints"][-1]
        result.update(status="completed", stop_reason="fixed_step_budget", error=None,
                      selected_step=STEPS, selected_checkpoint=selected["file"],
                      selected_checkpoint_sha256=selected["sha256"])
    except Exception as exc:
        result.update(status="failed", stop_reason=type(exc).__name__, error=str(exc))
        if initialized is not None and (directory / "config.json").exists():
            try:
                save_state(directory / "stopped.pt", initialized, progress, read(directory / "config.json"))
                result["stopped_checkpoint_sha256"] = file_hash(directory / "stopped.pt")
            except Exception as save_error:
                result["stop_save_error"] = str(save_error)
    sync(device)
    if initialized is not None:
        try:
            result["frozen_proof"] = initialized[0].frozen_proof()
        except Exception as exc:
            result.update(status="failed", stop_reason="frozen_proof", error=str(exc), selected_step=None,
                          selected_checkpoint=None, selected_checkpoint_sha256=None)
    result.update(completed_steps=progress["step"], completed_optimizer_steps=progress["step"],
        loss_history=progress["history"], validation_history=progress["validation_history"],
        train_probe_history=progress["train_probe_history"], seconds=time.perf_counter()-started,
        peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
        cuda_peak_allocated_bytes=torch.cuda.max_memory_allocated() if device == "cuda" and torch.cuda.is_initialized() else 0,
        cuda_peak_reserved_bytes=torch.cuda.max_memory_reserved() if device == "cuda" and torch.cuda.is_initialized() else 0,
        environment=dict(python=platform.python_version(), torch=torch.__version__, numpy=np.__version__,
                         cuda=torch.version.cuda, gpu=torch.cuda.get_device_name() if device == "cuda" and torch.cuda.is_initialized() else None))
    write_json(directory / "run.json", result)
    return result


def state_equal(first, second):
    if isinstance(first, torch.Tensor):
        return isinstance(second, torch.Tensor) and torch.equal(first.cpu(), second.cpu())
    if isinstance(first, np.ndarray):
        return isinstance(second, np.ndarray) and np.array_equal(first, second)
    if isinstance(first, dict):
        return isinstance(second, dict) and first.keys() == second.keys() and all(state_equal(first[k], second[k]) for k in first)
    if isinstance(first, (list, tuple)):
        return type(first) is type(second) and len(first) == len(second) and all(state_equal(a, b) for a, b in zip(first, second))
    return first == second


class ToyData:
    """Measured finite synthetic images solely for exact state/resume checks."""
    def __init__(self):
        self.images = np.random.default_rng(260010).uniform(.1, .9, (8, 1, 64, 64)).astype(np.float32)

    def sample_indices(self, sampler, batch_size):
        return torch.randint(8, (batch_size,), generator=sampler).tolist()

    def batch(self, indices, rng):
        base = self.images[indices]
        views = np.stack([base+rng.normal(0., .02, base.shape).astype(np.float32) for _ in range(2)], axis=1)
        return dict(views=torch.from_numpy(views), shifts=torch.zeros(len(base), 2, 2),
                    scales=torch.full((len(base),), 48.))


def resume_audit(device, seed, assets):
    data = ToyData()
    with tempfile.TemporaryDirectory(prefix="pretrained26-resume-") as temporary:
        directory = Path(temporary)
        continuous = initialize(seed, device, assets)
        config = dict(purpose="technical_only", seed=seed, asset=continuous[0].asset,
                      base_state_sha256=continuous[0].base_digest)
        history = [train_step(*continuous, data, step, device, batch_size=4) for step in range(1, 7)]
        save_state(directory / "continuous.pt", continuous, dict(step=6, history=history), config)
        proof = continuous[0].frozen_proof()
        del continuous
        split = initialize(seed, device, assets)
        history = [train_step(*split, data, step, device, batch_size=4) for step in range(1, 4)]
        save_state(directory / "middle.pt", split, dict(step=3, history=history), config)
        del split
        resumed = initialize(seed, device, assets)
        progress = restore_state(directory / "middle.pt", resumed, config)
        history = progress["history"] + [train_step(*resumed, data, step, device, batch_size=4) for step in range(4, 7)]
        save_state(directory / "resumed.pt", resumed, dict(step=6, history=history), config)
        left, right = read_checkpoint(directory / "continuous.pt"), read_checkpoint(directory / "resumed.pt")
        checks = {name: state_equal(left[name], right[name]) for name in ("model", "optimizer", "scheduler", "rng", "progress")}
    return dict(seed=seed, passed=all(checks.values()), checks=checks, frozen_proof=proof,
                optimizer_steps=12, scope="6 continuous versus3+save/restore+3; toy arrays; weights discarded")


def preflight(data_root, output, device, assets, resume_check):
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError("Preserve previous preflight")
    deny_references()
    with reporting_stage(output.parent, output.stem) as budget:
        initialized = initialize(SEEDS[0], device, assets)
        model = initialized[0]
        data = AdaptationData(data_root, "transfer")
        batch = data.batch(data.sample_indices(initialized[3], BATCH_SIZE), initialized[4])
        device_views = batch["views"].flatten(0, 1).to(device)
        before = state_digest(model.delta)
        with torch.no_grad():
            official = model.backbone.forward_features(transform(device_views))["x_norm_patchtokens"]
            prefix = model.prefix(device_views)
            wrapped = model.tokens(prefix, "student")
            teacher = model.tokens(prefix, "teacher")
        checks = dict(official_wrapper_bitwise=torch.equal(official, wrapped),
                      initial_teacher_student_bitwise=torch.equal(wrapped, teacher),
                      initial_mean384_bitwise=torch.equal(official.mean(1), wrapped.mean(1)))
        started = time.perf_counter()
        terms, _ = batch_terms(model, batch, device)
        terms["loss"].backward()
        sync(device)
        elapsed = time.perf_counter()-started
        checks["all_trainable_gradients_finite"] = all(p.grad is not None and bool(torch.isfinite(p.grad).all())
            for p in model.parameters() if p.requires_grad)
        checks["zero_optimizer_step_state_unchanged"] = state_digest(model.delta) == before
        proof = model.frozen_proof()
        model.zero_grad(set_to_none=True)
        validation = validate(model, [batch], device)
        checks["validation_no_center_or_weight_mutation"] = state_digest(model.delta) == before
        # Finite affine token fields expose sign/axis mistakes and interpolation padding.
        axis = torch.arange(8, dtype=torch.float32, device=device)
        yy, xx = torch.meshgrid(axis, axis, indexing="ij")
        shift = torch.tensor([[2., -2.]], device=device)
        field = (xx+2*yy)[None, None]
        actual = aligned_tokens(field, shift, torch.tensor([32.], device=device))[0, :, 0]
        expected = (xx[1:7, 1:7]+2*yy[1:7, 1:7]+.5).flatten()
        checks["correspondence_affine_exact"] = torch.equal(actual, expected)
        rejected = False
        try:
            transform(torch.full((1, 1, 64, 64), float("nan"), device=device))
        except ValueError:
            rejected = True
        checks["nonfinite_measured_input_rejected"] = rejected
        checks["gpu_tensor_budget"] = device != "cuda" or torch.cuda.max_memory_allocated() <= CAPS["gpu_tensor_bytes"]
        # Sampling/augmentation streams are the unchanged issue22 views of20.
        paired = []
        for seed in SEEDS:
            sampler_a = torch.Generator(device="cpu").manual_seed(seed+100)
            sampler_b = torch.Generator(device="cpu").manual_seed(seed+100)
            rng_a, rng_b = np.random.default_rng(seed+200), np.random.default_rng(seed+200)
            legacy = SSLTrainingData(data_root, "transfer")
            batches_equal = True
            hashes = []
            for _ in range(3):
                ia, ib = data.sample_indices(sampler_a, 4), legacy.sample_indices(sampler_b, 4)
                a, b = data.batch(ia, rng_a), legacy.batch(ib, rng_b)
                batches_equal &= ia == ib and state_equal(a, b)
                hashes.append(arrays_hash({name: value.numpy() for name, value in a.items()}))
            paired.append(dict(seed=seed, identical_batches=batches_equal, steps=3, batch_sha256=hashes))
        checks["original20_22_sampler_and_augmentation_identical"] = all(row["identical_batches"] for row in paired)
        del model, initialized
        resumes = [resume_audit(device, seed, assets) for seed in SEEDS] if resume_check else []
        result = dict(schema="stmdomains-pretrained-ssl26-preflight-v1", passed=all(checks.values()) and all(r["passed"] for r in resumes),
            checks=checks, resume=resumes, paired_data=paired, technical_optimizer_steps=sum(r["optimizer_steps"] for r in resumes),
            batch64_forward_backward_seconds=elapsed, zero_optimizer_forward_backward=1,
            frozen_proof=proof, diagnostics=validation, architecture=ARCHITECTURE,
            asset=asset_identity(assets), source_sha256=source_hashes(),
            cuda_peak_allocated_bytes=torch.cuda.max_memory_allocated() if device == "cuda" else 0,
            reference_access=False, resources=budget.measurements())
        write_json(output, result)
        if not result["passed"]:
            raise RuntimeError("Technical adaptation preflight failed; preserve evidence")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("preflight", "run"):
        p = sub.add_parser(name)
        p.add_argument("--data", type=Path, required=True)
        p.add_argument("--output", type=Path, required=True)
        p.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
        if name == "preflight":
            p.add_argument("--assets", type=Path, default=DEFAULT_ASSETS)
            p.add_argument("--resume-check", action="store_true")
        else:
            p.add_argument("--regime", choices=("transfer", "transductive"), required=True)
            p.add_argument("--seed", type=int, choices=SEEDS, required=True)
            p.add_argument("--steps", type=int, default=STEPS)
    args = parser.parse_args()
    if args.command == "preflight":
        result = preflight(args.data, args.output, args.device, args.assets, args.resume_check)
        print(json.dumps({k: result[k] for k in ("passed", "technical_optimizer_steps", "batch64_forward_backward_seconds")}))
    else:
        result = fit_one(args.data, args.output, args.regime, args.seed, args.steps, args.device)
        print(json.dumps({k: result[k] for k in ("run_id", "status", "completed_steps", "seconds")}))
        if result["status"] != "completed":
            raise SystemExit(2)


if __name__ == "__main__":
    main()
