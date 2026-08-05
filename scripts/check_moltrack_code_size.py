"""Enforce the MolTrack source-size limits and their legacy ratchet."""

from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASELINE = PROJECT_ROOT / "scripts" / "moltrack_code_size_baseline.json"
PRODUCTION_LINE_LIMIT = 800
PRODUCTION_DEFINITION_LIMIT = 30
PRODUCTION_CLASS_LIMIT = 10
FUNCTION_LINE_LIMIT = 80
TEST_LINE_LIMIT = 1000
TEST_COUNT_LIMIT = 40


@dataclass(frozen=True)
class BaselineCap:
    relative: str
    metric: str
    value: int
    function_name: str | None = None

    @property
    def key(self) -> tuple[str, str, str | None]:
        return self.relative, self.metric, self.function_name

    @property
    def location(self) -> str:
        if self.function_name is None:
            return self.relative
        return f"{self.relative}:{self.function_name}"


@dataclass(frozen=True)
class MetricCheck:
    location: str
    metric: str
    current: int
    limit: int
    cap: int | None = None
    preferred: str | None = None

    def violation(self) -> str | None:
        prefix = f"{self.location}: metric={self.metric} current={self.current}"
        if self.cap is not None and self.current <= self.limit:
            return (
                f"{prefix} baseline={self.cap}; lower or remove the baseline "
                "entry (universal limit reached)"
            )
        if self.cap is not None and self.current < self.cap:
            return f"{prefix} baseline={self.cap}; lower or remove the baseline"
        if self.cap is not None and self.current > self.cap:
            return f"{prefix} limit={self.limit} ratchet={self.cap}"
        if self.cap is None and self.current > self.limit:
            preferred = (
                "" if self.preferred is None else f" preferred={self.preferred}"
            )
            return f"{prefix} limit={self.limit}{preferred}"
        return None


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    return parser.parse_args()


def _python_paths(root: Path, relative_dir: str) -> list[Path]:
    if not (root / ".git").exists():
        return sorted((root / relative_dir).rglob("*.py"))
    completed = subprocess.run(
        [
            "git",
            "ls-files",
            "--cached",
            "--others",
            "--exclude-standard",
            "--",
            relative_dir,
        ],
        cwd=root,
        capture_output=True,
        check=True,
        encoding="utf-8",
        text=True,
    )
    return sorted(
        root / relative
        for relative in completed.stdout.splitlines()
        if relative.endswith(".py") and (root / relative).is_file()
    )


def _function_lengths_from_tree(tree: ast.AST) -> dict[str, int]:
    results: dict[str, int] = {}

    def collect(node: ast.AST, parents: tuple[str, ...] = ()) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                collect(child, (*parents, child.name))
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                start = min(
                    (decorator.lineno for decorator in child.decorator_list),
                    default=child.lineno,
                )
                base_name = ".".join((*parents, child.name))
                name = _unique_function_name(base_name, results)
                results[name] = child.end_lineno - start + 1
                collect(child, (*parents, child.name))
            else:
                collect(child, parents)

    collect(tree)
    return results


def _unique_function_name(base_name: str, results: dict[str, int]) -> str:
    if base_name not in results:
        return base_name
    occurrence = 2
    while f"{base_name}#{occurrence}" in results:
        occurrence += 1
    return f"{base_name}#{occurrence}"


def _function_lengths_from_source(source: str, filename: str) -> dict[str, int]:
    return _function_lengths_from_tree(ast.parse(source, filename=filename))


def _baseline_caps(baseline: dict) -> tuple[BaselineCap, ...]:
    caps = [
        BaselineCap(relative, metric, int(value))
        for relative, metrics in baseline.get("files", {}).items()
        for metric, value in metrics.items()
    ]
    caps.extend(
        BaselineCap(relative, "function_lines", int(value), function_name)
        for relative, functions in baseline.get("functions", {}).items()
        for function_name, value in functions.items()
    )
    return tuple(caps)


def _caps_by_key(baseline: dict) -> dict[tuple[str, str, str | None], int]:
    return {cap.key: cap.value for cap in _baseline_caps(baseline)}


def _git_json(root: Path, revision: str, relative: str) -> dict | None:
    completed = subprocess.run(
        ["git", "show", f"{revision}:{relative}"],
        cwd=root,
        capture_output=True,
        check=False,
        encoding="utf-8",
        text=True,
    )
    if completed.returncode != 0:
        return None
    return json.loads(completed.stdout)


def _comparison_baseline(root: Path, path: Path, current: dict) -> dict | None:
    if not (root / ".git").exists():
        return None
    try:
        relative = path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return None
    committed = _git_json(root, "HEAD", relative)
    if committed is None or committed != current:
        return committed
    history = subprocess.run(
        ["git", "log", "--format=%H", "--", relative],
        cwd=root,
        capture_output=True,
        check=True,
        encoding="utf-8",
        text=True,
    ).stdout.splitlines()
    if len(history) < 2:
        return None
    return _git_json(root, history[1], relative)


def _baseline_growth_violations(current: dict, previous: dict | None) -> list[str]:
    if previous is None:
        return []
    old_caps = _caps_by_key(previous)
    violations: list[str] = []
    for cap in _baseline_caps(current):
        old_cap = old_caps.get(cap.key)
        if old_cap is None:
            violations.append(
                f"{cap.location}: metric={cap.metric}; "
                "new baseline exception is forbidden"
            )
        elif cap.value > old_cap:
            violations.append(
                f"{cap.location}: metric={cap.metric}; baseline cap increased "
                f"from {old_cap} to {cap.value}"
            )
    return violations


def _source_at_commit(root: Path, commit: str, relative: str) -> str | None:
    completed = subprocess.run(
        ["git", "show", f"{commit}:{relative}"],
        cwd=root,
        capture_output=True,
        check=False,
        encoding="utf-8",
        text=True,
    )
    return completed.stdout if completed.returncode == 0 else None


def _metric_from_source(source: str, relative: str, metric: str) -> int:
    if metric == "physical_lines":
        return len(source.splitlines())
    tree = ast.parse(source, filename=relative)
    functions = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    if metric == "definitions":
        return len(functions)
    if metric == "classes":
        return sum(isinstance(node, ast.ClassDef) for node in ast.walk(tree))
    if metric == "tests":
        return sum(node.name.startswith("test") for node in functions)
    raise ValueError(f"Unsupported baseline metric: {metric}")


def _initial_baseline_violations(root: Path, baseline: dict) -> list[str]:
    commit = baseline.get("test_suite", {}).get("baseline_commit")
    if not commit or not (root / ".git").exists():
        return []
    sources: dict[str, str | None] = {}
    violations: list[str] = []
    for cap in _baseline_caps(baseline):
        if cap.relative not in sources:
            sources[cap.relative] = _source_at_commit(
                root,
                str(commit),
                cap.relative,
            )
        source = sources[cap.relative]
        if source is None:
            violations.append(
                f"{cap.location}: did not exist at baseline commit {commit}"
            )
            continue
        original = _original_cap_value(source, cap)
        if cap.value != original:
            violations.append(
                f"{cap.location}: metric={cap.metric}; baseline cap={cap.value} "
                f"does not match baseline commit value={original}"
            )
    return violations


def _original_cap_value(source: str, cap: BaselineCap) -> int:
    if cap.function_name is None:
        return _metric_from_source(source, cap.relative, cap.metric)
    lengths = _function_lengths_from_source(source, cap.relative)
    original = lengths.get(cap.function_name)
    if original is None:
        return -1
    return original


def _file_cap(baseline: dict, relative: str, metric: str) -> int | None:
    value = baseline.get("files", {}).get(relative, {}).get(metric)
    return None if value is None else int(value)


def _function_cap(baseline: dict, relative: str, name: str) -> int | None:
    value = baseline.get("functions", {}).get(relative, {}).get(name)
    return None if value is None else int(value)


def _production_checks(
    path: Path,
    root: Path,
    baseline: dict,
) -> tuple[list[MetricCheck], set[str]]:
    relative = path.relative_to(root).as_posix()
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    functions = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    values = {
        "physical_lines": len(source.splitlines()),
        "definitions": len(functions),
        "classes": sum(isinstance(node, ast.ClassDef) for node in ast.walk(tree)),
    }
    limits = {
        "physical_lines": (PRODUCTION_LINE_LIMIT, "250-500"),
        "definitions": (PRODUCTION_DEFINITION_LIMIT, None),
        "classes": (PRODUCTION_CLASS_LIMIT, None),
    }
    checks = [
        MetricCheck(
            relative,
            metric,
            current,
            limits[metric][0],
            _file_cap(baseline, relative, metric),
            limits[metric][1],
        )
        for metric, current in values.items()
    ]
    function_lengths = _function_lengths_from_tree(tree)
    checks.extend(
        MetricCheck(
            f"{relative}:{name}",
            "function_lines",
            current,
            FUNCTION_LINE_LIMIT,
            _function_cap(baseline, relative, name),
            "40",
        )
        for name, current in function_lengths.items()
    )
    return checks, set(function_lengths)


def _test_checks(path: Path, root: Path, baseline: dict) -> list[MetricCheck]:
    relative = path.relative_to(root).as_posix()
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    test_count = sum(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test")
        for node in ast.walk(tree)
    )
    return [
        MetricCheck(
            relative,
            "physical_lines",
            len(source.splitlines()),
            TEST_LINE_LIMIT,
            _file_cap(baseline, relative, "physical_lines"),
        ),
        MetricCheck(
            relative,
            "tests",
            test_count,
            TEST_COUNT_LIMIT,
            _file_cap(baseline, relative, "tests"),
        ),
    ]


def _stale_baseline_violations(
    baseline: dict,
    seen_files: set[str],
    seen_functions: dict[str, set[str]],
) -> list[str]:
    violations = [
        f"{relative}: stale file baseline; remove it"
        for relative in baseline.get("files", {})
        if relative not in seen_files
    ]
    for relative, functions in baseline.get("functions", {}).items():
        current_names = seen_functions.get(relative, set())
        violations.extend(
            f"{relative}:{name}: stale function baseline; remove it"
            for name in functions
            if name not in current_names
        )
    return violations


def _current_tree_violations(root: Path, baseline: dict) -> list[str]:
    checks: list[MetricCheck] = []
    seen_files: set[str] = set()
    seen_functions: dict[str, set[str]] = {}
    for path in _python_paths(root, "moltrack"):
        relative = path.relative_to(root).as_posix()
        seen_files.add(relative)
        file_checks, function_names = _production_checks(path, root, baseline)
        checks.extend(file_checks)
        seen_functions[relative] = function_names
    for path in _python_paths(root, "tests/moltrack"):
        seen_files.add(path.relative_to(root).as_posix())
        checks.extend(_test_checks(path, root, baseline))
    violations = [value for check in checks if (value := check.violation())]
    violations.extend(
        _stale_baseline_violations(baseline, seen_files, seen_functions)
    )
    return violations


def _load_baseline(path: Path) -> dict:
    baseline = json.loads(path.read_text(encoding="utf-8"))
    if baseline.get("schema_version") != 1:
        raise ValueError(
            f"Unsupported baseline schema_version: {baseline.get('schema_version')}"
        )
    return baseline


def _all_violations(root: Path, baseline_path: Path, baseline: dict) -> list[str]:
    comparison = _comparison_baseline(root, baseline_path, baseline)
    violations = _baseline_growth_violations(baseline, comparison)
    if comparison is None:
        violations.extend(_initial_baseline_violations(root, baseline))
    violations.extend(_current_tree_violations(root, baseline))
    return violations


def main() -> int:
    args = _parse_args()
    try:
        baseline = _load_baseline(args.baseline)
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 2
    violations = _all_violations(args.root, args.baseline, baseline)
    if not violations:
        print("MolTrack code-size guard passed.")
        return 0
    print("MolTrack code-size guard failed:")
    for violation in violations:
        print(f"- {violation}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
