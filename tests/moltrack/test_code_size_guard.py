import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CHECKER = PROJECT_ROOT / "scripts" / "check_moltrack_code_size.py"


def _write_baseline(root: Path, baseline: dict) -> Path:
    baseline_path = root / "baseline.json"
    baseline_path.write_text(json.dumps(baseline), encoding="utf-8")
    return baseline_path


def _run_checker(root: Path, baseline: dict) -> subprocess.CompletedProcess[str]:
    baseline_path = _write_baseline(root, baseline)
    return subprocess.run(
        [
            sys.executable,
            str(CHECKER),
            "--root",
            str(root),
            "--baseline",
            str(baseline_path),
        ],
        capture_output=True,
        check=False,
        text=True,
    )


def _init_repo(root: Path) -> None:
    subprocess.run(
        ["git", "init", "-q"],
        cwd=root,
        capture_output=True,
        check=True,
        text=True,
    )


def _commit_all(root: Path) -> None:
    subprocess.run(
        ["git", "add", "."],
        cwd=root,
        capture_output=True,
        check=True,
        text=True,
    )
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Code Size Test",
            "-c",
            "user.email=code-size@example.invalid",
            "commit",
            "-q",
            "-m",
            "baseline",
        ],
        cwd=root,
        capture_output=True,
        check=True,
        text=True,
    )


class MolTrackCodeSizeGuardTests(unittest.TestCase):
    def test_rejects_new_oversized_production_file_with_actionable_message(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "moltrack" / "oversized.py"
            source.parent.mkdir(parents=True)
            source.write_text("value = 1\n" * 801, encoding="utf-8")

            completed = _run_checker(
                root,
                {"schema_version": 1, "files": {}, "functions": {}},
            )

        self.assertEqual(completed.returncode, 1)
        self.assertIn("moltrack/oversized.py", completed.stdout)
        self.assertIn("physical_lines", completed.stdout)
        self.assertIn("current=801", completed.stdout)
        self.assertIn("limit=800", completed.stdout)
        self.assertIn("preferred=250-500", completed.stdout)

    def test_rejects_production_file_with_too_many_definitions(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "moltrack" / "too_many_definitions.py"
            source.parent.mkdir(parents=True)
            source.write_text(
                "\n".join(f"def function_{index}(): pass" for index in range(31)),
                encoding="utf-8",
            )

            completed = _run_checker(
                root,
                {"schema_version": 1, "files": {}, "functions": {}},
            )

        self.assertEqual(completed.returncode, 1)
        self.assertIn("metric=definitions", completed.stdout)
        self.assertIn("current=31", completed.stdout)
        self.assertIn("limit=30", completed.stdout)

    def test_rejects_production_file_with_too_many_classes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "moltrack" / "too_many_classes.py"
            source.parent.mkdir(parents=True)
            source.write_text(
                "\n".join(f"class Example{index}: pass" for index in range(11)),
                encoding="utf-8",
            )

            completed = _run_checker(
                root,
                {"schema_version": 1, "files": {}, "functions": {}},
            )

        self.assertEqual(completed.returncode, 1)
        self.assertIn("metric=classes", completed.stdout)
        self.assertIn("current=11", completed.stdout)
        self.assertIn("limit=10", completed.stdout)

    def test_rejects_overlong_function_with_preferred_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "moltrack" / "overlong_function.py"
            source.parent.mkdir(parents=True)
            source.write_text(
                "def overlong():\n" + "    value = 1\n" * 80,
                encoding="utf-8",
            )

            completed = _run_checker(
                root,
                {"schema_version": 1, "files": {}, "functions": {}},
            )

        self.assertEqual(completed.returncode, 1)
        self.assertIn("overlong_function.py:overlong", completed.stdout)
        self.assertIn("metric=function_lines", completed.stdout)
        self.assertIn("current=81", completed.stdout)
        self.assertIn("limit=80", completed.stdout)
        self.assertIn("preferred=40", completed.stdout)

    def test_rejects_oversized_test_file_at_its_separate_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "tests" / "moltrack" / "test_oversized.py"
            source.parent.mkdir(parents=True)
            source.write_text("value = 1\n" * 1001, encoding="utf-8")

            completed = _run_checker(
                root,
                {"schema_version": 1, "files": {}, "functions": {}},
            )

        self.assertEqual(completed.returncode, 1)
        self.assertIn("tests/moltrack/test_oversized.py", completed.stdout)
        self.assertIn("metric=physical_lines", completed.stdout)
        self.assertIn("current=1001", completed.stdout)
        self.assertIn("limit=1000", completed.stdout)

    def test_rejects_test_file_with_more_than_forty_tests(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "tests" / "moltrack" / "test_too_many.py"
            source.parent.mkdir(parents=True)
            source.write_text(
                "\n".join(f"def test_case_{index}(): pass" for index in range(41)),
                encoding="utf-8",
            )

            completed = _run_checker(
                root,
                {"schema_version": 1, "files": {}, "functions": {}},
            )

        self.assertEqual(completed.returncode, 1)
        self.assertIn("metric=tests", completed.stdout)
        self.assertIn("current=41", completed.stdout)
        self.assertIn("limit=40", completed.stdout)

    def test_legacy_file_cap_passes_at_baseline_and_rejects_growth(self) -> None:
        baseline = {
            "schema_version": 1,
            "files": {"moltrack/legacy.py": {"physical_lines": 801}},
            "functions": {},
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "moltrack" / "legacy.py"
            source.parent.mkdir(parents=True)
            source.write_text("value = 1\n" * 801, encoding="utf-8")

            unchanged = _run_checker(root, baseline)
            source.write_text("value = 1\n" * 802, encoding="utf-8")
            grown = _run_checker(root, baseline)

        self.assertEqual(unchanged.returncode, 0)
        self.assertEqual(grown.returncode, 1)
        self.assertIn("metric=physical_lines", grown.stdout)
        self.assertIn("current=802", grown.stdout)
        self.assertIn("ratchet=801", grown.stdout)

    def test_reduced_legacy_file_requires_lowering_the_baseline(self) -> None:
        baseline = {
            "schema_version": 1,
            "files": {"moltrack/legacy.py": {"physical_lines": 801}},
            "functions": {},
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "moltrack" / "legacy.py"
            source.parent.mkdir(parents=True)
            source.write_text("value = 1\n" * 800, encoding="utf-8")

            completed = _run_checker(root, baseline)

        self.assertEqual(completed.returncode, 1)
        self.assertIn("metric=physical_lines", completed.stdout)
        self.assertIn("current=800", completed.stdout)
        self.assertIn("baseline=801", completed.stdout)
        self.assertIn("lower or remove", completed.stdout)

    def test_rejects_baseline_entry_after_file_reaches_universal_limit(self) -> None:
        baseline = {
            "schema_version": 1,
            "files": {"moltrack/legacy.py": {"physical_lines": 800}},
            "functions": {},
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "moltrack" / "legacy.py"
            source.parent.mkdir(parents=True)
            source.write_text("value = 1\n" * 800, encoding="utf-8")

            completed = _run_checker(root, baseline)

        self.assertEqual(completed.returncode, 1)
        self.assertIn("metric=physical_lines", completed.stdout)
        self.assertIn("remove the baseline entry", completed.stdout)

    def test_legacy_function_cap_passes_at_baseline_and_rejects_growth(self) -> None:
        baseline = {
            "schema_version": 1,
            "files": {},
            "functions": {"moltrack/legacy.py": {"Legacy.run": 81}},
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "moltrack" / "legacy.py"
            source.parent.mkdir(parents=True)
            source.write_text(
                "class Legacy:\n    def run(self):\n" + "        value = 1\n" * 80,
                encoding="utf-8",
            )

            unchanged = _run_checker(root, baseline)
            source.write_text(
                "class Legacy:\n    def run(self):\n" + "        value = 1\n" * 81,
                encoding="utf-8",
            )
            grown = _run_checker(root, baseline)

        self.assertEqual(unchanged.returncode, 0)
        self.assertEqual(grown.returncode, 1)
        self.assertIn("legacy.py:Legacy.run", grown.stdout)
        self.assertIn("current=82", grown.stdout)
        self.assertIn("ratchet=81", grown.stdout)

    def test_reduced_legacy_function_requires_lowering_the_baseline(self) -> None:
        baseline = {
            "schema_version": 1,
            "files": {},
            "functions": {"moltrack/legacy.py": {"Legacy.run": 81}},
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "moltrack" / "legacy.py"
            source.parent.mkdir(parents=True)
            source.write_text(
                "class Legacy:\n    def run(self):\n" + "        value = 1\n" * 79,
                encoding="utf-8",
            )

            completed = _run_checker(root, baseline)

        self.assertEqual(completed.returncode, 1)
        self.assertIn("legacy.py:Legacy.run", completed.stdout)
        self.assertIn("current=80", completed.stdout)
        self.assertIn("baseline=81", completed.stdout)
        self.assertIn("lower or remove", completed.stdout)

    def test_legacy_definition_cap_uses_the_file_metric_ratchet(self) -> None:
        baseline = {
            "schema_version": 1,
            "files": {"moltrack/legacy.py": {"definitions": 31}},
            "functions": {},
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "moltrack" / "legacy.py"
            source.parent.mkdir(parents=True)
            source.write_text(
                "\n".join(f"def function_{index}(): pass" for index in range(31)),
                encoding="utf-8",
            )

            unchanged = _run_checker(root, baseline)
            source.write_text(
                "\n".join(f"def function_{index}(): pass" for index in range(32)),
                encoding="utf-8",
            )
            grown = _run_checker(root, baseline)

        self.assertEqual(unchanged.returncode, 0)
        self.assertEqual(grown.returncode, 1)
        self.assertIn("metric=definitions", grown.stdout)
        self.assertIn("current=32", grown.stdout)
        self.assertIn("ratchet=31", grown.stdout)

    def test_legacy_class_cap_uses_the_file_metric_ratchet(self) -> None:
        baseline = {
            "schema_version": 1,
            "files": {"moltrack/legacy.py": {"classes": 11}},
            "functions": {},
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "moltrack" / "legacy.py"
            source.parent.mkdir(parents=True)
            source.write_text(
                "\n".join(f"class Example{index}: pass" for index in range(11)),
                encoding="utf-8",
            )

            unchanged = _run_checker(root, baseline)
            source.write_text(
                "\n".join(f"class Example{index}: pass" for index in range(12)),
                encoding="utf-8",
            )
            grown = _run_checker(root, baseline)

        self.assertEqual(unchanged.returncode, 0)
        self.assertEqual(grown.returncode, 1)
        self.assertIn("metric=classes", grown.stdout)
        self.assertIn("current=12", grown.stdout)
        self.assertIn("ratchet=11", grown.stdout)

    def test_legacy_test_count_cap_uses_the_file_metric_ratchet(self) -> None:
        relative = "tests/moltrack/test_legacy.py"
        baseline = {
            "schema_version": 1,
            "files": {relative: {"tests": 41}},
            "functions": {},
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / relative
            source.parent.mkdir(parents=True)
            source.write_text(
                "\n".join(f"def test_case_{index}(): pass" for index in range(41)),
                encoding="utf-8",
            )

            unchanged = _run_checker(root, baseline)
            source.write_text(
                "\n".join(f"def test_case_{index}(): pass" for index in range(42)),
                encoding="utf-8",
            )
            grown = _run_checker(root, baseline)

        self.assertEqual(unchanged.returncode, 0)
        self.assertEqual(grown.returncode, 1)
        self.assertIn("metric=tests", grown.stdout)
        self.assertIn("current=42", grown.stdout)
        self.assertIn("ratchet=41", grown.stdout)

    def test_legacy_test_line_cap_uses_the_file_metric_ratchet(self) -> None:
        relative = "tests/moltrack/test_legacy.py"
        baseline = {
            "schema_version": 1,
            "files": {relative: {"physical_lines": 1001}},
            "functions": {},
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / relative
            source.parent.mkdir(parents=True)
            source.write_text("value = 1\n" * 1001, encoding="utf-8")

            unchanged = _run_checker(root, baseline)
            source.write_text("value = 1\n" * 1002, encoding="utf-8")
            grown = _run_checker(root, baseline)

        self.assertEqual(unchanged.returncode, 0)
        self.assertEqual(grown.returncode, 1)
        self.assertIn("metric=physical_lines", grown.stdout)
        self.assertIn("current=1002", grown.stdout)
        self.assertIn("ratchet=1001", grown.stdout)

    def test_rejects_stale_file_and_function_baseline_entries(self) -> None:
        baseline = {
            "schema_version": 1,
            "files": {"moltrack/missing.py": {"physical_lines": 900}},
            "functions": {"moltrack/present.py": {"removed": 90}},
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "moltrack" / "present.py"
            source.parent.mkdir(parents=True)
            source.write_text("def short(): pass\n", encoding="utf-8")

            completed = _run_checker(root, baseline)

        self.assertEqual(completed.returncode, 1)
        self.assertIn("moltrack/missing.py", completed.stdout)
        self.assertIn("stale file baseline", completed.stdout)
        self.assertIn("moltrack/present.py:removed", completed.stdout)
        self.assertIn("stale function baseline", completed.stdout)

    def test_ignores_python_files_excluded_from_version_control(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _init_repo(root)
            (root / ".gitignore").write_text(
                "moltrack/ignored.py\n",
                encoding="utf-8",
            )
            source = root / "moltrack" / "ignored.py"
            source.parent.mkdir(parents=True)
            source.write_text("value = 1\n" * 801, encoding="utf-8")

            completed = _run_checker(
                root,
                {"schema_version": 1, "files": {}, "functions": {}},
            )

        self.assertEqual(completed.returncode, 0)

    def test_rejects_unknown_baseline_schema_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            completed = _run_checker(
                Path(tmpdir),
                {"schema_version": 2, "files": {}, "functions": {}},
            )

        self.assertEqual(completed.returncode, 2)
        self.assertIn("Unsupported baseline schema_version: 2", completed.stderr)

    def test_checks_every_redefinition_of_the_same_function_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "moltrack" / "redefined.py"
            source.parent.mkdir(parents=True)
            source.write_text(
                "def duplicate():\n"
                + "    value = 1\n" * 80
                + "\ndef duplicate(): pass\n",
                encoding="utf-8",
            )

            completed = _run_checker(
                root,
                {"schema_version": 1, "files": {}, "functions": {}},
            )

        self.assertEqual(completed.returncode, 1)
        self.assertIn("redefined.py:duplicate", completed.stdout)
        self.assertIn("current=81", completed.stdout)

    def test_rejects_raising_a_committed_ratchet_cap(self) -> None:
        relative = "moltrack/legacy.py"
        baseline = {
            "schema_version": 1,
            "files": {relative: {"physical_lines": 801}},
            "functions": {},
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _init_repo(root)
            source = root / relative
            source.parent.mkdir(parents=True)
            source.write_text("value = 1\n" * 801, encoding="utf-8")
            _write_baseline(root, baseline)
            _commit_all(root)

            source.write_text("value = 1\n" * 802, encoding="utf-8")
            raised = {
                **baseline,
                "files": {relative: {"physical_lines": 802}},
            }
            completed = _run_checker(root, raised)

        self.assertEqual(completed.returncode, 1)
        self.assertIn("metric=physical_lines", completed.stdout)
        self.assertIn("baseline cap increased from 801 to 802", completed.stdout)

    def test_initial_baseline_cannot_exempt_a_new_oversized_file(self) -> None:
        relative = "moltrack/new_oversized.py"
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _init_repo(root)
            (root / "README.md").write_text("baseline\n", encoding="utf-8")
            _commit_all(root)
            base_commit = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=root,
                capture_output=True,
                check=True,
                text=True,
            ).stdout.strip()
            source = root / relative
            source.parent.mkdir(parents=True)
            source.write_text("value = 1\n" * 801, encoding="utf-8")

            completed = _run_checker(
                root,
                {
                    "schema_version": 1,
                    "test_suite": {"baseline_commit": base_commit},
                    "files": {relative: {"physical_lines": 801}},
                    "functions": {},
                },
            )

        self.assertEqual(completed.returncode, 1)
        self.assertIn(relative, completed.stdout)
        self.assertIn("did not exist at baseline commit", completed.stdout)

    def test_rejects_a_ratchet_cap_raised_in_the_current_commit(self) -> None:
        relative = "moltrack/legacy.py"
        baseline = {
            "schema_version": 1,
            "files": {relative: {"physical_lines": 801}},
            "functions": {},
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _init_repo(root)
            source = root / relative
            source.parent.mkdir(parents=True)
            source.write_text("value = 1\n" * 801, encoding="utf-8")
            _write_baseline(root, baseline)
            _commit_all(root)
            source.write_text("value = 1\n" * 802, encoding="utf-8")
            _write_baseline(
                root,
                {**baseline, "files": {relative: {"physical_lines": 802}}},
            )
            _commit_all(root)

            completed = _run_checker(
                root,
                {**baseline, "files": {relative: {"physical_lines": 802}}},
            )

        self.assertEqual(completed.returncode, 1)
        self.assertIn("baseline cap increased from 801 to 802", completed.stdout)

    def test_reads_utf8_python_source_from_the_baseline_commit(self) -> None:
        relative = "moltrack/legacy_unicode.py"
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _init_repo(root)
            source = root / relative
            source.parent.mkdir(parents=True)
            source.write_text("zażółć = 1\n" * 801, encoding="utf-8")
            _commit_all(root)
            base_commit = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=root,
                capture_output=True,
                check=True,
                text=True,
            ).stdout.strip()

            completed = _run_checker(
                root,
                {
                    "schema_version": 1,
                    "test_suite": {"baseline_commit": base_commit},
                    "files": {relative: {"physical_lines": 801}},
                    "functions": {},
                },
            )

        self.assertEqual(completed.returncode, 0)


if __name__ == "__main__":
    unittest.main()
