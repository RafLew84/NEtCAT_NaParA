"""Run the six pinned fits once, retaining failed processes and exact costs."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

from ...bundle import file_hash, write_json
from .common import CAPS, read_json
from .prepare import verify_plan


def run_suite(root, device="cuda"):
    root = Path(root).resolve()
    plan = verify_plan(root)
    training = root / "training"
    if training.exists():
        raise FileExistsError("Preserve the first suite; no automatic restart")
    training.mkdir()
    specs = plan["run_specs"]
    registry = dict(schema="stmdomains-pretrained-ssl26-registry-v1", suite_finished=False,
        planned_run_ids=[r["run_id"] for r in specs], outcomes=[], runs=[],
        plan_sha256=file_hash(root / "plan.json"), worker_wall_seconds=0., worker_cpu_seconds=0.,
        quality_optimizer_steps_known=0, unknown_optimizer_steps=False)

    def save():
        registry["runs"] = registry["outcomes"]
        registry["completed_count"] = sum(r["status"] == "completed" for r in registry["outcomes"])
        temporary = training / "registry.pending.json"
        write_json(temporary, registry)
        temporary.replace(training / "registry.json")

    save()
    for spec in specs:
        directory = training / spec["run_id"]
        outcome = dict(run_id=spec["run_id"], directory=str(directory), status="skipped", reason=None)
        remaining = CAPS["max_total_fit_seconds"] - registry["worker_wall_seconds"]
        storage = sum(p.stat().st_size for p in training.rglob("*.pt"))
        if remaining < 930 or storage >= CAPS["all_checkpoint_bytes"]:
            outcome["reason"] = "Remaining declared suite time or checkpoint storage is insufficient; no replacement fit"
            registry["outcomes"].append(outcome)
            save()
            continue
        log = training / (spec["run_id"].replace("/", "--") + ".log")
        command = [sys.executable, "-m", "stmdomains.experiments.training.pretrained_ssl.fit", "run",
                   "--data", plan["data_root"], "--output", str(root), "--regime", spec["regime"],
                   "--seed", str(spec["seed"]), "--steps", "1000", "--device", device]
        started = time.monotonic()
        terminated = threading.Event()
        with log.open("w") as stream:
            child = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                     bufsize=1, start_new_session=True)

            def watchdog(pid=child.pid, event=terminated):
                # The worker checks its own900s cap and saves a stopped state.
                # This additional30s grace covers startup and a terminal write.
                try:
                    os.killpg(pid, 15)
                    event.set()
                except ProcessLookupError:
                    pass

            timer = threading.Timer(930, watchdog)
            timer.start()
            try:
                for line in child.stdout:
                    stream.write(line)
                    stream.flush()
                    print(line, end="", flush=True)
                _, status, usage = os.wait4(child.pid, 0)
                child.returncode = os.waitstatus_to_exitcode(status)
            finally:
                timer.cancel()
        seconds = time.monotonic() - started
        outcome.update(returncode=child.returncode, wall_seconds=seconds,
            cpu_seconds=usage.ru_utime + usage.ru_stime, peak_rss_bytes=usage.ru_maxrss * 1024,
            watchdog_termination=terminated.is_set(), command=command,
            log_file=str(log.relative_to(root)), log_sha256=file_hash(log))
        registry["worker_wall_seconds"] += seconds
        registry["worker_cpu_seconds"] += outcome["cpu_seconds"]
        report = directory / "run.json"
        if report.exists():
            record = read_json(report)
            outcome.update(status=record["status"], run_sha256=file_hash(report),
                           completed_optimizer_steps=record["completed_optimizer_steps"])
            registry["quality_optimizer_steps_known"] += record["completed_optimizer_steps"]
            if child.returncode != 0 or record["status"] != "completed":
                outcome.update(status="failed", reason=record.get("error") or f"Worker exited{child.returncode}")
        else:
            outcome.update(status="failed", reason="External termination/setup failure; no terminal run.json; optimizer-step count unknown",
                           external_termination=True, completed_optimizer_steps=None)
            registry["unknown_optimizer_steps"] = True
        registry["outcomes"].append(outcome)
        save()
    registry["suite_finished"] = True
    registry["checkpoint_bytes"] = sum(p.stat().st_size for p in training.rglob("*.pt"))
    save()
    print({key: registry[key] for key in ("suite_finished", "completed_count", "worker_wall_seconds", "quality_optimizer_steps_known")})
    return registry


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    args = parser.parse_args()
    run_suite(args.output, args.device)


if __name__ == "__main__":
    main()
