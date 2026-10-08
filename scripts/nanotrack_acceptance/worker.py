"""Private worker: the public supervisor handles native crashes and deadlines."""
from __future__ import annotations

import argparse
from importlib.metadata import version
import os
from pathlib import Path
import subprocess
import sys
import traceback

from scripts.nanotrack_acceptance.reporting import AcceptanceReport, write_status


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("quick", "full", "session", "aligned", "expanded", "particles", "edges"))
    parser.add_argument("--input", type=Path)
    parser.add_argument("--report-dir", type=Path, required=True)
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args()
    os.environ["QT_QPA_PLATFORM"] = "offscreen" if args.headless else "windows"
    report = AcceptanceReport(args.report_dir, args.mode, args.headless)
    try:
        from PyQt6.QtCore import QTimer
        from PyQt6.QtWidgets import QApplication, QMessageBox, QProgressDialog
        from nanotrack.app import configure_pyqtgraph
        from nanotrack.ui.main_window import NanoTrackMainWindow
        from scripts.nanotrack_acceptance.scenarios import Scenarios

        report.data["environment"] = {"python": sys.version, **{
            name: version(name) for name in ("numpy", "scipy", "scikit-image", "PyQt6", "pyqtgraph")
        }}
        if args.mode in ("quick", "full"):
            report.data["environment"]["bm3d"] = version("bm3d")
        report.data["code"] = {
            "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
            "tracked_changes": subprocess.check_output(["git", "status", "--short", "--untracked-files=no"], text=True).splitlines(),
        }
        configure_pyqtgraph()
        app = QApplication([])
        window = NanoTrackMainWindow()
        window.resize(1500, 950)
        window.show()
        scenario = Scenarios(window, report)

        def monitor() -> None:
            modal = app.activeModalWidget()
            if isinstance(modal, QMessageBox):
                report.data.setdefault("dialogs", []).append(modal.text())
                report.flush()
                modal.reject()
            stages = report.data["stages"]
            status = {"stage": stages[-1]["name"] if stages else "starting", "status": report.data["status"]}
            if isinstance(modal, QProgressDialog):
                status.update(operation=modal.windowTitle(), current=modal.value(), total=modal.maximum())
            write_status(args.report_dir, status)

        timer = QTimer()
        timer.timeout.connect(monitor)
        timer.start(1000)

        def run() -> None:
            try:
                if args.mode == "quick":
                    scenario.quick()
                elif args.mode == "aligned":
                    from scripts.nanotrack_acceptance.aligned import run as run_aligned
                    run_aligned(scenario)
                elif args.mode == "expanded":
                    from scripts.nanotrack_acceptance.expanded import run as run_expanded
                    run_expanded(scenario)
                elif args.mode == "particles":
                    from scripts.nanotrack_acceptance.particles import run as run_particles
                    assert args.input is not None
                    run_particles(scenario, args.input)
                elif args.mode == "edges":
                    from scripts.nanotrack_acceptance.edges import run as run_edges
                    assert args.input is not None
                    run_edges(scenario, args.input)
                else:
                    assert args.input is not None
                    if args.mode == "full":
                        scenario.full(args.input)
                    else:
                        scenario.session(args.input)
                scenario.check_dialogs()
                report.data["status"] = "passed"
            except Exception:
                report.data.update(status="failed", exception=traceback.format_exc())
            finally:
                report.flush()
                monitor()
                window.close()
                app.exit(0 if report.data["status"] == "passed" else 1)

        QTimer.singleShot(250, run)
        return app.exec()
    except Exception:
        report.data.update(status="failed", exception=traceback.format_exc())
        report.flush()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
