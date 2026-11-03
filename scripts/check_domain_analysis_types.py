from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASELINE = PROJECT_ROOT / "scripts" / "domain_analysis_mypy_baseline.json"
MYPY_OPTIONS = (
    "--ignore-missing-imports",
    "--follow-imports=silent",
    "--show-error-codes",
    "--no-error-summary",
)
RATCHET_REFERENCE_ENV = "DOMAIN_ANALYSIS_RATCHET_REF"
ERROR_LINE = re.compile(
    r"^(?P<path>.+?):(?P<line>\d+)(?::\d+)?: error: "
    r"(?P<message>.*?)(?:  \[(?P<code>[^]]+)\])?$"
)


class TypecheckGateError(ValueError):
    """Raised when the typecheck gate configuration is invalid."""


def _run_git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        check=False,
        text=True,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise TypecheckGateError(detail or f"git {' '.join(args)} failed")
    return completed.stdout


def _validate_baseline(payload: Any, source: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise TypecheckGateError(f"Typecheck baseline {source} must be an object")
    if payload.get("schema_version") != 1:
        raise TypecheckGateError(
            f"Unsupported baseline schema_version: {payload.get('schema_version')!r}"
        )
    scope = payload.get("scope")
    if not isinstance(scope, dict) or not isinstance(scope.get("baseline_commit"), str):
        raise TypecheckGateError("Baseline scope.baseline_commit must be a string")
    if not isinstance(payload.get("errors"), dict):
        raise TypecheckGateError("Baseline errors must be an object")
    return payload


def _load_baseline(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise TypecheckGateError(f"Cannot read typecheck baseline {path}: {error}") from error
    return _validate_baseline(payload, str(path))


def _load_committed_baseline(
    root: Path,
    path: Path,
    reference: str,
) -> dict[str, Any] | None:
    if reference == "0" * 40:
        reference = "HEAD^"
        parent = subprocess.run(
            ["git", "rev-parse", "--verify", f"{reference}^{{commit}}"],
            cwd=root,
            capture_output=True,
            check=False,
            text=True,
        )
        if parent.returncode != 0:
            return None
    try:
        relative = path.relative_to(root).as_posix()
    except ValueError:
        return None
    _run_git(root, "rev-parse", "--verify", f"{reference}^{{commit}}")
    completed = subprocess.run(
        ["git", "show", f"{reference}:{relative}"],
        cwd=root,
        capture_output=True,
        check=False,
        text=True,
    )
    if completed.returncode != 0:
        return None
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise TypecheckGateError(
            f"Cannot read typecheck baseline {reference}:{relative}: {error}"
        ) from error
    return _validate_baseline(payload, f"{reference}:{relative}")


def _discover_sources(root: Path, baseline_commit: str) -> tuple[str, ...]:
    changed = _run_git(
        root,
        "diff",
        "--name-only",
        "--diff-filter=ACMRT",
        baseline_commit,
        "--",
        "moltrack",
    ).splitlines()
    untracked = _run_git(
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


def _run_mypy(root: Path, sources: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "mypy", *MYPY_OPTIONS, *sources],
        cwd=root,
        capture_output=True,
        check=False,
        text=True,
    )


Diagnostic = tuple[str, str, str]


def _error_counts(output: str) -> Counter[Diagnostic]:
    counts: Counter[Diagnostic] = Counter()
    for line in output.splitlines():
        match = ERROR_LINE.match(line)
        if match is None:
            continue
        path = match.group("path").replace("\\", "/")
        counts[
            (
                path,
                match.group("code") or "unclassified",
                match.group("message").strip(),
            )
        ] += 1
    return counts


def _baseline_counts(payload: dict[str, Any]) -> Counter[Diagnostic]:
    counts: Counter[Diagnostic] = Counter()
    for path, entry in payload["errors"].items():
        if not isinstance(path, str) or not isinstance(entry, dict):
            raise TypecheckGateError("Every baseline error entry must be an object")
        if not isinstance(entry.get("owner"), str) or not entry["owner"].strip():
            raise TypecheckGateError(f"Baseline entry {path} requires an owner")
        if not isinstance(entry.get("justification"), str) or not entry[
            "justification"
        ].strip():
            raise TypecheckGateError(f"Baseline entry {path} requires a justification")
        errors = entry.get("errors")
        if not isinstance(errors, dict):
            raise TypecheckGateError(f"Baseline entry {path} requires an errors object")
        for code, messages in errors.items():
            if not isinstance(code, str) or not isinstance(messages, dict):
                raise TypecheckGateError(
                    f"Baseline diagnostics for {path} [{code}] must be an object"
                )
            for message, count in messages.items():
                if (
                    not isinstance(message, str)
                    or not isinstance(count, int)
                    or count <= 0
                ):
                    raise TypecheckGateError(
                        f"Baseline count for {path} [{code}] must be a positive integer"
                    )
                counts[(path.replace("\\", "/"), code, message)] = count
    return counts


def _format_count(key: Diagnostic, count: int) -> str:
    path, code, message = key
    return f"{path} [{code}] {message}: {count}"


def _evaluate(
    current: Counter[Diagnostic],
    allowed: Counter[Diagnostic],
) -> list[str]:
    failures: list[str] = []
    for key in sorted(current.keys() | allowed.keys()):
        actual = current[key]
        baseline = allowed[key]
        if actual > baseline:
            failures.append(
                "new type errors: "
                f"{_format_count(key, actual)} (baseline={baseline})"
            )
        elif actual < baseline:
            failures.append(
                "stale typecheck baseline; lower or remove: "
                f"{_format_count(key, baseline)} (current={actual})"
            )
    return failures


def _evaluate_baseline_ratchet(
    current: Counter[Diagnostic],
    committed: Counter[Diagnostic],
) -> list[str]:
    failures: list[str] = []
    for key in sorted(current):
        if current[key] > committed[key]:
            failures.append(
                "baseline cap increased: "
                f"{_format_count(key, committed[key])} -> {current[key]}"
            )
    return failures


def _evaluate_scope_ratchet(
    current: dict[str, Any],
    committed: dict[str, Any],
) -> list[str]:
    current_commit = current["scope"]["baseline_commit"]
    committed_commit = committed["scope"]["baseline_commit"]
    if current_commit == committed_commit:
        return []
    return [
        "scope baseline commit changed: "
        f"{committed_commit} -> {current_commit}"
    ]


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
        payload = _load_baseline(baseline_path)
        sources = _discover_sources(root, payload["scope"]["baseline_commit"])
        allowed = _baseline_counts(payload)
        ratchet_reference = os.environ.get(RATCHET_REFERENCE_ENV, "HEAD").strip()
        committed_payload = _load_committed_baseline(
            root,
            baseline_path,
            ratchet_reference or "HEAD",
        )
        baseline_failures = (
            _evaluate_scope_ratchet(payload, committed_payload)
            + _evaluate_baseline_ratchet(allowed, _baseline_counts(committed_payload))
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

    completed = _run_mypy(root, sources)
    current = _error_counts(completed.stdout)
    failures = _evaluate(current, allowed)
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
