"""Run the same NanoTrack quality gate locally and on the Windows CI runner."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]
TEST_PATHS = ("tests/nanotrack", "tests/moltrack/test_stm_series_viewer.py")
REQUIRED_MODULES = (
    "pytest", "numpy", "scipy", "skimage", "PyQt6.QtCore",
    "PyQt6.QtWidgets", "pyqtgraph", "cv2",
)
RUNTIME_SMOKE_TESTS = frozenset({
    "tests/nanotrack/test_dam4sam_helpers.py::Dam4SamRuntimeSmokeTests::test_default_dam4sam_worker_smoke_runs_if_runtime_is_available",
    "tests/nanotrack/test_samurai_worker.py::SamuraiRuntimeSmokeTests::test_default_samurai_worker_smoke_runs_if_runtime_is_available",
    "tests/nanotrack/test_muge_backend.py::MugeSubprocessBackendTests::test_real_backend_smoke_when_local_runtime_available",
})
RUNTIME_SKIP = "External model smoke test; enable with --runtime-smoke."
OPTIONAL_GUI_SKIPS = frozenset({
    "No local YOLO models available for the GUI test.",
    "Right sidebar does not overflow in this Qt environment.",
})


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def probe_environment() -> dict:
    """Import actual modules (including DLLs), then exercise the Qt platform."""
    result = {"python": sys.version, "executable": sys.executable, "modules": {}, "errors": []}
    modules = {}
    for name in REQUIRED_MODULES:
        try:
            module = importlib.import_module(name)
            modules[name] = module
            result["modules"][name] = str(getattr(module, "__version__", getattr(module, "PYQT_VERSION_STR", "imported")))
        except Exception as error:
            result["errors"].append(f"{name}: {type(error).__name__}: {error}")
    if not result["errors"]:
        if not callable(getattr(modules["cv2"], "findTransformECC", None)):
            result["errors"].append("cv2: findTransformECC is unavailable")
    if not result["errors"]:
        try:
            widgets = modules["PyQt6.QtWidgets"]
            app = widgets.QApplication.instance() or widgets.QApplication([])
            widget = widgets.QWidget()
            widget.resize(32, 32)
            if widget.grab().isNull():
                raise RuntimeError("Qt could not render an offscreen widget")
            app.processEvents()
            widget.close()
            result["qt_platform"] = app.platformName()
            result["qt_version"] = modules["PyQt6.QtCore"].QT_VERSION_STR
        except Exception as error:
            result["errors"].append(f"Qt platform: {type(error).__name__}: {error}")
    return result


def allowed_skip(nodeid: str, reason: str, runtime_smoke: bool) -> bool:
    if not runtime_smoke and nodeid in RUNTIME_SMOKE_TESTS and reason == RUNTIME_SKIP:
        return True
    return (
        nodeid.startswith("tests/nanotrack/test_main_window.py::")
        and reason in OPTIONAL_GUI_SKIPS
    )


class GateResults:
    def __init__(self, runtime_smoke: bool = False) -> None:
        self.runtime_smoke = runtime_smoke
        self.passed = 0
        self.failures: list[dict] = []
        self.errors: list[dict] = []
        self.skipped: list[dict] = []

    def pytest_collection_modifyitems(self, items) -> None:
        import pytest

        if not self.runtime_smoke:
            for item in items:
                if item.nodeid in RUNTIME_SMOKE_TESTS:
                    item.add_marker(pytest.mark.skip(reason=RUNTIME_SKIP))

    def pytest_collectreport(self, report) -> None:
        if report.failed:
            self.errors.append({"nodeid": report.nodeid, "phase": "collection", "detail": str(report.longrepr)})
        elif report.skipped:
            self._record_skip(report, "collection")

    def _record_skip(self, report, phase: str) -> None:
        reason = str(report.longrepr[2]) if isinstance(report.longrepr, tuple) else str(report.longrepr)
        reason = reason.removeprefix("Skipped: ")
        self.skipped.append({
            "nodeid": report.nodeid,
            "phase": phase,
            "reason": reason,
            "allowed": allowed_skip(report.nodeid, reason, self.runtime_smoke),
        })

    def pytest_runtest_logreport(self, report) -> None:
        if report.failed:
            target = self.failures if report.when == "call" else self.errors
            target.append({"nodeid": report.nodeid, "phase": report.when, "detail": str(report.longrepr)})
        elif report.skipped:
            self._record_skip(report, report.when)
        elif report.when == "call" and report.passed:
            self.passed += 1

    @property
    def unexpected_skips(self) -> list[dict]:
        return [item for item in self.skipped if not item["allowed"]]

    def pytest_sessionfinish(self, session, exitstatus) -> None:
        # A missing GUI/ECC dependency must never turn a green gate into all skips.
        if exitstatus == 0 and self.unexpected_skips:
            session.exitstatus = 1

    def pytest_terminal_summary(self, terminalreporter) -> None:
        terminalreporter.section("NanoTrack quality gate")
        terminalreporter.write_line(
            f"PASS {self.passed} | FAIL {len(self.failures)} | ERROR {len(self.errors)} | "
            f"SKIP {len(self.skipped)} (unexpected: {len(self.unexpected_skips)})"
        )
        for item in self.skipped:
            label = "optional" if item["allowed"] else "ERROR: unexpected skip"
            terminalreporter.write_line(f"{label}: {item['nodeid']}: {item['reason']}")


def run_tests(paths: list[str], report_dir: Path, *, runtime_smoke: bool = False) -> int:
    import pytest

    results = GateResults(runtime_smoke)
    exit_code = int(pytest.main([
        *paths, "-q", "-ra", "--tb=short", "-p", "no:cacheprovider",
        "-o", "addopts=", f"--junitxml={report_dir / 'junit.xml'}",
    ], plugins=[results]))
    write_json(report_dir / "summary.json", {
        "status": "passed" if exit_code == 0 else "failed",
        "exit_code": exit_code,
        "test_paths": paths,
        "runtime_smoke": runtime_smoke,
        "passed": results.passed,
        "failures": results.failures,
        "errors": results.errors,
        "skipped": results.skipped,
        "unexpected_skips": results.unexpected_skips,
    })
    return exit_code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-dir", type=Path, help="New or empty directory for environment.json, summary.json and junit.xml")
    parser.add_argument("--runtime-smoke", action="store_true", help="Also require the three external-model smoke tests to run")
    parser.add_argument("--probe-output", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    os.environ["PYTHONIOENCODING"] = "utf-8"
    os.environ["PYTHONUTF8"] = "1"
    # Keep unrelated globally installed pytest plugins/options out of this gate.
    os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    os.environ.pop("PYTEST_ADDOPTS", None)
    os.environ.pop("PYTEST_PLUGINS", None)
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    if args.probe_output:
        result = probe_environment()
        write_json(args.probe_output, result)
        return 1 if result["errors"] else 0

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]
    report_dir = (args.report_dir or ROOT / ".scratch" / "nanotrack-quality" / run_id).resolve()
    if report_dir.exists() and any(report_dir.iterdir()):
        parser.error(f"Report directory must be empty: {report_dir}")
    report_dir.mkdir(parents=True, exist_ok=True)
    print(f"NanoTrack reports: {report_dir}", flush=True)
    try:
        probe = subprocess.run([
            sys.executable, str(Path(__file__).resolve()),
            "--probe-output", str(report_dir / "environment.json"),
        ], timeout=60, check=False)
        error = None if probe.returncode == 0 else f"Dependency/Qt preflight failed (exit {probe.returncode})."
    except (OSError, subprocess.TimeoutExpired) as exc:
        error = f"Dependency/Qt preflight failed: {exc}"
    if error:
        environment_file = report_dir / "environment.json"
        if environment_file.exists():
            details = json.loads(environment_file.read_text(encoding="utf-8"))
            for detail in details.get("errors", []):
                print(detail, file=sys.stderr)
        print(error, file=sys.stderr)
        write_json(report_dir / "summary.json", {"status": "preflight_failed", "exit_code": 1, "error": error})
        return 1
    print("Required dependencies and offscreen Qt: OK", flush=True)
    return run_tests(list(TEST_PATHS), report_dir, runtime_smoke=args.runtime_smoke)


if __name__ == "__main__":
    raise SystemExit(main())
