from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Sequence


# Support both direct execution and imports by tests.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.mypy_baseline import (
    TypecheckGateError, run_git, load_baseline, load_committed_baseline,
    run_mypy, error_counts, baseline_counts, evaluate,
    evaluate_baseline_ratchet, evaluate_scope_ratchet,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASELINE = PROJECT_ROOT / "scripts" / "domain_analysis_mypy_baseline.json"
RATCHET_REFERENCE_ENV = "DOMAIN_ANALYSIS_RATCHET_REF"


def _discover_sources(root: Path, baseline_commit: str) -> tuple[str, ...]:
    changed = run_git(
        root,
        "diff",
        "--name-only",
        "--diff-filter=ACMRT",
        baseline_commit,
        "--",
        "moltrack",
    ).splitlines()
    untracked = run_git(
        root,
        "ls-files",
        "--others",
        "--exclude-standard",
        "--",
        "moltrack",
    ).splitlines()
    always_checked: set[str] = set()
    for source_root in (
        root / "moltrack" / "analysis" / "domain_analysis",
        root / "moltrack" / "ui",
    ):
        if source_root.is_dir():
            always_checked.update(
                path.relative_to(root).as_posix()
                for path in source_root.rglob("*.py")
                if path.is_file()
                and not any(
                    part.startswith("_prototype")
                    for part in path.relative_to(source_root).parts
                )
            )
    candidates = {
        path.replace("\\", "/") for path in (*changed, *untracked)
    } | always_checked
    return tuple(
        sorted(
            path
            for path in candidates
            if path.endswith(".py") and (root / path).is_file()
        )
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the ratcheted MolTrack Domain Analysis mypy gate."
    )
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.root.resolve()
    baseline_path = args.baseline.resolve()
    try:
        payload = load_baseline(baseline_path)
        sources = _discover_sources(root, payload["scope"]["baseline_commit"])
        allowed = baseline_counts(payload)
        ratchet_reference = os.environ.get(RATCHET_REFERENCE_ENV, "HEAD").strip()
        committed_payload = load_committed_baseline(
            root,
            baseline_path,
            ratchet_reference or "HEAD",
        )
        baseline_failures = (
            evaluate_scope_ratchet(payload, committed_payload)
            + evaluate_baseline_ratchet(allowed, baseline_counts(committed_payload))
            if committed_payload is not None
            else []
        )
    except TypecheckGateError as error:
        print(f"Domain Analysis typecheck configuration error: {error}", file=sys.stderr)
        return 2

    if baseline_failures:
        print("Domain Analysis typecheck gate failed:")
        for failure in baseline_failures:
            print(f"- {failure}")
        return 1
    if not sources:
        print("Domain Analysis typecheck gate found no production Python sources.")
        return 0

    completed = run_mypy(root, sources)
    current = error_counts(completed.stdout)
    failures = evaluate(current, allowed)
    if completed.returncode not in (0, 1):
        print(completed.stdout, end="")
        print(completed.stderr, end="", file=sys.stderr)
        return completed.returncode
    if failures:
        print(completed.stdout, end="")
        print("Domain Analysis typecheck gate failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print(
        "Domain Analysis typecheck gate passed "
        f"for {len(sources)} production files with {sum(current.values())} "
        "ratcheted legacy errors."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
