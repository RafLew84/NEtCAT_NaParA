import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = ROOT / "scripts/run_python_utf8.ps1"
FIXTURES = Path(__file__).parent / "fixtures"
POWERSHELL = shutil.which("powershell") or shutil.which("pwsh")
MESSAGE = "Zażółć gęślą jaźń — Łódź, źródło, przesunięcie"


@unittest.skipUnless(POWERSHELL, "PowerShell is required for launcher integration tests")
class PythonUtf8LauncherTests(unittest.TestCase):
    def run_powershell(self, script, *arguments, cwd=ROOT):
        env = dict(os.environ, PYTHONUTF8="0", PYTHONIOENCODING="ascii")
        return subprocess.run(
            [POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script), *map(str, arguments)],
            cwd=cwd, env=env, capture_output=True, text=True, encoding="utf-8", timeout=30,
        )

    def test_unicode_source_arguments_and_streams(self):
        with tempfile.TemporaryDirectory(prefix="kontrola-zażółć-") as directory:
            probe = Path(directory) / "próba z polską nazwą.py"
            shutil.copyfile(FIXTURES / "utf8_probe.py", probe)
            result = self.run_powershell(LAUNCHER, "-PythonExe", sys.executable, "-ScriptPath", probe, "0", MESSAGE, "ścieżka ze spacją")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["message"], MESSAGE)
        self.assertEqual(payload["arguments"], [MESSAGE, "ścieżka ze spacją"])
        self.assertEqual(payload["utf8_mode"], 1)
        self.assertIn(MESSAGE, payload["source"])
        for stream in ("stdin_encoding", "stdout_encoding", "stderr_encoding"):
            self.assertEqual(payload[stream].replace("-", "").lower(), "utf8")
        self.assertIn("Błąd próbny: " + MESSAGE, result.stderr)

    def test_nonzero_exit_code_survives_stderr(self):
        result = self.run_powershell(LAUNCHER, "-PythonExe", sys.executable, "-ScriptPath", FIXTURES / "utf8_probe.py", "37")
        self.assertEqual(result.returncode, 37, result.stderr)
        self.assertIn(MESSAGE, result.stderr)

    def test_call_from_powershell_restores_environment_and_decodes_output(self):
        for code in (0, 37):
            with self.subTest(exit_code=code):
                result = self.run_powershell(
                    FIXTURES / "utf8_pipeline.ps1", "-Launcher", LAUNCHER,
                    "-PythonExe", sys.executable, "-Probe", FIXTURES / "utf8_probe.py",
                    "-ExitCode", str(code), cwd=FIXTURES,
                )
                self.assertEqual(result.returncode, code, result.stderr)
                self.assertEqual(json.loads(result.stdout)["message"], MESSAGE)

    def test_module_invocation_passes_options_and_uses_repo_root(self):
        result = self.run_powershell(
            LAUNCHER, "-PythonExe", sys.executable, "-Module", "unittest", "discover",
            "-s", "tests/wayfinder", "-p", "test_*.py", "-v", cwd=FIXTURES,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("OK", result.stderr)
        self.assertIn("test_saved_valid_examples", result.stderr)

    def test_missing_script_or_interpreter_is_a_failure(self):
        result = self.run_powershell(LAUNCHER, "-PythonExe", sys.executable, "-ScriptPath", "missing-script.py")
        self.assertEqual(result.returncode, 1)
        self.assertIn("existing .py file", result.stderr)
        result = self.run_powershell(LAUNCHER, "-PythonExe", "missing-python-for-test.exe", "-ScriptPath", FIXTURES / "utf8_probe.py", "0")
        self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
