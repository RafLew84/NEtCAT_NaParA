"""Fresh-process continuation check of both actual issue-21 model families."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

from ..bundle import write_json
from .checkpoint import load_checkpoint, read_checkpoint, save_checkpoint
from .fit import TrainingData, initialize, make_config, train_step, validate
from .gpu_probe import compare_states


def worker(data_root: Path, out: Path, family: str, device: str, phase: str) -> None:
    data = TrainingData(data_root, "transfer")
    config = make_config(data, family, 32, 20261101, device, 6, purpose="technical_issue21_resume")
    model, optimizer, scheduler, sampler, augmentation = initialize(family, 32, 20261101, device)
    validation = data.validation_batches()
    progress = {"step": 0, "history": [], "validation_history": [], "best_validation_loss": None}
    if phase == "resume":
        progress = load_checkpoint(out / "first.pt", model=model, optimizer=optimizer,
                                   scheduler=scheduler, sampler=sampler, np_generator=augmentation,
                                   config=config)
    stop = 3 if phase == "first" else 6
    for step in range(progress["step"] + 1, stop + 1):
        progress["history"].append(train_step(model, optimizer, scheduler, sampler, augmentation,
                                               data, step, device))
        progress["step"] = step
        if step % 3 == 0:
            value = validate(model, validation, device)
            progress["validation_history"].append({"step": step, **value})
            if progress["best_validation_loss"] is None or value["loss"] < progress["best_validation_loss"]:
                progress["best_validation_loss"] = value["loss"]
    save_checkpoint(out / f"{phase}.pt", model=model, optimizer=optimizer, scheduler=scheduler,
                    sampler=sampler, np_generator=augmentation, progress=progress, config=config)


def check(data_root: Path, out: Path, device: str) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    report = {"schema": "stmdomains-issue21-resume-v1", "device": device,
              "seed": 20261101, "batch_size": 64, "absolute_tolerance": 1e-6,
              "scope": "technical6vs3+3; unlabelled fixed validation after3/6; not hyperparameter training",
              "families": {}}
    for family in ("ae", "rvae"):
        target = out / family
        target.mkdir(exist_ok=True)
        for phase in ("full", "first", "resume"):
            subprocess.run([sys.executable, "-m", "stmdomains.experiments.training.resume_check",
                            "--data", str(data_root.resolve()), "--out", str(target.resolve()),
                            "--device", device, "--worker", phase, "--family", family], check=True)
        left, right = (read_checkpoint(target / f"{name}.pt") for name in ("full", "resume"))
        comparisons = {key: compare_states(left[key], right[key]) for key in
                       ("model", "optimizer", "scheduler", "rng", "progress", "config", "runtime")}
        report["families"][family] = {"comparison": comparisons,
                                     "passed": all(row["passed"] for row in comparisons.values())}
    report["passed"] = all(row["passed"] for row in report["families"].values())
    write_json(out / "resume-report.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    parser.add_argument("--worker", choices=("full", "first", "resume"))
    parser.add_argument("--family", choices=("ae", "rvae"))
    args = parser.parse_args()
    if args.worker:
        worker(args.data, args.out, args.family, args.device, args.worker)
    else:
        result = check(args.data, args.out, args.device)
        print(json.dumps({"passed": result["passed"], "report": str(args.out / "resume-report.json")}))
        if not result["passed"]:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
