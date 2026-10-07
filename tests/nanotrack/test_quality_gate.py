"""Exercise failures that must make the CI gate red, even if pytest only skips."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

from scripts import check_nanotrack as gate


class NanoTrackQualityGateTests(unittest.TestCase):
    def test_missing_gui_or_ecc_dependency_is_a_preflight_error(self):
        for missing in ("PyQt6.QtCore", "pyqtgraph", "cv2"):
            with self.subTest(module=missing):
                def import_module(name):
                    if name == missing:
                        raise ImportError("test missing dependency")
                    return SimpleNamespace()

                with patch.object(gate.importlib, "import_module", side_effect=import_module):
                    result = gate.probe_environment()
                self.assertEqual(len(result["errors"]), 1)
                self.assertIn(missing, result["errors"][0])

    def test_opencv_without_ecc_is_a_preflight_error(self):
        with patch.object(gate.importlib, "import_module", return_value=SimpleNamespace()):
            result = gate.probe_environment()
        self.assertEqual(result["errors"], ["cv2: findTransformECC is unavailable"])

    def test_preflight_failure_stops_tests_and_writes_failure_report(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(gate.subprocess, "run", return_value=SimpleNamespace(returncode=1)), \
                    patch.object(gate, "run_tests") as run_tests:
                code = gate.main(["--report-dir", directory])
            summary = json.loads((Path(directory) / "summary.json").read_text(encoding="utf-8"))
        self.assertEqual(code, 1)
        self.assertEqual(summary["status"], "preflight_failed")
        run_tests.assert_not_called()

    def test_typecheck_failure_stops_gate_before_pytest(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(gate.subprocess, "run", side_effect=[SimpleNamespace(returncode=0), SimpleNamespace(returncode=1)]), \
                    patch.object(gate, "run_tests") as run_tests:
                code = gate.main(["--report-dir", directory])
            summary = json.loads((Path(directory) / "summary.json").read_text(encoding="utf-8"))
        self.assertEqual(code, 1)
        self.assertEqual(summary["status"], "typecheck_failed")
        run_tests.assert_not_called()

    def run_sample_suite(self, source, *, relative_path="test_sample.py", runtime_smoke=False):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sample = root / relative_path
            sample.parent.mkdir(parents=True, exist_ok=True)
            sample.write_text(source, encoding="utf-8")
            report_dir = root / "reports"
            report_dir.mkdir()
            env = dict(os.environ, PYTEST_DISABLE_PLUGIN_AUTOLOAD="1")
            env.pop("PYTEST_ADDOPTS", None)
            env.pop("PYTEST_PLUGINS", None)
            command = (
                "import sys; from pathlib import Path; "
                "sys.path.insert(0, sys.argv[1]); "
                "from scripts.check_nanotrack import run_tests; "
                "raise SystemExit(run_tests([sys.argv[2]], Path(sys.argv[3]), "
                "runtime_smoke=sys.argv[4] == 'True'))"
            )
            result = subprocess.run(
                [sys.executable, "-c", command, str(gate.ROOT), relative_path, str(report_dir), str(runtime_smoke)],
                cwd=root, env=env, capture_output=True, text=True, encoding="utf-8", timeout=30,
            )
            self.assertTrue((report_dir / "summary.json").exists(), result.stdout + result.stderr)
            summary = json.loads((report_dir / "summary.json").read_text(encoding="utf-8"))
            junit = ET.parse(report_dir / "junit.xml")
        return result, summary, junit

    def test_failures_errors_and_skips_are_reported_separately(self):
        result, summary, junit = self.run_sample_suite(
            "import pytest\n"
            "def test_pass(): pass\n"
            "def test_fail(): assert False, 'failure example'\n"
            "def test_skip(): pytest.skip('missing GUI dependency')\n"
            "@pytest.fixture\n"
            "def broken(): raise RuntimeError('setup example')\n"
            "def test_error(broken): pass\n"
        )
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(summary["passed"], 1)
        self.assertEqual(len(summary["failures"]), 1)
        self.assertEqual(len(summary["errors"]), 1)
        self.assertEqual(len(summary["skipped"]), 1)
        self.assertEqual(len(summary["unexpected_skips"]), 1)
        self.assertEqual(len(junit.findall(".//testcase")), 4)

    def test_skip_without_any_failing_test_still_fails_gate(self):
        for source in (
            "import pytest\ndef test_missing_gui(): pytest.skip('PyQt6 is required')\n",
            "import pytest\npytest.skip('missing cv2', allow_module_level=True)\n",
        ):
            with self.subTest(source=source):
                result, summary, _ = self.run_sample_suite(source)
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(len(summary["unexpected_skips"]), 1)

    def test_external_model_smoke_is_optional_until_explicitly_requested(self):
        source = (
            "import unittest\n"
            "class Dam4SamRuntimeSmokeTests(unittest.TestCase):\n"
            "    def test_default_dam4sam_worker_smoke_runs_if_runtime_is_available(self):\n"
            "        self.skipTest('External runtime not installed')\n"
        )
        path = "tests/nanotrack/test_dam4sam_helpers.py"
        result, summary, _ = self.run_sample_suite(source, relative_path=path)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(len(summary["skipped"]), 1)
        self.assertEqual(summary["unexpected_skips"], [])
        result, summary, _ = self.run_sample_suite(source, relative_path=path, runtime_smoke=True)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(len(summary["unexpected_skips"]), 1)


if __name__ == "__main__":
    unittest.main()
