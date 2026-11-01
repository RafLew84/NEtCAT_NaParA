"""Audit saved masked-AE training mechanics without opening domain references."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import statistics

import numpy as np

from ...bundle import arrays_hash, file_hash, write_json
from ..checkpoint import config_hash, read_checkpoint
from .common import CAPS, reporting_stage
from .fit import SEEDS, deny_references, read, run_specs, verified_plan


def require(condition, message):
    if not condition:
        raise ValueError(message)


def audit(output, budget):
    root = Path(output).resolve()
    plan = read(root / "plan.json")
    verified_plan(plan["data_root"], root)
    specifications = {r["run_id"]: r for r in run_specs()}
    paths = sorted((root / "training").glob("*/*/z32/seed-*/run.json"))
    require(bool(paths), "No recorded fit outcomes")
    records, checkpoints_checked, base_batches = {}, 0, []
    for path in budget.checked(paths):
        run = read(path)
        ident = run["run_id"]
        require(ident in specifications and ident not in records, "Undeclared or repeated fit")
        require(path.parent == root / "training" / ident, "Run directory disagrees with identity")
        records[ident] = run
        config_path = path.parent / "config.json"
        config = read(config_path)
        require(file_hash(config_path) == run["config_file_sha256"], "Changed run configuration")
        require(config_hash(config) == run["config_hash"], "Changed config content")
        require(config["plan_sha256"] == file_hash(root / "plan.json"), "Run belongs to another plan")
        require(config["code_sha256"] == plan["code_sha256"], "Run used another numerical source freeze")
        require(run["parameter_count"] == 250513, "Capacity differs from AE21")
        require(run["completed_steps"] == run["completed_optimizer_steps"] == len(run["loss_history"]), "Step counts disagree")
        initial_path = path.parent / run["initial_checkpoint"]
        require(file_hash(initial_path) == run["initial_checkpoint_sha256"], "Changed initial checkpoint")
        initial = read_checkpoint(initial_path)
        require(initial["config_hash"] == config_hash(config) and initial["progress"]["step"] == 0, "Invalid initial checkpoint")
        digest = arrays_hash({name: value.numpy() for name, value in initial["model"].items()})
        require(digest == run["initial_state_sha256"], "Changed initial weights")
        require("mask_rng_state" in initial["progress"] and initial["rng"]["numpy_generator"] is not None,
                "Checkpoint omits mask or augmentation RNG")
        require(initial["optimizer"]["state"] == {}, "Initial checkpoint has optimization history")
        for entry in budget.checked(run["checkpoints"]):
            checkpoint = path.parent / entry["file"]
            require(file_hash(checkpoint) == entry["sha256"], "Changed periodic checkpoint")
            saved = read_checkpoint(checkpoint)
            require(saved["config_hash"] == config_hash(config), "Checkpoint config differs")
            require(saved["progress"]["step"] == entry["step"], "Checkpoint step differs")
            require("mask_rng_state" in saved["progress"] and saved["rng"]["numpy_generator"] is not None,
                    "Periodic checkpoint omits a random stream")
            require(len(saved["progress"]["history"]) == entry["step"], "Checkpoint history is incomplete")
            require(all(int(state["step"]) == entry["step"] for state in saved["optimizer"]["state"].values()),
                    "Optimizer step differs from checkpoint progress")
            checkpoints_checked += 1
        if run["status"] == "completed":
            selected = next(entry for entry in run["checkpoints"] if entry["step"] == run["selected_step"])
            require(selected["file"] == run["selected_checkpoint"] and selected["sha256"] == run["selected_checkpoint_sha256"],
                    "Selected checkpoint is not the recorded periodic state")
            if run["regime"] == "transfer":
                best = min(run["validation_history"], key=lambda value: (value["loss"], value["step"]))
                require(run["completed_steps"] == 2000 and best["step"] == run["selected_step"], "Wrong transfer checkpoint selection")
                require(best["loss"] == run["best_validation_loss"], "Selected validation loss differs")
            else:
                require(run["selected_step"] == run["completed_steps"], "Transduction selected an intermediate checkpoint")
        # ExistingAE32 provides a direct recorded check of the unchanged sampler
        # and augmentation, over every common step rather than a new AE fit.
        baseline = next(r for r in plan["baseline_runs"] if r["family"] == "ae" and
                        r["regime"] == run["regime"] and r["seed"] == run["seed"])
        historical = read(Path(baseline["directory"]) / "run.json")
        paired = list(zip(run["loss_history"], historical["loss_history"]))
        require(bool(paired), "No common historicalAE batch evidence")
        require(all(a["batch_content_sha256"] == b["batch_content_sha256"] and a["batch_indices"] == b["batch_indices"]
                    for a, b in paired), "Sampler/augmentation differs from matched AE21")
        base_batches.append(dict(run_id=ident, historical_AE_run=baseline["run_id"], matched_steps=len(paired)))
    pairs = []
    for regime in ("transfer", "transductive"):
        for seed in SEEDS:
            identifiers = [f"{regime}/{family}/z32/seed-{seed}" for family in ("mask25", "mask50")]
            if not all(ident in records for ident in identifiers):
                continue
            first, second = (records[ident] for ident in identifiers)
            require(first["initial_state_sha256"] == second["initial_state_sha256"], "Mask ratios have different initial weights")
            require(first["validation"]["image_content_sha256"] == second["validation"]["image_content_sha256"] and
                    first["validation"]["mask_order_sha256"] == second["validation"]["mask_order_sha256"],
                    "Validation images or nested block orders differ")
            paired = list(zip(first["loss_history"], second["loss_history"]))
            require(all(a["batch_content_sha256"] == b["batch_content_sha256"] and a["mask_order_sha256"] == b["mask_order_sha256"]
                        for a, b in paired), "Mask ratios changed sampling or block permutations")
            require(all(a["masked_pixels"] * 2 == b["masked_pixels"] and a["measured_pixels"] == b["measured_pixels"]
                        for a, b in paired), "Mask ratios do not cover exactly4/8 blocks")
            pairs.append(dict(regime=regime, seed=seed, identical_initialization=True, matched_steps=len(paired)))
    for family in ("mask25", "mask50"):
        transfers = [records.get(f"transfer/{family}/z32/seed-{seed}") for seed in SEEDS]
        if all(run and run["status"] == "completed" for run in transfers):
            expected = int(statistics.median(run["selected_step"] for run in transfers))
            for seed in SEEDS:
                run = records.get(f"transductive/{family}/z32/seed-{seed}")
                if run and run["status"] == "completed":
                    require(run["completed_steps"] == expected, "Transduction did not use its own ratio's median")
    checkpoint_bytes = sum(path.stat().st_size for path in (root / "training").rglob("*.pt"))
    total_seconds = sum(run["seconds"] for run in records.values())
    require(len(records) <= CAPS["max_total_fits"] and total_seconds <= CAPS["max_total_fit_seconds"], "Training budget exceeded")
    require(checkpoint_bytes <= CAPS["all_checkpoint_bytes"], "Checkpoint storage exceeded")
    return dict(schema="stmdomains-masked-ae25-training-audit-v1", passed=True,
        attempted_runs=len(records), completed_runs=sum(r["status"] == "completed" for r in records.values()),
        all_planned_fits_completed=len(records) == 12 and all(r["status"] == "completed" for r in records.values()),
        total_optimizer_steps=sum(r["completed_optimizer_steps"] for r in records.values()),
        total_fit_seconds=total_seconds, checkpoint_bytes=checkpoint_bytes,
        periodic_checkpoints_checked=checkpoints_checked, paired_mask_ratios=pairs,
        matched_historical_AE_batches=base_batches, reference_access=False,
        run_sha256={ident: file_hash(root / "training" / ident / "run.json") for ident in records},
        auditor_sha256=file_hash(Path(__file__)), plan_sha256=file_hash(root / "plan.json"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.output.resolve()
    target = root / "training-audit.json"
    if target.exists():
        raise FileExistsError("Preserve the previous training audit")
    deny_references()
    with reporting_stage(root, "training-audit") as budget:
        result = audit(root, budget)
        write_json(target, result)
    print(json.dumps({key: result[key] for key in ("passed", "attempted_runs", "completed_runs", "periodic_checkpoints_checked")}))


if __name__ == "__main__":
    main()
