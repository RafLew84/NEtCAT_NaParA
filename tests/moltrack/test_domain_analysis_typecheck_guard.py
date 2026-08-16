from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CHECKER = PROJECT_ROOT / "scripts" / "check_domain_analysis_types.py"
QUALITY_GATES = PROJECT_ROOT / "docs" / "moltrack" / "QUALITY_GATES.md"
CI_WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "moltrack-quality.yml"
PUBLIC_COMMAND = "conda run -n netcat python scripts\\check_domain_analysis_types.py"
ASSIGNMENT_DIAGNOSTIC = (
    'Incompatible types in assignment (expression has type "str", '
    'variable has type "int")'
)


def _run_git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        check=True,
        text=True,
    ).stdout.strip()


def _commit_all(root: Path, message: str) -> str:
    _run_git(root, "add", ".")
    _run_git(
        root,
        "-c",
        "user.name=Typecheck Test",
        "-c",
        "user.email=typecheck@example.invalid",
        "commit",
        "-q",
        "-m",
        message,
    )
    return _run_git(root, "rev-parse", "HEAD")


def _commit_baseline(root: Path) -> str:
    _run_git(root, "init", "-q")
    return _commit_all(root, "baseline")


def _initialize_repository(
    root: Path,
    relative_path: str = "moltrack/existing.py",
    source: str = "value: int = 1\n",
) -> str:
    initial = root / relative_path
    initial.parent.mkdir(parents=True)
    initial.write_text(source, encoding="utf-8")
    return _commit_baseline(root)


def _legacy_errors(count: int = 1) -> dict[str, object]:
    return {
        "moltrack/legacy.py": {
            "owner": "Legacy owner",
            "justification": "Predates the typecheck gate.",
            "errors": {"assignment": {ASSIGNMENT_DIAGNOSTIC: count}},
        }
    }


def _write_baseline(
    root: Path,
    base_commit: str,
    errors: dict[str, object] | None = None,
) -> Path:
    baseline = root / "typecheck-baseline.json"
    baseline.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "owner": "MolTrack Domain Analysis",
                "scope": {"baseline_commit": base_commit},
                "errors": errors or {},
            }
        ),
        encoding="utf-8",
    )
    return baseline


def _run_checker(
    root: Path,
    baseline: Path,
    *,
    ratchet_reference: str | None = None,
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    if ratchet_reference is not None:
        environment["DOMAIN_ANALYSIS_RATCHET_REF"] = ratchet_reference
    return subprocess.run(
        [
            sys.executable,
            str(CHECKER),
            "--root",
            str(root),
            "--baseline",
            str(baseline),
        ],
        capture_output=True,
        check=False,
        env=environment,
        text=True,
    )


class DomainAnalysisTypecheckGuardTests(unittest.TestCase):
    def test_documentation_and_ci_use_the_same_public_command(self) -> None:
        documentation = QUALITY_GATES.read_text(encoding="utf-8")
        workflow = CI_WORKFLOW.read_text(encoding="utf-8")

        self.assertIn(PUBLIC_COMMAND, documentation)
        self.assertIn(PUBLIC_COMMAND, workflow)
        self.assertIn("fetch-depth: 0", workflow)
        self.assertIn("DOMAIN_ANALYSIS_RATCHET_REF", workflow)
        self.assertNotIn("python -m mypy", documentation)

    def test_new_production_module_is_discovered_and_typechecked(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            base_commit = _initialize_repository(root)
            baseline = _write_baseline(root, base_commit)

            added = root / "moltrack" / "analysis" / "domain_analysis" / "added.py"
            added.parent.mkdir(parents=True)
            added.write_text('value: int = "not an int"\n', encoding="utf-8")
            completed = _run_checker(root, baseline)

        self.assertEqual(completed.returncode, 1)
        self.assertIn("moltrack/analysis/domain_analysis/added.py", completed.stdout)
        self.assertIn("new type errors", completed.stdout)

    def test_unchanged_domain_analysis_core_module_is_typechecked(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            base_commit = _initialize_repository(
                root,
                "moltrack/analysis/domain_analysis/core.py",
                'value: int = "not an int"\n',
            )
            baseline = _write_baseline(root, base_commit)

            completed = _run_checker(root, baseline)

        self.assertEqual(completed.returncode, 1)
        self.assertIn("moltrack/analysis/domain_analysis/core.py", completed.stdout)
        self.assertIn("new type errors", completed.stdout)

    def test_unchanged_moltrack_ui_module_is_typechecked(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            base_commit = _initialize_repository(
                root,
                "moltrack/ui/panel.py",
                'value: int = "not an int"\n',
            )
            baseline = _write_baseline(root, base_commit)

            completed = _run_checker(root, baseline)

        self.assertEqual(completed.returncode, 1)
        self.assertIn("moltrack/ui/panel.py", completed.stdout)
        self.assertIn("new type errors", completed.stdout)

    def test_committed_type_error_cap_cannot_be_raised_with_new_errors(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            base_commit = _initialize_repository(root)
            legacy = root / "moltrack" / "legacy.py"
            legacy.write_text('first: int = "wrong"\n', encoding="utf-8")
            baseline = _write_baseline(
                root,
                base_commit,
                _legacy_errors(),
            )
            _commit_all(root, "record accepted debt")

            legacy.write_text(
                'first: int = "wrong"\nsecond: int = "also wrong"\n',
                encoding="utf-8",
            )
            _write_baseline(
                root,
                base_commit,
                _legacy_errors(2),
            )
            completed = _run_checker(root, baseline)

        self.assertEqual(completed.returncode, 1)
        self.assertIn("baseline cap increased", completed.stdout)

    def test_ci_compares_committed_cap_with_the_base_revision(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            base_commit = _initialize_repository(root)
            legacy = root / "moltrack" / "legacy.py"
            legacy.write_text('first: int = "wrong"\n', encoding="utf-8")
            baseline = _write_baseline(root, base_commit, _legacy_errors())
            accepted_at = _commit_all(root, "record accepted debt")

            legacy.write_text(
                'first: int = "wrong"\nsecond: int = "also wrong"\n',
                encoding="utf-8",
            )
            _write_baseline(root, base_commit, _legacy_errors(2))
            _commit_all(root, "attempt to raise accepted debt")
            completed = _run_checker(
                root,
                baseline,
                ratchet_reference=accepted_at,
            )

        self.assertEqual(completed.returncode, 1)
        self.assertIn("baseline cap increased", completed.stdout)

    def test_first_branch_push_compares_cap_with_parent_commit(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            base_commit = _initialize_repository(root)
            legacy = root / "moltrack" / "legacy.py"
            legacy.write_text('first: int = "wrong"\n', encoding="utf-8")
            baseline = _write_baseline(root, base_commit, _legacy_errors())
            _commit_all(root, "record accepted debt")

            legacy.write_text(
                'first: int = "wrong"\nsecond: int = "also wrong"\n',
                encoding="utf-8",
            )
            _write_baseline(root, base_commit, _legacy_errors(2))
            _commit_all(root, "first commit on a new branch")
            completed = _run_checker(
                root,
                baseline,
                ratchet_reference="0" * 40,
            )

        self.assertEqual(completed.returncode, 1)
        self.assertIn("baseline cap increased", completed.stdout)

    def test_different_diagnostic_cannot_replace_one_with_the_same_code(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            base_commit = _initialize_repository(root)
            legacy = root / "moltrack" / "legacy.py"
            legacy.write_text('first: int = "wrong"\n', encoding="utf-8")
            baseline = _write_baseline(
                root,
                base_commit,
                _legacy_errors(),
            )
            _commit_all(root, "record accepted debt")

            legacy.write_text("replacement: str = 2\n", encoding="utf-8")
            completed = _run_checker(root, baseline)

        self.assertEqual(completed.returncode, 1)
        self.assertIn("new type errors", completed.stdout)

    def test_committed_ownership_boundary_cannot_move_forward(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            base_commit = _initialize_repository(root)
            legacy = root / "moltrack" / "legacy.py"
            legacy.write_text('value: int = "wrong"\n', encoding="utf-8")
            baseline = _write_baseline(
                root,
                base_commit,
                _legacy_errors(),
            )
            adopted_at = _commit_all(root, "record accepted debt")

            _write_baseline(root, adopted_at)
            completed = _run_checker(root, baseline)

        self.assertEqual(completed.returncode, 1)
        self.assertIn("scope baseline commit changed", completed.stdout)


if __name__ == "__main__":
    unittest.main()
