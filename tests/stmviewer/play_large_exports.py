"""Opt-in VLC playback of complete exported AVI files on an isolated X11 screen.

Captures two process-relative times for visual review (startup can delay video).
Decoder fidelity is checked by
check_large_exports.py; screenshots are not proof of physical-monitor refresh.
"""

import argparse
import json
from pathlib import Path
import subprocess
from time import perf_counter

from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--vlc", default="vlc")
    args = parser.parse_args()
    source = json.loads(args.report.read_text())
    app = QApplication([])
    if app.platformName() != "xcb":
        raise RuntimeError("Require an unobscured X11 screen, Qt xcb.")
    destination = args.report.parent / "vlc"
    destination.mkdir(exist_ok=False)
    results = []
    try:
        for row in source["exports"]:
            if row["kind"] != "avi" or row["status"] != "saved":
                continue
            name = Path(row["file"]).stem
            duration = row["frames"] / row["fps"]
            snapshots = {"early": 2.0, "late": duration - 1}
            started = perf_counter()
            with (destination / f"{name}.log").open("wb") as log:
                process = subprocess.Popen(
                    [
                        args.vlc,
                        "--config=/dev/null",
                        "--no-one-instance",
                        "--no-qt-privacy-ask",
                        "--no-metadata-network-access",
                        "--no-video-title-show",
                        "--no-audio",
                        "--avcodec-hw=none",
                        "--vout=xcb_x11",
                        "--play-and-exit",
                        row["file"],
                    ],
                    stdout=log,
                    stderr=subprocess.STDOUT,
                )
                try:
                    while process.poll() is None:
                        elapsed = perf_counter() - started
                        if elapsed > duration + 20:
                            raise TimeoutError(row["file"])
                        for label, when in list(snapshots.items()):
                            if elapsed >= when:
                                image = app.primaryScreen().grabWindow(0)
                                assert not image.isNull()
                                image.save(str(destination / f"{name}-{label}.png"))
                                del snapshots[label]
                        QTest.qWait(50)
                    elapsed = perf_counter() - started
                    assert process.returncode == 0, (row["file"], process.returncode)
                    assert not snapshots and elapsed >= duration - 0.5, (
                        row["file"],
                        elapsed,
                    )
                finally:
                    if process.poll() is None:
                        process.terminate()
                        process.wait(timeout=10)
            results.append(
                dict(
                    file=row["file"],
                    expected_seconds=duration,
                    process_seconds=elapsed,
                    exit_code=process.returncode,
                )
            )
            print(json.dumps(results[-1]), flush=True)
    finally:
        (destination / "playback.json").write_text(json.dumps(results, indent=2) + "\n")


if __name__ == "__main__":
    main()
