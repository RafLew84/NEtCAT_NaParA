"""Run preprocessing, Aligned/Expanded geometry or session acceptance with a bounded worker."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import math
from pathlib import Path
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.nanotrack_acceptance.reporting import supervise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("quick", "full", "session", "aligned", "expanded", "particles", "edges", "exclusions"))
    parser.add_argument("--input", type=Path, help="MPP for full, .nanotrack for session")
    parser.add_argument("--report-dir", type=Path, help="New or empty output directory")
    parser.add_argument("--timeout", type=float, help="Total seconds; default 180, full 7200")
    parser.add_argument("--headless", action="store_true", help="Offscreen checks; explicitly not visible GUI acceptance")
    args = parser.parse_args(argv)
    if args.mode in ("full", "session", "particles", "edges", "exclusions") and (args.input is None or not args.input.is_file()):
        parser.error("full/session/particles/edges/exclusions require --input pointing to an existing file")
    if args.mode in ("quick", "aligned", "expanded") and args.input is not None:
        parser.error("quick/aligned/expanded generate their own known sample; use full/session for --input")
    timeout = args.timeout if args.timeout is not None else (7200 if args.mode == "full" else 180)
    if not math.isfinite(timeout) or timeout <= 0:
        parser.error("--timeout must be finite and positive")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]
    directory = (args.report_dir or ROOT / ".scratch/nanotrack-acceptance" / run_id).resolve()
    if directory.exists() and any(directory.iterdir()):
        parser.error("--report-dir must be new or empty; earlier evidence is never overwritten")
    directory.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, "-X", "utf8", "-m", "scripts.nanotrack_acceptance.worker",
               args.mode, "--report-dir", str(directory)]
    if args.input is not None:
        command.extend(("--input", str(args.input.resolve())))
    if args.headless:
        command.append("--headless")
    print(f"NanoTrack acceptance {args.mode}: {directory}\nLive status: {directory / 'status.html'}", flush=True)
    return supervise(command, directory, timeout, cwd=ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
