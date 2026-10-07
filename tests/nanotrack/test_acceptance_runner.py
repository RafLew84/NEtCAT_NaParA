"""Supervise actual subprocesses: crashes, hangs and misleading reports cannot pass."""
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from scripts.nanotrack_acceptance.reporting import supervise


ROOT = Path(__file__).resolve().parents[2]


class AcceptanceRunnerTests(unittest.TestCase):
    def run_worker(self, body, timeout=5):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            worker = root / "worker.py"
            worker.write_text("import json, pathlib, sys, time\n" + body, encoding="utf-8")
            code = supervise([sys.executable, str(worker)], root, timeout, cwd=root)
            report = json.loads((root / "report.json").read_text(encoding="utf-8"))
            self.assertTrue((root / "worker.log").exists())
            self.assertTrue((root / "status.html").exists())
            status = json.loads((root / "status.json").read_text(encoding="utf-8"))
            self.assertEqual(status["status"], report["status"])
            return code, report

    def test_crash_without_completion_file_fails_promptly(self):
        code, report = self.run_worker("sys.exit(7)\n")
        self.assertEqual(code, 1)
        self.assertEqual(report["worker_exit_code"], 7)
        self.assertEqual(report["status"], "failed")

    def test_hung_worker_is_stopped_and_running_stage_is_interrupted(self):
        source = (
            "pathlib.Path('worker-report.json').write_text(json.dumps({'status':'running', "
            "'stages':[{'name':'bm3d','status':'running'}]}))\n"
            "time.sleep(30)\n"
        )
        code, report = self.run_worker(source, timeout=1)
        self.assertEqual(code, 1)
        self.assertEqual(report["status"], "timeout")
        self.assertEqual(report["stages"][0]["status"], "interrupted")
        self.assertLess(report["elapsed_seconds"], 10)

    def test_only_successful_exit_with_completed_stages_passes(self):
        for stages, exit_code, expected in (
            ([{"name": "save_open", "status": "passed"}], 0, 0),
            ([{"name": "save_open", "status": "failed"}], 0, 1),
            ([{"name": "save_open", "status": "passed"}], 3, 1),
            ([], 0, 1),
        ):
            with self.subTest(stages=stages, exit_code=exit_code):
                payload = json.dumps({"status": "passed", "stages": stages})
                body = f"pathlib.Path('worker-report.json').write_text({payload!r})\nsys.exit({exit_code})\n"
                code, _ = self.run_worker(body)
                self.assertEqual(code, expected)

    def test_malformed_report_fails_closed(self):
        for payload in ('not json', '{"status":"passed","stages":null}', '{"status":"passed","stages":[1]}'):
            with self.subTest(payload=payload):
                code, report = self.run_worker(f"pathlib.Path('worker-report.json').write_text({payload!r})\n")
                self.assertEqual(code, 1)
                self.assertEqual(report["status"], "failed")

    def test_public_cli_rejects_reusing_a_report_directory(self):
        with TemporaryDirectory() as directory:
            target = Path(directory) / "report.json"
            target.write_text("original evidence", encoding="utf-8")
            process = subprocess.run([sys.executable, str(ROOT / "scripts/run_nanotrack_acceptance.py"),
                                      "quick", "--report-dir", directory], capture_output=True, text=True, timeout=10)
            self.assertEqual(process.returncode, 2)
            self.assertEqual(target.read_text(encoding="utf-8"), "original evidence")

    def test_full_scenario_rejects_in_place_annotation_changes(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt6.QtWidgets import QApplication
        from nanotrack.ui.main_window import NanoTrackMainWindow
        from nanotrack_test_fixtures import sample_mpp_path
        from scripts.nanotrack_acceptance.reporting import AcceptanceReport
        from scripts.nanotrack_acceptance.scenarios import Scenarios

        app = QApplication.instance() or QApplication([])
        window = NanoTrackMainWindow()
        try:
            with TemporaryDirectory() as directory:
                report = AcceptanceReport(Path(directory), "full", True)
                scenario = Scenarios(window, report)

                def corrupt_annotation():
                    window.current_tracks()[0].label = "Unexpected change during preprocessing"

                with patch.object(scenario, "process", side_effect=corrupt_annotation), patch.object(
                    window, "current_denoised_frames", side_effect=lambda: window.current_sequence().raw_frames.copy(),
                ):
                    with self.assertRaisesRegex(AssertionError, "label"):
                        scenario.full(sample_mpp_path())
                self.assertEqual(report.data["stages"][-1]["status"], "failed")
                self.assertEqual(report.data["stages"][-1]["name"], "preservation")
        finally:
            window.close()
            app.processEvents()
