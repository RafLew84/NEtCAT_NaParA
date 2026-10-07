"""The public command catches new diagnostics and prevents increasing their allowance."""
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from scripts.check_nanotrack_types import check


ROOT = Path(__file__).resolve().parents[2]
CHECKER = ROOT / "scripts/check_nanotrack_types.py"
MESSAGE = 'Incompatible types in assignment (expression has type "str", variable has type "int")'


class NanoTrackTypecheckTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        (self.root / "nanotrack").mkdir()
        (self.root / "nanotrack/__init__.py").write_text("", encoding="utf-8")
        self.source = self.root / "nanotrack/legacy.py"
        self.source.write_text('value: int = "old"\n', encoding="utf-8")
        self.git("init", "-q")
        self.commit()
        self.baseline = self.root / "baseline.json"
        self.payload = {"schema_version": 1, "scope": {"baseline_commit": self.git("rev-parse", "HEAD")},
                        "errors": {"nanotrack/legacy.py": {"owner": "test", "justification": "known fixture",
                                   "errors": {"assignment": {MESSAGE: 1}}}}}
        self.save_baseline()
        self.commit()

    def git(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.root, text=True).strip()

    def commit(self):
        self.git("add", ".")
        self.git("-c", "user.name=Gate Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "fixture")

    def save_baseline(self):
        self.baseline.write_text(json.dumps(self.payload), encoding="utf-8")

    def run_gate(self):
        report = self.root / "report.json"
        env = dict(os.environ)
        env.pop("NANOTRACK_RATCHET_REF", None)
        result = subprocess.run([sys.executable, str(CHECKER), "--root", str(self.root),
                                 "--baseline", str(self.baseline), "--report", str(report)],
                                capture_output=True, text=True, env=env, timeout=60)
        return result.returncode, json.loads(report.read_text(encoding="utf-8"))

    def test_legacy_passes_but_new_untracked_production_module_fails(self):
        code, report = self.run_gate()
        self.assertEqual(code, 0, report)
        (self.root / "nanotrack/new.py").write_text('value: int = "new"\n', encoding="utf-8")
        code, report = self.run_gate()
        self.assertEqual(code, 1)
        self.assertIn("nanotrack/new.py", "\n".join(report["failures"]))

    def test_another_diagnostic_cannot_replace_one_with_the_same_total(self):
        self.source.write_text("value: int = []\n", encoding="utf-8")
        code, report = self.run_gate()
        self.assertEqual(code, 1)
        self.assertEqual(report["current_errors"], 1)
        self.assertIn("new type errors", "\n".join(report["failures"]))

    def test_baseline_cannot_be_increased_to_hide_new_errors(self):
        self.payload["errors"]["nanotrack/legacy.py"]["errors"]["assignment"][MESSAGE] = 2
        self.save_baseline()
        code, report = self.run_gate()
        self.assertEqual(code, 1)
        self.assertIn("baseline cap increased", "\n".join(report["failures"]))

    def test_fixed_error_requires_removing_its_obsolete_allowance(self):
        self.source.write_text("value: int = 3\n", encoding="utf-8")
        code, report = self.run_gate()
        self.assertEqual(code, 1)
        self.assertIn("stale typecheck baseline", "\n".join(report["failures"]))
        self.payload["errors"] = {}
        self.save_baseline()
        code, report = self.run_gate()
        self.assertEqual(code, 0, report)

    def test_mypy_cannot_complete_is_a_failure(self):
        self.source.write_text("def broken(:\n", encoding="utf-8")
        code, report = self.run_gate()
        self.assertEqual(code, 1)
        self.assertEqual(report["status"], "configuration_error")

    def test_timeout_stops_the_actual_mypy_process_and_reports_failure(self):
        (self.root / "mypy.py").write_text("import time\ntime.sleep(30)\n", encoding="utf-8")
        processes = []
        launch = subprocess.Popen

        def record_process(*args, **kwargs):
            process = launch(*args, **kwargs)
            processes.append(process)
            return process

        with patch("scripts.mypy_baseline.subprocess.Popen", side_effect=record_process):
            report = check(self.root, self.baseline, "HEAD", mypy_timeout=0.5)
        self.assertEqual(report["status"], "timeout", report)
        mypy_process = next(process for process in processes if process.args[1:3] == ["-m", "mypy"])
        self.assertIsNotNone(mypy_process.poll(), "Timed-out mypy must not remain alive")
        self.assertIn("process was stopped", "\n".join(report["failures"]))
