"""Opt-in full 1000-frame MPP/AVI GUI exports, plus deletion/reregistration and cancellation."""

import argparse
import json
import platform
import subprocess
from pathlib import Path

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QPushButton

from export_faults import export_failure
from large_export_probe import ExportProbe
from large_series_probe import source_identity
from stmviewer.ui.main_window import STMViewerMainWindow


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    args.destination.mkdir(parents=True, exist_ok=False)
    report = dict(
        input=source_identity(args.source),
        platform=platform.platform(),
        commit=subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        operations=[],
        exports=[],
    )
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_DontUseNativeDialogs)
    app = QApplication([])
    if app.platformName() != "xcb":
        raise RuntimeError("Require an unobscured X11 display and Qt xcb.")
    window = STMViewerMainWindow()
    probe = ExportProbe(window)
    window.show()
    errors = []
    indices = []

    def save():
        report["rss_peak"] = max(v for t, v in probe.resources.samples)
        (args.destination / "report.json").write_text(
            json.dumps(report, indent=2) + "\n"
        )

    def export(
        group, kind, version, codec="FFV1", contrast="movie", gamma=2, background=255
    ):
        name = f"{group}-{version}" + (f"-{codec}.avi" if kind == "avi" else ".mpp")
        options = dict(
            kind=kind,
            version=version,
            codec=codec,
            contrast=contrast,
            gamma=gamma,
            background=background,
            fps=30,
            annotations=True,
            group=group,
            indices=list(indices),
        )
        row = probe.export(args.destination / name, options)
        report["exports"].append(row)
        print(
            "EXPORT",
            json.dumps({k: v for k, v in row.items() if k != "indices"}),
            flush=True,
        )
        save()
        return row

    def register(name):
        row = probe.operation(
            lambda: probe.widget(QPushButton, "registerFrames").click(),
            kind="registration",
        )
        row["name"] = name
        report["operations"].append(row)
        save()

    def repeat_export(kind, *, cancel_fraction=None, fail=False):
        previous = next(
            row
            for row in report["exports"]
            if row["group"] == "reregistered"
            and row["kind"] == kind
            and row["codec"] == "FFV1"
            and row["status"] == "saved"
        )
        target = Path(previous["file"])
        originals = [source_identity(target)]
        if kind == "mpp":
            originals.append(
                source_identity(target.with_name(target.name + ".stmviewer.json"))
            )
        if fail:
            with export_failure(kind, target, len(indices)) as error:
                result = probe.export(target, previous, expected_error=error)
        else:
            result = probe.export(target, previous, cancel_fraction=cancel_fraction)
        for original in originals:
            assert source_identity(Path(original["source"])) == original
        assert not list(args.destination.glob(".stmviewer-*"))
        report["exports"].append(result)
        save()

    def run():
        try:
            report["operations"].append(
                probe.operation(lambda: probe.open(args.source), kind="import")
            )
            indices.extend(range(probe.number.maximum()))
            register("initial-phase")
            for version in ("original", "aligned"):
                export("full", "mpp", version)
                for codec in ("MJPG", "FFV1"):
                    export(
                        "full",
                        "avi",
                        version,
                        codec,
                        contrast="per_frame" if version == "original" else "movie",
                        gamma=1 if version == "original" else 2,
                        background=0 if version == "original" else 255,
                    )
            # Preserve existing canvas after deleting the reference and the last frame.
            for index in (1, probe.number.maximum() - 1):
                probe.number.setValue(index)
                indices.pop(index - 1)
                probe.widget(QPushButton, "deleteFrame").click()
            for version in ("original", "aligned"):
                export("deleted", "mpp", version)
            export(
                "deleted",
                "avi",
                "aligned",
                "MJPG",
                contrast="per_frame",
                gamma=1,
                background=0,
            )
            export("deleted", "avi", "aligned", "FFV1", background=128)
            register("phase-after-delete")
            export("reregistered", "mpp", "aligned")
            export(
                "reregistered",
                "avi",
                "aligned",
                "MJPG",
                contrast="per_frame",
                background=128,
            )
            export("reregistered", "avi", "aligned", "FFV1", background=255)
            # Cancellation on existing complete files, observed through public progress/UI.
            for kind, fraction in [("mpp", 0.3), ("avi", 0.2), ("avi", 0.8)]:
                repeat_export(kind, cancel_fraction=fraction)
            for kind in ("mpp", "avi"):
                repeat_export(kind, fail=True)
            report["status"] = "completed"
        except Exception as error:
            errors.append(error)
            report["status"] = "failed"
            report["error"] = repr(error)
        finally:
            probe.resources.close()
            save()
            window.grab().save(str(args.destination / "final-window.png"))
            window.close()
            while window.isVisible():
                QTest.qWait(10)
            app.quit()

    QTimer.singleShot(100, run)
    app.exec()
    if errors:
        raise errors[0]


if __name__ == "__main__":
    main()
