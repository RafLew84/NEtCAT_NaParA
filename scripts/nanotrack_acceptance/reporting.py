"""Persistent stage results; independent of Qt and numerical libraries."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
from html import escape
from pathlib import Path
import time
from typing import Iterator


def write_json(path: Path, payload: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def write_status(directory: Path, status: dict) -> None:
    """A single live display, also readable by tools without repeated log output."""
    write_json(directory / "status.json", status)
    text = escape(json.dumps(status, indent=2, ensure_ascii=False))
    refresh = '<meta http-equiv="refresh" content="2">' if status.get("status") == "running" else ""
    page = (f'<!doctype html><html lang="pl"><meta charset="utf-8">{refresh}'
            '<title>NanoTrack — odbiór</title><style>body{font:18px system-ui;max-width:50em;'
            'margin:3em auto;background:#171b21;color:#eef3f8}pre{white-space:pre-wrap}</style>'
            f'<h1>NanoTrack — odbiór</h1><pre>{text}</pre><p>Raport: report.json · Log: worker.log</p></html>')
    temporary = directory / "status.html.tmp"
    temporary.write_text(page, encoding="utf-8")
    temporary.replace(directory / "status.html")


class AcceptanceReport:
    def __init__(self, directory: Path, mode: str, headless: bool):
        self.directory = directory
        self.data: dict = {
            "schema": "nanotrack.acceptance.v1", "mode": mode,
            "gui": "offscreen" if headless else "visible",
            "status": "running", "started_utc": datetime.now(timezone.utc).isoformat(),
            "stages": [], "artifacts": [],
        }
        self.flush()

    def flush(self) -> None:
        write_json(self.directory / "worker-report.json", self.data)

    @contextmanager
    def stage(self, name: str) -> Iterator[dict]:
        entry: dict = {"name": name, "status": "running"}
        self.data["stages"].append(entry)
        self.flush()
        print(f"START {name}", flush=True)
        started = time.monotonic()
        try:
            yield entry
        except Exception as error:
            entry.update(status="failed", error=f"{type(error).__name__}: {error}")
            raise
        else:
            entry["status"] = "passed"
        finally:
            entry["seconds"] = time.monotonic() - started
            self.flush()
            print(f"{entry['status'].upper()} {name}", flush=True)


def supervise(command: list[str], directory: Path, timeout: float, *, cwd: Path) -> int:
    """Wait for our worker, never for a sentinel file; stop it at the deadline."""
    import subprocess

    started = time.monotonic()
    timed_out = False
    interrupted = False
    with (directory / "worker.log").open("w", encoding="utf-8") as log:
        try:
            worker = subprocess.Popen(command, cwd=cwd, stdout=log, stderr=subprocess.STDOUT,
                                      creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            try:
                code = worker.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
                worker.kill()
                code = worker.wait(timeout=10)
            except KeyboardInterrupt:
                interrupted = True
                worker.kill()
                code = worker.wait(timeout=10)
        except OSError as error:
            code = -1
            log.write(f"Worker could not start: {error}\n")
    report_path = directory / "worker-report.json"
    try:
        result = json.loads(report_path.read_text(encoding="utf-8"))
        if not isinstance(result, dict) or not isinstance(result.get("stages"), list) or any(
            not isinstance(stage, dict) for stage in result["stages"]
        ):
            raise ValueError("worker report has an invalid structure")
    except (OSError, ValueError):
        result = {"stages": [], "status": "missing_report"}
    worker_status = result.get("status")
    result.update(worker_status=worker_status, worker_exit_code=code,
                  elapsed_seconds=time.monotonic() - started, timeout_seconds=timeout)
    if timed_out:
        result["status"] = "timeout"
    elif interrupted:
        result["status"] = "cancelled"
    elif code != 0 or worker_status != "passed" or not result.get("stages") or any(
        stage.get("status") != "passed" for stage in result["stages"]
    ):
        result["status"] = "failed"
    else:
        result["status"] = "passed"
    for stage in result.get("stages", []):
        if stage.get("status") == "running":
            stage["status"] = "interrupted"
    write_json(directory / "report.json", result)
    write_status(directory, {"status": result["status"], "seconds": result["elapsed_seconds"],
                             "report": "report.json", "log": "worker.log"})
    print(f"NanoTrack acceptance: {result['status'].upper()} — {directory / 'report.json'}", flush=True)
    return 0 if result["status"] == "passed" else 1
