"""Twelve bounded masked-AE fits; original21 data sampling and augmentation."""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import platform
import random
import resource
import statistics
import tempfile
import time

import numpy as np
import torch

from ...bundle import arrays_hash, file_hash, write_json
from ..checkpoint import capture_rng, config_hash, load_checkpoint, read_checkpoint, save_checkpoint
from ..fit import TrainingData, initialize as original_initialize, preparation_root
from .common import CAPS, PROTOCOL_PATH, reporting_stage
from .models import ARCHITECTURE, MASK_RATIOS, apply_mask, block_masks, make_model, masked_losses


SEEDS = (20261101, 20261102, 20261103)
TRANSFER_STEPS = 2000
MASK_VALIDATION_SEED = 740025
REPOSITORY = Path(__file__).resolve().parents[4]


def read(path):
    return json.loads(Path(path).read_text())


def deny_references():
    import sys
    def hook(event, args):
        if event == "open" and isinstance(args[0], (str, bytes, os.PathLike)):
            name = os.fsdecode(args[0]).replace("\\", "/")
            if "/evaluation/" in name or "/references/" in name or "manual_domain" in name:
                raise PermissionError("References denied to masked-AE training: " + name)
    sys.addaudithook(hook)


def source_hashes():
    own = Path(__file__).parent
    paths = [own / name for name in ("models.py", "fit.py", "common.py")]
    paths += [own.parent / name for name in ("models.py", "fit.py", "data.py", "checkpoint.py")]
    paths.append(own.parent.parent / "bundle.py")
    return {str(path.resolve().relative_to(REPOSITORY)): file_hash(path) for path in paths}


def run_specs():
    return [dict(run_id=f"{regime}/{family}/z32/seed-{seed}", regime=regime, family=family,
                 seed=seed, latent_dim=32, mask_fraction=MASK_RATIOS[family])
            for regime in ("transfer", "transductive") for family in MASK_RATIOS for seed in SEEDS]


def verified_plan(data_root, output):
    plan = read(Path(output) / "plan.json")
    if plan["schema"] != "masked-ae25-plan-v1" or plan["training_caps"] != CAPS:
        raise ValueError("Unexpected masked-AE plan or budget")
    for name, digest in plan["code_sha256"].items():
        path = Path(name)
        path = path if path.is_absolute() else REPOSITORY / path
        if file_hash(path) != digest:
            raise ValueError("Frozen numerical source changed: " + name)
    pinned = {str((Path(name) if Path(name).is_absolute() else REPOSITORY / name).resolve()): value
              for name, value in plan["code_sha256"].items()}
    for name, digest in source_hashes().items():
        if pinned.get(str((REPOSITORY / name).resolve())) != digest:
            raise ValueError("Incomplete model source freeze: " + name)
    for name, digest in plan["source_files"].items():
        if file_hash(Path(name)) != digest:
            raise ValueError("Changed source data or baseline: " + name)
    protocol = Path(plan["protocol_file"])
    protocol = protocol if protocol.is_absolute() else REPOSITORY / protocol
    if file_hash(protocol) != plan["protocol_sha256"] or file_hash(PROTOCOL_PATH) != plan["protocol_sha256"]:
        raise ValueError("Changed frozen protocol")
    root = preparation_root(data_root)
    if root != preparation_root(plan["data_root"]) or file_hash(root / "manifest.json") != plan["data_manifest_sha256"]:
        raise ValueError("Training data differs from the plan")
    expected = {(r["run_id"], r["family"], r["regime"], r["seed"]) for r in run_specs()}
    actual = {(r["run_id"], r["family"], r["regime"], r["seed"]) for r in plan["run_specs"]}
    if actual != expected or len(plan["run_specs"]) != 12:
        raise ValueError("Changed twelve-fit matrix")
    return plan


def initialize(family, seed, device):
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
    model = make_model(family).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=.001, weight_decay=.0001, foreach=False)
    scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, lr_lambda=lambda _: 1.)
    sampler = torch.Generator(device="cpu").manual_seed(seed + 100)
    augmentation = np.random.default_rng(seed + 200)
    mask_rng = np.random.default_rng(seed + 300)
    return model, optimizer, scheduler, sampler, augmentation, mask_rng


def validation_batches(data, family):
    """Original21 fixed images plus independent fixed, nested block masks."""
    rng = np.random.default_rng(MASK_VALIDATION_SEED)
    output, offset = [], 0
    for inputs, target in data.validation_batches():
        mask, order = block_masks(len(inputs), MASK_RATIOS[family], rng, with_order=True)
        output.append(dict(inputs=inputs, target=target, mask=mask, measured=torch.ones_like(mask),
            window_ids=[row["window_id"] for row in data.validation[offset:offset+len(inputs)]],
            mask_order=order))
        offset += len(inputs)
    return output


def validation_identity(batches):
    images = {f"{i}-{name}": batch[name].numpy() for i, batch in enumerate(batches) for name in ("inputs", "target")}
    masks = {str(i): batch["mask"].numpy() for i, batch in enumerate(batches)}
    order = {str(i): batch["mask_order"] for i, batch in enumerate(batches)}
    return dict(image_content_sha256=arrays_hash(images), mask_content_sha256=arrays_hash(masks),
                mask_order_sha256=arrays_hash(order), mask_seed=MASK_VALIDATION_SEED,
                window_ids=[ident for batch in batches for ident in batch["window_ids"]])


def train_step(model, optimizer, scheduler, sampler, augmentation, mask_rng, data,
               step, device, family, batch_size=64):
    indices = data.sample_indices(sampler, batch_size)
    inputs, target = data.batch(indices, augmentation)
    mask, order = block_masks(len(inputs), MASK_RATIOS[family], mask_rng, with_order=True)
    base_digest = arrays_hash({"inputs": inputs.numpy(), "targets": target.numpy()})
    mask_digest = arrays_hash({"mask": mask.numpy()})
    inputs, target, mask = inputs.to(device), target.to(device), mask.to(device)
    measured = torch.ones_like(mask)
    optimizer.zero_grad(set_to_none=True)
    prediction = model(apply_mask(inputs, mask, measured), sample=False)["reconstruction"]
    terms = masked_losses(prediction, target, mask, measured)
    if not bool(torch.isfinite(terms["loss"])):
        raise FloatingPointError("Non-finite masked reconstruction loss")
    terms["loss"].backward()
    norm = torch.nn.utils.clip_grad_norm_(model.parameters(), 1., error_if_nonfinite=True, foreach=False)
    if any(p.grad is None or not bool(torch.isfinite(p.grad).all()) for p in model.parameters()):
        raise FloatingPointError("Missing or non-finite gradient")
    optimizer.step()
    scheduler.step()
    return dict(step=step, batch_indices=indices, batch_content_sha256=base_digest,
                mask_content_sha256=mask_digest, mask_order_sha256=arrays_hash({"order": order}),
                gradient_norm_before_clip=float(norm), **{name: float(terms[name].detach())
                for name in ("loss", "masked_mse", "visible_mse", "full_mse")},
                masked_pixels=int(terms["masked_pixels"]), measured_pixels=int(terms["measured_pixels"]))


@torch.inference_mode()
def validate(model, batches, device):
    totals = {name: 0. for name in ("loss", "masked_mse", "visible_mse", "full_mse")}
    count = 0
    was_training = model.training
    model.eval()
    try:
        for batch in batches:
            values = {name: batch[name].to(device) for name in ("inputs", "target", "mask", "measured")}
            prediction = model(apply_mask(values["inputs"], values["mask"], values["measured"]), sample=False)["reconstruction"]
            terms = masked_losses(prediction, values["target"], values["mask"], values["measured"])
            for name in totals:
                totals[name] += float(terms[name]) * len(values["inputs"])
            count += len(values["inputs"])
    finally:
        model.train(was_training)
    if not count or not np.isfinite(list(totals.values())).all():
        raise FloatingPointError("Missing or non-finite validation")
    return {name: value / count for name, value in totals.items()} | {"elements": count}


def model_digest(model):
    return arrays_hash({name: value.detach().cpu().numpy() for name, value in model.state_dict().items()})


def save_state(path, initialized, progress, config):
    model, optimizer, scheduler, sampler, augmentation, mask_rng = initialized
    complete_progress = dict(progress, mask_rng_state=deepcopy(mask_rng.bit_generator.state))
    save_checkpoint(path, model=model, optimizer=optimizer, scheduler=scheduler, sampler=sampler,
                    np_generator=augmentation, progress=complete_progress, config=config)


def restore_state(path, initialized, config):
    model, optimizer, scheduler, sampler, augmentation, mask_rng = initialized
    progress = load_checkpoint(path, model=model, optimizer=optimizer, scheduler=scheduler, sampler=sampler,
                               np_generator=augmentation, config=config)
    mask_state = progress["mask_rng_state"]
    if mask_state["bit_generator"] != type(mask_rng.bit_generator).__name__:
        raise ValueError("Checkpoint mask RNG differs")
    mask_rng.bit_generator.state = mask_state
    return progress


def sync(device):
    if device == "cuda":
        torch.cuda.synchronize()


def fit_one(data_root, output, regime, family, seed, steps, device="cuda"):
    output = Path(output).resolve()
    started = time.perf_counter()
    plan = verified_plan(data_root, output)
    spec = next((r for r in run_specs() if (r["regime"], r["family"], r["seed"]) == (regime, family, seed)), None)
    if spec is None:
        raise ValueError("Undeclared fit")
    if regime == "transfer":
        expected = TRANSFER_STEPS
    else:
        transfers = [read(output / f"training/transfer/{family}/z32/seed-{s}/run.json") for s in SEEDS]
        if any(row["status"] != "completed" for row in transfers):
            raise ValueError("Transduction requires three completed transfers for its own ratio")
        expected = int(statistics.median(row["selected_step"] for row in transfers))
    if steps != expected:
        raise ValueError(f"Expected exactly {expected} steps")
    previous_configs = list((output / "training").rglob("config.json"))
    if any(not p.with_name("run.json").exists() for p in previous_configs):
        raise RuntimeError("An earlier fit is unfinished; no implicit retry or continuation")
    previous = [read(p.with_name("run.json")) for p in previous_configs]
    if len(previous) >= CAPS["max_total_fits"] or sum(r["seconds"] for r in previous) + 900 > CAPS["max_total_fit_seconds"]:
        raise RuntimeError("Fit-count or total-time budget exhausted")
    directory = output / "training" / spec["run_id"]
    if directory.exists():
        raise FileExistsError("Run already attempted; no implicit retry")
    deny_references()
    data = TrainingData(data_root, regime)
    config = dict(schema="stmdomains-masked-ae25-run-v1", **spec, architecture=ARCHITECTURE,
        data=data.identity(), data_root=str(preparation_root(data_root)), device=device,
        plan_sha256=file_hash(output / "plan.json"), protocol_sha256=file_hash(PROTOCOL_PATH),
        code_sha256=plan["code_sha256"], training_caps=CAPS, max_steps=steps,
        precision="float32", batch_size=64, amp=False,
        optimizer=dict(name="AdamW", lr=.001, weight_decay=.0001, clip_norm=1.),
        scheduler="constant", checkpoint_interval=100, augmentation_rng_seed=seed+200,
        mask_rng_seed=seed+300, mask_validation_seed=MASK_VALIDATION_SEED,
        selected_on="fixed_mask_unlabelled_validation_mse" if regime == "transfer" else "fixed_last_step")
    directory.mkdir(parents=True)
    write_json(directory / "config.json", config)
    initialized = initialize(family, seed, device)
    model = initialized[0]
    batches = validation_batches(data, family) if regime == "transfer" else []
    validation = validation_identity(batches)
    write_json(directory / "validation.json", validation)
    initial_digest = model_digest(model)
    progress = dict(step=0, history=[], validation_history=[], selected_step=None, best_validation_loss=None)
    initial_path = directory / "step-0000.pt"
    save_state(initial_path, initialized, progress, config)
    if device == "cuda":
        torch.cuda.reset_peak_memory_stats()
    checkpoints, first100, error = [], None, None
    status, stop_reason = "completed", "fixed_step_budget"
    try:
        for step in range(1, steps + 1):
            if time.perf_counter() - started >= CAPS["seconds_per_fit_including_validation_and_checkpoint"]:
                raise TimeoutError("Per-fit time cap reached")
            record = train_step(*initialized, data, step, device, family)
            progress["step"] = step
            progress["history"].append(record)
            if step == 100:
                sync(device)
                first100 = time.perf_counter() - started
            if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024 > CAPS["process_rss_bytes"]:
                raise MemoryError("Process RSS cap reached")
            if device == "cuda" and torch.cuda.max_memory_allocated() > CAPS["gpu_tensor_bytes"]:
                raise MemoryError("CUDA tensor cap reached")
            if step % 100 == 0 or step == steps:
                if regime == "transfer":
                    result = validate(model, batches, device)
                    progress["validation_history"].append(dict(step=step, **result))
                    if progress["best_validation_loss"] is None or result["loss"] < progress["best_validation_loss"]:
                        progress["best_validation_loss"], progress["selected_step"] = result["loss"], step
                else:
                    progress["selected_step"] = step
                path = directory / f"step-{step:04}.pt"
                save_state(path, initialized, progress, config)
                checkpoints.append(dict(step=step, file=path.name, sha256=file_hash(path)))
                sync(device)
                elapsed = time.perf_counter() - started
                print(json.dumps(dict(run_id=spec["run_id"], step=step, seconds=elapsed,
                                      selected_step=progress["selected_step"])), flush=True)
                if elapsed > CAPS["seconds_per_fit_including_validation_and_checkpoint"]:
                    raise TimeoutError("Validation/checkpoint exceeded per-fit cap")
                if sum(p.stat().st_size for p in (output / "training").rglob("*.pt")) > CAPS["all_checkpoint_bytes"]:
                    raise MemoryError("Checkpoint storage cap reached")
    except Exception as exc:
        status, stop_reason, error = "failed", type(exc).__name__, str(exc)
        save_state(directory / "stopped.pt", initialized, progress, config)
    sync(device)
    selected = next((row for row in checkpoints if row["step"] == progress["selected_step"]), None)
    result = dict(schema="stmdomains-masked-ae25-fit-result-v1", **spec,
        run_directory="training/" + spec["run_id"], config_hash=config_hash(config),
        config_file_sha256=file_hash(directory / "config.json"), status=status, stop_reason=stop_reason, error=error,
        selected_step=progress["selected_step"] if status == "completed" else None,
        selected_checkpoint=selected["file"] if selected and status == "completed" else None,
        selected_checkpoint_sha256=selected["sha256"] if selected and status == "completed" else None,
        initial_checkpoint=initial_path.name, initial_checkpoint_sha256=file_hash(initial_path),
        initial_state_sha256=initial_digest, completed_steps=progress["step"],
        completed_optimizer_steps=progress["step"], seconds=time.perf_counter()-started,
        first100_seconds_including_setup=first100, best_validation_loss=progress["best_validation_loss"],
        validation=validation, validation_history=progress["validation_history"], loss_history=progress["history"],
        parameter_count=sum(p.numel() for p in model.parameters()), checkpoints=checkpoints,
        train_windows=len(data.train), validation_windows=len(data.validation),
        peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
        cuda_peak_allocated_bytes=torch.cuda.max_memory_allocated() if device == "cuda" else 0,
        cuda_peak_reserved_bytes=torch.cuda.max_memory_reserved() if device == "cuda" else 0,
        environment=dict(python=platform.python_version(), torch=torch.__version__, numpy=np.__version__,
                         cuda=torch.version.cuda, gpu=torch.cuda.get_device_name() if device == "cuda" else None),
        reference_access=False)
    write_json(directory / "run.json", result)
    return result


def state_equal(first, second):
    if isinstance(first, torch.Tensor):
        return isinstance(second, torch.Tensor) and torch.equal(first.cpu(), second.cpu())
    if isinstance(first, np.ndarray):
        return isinstance(second, np.ndarray) and np.array_equal(first, second)
    if isinstance(first, dict):
        return isinstance(second, dict) and first.keys() == second.keys() and all(state_equal(first[k], second[k]) for k in first)
    if isinstance(first, (tuple, list)):
        return type(first) is type(second) and len(first) == len(second) and all(state_equal(a, b) for a, b in zip(first, second))
    return first == second


class ToyData:
    """Finite measured synthetic arrays for resume mechanics, never fit selection."""
    def __init__(self):
        self.images = np.random.default_rng(250010).uniform(.1, .9, (8, 1, 64, 64)).astype(np.float32)

    def sample_indices(self, sampler, batch_size):
        return torch.randint(8, (batch_size,), generator=sampler).tolist()

    def batch(self, indices, rng):
        target = self.images[indices].copy()
        noisy = target + rng.normal(0., .02, target.shape).astype(np.float32)
        return torch.from_numpy(noisy), torch.from_numpy(target)


def resume_audit(device, seed):
    data, config = ToyData(), dict(purpose="masked_ae25_resume_technical", device=device, family="mask50", seed=seed)
    with tempfile.TemporaryDirectory(prefix="masked-ae25-resume-") as temporary:
        directory = Path(temporary)
        continuous = initialize("mask50", seed, device)
        full_history = [train_step(*continuous, data, step, device, "mask50", batch_size=4) for step in range(1, 7)]
        save_state(directory / "continuous.pt", continuous, dict(step=6, history=full_history), config)
        split = initialize("mask50", seed, device)
        split_history = [train_step(*split, data, step, device, "mask50", batch_size=4) for step in range(1, 4)]
        save_state(directory / "middle.pt", split, dict(step=3, history=split_history), config)
        resumed = initialize("mask50", seed, device)
        progress = restore_state(directory / "middle.pt", resumed, config)
        split_history = progress["history"] + [train_step(*resumed, data, step, device, "mask50", batch_size=4) for step in range(4, 7)]
        save_state(directory / "resumed.pt", resumed, dict(step=6, history=split_history), config)
        left, right = read_checkpoint(directory / "continuous.pt"), read_checkpoint(directory / "resumed.pt")
        checks = {name: state_equal(left[name], right[name]) for name in ("model", "optimizer", "scheduler", "rng", "progress")}
    return dict(seed=seed, passed=all(checks.values()), checks=checks, optimizer_steps=12,
                scope="6 continuous versus3+save/restore+3 on synthetic measured arrays; weights discarded")


def measured_loss_audit(device):
    mask = block_masks(1, .5, np.random.default_rng(250012)).to(device)
    measured = torch.ones_like(mask)
    position = torch.nonzero(mask, as_tuple=True)
    excluded = tuple(int(axis[0]) for axis in position)
    measured[excluded] = False
    target = torch.full((1, 1, 64, 64), .3, dtype=torch.float32, device=device)
    prediction = torch.linspace(0., 1., 4096, device=device).reshape(1, 1, 64, 64).requires_grad_()
    original = masked_losses(prediction, target, mask, measured)
    original["loss"].backward()
    gradient = prediction.grad.detach().clone()
    nan_prediction, nan_target = prediction.detach().clone().requires_grad_(), target.clone()
    with torch.no_grad():
        nan_prediction[excluded] = float("nan")
        nan_target[excluded] = float("nan")
    ignored = masked_losses(nan_prediction, nan_target, mask, measured)
    ignored["loss"].backward()
    visible_changed = target.clone()
    visible_changed[~mask & measured] = 1000.
    visible_loss = masked_losses(prediction.detach(), visible_changed, mask, measured)["loss"]
    changed_input = target.clone()
    changed_input[mask] = 2000.
    input_isolated = torch.equal(apply_mask(target, mask), apply_mask(changed_input, mask))
    rejected = False
    try:
        apply_mask(target, mask, measured)
    except ValueError:
        rejected = True
    checks = dict(unmeasured_nan_loss_unchanged=torch.equal(original["loss"], ignored["loss"]),
                  unmeasured_nan_gradient_unchanged=torch.equal(gradient, nan_prediction.grad),
                  visible_targets_do_not_change_masked_loss=torch.equal(original["loss"], visible_loss),
                  hidden_input_values_do_not_enter_encoder=input_isolated,
                  partial_measurement_input_rejected=rejected)
    return dict(passed=all(checks.values()), checks=checks)


def paired_data_audit(data, device):
    results = []
    for seed in SEEDS:
        original = original_initialize("ae", 32, seed, device)
        states = {family: initialize(family, seed, device) for family in MASK_RATIOS}
        hashes = {family: model_digest(state[0]) for family, state in states.items()}
        identical_init = all(value == model_digest(original[0]) for value in hashes.values())
        same_batches, independent_rng, nested = True, True, True
        for _ in range(3):
            indices = data.sample_indices(original[3], 4)
            reference = data.batch(indices, original[4])
            masks, orders = {}, {}
            for family, state in states.items():
                chosen = data.sample_indices(state[3], 4)
                batch = data.batch(chosen, state[4])
                same_batches &= chosen == indices and all(torch.equal(a, b) for a, b in zip(batch, reference))
                before = (state[3].get_state().clone(), deepcopy(state[4].bit_generator.state),
                          torch.get_rng_state().clone(), deepcopy(np.random.get_state()))
                masks[family], orders[family] = block_masks(4, MASK_RATIOS[family], state[5], with_order=True)
                after = (state[3].get_state(), state[4].bit_generator.state,
                         torch.get_rng_state(), np.random.get_state())
                independent_rng &= state_equal(before, after)
            nested &= bool((masks["mask25"] <= masks["mask50"]).all()) and np.array_equal(orders["mask25"], orders["mask50"])
        count = sum(p.numel() for p in original[0].parameters())
        results.append(dict(seed=seed, initial_state_sha256=model_digest(original[0]),
            bitwise_initialization_matches_AE21=identical_init, parameter_count=count,
            three_paired_augmented_batches=same_batches, independent_mask_rng=independent_rng,
            nested_masks=nested, optimizer_steps=0,
            passed=bool(identical_init and count == 250513 and same_batches and independent_rng and nested)))
    return dict(passed=all(r["passed"] for r in results), seeds=results)


def preflight(data_root, output, device="cpu", *, resume_check=False):
    deny_references()
    data = TrainingData(data_root, "transfer")
    initialized = initialize("mask50", SEEDS[0], device)
    model, optimizer, _, sampler, augmentation, mask_rng = initialized
    inputs, target = data.batch(data.sample_indices(sampler, 4), augmentation)
    mask = block_masks(4, .5, mask_rng)
    initial = model_digest(model)
    inputs, target, mask = inputs.to(device), target.to(device), mask.to(device)
    terms = masked_losses(model(apply_mask(inputs, mask), sample=False)["reconstruction"], target, mask)
    terms["loss"].backward()
    gradients = {name: value.grad.detach().clone() for name, value in model.named_parameters()}
    optimizer.zero_grad(set_to_none=True)
    second = masked_losses(model(apply_mask(inputs, mask), sample=False)["reconstruction"], target, mask)
    second["loss"].backward()
    deterministic = torch.equal(terms["loss"], second["loss"]) and all(torch.equal(gradients[name], p.grad) for name, p in model.named_parameters())
    a = block_masks(4, .25, np.random.default_rng(250011))
    b = block_masks(4, .5, np.random.default_rng(250011))
    nested = bool((a <= b).all()) and bool((a.flatten(1).sum(1) == 1024).all()) and bool((b.flatten(1).sum(1) == 2048).all())
    result = dict(schema="stmdomains-masked-ae25-preflight-v1", device=device,
        data=data.identity(), code_sha256=source_hashes(), optimizer_steps=0,
        deterministic_forward_backward=deterministic, weights_unchanged=model_digest(model) == initial,
        nested_exact_block_masks=nested, parameter_count=sum(p.numel() for p in model.parameters()),
        reference_access=False, training_fit=False)
    result["measured_loss_guards"] = measured_loss_audit(device)
    result["paired_AE21_data"] = paired_data_audit(data, device)
    if resume_check:
        audits = [resume_audit(device, seed) for seed in SEEDS]
        result["resume"] = dict(passed=all(r["passed"] for r in audits), seeds=audits,
                                optimizer_steps=sum(r["optimizer_steps"] for r in audits))
        result["optimizer_steps"] = result["resume"]["optimizer_steps"]
    result["passed"] = bool(deterministic and result["weights_unchanged"] and nested
        and result["measured_loss_guards"]["passed"] and result["paired_AE21_data"]["passed"]
        and (not resume_check or result["resume"]["passed"]))
    write_json(output, result)
    if not result["passed"]:
        raise RuntimeError("Masked-AE technical preflight failed")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run")
    check = sub.add_parser("preflight")
    for child in (run, check):
        child.add_argument("--data", type=Path, required=True)
        child.add_argument("--output", type=Path, required=True)
        child.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    run.add_argument("--regime", choices=("transfer", "transductive"), required=True)
    run.add_argument("--family", choices=tuple(MASK_RATIOS), required=True)
    run.add_argument("--seed", type=int, choices=SEEDS, required=True)
    run.add_argument("--steps", type=int, required=True)
    check.add_argument("--resume-check", action="store_true")
    args = parser.parse_args()
    if args.command == "run":
        result = fit_one(args.data, args.output, args.regime, args.family, args.seed, args.steps, args.device)
        print(json.dumps({k: result[k] for k in ("run_id", "status", "selected_step", "completed_steps", "seconds")}), flush=True)
        if result["status"] != "completed":
            raise SystemExit(1)
    else:
        if args.output.exists():
            raise FileExistsError("Preserve the previous technical preflight")
        with reporting_stage(args.output.parent, args.output.stem):
            result = preflight(args.data, args.output, args.device, resume_check=args.resume_check)
        print(json.dumps({k: result[k] for k in ("passed", "optimizer_steps", "deterministic_forward_backward")}))


if __name__ == "__main__":
    main()
