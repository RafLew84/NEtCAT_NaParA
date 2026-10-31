"""Bounded21a training; every real optimization step belongs to one of11 runs.

The original21 loop/data/checkpoint implementation is reused through temporary
process-local substitutions. Its source and all original artifacts stay intact.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

import numpy as np
import torch

from ...bundle import arrays_hash, file_hash, write_json
from .. import fit as original
from ..checkpoint import config_hash, read_checkpoint
from ..data import extract_patch
from .models import ARCHITECTURE, BETAS, FAMILIES, make_model

SEEDS = original.SEEDS
MODULE = "stmdomains.experiments.training.rvae_followup.fit"
PROTOCOL = Path(__file__).with_name("protocol.json")
CAPS = {
    "seconds_per_fit_including_validation_and_checkpoint": 900,
    "gpu_tensor_bytes": 8 * 1024**3, "process_rss_bytes": 12 * 1024**3,
    "all_checkpoint_bytes": 4 * 1024**3,
}


def read_json(path):
    return json.loads(Path(path).read_text())


def source_hashes():
    own = Path(__file__).parent
    names = [own / name for name in ("models.py", "fit.py", "protocol.json")]
    names += [own.parent / name for name in ("models.py", "fit.py", "checkpoint.py", "data.py")]
    names += [own.parent.parent / "bundle.py"]
    root = Path.cwd().resolve()
    return {str(p.resolve().relative_to(root)): file_hash(p) for p in names}


def diagnostic_selection(data: original.TrainingData):
    indices = np.linspace(0, len(data.train)-1, 16, dtype=int).tolist()
    rows = [data.train[i] for i in indices]
    patches = np.stack([extract_patch(data.arrays[r["sample_id"]], r, data.normalizer,
                                      shift_xy=(0., 0.)) for r in rows]).astype(np.float32)
    return rows, patches


class DiagnosticData(original.TrainingData):
    def __init__(self, root, regime):
        super().__init__(root, regime)
        self.train, patches = diagnostic_selection(self)
        self.validation = list(self.train)
        self.patches = torch.from_numpy(patches[:, None])

    def sample_indices(self, generator, batch_size):
        return torch.randint(16, (batch_size,), generator=generator).tolist()

    def batch(self, indices, rng, *, validation=False):
        value = self.patches[indices]
        return value.clone(), value.clone()

    def identity(self):
        return {**super().identity(), "purpose": "memorization_only",
                "sampling": "uniform 16 predetermined training patches with replacement",
                "augmentation": "none", "validation": "same16trainingpatches; no generalization claim",
                "patch_content_sha256": arrays_hash({"patches": self.patches.numpy()})}


def losses(output, target, step, *, beta, validation=False, diagnostic=False):
    mse = (output["reconstruction"]-target).square().flatten(1).mean(1)
    kl = output["kl_per_sample"]
    weight = beta if validation or diagnostic else beta * min(1., step/200.)
    return {"loss": (mse+weight*kl).mean(), "mse": mse.mean(), "kl": kl.mean(), "beta": weight}


def run_specs():
    specs = [dict(run_id=f"diagnostic/{name}", family="rvae", beta=beta,
                  seed=20261101, diagnostic=True, steps=2000, seconds_cap=300)
             for name, beta in (("beta-1e-3", .001), ("beta-0", 0.))]
    specs += [dict(run_id=f"training/transfer/{family}/z32/seed-{seed}", family=family,
                   beta=BETAS[family], seed=seed, diagnostic=False, steps=2000, seconds_cap=900)
              for family in FAMILIES for seed in SEEDS]
    return specs


def prepare_plan(data_root, baseline, output):
    output = Path(output)
    if (output / "plan.json").exists():
        raise FileExistsError("Plan already frozen; do not replace it")
    if any((output/spec["run_id"]).exists() for spec in run_specs()):
        raise ValueError("A run exists before the plan freeze")
    data = original.TrainingData(data_root, "transfer")
    rows, patches = diagnostic_selection(data)
    baseline = Path(baseline).resolve()
    baselines = []
    for family in ("ae", "rvae"):
        for seed in SEEDS:
            path = baseline/f"training/transfer/{family}/z32/seed-{seed}"
            result = read_json(path/"run.json")
            if result["status"] != "completed":
                raise ValueError("Required21 baseline did not complete")
            if file_hash(path/result["selected_checkpoint"]) != result["selected_checkpoint_sha256"]:
                raise ValueError("Changed baseline checkpoint")
            step2000 = next(row for row in result["checkpoints"] if row["step"] == 2000)
            if file_hash(path/step2000["file"]) != step2000["sha256"]:
                raise ValueError("Changed baseline fixed-step checkpoint")
            baselines.append(dict(family=family, seed=seed, path=str(path),
                                  run_sha256=file_hash(path/"run.json"),
                                  selected_checkpoint_sha256=result["selected_checkpoint_sha256"],
                                  step2000_sha256=step2000["sha256"]))
    plan = dict(schema="stmdomains-rvae-followup-plan-v1", architecture=ARCHITECTURE,
                protocol_sha256=file_hash(PROTOCOL), code_sha256=source_hashes(),
                prepared=str(Path(data_root).resolve()), baseline=str(baseline),
                data=data.identity(), baselines=baselines, runs=run_specs(),
                diagnostic=dict(window_ids=[r["window_id"] for r in rows],
                                selection="16 integer linspace positions over sorted eligible transfer train grid windows",
                                scales=[r["scale_raw_px"] for r in rows],
                                patches_sha256=arrays_hash({"patches": patches[:, None]}),
                                beta_schedule="constant from step1; no augmentation; stochastic posterior",
                                batch_size=64, interpretation="training memorization, not generalization"),
                full_fit=dict(max_steps=2000, checkpoint_interval=100, batch_size=64,
                              beta_warmup_steps=200, validation_beta="configuration target from first validation",
                              selected_on="minimum own-beta unlabelled validation loss; earliest tie",
                              source_labels_used=False),
                caps={**CAPS, "diagnostic_seconds_per_run": 300, "maximum_fit_count": 9,
                      "maximum_diagnostic_runs": 2, "total_steps": 22000,
                      "total_training_seconds": 8700, "postprocess_cpu_seconds": 7200},
                purpose="frozen before first21a optimization step; no new21/22 training or gate tuning")
    write_json(output/"plan.json", plan)
    shutil.copyfile(PROTOCOL, output/"protocol.json")
    np.savez_compressed(output/"diagnostic-inputs.npz", images=patches[:, None])
    write_json(output/"training/architecture.json", dict(architecture=ARCHITECTURE,
               plan_sha256=file_hash(output/"plan.json"), code_sha256=plan["code_sha256"]))
    print(json.dumps({"plan": str(output/"plan.json"), "sha256": file_hash(output/"plan.json"),
                      "runs": len(plan["runs"])}), flush=True)
    return plan


def verified_plan(data_root, baseline, output):
    plan = read_json(Path(output)/"plan.json")
    if plan["code_sha256"] != source_hashes() or plan["protocol_sha256"] != file_hash(PROTOCOL):
        raise ValueError("Changed code/protocol after plan freeze")
    if plan["protocol_sha256"] != file_hash(Path(output)/"protocol.json"):
        raise ValueError("Changed local protocol snapshot")
    if plan["prepared"] != str(Path(data_root).resolve()) or plan["baseline"] != str(Path(baseline).resolve()):
        raise ValueError("Input roots differ from frozen plan")
    if plan["runs"] != run_specs():
        raise ValueError("Run list differs from frozen plan")
    return plan


@contextmanager
def patched_loop(spec, output, plan):
    # The worker owns its process; this context also makes CPU unit checks safe.
    names = ("make_model", "losses", "validate", "make_config", "TrainingData", "initialize")
    saved = {name: getattr(original, name) for name in names}
    beta, diagnostic = spec["beta"], spec["diagnostic"]

    def selected_losses(pred, target, step, *, validation=False):
        return losses(pred, target, step, beta=beta, validation=validation, diagnostic=diagnostic)

    def selected_validate(model, batches, device):
        result = saved["validate"](model, batches, device)
        return {**result, "beta": beta}

    def selected_initialize(family, latent_dim, seed, device):
        values = saved["initialize"](family, latent_dim, seed, device)
        state = {name: value.detach().cpu().numpy() for name, value in values[0].state_dict().items()}
        shared = {name: value for name, value in state.items() if not name.startswith("decoder.0.")}
        write_json(Path(output)/spec["run_id"]/"initialization.json", dict(
            full_state_sha256=arrays_hash(state), shared_state_sha256=arrays_hash(shared),
            torch_cpu_rng_sha256=arrays_hash({"state": torch.get_rng_state().numpy()}),
            sampler_rng_sha256=arrays_hash({"state": values[3].get_state().numpy()}),
            seed=seed, optimization_steps=0))
        return values

    def selected_config(data, family, latent_dim, seed, device, steps, **kwargs):
        config = saved["make_config"](data, family, latent_dim, seed, device, steps, **kwargs)
        if diagnostic:
            if ([r["window_id"] for r in data.train] != plan["diagnostic"]["window_ids"] or
                arrays_hash({"patches": data.patches.numpy()}) != plan["diagnostic"]["patches_sha256"]):
                raise ValueError("Diagnostic inputs differ from frozen plan")
        elif data.identity() != plan["data"]:
            raise ValueError("Training data identity differs from frozen plan")
        config.update(schema="stmdomains-rvae-followup-run-v1",
                      purpose="issue21a_memorization" if diagnostic else "issue21a_fit",
                      architecture=ARCHITECTURE, plan_sha256=file_hash(Path(output)/"plan.json"),
                      code_sha256=plan["code_sha256"], validation_beta=beta, target_beta=beta,
                      diagnostic=diagnostic, run_id=spec["run_id"],
                      limits={**CAPS, "seconds_per_fit_including_validation_and_checkpoint": spec["seconds_cap"]})
        if diagnostic:
            config["selected_on"] = "minimum training16 posterior-mean loss; diagnostic only"
        return config

    original.make_model = make_model
    original.losses = selected_losses
    original.validate = selected_validate
    original.initialize = selected_initialize
    original.make_config = selected_config
    if diagnostic:
        original.TrainingData = DiagnosticData
    try:
        yield
    finally:
        for name, value in saved.items():
            setattr(original, name, value)


def worker(data_root, baseline, output, run_id, device):
    plan = verified_plan(data_root, baseline, output)
    spec = next(spec for spec in plan["runs"] if spec["run_id"] == run_id)
    target = Path(output)/run_id
    from ..predict import deny_evaluation_paths
    deny_evaluation_paths()
    with patched_loop(spec, output, plan):
        result = original.fit_one(Path(data_root), target, spec["family"], 32, spec["seed"],
                                  "transfer", spec["steps"], device, Path(output))
    result.update(run_id=run_id, target_beta=spec["beta"], diagnostic=spec["diagnostic"])
    write_json(target/"run.json", result)
    return result


def run_stage(stage, data_root, baseline, output, device):
    output = Path(output)
    plan = verified_plan(data_root, baseline, output)
    specs = [spec for spec in plan["runs"] if spec["diagnostic"] == (stage == "diagnostic")]
    if stage == "train":
        if any(not (output/spec["run_id"]/"run.json").exists()
               for spec in plan["runs"] if spec["diagnostic"]):
            raise ValueError("Complete the two diagnostic runs first")
    for spec in specs:
        target = output/spec["run_id"]
        if target.exists():
            raise FileExistsError(f"Run already attempted; no retry: {target}")
    results = []
    logdir = output/"logs"
    logdir.mkdir(exist_ok=True)
    for spec in specs:
        if total_recorded_seconds(output) >= plan["caps"]["total_training_seconds"]:
            raise RuntimeError("Combined training time cap reached")
        target = output/spec["run_id"]
        log = logdir/(spec["run_id"].replace("/", "--")+".log")
        print("start "+spec["run_id"], flush=True)
        command = [sys.executable, "-m", MODULE, "worker", "--data", str(Path(data_root).resolve()),
                   "--baseline", str(Path(baseline).resolve()), "--output", str(output.resolve()),
                   "--device", device, "--run-id", spec["run_id"]]
        started = time.perf_counter()
        with log.open("x") as stream:
            completed = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, check=False)
        if not (target/"run.json").exists():
            # An unexpected worker failure consumes this run, never a replacement.
            write_json(target/"run.json", dict(status="failed", stop_reason="worker_failed_without_result",
                       exit_code=completed.returncode, family=spec["family"], seed=spec["seed"],
                       latent_dim=32, regime="transfer", run_id=spec["run_id"],
                       completed_steps=None, reserved_steps_consumed=2000,
                       seconds=time.perf_counter()-started, diagnostic=spec["diagnostic"],
                       selected_checkpoint=None, checkpoints=[]))
        result = read_json(target/"run.json")
        results.append({**result, "path": str(target.resolve())})
        print(json.dumps({"run": spec["run_id"], "status": result["status"],
                          "steps": result["completed_steps"], "seconds": result["seconds"],
                          "selected_step": result.get("selected_step")}), flush=True)
        registry = dict(schema="stmdomains-rvae-followup-suite-v1", stage=stage,
                        plan_sha256=file_hash(output/"plan.json"), runs=results,
                        completed=sum(row["status"] == "completed" for row in results),
                        total_fit_seconds=sum(row["seconds"] for row in results))
        path = output/("diagnostic/registry.json" if stage == "diagnostic" else "training/registry.json")
        write_json(path, registry)
    return registry


def total_recorded_seconds(output):
    return sum(read_json(path).get("seconds", 0.) for path in Path(output).rglob("run.json"))


def audit(data_root, baseline, output):
    output = Path(output)
    plan = verified_plan(data_root, baseline, output)
    rows, failures = [], []
    full_steps, diag_steps, checkpoints = 0, 0, 0
    for spec in plan["runs"]:
        target = output/spec["run_id"]
        result = read_json(target/"run.json")
        if result["status"] != "completed":
            failures.append({"run_id": spec["run_id"], "status": result["status"], "reason": result["stop_reason"]})
        step_count = result.get("completed_steps")
        step_count = 2000 if step_count is None else step_count
        if spec["diagnostic"]:
            diag_steps += step_count
        else:
            full_steps += step_count
        if not (target/"config.json").exists():
            rows.append({"run_id": spec["run_id"], "status": result["status"]})
            continue
        config = read_json(target/"config.json")
        if config_hash(config) != result["config_hash"] or file_hash(target/"config.json") != result["config_file_sha256"]:
            raise ValueError("Run configuration changed")
        for checkpoint in result["checkpoints"]:
            if file_hash(target/checkpoint["file"]) != checkpoint["sha256"]:
                raise ValueError("Checkpoint changed")
            checkpoints += 1
        history = result["validation_history"]
        if history:
            best = min(history, key=lambda row: (row["loss"], row["step"]))
            if best["step"] != result["selected_step"]:
                raise ValueError("Wrong validation-selected checkpoint")
            if not all(row["beta"] == spec["beta"] for row in history):
                raise ValueError("Variable validation beta")
        matched = None
        init = read_json(target/"initialization.json")
        torch.manual_seed(spec["seed"])
        base_model = original.make_model("rvae", 32)
        base_state = {name: value.detach().numpy() for name, value in base_model.state_dict().items()}
        shared_state = {name: value for name, value in base_state.items() if not name.startswith("decoder.0.")}
        init_match = init["shared_state_sha256"] == arrays_hash(shared_state)
        rng_match = init["torch_cpu_rng_sha256"] == arrays_hash({"state": torch.get_rng_state().numpy()})
        if "fourier" not in spec["family"]:
            init_match = init_match and init["full_state_sha256"] == arrays_hash(base_state)
        if not init_match or not rng_match:
            raise ValueError("Initialization/shared weights or posterior CPU RNG differ from baseline")
        if not spec["diagnostic"]:
            prior = read_json(Path(baseline)/f"training/transfer/rvae/z32/seed-{spec['seed']}/run.json")
            matched = (result["validation_content_sha256"] == prior["validation_content_sha256"] and
                       all(a["batch_content_sha256"] == b["batch_content_sha256"] and
                           a["batch_indices"] == b["batch_indices"]
                           for a, b in zip(result["loss_history"], prior["loss_history"])))
            if not matched:
                raise ValueError("Input batches differ from original same-seed baseline")
        rows.append(dict(run_id=spec["run_id"], status=result["status"],
                         completed_steps=result["completed_steps"], selected_step=result["selected_step"],
                         baseline_batches_identical=matched, checkpoint_count=len(result["checkpoints"]),
                         initialization_matches_baseline=init_match, constructor_rng_matches_baseline=rng_match,
                         seconds=result["seconds"], parameter_count=result["parameter_count"],
                         peak_rss_bytes=result["peak_rss_bytes"],
                         cuda_peak_allocated_bytes=result["cuda_peak_allocated_bytes"]))
    diagnostic_runs = [read_json(output/spec["run_id"]/"run.json") for spec in plan["runs"] if spec["diagnostic"]]
    left, right = diagnostic_runs
    diag_match = (all(a["batch_content_sha256"] == b["batch_content_sha256"] for a, b in
                      zip(left["loss_history"], right["loss_history"]))
                  if left.get("loss_history") and right.get("loss_history") else None)
    if diag_match is False:
        raise ValueError("Diagnostic batches differ")
    total_seconds = total_recorded_seconds(output)
    checkpoint_bytes = original._checkpoint_bytes(output)
    if full_steps+diag_steps > 22000 or checkpoint_bytes > CAPS["all_checkpoint_bytes"]:
        raise ValueError("Overall step/storage cap exceeded")
    for base in plan["baselines"]:
        if file_hash(Path(base["path"])/"run.json") != base["run_sha256"]:
            raise ValueError("Original baseline metadata changed")
    result = dict(schema="stmdomains-rvae-followup-training-audit-v1", runs=rows, failures=failures,
                  completed_full=sum(not s["diagnostic"] and r["status"] == "completed" for s, r in zip(plan["runs"], rows)),
                  completed_diagnostic=sum(s["diagnostic"] and r["status"] == "completed" for s, r in zip(plan["runs"], rows)),
                  full_steps=full_steps, diagnostic_steps=diag_steps, seconds=total_seconds,
                  checkpoint_bytes=checkpoint_bytes, checkpoints_verified=checkpoints,
                  diagnostic_batches_identical=diag_match, plan_sha256=file_hash(output/"plan.json"),
                  source_hashes_unchanged=True, baseline_metadata_unchanged=True,
                  within_training_time_cap=total_seconds <= 8700)
    write_json(output/"training/training-audit.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("plan", "diagnostic", "train", "audit", "worker"))
    parser.add_argument("--data", type=Path, default=Path(".scratch/training-20"))
    parser.add_argument("--baseline", type=Path, default=Path(".scratch/autoencoder-21"))
    parser.add_argument("--output", type=Path, default=Path(".scratch/rvae-21a"))
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    parser.add_argument("--run-id")
    args = parser.parse_args()
    if args.stage == "plan":
        prepare_plan(args.data, args.baseline, args.output)
    elif args.stage == "worker":
        result = worker(args.data, args.baseline, args.output, args.run_id, args.device)
        if result["status"] != "completed":
            raise SystemExit(1)
    elif args.stage == "audit":
        result = audit(args.data, args.baseline, args.output)
        print(json.dumps({k: v for k, v in result.items() if k not in ("runs", "failures")}))
    else:
        run_stage(args.stage, args.data, args.baseline, args.output, args.device)


if __name__ == "__main__":
    main()
