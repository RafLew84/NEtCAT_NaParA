"""Shared mypy diagnostic baselines for the NanoTrack and MolTrack gates."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Sequence


MYPY_OPTIONS = (
    "--ignore-missing-imports",
    "--follow-imports=silent",
    "--show-error-codes",
    "--no-error-summary",
)


ERROR_LINE = re.compile(
    r"^(?P<path>.+?):(?P<line>\d+)(?::\d+)?: error: "
    r"(?P<message>.*?)(?:  \[(?P<code>[^]]+)\])?$"
)


class TypecheckGateError(ValueError):
    """Raised when the typecheck gate configuration is invalid."""


def run_git(root: Path, *args: str) -> str:
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


def validate_baseline(payload: Any, source: str) -> dict[str, Any]:
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


def load_baseline(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise TypecheckGateError(f"Cannot read typecheck baseline {path}: {error}") from error
    return validate_baseline(payload, str(path))


def load_committed_baseline(
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
    run_git(root, "rev-parse", "--verify", f"{reference}^{{commit}}")
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
    return validate_baseline(payload, f"{reference}:{relative}")


def run_mypy(
    root: Path, sources: Sequence[str], *, timeout: float | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "mypy", *MYPY_OPTIONS, *sources],
        cwd=root,
        capture_output=True,
        check=False,
        text=True,
        timeout=timeout,
    )


Diagnostic = tuple[str, str, str]


def error_counts(output: str) -> Counter[Diagnostic]:
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


def baseline_counts(payload: dict[str, Any]) -> Counter[Diagnostic]:
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


def format_count(key: Diagnostic, count: int) -> str:
    path, code, message = key
    return f"{path} [{code}] {message}: {count}"


def evaluate(
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
                f"{format_count(key, actual)} (baseline={baseline})"
            )
        elif actual < baseline:
            failures.append(
                "stale typecheck baseline; lower or remove: "
                f"{format_count(key, baseline)} (current={actual})"
            )
    return failures


def evaluate_baseline_ratchet(
    current: Counter[Diagnostic],
    committed: Counter[Diagnostic],
) -> list[str]:
    failures: list[str] = []
    for key in sorted(current):
        if current[key] > committed[key]:
            failures.append(
                "baseline cap increased: "
                f"{format_count(key, committed[key])} -> {current[key]}"
            )
    return failures


def evaluate_scope_ratchet(
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
