"""Reject new NanoTrack mypy diagnostics while accounting for recorded legacy errors."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.mypy_baseline import (
    TypecheckGateError, load_baseline, load_committed_baseline, run_mypy,
    error_counts, baseline_counts, evaluate, evaluate_baseline_ratchet,
    evaluate_scope_ratchet,
)


def check(root: Path, baseline: Path, reference: str, *, mypy_timeout: float = 180) -> dict:
    report: dict = {"status": "failed", "failures": []}
    try:
        current_baseline = load_baseline(baseline)
        allowed = baseline_counts(current_baseline)
        previous = load_committed_baseline(root, baseline, reference)
        if previous is not None:
            report["failures"].extend(evaluate_scope_ratchet(current_baseline, previous))
            report["failures"].extend(evaluate_baseline_ratchet(allowed, baseline_counts(previous)))
        if not (root / "nanotrack").is_dir():
            raise TypecheckGateError("NanoTrack source directory is missing")
        sources = ["nanotrack"] + [name for name in (
            "scripts/check_nanotrack_types.py", "scripts/mypy_baseline.py",
            "scripts/run_nanotrack_acceptance.py", "scripts/nanotrack_acceptance",
        ) if (root / name).exists()]
        report["sources"] = sources
        if report["failures"]:
            return report
        completed = run_mypy(root, sources, timeout=mypy_timeout)
        diagnostics = error_counts(completed.stdout)
        report.update(legacy_errors=sum(allowed.values()), current_errors=sum(diagnostics.values()),
                      mypy_exit_code=completed.returncode, output=completed.stdout, stderr=completed.stderr)
        if completed.returncode not in (0, 1) or (completed.returncode == 1 and not diagnostics) or completed.stderr.strip():
            raise TypecheckGateError("Mypy failed to complete a valid diagnostic run; see output/stderr")
        report["failures"].extend(evaluate(diagnostics, allowed))
        report["status"] = "passed" if not report["failures"] else "failed"
    except subprocess.TimeoutExpired as error:
        report.update(status="timeout", timeout_seconds=error.timeout)
        report["failures"].append(f"Mypy exceeded {error.timeout:g} seconds; its process was stopped")
    except (TypecheckGateError, OSError) as error:
        report["status"] = "configuration_error"
        report["failures"].append(str(error))
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    baseline = (args.baseline or root / "scripts/nanotrack_mypy_baseline.json").resolve()
    report = check(root, baseline, os.environ.get("NANOTRACK_RATCHET_REF", "HEAD").strip() or "HEAD")
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if report["status"] != "passed":
        for failure in report["failures"]:
            print(failure, file=sys.stderr)
        return 1
    print(f"NanoTrack types: PASS; {report['current_errors']} recorded legacy errors, no new diagnostics")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
