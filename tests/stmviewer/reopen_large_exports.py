"""Reopen every measured MPP through GUI while a large registered series is loaded."""

import argparse
import json
from pathlib import Path

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QLabel, QPushButton

from large_series_probe import GuiProbe
from stmviewer.ui.main_window import STMViewerMainWindow


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    source = json.loads(args.report.read_text())
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_DontUseNativeDialogs)
    app = QApplication([])
    if app.platformName() != "xcb":
        raise RuntimeError("Require Qt xcb/X11.")
    window = STMViewerMainWindow()
    probe = GuiProbe(window)
    window.show()
    results, errors = [], []

    def run():
        try:
            probe.operation(
                lambda: probe.open(Path(source["input"]["source"])), kind="import"
            )
            probe.operation(
                lambda: probe.widget(QPushButton, "registerFrames").click(),
                kind="registration",
            )
            # Largest reopen first, preserving both large old buffers during transactional import.
            rows = [
                r
                for r in source["exports"]
                if r["kind"] == "mpp" and r["status"] == "saved"
            ]
            rows.sort(key=lambda r: r["source_bytes"], reverse=True)
            for row in rows:
                result = probe.operation(
                    lambda: probe.open(Path(row["file"])), kind="import"
                )
                assert probe.number.maximum() == row["frames"]
                result.update(
                    file=row["file"],
                    metadata=probe.widget(QLabel, "metadataImportInfo").text(),
                )
                assert "wczytano" in result["metadata"]
                probe.select(row["frames"])
                QTest.qWait(100)
                window.grab().save(
                    str(args.report.with_name(Path(row["file"]).stem + "-reopened.png"))
                )
                results.append(result)
                print(json.dumps(result), flush=True)
        except Exception as error:
            errors.append(repr(error))
        finally:
            probe.resources.close()
            report = dict(
                operations=results,
                errors=errors,
                rss_peak=max(v for t, v in probe.resources.samples),
            )
            args.report.with_name("gui-reopen.json").write_text(
                json.dumps(report, indent=2) + "\n"
            )
            window.close()
            while window.isVisible():
                QTest.qWait(10)
            app.quit()

    QTimer.singleShot(100, run)
    app.exec()
    if errors:
        raise RuntimeError(errors)


if __name__ == "__main__":
    main()
