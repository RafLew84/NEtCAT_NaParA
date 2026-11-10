"""Read-only audit of all six adaptation outcomes and delta checkpoints."""
from __future__ import annotations

import argparse
from collections import defaultdict
import math
from pathlib import Path

import torch

from ...bundle import arrays_hash, file_hash, write_json
from ..checkpoint import config_hash, read_checkpoint
from .common import CAPS, reporting_stage
from .fit import STEPS, deny_references, external_failures, read, run_specs, verified_plan
from .models import ARCHITECTURE, asset_identity


def require(condition, message):
    if not condition:
        raise ValueError(message)


def expected_delta_shapes(assets):
    """Derive the suffix from authenticated upstream weights; head is explicit."""
    identity = asset_identity(assets)
    base = torch.load(identity["weights_file"], map_location="cpu", weights_only=True)
    suffix = {"block."+name[len("blocks.11."):]: tuple(value.shape)
              for name, value in base.items() if name.startswith("blocks.11.")}
    suffix.update({name: tuple(value.shape) for name, value in base.items() if name.startswith("norm.")})
    suffix.update({"head.mlp.0.weight": (256, 384), "head.mlp.0.bias": (256,),
                   "head.mlp.2.weight": (64, 256), "head.mlp.2.bias": (64,),
                   "head.last_layer.weight_g": (256, 1), "head.last_layer.weight_v": (256, 64)})
    expected = {role+"."+name: shape for role in ("student", "teacher") for name, shape in suffix.items()}
    expected["center"] = (1, 1, 256)
    require(len(expected) == 45, "Official backbone/head state schema changed")
    return expected


def audit(root, budget):
    root = Path(root).resolve()
    plan = read(root / "plan.json")
    verified_plan(plan["data_root"], root)
    delta_shapes = expected_delta_shapes(plan["assets_root"])
    expected = {row["run_id"] for row in run_specs()}
    external = external_failures(root)
    registry_path = root / "training/registry.json"
    registry = read(registry_path) if registry_path.exists() else None
    if registry is not None:
        require(registry["suite_finished"] is True, "Audit requires a finished suite")
        require(set(registry["planned_run_ids"]) == expected, "Registry plan mismatch")
    paths = sorted((root / "training").glob("*/*/seed-*/run.json"))
    records, checks, initial_heads = {}, 0, defaultdict(list)
    for path in budget.checked(paths):
        run = read(path)
        ident = run["run_id"]
        require(ident in expected and ident not in records, "Unexpected or duplicate fit outcome")
        require(path.parent == root / "training" / ident, "Run path mismatch")
        records[ident] = run
        require(run["status"] in ("completed", "failed"), "Nonterminal fit")
        require(run["reference_access"] is False, "Training read reference labels")
        require(run["completed_steps"] == run["completed_optimizer_steps"] == len(run["loss_history"]), "Step accounting mismatch")
        if not (path.parent / "config.json").exists():
            require(run["status"] == "failed" and run["completed_steps"] == 0, "Missing config after training")
            continue
        config = read(path.parent / "config.json")
        require(file_hash(path.parent / "config.json") == run["config_file_sha256"], "Changed configuration")
        require(config_hash(config) == run["config_hash"], "Invalid config hash")
        require(config["plan_sha256"] == file_hash(root / "plan.json"), "Changed plan")
        require(config["code_sha256"] == plan["code_sha256"], "Different numerical code")
        require(config["selected_on"] == "fixed_last_step" and config["selected_role"] == "teacher", "Data-selected checkpoint")
        require(run["trainable_parameter_count"] == ARCHITECTURE["trainable_parameters"], "Changed trainable capacity")
        require(run["parameter_count"] == ARCHITECTURE["backbone_parameters"], "Changed backbone capacity")
        require(run["base_checkpoint_sha256"] == config["asset"]["weights_sha256"], "Changed required base")
        require(run.get("frozen_proof", {}).get("unchanged") is True, "Missing unchanged-base proof")
        if "initial_checkpoint" not in run:
            require(run["status"] == "failed" and run["completed_steps"] == 0, "Missing initial state after training")
            continue
        entries = [dict(step=0, file=run["initial_checkpoint"], sha256=run["initial_checkpoint_sha256"])] + run["checkpoints"]
        if "stopped_checkpoint_sha256" in run:
            entries.append(dict(step=run["completed_steps"], file="stopped.pt", sha256=run["stopped_checkpoint_sha256"]))
        for entry in budget.checked(entries):
            p = path.parent / entry["file"]
            require(file_hash(p) == entry["sha256"], "Changed saved checkpoint")
            state = read_checkpoint(p)
            require(state["config_hash"] == run["config_hash"], "Checkpoint config mismatch")
            require(state["progress"]["step"] == entry["step"], "Checkpoint step mismatch")
            require(len(state["progress"]["history"]) == entry["step"], "Checkpoint lacks complete history")
            require(state["rng"]["numpy_generator"] is not None, "Missing augmentation RNG")
            require(set(state["model"]) == set(delta_shapes), "Missing or extra delta checkpoint tensor")
            require(all(tuple(state["model"][name].shape) == shape and state["model"][name].dtype == torch.float32
                        for name, shape in delta_shapes.items()), "Wrong delta checkpoint tensor shape or dtype")
            for role in ("student", "teacher"):
                value = state["model"][role+".head.last_layer.weight_g"]
                require(torch.equal(value, torch.ones_like(value)), "Frozen head scale changed")
            if entry["step"] == 0:
                require(not state["optimizer"]["state"], "Initial state includes optimizer updates")
                digest = arrays_hash({k: v.numpy() for k, v in state["model"].items()})
                require(digest == run["initial_state_sha256"], "Changed initialization")
                first = {k[8:]: v for k, v in state["model"].items() if k.startswith("student.")}
                second = {k[8:]: v for k, v in state["model"].items() if k.startswith("teacher.")}
                require(first.keys() == second.keys() and all(torch.equal(first[k], second[k]) for k in first), "Initial teacher differs from student")
                initial_heads[run["seed"]].append(digest)
            else:
                require(all(int(v["step"]) == entry["step"] for v in state["optimizer"]["state"].values()), "Optimizer state step mismatch")
            checks += 1
        for step, row in enumerate(run["loss_history"], 1):
            require(row["step"] == step and len(row["batch_indices"]) == 64, "Wrong step or sampling batch")
            expected_momentum = 1-.004*(math.cos(math.pi*step/STEPS)+1)/2
            require(row["teacher_momentum"] == expected_momentum, "EMA schedule mismatch")
        if run["status"] == "completed":
            require(run["completed_steps"] == run["selected_step"] == STEPS, "Wrong fixed checkpoint")
            selected = run["checkpoints"][-1]
            require(selected["file"] == run["selected_checkpoint"] and selected["sha256"] == run["selected_checkpoint_sha256"], "Wrong exported teacher state")
            require([row["step"] for row in run["checkpoints"]] == list(range(100, 1001, 100)), "Checkpoint interval changed")
            for key in ("validation_history", "train_probe_history"):
                require([row["step"] for row in run[key]] == list(range(0, 1001, 100)), "Incomplete diagnostics")
            require(run["validation_windows"] == 270, "Diagnostic validation IDs changed")
    require(bool(records) or bool(external) or registry is not None, "No training outcomes")
    require(all(len(set(values)) == 1 for values in initial_heads.values()), "Same seed differs across regimes")
    total = registry["worker_wall_seconds"] if registry is not None else sum(row["seconds"] for row in records.values())
    known_steps = sum(r["completed_steps"] for r in records.values())
    skipped = []
    if registry is not None:
        outcomes = {row["run_id"]: row for row in registry["outcomes"]}
        require(len(outcomes) == len(registry["outcomes"]) and set(outcomes) == expected, "Registry omits or repeats planned outcomes")
        require(registry["quality_optimizer_steps_known"] == known_steps, "Registry known-step total mismatch")
        require(registry["unknown_optimizer_steps"] == bool(external), "Registry unknown-step flag mismatch")
        for ident, outcome in outcomes.items():
            if ident in records:
                require(outcome["run_sha256"] == file_hash(root / "training" / ident / "run.json"), "Registry run hash mismatch")
                require(outcome["completed_optimizer_steps"] == records[ident]["completed_steps"], "Registry step mismatch")
            elif ident not in external:
                require(outcome["status"] == "skipped" and bool(outcome["reason"]), "Unaccounted missing run")
                skipped.append(ident)
    size = sum(p.stat().st_size for p in (root / "training").rglob("*.pt"))
    require(len(records)+len(external) <= 6 and total <= CAPS["max_total_fit_seconds"] and size <= CAPS["all_checkpoint_bytes"], "Training budget exceeded")
    return dict(schema="stmdomains-pretrained-ssl26-training-audit-v1", passed=True,
        attempted_runs=len(records)+len(external), completed_runs=sum(r["status"] == "completed" for r in records.values()),
        all_planned_fits_completed=set(records) == expected and all(r["status"] == "completed" for r in records.values()),
        total_optimizer_steps=None if external else known_steps, known_optimizer_steps=known_steps,
        unknown_optimizer_steps=bool(external), external_termination=list(external.values()),
        skipped_run_ids=skipped, total_fit_seconds=total,
        worker_cpu_seconds=registry["worker_cpu_seconds"] if registry is not None else None,
        checkpoint_bytes=size, checkpoints_checked=checks, reference_access=False,
        failed_run_ids=[ident for ident, r in records.items() if r["status"] == "failed"],
        run_sha256={ident: file_hash(root / "training" / ident / "run.json") for ident in records},
        plan_sha256=file_hash(root / "plan.json"), auditor_sha256=file_hash(Path(__file__)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    target = args.output / "training-audit.json"
    if target.exists():
        raise FileExistsError("Preserve previous training audit")
    deny_references()
    with reporting_stage(args.output, "training-audit") as budget:
        result = audit(args.output, budget)
        write_json(target, result)
    print({k: result[k] for k in ("passed", "attempted_runs", "completed_runs", "checkpoints_checked")})


if __name__ == "__main__":
    main()
